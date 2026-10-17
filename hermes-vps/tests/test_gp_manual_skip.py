"""Skipping a manual GP candidate defers it without submitting data."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


def test_skip_manual_gp_candidate_defers_without_write() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        os.environ["UDISE_CONTROL_STATE"] = str(root / "state")
        os.environ["UDISE_CONTROL_RUNTIME"] = str(root / "runtime")
        os.environ["UDISE_CONTROL_TOKEN_FILE"] = str(root / "token")
        os.environ["UDISE_VPS_RUNNER"] = str(root / "runner")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import importlib
        from control_api import app
        importlib.reload(app)
        app.require_api = lambda authorization: None

        job_id = "f" * 32
        now = int(time.time())
        with app._db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (job_id, now, now, "awaiting_input", "gp", "X", "school", "session", 1, "Manual review pending"),
            )
        job_dir = app.JOBS / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        pending = {
            "PEN1": {"pen": "PEN1", "student_id": "S1", "name": "Student One", "fields": ["address"]},
            "PEN2": {"pen": "PEN2", "student_id": "S2", "name": "Student Two", "fields": ["pincode"]},
        }
        (job_dir / "gp-manual-pending.json").write_text(json.dumps(pending), encoding="utf-8")

        result = app.skip_gp_manual_student(job_id, {"student_key": "PEN1"}, authorization="test")
        remaining = json.loads((job_dir / "gp-manual-pending.json").read_text(encoding="utf-8"))
        deferred = json.loads((job_dir / "gp-manual-skipped.json").read_text(encoding="utf-8"))
        with app._db() as conn:
            status = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()["status"]
            events = [r["message"] for r in conn.execute("SELECT message FROM events WHERE job_id=?", (job_id,)).fetchall()]
        assert result["skipped"] is True
        assert result["remaining_students"] == 1
        assert "PEN1" not in remaining and "PEN2" in remaining
        assert "PEN1" in deferred and "no GP write was sent" in deferred["PEN1"]["reason"]
        assert status == "awaiting_input"
        assert any("GP-MANUAL-SKIPPED" in event for event in events)
        assert not (job_dir / "approved-plan.json").exists()


if __name__ == "__main__":
    test_skip_manual_gp_candidate_defers_without_write()
    print("1/1 passed")
