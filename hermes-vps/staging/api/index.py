"""UDISE login staging service — serverless, stateless, browser-optional.

This is a **staging harness**, not the production control plane. It exists so the
browser-free login can be exercised on a serverless host and compared against the
Playwright path, without touching the Oracle deployment.

Why it looks different from ``control_api``
-------------------------------------------
Serverless functions share no memory between invocations, so the login state
cannot live in a module-level dict the way ``LOGIN_BROWSERS`` does. Instead the
carried state is sealed into an **encrypted cookie** and the CAPTCHA PNG is
returned inline as base64 (a 10 KB PNG will not fit in a 4 KB cookie).

    POST /api/v1/login-requests            -> {token, captcha_png, expires_in}
                                              + Set-Cookie: udise_stage=<sealed state>
    POST /api/v1/login-requests/submit     -> {ready, cookie_header, school}

Backends
--------
``UDISE_LOGIN_BACKEND`` selects how the portal is driven:

    http     (default) plain requests — works on any serverless host
    browser  Playwright Chromium — requires a container; a no-op on Vercel

The endpoint contract is identical either way, so the same UI and the same tests
work against both.

Security
--------
Staging-only. The control token is a single shared secret; there is no job queue,
no approval gate, and no write path. It never writes to the portal. Do not point
a production UI at it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# The vendored copy of the login module sits next to this file (see sync_module.sh).
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from udise_login import LoginError, LoginSession, begin_login, submit_login
except ImportError as exc:  # pragma: no cover - deployment misconfiguration
    raise SystemExit(
        "staging is missing udise_login.py next to index.py; run ./sync_module.sh"
    ) from exc

BACKEND = os.environ.get("UDISE_LOGIN_BACKEND", "http").strip().lower()
# Strip surrounding whitespace: env vars pasted from a terminal or a file often
# carry a trailing newline, and an exact compare would then reject a correct token.
CONTROL_TOKEN = os.environ.get("UDISE_CONTROL_TOKEN", "").strip()
COOKIE_SECRET = os.environ.get("UDISE_STAGE_COOKIE_SECRET", "")
COOKIE_NAME = "udise_stage"
REQUEST_TTL = 10 * 60
COOKIE_MAX_AGE = REQUEST_TTL

if not CONTROL_TOKEN:
    # Refuse to serve with no auth rather than silently exposing the staging box.
    raise SystemExit("UDISE_CONTROL_TOKEN must be set")

if not COOKIE_SECRET:
    raise SystemExit("UDISE_STAGE_COOKIE_SECRET must be set (>= 32 chars)")

app = FastAPI(title="UDISE Login Staging", version="0.1.0")


# --------------------------------------------------------------------------
# sealed cookie: AES-free, HMAC-authenticated, XOR-masked payload
# --------------------------------------------------------------------------


def _keystream(secret: bytes, nonce: bytes, length: int) -> bytes:
    """Deterministic keystream from the secret+nonce (SHA-256 in counter mode)."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        out += hashlib.sha256(secret + nonce + counter.to_bytes(4, "big")).digest()
        counter += 1
    return bytes(out[:length])


