/** 通用异步状态：加载 / 空 / 错误三态 + 手动重试（避免每页重复写 useEffect） */
import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../api'

export interface AsyncState<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
  reload: () => void
  setData: (v: T | null) => void
}

export function toApiError(e: unknown): ApiError {
  if (e instanceof ApiError) return e
  if (e instanceof Error) return new ApiError(e.message, 0)
  return new ApiError(String(e), 0)
}

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
  enabled = true,
): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(enabled)
  const [error, setError] = useState<ApiError | null>(null)
  const [tick, setTick] = useState(0)

  const fnRef = useRef(fn)
  useEffect(() => {
    fnRef.current = fn
  }, [fn])

  useEffect(() => {
    if (!enabled) {
      setLoading(false)
      return
    }
    let alive = true
    setLoading(true)
    setError(null)
    fnRef
      .current()
      .then((d) => {
        if (!alive) return
        setData(d)
        setLoading(false)
      })
      .catch((e: unknown) => {
        if (!alive) return
        setError(toApiError(e))
        setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, tick, ...deps])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, loading, error, reload, setData }
}
