"""Offline tests for the eShikshaKosh report-source module.

No network, no credentials, no live portal.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udise_vps import esk  # noqa: E402

PASSED = []
FAILED = []


def check(name):
    def deco(fn):
        try:
            fn()
            PASSED.append(name)
            print(f"PASS {name}")
        except Exception as exc:
            FAILED.append((name, exc))
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
        return fn
    return deco


@check("maintained_vps_script_path_is_first")
def _():
    expected = (
        Path.home() / "projects" / "eshikshakosh-automation" /
        "local-script" / "esk_otr_api.py"
    )
    assert esk._SCRIPT_CANDIDATES[0] == expected


@check("read_credentials_parses_conf")
def _():
    with tempfile.TemporaryDirectory() as d:
        conf = Path(d) / "eshikshakosh.conf"
        conf.write_text(
            "[eshikshakosh]\nudise = 10160203806\n"
            "password = secret123\nyear = 2026-27\n", encoding="utf-8")
        got = esk.read_credentials(conf)
        assert got["udise"] == "10160203806", got
        assert got["password"] == "secret123", got
        assert got["year"] == "2026-27", got


@check("read_credentials_missing_file_returns_empty")
def _():
    assert esk.read_credentials("/nonexistent/nope.conf") == {}


@check("read_credentials_malformed_returns_empty")
def _():
    with tempfile.TemporaryDirectory() as d:
        conf = Path(d) / "bad.conf"
        conf.write_text("this is not an ini file at all\n", encoding="utf-8")
        assert esk.read_credentials(conf) == {}


@check("read_credentials_requires_both_fields")
def _():
    with tempfile.TemporaryDirectory() as d:
        conf = Path(d) / "half.conf"
        conf.write_text("[eshikshakosh]\nudise = 123\n", encoding="utf-8")
        assert esk.read_credentials(conf) == {}


@check("export_report_without_credentials_raises")
def _():
    """A clear error, not a stack trace, when nothing is configured."""
    saved = {k: os.environ.pop(k, None)
             for k in ("ESHIKSHAKOSH_UDISE", "ESHIKSHAKOSH_PASSWORD")}
    real = esk.read_credentials
    real_find = esk.find_fetch_script
    esk.read_credentials = lambda *a, **k: {}
    esk.find_fetch_script = lambda: Path("/fake/esk_otr_api.py")
    try:
        try:
            esk.export_report(udise="", password="")
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert "credential" in str(exc).lower(), str(exc)
    finally:
        esk.read_credentials = real
        esk.find_fetch_script = real_find
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


@check("export_report_uses_script_and_output_path")
def _():
    """The export invokes the bundled script with the right arguments."""
    calls = []

    def fake_run(cmd, capture_output, text, timeout):
        calls.append(cmd)
        out = Path(cmd[cmd.index("--output") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("x", encoding="utf-8")

        class R:
            returncode = 0
            stdout = ""
            stderr = ""
        return R()

    real_run = esk.subprocess.run
    real_find = esk.find_fetch_script
    esk.subprocess.run = fake_run
    esk.find_fetch_script = lambda: Path("/fake/esk_otr_api.py")
    try:
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "r.xlsx"
            got = esk.export_report(udise="10160203806", password="pw",
                                    year="2026-27", output=out)
            assert got == out, got
            assert out.is_file()
            cmd = calls[0]
            assert "--udise" in cmd and "10160203806" in cmd
            assert "--year" in cmd and "2026-27" in cmd
            assert "--output" in cmd
    finally:
        esk.subprocess.run = real_run
        esk.find_fetch_script = real_find


@check("export_report_reports_script_failure")
def _():
    real_run = esk.subprocess.run
    real_find = esk.find_fetch_script
    esk.find_fetch_script = lambda: Path("/fake/esk_otr_api.py")

    class R:
        returncode = 1
        stdout = ""
        stderr = "login failed - no token captured"
    esk.subprocess.run = lambda *a, **k: R()
    try:
        try:
            esk.export_report(udise="1", password="pw",
                              output="/tmp/never.xlsx")
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert "login failed" in str(exc), str(exc)
    finally:
        esk.subprocess.run = real_run
        esk.find_fetch_script = real_find


@check("export_report_without_script_raises")
def _():
    real_find = esk.find_fetch_script
    esk.find_fetch_script = lambda: None
    try:
        try:
            esk.export_report(udise="1", password="pw")
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert "not found" in str(exc).lower(), str(exc)
            assert "--report" in str(exc), "error should point at --report"
    finally:
        esk.find_fetch_script = real_find


print()
if FAILED:
    print(f"{len(PASSED)}/{len(PASSED) + len(FAILED)} passed")
    for name, exc in FAILED:
        print(f"  FAIL {name}: {exc}")
    sys.exit(1)
print(f"{len(PASSED)}/{len(PASSED)} passed")
