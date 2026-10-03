from __future__ import annotations

import html
import json
import os
import re
import secrets
import sqlite3
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from .capabilities import get_capabilities

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("UDISE_CONTROL_STATE", Path.home() / ".hermes/state/udise-control"))
RUNTIME = Path(os.environ.get("UDISE_CONTROL_RUNTIME", Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "udise-control"))
JOBS = STATE / "jobs"
SESSIONS = RUNTIME / "sessions"
REQUESTS = RUNTIME / "session-requests"
DB = STATE / "jobs.sqlite3"
CONTROL_TOKEN_FILE = Path(os.environ.get("UDISE_CONTROL_TOKEN_FILE", Path.home() / ".config/udise-control/api-token"))
RUNNER = Path(os.environ.get("UDISE_VPS_RUNNER", Path.home() / ".local/bin/udise-vps"))
SESSION_TTL = 8 * 60 * 60
REQUEST_TTL = 10 * 60

for p in (STATE, RUNTIME, JOBS, SESSIONS, REQUESTS):
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)

app = FastAPI(title="UDISE Hermes Control API", version="0.1.0")


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            class_name TEXT,
            school TEXT NOT NULL,
            session_id TEXT NOT NULL,
            preview INTEGER NOT NULL DEFAULT 1,
            progress_current INTEGER NOT NULL DEFAULT 0,
            progress_total INTEGER NOT NULL DEFAULT 0,
            message TEXT NOT NULL DEFAULT '',
            result_path TEXT,
            error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


with _db():
    pass


def _control_token() -> str:
    try:
        return CONTROL_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return ""


def require_api(authorization: str | None = Header(default=None)) -> None:
    expected = _control_token()
    if not expected or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    got = authorization[7:].strip()
    if not secrets.compare_digest(got, expected):
        raise HTTPException(401, "Unauthorized")


def _json_read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def _session_path(session_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", session_id or ""):
        raise HTTPException(400, "Invalid session")
    return SESSIONS / f"{session_id}.json"


def _load_session(session_id: str) -> dict:
    p = _session_path(session_id)
    if not p.exists():
        raise HTTPException(401, "UDISE session not available")
    data = _json_read(p)
    if int(time.time()) > int(data.get("expires_at", 0)):
        p.unlink(missing_ok=True)
        raise HTTPException(401, "UDISE session expired")
    return data


class SessionRequestIn(BaseModel):
    return_url: str | None = None


class JobIn(BaseModel):
    session_id: str
    school: str = Field(min_length=1, max_length=200)
    stage: str
    class_name: str | None = None
    preview: bool = True


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "udise-control", "version": app.version}


@app.get("/api/v1/capabilities")
def capabilities() -> dict:
    return get_capabilities()


