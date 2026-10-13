import {useEffect, useRef} from 'react'

/** 圈定模态焦点；仅挂载时移动，翻页/异步更新不抢焦点。 */
export function useModalFocus(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const controls = () => Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]')).filter(el => el.getClientRects().length > 0)
    ;(controls()[0] || dialog).focus()
    const keydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {event.preventDefault(); event.stopPropagation(); close.current(); return}
      if (event.key !== 'Tab') return
      const nodes = controls()
      const first = nodes[0], last = nodes[nodes.length - 1]
      if (!first) {event.preventDefault(); dialog.focus(); return}
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {event.preventDefault(); last.focus()}
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog)) {event.preventDefault(); first.focus()}
    }
    const focusin = (event: FocusEvent) => {
      if (!dialog.contains(event.target as Node)) (controls()[0] || dialog).focus()
    }
    dialog.addEventListener('keydown', keydown)
    document.addEventListener('focusin', focusin)
    return () => {
      dialog.removeEventListener('keydown', keydown)
      document.removeEventListener('focusin', focusin)
      if (trigger?.isConnected) trigger.focus()
    }
  }, [])
  return ref
}
