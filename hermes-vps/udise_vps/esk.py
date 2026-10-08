"""Obtain the eShikshaKosh OTR report, from an export or by logging in.

The report supplies the Admission No. that UDISE leaves blank. Two sources,
in priority order:

  1. A workbook the operator exported from the eShikshaKosh portal
     (``--report path.xlsx``) — used as-is, no credentials needed.
  2. A live fetch via the bundled ``esk_otr_api.py`` script, which logs in
     with the school's UDISE id + password and writes the same workbook.

Nothing here invents an admission number. If neither source yields a row for
a student, the caller falls back to Roll No. and then to a generated number.
"""
from __future__ import annotations

import os
import json
import re
import subprocess
import sys
from pathlib import Path

# Where a live fetch writes its workbook.
DEFAULT_CACHE_DIR = Path.home() / "Eshikshakosh_OTR_Report" / "local-script"

# Candidate locations of the bundled fetch script, most specific first.
_SCRIPT_CANDIDATES = (
    Path.home() / "projects" / "eshikshakosh-automation" / "local-script" / "esk_otr_api.py",
    Path.home() / "Eshikshakosh_OTR_Report" / "local-script" / "esk_otr_api.py",
    Path.home() / "Eshikshakosh_OTR_Report" / "esk_otr_api.py",
    Path.home() / "esk_otr_api.py",
)

# Candidate credential files, same order.
_CONF_CANDIDATES = (
    Path.home() / "projects" / "eshikshakosh-automation" / "local-script" / "eshikshakosh.conf",
    Path.home() / "Eshikshakosh_OTR_Report" / "local-script" / "eshikshakosh.conf",
    Path.home() / "Eshikshakosh_OTR_Report" / "eshikshakosh.conf",
    Path.home() / "eshikshakosh.conf",
)


def find_fetch_script() -> Path | None:
    """Locate the bundled eShikshaKosh OTR fetch script."""
    for path in _SCRIPT_CANDIDATES:
        if path.is_file():
            return path
    return None