@app.post("/api/v1/session-requests", dependencies=[])
def create_session_request(body: SessionRequestIn, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    data = {
        "created_at": now,
        "expires_at": now + REQUEST_TTL,
        "used": False,
        "ready": False,
        "return_url": body.return_url or "",
    }
    _json_write(REQUESTS / f"{token}.json", data)
    base = os.environ.get("UDISE_CONTROL_PUBLIC_BASE", "").rstrip("/")
    return {
        "token": token,
        "expires_in": REQUEST_TTL,
        "entry_url": f"{base}/session/{token}" if base else f"/session/{token}",
    }


@app.get("/api/v1/session-requests/{token}")
def session_request_status(token: str, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", token):
        raise HTTPException(400, "Invalid request token")
    p = REQUESTS / f"{token}.json"
    if not p.exists():
        raise HTTPException(404, "Not found")
    data = _json_read(p)
    if int(time.time()) > int(data.get("expires_at", 0)):
        raise HTTPException(410, "Expired")
    return {"ready": bool(data.get("ready")), "session_id": data.get("session_id") if data.get("ready") else None}


@app.get("/session/{token}", response_class=HTMLResponse)
def session_form(token: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", token):
        raise HTTPException(400, "Invalid link")
    p = REQUESTS / f"{token}.json"
    if not p.exists():
        raise HTTPException(404, "Link unavailable")
    data = _json_read(p)
    if data.get("used") or int(time.time()) > int(data.get("expires_at", 0)):
        raise HTTPException(410, "Link expired or already used")
    return HTMLResponse(f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>UDISE Secure Session</title><style>
body{{font-family:system-ui;max-width:620px;margin:40px auto;padding:0 18px;background:#f6f7f9;color:#111}}
.card{{background:#fff;border:1px solid #ddd;border-radius:16px;padding:24px}}
textarea{{width:100%;box-sizing:border-box;min-height:150px;padding:12px;border:1px solid #bbb;border-radius:10px}}
button{{width:100%;padding:13px;margin-top:14px;border:0;border-radius:10px;background:#111;color:white;font-size:16px}}
small{{color:#666}}</style></head><body><div class="card">
<h2>UDISE Secure Session</h2>
<p>Browser Network tab se UDISE Cookie header yahan paste karein. Ye Vercel/WhatsApp chat me nahi jayega.</p>
<form method="post" action="/session/{html.escape(token)}">
<textarea name="cookie" autocomplete="off" required placeholder="JSESSIONID=...; XSRF-TOKEN=..."></textarea>
<button type="submit">Save temporary session</button></form>
<p><small>Session server par protected temporary storage me rahega aur expire ho jayega.</small></p>
</div></body></html>""")


@app.post("/session/{token}")
async def session_submit(token: str, request: Request):
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", token):
        raise HTTPException(400, "Invalid link")
    p = REQUESTS / f"{token}.json"
    if not p.exists():
        raise HTTPException(404, "Link unavailable")
    data = _json_read(p)
    now = int(time.time())
    if data.get("used") or now > int(data.get("expires_at", 0)):
        raise HTTPException(410, "Link expired or already used")
    form = await request.form()
    cookie = str(form.get("cookie") or "").strip()
    if "JSESSIONID=" not in cookie or "XSRF-TOKEN=" not in cookie:
        raise HTTPException(400, "Cookie header must include JSESSIONID and XSRF-TOKEN")
    sid = secrets.token_urlsafe(32)
    _json_write(SESSIONS / f"{sid}.json", {"cookie": cookie, "created_at": now, "expires_at": now + SESSION_TTL})
    data.update({"used": True, "ready": True, "session_id": sid, "used_at": now})
    _json_write(p, data)
    return HTMLResponse("""<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui;max-width:560px;margin:50px auto;padding:20px">
<h2>✅ Session saved</h2><p>Ab UDISE automation screen/WhatsApp par wapas ja sakte hain.</p></body></html>""")


def _event(job_id: str, message: str, level: str = "info") -> None:
    message = message.strip()[:500]
    with _db() as conn:
        conn.execute("INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)",
                     (job_id, int(time.time()), level, message))
        conn.execute("UPDATE jobs SET updated_at=?,message=? WHERE id=?",
                     (int(time.time()), message, job_id))


def _progress_line(line: str) -> tuple[str | None, int | None, int | None]:
    line = line.strip()
    m = re.search(r"\[COMPLETION\]\s+(\d+)/(\d+)\s+", line)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return f"Completion status: {a}/{b} students checked", a, b
    m = re.search(r"Loaded\s+(\d+)\s+students", line, re.I)
    if m:
        n = int(m.group(1))
        return f"Roster loaded: {n} students", n, n
    if line.startswith("REPORT_READY="):
        return "Report file ready", None, None
    if line.startswith("✅ Authenticated."):
        return "UDISE session authenticated", None, None
    if line.startswith("[") and "WAIT " in line:
        return "Portal is responding slowly; still working…", None, None
    if any(k in line for k in ("Completed", "Ready to Complete", "Need FP", "Need EP + FP", "Need GP + EP + FP", "Read failures")):
        return re.sub(r"\s+", " ", line), None, None
    return None, None, None


def _update_progress(job_id: str, current: int | None, total: int | None) -> None:
    if current is None and total is None:
        return
    with _db() as conn:
        conn.execute("UPDATE jobs SET progress_current=COALESCE(?,progress_current), progress_total=COALESCE(?,progress_total), updated_at=? WHERE id=?",
                     (current, total, int(time.time()), job_id))


def _run_job(job_id: str) -> None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return
    try:
        session = _load_session(row["session_id"])
        out_dir = JOBS / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir, 0o700)
        stage = row["stage"]
        cmd = [str(RUNNER), stage, "--school", row["school"], "--out", str(out_dir)]
        if stage == "completion":
            cmd += ["--class", row["class_name"]]
        elif stage not in {"students"}:
            raise RuntimeError("This stage is not enabled in the read-only MVP")

        env = os.environ.copy()
        env["UDISE_COOKIE_HEADER"] = session["cookie"]
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='running',updated_at=?,message=? WHERE id=?",
                         (int(time.time()), "Starting UDISE job", job_id))
        _event(job_id, "Starting UDISE job")

        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                bufsize=1)
        report_path = None
        assert proc.stdout is not None
        for raw in proc.stdout:
            if raw.startswith("REPORT_READY="):
                report_path = raw.split("=", 1)[1].strip()
            msg, cur, total = _progress_line(raw)
            if msg:
                _event(job_id, msg)
                _update_progress(job_id, cur, total)
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"Runner exited with code {code}")
        if report_path and Path(report_path).is_file():
            rp = str(Path(report_path).resolve())
        else:
            files = sorted(out_dir.glob("*.xlsx"))
            rp = str(files[-1].resolve()) if files else None
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='completed',updated_at=?,message=?,result_path=? WHERE id=?",
                         (int(time.time()), "Completed successfully", rp, job_id))
        _event(job_id, "Completed successfully")
    except Exception as exc:
        safe = re.sub(r"[A-Za-z0-9_-]{24,}", "[redacted]", str(exc))[:500]
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='failed',updated_at=?,message=?,error=? WHERE id=?",
                         (int(time.time()), "Job failed", safe, job_id))
        _event(job_id, f"Job failed: {safe}", "error")


@app.post("/api/v1/jobs")
def create_job(body: JobIn, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    caps = get_capabilities()
    stages = {x["id"]: x for x in caps["stages"]}
    stage = stages.get(body.stage)
    if not stage:
        raise HTTPException(400, "Unsupported stage")
    if stage["mode"] != "read":
        raise HTTPException(409, "Write stages are visible but disabled in the read-only MVP")
    if stage.get("requires_class"):
        if not body.class_name or body.class_name not in stage["classes"]:
            raise HTTPException(400, "Select a supported class")
    _load_session(body.session_id)
    job_id = uuid.uuid4().hex
    now = int(time.time())
    with _db() as conn:
        conn.execute("""INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message)
                        VALUES(?,?,?,?,?,?,?,?,?,?)""",
                     (job_id, now, now, "queued", body.stage, body.class_name, body.school,
                      body.session_id, 1, "Queued"))
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


def _job_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d.pop("session_id", None)
    d["has_result"] = bool(d.pop("result_path", None))
    return d


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    with _db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Job not found")
        events = conn.execute("SELECT id,created_at,level,message FROM events WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
    return {"job": _job_dict(row), "events": [dict(x) for x in events]}


@app.get("/api/v1/jobs/{job_id}/result")
def job_result(job_id: str, authorization: str | None = Header(default=None)):
    require_api(authorization)
    with _db() as conn:
        row = conn.execute("SELECT result_path,status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row or row["status"] != "completed" or not row["result_path"]:
        raise HTTPException(404, "Result not ready")
    p = Path(row["result_path"])
    if not p.is_file() or JOBS not in p.parents:
        raise HTTPException(404, "Result unavailable")
    return FileResponse(p, filename=p.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
