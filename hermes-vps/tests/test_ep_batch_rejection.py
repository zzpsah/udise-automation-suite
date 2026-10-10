"""Regression: definitive EP rejection must not consume the selected save limit."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from udise_vps import ep  # noqa: E402


class FakeSession:
    school_id = "school-1"

    def __init__(self):
        self.students = [
            {"studentId": "student-1", "studentCodeNat": "PEN001",
             "studentName": "First Student", "classId": 9, "rollNo": "1"},
            {"studentId": "student-2", "studentCodeNat": "PEN002",
             "studentName": "Second Student", "classId": 9, "rollNo": "2"},
        ]
        self.enrolments = {"student-1": {}, "student-2": {}}
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
    session = FakeSession()
    approved_plan = {
        "PEN001": {"changes": {"admnNumber": "1"}},
        "PEN002": {"changes": {"admnNumber": "2"}},
    }

    with patch.object(ep, "load_subject_rules", return_value={}), \
         patch.object(ep.time, "sleep", return_value=None):
        results = ep.run_ep(
            session,
            class_scope_name="IX",
            limit=0,
            allow_submit=True,
            max_submissions=1,
            approved_plan=approved_plan,
        )

    assert session.posts == ["student-1", "student-2"], session.posts
    assert [(r.pen, r.status) for r in results] == [
        ("PEN001", "SKIPPED_GP_REQUIRED"),
        ("PEN002", "SUCCESS_CONFIRMED_BY_RESPONSE_AND_READBACK"),
    ]
    assert results[1].confirmed is True

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
