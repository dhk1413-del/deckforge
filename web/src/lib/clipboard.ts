/**
 * 剪贴板取图 —— 让「风格构建」的上传区支持截图后直接 ⌘V / Ctrl+V 上传。
 *
 * 只认图片（截图 PNG / JPEG、从文件管理器复制的图片文件）；纯文本、HTML、文件路径一律不接管，
 * 把这次粘贴交回浏览器默认行为 —— 否则会把输入框里的文本粘贴一起吃掉。
 *
 * 为什么要重命名：剪贴板里的图片经常没有可靠文件名（浏览器截图统一叫 image.png），
 * 同名文件在上传清单里会撞 key，也分不清是哪一次粘贴；这里统一成
 * `${原名去掉后缀}-YYYYMMDD-HHmmss-N.png`（没有原名就用「粘贴图片」）。
 */

/** MIME → 后缀（剪贴板截图通常是 image/png；jpeg 统一归一成 .jpg） */
const MIME_EXT: Record<string, string> = {
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/jpg': '.jpg',
  'image/webp': '.webp',
}

/** 后缀 → MIME（File 没带 type 时补一个，后端按后缀识别，两处都要对得上） */
const EXT_MIME: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
}

const IMAGE_NAME_RE = /\.(png|jpe?g|webp)$/i

/** 图片后缀；不是图片 → ''（调用方据此忽略这次粘贴） */
function imageExtOf(file: File): string {
  const named = IMAGE_NAME_RE.exec(file.name || '')?.[1]?.toLowerCase() ?? ''
  if (named) return named === 'jpeg' ? '.jpg' : `.${named}`
  return MIME_EXT[(file.type || '').trim().toLowerCase()] ?? ''
}

const pad2 = (n: number) => String(n).padStart(2, '0')

/** 占位文件名：原名 + 时间戳 + 序号，保证同批粘贴不重名 */
function pastedName(file: File, ext: string, now: Date, index: number): string {
  const base = (file.name || '').replace(/\.[^./\\]+$/, '').trim() || '粘贴图片'
  const day = `${now.getFullYear()}${pad2(now.getMonth() + 1)}${pad2(now.getDate())}`
  const time = `${pad2(now.getHours())}${pad2(now.getMinutes())}${pad2(now.getSeconds())}`
  return `${base}-${day}-${time}-${index}${ext}`
}

/**
 * 从一次粘贴事件的数据里取出图片文件（可能是 0 张）。
 * 0 张 → 调用方不该 preventDefault，让文本/HTML 照常粘贴。
 */
export function clipboardImages(data: DataTransfer | null, now: Date = new Date()): File[] {
  if (!data) return []
  const out: File[] = []

  const take = (file: File | null) => {
    if (!file) return
    const ext = imageExtOf(file)
    if (!ext) return
    const type = file.type || EXT_MIME[ext]
    out.push(
      new File([file], pastedName(file, ext, now, out.length + 1), {
        type,
        lastModified: file.lastModified || now.getTime(),
      }),
    )
  }

  // 标准路径：items 里 kind=file 的才是文件（文本/HTML 的 kind 是 string）
  if (data.items) {
    for (const item of Array.from<DataTransferItem>(data.items)) {
      if (item.kind === 'file') take(item.getAsFile())
    }
  }
  // 兜底：个别浏览器只填 files 不填 items；items 已取到图就不重复取
  if (out.length === 0) {
    for (const file of Array.from<File>(data.files)) take(file)
  }
  return out
}
