"use client";
import { useEffect, useMemo, useState } from "react";

type Stage={id:string;label:string;mode:"read"|"write";classes:string[];requires_class:boolean;description:string;preview_enabled?:boolean};
type Caps={classes:{id:string;label:string}[];stages:Stage[]};
type JobState={job:{id:string;status:string;stage:string;class_name?:string;progress_current:number;progress_total:number;message:string;has_result:boolean;error?:string};events:{id:number;message:string;level:string}[]};

const HERMES_FLOW_REFERENCE: Record<string,string> = {
  students: "Phase 1 · Session · Fetch the roster",
  snapshot: "Read-only audit · Students + GP + EP + Facility + Completion + Issues",
  gp: "Phase 3 · General Profile · fresh read → blank-only preview → read-back",
  ep: "Phase 4 · Enrolment & Facility · per-student loop",
  facility: "Phase 4 · Enrolment & Facility · blank-only fill and read-back",
  completion: "Phase 5 · Complete Data · fresh status overview",
  finalize: "Phase 5 · Complete Data · eligible status 3 only",
};
const LOGIN_REFERENCE = "Hermes VPS flow · Phase 1 · Secure session";
const STAGE_META: Record<string,{icon:string;short:string;fills:string[]}> = {
  students: {icon:"👥",short:"Student list Excel",fills:["Read only","Masked Aadhaar"]},
  snapshot: {icon:"📊",short:"Sabhi stages ka Excel",fills:["GP + EP + Facility","Issues sheet"]},
  gp: {icon:"🪪",short:"Basic profile details",fills:["Mother tongue","BPL / EWS / CWSN","Nationality","Blood group"]},
  ep: {icon:"📚",short:"Admission & subjects",fills:["eShiksha admission no.","Languages & subjects","Exam status"]},
  facility: {icon:"🎒",short:"Facilities & benefits",fills:["Height & weight","Distance","Parent education","Yes / No fields"]},
  completion: {icon:"✅",short:"Kaam kitna complete hai",fills:["Current status","Pending stages"]},
  finalize: {icon:"🏁",short:"Final Complete Data",fills:["Eligible status 3 only","Proposed status 6"]},
};

