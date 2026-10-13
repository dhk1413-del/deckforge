/** 健康探测：挂载即拉一次，之后每 20s 轮询（供应商状态要能自己变） */
import { useEffect } from 'react'
import { getHealth } from '../api'
import { useAsync } from './useAsync'

export function useHealth(pollMs = 20_000) {
  const state = useAsync(getHealth, [])
  const { reload } = state
  useEffect(() => {
    const id = window.setInterval(reload, pollMs)
    return () => window.clearInterval(id)
  }, [reload, pollMs])
  return state
}
