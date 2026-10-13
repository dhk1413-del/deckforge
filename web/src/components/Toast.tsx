/**
 * 全局提示（Toast）：右上角、4s 自动消失；错误可复制详情（components.md）。
 */
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { cn } from '../lib/format'

export type ToastKind = 'info' | 'success' | 'warn' | 'error'

export interface ToastItem {
  id: number
  kind: ToastKind
  text: string
  detail?: string
}

interface ToastApi {
  push: (kind: ToastKind, text: string, detail?: string) => void
  info: (text: string, detail?: string) => void
  success: (text: string, detail?: string) => void
  warn: (text: string, detail?: string) => void
  error: (text: string, detail?: string) => void
}

const ToastCtx = createContext<ToastApi | null>(null)

export function useToast(): ToastApi {
  const ctx = useContext(ToastCtx)
  if (!ctx) throw new Error('useToast 必须在 <ToastProvider> 内使用')
  return ctx
}

const KIND_STYLE: Record<ToastKind, string> = {
  info: 'status-info',
  success: 'status-success',
  warn: 'status-warn',
  error: 'status-danger',
}

const KIND_TEXT: Record<ToastKind, string> = {
  info: '提示',
  success: '完成',
  warn: '注意',
  error: '失败',
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const seq = useRef(0)

  const push = useCallback((kind: ToastKind, text: string, detail?: string) => {
    const id = ++seq.current
    setItems((prev) => [...prev, { id, kind, text, detail }])
    window.setTimeout(() => setItems((prev) => prev.filter((t) => t.id !== id)), 4000)
  }, [])

  const api = useMemo<ToastApi>(
    () => ({
      push,
      info: (t, d) => push('info', t, d),
      success: (t, d) => push('success', t, d),
      warn: (t, d) => push('warn', t, d),
      error: (t, d) => push('error', t, d),
    }),
    [push],
  )

  return (
    <ToastCtx.Provider value={api}>
      {children}
      <div
        className="fixed right-6 top-6 z-50 flex w-[360px] max-w-[calc(100vw-48px)] flex-col gap-2"
        role="region"
        aria-label="通知"
      >
        {items.map((t) => (
          <div key={t.id} className="toast items-start">
            <span className={cn(t.kind === 'success' ? 'status-success' : KIND_STYLE[t.kind], 'shrink-0')}>
              {KIND_TEXT[t.kind]}
            </span>
            <div className="min-w-0 flex-1">
              <div className="break-words">{t.text}</div>
              {t.detail && (
                <details className="mt-1">
                  <summary className="link text-caption">复制详情</summary>
                  <textarea
                    readOnly
                    className="input mt-2 h-20 resize-none py-2 text-caption"
                    value={t.detail}
                    onFocus={(e) => e.currentTarget.select()}
                  />
                </details>
              )}
            </div>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}
