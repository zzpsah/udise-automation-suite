"use client";
import { useEffect, useMemo, useState } from "react";

type Stage={id:string;label:string;mode:"read"|"write";classes:string[];requires_class:boolean;description:string;preview_enabled?:boolean};
type Caps={classes:{id:string;label:string}[];stages:Stage[]};
type JobState={job:{id:string;status:string;stage:string;class_name?:string;progress_current:number;progress_total:number;message:string;has_result:boolean;error?:string};events:{id:number;message:string;level:string}[]};

const HERMES_FLOW_REFERENCE: Record<string,string> = {
  students: "Phase 1 · Validate session and fetch the current roster",
  snapshot: "Read-only audit · Students, GP, EP, Facility, Completion and Issues",
  gp: "Phase 3 · Fresh GP read → blank-only proposal → approval → save → read-back",
  ep: "Phase 4 · Fresh GP/EP/FP read → admission and subject proposal → approval → read-back",
  facility: "Phase 4 · Fresh profile read → blank-only facility proposal → approval → read-back",
  completion: "Phase 5 · Read current GP, EP, Facility and final completion status",
  finalize: "Phase 5 · Fresh status read → status 3 eligibility → one approved submission → status 6 read-back",
};
const LOGIN_REFERENCE = "Phase 1 · Secure session and roster access";
const STAGE_META: Record<string,{icon:string;short:string;fills:string[]}> = {
  students: {icon:"P1",short:"Export the current masked roster",fills:["Read-only","Masked Aadhaar"]},
  snapshot: {icon:"RA",short:"Export a full read-only audit workbook",fills:["Students + GP + EP + Facility","Completion + Issues"]},
  gp: {icon:"P3",short:"Review proposed blank-only GP values",fills:["Mother tongue","BPL / EWS / CWSN","Nationality","Blood group"]},
  ep: {icon:"P4",short:"Review admission, language and subject values",fills:["eShikshaKosh admission number","Languages and subjects","Previous-year exam status"]},
  facility: {icon:"P4",short:"Review proposed blank-only Facility values",fills:["Height and weight","Distance","Parent education","Facility Yes / No fields"]},
  completion: {icon:"P5",short:"Export the current stage status",fills:["GP / EP / Facility status","Pending and completed records"]},
  finalize: {icon:"P5",short:"Review records eligible for Complete Data",fills:["Fresh status 3 only","Proposed transition to status 6"]},
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
  const [eshikshaToken,setEshikshaToken]=useState("");
  const [eshikshaUrl,setEshikshaUrl]=useState("");
  const [eshikshaReady,setEshikshaReady]=useState(false);
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
    setMsg("Creating a secure session link…");
    const r=await fetch("/api/session-request",{method:"POST"});
    const d=await r.json();
    if(!r.ok){setMsg(d.error||"Could not create secure session link");return}
    setSessionToken(d.token);setEntryUrl(d.entry_url);
    setMsg("Paste the UDISE Cookie header in the secure panel.");
  }

  useEffect(()=>{
    if(!sessionToken || sessionId) return;
    const t=setInterval(async()=>{
      const r=await fetch("/api/session-status?token="+encodeURIComponent(sessionToken),{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      if(d.ready && d.session_id){setSessionId(d.session_id);setEntryUrl("");setMsg("UDISE session connected. Choose a workflow to continue.");clearInterval(t)}
    },2000);
    return ()=>clearInterval(t);
  },[sessionToken,sessionId]);

  async function connectEshiksha(){
    setMsg("Preparing secure eShikshaKosh sign-in…");
    const r=await fetch("/api/eshiksha-request",{method:"POST"});
    const d=await r.json();
    if(!r.ok){setMsg(d.error||"Could not create the secure eShikshaKosh sign-in");return}
    setEshikshaToken(d.token);setEshikshaUrl(d.entry_url);
    setMsg("Enter the eShikshaKosh details in the secure panel.");
  }

  useEffect(()=>{
    if(!eshikshaToken || eshikshaReady) return;
    const t=setInterval(async()=>{
      const r=await fetch("/api/eshiksha-status?token="+encodeURIComponent(eshikshaToken),{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      if(d.ready){setEshikshaReady(true);setEshikshaUrl("");setMsg("eShikshaKosh is connected. The EP preview is ready to run.");clearInterval(t)}
    },2000);
    return ()=>clearInterval(t);
  },[eshikshaToken,eshikshaReady]);

  async function startJob(){
    if(!sessionId){setMsg("Connect a secure UDISE session first.");return}
    if(!school.trim()){setMsg("Enter the school URL or 7-digit internal ID.");return}
    if(selected?.id==="ep"&&!eshikshaReady){await connectEshiksha();return}
    setMsg("Preparing the workflow…");setJob(null);setJobId("");
    const r=await fetch("/api/jobs",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({
      session_id:sessionId,school:school.trim(),stage,class_name:selected?.requires_class?klass:null,preview:true
    })});
    const d=await r.json();
    if(!r.ok){setMsg(d.detail||d.error||"Job start failed");return}
    setJobId(d.job_id);setMsg("Workflow started.");
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
    <div className="hero"><div><span className="eyebrow">HERMES VPS</span><h1>UDISE Operations Console</h1></div><span className="privacy-pill">Private · Tailnet</span></div>
    <div className="workspace">
      <div className="controls">
        <section className="card setup-card">
          <div className="section-title"><span className="step">1</span><div><h2>Connect school</h2><p>{LOGIN_REFERENCE}</p></div></div>
          <div className="setup-row">
            <input aria-label="School URL or internal ID" value={school} onChange={e=>setSchool(e.target.value)} placeholder="School URL or 7-digit internal ID"/>
            <button onClick={connectSession}>{sessionId?"Reconnect":"Connect UDISE"}</button>
            {sessionId&&<span className="badge ok">● Ready</span>}
            {!sessionId&&sessionToken&&<span className="badge">Waiting…</span>}
          </div>
        </section>

        <section className="card stage-card">
          <div className="section-heading"><div className="section-title"><span className="step">2</span><div><h2>Choose workflow</h2><p>Phases 1–5 · Preview before any change</p></div></div><span className="stage-count">{readyCount+previewCount} workflows</span></div>
          <div className="grid">{caps?.stages.map(s=>{
            const meta=STAGE_META[s.id]||{icon:"--",short:s.description,fills:[]};
            return <button type="button" aria-pressed={stage===s.id} key={s.id} className={"choice "+(stage===s.id?"active ":"")+(s.mode==="write"?"previewable":"ready")} onClick={()=>setStage(s.id)}>
              <span className="stage-icon" aria-hidden="true">{meta.icon}</span>
              <span className="stage-copy"><strong>{s.label}</strong><small>{meta.short}</small></span>
              <span className={"badge "+(s.mode==="write"?"preview":"ok")}>{s.mode==="write"?"Preview":"Ready"}</span>
            </button>})}</div>

          {selected&&<div className={"selected-stage "+(selected.mode==="write"?"is-locked":"is-ready")}>
            <div className="selected-stage-head"><span aria-hidden="true">{selectedMeta?.icon||"--"}</span><div><strong>{selected.label}</strong><small>{HERMES_FLOW_REFERENCE[selected.id]}</small></div></div>
            <div className="fill-chips">{selectedMeta?.fills.map(item=><span key={item}>{item}</span>)}</div>
            {selected.id==="ep"&&<div className={"source-status "+(eshikshaReady?"ready":"needed")}>{eshikshaReady?"● eShikshaKosh source ready":"○ eShikshaKosh sign-in required"}</div>}
            {selected.mode==="write"?<div className="lock-reason"><div><strong>Preview enabled · Portal save protected</strong><span>This run produces an Excel proposal only. A portal write requires separate explicit approval and must be followed by a fresh matching read-back.{selected.id==="ep"?" The workbook also includes the masked eShikshaKosh source report.":""}</span></div></div>:<p>{selected.description}</p>}
          </div>}

          <div className="run-row">
            {selected?.requires_class&&<div className="class-picker"><label>Class</label><select value={klass} onChange={e=>setKlass(e.target.value)}>
              {selected.classes.map(c=><option value={c} key={c}>{caps?.classes.find(x=>x.id===c)?.label||c}</option>)}
            </select></div>}
            <button className="run-button" disabled={selected?.mode==="write"&&!selected.preview_enabled} onClick={startJob}>{selected?.id==="ep"&&!eshikshaReady?"Connect eShikshaKosh":selected?.mode==="write"?"Generate preview":"Run report"}</button>
          </div>
        </section>
      </div>

      <aside className="card output-card">
        <div className="output-title"><div><span className="eyebrow">ACTIVITY &amp; RESULT</span><h2>{job?"Workflow progress":"Ready to begin"}</h2></div>{job&&<span className="badge">{job.job.status}</span>}</div>
        {!job&&<div className="empty-output"><span className="status-mark">STATUS</span><strong>{msg||"Connect UDISE and choose a workflow."}</strong><p>Progress and downloadable results will appear here.</p></div>}
        {job&&<div className="job-output">
          <div className="friendly-message">{job.job.message||msg}</div>
          {job.job.progress_total>0&&<><div className="progress"><div style={{width:pct+"%"}}/></div><p className="progress-copy"><strong>{pct}%</strong><span>{job.job.progress_current}/{job.job.progress_total} students</span></p></>}
          <ul className="events">{job.events.slice(-6).map(e=><li key={e.id}><b>{e.level==="error"?"Error":"Update"}</b> · {e.message}</li>)}</ul>
          {job.job.has_result&&<a className="download" href={"/api/jobs/"+job.job.id+"/result"}>Download Excel workbook</a>}
          {job.job.error&&<div className="error-box"><strong>Workflow stopped</strong><span>{job.job.error}</span></div>}
        </div>}
      </aside>
    </div>
    {entryUrl&&!sessionId&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Secure UDISE session">
      <div className="session-modal">
        <div className="modal-head"><div><span className="eyebrow">SECURE SESSION</span><h2>Connect UDISE securely</h2></div><button className="modal-close" onClick={()=>setEntryUrl("")} aria-label="Close">×</button></div>
        <p>Paste the browser Cookie header below. It goes directly to protected Oracle runtime storage and is never shown in chat or job output.</p>
        <iframe title="Secure UDISE Cookie entry" src={entryUrl}/>
      </div>
    </div>}
    {eshikshaUrl&&!eshikshaReady&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Secure eShikshaKosh login">
      <div className="session-modal">
        <div className="modal-head"><div><span className="eyebrow">READ-ONLY SOURCE</span><h2>Connect eShikshaKosh</h2></div><button className="modal-close" onClick={()=>setEshikshaUrl("")} aria-label="Close">×</button></div>
        <p>Credentials are used once for the read-only EP source fetch. The password is deleted when the preview starts; the masked report remains available for 24 hours.</p>
        <iframe title="Secure eShikshaKosh login" src={eshikshaUrl}/>
      </div>
    </div>}
  </main>
}
