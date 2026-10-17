/**
 * 首页：一个切换控件 + 三种生成方式。
 *
 *   ① 文档导入生成 —— 可用：选好文档 → 交给 6 步生成向导（不复制第二套上传/生成逻辑）
 *   ② 图片转可编辑 —— 内嵌上传：渲染出原页后进项目工作台「按图片版重建」页签，
 *                     逐页精细重建（只走第三方 skill，不做本地渲染兜底）
 *   ③ PPT美化     —— 上传 → 前 3 页逐页生图预览 → 确认后生成全部页面
 *
 * 文档与图片导入进入项目工作台；PPT 美化在首页预览与下载。地址可直达： `#/?mode=topic|editable|reskin`
 * 诚实边界：未实现的模式不允许按钮可点却什么都不做，也不假装已生成任何东西。
 */
import { useEffect, useState, type ReactNode } from 'react'
import { createProject, importPages, listStylePacks, type ApiError } from '../api'
import { IconFolder, IconPalette, IconSparkles } from '../components/Icons'
import { Dropzone } from '../components/Dropzone'
import { StylePackCard } from '../components/StylePackCard'
import { BeautifyPanel } from '../components/BeautifyPanel'
import { useAsync } from '../hooks/useAsync'
import { cn } from '../lib/format'
import { sourceTypeOf } from '../lib/source'
import { setPendingFile } from '../pendingFile'
import { UPLOAD_SIZE_HINT, uploadTooLarge, MAX_UPLOAD_BYTES } from '../lib/format'
import type { StylePack } from '../types'
import { navigate } from '../router'

type Mode = 'topic' | 'editable' | 'reskin'

// ③ PPT美化：上传 → 逐页生图预览 → 确认后逐页精细重建可编辑版。
const MODES: Array<{ id: Mode; label: string }> = [
  { id: 'topic', label: '文档导入生成' },
  { id: 'editable', label: '图片转可编辑' },
  { id: 'reskin', label: 'PPT美化' },
]

/** 左侧导轨的图标：三种方式各一个，避免用了同一枚 icon 看不出区别。 */
function ModeIcon({ id }: { id: Mode }) {
  const Icon = id === 'topic' ? IconFolder : id === 'editable' ? IconSparkles : IconPalette
  return <Icon className="h-5 w-5" />
}

function readMode(): Mode {
  const m = /[?&]mode=([^&]+)/.exec(window.location.hash)?.[1]
  return m === 'editable' || m === 'reskin' ? m : 'topic'
}

