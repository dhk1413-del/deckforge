/** 文件名 → 契约 source_type（图片统一记 image） */
import type { SourceType } from '../types'

export function sourceTypeOf(name: string): SourceType {
  const ext = (name.split('.').pop() || '').toLowerCase()
  if (ext === 'markdown' || ext === 'md') return 'markdown'
  if (ext === 'txt') return 'text'
  if (ext === 'png' || ext === 'jpg' || ext === 'jpeg' || ext === 'webp') return 'image'
  return ext as SourceType
}
