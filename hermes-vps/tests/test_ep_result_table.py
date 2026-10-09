"""Offline regression for student-level EP result output."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path


def test_ep_result_table_lists_students() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        os.environ["UDISE_CONTROL_STATE"] = str(root / "state")
        os.environ["UDISE_CONTROL_RUNTIME"] = str(root / "runtime")
        os.environ["UDISE_CONTROL_TOKEN_FILE"] = str(root / "token")
        os.environ["UDISE_VPS_RUNNER"] = str(root / "runner")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from control_api import app

        job_id = "b" * 32
        now = int(time.time())
        with app._db() as conn:
            conn.execute(
                """INSERT INTO jobs(
                    id,created_at,updated_at,status,stage,class_name,school,session_id,preview
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (job_id, now, now, "completed", "ep", "IX", "school", "session", 1),
            )
            events = [
                ("EP_RESULT", "SUCCESS_CONFIRMED", "PEN001", "Ravi Kumar", "Saved and verified"),
                ("EP_SAVE_RESULT", "SKIPPED_NOT_IN_APPROVED_PLAN", "PEN002", "Sunita Devi", "Student was not in the save plan; no POST sent."),
                ("EP_SAVE_RESULT", "LIMIT_REACHED", "PEN003", "Amit Kumar", "Save limit (1) reached; no POST sent."),
                ("EP_SAVE_RESULT", "SKIPPED_STATE_CHANGED", "PEN004", "Pooja Devi", "Live EP values changed since preview: admnNumber. No POST sent."),
            ]
            for event, status, pen, name, detail in events:
                conn.execute(
                    "INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)",
                    (job_id, now, "info", f"📋 {event} status={status} pen={pen} name={name} detail={detail}"),
                )

        output = app._result_table_message(job_id, "ep")
        assert "Status|PEN|Student|Reason / Action" in output
        assert "Saved + confirmed|PEN001|Ravi Kumar|Saved and verified" in output
        assert "Needs fresh preview|PEN002|Sunita Devi|Student was not in the save plan; no POST sent." in output
        assert "Save limit reached|PEN003|Amit Kumar|Save limit (1) reached; no POST sent." in output
        assert "Live value changed|PEN004|Pooja Devi|Live EP values changed since preview: admnNumber. No POST sent." in output


if __name__ == "__main__":
    test_ep_result_table_lists_students()
    print("1/1 passed")
