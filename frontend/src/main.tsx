import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BellRing,
  Check,
  EyeOff,
  RotateCcw,
  Sparkles,
  Users,
  Utensils,
} from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8100";

type State = "available_clean" | "occupied" | "attention_due" | "vacated_needs_cleaning" | "cleaning" | "out_of_service";
type Table = {id:string;label:string;seats:number;zone_x:number;zone_y:number;state:State;elapsed_minutes:number;attention_after_minutes:number;assigned_server:string|null;last_confidence:number};
type Alert = {id:number;table_id:string;alert_type:string;priority:string;message:string;status:string;created_at:string;acknowledged_by:string|null};
type Snapshot = {tables:Table[];alerts:Alert[];metrics:Record<string,number>};

const labels:Record<State,string>={available_clean:"Ready",occupied:"Dining",attention_due:"Check guests",vacated_needs_cleaning:"Clean table",cleaning:"Cleaning",out_of_service:"Offline"};

function App(){
  const [data,setData]=useState<Snapshot>({tables:[],alerts:[],metrics:{available:0,occupied:0,attention_due:0,needs_cleaning:0}});
  const [selected,setSelected]=useState("T1");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [now,setNow]=useState(new Date());
  const [alertFilter,setAlertFilter]=useState<"all"|"urgent">("all");
  const load=async()=>{try{const r=await fetch(`${API}/api/floor`);if(!r.ok)throw new Error();setData(await r.json());setError("");}catch{setError("API unavailable on port 8100");}};
  useEffect(()=>{load();const timer=setInterval(load,3000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{const timer=setInterval(()=>setNow(new Date()),1000);return()=>clearInterval(timer);},[]);
  const act=async(path:string,body?:object)=>{setBusy(true);await fetch(`${API}${path}`,{method:"POST",headers:{"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});await load();setBusy(false);};
  const chosen=useMemo(()=>data.tables.find(t=>t.id===selected),[data,selected]);
  const shownAlerts=alertFilter==="urgent"?data.alerts.filter(a=>a.priority==="high"):data.alerts;
  const occupancy=Math.round(((data.metrics.occupied||0)/Math.max(data.tables.length,1))*100);
  const tempo=occupancy>=75?"Peak":occupancy>=45?"Building":"Calm";
  const selectedProgress=chosen?Math.min(100,(chosen.elapsed_minutes/Math.max(chosen.attention_after_minutes,1))*100):0;

  return <div className="app">
    <header className="topbar">
      <div className="brand"><span className="brand-mark"><Activity/></span><div><strong>MidaPulse</strong><span>Floor operations</span></div></div>
      <div className="service-mode"><i/>Dinner service <span>{now.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"})}</span></div>
      <nav><button className="active"><Utensils/>Floor</button><button><BellRing/>Dispatch <b>{data.alerts.length}</b></button></nav>
      <div className="actions"><button title="Reset demo" onClick={()=>act("/api/demo/reset")}><RotateCcw/><span>Reset</span></button><button className="primary" onClick={()=>act("/api/demo/step")} disabled={busy}><Sparkles/>Advance</button></div>
    </header>

    <main className="cockpit">
      {error&&<div className="error">{error}</div>}
      <section className="service-ribbon">
        <div className="ribbon-title"><div><p className="eyebrow">Live room status</p><h1>Dinner floor</h1></div><div className="tempo"><span>{tempo} - {occupancy}%</span><i><b style={{width:`${occupancy}%`}}/></i></div></div>
        <div className="metric available"><span>Ready</span><strong>{data.metrics.available||0}</strong><small>Open tables</small></div>
        <div className="metric occupied"><span>Dining</span><strong>{data.metrics.occupied||0}</strong><small>Active tables</small></div>
        <div className="metric attention"><span>Attention</span><strong>{data.metrics.attention_due||0}</strong><small>Server check</small></div>
        <div className="metric cleaning"><span>Turnover</span><strong>{data.metrics.needs_cleaning||0}</strong><small>Needs cleaning</small></div>
      </section>

      <div className="workspace">
        <section className="floor-stage">
          <div className="stage-heading"><div><p className="eyebrow">Anonymous occupancy zones</p><h2>Live floor plan</h2></div><div className="stage-tools"><div className="room-signal" title="Live room signal">{data.tables.map(t=><i key={t.id} className={t.state} style={{height:`${Math.max(18,Math.round(t.last_confidence*100))}%`}}/>)}<span>Signal</span></div><div className="legend"><span><i className="ready"/>Ready</span><span><i className="dining"/>Dining</span><span><i className="attention"/>Attention</span><span><i className="clean"/>Clean</span></div></div></div>
          <div className="map"><svg className="service-routes" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><path d="M50 10 V48 H15 V72"/><path d="M50 48 H48 V74"/><path d="M50 48 H77 V72"/></svg><div className="scan-line"/><div className="zone-label window">Window</div><div className="zone-label center">Main room</div><div className="zone-label lounge">Lounge</div><div className="bar"><span>Pass</span><strong>Service counter</strong><span>Pickup</span></div>{data.tables.map((t,index)=><button key={t.id} style={{left:`${t.zone_x}%`,top:`${t.zone_y}%`,"--delay":`${index*70}ms`,"--confidence":`${Math.round(t.last_confidence*100)}%`} as React.CSSProperties} className={`table ${t.state} ${selected===t.id?"selected":""}`} onClick={()=>setSelected(t.id)}><span className="table-number">{t.label.replace("Table ","")}</span><strong>{t.label}</strong><span>{labels[t.state]}</span>{t.elapsed_minutes>0&&<small>{t.elapsed_minutes} min</small>}<span className="seats" aria-hidden="true">{Array.from({length:Math.min(t.seats,6)},(_,seat)=><i key={seat}/>)}</span><span className="confidence"/><em><Users/> {t.seats}</em></button>)}</div>
        </section>

        <aside className="dispatch">
          <section className="queue"><div className="dispatch-heading"><div><p className="eyebrow">Dispatch feed</p><h2>Needs action</h2></div><span className="queue-count">{data.alerts.length}</span></div><div className="queue-filter"><button className={alertFilter==="all"?"active":""} onClick={()=>setAlertFilter("all")}>All</button><button className={alertFilter==="urgent"?"active":""} onClick={()=>setAlertFilter("urgent")}>Urgent</button></div>{shownAlerts.length===0?<p className="empty">No alerts in this view.</p>:shownAlerts.map((a,index)=><article className={`alert ${a.priority}`} style={{"--delay":`${index*90}ms`} as React.CSSProperties} key={a.id}><span className="alert-symbol">{a.alert_type==="cleaning"?<Sparkles/>:<BellRing/>}</span><div className="alert-meta"><span>{a.priority}</span><time>Live</time></div><strong>{a.table_id} - {a.alert_type.replaceAll("_"," ")}</strong><p>{a.message}</p><button title="Acknowledge alert" aria-label="Acknowledge alert" onClick={()=>act(`/api/alerts/${a.id}/acknowledge`,{server:"Sara"})}><Check/>Acknowledge</button></article>)}</section>
          {chosen&&<section className="inspector" key={chosen.id}><div className="inspector-number">{chosen.label.replace("Table ","")}</div><div className="inspector-title"><div><p className="eyebrow">On the floor</p><h2>{chosen.label}</h2></div><span className={`state-pill ${chosen.state}`}>{labels[chosen.state]}</span></div><div className="inspector-visual"><div className="service-dial"><svg viewBox="0 0 44 44" aria-hidden="true"><circle className="dial-track" cx="22" cy="22" r="18"/><circle className="dial-value" cx="22" cy="22" r="18" pathLength="100" style={{strokeDasharray:`${selectedProgress} 100`}}/></svg><strong>{chosen.elapsed_minutes}</strong><span>min</span></div><div className="server-visual"><span>{chosen.assigned_server?.slice(0,1)||"?"}</span><div><small>Assigned</small><strong>{chosen.assigned_server||"Unassigned"}</strong></div></div></div><dl><div><dt>Status</dt><dd>{labels[chosen.state]}</dd></div><div><dt>Vision confidence</dt><dd>{Math.round(chosen.last_confidence*100)}%</dd></div></dl><div className="service-window"><div><span>Service window</span><b>{chosen.attention_after_minutes} min</b></div><i><b style={{width:`${selectedProgress}%`}}/></i></div>{chosen.state==="vacated_needs_cleaning"&&<button className="primary wide" onClick={()=>act(`/api/tables/${chosen.id}/cleaning`,{staff:"Nora",action:"complete"})}>Mark clean</button>}</section>}
          <div className="privacy"><EyeOff/><div><strong>Anonymous by design</strong><span>No faces or stored video.</span></div></div>
        </aside>
      </div>
    </main>
  </div>
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
