"""Authenticated session handling for the UDISE+ SDMS portal.

Ported from the notebook's Login cell. The notebook pastes a browser Cookie
header into a Colab runtime; on a VPS the same header is read from stdin or an
env var so it never lands on disk or in shell history.

Security rules carried over unchanged:
  - cookies/JSESSIONID/XSRF values are runtime-only
  - they are never printed, logged, or persisted
"""

from __future__ import annotations

import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import requests

from .constants import BASE_URL, KNOWN_SCHOOLS

DEFAULT_READ_TIMEOUT = 45
DEFAULT_GET_ATTEMPTS = 2


class AuthError(RuntimeError):
    """Raised when the portal rejects or cannot confirm the session."""


def _stamp(stage: str, message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] [LOGIN] {stage}: {message}", flush=True)


def parse_cookie_header(header: str) -> dict:
    """Split a browser Cookie request-header value into a name->value dict."""
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name and value:
            cookies[name] = value
    return cookies


def resolve_school_id(school_reference: str) -> str:
    """Accept a full UDISE school URL or a 7-digit internal school ID."""
    school_reference = (school_reference or "").strip()
    if not school_reference:
        raise ValueError("School reference is empty.")

    url_match = re.search(r"/school/(\d+)(?:/|$)", school_reference)
    if url_match:
        return url_match.group(1)
    if re.fullmatch(r"\d{7}", school_reference):
        return school_reference
    if re.fullmatch(r"\d{11}", school_reference):
        raise ValueError(
            "This is an 11-digit UDISE code. Use the school URL or its "
            "7-digit internal school ID instead."
        )
    raise ValueError(
        "Enter a complete UDISE school URL or its 7-digit internal school ID."
    )


