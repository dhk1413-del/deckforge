/**
 * 首页 → 向导的「已选文件」暂存。
 * 首页只负责选文件，真正的上传/解析仍走向导里那套既有逻辑（不复制第二套）。
 */
let pending: File | null = null

export function setPendingFile(file: File | null): void {
  pending = file
}

/** 取走并清空（防止 React 严格模式重复挂载时上传两次） */
export function takePendingFile(): File | null {
  const file = pending
  pending = null
  return file
}
