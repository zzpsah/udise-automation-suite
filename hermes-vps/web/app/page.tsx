"use client";
import { useEffect, useMemo, useState } from "react";

type Stage={id:string;label:string;mode:"read"|"write";classes:string[];requires_class:boolean;description:string;preview_enabled?:boolean;approval_enabled?:boolean};
type SchoolPreset={internal_id:string;udise_code:string;name:string};
type Caps={classes:{id:string;label:string}[];stages:Stage[];school_presets?:SchoolPreset[]};
type JobState={job:{id:string;status:string;stage:string;class_name?:string;preview:number;approved_from?:string;max_submissions?:number;progress_current:number;progress_total:number;message:string;has_result:boolean;auto_write_job_id?:string;error?:string};events:{id:number;message:string;level:string}[]};
type EshikshaPreview={ready:boolean;source:string;school_name:string;udise:string;total:number;class_counts:Record<string,number>;preview_limit:number;rows:Array<Record<string,string>>};

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

function clientFailure(component:string, operation:string, detail:string):string {
  const clean=String(detail||"Unknown error").replace(/\\s+/g," ").trim().slice(0,700);
  return `FAILURE · Component: ${component} · Operation: ${operation} · Detail: ${clean}`;
}
const WORKFLOW_INFO: Record<string,{title:string;steps:string[]}> = {
  students:{title:"Student roster",steps:["Read current UDISE student roster","Mask Aadhaar in output","Generate downloadable Excel","No portal data is changed"]},
  snapshot:{title:"Full read snapshot",steps:["Read Students, GP, EP, Facility and Completion","Collect issues in a separate sheet","Generate one audit workbook","No portal data is changed"]},
  gp:{title:"General Profile",steps:["Read current GP values","Fill only eligible blank fields","Save eligible changes","Read back and verify the save"]},
  ep:{title:"Enrollment Profile",steps:["Read current UDISE profile","Fetch required source from eShikshaKosh","Prepare eligible EP values","Save and verify with fresh read-back"]},
  facility:{title:"Facility Profile",steps:["Read current Facility values","Fill only eligible blank fields","Save changes","Read back and verify each saved record"]},
  completion:{title:"Completion overview",steps:["Read GP, EP and Facility completion state","Calculate current student status","Generate downloadable report","No portal data is changed"]},
  finalize:{title:"Complete Data",steps:["Read fresh completion status","Use only currently eligible records","Submit Complete Data","Read back and verify completed status"]},
};
const STAGE_META: Record<string,{icon:string;short:string;fills:string[]}> = {
  students: {icon:"P1",short:"Export the current masked roster",fills:["Read-only","Masked Aadhaar"]},
  snapshot: {icon:"RA",short:"Export a full read-only audit workbook with class-wise pending counts",fills:["Class IX / X / XI / XII student totals","GP pending: blank eligible fields by class","EP pending: admission, language and subject gaps by class","Facility pending: blank measurements and Yes/No fields by class","Completion status and Issues sheets; read-only, no portal changes"]},
  gp: {icon:"P3",short:"Blank fields only; existing values are never overwritten",fills:["4.1.12 Mother Tongue → Hindi (42) or Bhojpuri (28)","Blood Group → Under Investigation (9)","4.1.14 BPL → No (2)","4.1.15 AAY → Not Applicable (9) when BPL is No","4.1.16 EWS → No (2)","4.1.17 CWSN → No (2); existing Yes is manual review","4.1.18 Indian National → Yes (1)","4.1.19 Out-of-School-Child → No (2)"]},
  ep: {icon:"P4",short:"Blank EP fields only; existing values are never overwritten",fills:["4.2.1 Admission No. → matched eShikshaKosh value, then Roll No. fallback","No match/ambiguous → temporary 0001, 0002… sequence shown for Excel review","4.2.9 language pair → Urdu/HIN or Hindi/Sanskrit by minority status","Subjects 3–6 → Mathematics 401, Science 402, Social Science 404, English 612","Invalid previous-year result → None / Not Studying with null dependent fields","Class XI stream → eShikshaKosh stream when the portal permits it"]},
  facility: {icon:"P4",short:"Blank facility fields only; existing values are never overwritten",fills:["Boys: Height → 150–170 cm; Weight → 42–60 kg","Girls: lower range → 146–166 cm; Weight → 38–56 kg","4.3.6 Distance → seeded 1–3 km or 3–5 km","Parent education → Secondary","Blank Yes/No facility fields → No"]},
  completion: {icon:"P5",short:"Export the current stage status",fills:["GP / EP / Facility status","Pending and completed records"]},
  finalize: {icon:"P5",short:"Review records eligible for Complete Data",fills:["Fresh status 3 only","Proposed transition to status 6"]},
};

