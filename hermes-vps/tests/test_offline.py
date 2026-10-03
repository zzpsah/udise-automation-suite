"""Offline tests for the VPS port.

No network. These verify the safety rules the notebook enforces are actually
preserved in the ported code:

  - blank-only fill; existing values preserved
  - CWSN=Yes skips entirely
  - preview never writes
  - one POST only; never replayed
  - success requires fresh read-back
  - Finalize only touches fresh status 3
  - status 6 is never re-finalized

The fake below is a stateful portal simulator: a write it accepts is visible to
the next read, which is what makes the read-back assertions meaningful.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udise_vps import completion, finalize, general_profile  # noqa: E402
from udise_vps.session import parse_cookie_header, resolve_school_id  # noqa: E402


# --------------------------------------------------------------- fake portal
class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body if body is not None else {"status": True}

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakePortal:
    """Simulates the observable behaviour of the SDMS portal.

    Flags let a test reproduce the awkward cases:
      persist_gp           apply GP payload on POST (normal save)
      persist_before_fail  apply the write, then raise (ambiguous transport loss)
      persist_submit       apply the finalize write
      submit_new_status    what formStatus becomes after a finalize submit
    """

    def __init__(
        self,
        records,
        *,
        persist_gp=True,
        fail_gp=None,
        persist_before_fail=False,
        persist_submit=True,
        fail_submit=None,
        submit_new_status=6,
    ):
        self.records = {str(k): dict(v) for k, v in records.items()}
        self.persist_gp = persist_gp
        self.fail_gp = fail_gp
        self.persist_before_fail = persist_before_fail
        self.persist_submit = persist_submit
        self.fail_submit = fail_submit
        self.submit_new_status = submit_new_status

        self.headers = {"X-XSRF-TOKEN": "test"}
        self.base_url = "https://example.invalid"
        self.school_id = "2497128"
        self.students = []

        self.gets = []
        self.posts = []
        self.submits = []

        # finalize._submit_once reaches for session.session.post(...)
        self.session = self

    # ------------------------------------------------------------- read path
    def student_detail(self, sid):
        sid = str(sid)
        self.gets.append(sid)
        if sid not in self.records:
            raise RuntimeError(f"no such student {sid}")
        return dict(self.records[sid])

    # ------------------------------------------------------- GP write path
    def post_once(self, route, json_body=None, read_timeout=90):
        sid = route.rstrip("/").split("/")[-1]
        self.posts.append((sid, json_body))

        if self.fail_gp is not None:
            if self.persist_before_fail and json_body:
                self.records[sid].update(json_body)
            raise self.fail_gp

        if self.persist_gp and json_body:
            self.records[sid].update(json_body)
        return 200, {"status": True}

    # ------------------------------------------------- finalize write path
    def post(self, url, headers=None, data=None, timeout=None, allow_redirects=None):
        sid = str(url).rstrip("/").split("/")[-1]
        self.submits.append(sid)

        if self.fail_submit is not None:
            raise self.fail_submit
        if self.persist_submit:
            self.records[sid]["formStatus"] = self.submit_new_status
        return FakeResponse(200, {"status": True})


def student(sid, pen, class_id=9, name="Test Student"):
    return {"studentId": str(sid), "studentCodeNat": pen,
            "classId": class_id, "studentName": name}


# ------------------------------------------------------------------- helpers
def test_parse_cookie_header():
    cookies = parse_cookie_header("JSESSIONID=abc; XSRF-TOKEN=def; other=x")
    assert cookies == {"JSESSIONID": "abc", "XSRF-TOKEN": "def", "other": "x"}
    print("PASS test_parse_cookie_header")


def test_resolve_school_id():
    assert resolve_school_id("https://sdms.udiseplus.gov.in/g0/school/2497128/x") == "2497128"
    assert resolve_school_id("2497128") == "2497128"
    for bad in ("10160203806", "nonsense", ""):
        try:
            resolve_school_id(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {bad!r}")
    print("PASS test_resolve_school_id")


# ------------------------------------------------------------------- AUTO GP
def test_blank_only_fill_preserves_values():
    """Existing nonblank values must survive; only blanks get defaults."""
    portal = FakePortal({"1": {
        "cwsnYN": 2,          # nonblank -> preserved
        "motherTongue": 42,   # nonblank -> preserved
        "isBplYN": None,      # blank   -> filled
        "ewsYN": "",          # blank   -> filled
        "natIndYN": 0,        # blank   -> filled
        "ooscYN": None,       # blank   -> filled
        "bloodGroup": None,   # blank   -> filled
    }})
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=True)

    assert len(portal.posts) == 1, f"expected one POST, got {len(portal.posts)}"
    _, payload = portal.posts[0]

    assert payload["cwsnYN"] == 2, "nonblank CWSN must be preserved"
    assert payload["motherTongue"] == 42, "nonblank mother tongue must be preserved"
    assert payload["isBplYN"] == 2, "blank BPL should be filled with No"
    assert payload["ewsYN"] == 2, "blank EWS should be filled with No"
    assert payload["natIndYN"] == 1, "blank national should be filled with Yes"
    assert payload["bloodGroup"] == "9"
    assert results[0].confirmed, results[0].status
    print("PASS test_blank_only_fill_preserves_values")


def test_untouched_fields_are_carried_into_payload():
    """A write must not silently drop unrelated profile fields."""
    portal = FakePortal({"1": {
        "cwsnYN": 2, "motherTongue": 42, "socCatId": 2, "minorityId": 7,
        "isBplYN": None,
    }})
    portal.students = [student("1", "PEN1")]

    general_profile.run_auto_gp(portal, allow_submit=True)
    _, payload = portal.posts[0]

    assert payload["motherTongue"] == 42
    assert payload["socCatId"] == 2
    assert payload["minorityId"] == 7
    assert payload["cwsnYN"] == 2
    print("PASS test_untouched_fields_are_carried_into_payload")


def test_cwsn_yes_is_skipped():
    """CWSN=Yes must skip entirely — no POST at all."""
    portal = FakePortal({"1": {"cwsnYN": 1, "isBplYN": None}})
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=True)

    assert not portal.posts, "CWSN=Yes must never POST"
    assert results[0].status == "SKIPPED_CWSN"
    print("PASS test_cwsn_yes_is_skipped")


def test_unexpected_cwsn_code_is_skipped():
    portal = FakePortal({"1": {"cwsnYN": 5, "isBplYN": None}})
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=True)

    assert not portal.posts
    assert results[0].status == "SKIPPED_CWSN_UNEXPECTED"
    print("PASS test_unexpected_cwsn_code_is_skipped")


def test_preview_never_writes():
    portal = FakePortal({"1": {"isBplYN": None}})
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=False)

    assert not portal.posts, "preview must not POST"
    assert results[0].status == "PREVIEW"
    print("PASS test_preview_never_writes")


def test_no_blank_fields_means_no_write():
    # Every AUTO field must be present for this to be a true "nothing blank"
    # case. aayBplYN is included because the BPL/AAY rule (4.1.15) would
    # otherwise correctly fill it: BPL=No implies AAY=Not Applicable.
    portal = FakePortal({"1": {"cwsnYN": 2, "motherTongue": 42, "isBplYN": 2,
                               "aayBplYN": 9, "ewsYN": 2, "natIndYN": 1,
                               "ooscYN": 2, "bloodGroup": "9"}})
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=True)

    assert not portal.posts, "nothing blank means no POST"
    assert results[0].status == "NO_CHANGE"
    print("PASS test_no_blank_fields_means_no_write")


def test_submission_cap_is_honoured():
    records = {str(i): {"cwsnYN": 2, "isBplYN": None} for i in range(1, 6)}
    portal = FakePortal(records)
    portal.students = [student(str(i), f"PEN{i}") for i in range(1, 6)]

    general_profile.run_auto_gp(
        portal, run_mode="All students", allow_submit=True, max_submissions=2,
    )

    assert len(portal.posts) == 2, f"cap not honoured: {len(portal.posts)} posts"
    print("PASS test_submission_cap_is_honoured")


def test_post_not_replayed_on_error():
    """A transport error must not trigger a second POST."""
    portal = FakePortal(
        {"1": {"cwsnYN": 2, "isBplYN": None}},
        fail_gp=ConnectionError("connection lost"),
        persist_before_fail=True,
    )
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=True)

    assert len(portal.posts) == 1, f"POST replayed: {len(portal.posts)}"
    assert results[0].status == "SUCCESS_CONFIRMED_AFTER_POST_ERROR", results[0].status
    print("PASS test_post_not_replayed_on_error")


def test_post_error_without_persistence_is_unconfirmed():
    """Transport error and no persisted change must stop for manual review."""
    portal = FakePortal(
        {"1": {"cwsnYN": 2, "isBplYN": None}},
        fail_gp=ConnectionError("connection lost"),
        persist_before_fail=False,
    )
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=True)

    assert len(portal.posts) == 1
    assert results[0].status == "UNCONFIRMED"
    print("PASS test_post_error_without_persistence_is_unconfirmed")


def test_unconfirmed_when_readback_differs():
    """POST accepted but read-back does not match => UNCONFIRMED."""
    portal = FakePortal({"1": {"cwsnYN": 2, "isBplYN": None}}, persist_gp=False)
    portal.students = [student("1", "PEN1")]

    results = general_profile.run_auto_gp(portal, allow_submit=True)

    assert results[0].status == "UNCONFIRMED"
    assert not results[0].confirmed
    print("PASS test_unconfirmed_when_readback_differs")


# ------------------------------------------------------------------ finalize
def test_finalize_only_touches_status_3():
    portal = FakePortal({"1": {"formStatus": 2}})
    portal.students = [student("1", "PEN1")]

    results = finalize.finalize(portal, ["PEN1"], allow_finalize=True)

    assert not portal.submits, "status 2 must not be finalized"
    assert results[0].status == "SKIPPED_NOT_READY"
    print("PASS test_finalize_only_touches_status_3")


def test_finalize_blocks_status_0_1():
    for status in (0, 1):
        portal = FakePortal({"1": {"formStatus": status}})
        portal.students = [student("1", "PEN1")]
        results = finalize.finalize(portal, ["PEN1"], allow_finalize=True)
        assert not portal.submits, f"status {status} must not be finalized"
        assert results[0].status == "SKIPPED_NOT_READY"
    print("PASS test_finalize_blocks_status_0_1")


def test_finalize_skips_status_6():
    portal = FakePortal({"1": {"formStatus": 6}})
    portal.students = [student("1", "PEN1")]

    results = finalize.finalize(portal, ["PEN1"], allow_finalize=True)

    assert not portal.submits, "status 6 must never be re-finalized"
    assert results[0].status == "SKIPPED_ALREADY_COMPLETE"
    print("PASS test_finalize_skips_status_6")


def test_finalize_preview_no_post():
    portal = FakePortal({"1": {"formStatus": 3}})
    portal.students = [student("1", "PEN1")]

    results = finalize.finalize(portal, ["PEN1"], allow_finalize=False)

    assert not portal.submits, "preview must not POST"
    assert results[0].status == "PREVIEW"
    print("PASS test_finalize_preview_no_post")


def test_finalize_status_3_to_6_confirmed():
    portal = FakePortal({"1": {"formStatus": 3}}, submit_new_status=6)
    portal.students = [student("1", "PEN1")]

    results = finalize.finalize(portal, ["PEN1"], allow_finalize=True)

    assert len(portal.submits) == 1, f"expected one POST, got {len(portal.submits)}"
    assert results[0].confirmed, results[0].status
    print("PASS test_finalize_status_3_to_6_confirmed")


def test_finalize_unconfirmed_when_not_6():
    portal = FakePortal({"1": {"formStatus": 3}}, submit_new_status=3)
    portal.students = [student("1", "PEN1")]

    results = finalize.finalize(portal, ["PEN1"], allow_finalize=True)

    assert results[0].status == "UNCONFIRMED"
    assert not results[0].confirmed
    print("PASS test_finalize_unconfirmed_when_not_6")


def test_finalize_stops_batch_after_unconfirmed():
    """An unconfirmed result must stop the batch, not continue."""
    portal = FakePortal(
        {"1": {"formStatus": 3}, "2": {"formStatus": 3}},
        submit_new_status=3,
    )
    portal.students = [student("1", "PEN1"), student("2", "PEN2")]

    finalize.finalize(portal, ["PEN1", "PEN2"], allow_finalize=True)

    assert len(portal.submits) == 1, f"batch should stop: {len(portal.submits)}"
    print("PASS test_finalize_stops_batch_after_unconfirmed")


def test_finalize_cap_is_honoured():
    portal = FakePortal(
        {str(i): {"formStatus": 3} for i in range(1, 4)},
        submit_new_status=6,
    )
    portal.students = [student(str(i), f"PEN{i}") for i in range(1, 4)]

    finalize.finalize(portal, ["PEN1", "PEN2", "PEN3"],
                      allow_finalize=True, max_submissions=2)

    assert len(portal.submits) == 2, f"cap not honoured: {len(portal.submits)}"
    print("PASS test_finalize_cap_is_honoured")


def test_finalize_unknown_pen_is_reported():
    portal = FakePortal({"1": {"formStatus": 3}})
    portal.students = [student("1", "PEN1")]

    results = finalize.finalize(portal, ["NOPE"], allow_finalize=True)

    assert results[0].status == "NOT_FOUND"
    assert not portal.submits
    print("PASS test_finalize_unknown_pen_is_reported")


# ---------------------------------------------------------------- completion
def test_completion_groups_by_status():
    portal = FakePortal({
        "1": {"formStatus": 0, "studentName": "A"},
        "2": {"formStatus": 3, "studentName": "B"},
        "3": {"formStatus": 6, "studentName": "C"},
        "4": {"formStatus": 1, "studentName": "D"},
    })
    portal.students = [student(str(i), f"PEN{i}") for i in range(1, 5)]

    report = completion.scan_completion(portal)

    assert report.ready_pens == ["PEN2"], report.ready_pens
    assert report.completed_pens == ["PEN3"]
    assert report.all_pending_pens == ["PEN1"]
    assert report.gp_only_pens == ["PEN4"]
    assert not portal.posts and not portal.submits, "scan must be read-only"
    print("PASS test_completion_groups_by_status")


def test_completion_survives_read_error():
    portal = FakePortal({"1": {"formStatus": 0}})
    portal.students = [student("1", "PEN1"), student("2", "PEN2")]

    report = completion.scan_completion(portal)

    assert report.failed == ["PEN2"], report.failed
    assert len(report.rows) == 2, "a failed read must still produce a row"
    assert any(r.form_status == "ERROR" for r in report.rows)
    print("PASS test_completion_survives_read_error")


def test_completion_scope_filters_classes():
    portal = FakePortal({
        "1": {"formStatus": 3, "studentName": "IX"},
        "2": {"formStatus": 3, "studentName": "XI"},
    })
    portal.students = [student("1", "PEN1", class_id=9),
                       student("2", "PEN2", class_id=11)]

    report = completion.scan_completion(portal, class_scope_name="IX")

    assert report.ready_pens == ["PEN1"], report.ready_pens
    print("PASS test_completion_scope_filters_classes")


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
