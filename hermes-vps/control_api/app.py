from __future__ import annotations

import html
import json
import os
import re
import secrets
import shutil
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
_runtime_uid = getattr(os, "getuid", os.getpid)()
RUNTIME = Path(os.environ.get("UDISE_CONTROL_RUNTIME", Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{_runtime_uid}")) / "udise-control"))
JOBS = STATE / "jobs"
SESSIONS = RUNTIME / "sessions"
REQUESTS = RUNTIME / "session-requests"
ESK_REQUESTS = RUNTIME / "eshiksha-requests"
ESK_CREDENTIAL = RUNTIME / "eshiksha-credential.json"
DB = STATE / "jobs.sqlite3"
CONTROL_TOKEN_FILE = Path(os.environ.get("UDISE_CONTROL_TOKEN_FILE", Path.home() / ".config/udise-control/api-token"))
RUNNER = Path(os.environ.get("UDISE_VPS_RUNNER", Path.home() / ".local/bin/udise-vps"))
SESSION_TTL = 8 * 60 * 60
REQUEST_TTL = 10 * 60
ESK_CREDENTIAL_TTL = 30 * 60
RESULT_TTL = 24 * 60 * 60

for p in (STATE, RUNTIME, JOBS, SESSIONS, REQUESTS, ESK_REQUESTS):
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)

app = FastAPI(title="UDISE Hermes Control API", version="0.2.0")


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
            error TEXT,
            approved_from TEXT,
            approved_at INTEGER,
            max_submissions INTEGER NOT NULL DEFAULT 0
        )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    for name, definition in (
        ("approved_from", "TEXT"),
        ("approved_at", "INTEGER"),
        ("max_submissions", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS jobs_one_approval "
        "ON jobs(approved_from) WHERE approved_from IS NOT NULL"
    )
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


_startup_connection = _db()
_startup_connection.close()


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


class ApprovalIn(BaseModel):
    confirmation: str = Field(min_length=1, max_length=100)
    acknowledge_readback: bool = False
    max_submissions: int = Field(default=1, ge=1, le=500)


def _request_file(directory: Path, token: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", token or ""):
        raise HTTPException(400, "Invalid request token")
    return directory / f"{token}.json"


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
<p>Paste the UDISE Cookie header from your browser's Network panel. It is stored only in protected Oracle runtime storage and is never sent through chat.</p>
<form method="post" action="/session/{html.escape(token)}">
<textarea name="cookie" autocomplete="off" required placeholder="JSESSIONID=...; XSRF-TOKEN=..."></textarea>
<button type="submit">Save temporary session</button></form>
<p><small>The temporary session is protected on the server and expires automatically.</small></p>
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
<h2>Session connected</h2><p>You may now return to the UDISE console or WhatsApp workflow.</p></body></html>""")


@app.post("/api/v1/eshiksha-requests")
def create_eshiksha_request(body: SessionRequestIn, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    _json_write(ESK_REQUESTS / f"{token}.json", {
        "created_at": now, "expires_at": now + REQUEST_TTL,
        "used": False, "ready": False, "return_url": body.return_url or "",
    })
    base = os.environ.get("UDISE_CONTROL_PUBLIC_BASE", "").rstrip("/")
    return {
        "token": token, "expires_in": REQUEST_TTL,
        "entry_url": f"{base}/eshiksha/{token}" if base else f"/eshiksha/{token}",
    }


@app.get("/api/v1/eshiksha-requests/{token}")
def eshiksha_request_status(token: str, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    p = _request_file(ESK_REQUESTS, token)
    if not p.exists():
        raise HTTPException(404, "Not found")
    data = _json_read(p)
    if int(time.time()) > int(data.get("expires_at", 0)):
        raise HTTPException(410, "Expired")
    return {"ready": bool(data.get("ready"))}


@app.get("/eshiksha/{token}", response_class=HTMLResponse)
def eshiksha_form(token: str):
    p = _request_file(ESK_REQUESTS, token)
    if not p.exists():
        raise HTTPException(404, "Link unavailable")
    data = _json_read(p)
    if data.get("used") or int(time.time()) > int(data.get("expires_at", 0)):
        raise HTTPException(410, "Link expired or already used")
    return HTMLResponse(f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>eShikshaKosh Secure Login</title><style>
body{{font-family:system-ui;max-width:620px;margin:24px auto;padding:0 18px;background:#f6f7f9;color:#111}}
.card{{background:#fff;border:1px solid #ddd;border-radius:16px;padding:22px}}
input{{width:100%;box-sizing:border-box;padding:12px;margin:5px 0 11px;border:1px solid #bbb;border-radius:10px;font-size:16px}}
label{{font-weight:650;font-size:13px}}button{{width:100%;padding:13px;border:0;border-radius:10px;background:#111;color:white;font-size:16px}}
small{{color:#666}}</style></head><body><div class="card"><h2>eShikshaKosh Secure Login</h2>
<p>Enter the details required to fetch the read-only OTR source report.</p>
<form method="post" action="/eshiksha/{html.escape(token)}">
<label>UDISE code / username</label><input name="udise" autocomplete="username" required>
<label>Password</label><input name="password" type="password" autocomplete="current-password" required>
<label>Academic year</label><input name="year" value="2026-27" required>
<button type="submit">Use once for preview</button></form>
<p><small>The password is deleted from temporary storage as soon as the EP preview starts.</small></p>
</div></body></html>""")


@app.post("/eshiksha/{token}")
async def eshiksha_submit(token: str, request: Request):
    p = _request_file(ESK_REQUESTS, token)
    if not p.exists():
        raise HTTPException(404, "Link unavailable")
    data = _json_read(p)
    now = int(time.time())
    if data.get("used") or now > int(data.get("expires_at", 0)):
        raise HTTPException(410, "Link expired or already used")
    form = await request.form()
    udise = str(form.get("udise") or "").strip()
    password = str(form.get("password") or "").strip()
    year = str(form.get("year") or "2026-27").strip()
    if not udise or not password or not re.fullmatch(r"\d{4}-\d{2}", year):
        raise HTTPException(400, "UDISE, password and valid year are required")
    _json_write(ESK_CREDENTIAL, {
        "udise": udise, "password": password, "year": year,
        "created_at": now, "expires_at": now + ESK_CREDENTIAL_TTL,
    })
    data.update({"used": True, "ready": True, "used_at": now})
    _json_write(p, data)
    return HTMLResponse("""<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui;max-width:560px;margin:50px auto;padding:20px;text-align:center">
<h2>eShikshaKosh connected</h2><p>Close this panel and generate the EP preview workbook.</p></body></html>""")


def _load_eshiksha_credentials() -> dict:
    if not ESK_CREDENTIAL.exists():
        raise RuntimeError("Connect eShikshaKosh securely before running EP preview")
    data = _json_read(ESK_CREDENTIAL)
    if int(time.time()) > int(data.get("expires_at", 0)):
        ESK_CREDENTIAL.unlink(missing_ok=True)
        raise RuntimeError("eShikshaKosh temporary credentials expired; connect again")
    if not data.get("udise") or not data.get("password"):
        raise RuntimeError("eShikshaKosh temporary credentials are incomplete")
    return data


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
    m = re.search(r"\[SNAPSHOT\]\s+(\d+)/(\d+)\s+", line)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return f"Full snapshot: {a}/{b} students checked", a, b
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


def _cleanup_expired_results() -> None:
    """Remove private job files after 24 hours while retaining job audit rows."""
    cutoff = int(time.time()) - RESULT_TTL
    with _db() as conn:
        rows = conn.execute(
            "SELECT id FROM jobs WHERE updated_at<? AND status IN ('completed','failed')",
            (cutoff,),
        ).fetchall()
        for row in rows:
            job_id = str(row["id"])
            if not re.fullmatch(r"[a-f0-9]{32}", job_id):
                continue
            directory = (JOBS / job_id).resolve()
            if directory.parent != JOBS.resolve():
                continue
            if directory.is_dir():
                shutil.rmtree(directory)
            conn.execute(
                "UPDATE jobs SET result_path=NULL,message=? WHERE id=?",
                ("Temporary result expired after 24 hours", job_id),
            )


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
        is_preview = bool(row["preview"])
        cmd = [str(RUNNER), stage, "--school", row["school"], "--out", str(out_dir)]
        if stage == "completion":
            cmd += ["--class", row["class_name"]]
        elif stage == "gp":
            cmd += ["--class", row["class_name"], "--run-mode", "All students"]
        elif stage == "ep":
            if is_preview:
                eshiksha = _load_eshiksha_credentials()
                cmd += [
                    "--class", row["class_name"], "--fetch-report",
                    "--year", eshiksha.get("year", "2026-27"),
                ]
            else:
                source_dir = JOBS / str(row["approved_from"])
                reports = sorted(source_dir.glob("eShikshaKosh_OTR_*.xlsx"))
                if not reports:
                    raise RuntimeError("Approved eShikshaKosh source report is no longer available; generate a new preview")
                cmd += ["--class", row["class_name"], "--report", str(reports[-1])]
        elif stage == "facility":
            cmd += ["--class", row["class_name"]]
        elif stage == "finalize":
            cmd += ["--class", row["class_name"], "--from-completion"]
        elif stage not in {"students", "snapshot"}:
            raise RuntimeError("This stage is not enabled in the read-only MVP")

        if not is_preview:
            cmd += ["--submit", "--max", str(row["max_submissions"])]

        env = os.environ.copy()
        env["UDISE_COOKIE_HEADER"] = session["cookie"]
        if stage == "ep" and is_preview:
            env["ESHIKSHAKOSH_UDISE"] = eshiksha["udise"]
            env["ESHIKSHAKOSH_PASSWORD"] = eshiksha["password"]
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='running',updated_at=?,message=? WHERE id=?",
                         (int(time.time()), "Starting UDISE job", job_id))
        _event(job_id, "Starting UDISE job")

        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                bufsize=1)
        if stage == "ep" and is_preview:
            ESK_CREDENTIAL.unlink(missing_ok=True)
        report_path = None
        runner_error = None
        assert proc.stdout is not None
        for raw in proc.stdout:
            if raw.startswith("REPORT_READY="):
                report_path = raw.split("=", 1)[1].strip()
            if raw.strip().startswith("ERROR:"):
                runner_error = raw.strip().removeprefix("ERROR:").strip()
            msg, cur, total = _progress_line(raw)
            if msg:
                _event(job_id, msg)
                _update_progress(job_id, cur, total)
        code = proc.wait()
        if code != 0:
            raise RuntimeError(runner_error or f"Runner exited with code {code}")
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
    _cleanup_expired_results()
    caps = get_capabilities()
    stages = {x["id"]: x for x in caps["stages"]}
    stage = stages.get(body.stage)
    if not stage:
        raise HTTPException(400, "Unsupported stage")
    if stage["mode"] != "read" and not (stage.get("preview_enabled") and body.preview):
        raise HTTPException(409, "Actual saves require a separately approved write workflow")
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


