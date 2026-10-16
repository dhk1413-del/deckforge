/** 展示层格式化 —— 数字一律等宽（class="num"），金额 4 位小数（契约） */

/** 标准部署的离线提示；开发代理端口由 Vite 配置决定。 */
export const BACKEND_HINT = '后端未响应 —— 在项目根目录执行 bash server/start-lan.sh（默认 127.0.0.1:8641），然后点「重试」'

/** 单文件上传上限（前端守卫；后端不设上限）。文案与各处守卫共用，避免改一处漏一处。 */
export const MAX_UPLOAD_MB = 60
export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
/** Dropzone 里显示的格式+大小提示（各流程格式不同，大小这部分统一取这里） */
export const UPLOAD_SIZE_HINT = `单文件最大 ${MAX_UPLOAD_MB}MB`
export const uploadTooLarge = (file: { name: string; size: number }) =>
  `${file.name} 超过 ${MAX_UPLOAD_MB}MB（${(file.size / 1048576).toFixed(1)}MB）`

export const cn = (...parts: Array<string | false | null | undefined>) =>
  parts.filter(Boolean).join(' ')

/** 金额：契约单位为「元」，保留 4 位小数 */
export const cny = (v: number | null | undefined) => `¥${(v ?? 0).toFixed(4)}`

/** 耗时：<1s 用 ms，否则秒（保留 1 位） */
export const ms = (v: number | null | undefined) => {
  const n = v ?? 0
  return n < 1000 ? `${n} ms` : `${(n / 1000).toFixed(1)} s`
}

export const bytes = (v: number | null | undefined) => {
  const n = v ?? 0
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

/** 百分比（0~1 输入） */
export const pct = (v: number | null | undefined) => `${Math.round((v ?? 0) * 100)}%`

export const fmtTime = (iso: string) => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** 页码统一 2 位补齐，便于表格对齐 */
export const pageNo = (n: number) => String(n).padStart(2, '0')

/** 语义色兜底：只接受 #RGB / #RRGGBB，其余回退到设计令牌 */
export const safeHex = (v: string, fallback: string) =>
  /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(v) ? v : fallback

/** 从 style.md front matter tokens 里抓颜色（形状不定，防御式扁平化） */
export function collectColorTokens(tokens: unknown): Array<{ name: string; value: string }> {
  const out: Array<{ name: string; value: string }> = []
  const walk = (node: unknown, prefix: string) => {
    if (typeof node === 'string') {
      if (/^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(node)) out.push({ name: prefix, value: node })
      return
    }
    if (node && typeof node === 'object') {
      for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
        walk(v, prefix ? `${prefix}.${k}` : k)
      }
    }
  }
  walk(tokens, '')
  return out.slice(0, 16)
}

export const STATUS_LABEL: Record<string, string> = {
  interrupted: '已中断',
  cancelled: '已取消',
  imported: '已导入',
  partial_success: '部分完成',
  draft: '草稿',
  parsed: '已解析',
  outlined: '已梳理',
  generating: '生成中',
  done: '已完成',
  failed: '失败',
  pending: '排队中',
  running: '生成中',
  queued: '排队中',
  error: '失败',
}

export const statusLabel = (s: string) => STATUS_LABEL[s] ?? s

/** 备注任务状态 → 中文。与项目状态区分：备注的 generating 是「写备注中」 */
export const NOTES_STATUS_LABEL: Record<string, string> = {
  uploaded: '刚上传',
  analyzing: '识别中',
  analyzed: '已识别',
  generating: '写备注中',
  done: '已完成',
  failed: '失败',
}
export const notesStatusLabel = (s: string) => NOTES_STATUS_LABEL[s] ?? s

/** 状态 → 状态胶囊类（浅底 + 深字） */
export function statusClass(s: string): string {
  if (['done', 'ok', 'success'].includes(s)) return 'status status-success'
  if (['failed', 'error'].includes(s)) return 'status status-danger'
  if (['running', 'generating', 'queued', 'pending'].includes(s)) return 'status status-warn'
  return 'status status-info'
}

export const projectStageLabel = (step?:number) => ['上传内容','编辑大纲','内容梳理','选择风格','确认设计','生成页面'][(step || 1)-1] || '上传内容'
