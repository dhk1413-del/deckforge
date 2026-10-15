/**
 * 「风格构建」面板（自包含组件）
 *
 * 用户视角：上传 PPTX / PDF 模板或风格参考图 → 后端解析出配色 / 字体层级 / 版式 / 画面语言 →
 * 人工确认（id / 中文名 / 分类 / 标签 / 一句话摘要）→ 存成新的风格包。
 *
 * 自包含约定：builder_id、SSE 进度、解析结果、表单全部在组件内部管理，不依赖任何全局 store；
 * 父级只需接 onSaved（跳到风格库）与 onCancel（关闭/返回）。
 *
 * 状态机：pick → uploaded → analyzing →（preview | failed）→ saved
 *  · analyzing 期间：useJobStream(job_id) 订阅进度（SSE），同时 4s 轮询一次 GET 拿最终 result；
 *  · failed：显示后端 error，给「重试」；
 *  · 取消 / 卸载且作业在跑：调 DELETE 清理后端临时目录。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ApiError } from '../api'
import { useAsync } from '../hooks/useAsync'
import { useJobStream } from '../hooks/useJobStream'
import { bytes, cn, safeHex } from '../lib/format'
import {
  ACCEPT_ATTR,
  FORMAT_HINT,
  ID_HINT,
  analyzeStyleBuilder,
  collectStyleTokens,
  deleteStyleBuilder,
  evidencePairs,
  getStyleBuilder,
  idFieldError,
  isValidStyleId,
  paletteEntries,
  parseTags,
  saveStyleBuilder,
  tokenStats,
  tokenStatsText,
  uploadStyleBuilder,
} from '../lib/styleBuilder'
import type {
  PaletteEntry,
  StyleBuilderResult,
  StyleBuilderSavedPack,
  StyleBuilderUploadResponse,
} from '../lib/styleBuilder'
import { Dropzone } from './Dropzone'
import { ProgressPanel } from './ProgressPanel'
import { ErrorState, Loading, Notice } from './StateBlock'
import { useToast } from './Toast'

type Phase = 'pick' | 'uploaded' | 'analyzing' | 'failed' | 'preview' | 'saved'

const PHASE_BADGE: Record<Phase, { text: string; cls: string }> = {
  pick: { text: '待上传', cls: 'status-info' },
  uploaded: { text: '已上传', cls: 'status-info' },
  analyzing: { text: '解析中', cls: 'status-warn' },
  failed: { text: '解析失败', cls: 'status-danger' },
  preview: { text: '待确认', cls: 'status-warn' },
  saved: { text: '已保存', cls: 'status-success' },
}

/** 解析阶段（后端 stage → 中文）：提取主题色 → 像素统计 → 视觉理解 → 撰写规范 → 落盘预览 */
const STAGES: Array<{ key: string; label: string }> = [
  { key: 'palette', label: '提取主题色' },
  { key: 'pixels', label: '像素统计' },
  { key: 'vision', label: '视觉理解' },
  { key: 'spec', label: '撰写规范' },
  { key: 'preview', label: '落盘预览' },
]

/** 后端 stage 名可能有别名，统一归一到一个阶段 key */
const STAGE_ALIAS: Record<string, string> = {
  palette: 'palette',
  palette_extract: 'palette',
  paletteextract: 'palette',
  colors: 'palette',
  theme: 'palette',
  pixels: 'pixels',
  pixel: 'pixels',
  stats: 'pixels',
  vision: 'vision',
  understand: 'vision',
  vision_understand: 'vision',
  spec: 'spec',
  style: 'spec',
  style_md: 'spec',
  write: 'spec',
  prompt: 'spec',
  preview: 'preview',
  previews: 'preview',
  render: 'preview',
  save: 'preview',
  done: 'preview',
}

const stageKeyOf = (stage: string) => STAGE_ALIAS[stage] ?? ''