def _approval_phrase(stage: str, class_name: str | None) -> str:
    return f"SAVE {stage.upper()} {class_name or 'ALL'}"


@app.post("/api/v1/jobs/{job_id}/approve")
def approve_job(job_id: str, body: ApprovalIn, authorization: str | None = Header(default=None)) -> dict:
    """Create one bounded write job from a completed preview."""
    require_api(authorization)
    _cleanup_expired_results()
    with _db() as conn:
        preview = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not preview:
            raise HTTPException(404, "Preview job not found")
        if preview["status"] != "completed" or not bool(preview["preview"]):
            raise HTTPException(409, "Only a completed preview can be approved")
        stage = next(
            (item for item in get_capabilities()["stages"] if item["id"] == preview["stage"]),
            None,
        )
        if not stage or stage["mode"] != "write":
            raise HTTPException(409, "This job is not an approvable write preview")
        _load_session(preview["session_id"])
        expected = _approval_phrase(preview["stage"], preview["class_name"])
        if not body.acknowledge_readback or not secrets.compare_digest(body.confirmation.strip(), expected):
            raise HTTPException(400, f"Type {expected} and acknowledge fresh read-back")
        if not preview["result_path"] or not Path(preview["result_path"]).is_file():
            raise HTTPException(410, "Preview workbook expired; generate a new preview")
        existing = conn.execute(
            "SELECT id FROM jobs WHERE approved_from=? AND status IN ('queued','running','completed') LIMIT 1",
            (job_id,),
        ).fetchone()
        if existing:
            raise HTTPException(409, "This preview has already been approved")
        if preview["stage"] == "ep" and not list((JOBS / job_id).glob("eShikshaKosh_OTR_*.xlsx")):
            raise HTTPException(410, "eShikshaKosh source expired; generate a new EP preview")
        write_job_id = uuid.uuid4().hex
        now = int(time.time())
        try:
            conn.execute(
                """INSERT INTO jobs(
                       id,created_at,updated_at,status,stage,class_name,school,session_id,
                       preview,message,approved_from,approved_at,max_submissions
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    write_job_id, now, now, "queued", preview["stage"], preview["class_name"],
                    preview["school"], preview["session_id"], 0,
                    "Approved write queued", job_id, now, body.max_submissions,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(409, "This preview has already been approved") from exc
    threading.Thread(target=_run_job, args=(write_job_id,), daemon=True).start()
    return {"job_id": write_job_id, "status": "queued", "max_submissions": body.max_submissions}


def _job_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d.pop("session_id", None)
    d["has_result"] = bool(d.pop("result_path", None))
    return d


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    _cleanup_expired_results()
    with _db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Job not found")
        events = conn.execute("SELECT id,created_at,level,message FROM events WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
    return {"job": _job_dict(row), "events": [dict(x) for x in events]}


@app.get("/api/v1/jobs/{job_id}/result")
def job_result(job_id: str, authorization: str | None = Header(default=None)):
    require_api(authorization)
    _cleanup_expired_results()
    with _db() as conn:
        row = conn.execute("SELECT result_path,status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row or row["status"] != "completed" or not row["result_path"]:
        raise HTTPException(404, "Result not ready")
    p = Path(row["result_path"])
    if not p.is_file() or JOBS not in p.parents:
        raise HTTPException(404, "Result unavailable")
    return FileResponse(p, filename=p.name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
