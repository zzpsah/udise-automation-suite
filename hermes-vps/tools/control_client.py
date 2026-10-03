#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE=os.environ.get("UDISE_CONTROL_LOCAL_API","http://127.0.0.1:9135").rstrip("/")
TOKEN_FILE=Path(os.environ.get("UDISE_CONTROL_TOKEN_FILE",Path.home()/".config/udise-control/api-token"))

def token():
    return TOKEN_FILE.read_text().strip()

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
    r=sub.add_parser("run")
    r.add_argument("--session",required=True); r.add_argument("--school",required=True)
    r.add_argument("--stage",required=True); r.add_argument("--class",dest="klass",default=None)
    s=sub.add_parser("status"); s.add_argument("job")
    w=sub.add_parser("watch"); w.add_argument("job"); w.add_argument("--interval",type=int,default=3)
    o=sub.add_parser("result"); o.add_argument("job"); o.add_argument("--out",required=True)
    a=ap.parse_args()

    if a.cmd=="capabilities":
        print(json.dumps(call("/api/v1/capabilities",auth=False),ensure_ascii=False)); return
    if a.cmd=="connect":
        print(json.dumps(call("/api/v1/session-requests","POST",{"return_url":a.return_url}),ensure_ascii=False)); return
    if a.cmd=="connect-status":
        print(json.dumps(call("/api/v1/session-requests/"+a.token),ensure_ascii=False)); return
    if a.cmd=="run":
        body={"session_id":a.session,"school":a.school,"stage":a.stage,"class_name":a.klass,"preview":True}
        print(json.dumps(call("/api/v1/jobs","POST",body),ensure_ascii=False)); return
    if a.cmd in {"status","watch"}:
        last=0
        while True:
            d=call("/api/v1/jobs/"+a.job)
            if a.cmd=="status":
                print(json.dumps(d,ensure_ascii=False)); return
            for e in d.get("events",[]):
                if int(e["id"])>last:
                    print(e["message"],flush=True); last=int(e["id"])
            st=d.get("job",{}).get("status")
            if st in {"completed","failed"}:
                print("FINAL_STATUS="+str(st),flush=True); return
            time.sleep(max(1,a.interval))
    if a.cmd=="result":
        req=Request(BASE+"/api/v1/jobs/"+a.job+"/result",headers={"Authorization":"Bearer "+token()})
        with urlopen(req,timeout=60) as r:
            data=r.read()
        out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(data)
        print(str(out.resolve())); return

if __name__=="__main__":
    main()
