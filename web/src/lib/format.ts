/** 展示层格式化 —— 数字一律等宽（class="num"），金额 4 位小数（契约） */

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

/** 状态 → 状态胶囊类（浅底 + 深字） */
export function statusClass(s: string): string {
  if (['done', 'ok', 'success'].includes(s)) return 'status status-success'
  if (['failed', 'error'].includes(s)) return 'status status-danger'
  if (['running', 'generating', 'queued', 'pending'].includes(s)) return 'status status-warn'
  return 'status status-info'
}

export const projectStageLabel = (step?:number) => ['输入原稿','确认页面','确认内容','选择风格','生成结果'][(step || 1)-1] || '输入原稿'
