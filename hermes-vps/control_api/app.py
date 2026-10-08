from __future__ import annotations

import asyncio
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

import requests
from urllib.parse import parse_qs, urlparse
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .capabilities import get_capabilities

ROOT = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("UDISE_CONTROL_STATE", Path.home() / ".hermes/state/udise-control"))
_runtime_uid = getattr(os, "getuid", os.getpid)()
RUNTIME = Path(os.environ.get("UDISE_CONTROL_RUNTIME", Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{_runtime_uid}")) / "udise-control"))
JOBS = STATE / "jobs"
SESSIONS = RUNTIME / "sessions"
REQUESTS = RUNTIME / "session-requests"
LOGIN_REQUESTS = RUNTIME / "login-requests"
ESK_REQUESTS = RUNTIME / "eshiksha-requests"
ESK_CREDENTIAL = RUNTIME / "eshiksha-credential.json"
ESK_UPLOAD = RUNTIME / "eshiksha-upload.xlsx"
ESK_UPLOAD_META = RUNTIME / "eshiksha-upload.json"
DB = STATE / "jobs.sqlite3"
CONTROL_TOKEN_FILE = Path(os.environ.get("UDISE_CONTROL_TOKEN_FILE", Path.home() / ".config/udise-control/api-token"))
RUNNER = Path(os.environ.get("UDISE_VPS_RUNNER", Path.home() / ".local/bin/udise-vps"))
SESSION_TTL = 45 * 60
REQUEST_TTL = 10 * 60
ESK_CREDENTIAL_TTL = 45 * 60
RESULT_TTL = 24 * 60 * 60

for p in (STATE, RUNTIME, JOBS, SESSIONS, REQUESTS, LOGIN_REQUESTS, ESK_REQUESTS):
    p.mkdir(parents=True, exist_ok=True)
    os.chmod(p, 0o700)

app = FastAPI(title="UDISE Hermes Control API", version="0.2.0")
LOGIN_BROWSERS: dict[str, dict[str, Any]] = {}
# Serialize workflows that use the same authenticated UDISE session. The portal
# session is shared, so concurrent runners can invalidate/race each other.
_SESSION_JOB_LOCKS: dict[str, threading.Lock] = {}
_SESSION_JOB_LOCKS_GUARD = threading.Lock()


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
            max_submissions INTEGER NOT NULL DEFAULT 0,
            auto_save INTEGER NOT NULL DEFAULT 0,
            auto_write_job_id TEXT
        )
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    for name, definition in (
        ("approved_from", "TEXT"),
        ("approved_at", "INTEGER"),
        ("max_submissions", "INTEGER NOT NULL DEFAULT 0"),
        ("auto_save", "INTEGER NOT NULL DEFAULT 0"),
        ("auto_write_job_id", "TEXT"),
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

def _check_portal_session(session_id: str, *, extend: bool = False) -> dict:
    """Validate the real SDMS session; optionally refresh only the local idle TTL."""
    import requests
    p = _session_path(session_id)
    data = _load_session(session_id)
    cookie = str(data.get("cookie") or "")
    cookies = {}
    for part in cookie.split(";"):
        name, sep, value = part.strip().partition("=")
        if sep and name:
            cookies[name] = value
    try:
        r = requests.get(
            "https://sdms.udiseplus.gov.in/p0/check-session",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://sdms.udiseplus.gov.in/g0/",
                "User-Agent": "Mozilla/5.0",
                "X-XSRF-TOKEN": str(cookies.get("XSRF-TOKEN") or ""),
                "Cookie": cookie,
            },
            timeout=20,
            allow_redirects=False,
        )
    except Exception as exc:
        raise HTTPException(503, "Could not verify the live UDISE session") from exc
    if r.status_code != 200:
        p.unlink(missing_ok=True)
        raise HTTPException(401, "UDISE portal session is no longer active")
    now = int(time.time())
    if extend:
        data["last_verified_at"] = now
        data["expires_at"] = now + SESSION_TTL
        _json_write(p, data)
    return data


class SessionRequestIn(BaseModel):
    return_url: str | None = None
    session_id: str | None = None

class UdiseLoginSubmitIn(BaseModel):
    username: str
    password: str
    captcha: str

class EshikshaCredentialIn(BaseModel):
    token: str
    udise: str
    password: str
    year: str = "2026-27"
    session_id: str | None = None


class JobIn(BaseModel):
    session_id: str
    school: str = Field(min_length=1, max_length=200)
    stage: str
    class_name: str | None = None
    preview: bool = True
    auto_save: bool = False
    max_submissions: int = Field(default=0, ge=0, le=10000)


class ApprovalIn(BaseModel):
    confirmation: str = Field(min_length=1, max_length=100)
    acknowledge_readback: bool = False
    max_submissions: int = Field(default=1, ge=1, le=500)


def _request_file(directory: Path, token: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,120}", token or ""):
        raise HTTPException(400, "Invalid request token")
    return directory / f"{token}.json"


UDISE_AUTH_BASE = "https://auth.udiseplus.gov.in"
UDISE_LOGIN_START = "https://sdms.udiseplus.gov.in/p0/oauth2/login"

def _dump_cookies(session: requests.Session) -> list[dict[str, str]]:
    return [{
        "name": c.name, "value": c.value, "domain": c.domain or "",
        "path": c.path or "/",
    } for c in session.cookies]

def _restore_http_session(items: list[dict[str, str]]) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    for item in items:
        session.cookies.set(
            str(item.get("name") or ""),
            str(item.get("value") or ""),
            domain=str(item.get("domain") or "") or None,
            path=str(item.get("path") or "/"),
        )
    return session

def _hidden_input(text: str, name: str) -> str:
    escaped = re.escape(name)
    m = re.search(rf'name="{escaped}"[^>]*value="([^"]*)"', text, re.I)
    if not m:
        m = re.search(rf'value="([^"]*)"[^>]*name="{escaped}"', text, re.I)
    return html.unescape(m.group(1)) if m else ""


def _csrf_from_login_html(text: str) -> str:
    value = _hidden_input(text, "_csrf")
    if not value:
        raise RuntimeError("UDISE login page did not provide a CSRF token")
    return value

def _sdms_cookie_header(session: requests.Session) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for c in session.cookies:
        domain = (c.domain or "").lstrip(".").lower()
        if domain and not domain.endswith("sdms.udiseplus.gov.in"):
            continue
        if c.name in seen:
            continue
        seen.add(c.name)
        values.append(f"{c.name}={c.value}")
    return "; ".join(values)


def _login_failure_detail(result: requests.Response) -> str:
    final_url = str(result.url or "")
    query = parse_qs(urlparse(final_url).query, keep_blank_values=True)
    flags = {str(k).lower() for k in query}
    text = result.text or ""
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    plain = re.sub(r"\s+", " ", plain).strip()
    low = plain.lower()

    if "captchaerror" in flags or "invalid captcha" in low:
        return "CAPTCHA incorrect or expired. A fresh CAPTCHA has been loaded."
    if "locked" in flags or "account is locked" in low or "login locked" in low:
        return "UDISE has temporarily locked this login after failed attempts. Try again after the lock period."
    if flags.intersection({"expired", "sessionexpired", "sessioninvalid", "flowwarning"}) or "login page has expired" in low or "link has expired" in low:
        return "UDISE login session expired. A fresh CAPTCHA has been loaded; enter the credentials again."
    if "error" in flags:
        return "UDISE did not accept the username/password for this login attempt."
    if "invalid credential" in low or "invalid username" in low or "incorrect password" in low:
        return "UDISE did not accept the username/password for this login attempt."
    return "UDISE login was not completed. A fresh CAPTCHA has been loaded."


def _login_failure_detail_text(final_url: str, text: str) -> str:
    query = parse_qs(urlparse(final_url).query, keep_blank_values=True)
    flags = {str(k).lower() for k in query}
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    plain = re.sub(r"\s+", " ", plain).strip()
    low = plain.lower()
    if "captchaerror" in flags or "invalid captcha" in low:
        return "CAPTCHA incorrect or expired. A fresh CAPTCHA has been loaded."
    if "locked" in flags or "account is locked" in low or "login locked" in low:
        return "UDISE has temporarily locked this login after failed attempts. Try again after the lock period."
    if flags.intersection({"expired", "sessionexpired", "sessioninvalid", "flowwarning"}) or "login page has expired" in low or "link has expired" in low:
        return "UDISE login session expired. A fresh CAPTCHA has been loaded; enter the credentials again."
    if "error" in flags or "invalid credential" in low or "invalid username" in low or "incorrect password" in low:
        return "UDISE did not accept the username/password for this login attempt."
    return "UDISE login was not completed. A fresh CAPTCHA has been loaded."


def _cookie_header_from_playwright(items: list[dict[str, Any]]) -> tuple[str, dict[str, str]]:
    values: list[str] = []
    by_name: dict[str, str] = {}
    for item in items:
        domain = str(item.get("domain") or "").lstrip(".").lower()
        if domain and not domain.endswith("sdms.udiseplus.gov.in"):
            continue
        name = str(item.get("name") or "")
        value = str(item.get("value") or "")
        if not name or name in by_name:
            continue
        by_name[name] = value
        values.append(f"{name}={value}")
    return "; ".join(values), by_name


def _extract_school_context(value: Any) -> dict[str, str]:
    found: dict[str, str] = {}
    school_keys = {"schoolid", "school_id", "internalschoolid", "schoolpk", "schid", "schoolinternalid"}
    udise_keys = {"udisecode", "schoolcode", "udiseid", "userid", "udiseschcode"}
    name_keys = {"schoolname", "school_name"}
    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            region_type = str(obj.get("regionType") or obj.get("region_type") or "").strip()
            region_id = str(obj.get("userRegionId") or obj.get("user_region_id") or "").strip()
            if region_type == "6" and re.fullmatch(r"\d{6,8}", region_id):
                found.setdefault("school_id", region_id)
                region_name = str(obj.get("userRegion") or obj.get("regionName") or "").strip()
                if region_name:
                    found.setdefault("school_name", region_name)
            for k, v in obj.items():
                nk = re.sub(r"[^a-z0-9_]", "", str(k).lower())
                sv = str(v).strip() if isinstance(v, (str, int)) else ""
                if nk in school_keys and re.fullmatch(r"\d{6,8}", sv):
                    found.setdefault("school_id", sv)
                if nk in udise_keys and re.fullmatch(r"\d{11}", sv):
                    found.setdefault("udise_code", sv)
                if nk in name_keys and sv:
                    found.setdefault("school_name", sv)
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(value)
    return found


async def _close_login_browser(token: str) -> None:
    state = LOGIN_BROWSERS.pop(token, None)
    if not state:
        return
    try:
        await state["context"].close()
    except Exception:
        pass
    try:
        await state["browser"].close()
    except Exception:
        pass
    try:
        await state["playwright"].stop()
    except Exception:
        pass


async def _expire_login_browser(token: str, created_at: int) -> None:
    await asyncio.sleep(REQUEST_TTL + 5)
    state = LOGIN_BROWSERS.get(token)
    if state and int(state.get("created_at", 0)) == created_at:
        await _close_login_browser(token)
        (LOGIN_REQUESTS / f"{token}.png").unlink(missing_ok=True)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "udise-control", "version": app.version}


