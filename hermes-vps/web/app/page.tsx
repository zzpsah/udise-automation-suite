"use client";
import { useEffect, useMemo, useState } from "react";

type Stage={id:string;label:string;mode:"read"|"write";classes:string[];requires_class:boolean;description:string;preview_enabled?:boolean;approval_enabled?:boolean};
type SchoolPreset={internal_id:string;udise_code:string;name:string};
type Caps={classes:{id:string;label:string}[];stages:Stage[];school_presets?:SchoolPreset[]};
type JobState={job:{id:string;status:string;stage:string;class_name?:string;preview:number;approved_from?:string;max_submissions?:number;progress_current:number;progress_total:number;message:string;has_result:boolean;error?:string};events:{id:number;message:string;level:string}[]};

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
  facility: {icon:"P4",short:"Blank facility fields only; existing values are never overwritten",fills:["Height → seeded value 146–160 cm","Weight → seeded value 42–52 kg","4.3.6 Distance → seeded 1–3 km or 3–5 km","Parent education → Secondary","Blank Yes/No facility fields → No"]},
  completion: {icon:"P5",short:"Export the current stage status",fills:["GP / EP / Facility status","Pending and completed records"]},
  finalize: {icon:"P5",short:"Review records eligible for Complete Data",fills:["Fresh status 3 only","Proposed transition to status 6"]},
};

