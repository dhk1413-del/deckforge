/**
 * 生成向导：5 步
 * 首页（#/）选定文档后跳到这里，会自动消费待办文件并走同一套上传逻辑。
 *  ① 上传（拖拽 / 粘贴文本）  ② 页面确认（勾选保留 + 改标题/布局）
 *  ③ 内容梳理（DeepSeek，无 key 本地切页兜底）  ④ 选择风格
 *  ⑤ 生成结果（保留转可编辑页签）
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  createProject,
  getProject, getProjectJobs, getSlides, configureProject,
  getSourcePages,
  listLayouts,
  listStylePacks,
  postOutline,
  putPages,
  uploadSource,
  ApiError,
} from '../api'
import { ActionBar, FlowSteps, PageSelectGrid } from '../components/FlowKit'
import { ContentEditor } from '../components/ContentEditor'
import { Dropzone } from '../components/Dropzone'
import { useTextReady } from '../components/ProviderStatus'
import { ProjectWorkbench } from '../components/ProjectWorkbench'
import { SlidePreview } from '../components/SlidePreview'
import { EmptyState, ErrorState, Loading, Notice, NotConfiguredBanner } from '../components/StateBlock'
import { StylePackCard } from '../components/StylePackCard'
import { WIZARD_STEPS, type WizardStepNo } from '../components/Steps'
import { useToast } from '../components/Toast'
import { Link, navigate, readQuery, registerLeaveGuard, useRoute } from '../router'
import { takePendingFile } from '../pendingFile'
import { useAsync } from '../hooks/useAsync'
import { cn, pageNo as padPageNo } from '../lib/format'
import type { LayoutInfo, OutlinePage, Slide, SourcePagesResponse, SourceType, UploadResponse } from '../types'

/** 离线兜底布局清单（与契约 /api/layouts 示例一致，后端不可用时仍可编辑页清单） */
const LAYOUT_FALLBACK: LayoutInfo[] = [
  { key: 'cover', title: '封面', best_for: '整册首页', slots: ['title', 'subtitle', 'meta'] },
  { key: 'section', title: '章节页', best_for: '分段过渡', slots: ['title', 'subtitle'] },
  { key: 'cards_4', title: '四卡要点', best_for: '并列要点', slots: ['title', 'items'] },
  { key: 'comparison_2col', title: '左右对比', best_for: '方案对比', slots: ['title', 'left', 'right'] },
  { key: 'data_chart', title: '数据图表', best_for: '指标展示', slots: ['title', 'chart', 'caption'] },
  { key: 'timeline', title: '时间线', best_for: '流程/历程', slots: ['title', 'milestones'] },
  { key: 'summary', title: '总结页', best_for: '收尾', slots: ['title', 'points'] },
]

const SOURCE_PAGE_RETRY_LIMIT = 10

/** 第 ② 步可编辑的页清单条目 */
interface PageDraft {
  slide_id?: string
  content_revision?: number
  source_page_no?: number | null
  valid?: boolean
  page_no: number
  title: string
  role: string
  outline: string
  points: string[]
  keep: boolean
  layout: string
}

const ACCEPT = '.md,.markdown,.txt,.docx,.pdf,.pptx'
/** 每页讲解时长（分钟）：曾是可调输入项，按用户要求去掉界面，统一用这个默认值喂给大纲接口。 */
const PAGE_MINUTES = 1.5

/** 来源类型猜测（后缀 → 契约 source_type） */
function guessSourceType(name: string): SourceType {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'md' || ext === 'markdown') return 'markdown'
  if (ext === 'docx') return 'docx'
  if (ext === 'pdf') return 'pdf'
  if (ext === 'pptx') return 'pptx'
  return 'text'
}

/** 由页数生成初始草稿（标题待第 ③ 步梳理后回填） */
function draftPages(count: number): PageDraft[] {
  const n = Math.max(1, Math.min(80, Math.round(count) || 1))
  return Array.from({ length: n }, (_, i) => {
    const no = i + 1
    return {
      page_no: no,
      title: '',
      role: no === 1 ? 'cover' : no === n ? 'summary' : 'content',
      outline: '',
      points: [],
      keep: true,
      layout: no === 1 ? 'cover' : no === n ? 'summary' : 'cards_4',
    }
  })
}

