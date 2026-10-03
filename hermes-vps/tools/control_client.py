#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE=os.environ.get("UDISE_CONTROL_LOCAL_API","http://127.0.0.1:9135").rstrip("/")
TOKEN_FILE=Path(os.environ.get("UDISE_CONTROL_TOKEN_FILE",Path.home()/".config/udise-control/api-token"))

def token():
    return TOKEN_FILE.read_text().strip()

PROGRESS_RE = re.compile(r"(?P<label>[^:]+):\s*(?P<current>\d+)/(?P<total>\d+)\s+students checked", re.I)

def _progress_percent(message):
    m=PROGRESS_RE.search(str(message or ""))
    if not m:
        return None
    current=int(m.group("current")); total=int(m.group("total"))
    if total <= 0:
        return None
    return current, total, min(100, int(current * 100 / total))

def milestone_events(events, last_id=0, last_bucket=-1, step=25):
    lines=[]
    step=max(1,min(100,int(step)))
    for e in events or []:
        eid=int(e.get("id") or 0)
        if eid <= last_id:
            continue
        last_id=max(last_id,eid)
        msg=str(e.get("message") or "").strip()
        progress=_progress_percent(msg)
        if progress:
            current,total,pct=progress
            bucket=pct // step
            if current == total or (bucket > 0 and bucket > last_bucket):
                shown=100 if current == total else min(100,bucket*step)
                lines.append(f"PROGRESS={shown}% ({current}/{total})")
                last_bucket=max(last_bucket,bucket)
            continue
        low=msg.lower()
        if (low.startswith("roster loaded:")
            or low == "udise session authenticated"
            or low == "report file ready"
            or low.startswith("completed successfully")):
            lines.append(msg)
    return lines,last_id,last_bucket

def download_result(job, out_path):
    req=Request(BASE+"/api/v1/jobs/"+job+"/result",headers={"Authorization":"Bearer "+token()})
    with urlopen(req,timeout=60) as r:
        data=r.read()
    out=Path(out_path); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data)
    return out.resolve()

def call(path, method="GET", body=None, auth=True):
    data=json.dumps(body).encode() if body is not None else None
    headers={"Content-Type":"application/json"}
    if auth: headers["Authorization"]="Bearer "+token()
    req=Request(BASE+path,data=data,headers=headers,method=method)
    try:
        with urlopen(req,timeout=30) as r:
            c=r.read()
            return json.loads(c) if c else {}
    except HTTPError as e:
        msg=e.read().decode(errors="ignore")
        raise SystemExit(f"HTTP {e.code}: {msg[:500]}")

def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd",required=True)
    sub.add_parser("capabilities")
    c=sub.add_parser("connect"); c.add_argument("--return-url",default="")
    cs=sub.add_parser("connect-status"); cs.add_argument("token")
    ec=sub.add_parser("eshiksha-connect"); ec.add_argument("--return-url",default="")
    es=sub.add_parser("eshiksha-status"); es.add_argument("token")
    r=sub.add_parser("run")
    r.add_argument("--session",required=True); r.add_argument("--school",required=True)
    r.add_argument("--stage",required=True); r.add_argument("--class",dest="klass",default=None)
    s=sub.add_parser("status"); s.add_argument("job")
    w=sub.add_parser("watch"); w.add_argument("job"); w.add_argument("--interval",type=int,default=3)
    w.add_argument("--milestone-step",type=int,default=0,
                   help="Emit sparse progress milestones instead of every event (for chat use).")
    w.add_argument("--out",default="",
                   help="On successful completion, download the result workbook here.")
    o=sub.add_parser("result"); o.add_argument("job"); o.add_argument("--out",required=True)
    a=ap.parse_args()

    if a.cmd=="capabilities":
        print(json.dumps(call("/api/v1/capabilities",auth=False),ensure_ascii=False)); return
    if a.cmd=="connect":
        print(json.dumps(call("/api/v1/session-requests","POST",{"return_url":a.return_url}),ensure_ascii=False)); return
    if a.cmd=="connect-status":
        print(json.dumps(call("/api/v1/session-requests/"+a.token),ensure_ascii=False)); return
    if a.cmd=="eshiksha-connect":
        print(json.dumps(call("/api/v1/eshiksha-requests","POST",{"return_url":a.return_url}),ensure_ascii=False)); return
    if a.cmd=="eshiksha-status":
        print(json.dumps(call("/api/v1/eshiksha-requests/"+a.token),ensure_ascii=False)); return
    if a.cmd=="run":
        body={"session_id":a.session,"school":a.school,"stage":a.stage,"class_name":a.klass,"preview":True}
        print(json.dumps(call("/api/v1/jobs","POST",body),ensure_ascii=False)); return
    if a.cmd in {"status","watch"}:
        last=0
        last_bucket=-1
        while True:
            d=call("/api/v1/jobs/"+a.job)
            if a.cmd=="status":
                print(json.dumps(d,ensure_ascii=False)); return
            events=d.get("events",[])
            if a.milestone_step:
                lines,last,last_bucket=milestone_events(
                    events,last_id=last,last_bucket=last_bucket,step=a.milestone_step
                )
                for line in lines:
                    print(line,flush=True)
            else:
                for e in events:
                    if int(e["id"])>last:
                        print(e["message"],flush=True); last=int(e["id"])
            st=d.get("job",{}).get("status")
            if st in {"completed","failed"}:
                print("FINAL_STATUS="+str(st),flush=True)
                if st=="completed" and a.out:
                    result=download_result(a.job,a.out)
                    print("RESULT_FILE="+str(result),flush=True)
                return
            time.sleep(max(1,a.interval))
    if a.cmd=="result":
        print(str(download_result(a.job,a.out))); return

if __name__=="__main__":
    main()
