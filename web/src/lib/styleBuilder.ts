/**
 * 「风格构建」面板的契约层（自包含）：类型 + API 封装 + 纯函数小工具。
 *
 * 后端契约（由并行开发的 server 端提供）：
 *   POST   /api/style-builder/upload          multipart 字段 files（多份；也兼容单个 file）
 *                                             → { builder_id, kind, files:[{name,size}], pages }
 *   POST   /api/style-builder/{bid}/analyze   { use_vision?, pages? } → { job_id, progress_url }
 *   GET    /api/style-builder/{bid}           → { builder_id, kind, status, files, result?, error? }
 *   POST   /api/style-builder/{bid}/save      { id, name, category, tags, summary } → { ok, style_pack }
 *   DELETE /api/style-builder/{bid}
 *
 * 只读依赖 ../api 的 ApiError —— 后端 {detail} 里的中文信息原样抛给界面展示，不吞。
 */
import { ApiError } from '../api'
import { BACKEND_HINT } from './format'

const API_BASE = '/api'

/* ---------------- 类型 ---------------- */

export type StyleBuilderKind = 'pptx' | 'pdf' | 'image'

/** 后端状态机：已上传 → 解析中 → 就绪 / 失败 */
export type StyleBuilderStatus = 'uploaded' | 'analyzing' | 'ready' | 'failed'

export interface StyleBuilderFileInfo {
  name: string
  size: number
}

/**
 * 实测色值（后端从画面像素统计里取，不是猜的）。
 * 固定给 accent/accent2/bg/surface/ink/inkSub，其余键名放任扩展（索引签名兜住）。
 */
export interface StyleBuilderPalette {
  accent: string
  accent2: string
  bg: string
  surface: string
  ink: string
  inkSub: string
  [key: string]: string
}

export interface StyleBuilderSuggested {
  id: string
  name: string
  category: string
  tags: string[]
  summary: string
}

export interface StyleBuilderResult {
  palette: StyleBuilderPalette
  /** {色值: 出处说明} —— 每个主色「从哪张图/哪一页的哪个区域量出来的」 */
  evidence?: Record<string, string>
  summary: string
  style_md: string
  prompt_md: string
  suggested: StyleBuilderSuggested
  /** 预览图 URL（落盘后的缩略图） */
  previews: string[]
  /** 降级提示（未配置视觉/文本模型等）：**必须显式展示，不吞** */
  warnings: string[]
}

export interface StyleBuilderState {
  builder_id: string
  kind: StyleBuilderKind
  status: StyleBuilderStatus
  files: StyleBuilderFileInfo[]
  pages?: number
  result?: StyleBuilderResult
  error?: string
}

export interface StyleBuilderUploadResponse {
  builder_id: string
  kind: StyleBuilderKind
  files: StyleBuilderFileInfo[]
  pages: number
}

export interface StyleBuilderAnalyzeResponse {
  job_id: string
  /** 后端给的进度流地址；前端按既有习惯用 useJobStream(job_id) 订阅 /api/jobs/{id}/stream */
  progress_url: string
}

export interface StyleBuilderSavePayload {
  id: string
  name: string
  category: string
  tags: string[]
  summary: string
}

/** 保存后回传的风格包（后端可能只给部分字段，故宽松声明） */
export interface StyleBuilderSavedPack {
  id?: string
  name?: string
  [key: string]: unknown
}

export interface StyleBuilderSaveResponse {
  ok: true
  style_pack: StyleBuilderSavedPack
}

/* ---------------- 前端常量 ---------------- */

/** 支持的后缀（Dropzone 的 accept） */
export const ACCEPT_ATTR = '.pptx,.pdf,.png,.jpg,.jpeg,.webp'

export const FORMAT_HINT = '支持 .pptx / .pdf / .png / .jpg / .jpeg / .webp（图片可多张）'

/** id 只允许小写字母、数字与连字符（契约） */
export const STYLE_ID_RE = /^[a-z0-9-]+$/

