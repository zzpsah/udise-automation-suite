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
        write_job_id = "d" * 32
        with app._db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,auto_write_job_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, now, now, "awaiting_input", "gp", "X", "school", "session", 1, "Manual review pending", write_job_id),
            )
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,approved_from) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (write_job_id, now, now, "queued", "gp", "X", "school", "session", 0, "Approved plan queued", job_id),
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
        assert result["write_job_id"] == write_job_id
        assert "PEN1" not in remaining and "PEN2" in remaining
        assert "PEN1" in deferred and "no GP write was sent" in deferred["PEN1"]["reason"]
        assert status == "awaiting_input"
        assert any("GP-MANUAL-SKIPPED" in event for event in events)
        assert not (job_dir / "approved-plan.json").exists()

        # If a manual subset was submitted, skipping the final pending student
        # must follow that newer manual child, not the older automatic child.
        manual_write_id = "e" * 32
        with app._db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,approved_from) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (manual_write_id, now + 1, now + 1, "completed", "gp", "X", "school", "session", 0, "Manual subset completed", job_id),
            )
        final = app.skip_gp_manual_student(job_id, {"student_key": "PEN2"}, authorization="test")
        with app._db() as conn:
            final_status = conn.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()["status"]
        assert final["remaining_students"] == 0
        assert final["write_job_id"] == manual_write_id
        assert final_status == "completed"
        assert "approved-plan save job" in final["message"]

        # Skip All must defer every currently pending candidate in one request,
        # while preserving the independent approved-plan save job.
        all_job_id = "a" * 32
        all_write_job_id = "b" * 32
        with app._db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,auto_write_job_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (all_job_id, now, now, "awaiting_input", "gp", "X", "school", "session", 1, "Manual review pending", all_write_job_id),
            )
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,approved_from) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (all_write_job_id, now, now, "queued", "gp", "X", "school", "session", 0, "Approved plan queued", all_job_id),
            )
        all_dir = app.JOBS / all_job_id
        all_dir.mkdir(parents=True, exist_ok=True)
        all_pending = {f"PEN{i}": {"pen": f"PEN{i}", "name": f"Student {i}", "fields": ["address"]} for i in range(3)}
        (all_dir / "gp-manual-pending.json").write_text(json.dumps(all_pending), encoding="utf-8")
        all_result = app.skip_gp_manual_student(all_job_id, {"skip_all": True}, authorization="test")
        left = json.loads((all_dir / "gp-manual-pending.json").read_text(encoding="utf-8"))
        deferred_all = json.loads((all_dir / "gp-manual-skipped.json").read_text(encoding="utf-8"))
        with app._db() as conn:
            all_status = conn.execute("SELECT status FROM jobs WHERE id=?", (all_job_id,)).fetchone()["status"]
        assert all_result["skip_all"] is True and all_result["skipped_now"] == 3
        assert all_result["remaining_students"] == 0 and all_result["write_job_id"] == all_write_job_id
        assert left == {} and set(deferred_all) == set(all_pending)
        assert all_status == "completed"
        # Skip All must not modify the independent approved write plan.
        assert not (all_dir / "approved-plan.json").exists()


def test_job_dict_hides_manual_queue_during_auto_save_initialization() -> None:
    """An awaiting-input GP parent is still processing while its child is linked."""
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
        now = int(time.time())
        job_id = "c" * 32
        with app._db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,auto_save) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, now, now, "awaiting_input", "gp", "IX", "school", "session", 1, "Manual review pending", 1),
            )
        job_dir = app.JOBS / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "gp-manual-pending.json").write_text(json.dumps({"PEN1": {"pen":"PEN1","name":"Manual Student","fields":["address"]}}))
        (job_dir / "approved-plan.json").write_text(json.dumps({"PEN2": {"pen":"PEN2","name":"Eligible Student","changes":{"motherTongue":42}}}))
        with app._db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        state = app._job_dict(row)
        assert state["auto_write_job_status"] == "preparing"
        assert "initialized" in state["auto_write_job_message"]

        # A preview with manual candidates but no automatic entries must not
        # wait forever for a child that correctly will not be created.
        (job_dir / "approved-plan.json").write_text("{}")
        with app._db() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        state = app._job_dict(row)
        assert state["auto_write_job_status"] == "no_changes"