@app.get("/api/v1/capabilities")
def capabilities() -> dict:
    return get_capabilities()


@app.post("/api/v1/login-requests")
async def create_udise_login_request(authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    playwright = None
    browser = None
    context = None
    try:
        bootstrap_session = requests.Session()
        bootstrap_session.headers.update({"User-Agent": "Mozilla/5.0"})
        bootstrap = await asyncio.to_thread(
            bootstrap_session.get,
            UDISE_LOGIN_START,
            timeout=30,
            allow_redirects=False,
        )
        bootstrap.raise_for_status()
        auth_start = str(bootstrap.headers.get("Location") or "")
        if auth_start.startswith("http://auth.udiseplus.gov.in/"):
            auth_start = "https://" + auth_start[len("http://"):]
        parsed = urlparse(auth_start)
        query = parse_qs(parsed.query)
        if (
            not auth_start.startswith(UDISE_AUTH_BASE + "/oauth2/authorize?")
            or str((query.get("client_id") or [""])[0]) != "udise-sdms-g0"
            or not str((query.get("state") or [""])[0])
        ):
            raise RuntimeError("Students OAuth bootstrap did not provide the expected client/state")

        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        browser_cookies = []
        for cookie in bootstrap_session.cookies:
            browser_cookies.append({
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain or "sdms.udiseplus.gov.in",
                "path": cookie.path or "/",
            })
        if browser_cookies:
            await context.add_cookies(browser_cookies)

        page = await context.new_page()
        await page.goto(auth_start, wait_until="domcontentloaded", timeout=35_000)
        await page.locator("#username").wait_for(state="visible", timeout=15_000)
        await page.locator("#password").wait_for(state="visible", timeout=15_000)
        captcha = page.locator("#captchaImage")
        await captcha.wait_for(state="visible", timeout=15_000)

        final_url = page.url
        final_query = parse_qs(urlparse(final_url).query)
        login_txn_id = await page.locator('input[name="loginTxnId"]').get_attribute("value")
        state = str((final_query.get("state") or [""])[0])
        client_id = str((final_query.get("client_id") or [""])[0])
        if client_id != "udise-sdms-g0" or not login_txn_id or not state:
            raise RuntimeError("Students login page did not provide client/state/loginTxnId")

        captcha_path = LOGIN_REQUESTS / f"{token}.png"
        await captcha.screenshot(path=str(captcha_path))
        os.chmod(captcha_path, 0o600)

        LOGIN_BROWSERS[token] = {
            "created_at": now,
            "playwright": playwright,
            "browser": browser,
            "context": context,
            "page": page,
        }
        _json_write(LOGIN_REQUESTS / f"{token}.json", {
            "created_at": now,
            "expires_at": now + REQUEST_TTL,
            "used": False,
            "browser_backed": True,
            "client_id": client_id,
            "state": state,
            "login_txn_id": login_txn_id,
        })
        asyncio.create_task(_expire_login_browser(token, now))
        return {"token": token, "expires_in": REQUEST_TTL, "mode": "browser"}
    except Exception as exc:
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                await browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                await playwright.stop()
            except Exception:
                pass
        (LOGIN_REQUESTS / f"{token}.png").unlink(missing_ok=True)
        raise HTTPException(502, f"UDISE browser login unavailable: {type(exc).__name__}") from exc


@app.get("/api/v1/login-requests/{token}/captcha")
def udise_login_captcha(token: str, authorization: str | None = Header(default=None)):
    require_api(authorization)
    p = _request_file(LOGIN_REQUESTS, token)
    if not p.exists():
        raise HTTPException(404, "Login request not found")
    data = _json_read(p)
    if int(time.time()) > int(data.get("expires_at", 0)):
        p.unlink(missing_ok=True)
        (LOGIN_REQUESTS / f"{token}.png").unlink(missing_ok=True)
        raise HTTPException(410, "Login request expired")
    captcha_path = LOGIN_REQUESTS / f"{token}.png"
    if not captcha_path.exists():
        raise HTTPException(404, "CAPTCHA unavailable")
    return FileResponse(captcha_path, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/v1/login-requests/{token}/submit")
async def submit_udise_login(
    token: str,
    body: UdiseLoginSubmitIn,
    authorization: str | None = Header(default=None),
) -> dict:
    require_api(authorization)
    p = _request_file(LOGIN_REQUESTS, token)
    if not p.exists():
        raise HTTPException(404, "Login request not found")
    data = _json_read(p)
    now = int(time.time())
    if data.get("used") or now > int(data.get("expires_at", 0)):
        await _close_login_browser(token)
        raise HTTPException(410, "Login request expired or already used")
    if not body.username.strip() or not body.password or not body.captcha.strip():
        raise HTTPException(400, "Username, password and CAPTCHA are required")

    browser_state = LOGIN_BROWSERS.get(token)
    if not browser_state:
        raise HTTPException(410, "Browser login session expired. Refresh CAPTCHA and try again.")

    page = browser_state["page"]
    context = browser_state["context"]
    try:
        await page.locator("#username").fill(body.username.strip())
        await page.locator("#password").fill(body.password)
        await page.locator('input[name="captchaMode"][value="image"]').check()
        await page.locator('input[name="captcha"]').fill(body.captcha.strip())
        try:
            async with page.expect_navigation(wait_until="domcontentloaded", timeout=45_000):
                await page.locator("#loginBtn").click()
        except PlaywrightTimeoutError:
            await page.wait_for_timeout(1_000)

        final_url = page.url
        page_html = await page.content()
        items = await context.cookies()
        cookie, cookies = _cookie_header_from_playwright(items)

        authenticated = False
        if "JSESSIONID=" in cookie and "XSRF-TOKEN=" in cookie:
            try:
                check = await context.request.get(
                    "https://sdms.udiseplus.gov.in/p0/check-session",
                    headers={
                        "Accept": "application/json, text/plain, */*",
                        "Referer": "https://sdms.udiseplus.gov.in/p0/",
                        "X-XSRF-TOKEN": str(cookies.get("XSRF-TOKEN") or ""),
                    },
                    timeout=20_000,
                    max_redirects=0,
                )
                authenticated = check.status == 200
            except Exception:
                authenticated = False

        if not authenticated:
            detail = _login_failure_detail_text(final_url, page_html)
            data.update({"used": True, "failed_at": now, "failure": detail})
            _json_write(p, data)
            await _close_login_browser(token)
            (LOGIN_REQUESTS / f"{token}.png").unlink(missing_ok=True)
            raise HTTPException(401, detail)

        school_context: dict[str, str] = {}
        try:
            user_response = await context.request.get(
                "https://sdms.udiseplus.gov.in/p0/api/user",
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://sdms.udiseplus.gov.in/g0/",
                    "X-XSRF-TOKEN": str(cookies.get("XSRF-TOKEN") or ""),
                },
                timeout=20_000,
                max_redirects=0,
            )
            if user_response.status == 200:
                user_json = await user_response.json()
                school_context.update(_extract_school_context(user_json))
                school_id = school_context.get("school_id")
                if school_id:
                    try:
                        school_response = await context.request.get(
                            f"https://sdms.udiseplus.gov.in/p0/api/v2/school/school-details/{school_id}",
                            headers={
                                "Accept": "application/json, text/plain, */*",
                                "Referer": "https://sdms.udiseplus.gov.in/g0/",
                                "X-XSRF-TOKEN": str(cookies.get("XSRF-TOKEN") or ""),
                            },
                            timeout=20_000,
                            max_redirects=0,
                        )
                        if school_response.status == 200:
                            school_json = await school_response.json()
                            school_context.update({
                                k: v for k, v in _extract_school_context(school_json).items()
                                if v
                            })
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            storage = await page.evaluate("""() => {
              const out = {};
              for (const store of [localStorage, sessionStorage]) {
                for (let i = 0; i < store.length; i++) {
                  const k = store.key(i);
                  if (k) out[k] = store.getItem(k);
                }
              }
              return out;
            }""")
            school_context.update({
                k: v for k, v in _extract_school_context(storage).items()
                if k not in school_context
            })
        except Exception:
            pass

        sid = secrets.token_urlsafe(32)
        session_record = {
            "cookie": cookie,
            "created_at": now,
            "expires_at": now + SESSION_TTL,
        }
        session_record.update(school_context)
        _json_write(SESSIONS / f"{sid}.json", session_record)
        data.update({"used": True, "ready": True, "session_id": sid, "used_at": now})
        data.update(school_context)
        _json_write(p, data)
        await _close_login_browser(token)
        (LOGIN_REQUESTS / f"{token}.png").unlink(missing_ok=True)
        return {
            "ready": True,
            "session_id": sid,
            "expires_in": SESSION_TTL,
            "mode": "browser",
            "school_id": school_context.get("school_id"),
            "school_name": school_context.get("school_name"),
            "udise_code": school_context.get("udise_code"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        await _close_login_browser(token)
        (LOGIN_REQUESTS / f"{token}.png").unlink(missing_ok=True)
        raise HTTPException(502, f"UDISE browser login failed: {type(exc).__name__}") from exc


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


@app.get("/api/v1/sessions/{session_id}/status")
def session_status(session_id: str, refresh: bool = False, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    data = _check_portal_session(session_id, extend=refresh)
    now = int(time.time())
    return {
        "active": True,
        "expires_in": max(0, int(data.get("expires_at", now)) - now),
        "last_verified_at": int(data.get("last_verified_at") or now),
        "school_name": data.get("school_name", ""),
        "udise_code": data.get("udise_code", ""),
    }


@app.post("/api/v1/eshiksha-requests")
def create_eshiksha_request(body: SessionRequestIn, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    if body.session_id:
        _load_session(body.session_id)
    _json_write(ESK_REQUESTS / f"{token}.json", {
        "created_at": now, "expires_at": now + REQUEST_TTL,
        "used": False, "ready": False, "return_url": body.return_url or "",
        "session_id": body.session_id or "",
    })
    base = os.environ.get("UDISE_CONTROL_PUBLIC_BASE", "").rstrip("/")
    return {
        "token": token, "expires_in": REQUEST_TTL,
        "entry_url": f"{base}/eshiksha/{token}" if base else f"/eshiksha/{token}",
    }

@app.post("/api/v1/eshiksha-credentials")
def save_eshiksha_credentials(body: EshikshaCredentialIn, authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    p = _request_file(ESK_REQUESTS, body.token)
    if not p.exists():
        raise HTTPException(404, "eShikshaKosh request not found")
    data = _json_read(p)
    now = int(time.time())
    if data.get("used") or now > int(data.get("expires_at", 0)):
        raise HTTPException(410, "Link expired or already used")
    if not body.udise.strip() or not body.password.strip() or not re.fullmatch(r"\d{4}-\d{2}", body.year):
        raise HTTPException(400, "UDISE, password and valid year are required")
    bound_session = body.session_id or data.get("session_id") or ""
    session_data = _load_session(bound_session) if bound_session else {}
    from udise_vps.esk import verify_credentials
    try:
        verified = verify_credentials(udise=body.udise.strip(), password=body.password, year=body.year)
    except Exception as exc:
        raise HTTPException(401, str(exc)[:500]) from exc
    expires_at = min(
        now + ESK_CREDENTIAL_TTL,
        int(session_data.get("expires_at") or now + ESK_CREDENTIAL_TTL),
    )
    _json_write(ESK_CREDENTIAL, {
        "udise": body.udise.strip(),
        "password": body.password,
        "year": body.year,
        "created_at": now,
        "expires_at": expires_at,
        "session_id": bound_session,
        "verified": True,
        "school_name": verified.get("school_name", ""),
        "school_id": verified.get("school_id", ""),
        "student_count": verified.get("student_count", 0),
    })
    ESK_UPLOAD.unlink(missing_ok=True)
    ESK_UPLOAD_META.unlink(missing_ok=True)
    data.update({
        "used": True,
        "ready": True,
        "used_at": now,
        "school_name": verified.get("school_name", ""),
        "udise": verified.get("udise", body.udise.strip()),
    })
    _json_write(p, data)
    return {
        "ready": True,
        "verified": True,
        "school_name": verified.get("school_name", ""),
        "udise": verified.get("udise", body.udise.strip()),
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
    credential = _json_read(ESK_CREDENTIAL) if ESK_CREDENTIAL.exists() else {}
    bound_session = str(data.get("session_id") or "")
    credential_available = bool(
        credential
        and credential.get("verified")
        and (not bound_session or credential.get("session_id") == bound_session)
        and int(time.time()) <= int(credential.get("expires_at", 0))
    )
    report_meta = _json_read(ESK_UPLOAD_META) if ESK_UPLOAD_META.exists() else {}
    report_available = ESK_UPLOAD.exists() and (
        not bound_session or report_meta.get("session_id") in {"", bound_session}
    )
    return {
        "ready": bool(data.get("ready")) and credential_available,
        "verified": credential_available,
        "credential_available": credential_available,
        "report_available": report_available,
        "school_name": credential.get("school_name", "") if credential_available else "",
        "udise": credential.get("udise", "") if credential_available else "",
    }


@app.post("/api/v1/eshiksha-upload")
async def eshiksha_upload(file: UploadFile = File(...), authorization: str | None = Header(default=None)) -> dict:
    require_api(authorization)
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Upload an Excel eShikshaKosh report (.xlsx or .xls)")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Report is larger than the 20 MB limit")
    ESK_UPLOAD.write_bytes(data)
    os.chmod(ESK_UPLOAD, 0o600)
    _json_write(ESK_UPLOAD_META, {"created_at": int(time.time()), "session_id": "", "source": "upload"})
    return {"ready": True, "report_available": True}


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
    from udise_vps.esk import verify_credentials
    try:
        verified = verify_credentials(udise=udise, password=password, year=year)
    except Exception as exc:
        raise HTTPException(401, str(exc)[:500]) from exc
    bound_session = str(data.get("session_id") or "")
    session_data = _load_session(bound_session) if bound_session else {}
    expires_at = min(
        now + ESK_CREDENTIAL_TTL,
        int(session_data.get("expires_at") or now + ESK_CREDENTIAL_TTL),
    )
    _json_write(ESK_CREDENTIAL, {
        "udise": udise,
        "password": password,
        "year": year,
        "created_at": now,
        "expires_at": expires_at,
        "session_id": bound_session,
        "verified": True,
        "school_name": verified.get("school_name", ""),
        "school_id": verified.get("school_id", ""),
        "student_count": verified.get("student_count", 0),
    })
    data.update({
        "used": True,
        "ready": True,
        "used_at": now,
        "school_name": verified.get("school_name", ""),
        "udise": verified.get("udise", udise),
    })
    _json_write(p, data)
    school_name = html.escape(str(verified.get("school_name") or "eShikshaKosh school"))
    return HTMLResponse(f"""<!doctype html><html><meta name="viewport" content="width=device-width,initial-scale=1">
<body style="font-family:system-ui;max-width:560px;margin:50px auto;padding:20px;text-align:center">
<h2>eShikshaKosh connected</h2><p>Login verified for <strong>{school_name}</strong>. Close this panel and return to Enrollment Profile.</p></body></html>""")


def _load_eshiksha_credentials(session_id: str | None = None) -> dict:
    if not ESK_CREDENTIAL.exists():
        raise RuntimeError("Connect eShikshaKosh securely before running EP preview")
    data = _json_read(ESK_CREDENTIAL)
    if int(time.time()) > int(data.get("expires_at", 0)):
        ESK_CREDENTIAL.unlink(missing_ok=True)
        raise RuntimeError("eShikshaKosh temporary credentials expired; connect again")
    if not data.get("verified"):
        raise RuntimeError("eShikshaKosh login has not been verified")
    if session_id and data.get("session_id") != session_id:
        raise RuntimeError("eShikshaKosh belongs to a different UDISE session; connect again")
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
    gp = re.search(r"📋 GP(?:_APPROVED)?_RESULT status=(\\S+) pen=(\\S+) name=(.*?) detail=(.*)$", line)
    if gp:
        status, pen, name, detail = gp.groups()
        labels = {
            "NO_CHANGE": "Skipped",
            "SKIPPED_CWSN": "Skipped",
            "SKIPPED_CWSN_UNEXPECTED": "Skipped",
            "SUCCESS_CONFIRMED": "Saved + confirmed",
            "FAILED": "Failed",
            "UNCONFIRMED": "Not confirmed",
            "READ_ERROR": "Skipped",
            "PREVIEW": "Eligible",
            "LIMIT_REACHED": "Skipped",
            "CWSN_CONFIRM_REQUIRED": "Confirmation required",
        }
        label = labels.get(status, status.replace("_", " ").title())
        return f"GP-UPDATE: {pen} - {name} - {label} - {detail}", None, None
    m = re.search(r"scope:\s*([A-Za-z ]+)\s*\|\s*(\d+)\s+student", line, re.I)
    if m:
        return f"{line}", 0, int(m.group(2))
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
    if any(k in line for k in ("Completed", "Ready to Complete", "Need FP", "Need EP + FP", "Need GP + EP + FP", "Read failures", "Saved + confirmed", "No change needed", "Nothing to fill", "Preview only", "Skipped / other", "Other", "eShikshaKosh", "EP_APPROVED_RESULT", "EP approved plan", "EP approved outcome", "GP_APPROVED_RESULT", "GP_RESULT", "GP approved plan", "GP approved outcome", "FP_RESULT", "FP outcome", "FINALIZE_RESULT", "FINALIZE outcome", "GP_CWSN_CONFIRM_REQUIRED", "SNAPSHOT_RESULT", "ROSTER_STUDENT", "report rows", "scope:", "pending=", "students=")):
        return re.sub(r"\s+", " ", line), None, None
    return None, None, None


def _update_progress(job_id: str, current: int | None, total: int | None) -> None:
    if current is None and total is None:
        return
    with _db() as conn:
        conn.execute("UPDATE jobs SET progress_current=COALESCE(?,progress_current), progress_total=COALESCE(?,progress_total), updated_at=? WHERE id=?",
                     (current, total, int(time.time()), job_id))


def _result_table_message(job_id: str, stage: str, awaiting_confirmation: bool = False) -> str:
    """Build a compact machine-readable final message for the operator UI."""
    with _db() as conn:
        rows = conn.execute("SELECT message FROM events WHERE job_id=? ORDER BY id", (job_id,)).fetchall()
    messages = [str(row["message"] or "") for row in rows]
    counts: dict[str, int] = {}
    patterns = {
        "gp": r"GP(?:_APPROVED)?_RESULT status=([A-Z0-9_]+)",
        "ep": r"EP(?:_APPROVED)?_RESULT status=([A-Z0-9_]+)",
        "facility": r"FP_RESULT status=([A-Z0-9_]+)",
        "finalize": r"FINALIZE_RESULT status=([A-Z0-9_]+)",
        "snapshot": r"SNAPSHOT_RESULT status=([A-Z0-9_]+)",
    }
    pattern = patterns.get(stage)
    if pattern:
        for message in messages:
            match = re.search(pattern, message)
            if match:
                status = match.group(1)
                counts[status] = counts.get(status, 0) + 1
    labels = {
        "SUCCESS_CONFIRMED": "Saved + confirmed",
        "SUCCESS_CONFIRMED_AFTER_POST_ERROR": "Saved + confirmed",
        "NO_CHANGE": "Skipped",
        "SKIPPED_ALREADY_UP_TO_DATE": "Skipped",
        "SKIPPED_CWSN": "Skipped",
        "SKIPPED_CWSN_UNEXPECTED": "Skipped",
        "SKIPPED_NOT_IN_APPROVED_PLAN": "Skipped",
        "SKIPPED_STATE_CHANGED": "Skipped",
        "LIMIT_REACHED": "Skipped",
        "MANUAL_REVIEW": "Manual review",
        "FAILED": "Failed",
        "UNCONFIRMED": "Not confirmed",
        "READ_ERROR": "Read error",
        "CWSN_CONFIRM_REQUIRED": "Confirmation required",
        "PREVIEW": "Eligible",
    }
    grouped: dict[str, int] = {}
    for status, count in counts.items():
        label = labels.get(status, status.replace("_", " ").title())
        grouped[label] = grouped.get(label, 0) + count
    if awaiting_confirmation:
        return (
            "RESULT_TABLE\n"
            "Status|Count\n"
            f"Confirmation required|{sum(counts.values())}\n"
            "Action|Review listed students and confirm CWSN=No"
        )
    if not grouped:
        return "RESULT_TABLE\nStatus|Count\nCompleted|1"
    lines = ["RESULT_TABLE", "Status|Count"]
    for label, count in grouped.items():
        lines.append(f"{label}|{count}")
    return "\n".join(lines)


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


def _queue_automatic_write(preview_job_id: str) -> str:
    """Queue the durable write half of an authorized one-click workflow.

    The browser is not the approval authority. `auto_save` is set only by the
    production one-click UI; the API records the preview as the parent and
    creates exactly one bounded write child. The normal approve endpoint remains
    available as a recovery/manual path.
    """
    with _db() as conn:
        preview = conn.execute("SELECT * FROM jobs WHERE id=?", (preview_job_id,)).fetchone()
        if not preview:
            raise RuntimeError("Preview job disappeared before automatic save")
        if preview["status"] not in {"completed", "awaiting_confirmation"} or not bool(preview["preview"]):
            raise RuntimeError("Automatic save requires a completed preview or an explicitly confirmed GP CWSN preview")
        if preview["stage"] == "gp" and preview["status"] == "awaiting_confirmation":
            pending_path = JOBS / preview_job_id / "cwsn-pending.json"
            if pending_path.is_file() and _json_read(pending_path):
                raise RuntimeError("GP CWSN confirmation is still pending")
        stage = next((item for item in get_capabilities()["stages"] if item["id"] == preview["stage"]), None)
        if not stage or stage["mode"] != "write":
            raise RuntimeError("Automatic save is only available for write workflows")
        if not preview["result_path"] or not Path(preview["result_path"]).is_file():
            raise RuntimeError("Preview workbook is unavailable for automatic save")
        existing = conn.execute(
            "SELECT id FROM jobs WHERE approved_from=? LIMIT 1", (preview_job_id,)
        ).fetchone()
        if existing:
            return str(existing["id"])
        if preview["stage"] == "ep" and not list((JOBS / preview_job_id).glob("eShikshaKosh_OTR_*.xlsx")) and str(preview["class_name"]).upper() != "X":
            raise RuntimeError("eShikshaKosh source is unavailable for automatic EP save; generate a new preview")
        # An empty approved plan means the preview found no eligible changes.
        # Do not manufacture a write child that will mark every student as
        # SKIPPED_NOT_IN_APPROVED_PLAN; that is misleading and produces the
        # old "Skipped / other" count for a genuinely no-op preview.
        plan_path = JOBS / preview_job_id / "approved-plan.json"
        if preview["stage"] in {"gp", "ep"} and plan_path.is_file():
            plan = _json_read(plan_path)
            if not isinstance(plan, dict) or not plan:
                _event(preview_job_id, "ℹ️ No eligible changes in the approved preview plan; no write job was created.")
                with _db() as conn:
                    conn.execute("UPDATE jobs SET updated_at=?,message=? WHERE id=?", (int(time.time()), "Completed — no changes to save.", preview_job_id))
                return ""
        write_job_id = uuid.uuid4().hex
        now = int(time.time())
        conn.execute(
            """INSERT INTO jobs(
                   id,created_at,updated_at,status,stage,class_name,school,session_id,
                   preview,message,approved_from,approved_at,max_submissions,auto_save
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                write_job_id, now, now, "queued", preview["stage"], preview["class_name"],
                preview["school"], preview["session_id"], 0,
                "Authorized automatic save queued", preview_job_id, now, int(preview["max_submissions"] if preview["max_submissions"] is not None else 0), 0,
            ),
        )
        conn.execute(
            "UPDATE jobs SET auto_write_job_id=?,updated_at=? WHERE id=?",
            (write_job_id, now, preview_job_id),
        )
    _event(preview_job_id, "🔐 Preview complete; authorized automatic save queued. Browser connection is no longer required.")
    if preview["stage"] == "gp":
        plan = _json_read(JOBS / preview_job_id / "approved-plan.json") if (JOBS / preview_job_id / "approved-plan.json").is_file() else {}
        if isinstance(plan, dict):
            for item in plan.values():
                changes = item.get("changes") if isinstance(item, dict) else {}
                if isinstance(changes, dict) and str(changes.get("cwsnYN")) == "2":
                    _event(
                        write_job_id,
                        f"GP-UPDATE: {str(item.get('pen') or '')} - {str(item.get('name') or '')} - Father: {str(item.get('father_name') or 'Not available')} - Confirmed CWSN=No - Saving and verifying",
                    )
    threading.Thread(target=_run_job, args=(write_job_id,), daemon=True).start()
    return write_job_id


def _run_job_unlocked(job_id: str) -> None:
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
        eshiksha = None
        cmd = [str(RUNNER), stage, "--school", row["school"], "--out", str(out_dir)]
        if stage == "completion":
            cmd += ["--class", row["class_name"]]
        elif stage == "snapshot":
            # Full Snapshot is class-scoped in the UI/API. Always forward the
            # selected class; otherwise the CLI defaults to the full roster,
            # and an earlier wrapper path could accidentally run its default
            # IX scope when Class X was requested.
            cmd += ["--class", row["class_name"]]
        elif stage == "gp":
            cmd += ["--class", row["class_name"], "--run-mode", "All students"]
            if is_preview:
                cmd += ["--plan-out", str(out_dir / "approved-plan.json")]
            else:
                plan_path = JOBS / str(row["approved_from"]) / "approved-plan.json"
                if not plan_path.is_file():
                    raise RuntimeError("Approved GP write plan is unavailable; generate a new preview")
                cmd += ["--plan", str(plan_path)]
        elif stage == "ep":
            ep_class = str(row["class_name"] or "").upper()
            if is_preview:
                report_meta = _json_read(ESK_UPLOAD_META) if ESK_UPLOAD_META.exists() else {}
                if ESK_UPLOAD.exists() and report_meta.get("session_id") in {"", row["session_id"]}:
                    # Keep a job-scoped copy so the exact source used for this
                    # preview survives into the separately approved write job.
                    job_report = out_dir / "eShikshaKosh_OTR_ALL.xlsx"
                    shutil.copy2(ESK_UPLOAD, job_report)
                    os.chmod(job_report, 0o600)
                    cmd += ["--class", ep_class, "--report", str(job_report)]
                elif ep_class == "X":
                    cmd += ["--class", ep_class]
                else:
                    eshiksha = _load_eshiksha_credentials(row["session_id"])
                    cmd += ["--class", ep_class, "--fetch-report", "--year", eshiksha.get("year", "2026-27")]
                cmd += ["--plan-out", str(out_dir / "approved-plan.json")]
            else:
                source_dir = JOBS / str(row["approved_from"])
                plan_path = source_dir / "approved-plan.json"
                if not plan_path.is_file():
                    raise RuntimeError("Approved EP write plan is unavailable; generate a new preview")
                cmd += ["--plan", str(plan_path)]
                reports = sorted(source_dir.glob("eShikshaKosh_OTR_*.xlsx"))
                if reports:
                    cmd += ["--class", ep_class, "--report", str(reports[-1])]
                elif ep_class == "X":
                    cmd += ["--class", ep_class]
                else:
                    raise RuntimeError("Approved eShikshaKosh source report is no longer available; generate a new preview")
        elif stage == "facility":
            cmd += ["--class", row["class_name"]]
            if is_preview:
                cmd += ["--plan-out", str(out_dir / "approved-plan.json")]
            else:
                plan_path = JOBS / str(row["approved_from"]) / "approved-plan.json"
                if not plan_path.is_file():
                    raise RuntimeError("Approved Facility write plan is unavailable; generate a new preview")
                cmd += ["--plan", str(plan_path)]
        elif stage == "finalize":
            cmd += ["--class", row["class_name"], "--from-completion"]
        elif stage not in {"students", "snapshot"}:
            raise RuntimeError("This stage is not enabled in the read-only MVP")

        if not is_preview:
            cmd += ["--submit", "--max", str(row["max_submissions"])]

        env = os.environ.copy()
        env["UDISE_COOKIE_HEADER"] = session["cookie"]
        if stage == "ep" and is_preview and eshiksha:
            env["ESHIKSHAKOSH_UDISE"] = eshiksha["udise"]
            env["ESHIKSHAKOSH_PASSWORD"] = eshiksha["password"]
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='running',updated_at=?,message=? WHERE id=?",
                         (int(time.time()), "Starting UDISE job", job_id))
        _event(job_id, "Starting UDISE job")
        if row["class_name"] and stage != "students":
            _event(job_id, f"Scope locked to Class {row['class_name']}; only matching students will be processed.")

        _check_portal_session(row["session_id"], extend=True)
        proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                bufsize=1)
        heartbeat_stop = threading.Event()
        heartbeat_state = {"expired": False}
        def _job_keepalive() -> None:
            while not heartbeat_stop.wait(180):
                try:
                    _check_portal_session(row["session_id"], extend=True)
                except HTTPException as exc:
                    if exc.status_code == 401:
                        heartbeat_state["expired"] = True
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        break
                except Exception:
                    pass
        heartbeat_thread = threading.Thread(target=_job_keepalive, daemon=True)
        heartbeat_thread.start()
        report_path = None
        runner_error = None
        runner_tail: list[str] = []
        assert proc.stdout is not None
        for raw in proc.stdout:
            clean_raw = raw.strip()
            if clean_raw:
                runner_tail.append(clean_raw)
                if len(runner_tail) > 20:
                    runner_tail.pop(0)
            if raw.startswith("REPORT_READY="):
                report_path = raw.split("=", 1)[1].strip()
            if raw.strip().startswith("ERROR:"):
                runner_error = raw.strip().removeprefix("ERROR:").strip()
            msg, cur, total = _progress_line(raw)
            if msg:
                _event(job_id, msg)
                _update_progress(job_id, cur, total)
        code = proc.wait()
        heartbeat_stop.set()
        if code != 0:
            if heartbeat_state.get("expired"):
                raise RuntimeError("UDISE portal session expired during the workflow. No blind retry was attempted.")
            if code == -15:
                raise RuntimeError("Runner was stopped before completion (SIGTERM); no remaining students were written.")
            if runner_error:
                raise RuntimeError(runner_error)
            tail = " | ".join(runner_tail[-8:])
            tail = re.sub(r"(?:Bearer\s+)[A-Za-z0-9._-]+", "Bearer [redacted]", tail)
            tail = re.sub(r"[A-Za-z0-9_-]{32,}", "[redacted]", tail)[:1200]
            raise RuntimeError(f"Runner exited with code {code}" + (f"; last output: {tail}" if tail else ""))
        if report_path and Path(report_path).is_file():
            rp = str(Path(report_path).resolve())
        else:
            files = sorted(out_dir.glob("*.xlsx"))
            rp = str(files[-1].resolve()) if files else None
        if stage == "ep" and is_preview and eshiksha:
            ESK_CREDENTIAL.unlink(missing_ok=True)
            _event(job_id, "eShikshaKosh source fetched and attached to this EP preview; temporary password discarded.")
        # GP/EP approval depends on the exact plan produced by the preview.
        # Never mark such a preview completed (or queue a write child) if the
        # plan artifact was not actually persisted by the runner.
        if is_preview and stage in {"gp", "ep"}:
            plan_path = out_dir / "approved-plan.json"
            if not plan_path.is_file():
                raise RuntimeError(
                    f"{stage.upper()} preview completed without approved-plan.json; no write job was queued"
                )
            plan = _json_read(plan_path)
            if not isinstance(plan, dict):
                raise RuntimeError(f"{stage.upper()} approved plan is invalid JSON; no write job was queued")
        pending_cwsn = out_dir / "cwsn-pending.json"
        pending_data = _json_read(pending_cwsn) if pending_cwsn.is_file() else {}
        cwsn_waiting = bool(is_preview and stage == "gp" and isinstance(pending_data, dict) and pending_data)
        with _db() as conn:
            scoped_total = conn.execute("SELECT progress_total FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            final_status = "awaiting_confirmation" if cwsn_waiting else "completed"
            final_message = _result_table_message(job_id, stage, awaiting_confirmation=cwsn_waiting)
            conn.execute("UPDATE jobs SET status=?,updated_at=?,message=?,result_path=? WHERE id=?",
                         (final_status, int(time.time()), final_message, rp, job_id))
        if scoped_total:
            _update_progress(job_id, scoped_total, scoped_total)
        if cwsn_waiting:
            _event(
                job_id,
                f"GP-UPDATE: CWSN confirmation required for {len(pending_data)} student(s). Review PEN, Name and Father's Name before continuing.",
            )
            for item in pending_data.values():
                _event(
                    job_id,
                    f"GP-UPDATE: {str(item.get('pen') or '')} - {str(item.get('name') or '')} - Father: {str(item.get('father_name') or 'Not available')} - Confirmation required - CWSN=Yes",
                )
        else:
            _event(job_id, "Completed successfully — review saved, skipped/already-filled, and other counts above.")
        if is_preview and bool(row["auto_save"]) and stage in {"gp", "ep", "facility", "finalize"} and not cwsn_waiting:
            try:
                _queue_automatic_write(job_id)
            except Exception as auto_exc:
                safe_auto = re.sub(r"[A-Za-z0-9_-]{24,}", "[redacted]", str(auto_exc))[:500]
                _event(job_id, f"FAILURE · Component: {stage.upper()} Automatic Save · Operation: queue write · Detail: {safe_auto}", "error")
    except Exception as exc:
        safe = re.sub(r"[A-Za-z0-9_-]{24,}", "[redacted]", str(exc))[:500]
        stage_label = str(row["stage"] or "unknown").upper()
        component = {
            "students": "UDISE Student Roster",
            "snapshot": "UDISE Snapshot Runner",
            "gp": "UDISE General Profile Runner",
            "ep": "UDISE Enrollment Profile Runner",
            "facility": "UDISE Facility Profile Runner",
            "completion": "UDISE Completion Runner",
            "finalize": "UDISE Finalize Runner",
        }.get(str(row["stage"]), "Workflow Runner")
        if str(row["stage"]) == "ep" and bool(row["preview"]) and eshiksha:
            component = "eShikshaKosh Source Fetch / EP Runner"
        operation = "preview" if bool(row["preview"]) else "approved write"
        diagnostic = f"FAILURE · Component: {component} · Stage: {stage_label} · Operation: {operation} · Detail: {safe}"
        with _db() as conn:
            conn.execute("UPDATE jobs SET status='failed',updated_at=?,message=?,error=? WHERE id=?",
                         (int(time.time()), diagnostic, diagnostic, job_id))
        _event(job_id, diagnostic, "error")


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
    if body.stage == "ep" and body.preview and str(body.class_name or "").upper() != "X":
        report_meta = _json_read(ESK_UPLOAD_META) if ESK_UPLOAD_META.exists() else {}
        matching_report = ESK_UPLOAD.exists() and report_meta.get("session_id") in {"", body.session_id}
        if not matching_report:
            try:
                _load_eshiksha_credentials(body.session_id)
            except RuntimeError as exc:
                raise HTTPException(409, str(exc)) from exc
    if stage.get("requires_class"):
        if not body.class_name or body.class_name not in stage["classes"]:
            raise HTTPException(400, "Select a supported class")
    session_data = _load_session(body.session_id)
    effective_school = str(session_data.get("school_id") or body.school).strip()
    if not effective_school:
        raise HTTPException(409, "Authenticated school scope could not be detected. Sign in again or use Advanced fallback.")
    job_id = uuid.uuid4().hex
    now = int(time.time())
    with _db() as conn:
        conn.execute("""INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,approved_from,approved_at,max_submissions,auto_save)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                     (job_id, now, now, "queued", body.stage, body.class_name, effective_school,
                      body.session_id, 1, "Queued", None, None, int(body.max_submissions), int(bool(body.auto_save))))
    threading.Thread(target=_run_job, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": "queued"}


def _approval_phrase(stage: str, class_name: str | None) -> str:
    return f"SAVE {stage.upper()} {class_name or 'ALL'}"


def _run_job(job_id: str) -> None:
    """Run one workflow at a time per authenticated UDISE session."""
    with _SESSION_JOB_LOCKS_GUARD:
        lock = _SESSION_JOB_LOCKS.setdefault(str(job_id and _job_session_id(job_id)), threading.Lock())
    lock.acquire()
    try:
        _run_job_unlocked(job_id)
    finally:
        lock.release()


def _job_session_id(job_id: str) -> str:
    with _db() as conn:
        row = conn.execute("SELECT session_id FROM jobs WHERE id=?", (job_id,)).fetchone()
    return str(row[0]) if row else str(job_id)


@app.post("/api/v1/jobs/{job_id}/confirm-cwsn")
def confirm_cwsn(job_id: str, authorization: str | None = Header(default=None)) -> dict:
    """Explicitly authorize changing the pending CWSN=Yes records to No."""
    require_api(authorization)
    with _db() as conn:
        preview = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not preview:
        raise HTTPException(404, "Preview job not found")
    if preview["stage"] != "gp" or not bool(preview["preview"]) or preview["status"] != "awaiting_confirmation":
        raise HTTPException(409, "Only a completed GP preview can receive CWSN confirmation")
    pending_path = JOBS / job_id / "cwsn-pending.json"
    plan_path = JOBS / job_id / "approved-plan.json"
    if not pending_path.is_file():
        raise HTTPException(409, "No pending CWSN confirmations are waiting")
    pending = _json_read(pending_path)
    if not isinstance(pending, dict) or not pending:
        raise HTTPException(409, "No pending CWSN confirmations are waiting")
    plan = _json_read(plan_path) if plan_path.is_file() else {}
    if not isinstance(plan, dict):
        plan = {}
    for key, item in pending.items():
        changes = dict(item.get("changes") or {})
        changes["cwsnYN"] = 2
        plan[key] = {
            "pen": str(item.get("pen") or ""),
            "student_id": str(item.get("student_id") or ""),
            "name": str(item.get("name") or ""),
            "father_name": str(item.get("father_name") or ""),
            "changes": changes,
        }
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending_path.unlink(missing_ok=True)
    _event(job_id, f"GP-UPDATE: CWSN confirmation received for {len(pending)} student(s). Confirmed CWSN=No; verified GP save is being queued.")
    try:
        write_job_id = _queue_automatic_write(job_id)
    except Exception as exc:
        raise HTTPException(500, f"Could not queue the confirmed GP save: {exc}") from exc
    return {"job_id": job_id, "write_job_id": write_job_id, "confirmed": len(pending)}


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
        if preview["stage"] == "gp":
            pending_path = JOBS / job_id / "cwsn-pending.json"
            if pending_path.is_file() and _json_read(pending_path):
                raise HTTPException(409, "CWSN confirmation is required before this GP preview can be approved")
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

@app.get("/api/v1/jobs/{job_id}/eshiksha-report")
def eshiksha_report_result(job_id: str, authorization: str | None = Header(default=None)):
    require_api(authorization)
    with _db() as conn:
        row = conn.execute("SELECT stage,status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row or row["stage"] != "ep" or row["status"] != "completed":
        raise HTTPException(404, "eShikshaKosh report not ready")
    reports = sorted((JOBS / job_id).glob("eShikshaKosh_OTR_*.xlsx"))
    if not reports:
        raise HTTPException(404, "This EP run used an uploaded report or no source report was retained")
    return FileResponse(reports[-1], filename=reports[-1].name, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.get("/api/v1/eshiksha-preview")
def eshiksha_preview(session_id: str | None = None, authorization: str | None = Header(default=None)):
    """Return a safe browser preview of the retained eShikshaKosh source workbook."""
    require_api(authorization)
    if not ESK_UPLOAD.exists():
        raise HTTPException(404, "eShikshaKosh source report is not available; fetch it first")
    meta = _json_read(ESK_UPLOAD_META) if ESK_UPLOAD_META.exists() else {}
    bound_session = str(meta.get("session_id") or "")
    if session_id and bound_session and bound_session != session_id:
        raise HTTPException(409, "eShikshaKosh source belongs to a different UDISE session")
    try:
        from openpyxl import load_workbook
        wb = load_workbook(ESK_UPLOAD, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        headers = [str(x or "").strip() for x in next(rows, ())]
        index = {name: i for i, name in enumerate(headers)}
        wanted = ["Student Name", "Father's Name", "Class", "Section", "Admission No", "OTR Number", "OTR Status", "Stream"]
        missing = [name for name in wanted if name not in index]
        if missing:
            wb.close()
            raise RuntimeError("eShikshaKosh report is missing expected columns: " + ", ".join(missing))
        preview_rows = []
        class_counts = {}
        total = 0
        for values in rows:
            if not any(v not in (None, "") for v in values):
                continue
            total += 1
            cls = str(values[index["Class"]] or "").strip()
            class_counts[cls] = class_counts.get(cls, 0) + 1
            if len(preview_rows) < 25:
                preview_rows.append({
                    name: str(values[index[name]] or "").strip()
                    for name in wanted
                })
        wb.close()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, "Could not read the fetched eShikshaKosh workbook: " + str(exc)[:500]) from exc
    return {
        "ready": True,
        "source": "live" if meta.get("source") == "live" else "upload",
        "school_name": meta.get("school_name", ""),
        "udise": meta.get("udise", ""),
        "total": total,
        "class_counts": class_counts,
        "preview_limit": len(preview_rows),
        "rows": preview_rows,
    }


@app.get("/api/v1/ep-template")
def ep_template(class_name: str = "IX", session_id: str | None = None, school: str = "school", authorization: str | None = Header(default=None)):
    """Return a live, pre-filled EP review workbook with subject dropdowns."""
    require_api(authorization)
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from tempfile import NamedTemporaryFile
    from udise_vps.session import connect
    from udise_vps import ep as ep_mod
    from udise_vps import subjects as subjects_mod

    safe_class = re.sub(r"[^A-Za-z0-9_-]", "", class_name.upper()) or "IX"
    class_id = {"IX": 9, "X": 10, "XI": 11, "XII": 12}.get(safe_class)
    if class_id is None:
        raise HTTPException(400, "EP template supports Class IX, X, XI or XII")

    rows: list[dict[str, Any]] = []
    current_rows: list[dict[str, Any]] = []
    subject_options: dict[int, list[str]] = {}
    live_school_name = ""
    live_udise_code = ""

    fallback_options = {
        1: ["HINDI", "URDU"],
        2: ["SANSKRIT", "HIN (NLH)"],
        3: ["MATHEMATICS"],
        4: ["SCIENCE"],
        5: ["SOCIAL SCIENCE"],
        6: ["ENGLISH"],
    }
    fallback_code_labels = {
        629: "HINDI", 638: "URDU", 637: "SANSKRIT", 1102: "HIN (NLH)",
        401: "MATHEMATICS", 402: "SCIENCE", 404: "SOCIAL SCIENCE", 612: "ENGLISH",
    }

    if session_id:
        session_data = _load_session(session_id)
        effective_school = str(session_data.get("school_id") or school).strip()
        try:
            udise = connect(session_data["cookie"], effective_school)
        except Exception as exc:
            raise HTTPException(502, "Could not open the current UDISE session for the EP template: " + type(exc).__name__) from exc

        live_school_name = udise.school_name
        live_udise_code = udise.udise_code
        rules = ep_mod.load_subject_rules(udise, {class_id})

        for slot in range(1, 7):
            field_name = "subject" + str(slot)
            options = []
            for rule in rules.get(class_id, []):
                if rule.get("fieldName") != field_name:
                    continue
                for option in rule.get("options") or []:
                    label = str((option or {}).get("subjectDesc") or "").strip()
                    if label and label not in options:
                        options.append(label)
            subject_options[slot] = options or list(fallback_options[slot])

        selected = [student for student in udise.students if int(student.get("classId") or -1) == class_id]
        for student in selected:
            sid = str(student.get("studentId") or student.get("id") or "").strip()
            pen = str(student.get("studentCodeNat") or "").strip()
            name = str(student.get("studentName") or "").strip()
            roll_from_roster = str(student.get("rollNo") or student.get("rollNumber") or "").strip()
            try:
                current = udise.enrolment_detail(sid)
            except Exception:
                current = {}

            try:
                general = udise.student_detail(sid)
                minority_id = general.get("minorityId")
            except Exception:
                minority_id = None

            def label_for_subject(slot: int, value) -> str:
                if value in (None, "", 0, "0", 9, "9"):
                    return ""
                label = ep_mod.subject_label(rules, class_id, "subject" + str(slot), value)
                if label and label != str(value):
                    return str(label)
                try:
                    return fallback_code_labels.get(int(float(str(value))), str(label or value))
                except Exception:
                    return str(label or value)

            current_values = {
                "Student Name": name,
                "PEN": pen,
                "Roll No.": current.get("rollNumber") or roll_from_roster or "",
                "Admission No.": current.get("admnNumber") or "",
                "Stream": current.get("academicStream") or "",
            }
            for slot in range(1, 7):
                current_values["Subject " + str(slot)] = label_for_subject(slot, current.get("subject" + str(slot)))

            effective = dict(current_values)
            if not str(effective["Roll No."]).strip() and roll_from_roster:
                effective["Roll No."] = roll_from_roster
            if not str(effective["Admission No."]).strip() and safe_class in {"IX", "X"} and roll_from_roster:
                effective["Admission No."] = roll_from_roster

            if class_id in {9, 10}:
                plan, _missing = ep_mod.resolve_language_codes(rules, class_id, minority_id)
                for field_name, code in plan.get("codes", {}).items():
                    slot = int(field_name.replace("subject", ""))
                    if not str(effective["Subject " + str(slot)]).strip():
                        effective["Subject " + str(slot)] = label_for_subject(slot, code)
                for slot in subjects_mod.MANDATORY_SUBJECT_SLOTS:
                    if not str(effective["Subject " + str(slot)]).strip():
                        code = subjects_mod.SUBJECT_FIXED_CODES[slot]
                        effective["Subject " + str(slot)] = fallback_code_labels.get(code, str(code))

            rows.append(effective)
            current_rows.append(current_values)
    else:
        for slot in range(1, 7):
            subject_options[slot] = list(fallback_options[slot])
        blank = {"Student Name": "", "PEN": "", "Roll No.": "", "Admission No.": "", "Stream": ""}
        for slot in range(1, 7):
            blank["Subject " + str(slot)] = ""
        rows.append(dict(blank))
        current_rows.append(dict(blank))

    headers = ["Student Name", "PEN", "Roll No.", "Admission No.", "Stream"] + ["Subject " + str(i) for i in range(1, 7)]
    wb = Workbook()
    ws = wb.active
    ws.title = "Enrollment Profile"
    current_ws = wb.create_sheet("Current UDISE Values")
    lists = wb.create_sheet("Subject Lists")

    for target in (ws, current_ws):
        target.append(headers)
        for cell in target[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1E3A8A")
        target.freeze_panes = "A2"

    for item in rows:
        ws.append([item.get(h, "") for h in headers])
    for item in current_rows:
        current_ws.append([item.get(h, "") for h in headers])

    current_fill = PatternFill("solid", fgColor="E2F0D9")
    proposed_fill = PatternFill("solid", fgColor="FFF2CC")
    for row_idx in range(2, ws.max_row + 1):
        for col_idx, _header in enumerate(headers, 1):
            current_value = current_ws.cell(row_idx, col_idx).value
            effective_value = ws.cell(row_idx, col_idx).value
            if effective_value not in (None, ""):
                ws.cell(row_idx, col_idx).fill = current_fill if current_value not in (None, "") else proposed_fill

    for slot in range(1, 7):
        options = subject_options.get(slot) or fallback_options[slot]
        lists.cell(1, slot, "Subject " + str(slot))
        for ri, label in enumerate(options, 2):
            lists.cell(ri, slot, label)
        target_col = headers.index("Subject " + str(slot)) + 1
        target_letter = get_column_letter(target_col)
        source_letter = get_column_letter(slot)
        formula = "'Subject Lists'!$" + source_letter + "$2:$" + source_letter + "$" + str(1 + len(options))
        dv = DataValidation(type="list", formula1=formula, allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(target_letter + "2:" + target_letter + str(max(2, ws.max_row)))

    if class_id == 11:
        stream_list = ["Arts", "Science", "Commerce"]
        stream_col = 8
        lists.cell(1, stream_col, "Stream")
        for ri, label in enumerate(stream_list, 2):
            lists.cell(ri, stream_col, label)
        dv = DataValidation(type="list", formula1="'Subject Lists'!$H$2:$H$4", allow_blank=True)
        ws.add_data_validation(dv)
        dv.add("E2:E" + str(max(2, ws.max_row)))

    lists.sheet_state = "hidden"

    for target in (ws, current_ws):
        target.auto_filter.ref = "A1:K" + str(max(2, target.max_row))
        widths = [28, 16, 12, 16, 16, 20, 20, 20, 20, 20, 20]
        for idx, width in enumerate(widths, 1):
            target.column_dimensions[get_column_letter(idx)].width = width

    notes = wb.create_sheet("Instructions")
    notes.append(["Enrollment Profile review template"])
    notes.append(["Class: " + safe_class])
    if live_school_name:
        notes.append(["School: " + live_school_name])
    if live_udise_code:
        notes.append(["UDISE code: " + live_udise_code])
    notes.append(["Green cells = values already saved in UDISE. Yellow cells = values auto-filled by the EP rules for currently blank fields."])
    notes.append(["Subject 1–6 cells include dropdowns from the live UDISE subject catalogue when available."])
    notes.append(["Class X does not require eShikshaKosh. It may still be connected as an optional Admission Number source."])
    notes.append(["Current UDISE Values preserves the original portal values for comparison."])
    notes.append(["Only eligible blank UDISE fields are written by automation; editing this workbook does not itself modify the portal."])
    notes.column_dimensions["A"].width = 120
    notes["A1"].font = Font(bold=True, size=14)

    with NamedTemporaryFile(suffix="-ep-" + safe_class + "-template.xlsx", delete=False) as tmp:
        wb.save(tmp.name)
        path = Path(tmp.name)
    return FileResponse(
        path,
        filename="Enrollment_Profile_" + safe_class + "_template.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/v1/eshiksha-export")
def eshiksha_export(class_name: str = "ALL", session_id: str | None = None, authorization: str | None = Header(default=None)):
    """Fetch once, attach the workbook to EP, then discard the temporary password."""
    require_api(authorization)
    from udise_vps.esk import export_report
    try:
        creds = _load_eshiksha_credentials(session_id)
        out = JOBS / f"eshiksha-download-{uuid.uuid4().hex}"
        out.mkdir(parents=True, exist_ok=True)
        # eShikshaKosh is the single source of truth for the OTR data.
        # Fetch the complete school roster once; the selected UDISE class is
        # applied later by the EP matcher against this workbook.
        report = export_report(
            udise=creds["udise"],
            password=creds["password"],
            year=creds.get("year", "2026-27"),
            output=out / "eShikshaKosh_OTR_ALL.xlsx",
        )
        shutil.copy2(report, ESK_UPLOAD)
        os.chmod(ESK_UPLOAD, 0o600)
        _json_write(ESK_UPLOAD_META, {
            "created_at": int(time.time()),
            "session_id": session_id or creds.get("session_id", ""),
            "source": "live",
            "school_name": creds.get("school_name", ""),
            "udise": creds.get("udise", ""),
        })
        ESK_CREDENTIAL.unlink(missing_ok=True)
    except Exception as exc:
        raise HTTPException(502, str(exc)[:1200]) from exc
    return FileResponse(report, filename="eShikshaKosh_OTR_ALL.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
