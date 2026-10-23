import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { BellRing, Check, EyeOff, RotateCcw, Sparkles, Users, Utensils, Waves } from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8100";
type State = "available_clean" | "occupied" | "attention_due" | "vacated_needs_cleaning" | "cleaning" | "out_of_service";
type Table = {id:string;label:string;seats:number;zone_x:number;zone_y:number;state:State;elapsed_minutes:number;assigned_server:string|null;last_confidence:number};
type Alert = {id:number;table_id:string;alert_type:string;priority:string;message:string;status:string;created_at:string;acknowledged_by:string|null};
type Snapshot = {tables:Table[];alerts:Alert[];metrics:Record<string,number>};
const labels:Record<State,string>={available_clean:"Ready",occupied:"Dining",attention_due:"Check guests",vacated_needs_cleaning:"Clean table",cleaning:"Cleaning",out_of_service:"Offline"};

function App(){
  const [data,setData]=useState<Snapshot>({tables:[],alerts:[],metrics:{available:0,occupied:0,attention_due:0,needs_cleaning:0}});
  const [selected,setSelected]=useState<string>("T1"); const [error,setError]=useState(""); const [busy,setBusy]=useState(false);
  const load=async()=>{try{const r=await fetch(`${API}/api/floor`);if(!r.ok)throw new Error();setData(await r.json());setError("");}catch{setError("API unavailable on port 8100");}};
  useEffect(()=>{load();const timer=setInterval(load,3000);return()=>clearInterval(timer);},[]);
  const act=async(path:string,body?:object)=>{setBusy(true);await fetch(`${API}${path}`,{method:"POST",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});await load();setBusy(false);};
  const chosen=useMemo(()=>data.tables.find(t=>t.id===selected),[data,selected]);
  return <div className="app">
    <aside><div className="brand"><Waves/><div><strong>MidaPulse</strong><span>Live floor intelligence</span></div></div><nav><button className="active"><Utensils/>Dining room</button><button><BellRing/>Service alerts <b>{data.alerts.length}</b></button></nav><div className="privacy"><EyeOff/><div><strong>Privacy mode</strong><span>No faces. No stored video.</span></div></div></aside>
    <main><header><div><p className="eyebrow">Dinner service · Live</p><h1>Dining room pulse</h1></div><div className="actions"><button onClick={()=>act("/api/demo/reset")}><RotateCcw/>Reset</button><button className="primary" onClick={()=>act("/api/demo/step")} disabled={busy}><Sparkles/>Advance demo</button></div></header>
    {error&&<div className="error">{error}</div>}
    <section className="metrics"><div><span>Available</span><strong>{data.metrics.available||0}</strong></div><div><span>Occupied</span><strong>{data.metrics.occupied||0}</strong></div><div><span>Attention due</span><strong>{data.metrics.attention_due||0}</strong></div><div><span>Needs cleaning</span><strong>{data.metrics.needs_cleaning||0}</strong></div></section>
    <div className="grid"><section className="floor"><div className="section-title"><div><p className="eyebrow">Camera 01 · Anonymous zones</p><h2>Floor map</h2></div><span className="live"><i/>Live</span></div><div className="map"><div className="bar">SERVICE COUNTER</div>{data.tables.map(t=><button key={t.id} style={{left:`${t.zone_x}%`,top:`${t.zone_y}%`}} className={`table ${t.state} ${selected===t.id?"selected":""}`} onClick={()=>setSelected(t.id)}><strong>{t.label}</strong><span>{labels[t.state]}</span>{t.elapsed_minutes>0&&<small>{t.elapsed_minutes} min</small>}<em><Users/> {t.seats}</em></button>)}</div></section>
    <section className="right"><div className="section-title"><div><p className="eyebrow">Action queue</p><h2>Staff alerts</h2></div></div>{data.alerts.length===0?<p className="empty">No open alerts. The floor is moving normally.</p>:data.alerts.map(a=><article className={`alert ${a.priority}`} key={a.id}><div><strong>{a.table_id} · {a.alert_type.replaceAll("_"," ")}</strong><p>{a.message}</p></div><button title="Acknowledge" onClick={()=>act(`/api/alerts/${a.id}/acknowledge`,{server:"Sara"})}><Check/></button></article>)}
    {chosen&&<div className="table-detail"><p className="eyebrow">Selected table</p><h2>{chosen.label}</h2><dl><div><dt>Status</dt><dd>{labels[chosen.state]}</dd></div><div><dt>Server</dt><dd>{chosen.assigned_server||"Unassigned"}</dd></div><div><dt>Vision confidence</dt><dd>{Math.round(chosen.last_confidence*100)}%</dd></div></dl>{chosen.state==="vacated_needs_cleaning"&&<button className="primary wide" onClick={()=>act(`/api/tables/${chosen.id}/cleaning`,{staff:"Nora",action:"complete"})}>Mark clean</button>}</div>}
    </section></div></main></div>
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
