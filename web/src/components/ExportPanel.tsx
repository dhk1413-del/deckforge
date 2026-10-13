import {useModalFocus} from '../hooks/useModalFocus'
import {useEffect,useState} from 'react'
import {createExport,listExports,previewExport,toEditable,SubmissionCancelled, type ExportPlan,type ExportRecord} from '../api'
import type {Slide} from '../types'
import {useToast} from './Toast'
import {useJobStream} from '../hooks/useJobStream'
import {ProgressPanel} from './ProgressPanel'

export function ExportPanel({projectId,slides}:{projectId:string;slides:Slide[]}) {
  const toast=useToast()
  const [kind,setKind]=useState<'image'|'native'>('image')
  const [selected,setSelected]=useState<number[]>([])
  const [scope,setScope]=useState<'all'|'selected'>('all')
  const [plan,setPlan]=useState<ExportPlan|null>(null)
  const [confirmed,setConfirmed]=useState(false)
  const [confirmationOpen,setConfirmationOpen]=useState(false)
  const [busy,setBusy]=useState(false)
  const [history,setHistory]=useState<ExportRecord[]>([])
  const [job,setJob]=useState<string|null>(null)
  const [error,setError]=useState('')
  const reload=()=>listExports(projectId).then(r=>setHistory(r.items)).catch(e=>setError(String(e)))
  const stream=useJobStream(job,{onDone:()=>{void reload()},onError:m=>toast.error('转换失败',m)})
  useEffect(()=>{void reload()},[projectId])
  useEffect(()=>{
    let active=true
    setPlan(null);setConfirmed(false);setConfirmationOpen(false);setError('')
    previewExport(projectId,kind,scope==='selected'?selected:undefined).then(p=>{if(active)setPlan(p)}).catch(e=>{if(active)setError(e.detail || String(e))})
    return()=>{active=false}
  },[projectId,slides,kind,scope,selected])
  const count=plan?.included.length || 0
  async function pack(){
    if(!plan)return
    setBusy(true)
    try{await createExport(projectId,plan);await reload();setConfirmed(false);toast.success('导出快照已保存，可下载')}
    catch(e){setError(e instanceof Error?e.message:String(e));setConfirmed(false);setPlan(await previewExport(projectId,kind,scope==='selected'?selected:undefined).catch(()=>null))}
    finally{setBusy(false)}
  }
  async function convert(){
    if(!plan)return
    setBusy(true)
    try{const result=await toEditable(projectId,plan.included.map(p=>p.page_no),'editppt',false);setJob(result.job_id)}
    catch(e){if(e instanceof SubmissionCancelled)toast.info('已取消，未提交');else toast.error('转换未提交',e instanceof Error?e.message:String(e))}
    finally{setBusy(false)}
  }
  return <div className="card">
    <h2 className="card-title">转换与导出</h2>
    {plan?.capabilities.map(c=><div key={c.kind} className="my-2"><button type="button" className="btn btn-secondary" disabled={busy || !c.available || (c.kind==='editable_hi' && (!confirmed || !count || stream.status==='running' || kind!=='image'))} onClick={()=>c.kind==='editable_hi'?void convert():setKind(c.kind as 'image'|'native')}>{c.label}{c.kind===kind?' · 已选':''}</button><p className="text-ink-sub">{c.reason}</p></div>)}
    <p>打包既有成果，不调用模型、不新增模型费用。转文字可编辑需另行报价确认，本机模型额度费用可能未知。</p>
    <div className="flex gap-3"><label><input type="radio" checked={scope==='all'} onChange={()=>setScope('all')}/> 全部参与页</label><label><input type="radio" checked={scope==='selected'} onChange={()=>setScope('selected')}/> 仅导出所选页</label></div>
    <div className="flex flex-wrap gap-3 my-3">{slides.filter(s=>s.keep).map(s=><label key={s.slide_id} className="num"><input type="checkbox" checked={selected.includes(s.page_no)} onChange={e=>{setScope('selected');setSelected(e.target.checked?[...selected,s.page_no]:selected.filter(n=>n!==s.page_no))}}/> 第 {s.page_no} 页 · 序号 {s.display_order}</label>)}</div>
    {error && <p role="alert">{error}</p>}
    {plan && <><p>{plan.note}</p><p className="num">将导出 {count} 页：</p><ul>{plan.included.map(p=><li className="num" key={p.slide_id}>第 {p.page_no} 页 · 展示序号 {p.display_order} · 当前版本 V{p.version_number}{p.content_stale || p.config_stale?' · 现有成果已过期，导出保留该版本':''}</li>)}</ul>{plan.excluded.length>0 && <><p>以下页面已排除：</p><ul>{plan.excluded.map(p=><li className="num" key={p.slide_id}>第 {p.page_no} 页 · 展示序号 {p.display_order}：{p.reason}</li>)}</ul></>}<label><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/> 已确认范围、当前版本及排除页面；导出即固定为导出时刻的版本快照</label></>}
    <div className="mt-3"><button type="button" className="btn btn-primary" disabled={busy || !confirmed || !count || !plan?.capabilities.find(c=>c.kind===kind)?.available} onClick={()=>setConfirmationOpen(true)}>{busy?'处理中…':`导出${scope==='selected'?'所选':'全部可用'} ${count} 页`}</button></div>
    {confirmationOpen && plan && <ExportConfirmation plan={plan} onClose={()=>setConfirmationOpen(false)} onConfirm={()=>{setConfirmationOpen(false);void pack()}}/>}
    {job && <ProgressPanel job={stream} stageLabel="转文字可编辑进度"/>}
    <h3 className="mt-4">已导出记录</h3>
    {history.map(r=><div key={r.id} className="my-2"><p className="num">{r.kind==='native'?'原生可编辑版':r.kind==='image'?'图片版':r.kind==='editable_hi'?'转文字可编辑':r.kind} · {r.pages} 页 · {r.created_at}</p><p className="num">{r.snapshot.length?r.snapshot.map(p=>`第 ${p.page_no} 页 / 序号 ${p.display_order} / V${p.version_number ?? '未知'}`).join('；'):'历史记录无版本快照，版本不可追溯'}</p>{r.file?<a className="btn btn-secondary" href={r.file} download>下载已固定产物</a>:<p>产物文件缺失，无法下载</p>}</div>)}
  </div>
}

function ExportConfirmation({plan,onClose,onConfirm}:{plan:ExportPlan;onClose:()=>void;onConfirm:()=>void}) {
  const ref=useModalFocus(onClose)
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
    <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label="确认导出版本快照" className="card max-h-[85vh] w-full max-w-xl overflow-auto" onClick={e=>e.stopPropagation()}>
      <h2>确认导出版本快照</h2><p>{plan.note}</p>
      <ul>{plan.included.map(p=><li key={p.slide_id} className="num">第 {p.page_no} 页 · 序号 {p.display_order} · V{p.version_number}{p.content_stale || p.config_stale?' · 已过期':''}</li>)}</ul>
      {plan.excluded.length>0 && <><p>排除页面：</p><ul>{plan.excluded.map(p=><li key={p.slide_id} className="num">第 {p.page_no} 页：{p.reason}</li>)}</ul></>}
      <p>仅打包既有成果，不新增模型费用；内容或版本发生变化时需重新确认。</p>
      <div className="flex gap-3"><button type="button" className="btn btn-secondary" onClick={onClose}>返回</button><button type="button" className="btn btn-primary" onClick={onConfirm}>确认导出 {plan.included.length} 页</button></div>
    </div>
  </div>
}
