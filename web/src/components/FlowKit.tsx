/**
 * 流程共用件（FlowKit）——三条流程（文档生成 / 图片转可编辑 / PPT 美化）共用同一套步骤条、
 * 页面导航栏、单页画框、放大灯箱与底部胶囊操作条，避免各写一份导致交互走样。
 *
 * 约定：这里只放**结构与交互**，不放业务文案；文案一律由调用方按该页真源传入。
 */
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { cn } from '../lib/format'
import { useModalFocus } from '../hooks/useModalFocus'

export interface FlowStep {
  key: number
  label: string
}

/**
 * 步骤条：可按数据前进/后退；未就绪的步骤显示为虚线灰态，点击时把「缺什么」交给调用方提示。
 */
export function FlowSteps({ steps, current, locks, busy, onJump, onLocked, label = '步骤' }: {
  steps: readonly FlowStep[]
  current: number
  /** 每个步骤缺失的真实前置条件；有值即视为未就绪 */
  locks: Record<number, string | undefined>
  busy?: boolean
  onJump: (step: number) => void
  onLocked?: (step: number, reason: string) => void
  label?: string
}) {
  return (
    <ol className="deck-stepper" aria-label={label}>
      {steps.map((step, index) => {
        const lock = locks[step.key]
        return (
          <li key={step.key} aria-current={current === step.key ? 'step' : undefined}>
            {index > 0 && <span className="deck-step-line" aria-hidden="true" />}
            <button
              type="button"
              disabled={busy}
              aria-disabled={Boolean(lock)}
              title={lock}
              className={cn('deck-step-button', current === step.key && 'is-current', current > step.key && 'is-complete', lock && 'is-locked')}
              onClick={() => (lock ? onLocked?.(step.key, lock) : onJump(step.key))}
            >
              <span className="num deck-step-number">{current > step.key ? '✓' : step.key}</span>
              <span>{step.label}</span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

export interface SelectablePage {
  pageNo: number
  image: string
  /** 图片 alt 文案；不传则用「第 N 页」 */
  alt?: string
}

/** 页面选择网格：附加行与放大行为由调用方提供。 */
export function PageSelectGrid({ pages, selected, disabled, onToggle, onZoom, zoomLabel, renderRow }: {
  pages: SelectablePage[]
  selected: number[]
  disabled?: boolean
  onToggle: (pageNo: number) => void
  /** 传了才显示放大按钮（点了由调用方打开灯箱） */
  onZoom?: (pageNo: number) => void
  zoomLabel?: (pageNo: number) => string
  /** 每页卡片底部的附加行；选中状态由调用方自己判断 */
  renderRow?: (pageNo: number, checked: boolean) => ReactNode
}) {
  return (
    <div className="deck-page-grid">
      {pages.map(page => {
        const checked = selected.includes(page.pageNo)
        const toggle = () => onToggle(page.pageNo)
        return <article key={page.pageNo} className={cn('deck-page-card', !checked && 'is-excluded')}>
          <div className="deck-page-preview">
            <button type="button" disabled={disabled} aria-pressed={checked} aria-label={`第 ${page.pageNo} 页${checked ? '取消选择' : '选择'}`} onClick={toggle} className="deck-page-select">
              <img src={page.image} alt={page.alt ?? `第 ${page.pageNo} 页`} loading="lazy" />
              <span className="num deck-page-number">{page.pageNo}</span>
              <span className={cn('deck-page-check', checked && 'is-checked')}>{checked ? '✓' : ''}</span>
            </button>
            <button type="button" aria-label={`移除第 ${page.pageNo} 页选择`} disabled={disabled || !checked} onClick={toggle} className="deck-page-remove">×</button>
            {onZoom && <button type="button" aria-label={zoomLabel?.(page.pageNo) ?? `放大第 ${page.pageNo} 页`} disabled={disabled} onClick={() => onZoom(page.pageNo)} className="deck-page-zoom">⤢</button>}
          </div>
          {renderRow?.(page.pageNo, checked)}
        </article>
      })}
    </div>
  )
}

export interface RailItem {
  key: number | string
  /** 主文字（如「第 3 页」或该页标题） */
  label: string
  /** 结果缩略图；没有则显示 index 徽标 */
  thumb?: string
  /** 左侧序号徽标（如 P1），与 thumb 二选一 */
  index?: string
  /** 右侧状态胶囊 */
  status?: { text: string; cls: string }
  /** 右侧二态小圆点 */
  dot?: 'done' | 'idle'
  title?: string
}

/** 页面导航栏：一次只显示一页时的左侧（窄屏为横向）列表。 */
export function PageRail({ items, current, onSelect, label }: {
  items: RailItem[]
  current: number
  onSelect: (index: number) => void
  label: string
}) {
  return (
    <nav className="deck-rail" aria-label={label}>
      {items.map((item, index) => (
        <button
          key={item.key}
          type="button"
          className={cn('deck-rail-item', index === current && 'is-current')}
          aria-current={index === current ? 'true' : undefined}
          title={item.title}
          onClick={() => onSelect(index)}
        >
          {item.thumb
            ? <img className="deck-rail-thumb" src={item.thumb} alt="" loading="lazy" />
            : item.index ? <span className="num deck-rail-index">{item.index}</span> : null}
          <span className="deck-rail-text">
            <span className="deck-rail-title">{item.label}</span>
            {item.status && <span className={cn('status', item.status.cls)}>{item.status.text}</span>}
            {!item.status && item.dot && <span className={cn('deck-rail-dot', item.dot === 'done' && 'is-done')} aria-hidden="true" />}
          </span>
        </button>
      ))}
    </nav>
  )
}

/** 底部胶囊操作条（翻页、计数、主次按钮都放这里）。 */
export function ActionBar({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('deck-action-bar', className)}>{children}</div>
}

/** 胶囊操作条里的圆形翻页箭头。 */
export function PagerArrow({ dir, disabled, onClick }: { dir: 'prev' | 'next'; disabled?: boolean; onClick: () => void }) {
  return (
    <button type="button" className="deck-pager-arrow" aria-label={dir === 'prev' ? '上一页' : '下一页'} disabled={disabled} onClick={onClick}>
      {dir === 'prev' ? '‹' : '›'}
    </button>
  )
}

export interface OverviewItem {
  key: number | string
  image?: string
  label: string
}

/** 缩略总览：一次看完所有页，点任一张回到单页。 */
export function OverviewGrid({ items, current, onSelect, emptyText }: {
  items: OverviewItem[]
  current: number
  onSelect: (index: number) => void
  emptyText: string
}) {
  return (
    <div className="deck-overview-grid">
      {items.map((item, index) => (
        <button key={item.key} type="button" className={cn('deck-overview-item', index === current && 'is-current')} aria-label={item.label} onClick={() => onSelect(index)}>
          {item.image
            ? <img src={item.image} alt={item.label} loading="lazy" />
            : <span className="deck-overview-empty">{emptyText}</span>}
          <span className="num deck-overview-no">{index + 1}</span>
        </button>
      ))}
    </div>
  )
}

export interface LightboxPage {
  image?: string
  /** 顶部左侧标签，如「P1 · 第 1 页」（允许带 num 等宽数字片段） */
  label: ReactNode
  /** 底部计数，如「P1 · 第 1 / 3 页」 */
  counter: ReactNode
}

/**
 * 放大看单页：深色灯箱 + 顶部标签/关闭 + 底部翻页；Esc 关闭、←/→ 翻页（焦点圈定在灯箱内）。
 * `version` 用来给图片加 ?v=，避免重生成后看到旧缓存。
 */
export function PageLightbox({ pages, index, onIndex, onClose, version, ariaLabel, emptyText, prevText = '← 上一页', nextText = '下一页 →', closeText = '✕ 关闭' }: {
  pages: LightboxPage[]
  index: number
  onIndex: (next: number) => void
  onClose: () => void
  version?: string
  ariaLabel: string
  emptyText: string
  prevText?: string
  nextText?: string
  closeText?: string
}) {
  const modalRef = useModalFocus(onClose)
  const page = pages[index]
  const total = pages.length
  const step = (delta: number) => onIndex(Math.min(Math.max(index + delta, 0), total - 1))
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'ArrowRight') { event.preventDefault(); step(1) }
      if (event.key === 'ArrowLeft') { event.preventDefault(); step(-1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
  if (!page) return null   // hooks 必须先全部调用，再判断早退
  return (
    <div className="deck-lightbox" ref={modalRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label={ariaLabel} onClick={onClose}>
      <div className="deck-lightbox-inner" onClick={(event) => event.stopPropagation()}>
        <div className="deck-lightbox-head">
          <span className="deck-lightbox-label">{page.label}</span>
          <button type="button" className="deck-lightbox-close" onClick={onClose}>{closeText}</button>
        </div>
        {page.image
          ? <img className="deck-lightbox-img" src={withVersion(page.image, version)} alt="" />
          : <p className="deck-lightbox-empty">{emptyText}</p>}
        <div className="deck-lightbox-foot">
          <button type="button" className="deck-lightbox-nav" disabled={index === 0} onClick={() => step(-1)}>{prevText}</button>
          <span>{page.counter}</span>
          <button type="button" className="deck-lightbox-nav" disabled={index >= total - 1} onClick={() => step(1)}>{nextText}</button>
        </div>
      </div>
    </div>
  )
}

/** 给图片地址加版本参数：同名文件被覆盖后靠它避开浏览器旧缓存。 */
export function withVersion(url: string, version?: string) {
  return !url || !version ? url : `${url}${url.includes('?') ? '&' : '?'}v=${encodeURIComponent(version)}`
}