/** 错误对象 → 可展示的中文一句（后端 detail 优先，不吞） */
function detailOf(e: unknown): string {
  if (e instanceof ApiError) return e.detail
  if (e instanceof Error) return e.message
  return String(e)
}

/** 阶段进度条（五个阶段：已完成 / 进行中 / 未开始） */
function StageStrip({ seen, current }: { seen: Set<string>; current: string }) {
  return (
    <ol className="m-0 flex list-none flex-wrap items-center gap-2 p-0" aria-label="解析阶段">
      {STAGES.map((s, i) => {
        const done = seen.has(s.key)
        const active = !done && s.key === current
        return (
          <li key={s.key} className="flex items-center gap-2">
            {i > 0 && <span aria-hidden="true" className="text-ink-muted">→</span>}
            <span
              className={cn('status', done ? 'status-success' : active ? 'status-warn' : 'status-info')}
              aria-current={active ? 'step' : undefined}
              title={done ? '已完成' : active ? '进行中' : '未开始'}
            >
              {s.label}
              {done ? ' ✓' : active ? ' …' : ''}
            </span>
          </li>
        )
      })}
    </ol>
  )
}

/** 只读结果预览（saved 阶段也复用同一块，确认用户看到的就是要存的东西） */
function ResultPreview({
  result,
  copiedKey,
  onCopy,
  onZoom,
}: {
  result: StyleBuilderResult
  copiedKey: string | null
  onCopy: (value: string, key: string) => void
  onZoom: (url: string) => void
}) {
  const entries = useMemo(() => paletteEntries(result.palette, result.evidence), [result.palette, result.evidence])
  const evidence = useMemo(() => evidencePairs(result.evidence), [result.evidence])
  const tokens = useMemo(() => collectStyleTokens(result.style_md ?? ''), [result.style_md])
  const stats = useMemo(() => tokenStats(tokens), [tokens])

  return (
    <div className="flex flex-col gap-3">
      {/* 降级提示：后端说没配上模型就直说，不装作正常 */}
      {result.warnings?.length > 0 && (
        <div className="flex flex-col gap-2" role="status">
          {result.warnings.map((w) => (
            <Notice key={w} kind="warn">
              {w}
            </Notice>
          ))}
        </div>
      )}

      <p className="m-0 text-body-md">{result.summary || '（后端未给出风格摘要）'}</p>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="panel-alt flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-semibold">色板</span>
            <span className="text-caption text-ink-sub">实测色值 · 点色块即复制</span>
          </div>
          <div className="flex flex-wrap gap-3">
            {entries.map((e: PaletteEntry) => (
              <button
                key={e.key}
                type="button"
                className="flex cursor-pointer flex-col items-start gap-1 rounded-sm border-0 bg-transparent p-1 text-left"
                onClick={() => onCopy(e.value, e.key)}
                aria-label={`复制色值 ${e.value}（${e.label}）`}
                title={e.evidence ? `${e.label} ${e.value} —— ${e.evidence}` : `${e.label} ${e.value}`}
              >
                <span
                  className="inline-block h-8 w-12 rounded-sm border border-border"
                  style={{ background: safeHex(e.value, 'var(--color-surface-alt)') }}
                  aria-hidden="true"
                />
                <span className="text-caption">
                  <span className="num">{e.value}</span>
                  <br />
                  <span className="text-ink-sub">
                    {e.label}
                    {copiedKey === e.key ? ' · 已复制' : ''}
                  </span>
                </span>
              </button>
            ))}
            {entries.length === 0 && <span className="text-caption text-ink-sub">后端未返回色板</span>}
          </div>
        </div>

        <div className="panel-alt flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-semibold">实测证据</span>
            <span className="text-caption text-ink-sub">每个主色从哪来的</span>
          </div>
          {evidence.length > 0 ? (
            <ul className="m-0 list-none overflow-auto p-0 text-caption">
              {evidence.map(([color, why]) => (
                <li key={color} className="flex items-start gap-2 border-t border-divider py-1">
                  <span
                    className="mt-0.5 inline-block h-3 w-3 shrink-0 rounded-sm border border-border"
                    style={{ background: safeHex(color, 'var(--color-surface-alt)') }}
                    aria-hidden="true"
                  />
                  <span className="num shrink-0">{color}</span>
                  <span className="min-w-0 flex-1 text-ink-sub">{why}</span>
                </li>
              ))}
            </ul>
          ) : (
            <span className="text-caption text-ink-sub">后端未给出逐色出处（可能未开启视觉模型）</span>
          )}
        </div>

        <div className="panel-alt flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-semibold">style.md 令牌概要</span>
            <span className="num text-caption text-ink-sub">{tokenStatsText(stats)}</span>
          </div>
          {tokens.length > 0 ? (
            <details>
              <summary className="link text-caption">展开令牌明细（{tokens.length} 条）</summary>
              <ul className="m-0 list-none overflow-auto p-0 text-caption">
                {tokens.map((t) => (
                  <li key={`${t.name}=${t.value}`} className="flex items-center gap-2 border-t border-divider py-1">
                    <span className="tag shrink-0">{t.group}</span>
                    <span className="num min-w-0 flex-1 truncate" title={t.name}>{t.name}</span>
                    <span className="num shrink-0 text-ink-sub">{t.value}</span>
                  </li>
                ))}
              </ul>
            </details>
          ) : (
            <span className="text-caption text-ink-sub">style.md 里没解析出可识别的令牌行</span>
          )}
          <pre className="panel-alt m-0 max-h-40 overflow-auto whitespace-pre-wrap text-caption">
            {result.style_md?.slice(0, 1200) || '（空）'}
          </pre>
        </div>

        <div className="panel-alt flex flex-col gap-2">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="font-semibold">预览</span>
            <span className="num text-caption text-ink-sub">
              {result.previews?.length ?? 0} 张
            </span>
          </div>
          {result.previews?.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {result.previews.map((u, i) => (
                <button
                  key={u}
                  type="button"
                  className="overflow-hidden rounded-sm border border-border bg-transparent p-0"
                  onClick={() => onZoom(u)}
                  aria-label={`查看第 ${i + 1} 张风格预览大图`}
                >
                  <img src={u} alt={`风格预览 ${i + 1}`} loading="lazy" className="block h-20 w-32 object-cover" />
                </button>
              ))}
            </div>
          ) : (
            <span className="text-caption text-ink-sub">后端未产出预览图</span>
          )}
        </div>
      </div>
    </div>
  )
}

