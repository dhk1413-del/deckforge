/** 大纲编辑器（文档向导第②步「编辑大纲」）。
 *
 *  布局：左侧章节栏（每章一张卡，带页数与「+ 过渡页 / + 内容页」）+ 右侧该章的页面卡片；
 *  点击页面卡片打开编辑弹窗（标题 / 本页原文 / 前移后移新增拆页删除 / 上一页下一页完成）。
 *  数据全部来自真实大纲（章节由后端按素材标题层级归纳），所有改动经 onChange 写回页清单，
 *  由父层统一保存 —— 编辑器自己不直接发请求。
 */
import { useMemo, useState } from 'react'
import { cn } from '../lib/format'
import { ActionBar } from './FlowKit'

export interface EditorPage {
  page_no: number
  title: string
  role: string
  outline: string
  points: string[]
  keep: boolean
  layout: string
  chapter_no?: number
  chapter_title?: string
}

export interface EditorChapter {
  key: number
  title: string
  pages: EditorPage[]
}

/** 页型标签：只用后端真实的 role / layout，不认识的按「内容页」 */
const TYPE_LABEL: Record<string, string> = {
  cover: '封面', section: '过渡页', summary: '总结页', data: '数据页', content: '内容页',
  cards_4: '内容页', cards_3: '内容页', cards_2: '内容页', bullets: '内容页', chart: '数据页',
}
const typeLabel = (page: EditorPage) => TYPE_LABEL[page.role] || TYPE_LABEL[page.layout] || '内容页'

const isTransition = (page: EditorPage) => page.role === 'section' || page.layout === 'section'

/** 把页清单按章节分组（保持出现顺序，章号重新连续编号，便于用户新增章节） */
function groupChapters(pages: EditorPage[]): EditorChapter[] {
  const out: EditorChapter[] = []
  pages.forEach((page) => {
    const raw = page.chapter_no || 0
    const title = (page.chapter_title || '').trim()
    const last = out[out.length - 1]
    if (last && last.pages[0] && (last.pages[0].chapter_no || 0) === raw && (last.pages[0].chapter_title || '').trim() === title) {
      last.pages.push(page)
      return
    }
    out.push({ key: raw || out.length + 1, title, pages: [page] })
  })
  return out.map((chapter, index) => ({ ...chapter, key: index + 1, title: chapter.title || `第 ${index + 1} 章` }))
}

const renumber = (list: EditorPage[]) => list.map((page, index) => ({ ...page, page_no: index + 1 }))

/** 章内页序重排后，把整份清单的 chapter_no/chapter_title 规整一遍 */
function normalizeChapters(list: EditorPage[]): EditorPage[] {
  const groups = groupChapters(list)
  const next: EditorPage[] = []
  groups.forEach((chapter, index) => {
    chapter.pages.forEach((page) => next.push({ ...page, chapter_no: index + 1, chapter_title: chapter.title }))
  })
  return renumber(next)
}

