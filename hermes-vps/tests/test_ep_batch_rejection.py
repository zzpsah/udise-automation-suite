"""Regression: definitive EP rejection must not consume the selected save limit."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from udise_vps import ep  # noqa: E402


class FakeSession:
    school_id = "school-1"

    def __init__(self, count=2):
        self.students = [
            {"studentId": f"student-{i}", "studentCodeNat": f"PEN{i:03d}",
             "studentName": f"Student {i}", "classId": 9, "rollNo": str(i)}
            for i in range(1, count + 1)
        ]
        self.enrolments = {student["studentId"]: {} for student in self.students}
        self.posts = []

    def student_detail(self, sid):
        return {"studentName": sid, "fatherName": "Parent",
                "dob": "2012-01-01", "uuid": "", "formStatus": 1}

    def get_json(self, endpoint, **kwargs):
        sid = endpoint.rsplit("/", 1)[-1]
        return {"data": self.enrolments[sid]}

    def _request(self, method, endpoint, **kwargs):
        sid = endpoint.rsplit("/", 1)[-1]
        self.posts.append(sid)
        if sid == "student-1":
            return 200, {
                "status": False,
                "error": {"message": "Student profile is not updated yet. "
                                    "Please save the General Profile(GP) first. (ER1010)"},
            }
        self.enrolments[sid] = dict(kwargs["json"])
        return 200, {"status": True}


def test_rejected_student_does_not_consume_ep_save_limit():
    # One rejection followed by five eligible students must still allow
    # five confirmed saves when the operator selects a limit of five.
    session = FakeSession(count=6)
    approved_plan = {
        student["studentCodeNat"]: {"changes": {"admnNumber": str(i)}}
        for i, student in enumerate(session.students, 1)
    }

    with patch.object(ep, "load_subject_rules", return_value={}), \
         patch.object(ep.time, "sleep", return_value=None):
        results = ep.run_ep(
            session,
            class_scope_name="IX",
            limit=0,
            allow_submit=True,
            max_submissions=5,
            approved_plan=approved_plan,
        )

    assert session.posts == [f"student-{i}" for i in range(1, 7)], session.posts
    assert results[0].status == "SKIPPED_GP_REQUIRED"
    assert sum(result.confirmed for result in results) == 5
    assert all(result.confirmed for result in results[1:])

def test_regular_ep_rejection_is_classified_and_batch_continues():
    session = FakeSession()

    with patch.object(ep, "load_subject_rules", return_value={}), \
         patch.object(ep.time, "sleep", return_value=None):
        results = ep.run_ep(
            session,
            class_scope_name="IX",
            limit=0,
            allow_submit=True,
            max_submissions=1,
            approved_plan=None,
        )

    assert session.posts == ["student-1", "student-2"], session.posts
    assert results[0].status == "SKIPPED_GP_REQUIRED"
    assert "ER1010" in results[0].detail
    assert results[1].confirmed is True


def test_ep_summary_separates_limit_reached_from_other(capsys):
    session = FakeSession(count=7)
    approved_plan = {
        student["studentCodeNat"]: {"changes": {"admnNumber": str(i)}}
        for i, student in enumerate(session.students, 1)
    }
    with patch.object(ep, "load_subject_rules", return_value={}), \
         patch.object(ep.time, "sleep", return_value=None):
        results = ep.run_ep(
            session, class_scope_name="IX", limit=0, allow_submit=True,
            max_submissions=5, approved_plan=approved_plan,
        )
    output = capsys.readouterr().out
    assert sum(r.confirmed for r in results) == 5
    assert sum(r.status == "LIMIT_REACHED" for r in results) == 1
    assert "Save limit reached             : 1 (not attempted)" in output
    assert "Other / inspect status         : 0" not in output
    assert "Nothing to fill" not in output
