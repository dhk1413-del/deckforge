/** 任务进度流：SSE 订阅 /api/jobs/{id}/stream，逐页显示进度 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { getJob, openJobStream } from '../api'
import type { JobProgressEvent } from '../types'

export interface JobState {
  status: 'idle' | 'running' | 'done' | 'error' | 'cancelled' | 'interrupted'
  total: number
  /** 最近一条事件对应的页序号（本次任务内第几页） */
  page: number
  message: string
  /** 各页最近一次进度事件（键为页号） */
  byPage: Record<number, JobProgressEvent>
  /** 已达终态的页（done / failed）——进度条的分母分子用它算，running 事件不会虚增进度 */
  settled: Record<number, 'done' | 'failed'>
  /** 后端事件里报告过的「已完成页数」最大值：skill 引擎走任务级 done 而不是逐页 status 事件 */
  progressDone: number
  /** 事件流水（按到达顺序，最新在后） */
  events: JobProgressEvent[]
  /** 订阅开始 / 结束的时刻，用于显示「已用 / 预计」 */
  startedAt: number | null
  finishedAt: number | null
  error: string | null
  /** 连接层失败次数（后端没起 / 中途断流） */
  transportErrors: number
}

const EMPTY: JobState = {
  status: 'idle',
  total: 0,
  page: 0,
  message: '',
  byPage: {},
  settled: {},
  progressDone: 0,
  events: [],
  startedAt: null,
  finishedAt: null,
  error: null,
  transportErrors: 0,
}

export function useJobStream(
  jobId: string | null,
  handlers: { onDone?: (deckId?: string) => void; onError?: (message: string) => void; onCancelled?: (message: string) => void } = {},
) {
  const [state, setState] = useState<JobState>(EMPTY)
  const currentTask = useRef(jobId)
  currentTask.current = jobId
  const handlersRef = useRef(handlers)
  useEffect(() => {
    handlersRef.current = handlers
  }, [handlers])

  useEffect(() => {
    if (!jobId) {
      setState(EMPTY)
      return
    }
    setState({ ...EMPTY, status: 'running', startedAt: Date.now(), message: '已提交任务，等待后端返回进度…' })
    let active = true
    let version = -1
    const accept = (evt: {job_id?:string; version?:number}) => {
      if (!active || currentTask.current !== jobId || (evt.job_id && evt.job_id !== jobId) || (evt.version !== undefined && evt.version < version)) return false
      version = evt.version ?? version
      return true
    }
    const recover = async () => {
      try {
        const snapshot = await getJob(jobId)
        if (!accept({job_id:snapshot.id,version:snapshot.version})) return
        const byPage = JSON.parse(snapshot.pages_json || '{}') as Record<number,JobProgressEvent>
        setState(prev => ({...prev, total:snapshot.total, byPage,
          settled:Object.fromEntries(Object.values(byPage).filter(e=>['done','failed'].includes(e.status)).map(e=>[e.page,e.status as 'done'|'failed'])),
          progressDone:snapshot.done, status:snapshot.status==='done'?'done':snapshot.status==='failed'?'error':snapshot.status==='cancelled'?'cancelled':snapshot.status==='interrupted'?'interrupted':'running',
          message:snapshot.message, error:snapshot.status==='failed'?snapshot.message:null, finishedAt:['done','failed','cancelled','interrupted'].includes(snapshot.status)?Date.parse(snapshot.updated_at || '') || Date.now():null, transportErrors:0}))
      } catch { /* keep last confirmed state */ }
    }
    void recover()
    const poll = window.setInterval(()=>void recover(),5000)
    window.addEventListener('focus', recover)
    const close = openJobStream(jobId, {
      onProgress: (evt) => {
        if (!accept(evt)) return
        const at = Date.now()
        setState((prev) => {
          const final = evt.status === 'done' || evt.status === 'failed'
          return {
            ...prev,
            status: prev.status === 'done' || prev.status === 'error' || prev.status === 'cancelled' || prev.status === 'interrupted' ? prev.status : 'running',
            startedAt: prev.startedAt ?? at,
            total: evt.total || prev.total,
            page: evt.page,
            message: evt.message || prev.message,
            byPage: { ...prev.byPage, [evt.page]: evt },
            settled: final ? { ...prev.settled, [evt.page]: evt.status as 'done' | 'failed' } : prev.settled,
            progressDone: Math.max(prev.progressDone, Number(evt.done) || 0),
            events: [...prev.events, evt].slice(-300),
          }
        })
      },
      onDone: (evt) => {
        if (!accept(evt as {job_id?:string;version?:number})) return
        void recover()
        setState((prev) => ({ ...prev, status: 'done', finishedAt: Date.now(), message: '任务处理结束，结果以服务端逐页状态为准' }))
        handlersRef.current.onDone?.(evt.deck_id)
      },
      onInterrupted: (evt) => {
        if (!accept(evt)) return
        setState(prev=>({...prev,status:'interrupted',finishedAt:Date.now(),message:evt.message,error:null,transportErrors:0}))
        void recover()
      },
      onCancelled: (evt) => {
        if (!accept(evt as {job_id?:string;version?:number})) return
        setState((prev) => ({ ...prev, status: 'cancelled', finishedAt: Date.now(), message: evt.message, error: null }))
        handlersRef.current.onCancelled?.(evt.message)
      },
      onError: (evt) => {
        if (!accept(evt as {job_id?:string;version?:number})) return
        setState((prev) => ({
          ...prev,
          status: 'error',
          finishedAt: Date.now(),
          error: evt.message,
          message: evt.message,
        }))
        handlersRef.current.onError?.(evt.message)
      },
      onTransportError: () => {
        if (!active || currentTask.current !== jobId) return
        void recover()
        setState((prev) =>
          ['done', 'error', 'cancelled', 'interrupted'].includes(prev.status)
            ? prev
            : {
                ...prev,
                transportErrors: prev.transportErrors + 1,
                message: '连接中断，正在恢复状态',
              },
        )
      },
    })
    return () => {active=false;window.clearInterval(poll); close();window.removeEventListener('focus',recover)}
  }, [jobId])

  const reset = useCallback(() => setState(EMPTY), [])
  return { ...state, reset }
}