export function OutlineEditor({
  pages, busy, onChange, onRegenerate, onContinue,
}: {
  pages: EditorPage[]
  busy: boolean
  onChange: (next: EditorPage[]) => void
  onRegenerate: () => void
  onContinue: () => void
}) {
  const [editingNo, setEditingNo] = useState<number | null>(null)
  const [verbose, setVerbose] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null)

  const chapters = useMemo(() => groupChapters(pages), [pages])
  const editingIndex = editingNo === null ? -1 : pages.findIndex((page) => page.page_no === editingNo)
  const editing = editingIndex >= 0 ? pages[editingIndex] : null
  const editingChapter = editing ? chapters.find((chapter) => chapter.pages.some((page) => page.page_no === editing.page_no)) : null

  const commit = (next: EditorPage[]) => onChange(renumber(next))
  const replacePage = (pageNo: number, patch: Partial<EditorPage>) =>
    commit(pages.map((page) => (page.page_no === pageNo ? { ...page, ...patch } : page)))

  const movePage = (pageNo: number, delta: number) => {
    const page = pages.find((item) => item.page_no === pageNo)
    const chapter = chapters.find((item) => item.pages.some((item2) => item2.page_no === pageNo))
    if (!page || !chapter) return
    const inChapter = chapter.pages.findIndex((item) => item.page_no === pageNo)
    const target = inChapter + delta
    if (target < 0 || target >= chapter.pages.length) return
    const reordered = [...chapter.pages]
    reordered.splice(inChapter, 1)
    reordered.splice(target, 0, page)
    const others = pages.filter((item) => !chapter.pages.some((item2) => item2.page_no === item.page_no))
    const insertAt = pages.findIndex((item) => item.page_no === chapter.pages[0].page_no)
    const next = [...others]
    next.splice(insertAt, 0, ...reordered)
    onChange(normalizeChapters(next))
  }

  const insertAfter = (pageNo: number, page: Partial<EditorPage>) => {
    const index = pages.findIndex((item) => item.page_no === pageNo)
    const current = pages[index]
    if (!current) return
    const next = [...pages]
    next.splice(index + 1, 0, {
      page_no: 0, title: '', role: 'content', outline: '', points: [], keep: true, layout: 'cards_4',
      chapter_no: current.chapter_no, chapter_title: current.chapter_title, ...page,
    })
    onChange(normalizeChapters(next))
  }

  const removePage = (pageNo: number) => {
    if (pages.length <= 1) return
    commit(pages.filter((page) => page.page_no !== pageNo))
    if (editingNo === pageNo) setEditingNo(null)
  }

  /** 拆页：把本页要点对半分到两页（同章相邻），不新增任何内容 */
  const splitPage = (pageNo: number) => {
    const index = pages.findIndex((item) => item.page_no === pageNo)
    const page = pages[index]
    const points = page.points.filter((point) => point.trim())
    if (points.length < 2) return
    const half = Math.ceil(points.length / 2)
    const next = [...pages]
    next[index] = { ...page, points: points.slice(0, half) }
    next.splice(index + 1, 0, { ...page, page_no: 0, title: '', points: points.slice(half) })
    onChange(normalizeChapters(next))
  }

  const addChapter = () => {
    const key = chapters.length + 1
    commit([...pages, { page_no: 0, title: '', role: 'content', outline: '', points: [], keep: true, layout: 'cards_4', chapter_no: key, chapter_title: `第 ${key} 章` }])
  }

  const removeChapter = (chapter: EditorChapter) => {
    const remaining = pages.filter((page) => !chapter.pages.some((item) => item.page_no === page.page_no))
    if (!remaining.length) return
    onChange(normalizeChapters(remaining))
    setConfirmDelete(null)
    if (editing && chapter.pages.some((page) => page.page_no === editing.page_no)) setEditingNo(null)
  }

  const moveChapter = (chapter: EditorChapter, delta: number) => {
    const index = chapters.findIndex((item) => item.key === chapter.key)
    const target = index + delta
    if (target < 0 || target >= chapters.length) return
    const ordered = [...chapters]
    ordered.splice(index, 1)
    ordered.splice(target, 0, chapter)
    onChange(normalizeChapters(ordered.flatMap((item) => item.pages)))
  }

  const addTransition = (chapter: EditorChapter) => {
    const first = chapter.pages[0]
    insertAfter(first.page_no - 1 >= 1 ? first.page_no - 1 : first.page_no, {
      title: chapter.title, role: 'section', layout: 'section',
    })
  }

  const addContentPage = (chapter: EditorChapter) => {
    const last = chapter.pages[chapter.pages.length - 1]
    insertAfter(last.page_no, {})
  }

  /** 批量：给每个「开头不是过渡页」的章节补一张过渡页（已经是过渡页的章节不动） */
  const batchAddTransitions = () => {
    let next = [...pages]
    chapters.forEach((chapter) => {
      if (isTransition(chapter.pages[0])) return
      const first = chapter.pages[0]
      const index = next.findIndex((page) => page.page_no === first.page_no)
      next.splice(index, 0, {
        page_no: 0, title: chapter.title, role: 'section', outline: '', points: [], keep: true, layout: 'section',
        chapter_no: first.chapter_no, chapter_title: first.chapter_title,
      })
    })
    onChange(normalizeChapters(next))
  }

  const pageIndexInList = editing ? pages.findIndex((page) => page.page_no === editing.page_no) : -1

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body-sm text-ink-sub">
          结构总览 <span className="num">{chapters.length}</span> 章 · <span className="num">{pages.length}</span> 页 · 点击卡片即可编辑内容
        </span>
        <span className="flex-1" />
        <button type="button" className="btn btn-secondary rounded-full!" disabled={busy} onClick={batchAddTransitions}
                title="给每章开头补一张过渡页；已经是过渡页的章节不动">批量添加过渡页</button>
        <div className="flex items-center gap-1" role="group" aria-label="视图密度">
          <button type="button" className={cn('btn rounded-full!', !verbose ? 'btn-primary' : 'btn-secondary')} aria-pressed={!verbose} onClick={() => setVerbose(false)}>精简视图</button>
          <button type="button" className={cn('btn rounded-full!', verbose ? 'btn-primary' : 'btn-secondary')} aria-pressed={verbose} onClick={() => setVerbose(true)}>原文视图</button>
        </div>
      </div>

      <div className="outline-board">
        {chapters.map((chapter) => (
          <div className="outline-chapter-row" key={chapter.key}>
            <div className="outline-chapter">
              <div className="flex flex-wrap items-center gap-1">
                <span className="text-body-sm font-semibold">{chapter.title}</span>
                <span className="text-caption text-ink-sub"><span className="num">{chapter.pages.length}</span> 页</span>
              </div>
              <div className="outline-chapter-actions">
                <button type="button" className="btn btn-secondary h-8! text-body-sm" disabled={busy} onClick={() => addTransition(chapter)} title="在本章开头插入一张过渡页">+ 过渡页</button>
                <button type="button" className="btn btn-secondary h-8! text-body-sm" disabled={busy} onClick={() => addContentPage(chapter)} title="在本章末尾新增一张空白内容页">+ 内容页</button>
              </div>
              <div className="outline-chapter-actions">
                <button type="button" className="link" disabled={busy || chapters[0].key === chapter.key} onClick={() => moveChapter(chapter, -1)}>上移</button>
                <button type="button" className="link" disabled={busy || chapters[chapters.length - 1].key === chapter.key} onClick={() => moveChapter(chapter, 1)}>下移</button>
                {confirmDelete === `c${chapter.key}`
                  ? <button type="button" className="link is-danger" disabled={busy} onClick={() => removeChapter(chapter)}>确认删除本章</button>
                  : <button type="button" className="link" disabled={busy || pages.length === chapter.pages.length} onClick={() => setConfirmDelete(`c${chapter.key}`)} title={pages.length === chapter.pages.length ? '至少要保留 1 页' : '删除本章全部页面'}>删除本章</button>}
              </div>
            </div>

            <div className="outline-pages">
              {chapter.pages.map((page) => (
                <article key={page.page_no} className="outline-page-card" role="button" tabIndex={0}
                         onClick={() => setEditingNo(page.page_no)}
                         onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setEditingNo(page.page_no) } }}
                         aria-label={`编辑第 ${page.page_no} 页`}>
                  <header className="outline-page-head">
                    <span className="num font-semibold text-primary">P{page.page_no}</span>
                    <span className="tag">{typeLabel(page)}</span>
                    <span className="flex-1" />
                    <span className="outline-page-tools" onClick={(event) => event.stopPropagation()}>
                      <button type="button" className="outline-icon" aria-label="前移" disabled={busy || chapter.pages[0].page_no === page.page_no} onClick={() => movePage(page.page_no, -1)}>←</button>
                      <button type="button" className="outline-icon" aria-label="后移" disabled={busy || chapter.pages[chapter.pages.length - 1].page_no === page.page_no} onClick={() => movePage(page.page_no, 1)}>→</button>
                      <button type="button" className="outline-icon" aria-label="新增一页" disabled={busy} onClick={() => insertAfter(page.page_no, {})}>+</button>
                      <button type="button" className="outline-icon" aria-label="拆页" disabled={busy || page.points.filter((point) => point.trim()).length < 2} title="把本页要点对半分到两页" onClick={() => splitPage(page.page_no)}>⧉</button>
                      <button type="button" className="outline-icon is-danger" aria-label="删除此页" disabled={busy || pages.length <= 1} onClick={() => removePage(page.page_no)}>🗑</button>
                    </span>
                  </header>
                  <h3 className="outline-page-title">{page.title?.trim() || '（未命名页）'}</h3>
                  {page.points.filter((point) => point.trim()).length > 0
                    ? <ul className="outline-page-points">
                        {(verbose ? page.points : page.points.slice(0, 2)).filter((point) => point.trim()).map((point, index) => <li key={index}>{point}</li>)}
                        {!verbose && page.points.filter((point) => point.trim()).length > 2 && <li className="text-ink-muted">…还有 <span className="num">{page.points.filter((point) => point.trim()).length - 2}</span> 条要点</li>}
                      </ul>
                    : <p className="m-0 text-caption text-ink-muted">暂无要点{verbose && page.outline ? ` · ${page.outline}` : ''}</p>}
                  {verbose && page.outline && <p className="m-0 mt-1 text-caption text-ink-sub">{page.outline}</p>}
                </article>
              ))}
              {chapter.pages.length === 0 && <p className="m-0 text-caption text-ink-muted">本章还没有页面</p>}
            </div>
          </div>
        ))}

        <button type="button" className="outline-add-chapter" disabled={busy} onClick={addChapter}>+ 新增章节</button>
      </div>

      <ActionBar>
        <span><span className="num">{chapters.length}</span> 章 · <span className="num">{pages.length}</span> 页</span>
        <button type="button" className="btn btn-secondary rounded-full" disabled={busy} onClick={onRegenerate}>{busy ? '正在生成…' : '重新生成大纲'}</button>
        <button type="button" className="btn btn-primary rounded-full px-6" disabled={busy || !pages.length} onClick={onContinue}>进入内容梳理 ›</button>
      </ActionBar>

      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true"
             aria-label={`编辑第 ${editing.page_no} 页`} onClick={() => setEditingNo(null)}>
          <div className="card flex w-full max-w-[42rem] flex-col gap-3" onClick={(event) => event.stopPropagation()}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="num font-semibold text-primary">P{editing.page_no}</span>
              <span className="tag">{typeLabel(editing)}</span>
              <span className="text-body-sm text-ink-sub">{editingChapter?.title}</span>
              <span className="flex-1" />
              <button type="button" className="btn btn-secondary h-8! text-body-sm" onClick={() => setEditingNo(null)}>关闭</button>
            </div>

            <label className="flex flex-col gap-1">
              <span className="metric-label">本页标题</span>
              <input className="input" value={editing.title} placeholder="本页标题（可留空）"
                     onChange={(event) => replacePage(editing.page_no, { title: event.target.value })} />
            </label>

            <label className="flex flex-col gap-1">
              <span className="metric-label">本页原文 <span className="text-ink-muted">请核对本页内容，后续 AI 将基于此内容继续梳理</span></span>
              <textarea className="input h-52! resize-y py-2!" value={editing.points.join('\n')} placeholder="每行一条要点"
                        onChange={(event) => replacePage(editing.page_no, { points: event.target.value.split('\n') })} />
            </label>

            <div className="flex flex-wrap items-center gap-2">
              <span className="metric-label">本页操作</span>
              <button type="button" className="btn btn-secondary h-8! text-body-sm" disabled={busy || editingChapter?.pages[0].page_no === editing.page_no} onClick={() => movePage(editing.page_no, -1)}>← 前移</button>
              <button type="button" className="btn btn-secondary h-8! text-body-sm" disabled={busy || editingChapter?.pages[editingChapter.pages.length - 1].page_no === editing.page_no} onClick={() => movePage(editing.page_no, 1)}>后移 →</button>
              <button type="button" className="btn btn-secondary h-8! text-body-sm" disabled={busy} onClick={() => insertAfter(editing.page_no, {})}>+ 新增</button>
              <button type="button" className="btn btn-secondary h-8! text-body-sm" disabled={busy || editing.points.filter((point) => point.trim()).length < 2} title="把本页要点对半分到两页" onClick={() => splitPage(editing.page_no)}>⧉ 拆页</button>
              {confirmDelete === `p${editing.page_no}`
                ? <button type="button" className="btn btn-danger h-8! text-body-sm" disabled={busy} onClick={() => { removePage(editing.page_no) }}>确认删除此页</button>
                : <button type="button" className="btn btn-secondary h-8! text-body-sm" disabled={busy || pages.length <= 1} title={pages.length <= 1 ? '至少要保留 1 页' : '删除本页'} onClick={() => setConfirmDelete(`p${editing.page_no}`)}>🗑 删除此页</button>}
            </div>

            <div className="flex items-center gap-2">
              <button type="button" className="btn btn-secondary flex-1 rounded-full" disabled={pageIndexInList <= 0}
                      onClick={() => setEditingNo(pages[pageIndexInList - 1].page_no)}>← 上一页</button>
              <button type="button" className="btn btn-secondary flex-1 rounded-full" disabled={pageIndexInList < 0 || pageIndexInList >= pages.length - 1}
                      onClick={() => setEditingNo(pages[pageIndexInList + 1].page_no)}>下一页 →</button>
              <button type="button" className="btn btn-primary flex-1 rounded-full" onClick={() => setEditingNo(null)}>完成</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