export function StyleBuilderPanel({
  onSaved,
  onCancel,
  className,
}: {
  /** 保存成功后的跳转提示（父级负责导航，例如 navigate(`/styles/${id}`)） */
  onSaved?: (packId: string) => void
  /** 点「取消 / 放弃」时通知父级（可关闭面板或返回上一页） */
  onCancel?: () => void
  className?: string
}) {
  const toast = useToast()

  const [phase, setPhase] = useState<Phase>('pick')
  const [uploading, setUploading] = useState(false)
  const [uploadRes, setUploadRes] = useState<StyleBuilderUploadResponse | null>(null)
  const [useVision, setUseVision] = useState(true)
  const [jobId, setJobId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState<StyleBuilderSavedPack | null>(null)
  const [copiedKey, setCopiedKey] = useState<string | null>(null)
  const [zoom, setZoom] = useState<string | null>(null)
  const [form, setForm] = useState({ id: '', name: '', category: '', tags: '', summary: '' })

  const bid = uploadRes?.builder_id ?? null
  const bidRef = useRef<string | null>(null)
  const phaseRef = useRef<Phase>(phase)
  /** 已把 suggested 灌进表单的 builder_id（避免轮询把用户改过的输入覆盖掉） */
  const seededRef = useRef('')

  useEffect(() => {
    bidRef.current = bid
  }, [bid])
  useEffect(() => {
    phaseRef.current = phase
  }, [phase])

  /* ---------------- 数据：GET 状态/结果 ---------------- */
  const detail = useAsync(() => getStyleBuilder(bid as string), [bid], Boolean(bid))
  const data = detail.data
  const reload = detail.reload

  const stream = useJobStream(jobId, {
    onDone: () => {
      // 终态：立刻拉一次结果（保持 jobId，让进度面板停在「已完成」）
      reload()
    },
    onError: (msg) => {
      setActionError(msg)
      setJobId(null)
      setPhase('failed')
    },
  })

  /** 解析中：GET 轮询兜底（SSE 断了也能走到 preview / failed） */
  useEffect(() => {
    if (phase !== 'analyzing') return
    const t = window.setInterval(() => reload(), 4000)
    return () => window.clearInterval(t)
  }, [phase, reload])

  /** 后端状态 → 阶段 + 表单初始值 */
  useEffect(() => {
    if (!data) return
    if (data.status === 'ready' && data.result && seededRef.current !== data.builder_id) {
      seededRef.current = data.builder_id
      const s = data.result.suggested
      setForm({
        id: s?.id ?? '',
        name: s?.name ?? '',
        category: s?.category ?? '',
        tags: (s?.tags ?? []).join('、'),
        summary: s?.summary || data.result.summary || '',
      })
      setJobId(null)
      setActionError(null)
      setPhase('preview')
    } else if (data.status === 'failed') {
      setActionError(data.error || '解析失败（后端未给出原因）')
      setJobId(null)
      setPhase('failed')
    }
  }, [data])

  /* ---------------- 交互 ---------------- */

  const resetAll = useCallback(() => {
    seededRef.current = ''
    setUploadRes(null)
    setJobId(null)
    setPhase('pick')
    setUploading(false)
    setSaving(false)
    setActionError(null)
    setFormError(null)
    setSaved(null)
    setForm({ id: '', name: '', category: '', tags: '', summary: '' })
  }, [])

  /** 卸载时若作业还在跑 → 清掉后端临时目录（已完成/已保存的不动） */
  useEffect(
    () => () => {
      const id = bidRef.current
      const p = phaseRef.current
      if (id && (p === 'analyzing' || p === 'uploaded' || p === 'failed')) {
        void deleteStyleBuilder(id).catch(() => {})
      }
    },
    [],
  )

  const onPick = useCallback(
    async (files: File[]) => {
      if (!files.length) return
      setActionError(null)
      setUploading(true)
      try {
        const res = await uploadStyleBuilder(files)
        setUploadRes(res)
        seededRef.current = ''
        setPhase('uploaded')
        toast.success(
          `已上传 ${res.files?.length ?? files.length} 个文件`,
          res.kind === 'pptx' ? `PPTX 模板，共 ${res.pages} 页` : res.kind === 'pdf' ? `PDF 参考文件，共 ${res.pages} 页` : `风格参考图，共 ${res.pages} 张`,
        )
      } catch (e) {
        const d = detailOf(e)
        setActionError(d)
        toast.error('上传失败', d)
      } finally {
        setUploading(false)
      }
    },
    [toast],
  )

  const startAnalyze = useCallback(async () => {
    if (!bid) return
    setActionError(null)
    setPhase('analyzing')
    try {
      const res = await analyzeStyleBuilder(bid, { use_vision: useVision })
      setJobId(res.job_id)
      reload()
    } catch (e) {
      const d = detailOf(e)
      setActionError(d)
      setPhase('failed')
    }
  }, [bid, useVision, reload])

  /** 清理后端临时目录；silent=true 时失败不打扰用户 */
  const discard = useCallback(
    async (silent = false) => {
      const id = bidRef.current
      if (!id) return
      try {
        await deleteStyleBuilder(id)
        if (!silent) toast.info('已放弃这次风格构建', '后端临时目录已清理')
      } catch (e) {
        if (!silent) toast.warn('临时目录未能清理', detailOf(e))
      }
    },
    [toast],
  )

  const handleDiscard = useCallback(() => {
    const keep = phaseRef.current === 'saved'
    if (!keep) void discard()
    bidRef.current = null
    resetAll()
    onCancel?.()
  }, [discard, onCancel, resetAll])

  const copyColor = useCallback(
    async (value: string, key: string) => {
      try {
        if (!navigator.clipboard) throw new Error('当前浏览器不支持剪贴板 API')
        await navigator.clipboard.writeText(value)
        setCopiedKey(key)
        window.setTimeout(() => setCopiedKey((c) => (c === key ? null : c)), 1600)
        toast.info(`已复制 ${value}`)
      } catch {
        toast.warn('复制失败', `请手动选中 ${value} 复制（浏览器拒绝了剪贴板访问）`)
      }
    },
    [toast],
  )

  const idError = form.id ? idFieldError(form.id) : null
  const idOk = isValidStyleId(form.id)

  const doSave = useCallback(async () => {
    if (!bid) return
    const err = idFieldError(form.id)
    if (err) {
      setFormError(err)
      return
    }
    setFormError(null)
    setSaving(true)
    try {
      const res = await saveStyleBuilder(bid, {
        id: form.id.trim(),
        name: form.name.trim() || form.id.trim(),
        category: form.category.trim() || '未分类',
        tags: parseTags(form.tags),
        summary: form.summary.trim(),
      })
      setSaved(res.style_pack ?? { id: form.id.trim() })
      setPhase('saved')
      toast.success(
        `已保存风格包「${res.style_pack?.name ?? (form.name.trim() || form.id.trim())}」`,
        '可在「风格」页查看并绑定到生成向导',
      )
    } catch (e) {
      const d = detailOf(e)
      setFormError(d)
      toast.error('保存失败', d)
    } finally {
      setSaving(false)
    }
  }, [bid, form, toast])

  /* 预览大图：Esc 关闭 */
  useEffect(() => {
    if (!zoom) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setZoom(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [zoom])

  const seenStages = useMemo(() => {
    const s = new Set<string>()
    for (const e of stream.events) {
      const k = stageKeyOf(e.stage)
      if (k) s.add(k)
    }
    return s
  }, [stream.events])

  const currentStage = useMemo(() => {
    for (let i = stream.events.length - 1; i >= 0; i--) {
      const k = stageKeyOf(stream.events[i].stage)
      if (k) return k
    }
    return ''
  }, [stream.events])

  const badge = PHASE_BADGE[phase]
  const result = data?.result
  const savedId = (saved?.id as string | undefined) ?? form.id.trim()

  return (
    <section className={cn('card flex flex-col gap-3', className)} aria-label="风格构建面板">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="card-title m-0! text-h3">风格构建</h2>
        <span className={cn('status', badge.cls)}>{badge.text}</span>
        {bid && <span className="num text-caption text-ink-sub">builder: {bid}</span>}
        <span className="flex-1" />
        {onCancel && phase !== 'pick' && phase !== 'saved' && (
          <button
            type="button"
            className="btn btn-ghost h-8! text-body-sm"
            onClick={handleDiscard}
            aria-label="取消并放弃这次风格构建"
          >
            取消
          </button>
        )}
      </div>

      <p className="m-0 text-body-sm text-ink-sub">
        上传 PPTX / PDF 模板或风格参考图，系统会自动解析出配色、字体层级、版式与画面语言，生成一套新的风格规范。
      </p>

      {/* 即时错误（上传/保存/解析）：后端中文 detail 原样展示 */}
      {actionError && phase !== 'failed' && (
        <div className="error-box" role="alert">
          {actionError}
        </div>
      )}
      {detail.error && (
        <ErrorState error={detail.error} onRetry={reload} title="风格构建状态读取失败" />
      )}

      {/* 1. 初始态：上传 */}
      {phase === 'pick' && (
        <div className="flex flex-col gap-2">
          <Dropzone
            head="上传模板或参考图"
            hint="拖进来或点击选择；解析结果先给你确认，确认后才落成风格包"
            formats={FORMAT_HINT}
            accept={ACCEPT_ATTR}
            multiple
            onPick={(files) => void onPick(files)}
          />
          {uploading && <Loading rows={1} label="正在上传…" />}
        </div>
      )}

      {/* 2. 已上传：文件清单 + 页数 + 开始解析 */}
      {phase === 'uploaded' && uploadRes && (
        <div className="flex flex-col gap-3">
          <div className="panel-alt flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">
                {uploadRes.kind === 'pptx' ? 'PPTX 模板' : uploadRes.kind === 'pdf' ? 'PDF 参考文件' : '风格参考图'}
              </span>
              <span className="tag num">{uploadRes.pages} 页</span>
              <span className="text-caption text-ink-sub">
                共 {uploadRes.files?.length ?? 0} 个文件
              </span>
            </div>
            <ul className="m-0 list-none p-0 text-body-sm">
              {(uploadRes.files ?? []).map((f) => (
                <li key={f.name} className="flex items-center gap-2 border-t border-divider py-1">
                  <span className="num min-w-0 flex-1 truncate" title={f.name}>{f.name}</span>
                  <span className="num shrink-0 text-ink-sub">{bytes(f.size)}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void startAnalyze()}
              aria-label="开始解析上传的模板或参考图"
            >
              开始解析
            </button>
            <label className="flex items-center gap-2 text-body-sm">
              <input
                type="checkbox"
                className="h-4 w-4 accent-[var(--color-accent)]"
                checked={useVision}
                onChange={(e) => setUseVision(e.target.checked)}
                aria-label="用视觉模型看画面（理解版式与画面语言）"
              />
              用视觉模型看画面
            </label>
            <span className="text-caption text-ink-sub">
              不勾选也能出配色与像素统计，但画面语言/版式描述会弱一些
            </span>
            <span className="flex-1" />
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleDiscard}
              aria-label="放弃这次上传并清理后端临时目录"
            >
              放弃
            </button>
          </div>
        </div>
      )}

      {/* 3. 解析中：SSE 进度 + 阶段文字 */}
      {phase === 'analyzing' && (
        <div className="flex flex-col gap-3">
          <StageStrip seen={seenStages} current={currentStage} />
          <ProgressPanel job={stream} stageLabel="正在解析风格" />
        </div>
      )}

      {/* 4. 失败：error + 重试 */}
      {phase === 'failed' && (
        <div className="flex flex-col gap-3">
          <div className="error-box" role="alert">
            <div className="font-semibold">解析失败</div>
            <p className="m-0 mt-1 text-body-sm">{actionError ?? '后端未给出原因'}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void startAnalyze()}
              disabled={!bid}
              aria-label="重试解析"
            >
              重试
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleDiscard}
              aria-label="放弃这次风格构建并清理后端临时目录"
            >
              放弃
            </button>
          </div>
        </div>
      )}

      {/* 5. 结果预览 + 表单 + 保存 */}
      {(phase === 'preview' || phase === 'saved') && result && (
        <div className="flex flex-col gap-3">
          <ResultPreview
            result={result}
            copiedKey={copiedKey}
            onCopy={(v, k) => void copyColor(v, k)}
            onZoom={setZoom}
          />

          <div className="panel-alt flex flex-col gap-2">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-semibold">风格标识</span>
              <span className="text-caption text-ink-sub">保存后写入 style-packs/&lt;id&gt;/</span>
            </div>
            <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
              <label className="flex flex-col gap-1 text-caption">
                <span>id（{ID_HINT}）</span>
                <input
                  className={cn('input', idError && 'is-error')}
                  value={form.id}
                  placeholder="warm-editorial"
                  aria-label="风格标识 id"
                  aria-invalid={Boolean(idError)}
                  disabled={phase === 'saved'}
                  onChange={(e) => {
                    setForm((f) => ({ ...f, id: e.target.value }))
                    setFormError(null)
                  }}
                />
              </label>
              <label className="flex flex-col gap-1 text-caption">
                <span>中文名</span>
                <input
                  className="input"
                  value={form.name}
                  placeholder="暖调编辑风"
                  aria-label="风格中文名"
                  disabled={phase === 'saved'}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                />
              </label>
              <label className="flex flex-col gap-1 text-caption">
                <span>分类</span>
                <input
                  className="input"
                  value={form.category}
                  placeholder="商务 / 教育 / 科技…"
                  aria-label="风格分类"
                  disabled={phase === 'saved'}
                  onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                />
              </label>
              <label className="flex flex-col gap-1 text-caption">
                <span>标签（顿号或逗号分隔）</span>
                <input
                  className="input"
                  value={form.tags}
                  placeholder="暖色、留白、衬线标题"
                  aria-label="风格标签"
                  disabled={phase === 'saved'}
                  onChange={(e) => setForm((f) => ({ ...f, tags: e.target.value }))}
                />
              </label>
            </div>
            <label className="flex flex-col gap-1 text-caption">
              <span>一句话摘要</span>
              <input
                className="input"
                value={form.summary}
                placeholder="米色底 + 砖红强调色，标题用粗衬线，正文留白大"
                aria-label="风格一句话摘要"
                disabled={phase === 'saved'}
                onChange={(e) => setForm((f) => ({ ...f, summary: e.target.value }))}
              />
            </label>
            {idError && (
              <span className="text-caption" role="alert" style={{ color: 'var(--color-danger-ink)' }}>
                {idError}
              </span>
            )}
            {formError && (
              <div className="error-box" role="alert">
                {formError}
              </div>
            )}
          </div>

          {phase === 'preview' ? (
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => void doSave()}
                disabled={saving || !idOk}
                title={idOk ? '把这次解析结果存成风格包' : ID_HINT}
                aria-label="保存为风格包"
              >
                保存为风格包
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleDiscard}
                aria-label="放弃这次风格构建并清理后端临时目录"
              >
                放弃
              </button>
              {saving && <span className="text-caption text-ink-sub">正在保存…</span>}
              {!idOk && form.id && <span className="text-caption text-ink-sub">{ID_HINT}</span>}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              <Notice
                kind="success"
                action={
                  <button
                    type="button"
                    className="btn btn-secondary h-8! text-body-sm"
                    onClick={() => onSaved?.(savedId)}
                    disabled={!onSaved}
                    title={onSaved ? '跳到风格库查看新风格包' : '父级未提供 onSaved 回调，无法跳转'}
                    aria-label="跳转到风格库查看新风格包"
                  >
                    去风格库看看
                  </button>
                }
              >
                已加入风格库：<span className="num">{savedId}</span>
                {form.name ? `（${form.name}）` : ''}
              </Notice>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={handleDiscard}
                  aria-label="再做一套风格"
                >
                  再做一套
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 预览大图灯箱 */}
      {zoom && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-label="风格预览大图"
          onClick={() => setZoom(null)}
        >
          <img
            src={zoom}
            alt="风格预览大图"
            className="max-h-[80vh] max-w-[92vw] rounded-md border border-white/25 bg-white object-contain"
          />
          <button
            type="button"
            className="btn btn-secondary absolute bottom-6"
            onClick={(e) => {
              e.stopPropagation()
              setZoom(null)
            }}
            aria-label="关闭预览大图"
          >
            关闭
          </button>
        </div>
      )}
    </section>
  )
}
