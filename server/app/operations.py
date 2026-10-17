"""操作报价、持久幂等键与项目成本解释；不提供余额或支付。"""
import asyncio
import hashlib
import json
from contextvars import ContextVar
from functools import wraps

from fastapi import HTTPException
from . import config, db, providers

submission_key = ContextVar('submission_key', default=None)
_submit_lock = asyncio.Lock()


def snapshot(pid, payload):
    project = db.q1('SELECT * FROM projects WHERE id=?', (pid,))
    if not project:
        raise HTTPException(404, '项目不存在')
    action = payload.get('operation')
    if action not in ('generate', 'regenerate', 'editable'):
        raise HTTPException(400, '操作必须为 generate / regenerate / editable')
    rows = [dict(r) for r in db.q('SELECT * FROM slides WHERE project_id=? ORDER BY page_no', (pid,))]
    pages = payload.get('page_nos')
    if pages is None:
        pages = [r['page_no'] for r in rows if r['keep']]
    if not isinstance(pages, list) or not pages or any(type(n) is not int for n in pages):
        raise HTTPException(400, '请选择有效页号')
    pages = sorted(set(pages))
    chosen = [r for r in rows if r['page_no'] in pages]
    if len(chosen) != len(pages) or (action == 'regenerate' and len(pages) != 1):
        raise HTTPException(400, '页面范围无效')
    if action == 'editable' and any(not r['image_path'] for r in chosen):
        raise HTTPException(400, '所选页面缺少图片，不能转换')
    style = payload.get('style_pack_id') or project['style_pack_id'] or 'tech-deepblue'
    size = payload.get('size') or project['size'] or '2K'
    picked = providers.pick_image_provider()
    # data_chart 使用确定性本地绘制，不调用生图供应商。
    billable = [] if action == 'editable' or not picked else [r['page_no'] for r in chosen if r['layout'] != 'data_chart']
    price = None if action == 'editable' else (picked or {}).get('unit_price_cny', 0.0)
    total = None if price is None else round(len(billable) * price, 4)
    cfg = {'providers': config.image_providers(with_keys=True), 'priority': config.priority(),
           'network': config.network_mode(), 'proxy': config.http_proxy_url()}
    # 配置指纹只存 hash，不落库密钥。转换同样绑定引擎选择、输入资产与续跑模式。
    basis = dict(project_id=pid, operation=action, pages=pages, style=style, size=size,
                 revisions={r['id']: r['content_revision'] for r in chosen},
                 assets=[(r['image_path'], r['current_version_id']) for r in chosen] if action == 'editable' else [],
                 confirmed=project['content_confirmed_at'], keep=[r['keep'] for r in chosen],
                 engine=payload.get('engine', 'editppt'), resume=bool(payload.get('resume')), config=cfg)
    fingerprint = hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return dict(operation=action, operation_name={'generate':'整套 / 所选页生成','regenerate':'单页重生成 / AI 优化','editable':'图片转可编辑'}[action],
                page_nos=pages, final_scope=pages, content_revisions=basis['revisions'], style_revision=style,
                page_versions=[dict(page_no=r['page_no'], display_order=r.get('display_order') or r['page_no'],
                    version_id=r.get('current_version_id'), version_number=next((i for i,v in enumerate(db.q(
                        'SELECT id FROM slide_versions WHERE slide_id=? ORDER BY rowid', (r['id'],)),1)
                        if v['id']==r.get('current_version_id')),None)) for r in chosen] if action=='editable' else [],
                mode='精细重建（续跑跳过已完成页）' if action == 'editable' and payload.get('resume') else '精细重建' if action == 'editable' else '图片生成 · '+size,
                provider='editppt' if action == 'editable' else (picked or {}).get('id','local_render'),
                unit_price_cny=price, billable_pages=billable, total_cny=total,
                cancellable=True, estimated_time='约 13 分钟 / 页' if action == 'editable' else '受供应商响应与重试影响，暂无可靠预计耗时',
                price_note=('本机模型额度费用无法核实；账本金额记 0，不代表免费' if action == 'editable'
                            else '单价未配置；账本金额记 0，不代表免费' if price is None
                            else '本地兜底 / 确定性图表费用为 0；其余页按已配置单价估算'),
                failure_policy='账本记录本系统可核实的调用成本；失败不承诺退款。供应商失败调用或本机模型额度费用无法核实，不视为免费。'), fingerprint


def quote(pid, payload):
    result, fingerprint = snapshot(pid, payload)
    result['quote_id'] = db.uid('q')
    db.insert('operation_quotes', dict(id=result['quote_id'], project_id=pid, fingerprint=fingerprint,
                                      body_json=json.dumps(result, ensure_ascii=False)))
    return result


