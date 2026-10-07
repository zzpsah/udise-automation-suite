"""UDISE SDMS login over plain HTTP — no browser, no Playwright.

The portal's login page at ``auth.udiseplus.gov.in`` is a server-rendered HTML
form. Every value the browser would submit is already in the HTML:

    <form action="/login" method="post">
      <input type="hidden" name="_csrf"      value="...">
      <input type="hidden" name="loginTxnId" value="...">
      <input name="username"    type="text">
      <input name="password"    type="password">
      <input name="captchaMode" type="radio" value="image">
      <input name="captcha"     type="text">

The CAPTCHA is a plain ``GET /captcha-image`` returning a PNG, and the password
is NOT encrypted client-side (``crypto-js`` is loaded but unused for auth). So
``requests`` can drive the whole flow.

This module exists so the login step does not require Chromium, which is what
forces the stack onto a VPS. It is deliberately dependency-free beyond
``requests`` so it can run in a serverless function.

Flow
----
1. ``GET  /p0/oauth2/login``          → 302 to the auth host (may be http://)
2. ``GET  /oauth2/authorize?...``     → login HTML; parse ``_csrf``/``loginTxnId``
3. ``GET  /captcha-image``            → PNG for the operator to read
4. ``POST /login`` {username,password,captchaMode,captcha,_csrf,loginTxnId}
5. follow redirects → collect SDMS cookies → ``JSESSIONID`` + ``XSRF-TOKEN``

Step 1 is essential: it establishes the OAuth ``state`` and the session cookies
the login page expects. Posting straight to ``/login`` without it fails.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

SDMS_BASE = "https://sdms.udiseplus.gov.in"
AUTH_BASE = "https://auth.udiseplus.gov.in"
LOGIN_START = f"{SDMS_BASE}/p0/oauth2/login"
CHECK_SESSION = f"{SDMS_BASE}/p0/check-session"
EXPECTED_CLIENT_ID = "udise-sdms-g0"
CHECK_SESSION_TIMEOUT = 20
DEFAULT_TIMEOUT = 40

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class LoginError(RuntimeError):
    """A login step failed. ``kind`` drives the operator-facing message."""

    def __init__(self, message: str, kind: str = "unavailable") -> None:
        super().__init__(message)
        self.kind = kind


@dataclass
class LoginSession:
    """State carried between the captcha step and the submit step.

    Serialisable via :meth:`to_dict` / :meth:`from_dict` so a stateless host can
    keep it in a signed cookie instead of server memory.
    """

    csrf: str = ""
    login_txn_id: str = ""
    auth_url: str = ""
    state: str = ""
    client_id: str = ""
    cookies: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "csrf": self.csrf,
            "login_txn_id": self.login_txn_id,
            "auth_url": self.auth_url,
            "state": self.state,
            "client_id": self.client_id,
            "cookies": self.cookies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoginSession":
        return cls(
            csrf=str(data.get("csrf") or ""),
            login_txn_id=str(data.get("login_txn_id") or ""),
            auth_url=str(data.get("auth_url") or ""),
            state=str(data.get("state") or ""),
            client_id=str(data.get("client_id") or ""),
            cookies=list(data.get("cookies") or []),
        )


# --------------------------------------------------------------------------
# cookie helpers
# --------------------------------------------------------------------------


def dump_cookies(session: requests.Session) -> list[dict[str, str]]:
    return [
        {
            "name": c.name,
            "value": c.value,
            "domain": c.domain or "",
            "path": c.path or "/",
        }
        for c in session.cookies
    ]


def restore_session(items: list[dict[str, str]]) -> requests.Session:
    session = new_session()
    for item in items:
        name = str(item.get("name") or "")
        if not name:
            continue
        session.cookies.set(
            name,
            str(item.get("value") or ""),
            domain=str(item.get("domain") or "") or None,
            path=str(item.get("path") or "/"),
        )
    return session


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def sdms_cookie_header(session: requests.Session) -> str:
    """The ``Cookie:`` header the runner needs, SDMS cookies only, deduped."""
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


def cookies_by_name(session: requests.Session) -> dict[str, str]:
    out: dict[str, str] = {}
    for c in session.cookies:
        domain = (c.domain or "").lstrip(".").lower()
        if domain and not domain.endswith("sdms.udiseplus.gov.in"):
            continue
        out.setdefault(c.name, c.value)
    return out


# --------------------------------------------------------------------------
# HTML parsing
# --------------------------------------------------------------------------


def _hidden_input(text: str, name: str) -> str:
    escaped = re.escape(name)
    m = re.search(rf'name="{escaped}"[^>]*value="([^"]*)"', text, re.I)
    if not m:
        m = re.search(rf'value="([^"]*)"[^>]*name="{escaped}"', text, re.I)
    return html.unescape(m.group(1)) if m else ""


def parse_login_form(text: str) -> tuple[str, str]:
    """Return ``(csrf, loginTxnId)`` from the login page HTML."""
    csrf = _hidden_input(text, "_csrf")
    if not csrf:
        raise LoginError("UDISE login page did not provide a CSRF token", "shape")
    return csrf, _hidden_input(text, "loginTxnId")


def normalize_auth_url(location: str) -> str:
    """The portal hands out an ``http://`` authorize URL; port 80 is unreachable."""
    if location.startswith("http://auth.udiseplus.gov.in/"):
        return "https://" + location[len("http://") :]
    return location


# --------------------------------------------------------------------------
# failure classification
# --------------------------------------------------------------------------


