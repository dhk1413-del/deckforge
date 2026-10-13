/** 风格库：分类筛选 + 风格卡网格；详情页 #/styles/:id（色板 / 布局 / style.md 摘要） */
import { useMemo, useState } from 'react'
import { getStylePack, listLayouts, listStylePacks } from '../api'
import { collectColorTokens, cn, safeHex } from '../lib/format'
import { useAsync } from '../hooks/useAsync'
import { EmptyState, ErrorState, Loading } from '../components/StateBlock'
import { StylePackCard } from '../components/StylePackCard'
import { useToast } from '../components/Toast'
import { Link, navigate, useRoute } from '../router'
import type { LayoutKey } from '../types'

/* ---------------- 列表页 ---------------- */

export function StylesPage() {
  const toast = useToast()
  const packs = useAsync(listStylePacks, [])
  const [category, setCategory] = useState<string>('全部')
  const [previewing, setPreviewing] = useState<string | null>(null)

  const items = packs.data?.items ?? []
  const categories = useMemo(
    () => ['全部', ...Array.from(new Set(items.map((p) => p.category)))],
    [items],
  )
  const visible = category === '全部' ? items : items.filter((p) => p.category === category)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-end gap-3">
        <h1 className="m-0 text-h1 font-semibold">风格库</h1>
        <span className="flex-1" />
        <Link to="/style-builder" className="btn btn-primary">
          + 风格构建
        </Link>
      </div>

      {packs.loading && !items.length && <Loading rows={3} label="加载风格包…" />}
      {packs.error && <ErrorState error={packs.error} onRetry={packs.reload} title="风格包加载失败" />}

      {!packs.loading && !packs.error && items.length === 0 && (
        <div className="card">
          <EmptyState
            title="还没有任何风格包"
            desc="把风格包放进仓库的 style-packs/ 目录（每个包含 style.md + prompt.md），然后重新加载本页。"
            actionLabel="重新加载"
            onAction={packs.reload}
          />
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="chips">
            {categories.map((c) => (
              <button
                key={c}
                type="button"
                className={cn('chip h-8! text-body-sm', category === c && 'is-active')}
                aria-pressed={category === c}
                onClick={() => setCategory(c)}
              >
                {c}
                {c !== '全部' && (
                  <span className="num ml-1 opacity-80">
                    {items.filter((p) => p.category === c).length}
                  </span>
                )}
              </button>
            ))}
          </div>

          <div className="band grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" role="listbox" aria-label="风格包列表">
            {visible.map((p) => (
              <StylePackCard
                key={p.id}
                pack={p}
                selected={false}
                previewing={previewing === p.id}
                onSelect={() => {
                  toast.success(`已选中「${p.name}」样式`, '回到生成向导「选择风格」即可绑定该风格')
                  navigate(`/?style=${encodeURIComponent(p.id)}`)
                }}
                onPreview={() => setPreviewing((v) => (v === p.id ? null : p.id))}
                onDetail={() => navigate(`/styles/${encodeURIComponent(p.id)}`)}
              />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

/* ---------------- 详情页 ---------------- */

function LayoutChip({ layoutKey, title, bestFor }: { layoutKey: LayoutKey; title?: string; bestFor?: string }) {
  return (
    <span className="tag" title={bestFor}>
      <span className="num">{layoutKey}</span>
      {title ? ` · ${title}` : ''}
    </span>
  )
}

export function StyleDetailPage({ id }: { id: string }) {
  const detail = useAsync(() => getStylePack(id), [id])
  const layouts = useAsync(listLayouts, [])

  if (detail.loading && !detail.data) return <Loading rows={4} label="加载风格详情…" />
  if (detail.error) {
    return (
      <div className="flex flex-col gap-3">
        <Link to="/styles" className="link">
          ‹ 返回风格列表
        </Link>
        <ErrorState error={detail.error} onRetry={detail.reload} title="风格详情加载失败" />
      </div>
    )
  }
  const pack = detail.data
  if (!pack) return null

  const accent = safeHex(pack.accent, 'var(--color-accent)')
  const bg = safeHex(pack.bg, 'var(--color-surface-alt)')
  const colorTokens = collectColorTokens(pack.tokens)
  const layoutMap = new Map((layouts.data?.items ?? []).map((l) => [l.key, l]))

  return (
    <div className="flex flex-col gap-4">
      <Link to="/styles" className="link">
        ‹ 返回风格列表
      </Link>

      <div className="card">
        <div className="flex flex-wrap items-start gap-4">
          <div
            className="flex h-20 w-32 shrink-0 items-center justify-center rounded-md border border-border"
            style={{ background: bg, color: accent }}
            aria-label={`风格示意：底色 ${bg}，主色 ${accent}`}
          >
            <span className="text-h2" style={{ color: accent }}>
              Aa
            </span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="m-0 text-h1 font-semibold">{pack.name}</h1>
              {pack.badge && <span className="badge">{pack.badge}</span>}
              <span className="tag">{pack.category}</span>
            </div>
            <p className="m-0 mt-1 text-ink-sub">{pack.summary}</p>
            <div className="mt-2 flex flex-wrap items-center gap-3 text-caption text-ink-sub">
              <span className="num">id: {pack.id}</span>
              <span className="num">v{pack.version}</span>
              <span>来源：{pack.source_type}</span>
              <span className="num">{pack.layouts.length} 布局</span>
            </div>
          </div>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate(`/?style=${encodeURIComponent(pack.id)}`)}
            title="带着该风格进入生成向导「选择风格」"
          >
            用这个风格生成
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card">
          <h2 className="card-title text-h3">色板</h2>
          <div className="flex flex-wrap gap-3">
            {[
              { name: '主色 accent', value: accent },
              { name: '底色 bg', value: bg },
              ...colorTokens,
            ].map((c, i) => (
              <div key={`${c.name}-${i}`} className="flex items-center gap-2">
                <span
                  className="inline-block h-8 w-8 rounded-sm border border-border"
                  style={{ background: safeHex(c.value, 'var(--color-surface-alt)') }}
                  aria-hidden="true"
                />
                <span className="text-caption">
                  <span className="num">{c.value}</span>
                  <br />
                  <span className="text-ink-sub">{c.name}</span>
                </span>
              </div>
            ))}
            {colorTokens.length === 0 && (
              <span className="text-caption text-ink-sub">style.md 未声明额外颜色令牌</span>
            )}
          </div>

          <div className="divider my-3" />
          <h2 className="card-title text-h3">可用布局</h2>
          <div className="flex flex-wrap gap-2">
            {pack.layouts.map((k) => {
              const info = layoutMap.get(k)
              return <LayoutChip key={k} layoutKey={k} title={info?.title} bestFor={info?.best_for} />
            })}
          </div>
          {layouts.data && (
            <p className="mt-2 mb-0 text-caption text-ink-sub">
              布局插槽取自 GET /api/layouts：
              {layouts.data.items
                .filter((l) => pack.layouts.includes(l.key))
                .map((l) => `${l.key}(${l.slots.join('/')})`)
                .join('，') || '—'}
            </p>
          )}
        </div>

        <div className="card">
          <h2 className="card-title text-h3">style.md</h2>
          <p className="card-desc">风格原文（截断摘要）</p>
          <pre className="panel-alt max-h-56 overflow-auto whitespace-pre-wrap text-caption">
            {pack.style_md?.slice(0, 1200) || '（空）'}
          </pre>
          <h2 className="card-title mt-4 text-h3">prompt.md</h2>
          <p className="card-desc">生图提示词模板（截断摘要）</p>
          <pre className="panel-alt max-h-56 overflow-auto whitespace-pre-wrap text-caption">
            {pack.prompt_md?.slice(0, 1200) || '（空）'}
          </pre>
        </div>
      </div>
    </div>
  )
}

/** 详情路由入口：把 id 从路由 params 里取出来 */
export function StyleDetailRoute() {
  const route = useRoute()
  return <StyleDetailPage id={route.params.id ?? ''} />
}
