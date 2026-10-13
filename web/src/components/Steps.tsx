/** 5 步向导步骤条：active/done/pending/error；已完成步骤可回跳（components.md） */
import { cn } from '../lib/format'

export const WIZARD_STEPS = [
  { key: 1, label: '输入内容' },
  { key: 2, label: '页面确认' },
  { key: 3, label: '内容确认' },
  { key: 4, label: '选择风格' },
  { key: 5, label: '生成结果' },
] as const

export type WizardStepNo = (typeof WIZARD_STEPS)[number]['key']

export function Steps({
  current,
  locked,
  errorAt,
  onJump,
}: {
  current: number
  /** 每个步骤缺失的真实前置条件 */
  locked: Record<number, string | undefined>
  errorAt?: number
  onJump?: (step: number) => void
}) {
  return (
    <div className="steps" role="list" aria-label="生成向导步骤">
      {WIZARD_STEPS.map((s, i) => {
        const isError = errorAt === s.key
        const isDone = !isError && s.key < current
        const isActive = s.key === current && !isError
        const canJump = !!onJump && !locked[s.key] && s.key !== current
        const cls = isError
          ? 'error'
          : isActive
            ? 'active'
            : isDone
              ? 'done'
              : 'pending'
        return (
          <div key={s.key} className="flex items-center gap-2" role="listitem">
            {i > 0 && <span className="step-sep">›</span>}
            <button
              type="button"
              className={cn('step', cls, canJump ? 'cursor-pointer hover:opacity-90' : 'cursor-default')}
              disabled={!canJump}
              aria-current={isActive ? 'step' : undefined}
              title={locked[s.key] || (canJump ? `回到「${s.label}」` : isError ? '该步骤出错，可点「重试」' : undefined)}
              onClick={() => canJump && onJump?.(s.key)}
            >
              <span className="num">{isDone ? '✓' : s.key}</span>
              <span>{s.label}{locked[s.key] && <small className="block text-caption">{locked[s.key]}</small>}</span>
            </button>
          </div>
        )
      })}
    </div>
  )
}
