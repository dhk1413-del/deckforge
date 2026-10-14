/** 用量：所选时间范围的成本、生成指标与供应商汇总 */
import { useMemo, useState } from 'react'
import { getUsage } from '../api'
import { useAsync } from '../hooks/useAsync'
import { cn, cny } from '../lib/format'
import { Metric } from '../components/Metric'
import { ErrorState, Loading } from '../components/StateBlock'
import type { UsageRange } from '../types'

const RANGES: Array<{ key: UsageRange; label: string }> = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'all', label: '全部' },
]

export function UsagePage() {
  const [range, setRange] = useState<UsageRange>('month')
  const usage = useAsync(() => getUsage(range), [range])
  const data = usage.data

  const stats = useMemo(() => {
    const items = data?.items ?? []
    const count = items.length
    const avgLatency = count ? Math.round(items.reduce((s, i) => s + (i.latency_ms ?? 0), 0) / count) : 0
    const failures = items.filter((i) => !i.ok).length
    const genCount =
      data?.by_action?.find((a) => a.action === 'generate')?.count ??
      data?.by_action?.reduce((s, a) => s + a.count, 0) ??
      0
    const maxProvider = Math.max(1, ...(data?.by_provider ?? []).map((p) => p.cny))
    return { count, avgLatency, failures, genCount, maxProvider }
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

          <p className="m-0 text-caption text-ink-sub">
            未填单价时账本金额记 0，不代表免费。金额是记录成本，非支付实扣凭证；失败不承诺退款。
          </p>

          <div className="band grid grid-cols-1 gap-3">
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
        </>
      )}
    </div>
  )
}
