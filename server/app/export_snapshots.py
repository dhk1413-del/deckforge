"""范围预览与不可变 PPTX 快照；只打包既有资产，不调用模型。"""
import hashlib
import json
import os
import shutil
from . import config, db, editppt_engine, export_pptx, pipeline


def plan(pid, items, kind='image', page_nos=None):
    if kind != 'image':
        raise ValueError('导出类型只支持 image；可编辑版请走「图片转可编辑」的 editppt 精细重建')
    if page_nos is not None and (not isinstance(page_nos, list) or any(type(n) is not int for n in page_nos) or not page_nos or len(set(page_nos)) != len(page_nos) or
                                set(page_nos) - {p['page_no'] for p in items if p['keep']}):
        raise ValueError('所选页范围无效，请重新选择参与页')
    wanted = [p for p in items if p['keep'] and (page_nos is None or p['page_no'] in page_nos)]
    included, excluded = [], []
    for p in sorted(wanted, key=lambda p: (p['display_order'], p['page_no'])):
        current = next((v for v in p['versions'] if v['id'] == p['current_version_id']), None)
        entry = dict(slide_id=p['slide_id'], page_no=p['page_no'], display_order=p['display_order'],
                     version_id=p['current_version_id'], version_number=current['number'] if current else None,
                     content_stale=p['content_stale'], config_stale=p['config_stale'])
        reason = ('页面状态：' + {'pending':'未就绪','failed':'失败','interrupted':'中断','running':'运行中','queued':'排队中'}.get(p['status'], p['status'])) if p['status'] != 'done' else ''
        if not reason and not p['image_url']: reason = '图片资产缺失'
        if not reason and not current: reason = '当前版本记录缺失'
        if not reason and p['review_required']: reason = '生成图片待核对'
        (excluded if reason else included).append(dict(entry, reason=reason) if reason else entry)
    engine = editppt_engine.available()
    capabilities = [dict(kind='image', label='图片版', available=True, reason='本机装配既有整页图'),
                    dict(kind='editable_hi', label='选择页转文字可编辑（图片→可编辑，editppt 精细重建）',
                         available=bool(engine['ok']), reason=engine['reason'])]
    basis = dict(kind=kind, included=included, excluded=excluded,
                 assets=[(p['slide_id'], p['image_path'], p.get('native_scene_json'), p.get('reviewed_image')) for p in wanted])
    token = hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return dict(project_id=pid, kind=kind, page_nos=page_nos, included=included, excluded=excluded,
                snapshot_token=token, capabilities=capabilities, note='导出即固定为导出时刻的版本快照；打包不调用模型、不新增模型费用')


def create(pid, preview):
    proj = dict(db.q1('SELECT * FROM projects WHERE id=?', (pid,)))
    if not preview['included']: raise ValueError('范围内没有可导出的已核对页面')
    if not next(c for c in preview['capabilities'] if c['kind']==preview['kind'])['available']:
        raise ValueError('当前输出类型不可用')
    eid = db.uid('e')
    root = os.path.join(config.FILES_DIR, 'exports', eid)
    os.makedirs(root, exist_ok=False)
    rows = []
    try:
        for entry in preview['included']:
            row = dict(db.q1('SELECT * FROM slides WHERE id=? AND project_id=?', (entry['slide_id'], pid)))
            if row['current_version_id'] != entry['version_id'] or row['status'] != 'done' or not row['keep']:
                raise ValueError('当前版本或页面状态已变化，请重新确认导出')
            frozen = os.path.join(root, str(entry['page_no']) + os.path.splitext(row['image_path'])[1])
            shutil.copyfile(row['image_path'], frozen)
            row['image_path'] = frozen
            rows.append(row)
        name = pipeline._safe_name(proj['title']) + '_' + preview['kind'] + '_' + eid + '.pptx'
        path = os.path.join(root, name)
        if preview['kind'] != 'image':
            raise ValueError('导出类型只支持 image')
        meta = export_pptx.export_image_pptx(proj, rows, path)
        rec = dict(id=eid, project_id=pid, kind=preview['kind'], path=path, pages=meta['pages'],
                   editable_pages_json=json.dumps(meta['editable_pages']), passthrough_pages_json=json.dumps(meta['passthrough_pages']),
                   snapshot_json=json.dumps(preview['included'], ensure_ascii=False), size_bytes=os.path.getsize(path), created_at=db.now())
        db.insert('exports', rec)
        return response(rec)
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise


def response(rec):
    return dict(id=rec['id'], project_id=rec['project_id'], kind=rec['kind'], pages=rec['pages'],
                file=pipeline._files_url(rec['path']) if os.path.isfile(rec['path'] or '') else '',
                size_bytes=rec['size_bytes'], created_at=rec['created_at'],
                snapshot=json.loads(rec.get('snapshot_json') or '[]'), editable_pages=json.loads(rec['editable_pages_json']),
                passthrough_pages=json.loads(rec['passthrough_pages_json']))
