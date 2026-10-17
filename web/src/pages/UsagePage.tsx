/** 用量：所选时间范围的成本、生成指标与供应商汇总 */
import { useMemo, useState } from 'react'
import { getProviderUsage, getUsage } from '../api'
import { useAsync } from '../hooks/useAsync'
import { cn, cny, fmtTime } from '../lib/format'
import { Metric } from '../components/Metric'
import { ErrorState, Loading } from '../components/StateBlock'
import type { ProviderUsageDelta, ProviderUsageItem, UsageRange } from '../types'

const RANGES: Array<{ key: UsageRange; label: string }> = [
  { key: 'today', label: '今日' },
  { key: 'week', label: '本周' },
  { key: 'month', label: '本月' },
  { key: 'all', label: '全部' },
]

const usdText = (v: number | null | undefined) => (v == null ? '—' : `$${v.toFixed(2)}`)
const cnyText = (v: number | null | undefined) => (v == null ? '—' : `¥${v.toFixed(2)}`)

/** 面板侧累计用量的主数值：币种由面板 quota_display_type 决定，不硬编码人民币 */
function panelAmount(item: ProviderUsageItem): string {
  if (item.currency === 'TOKENS') return `${(item.total_usage ?? 0).toLocaleString()} tokens`
  if (item.currency === 'CNY') {
    return `${cnyText(item.used_cny)}${item.used_usd == null ? '' : `（≈ ${usdText(item.used_usd)}）`}`
  }
  return `${usdText(item.used_usd)}${item.used_cny == null ? '' : `（≈ ${cnyText(item.used_cny)}）`}`
}

function panelDelta(item: ProviderUsageItem, delta: ProviderUsageDelta): string {
  const sign = delta.total_usage > 0 ? '+' : ''
  if (item.currency === 'TOKENS') return `${sign}${delta.total_usage.toLocaleString()} tokens`
  if (item.currency === 'CNY') return `${sign}${cnyText(delta.used_cny)}`
  return `${sign}${usdText(delta.used_usd)}`
}

export function UsagePage() {
  const [range, setRange] = useState<UsageRange>('month')
  const usage = useAsync(() => getUsage(range), [range])
  const data = usage.data
  const upstream = useAsync(() => getProviderUsage(), [])
  const [upstreamBusy, setUpstreamBusy] = useState(false)
  /** 手动刷新绕过服务端 60 秒缓存；失败时保留上一次结果，不让卡片变空 */
  const refreshUpstream = async () => {
    setUpstreamBusy(true)
    try {
      upstream.setData(await getProviderUsage(true))
    } catch {
      /* 保留旧数据，错误由后续重试提示 */
    } finally {
      setUpstreamBusy(false)
    }
  }

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

      {(upstream.loading || (upstream.data?.items.length ?? 0) > 0) && (
        <div className="card">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="card-title m-0! text-h3">供应商侧用量</h2>
            <span className="text-caption text-ink-sub">面板口径 · 累计值（不按日期区间）</span>
            <span className="flex-1" />
            <button
              type="button"
              className="btn btn-secondary h-8! text-body-sm"
              disabled={upstreamBusy}
              onClick={() => void refreshUpstream()}
            >
              {upstreamBusy ? '查询中…' : '向面板刷新'}
            </button>
          </div>

          {upstream.loading && !upstream.data && (
            <p className="m-0 text-body-sm text-ink-sub">正在向供应商面板查询用量（通常几秒；网络不好时需要更久，可稍后刷新）…</p>
          )}
          {upstream.error && !upstream.data && (
            <p className="m-0 text-body-sm text-ink-sub">面板查询失败：{upstream.error.detail}（不影响本地账本）</p>
          )}

          <ul className="m-0 mt-2 flex list-none flex-col gap-2 p-0">
            {(upstream.data?.items ?? []).map((item) => (
              <li key={item.provider_id} className="rounded-md border border-border px-3 py-2">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="text-body-md">{item.label}</span>
                  {item.ok ? (
                    <>
                      <span className="num text-body-md">{panelAmount(item)}</span>
                      {item.delta && (
                        <span className="num text-caption text-ink-sub">
                          较上次快照 {panelDelta(item, item.delta)}（{fmtTime(item.delta.previous_ts)}）
                        </span>
                      )}
                      <span className="flex-1" />
                      <span className="text-caption text-ink-sub">
                        查询于 {fmtTime(item.fetched_at)} · <span className="num">{item.duration_ms}</span> ms
                        {item.cached ? ' · 缓存' : ''}
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="flex-1" />
                      <span className="text-caption text-danger-ink">{item.error}</span>
                    </>
                  )}
                </div>
                {item.ok && (
                  <p className="m-0 mt-1 text-caption text-ink-sub">
                    {item.scope_note}。
                    {item.unlimited
                      ? '面板未给额度上限。'
                      : `面板额度上限 ${usdText(item.limit_usd)}，剩余 ${usdText(item.limit_remaining_usd)}。`}
                    {item.exchange_rate ? `人民币按面板汇率 ${item.exchange_rate} 折算，仅作参考。` : '本次未取到面板汇率，未折算人民币。'}
                  </p>
                )}
              </li>
            ))}
          </ul>

          {upstream.data?.note && <p className="m-0 mt-2 text-caption text-ink-sub">{upstream.data.note}</p>}
        </div>
      )}
    </div>
  )
}
