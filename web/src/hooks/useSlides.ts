/** 页面清单（slides）：生成/转可编辑期间自动轮询刷新 */
import { useEffect } from 'react'
import { getSlides } from '../api'
import { useAsync } from './useAsync'

export function useSlides(projectId: string | null, polling = false) {
  const state = useAsync(() => getSlides(projectId ?? ''), [projectId], !!projectId)
  const { reload } = state

  useEffect(() => {
    if (!polling || !projectId) return
    const id = window.setInterval(reload, 3000)
    return () => window.clearInterval(id)
  }, [polling, projectId, reload])

  return state
}