export function WizardPage() {
  const toast = useToast()

  const route = useRoute()
  const step = (Number(route.params.step) || 1) as WizardStepNo
  const [restoring, setRestoring] = useState(Boolean(route.params.id))
  const [restoreError, setRestoreError] = useState<ApiError | null>(null)
  const [pagesConfirmed, setPagesConfirmed] = useState(false)
  const [contentConfirmed, setContentConfirmed] = useState(false)
  const [hasResults, setHasResults] = useState(false)
  const [projectSize, setProjectSize] = useState('2K')
  const [tab, setTab] = useState<'generate' | 'editable'>(readQuery().tab === 'editable' ? 'editable' : 'generate')
  const [errorAt, setErrorAt] = useState<number | undefined>(undefined)

  // ① 上传
  const [title, setTitle] = useState('')
  const [sourceType, setSourceType] = useState<SourceType>('markdown')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<ApiError | null>(null)

  // ② 页面确认 / ③ 内容梳理
  const [projectId, setProjectId] = useState<string | null>(null)
  const [parsed, setParsed] = useState<UploadResponse | null>(null)
  const [pages, setPages] = useState<PageDraft[]>([])
  const [savingPages, setSavingPages] = useState(false)
  const [pagesError, setPagesError] = useState<ApiError | null>(null)
  const [targetPages, setTargetPages] = useState(13)
  const [outline, setOutline] = useState<OutlinePage[] | null>(null)
  const [outlineMeta, setOutlineMeta] = useState<{ configured?: boolean; hint?: string; fallback?: string } | null>(null)
  const [outlining, setOutlining] = useState(false)
  const [outlineError, setOutlineError] = useState<ApiError | null>(null)
  const [sourcePages, setSourcePages] = useState<SourcePagesResponse | null>(null)
  const [sourceUploadDone, setSourceUploadDone] = useState(false)
  const [sourcePreviewIndex, setSourcePreviewIndex] = useState<number | null>(null)
  const [sourceLargeReady, setSourceLargeReady] = useState<Set<number>>(() => new Set())
  const [sourceLargeLoading, setSourceLargeLoading] = useState<number | null>(null)

  // ④ 选择风格
  const [stylePackId, setStylePackId] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState<string | null>(null)

  const reachedStep4 = true
  const layoutsAsync = useAsync(listLayouts, [], reachedStep4)
  const packsAsync = useAsync(listStylePacks, [], reachedStep4)
  const layouts = layoutsAsync.data?.items?.length ? layoutsAsync.data.items : LAYOUT_FALLBACK
  const packs = packsAsync.data?.items ?? []
  const [category, setCategory] = useState('全部')

  const goto = (next: WizardStepNo, id = projectId) => {
    navigate(id ? `/wizard/${encodeURIComponent(id)}/${next}` : `/wizard?style=${encodeURIComponent(stylePackId || '')}`)
  }

  useEffect(() => {
    const style = readQuery().style
    if (style) setStylePackId(style)
  }, [])

  useEffect(() => {
    const id = route.params.id
    if (!id) return
    let cancelled = false
    setRestoring(true)
    Promise.all([getProject(id), getSlides(id)]).then(([project, slides]) => {
      if (cancelled) return
      setHasResults(slides.some(p => Boolean(p.image_url) || ['running','failed','interrupted'].includes(p.status)))
      setProjectId(id)
      projectStamp.current=project.updated_at
      setTitle(project.title)
      setSourceType(project.source_type as SourceType)
      const text = project.parsed_text || ''
      const count = project.target_pages || Math.max(3, Math.min(30, Math.round(text.length / 420) || 3))
      setTargetPages(count)
      setParsed(text ? { parsed_text: text, char_count: text.length, suggested_pages: count, warnings: [] } : null)
      setSourceUploadDone(true)
      setPages(slides.length ? slides.map((slide) => {
        const draft = project.page_drafts?.find(p => p.page_no === slide.page_no)
        return { slide_id: slide.slide_id, content_revision:slide.content_revision, source_page_no:slide.source_page_no, valid: slide.source_available !== 0, page_no: slide.page_no, title: slide.title,
          role: slide.role || 'content', outline: slide.outline || '', points: slide.points || [],
          keep: draft?.keep ?? Boolean(slide.keep), layout: draft?.layout || slide.layout || 'cards_4' }
      }) : project.page_drafts?.length ? project.page_drafts.map(p => ({ ...p, role: 'content', outline: '', points: [] })) : draftPages(count))
      setOutline(slides.length ? slides.map(p => ({page_no: p.page_no, title:p.title, role:p.role || 'content', outline:p.outline || '', points:p.points || []})) : null)
      setPagesConfirmed(Boolean(project.pages_confirmed))
      setContentConfirmed(Boolean(project.content_confirmed))
      setStylePackId(project.style_pack_id || readQuery().style || null)
      setProjectSize(project.size || '2K')
      if (!route.params.step) navigate(`/wizard/${encodeURIComponent(id)}/${project.resume_step || 1}${window.location.hash.includes('?') ? '?' + window.location.hash.split('?')[1] : ''}`)
    }).catch(e => { if (!cancelled) setRestoreError(e as ApiError) }).finally(() => {if (!cancelled) setRestoring(false)})
    return () => {cancelled = true}
  }, [route.params.id])

  const [taskRunning,setTaskRunning] = useState(false)
  const projectStamp = useRef<string | undefined>(undefined)
  const [remoteConfig,setRemoteConfig] = useState<Awaited<ReturnType<typeof getProject>> | null>(null)
  const [configConflict,setConfigConflict] = useState(false)
  type ConfigPayload = Parameters<typeof configureProject>[1]
  const configQueue = useRef<Promise<boolean>>(Promise.resolve(true))
  const configDraft = useRef<ConfigPayload>({})
  const configSequence = useRef(0)
  const [saveState,setSaveState] = useState('已保存')
  const [contentSaveState,setContentSaveState] = useState('已保存')
  const [draftTick,setDraftTick] = useState(0)
  const configKey = (id:string) => `deckforge:draft:local-account:${id}:project`
  function stageConfig(payload:ConfigPayload) {
    configDraft.current={...configDraft.current,...payload}
    configSequence.current+=1
    if(projectId)localStorage.setItem(configKey(projectId),JSON.stringify(configDraft.current))
    setSaveState('未保存');setDraftTick(n=>n+1)
  }
  function flushConfig():Promise<boolean> {
    const id=projectId
    if(!id)return Promise.resolve(true)
    const pending=configQueue.current.then(async()=>{
      if(configConflict){setSaveState('保存失败');return false}
      while(Object.keys(configDraft.current).length){
        const snapshot={...configDraft.current},sequence=configSequence.current
        setSaveState('正在保存')
        try {
          const project=await configureProject(id,{...snapshot,expected_updated_at:projectStamp.current})
          projectStamp.current=project.updated_at
          for(const key of Object.keys(snapshot) as (keyof ConfigPayload)[]) {
            if(JSON.stringify(configDraft.current[key])===JSON.stringify(snapshot[key])) delete configDraft.current[key]
          }
          const revisions=project.content_revisions || {}
          setPages(prev=>prev.map(p=>({...p,content_revision:p.slide_id?revisions[p.slide_id]??p.content_revision:p.content_revision})))
          if(configDraft.current.page_drafts) configDraft.current.page_drafts=configDraft.current.page_drafts.map(p=>{
            const slide=pages.find(s=>s.page_no===p.page_no);return {...p,revision:slide?.slide_id?revisions[slide.slide_id]??p.revision:p.revision}
          })
          if(sequence===configSequence.current){
            if(snapshot.style_pack_id!==undefined)setStylePackId(project.style_pack_id||null)
            if(snapshot.size!==undefined)setProjectSize(project.size||'2K')
            setPagesConfirmed(Boolean(project.pages_confirmed));setContentConfirmed(Boolean(project.content_confirmed))
          }
          if(Object.keys(configDraft.current).length)localStorage.setItem(configKey(id),JSON.stringify(configDraft.current))
          else{localStorage.removeItem(configKey(id));setSaveState('已保存')}
        }catch(e){if((e as ApiError).status===409){setConfigConflict(true);setRemoteConfig(await getProject(id))}setSaveState('保存失败');toast.error('保存配置失败',(e as ApiError).detail);return false}
      }
      return true
    })
    configQueue.current=pending.catch(()=>false)
    return pending
  }
  function saveConfig(payload:ConfigPayload):Promise<boolean> {stageConfig(payload);return flushConfig()}
  useEffect(()=>{const timer=window.setTimeout(()=>{if(Object.keys(configDraft.current).length)void flushConfig()},700);return()=>window.clearTimeout(timer)},[draftTick,projectId])
  useEffect(()=>{
    if(!projectId)return
    const unregister=registerLeaveGuard(()=>flushConfig())
    const unload=(e:BeforeUnloadEvent)=>{if(Object.keys(configDraft.current).length){e.preventDefault();e.returnValue=''}}
    window.addEventListener('beforeunload',unload)
    return()=>{unregister();window.removeEventListener('beforeunload',unload);void flushConfig()}
  },[projectId])
  useEffect(()=>{
    if(!projectId)return
    const raw=localStorage.getItem(configKey(projectId))
    if(raw)try{const draft=JSON.parse(raw) as ConfigPayload;configDraft.current=draft;setSaveState('未保存');setConfigConflict(true);void getProject(projectId).then(setRemoteConfig);
      if(draft.title!==undefined)setTitle(draft.title)
      if(draft.page_drafts)setPages(prev=>prev.map(p=>({...p,...draft.page_drafts!.find(x=>x.page_no===p.page_no)})))
      setDraftTick(n=>n+1)
    }catch{setSaveState('保存失败')}
  },[projectId])
  useEffect(()=>{
    if(!projectId)return
    const refresh=async()=>{try{const [remote,jobs]=await Promise.all([getProject(projectId),getProjectJobs(projectId)]);setTaskRunning(jobs.items.some(j=>j.kind==='generate'&&['queued','running','cancelling'].includes(j.status)));setRemoteConfig(remote)
      if(Object.keys(configDraft.current).length){if(projectStamp.current && remote.updated_at!==projectStamp.current){setConfigConflict(true);setSaveState('保存失败')}return}
      projectStamp.current=remote.updated_at;setPages(prev=>prev.map(p=>({...p,...remote.page_drafts?.find(d=>d.page_no===p.page_no),content_revision:p.slide_id?remote.content_revisions?.[p.slide_id]??p.content_revision:p.content_revision})));setTitle(remote.title);setStylePackId(remote.style_pack_id||null);setProjectSize(remote.size||'2K');setPagesConfirmed(Boolean(remote.pages_confirmed));setContentConfirmed(Boolean(remote.content_confirmed));setSaveState('已保存')
    }catch(e){toast.error('刷新项目状态失败',(e as ApiError).detail)}}
    void refresh()
    const poll=window.setInterval(()=>void refresh(),5000)
    window.addEventListener('focus',refresh)
    return()=>{window.clearInterval(poll);window.removeEventListener('focus',refresh)}
  },[projectId])
  function pagePayload(next:PageDraft[]) {return next.map(p=>({page_no:p.page_no,title:p.title,keep:p.keep,layout:p.layout,revision:p.content_revision}))}
  async function persistPages(next: PageDraft[]) {
    setPages(next)
    return saveConfig({page_drafts:pagePayload(next)})
  }

  const keptPages = useMemo(() => pages.filter((p) => p.keep && p.valid !== false), [pages])
  const textReady = useTextReady()   // 复用顶栏那份健康探测：用于加载页写清这次走模型还是本地切页
  const categories = useMemo(
    () => ['全部', ...Array.from(new Set(packs.map((p) => p.category)))],
    [packs],
  )
  const visiblePacks = category === '全部' ? packs : packs.filter((p) => p.category === category)
  const sourceSlides = useMemo<Slide[]>(
    () =>
      (sourcePages?.pages ?? []).map((page) => ({
        slide_id: `source-${projectId}-${page.page_no}`,
        page_no: page.page_no,
        title: `原稿 P${String(page.page_no).padStart(2, '0')}`,
        // 预览先显示已有 420px 缩略图；大图预取完成后再替换，避免弹窗像卡死一样空白。
        image_url: sourceLargeReady.has(page.page_no)
          ? `/api/projects/${encodeURIComponent(projectId ?? '')}/source-pages/${page.page_no}?w=1100`
          : page.thumb_url,
        width: page.width,
        height: page.height,
        status: 'done',
        editable: false,
        provider: 'original',
        model: 'pptx',
        size: '1100px',
        cost_cny: 0,
        latency_ms: 0,
        verify: { text_accuracy: 0, issues: [] },
      })),
    [sourcePages, projectId, sourceLargeReady],
  )

  const preloadSourceLarge = useCallback((index: number) => {
    const page = sourcePages?.pages[index]
    if (!page || !projectId || sourceLargeReady.has(page.page_no)) return
    setSourceLargeLoading(page.page_no)
    const image = new Image()
    image.onload = () => {
      setSourceLargeReady((ready) => new Set(ready).add(page.page_no))
      setSourceLargeLoading((loading) => (loading === page.page_no ? null : loading))
    }
    image.onerror = () => setSourceLargeLoading((loading) => (loading === page.page_no ? null : loading))
    image.src = `/api/projects/${encodeURIComponent(projectId)}/source-pages/${page.page_no}?w=1100`
  }, [projectId, sourceLargeReady, sourcePages])

  const openSourcePreview = useCallback((index: number) => {
    setSourcePreviewIndex(index)
    preloadSourceLarge(index)
  }, [preloadSourceLarge])

  /* ---------------- ① 上传 ---------------- */

  async function handleFile(file: File) {
    if (file.size > 30 * 1024 * 1024) {          // 与首页/美化一致：框里写着 30MB，这里就得拦住
      setUploadError(new ApiError(`${file.name} 超过 30MB（${(file.size / 1048576).toFixed(1)}MB）`, 0))
      setErrorAt(1)
      return
    }
    setUploading(true)
    setUploadError(null)
    setErrorAt(undefined)
    setSourceUploadDone(false)
    const guessTitle = title.trim() || file.name.replace(/\.[^.]+$/, '') || '未命名项目'
    try {
      const st = guessSourceType(file.name)
      setSourceType(st)
      setSourcePages(null)
      setSourcePreviewIndex(null)
      setSourceLargeReady(new Set())
      setSourceLargeLoading(null)
      const { id } = await createProject({ title: guessTitle, source_type: st, intake_mode: 'doc' })
      setProjectId(id)
      setTitle(guessTitle)
      const res = await uploadSource(id, file)
      setSourceUploadDone(true)
      setParsed(res)
      const count = res.suggested_pages || Math.max(1, Math.round(res.char_count / 600))
      setTargetPages(count)
      setPages(draftPages(count))
      toast.success(`已解析 ${file.name}`, `${res.char_count} 字 · 建议 ${count} 页`)
      if (stylePackId) await configureProject(id, {style_pack_id: stylePackId})
      goto(2, id)
      // 上传完直接开始梳理内容：不再让用户在第②步二次确认（要重来可用「重新梳理」）
      void runOutline(id, count)
    } catch (e) {
      setUploadError(e as ApiError)
      setErrorAt(1)
    } finally {
      setUploading(false)
    }
  }

  // 首页（#/）选好文档后跳到这里：自动消费待办文件，走同一套上传逻辑（不复制第二套）
  useEffect(() => {
    const pending = takePendingFile()
    if (pending) void handleFile(pending)
    // 只在首次挂载消费一次；handleFile 每次渲染都会重建，故意不入依赖
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])


  // PPTX 上传响应不等待 LibreOffice；上传落盘后才开始查询，并限定轮询时间。
  useEffect(() => {
    if (!projectId || sourceType !== 'pptx' || !sourceUploadDone) return
    let cancelled = false
    let timer: number | undefined
    let attempts = 0
    const retryOrFail = () => {
      if (attempts >= SOURCE_PAGE_RETRY_LIMIT) {
        setSourcePages({ page_count: 0, ready: false, generating: false, pages: [], error: '状态暂不可用' })
        return
      }
      timer = window.setTimeout(() => void refresh(), 1500)
    }
    const refresh = async () => {
      attempts += 1
      try {
        const next = await getSourcePages(projectId)
        if (cancelled) return
        if (next.ready) {
          setSourcePages(next)
          return
        }
        // 后端尚未登记原稿或转换任务暂未就绪时，继续显示生成中并重试。
        setSourcePages({ ...next, error: undefined })
        retryOrFail()
      } catch {
        if (cancelled) return
        // 400/404 与短暂网络故障都可能发生在上传落盘、后台转换的交界处。
        retryOrFail()
      }
    }
    void refresh()
    return () => {
      cancelled = true
      if (timer) window.clearTimeout(timer)
    }
  }, [projectId, sourceType, sourceUploadDone])

  /* ---------------- ② 页面确认 ---------------- */

  async function savePages() {
    if (!projectId) return
    if (!keptPages.length) {
      toast.warn('至少要保留 1 页', '取消勾选后所有页都被排除了')
      return
    }
    setSavingPages(true)
    setPagesError(null)
    try {
      if(!await flushConfig())return
      await putPages(projectId, {
        pages: pages.map((p) => ({
          page_no: p.page_no,
          title: p.title,
          keep: p.keep,
          layout: p.layout,
          revision:p.content_revision,
        })),
      })
      setPagesConfirmed(true)
      setContentConfirmed(false)
      setTargetPages(keptPages.length)
      toast.success(`页清单已保存（保留 ${keptPages.length} 页）`)
      goto(3)
    } catch (e) {
      setPagesError(e as ApiError)
      toast.error('保存页清单失败', (e as ApiError).detail)
    } finally {
      setSavingPages(false)
    }
  }

  /* ---------------- ③ 内容梳理 ---------------- */

  const runOutline = useCallback(async (idArg: string | null = projectId, targetArg: number = targetPages) => {
    const id = idArg
    if (!id) return
    setOutlining(true)
    setOutlineError(null)
    setErrorAt(undefined)
    try {
      const res = await postOutline(id, targetArg, PAGE_MINUTES)
      const slides = await getSlides(id)
      setPagesConfirmed(false)
      setContentConfirmed(false)
      setOutline(res.pages ?? [])
      setOutlineMeta({
        configured: res.configured,
        hint: res.hint,
        fallback: res.fellback,
      })
      // 把梳理结果回填到页清单（标题/role/要点），页数按后端返回对齐
      setPages((prev) =>
        (res.pages ?? []).map((op, i) => {
          const existing = prev.find((p) => p.page_no === op.page_no) ?? prev[i]
          return {
            slide_id: slides.find(s => s.page_no === op.page_no)?.slide_id,
            content_revision:slides.find(s=>s.page_no===op.page_no)?.content_revision,
            source_page_no: slides.find(s => s.page_no === op.page_no)?.source_page_no,
            valid: slides.find(s => s.page_no === op.page_no)?.source_available !== 0,
            page_no: op.page_no,
            title: op.title || existing?.title || '',
            role: op.role || existing?.role || 'content',
            outline: op.outline ?? '',
            points: op.points ?? [],
            keep: existing?.keep ?? true,
            layout: existing?.layout ?? (op.page_no === 1 ? 'cover' : 'cards_4'),
          }
        }),
      )
      if (res.configured === false) {
        toast.warn('未配置 DeepSeek，已本地兜底切页', res.hint)
      } else {
        toast.success(`内容梳理完成：${res.pages?.length ?? 0} 页`)
      }
    } catch (e) {
      setOutlineError(e as ApiError)
      setErrorAt(3)
      toast.error('内容梳理失败', (e as ApiError).detail)
    } finally {
      setOutlining(false)
    }
  }, [projectId, keptPages.length, targetPages, toast])

  /* ---------------- 渲染 ---------------- */

  const uploadStep = (
    <div className="flex flex-col gap-4">
      <div className="card">
        <h2 className="card-title text-h3">上传原稿</h2>

        <label className="flex flex-col gap-1 md:max-w-[420px]">
          <span className="metric-label">项目标题（可留空，默认取文件名）</span>
          <input
            className="input"
            value={title}
            placeholder="例如：三创汇报"
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>

        <div className="mt-4">
          <Dropzone
            head="把原稿拖到这里"
            hint="或点击此处选择文件（单个文件）"
            formats="TXT · MD · DOCX · PDF · PPTX · 单文件最大 30MB"
            accept={ACCEPT}
            onPick={(files) => {
              const f = files[0]
              if (f) void handleFile(f)
            }}
          />
          {uploading && (
            <div className="mt-3 w-56">
              <div className="progress is-decor">
                <i className="df-breathing" style={{ width: '60%' }} />
              </div>
            </div>
          )}
        </div>
      </div>

      {uploadError && <ErrorState error={uploadError} onRetry={() => setUploadError(null)} title="上传/解析失败" />}
    </div>
  )

  const pagesStep = (
    <div className="flex flex-col gap-4">
      <div className="card">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="card-title m-0! text-h3">页面确认</h2>
          <span className="tag num">
            {parsed ? `${parsed.char_count} 字` : '—'}
          </span>
          <span className="status status-info">
            保留 <span className="num">{keptPages.length}</span> / {pages.length} 页
          </span>
          <span className="flex-1" />
          <label className="flex items-center gap-2">
            <span className="metric-label">目标页数</span>
            <input
              className="input num w-20"
              type="number"
              min={1}
              max={80}
              value={targetPages}
              onChange={(e) => setTargetPages(Number(e.target.value) || 1)}
              onBlur={() => void saveConfig({target_pages: targetPages})}
            />
          </label>
          <button
            type="button"
            className="btn btn-secondary h-8! text-body-sm"
            onClick={async () => { if (!projectId) return; if (await saveConfig({target_pages: targetPages})) await runOutline() }}
            disabled={outlining} title="按目标页数梳理页清单"
          >
            重建清单
          </button>
        </div>

        <p className="card-desc mt-2">
          取消勾选仅排除本次任务，原稿仍保留。请核对原稿页号、可用状态与素材策略。
        </p>

        {parsed?.warnings && parsed.warnings.length > 0 && (
          <div className="mb-3">
            <Notice kind="warn">解析告警：{parsed.warnings.join('；')}</Notice>
          </div>
        )}

        {sourceType === 'pptx' && (
          <section className="mb-4 rounded-lg border border-divider bg-surface-alt p-3" aria-label="原稿逐页缩略图">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="m-0 text-body-sm font-semibold">原稿逐页缩略图</h3>
              <span className="status status-info num">
                原稿 {sourcePages?.ready ? sourcePages.page_count : '—'} 页 / 目标 {pages.length} 页
              </span>
              <span className="text-caption text-ink-sub">原稿预览；任务范围以下方页面卡片为准</span>
            </div>
            {sourcePages?.ready ? (
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
                {sourcePages.pages.map((page, index) => (
                  <button
                    key={page.page_no}
                    type="button"
                    className="group overflow-hidden rounded-md border border-border bg-surface text-left shadow-sm transition hover:border-[var(--color-accent)]"
                    onClick={() => openSourcePreview(index)}
                    title={`查看原稿 P${String(page.page_no).padStart(2, '0')} 大图`}
                  >
                    <img
                      src={page.thumb_url}
                      alt={`原稿 P${String(page.page_no).padStart(2, '0')}`}
                      loading="lazy"
                      className="block aspect-video w-full object-cover"
                    />
                    <span className="block px-2 py-1 text-caption text-ink-sub num group-hover:text-ink">
                      原稿 P{String(page.page_no).padStart(2, '0')}
                    </span>
                  </button>
                ))}
              </div>
            ) : sourcePages?.error ? (
              <p className="mb-0 mt-2 text-body-sm text-ink-sub">原页缩略图不可用（不影响生成）</p>
            ) : (
              <p className="mb-0 mt-2 text-body-sm text-ink-sub">原页缩略图生成中…</p>
            )}
          </section>
        )}

        <PageSelectGrid
          pages={pages.map(p => ({
            pageNo: p.page_no,
            image: sourcePages?.pages.find(x => x.page_no === p.source_page_no)?.thumb_url,
            alt: `原稿第 ${p.source_page_no} 页`,
            disabled: p.valid === false,
            emptyText: p.source_page_no ? '原稿缩略图暂不可用' : '文档内容页 · 无可验证的原稿页映射',
          }))}
          selected={pages.filter(p => p.keep).map(p => p.page_no)}
          showRemove={false}
          onToggle={pageNo => void persistPages(pages.map(p => p.page_no === pageNo ? {...p, keep: !p.keep} : p))}
          onZoom={pageNo => {
            const p = pages.find(p => p.page_no === pageNo)
            const original = sourcePages?.pages.find(x => x.page_no === p?.source_page_no)
            if (original?.thumb_url) openSourcePreview(sourcePages!.pages.indexOf(original))
          }}
          zoomLabel={pageNo => `查看原稿 P${String(pages.find(p => p.page_no === pageNo)?.source_page_no).padStart(2, '0')} 大图`}
          renderRow={pageNo => {
            const idx = pages.findIndex(p => p.page_no === pageNo)
            const p = pages[idx]
            return <div className="p-3">
              <div className="flex gap-2 mt-2"><span className="num">{p.source_page_no?`源页 ${p.source_page_no}`:`内容页 ${p.page_no}`}</span><span>{p.valid===false?'不可用':'可用'}</span></div>
              <label className="block mt-2">标题<input className="input w-full" value={p.title} onChange={e=>{const next=pages.map((x,i)=>i===idx?{...x,title:e.target.value}:x);setPages(next);stageConfig({page_drafts:pagePayload(next)})}} onBlur={()=>void persistPages(pages)}/></label>
              <label className="block mt-2">布局<select className="input w-full" value={p.layout} onChange={e=>void persistPages(pages.map((x,i)=>i===idx?{...x,layout:e.target.value}:x))}>{layouts.map(l=><option key={l.key} value={l.key}>{l.title}</option>)}</select></label>
              <p className="text-caption">素材策略：{p.keep?'原稿内容作为参考；重新排版，不能保证原图完整保留':'未应用（此页已排除）'}</p>
            </div>
          }}
        />

        {pagesError && (
          <div className="mt-3">
            <ErrorState compact error={pagesError} onRetry={savePages} title="保存页清单失败" />
          </div>
        )}
        <ActionBar>
          <span className="font-semibold">已选 <span className="num text-primary">{keptPages.length}</span> / <span className="num">{pages.length}</span> 页</span>
          <button className="btn btn-secondary" onClick={() => void persistPages(pages.map(p=>({...p,keep:p.valid !== false})))}>全选有效页</button>
          <button className="btn btn-secondary" onClick={() => void persistPages(pages.map(p=>({...p,keep:false})))}>取消全选</button>
          <button
            type="button"
            className="btn btn-primary rounded-full px-6"
            disabled={savingPages || !keptPages.length || !projectId}
            title={
              !projectId
                ? '还没有项目：先上传原稿'
                : !keptPages.length
                  ? '至少保留 1 页'
                  : '保存页清单并进入内容梳理'
            }
            onClick={savePages}
          >
            {!keptPages.length ? '请至少选择一页' : savingPages ? '保存中…' : '保存页清单并继续'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => goto(1)}>
            ‹ 回到上传
          </button>
          <span className="text-caption text-ink-sub">
            布局清单来自 <span className="num">GET /api/layouts</span>
            {layoutsAsync.error ? '（后端不可用，当前为内置兜底布局）' : ''}
          </span>
        </ActionBar>
      </div>
    </div>
  )

  const outlineStep = outlining && !outline ? (
    <div className="deck-loading">
      <section className="deck-loading-card" role="status" aria-live="polite" aria-busy="true">
        <span className="deck-spinner" aria-hidden="true" />
        <h3 className="deck-loading-title">正在生成 PPT 大纲…</h3>
        <p className="deck-loading-sub">正在读取你的文档内容…</p>
        <div className="deck-loading-bar" role="progressbar" aria-label="大纲生成进度" aria-valuetext="生成中">
          <i />
        </div>
        <p className="deck-loading-hint">请保持当前页面打开，生成完成后会自动显示页清单。</p>
        <p className="deck-loading-hint">
          {textReady === true
            ? '正在调用 DeepSeek 提炼标题与要点，通常十几秒到一分钟。'
            : textReady === false
              ? '未配置文本模型：本次按段落本地切页，通常几秒完成。'
              : '未配置文本模型时会按段落本地切页；已配置则由模型提炼标题与要点。'}
        </p>
      </section>

      <div className="deck-loading-meta">
        <span>文档字数 <b className="num">{parsed?.char_count != null ? `约 ${parsed.char_count} 字` : '—'}</b></span>
        <span>目标页数 <b className="num">{targetPages} 页</b></span>
      </div>

      <ActionBar className="deck-loading-actions">
        <span className="text-ink-sub">目标 <span className="num">{targetPages}</span> 页</span>
        <button type="button" className="btn btn-secondary rounded-full" disabled title="大纲生成中，请稍候">重新生成大纲</button>
        <button type="button" className="btn btn-primary rounded-full px-6" disabled title="大纲生成完成后自动进入">继续：页面确认 ›</button>
      </ActionBar>
    </div>
  ) : (
    <div className="flex flex-col gap-4">
      <div className="card">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="card-title m-0! text-h3">内容梳理</h2>
          <span className="status status-info num">{keptPages.length} 页待梳理</span>
          <span className="flex-1" />
          <button
            type="button"
            className="btn btn-secondary h-8! text-body-sm"
            disabled={outlining || !projectId}
            title="调用 POST /api/projects/{id}/outline 重新梳理"
            onClick={() => void runOutline()}
          >
            {outlining ? '梳理中…' : outline ? '重新梳理' : '开始梳理'}
          </button>
        </div>

        {outlineMeta?.configured === false && (
          <div className="mb-3">
            <NotConfiguredBanner hint={outlineMeta.hint} fellback={outlineMeta.fallback} />
          </div>
        )}

        {outlineError && <ErrorState error={outlineError} onRetry={() => void runOutline()} title="内容梳理失败" />}

        {outline && outline.length > 0 && (
          <>
            <ul className="m-0 list-none p-0">
              {outline.filter(p => pages.some(x => x.page_no === p.page_no && x.keep)).map((p) => (
                <li key={pages.find(x => x.page_no === p.page_no)?.slide_id || p.page_no} className="border-t border-divider py-3 first:border-t-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="num text-ink-sub">P{padPageNo(p.page_no)}</span>
                    <span className="font-semibold">{p.title}</span>
                    <span className="tag num">{p.role}</span>
                    {p.points?.length ? (
                      <span className="status status-info num">{p.points.length} 要点</span>
                    ) : null}
                  </div>
                  {p.outline && <p className="mt-1 mb-1 text-body-sm text-ink-sub">{p.outline}</p>}
                  {p.points?.length ? (
                    <ul className="m-0 list-disc pl-5 text-body-sm">
                      {p.points.map((pt, i) => (
                        <li key={i}>{pt}</li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" className="btn btn-primary" onClick={async () => { if (step === 2) goto(2); else if (await saveConfig({confirm_content: true})) goto(4) }}>
                {step === 2 ? '继续：页面确认 ›' : '继续：选择风格 ›'}
              </button>
              <button type="button" className="btn btn-secondary" onClick={() => goto(2)}>
                ‹ 回到页面确认
              </button>
            </div>
          </>
        )}

        {!outlining && !outline && !outlineError && (
          <EmptyState
            title="还没有梳理结果"
            desc="点「开始梳理」让 DeepSeek 提炼每页标题与要点；没有 key 时会用本地规则切页兜底。"
            actionLabel="开始梳理"
            onAction={() => void runOutline()}
          />
        )}
      </div>
    </div>
  )

  const styleStep = (
    <div className="flex flex-col gap-4">
      <div className="card">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="card-title m-0! text-h3">选择风格</h2>
          {stylePackId && <span className="status status-success">已选：{stylePackId}</span>}
          <span className="flex-1" />
          <Link to="/style-builder" className="btn btn-secondary h-8! text-body-sm">
            + 风格构建
          </Link>
          <button type="button" className="btn btn-secondary h-8! text-body-sm" onClick={packsAsync.reload}>
            刷新风格包
          </button>
        </div>
        <p className="card-desc mt-2">
          风格包来自 <span className="num">GET /api/style-packs</span>（读仓库 style-packs/）；
          选择后保存到项目。
        </p>
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
            </button>
          ))}
        </div>
      </div>

      {packsAsync.loading && !packs.length && <Loading rows={2} label="加载风格包…" />}
      {packsAsync.error && (
        <ErrorState error={packsAsync.error} onRetry={packsAsync.reload} title="风格包加载失败" />
      )}
      {!packsAsync.loading && !packsAsync.error && packs.length === 0 && (
        <div className="card">
          <EmptyState
            title="还没有风格包"
            desc="把风格包放进仓库 style-packs/（每个包含 style.md + prompt.md），然后点「刷新风格包」。"
            actionLabel="刷新风格包"
            onAction={packsAsync.reload}
          />
        </div>
      )}

      {visiblePacks.length > 0 && (
        <div className="band grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3" role="listbox" aria-label="风格包">
          {visiblePacks.map((p) => (
            <StylePackCard
              key={p.id}
              pack={p}
              selected={stylePackId === p.id}
              previewing={previewing === p.id}
              onSelect={() => {
                void saveConfig({style_pack_id: p.id})
              }}
              onPreview={() => setPreviewing((v) => (v === p.id ? null : p.id))}
            />
          ))}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!stylePackId}
          title={!stylePackId ? '请先选中一个风格包' : '进入生成'}
          onClick={() => goto(5)}
        >
          继续：开始生成 ›
        </button>
        <button type="button" className="btn btn-secondary" onClick={() => goto(3)}>
          ‹ 回到内容梳理
        </button>
      </div>
    </div>
  )

  const locked: Record<number, string | undefined> = {
    2: projectId && (parsed || pages.length) ? undefined : '先输入内容',
    3: pagesConfirmed ? undefined : '先完成页面确认',
    4: contentConfirmed ? undefined : '先完成内容确认',
    5: hasResults || (contentConfirmed && stylePackId) ? undefined : !contentConfirmed ? '先完成内容确认' : '先选择风格',
  }
  if (restoring) return <Loading rows={4} label="加载项目工作台…" />
  if (restoreError) return <ErrorState error={restoreError} title="项目加载失败" />
  return (
    <div className="flex flex-col gap-4">
      <div className="card">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <h1 className="m-0 text-h1 font-semibold">{projectId ? title : '生成向导'}</h1>
            {projectId && <label className="flex items-center gap-2 mt-2"><span>项目名称</span><input className="input" value={title} onChange={e => {setTitle(e.target.value);stageConfig({title:e.target.value})}} onBlur={() => void saveConfig({title})} /></label>}
          </div>
          <span className="flex-1" />
          {parsed && (
            <div className="flex flex-wrap items-center gap-2 text-caption">
              <span className="tag num">{sourceType}</span>
              <span className="tag num">{parsed.char_count} 字</span>
              <span className="tag num">建议 {parsed.suggested_pages} 页</span>
              <span className="tag num">保留 {keptPages.length} 页</span>
              {stylePackId && <span className="tag num">{stylePackId}</span>}
            </div>
          )}
        </div>
        <div className="divider my-3" />
        {configConflict&&remoteConfig&&<div className="card"><p>项目配置已由其他窗口修改，本地草稿已保留。</p><details><summary>查看差异</summary><pre className="whitespace-pre-wrap">{JSON.stringify({本地草稿:configDraft.current,服务器:remoteConfig},null,2)}</pre></details><button className="btn btn-secondary" onClick={()=>{projectStamp.current=remoteConfig.updated_at;setConfigConflict(false);setDraftTick(n=>n+1)}}>采用本地草稿（覆盖对应字段）</button><button className="btn btn-secondary" onClick={()=>{configDraft.current={};if(projectId)localStorage.removeItem(configKey(projectId));projectStamp.current=remoteConfig.updated_at;setTitle(remoteConfig.title);setStylePackId(remoteConfig.style_pack_id||null);setProjectSize(remoteConfig.size||'2K');setPages(prev=>prev.map(p=>({...p,...remoteConfig.page_drafts?.find(d=>d.page_no===p.page_no),content_revision:p.slide_id?remoteConfig.content_revisions?.[p.slide_id]??p.content_revision:p.content_revision})));setConfigConflict(false);setSaveState('已保存')}}>采用服务器配置</button></div>}
        {projectId&&<div role="status" className="flex gap-3 items-center mb-3"><span>保存状态：{[saveState,...(step===3?[contentSaveState]:[])].includes('保存失败')?'保存失败':[saveState,...(step===3?[contentSaveState]:[])].includes('正在保存')?'正在保存':[saveState,...(step===3?[contentSaveState]:[])].includes('未保存')?'未保存':'已保存'}</span>{saveState==='保存失败'&&<button className="btn btn-secondary" onClick={()=>void flushConfig()}>重试保存（不生成）</button>}</div>}
        <FlowSteps
          steps={WIZARD_STEPS}
          current={step}
          locks={locked}
          hints={locked}
          errorAt={errorAt}
          busy={taskRunning}
          onJump={(s) => goto(s as WizardStepNo)}
          onLocked={(_, reason) => { if (reason) toast.warn(reason) }}
          label="生成向导步骤"
        />
      </div>

      {locked[step] && <Notice kind="warn">{locked[step]}</Notice>}
      {step === 1 && uploadStep}
      {taskRunning&&step<5&&<Notice kind="info">任务运行中，页面范围与整册风格配置暂不能修改。可通过步骤导航查看已有结果。</Notice>}
      {step === 2 && !locked[2] && <fieldset disabled={taskRunning} title={taskRunning?'任务运行中，页面配置暂不能修改':undefined}>{outline ? pagesStep : outlineStep}</fieldset>}
      {step === 3 && !locked[3] && projectId && <ContentEditor key={projectId} projectId={projectId} onSaveState={setContentSaveState} onConfirmed={()=>{setContentConfirmed(true);goto(4)}} onExclude={async no=>{const next=pages.map(p=>p.page_no===no?{...p,keep:false}:p);const fresh=await getSlides(projectId);const updated=next.map(p=>({...p,title:fresh.find(s=>s.page_no===p.page_no)?.title||p.title,content_revision:fresh.find(s=>s.page_no===p.page_no)?.content_revision}));if(!await persistPages(updated))throw new Error('保存失败，请重试');if(updated.some(p=>p.keep)){await putPages(projectId,{pages:updated});setPagesConfirmed(true)}}}/>}
      {step === 4 && !locked[4] && <fieldset disabled={taskRunning} title={taskRunning?'任务运行中，风格暂不能修改':undefined}>{styleStep}</fieldset>}
      {/* 同槽位渲染同一个实例：⑤⑥ 之间切步骤时不丢勾选/进度状态 */}
      {(step === 5) && !locked[5] && projectId && (
        <ProjectWorkbench
          projectId={projectId}
          stylePackId={stylePackId}
          pageNos={keptPages.map((p) => p.page_no)}
          view="both"
          defaultSize={projectSize}
          tab={tab}
          autoEditable={readQuery().auto === '1'}
          onTabChange={setTab}
        />
      )}
      {(step === 5) && !projectId && (
        <div className="card">
          <EmptyState
            title="还没有项目"
            desc="先生成/上传一个项目，才能进入生成结果与按图片版重建。"
            actionLabel="回到上传原稿"
            onAction={() => goto(1)}
          />
        </div>
      )}
      {sourcePreviewIndex !== null && sourceSlides.length > 0 && (
        <>
          <SlidePreview
            slides={sourceSlides}
            index={sourcePreviewIndex}
            onIndexChange={openSourcePreview}
            onClose={() => setSourcePreviewIndex(null)}
          />
          {sourceLargeLoading !== null && !sourceLargeReady.has(sourceLargeLoading) && (
            <div className="fixed right-6 top-6 z-50 rounded-md bg-surface px-3 py-2 text-body-sm shadow-[var(--shadow-overlay)]" role="status">
              正在渲染原页…（先显示缩略图）
            </div>
          )}
        </>
      )}
    </div>
  )
}
