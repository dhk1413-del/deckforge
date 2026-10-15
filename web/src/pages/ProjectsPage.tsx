/** 项目：卡片网格（封面 / 标题 / 元信息 / 状态 / 下载）+ 名称·阶段·项目类别筛选；
 *  类别为「备注生成」时改为列出备注任务（备注不是 project，数据来自 GET /api/notes）。 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { ApiError, configureProject, deleteProject, listNotes, listProjects } from '../api'
import { useAsync } from '../hooks/useAsync'
import { cn, notesStatusLabel, projectStageLabel, statusLabel } from '../lib/format'
import { EmptyState, ErrorState, Loading } from '../components/StateBlock'
import { IconCheck, IconClock } from '../components/Icons'
import { useToast } from '../components/Toast'
import { useModalFocus } from '../hooks/useModalFocus'
import { Link, readQuery, navigate } from '../router'
import type { NotesJob, Project, ProjectExportBrief } from '../types'

/** 项目类别：前三个按后端 flow 事实判定，备注是独立实体（GET /api/notes） */
const CATEGORY_OPTIONS: Array<{ key: string; label: string }> = [
  { key: '', label: '全部类别' },
  { key: 'wizard', label: 'PPT生成' },
  { key: 'beautify', label: 'PPT美化' },
  { key: 'editable', label: '图片转可编辑' },
  { key: 'notes', label: '备注生成' },
]

/* 导出类型的真实名称（后端 kind → 界面文案），不认识的原样显示 */
const EXPORT_LABEL: Record<string, string> = {
  image: '图片版 PPT',
  native: '原生可编辑 PPT',
  editable_hi: '转文字可编辑 PPT',
  beautify_image: '美化图片版 PPT',
  beautify_editable: '美化可编辑版 PPT',
}

/** 状态 → 卡片状态行的图标与语气（如实映射后端 status，不额外造状态） */
function statusTone(status: string) {
  if (status === 'done') return { icon: 'check' as const, cls: 'text-success-ink' }
  if (['generating', 'running', 'queued', 'pending'].includes(status)) return { icon: 'clock' as const, cls: 'text-warn-ink' }
  if (['failed', 'error'].includes(status)) return { icon: 'clock' as const, cls: 'text-danger-ink' }
  return { icon: 'clock' as const, cls: 'text-ink-muted' }
}