export default function Page(){
  const [caps,setCaps]=useState<Caps|null>(null);
  const [school,setSchool]=useState("");
  const [klass,setKlass]=useState("IX");
  const [stage,setStage]=useState("completion");
  const [sessionId,setSessionId]=useState("");
  const [sessionSchoolName,setSessionSchoolName]=useState("");
  const [sessionUdiseCode,setSessionUdiseCode]=useState("");
  const [sessionExpiresAt,setSessionExpiresAt]=useState(0);
  const [sessionSeconds,setSessionSeconds]=useState(0);
  const [sessionToken,setSessionToken]=useState("");
  const [entryUrl,setEntryUrl]=useState("");
  const [loginToken,setLoginToken]=useState("");
  const [username,setUsername]=useState("");
  const [password,setPassword]=useState("");
  const [showPassword,setShowPassword]=useState(false);
  const [captcha,setCaptcha]=useState("");
  const [captchaNonce,setCaptchaNonce]=useState(0);
  const [loginBusy,setLoginBusy]=useState(false);
  const [eshikshaToken,setEshikshaToken]=useState("");
  const [eshikshaUrl,setEshikshaUrl]=useState("");
  const [eshikshaReady,setEshikshaReady]=useState(false);
  const [eshikshaReportReady,setEshikshaReportReady]=useState(false);
  const [eshikshaPreview,setEshikshaPreview]=useState<EshikshaPreview|null>(null);
  const [eshikshaFile,setEshikshaFile]=useState<File|null>(null);
  const [eshikshaUdise,setEshikshaUdise]=useState("");
  const [eshikshaPassword,setEshikshaPassword]=useState("");
  const [showEshikshaPassword,setShowEshikshaPassword]=useState(false);
  const [eshikshaYear,setEshikshaYear]=useState("2026-27");
  const [eshikshaSchoolName,setEshikshaSchoolName]=useState("");
  const [eshikshaConnectedUdise,setEshikshaConnectedUdise]=useState("");
  const [jobId,setJobId]=useState("");
  const [job,setJob]=useState<JobState|null>(null);
  const [infoStage,setInfoStage]=useState<string|null>(null);
  const [msg,setMsg]=useState("");
  const [saveLimit,setSaveLimit]=useState(1);
  const [cwsnConfirmBusy,setCwsnConfirmBusy]=useState(false);

  async function loadCaps(){
    const r=await fetch("/api/capabilities",{cache:"no-store"});
    if(!r.ok){setMsg("Capabilities load failed");return}
    const data:Caps=await r.json();
    setCaps(data);
    if(data.school_presets?.length) setSchool(current=>current||data.school_presets![0].internal_id);
  }
  useEffect(()=>{loadCaps()},[]);

  const selected=useMemo(()=>caps?.stages.find(x=>x.id===stage),[caps,stage]);
  const selectedMeta=selected?STAGE_META[selected.id]:undefined;
  const readyCount=caps?.stages.filter(x=>x.mode==="read").length||0;
  const previewCount=caps?.stages.filter(x=>x.mode==="write"&&x.preview_enabled).length||0;
  useEffect(()=>{
    if(selected?.requires_class && !selected.classes.includes(klass)) setStage("completion");
  },[selected,klass]);

  async function beginUdiseLogin(){
    setLoginBusy(true);
    setCaptcha("");
    setMsg("Loading UDISE CAPTCHA…");
    const r=await fetch("/api/udise-login/start",{method:"POST"});
    const d=await r.json();
    if(!r.ok){setLoginBusy(false);setMsg(d.error||d.detail||"Could not start UDISE login");return}
    setLoginToken(d.token);
    setCaptchaNonce(Date.now());
    setLoginBusy(false);
    setMsg("");
  }

  async function submitUdiseLogin(){
    if(!loginToken){await beginUdiseLogin();return}
    if(!username.trim()||!password||!captcha.trim()){setMsg("Enter username, password and CAPTCHA.");return}
    setLoginBusy(true);
    setMsg("Signing in to UDISE…");
    const r=await fetch("/api/udise-login/submit",{
      method:"POST",
      headers:{"content-type":"application/json"},
      body:JSON.stringify({token:loginToken,username:username.trim(),password,captcha:captcha.trim()})
    });
    const d=await r.json();
    setLoginBusy(false);
    if(!r.ok){
      const errorMessage=d.detail||d.error||"UDISE login failed";
      setPassword("");
      setCaptcha("");
      await beginUdiseLogin();
      setMsg(errorMessage);
      return;
    }
    setSessionId(d.session_id);
    if(d.school_id) setSchool(String(d.school_id));
    setSessionSchoolName(String(d.school_name||""));
    setSessionUdiseCode(String(d.udise_code||""));
    const expiresAt=Date.now()+Number(d.expires_in||0)*1000;
    setSessionExpiresAt(expiresAt);
    setSessionSeconds(Math.max(0,Math.floor((expiresAt-Date.now())/1000)));
    setPassword("");
    setCaptcha("");
    setMsg(d.school_id?"Students Module connected. Select class and workflow.":"UDISE connected, but Students Module school scope could not be resolved.");
  }

  useEffect(()=>{beginUdiseLogin()},[]);
  useEffect(()=>{
    if(!sessionId){setSessionSeconds(0);return}
    let cancelled=false;
    const verify=async(refresh=false)=>{
      const r=await fetch(`/api/session-status-live?session_id=${encodeURIComponent(sessionId)}&refresh=${refresh?"1":"0"}`,{cache:"no-store"});
      if(!r.ok){
        if(!cancelled){setSessionId("");setMsg("UDISE portal session expired. Sign in again.")}
        return;
      }
      const d=await r.json();
      if(!cancelled){
        const seconds=Number(d.expires_in||0);
        setSessionSeconds(seconds);
        setSessionExpiresAt(Date.now()+seconds*1000);
      }
    };
    verify(true);
    const heartbeat=setInterval(()=>{if(document.visibilityState==="visible") verify(true)},4*60*1000);
    const tick=setInterval(()=>setSessionSeconds(v=>Math.max(0,v-1)),1000);
    return ()=>{cancelled=true;clearInterval(heartbeat);clearInterval(tick)};
  },[sessionId]);

  async function connectExistingSession(){
    setMsg("Creating secure browser-session link…");
    const r=await fetch("/api/session-request",{method:"POST"});
    const d=await r.json();
    if(!r.ok){setMsg(d.error||d.detail||"Could not create browser-session link");return}
    setSessionToken(d.token);
    setEntryUrl(d.entry_url);
    setMsg("Use the secure fallback panel to connect your existing UDISE browser session.");
  }

  useEffect(()=>{
    if(!sessionToken||sessionId) return;
    const t=setInterval(async()=>{
      const r=await fetch("/api/session-status?token="+encodeURIComponent(sessionToken),{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      if(d.ready&&d.session_id){
        setSessionId(d.session_id);setEntryUrl("");setMsg("UDISE session connected.");clearInterval(t)
      }
    },1800);
    return ()=>clearInterval(t);
  },[sessionToken,sessionId]);

  async function connectEshiksha(){
    setMsg("Preparing secure eShikshaKosh sign-in…");
    setEshikshaReady(false);setEshikshaReportReady(false);setEshikshaPreview(null);
    const r=await fetch("/api/eshiksha-request",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({session_id:sessionId})});
    const d=await r.json();
    if(!r.ok){setMsg(clientFailure("eShikshaKosh Connector","Create secure sign-in",d.error||d.detail||"Unknown error"));return}
    setEshikshaToken(d.token);setEshikshaUrl(d.entry_url);
    setMsg("Enter the eShikshaKosh details in the secure panel.");
  }

  async function uploadEshikshaReport(){
    if(!eshikshaFile){setMsg("Choose an eShikshaKosh Excel report first.");return}
    setMsg("Uploading the eShikshaKosh report securely…");
    const form=new FormData(); form.append("file",eshikshaFile);
    const r=await fetch("/api/eshiksha-upload",{method:"POST",body:form});
    const d=await r.json();
    if(!r.ok){setMsg(clientFailure("eShikshaKosh Source Upload","Upload workbook",d.error||d.detail||"Unknown error"));return}
    setEshikshaReportReady(true);setEshikshaFile(null);setMsg("eShikshaKosh report ready. Generate the EP preview.");
  }
  async function saveEshikshaCredentials(){
    if(!eshikshaToken||!eshikshaUdise||!eshikshaPassword){setMsg("Enter eShikshaKosh UDISE code and password.");return}
    const r=await fetch("/api/eshiksha-credentials",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({token:eshikshaToken,udise:eshikshaUdise,password:eshikshaPassword,year:eshikshaYear,session_id:sessionId})});
    const d=await r.json(); setEshikshaPassword("");
    if(!r.ok){setEshikshaReady(false);setMsg(clientFailure("eShikshaKosh Authentication","Verify credentials",d.detail||d.error||"Unknown error"));return}
    setEshikshaReady(Boolean(d.verified));setEshikshaUrl("");
    setEshikshaSchoolName(String(d.school_name||""));setEshikshaConnectedUdise(String(d.udise||eshikshaUdise));
    setMsg(`eShikshaKosh connected${d.school_name?": "+d.school_name:""}.`);
  }

  async function downloadEshikshaReport(){
    if(!eshikshaReady){
      await connectEshiksha();
      setMsg("Connect eShikshaKosh first, then fetch the source report.");
      return;
    }
    setMsg("Fetching the complete eShikshaKosh OTR report…");
    const r=await fetch(`/api/eshiksha-export?class=${encodeURIComponent(klass)}&session_id=${encodeURIComponent(sessionId)}`,{cache:"no-store"});
    if(!r.ok){
      let detail="eShikshaKosh report fetch failed.";
      try{
        const d=await r.json();
        detail=d.detail||d.error||detail;
      }catch{
        const t=await r.text();
        if(t) detail=t.slice(0,500);
      }
      setEshikshaReady(false);
      setMsg(clientFailure("eShikshaKosh Report Fetch","Fetch complete OTR workbook",detail));
      return;
    }
    const blob=await r.blob();
    const url=URL.createObjectURL(blob);
    const a=document.createElement("a");
    a.href=url;
    a.download=`eShikshaKosh_OTR_ALL.xlsx`;
    document.body.appendChild(a);a.click();a.remove();
    URL.revokeObjectURL(url);
    setEshikshaReportReady(true);setEshikshaReady(false);
    try {
      const previewResponse = await fetch(`/api/eshiksha-preview?session_id=${encodeURIComponent(sessionId)}`,{cache:"no-store"});
      const previewData = await previewResponse.json();
      if(previewResponse.ok) setEshikshaPreview(previewData);
      else setMsg(previewData.detail||previewData.error||"Report fetched, but the browser preview could not be loaded.");
    } catch { setMsg("Report fetched and retained for EP, but the browser preview could not be loaded."); }
    setMsg("Latest eShikshaKosh report fetched. The source is ready for Enrollment Profile processing.");
  }

  useEffect(()=>{
    if(!eshikshaToken || eshikshaReady) return;
    const t=setInterval(async()=>{
      const r=await fetch("/api/eshiksha-status?token="+encodeURIComponent(eshikshaToken),{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      if(d.ready&&d.verified){setEshikshaReady(true);setEshikshaUrl("");setEshikshaSchoolName(String(d.school_name||""));setEshikshaConnectedUdise(String(d.udise||""));setMsg(`eShikshaKosh connected${d.school_name?": "+d.school_name:""}. EP source is ready.`);clearInterval(t)}
      else if(eshikshaReady){setEshikshaReady(false);setMsg("The temporary eShikshaKosh connection is no longer available. Connect again before EP preview.");clearInterval(t)}
    },2000);
    return ()=>clearInterval(t);
  },[eshikshaToken,eshikshaReady]);

  async function confirmCwsn(){
    if(!jobId||cwsnConfirmBusy) return;
    const ok=window.confirm("Confirm CWSN = No for every listed student? The system will set CWSN to No and then save and fresh-read each record.");
    if(!ok) return;
    setCwsnConfirmBusy(true);
    setMsg("CWSN confirmation received. Queuing verified GP saves…");
    const r=await fetch("/api/jobs/"+encodeURIComponent(jobId)+"/confirm-cwsn",{method:"POST"});
    const d=await r.json().catch(()=>({}));
    setCwsnConfirmBusy(false);
    if(!r.ok){
      setMsg(clientFailure("UDISE General Profile","Confirm CWSN=No",d.detail||d.error||"Unknown error"));
      return;
    }
    setMsg("CWSN=No confirmed. Verified GP save is now running.");
    if(d.write_job_id) setJobId(d.write_job_id);
  }

  async function startJob(){
    if(!sessionId){setMsg("Connect a secure UDISE session first.");return}
    if(!school.trim()){setMsg("Enter the school URL or 7-digit internal ID.");return}
    if(selected?.requires_class&&!selected.classes.includes(klass)){setMsg(`${selected.label} is not available for Class ${klass}.`);return}
    if(selected?.id==="ep"&&klass!=="X"&&!eshikshaReady&&!eshikshaReportReady){await connectEshiksha();return}
    setMsg(selected?.mode==="write"?"Preparing and saving…":"Preparing the workflow…");setJob(null);setJobId("");
    const r=await fetch("/api/jobs",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({
      session_id:sessionId,school:school.trim(),stage,class_name:selected?.requires_class?klass:null,preview:true,auto_save:selected?.mode==="write",max_submissions:selected?.mode==="write"?saveLimit:1
    })});
    const d=await r.json();
    if(!r.ok){setMsg(clientFailure(selected?.label||stage,"Start preview",d.detail||d.error||"Unknown error"));return}
    setJobId(d.job_id);setMsg("Workflow started.");
  }

  useEffect(()=>{
    if(!jobId) return;
    const poll=async()=>{
      const r=await fetch("/api/jobs/"+jobId,{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      setJob(d);
      if(d.job.stage==="ep"&&["completed","failed"].includes(d.job.status)) setEshikshaReady(false);
      if(d.job.auto_write_job_id){
        const limit=Number(d.job.max_submissions||saveLimit||1); setMsg(`Preview verified. Server-side save is queued for up to ${limit} record(s); browser connection is no longer required.`);
        if(d.job.auto_write_job_id!==jobId){
          setJobId(d.job.auto_write_job_id);
          return;
        }
      }
      if(["completed","failed"].includes(d.job.status)) clearInterval(timer);
    };
    const timer=setInterval(poll,1800);poll();
    return ()=>clearInterval(timer);
  },[jobId]);

  const pct=job?.job.progress_total?Math.min(100,Math.round(job.job.progress_current*100/job.job.progress_total)):0;
  return <main>
    <div className="hero"><div><span className="eyebrow">HERMES VPS</span><h1>UDISE Operations Console</h1></div><span className="privacy-pill">Secure control plane</span></div>
    <div className="workspace">
      <div className="controls">
        <section className="card setup-card">
          <div className="section-title"><span className="step">1</span><div><h2>UDISE Login</h2><p>Username, password and CAPTCHA</p></div></div>
          {!sessionId?<div className="login-form-grid">
            <label>Username<input value={username} onChange={e=>setUsername(e.target.value)} autoComplete="username" placeholder="UDISE username"/></label>
            <label>Password<div className="password-field"><input type={showPassword?"text":"password"} value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password" placeholder="Password"/><button type="button" className="password-toggle" onClick={()=>setShowPassword(v=>!v)} aria-label={showPassword?"Hide password":"Show password"} title={showPassword?"Hide password":"Show password"}>{showPassword?"🙈":"👁️"}</button></div></label>
            <div className="captcha-row">
              {loginToken?<img className="captcha-image" src={"/api/udise-login/captcha?token="+encodeURIComponent(loginToken)+"&v="+captchaNonce} alt="UDISE CAPTCHA"/>:<div className="captcha-placeholder">Loading CAPTCHA…</div>}
              <button type="button" className="secondary-button" onClick={beginUdiseLogin} disabled={loginBusy}>Refresh CAPTCHA</button>
            </div>
            <label>CAPTCHA<input value={captcha} onChange={e=>setCaptcha(e.target.value)} onKeyDown={e=>e.key==="Enter"&&submitUdiseLogin()} autoComplete="off" placeholder="Enter CAPTCHA"/></label>
            <button type="button" className="run-button" onClick={submitUdiseLogin} disabled={loginBusy}>{loginBusy?"Please wait…":"Sign in"}</button>
            <details className="advanced-login"><summary>Advanced / fallback login</summary><button type="button" className="secondary-button" onClick={connectExistingSession}>Use existing browser session</button></details>
          </div>:<div className="connected-row"><div><span className="badge ok">● Students Module connected</span><div className="session-meta"><strong>{sessionSchoolName||"School"}</strong>{sessionUdiseCode&&<span>UDISE: {sessionUdiseCode}</span>}<span>Verified window: {String(Math.floor(sessionSeconds/3600)).padStart(2,"0")}:{String(Math.floor((sessionSeconds%3600)/60)).padStart(2,"0")}:{String(sessionSeconds%60).padStart(2,"0")}</span></div></div><button type="button" className="secondary-button" onClick={()=>{setSessionId("");setSessionSchoolName("");setSessionUdiseCode("");setSessionExpiresAt(0);beginUdiseLogin()}}>Sign in again</button></div>}
        </section>

        {sessionId&&<>
        <section className="card scope-card">
          <div className="section-heading"><div className="section-title"><span className="step">2</span><div><h2>Select class</h2><p>Phase 2 · Class scope for all profile operations</p></div></div><span className="stage-count">Class {klass}</span></div>
          <div className="class-grid" role="group" aria-label="Operation class">
            {caps?.classes.map(c=><button type="button" aria-pressed={klass===c.id} key={c.id} className={"class-choice "+(klass===c.id?"active":"")} onClick={()=>setKlass(c.id)}>{c.label}</button>)}
          </div>
        </section>

        <section className="card stage-card">
          <div className="section-heading"><div className="section-title"><span className="step">3</span><div><h2>Choose workflow</h2><p>Available operations for Class {klass}</p></div></div><span className="stage-count">{readyCount+previewCount} workflows</span></div>
          <div className="grid">{caps?.stages.map(s=>{
            const meta=STAGE_META[s.id]||{icon:"--",short:s.description,fills:[]};
            const unavailable=s.requires_class&&!s.classes.includes(klass);
            return <button type="button" aria-pressed={stage===s.id} disabled={unavailable} key={s.id} className={"choice "+(stage===s.id?"active ":"")+(s.mode==="write"?"previewable":"ready")} onClick={()=>setStage(s.id)}>
              <span className="stage-icon" aria-hidden="true">{meta.icon}</span>
              <span className="stage-copy"><strong>{s.label}</strong><small>{meta.short}</small></span>
              <span className={"badge "+(unavailable?"warn":s.mode==="write"?"preview":"ok")}>{unavailable?"Unavailable":s.mode==="write"?"Save":"Ready"}</span>
              <span className="badge" role="button" tabIndex={0} aria-label={"How "+s.label+" works"} onClick={e=>{e.stopPropagation();setInfoStage(s.id)}} onKeyDown={e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();e.stopPropagation();setInfoStage(s.id)}}}>ⓘ</span>
            </button>})}
          </div>

          {selected&&<div className={"selected-stage "+(selected.mode==="write"?"is-locked":"is-ready")}>
            <div className="selected-stage-head"><span aria-hidden="true">{selectedMeta?.icon||"--"}</span><div><strong>{selected.label}</strong><small>{HERMES_FLOW_REFERENCE[selected.id]}</small></div></div>
            <div className="fill-chips">{selectedMeta?.fills.map(item=><span key={item}>{item}</span>)}</div>
            {selected.mode!=="read"&&<div className="blank-only-note"><strong>Blank-only rule:</strong> values already saved in UDISE are untouched. Only eligible blank fields are proposed; skipped and already-complete students are listed in the Excel result.</div>}
            {selected.id==="ep"&&<div className="ep-source">
              <div className="ep-source-head">
                <div>
                  <span className="eyebrow">ENROLLMENT DATA SOURCE</span>
                  <h3>Use eShikshaKosh to complete UDISE Enrollment Profile</h3>
                  <p>eShikshaKosh supplies the source data used to match students and fill eligible blank EP fields—primarily <strong>Admission Number</strong> and, for Class XI, <strong>stream</strong>. Connecting this source does not write anything to UDISE.</p>
                </div>
                <span className={"source-pill "+((eshikshaReady||eshikshaReportReady||klass==="X")?"ready":"needed")}>{eshikshaReportReady?"EP source ready":eshikshaReady?"Verified connection":klass==="X"?"Optional for Class X":"Source required"}</span>
              </div>
              {eshikshaReady&&<div className="source-identity"><strong>Connected:</strong> {eshikshaSchoolName||"eShikshaKosh school"}{eshikshaConnectedUdise?` · UDISE ${eshikshaConnectedUdise}`:""}<small>Login verified. The password is temporary for this UDISE session and is discarded after the live source fetch.</small></div>}
              {eshikshaReportReady&&<div className="source-identity"><strong>EP source ready.</strong> The fetched/uploaded eShikshaKosh report is retained server-side and passed automatically into Enrollment Profile.</div>}
              {eshikshaPreview&&<div className="source-preview">
                <div className="source-preview-head"><div><strong>Latest eShikshaKosh data</strong><small>{eshikshaPreview.total} students loaded · showing first {eshikshaPreview.preview_limit}</small></div><span className="badge ok">Ready for EP</span></div>
                <div className="source-counts">{Object.entries(eshikshaPreview.class_counts).sort().map(([k,v])=><span key={k}>Class {k.replace(/^Class\\s*/i,"")}: <strong>{v}</strong></span>)}</div>
                <div className="source-table-wrap"><table className="source-table"><thead><tr><th>Student</th><th>Father</th><th>Class</th><th>Admission</th><th>OTR</th><th>Stream</th></tr></thead><tbody>{eshikshaPreview.rows.map((row,i)=><tr key={i}><td>{row["Student Name"]}</td><td>{row["Father's Name"]}</td><td>{row["Class"]}</td><td>{row["Admission No"]}</td><td>{row["OTR Number"]}</td><td>{row["Stream"]}</td></tr>)}</tbody></table></div>
                <small className="source-preview-note">Preview is read-only. The complete retained workbook—not just these displayed rows—is used by the EP matcher.</small>
              </div>}

              <div className="source-methods">
                <div className="source-method recommended">
                  <div className="method-title"><div><strong>Automatic fetch</strong><span>{klass==="X"?"Optional":"Recommended"}</span></div><small>{klass==="X"?"Class X can run without eShikshaKosh. Connect it only when you want eShikshaKosh Admission Number data for matching.":`Sign in once and fetch the latest read-only eShikshaKosh report for Class ${klass}.`}</small></div>
                  {!eshikshaReady&&<button type="button" className="source-primary" onClick={connectEshiksha}>{eshikshaToken?"Update sign-in details":"Connect eShikshaKosh"}</button>}
                  {eshikshaReady&&<div className="method-actions"><button type="button" className="source-primary" onClick={downloadEshikshaReport}>Fetch latest report</button><button type="button" className="source-secondary" onClick={connectEshiksha}>Change sign-in</button></div>}
                  {eshikshaToken&&!eshikshaReady&&!eshikshaReportReady&&<div className="credential-grid">
                    <label>UDISE code / username<input value={eshikshaUdise} onChange={e=>setEshikshaUdise(e.target.value)} autoComplete="username"/></label>
                    <label>Password<div className="password-field"><input type={showEshikshaPassword?"text":"password"} value={eshikshaPassword} onChange={e=>setEshikshaPassword(e.target.value)} autoComplete="current-password"/><button type="button" className="password-toggle" onClick={()=>setShowEshikshaPassword(v=>!v)} aria-label={showEshikshaPassword?"Hide password":"Show password"} title={showEshikshaPassword?"Hide password":"Show password"}>{showEshikshaPassword?"🙈":"👁️"}</button></div></label>
                    <label>Academic year<input value={eshikshaYear} onChange={e=>setEshikshaYear(e.target.value)}/></label>
                    <button type="button" className="source-primary" onClick={saveEshikshaCredentials}>Use for this EP session</button>
                  </div>}
                </div>

                <div className="source-method">
                  <div className="method-title"><div><strong>Upload existing Excel</strong><span>Fallback</span></div><small>Use a previously exported eShikshaKosh workbook instead of signing in.</small></div>
                  <label className="file-picker"><span>{eshikshaFile?eshikshaFile.name:"Choose Excel report"}</span><input type="file" accept=".xlsx,.xls" onChange={e=>setEshikshaFile(e.target.files?.[0]||null)}/></label>
                  <button type="button" className="source-secondary" onClick={uploadEshikshaReport} disabled={!eshikshaFile}>Use uploaded report</button>
                </div>
              </div>

              <div className="source-utility">
                <div><strong>Need a review template?</strong><span>Download the current UDISE Class {klass} roster as an EP template for manual review or matching.</span></div>
                <a className="source-link" href={`/api/ep-template?class=${encodeURIComponent(klass)}&session_id=${encodeURIComponent(sessionId)}&school=${encodeURIComponent(school)}`}>Download EP template</a>
              </div>
            </div>}
            {selected.mode==="write"?<><div className="save-limit-control"><label><strong>Students to save</strong><select value={saveLimit} onChange={e=>setSaveLimit(Number(e.target.value))}>{[1,5,10,25,50,100,250,500].map(n=><option key={n} value={n}>{n} student{n===1?"":"s"}</option>)}</select></label><small>Preview checks the full selected class. After preview, the server will save at most the selected number of eligible records.</small></div><div className="lock-reason"><div><strong>Automatic save with verification</strong><span>The system checks current values, saves only eligible changes, then verifies each save with a fresh read-back.{selected.id==="ep"?(eshikshaReady||eshikshaReportReady?" eShikshaKosh is used as the EP source.":klass==="X"?" Class X can use UDISE current values and built-in EP rules without eShikshaKosh.":""):""}</span></div></div></>:<p>{selected.description}</p>}
          </div>}

          <div className="run-row">
            <button className="run-button" disabled={(selected?.mode==="write"&&!selected.preview_enabled)||Boolean(selected?.requires_class&&!selected.classes.includes(klass))} onClick={startJob}>{selected?.id==="ep"&&klass!=="X"&&!eshikshaReady&&!eshikshaReportReady?"Connect eShikshaKosh":selected?.mode==="write"?"Run & Save":"Run"}</button>
          </div>
        </section>
        </>}
      </div>

      <aside className="card output-card">
        <div className="output-title"><div><span className="eyebrow">ACTIVITY &amp; RESULT</span><h2>{job?"Workflow progress":"Ready to begin"}</h2></div>{job&&<span className="badge">{job.job.status}</span>}</div>
        {!job&&<div className="empty-output"><span className="status-mark">STATUS</span><strong>{msg||"Connect UDISE and choose a workflow."}</strong><p>Progress and downloadable results will appear here.</p></div>}
        {job&&<div className="job-output">
          <div className="friendly-message">{job.job.message||msg}</div>
          {job.job.progress_total>0&&<><div className="progress"><div style={{width:pct+"%"}}/></div><p className="progress-copy"><strong>{pct}%</strong><span>{job.job.progress_current}/{job.job.progress_total} students</span></p></>}
          {job.events.some(e=>e.message.includes("GP_CWSN_CONFIRM_REQUIRED"))&&job.job.stage==="gp"&&job.job.status==="awaiting_confirmation"&&!job.job.auto_write_job_id&&<div className="error-box" role="alert">
            <strong>CWSN confirmation required</strong>
            <span>Students with CWSN=Yes are listed below with PEN, Name and Father&apos;s Name. Verify them before confirming. The system will set CWSN=No, save each record, and perform a fresh read-back verification.</span>
            <button type="button" className="run-button" onClick={confirmCwsn} disabled={cwsnConfirmBusy}>{cwsnConfirmBusy?"Confirming…":"Confirm CWSN = No & Continue"}</button>
          </div>}
          <ul className="events" aria-live="polite">{job.events.slice(-12).map(e=><li key={e.id} className={e.level==="error"?"event-error":""}>{e.message}</li>)}</ul>
          {job.job.has_result&&<a className="download" href={"/api/jobs/"+job.job.id+"/result"}>Download Excel workbook</a>}
          {job.job.error&&<div className="error-box"><strong>Workflow stopped</strong><span>{job.job.error}</span></div>}
        </div>}
      </aside>
    </div>
    {entryUrl&&!sessionId&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Existing UDISE browser session">
      <div className="session-modal">
        <div className="modal-head"><div><span className="eyebrow">FALLBACK</span><h2>Use existing browser session</h2></div><button className="modal-close" onClick={()=>setEntryUrl("")} aria-label="Close">×</button></div>
        <p>Use this only if direct UDISE login is unavailable. Connect the already signed-in browser session using the secure session bridge or cookie header.</p>
        <iframe title="Secure UDISE browser session" src={entryUrl}/>
      </div>
    </div>}
    {infoStage&&WORKFLOW_INFO[infoStage]&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Workflow information">
      <div className="session-modal">
        <div className="modal-head"><div><span className="eyebrow">WORKFLOW</span><h2>{WORKFLOW_INFO[infoStage].title}</h2></div><button className="modal-close" onClick={()=>setInfoStage(null)} aria-label="Close">×</button></div>
        <ol>{WORKFLOW_INFO[infoStage].steps.map((step,i)=><li key={i} style={{marginBottom:10}}>{step}</li>)}</ol>
        <button className="run-button" onClick={()=>setInfoStage(null)}>Close</button>
      </div>
    </div>}
  </main>
}
