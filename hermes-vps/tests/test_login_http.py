"""Offline tests for the browser-free UDISE login (udise_vps/login_http.py).

No network. Every portal response is a recorded fixture in tests/fixtures/.
The fixtures are real HTML captured from the live login page, so the parser is
tested against the actual markup rather than an idealised version.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udise_vps import login_http as L  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PASSED = 0
FAILED = 0


def check(label: str, cond: bool, extra: str = "") -> None:
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
        print(f"  FAIL: {label} {extra}")


def eq(label: str, got, want) -> None:
    check(label, got == want, f"(got {got!r}, want {want!r})")


# --------------------------------------------------------------------------
# HTML parsing — against the real captured login page
# --------------------------------------------------------------------------


def test_parse_real_login_page() -> None:
    html = (FIXTURES / "login_page.html").read_text(encoding="utf-8")
    csrf, txn = L.parse_login_form(html)
    check("csrf is a long token", len(csrf) > 40, f"len={len(csrf)}")
    check("loginTxnId is a uuid", len(txn) >= 32 and "-" in txn, f"txn={txn!r}")
    # attribute order must not matter
    swapped = f'<input value="{csrf}" name="_csrf"/>'
    eq("csrf parses when value precedes name", L._hidden_input(swapped, "_csrf"), csrf)


def test_parse_rejects_missing_csrf() -> None:
    try:
        L.parse_login_form("<html><body>no form here</body></html>")
        check("missing csrf raises", False)
    except L.LoginError as e:
        eq("missing csrf raises LoginError", e.kind, "shape")


def test_html_entity_unescape() -> None:
    html = '<input name="_csrf" value="a&amp;b&lt;c">'
    eq("entities are unescaped", L._hidden_input(html, "_csrf"), "a&b<c")


def test_normalize_auth_url() -> None:
    http = "http://auth.udiseplus.gov.in/oauth2/authorize?client_id=x"
    eq(
        "http authorize is upgraded to https",
        L.normalize_auth_url(http),
        "https://auth.udiseplus.gov.in/oauth2/authorize?client_id=x",
    )
    already = "https://auth.udiseplus.gov.in/oauth2/authorize?client_id=x"
    eq("https is left alone", L.normalize_auth_url(already), already)


# --------------------------------------------------------------------------
# failure classification — real redirect URLs
# --------------------------------------------------------------------------


def test_classify_captcha_error() -> None:
    url = "https://auth.udiseplus.gov.in/login?captchaError&loginTxnId=abc"
    msg = L.classify_failure(url, "")
    check("captcha error is recognised", "CAPTCHA" in msg, msg)


def test_classify_locked() -> None:
    url = "https://auth.udiseplus.gov.in/login?locked"
    msg = L.classify_failure(url, "")
    check("lockout is recognised", "locked" in msg.lower(), msg)


def test_classify_expired() -> None:
    url = "https://auth.udiseplus.gov.in/login?sessionExpired"
    msg = L.classify_failure(url, "")
    check("expiry is recognised", "expired" in msg.lower(), msg)


def test_classify_bad_credentials() -> None:
    msg = L.classify_failure("https://auth.udiseplus.gov.in/login?error", "")
    check("bad credentials are recognised", "username/password" in msg, msg)
    msg2 = L.classify_failure("", "Invalid credentials supplied")
    check("body text also detects bad credentials", "username/password" in msg2, msg2)


def test_classify_unknown_falls_back() -> None:
    msg = L.classify_failure("https://auth.udiseplus.gov.in/login", "")
    check("unknown failure has a default message", len(msg) > 10, msg)


# --------------------------------------------------------------------------
# cookie handling
# --------------------------------------------------------------------------


class _FakeCookie:
    def __init__(self, name, value, domain="sdms.udiseplus.gov.in", path="/"):
        self.name, self.value, self.domain, self.path = name, value, domain, path


class _FakeJar(list):
    pass


def test_cookie_header_filters_to_sdms() -> None:
    import requests

    s = requests.Session()
    s.cookies.set("JSESSIONID", "j1", domain="sdms.udiseplus.gov.in")
    s.cookies.set("XSRF-TOKEN", "x1", domain="sdms.udiseplus.gov.in")
    s.cookies.set("UA_SID", "should-be-excluded", domain="auth.udiseplus.gov.in")
    header = L.sdms_cookie_header(s)
    check("JSESSIONID included", "JSESSIONID=j1" in header, header)
    check("XSRF-TOKEN included", "XSRF-TOKEN=x1" in header, header)
    check("auth-host cookie excluded", "UA_SID" not in header, header)


def test_cookie_header_dedupes() -> None:
    import requests

    s = requests.Session()
    s.cookies.set("JSESSIONID", "first", domain="sdms.udiseplus.gov.in", path="/")
    s.cookies.set("JSESSIONID", "second", domain="sdms.udiseplus.gov.in", path="/p0/")
    header = L.sdms_cookie_header(s)
    eq("duplicate names appear once", header.count("JSESSIONID="), 1)


def test_dump_and_restore_roundtrip() -> None:
    import requests

    s = requests.Session()
    s.cookies.set("JSESSIONID", "abc", domain="sdms.udiseplus.gov.in", path="/")
    s.cookies.set("XSRF-TOKEN", "def", domain="sdms.udiseplus.gov.in", path="/")
    dumped = L.dump_cookies(s)
    restored = L.restore_session(dumped)
    eq("roundtrip preserves the header", L.sdms_cookie_header(restored), L.sdms_cookie_header(s))


def test_cookies_by_name() -> None:
    import requests

    s = requests.Session()
    s.cookies.set("JSESSIONID", "j", domain="sdms.udiseplus.gov.in")
    s.cookies.set("OTHER", "o", domain="example.com")
    by = L.cookies_by_name(s)
    check("sdms cookie present", by.get("JSESSIONID") == "j")
    check("foreign cookie excluded", "OTHER" not in by)


# --------------------------------------------------------------------------
# carried state — the serverless cookie payload
# --------------------------------------------------------------------------


def test_login_session_roundtrip() -> None:
    original = L.LoginSession(
        csrf="c" * 96,
        login_txn_id="9f1c-uuid",
        auth_url="https://auth.udiseplus.gov.in/oauth2/authorize?state=s",
        state="s",
        client_id="udise-sdms-g0",
        cookies=[{"name": "JSESSIONID", "value": "j", "domain": "x", "path": "/"}],
    )
    wire = json.loads(json.dumps(original.to_dict()))
    back = L.LoginSession.from_dict(wire)
    eq("csrf survives the wire", back.csrf, original.csrf)
    eq("txn survives the wire", back.login_txn_id, original.login_txn_id)
    eq("state survives the wire", back.state, original.state)
    eq("cookies survive the wire", back.cookies, original.cookies)


def test_login_session_from_empty_dict() -> None:
    back = L.LoginSession.from_dict({})
    eq("empty dict gives empty csrf", back.csrf, "")
    eq("empty dict gives empty cookies", back.cookies, [])


def test_carried_state_is_small_enough_for_a_cookie() -> None:
    """A serverless host keeps this in a cookie: must stay well under 4 KB."""
    carried = L.LoginSession(
        csrf="c" * 96,
        login_txn_id="a" * 36,
        auth_url="https://auth.udiseplus.gov.in/oauth2/authorize?client_id=udise-sdms-g0&state=" + "s" * 36,
        state="s" * 36,
        client_id="udise-sdms-g0",
        cookies=[
            {"name": "JSESSIONID", "value": "v" * 60, "domain": "sdms.udiseplus.gov.in", "path": "/"},
            {"name": "XSRF-TOKEN", "value": "v" * 36, "domain": "sdms.udiseplus.gov.in", "path": "/"},
            {"name": "NSC_tent.vejtfqmvt_nqy_Wtfswfs_TTM", "value": "v" * 56, "domain": "sdms.udiseplus.gov.in", "path": "/"},
            {"name": "UA_SID", "value": "v" * 36, "domain": "auth.udiseplus.gov.in", "path": "/"},
        ],
    )
    size = len(json.dumps(carried.to_dict()))
    check("carried state under 2 KB", size < 2048, f"size={size}")
    check("carried state has room to spare under 4 KB", size < 4096, f"size={size}")


# --------------------------------------------------------------------------
# input validation
# --------------------------------------------------------------------------


def test_submit_requires_all_three_fields() -> None:
    carried = L.LoginSession(csrf="c", login_txn_id="t", auth_url="u")
    for label, u, p, c in [
        ("empty username", "", "pw", "cap"),
        ("whitespace username", "   ", "pw", "cap"),
        ("empty password", "user", "", "cap"),
        ("empty captcha", "user", "pw", ""),
    ]:
        try:
            L.submit_login(carried, u, p, c)
            check(f"{label} is rejected", False)
        except L.LoginError as e:
            eq(f"{label} is rejected", e.kind, "input")


def test_begin_login_rejects_bad_bootstrap(monkeypatch=None) -> None:
    """A 200 that is not the expected redirect must fail loudly, not silently."""
    import requests

    class FakeResp:
        status_code = 200
        headers = {"Location": "https://evil.example.com/oauth2/authorize?client_id=x"}

        def raise_for_status(self):
            return None

    class FakeSession(requests.Session):
        def get(self, *a, **k):
            return FakeResp()

    try:
        L.begin_login(FakeSession())
        check("bad bootstrap is rejected", False)
    except L.LoginError as e:
        check("bad bootstrap is rejected", e.kind == "shape", f"kind={e.kind}")


def test_begin_login_rejects_wrong_client_id() -> None:
    import requests

    class FakeResp:
        status_code = 200
        headers = {
            "Location": "https://auth.udiseplus.gov.in/oauth2/authorize?client_id=WRONG&state=s"
        }

        def raise_for_status(self):
            return None

    class FakeSession(requests.Session):
        def get(self, *a, **k):
            return FakeResp()

    try:
        L.begin_login(FakeSession())
        check("wrong client_id is rejected", False)
    except L.LoginError as e:
        check("wrong client_id is rejected", e.kind == "shape", f"kind={e.kind}")


def test_begin_login_rejects_missing_state() -> None:
    import requests

    class FakeResp:
        status_code = 200
        headers = {
            "Location": "https://auth.udiseplus.gov.in/oauth2/authorize?client_id=udise-sdms-g0"
        }

        def raise_for_status(self):
            return None

    class FakeSession(requests.Session):
        def get(self, *a, **k):
            return FakeResp()

    try:
        L.begin_login(FakeSession())
        check("missing state is rejected", False)
    except L.LoginError as e:
        check("missing state is rejected", e.kind == "shape", f"kind={e.kind}")


# --------------------------------------------------------------------------
# submit path — fake session, no network
# --------------------------------------------------------------------------


class _PostResp:
    def __init__(self, url, text=""):
        self.url = url
        self.text = text
        self.status_code = 200


def _submit_with(result_url: str, text: str = "", cookies: dict | None = None):
    """Drive submit_login against a stubbed POST."""
    import requests

    carried = L.LoginSession(
        csrf="csrf", login_txn_id="txn", auth_url="https://auth.udiseplus.gov.in/login"
    )

    class FakeSession(requests.Session):
        def post(self, *a, **k):
            for name, value in (cookies or {}).items():
                self.cookies.set(name, value, domain="sdms.udiseplus.gov.in")
            return _PostResp(result_url, text)

        def get(self, *a, **k):  # check-session
            return _PostResp(L.CHECK_SESSION)

    original_restore = L.restore_session
    original_verify = L.verify_session
    L.restore_session = lambda items: FakeSession()  # type: ignore
    L.verify_session = lambda s: True  # type: ignore
    try:
        return L.submit_login(carried, "user", "pw", "cap")
    finally:
        L.restore_session = original_restore  # type: ignore
        L.verify_session = original_verify  # type: ignore


def test_submit_captcha_failure_on_auth_host() -> None:
    try:
        _submit_with("https://auth.udiseplus.gov.in/login?captchaError")
        check("captcha failure raises", False)
    except L.LoginError as e:
        eq("captcha failure kind", e.kind, "captcha")


def test_submit_lockout() -> None:
    try:
        _submit_with("https://auth.udiseplus.gov.in/login?locked")
        check("lockout raises", False)
    except L.LoginError as e:
        eq("lockout kind", e.kind, "locked")


def test_submit_success_returns_cookie_header() -> None:
    header = _submit_with(
        "https://sdms.udiseplus.gov.in/p0/",
        cookies={"JSESSIONID": "j", "XSRF-TOKEN": "x"},
    )
    check("success returns JSESSIONID", "JSESSIONID=j" in header, header)
    check("success returns XSRF-TOKEN", "XSRF-TOKEN=x" in header, header)


def test_submit_missing_cookies_is_a_failure() -> None:
    try:
        _submit_with("https://sdms.udiseplus.gov.in/p0/", cookies={})
        check("missing cookies raise", False)
    except L.LoginError as e:
        check("missing cookies raise LoginError", e.kind in {"captcha", "credentials"}, e.kind)


def test_submit_unverified_session_is_reported() -> None:
    import requests

    carried = L.LoginSession(csrf="c", login_txn_id="t", auth_url="u")

    class FakeSession(requests.Session):
        def post(self, *a, **k):
            self.cookies.set("JSESSIONID", "j", domain="sdms.udiseplus.gov.in")
            self.cookies.set("XSRF-TOKEN", "x", domain="sdms.udiseplus.gov.in")
            return _PostResp("https://sdms.udiseplus.gov.in/p0/")

    o1, o2 = L.restore_session, L.verify_session
    L.restore_session = lambda items: FakeSession()  # type: ignore
    L.verify_session = lambda s: False  # type: ignore
    try:
        L.submit_login(carried, "user", "pw", "cap")
        check("unverified session raises", False)
    except L.LoginError as e:
        eq("unverified session kind", e.kind, "unverified")
    finally:
        L.restore_session, L.verify_session = o1, o2  # type: ignore


def test_no_playwright_import_anywhere() -> None:
    """The whole point: this module must not pull in a browser.

    Checks the actual import statements, not the prose — the module docstring
    explains why Playwright is unnecessary and so mentions the name.
    """
    src = (Path(__file__).resolve().parent.parent / "udise_vps" / "login_http.py").read_text(
        encoding="utf-8"
    )
    imports = [
        line.strip()
        for line in src.splitlines()
        if line.strip().startswith(("import ", "from ")) and "playwright" in line.lower()
    ]
    eq("login_http does not import playwright", imports, [])
    check("login_http does not import asyncio", "import asyncio" not in src)
    check("login_http only needs requests", "import requests" in src)
    # a browser import would also drag in the async machinery
    check("no async browser API referenced", "async_playwright" not in src)


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        try:
            t()
        except Exception as exc:  # noqa: BLE001
            global FAILED
            FAILED += 1
            print(f"  ERROR in {t.__name__}: {type(exc).__name__}: {exc}")
    total = PASSED + FAILED
    if FAILED:
        print(f"{PASSED}/{total} passed")
        return 1
    print(f"{PASSED}/{total} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
