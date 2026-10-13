import { useModalFocus } from '../hooks/useModalFocus'
/** 单页大图预览：loading / ready / failed + 2x·4x 放大 + ‹ n/N › 翻页（components.md） */
import { useEffect, useState } from 'react'
import { cn, pageNo } from '../lib/format'
import type { Slide } from '../types'

export function SlidePreview({
  slides,
  index,
  onIndexChange,
  onClose,
  onOptimize,
  optimizeDisabledReason,
}: {
  slides: Slide[]
  index: number
  onIndexChange: (i: number) => void
  onClose: () => void
  /** [✦ 优化本页] —— 单页重生成 */
  onOptimize?: (page_no: number) => void
  optimizeDisabledReason?: string
}) {
  const modalRef = useModalFocus(onClose)
  const [zoom, setZoom] = useState<1 | 2 | 4>(1)
  const [failed, setFailed] = useState(false)
  const slide = slides[index]
  const total = slides.length

  useEffect(() => setFailed(false), [index])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') onIndexChange(Math.max(0, index - 1))
      if (e.key === 'ArrowRight') onIndexChange(Math.min(total - 1, index + 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [index, total, onClose, onIndexChange])

  if (!slide) return null

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-[rgba(30,35,46,.45)] p-6"
      ref={modalRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label={`第 ${slide.page_no} 页大图预览`}
      onClick={onClose}
    >
      <div
        className="flex max-h-full w-full max-w-[1000px] flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-[var(--shadow-overlay)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-divider px-5 py-3">
          <span className="num text-ink-sub">
            {pageNo(slide.page_no)} / {total}
          </span>
          <span className="min-w-0 flex-1 truncate font-semibold">{slide.title || '（无标题）'}</span>
          <span className="status status-info">图片预览</span>
          <div className="flex items-center gap-1">
            {([1, 2, 4] as const).map((z) => (
              <button
                key={z}
                type="button"
                className={cn('btn h-7! px-2! text-caption', zoom === z ? 'btn-primary' : 'btn-secondary')}
                onClick={() => setZoom(z)}
                aria-pressed={zoom === z}
              >
                <span className="num">{z}x</span>
              </button>
            ))}
          </div>
          <button type="button" className="btn btn-secondary h-8!" onClick={onClose} aria-label="关闭预览">
            关闭
          </button>
        </div>

        <div className="flex min-h-0 flex-1 items-center justify-center overflow-auto bg-surface-alt p-4">
          {slide.image_url && !failed ? (
            <img
              src={slide.image_url}
              alt={`第 ${slide.page_no} 页`}
              className="origin-center object-contain transition-transform"
              style={{ transform: `scale(${zoom})`, maxHeight: '62vh', width: '100%' }}
              onError={() => setFailed(true)}
            />
          ) : (
            <div className="empty">
              <div className="font-semibold text-ink">这一页还没有可用图片</div>
              <p className="mt-1 text-ink-sub">
                {failed
                  ? '图片加载失败：确认后端 /files 静态目录可访问，然后回到网格点「刷新结果」'
                  : '页面可能仍在生成中或生成失败，可点下方「刷新结果」或「优化本页」重生成'}
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-divider px-5 py-3">
          <button
            type="button"
            className="btn btn-secondary"
            disabled={index <= 0}
            title={index <= 0 ? '已经是第一页' : '上一页'}
            onClick={() => onIndexChange(index - 1)}
          >
            ‹ 上一页
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={index >= total - 1}
            title={index >= total - 1 ? '已经是最后一页' : '下一页'}
            onClick={() => onIndexChange(index + 1)}
          >
            下一页 ›
          </button>
          <span className="flex-1" />
          <span className="text-caption text-ink-sub">
            {slide.provider} / {slide.model} / {slide.size} ·{' '}
            <span className="num">¥{slide.cost_cny.toFixed(4)}</span> ·{' '}
            <span className="num">{slide.latency_ms} ms</span>
          </span>
          {onOptimize && (
            <button type="button" className="btn btn-secondary" disabled={Boolean(optimizeDisabledReason)} title={optimizeDisabledReason} onClick={() => onOptimize(slide.page_no)}>
              ✦ 优化本页
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
