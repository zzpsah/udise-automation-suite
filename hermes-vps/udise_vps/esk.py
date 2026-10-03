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
    cmd = [str(python), str(script),
           "--udise", udise, "--password", password,
           "--year", year, "--output", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0 or not out.is_file():
        diagnostics = "\n".join(part for part in (proc.stderr, proc.stdout) if part)
        tail = re.sub(r"\s+", " ", diagnostics.strip())[-1600:]
        raise RuntimeError(
            f"eShikshaKosh export failed (exit {proc.returncode}). "
            f"{tail or 'No diagnostic output was returned.'}"
        )
    return out