export const ID_HINT = '只能用小写字母、数字与连字符，例如 warm-editorial'

export const isValidStyleId = (id: string) => STYLE_ID_RE.test(id.trim())

/* ---------------- API 封装 ---------------- */

async function toApiError(res: Response): Promise<ApiError> {
  let detail = `请求失败（HTTP ${res.status}）`
  try {
    const body: unknown = await res.json()
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      const d = (body as { detail: unknown }).detail
      if (typeof d === 'string' && d.trim()) detail = d
    }
  } catch {
    /* 非 JSON 响应，保留默认文案 */
  }
  return new ApiError(detail, res.status)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch {
    // 离线错误与 api.ts、StateBlock 共用标准部署提示，说明启动方式与重试操作。
    throw new ApiError(BACKEND_HINT, 0, true)
  }
  if (!res.ok) throw await toApiError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

const bidPath = (bid: string) => `/style-builder/${encodeURIComponent(bid)}`

/** 上传模板 / 参考图（多份走 files；单份也走 files，后端兼容单 file 字段） */
export async function uploadStyleBuilder(files: File[]): Promise<StyleBuilderUploadResponse> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  return request<StyleBuilderUploadResponse>('/style-builder/upload', { method: 'POST', body: form })
}

/** 开始解析：返回 job_id + progress_url（progress_url 可直接交给进度流组件） */
export const analyzeStyleBuilder = (
  bid: string,
  opts: { use_vision?: boolean; pages?: number[] } = {},
) =>
  request<StyleBuilderAnalyzeResponse>(`${bidPath(bid)}/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...(opts.use_vision === undefined ? {} : { use_vision: opts.use_vision }),
      ...(opts.pages ? { pages: opts.pages } : {}),
    }),
  })

export const getStyleBuilder = (bid: string) =>
  request<StyleBuilderState>(bidPath(bid), { method: 'GET' })

export const saveStyleBuilder = (bid: string, payload: StyleBuilderSavePayload) =>
  request<StyleBuilderSaveResponse>(`${bidPath(bid)}/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

/** 清理临时目录（取消 / 卸载时调；后端已删掉也当成功） */
export const deleteStyleBuilder = (bid: string) =>
  request<void>(bidPath(bid), { method: 'DELETE' })

/* ---------------- 纯函数：色板 ---------------- */

/** 固定展示顺序；不在表里的键按后端给出顺序追加 */
export const PALETTE_ORDER = ['accent', 'accent2', 'bg', 'surface', 'ink', 'inkSub'] as const

export const PALETTE_LABEL: Record<string, string> = {
  accent: '主色',
  accent2: '辅色',
  bg: '底色',
  surface: '卡片面',
  ink: '正文色',
  inkSub: '次级文字',
}

export interface PaletteEntry {
  key: string
  label: string
  value: string
  /** 该色的出处说明（evidence 按色值键；兼容按令牌名键） */
  evidence?: string
}

export function paletteEntries(
  palette?: StyleBuilderPalette | null,
  evidence?: Record<string, string> | null,
): PaletteEntry[] {
  if (!palette) return []
  const known = PALETTE_ORDER as readonly string[]
  const has = (k: string) => typeof palette[k] === 'string' && palette[k].trim() !== ''
  const keys = [...PALETTE_ORDER.filter(has), ...Object.keys(palette).filter((k) => !known.includes(k) && has(k))]
  return keys.map((k) => {
    const value = palette[k]
    const ev =
      evidence?.[value] ?? evidence?.[value.toUpperCase()] ?? evidence?.[value.toLowerCase()] ?? evidence?.[k]
    return { key: k, label: PALETTE_LABEL[k] ?? k, value, ...(ev ? { evidence: ev } : {}) }
  })
}

/** evidence 逐条出处（不受色板键名限制，后端多给的也显示出来） */
export const evidencePairs = (evidence?: Record<string, string> | null): Array<[string, string]> =>
  evidence ? Object.entries(evidence).filter(([, v]) => typeof v === 'string' && v.trim() !== '') : []

/* ---------------- 纯函数：style.md 令牌概要 ---------------- */

export type StyleTokenGroup = '色值' | '字体' | '圆角' | '间距' | '其他'

export interface StyleTokenLine {
  group: StyleTokenGroup
  name: string
  value: string
}

const HEX_RE = /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/

/** 令牌归类：先看值像不像色值，再看键名语义 */
export function classifyToken(name: string, value: string): StyleTokenGroup {
  if (HEX_RE.test(value) || /colou?r|palette|配色|色/i.test(name)) return '色值'
  if (/font|typeface|字/i.test(name) || /(sans|serif|mono|PingFang|Noto|Inter|思源|黑体|宋体|雅黑)/i.test(value))
    return '字体'
  if (/radius|round|圆角/i.test(name)) return '圆角'
  if (/space|spacing|gap|padding|margin|leading|line-height|间距/i.test(name)) return '间距'
  return '其他'
}

/**
 * 从 style.md 里抽「令牌行」（key: value，含缩进层级 → 拼成 a.b 键名）。
 * 值写在下层的 section 头（`palette:`）也要进缩进栈 —— 否则子项会丢掉前缀，变成裸 `accent`。
 * 防御式：形状不定就返回空数组，绝不抛异常（风格规范由用户/AI 写，格式不可控）。
 */
export function collectStyleTokens(style_md: string, limit = 40): StyleTokenLine[] {
  const out: StyleTokenLine[] = []
  if (!style_md) return out
  const seen = new Set<string>()
  const stack: string[] = []
  for (const raw of style_md.split(/\r?\n/)) {
    if (/^\s*```/.test(raw)) break // 代码块里的是示例排版，不算令牌
    if (/^\s*---\s*$/.test(raw)) {
      stack.length = 0
      continue
    }
    const m = /^(\s*)([A-Za-z0-9_.\-]+)\s*[:=]\s*(.*?)\s*$/.exec(raw)
    if (!m) continue
    const depth = Math.floor(m[1].replace(/\t/g, '  ').length / 2)
    const value = m[3].replace(/^["']|["']$/g, '').trim()
    stack.length = depth
    stack[depth] = m[2]
    // 无内联值（`palette:` / `|` / `>`）只是分组头：记进栈但不产出令牌行
    if (!value || value === '|' || value === '>') continue
    const name = stack.filter(Boolean).join('.')
    const dedupe = `${name}=${value}`
    if (seen.has(dedupe)) continue
    seen.add(dedupe)
    out.push({ group: classifyToken(name, value), name, value })
    if (out.length >= limit) break
  }
  return out
}

export type TokenStats = Record<StyleTokenGroup, number>

export function tokenStats(lines: StyleTokenLine[]): TokenStats {
  const stats: TokenStats = { 色值: 0, 字体: 0, 圆角: 0, 间距: 0, 其他: 0 }
  for (const l of lines) stats[l.group] += 1
  return stats
}

/** 令牌概要一句话（色值 / 字体 / 圆角 / 间距 各多少个） */
export const tokenStatsText = (stats: TokenStats) =>
  `色值 ${stats['色值']} · 字体 ${stats['字体']} · 圆角 ${stats['圆角']} · 间距 ${stats['间距']}`

/* ---------------- 纯函数：表单 ---------------- */

/** 标签串 → 数组（顿号/逗号/分号/空白都算分隔符，去重、截断到 12 个） */
export function parseTags(input: string): string[] {
  return Array.from(
    new Set(
      input
        .split(/[,，、;；\s]+/)
        .map((t) => t.trim())
        .filter(Boolean),
    ),
  ).slice(0, 12)
}

/** 表单里 id 的即时校验文案（合法 → null） */
export function idFieldError(id: string): string | null {
  const v = id.trim()
  if (!v) return '请填写风格 id（用于 style-packs/<id>/ 目录名）'
  if (!isValidStyleId(v)) return `id 不合法：${ID_HINT}`
  return null
}