const fmtDay = (iso?: string) => {
  const date = new Date(iso || '')
  return Number.isNaN(date.getTime()) ? '—' : `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`
}
const fileSize = (bytes?: number) => {
  if (!bytes) return ''
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)}MB` : `${Math.max(1, Math.round(bytes / 1024))}KB`
}

/** 重命名弹窗（真实调用 PATCH /projects/{id}，只改标题） */
function RenameDialog({ project, onClose, onSaved }: { project: Project; onClose: () => void; onSaved: () => void }) {
  const modalRef = useModalFocus(onClose)
  const [title, setTitle] = useState(project.title)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const save = async () => {
    if (!title.trim()) { setError('名称不能为空'); return }
    setBusy(true); setError(null)
    try { await configureProject(project.id, { title: title.trim() }); onSaved(); onClose() }
    catch (e) { setError((e as { detail?: string })?.detail || String(e)) }
    finally { setBusy(false) }
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" ref={modalRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="重命名项目" onClick={onClose}>
      <div className="card flex w-full max-w-md flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <h3 className="m-0 text-h3">重命名项目</h3>
        <label className="flex flex-col gap-1 text-body-sm">项目名称
          <input className="input" value={title} autoFocus onChange={(e) => setTitle(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') void save() }} />
        </label>
        {error && <div className="error-box text-body-sm" role="alert">{error}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void save()}>{busy ? '保存中…' : '保存'}</button>
        </div>
      </div>
    </div>
  )
}

/** 删除确认弹窗（真实调用 DELETE /projects/{id}，不可撤销）：逐条列出会消失的东西，并说明账本保留 */
function DeleteDialog({ project, onClose, onDeleted }: { project: Project; onClose: () => void; onDeleted: (title: string) => void }) {
  const modalRef = useModalFocus(onClose)
  const inflight = useRef(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const remove = async () => {
    if (inflight.current) return
    inflight.current = true
    setBusy(true); setError(null)
    try { await deleteProject(project.id) }
    catch (e) {
      if (!(e instanceof ApiError && e.status === 404)) {
        inflight.current = false
        setBusy(false)
        setError((e as { detail?: string })?.detail || String(e))
        return
      }
    }
    onDeleted(project.title)
    onClose()
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" ref={modalRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label="删除项目" onClick={onClose}>
      <div className="card flex w-full max-w-md flex-col gap-3" onClick={(e) => e.stopPropagation()}>
        <h3 className="m-0 text-h3">删除项目</h3>
        <p className="m-0 text-body-sm">确定删除「{project.title || '(无标题)'}」？<strong>此操作不可撤销。</strong></p>
        <ul className="m-0 flex list-disc flex-col gap-1 pl-5 text-body-sm text-ink-sub">
          <li><span className="num">{project.page_count}</span> 页的页面记录、原稿与生成图片</li>
          <li>{project.exports?.length ? <>导出文件 <span className="num">{project.exports.length}</span> 份与导出记录</> : '导出记录'}</li>
          <li>精细重建现场与该项目的任务记录</li>
          <li>用量账本里的成本记录会<strong>保留</strong>（删项目不抹账）</li>
        </ul>
        {error && <div className="error-box text-body-sm" role="alert">{error}</div>}
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" disabled={busy} onClick={onClose}>取消</button>
          <button type="button" className="btn btn-danger" disabled={busy} onClick={() => void remove()}>{busy ? '删除中…' : '删除项目'}</button>
        </div>
      </div>
    </div>
  )
}

/** 单张项目卡：封面 + 名称 + 元信息 + 状态 + 下载（下拉可选其它导出） */
function ProjectCard({ project, onRenamed, onDeleted }: { project: Project; onRenamed: () => void; onDeleted: (title: string) => void }) {
  const exports = project.exports ?? []
  const [menu, setMenu] = useState(false)
  const [downloads, setDownloads] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [shotFailed, setShotFailed] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)
  const latest = exports[0]
  const tone = statusTone(project.status)

  useEffect(() => {
    if (!menu && !downloads) return
    const onDown = (event: MouseEvent) => { if (!wrapRef.current?.contains(event.target as Node)) { setMenu(false); setDownloads(false) } }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') { setMenu(false); setDownloads(false) } }
    window.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('mousedown', onDown); window.removeEventListener('keydown', onKey) }
  }, [menu, downloads])

  const stageStep = project.resume_step ?? 1        // 后端未给阶段时按第①步显示，不编造

  return (
    <article className="project-card" ref={wrapRef}>
      <div className="project-cover">
        <Link to={`/projects/${encodeURIComponent(project.id)}`} className="project-cover-link"
              title={`打开「${project.title || '未命名项目'}」`} aria-label={`打开项目：${project.title || '未命名项目'}`}>
          {project.cover_url && !shotFailed
            ? <img src={project.cover_url} alt={`${project.title} 封面`} loading="lazy" onError={() => setShotFailed(true)} />
            : <span className="project-cover-empty">{project.cover_url ? '封面图不可访问' : '暂无封面'}</span>}
        </Link>
        <button type="button" className="project-more" aria-label="更多操作" aria-haspopup="menu" aria-expanded={menu} onClick={() => { setMenu((v) => !v); setDownloads(false) }}>…</button>
        {menu && <div className="project-menu" role="menu">
          <button type="button" role="menuitem" onClick={() => navigate(`/projects/${encodeURIComponent(project.id)}`)}>打开工作台</button>
          <button type="button" role="menuitem" onClick={() => { setRenaming(true); setMenu(false) }}>重命名</button>
          <button type="button" role="menuitem" onClick={() => navigate('/usage')}>查看用量</button>
          <button type="button" role="menuitem" className="is-danger" onClick={() => { setDeleting(true); setMenu(false) }}>删除项目</button>
        </div>}
      </div>

      <Link to={`/projects/${encodeURIComponent(project.id)}`} className="project-title" title={project.title}>{project.title || '(无标题)'}</Link>
      <p className="project-meta project-meta-facts">
        <span className="fact-pages"><span className="num">{project.page_count}</span> 页</span>
        <span className="fact-sep" aria-hidden="true">·</span>
        <span className="fact-date">{fmtDay(project.created_at)}</span>
        <span className="fact-sep" aria-hidden="true">·</span>
        <span className={cn('fact-stage', stageStep >= 5 && 'is-done', stageStep === 4 && 'is-doing')}>
          阶段：{projectStageLabel(stageStep)}
        </span>
      </p>
      <p className={`project-status ${tone.cls}`}>
        {tone.icon === 'check' ? <IconCheck className="h-4 w-4" /> : <IconClock className="h-4 w-4" />}
        {statusLabel(project.status)}
        {project.style_pack_id && <span className="text-ink-muted">· {project.style_pack_id}</span>}
      </p>

      <div className="project-actions">
        {latest && latest.file ? <>
          <a className="project-download" href={latest.file} download>{exports.length > 1 ? '下载最新' : '下载'}</a>
          <button type="button" className="project-download-more" aria-label="选择其它导出" aria-haspopup="menu" aria-expanded={downloads} onClick={() => { setDownloads((v) => !v); setMenu(false) }}>▾</button>
          {downloads && <div className="project-menu project-menu-down" role="menu">
            {exports.map((item: ProjectExportBrief) => item.file
              ? <a key={item.id} role="menuitem" className="project-menu-item" href={item.file} download>
                  {EXPORT_LABEL[item.kind] || item.kind} · <span className="num">{item.pages}</span> 页{item.size_bytes ? ` · ${fileSize(item.size_bytes)}` : ''}
                </a>
              : <span key={item.id} className="project-menu-item is-disabled" role="menuitem" aria-disabled="true">
                  {EXPORT_LABEL[item.kind] || item.kind} · 产物文件缺失，无法下载
                </span>)}
          </div>}
        </> : <button type="button" className="project-download is-disabled" disabled>{latest ? '产物文件缺失，无法下载' : '生成后可下载'}</button>}
      </div>

      {renaming && <RenameDialog project={project} onClose={() => setRenaming(false)} onSaved={onRenamed} />}
      {deleting && <DeleteDialog project={project} onClose={() => setDeleting(false)} onDeleted={onDeleted} />}
    </article>
  )
}

export function ProjectsPage() {
  const toast = useToast()
  const projects = useAsync(listProjects, [])
  useEffect(()=>{window.addEventListener('focus',projects.reload);const poll=window.setInterval(projects.reload,5000);return()=>{window.removeEventListener('focus',projects.reload);window.clearInterval(poll)}},[projects.reload])
  const [deletedIds, setDeletedIds] = useState<string[]>([])
  useEffect(() => {
    if (!projects.data) return
    const listedIds = new Set(projects.data.items.map(project => project.id))
    setDeletedIds(ids => {
      const remaining = ids.filter(id => listedIds.has(id))
      return remaining.length === ids.length ? ids : remaining
    })
  }, [projects.data])
  const items = useMemo(
    () => (projects.data?.items ?? []).filter(project => !deletedIds.includes(project.id)),
    [projects.data, deletedIds])
  const [filters, setFilters] = useState(readQuery)
  useEffect(() => {
    const sync = () => setFilters(readQuery())
    window.addEventListener('deckforge:route', sync)
    return () => window.removeEventListener('deckforge:route', sync)
  }, [])
  const updateFilter = (key: string, value: string) => {
    const next = {...filters, [key]: value}
    setFilters(next)
    const query = Object.entries(next).filter(([, v]) => v).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
    navigate(`/projects${query ? '?' + query : ''}`)
  }
  /** 备注任务：只有切到「备注生成」这一类别时才展示，数据来自独立接口 */
  const notes = useAsync(listNotes, [])
  const noteItems = notes.data?.items ?? []
  const matchName = (title: string) => !filters.q || (title || '').toLocaleLowerCase().includes(filters.q.trim().toLocaleLowerCase())
  const noteMatches = noteItems.filter(note => matchName(note.title))
  const byCategory = filters.category === 'notes' ? [] : items.filter(p =>
    matchName(p.title) &&
    (!filters.stage || String(p.resume_step || 1) === filters.stage) &&
    (!filters.category || p.flow === filters.category))
  const filtered = byCategory
  const hasFilter = Boolean(filters.q || filters.stage || filters.category)

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="m-0 text-h1 font-semibold">我的项目</h1>
        <span className="flex-1" />
        <button type="button" className="btn btn-secondary" onClick={projects.reload}>刷新</button>
      </div>

      <div className="card flex flex-wrap items-end gap-3">
        <label>按名称搜索<input className="input" type="search" value={filters.q || ''} onChange={e => updateFilter('q', e.target.value)} placeholder="输入项目名称" /></label>
        <label>项目类别<select className="input" value={filters.category || ''} onChange={e => updateFilter('category', e.target.value)}>{CATEGORY_OPTIONS.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></label>
        {filters.category !== 'notes' && <label>阶段<select className="input" value={filters.stage || ''} onChange={e => updateFilter('stage', e.target.value)}><option value="">全部阶段</option>{[1,2,3,4,5].map(step => <option key={step} value={step}>{projectStageLabel(step)}</option>)}</select></label>}
        <button type="button" className="btn btn-secondary" disabled={!hasFilter} onClick={() => {setFilters({}); navigate('/projects')}}>清除搜索与筛选</button>
        <span role="status" className="num">{hasFilter ? (filters.category === 'notes' ? `找到 ${noteMatches.length} 个备注任务` : `找到 ${filtered.length} 个项目`) : ''}</span>
      </div>
      {filters.category !== 'notes' && items.length > 0 && filtered.length === 0 && <div className="card"><EmptyState title="没有符合条件的项目" desc="请更换项目名称、项目类别或阶段，或清除搜索与筛选。" /></div>}
      {filters.category === 'notes' && !notes.loading && !notes.error && noteItems.length > 0 && noteMatches.length === 0 && <div className="card"><EmptyState title="没有符合条件的备注任务" desc="请更换名称关键词，或清除搜索与筛选。" /></div>}

      {projects.loading && !items.length && <Loading rows={3} label="加载项目…" />}
      {projects.error && <ErrorState error={projects.error} onRetry={projects.reload} title="项目列表加载失败" />}

      {filters.category !== 'notes' && !projects.loading && !projects.error && items.length === 0 && (
        <div className="card">
          <EmptyState
            title="还没有项目"
            desc="从「生成向导」开始：上传原稿（或粘贴文本）→ 确认页清单 → 内容梳理 → 选风格 → 生成。全套零 key 也能跑通。"
            actionLabel="去生成向导"
            to="/"
          />
        </div>
      )}

      {filters.category === 'notes' && <>
        {notes.loading && !noteItems.length && <Loading rows={3} label="加载备注任务…" />}
        {notes.error && <ErrorState error={notes.error} onRetry={notes.reload} title="备注任务加载失败" />}
        {!notes.loading && !notes.error && noteItems.length === 0 && (
          <div className="card"><EmptyState title="还没有备注任务" desc="到「备注生成」上传 PPTX / PDF，即可按页生成讲稿备注。" actionLabel="去备注生成" to="/notes" /></div>
        )}
        {noteMatches.length > 0 && <div className="project-grid">
          {noteMatches.map((note: NotesJob) => {
            const tone = statusTone(note.status)
            return <article key={note.id} className="project-card">
              <Link to={`/notes/${encodeURIComponent(note.id)}`} className="project-title" title={note.title}>{note.title || '(无标题)'}</Link>
              <p className="project-meta project-meta-facts">
                <span className="fact-pages"><span className="num">{note.pages}</span> 页</span>
                <span className="fact-sep" aria-hidden="true">·</span>
                <span className="fact-date">{fmtDay(note.created_at)}</span>
              </p>
              <p className={`project-status ${tone.cls}`}>
                {tone.icon === 'check' ? <IconCheck className="h-4 w-4" /> : <IconClock className="h-4 w-4" />}
                {notesStatusLabel(note.status)}
              </p>
              <div className="project-actions">
                <Link className="project-download" to={`/notes/${encodeURIComponent(note.id)}`}>打开备注</Link>
              </div>
            </article>
          })}
        </div>}
      </>}
      {filtered.length > 0 && <div className="project-grid">
        {filtered.map(project => <ProjectCard key={project.id} project={project}
          onRenamed={() => {projects.reload(); toast.success('已重命名')}}
          onDeleted={(title) => {
            setDeletedIds(ids => ids.includes(project.id) ? ids : [...ids, project.id])
            projects.reload()
            toast.success('已删除项目', title)
          }} />)}
      </div>}
    </div>
  )
}
