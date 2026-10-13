/** 任务反馈使用服务端阶段与实际页数，不推测页内百分比。 */
import { useEffect, useState } from 'react'
import { ApiError } from '../api'
import { useJobStream } from '../hooks/useJobStream'
import { cn, pageNo } from '../lib/format'
import type { JobProgressEvent } from '../types'
import { ErrorState, Notice } from './StateBlock'

/** 后端 stage → 中文短标签（generate / vision / hints / page / assemble / editable / verify…） */
const STAGE_LABEL: Record<string, string> = {
  generate: '生成图片',
  vision: '识别版面',
  hints: '文字真源',
  page: '逐页重建',
  assemble: '写回对象',
  editable: '重建',
  verify: '校验',
}
const stageLabelOf = (s: string) => STAGE_LABEL[s] ?? s

/** 毫秒 → 「12s」「1m30s」 */
export function fmtSec(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`
}

export function ProgressPanel({
  job,
  stageLabel,
}: {
  job: ReturnType<typeof useJobStream>
  stageLabel: string
}) {
  const total = job.total || 0
  /** 两种事件口径取大：generate/builtin 逐页报 done/failed，skill 引擎走任务级 done 数字 */
  const done = Math.max(Object.keys(job.settled).length, job.progressDone)
  const events = Object.values(job.byPage).sort((a, b) => a.page - b.page)
  const current = events.find((e) => e.status === 'running')
  const succeeded = Object.values(job.settled).filter(s=>s==='done').length
  const failed = Object.values(job.settled).filter(s=>s==='failed').length
  const running = job.status==='running' ? events.filter(e=>e.status==='running').length : 0
  // 秒表：进行中每秒刷新一次
  const [, setTick] = useState(0)
  useEffect(() => {
    if (job.status !== 'running') return
    const t = setInterval(() => setTick((x) => x + 1), 1000)
    return () => clearInterval(t)
  }, [job.status])

  const elapsedMs = job.startedAt ? (job.finishedAt ?? Date.now()) - job.startedAt : 0
  const finishedPages = Object.values(job.byPage).filter((e) => e.status === 'done' || e.status === 'failed')
  const measuredMs = finishedPages.length
    ? finishedPages.reduce((sum, e) => sum + (e.elapsed_ms ?? 0), 0) / finishedPages.length
    : 0
  // 剩余预估：只用本次任务里已完成页的实测均耗时（后端给的秒级预估对视觉模型明显偏低，不再采用）
  const remainMs =
    job.status === 'running' && total && done < total && measuredMs > 0
      ? measuredMs * (total - done)
      : 0
  /** 估不出量级（<2s）就不必显示，免得写「预计还需 ~0s」这种废话 */
  const showRemain = remainMs >= 2000

  return (
    <div className="card">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h2 className="card-title m-0! text-h3">{stageLabel}</h2>
        <span
          className={cn(
            'status',
            job.status === 'done'
              ? 'status-success'
              : job.status === 'error'
                ? 'status-danger'
                : 'status-warn',
          )}
        >
          {job.status === 'done' ? (failed ? '部分完成' : '已完成') : job.status === 'error' ? '失败' : job.status === 'interrupted' ? '已中断' : job.status === 'cancelled' ? '已取消' : '进行中'}
        </span>
        <span className="num text-ink-sub">已完成 {succeeded || (failed ? 0 : job.progressDone)}/{total || '—'}、失败 {failed}、处理中 {running}</span>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-3 text-body-sm">
        <span className="min-w-[220px] flex-1">{(job.transportErrors ? '连接中断，正在恢复状态' : job.status === 'running' ? current?.message : job.message) || job.message || '等待进度事件…'}</span>
        {job.startedAt && (
          <span className="num text-ink-sub">
            已用 {fmtSec(elapsedMs)}
            {showRemain ? ` · 预计还需 ~${fmtSec(remainMs)}` : ''}
          </span>
        )}
      </div>

      {events.length > 0 && (
        <ul className="mt-3 m-0 max-h-48 list-none overflow-auto p-0">
          {events.map((e: JobProgressEvent) => (
            <li key={e.page} className="flex items-center gap-2 border-t border-divider py-1 text-body-sm">
              <span className="num w-10 text-ink-sub">P{pageNo(e.page_no ?? e.page)}</span>
              <span className="flex-1 truncate">{e.message}</span>
              {e.elapsed_ms ? <span className="num text-ink-sub">{fmtSec(e.elapsed_ms)}</span> : null}
              <span className="tag num">{stageLabelOf(e.stage)}</span>
              <span
                className={cn(
                  'status',
                  e.status === 'failed' ? 'status-danger' : e.status === 'running' ? 'status-warn' : 'status-info',
                )}
              >
                {e.status === 'interrupted' ? '已中断·未生成' : job.status === 'cancelled' && ['queued','running'].includes(e.status) ? '未执行（已取消）' : e.status === 'queued' ? '排队中' : e.status === 'running' ? '进行中' : e.status === 'failed' ? '失败' : '完成'}
              </span>
            </li>
          ))}
        </ul>
      )}

      {job.status === 'interrupted' && <Notice kind="warn">服务重启，作业已中断；未完成页未生成，可在页面清单中重新生成。已完成结果和旧版本保留。</Notice>}
      {job.status === 'error' && (
        <div className="mt-3">
          <ErrorState
            compact
            title="生成失败"
            error={new ApiError(job.error ?? '未知错误（进度流未返回原因）', 0)}
          />
        </div>
      )}

      {job.status !== 'done' && job.transportErrors > 0 && job.status !== 'error' && (
        <div className="mt-3">
          <Notice kind="warn">
            连接中断，正在恢复状态。保留最后确认的状态，后台任务不会因离开而停止。
          </Notice>
        </div>
      )}
    </div>
  )
}