def seal(payload: dict) -> str:
    """Encrypt+authenticate the carried state for a cookie."""
    secret = COOKIE_SECRET.encode()
    raw = json.dumps(payload, separators=(",", ":")).encode()
    nonce = secrets.token_bytes(12)
    body = bytes(a ^ b for a, b in zip(raw, _keystream(secret, nonce, len(raw))))
    tag = hmac.new(secret, nonce + body, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(nonce + tag + body).decode().rstrip("=")


def unseal(token: str) -> dict:
    """Reverse :func:`seal`. Raises on tampering."""
    secret = COOKIE_SECRET.encode()
    pad = "=" * (-len(token) % 4)
    try:
        blob = base64.urlsafe_b64decode(token + pad)
    except Exception as exc:
        raise HTTPException(400, "Malformed staging cookie") from exc
    if len(blob) < 28:
        raise HTTPException(400, "Malformed staging cookie")
    nonce, tag, body = blob[:12], blob[12:28], blob[28:]
    expect = hmac.new(secret, nonce + body, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expect):
        raise HTTPException(400, "Staging cookie failed its integrity check")
    raw = bytes(a ^ b for a, b in zip(body, _keystream(secret, nonce, len(body))))
    return json.loads(raw.decode())


# --------------------------------------------------------------------------
# auth + models
# --------------------------------------------------------------------------


def require_token(authorization: str | None) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Unauthorized")
    got = authorization[7:].strip()
    if not secrets.compare_digest(got, CONTROL_TOKEN):
        # Help the operator without leaking either value.
        raise HTTPException(
            401,
            "Unauthorized — token mismatch "
            f"(sent {len(got)} chars, expected {len(CONTROL_TOKEN)})",
        )


class SubmitIn(BaseModel):
    username: str
    password: str
    captcha: str


def _cookie_kwargs() -> dict:
    return {
        "key": COOKIE_NAME,
        "httponly": True,
        "secure": True,
        "samesite": "lax",
        "max_age": COOKIE_MAX_AGE,
        "path": "/",
    }


# --------------------------------------------------------------------------
# browser backend (optional; container-only)
# --------------------------------------------------------------------------


async def _begin_browser() -> tuple[LoginSession, bytes]:
    """Playwright path. Only reachable when the host can run Chromium."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise HTTPException(
            501,
            "browser backend requested but Playwright is not installed on this host. "
            "Use UDISE_LOGIN_BACKEND=http, or deploy to a container.",
        ) from exc

    import asyncio

    from udise_login import (
        AUTH_BASE,
        EXPECTED_CLIENT_ID,
        LOGIN_START,
        dump_cookies,
        new_session,
        normalize_auth_url,
    )

    def _bootstrap():
        s = new_session()
        r = s.get(LOGIN_START, timeout=30, allow_redirects=False)
        r.raise_for_status()
        return s, normalize_auth_url(str(r.headers.get("Location") or ""))

    session, auth_url = await asyncio.to_thread(_bootstrap)
    pw = await async_playwright().start()
    try:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context()
        for c in session.cookies:
            await context.add_cookies(
                [
                    {
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain or "sdms.udiseplus.gov.in",
                        "path": c.path or "/",
                    }
                ]
            )
        page = await context.new_page()
        await page.goto(auth_url, wait_until="domcontentloaded", timeout=35_000)
        await page.locator("#username").wait_for(state="visible", timeout=15_000)
        await page.locator("#captchaImage").wait_for(state="visible", timeout=15_000)
        txn = await page.locator('input[name="loginTxnId"]').get_attribute("value")
        png = await page.locator("#captchaImage").screenshot()
        carried = LoginSession(
            csrf="",
            login_txn_id=str(txn or ""),
            auth_url=auth_url,
            client_id=EXPECTED_CLIENT_ID,
            cookies=dump_cookies(session),
        )
        carried.cookies.append({"name": "__browser", "value": "1", "domain": "", "path": "/"})
        return carried, png
    except Exception as exc:
        raise HTTPException(502, f"browser backend failed: {type(exc).__name__}") from exc
    finally:
        try:
            await pw.stop()
        except Exception:
            pass


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "udise-login-staging",
        "backend": BACKEND,
        "playwright_available": _playwright_available(),
        "stateless": True,
    }


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


@app.get("/api/v1/whoami")
def whoami(authorization: str | None = Header(default=None)) -> dict:
    """Diagnose a token mismatch without revealing either value.

    Open this in the browser (or curl it) with the same Authorization header the
    UI sends and it says whether the token matched and how long each side is.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return {
            "matched": False,
            "reason": "no Authorization header sent",
            "hint": "enter the token in step 1 and click 'Use this token'",
        }
    got = authorization[7:].strip()
    matched = secrets.compare_digest(got, CONTROL_TOKEN)
    return {
        "matched": matched,
        "sent_length": len(got),
        "expected_length": len(CONTROL_TOKEN),
        "reason": "token matches" if matched else "length or content differs",
        "sent_sha256_prefix": hashlib.sha256(got.encode()).hexdigest()[:12],
        "expected_sha256_prefix": hashlib.sha256(CONTROL_TOKEN.encode()).hexdigest()[:12],
    }


@app.get("/api/v1/capabilities")
def capabilities() -> dict:
    return {
        "backend": BACKEND,
        "playwright_available": _playwright_available(),
        "stages": [
            {
                "id": "login",
                "label": "UDISE Login",
                "mode": "read",
                "description": "Browser-free login against auth.udiseplus.gov.in.",
            }
        ],
        "note": "Staging harness. Read-only. No job queue, no write path.",
    }


@app.post("/api/v1/login-requests")
def create_login_request(
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    """Start a login. Returns the CAPTCHA inline and seals state into a cookie."""
    require_token(authorization)
    token = secrets.token_urlsafe(32)
    now = int(time.time())

    if BACKEND == "browser":
        import asyncio

        carried, png = asyncio.run(_begin_browser())
    else:
        try:
            carried, png = begin_login()
        except LoginError as exc:
            raise HTTPException(502, str(exc)) from exc

    payload = {
        "token": token,
        "created_at": now,
        "expires_at": now + REQUEST_TTL,
        "carried": carried.to_dict(),
    }
    response.set_cookie(value=seal(payload), **_cookie_kwargs())
    return {
        "token": token,
        "expires_in": REQUEST_TTL,
        "backend": BACKEND,
        "captcha_png": base64.b64encode(png).decode(),
        "note": "State is carried in an encrypted cookie; no server memory is used.",
    }


@app.post("/api/v1/login-requests/submit")
def submit(
    body: SubmitIn,
    request: Request,
    response: Response,
    authorization: str | None = Header(default=None),
) -> dict:
    require_token(authorization)
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        raise HTTPException(400, "No staging cookie; start a new login request")

    payload = unseal(raw)
    if int(time.time()) > int(payload.get("expires_at", 0)):
        response.delete_cookie(COOKIE_NAME, path="/")
        raise HTTPException(410, "Login request expired; start a new one")

    carried = LoginSession.from_dict(payload.get("carried") or {})
    if BACKEND == "browser":
        raise HTTPException(
            501,
            "browser backend cannot submit statelessly (the Chromium session died with the "
            "previous invocation). Deploy the container control plane for browser login.",
        )

    try:
        cookie_header = submit_login(carried, body.username, body.password, body.captcha)
    except LoginError as exc:
        status = {"captcha": 400, "credentials": 401, "locked": 423, "input": 400}.get(
            exc.kind, 502
        )
        response.delete_cookie(COOKIE_NAME, path="/")
        raise HTTPException(status, str(exc)) from exc

    response.delete_cookie(COOKIE_NAME, path="/")
    return {
        "ready": True,
        "backend": BACKEND,
        "cookie_header": cookie_header,
        "note": "Session cookie returned for inspection. Staging never stores it.",
    }


PAGE_FILE = Path(__file__).resolve().parent / "page.html"


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    """Serve the staging UI. Kept as a real file so it can be edited and linted."""
    try:
        return PAGE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            "<h1>staging UI missing</h1>"
            "<p>api/page.html was not bundled with this deployment.</p>"
        )