def find_fetch_python(script: Path) -> Path:
    """Use the maintained eShikshaKosh project's environment when available."""
    configured = os.environ.get("ESHIKSHAKOSH_PYTHON", "").strip()
    candidates = [
        Path(configured) if configured else None,
        script.parent.parent / ".venv" / "bin" / "python",
        script.parent / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    return Path(sys.executable)


def read_credentials(conf_path: str | os.PathLike | None = None) -> dict:
    """Read udise / password / year from an eshikshakosh.conf file.

    Returns {} when no file is found. Never raises on a malformed file.
    """
    import configparser

    candidates = [Path(conf_path)] if conf_path else list(_CONF_CANDIDATES)
    for path in candidates:
        if not path.is_file():
            continue
        parser = configparser.ConfigParser()
        try:
            parser.read(path, encoding="utf-8")
        except Exception:
            continue
        for section in ("eshikshakosh", "DEFAULT"):
            if parser.has_section(section) or section == "DEFAULT":
                src = parser[section] if section != "DEFAULT" else parser.defaults()
                udise = (src.get("udise") or "").strip()
                password = (src.get("password") or "").strip()
                year = (src.get("year") or "").strip()
                if udise and password:
                    return {"udise": udise, "password": password,
                            "year": year, "path": str(path)}
    return {}


def export_report(
    *,
    udise: str | None = None,
    password: str | None = None,
    year: str = "2026-27",
    output: str | os.PathLike | None = None,
    timeout: int = 900,
    class_filter: str = "",
    section_filter: str = "",
    stream_filter: str = "",
) -> Path:
    """Log in to eShikshaKosh and export the OTR report workbook.

    Credentials come from the arguments, else the environment
    (ESHIKSHAKOSH_UDISE / ESHIKSHAKOSH_PASSWORD), else eshikshakosh.conf.

    Returns the path written. Raises RuntimeError with an actionable message
    when the script or the credentials are missing, or the export fails.
    """
    script = find_fetch_script()
    if script is None:
        raise RuntimeError(
            "eShikshaKosh fetch script not found. Expected one of:\n  "
            + "\n  ".join(str(p) for p in _SCRIPT_CANDIDATES)
            + "\nPass --report <exported.xlsx> instead, or place the script."
        )

    udise = udise or os.environ.get("ESHIKSHAKOSH_UDISE", "").strip()
    password = password or os.environ.get("ESHIKSHAKOSH_PASSWORD", "").strip()
    conf = {}
    if not (udise and password):
        conf = read_credentials()
        udise = udise or conf.get("udise", "")
        password = password or conf.get("password", "")
        year = year or conf.get("year", "2026-27")

    if not (udise and password):
        raise RuntimeError(
            "No eShikshaKosh credentials. Set ESHIKSHAKOSH_UDISE and "
            "ESHIKSHAKOSH_PASSWORD, add them to eshikshakosh.conf, or pass "
            "--report <exported.xlsx>."
        )

    out = Path(output) if output else (
        DEFAULT_CACHE_DIR / f"Student_OTR_Report_{udise}_{year}.xlsx")
    out.parent.mkdir(parents=True, exist_ok=True)

    python = find_fetch_python(script)
    cmd = [str(python), str(script), "--year", year, "--output", str(out)]
    if class_filter:
        cmd += ["--class", str(class_filter)]
    if section_filter:
        cmd += ["--section", str(section_filter)]
    if stream_filter:
        cmd += ["--stream", str(stream_filter)]
    env = os.environ.copy()
    env["ESHIKSHAKOSH_USERNAME"] = udise
    env["ESHIKSHAKOSH_PASSWORD"] = password
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    if proc.returncode != 0 or not out.is_file():
        diagnostics = "\n".join(part for part in (proc.stderr, proc.stdout) if part)
        flat = re.sub(r"\s+", " ", diagnostics.strip())
        marker = "eShikshaKosh rejected the saved user ID/password."
        if marker in flat:
            detail = flat[flat.index(marker):]
            detail = re.sub(r"\s*\(HTTP\s+\d+\).*", "", detail).strip()
        else:
            error_lines = [
                re.sub(r"^.*?\[(?:ERROR|WARNING)\]\s*", "", line).strip()
                for line in diagnostics.splitlines()
                if "[ERROR]" in line or "[WARNING]" in line
            ]
            detail = error_lines[-1] if error_lines else flat[-600:]
        raise RuntimeError(detail or "eShikshaKosh report fetch failed.")
    return out

def verify_credentials(*, udise: str, password: str, year: str = "2026-27", timeout: int = 120) -> dict:
    """Verify a real eShikshaKosh login and return non-secret school identity."""
    script = find_fetch_script()
    if script is None:
        raise RuntimeError("eShikshaKosh fetch script not found.")
    if not udise or not password:
        raise RuntimeError("eShikshaKosh user ID and password are required.")

    python = find_fetch_python(script)
    env = os.environ.copy()
    env["ESHIKSHAKOSH_USERNAME"] = udise
    env["ESHIKSHAKOSH_PASSWORD"] = password
    proc = subprocess.run(
        [str(python), str(script), "--year", year, "--verify-only"],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    diagnostics = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    if proc.returncode != 0:
        flat = re.sub(r"\s+", " ", diagnostics.strip())
        error_lines = [
            re.sub(r"^.*?\[(?:ERROR|WARNING)\]\s*", "", line).strip()
            for line in diagnostics.splitlines()
            if "[ERROR]" in line or "[WARNING]" in line
        ]
        detail = error_lines[-1] if error_lines else flat[-500:]
        raise RuntimeError(detail or "eShikshaKosh login verification failed.")

    marker = "VERIFY_OK="
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith(marker)), "")
    if not line:
        raise RuntimeError("eShikshaKosh login verification did not return school identity.")
    try:
        data = json.loads(line[len(marker):])
    except Exception as exc:
        raise RuntimeError("eShikshaKosh school identity response could not be read.") from exc
    if not data.get("verified"):
        raise RuntimeError("eShikshaKosh login could not be verified.")
    return {
        "verified": True,
        "udise": str(data.get("udise") or udise),
        "school_id": str(data.get("school_id") or ""),
        "school_name": str(data.get("school_name") or "").strip(),
        "student_count": int(data.get("student_count") or 0),
    }
