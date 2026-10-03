"use client";
import { useEffect, useMemo, useState } from "react";

type Stage={id:string;label:string;mode:"read"|"write";classes:string[];requires_class:boolean;description:string};
type Caps={classes:{id:string;label:string}[];stages:Stage[]};
type JobState={job:{id:string;status:string;stage:string;class_name?:string;progress_current:number;progress_total:number;message:string;has_result:boolean;error?:string};events:{id:number;message:string;level:string}[]};

const HERMES_REFERENCE: Record<string,string> = {
  students: "Hermes VPS · udise-vps students · udise_vps/students.py",
  gp: "Hermes VPS · udise-vps gp · udise_vps/general_profile.py",
  ep: "Hermes VPS · udise-vps ep · udise_vps/ep.py",
  facility: "Hermes VPS · udise-vps facility · udise_vps/facility.py",
  completion: "Hermes VPS · udise-vps completion · udise_vps/completion.py",
  finalize: "Hermes VPS · udise-vps finalize · udise_vps/finalize.py",
};
const LOGIN_REFERENCE = "Hermes VPS · secure runtime session · control_api/app.py";

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
  useEffect(()=>{
    if(selected?.requires_class && !selected.classes.includes(klass)) setKlass(selected.classes[0]||"");
  },[selected,klass]);

  async function connectSession(){
    setMsg("Creating secure UDISE session link…");
    const r=await fetch("/api/session-request",{method:"POST"});
    const d=await r.json();
    if(!r.ok){setMsg(d.error||"Could not create secure session link");return}
    setSessionToken(d.token);setEntryUrl(d.entry_url);
    setMsg("Secure session page opened. Paste UDISE Cookie there, then return here.");
    window.open(d.entry_url,"_blank","noopener,noreferrer");
  }

  useEffect(()=>{
    if(!sessionToken || sessionId) return;
    const t=setInterval(async()=>{
      const r=await fetch("/api/session-status?token="+encodeURIComponent(sessionToken),{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      if(d.ready && d.session_id){setSessionId(d.session_id);setMsg("UDISE session connected.");clearInterval(t)}
    },2000);
    return ()=>clearInterval(t);
  },[sessionToken,sessionId]);

  async function startJob(){
    if(!sessionId){setMsg("Pehle UDISE session connect karein.");return}
    if(!school.trim()){setMsg("School internal ID ya school URL enter karein.");return}
    setMsg("Job queue ho raha hai…");setJob(null);setJobId("");
    const r=await fetch("/api/jobs",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({
      session_id:sessionId,school:school.trim(),stage,class_name:selected?.requires_class?klass:null,preview:true
    })});
    const d=await r.json();
    if(!r.ok){setMsg(d.detail||d.error||"Job start failed");return}
    setJobId(d.job_id);setMsg("Job started.");
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
    <div className="hero"><h1>UDISE Automation</h1><p className="muted">Class-wise, stage-wise school automation with readable progress.</p></div>

    <div className="card">
      <h2>1. School & session</h2>
      <p className="muted">Reference: {LOGIN_REFERENCE}</p>
      <label>School URL or 7-digit internal ID</label>
      <input value={school} onChange={e=>setSchool(e.target.value)} placeholder="School URL or internal ID"/>
      <div style={{height:14}}/>
      <div className="row">
        <button onClick={connectSession}>{sessionId?"Reconnect UDISE session":"Connect UDISE session"}</button>
        {sessionId&&<span className="badge ok">Session connected</span>}
        {!sessionId&&sessionToken&&<span className="badge">Waiting for secure session</span>}
      </div>
      {entryUrl&&!sessionId&&<p><a href={entryUrl} target="_blank" rel="noreferrer">Secure session page dubara kholen</a></p>}
    </div>

    <div className="card">
      <h2>2. Stage choose karein</h2>
      <div className="grid">{caps?.stages.map(s=><button key={s.id} className={"choice "+(stage===s.id?"active":"")} onClick={()=>setStage(s.id)}>
        <div className="stage-title"><strong>{s.label}</strong><span className={"badge "+(s.mode==="write"?"warn":"ok")}>{s.mode==="write"?"Write":"Read"}</span></div>
        <div className="muted" style={{marginTop:7,fontSize:13}}>{s.description}</div>
        {HERMES_REFERENCE[s.id]&&<div className="muted" style={{marginTop:7,fontSize:12}}>Runner reference: {HERMES_REFERENCE[s.id]}</div>}
      </button>)}</div>

      {selected?.requires_class&&<><label>Class</label><select value={klass} onChange={e=>setKlass(e.target.value)}>
        {selected.classes.map(c=><option value={c} key={c}>{caps?.classes.find(x=>x.id===c)?.label||c}</option>)}
      </select></>}

      {selected?.mode==="write"&&<p className="badge warn">Write stage visible hai, lekin read-only MVP me execution disabled hai. Preview/approval workflow next layer me enable hoga.</p>}
      <div style={{height:14}}/>
      <button disabled={selected?.mode!=="read"} onClick={startJob}>Run {selected?.label}</button>
    </div>

    {msg&&<div className="card"><strong>Status:</strong> {msg}</div>}

    {job&&<div className="card">
      <div className="row"><h2 style={{margin:0}}>3. Progress</h2><span className="badge">{job.job.status}</span></div>
      <p>{job.job.message}</p>
      {job.job.progress_total>0&&<><div className="progress"><div style={{width:pct+"%"}}/></div><p className="muted">{job.job.progress_current}/{job.job.progress_total} · {pct}%</p></>}
      <ul className="events">{job.events.slice(-12).map(e=><li key={e.id}>{e.level==="error"?"❌":"•"} {e.message}</li>)}</ul>
      {job.job.has_result&&<p><a href={"/api/jobs/"+job.job.id+"/result"}><button>Download Excel result</button></a></p>}
      {job.job.error&&<p className="warn badge">Error: {job.job.error}</p>}
    </div>}
  </main>
}
