"""Synthetic control-plane test with no portal network access or credentials."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook


def test_preview_lifecycle_and_write_lock() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        root = Path(directory)
        token_file = root / "api-token"
        token_file.write_text("synthetic-token\n", encoding="utf-8")
        os.environ["UDISE_CONTROL_STATE"] = str(root / "state")
        os.environ["UDISE_CONTROL_RUNTIME"] = str(root / "runtime")
        os.environ["UDISE_CONTROL_TOKEN_FILE"] = str(token_file)
        os.environ["UDISE_VPS_RUNNER"] = str(root / "synthetic-runner")

        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from control_api import app as api

        session_id = "synthetic_session_identifier_12345"
        api._json_write(
            api.SESSIONS / f"{session_id}.json",
            {
                "cookie": "JSESSIONID=synthetic; XSRF-TOKEN=synthetic",
                "created_at": int(time.time()),
                "expires_at": int(time.time()) + 300,
            },
        )

        observed: dict[str, object] = {}

        class SyntheticProcess:
            def __init__(self, cmd, cwd, env, **_kwargs):
                observed["cmd"] = list(cmd)
                observed["cookie"] = env.get("UDISE_COOKIE_HEADER")
                out_dir = Path(cmd[cmd.index("--out") + 1])
                result = out_dir / "synthetic-gp-preview.xlsx"
                workbook = Workbook()
                sheet = workbook.active
                sheet.title = "Proposed Changes"
                sheet.append(["PEN", "Field", "Current", "Proposed"])
                sheet.append(["SYNTHETIC-1", "motherTongue", "", "42"])
                workbook.save(result)
                self.stdout = iter(
                    [
                        "Authenticated synthetic session\n",
                        "Loaded 2 students\n",
                        f"REPORT_READY={result}\n",
                    ]
                )

            @staticmethod
            def wait() -> int:
                return 0

        original_popen = api.subprocess.Popen
        api.subprocess.Popen = SyntheticProcess
        try:
            authorization = "Bearer synthetic-token"
            capabilities = api.capabilities()
            gp = next(stage for stage in capabilities["stages"] if stage["id"] == "gp")
            assert gp["preview_enabled"] is True

            try:
                api.create_job(
                    api.JobIn(
                        session_id=session_id,
                        school="2497128",
                        stage="gp",
                        class_name="IX",
                        preview=False,
                    ),
                    authorization=authorization,
                )
            except HTTPException as exc:
                assert exc.status_code == 409
            else:
                raise AssertionError("A non-preview write-stage job was accepted")

            queued = api.create_job(
                api.JobIn(
                    session_id=session_id,
                    school="2497128",
                    stage="gp",
                    class_name="IX",
                    preview=True,
                ),
                authorization=authorization,
            )
            deadline = time.time() + 5
            state = None
            while time.time() < deadline:
                state = api.get_job(queued["job_id"], authorization=authorization)
                if state["job"]["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.02)

            assert state is not None
            assert state["job"]["status"] == "completed", state
            assert state["job"]["has_result"] is True
            assert state["job"]["progress_current"] == 2
            assert state["job"]["progress_total"] == 2
            assert "--submit" not in observed["cmd"]
            assert observed["cookie"] == "JSESSIONID=synthetic; XSRF-TOKEN=synthetic"

            with api._db() as connection:
                row = connection.execute(
                    "SELECT result_path FROM jobs WHERE id=?", (queued["job_id"],)
                ).fetchone()
            workbook = load_workbook(row["result_path"], read_only=True)
            assert workbook.sheetnames == ["Proposed Changes"]
            assert workbook["Proposed Changes"].max_row == 2
            workbook.close()
        finally:
            api.subprocess.Popen = original_popen


if __name__ == "__main__":
    test_preview_lifecycle_and_write_lock()
    print("PASS synthetic control API preview lifecycle and write lock")