def classify_failure(final_url: str, text: str) -> str:
    """Turn a failed login into one actionable sentence for the operator."""
    query = parse_qs(urlparse(final_url).query, keep_blank_values=True)
    flags = {str(k).lower() for k in query}
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    plain = re.sub(r"\s+", " ", plain).strip()
    low = plain.lower()

    if "captchaerror" in flags or "invalid captcha" in low:
        return "CAPTCHA incorrect or expired. A fresh CAPTCHA has been loaded."
    if "locked" in flags or "account is locked" in low or "login locked" in low:
        return (
            "UDISE has temporarily locked this login after failed attempts. "
            "Try again after the lock period."
        )
    if (
        flags.intersection({"expired", "sessionexpired", "sessioninvalid", "flowwarning"})
        or "login page has expired" in low
        or "link has expired" in low
    ):
        return (
            "UDISE login session expired. A fresh CAPTCHA has been loaded; "
            "enter the credentials again."
        )
    if "error" in flags:
        return "UDISE did not accept the username/password for this login attempt."
    if "invalid credential" in low or "invalid username" in low or "incorrect password" in low:
        return "UDISE did not accept the username/password for this login attempt."
    return "UDISE login was not completed. A fresh CAPTCHA has been loaded."


# --------------------------------------------------------------------------
# the flow
# --------------------------------------------------------------------------


def begin_login(session: requests.Session | None = None) -> tuple[LoginSession, bytes]:
    """Steps 1-3. Returns the carried state plus the CAPTCHA PNG bytes."""
    session = session or new_session()

    try:
        bootstrap = session.get(LOGIN_START, timeout=30, allow_redirects=False)
        bootstrap.raise_for_status()
    except requests.RequestException as exc:
        raise LoginError(f"UDISE login service unavailable: {type(exc).__name__}") from exc

    auth_url = normalize_auth_url(str(bootstrap.headers.get("Location") or ""))
    parsed = urlparse(auth_url)
    query = parse_qs(parsed.query)
    client_id = str((query.get("client_id") or [""])[0])
    state = str((query.get("state") or [""])[0])

    if not auth_url.startswith(AUTH_BASE + "/oauth2/authorize?"):
        raise LoginError("OAuth bootstrap did not redirect to the expected authorize URL", "shape")
    if client_id != EXPECTED_CLIENT_ID:
        raise LoginError(f"Unexpected OAuth client_id {client_id!r}", "shape")
    if not state:
        raise LoginError("OAuth bootstrap did not provide a state value", "shape")

    try:
        page = session.get(auth_url, timeout=DEFAULT_TIMEOUT)
        page.raise_for_status()
        csrf, txn = parse_login_form(page.text)
        captcha = session.get(f"{AUTH_BASE}/captcha-image", timeout=30)
        captcha.raise_for_status()
    except LoginError:
        raise
    except requests.RequestException as exc:
        raise LoginError(f"UDISE login page unavailable: {type(exc).__name__}") from exc

    carried = LoginSession(
        csrf=csrf,
        login_txn_id=txn,
        auth_url=auth_url,
        state=state,
        client_id=client_id,
        cookies=dump_cookies(session),
    )
    return carried, captcha.content


def verify_session(session: requests.Session) -> bool:
    """True when SDMS reports the session as authenticated."""
    jar = cookies_by_name(session)
    if "JSESSIONID" not in jar or "XSRF-TOKEN" not in jar:
        return False
    try:
        check = session.get(
            CHECK_SESSION,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": f"{SDMS_BASE}/p0/",
                "X-XSRF-TOKEN": jar.get("XSRF-TOKEN", ""),
            },
            timeout=CHECK_SESSION_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException:
        return False
    return check.status_code == 200


def submit_login(
    carried: LoginSession,
    username: str,
    password: str,
    captcha: str,
) -> str:
    """Steps 4-5. Returns the SDMS ``Cookie:`` header on success.

    Raises :class:`LoginError` with ``kind='captcha'`` / ``'credentials'`` /
    ``'locked'`` / ``'expired'`` so the caller can react differently.
    """
    if not username.strip() or not password or not captcha.strip():
        raise LoginError("Username, password and CAPTCHA are required", "input")

    session = restore_session(carried.cookies)
    form = {
        "_csrf": carried.csrf,
        "loginTxnId": carried.login_txn_id,
        "username": username.strip(),
        "password": password,
        "captchaMode": "image",
        "captcha": captcha.strip(),
    }
    referer = carried.auth_url or f"{AUTH_BASE}/login"
    try:
        result = session.post(
            f"{AUTH_BASE}/login",
            data=form,
            headers={"Referer": referer},
            timeout=DEFAULT_TIMEOUT,
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise LoginError(f"UDISE login request failed: {type(exc).__name__}") from exc

    # A wrong CAPTCHA leaves us on the auth host; success lands back on SDMS.
    if urlparse(str(result.url)).netloc.endswith("auth.udiseplus.gov.in"):
        detail = classify_failure(str(result.url), result.text or "")
        kind = "captcha" if "CAPTCHA" in detail else (
            "locked" if "locked" in detail else "credentials"
        )
        raise LoginError(detail, kind)

    cookie = sdms_cookie_header(session)
    if "JSESSIONID=" not in cookie or "XSRF-TOKEN=" not in cookie:
        detail = classify_failure(str(result.url), result.text or "")
        kind = "captcha" if "CAPTCHA" in detail else "credentials"
        raise LoginError(detail, kind)

    if not verify_session(session):
        raise LoginError(
            "UDISE accepted the credentials but the session did not validate. "
            "Refresh the CAPTCHA and try again.",
            "unverified",
        )
    return cookie
