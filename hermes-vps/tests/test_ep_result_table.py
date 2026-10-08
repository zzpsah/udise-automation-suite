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
            for pen, name in (("PEN001", "Ravi Kumar"), ("PEN002", "Sunita Devi")):
                conn.execute(
                    "INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)",
                    (
                        job_id,
                        now,
                        "info",
                        f"📋 EP_RESULT status=SUCCESS_CONFIRMED pen={pen} "
                        f"name={name} detail=Saved and verified",
                    ),
                )

        output = app._result_table_message(job_id, "ep")
        assert "Status|PEN|Student|Detail" in output
        assert "Saved + confirmed|PEN001|Ravi Kumar|Saved and verified" in output
        assert "Saved + confirmed|PEN002|Sunita Devi|Saved and verified" in output


if __name__ == "__main__":
    test_ep_result_table_lists_students()
    print("1/1 passed")
