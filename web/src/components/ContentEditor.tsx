import { useEffect, useRef, useState } from 'react'
import { configureProject, getSlides, retrySlideOutline, saveSlideContent, type ApiError } from '../api'
import type { Slide, ContentModule } from '../types'
import { finishPendingSaves, registerLeaveGuard } from '../router'

// This self-hosted application has no account system. Keep installation-local drafts isolated.
const draftKey = (pid: string, sid: string) => `deckforge:draft:local-account:${pid}:${sid}`
const editable = (s: Slide) => ({title:s.title, outline:s.outline || '', points:s.points || [], modules:s.modules || [], source_note:s.source_note || ''})
export function ContentEditor({projectId, onConfirmed, onExclude, onSaveState}: {projectId:string; onConfirmed:()=>void; onExclude:(no:number)=>Promise<void>; onSaveState:(state:string)=>void}) {
  const [rows, setRows] = useState<Slide[]>([])
  const current = useRef<Slide[]>([])
  const [states, setStates] = useState<Record<string,string>>({})
  const dirty = useRef(new Set<string>())
  const queue = useRef<Promise<boolean>>(Promise.resolve(true))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [serverRows,setServerRows] = useState<Record<string,Slide>>({})
  const conflicts=useRef<Record<string,number>>({})
  const active = useRef(true)
  useEffect(()=>{const values=Object.values(states);onSaveState(values.includes('保存失败')?'保存失败':values.includes('正在保存')?'正在保存':values.includes('未保存')?'未保存':'已保存')},[states,onSaveState])
  const publish = (next: Slide[]) => {current.current=next; if(active.current) setRows(next)}
  useEffect(() => {
    active.current=true
    getSlides(projectId).then(items => {
      setServerRows(Object.fromEntries(items.map(s=>[s.slide_id,s])))
      const next=items.filter(s=>s.keep).map(s=>{
        const raw=localStorage.getItem(draftKey(projectId,s.slide_id))
        if(raw) {try {const draft=JSON.parse(raw); dirty.current.add(s.slide_id); if(draft.revision !== s.content_revision) conflicts.current[s.slide_id]=s.content_revision || 1; return {...s,...draft.content,content_revision:draft.revision}} catch { /* retain unusable draft for recovery */ }}
        return s
      })
      publish(next)
      setStates(Object.fromEntries(next.map(s=>[s.slide_id,dirty.current.has(s.slide_id)?'未保存':'已保存'])))
    }).catch(e=>setError((e as ApiError).detail))
    const refresh=async()=>{try{const items=await getSlides(projectId);if(!active.current)return
      setServerRows(Object.fromEntries(items.map(s=>[s.slide_id,s])))
      publish(current.current.map(local=>{const remote=items.find(s=>s.slide_id===local.slide_id);if(!remote)return local
        if(dirty.current.has(local.slide_id)){if(remote.content_revision!==local.content_revision){conflicts.current[local.slide_id]=remote.content_revision || 1;setStates(prev=>({...prev,[local.slide_id]:'保存失败'}))}return {...local,status:remote.status}}
        return remote}))
    }catch(e){setError((e as ApiError).detail)}}
    window.addEventListener('focus',refresh)
    const unload=(e:BeforeUnloadEvent)=>{if(dirty.current.size){e.preventDefault();e.returnValue=''}}
    window.addEventListener('beforeunload',unload)
    const unregister=registerLeaveGuard(async()=>!dirty.current.size || await flush())
    return ()=>{active.current=false; window.removeEventListener('focus',refresh); window.removeEventListener('beforeunload',unload);unregister();void flush()}
  },[projectId])
  function change(id:string, patch:Partial<Slide>) {
    const next=current.current.map(s=>s.slide_id===id?{...s,...patch}:s)
    publish(next);dirty.current.add(id)
    const s=next.find(s=>s.slide_id===id)!
    localStorage.setItem(draftKey(projectId,id),JSON.stringify({revision:s.content_revision,content:editable(s)}))
    setStates(prev=>({...prev,[id]:'未保存'}))
  }
  function flush():Promise<boolean> {
    const pending=queue.current.then(async()=>{
      while(dirty.current.size) {
      for(const id of [...dirty.current]) {
        const s=current.current.find(s=>s.slide_id===id)
        if(!s) {dirty.current.delete(id);continue}
        if(conflicts.current[id]) {setError('服务器内容已更新，请先比较并选择版本');return false}
        const content=editable(s), snapshot=JSON.stringify(content)
        if(active.current) setStates(prev=>({...prev,[id]:'正在保存'}))
        try {
          const saved=await saveSlideContent(projectId,id,{...content,revision:s.content_revision || 1})
          const latest=current.current.find(s=>s.slide_id===id)!
          const unchanged=JSON.stringify(editable(latest))===snapshot
          publish(current.current.map(row=>row.slide_id===id?{...saved,...(unchanged?{}:editable(latest))}:row))
          if(unchanged){dirty.current.delete(id);localStorage.removeItem(draftKey(projectId,id))}
          else localStorage.setItem(draftKey(projectId,id),JSON.stringify({revision:saved.content_revision,content:editable(latest)}))
          if(active.current) setStates(prev=>({...prev,[id]:unchanged?'已保存':'未保存'}))
        } catch(e) {if((e as ApiError).status===409){const items=await getSlides(projectId);const remote=items.find(row=>row.slide_id===id);if(remote){conflicts.current[id]=remote.content_revision || 1;setServerRows(prev=>({...prev,[id]:remote}))}}if(active.current){setStates(prev=>({...prev,[id]:'保存失败'}));setError((e as ApiError).detail)}return false}
      }
      }
      return true
    })
    queue.current=pending.catch(()=>false)
    return pending
  }
  useEffect(()=>{const timer=window.setTimeout(()=>{if(dirty.current.size)void flush()},700);return()=>window.clearTimeout(timer)},[rows])
  async function confirm() {
    setBusy(true);setError('')
    try {if(!await finishPendingSaves()){setError('请先保存当前草稿，再确认内容');return}
      await configureProject(projectId,{confirm_content:true});onConfirmed()
    }catch(e){setError((e as ApiError).detail)}finally{setBusy(false)}
  }
  function moduleChange(s:Slide,index:number,patch:Partial<ContentModule>) {
    change(s.slide_id,{modules:(s.modules||[]).map((m,i)=>i===index?{...m,...patch}:m)})
  }
  const ready=rows.length>0&&rows.every(s=>s.title.trim()&&((s.outline||'').trim()||(s.points||[]).some(p=>p.trim())||(s.modules||[]).some(m=>m.text?.trim()||m.cells?.some(line=>line.some(c=>c!==null&&String(c).trim())))))
  return <div className="card"><h2 className="card-title">内容确认</h2>
    <p>请核对标题、要点、模块及数据来源。空值与「待统计」保持原样，不能作为 0。保存内容不会重新生成图片。</p>
    {error&&<p role="alert" className="text-danger">{error}</p>}
    {rows.map(s=><fieldset disabled={s.status==='running'||s.status==='queued'} title={s.status==='running'||s.status==='queued'?'页面任务运行中，暂不能修改内容或配置':undefined} key={s.slide_id} className="border-t border-divider py-4" onBlur={()=>void flush()}>
      {(s.status==='running'||s.status==='queued')&&<p>页面任务运行中，暂不能修改内容或配置；已有结果仍可查看。</p>}
      <div className="flex gap-3 items-center"><span className="num">第 {s.page_no} 页</span><span role="status">{states[s.slide_id]||'已保存'}</span>
        {(!s.title.trim()||!((s.outline||'').trim()||(s.points||[]).some(p=>p.trim())||(s.modules||[]).some(m=>m.text?.trim()||m.cells?.some(line=>line.some(c=>c!==null&&String(c).trim())))))&&<span>待补齐</span>}
        {conflicts.current[s.slide_id]&&<button className="btn btn-secondary" onClick={()=>{publish(current.current.map(row=>row.slide_id===s.slide_id?{...row,content_revision:conflicts.current[s.slide_id]}:row));delete conflicts.current[s.slide_id];void flush()}}>服务器内容已变更：采用保留草稿并保存</button>}
        {conflicts.current[s.slide_id]&&<>
          <button className="btn btn-secondary" onClick={()=>{const remote=serverRows[s.slide_id];if(!remote)return;dirty.current.delete(s.slide_id);delete conflicts.current[s.slide_id];localStorage.removeItem(draftKey(projectId,s.slide_id));publish(current.current.map(row=>row.slide_id===s.slide_id?remote:row));setStates(prev=>({...prev,[s.slide_id]:'已保存'}))}}>采用服务器版本</button>
          <button className="btn btn-secondary" onClick={()=>{const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(editable(s),null,2)],{type:'application/json'}));a.download=`内容草稿-${s.page_no}.json`;a.click();URL.revokeObjectURL(a.href)}}>保留草稿副本</button>
          <details><summary>查看差异（本地 / 服务器）</summary><pre className="whitespace-pre-wrap">{JSON.stringify({本地:editable(s),服务器:serverRows[s.slide_id]?editable(serverRows[s.slide_id]):'请重新聚焦以读取'},null,2)}</pre></details>
        </>}
        {s.content_stale&&<span>内容已更新，当前结果基于旧内容</span>}
        <button className="btn btn-secondary" onClick={()=>void flush()}>保存 / 重试保存</button>
        <button className="btn btn-secondary" disabled={busy} onClick={async()=>{setBusy(true);try{if(await flush()){const row=current.current.find(x=>x.slide_id===s.slide_id)!;const saved=await retrySlideOutline(projectId,s.slide_id,row.content_revision||1);publish(current.current.map(x=>x.slide_id===s.slide_id?saved:x))}}catch(e){setError((e as ApiError).detail)}finally{setBusy(false)}}}>仅重试此页梳理</button>
        <button className="btn btn-secondary" onClick={async()=>{try{if(await flush()){await onExclude(s.page_no);publish(current.current.filter(x=>x.slide_id!==s.slide_id))}}catch(e){setError((e as ApiError).detail)}}}>排除此页</button>
      </div>
      <label className="block mt-3">标题<input className="input w-full" value={s.title} onChange={e=>change(s.slide_id,{title:e.target.value})}/></label>
      <label className="block mt-3">内容大纲<textarea className="input w-full" value={s.outline||''} onChange={e=>change(s.slide_id,{outline:e.target.value})}/></label>
      <label className="block mt-3">要点（每行一条，保留单位与年份）<textarea className="input w-full" rows={4} value={(s.points||[]).join('\n')} onChange={e=>change(s.slide_id,{points:e.target.value.split('\n')})}/></label>
      <label className="block mt-3">数据来源 / 原文备注<textarea className="input w-full" value={s.source_note||''} onChange={e=>change(s.slide_id,{source_note:e.target.value})}/></label>
      {(s.modules||[]).map((m,i)=><div key={i} className="mt-3">
        <label>模块名称<input className="input" value={m.title||''} onChange={e=>moduleChange(s,i,{title:e.target.value})}/></label>
        {m.cells?<><label>单位<input className="input" value={m.unit||''} onChange={e=>moduleChange(s,i,{unit:e.target.value})}/></label><div className="overflow-x-auto"><table className="ledger"><tbody>{m.cells.map((row,r)=><tr key={r}>{row.map((cell,c)=><td key={c}><input className="input num" aria-label={`第 ${r+1} 行 ${c+1} 列`} value={cell ?? ''} onChange={e=>moduleChange(s,i,{cells:m.cells!.map((line,ri)=>line.map((value,ci)=>ri===r&&ci===c?e.target.value:value))})}/></td>)}</tr>)}</tbody></table></div>
          <button className="btn btn-secondary" onClick={()=>moduleChange(s,i,{cells:[...m.cells!,Array(m.cells![0]?.length||1).fill('')]})}>添加行</button>
          <button className="btn btn-secondary" onClick={()=>moduleChange(s,i,{cells:m.cells!.map(row=>[...row,''])})}>添加列</button>
          <button className="btn btn-secondary" onClick={()=>moduleChange(s,i,{cells:m.cells!.slice(0,-1)})}>删除末行</button>
          <button className="btn btn-secondary" onClick={()=>moduleChange(s,i,{cells:m.cells!.map(row=>row.slice(0,-1))})}>删除末列</button>
        </>:<textarea className="input w-full" value={m.text||''} onChange={e=>moduleChange(s,i,{text:e.target.value})}/>}
      </div>)}
      <button className="btn btn-secondary mt-3" onClick={()=>change(s.slide_id,{modules:[...(s.modules||[]),{type:'table',title:'',unit:'',cells:[['']]}]})}>添加表格</button>
    </fieldset>)}
    <button className="btn btn-primary" disabled={!ready||busy} onClick={confirm}>{busy?'正在保存与确认…':ready?'已人工核对，确认内容并继续':'所选页面内容待补齐'}</button>
  </div>
}
