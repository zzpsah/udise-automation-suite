"""VidyaDesk UDISE status contract tests; synthetic DB only, no portal access."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def api(tmp_path, monkeypatch):
    token_file = tmp_path / "control-token"
    token_file.write_text("synthetic-control-token\n", encoding="utf-8")
    monkeypatch.setenv("UDISE_CONTROL_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("UDISE_CONTROL_RUNTIME", str(tmp_path / "runtime"))
    monkeypatch.setenv("UDISE_CONTROL_TOKEN_FILE", str(token_file))
    monkeypatch.setenv("UDISE_VIDYADESK_READ_TOKEN", "synthetic-vidyadesk-token")
    sys.modules.pop("control_api.app", None)
    module = importlib.import_module("control_api.app")
    yield module
    sys.modules.pop("control_api.app", None)


def test_returns_fixed_school_aggregate_only(api):
    now = int(time.time())
    with api._db() as conn:
        conn.executemany(
            """INSERT INTO jobs(id,created_at,updated_at,status,stage,school,session_id,preview,message,error)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            [
                ("private-job-1", now - 50, now - 10, "completed", "gp", "2497128", "session-secret-1", 1, "student-specific message", "private error"),
                ("private-job-2", now - 60, now - 20, "failed", "ep", "2497128", "session-secret-2", 1, "another student detail", "sensitive error"),
                ("other-school-job", now - 10, now - 5, "running", "facility", "other-school", "other-session", 1, "other school", ""),
            ],
        )
    result = api._vidyadesk_job_summary(now=now)
    assert result["ok"] is True
    assert result["scope"] == {
        "schoolKey": "umv-tetahali", "schoolName": "UMV Tetahali", "udiseCode": "10160203806"
    }
    assert result["totalJobs"] == 2
    assert result["byStatus"]["completed"] == 1
    assert result["byStatus"]["failed"] == 1
    assert result["byStage"]["gp"] == 1
    assert result["byStage"]["ep"] == 1
    serialized = json.dumps(result)
    for private in ("private-job-1", "private-job-2", "other-school-job", "session-secret", "student-specific", "sensitive error", "other-school"):
        assert private not in serialized


def test_stale_jobs_and_unknown_states_are_flagged(api):
    with api._db() as conn:
        conn.executemany(
            """INSERT INTO jobs(id,created_at,updated_at,status,stage,school,session_id,preview)
               VALUES(?,?,?,?,?,?,?,?)""",
            [
                ("stale-queued", 100, 100, "queued", "gp", "2497128", "session-1", 1),
                ("stale-running", 100, 100, "running", "ep", "2497128", "session-2", 1),
                ("unknown-state", 900, 900, "mystery", "new-stage", "2497128", "session-3", 1),
            ],
        )
    result = api._vidyadesk_job_summary(now=2000)
    assert result["ok"] is False
    assert result["staleQueued"] == 1
    assert result["staleRunning"] == 1
    assert result["unknownStatusCount"] == 1
    assert result["unknownStageCount"] == 1
    assert "stale-queued" not in json.dumps(result)


def test_dedicated_token_is_separate_and_fails_closed(api):
    assert api.vidyadesk_status("synthetic-vidyadesk-token")["service"] == "udise-control"
    with pytest.raises(HTTPException) as exc:
        api.vidyadesk_status("synthetic-control-token")
    assert exc.value.status_code == 401
    with patch.object(api, "VIDYADESK_READ_TOKEN", ""):
        with pytest.raises(HTTPException) as exc:
            api.vidyadesk_status("anything")
    assert exc.value.status_code == 401


def test_summary_uses_sqlite_read_only_mode(api):
    # The adapter must not invoke the normal schema-initialising _db() helper.
    with patch.object(api, "_db", side_effect=AssertionError("write-capable DB helper used")):
        result = api._vidyadesk_job_summary()
    assert result["totalJobs"] == 0


def test_status_route_does_not_require_or_use_control_api_bearer(api):
    with api._db() as conn:
        conn.execute(
            """INSERT INTO jobs(id,created_at,updated_at,status,stage,school,session_id,preview)
               VALUES(?,?,?,?,?,?,?,?)""",
            ("safe-job", 100, 100, "completed", "snapshot", "2497128", "session-safe", 1),
        )
    result = api.vidyadesk_status("synthetic-vidyadesk-token")
    assert result["totalJobs"] == 1
    assert "events" not in result and "jobs" not in result