def test_skip_all_supported_gp_classes() -> None:
    """The manual GP queue lifecycle is class-agnostic for IX/X/XI/XII."""
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
        now = int(time.time())
        for index, class_name in enumerate(("IX", "X", "XI", "XII"), start=1):
            job_id = f"{index:032x}"
            write_job_id = f"{index + 100:032x}"
            with app._db() as conn:
                conn.execute(
                    "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,auto_write_job_id) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (job_id, now, now, "awaiting_input", "gp", class_name, "school", "session", 1, "Manual review pending", write_job_id),
                )
                conn.execute(
                    "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message,approved_from) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (write_job_id, now, now, "queued", "gp", class_name, "school", "session", 0, "Approved plan queued", job_id),
                )
            job_dir = app.JOBS / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            pending = {f"PEN-{class_name}": {"pen": f"PEN-{class_name}", "name": f"Student {class_name}", "fields": ["address"]}}
            (job_dir / "gp-manual-pending.json").write_text(json.dumps(pending), encoding="utf-8")
            result = app.skip_gp_manual_student(job_id, {"skip_all": True}, authorization="test")
            left = json.loads((job_dir / "gp-manual-pending.json").read_text(encoding="utf-8"))
            deferred = json.loads((job_dir / "gp-manual-skipped.json").read_text(encoding="utf-8"))
            assert result["skip_all"] is True, class_name
            assert result["remaining_students"] == 0, class_name
            assert result["write_job_id"] == write_job_id, class_name
            assert left == {} and f"PEN-{class_name}" in deferred, class_name
            with app._db() as conn:
                stored_class = conn.execute("SELECT class_name FROM jobs WHERE id=?", (job_id,)).fetchone()["class_name"]
            assert stored_class == class_name, class_name