export default function Page(){
  const [caps,setCaps]=useState<Caps|null>(null);
  const [school,setSchool]=useState("");
  const [savedSchools,setSavedSchools]=useState<Array<{id:string;label:string}>>([]);
  const [klass,setKlass]=useState("IX");
  const [stage,setStage]=useState("completion");
  const [sessionToken,setSessionToken]=useState("");
  const [sessionId,setSessionId]=useState("");
  const [entryUrl,setEntryUrl]=useState("");
  const [eshikshaToken,setEshikshaToken]=useState("");
  const [eshikshaUrl,setEshikshaUrl]=useState("");
  const [eshikshaReady,setEshikshaReady]=useState(false);
  const [eshikshaReportReady,setEshikshaReportReady]=useState(false);
  const [eshikshaFile,setEshikshaFile]=useState<File|null>(null);
  const [eshikshaUdise,setEshikshaUdise]=useState("");
  const [eshikshaPassword,setEshikshaPassword]=useState("");
  const [eshikshaYear,setEshikshaYear]=useState("2026-27");
  const [jobId,setJobId]=useState("");
  const [job,setJob]=useState<JobState|null>(null);
  const [autoSavePreview,setAutoSavePreview]=useState(false);
  const [infoStage,setInfoStage]=useState<string|null>(null);
  const [msg,setMsg]=useState("");

  async function loadCaps(){
    const r=await fetch("/api/capabilities",{cache:"no-store"});
    if(!r.ok){setMsg("Capabilities load failed");return}
    const data:Caps=await r.json();
    setCaps(data);
    if(data.school_presets?.length) setSchool(current=>current||data.school_presets![0].internal_id);
  }
  useEffect(()=>{loadCaps()},[]);
  useEffect(()=>{
    try { const raw=window.localStorage.getItem("udise_saved_schools"); if(raw) setSavedSchools(JSON.parse(raw)); } catch {}
  },[]);

  function saveSchool(){
    const id=school.trim();
    if(!id) return;
    const next=[{id,label:id},...savedSchools.filter(item=>item.id!==id)].slice(0,12);
    setSavedSchools(next);
    window.localStorage.setItem("udise_saved_schools",JSON.stringify(next));
    setMsg("School saved in this browser's dropdown.");
  }

  const selected=useMemo(()=>caps?.stages.find(x=>x.id===stage),[caps,stage]);
  const selectedMeta=selected?STAGE_META[selected.id]:undefined;
  const readyCount=caps?.stages.filter(x=>x.mode==="read").length||0;
  const previewCount=caps?.stages.filter(x=>x.mode==="write"&&x.preview_enabled).length||0;
  useEffect(()=>{
    if(selected?.requires_class && !selected.classes.includes(klass)) setStage("completion");
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
    setEshikshaReady(false);
    const r=await fetch("/api/eshiksha-request",{method:"POST"});
    const d=await r.json();
    if(!r.ok){setMsg(d.error||"Could not create the secure eShikshaKosh sign-in");return}
    setEshikshaToken(d.token);setEshikshaUrl(d.entry_url);
    setMsg("Enter the eShikshaKosh details in the secure panel.");
  }

  async function uploadEshikshaReport(){
    if(!eshikshaFile){setMsg("Choose an eShikshaKosh Excel report first.");return}
    setMsg("Uploading the eShikshaKosh report securely…");
    const form=new FormData(); form.append("file",eshikshaFile);
    const r=await fetch("/api/eshiksha-upload",{method:"POST",body:form});
    const d=await r.json();
    if(!r.ok){setMsg(d.error||"Report upload failed");return}
    setEshikshaReportReady(true);setEshikshaFile(null);setMsg("eShikshaKosh report ready. Generate the EP preview.");
  }
  async function saveEshikshaCredentials(){
    if(!eshikshaToken||!eshikshaUdise||!eshikshaPassword){setMsg("Enter eShikshaKosh UDISE code and password.");return}
    const r=await fetch("/api/eshiksha-credentials",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({token:eshikshaToken,udise:eshikshaUdise,password:eshikshaPassword,year:eshikshaYear})});
    const d=await r.json(); if(!r.ok){setMsg(d.detail||d.error||"Could not save eShikshaKosh credentials");return}
    setEshikshaReady(true);setEshikshaUrl("");setEshikshaPassword("");setMsg("eShikshaKosh credentials saved temporarily for this page.");
  }

  async function downloadEshikshaReport(){
    if(!eshikshaReady){
      await connectEshiksha();
      setMsg("Enter eShikshaKosh credentials first. Download will be enabled after they are saved.");
      return;
    }
    setMsg("Starting the eShikshaKosh report download. This does not require a UDISE session…");
    window.location.href=`/api/eshiksha-export?class=${encodeURIComponent(klass)}`;
  }

  useEffect(()=>{
    if(!eshikshaToken || eshikshaReady) return;
    const t=setInterval(async()=>{
      const r=await fetch("/api/eshiksha-status?token="+encodeURIComponent(eshikshaToken),{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();
      if(d.ready){setEshikshaReady(true);setEshikshaUrl("");setMsg("eShikshaKosh is connected. The EP preview is ready to run.");clearInterval(t)}
      else if(eshikshaReady){setEshikshaReady(false);setMsg("The temporary eShikshaKosh connection is no longer available. Connect again before EP preview.");clearInterval(t)}
    },2000);
    return ()=>clearInterval(t);
  },[eshikshaToken,eshikshaReady]);

  async function startJob(){
    if(!sessionId){setMsg("Connect a secure UDISE session first.");return}
    if(!school.trim()){setMsg("Enter the school URL or 7-digit internal ID.");return}
    if(selected?.requires_class&&!selected.classes.includes(klass)){setMsg(`${selected.label} is not available for Class ${klass}.`);return}
    if(selected?.id==="ep"&&!eshikshaReady&&!eshikshaReportReady){await connectEshiksha();return}
    setMsg(selected?.mode==="write"?"Preparing and saving…":"Preparing the workflow…");setJob(null);setJobId("");setAutoSavePreview(selected?.mode==="write");
    const r=await fetch("/api/jobs",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({
      session_id:sessionId,school:school.trim(),stage,class_name:selected?.requires_class?klass:null,preview:true
    })});
    const d=await r.json();
    if(!r.ok){setMsg(d.detail||d.error||"Job start failed");return}
    setJobId(d.job_id);setMsg("Workflow started.");
  }

  async function autoApproveWrite(previewJob:JobState){
    setAutoSavePreview(false);
    const phrase="SAVE "+previewJob.job.stage.toUpperCase()+" "+(previewJob.job.class_name||"ALL");
    setMsg("Preview checked. Saving eligible changes…");
    const r=await fetch(`/api/jobs/${previewJob.job.id}/approve`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({
      confirmation:phrase,acknowledge_readback:true,max_submissions:500
    })});
    const d=await r.json();
    if(!r.ok){setMsg(d.detail||d.error||"Save could not start");return}
    setJob(null);setJobId(d.job_id);
    setMsg("Saving to UDISE. Fresh read-back will verify each change.");
  }

  useEffect(()=>{
    if(!jobId) return;
    const poll=async()=>{
      const r=await fetch("/api/jobs/"+jobId,{cache:"no-store"});
      if(!r.ok) return;
      const d=await r.json();setJob(d);
      if(d.job.stage==="ep"&&d.job.status==="failed") setEshikshaReady(false);
      if(d.job.status==="completed"&&autoSavePreview&&d.job.preview&&d.job.has_result){
        clearInterval(timer);
        await autoApproveWrite(d);
        return;
      }
      if(["completed","failed"].includes(d.job.status)){
        clearInterval(timer);
        if(d.job.status==="failed") setAutoSavePreview(false);
      }
    };
    const timer=setInterval(poll,1800);poll();
    return ()=>clearInterval(timer);
  },[jobId,autoSavePreview]);

  const pct=job?.job.progress_total?Math.min(100,Math.round(job.job.progress_current*100/job.job.progress_total)):0;
  return <main>
    <div className="hero"><div><span className="eyebrow">HERMES VPS</span><h1>UDISE Operations Console</h1></div><span className="privacy-pill">Secure control plane</span></div>
    <div className="workspace">
      <div className="controls">
        <section className="card setup-card">
          <div className="section-title"><span className="step">1</span><div><h2>Connect school</h2><p>{LOGIN_REFERENCE}</p></div></div>
          <div className="setup-row">
            {Boolean(caps?.school_presets?.length)&&<select className="school-preset" aria-label="Saved school" value={caps?.school_presets?.some(p=>p.internal_id===school)?school:""} onChange={e=>setSchool(e.target.value)}>
              <option value="">Custom school</option>
              {caps?.school_presets?.map(p=><option value={p.internal_id} key={p.internal_id}>{p.udise_code} · {p.name}</option>)}
            </select>}
            {savedSchools.length>0&&<select className="school-preset" aria-label="My saved schools" value={savedSchools.some(item=>item.id===school)?school:""} onChange={e=>setSchool(e.target.value)}>
              <option value="">My saved schools</option>
              {savedSchools.map(item=><option value={item.id} key={item.id}>{item.label}</option>)}
            </select>}
            <input aria-label="School URL or internal ID" value={school} onChange={e=>setSchool(e.target.value)} placeholder="School URL or 7-digit internal ID"/>
            <button type="button" onClick={saveSchool}>Save school</button>
            <button onClick={connectSession}>{sessionId?"Reconnect":"Connect UDISE"}</button>
            {sessionId&&<span className="badge ok">● Ready</span>}
            {!sessionId&&sessionToken&&<span className="badge">Waiting…</span>}
          </div>
        </section>

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
            <button type="button" aria-pressed={stage==="ep"} className={"choice ready source-choice "+(stage==="ep"?"active":"")} onClick={()=>setStage("ep")}>
              <span className="stage-icon" aria-hidden="true">SRC</span>
              <span className="stage-copy"><strong>eShikshaKosh Report</strong><small>Open download, upload, or secure connection controls</small></span>
              <span className="badge ok">Open</span>
            </button>
          </div>

          {selected&&<div className={"selected-stage "+(selected.mode==="write"?"is-locked":"is-ready")}>
            <div className="selected-stage-head"><span aria-hidden="true">{selectedMeta?.icon||"--"}</span><div><strong>{selected.label}</strong><small>{HERMES_FLOW_REFERENCE[selected.id]}</small></div></div>
            <div className="fill-chips">{selectedMeta?.fills.map(item=><span key={item}>{item}</span>)}</div>
            {selected.mode!=="read"&&<div className="blank-only-note"><strong>Blank-only rule:</strong> values already saved in UDISE are untouched. Only eligible blank fields are proposed; skipped and already-complete students are listed in the Excel result.</div>}
            {selected.id==="ep"&&<div className="source-panel">
              <div className={"source-status "+((eshikshaReady||eshikshaReportReady)?"ready":"needed")}>{eshikshaReportReady?"● Uploaded eShikshaKosh report ready":eshikshaReady?"● eShikshaKosh credentials ready for this page":"○ eShikshaKosh report or credentials required"}</div>
              <div className="source-actions"><button type="button" onClick={connectEshiksha}>Prepare credential fields</button><a className="download template-download" href={`/api/ep-template?class=${encodeURIComponent(klass)}&session_id=${encodeURIComponent(sessionId)}&school=${encodeURIComponent(school)}`}>{sessionId?"Download class roster EP template":"Connect UDISE to include class roster"}</a><button type="button" className="download template-download" onClick={downloadEshikshaReport}>Download eShikshaKosh report</button><label className="upload-label">Upload Excel report<input type="file" accept=".xlsx,.xls" onChange={e=>setEshikshaFile(e.target.files?.[0]||null)}/></label><button type="button" onClick={uploadEshikshaReport} disabled={!eshikshaFile}>Upload report</button></div>
              {eshikshaToken&&!eshikshaReady&&!eshikshaReportReady&&<div className="inline-form compact"><label>UDISE code / username<input value={eshikshaUdise} onChange={e=>setEshikshaUdise(e.target.value)} autoComplete="username"/></label><label>Password<input type="password" value={eshikshaPassword} onChange={e=>setEshikshaPassword(e.target.value)} autoComplete="current-password"/></label><label>Academic year<input value={eshikshaYear} onChange={e=>setEshikshaYear(e.target.value)}/></label><button type="button" className="run-button" onClick={saveEshikshaCredentials}>Save credentials temporarily</button></div>}
              <small>Choose one method: enter credentials for an automatic read-only report, or upload an Excel report that you have filled with Admission No. and subjects. The uploaded report is used only for this EP preview.</small>
            </div>}
            {selected.mode==="write"?<div className="lock-reason"><div><strong>Automatic save with verification</strong><span>The system checks current values, saves only eligible changes, then verifies each save with a fresh read-back.{selected.id==="ep"?" The masked eShikshaKosh source is used for the EP run.":""}</span></div></div>:<p>{selected.description}</p>}
          </div>}

          <div className="run-row">
            <button className="run-button" disabled={(selected?.mode==="write"&&!selected.preview_enabled)||Boolean(selected?.requires_class&&!selected.classes.includes(klass))} onClick={startJob}>{selected?.id==="ep"&&!eshikshaReady&&!eshikshaReportReady?"Connect eShikshaKosh":selected?.mode==="write"?"Run & Save":"Run"}</button>
          </div>
        </section>
      </div>

      <aside className="card output-card">
        <div className="output-title"><div><span className="eyebrow">ACTIVITY &amp; RESULT</span><h2>{job?"Workflow progress":"Ready to begin"}</h2></div>{job&&<span className="badge">{job.job.status}</span>}</div>
        {!job&&<div className="empty-output"><span className="status-mark">STATUS</span><strong>{msg||"Connect UDISE and choose a workflow."}</strong><p>Progress and downloadable results will appear here.</p></div>}
        {job&&<div className="job-output">
          <div className="friendly-message">{job.job.message||msg}</div>
          {job.job.progress_total>0&&<><div className="progress"><div style={{width:pct+"%"}}/></div><p className="progress-copy"><strong>{pct}%</strong><span>{job.job.progress_current}/{job.job.progress_total} students</span></p></>}
          <ul className="events">{job.events.slice(-12).map(e=><li key={e.id}><b>{e.level==="error"?"Error":"Update"}</b> · {e.message}</li>)}</ul>
          {job.job.has_result&&<a className="download" href={"/api/jobs/"+job.job.id+"/result"}>Download Excel workbook</a>}
          {job.job.error&&<div className="error-box"><strong>Workflow stopped</strong><span>{job.job.error}</span></div>}
        </div>}
      </aside>
    </div>
    {infoStage&&WORKFLOW_INFO[infoStage]&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Workflow information">
      <div className="session-modal">
        <div className="modal-head"><div><span className="eyebrow">WORKFLOW</span><h2>{WORKFLOW_INFO[infoStage].title}</h2></div><button className="modal-close" onClick={()=>setInfoStage(null)} aria-label="Close">×</button></div>
        <ol>{WORKFLOW_INFO[infoStage].steps.map((step,i)=><li key={i} style={{marginBottom:10}}>{step}</li>)}</ol>
        <button className="run-button" onClick={()=>setInfoStage(null)}>Close</button>
      </div>
    </div>}
    {entryUrl&&!sessionId&&<div className="modal-backdrop" role="dialog" aria-modal="true" aria-label="Secure UDISE session">
      <div className="session-modal">
        <div className="modal-head"><div><span className="eyebrow">SECURE SESSION</span><h2>Connect UDISE securely</h2></div><button className="modal-close" onClick={()=>setEntryUrl("")} aria-label="Close">×</button></div>
        <p>Desktop Chrome/Edge can use the UDISE Hermes Session Bridge extension. Otherwise paste the browser Cookie header below. It goes directly to protected Oracle runtime storage and is never shown in chat or job output.</p>
        <iframe title="Secure UDISE Cookie entry" src={entryUrl}/>
      </div>
    </div>}
  </main>
}