export default function Page(){
  const [authed,setAuthed]=useState<boolean|null>(null);
  const [code,setCode]=useState("");
  const [caps,setCaps]=useState<Caps|null>(null);
  const [school,setSchool]=useState("");
  const [klass,setKlass]=useState("IX");
  const [stage,setStage]=useState("completion");
  const [sessionToken,setSessionToken]=useState("");
  const [sessionId,setSessionId]=useState("");
  const [entryUrl,setEntryUrl]=useState("");
  const [jobId,setJobId]=useState("");
  const [job,setJob]=useState<JobState|null>(null);
  const [msg,setMsg]=useState("");

  async function loadCaps(){
    const r=await fetch("/api/capabilities",{cache:"no-store"});
    if(r.status===401){setAuthed(false);return}
    if(!r.ok){setMsg("Capabilities load failed");return}
    setCaps(await r.json());setAuthed(true);
  }
  useEffect(()=>{loadCaps()},[]);

  async function login(){
    setMsg("");
    const r=await fetch("/api/login",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({code})});
    if(!r.ok){setMsg("Access code incorrect");return}
    setCode("");await loadCaps();
  }

  const selected=useMemo(()=>caps?.stages.find(x=>x.id===stage),[caps,stage]);
  const selectedMeta=selected?STAGE_META[selected.id]:undefined;
  const readyCount=caps?.stages.filter(x=>x.mode==="read").length||0;
  const previewCount=caps?.stages.filter(x=>x.mode==="write"&&x.preview_enabled).length||0;
  useEffect(()=>{
    if(selected?.requires_class && !selected.classes.includes(klass)) setKlass(selected.classes[0]||"");
  },[selected,klass]);

  async function connectSession(){
    setMsg("Secure session link bana raha hoon…");
    const r=await fetch("/api/session-request",{method:"POST"});
    const d=await r.json();
    if(!r.ok){setMsg(d.error||"Could not create secure session link");return}
    setSessionToken(d.token);setEntryUrl(d.entry_url);
    setMsg("Neeche secure box mein Cookie paste karein.");
  }

  useEffect(()=>{
    if(!sessionToken || sessionId) return;
    const t=setInterval(async()=>{
      const r=await fetch("/api/session-status?token="+encodeURIComponent(sessionToken),{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      if(d.ready && d.session_id){setSessionId(d.session_id);setEntryUrl("");setMsg("Session ready hai. Ab stage chala sakte hain.");clearInterval(t)}
    },2000);
    return ()=>clearInterval(t);
  },[sessionToken,sessionId]);

  async function startJob(){
    if(!sessionId){setMsg("Pehle secure UDISE session connect karein.");return}
    if(!school.trim()){setMsg("School ID ya URL daaliye.");return}
    setMsg("Kaam taiyar ho raha hai…");setJob(null);setJobId("");
    const r=await fetch("/api/jobs",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({
      session_id:sessionId,school:school.trim(),stage,class_name:selected?.requires_class?klass:null,preview:true
    })});
    const d=await r.json();
    if(!r.ok){setMsg(d.detail||d.error||"Job start failed");return}
    setJobId(d.job_id);setMsg("Kaam shuru ho gaya.");
  }

  useEffect(()=>{
    if(!jobId) return;
    const poll=async()=>{
      const r=await fetch("/api/jobs/"+jobId,{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();setJob(d);
      if(["completed","failed"].includes(d.job.status)) clearInterval(timer);
    };
    const timer=setInterval(poll,1800);poll();
    return ()=>clearInterval(timer);
  },[jobId]);

  if(authed===null) return <main><div className="card">Loading…</div></main>;
  if(!authed) return <main><div className="login card"><h1>UDISE Automation</h1><p className="muted">Authorized access only.</p>
    <label>Access code</label><input value={code} onChange={e=>setCode(e.target.value)} type="password" onKeyDown={e=>e.key==="Enter"&&login()}/>
    <div style={{height:12}}/><button onClick={login}>Sign in</button>{msg&&<p>{msg}</p>}</div></main>;

  const pct=job?.job.progress_total?Math.min(100,Math.round(job.job.progress_current*100/job.job.progress_total)):0;
  return <main>
    <div className="hero"><div><span className="eyebrow">HERMES VPS</span><h1>UDISE Automation</h1></div><span className="privacy-pill">🔐 Private trial</span></div>
    <div className="workspace">
      <div className="controls">
        <section className="card setup-card">
          <div className="section-title"><span className="step">1</span><div><h2>School connect karein</h2><p>{LOGIN_REFERENCE}</p></div></div>
          <div className="setup-row">
            <input aria-label="School URL or internal ID" value={school} onChange={e=>setSchool(e.target.value)} placeholder="School URL ya 7-digit ID"/>
            <button onClick={connectSession}>{sessionId?"Reconnect":"Connect session"}</button>
            {sessionId&&<span className="badge ok">● Ready</span>}
            {!sessionId&&sessionToken&&<span className="badge">Waiting…</span>}
          </div>
        </section>

        <section className="card stage-card">
          <div className="section-heading"><div className="section-title"><span className="step">2</span><div><h2>Kaam chuniye</h2><p>Stage par tap karein</p></div></div><span className="stage-count">{readyCount+previewCount} available</span></div>
          <div className="grid">{caps?.stages.map(s=>{
            const meta=STAGE_META[s.id]||{icon:"📄",short:s.description,fills:[]};
            return <button type="button" aria-pressed={stage===s.id} key={s.id} className={"choice "+(stage===s.id?"active ":"")+(s.mode==="write"?"previewable":"ready")} onClick={()=>setStage(s.id)}>
              <span className="stage-icon" aria-hidden="true">{meta.icon}</span>
              <span className="stage-copy"><strong>{s.label}</strong><small>{meta.short}</small></span>
              <span className={"badge "+(s.mode==="write"?"preview":"ok")}>{s.mode==="write"?"Preview":"Ready"}</span>
            </button>})}</div>

          {selected&&<div className={"selected-stage "+(selected.mode==="write"?"is-locked":"is-ready")}>
            <div className="selected-stage-head"><span aria-hidden="true">{selectedMeta?.icon||"📄"}</span><div><strong>{selected.label}</strong><small>{HERMES_FLOW_REFERENCE[selected.id]}</small></div></div>
            <div className="fill-chips">{selectedMeta?.fills.map(item=><span key={item}>{item}</span>)}</div>
            {selected.mode==="write"?<div className="lock-reason"><span aria-hidden="true">👁️</span><div><strong>Preview enabled—save abhi locked</strong><span>Excel verify karne ke baad hi <b>Approval → Save → Read-back</b> hoga.{selected.id==="ep"?" eShikshaKosh source bhi isi temporary workbook mein milega.":""}</span></div></div>:<p>{selected.description}</p>}
          </div>}

          <div className="run-row">
            {selected?.requires_class&&<div className="class-picker"><label>Class</label><select value={klass} onChange={e=>setKlass(e.target.value)}>
              {selected.classes.map(c=><option value={c} key={c}>{caps?.classes.find(x=>x.id===c)?.label||c}</option>)}
            </select></div>}
            <button className="run-button" disabled={selected?.mode==="write"&&!selected.preview_enabled} onClick={startJob}>{selected?.mode==="write"?"Preview Excel":"Run now"}</button>
          </div>
        </section>
      </div>

      <aside className="card output-card">
        <div className="output-title"><div><span className="eyebrow">LIVE OUTPUT</span><h2>{job?"Kaam ki progress":"Ready when you are"}</h2></div>{job&&<span className="badge">{job.job.status}</span>}</div>
        {!job&&<div className="empty-output"><span>✨</span><strong>{msg||"School connect karke stage chuniye."}</strong><p>Progress aur Excel result yahin dikhega.</p></div>}
        {job&&<div className="job-output">
          <div className="friendly-message">{job.job.message||msg}</div>
          {job.job.progress_total>0&&<><div className="progress"><div style={{width:pct+"%"}}/></div><p className="progress-copy"><strong>{pct}%</strong><span>{job.job.progress_current}/{job.job.progress_total} students</span></p></>}
          <ul className="events">{job.events.slice(-6).map(e=><li key={e.id}>{e.level==="error"?"❌":"✓"} {e.message}</li>)}</ul>
          {job.job.has_result&&<a className="download" href={"/api/jobs/"+job.job.id+"/result"}>⬇ Download Excel</a>}
          {job.job.error&&<div className="error-box"><strong>Kaam ruk gaya</strong><span>{job.job.error}</span></div>}
        </div>}
      </aside>
    </div>
    {entryUrl&&!sessionId&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Secure UDISE session">
      <div className="session-modal">
        <div className="modal-head"><div><span className="eyebrow">SECURE SESSION</span><h2>UDISE Cookie paste karein</h2></div><button className="modal-close" onClick={()=>setEntryUrl("")} aria-label="Close">×</button></div>
        <p>Cookie direct Oracle ke temporary secure storage mein jayegi—chat ya page output mein nahi dikhegi.</p>
        <iframe title="Secure UDISE Cookie entry" src={entryUrl}/>
      </div>
    </div>}
  </main>
}