@dataclass
class UdiseSession:
    """An authenticated, read-capable UDISE+ session."""

    session: requests.Session
    headers: dict
    school_id: str
    udise_code: str = ""
    school_name: str = ""
    base_url: str = BASE_URL
    students: list = field(default_factory=list)

    # ------------------------------------------------------------------ helpers
    def _request(
        self,
        method: str,
        route: str,
        *,
        attempts: int = 1,
        read_timeout: int = 60,
        connect_timeout: int = 15,
        label: str = "GET",
        **kwargs: Any,
    ):
        """Issue a request with a heartbeat and bounded, read-only retries.

        Writes must be issued with attempts=1 — the caller owns the
        no-blind-retry rule for POSTs.
        """
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            done = threading.Event()
            started = time.monotonic()

            def heartbeat() -> None:
                while not done.wait(10):
                    print(
                        f"[{label}] WAIT {method} {attempt}/{attempts}: "
                        f"{time.monotonic() - started:.0f}s",
                        flush=True,
                    )

            worker = threading.Thread(target=heartbeat, daemon=True)
            worker.start()
            try:
                response = self.session.request(
                    method,
                    self.base_url + route,
                    headers=self.headers,
                    timeout=(connect_timeout, read_timeout),
                    allow_redirects=False,
                    **kwargs,
                )
            except (
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
            ) as exc:
                last_error = exc
                print(
                    f"[{label}] temporary connection issue "
                    f"({attempt}/{attempts}): {type(exc).__name__}",
                    flush=True,
                )
                if attempt >= attempts:
                    raise
                time.sleep(2)
                continue
            finally:
                done.set()
                worker.join(timeout=1)

            try:
                body = response.json()
            except ValueError:
                body = {}
            if not isinstance(body, dict):
                body = {}
            return response.status_code, body

        raise RuntimeError(f"{method} failed after {attempts} attempt(s): {last_error}")

    # -------------------------------------------------------------- read paths
    def get(self, route: str, **kwargs: Any):
        kwargs.setdefault("attempts", DEFAULT_GET_ATTEMPTS)
        kwargs.setdefault("read_timeout", 30)
        kwargs.setdefault("label", "GET")
        return self._request("GET", route, **kwargs)

    def get_json(self, route: str, **kwargs: Any) -> dict:
        """GET and require the portal's success envelope."""
        status, body = self.get(route, **kwargs)
        if status != 200 or body.get("status") is not True:
            raise RuntimeError(
                f"GET {route} failed: HTTP {status}; "
                f"{body.get('message') or body.get('error') or 'no usable data'}"
            )
        return body

    def check_session(self) -> None:
        status, _ = self.get("/p0/check-session", attempts=1, read_timeout=15)
        if status != 200:
            raise AuthError(
                f"Session check returned HTTP {status}. "
                "Log in again and supply a fresh Cookie header."
            )

    # ------------------------------------------------------------ roster reads
    def fetch_roster(
        self,
        read_timeout: int = DEFAULT_READ_TIMEOUT,
        attempts: int = DEFAULT_GET_ATTEMPTS,
    ) -> list:
        """Fetch the current academic-session student roster."""
        _stamp("ROSTER", "Fetching student roster…")
        status, body = self.get(
            f"/p0/api/cy/students/all/{self.school_id}",
            attempts=attempts,
            read_timeout=read_timeout,
            label="ROSTER",
        )
        if status in (401, 403) or 300 <= status < 400:
            raise AuthError(
                f"Authentication/access response HTTP {status}. "
                "Supply a fresh Cookie header and retry."
            )
        if status != 200:
            raise RuntimeError(f"Portal returned HTTP {status}; roster not loaded.")
        if body.get("status") is not True:
            safe_keys = ",".join(sorted(str(k) for k in body.keys())[:12])
            safe_message = str(body.get("message") or body.get("error") or "")[:240]
            raise RuntimeError(
                "Portal did not confirm a successful roster response"
                + (f" (keys={safe_keys})" if safe_keys else "")
                + (f": {safe_message}" if safe_message else ".")
            )
        students = body.get("data") or []
        if not isinstance(students, list):
            raise RuntimeError("Roster payload was not a list.")
        self.students = students
        _stamp("ROSTER", f"Loaded {len(students)} students.")
        return students

    def student_detail(self, student_id: str) -> dict:
        """Fresh read of one student's General Profile record."""
        body = self.get_json(f"/p0/api/cy/students/{student_id}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"No usable student data for id {student_id}")
        return data

    def enrolment_detail(self, student_id: str) -> dict:
        """Fresh read of one student's Enrollment Profile record."""
        body = self.get_json(f"/p0/api/v2/students/enrolment/{student_id}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"Enrollment record unavailable for {student_id}")
        if data.get("schoolId") is not None and str(data.get("schoolId")) != str(self.school_id):
            raise ValueError("Enrollment record school identity mismatch")
        if data.get("studentId") is not None and str(data.get("studentId")) != str(student_id):
            raise ValueError("Enrollment record student identity mismatch")
        return data

    def facility_detail(self, student_id: str) -> dict:
        """Fresh read of one student's Facility record."""
        body = self.get_json(f"/p0/api/v2/students/facility/{student_id}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError(f"Facility record unavailable for {student_id}")
        if (
            str(data.get("schoolId")) != str(self.school_id)
            or str(data.get("studentId")) != str(student_id)
        ):
            raise ValueError("Facility record school/student identity mismatch")
        return data

    # ------------------------------------------------------------ write paths
    def post_once(self, route: str, *, json_body: Any = None, read_timeout: int = 90):
        """Exactly one POST. Never retried here — the caller decides what is safe.

        The notebook's rule is preserved: after an ambiguous transport failure
        the caller must perform a fresh read-back, not replay the write.
        """
        return self._request(
            "POST",
            route,
            attempts=1,
            read_timeout=read_timeout,
            connect_timeout=20,
            label="POST",
            json=json_body,
        )


# ------------------------------------------------------------------ entry point
def connect(
    cookie_header: str,
    school_reference: str,
    *,
    read_timeout: int = DEFAULT_READ_TIMEOUT,
    attempts: int = DEFAULT_GET_ATTEMPTS,
    fetch_students: bool = True,
) -> UdiseSession:
    """Validate a Cookie header, detect the school, and load the roster."""
    cookies = parse_cookie_header(cookie_header)
    missing = [n for n in ("JSESSIONID", "XSRF-TOKEN") if not cookies.get(n)]
    if missing:
        raise AuthError("Cookie header is missing: " + ", ".join(missing))

    session = requests.Session()
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="sdms.udiseplus.gov.in", path="/")

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/g0/",
        "User-Agent": "Mozilla/5.0",
        "X-XSRF-TOKEN": cookies["XSRF-TOKEN"],
    }

    school_id = resolve_school_id(school_reference)
    udise_code, school_name = KNOWN_SCHOOLS.get(school_id, ("", ""))

    obj = UdiseSession(
        session=session,
        headers=headers,
        school_id=school_id,
        udise_code=udise_code,
        school_name=school_name,
    )

    _stamp("STEP 1/3", "Validating session…")
    obj.check_session()
    _stamp("STEP 1/3", "Session valid. Cookies remain in memory only.")

    # Identify the school from the portal itself so the tool stays generic.
    # NOTE: /p0/api/user returns the logged-in USER's name, not the school.
    # The school name comes from a student record, which is authoritative.
    try:
        user = session.get(f"{BASE_URL}/p0/api/user", headers=headers, timeout=30).json()
        data = user.get("data") if isinstance(user, dict) else None
        if isinstance(data, dict):
            obj.udise_code = obj.udise_code or str(data.get("userId") or "").strip()
    except Exception:
        pass

    _stamp(
        "STEP 2/3",
        f"Internal school ID {school_id}"
        + (f" — {obj.school_name}" if obj.school_name else "")
        + (f" (UDISE {obj.udise_code})" if obj.udise_code else ""),
    )

    if fetch_students:
        _stamp("STEP 3/3", "Fetching student roster…")
        obj.fetch_roster(read_timeout=read_timeout, attempts=attempts)
        if obj.students:
            first = obj.students[0]
            obj.school_name = obj.school_name or str(first.get("schoolName") or "").strip()
            obj.udise_code = obj.udise_code or str(first.get("schUdiseCode") or "").strip()

    return obj


def cookie_from_environment() -> str:
    """Read the Cookie header from an env var, else prompt without echo.

    The env-var path keeps the value out of shell history and process argv.
    A non-interactive run with no env var fails cleanly rather than blocking.
    """
    value = os.environ.get("UDISE_COOKIE_HEADER", "").strip()
    if value:
        return value

    # Explicit opt-in for reading from a pipe (e.g. a secret manager).
    if os.environ.get("UDISE_COOKIE_FROM_STDIN") == "1":
        return sys.stdin.readline().strip()

    if not sys.stdin.isatty():
        return sys.stdin.readline().strip()

    # Never block a scripted run: require an interactive terminal to prompt.
    if os.environ.get("UDISE_ALLOW_PROMPT") != "1":
        raise AuthError(
            "No Cookie header available. Set UDISE_COOKIE_HEADER, or set "
            "UDISE_ALLOW_PROMPT=1 to be prompted interactively."
        )

    import getpass

    return getpass.getpass("Paste complete UDISE Cookie header: ").strip()