def lookup(pid, key):
    row = db.q1('SELECT * FROM operation_submissions WHERE id=? AND project_id=?', (key,pid))
    if not row:
        raise HTTPException(404, '未找到此幂等提交')
    if row['response_json']:
        return json.loads(row['response_json'])
    if row['job_id']:
        return dict(job_id=row['job_id'], recovered=True)
    raise HTTPException(409, '提交结果尚未确定，请继续按同一幂等键查询；不要创建新提交')


def confirmed(action):
    def decorate(fn):
        @wraps(fn)
        async def wrapped(pid, *args, **kwargs):
            payload = kwargs.get('payload')
            if payload is None:
                payload = args[-1] if args and isinstance(args[-1], dict) else {}
            payload = dict(payload)
            page = kwargs.get('page_no', args[0] if action == 'regenerate' and args else None)
            params = dict(payload, operation=action)
            if page is not None:
                params['page_nos'] = [page]
            key = payload.get('idempotency_key')
            async with _submit_lock:
                if key:
                    if not isinstance(key,str) or not 8 <= len(key) <= 200:
                        raise HTTPException(400,'幂等键格式无效')
                    old = db.q1('SELECT * FROM operation_submissions WHERE id=?',(key,))
                    if old:
                        saved=json.loads(old['quote_json'])
                        if old['project_id'] != pid or saved['operation'] != action or (page is not None and saved['page_nos'] != [page]):
                            raise HTTPException(409,'幂等键已用于其他操作')
                        return lookup(pid,key)
                current, fingerprint = snapshot(pid,params)
                qid = payload.get('quote_id')
                if qid:
                    saved = db.q1('SELECT * FROM operation_quotes WHERE id=? AND project_id=?',(qid,pid))
                    if not saved or saved['fingerprint'] != fingerprint:
                        raise HTTPException(409,'报价已失效，请重新获取报价并确认')
                    if not key:
                        raise HTTPException(400,'确认提交必须携带幂等键')
                elif action == 'editable' or providers.pick_image_provider():
                    raise HTTPException(428,'请先获取服务端报价并确认操作')
                # 零 key 旧客户端兼容；新客户端所有操作一律报价。
                if key:
                    conn=db.connect()
                    cur=conn.execute('INSERT OR IGNORE INTO operation_submissions(id,project_id,fingerprint,quote_json,created_at) VALUES(?,?,?,?,?)',
                                     (key,pid,fingerprint,json.dumps(current,ensure_ascii=False),db.now()))
                    if not cur.rowcount:
                        return lookup(pid,key)
                token=submission_key.set(key)
                pinned=providers.quoted_provider.set((True, providers.pick_image_provider()))
                try:
                    result = await fn(pid,*args,**kwargs)
                    if key:
                        db.x('UPDATE operation_submissions SET response_json=? WHERE id=?',(json.dumps(result,ensure_ascii=False),key))
                    return result
                except BaseException:
                    # 任务已经登记时永远保留键；仅确定尚未建任务时可撤回预留。
                    if key:
                        db.x('DELETE FROM operation_submissions WHERE id=? AND job_id IS NULL',(key,))
                    raise
                finally:
                    submission_key.reset(token)
                    providers.quoted_provider.reset(pinned)
        return wrapped
    return decorate


def ledger(pid):
    project=db.q1('SELECT title FROM projects WHERE id=?',(pid,))
    items=[dict(r) for r in db.q('SELECT * FROM usage_log WHERE project_id=? ORDER BY ts DESC',(pid,))]
    for item in items:
        item['billing_status']='实记成本' if item['cny'] else '失败（记录金额 0，外部费用未知）' if not item['ok'] else '本地免费' if item['provider']=='local_render' else '金额 0（不代表免费）'
    tasks=[]
    for row in db.q('SELECT * FROM operation_submissions WHERE project_id=? ORDER BY created_at DESC',(pid,)):
        q=json.loads(row['quote_json']); job=db.q1('SELECT * FROM jobs WHERE id=?',(row['job_id'],))
        details=[i for i in items if i['job_id']==row['job_id']]
        pages=[]
        for n in q['page_nos']:
            logs=[i for i in details if i['page_no']==n]
            terminal=job and job['status'] in ('done','failed','cancelled','interrupted')
            pages.append(dict(page_no=n,items=logs,status='已记录调用' if logs else '转换额度费用未知（无元计费记录）' if q['operation']=='editable' and terminal else '未执行 / 未计费' if terminal else '执行状态待确认',cny=round(sum(i['cny'] for i in logs),4)))
        tasks.append(dict(job_id=row['job_id'],operation=q['operation_name'],status=job['status'] if job else '提交状态待确认',pages=pages,total_cny=round(sum(i['cny'] for i in details),4)))
    return dict(project_id=pid,title=project['title'] if project else '已删除项目',total_cny=round(sum(i['cny'] for i in items),4),tasks=tasks,items=items,
                note='金额是本系统记录成本，非支付实扣凭证；未填单价时金额记 0，不代表免费。历史无任务关联的记录保留在明细。')
