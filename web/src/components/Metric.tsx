/** 指标卡（数字继承正文字体，tnum 对齐） */
import type { ReactNode } from 'react'

export function Metric({
  label,
  value,
  unit,
  hint,
  tone = 'default',
}: {
  label: string
  value: ReactNode
  unit?: string
  hint?: string
  tone?: 'default' | 'accent'
}) {
  return (
    <div className="card p-5!">
      <div className="metric-label">{label}</div>
      <div className="metric flex-row items-baseline gap-1">
        <span
          className="metric-value num"
          style={tone === 'accent' ? { color: 'var(--color-accent-strong)' } : undefined}
        >
          {value}
        </span>
        {unit && <span className="text-caption text-ink-sub">{unit}</span>}
      </div>
      {hint && <div className="mt-1 text-caption text-ink-sub">{hint}</div>}
    </div>
  )
}
