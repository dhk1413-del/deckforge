/** 用量账本：本月成本 + 按动作/供应商汇总 + 明细表（金额/耗时等宽右对齐） */
import { useMemo, useState } from 'react'
import { getUsage, getProjectUsage } from '../api'
import { useAsync } from '../hooks/useAsync'
import { cn, cny, fmtTime, ms } from '../lib/format'
import { Metric } from '../components/Metric'
import { EmptyState, ErrorState, Loading } from '../components/StateBlock'
import type { UsageRange } from '../types'

const RANGES: Array<{ key: UsageRange; label: string }> = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'all', label: '全部' },
]

export function UsagePage() {
  const [projectId,setProjectId]=useState('')
  const ledger=useAsync(()=>projectId?getProjectUsage(projectId):Promise.resolve(null),[projectId])
  const [range, setRange] = useState<UsageRange>('month')
  // 明细默认只显示最近 10 条：266 行的整表会让页面高到永远拉不到底
  const [expanded, setExpanded] = useState(false)
  const usage = useAsync(() => getUsage(range), [range])
  const data = usage.data
  const rows = data?.items ?? []

  const stats = useMemo(() => {
    const items = data?.items ?? []
    const count = items.length
    const avgLatency = count ? Math.round(items.reduce((s, i) => s + (i.latency_ms ?? 0), 0) / count) : 0
    const failures = items.filter((i) => !i.ok).length
    const genCount =
      data?.by_action?.find((a) => a.action === 'generate')?.count ??
      data?.by_action?.reduce((s, a) => s + a.count, 0) ??
      0
    const maxAction = Math.max(1, ...(data?.by_action ?? []).map((a) => a.cny))
    const maxProvider = Math.max(1, ...(data?.by_provider ?? []).map((p) => p.cny))
    return { count, avgLatency, failures, genCount, maxAction, maxProvider }
  }, [data])

  const label = RANGES.find((r) => r.key === range)?.label ?? '本月'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="m-0 text-h1 font-semibold">用量</h1>
        </div>
        <span className="flex-1" />
        <div className="tabs">
          {RANGES.map((r) => (
            <button
              key={r.key}
              type="button"
              className={cn('btn h-8! text-body-sm', range === r.key && 'is-active')}
              aria-pressed={range === r.key}
              onClick={() => setRange(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {usage.loading && !data && <Loading rows={4} label="加载用量…" />}
      {usage.error && <ErrorState error={usage.error} onRetry={usage.reload} title="用量加载失败" />}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Metric label={`${label}成本`} value={cny(data.total_cny)} tone="accent" hint="单位：元（4 位小数）" />
            <Metric label={`${label}生成次数`} value={stats.genCount} unit="次" hint={`账本条目 ${stats.count} 条`} />
            <Metric
              label="平均耗时"
              value={stats.avgLatency}
              unit="ms"
              hint={stats.failures ? `其中失败 ${stats.failures} 次` : '全部成功'}
            />
          </div>

          <div className="band grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="card">
              <h2 className="card-title m-0! text-h3">按动作汇总（按金额 TOP 3）</h2>
              {(data.by_action ?? []).length === 0 ? (
                <p className="m-0 text-ink-sub">这段时间没有调用记录。</p>
              ) : (
                <ul className="m-0 list-none p-0">
                  {data.by_action.slice(0, 3).map((a) => (
                    <li key={a.action} className="py-0.5">
                      <div className="flex items-center gap-2 text-body-sm">
                        <span className="w-24 truncate">{a.action}</span>
                        <span className="num flex-1 text-right">{cny(a.cny)}</span>
                        <span className="num w-14 text-right text-ink-sub">{a.count} 次</span>
                      </div>
                      <div className="progress is-decor mt-1">
                        <i style={{ width: `${(a.cny / stats.maxAction) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                  {data.by_action.length > 3 && (
                    <li className="pt-1 text-caption text-ink-muted">另有 {data.by_action.length - 3} 类动作未列出（按金额排序）</li>
                  )}
                </ul>
              )}
            </div>

            <div className="card">
              <h2 className="card-title m-0! text-h3">按供应商汇总（按金额 TOP 3）</h2>
              {(data.by_provider ?? []).length === 0 ? (
                <p className="m-0 text-ink-sub">这段时间没有调用记录。</p>
              ) : (
                <ul className="m-0 list-none p-0">
                  {data.by_provider.slice(0, 3).map((p) => (
                    <li key={p.provider} className="py-0.5">
                      <div className="flex items-center gap-2 text-body-sm">
                        <span className="w-28 truncate">{p.provider}</span>
                        <span className="num flex-1 text-right">{cny(p.cny)}</span>
                        <span className="num w-14 text-right text-ink-sub">{p.count} 次</span>
                      </div>
                      <div className="progress is-decor mt-1">
                        <i style={{ width: `${(p.cny / stats.maxProvider) * 100}%` }} />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="card">
            <h2 className="card-title">按项目汇总</h2>
            <p>未填单价时账本金额记 0，不代表免费。金额是记录成本，非支付实扣凭证；失败不承诺退款。</p>
            <table className="ledger"><thead><tr><th>项目 / 项目 id</th><th>成本（元）</th><th>调用数</th><th>明细</th></tr></thead><tbody>
              {data.by_project?.map(p=><tr key={p.project_id || 'unlinked'}><td>{p.title} <span className="num">{p.project_id}</span></td><td className="num">{cny(p.cny)}</td><td className="num">{p.count}</td><td>{p.project_id && <button className="btn btn-secondary" onClick={()=>setProjectId(p.project_id!)}>查看全部历史账本</button>}</td></tr>)}
            </tbody></table>
            {ledger.loading && <Loading label="查询项目全部历史成本…" />}
            {ledger.error && <ErrorState error={ledger.error} onRetry={ledger.reload} />}
            {ledger.data && <div><h3>{ledger.data.title} · <span className="num">{ledger.data.project_id} / {cny(ledger.data.total_cny)}</span></h3><p>{ledger.data.note}</p>
              {ledger.data.tasks.map(t=><details key={t.job_id}><summary>{t.operation} · {t.status} · <span className="num">{t.job_id} / {cny(t.total_cny)}</span></summary>{t.pages.map(p=><p className="num" key={p.page_no}>第 {p.page_no} 页 · {p.status} · {cny(p.cny)}</p>)}</details>)}
              <table className="ledger"><thead><tr><th>任务</th><th>页号</th><th>动作</th><th>金额（元）</th><th>计费说明</th></tr></thead><tbody>{ledger.data.items.map(i=><tr key={i.id}><td className="num">{i.job_id || '历史记录未关联任务'}</td><td className="num">{i.page_no ?? '—'}</td><td>{i.action}</td><td className="num">{cny(i.cny)}</td><td>{i.billing_status}</td></tr>)}</tbody></table>
            </div>}
          </div>

          <div className="card">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="card-title m-0! text-h3">明细</h2>
              <span className="num text-caption text-ink-sub">共 {rows.length} 条</span>
              <span className="flex-1" />
              {rows.length > 10 && (
                <button
                  type="button"
                  className="btn btn-secondary h-8! text-body-sm"
                  onClick={() => setExpanded((v) => !v)}
                  aria-expanded={expanded}
                >
                  {expanded ? '只看最近 10 条' : `展开全部 ${rows.length} 条`}
                </button>
              )}
            </div>
            {rows.length === 0 ? (
              <EmptyState
                title={`${label}还没有调用记录`}
                desc="回生成向导跑一次「开始生成」，这里就会出现每页的 provider / model / 成本 / 耗时。"
                actionLabel="去生成"
                to="/"
              />
            ) : (
              // 表格固定在可视高度内滚动：页面本身不再被明细撑高
              <div className="mt-2 max-h-[18vh] overflow-auto">
                <table className="ledger">
                  <thead>
                    <tr className="[&>th]:sticky [&>th]:top-0 [&>th]:z-10">
                      <th>时间</th>
                      <th>项目 / 任务 / 页</th>
                      <th>动作</th>
                      <th>供应商</th>
                      <th>模型</th>
                      <th>尺寸</th>
                      <th className="text-right">金额（元）</th>
                      <th className="text-right">耗时</th>
                      <th>状态</th>
                      <th>详情</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(expanded ? rows : rows.slice(0, 10)).map((i) => (
                      <tr key={i.id}>
                        <td className="num whitespace-nowrap">{fmtTime(i.ts)}</td>
                        <td className="num">{i.project_id || '未关联'} / {i.job_id || '历史记录'} / {i.page_no ?? '—'}</td>
                        <td>{i.action}</td>
                        <td>{i.provider}</td>
                        <td className="num">{i.model}</td>
                        <td className="num">{i.size}</td>
                        <td className="num text-right">{cny(i.cny)}</td>
                        <td className="num text-right">{ms(i.latency_ms)}</td>
                        <td>
                          <span className={cn('status', i.ok ? 'status-success' : 'status-danger')}>
                            {i.ok ? '成功' : '失败'}
                          </span>
                        </td>
                        <td className="text-ink-sub">{i.detail || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