export function HomePage() {
  const [mode, setMode] = useState<Mode>(readMode)
  const [beautifyStep, setBeautifyStep] = useState(1)
  const beautifyWorkbench = mode === 'reskin' && beautifyStep > 1

  // 地址栏与切换控件保持同步（支持前进/后退与直链）
  useEffect(() => {
    const sync = () => setMode(readMode())
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  const pick = (id: Mode) => {
    setMode(id)
    const next = `#/?mode=${id}`
    if (window.location.hash !== next) window.location.hash = next
  }

  const packs = useAsync(listStylePacks, [])
  const packOptions = packs.data?.items ?? []

  return (
    <div className="flex flex-col gap-4">
      {!beautifyWorkbench && <div>
        <h2 className="m-0 text-h2 font-semibold">生成演示文稿</h2>
      </div>}
      <section id="generation-modes" className={cn('scroll-mt-20', !beautifyWorkbench && 'band')}>
        <div className={cn('grid gap-5', !beautifyWorkbench && 'md:grid-cols-[168px_1fr]')}>
          {!beautifyWorkbench && <div className="mode-rail" role="tablist" aria-label="生成方式" aria-orientation="vertical">
            {MODES.map((m) => (
              <button
                key={m.id}
                type="button"
                role="tab"
                aria-selected={mode === m.id}
                onClick={() => pick(m.id)}
              >
                <span className="mode-rail-icon" aria-hidden="true"><ModeIcon id={m.id} /></span>
                <span>{m.label}</span>
              </button>
            ))}
          </div>}

          <div className="min-w-0">
            {mode === 'topic' && <TopicPanel packs={packOptions} packsLoading={packs.loading} />}
            {mode === 'editable' && <EditablePanel />}
            {mode === 'reskin' && <BeautifyPanel packs={packOptions} loadingPacks={packs.loading} onStepChange={setBeautifyStep} />}
          </div>
        </div>
      </section>
    </div>
  )
}

/* ───────────────────────── 共用件：拖拽区 / 已选文件 ───────────────────────── */

function PickedFile({ file, onClear }: { file: File; onClear?: () => void }) {
  return (
    <div className="panel-alt flex flex-wrap items-center gap-2">
      <span className={cn('status', onClear ? 'status-success' : 'status-info')}>已选择</span>
      <span className="truncate">{file.name}</span>
      <span className="num text-caption text-ink-sub">{(file.size / 1024).toFixed(0)} KB</span>
      {onClear && (
        <>
          <span className="flex-1" />
          <button type="button" className="link text-caption" onClick={onClear}>
            清除
          </button>
        </>
      )}
    </div>
  )
}

function PanelHead({ lead }: { lead: ReactNode }) {
  return <p className="m-0 text-ink-sub">{lead}</p>
}

/* ─────────────────────── ① 文档导入生成（可用） ─────────────────────── */

const DOC_ACCEPT = '.md,.markdown,.txt,.docx,.pdf,.pptx'

function TopicPanel({ packs, packsLoading }: { packs: StylePack[]; packsLoading: boolean }) {
  const [file, setFile] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)
  /* 风格库模板：在这里先挑一个，向导第④步会预选它（仍可更换） */
  const [pickedPack, setPickedPack] = useState<string | null>(null)
  const [previewing, setPreviewing] = useState<string | null>(null)

  const choose = (f: File | null) => {
    if (!f) return
    if (!/\.(md|markdown|txt|docx|pdf|pptx)$/i.test(f.name))
      return setError(`不支持的格式：${f.name}；支持 TXT · MD · DOCX · PDF · PPTX`)
    if (f.size > MAX_UPLOAD_BYTES) return setError(uploadTooLarge(f))
    setError(null)
    setFile(f)
  }

  return (
    <div className="flex flex-col gap-3">
      <PanelHead
        lead={
          <>
            <span className="font-semibold text-ink">适合已有完整文档</span>
            ，需要 AI 规划结构并生成整套 PPT。
            <span className="text-ink-muted">（页数与风格在下一步确定）</span>
          </>
        }
      />

      <Dropzone
        head="拖入文档，开始生成 PPT"
        hint="点击此处选择文件"
        formats={`TXT · MD · DOCX · PDF · PPTX · ${UPLOAD_SIZE_HINT}`}
        accept={DOC_ACCEPT}
        onPick={(picked) => choose(picked[0] ?? null)}
      />

      {error && <div className="error-box text-body-sm">{error}</div>}
      {file && <PickedFile file={file} onClear={() => setFile(null)} />}

      <div className="flex flex-wrap items-center justify-end gap-2">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!file}
          onClick={() => {
            // 交给既有的 6 步向导：上传 → ② 大纲/页清单 → ③ 梳理 → ④ 风格 → ⑤ 生成
            if (!file) return
            setPendingFile(file)
            // 带上首页选中的风格模板（向导第④步会预选，仍可改）
            navigate(pickedPack ? `/wizard?style=${encodeURIComponent(pickedPack)}` : '/wizard')
          }}
        >
          开始生成大纲
        </button>
      </div>

      {/* 风格库模板：直接在这个页面下方挑，生成时带上；详情/大图沿用风格库同一套卡片 */}
      <section className="flex flex-col gap-3 border-t border-border pt-4">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <h2 className="m-0 text-h3">风格模板</h2>
          <span className="text-body-sm text-ink-sub">
            从风格库挑一个模板，开始生成时自动带上
            {pickedPack ? <>（已选 <span className="font-semibold text-ink">{packs.find((p) => p.id === pickedPack)?.name ?? pickedPack}</span>，第④步仍可更换）</> : '（点卡片或「选择此风格」选中，再点一次取消）'}
          </span>
        </div>
        {packsLoading && <p className="m-0 text-body-sm text-ink-sub">正在读取风格库…</p>}
        {!packsLoading && !packs.length && <p className="m-0 text-body-sm text-ink-sub">风格库里还没有可用模板。</p>}
        {packs.length > 0 && (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4" role="listbox" aria-label="风格库模板">
            {packs.map((pack) => (
              <div
                key={pack.id}
                className="cursor-pointer"
                /* 点卡片空白处即可选中；点到内部按钮（预览 / 查看 / 选择此风格）时不抢它的行为 */
                onClick={(event) => {
                  if ((event.target as HTMLElement).closest('button')) return
                  setPickedPack((value) => (value === pack.id ? null : pack.id))
                }}
              >
                <StylePackCard
                  pack={pack}
                  selected={pickedPack === pack.id}
                  previewing={previewing === pack.id}
                  onSelect={() => setPickedPack((value) => (value === pack.id ? null : pack.id))}
                  onPreview={() => setPreviewing((value) => (value === pack.id ? null : pack.id))}
                  onPreviewClose={() => setPreviewing((value) => (value === pack.id ? null : value))}
                />
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

/* ───────────── ② 图片转可编辑（PDF / 图片 / pptx → 逐页精细重建）───────────── */

function EditablePanel() {
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const totalKb = Math.round(files.reduce((sum, f) => sum + f.size, 0) / 1024)

  const start = async () => {
    if (!files.length || busy) return
    setBusy(true)
    setError(null)
    try {
      const { id } = await createProject({
        title: files[0].name.replace(/\.[^.]+$/, '') || '图片转可编辑',
        source_type: sourceTypeOf(files[0].name),
        intake_mode: 'doc',
      })
      // 逐页渲染 + 登记成 slides → 直达项目工作台的「按图片版重建」页签，并自动开始
      await importPages(id, files)
      navigate(`/projects/${id}?tab=editable&auto=1`)
    } catch (e) {
      setError((e as ApiError).detail || '导入失败，请重试')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <PanelHead
        lead={
          <>
            <span className="font-semibold text-ink">上传 PDF / 图片 / 已有 pptx</span>
            ：先按原页渲染出图片版，再由本机 agent 逐页精细重建为<b>可编辑</b> PPT。
          </>
        }
      />

      <Dropzone
        multiple
        head="拖入 PDF / 图片 / pptx（可多选，按顺序成册）"
        hint="点击此处选择文件"
        formats="PDF · PNG · JPG · PPTX · 多张图片按顺序拼成一册"
        accept=".pdf,.png,.jpg,.jpeg,.webp,.pptx"
        onPick={(picked) => {
          setError(null)
          setFiles(picked)
        }}
      />

      {files.length > 0 && (
        <div className="panel-alt flex flex-wrap items-center gap-2">
          <span className="status status-success">已选择 {files.length} 个文件</span>
          <span className="truncate">
            {files[0].name}
            {files.length > 1 ? ' 等' : ''}
          </span>
          <span className="num text-caption text-ink-sub">{totalKb} KB</span>
          <span className="flex-1" />
          <button type="button" className="link text-caption" onClick={() => setFiles([])}>
            清除
          </button>
        </div>
      )}

      {error && <div className="error-box text-body-sm">{error}</div>}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-body-sm text-ink-sub">
          上传后自动开始逐页重建；每页约 13 分钟，可随时停止，已完成页会保留。
        </span>
        <button type="button" className="btn btn-primary" disabled={!files.length || busy} onClick={start}>
          {busy ? '正在导入…' : '转可编辑 PPT'}
        </button>
      </div>

      <div className="panel-alt text-body-sm text-ink-sub">
        重建走第三方 skill（本机 agent 逐页重建 + 自带 validation 校验），产物只包含所转页面。
      </div>
    </div>
  )
}
