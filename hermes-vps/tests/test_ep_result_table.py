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

        # GP-prerequisite and other EP_SAVE_RESULT lines must be retained by the
        # live progress filter so the final per-student table can include them.
        visible, current, total = app._progress_line(
            "📋 EP_SAVE_RESULT status=SKIPPED_GP_REQUIRED pen=PEN005 name=Laxmi Kumari detail=ER1010: save General Profile first"
        )
        assert visible is not None and "Laxmi Kumari" in visible and "ER1010" in visible
        assert current is None and total is None

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
                ("EP_SAVE_RESULT", "SKIPPED_GP_REQUIRED", "PEN005", "Laxmi Kumari", "Portal confirmed General Profile prerequisite (ER1010); no EP save confirmed."),
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
        assert "GP required|PEN005|Laxmi Kumari|Portal confirmed General Profile prerequisite (ER1010); no EP save confirmed." in output
        assert "Save limit reached|PEN003|Amit Kumar|Save limit (1) reached; no POST sent." in output
        assert "Live value changed|PEN004|Pooja Devi|Live EP values changed since preview: admnNumber. No POST sent." in output

        finalize_job_id = "c" * 32
        with app._db() as conn:
            conn.execute(
                """INSERT INTO jobs(
                    id,created_at,updated_at,status,stage,class_name,school,session_id,preview
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (finalize_job_id, now, now, "completed", "finalize", "X", "school", "session", 1),
            )
            conn.execute(
                "INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)",
                (finalize_job_id, now, "info", "ℹ️ Finalize preview: 0 eligible students. No students currently have formStatus=3 (Ready to Complete); no finalization is needed for this run."),
            )
        finalize_output = app._result_table_message(finalize_job_id, "finalize")
        assert "Eligible for Finalize|0" in finalize_output
        assert "No students have formStatus=3 (Ready to Complete); no finalization is needed." in finalize_output


if __name__ == "__main__":
    test_ep_result_table_lists_students()
    print("1/1 passed")


def test_gp_result_table_includes_normalized_manual_review_event() -> None:
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
        job_id = "d" * 32
        now = int(time.time())
        with app._db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview) VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, now, now, "completed", "gp", "IX", "school", "session", 1),
            )
            conn.execute(
                "INSERT INTO events(job_id,created_at,level,message) VALUES(?,?,?,?)",
                (job_id, now, "info", "GP-UPDATE: 23136932470 - LAXMI KUMARI - Manual Review Gp Incomplete - Portal formStatus=0; no eligible blank AUTO-GP fields were found."),
            )
        output = app._result_table_message(job_id, "gp")
        assert "Status|PEN|Student|Reason / Action" in output
        assert "Manual Review Gp Incomplete|23136932470|LAXMI KUMARI|Portal formStatus=0; no eligible blank AUTO-GP fields were found." in output
        assert "Other|" not in output
