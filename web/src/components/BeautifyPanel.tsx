import { useEffect, useRef, useState } from 'react'
import { cancelJob, beautifyOrigin, beautifyContinue, beautifyEditable, beautifyPreview, beautifyRegeneratePage, codexEngine, createProject, getBeautify, getProject, getProjectJobs, uploadSource, prepareBeautifyContent, saveBeautifyContent, type ApiError } from '../api'
import { IconFolder } from './Icons'
import { Dropzone } from './Dropzone'
import { ProgressPanel } from './ProgressPanel'
import { ActionBar, FlowSteps, OverviewGrid, PageLightbox, PageRail, PageSelectGrid, PagerArrow, withVersion, type FlowStep } from './FlowKit'
import { useToast } from './Toast'
import { useModalFocus } from '../hooks/useModalFocus'
import { useJobStream } from '../hooks/useJobStream'
import { MAX_UPLOAD_BYTES, UPLOAD_SIZE_HINT, bytes, cn, uploadTooLarge } from '../lib/format'
import type { BeautifyStatus, CodexEngineStatus, BeautifyContentPlan, StylePack } from '../types'

/* ─────────────── ③ PPT美化：上传 / 预览 / 完成 ─────────────── */

const BEAUTIFY_STEP_LABELS = ['上传内容', '页面确认', '内容梳理', '选择风格', '生成结果'] as const
const BEAUTIFY_STEPS: FlowStep[] = BEAUTIFY_STEP_LABELS.map((label, index) => ({ key: index + 1, label }))

const BEAUTIFY_STAGES: Record<string, string> = {
  render: '原稿转图', beauty: '逐页生图', codex: 'Codex 转可编辑', assemble: '组装导出',
}
const errorDetail = (e: unknown) => (e as ApiError)?.detail || (e instanceof Error ? e.message : String(e))
const STYLES_PER_PAGE = 6

function BeautifyStyleCover({ pack }: { pack: StylePack }) {
  const cover = pack.cover || pack.previews?.[0]
  const [failed, setFailed] = useState(false)
  useEffect(() => { setFailed(false) }, [cover])
  return cover && !failed
    ? <img src={cover} alt={`${pack.name} 风格封面`} loading="eager" decoding="async" className="beautify-style-cover" onError={() => setFailed(true)} />
    : <span className="beautify-style-cover-missing text-caption text-ink-sub">暂无封面图</span>
}

/** 单页重生成确认（会真的调用生图模型，先说清楚影响面再提交） */
function RegenerateDialog({ pageNo, onClose, onConfirm }: { pageNo: number; onClose: () => void; onConfirm: () => void }) {
  const modalRef = useModalFocus(onClose)
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" ref={modalRef} tabIndex={-1} role="dialog" aria-modal="true" aria-label={`重新生成第 ${pageNo} 页`} onClick={onClose}>
      <div className="card flex w-full max-w-[28rem] flex-col gap-3" onClick={(event) => event.stopPropagation()}>
        <h3 className="m-0 text-h3">重新生成第 <span className="num">{pageNo}</span> 页</h3>
        <p className="m-0 text-body-sm text-ink-sub">
          会调用已配置的生图模型，费用按设置与用量账本记录；<strong>其它页的生成结果与导出不会被改动</strong>，完成后会重新装配图片版。生成期间可以「取消生成」。
        </p>
        <div className="flex justify-end gap-2">
          <button type="button" className="btn btn-secondary" onClick={onClose}>取消</button>
          <button type="button" className="btn btn-primary" onClick={onConfirm}>开始重新生成</button>
        </div>
      </div>
    </div>
  )
}

/** ③内容梳理的真实阶段：每一步都对应代码里实际做的事，不写做不到的耗时承诺 */
const CONTENT_STAGES = ['读取原稿', '提取文字', '校验结构', '标注来源'] as const

