/** 拖拽上传区（首页「文档导入生成」与「图片转可编辑」共用） */
import { useRef, useState, type DragEvent } from 'react'
import { cn } from '../lib/format'

export function Dropzone({
  head, hint, formats, accept, multiple, onPick,
}: {
  head: string
  hint: string
  formats: string
  accept: string
  multiple?: boolean
  onPick: (files: File[]) => void
}) {
  const [over, setOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const openPicker = () => inputRef.current?.click()
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setOver(false)
    onPick([...(e.dataTransfer?.files ?? [])])
  }

  return (
    <div
      className={cn(
        'df-dropzone cursor-pointer rounded-lg border border-dashed border-border bg-surface px-6 py-8 text-center',
        over && 'is-over',
      )}
      onClick={openPicker}
      onDragOver={(e) => {
        e.preventDefault()
        setOver(true)
      }}
      onDragLeave={() => setOver(false)}
      onDrop={onDrop}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') openPicker()
      }}
    >
      <div className="text-h3">{head}</div>
      <div className="mt-1 text-body-sm text-ink-sub">{hint}</div>
      <div className="mt-2 text-caption text-ink-muted">{formats}</div>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(e) => {
          onPick([...(e.target.files ?? [])])
          e.target.value = ''            // 允许连续两次选同一个文件
        }}
      />
    </div>
  )
}
