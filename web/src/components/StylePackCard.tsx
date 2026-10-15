import { useModalFocus } from '../hooks/useModalFocus'
/** 风格包卡片：分类角标 + 配色块 + 布局数；状态 默认 / 已选 / 查看中（components.md）。简介只在详情页展示。 */
import { useEffect, useState } from 'react'
import { safeHex } from '../lib/format'
import { cn } from '../lib/format'
import type { StylePack } from '../types'

/** 灯箱：点封面看大图；有多张预览时可翻页（Esc 关闭、←/→ 翻页） */
function CoverLightbox({ pack, onClose }: { pack: StylePack; onClose: () => void }) {
  const modalRef = useModalFocus(onClose)
  const list = pack.previews?.length ? pack.previews : pack.cover ? [pack.cover] : []
  const [i, setI] = useState(0)
  const [broken, setBroken] = useState<string | null>(null)
  const go = (d: number) => setI((v) => (v + d + list.length) % list.length)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') go(1)
      if (e.key === 'ArrowLeft') go(-1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
  // 没有可预览的图时也要有反馈，否则点「查看」像是坏了
  if (!list.length) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" ref={modalRef} tabIndex={-1}
           role="dialog" aria-modal="true" aria-label={`${pack.name} 没有可预览的图`} onClick={onClose}>
        <div className="card flex max-w-[28rem] flex-col gap-3" onClick={(e) => e.stopPropagation()}>
          <p className="m-0 text-body-sm">该风格没有可预览的图：style.md 既没有声明配色示意，也没有预览图。</p>
          <button type="button" className="btn btn-secondary self-end" onClick={onClose}>关闭</button>
        </div>
      </div>
    )
  }
  return (
    <div
      className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-3 bg-black/70 p-4"
      ref={modalRef}
      tabIndex={-1}
      role="dialog"
      aria-modal="true"
      aria-label={`${pack.name} 风格预览`}
      onClick={onClose}
    >
      <img
        src={list[i]}
        alt={`${pack.name} 预览 ${i + 1}`}
        className="max-h-[76vh] max-w-[92vw] rounded-md border border-white/25 bg-white object-contain"
        onClick={(e) => e.stopPropagation()}
        onError={() => setBroken(list[i])}
      />
      {broken === list[i] && (
        <p className="m-0 rounded-md bg-white/95 px-3 py-2 text-body-sm" role="alert">
          这张预览图不可访问：<span className="num">{list[i]}</span>（换一张或关闭后可继续）
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2 text-white" onClick={(e) => e.stopPropagation()}>
        <span className="text-body-sm">
          {pack.name} · 第 {i + 1}/{list.length} 张
        </span>
        {list.length > 1 && (
          <>
            <button type="button" className="btn btn-secondary h-8! text-body-sm" onClick={() => go(-1)}>
              上一张
            </button>
            <button type="button" className="btn btn-secondary h-8! text-body-sm" onClick={() => go(1)}>
              下一张
            </button>
          </>
        )}
        <button type="button" className="btn btn-secondary h-8! text-body-sm" onClick={onClose}>
          关闭
        </button>
      </div>
      {list.length > 1 && (
        <div className="flex max-w-[92vw] gap-2 overflow-x-auto" onClick={(e) => e.stopPropagation()}>
          {list.map((u, k) => (
            <img
              key={u}
              src={u}
              alt=""
              role="button"
              tabIndex={0}
              aria-label={`查看第 ${k + 1} 张预览`}
              onKeyDown={e => {if (e.key === 'Enter' || e.key === ' ') {e.preventDefault(); setI(k)}}}
              onClick={() => setI(k)}
              className={cn('h-12 w-20 cursor-pointer rounded-sm border object-cover',
                k === i ? 'border-white' : 'border-white/30 opacity-70')}
            />
          ))}
        </div>
      )}
    </div>
  )
}

/** 预览图占位：用风格包自带 accent/bg 画一张 16:9 的示意（**没有真实封面图时**才用） */
function PreviewTile({ pack }: { pack: StylePack }) {
  const bg = safeHex(pack.bg, 'var(--color-surface-alt)')
  const accent = safeHex(pack.accent, 'var(--color-accent)')
  return (
    <div
      className="relative h-12 flex-1 overflow-hidden rounded-sm border border-border"
      style={{ background: bg }}
      aria-hidden="true"
    >
      <div className="absolute left-2 top-2 h-2 w-8 rounded-sm" style={{ background: accent }} />
      <div className="absolute left-2 top-5 h-1.5 w-14 rounded-sm opacity-70" style={{ background: accent }} />
      <div className="absolute inset-x-2 bottom-2 h-4 rounded-sm" style={{ background: accent, opacity: 0.22 }} />
    </div>
  )
}

export function StylePackCard({
  pack,
  selected,
  previewing,
  onSelect,
  onPreview,
}: {
  pack: StylePack
  selected: boolean
  previewing?: boolean
  onSelect: () => void
  onPreview?: () => void
}) {
  const accent = safeHex(pack.accent, 'var(--color-accent)')
  const bg = safeHex(pack.bg, 'var(--color-surface-alt)')
  const [shot, setShot] = useState(false)

  return (
    <div
      className={cn(
        'card card-interactive flex flex-col gap-3 transition-colors',
        selected && 'border-2 border-accent bg-surface!',
      )}
      style={selected ? { boxShadow: `inset 0 0 0 1px ${accent}, var(--shadow-card)` } : undefined}
      aria-selected={selected}
      role="option"
    >
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{pack.name}</span>
            {pack.badge && <span className="badge">{pack.badge}</span>}
            {selected && <span className="status status-success">已选</span>}
            {previewing && <span className="status status-warn">查看中</span>}
          </div>
        </div>
      </div>

      {/* 封面缩略图：真实预览图；**没有才回落成配色示意**（不假装有图） */}
      {pack.cover ? (
        <button
          type="button"
          className="group relative block w-full overflow-hidden rounded-sm border border-border"
          onClick={() => setShot(true)}
          title="点击查看大图预览"
        >
          <img
            src={pack.cover}
            alt={`${pack.name} 风格封面`}
            /* 封面是风格页的主内容：**不要用 lazy** —— 实测 lazy 在本页滚动容器下不触发，
               卡片会一直空着。风格包数量很少（个位数）且是局域网自托管，直接 eager 更稳。
               若将来包数变多，再换成 IntersectionObserver 手动懒加载。 */
            loading="eager"
            decoding="async"
            className="block aspect-video w-full object-cover transition-transform group-hover:scale-[1.02]"
          />
          <span className="absolute bottom-1 right-1 rounded-sm bg-black/55 px-1.5 py-0.5 text-caption text-white">
            {pack.previews && pack.previews.length > 1 ? `预览 ${pack.previews.length} 张` : '点击预览'}
          </span>
        </button>
      ) : (
        <div className="flex gap-2">
          {[0, 1, 2].map((i) => (
            <PreviewTile key={i} pack={pack} />
          ))}
        </div>
      )}
      {shot && <CoverLightbox pack={pack} onClose={() => setShot(false)} />}

      <div className="flex flex-wrap items-center gap-2">
        {pack.tags.map((t) => (
          <span key={t} className="tag">
            {t}
          </span>
        ))}
        <span className="flex-1" />
        <span className="flex items-center gap-1" title={`主色 ${accent} / 底色 ${bg}`}>
          <span
            className="inline-block h-4 w-4 rounded-sm border border-border"
            style={{ background: accent }}
            aria-label={`主色 ${accent}`}
          />
          <span
            className="inline-block h-4 w-4 rounded-sm border border-border"
            style={{ background: bg }}
            aria-label={`底色 ${bg}`}
          />
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={cn('btn', selected ? 'btn-secondary' : 'btn-primary')}
          onClick={onSelect}
          disabled={selected}
          title={selected ? '当前已选中该风格' : '选中该风格（在「开始生成」时绑定）'}
        >
          {selected ? '已选中' : '选择此风格'}
        </button>
        {onPreview && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              onPreview()
              setShot(true)
            }}
          >
            查看
          </button>
        )}
      </div>
    </div>
  )
}