export function BeautifyPanel({ packs, loadingPacks, onStepChange, resumeProjectId }: { packs: StylePack[]; loadingPacks: boolean; onStepChange: (step: number) => void; resumeProjectId?: string }) {
  const toast = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const imageMode = 'redesign' as const
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(resumeProjectId ? 2 : 1)
  const [file, setFile] = useState<File | null>(null)
  /** 原稿显示名：新上传取文件名；从项目恢复时取 source_path 的文件名（此时没有 File 对象） */
  const [sourceName, setSourceName] = useState('')
  const [origin, setOrigin] = useState<Awaited<ReturnType<typeof beautifyOrigin>> | null>(null)
  const [selected, setSelected] = useState<number[]>([])
  const [keepMaterial, setKeepMaterial] = useState<number[]>([])
  const [content, setContent] = useState<BeautifyContentPlan | null>(null)
  /** ③的真实阶段进度：0=无，1..4 对应 CONTENT_STAGES 中正在做的那一步，完成后归 0 */
  const [contentStage, setContentStage] = useState(0)
  const [contentSaved, setContentSaved] = useState(false)
  /** 内容梳理：左侧页列表当前页下标（不是页号）+ 正在原地编辑的页号 */
  const [pageIndex, setPageIndex] = useState(0)
  const [editingPage, setEditingPage] = useState<number | null>(null)
  /** 是否并排显示原稿该页，便于人工核对（默认关，保持文字呈现直观） */
  const [showOrigin, setShowOrigin] = useState(false)
  /** 生成结果：当前查看的页下标 + 缩略总览开关 */
  const [resultIndex, setResultIndex] = useState(0)
  const [overview, setOverview] = useState(false)
  /** 放大看单页结果（灯箱） */
  const [lightbox, setLightbox] = useState(false)
  /** 单页重生成的确认框（待确认的页号） */
  const [regenTarget, setRegenTarget] = useState<number | null>(null)
  const [packId, setPackId] = useState('')
  const [stylePage, setStylePage] = useState(1)
  const stylePageCount = Math.max(1, Math.ceil(packs.length / STYLES_PER_PAGE))
  const currentStylePage = Math.min(stylePage, stylePageCount)
  const visiblePacks = packs.slice((currentStylePage - 1) * STYLES_PER_PAGE, currentStylePage * STYLES_PER_PAGE)
  const [projectId, setProjectId] = useState<string | null>(resumeProjectId ?? null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BeautifyStatus | null>(null)
  const [engine, setEngine] = useState<CodexEngineStatus | null>(null)
  const [engineError, setEngineError] = useState<string | null>(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [cancelling, setCancelling] = useState(false)
  useEffect(() => {
    onStepChange(step)
    window.scrollTo({ top: 0 })
  }, [step, onStepChange])
  const stream = useJobStream(jobId, {
    onCancelled: () => { setCancelling(false); setBusy(false); setStep(5); void refresh(true) },
    onDone: () => { void refresh(true) },
    onError: (message) => { setError(message); setBusy(false); void refresh(true, message) },
  })
  /* 转可编辑版是按需作业（不随生成图片自动跑），单独跟一条 SSE */
  const [editableJobId, setEditableJobId] = useState<string | null>(null)
  const [editableBusy, setEditableBusy] = useState(false)
  const editableStream = useJobStream(editableJobId, {
    onDone: () => { setEditableBusy(false); toast.success('可编辑版已重建', '可在下方下载可编辑版 PPT'); void refresh(true) },
    onError: (message) => { setEditableBusy(false); setError(message); void refresh(true, message) },
    onCancelled: () => { setEditableBusy(false); void refresh(true) },
  })

  useEffect(() => {
    let active = true
    codexEngine().then((value) => { if (active) setEngine(value) })
      .catch((e: unknown) => { if (active) setEngineError(errorDetail(e)) })
    return () => { active = false }
  }, [])
  useEffect(() => {
    if (!packId && packs.length) setPackId(packs[0].id)
  }, [packs, packId])
  useEffect(() => { setStylePage(previous => Math.min(previous, stylePageCount)) }, [stylePageCount])

  /** 从「我的项目」进入：按后端记录的美化现场恢复到上一次执行到的步骤（不重跑生图、不新建项目） */
  useEffect(() => {
    if (!resumeProjectId) return
    let active = true
    setBusy(true); setError(null)
    ;(async () => {
      const [project, pages, status, jobs] = await Promise.all([
        getProject(resumeProjectId), beautifyOrigin(resumeProjectId),
        getBeautify(resumeProjectId), getProjectJobs(resumeProjectId),
      ])
      if (!active) return
      setProjectId(resumeProjectId)
      setSourceName(project.source_path ? (project.source_path.split('/').pop() || project.title) : project.title)
      setOrigin(pages)
      const pageNos = status.page_nos?.length ? status.page_nos : pages.pages.map(p => p.page_no)
      setSelected(pageNos)
      if (project.style_pack_id) setPackId(project.style_pack_id)
      setResult(status.phase ? status : null)
      try {
        const plan = await prepareBeautifyContent(resumeProjectId, { page_nos: pageNos, keep_material_page_nos: [] })
        if (!active) return
        setContent(plan)
        setContentSaved(Boolean(status.content_saved))
      } catch { /* 内容计划只服务第③步，取不到就停在页面确认，不编造内容 */ }
      const running = jobs.items.find(job => job.kind === 'beautify' && ['running', 'cancelling', 'queued'].includes(job.status))
      if (!active) return
      if (running) { setJobId(running.id); setBusy(true); setStep(5) }
      else {
        setBusy(false)
        // 有已生成页 → 回到生成结果；跑过但没产出（取消/失败）→ 回到内容梳理；从未跑过 → 页面确认
        setStep((status.pages?.length ?? 0) > 0 ? 5 : status.phase ? 3 : 2)
      }
    })().catch(e => { if (active) { setError(errorDetail(e)); setBusy(false) } })
    return () => { active = false }
  }, [resumeProjectId])
  useEffect(() => {
    if (stream.startedAt && stream.finishedAt)
      setElapsedMs((previous) => previous + stream.finishedAt! - stream.startedAt!)
  }, [stream.startedAt, stream.finishedAt])
  /* 运行期间每秒走一格，用于显示真实已用时（不再显示恒为 0 的假数据） */
  const [nowTick, setNowTick] = useState(() => Date.now())
  useEffect(() => {
    if (stream.status !== 'running') return
    const timer = window.setInterval(() => setNowTick(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [stream.status])

  async function refresh(finished = false, jobError: string | null = null) {
    if (!projectId) return
    setError(jobError)
    try {
      const status = await getBeautify(projectId)
      setResult(status)
      if (finished || (stream.status !== 'running' && (status.phase === 'done' || status.phase === 'preview'))) setBusy(false)
    } catch (e) {
      setError([jobError, errorDetail(e)].filter(Boolean).join('；'))
      if (finished || stream.status !== 'running') setBusy(false)
    }
  }

  async function cancelCurrent() {
    if (!jobId || cancelling) return
    setCancelling(true)
    try { await cancelJob(jobId) }
    catch (e) { setError(errorDetail(e)); setCancelling(false) }
  }

  function chooseFile(next: File) {
    if (busy) return
    if (!/\.(pptx|pdf)$/i.test(next.name)) { setError('请上传 PPTX 或 PDF'); return }
    if (next.size > MAX_UPLOAD_BYTES) { setError(uploadTooLarge(next)); return }
    setFile(next); setSourceName(next.name); setError(null); setOrigin(null); setResult(null); setJobId(null); setProjectId(null); setSelected([]); setStep(1)
    setKeepMaterial([]); setContent(null); setContentSaved(false)
  }

  async function recognize() {
    if (!file || busy) return
    const next = file
    setBusy(true); setError(null); setOrigin(null); setResult(null); setJobId(null); setProjectId(null)
    setKeepMaterial([]); setContent(null); setContentSaved(false)
    try {
      const project = await createProject({ title: next.name.replace(/\.[^.]+$/, ''), source_type: next.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'pptx', intake_mode: 'doc' })
      await uploadSource(project.id, next)
      const pages = await beautifyOrigin(project.id)
      setProjectId(project.id); setOrigin(pages); setSelected(pages.pages.map(p => p.page_no)); setStep(2)
    } catch (e) { setError(errorDetail(e)) }
    finally { setBusy(false) }
  }

  async function startPreview() {
    if (!projectId || !selected.length || !packId || busy) return
    setBusy(true)
    setCancelling(false)
    setError(null)
    setResult(null)
    setJobId(null)
    try {
      const job = await beautifyPreview(projectId, { style_pack_id: packId, mode: imageMode, preview_pages: 3, page_nos: selected })
      if (!job.job_id) throw new Error('后端没有返回作业号')
      setJobId(job.job_id)
      setStep(5)
    } catch (e) { setError(errorDetail(e)); setBusy(false) }
  }

  async function organizeContent() {
    if (!projectId || !selected.length || busy) return
    setBusy(true); setError(null); setContent(null); setContentSaved(false)
    setPageIndex(0); setEditingPage(null); setStep(3)          // 先进第③步，处理态就位
    try {
      setContentStage(1)                                       // 真实：本次选页与原稿指纹的前置校验
      setContentStage(2)                                       // 真实：唯一耗时的一步——后端抽取原页文字
      const plan = await prepareBeautifyContent(projectId, { page_nos: selected, keep_material_page_nos: keepMaterial.filter(n => selected.includes(n)) })
      setContentStage(3)                                       // 真实：校验返回结构
      const expected = [...selected].sort((a, b) => a - b)
      if (plan.pages.length !== expected.length || plan.pages.some((page, index) => page.page_no !== expected[index])) {
        throw new Error('后端返回的页序与本次选页不一致，已中止')
      }
      if (plan.pages.some(page => !Array.isArray(page.texts) || !Array.isArray(page.points))) {
        throw new Error('后端返回的文字结构不完整，已中止')
      }
      setContentStage(4)                                       // 真实：合并已保存草稿与「保留原图」标记
      setContent(previous => ({ ...plan, pages: plan.pages.map(page => {
        const draft = previous?.source_revision === plan.source_revision ? previous.pages.find(item => item.page_no === page.page_no) : null
        return draft ? { ...draft, keep_material: page.keep_material } : page
      }) }))
      setContentSaved(false)
      setPageIndex(0); setEditingPage(null)
    } catch (e) { setError(errorDetail(e)) }
    finally { setContentStage(0); setBusy(false) }
  }

  /** 按需重建原生可编辑版：生成图片时不自动执行，由用户点「转文字可编辑版」触发 */
  async function convertEditable() {
    if (!projectId || editableBusy) return
    setEditableBusy(true); setError(null)
    try {
      const job = await beautifyEditable(projectId, { style_pack_id: packId })
      if (!job.job_id) throw new Error('后端没有返回作业号')
      setEditableJobId(job.job_id)
      toast.info('已开始重建原生可编辑版', '这一步不会自动执行；完成后可下载可编辑版 PPT')
    } catch (e) { setEditableBusy(false); setError(errorDetail(e)) }
  }

  async function confirmContent() {
    if (!projectId || !content || busy) return
    setBusy(true); setError(null)
    try {
      const saved = await saveBeautifyContent(projectId, content)
      setContent(saved); setContentSaved(true); setStep(4)
    } catch (e) { setError(errorDetail(e)) }
    finally { setBusy(false) }
  }

  function updateContent(pageNo: number, field: 'title' | 'points', value: string) {
    setContent(previous => previous ? { ...previous, pages: previous.pages.map(page => page.page_no === pageNo ? { ...page, [field]: field === 'points' ? value.split('\n') : value } : page) } : previous)
    setContentSaved(false)
  }

  /** 重新提取当前页原文（后端按原稿重读，不调用模型、不补写）；其余页保持不变 */
  async function reextractPage(pageNo: number) {
    if (!projectId || !content || busy) return
    setBusy(true); setError(null)
    try {
      const plan = await prepareBeautifyContent(projectId, { page_nos: [pageNo], keep_material_page_nos: keepMaterial.filter(n => n === pageNo) })
      const fresh = plan.pages.find(page => page.page_no === pageNo)
      if (!fresh) throw new Error(`后端未返回第 ${pageNo} 页内容`)
      setContent(previous => previous ? { ...previous, pages: previous.pages.map(page => page.page_no === pageNo ? fresh : page) } : previous)
      setContentSaved(false); setEditingPage(null)
    } catch (e) { setError(errorDetail(e)) }
    finally { setBusy(false) }
  }

  async function continueAll() {
    if (!projectId || busy || result?.phase !== 'preview') return
    setBusy(true)
    setCancelling(false)
    setError(null)
    try {
      const job = await beautifyContinue(projectId, { style_pack_id: packId, mode: imageMode, page_nos: selected })
      if (!job.job_id) throw new Error('后端没有返回作业号')
      setResult(null)
      setJobId(job.job_id)
      setStep(5)
    } catch (e) { setError(errorDetail(e)); setBusy(false) }
  }

  const progress = {
    ...stream,
    message: stream.status === 'done' ? '作业已结束，请核对导出结果与警告' : stream.message,
    byPage: Object.fromEntries(Object.entries(stream.byPage).map(([key, event]) => [key, { ...event, stage: BEAUTIFY_STAGES[event.stage] || event.stage }])),
  }
  /* ── ③ 内容梳理：一次只展示一页，提炼出的文字按最终页面样式呈现 ── */
  const contentPages = content?.pages ?? []
  const currentIndex = Math.min(pageIndex, Math.max(0, contentPages.length - 1))
  const currentPage = contentPages[currentIndex]
  const pageHasText = (page: BeautifyContentPlan['pages'][number]) => Boolean(page.title.trim() || page.points.join('').trim())
  const filledCount = contentPages.filter(pageHasText).length
  const currentOriginUrl = currentPage ? origin?.pages.find(item => item.page_no === currentPage.page_no)?.image_url : undefined
  /* ── ⑤ 生成结果：逐页查看美化结果（页状态一律按后端真实字段判断，不编造） ── */
  const resultPages = result?.pages ?? []
  const resultCurrentIndex = Math.min(resultIndex, Math.max(0, resultPages.length - 1))
  const resultCurrent = resultPages[resultCurrentIndex]
  const resultDoneCount = resultPages.filter(page => Boolean(page.beauty_url)).length
  const generatingCurrent = Boolean(resultCurrent) && (
    progress.byPage[resultCurrent.page_no]?.status === 'running'          // 该页正在生成/重生成（参考图口径）
    || (!resultCurrent.beauty_url && stream.status === 'running')         // 整批跑着、这页还没有结果
  )
  const resultPercent = resultPages.length ? Math.round((100 * resultDoneCount) / resultPages.length) : 0
  /** 正在生成的页（后端 Semaphore(3) 并发，逐页 SSE 事件是真实状态） */
  const runningPages = Object.values(stream.byPage).filter(event => event.status === 'running')
  const jobActive = stream.status === 'running' || runningPages.length > 0
  const runningSeconds = stream.startedAt ? Math.max(0, Math.round(((stream.finishedAt ?? nowTick) - stream.startedAt) / 1000)) : null
  const resultPageState = (page: BeautifyStatus['pages'][number]) => {
    if (progress.byPage[page.page_no]?.status === 'running') return { label: '生成中', cls: 'status-info' }
    if (page.beauty_url && page.beauty_ok) return { label: '已完成', cls: 'status-success' }
    if (page.beauty_url) return { label: '已用原图', cls: 'status-warn' }
    if (progress.byPage[page.page_no]?.status === 'running') return { label: '生成中', cls: 'status-info' }
    return { label: '未生成', cls: 'status-info' }
  }
  /** 步骤可达性：只按真实数据放行（前进/后退都行）；不可达时给出中文原因，点击如实提示而不是静默点不动 */
  const stepLocks: Record<number, string | undefined> = {
    1: undefined,
    2: projectId ? undefined : '还没有原稿：先在第①步上传 PPTX / PDF',
    3: content ? undefined : '先在第②步点「开始梳理内容」',
    4: contentSaved ? undefined : '先在第③步点「确认内容，选择风格」',
    5: (result?.pages?.length ?? 0) > 0 ? undefined : '先在第④步生成前 3 页预览',
  }
  function goStep(target: number) {
    if (busy || target === step) return
    const lock = stepLocks[target]
    if (lock) { toast.info(`「${BEAUTIFY_STEP_LABELS[target - 1]}」暂时不能进入：${lock}`); return }
    setStep(target as 1 | 2 | 3 | 4 | 5)
  }
  /** 重新生成当前这一页：后端只动这一页，其它页与导出不变，最后重装配图片版 */
  async function regenerateCurrentPage() {
    if (!projectId || !resultCurrent || busy) return
    const pageNo = resultCurrent.page_no
    setRegenTarget(null)
    setBusy(true); setError(null)
    try {
      const job = await beautifyRegeneratePage(projectId, pageNo, { style_pack_id: packId || undefined, mode: imageMode })
      if (!job.job_id) throw new Error('后端没有返回作业号')
      setJobId(job.job_id)
      toast.info(`已开始重新生成第 ${pageNo} 页`, '其它页结果不会改动；完成后会重新装配图片版')
    } catch (e) { setError(errorDetail(e)); setBusy(false) }
  }

  return (
    <div className={cn('beautify-flow flex flex-col gap-5', step > 1 && 'beautify-workbench')}>
      <header className="beautify-flow-header">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <h2 className="m-0 min-w-0 flex-1 truncate text-2xl font-semibold" title={sourceName}>{sourceName.replace(/\.[^.]+$/, '') || 'PPT美化'}</h2>
          {projectId && <span className="status status-success">{contentSaved ? '内容已保存' : step === 3 ? '内容待确认' : '文件已上传'}</span>}
        </div>
        <FlowSteps steps={BEAUTIFY_STEPS} current={step} locks={stepLocks} busy={busy} onJump={goStep}
          onLocked={(target, reason) => toast.info(`「${BEAUTIFY_STEP_LABELS[target - 1]}」暂时不能进入：${reason}`)} label="PPT美化步骤" />
      </header>
      {step === 5 && engine && !engine.ok && <div className="panel-alt text-body-sm" role="alert">Codex 引擎不可用：{engine.reason}，将只能产出图片版</div>}
      {step === 5 && engineError && <div className="error-box" role="alert">Codex 引擎探测失败：{engineError}</div>}
      {step === 1 && <>
        {!file ? <Dropzone head="拖入要美化的 PPTX / PDF" hint="选择文件后，点击「开始 PPT 美化」分析页面" formats={`PPTX · PDF · ${UPLOAD_SIZE_HINT}`} accept=".pptx,.pdf" onPick={(picked) => { if (picked[0]) chooseFile(picked[0]) }} /> : <div className="flex min-h-64 flex-col items-center justify-center gap-4 rounded-2xl border border-border bg-surface-band px-6 py-8 text-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-2xl border border-border bg-surface text-primary"><IconFolder className="h-7 w-7" /></span>
          <h3 className="m-0 max-w-full break-words text-h3">{file.name}</h3>
          <p className="m-0 text-ink-sub">{file.name.toLowerCase().endsWith('.pdf') ? 'PDF' : 'PPTX'} · <span className="num">{bytes(file.size)}</span> · {busy ? '正在分析页面…' : '已就绪'}</p>
          <div className="flex gap-4">
            <button type="button" className="link" disabled={busy} onClick={() => fileInputRef.current?.click()}>重新选择</button>
            <button type="button" className="link" disabled={busy} onClick={() => { setFile(null); setError(null) }}>删除</button>
          </div>
          <input ref={fileInputRef} type="file" accept=".pptx,.pdf" className="hidden" disabled={busy} onChange={(event) => { const next = event.target.files?.[0]; if (next) chooseFile(next); event.target.value = '' }} />
        </div>}
        <div className="flex justify-end">
          <button type="button" className="btn btn-primary rounded-full px-6" disabled={!file || busy} onClick={() => void recognize()}>{busy ? '正在分析页面…' : '开始 PPT 美化'}</button>
        </div>
        {busy && <p role="status" className="m-0 text-body-sm text-ink-sub">正在上传文件并分析页面，请稍候…</p>}
      </>}
      {step === 2 && origin && <>
        <div className="flex flex-wrap items-center gap-3"><h3 className="m-0 text-h2 font-semibold">识别页面</h3><span className="text-ink-sub">共 <span className="num">{origin.page_count}</span> 页 · 默认全选并保持原顺序</span></div>
        <p className="m-0 text-body-md text-primary">开启「保留原图」后，以原页画面为参考保留图片与版式；关闭后按确认文字重新设计。无可用文字时会保留原图。</p>
        <PageSelectGrid
          pages={origin.pages.map(page => ({ pageNo: page.page_no, image: page.image_url, alt: `原稿第 ${page.page_no} 页` }))}
          selected={selected}
          disabled={busy}
          onToggle={pageNo => {
            const checked = selected.includes(pageNo)
            setSelected(previous => checked ? previous.filter(n => n !== pageNo) : [...previous, pageNo].sort((a, b) => a - b))
            setContentSaved(false)
          }}
          renderRow={(pageNo, checked) => {
            const kept = keepMaterial.includes(pageNo)
            return <div className="deck-option-row">
              <span className="text-caption text-ink-sub" title="保留整页画面作为视觉参考，包含原页图片和版式">保留原页图片素材</span>
              <button type="button" role="switch" aria-checked={kept} aria-label={`第 ${pageNo} 页保留原图`} disabled={busy || !checked} className="deck-switch" onClick={() => { setKeepMaterial(previous => kept ? previous.filter(n => n !== pageNo) : [...previous, pageNo]); setContentSaved(false) }}><span /></button>
            </div>
          }}
        />
      </>}
      {step === 3 && !content && <>
        <div className="deck-split beautify-content-workspace">
          <aside className="beautify-content-sidebar">
            <h3 className="m-0 mb-4 text-h3 font-semibold text-ink-sub">页面内容</h3>
            <PageRail label="页面内容列表" current={0} onSelect={() => undefined}
              items={[...selected].map(pageNo => ({
                key: pageNo, index: `P${pageNo}`, label: `第 ${pageNo} 页`, dot: 'idle' as const,
              }))} />
          </aside>
          <section className="deck-slide-shell beautify-content-paper" role="status" aria-busy="true" aria-label="内容梳理进度">
            <div className="deck-slide-head beautify-content-toolbar">
              <span className="num font-semibold text-primary">P{selected[0]}</span>
              <span className="text-body-sm text-ink-sub">内容页</span>
              <span className="status status-info">{CONTENT_STAGES[Math.max(0, contentStage - 1)]}…</span>
              <span className="flex-1" />
            </div>
            <div className="deck-slide beautify-content-slide beautify-organize">
              <span className="deck-spinner" aria-hidden="true" />
              <p className="beautify-organize-title">正在读取原页并提取文字…</p>
              <p className="beautify-organize-sub">只取原页已有的文字：PPTX 文本框与表格、PDF 文字层；不改写、不翻译、不精简</p>
              <ol className="beautify-organize-stages">
                {CONTENT_STAGES.map((name, index) => {
                  const no = index + 1
                  return <li key={name} className={cn('beautify-organize-stage', contentStage > no && 'is-done', contentStage === no && 'is-current')}>
                    <span className="beautify-organize-stage-dot" aria-hidden="true">{contentStage > no ? '✓' : no}</span>
                    <span>{name}</span>
                  </li>
                })}
              </ol>
              <p className="beautify-organize-note">本地完成，不调用模型，也不产生费用</p>
              <div className="beautify-organize-guide">
                <div><b>只取已有文字</b><span>文本框、表格、PDF 文字层；不改写、不翻译、不精简</span></div>
                <div><b>取不到就不编</b><span>本页没有可用文字时标为「未提取到」，留空不补写内容</span></div>
                <div><b>数字保持原样</b><span>单位、百分号、空值照原样保留，不推断成 0</span></div>
              </div>
            </div>
          </section>
        </div>
      </>}
      {step === 3 && content && currentPage && <>
        <div className="deck-split beautify-content-workspace">
          <aside className="beautify-content-sidebar">
          <h3 className="m-0 mb-4 text-h3 font-semibold text-ink-sub">页面内容</h3>
          <PageRail label="页面内容列表" current={currentIndex} onSelect={(index) => { setPageIndex(index); setEditingPage(null) }}
            items={contentPages.map(page => ({
              key: page.page_no, index: `P${page.page_no}`,
              label: `第 ${page.page_no} 页`,
              title: page.title.trim() || page.points.find(point => point.trim()) || '未提取到文字',
              dot: pageHasText(page) ? 'done' as const : 'idle' as const,
            }))} />
          </aside>
          <section className="deck-slide-shell beautify-content-paper" aria-label={`第 ${currentPage.page_no} 页内容`}>
            <div className="deck-slide-head beautify-content-toolbar">
              <span className="num font-semibold text-primary">P{currentPage.page_no}</span>
              <span className="text-body-sm text-ink-sub">内容页</span>
              <span className={cn('status', pageHasText(currentPage) ? 'status-success' : 'status-warn')}>{pageHasText(currentPage) ? currentPage.source === 'user' ? '已编辑内容' : '已提取原文' : '未提取到文字'}</span>
              <span className="tag">{currentPage.keep_material ? '保留原页画面' : '按文字重新设计'}</span>
              <span className="flex-1" />
              <button type="button" className="btn btn-secondary rounded-full" disabled={busy} onClick={() => setEditingPage(editingPage === currentPage.page_no ? null : currentPage.page_no)}>{editingPage === currentPage.page_no ? '完成编辑' : '编辑内容'}</button>
              <button type="button" className="btn btn-secondary rounded-full" disabled={busy} title="重新读取该页已保存的文字；尚未保存时读取原稿，不调用模型" onClick={() => void reextractPage(currentPage.page_no)}>{busy ? '读取中…' : '重新读取本页'}</button>
            </div>
            <div className="deck-slide beautify-content-slide">
              {editingPage === currentPage.page_no
                ? <>
                  <input className="deck-slide-title-input" value={currentPage.title} placeholder="页面标题（可留空）" aria-label={`第 ${currentPage.page_no} 页标题`} onChange={event => updateContent(currentPage.page_no, 'title', event.target.value)} />
                  <textarea className="deck-slide-body-input" value={currentPage.points.join('\n')} placeholder="页面正文，每行一条要点" aria-label={`第 ${currentPage.page_no} 页正文`} onChange={event => updateContent(currentPage.page_no, 'points', event.target.value)} />
                </>
                : <>
                  {currentPage.title.trim() && <h4 className="deck-slide-title">{currentPage.title}</h4>}
                  {currentPage.title.trim() && <span className="deck-slide-rule" aria-hidden="true" />}
                  <div className="beautify-content-text">
                  {currentPage.points.some(point => point.trim())
                    ? <ul className="deck-slide-points">{currentPage.points.filter(point => point.trim()).map((point, index) => <li key={index}>{point}</li>)}</ul>
                    : !currentPage.title.trim() && <p className="deck-slide-empty">这一页没有提取到文字。可点「编辑内容」手工补写；留空时后端会用原页画面，不编造文字。</p>}
                  </div>
                </>}
            </div>
            <div className="deck-slide-meta beautify-content-meta">
              <span>文字来源：{currentPage.source === 'none' ? '未提取到' : currentPage.source === 'user' ? '人工修改' : currentPage.source.toUpperCase()}</span>
              <span>原文段落：<span className="num">{currentPage.texts.length}</span> 条</span>
              <span>页内文字：<span className="num">{(currentPage.title + currentPage.points.join('')).length}</span> 字</span>
              <button type="button" className="link" onClick={() => setShowOrigin(value => !value)}>{showOrigin ? '隐藏原稿' : '对照原稿'}</button>
            </div>
            {showOrigin && (currentOriginUrl
              ? <img src={currentOriginUrl} alt={`原稿第 ${currentPage.page_no} 页`} className="deck-slide-origin" loading="lazy" />
              : <p className="m-0 text-caption text-ink-muted">后端未提供该页原稿图。</p>)}
          </section>
        </div>
      </>}
      {step === 4 && <>
        <div><h3 className="m-0 text-h2 font-semibold">选择目标风格</h3><p className="mb-0 mt-2 text-ink-sub">先生成所选页面中的前 <span className="num">{Math.min(3, selected.length)}</span> 页预览，核对后再继续生成全部所选页面和可编辑版。</p></div>
        <div className="beautify-style-grid" role="group" aria-label="目标风格">
          {loadingPacks && <p>加载风格包…</p>}
          {!loadingPacks && !packs.length && <p>没有可用风格包</p>}
          {visiblePacks.map(pack => <button type="button" key={pack.id} className={cn('beautify-style-option', packId === pack.id && 'is-selected')} aria-pressed={packId === pack.id} disabled={busy} onClick={() => setPackId(pack.id)}><BeautifyStyleCover pack={pack} /><span className="beautify-style-caption"><span className="font-semibold">{pack.name}</span><span className="text-caption text-ink-sub">{packId === pack.id ? '已选择' : '选择此风格'}</span></span></button>)}
        </div>
        {!loadingPacks && packs.length > 0 && <nav className="beautify-style-pagination" aria-label="风格分页">
          <span className="text-caption text-ink-sub">共 <span className="num">{packs.length}</span> 套风格 · 第 <span className="num">{currentStylePage}</span> / <span className="num">{stylePageCount}</span> 页</span>
          <button type="button" className="btn btn-secondary" disabled={busy || currentStylePage === 1} onClick={() => setStylePage(currentStylePage - 1)}>上一页</button>
          {Array.from({ length: stylePageCount }, (_, index) => index + 1).map(page => <button type="button" key={page} className={cn('beautify-pagination-number num', currentStylePage === page && 'is-current')} aria-label={`第 ${page} 页风格`} aria-current={currentStylePage === page ? 'page' : undefined} disabled={busy} onClick={() => setStylePage(page)}>{page}</button>)}
          <button type="button" className="btn btn-secondary" disabled={busy || currentStylePage === stylePageCount} onClick={() => setStylePage(currentStylePage + 1)}>下一页</button>
        </nav>}
        {packId && <p className="m-0 text-body-sm text-ink-sub">当前风格：<span className="font-semibold text-primary">{packs.find(pack => pack.id === packId)?.name || packId}</span></p>}
      </>}
      {error && <div className="error-box text-body-sm" role="alert">{error}</div>}
      {jobId && busy && stream.status === 'running' && <button type="button" className="btn btn-secondary self-start" disabled={cancelling} onClick={() => void cancelCurrent()}>{cancelling ? '正在取消，等待当前步骤结束…' : '取消生成'}</button>}
      {step === 5 && stream.status === 'cancelled' && <p role="status" className="text-body-sm">已取消，已完成的部分已保留</p>}
      {step === 5 && jobId && (stream.status === 'running' || stream.status === 'error') && <ProgressPanel job={progress} stageLabel={result?.confirmed ? '全部页面生成进度' : '美化生成进度'} />}
      {step === 5 && <button type="button" className="link self-start" onClick={() => void refresh()}>刷新结果</button>}
      {step === 5 && result?.phase !== 'done' && jobId && <div className="panel-alt text-body-sm">
        这是所选页面中前 <span className="num">3</span> 页的美化图预览（不足 <span className="num">3</span> 页时展示全部页）。可编辑版**不会自动生成**：确认后先生成图片版，需要时再点「转文字可编辑版」。
      </div>}
      {step === 5 && result && resultPages.length > 0 && <div className="deck-split">
        <PageRail label="结果页面列表" current={resultCurrentIndex} onSelect={(index) => { setResultIndex(index); setOverview(false) }}
          items={resultPages.map(page => {
            const pageState = resultPageState(page)
            return {
              key: page.page_no, label: `第 ${page.page_no} 页`,
              thumb: withVersion(page.beauty_url || page.origin_url, result.updated_at),
              status: { text: pageState.label, cls: pageState.cls },
            }
          })} />
        <section className="deck-slide-shell" aria-label={`第 ${resultCurrent.page_no} 页生成结果`}>
          <div className="deck-slide-head">
            <span className="num font-semibold text-primary">P{resultCurrent.page_no}</span>
            <span className="font-semibold">第 <span className="num">{resultCurrent.page_no}</span> 页</span>
            <span className={cn('status', resultPageState(resultCurrent).cls)}>{resultPageState(resultCurrent).label}</span>
            <span className="flex-1" />
            <button type="button" className="btn btn-primary rounded-full" disabled={busy || !resultCurrent.beauty_url} title={resultCurrent.beauty_url ? '只重新生成这一页，其它页结果不变' : '该页还没有结果，先生成预览'} onClick={() => setRegenTarget(resultCurrent.page_no)}>{busy ? '生成中…' : '重新生成本页'}</button>
            <button type="button" className="btn btn-secondary rounded-full" aria-pressed={showOrigin} disabled={busy} onClick={() => setShowOrigin(value => !value)}>{showOrigin ? '隐藏原稿' : '对比原稿'}</button>
            <button type="button" className="btn btn-secondary rounded-full" aria-pressed={overview} disabled={busy} onClick={() => setOverview(value => !value)}>{overview ? '返回单页' : '缩略总览'}</button>
          </div>
          {overview ? <OverviewGrid current={resultCurrentIndex} onSelect={(index) => { setResultIndex(index); setOverview(false) }} emptyText="未生成"
            items={resultPages.map(page => ({ key: page.page_no, label: `查看第 ${page.page_no} 页结果`, image: withVersion(page.beauty_url, result.updated_at) }))} /> : <>
            <div className="deck-media-frame">
              {generatingCurrent
                ? <div className="beautify-generating" role="status" aria-busy="true">
                      <span className="deck-spinner" aria-hidden="true" />
                      <p className="beautify-organize-title">正在生成美化结果…</p>
                      <p className="beautify-organize-sub">正在按所选风格{resultCurrent.keep_material ? '保留原页图片与版式、只替换配色与质感' : '重新设计本页'}</p>
                      <div className="beautify-generating-bar" role="progressbar" aria-valuemin={0} aria-valuemax={resultPages.length}
                           aria-valuenow={resultDoneCount} aria-valuetext={`已完成 ${resultDoneCount} / ${resultPages.length} 页`}>
                        <i style={{ width: `${resultPercent}%` }} />
                      </div>
                      <p className="beautify-organize-note">
                        已完成 <span className="num">{resultDoneCount}</span> / <span className="num">{resultPages.length}</span> 页
                        {runningPages.length > 1 && <> · <span className="num">{runningPages.length}</span> 页并发中</>}
                        {runningSeconds !== null && <> · 已用时 <span className="num">{runningSeconds}</span> 秒</>}
                      </p>
                    </div>
                : resultCurrent.beauty_url
                  ? <button type="button" className="deck-media-open" title="点击放大查看" onClick={() => setLightbox(true)}><img src={withVersion(resultCurrent.beauty_url, result.updated_at)} alt={`第 ${resultCurrent.page_no} 页生成结果`} /></button>
                  : <p className="deck-slide-empty">这一页还没有生成结果{result.phase === 'preview' ? '：预览阶段只生成所选页中的前 3 页' : ''}。</p>}
            </div>
            <div className="deck-slide-meta">
              <span>结果来源：{resultCurrent.beauty_ok ? '生图模型' : resultCurrent.beauty_url ? '生图失败，已用原图' : '尚未生成'}</span>
              <span>文字真源：{resultCurrent.text_source === 'none' ? '无（后端会降级为图生图）' : resultCurrent.text_source.toUpperCase()}</span>
            </div>
            {resultCurrent.beauty_ok === false && resultCurrent.beauty_url && <p className="m-0 text-body-sm text-ink-sub" role="alert">该页生图失败，当前显示的是原图副本；原因见下方「生成详情」的警告明细。</p>}
            {showOrigin && (resultCurrent.origin_url
              ? <img src={resultCurrent.origin_url} alt={`原稿第 ${resultCurrent.page_no} 页`} className="deck-slide-origin" loading="lazy" />
              : <p className="m-0 text-caption text-ink-muted">后端未提供该页原稿图。</p>)}
          </>}
        </section>
      </div>}
      {step === 5 && result && <details className="deck-details">
        <summary>生成详情（成本 / 供应商 / 警告 / Codex）</summary>
        <div className="panel-alt flex flex-wrap gap-4">
          <span>总页数：<span className="num">{result.page_count}</span></span>
          <span>生图张数：<span className="num">{result.cost.image_calls}</span> 张</span>
          <span>总成本：<span className="num">{result.cost.total_cny}</span> 元</span>
          <span>Codex 重建耗时：{result.codex.seconds === undefined ? '未提供' : <><span className="num">{result.codex.seconds}</span> 秒</>}</span>
          <span>耗时（本次会话作业计时）：<span className="num">{(elapsedMs / 1000).toFixed(1)}</span> 秒</span>
        </div>
        {result.cost.price_configured === false && <div className="error-box text-body-sm" role="alert">{result.cost.note}</div>}
        {result.cost.by_provider.length > 0 && <div className="panel-alt overflow-x-auto">
          <table className="w-full text-left text-body-sm">
            <thead><tr><th>供应商</th><th>生图张数</th><th>金额（元）</th></tr></thead>
            <tbody>{result.cost.by_provider.map((item) => <tr key={item.provider}>
              <td>{item.provider}</td><td className="num">{item.count}</td><td className="num">{item.cny}</td>
            </tr>)}</tbody>
          </table>
        </div>}
        <div className="panel-alt text-body-sm">
          <p className="mt-0">警告明细</p>
          {result.warnings.length ? <ul className="mb-0">{result.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : <span>后端未报告警告</span>}
          {result.codex.message && <p className="mb-0">Codex：{result.codex.message}</p>}
          {!result.exports.image && <p className="mb-0 text-ink-sub">图片版未产出：{error || result.warnings.join('；') || '后端未提供导出文件或具体原因。'}</p>}
          {!result.exports.editable && <p className="mb-0 text-ink-sub">可编辑版未产出：{result.codex.message || error || result.warnings.join('；') || (result.codex.ok ? '后端报告 Codex 成功，但未提供导出文件或具体原因。' : '后端未报告 Codex 重建成功，未提供具体原因。')}</p>}
        </div>
      </details>}
      {step === 2 && origin && <ActionBar>
        <span className="font-semibold">已选 <span className="num text-primary">{selected.length}</span> / <span className="num">{origin.page_count}</span> 页</span>
        <button type="button" className="btn btn-secondary rounded-full" disabled={busy} onClick={() => { setSelected(selected.length === origin.page_count ? [] : origin.pages.map(page => page.page_no)); setContentSaved(false) }}>{selected.length === origin.page_count ? '取消全选' : '全选'}</button>
        <button type="button" className="btn btn-secondary rounded-full" disabled={busy || !selected.length} onClick={() => { const allKept = selected.every(n => keepMaterial.includes(n)); setKeepMaterial(allKept ? keepMaterial.filter(n => !selected.includes(n)) : [...new Set([...keepMaterial, ...selected])]); setContentSaved(false) }}>{selected.length > 0 && selected.every(n => keepMaterial.includes(n)) ? '取消保留原图' : '全部保留原图'}</button>
        <button type="button" className="btn btn-primary rounded-full px-6" disabled={busy || !selected.length} onClick={() => void organizeContent()}>{busy ? '正在梳理内容…' : '开始梳理内容'}</button>
      </ActionBar>}
      {step === 3 && !content && <ActionBar>
        <span>第 <span className="num">1</span> / <span className="num">{selected.length}</span> 页</span>
        <span className="text-ink-sub">完成 <span className="num">0</span> / <span className="num">{selected.length}</span> 页</span>
        <span className="text-ink-sub">处理中 <span className="num">{selected.length}</span></span>
        <button type="button" className="btn btn-secondary rounded-full" disabled title="梳理进行中，请稍候">返回页面确认</button>
        <button type="button" className="btn btn-primary rounded-full" disabled title="梳理完成后可用">选择设计风格</button>
      </ActionBar>}
      {step === 3 && content && currentPage && <ActionBar>
        <PagerArrow dir="prev" disabled={busy || currentIndex === 0} onClick={() => { setPageIndex(currentIndex - 1); setEditingPage(null) }}/>
        <span>第 <span className="num">{currentIndex + 1}</span> / <span className="num">{contentPages.length}</span> 页</span>
        <PagerArrow dir="next" disabled={busy || currentIndex >= contentPages.length - 1} onClick={() => { setPageIndex(currentIndex + 1); setEditingPage(null) }}/>
        <span className="text-ink-sub">完成 <span className="num">{filledCount}</span> / <span className="num">{contentPages.length}</span> 页文字</span>
        <button type="button" className="btn btn-secondary rounded-full" disabled={busy} onClick={() => setStep(2)}>返回页面确认</button>
        <button type="button" className="btn btn-primary rounded-full" disabled={busy} onClick={() => void confirmContent()}>{busy ? '正在保存…' : '确认内容，选择风格'}</button>
      </ActionBar>}
      {step === 4 && <ActionBar>
        <button type="button" className="btn btn-secondary rounded-full" disabled={busy} onClick={() => setStep(3)}>返回内容梳理</button>
        <button type="button" className="btn btn-primary rounded-full px-6" disabled={busy || !packId || !selected.length || !contentSaved} onClick={() => void startPreview()}>生成前 <span className="num">{Math.min(3, selected.length)}</span> 页预览</button>
      </ActionBar>}
      {step === 5 && editableBusy && <div className="panel-alt text-body-sm" role="status">{editableStream.message || '正在重建原生可编辑版…'}</div>}
      {regenTarget !== null && <RegenerateDialog pageNo={regenTarget} onClose={() => setRegenTarget(null)} onConfirm={() => void regenerateCurrentPage()} />}
      {lightbox && result && resultPages.length > 0 && <PageLightbox
        pages={resultPages.map((page, index) => ({
          image: page.beauty_url,
          label: <>P<span className="num">{page.page_no}</span> · 第 <span className="num">{page.page_no}</span> 页</>,
          counter: <>P<span className="num">{page.page_no}</span> · 第 <span className="num">{index + 1}</span> / <span className="num">{resultPages.length}</span> 页</>,
        }))}
        index={resultCurrentIndex} onIndex={setResultIndex} onClose={() => setLightbox(false)} version={result.updated_at}
        ariaLabel={`第 ${resultCurrent?.page_no ?? ''} 页放大预览`} emptyText="这一页还没有生成结果" />}
      {step === 5 && result && resultPages.length > 0 && <ActionBar>
        <PagerArrow dir="prev" disabled={busy || resultCurrentIndex === 0} onClick={() => { setResultIndex(resultCurrentIndex - 1); setOverview(false) }}/>
        <span className="num">{resultCurrent.page_no} / {resultPages.length}</span>
        <PagerArrow dir="next" disabled={busy || resultCurrentIndex >= resultPages.length - 1} onClick={() => { setResultIndex(resultCurrentIndex + 1); setOverview(false) }}/>
        <span className="text-ink-sub">{jobActive
          ? <>正在生成 <span className="num">{resultDoneCount}</span> / <span className="num">{resultPages.length}</span> 页{runningPages.length > 1 && <>（<span className="num">{runningPages.length}</span> 页并发）</>}</>
          : <>已完成 <span className="num">{resultDoneCount}</span> / <span className="num">{resultPages.length}</span> 页</>}</span>
        <button type="button" className="btn btn-secondary rounded-full" disabled={busy || jobActive} onClick={() => setStep(4)}>重新选择风格</button>
        {result.phase === 'preview' && <button type="button" className="btn btn-primary rounded-full" disabled={busy || (!result.exports.image && stream.status !== 'cancelled')} onClick={() => void continueAll()}>{busy ? '正在生成…' : '确认预览，生成全部所选页面'}</button>}
        {result.phase === 'done' && <button type="button" className="btn btn-secondary rounded-full" disabled={busy || editableBusy}
          title={result.exports.editable ? '重新重建一次可编辑版' : '按需把图片版转成原生可编辑版（生成图片时不会自动执行）'}
          onClick={() => void convertEditable()}>{editableBusy ? '正在重建…' : result.exports.editable ? '重新转可编辑版' : '转文字可编辑版'}</button>}
        {result.exports.editable && <a className="btn btn-primary rounded-full" href={result.exports.editable} download>下载可编辑版 PPT</a>}
        {result.exports.image && <a className={cn('btn rounded-full', result.exports.editable ? 'btn-secondary' : result.phase === 'preview' ? 'btn-secondary' : 'btn-primary')} href={result.exports.image} download>下载图片集 PPT</a>}
      </ActionBar>}
      {step === 5 && stream.status === 'error' && <button type="button" className="btn btn-secondary self-start" onClick={() => { setStep(4); setResult(null); setError(null); setJobId(null) }}>返回并重新生成预览</button>}
    </div>
  )
}