def test_manual_gp_save_keeps_verified_fields_when_auto_defaults_go_stale() -> None:
    """Stale AUTO defaults are omitted, while verified manual fields can proceed."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from udise_vps.general_profile import (
        approved_gp_conflicts, reconcile_approved_gp_conflicts, resolve_approved_gp_changes,
    )

    # The same invalid code 9 treated as eligible during preview must not be
    # rejected as a stale nonblank value during save.
    assert approved_gp_conflicts({"natIndYN": 9}, {"natIndYN": 1}) == []
    assert approved_gp_conflicts({"isBplYN": "9"}, {"isBplYN": 2}) == []
    assert approved_gp_conflicts({"natIndYN": 1}, {"natIndYN": 2}) == ["natIndYN"]
    # The school's explicit Indian-national invariant intentionally corrects No to Yes.
    assert approved_gp_conflicts({"natIndYN": 2}, {"natIndYN": 1}) == []
    assert approved_gp_conflicts({"cwsnYN": 1}, {"cwsnYN": 2}) == []

    # If the first portal snapshot has a conflicting value but an immediate
    # fresh re-read shows the field blank/invalid, use the latest snapshot.
    chosen, conflicts, retried = reconcile_approved_gp_conflicts(
        {"ewsYN": 1}, {"ewsYN": None}, {"ewsYN": 2}
    )
    assert chosen == {"ewsYN": None} and conflicts == [] and retried is True
    # A persistent valid conflict remains blocking; never overwrite it.
    chosen, conflicts, retried = reconcile_approved_gp_conflicts(
        {"ewsYN": 1}, {"ewsYN": 1}, {"ewsYN": 2}
    )
    assert chosen == {"ewsYN": 1} and conflicts == ["ewsYN"] and retried is False
    # Never retry around a conflicting explicitly entered manual field.
    chosen, conflicts, retried = reconcile_approved_gp_conflicts(
        {"address": "Old verified address"}, {"address": "Old verified address"},
        {"address": "New verified address"}, {"address"}
    )
    assert conflicts == ["address"] and retried is False

    changes = {"motherTongue": 28, "isBplYN": 2, "address": "Verified address", "pincode": "843001", "minorityId": 1}
    updates, blocking, skipped = resolve_approved_gp_changes(
        changes, ["isBplYN"], {"address", "pincode", "minorityId"}
    )
    assert updates == {"motherTongue": 28, "address": "Verified address", "pincode": "843001", "minorityId": 1}
    assert blocking == [] and skipped == ["isBplYN"]

    # If an explicitly entered manual value conflicts with the live record,
    # preserve the no-overwrite safeguard and do not submit any part of it.
    updates, blocking, skipped = resolve_approved_gp_changes(
        changes, ["address", "isBplYN"], {"address", "pincode", "minorityId"}
    )
    assert updates == {} and blocking == ["address"] and skipped == []

    # Ordinary approved plans keep their original all-or-nothing stale check.
    updates, blocking, skipped = resolve_approved_gp_changes(changes, ["isBplYN"])
    assert updates == {} and blocking == ["isBplYN"] and skipped == []


def test_manual_gp_address_validation_matches_udise_portal() -> None:
    """Reject short addresses before queueing a write; accept portal-valid lengths."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        os.environ["UDISE_CONTROL_STATE"] = str(root / "state")
        os.environ["UDISE_CONTROL_RUNTIME"] = str(root / "runtime")
        os.environ["UDISE_CONTROL_TOKEN_FILE"] = str(root / "token")
        os.environ["UDISE_VPS_RUNNER"] = str(root / "runner")
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import importlib
        from fastapi import HTTPException
        from control_api import app
        importlib.reload(app)
        app.require_api = lambda authorization: None
        app.threading.Thread = lambda *args, **kwargs: type("NoStart", (), {"start": lambda self: None})()
        now = int(time.time())
        job_id = "e" * 32
        with app._db() as conn:
            conn.execute(
                "INSERT INTO jobs(id,created_at,updated_at,status,stage,class_name,school,session_id,preview,message) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (job_id, now, now, "awaiting_input", "gp", "IX", "school", "session", 1, "Manual review"),
            )
        job_dir = app.JOBS / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        pending = {"PEN1": {"pen":"PEN1", "student_id":"S1", "name":"Student One", "fields":["address", "pincode", "minorityId", "socCatId"]}}
        item = {"pen":"PEN1", "student_id":"S1", "name":"Student One", "changes":{"motherTongue":42}}
        (job_dir / "gp-manual-pending.json").write_text(json.dumps(pending), encoding="utf-8")
        (job_dir / "approved-plan.json").write_text(json.dumps({"PEN1":item}), encoding="utf-8")
        (job_dir / "gp-manual-plan.json").write_text(json.dumps({"PEN1":item}), encoding="utf-8")
        try:
            app.submit_gp_manual(job_id, {"students":{"PEN1":{"address":"Jale", "pincode":"847302", "minorityId":"7", "socCatId":"4"}}}, authorization="test")
            raise AssertionError("short address should be rejected")
        except HTTPException as exc:
            assert exc.status_code == 422
            assert "10–150 characters" in str(exc.detail)
        result = app.submit_gp_manual(job_id, {"students":{"PEN1":{"address":"Jale, Darbhanga, Bihar", "pincode":"847302", "minorityId":"7", "socCatId":"4"}}}, authorization="test")
        assert result["queued"] is True and result["students"] == 1
        child = app.JOBS / result["write_job_id"] / "approved-plan.json"
        saved = json.loads(child.read_text(encoding="utf-8"))
        assert saved["PEN1"]["changes"]["address"] == "Jale, Darbhanga, Bihar"
        assert saved["PEN1"]["changes"]["socCatId"] == 4


def test_approved_gp_batch_only_processes_allowlisted_students() -> None:
    """A one-student manual batch must not count the other class students as outcomes."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from udise_vps.general_profile import filter_approved_gp_students
    students = [
        {"studentCodeNat": "PEN1", "studentId": "S1"},
        {"studentCodeNat": "PEN2", "studentId": "S2"},
        {"studentCodeNat": "PEN3", "studentId": "S3"},
    ]
    batch, excluded = filter_approved_gp_students(students, {"PEN2": {"changes": {"address": "Verified"}}})
    assert batch == [students[1]]
    assert excluded == 2
    # Student-ID keys are also supported by approved plans.
    batch, excluded = filter_approved_gp_students(students, {"S3": {"changes": {"address": "Verified"}}})
    assert batch == [students[2]] and excluded == 2
    # Preview mode without an approved plan retains the original class scope.
    batch, excluded = filter_approved_gp_students(students, None)
    assert batch == students and excluded == 0


if __name__ == "__main__":
    test_skip_manual_gp_candidate_defers_without_write()
    test_skip_all_supported_gp_classes()
    test_job_dict_hides_manual_queue_during_auto_save_initialization()
    test_manual_gp_save_keeps_verified_fields_when_auto_defaults_go_stale()
    test_manual_gp_address_validation_matches_udise_portal()
    test_approved_gp_batch_only_processes_allowlisted_students()
    print("6/6 passed")
