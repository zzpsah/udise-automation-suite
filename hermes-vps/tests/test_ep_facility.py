"""Offline tests for the Enrollment (EP) and Facility modules.

No network. Focus is the logic that could silently corrupt portal data:

  - stream codes are mapped by NAME, never by the colliding numeric code
  - admission number: keep saved > use report match > allocate next
  - an ambiguous report match must never auto-fill
  - blank-only fill; saved values preserved
  - read-back mismatch => not confirmed
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from udise_vps import ep, facility  # noqa: E402


# ------------------------------------------------------------------ helpers
def test_stream_codes_are_not_swapped():
    """The two portals number streams differently; names must win."""
    # eShikshaKosh says: 1=Arts, 2=Science
    # UDISE says:        1=Science, 2=Arts
    assert ep.UDISE_STREAM_CODE["SCIENCE"] == 1
    assert ep.UDISE_STREAM_CODE["ARTS"] == 2
    assert ep.UDISE_STREAM_CODE["COMMERCE"] == 3
    # A raw code must never be passed through as a name.
    assert ep.stream_name("Science") == "SCIENCE"
    assert ep.stream_name("Arts") == "ARTS"
    assert ep.stream_name("Commerce") == "COMMERCE"
    assert ep.stream_name("") == ""
    print("PASS test_stream_codes_are_not_swapped")


def test_stream_name_from_eshikshakosh_text():
    """The OTR report stores stream as text; it must map to a UDISE code."""
    assert ep.UDISE_STREAM_CODE[ep.stream_name("Science")] == 1
    assert ep.UDISE_STREAM_CODE[ep.stream_name("Arts")] == 2
    assert ep.UDISE_STREAM_CODE[ep.stream_name("Commerce")] == 3
    # XI/XII have streams; IX/X are N/A.
    assert ep.UDISE_STREAM_CODE[ep.stream_name("N/A")] == 0
    # A blank stream must NOT silently become code 0.
    assert ep.stream_name("") == ""
    print("PASS test_stream_name_from_eshikshakosh_text")


def test_admission_class_isolation():
    """Class 10 numbering must not consume Class 9's sequence.

    Class 9 already reaches 33; Class 10 is empty, so Class 10 starts at 1.
    """
    students = [
        _student(9, "A", "B", "2012-03-02", admission="33"),
        _student(10, "C", "D", "2011-03-02"),
    ]
    decisions = ep.assign_admission_numbers(students, [])
    assert decisions[0]["admission"] == "33"
    assert decisions[1]["admission"] == "0001", decisions[1]
    print("PASS test_admission_class_isolation")


def test_norm_dob_handles_both_portal_formats():
    # UDISE style ISO, eShikshaKosh style DD-Mon-YYYY
    assert ep.norm_dob("2012-03-02") == "02032012"
    assert ep.norm_dob("02-Mar-2012") == "02032012"
    assert ep.norm_dob("02/03/2012") == "02032012"
    print("PASS test_norm_dob_handles_both_portal_formats")


def test_norm_dob_iso_matches_real_portal_data():
    """REGRESSION: real UDISE roster DOB is ISO; the report is ISO too.

    The inherited helper only handled 8-digit runs, so '2012-03-02' became
    '022012' and never matched. Every cross-portal match silently failed.
    """
    udise = ep.norm_dob("2012-03-02")          # roster format
    report = ep.norm_dob("2012-03-02")         # report format
    assert udise == report == "02032012", (udise, report)
    # And the day-month-name variant still normalises the same way.
    assert ep.norm_dob("02-Mar-2012") == "02032012"
    print("PASS test_norm_dob_iso_matches_real_portal_data")


def test_parse_admission_two_digit_year():
    """REGRESSION: real values include '5/25' and '62/25'.

    The inherited regex only looked for a 4-digit year, so '62/25' yielded
    year '' and '5/25' was misread.
    """
    assert ep.parse_admission("12/2026") == (12, "2026")
    assert ep.parse_admission("08/2026") == (8, "2026")
    assert ep.parse_admission("4/2025") == (4, "2025")
    assert ep.parse_admission("62/25") == (62, "25")
    assert ep.parse_admission("5/25") == (5, "25")
    assert ep.expand_year("25") == "2025"
    assert ep.expand_year("2026") == "2026"
    print("PASS test_parse_admission_two_digit_year")


def test_parse_admission_does_not_read_number_as_year():
    """REGRESSION: '142025' is '14/2025', not the number 142025.

    It appears in the Class X report among 25/2025, 24/2025, 08/2025, so the
    separator was simply lost. Reading it as 142025 poisoned the class
    sequence into '142026'.
    """
    number, year = ep.parse_admission("142025")
    assert number == 14, number
    assert year == "2025", year
    print("PASS test_parse_admission_does_not_read_number_as_year")


def test_last4_from_masked_and_unmasked():
    assert ep.last4("467019359802") == "9802"
    assert ep.last4("XXXX-XXXX-9802") == "9802"
    assert ep.last4("") == ""
    print("PASS test_last4_from_masked_and_unmasked")


# -------------------------------------------------------- admission numbers
def _student(class_id, name, father, dob, aadhaar="", admission=""):
    return {"class_id": class_id, "name": name, "father": father,
            "dob": dob, "aadhaar": aadhaar, "admission": admission}


def test_admission_keeps_saved_value():
    students = [_student(9, "A KUMAR", "B KUMAR", "2012-03-02", admission="12/2026")]
    decisions = ep.assign_admission_numbers(students, [])
    assert decisions[0]["admission"] == "12/2026"
    assert decisions[0]["source"] == "kept_saved"
    print("PASS test_admission_keeps_saved_value")


def test_report_class_id_all_four_classes():
    """REGRESSION: 'Class 11'/'Class 12'/'XI'/'XII' must map, not return None.

    The report's Class column reads 'Class 9'..'Class 12' while the portal uses
    'IX'/'X'/'XI'/'XII'. Missing XI/XII silently pushed 153 rows out of scope.
    """
    assert ep.report_class_id("Class 9") == 9
    assert ep.report_class_id("Class 10") == 10
    assert ep.report_class_id("Class 11") == 11
    assert ep.report_class_id("Class 12") == 12
    assert ep.report_class_id("IX") == 9
    assert ep.report_class_id("X") == 10
    assert ep.report_class_id("XI") == 11
    assert ep.report_class_id("XII") == 12
    # 'XI' must not be read as 'X'
    assert ep.report_class_id("XI (Science)") == 11
    assert ep.report_class_id("") is None
    print("PASS test_report_class_id_all_four_classes")


def test_parse_admission_glued_and_odd_forms():
    """REGRESSION: '142025' is '14/2025' with the separator lost.

    Reading it as 142025 poisoned the Class X sequence into '142026'.
    """
    assert ep.parse_admission("142025") == (14, "2025")
    assert ep.parse_admission("14/2025") == (14, "2025")
    assert ep.parse_admission("038/2025") == (38, "2025")
    assert ep.parse_admission("19//2026/SCI") == (19, "2026")
    assert ep.parse_admission("5/25") == (5, "25")
    assert ep.parse_admission("62/25") == (62, "25")
    assert ep.parse_admission("12/2026") == (12, "2026")
    assert ep.parse_admission("") is None
    print("PASS test_parse_admission_glued_and_odd_forms")


def test_admission_uses_roll_number_when_no_report_match():
    """Rule: no report match -> use the roster roll number as admission number."""
    students = [_student(9, "A", "B", "2012-03-02")]
    students[0]["roll"] = "7"
    decisions = ep.assign_admission_numbers(students, [])
    assert decisions[0]["admission"] == "7", decisions[0]
    assert decisions[0]["source"] == "roll_number"
    print("PASS test_admission_uses_roll_number_when_no_report_match")


def test_admission_generates_zero_padded_when_nothing_available():
    """Rule: no report match and no roll -> 0001, continuing from the highest."""
    students = [
        _student(9, "A", "B", "2012-03-02"),   # no roll, no report
    ]
    decisions = ep.assign_admission_numbers(students, [])
    assert decisions[0]["admission"] == "0001", decisions[0]
    assert decisions[0]["source"] == "next_number"
    print("PASS test_admission_generates_zero_padded_when_nothing_available")


def test_admission_generated_continues_after_highest():
    """0001-style generation must continue after the highest used number."""
    students = [
        _student(9, "A", "B", "2012-03-02", admission="33"),
        _student(9, "C", "D", "2012-04-02"),   # no roll, no report
    ]
    decisions = ep.assign_admission_numbers(students, [])
    assert decisions[0]["admission"] == "33"
    assert decisions[1]["admission"] == "0034", decisions[1]
    print("PASS test_admission_generated_continues_after_highest")


def test_admission_roll_preferred_over_generation():
    """A roll number beats a generated number."""
    students = [
        _student(9, "A", "B", "2012-03-02", admission="33"),
        _student(9, "C", "D", "2012-04-02"),
    ]
    students[1]["roll"] = "12"
    decisions = ep.assign_admission_numbers(students, [])
    assert decisions[1]["admission"] == "12", decisions[1]
    assert decisions[1]["source"] == "roll_number"
    print("PASS test_admission_roll_preferred_over_generation")


def test_admission_report_beats_roll():
    """A report match beats the roll number."""
    students = [_student(9, "AAKASH KUMAR", "PRAHLAD KUMAR RAM", "2012-03-02")]
    students[0]["roll"] = "99"
    report = [{"class_id": 9, "name": "AAKASH KUMAR", "father": "PRAHLAD KUMAR RAM",
               "dob": "02-Mar-2012", "aadhaar": "", "admission": "12/2026"}]
    decisions = ep.assign_admission_numbers(students, report)
    assert decisions[0]["admission"] == "12", decisions[0]
    assert decisions[0]["source"] == "eshikshakosh"
    print("PASS test_admission_report_beats_roll")


def test_auto_not_studying_for_invalid_exam_result():
    """Rule: an invalid exam result automatically becomes 'None/Not Studying'."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from udise_vps import ep as ep_mod
    from udise_vps import subjects as S

    class FakeSession:
        school_id = "1"
        students = [{"studentId": "1", "studentCodeNat": "PEN1",
                     "classId": 9, "studentName": "T"}]

        def __init__(self):
            self.record = {
                "admnNumber": None, "enrStatusPY": 2, "examResultPy": 5,
                "moiId": 0, "subject1": 0, "subject2": 0,
                "subject3": 0, "subject4": 0, "subject5": 0, "subject6": 0,
                "academicStream": 0, "classPY": 5, "examMarksPy": 0,
                "attendancePy": 56, "certifiedCheckCount": 0, "rollNumber": None,
                "admnStartDate": "01/01/2026",
            }
            self.posts = []

        def get_json(self, route, **kw):
            if "enrolment" in route:
                return {"status": True, "data": dict(self.record)}
            raise RuntimeError(route)

        def student_detail(self, sid):
            return {"minorityId": 7, "studentName": "T", "fatherName": "F",
                    "dob": "2012-01-01", "uuid": ""}

        def _request(self, method, route, **kw):
            body = kw.get("json") or {}
            self.posts.append(body)
            self.record.update({k: v for k, v in body.items()
                                if k not in ("schoolId", "studentId")})
            return 200, {"status": True}

        def post_once(self, route, json_body=None, read_timeout=90):
            self.posts.append(json_body or {})
            return 200, {"status": True}

    sess = FakeSession()
    results = ep_mod.run_ep(sess, class_scope_name="IX", limit=1,
                            allow_submit=True, max_submissions=1)
    assert sess.posts, "an invalid exam result must still be writable"
    payload = sess.posts[0]
    assert payload["enrStatusPY"] == S.ENR_STATUS_NOT_STUDYING, payload["enrStatusPY"]
    for field in ("classPY", "examResultPy", "examMarksPy", "attendancePy"):
        assert payload[field] is None, f"{field}={payload[field]!r}"
    assert results[0].status != "MANUAL_REVIEW", results[0].status
    print("PASS test_auto_not_studying_for_invalid_exam_result")


def test_auto_not_studying_can_be_disabled():
    """--no-auto-not-studying must report for review instead of writing."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from udise_vps import ep as ep_mod

    class FakeSession:
        school_id = "1"
        students = [{"studentId": "1", "studentCodeNat": "PEN1",
                     "classId": 9, "studentName": "T"}]

        def __init__(self):
            self.posts = []

        def get_json(self, route, **kw):
            if "enrolment" in route:
                return {"status": True, "data": {
                    "admnNumber": None, "enrStatusPY": 2, "examResultPy": 5,
                    "moiId": 4, "subject1": 0, "subject2": 0,
                    "subject3": 0, "subject4": 0, "subject5": 0, "subject6": 0,
                    "academicStream": 0, "classPY": 5, "examMarksPy": 0,
                    "attendancePy": 56, "certifiedCheckCount": 0,
                    "rollNumber": None, "admnStartDate": "01/01/2026"}}
            raise RuntimeError(route)

        def student_detail(self, sid):
            return {"minorityId": 7, "studentName": "T", "fatherName": "F",
                    "dob": "2012-01-01", "uuid": ""}

        def _request(self, *a, **k):
            self.posts.append(k.get("json") or {})
            return 200, {"status": True}

        def post_once(self, route, json_body=None, read_timeout=90):
            self.posts.append(json_body or {})
            return 200, {"status": True}

    sess = FakeSession()
    results = ep_mod.run_ep(sess, class_scope_name="IX", limit=1,
                            allow_submit=True, max_submissions=1,
                            auto_not_studying=False)
    assert not sess.posts, "with the rule off, no POST should be sent"
    assert results[0].status == "MANUAL_REVIEW", results[0].status
    print("PASS test_auto_not_studying_can_be_disabled")


def test_stream_code_direction_is_udise_not_esk():
    """REGRESSION: UDISE academicStream 1=Science, 2=Arts.

    eShikshaKosh numbers them the other way (1=Arts, 2=Science), so a raw code
    from the report must never be reused. Translation is by NAME only.
    """
    assert ep.UDISE_STREAM_CODE["SCIENCE"] == 1
    assert ep.UDISE_STREAM_CODE["ARTS"] == 2
    assert ep.UDISE_STREAM_CODE["COMMERCE"] == 3
    assert ep.UDISE_STREAM_CODE["NOT APPLICABLE"] == 0
    # the label table agrees with the code table
    assert ep.ENUM_LABELS["academicStream"][1] == "Science"
    assert ep.ENUM_LABELS["academicStream"][2] == "Arts"
    print("PASS test_stream_code_direction_is_udise_not_esk")


def test_stream_name_maps_both_portals():
    assert ep.stream_name("Science") == "SCIENCE"
    assert ep.stream_name("SCI") == "SCIENCE"
    assert ep.stream_name("Arts") == "ARTS"
    assert ep.stream_name("Commerce") == "COMMERCE"
    assert ep.stream_name("COMM") == "COMMERCE"
    assert ep.stream_name("N/A") == "NOT APPLICABLE"
    assert ep.stream_name("") == ""
    # 'ARTS' must not be read as 'SCI' and vice versa
    assert ep.stream_name("19/ARTS/2026") == "ARTS"
    assert ep.stream_name("35/2026/SCI") == "SCIENCE"
    print("PASS test_stream_name_maps_both_portals")


def test_resolve_stream_from_report():
    """A report match supplies the stream, translated by name."""
    student = _student(11, "AAKASH KUMAR", "PRAHLAD KUMAR RAM", "2010-03-02")
    report = [{"class_id": 11, "name": "AAKASH KUMAR",
               "father": "PRAHLAD KUMAR RAM", "dob": "02-Mar-2010",
               "aadhaar": "", "admission": "35/2026/SCI", "stream": "Science"}]
    code, label, src = ep.resolve_stream_for_xi(student, report)
    assert (code, label, src) == (1, "SCIENCE", "report"), (code, label, src)


def test_resolve_stream_saved_wins():
    """A stream already saved on UDISE is never overwritten."""
    student = _student(11, "A", "B", "2010-03-02")
    student["academicStream"] = 2
    report = [{"class_id": 11, "name": "A", "father": "B",
               "dob": "02-Mar-2010", "aadhaar": "", "admission": "1/2026",
               "stream": "Science"}]
    code, label, src = ep.resolve_stream_for_xi(student, report)
    assert (code, src) == (2, "saved"), (code, src)


def test_resolve_stream_asks_when_no_report_row():
    """No report match -> the operator is asked."""
    student = _student(11, "NOBODY HERE", "NOBODY", "2010-03-02")
    asked = []

    def ask(name, choices):
        asked.append((name, tuple(choices)))
        return "Commerce"

    code, label, src = ep.resolve_stream_for_xi(student, [], ask=ask)
    assert (code, label, src) == (3, "COMMERCE", "asked"), (code, label, src)
    assert asked and asked[0][1] == ("Science", "Arts", "Commerce"), asked


def test_resolve_stream_unknown_without_ask():
    """No report row and no ask callback -> unknown, never guessed."""
    student = _student(11, "NOBODY HERE", "NOBODY", "2010-03-02")
    code, label, src = ep.resolve_stream_for_xi(student, [])
    assert code is None and src == "unknown", (code, src)


def test_resolve_stream_rejects_bad_ask_answer():
    """A nonsense answer from the prompt must not become a stream."""
    student = _student(11, "X", "Y", "2010-03-02")
    code, label, src = ep.resolve_stream_for_xi(
        student, [], ask=lambda n, c: "Underwater Basket Weaving")
    assert code is None and src == "unknown", (code, src)


def test_stream_choices_order():
    assert ep.STREAM_CHOICES == ("Science", "Arts", "Commerce")


def test_match_ignores_class_mismatch():
    """REGRESSION: the two portals disagree about a student's class.

    A student UDISE holds in Class XI may sit in the report under X or XII.
    Requiring the class to agree lost those matches entirely.
    """
    student = _student(11, "ANSHU KUMARI", "RAJESH KUMAR", "2010-05-04")
    student["aadhaar"] = "123456789012"
    # report says Class 10, UDISE says 11 — same person
    report = [{"class_id": 10, "name": "ANSHU KUMARI", "father": "RAJESH KUMAR",
               "dob": "04-May-2010", "aadhaar": "9999123456789012",
               "admission": "11/2026", "stream": "Arts"}]
    row, problem = ep.match_report(student, report)
    assert row is not None, problem
    assert row["admission"] == "11/2026"


def test_match_aadhaar_last4_is_decisive():
    """Same name but a different Aadhaar last-4 is a different person."""
    student = _student(11, "ANSHU KUMARI", "RAJESH KUMAR", "2010-05-04")
    student["aadhaar"] = "123456789012"          # last4 = 9012
    report = [{"class_id": 11, "name": "ANSHU KUMARI", "father": "RAJESH KUMAR",
               "dob": "04-May-2010", "aadhaar": "000000001111",
               "admission": "99/2026"}]
    row, problem = ep.match_report(student, report)
    assert row is None and problem == "unmatched", (row, problem)


def test_match_aadhaar_beats_dob_conflict():
    """Aadhaar agreement outweighs a mistyped DOB."""
    student = _student(11, "ANSHU KUMARI", "RAJESH KUMAR", "2010-05-04")
    student["aadhaar"] = "123456789012"
    report = [{"class_id": 11, "name": "ANSHU KUMARI", "father": "RAJESH KUMAR",
               "dob": "09-Sep-2011",                 # DOB differs
               "aadhaar": "9999123456789012",        # last4 matches
               "admission": "7/2026"}]
    row, problem = ep.match_report(student, report)
    assert row is not None, problem
    assert row["admission"] == "7/2026"


def test_match_prefers_same_class_on_tie():
    """When two rows are equally good, the same-class one wins."""
    student = _student(11, "ANSHU KUMARI", "RAJESH KUMAR", "2010-05-04")
    report = [
        {"class_id": 10, "name": "ANSHU KUMARI", "father": "RAJESH KUMAR",
         "dob": "04-May-2010", "aadhaar": "", "admission": "10/2026"},
        {"class_id": 11, "name": "ANSHU KUMARI", "father": "RAJESH KUMAR",
         "dob": "04-May-2010", "aadhaar": "", "admission": "11/2026"},
    ]
    row, problem = ep.match_report(student, report)
    assert row is not None, problem
    assert row["admission"] == "11/2026", row


def test_match_ambiguous_across_classes():
    """Two equally good cross-class candidates are reported, not guessed."""
    student = _student(11, "ANSHU KUMARI", "RAJESH KUMAR", "2010-05-04")
    report = [
        {"class_id": 10, "name": "ANSHU KUMARI", "father": "RAJESH KUMAR",
         "dob": "04-May-2010", "aadhaar": "", "admission": "10/2026"},
        {"class_id": 12, "name": "ANSHU KUMARI", "father": "RAJESH KUMAR",
         "dob": "04-May-2010", "aadhaar": "", "admission": "12/2026"},
    ]
    row, problem = ep.match_report(student, report)
    assert row is None and problem == "ambiguous", (row, problem)


def test_admission_uses_report_match():
    students = [_student(9, "AAKASH KUMAR", "PRAHLAD KUMAR RAM", "2012-03-02",
                         aadhaar="467019359802")]
    report = [{"class_id": 9, "name": "AAKASH KUMAR", "father": "PRAHLAD KUMAR RAM",
               "dob": "02-Mar-2012", "aadhaar": "XXXX-XXXX-9802",
               "admission": "12/2026"}]
    decisions = ep.assign_admission_numbers(students, report)
    # UDISE stores the plain number, so the /2026 must be stripped.
    assert decisions[0]["admission"] == "12", decisions[0]
    assert decisions[0]["source"] == "eshikshakosh"
    print("PASS test_admission_uses_report_match")


def test_admission_format_plain_vs_slash_year():
    """REGRESSION: UDISE stores '0001', not '0001/2026'."""
    students = [_student(9, "A", "B", "2012-03-02")]
    # default = plain, zero padded
    d = ep.assign_admission_numbers(students, [])
    assert d[0]["admission"] == "0001", d[0]
    # explicit slash_year
    d = ep.assign_admission_numbers(students, [], style="slash_year")
    assert d[0]["admission"] == "0001/2026", d[0]
    print("PASS test_admission_format_plain_vs_slash_year")


def test_admission_number_part():
    assert ep.admission_number_part("12/2026") == "12"
    assert ep.admission_number_part("08/2026") == "08"
    assert ep.admission_number_part("1") == "1"
    assert ep.admission_number_part("") == ""
    assert ep.admission_number_part(None) == ""
    print("PASS test_admission_number_part")


def test_admission_allocates_next_after_highest():
    """No report match -> next number after the highest already used."""
    students = [
        _student(9, "A KUMAR", "B KUMAR", "2012-03-02", admission="33"),
        _student(9, "C KUMAR", "D KUMAR", "2012-04-02"),  # no admission
    ]
    decisions = ep.assign_admission_numbers(students, [])
    assert decisions[0]["admission"] == "33"
    assert decisions[1]["admission"] == "0034", decisions[1]
    assert decisions[1]["source"] == "next_number"
    print("PASS test_admission_allocates_next_after_highest")


def test_admission_fallback_zero_pad():
    """--fallback-width 2 turns 1 into 01 (UDISE stores plain numbers)."""
    students = [_student(9, "A KUMAR", "B KUMAR", "2012-03-02")]
    decisions = ep.assign_admission_numbers(students, [], fallback_width=2)
    assert decisions[0]["admission"] == "01", decisions[0]
    print("PASS test_admission_fallback_zero_pad")


def test_admission_ambiguous_match_gets_temporary_review_number():
    """Two report rows matching one student must never auto-fill."""
    students = [_student(9, "AAKASH KUMAR", "PRAHLAD KUMAR RAM", "2012-03-02")]
    report = [
        {"class_id": 9, "name": "AAKASH KUMAR", "father": "X", "dob": "02-Mar-2012",
         "aadhaar": "", "admission": "10/2026"},
        {"class_id": 9, "name": "AAKASH KUMAR", "father": "Y", "dob": "02-Mar-2012",
         "aadhaar": "", "admission": "11/2026"},
    ]
    decisions = ep.assign_admission_numbers(students, report)
    assert decisions[0]["source"] == "temporary_review"
    assert decisions[0]["admission"]
    print("PASS test_admission_ambiguous_match_gets_temporary_review_number")


def test_admission_dob_conflict_does_not_block_exact_name_and_father():
    """A DOB mismatch alone must NOT block a match.

    The eShikshaKosh report often carries no Aadhaar, so a DOB difference can
    never be confirmed either way. When the student's name AND father's name
    both match exactly, that is strong enough — DOB is the field most often
    mistyped. Real case: UJALA KHATOON, UDISE DOB 01/01/2007 vs report
    2009-06-07, father 'JAMALUDDIN ANSARI' vs 'MD ZAMAL ANSARI'.
    """
    students = [_student(9, "AAKASH KUMAR", "PRAHLAD KUMAR RAM", "2012-03-02")]
    report = [{"class_id": 9, "name": "AAKASH KUMAR", "father": "PRAHLAD KUMAR RAM",
               "dob": "05-May-2011", "aadhaar": "", "admission": "12/2026"}]
    decisions = ep.assign_admission_numbers(students, report)
    assert decisions[0]["source"] == "eshikshakosh", decisions[0]
    assert decisions[0]["admission"] == "12", decisions[0]
    print("PASS test_admission_dob_conflict_does_not_block_exact_name_and_father")


def test_match_transliterated_father_via_shared_token():
    """'JAMALUDDIN ANSARI' vs 'MD ZAMAL ANSARI' is the same father."""
    assert ep._shares_token("JAMALUDDINANSARI", "MDZAMALANSARI") is True
    # initials must not create a false match
    assert ep._shares_token("MD", "MD") is False
    assert ep._shares_token("", "ANYTHING") is False


def test_match_requires_some_identity_evidence():
    """A DOB-only agreement with no name/father/Aadhaar is not a match."""
    student = _student(9, "AAKASH KUMAR", "PRAHLAD KUMAR RAM", "2012-03-02")
    report = [{"class_id": 9, "name": "SOMEONE ELSE", "father": "DIFFERENT PERSON",
               "dob": "02-Mar-2012", "aadhaar": "", "admission": "77/2026"}]
    row, problem = ep.match_report(student, report)
    assert row is None and problem == "unmatched", (row, problem)


def test_admission_aadhaar_conflict_blocks_match():
    students = [_student(9, "AAKASH KUMAR", "PRAHLAD KUMAR RAM", "2012-03-02",
                         aadhaar="467019359802")]
    report = [{"class_id": 9, "name": "AAKASH KUMAR", "father": "PRAHLAD KUMAR RAM",
               "dob": "02-Mar-2012", "aadhaar": "XXXX-XXXX-1111",
               "admission": "12/2026"}]
    decisions = ep.assign_admission_numbers(students, report)
    assert decisions[0]["source"] == "next_number", decisions[0]
    print("PASS test_admission_aadhaar_conflict_blocks_match")


def test_admission_report_rows_without_numbers_are_ignored():
    students = [_student(9, "A", "B", "2012-03-02")]
    report = [{"class_id": 9, "name": "A", "father": "B", "dob": "02-Mar-2012",
               "aadhaar": "", "admission": ""}]
    decisions = ep.assign_admission_numbers(students, report)
    assert decisions[0]["source"] == "next_number", decisions[0]
    print("PASS test_admission_report_rows_without_numbers_are_ignored")

def test_readback_ignores_absent_fields():
    """Fields we did not submit must not cause a false mismatch."""
    saved = {"admnNumber": "12/2026"}
    expected = {"admnNumber": "12/2026"}
    matched, mismatches = ep.readback_matches(saved, expected)
    assert matched, mismatches
    print("PASS test_readback_ignores_absent_fields")


def test_ep_payload_fills_blank_moi():
    """REGRESSION: moiId=0 is rejected by the portal with ER1096.

    A blank Medium of Instruction must be filled with the school's medium.
    """
    current = {"moiId": 0, "admnNumber": "", "subject1": 0, "subject2": 0}
    payload = ep.build_ep_payload("1", "2", current, {"admnNumber": "18"})
    assert payload["moiId"] == 4, payload["moiId"]  # 04 - Hindi
    print("PASS test_ep_payload_fills_blank_moi")


def test_ep_payload_keeps_saved_moi():
    """A saved medium must never be overwritten."""
    current = {"moiId": 4, "admnNumber": ""}
    payload = ep.build_ep_payload("1", "2", current, {"admnNumber": "18"})
    assert payload["moiId"] == 4
    # and a different saved medium is preserved too
    current = {"moiId": 2, "admnNumber": ""}
    payload = ep.build_ep_payload("1", "2", current, {"admnNumber": "18"})
    assert payload["moiId"] == 2, payload["moiId"]
    print("PASS test_ep_payload_keeps_saved_moi")


def test_ep_payload_moi_override():
    """--moi-id overrides the default for schools with another medium."""
    current = {"moiId": 0, "admnNumber": ""}
    payload = ep.build_ep_payload("1", "2", current, {}, moi_id=6)
    assert payload["moiId"] == 6, payload["moiId"]
    print("PASS test_ep_payload_moi_override")


def test_ep_payload_none_moi_is_filled():
    """A missing (None) moiId is blank and must be filled."""
    current = {"moiId": None, "admnNumber": ""}
    payload = ep.build_ep_payload("1", "2", current, {})
    assert payload["moiId"] == 4, payload["moiId"]
    print("PASS test_ep_payload_none_moi_is_filled")


def test_mandatory_subjects_filled_when_blank():
    """REGRESSION: subjects 3-6 are mandatory; 0 is rejected by the portal."""
    from udise_vps import subjects as S
    assert S.SUBJECT_FIXED_CODES[3] == 401
    assert S.SUBJECT_FIXED_CODES[4] == 402
    assert S.SUBJECT_FIXED_CODES[5] == 404
    assert S.SUBJECT_FIXED_CODES[6] == 612
    assert S.MANDATORY_SUBJECT_SLOTS == (3, 4, 5, 6)
    print("PASS test_mandatory_subjects_filled_when_blank")


def test_exam_result_codes_match_the_portal():
    """REGRESSION: the real enum is 1, 3, 4 — not 1, 2, 3.

    Read from the portal's own EP response field `previousClassExamResult`:
        {"1": "Promoted/Passed",
         "3": "Not Promoted/Not Passed/Repeater",
         "4": "Promoted/Passed without Examination"}

    The notebook's ENUM_LABELS is wrong here: it lists 2 and 3, but the portal
    rejects 2 and accepts 4.
    """
    from udise_vps import subjects as S
    assert set(S.VALID_EXAM_RESULT_CODES) == {1, 3, 4}, S.VALID_EXAM_RESULT_CODES
    assert 2 not in S.VALID_EXAM_RESULT_CODES, "2 is NOT a valid code"
    assert S.VALID_EXAM_RESULT_CODES[1] == "Promoted/Passed"
    assert S.VALID_EXAM_RESULT_CODES[3] == "Not Promoted/Not Passed/Repeater"
    assert S.VALID_EXAM_RESULT_CODES[4] == "Promoted/Passed without Examination"
    print("PASS test_exam_result_codes_match_the_portal")


def test_enr_status_codes():
    """Field 4.2.5(a) previous-year schooling status."""
    from udise_vps import subjects as S
    assert S.ENR_STATUS_PY_CODES[4] == "None/Not Studying"
    assert S.ENR_STATUS_NOT_STUDYING == 4
    assert S.EXAM_RESULT_NOT_APPLICABLE == 4
    print("PASS test_enr_status_codes")


def test_not_studying_na_values():
    """Status 4 requires null for the dependent fields, not 0/0/4/0.

    Sending numbers is rejected with errorFields 'Not Applicable'. The portal
    then stores its own sentinels: classPY=99, examResultPy=0, examMarksPy=999,
    attendancePy=0.
    """
    from udise_vps import subjects as S
    assert S.NOT_STUDYING_NA_FIELDS == {
        "classPY": None, "examResultPy": None,
        "examMarksPy": None, "attendancePy": None,
    }, S.NOT_STUDYING_NA_FIELDS
    assert S.NOT_STUDYING_STORED["classPY"] == 99
    assert S.NOT_STUDYING_STORED["examMarksPy"] == 999
    print("PASS test_not_studying_na_values")


def test_na_sentinels_match_null_readback():
    """A stored NA sentinel must not look like a read-back mismatch."""
    # we send None, portal stores 99/0/999/0
    assert ep.comparable_value("classPY", 99) == ep.comparable_value("classPY", None)
    assert ep.comparable_value("examMarksPy", 999) == ep.comparable_value("examMarksPy", None)
    assert ep.comparable_value("examResultPy", 0) == ep.comparable_value("examResultPy", None)
    assert ep.comparable_value("attendancePy", 0) == ep.comparable_value("attendancePy", None)
    # a real value still differs
    assert ep.comparable_value("classPY", 5) != ep.comparable_value("classPY", None)
    print("PASS test_na_sentinels_match_null_readback")


def test_not_studying_needs_no_exam_result():
    """Status 4 disables the exam-result requirement entirely.

    Confirmed from the portal UI: with 4.2.5(a) = '4-None/Not Studying' the
    portal greys out 4.2.7(a) exam result, 4.2.7(b) marks, and 4.2.8
    attendance. So a not-studying record must be writable with no exam result.

    The fake below is STATEFUL: an accepted write becomes visible to the next
    read, which is what makes the read-back assertion meaningful.
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from udise_vps import ep as ep_mod
    from udise_vps import subjects as S

    class FakeSession:
        school_id = "1"
        students = [{"studentId": "1", "studentCodeNat": "PEN1",
                     "classId": 9, "studentName": "T"}]

        def __init__(self):
            self.record = {
                "admnNumber": None, "enrStatusPY": 4, "examResultPy": 5,
                "moiId": 0, "subject1": 0, "subject2": 0,
                "subject3": 0, "subject4": 0, "subject5": 0, "subject6": 0,
                "academicStream": 0, "classPY": 5, "examMarksPy": 0,
                "attendancePy": 0, "certifiedCheckCount": 0, "rollNumber": None,
                "admnStartDate": "01/01/2026",
            }
            self.posts = []

        def get_json(self, route, **kw):
            if "enrolment" in route:
                return {"status": True, "data": dict(self.record)}
            raise RuntimeError(route)

        def student_detail(self, sid):
            return {"minorityId": 7, "studentName": "T", "fatherName": "F",
                    "dob": "2012-01-01", "uuid": ""}

        def _request(self, method, route, **kw):
            body = kw.get("json") or {}
            self.posts.append(body)
            # Apply the write so the next read reflects it.
            self.record.update({k: v for k, v in body.items()
                                if k not in ("schoolId", "studentId")})
            return 200, {"status": True}

        def post_once(self, route, json_body=None, read_timeout=90):
            self.posts.append(json_body or {})
            self.record.update({k: v for k, v in (json_body or {}).items()
                                if k not in ("schoolId", "studentId")})
            return 200, {"status": True}

    sess = FakeSession()
    results = ep_mod.run_ep(
        sess, class_scope_name="IX", limit=1,
        allow_submit=True, max_submissions=1,
        not_studying_override=True,
    )
    assert sess.posts, "a not-studying student must be writable"
    payload = sess.posts[0]
    # Status 4 -> the four dependent fields are sent as null (Not Applicable).
    for field in ("classPY", "examResultPy", "examMarksPy", "attendancePy"):
        assert payload[field] is None, f"{field}={payload[field]!r} should be None"
    assert payload["enrStatusPY"] == S.ENR_STATUS_NOT_STUDYING
    assert results[0].status != "MANUAL_REVIEW", results[0].status
    print("PASS test_not_studying_needs_no_exam_result")


def test_ep_payload_preserves_untouched_subjects():
    """Subjects 3-8 must be carried from the current record, not blanked."""
    current = {
        "admnNumber": "12/2026", "rollNumber": "5", "moiId": 4,
        "academicStream": 0, "certifiedCheckCount": 2,
        "subject1": 11, "subject2": 22, "subject3": 33, "subject4": 44,
        "subject5": 55, "subject6": 66, "subject7": 77, "subject8": 88,
    }
    payload = ep.build_ep_payload("2497128", "1", current, {"subject1": 99})
    assert payload["subject3"] == 33, "subject3 must be preserved"
    assert payload["subject8"] == 88, "subject8 must be preserved"
    assert payload["subject1"] == 99, "submitted change must apply"
    assert payload["subject2"] == 22, "subject2 must be preserved"
    assert payload["certifiedCheckCount"] == 2
    assert "schoolId" in payload and "studentId" in payload
    print("PASS test_ep_payload_preserves_untouched_subjects")


def test_language_plan_selection():
    rules = {
        9: [
            {"fieldName": "subject1", "options": [
                {"subjectId": 11, "subjectDesc": "HINDI"},
                {"subjectId": 12, "subjectDesc": "URDU"},
            ]},
            {"fieldName": "subject2", "options": [
                {"subjectId": 21, "subjectDesc": "SANSKRIT"},
                {"subjectId": 22, "subjectDesc": "HIN (NLH)"},
            ]},
        ]
    }
    # Muslim: minorityId 1 — live catalogue wins when present
    plan, missing = ep.resolve_language_codes(rules, 9, 1)
    assert plan["plan"] == "muslim"
    assert plan["codes"] == {"subject1": 12, "subject2": 22}, plan
    assert plan["source"] == "live"
    assert not missing

    # Other
    plan, missing = ep.resolve_language_codes(rules, 9, 7)
    assert plan["plan"] == "other"
    assert plan["codes"] == {"subject1": 11, "subject2": 21}, plan
    print("PASS test_language_plan_selection")


def test_verified_static_subject_codes():
    """The static map is derived from live portal + a real export.

    AFRIN KHATOON   URDU  / HIN (NLH) -> 638 / 1102
    AMAN KUMAR SAH  HINDI / SANSKRIT  -> 629 / 637
    """
    from udise_vps import subjects as S
    assert S.static_code(1, "HINDI") == 629
    assert S.static_code(1, "URDU") == 638
    assert S.static_code(2, "SANSKRIT") == 637
    assert S.static_code(2, "HIN (NLH)") == 1102
    # tolerant of case and spacing
    assert S.static_code(1, "hindi") == 629
    assert S.static_code(2, "hin (nlh)") == 1102
    assert S.static_code(1, "KLINGON") is None
    print("PASS test_verified_static_subject_codes")


def test_static_fallback_when_catalogue_missing():
    """With no catalogue, the verified map must still resolve both plans."""
    # Muslim
    plan, missing = ep.resolve_language_codes(None, 9, 1)
    assert plan["codes"] == {"subject1": 638, "subject2": 1102}, plan
    assert plan["source"] == "static"
    assert not missing
    # Other
    plan, missing = ep.resolve_language_codes(None, 9, 7)
    assert plan["codes"] == {"subject1": 629, "subject2": 637}, plan
    assert not missing
    print("PASS test_static_fallback_when_catalogue_missing")


def test_static_fallback_when_catalogue_lacks_label():
    """A catalogue missing our label falls back rather than giving up."""
    rules = {9: [{"fieldName": "subject1", "options": [
        {"subjectId": 11, "subjectDesc": "BANGLA"}]}]}
    plan, missing = ep.resolve_language_codes(rules, 9, 7)
    # subject1 falls back to static HINDI, subject2 resolves statically
    assert plan["codes"]["subject1"] == 629, plan
    assert plan["codes"]["subject2"] == 637, plan
    assert not missing
    print("PASS test_static_fallback_when_catalogue_lacks_label")


def test_minority_plan_mapping():
    from udise_vps import subjects as S
    assert S.plan_for_minority(1) == "muslim"
    assert S.plan_for_minority("1") == "muslim"
    assert S.plan_for_minority("1.0") == "muslim"
    assert S.plan_for_minority(7) == "other"
    assert S.plan_for_minority(None) == "other"
    print("PASS test_minority_plan_mapping")


def test_catalogue_none_entries_do_not_crash():
    """REGRESSION: a catalogue with null entries crashed resolution."""
    rules = {9: [None, {"fieldName": "subject1", "options": None},
                 {"fieldName": "subject1", "options": [None,
                  {"subjectId": 11, "subjectDesc": "HINDI"}]}]}
    plan, missing = ep.resolve_language_codes(rules, 9, 7)
    # Must not raise. A catalogue whose first matching rule has null options is
    # not trustworthy, so the verified static map wins.
    assert plan["codes"]["subject1"] == 629, plan
    assert plan["codes"]["subject2"] == 637, plan
    print("PASS test_catalogue_none_entries_do_not_crash")


def test_catalogue_used_when_well_formed():
    """A clean catalogue must still take priority over the static map."""
    rules = {9: [{"fieldName": "subject1",
                  "options": [{"subjectId": 11, "subjectDesc": "HINDI"}]},
                 {"fieldName": "subject2",
                  "options": [{"subjectId": 21, "subjectDesc": "SANSKRIT"}]}]}
    plan, missing = ep.resolve_language_codes(rules, 9, 7)
    assert plan["codes"] == {"subject1": 11, "subject2": 21}, plan
    assert plan["source"] == "live"
    print("PASS test_catalogue_used_when_well_formed")


def test_subject_label_handles_none():
    assert ep.subject_label(None, 9, "subject1", 11) == "11"
    assert ep.subject_label({9: None}, 9, "subject1", 11) == "11"
    assert ep.subject_label({9: [None]}, 9, "subject1", 11) == "11"
    print("PASS test_subject_label_handles_none")


def test_language_missing_label_is_reported():
    """An unknown label with no static fallback must be reported, not guessed."""
    rules = {9: [{"fieldName": "subject1", "options": [
        {"subjectId": 11, "subjectDesc": "HINDI"}]}]}
    # Patch the static map so the label genuinely cannot resolve.
    from udise_vps import subjects as S
    original = S.SUBJECT_CODE_MAP.get(1, {}).pop("URDU", None)
    try:
        plan, missing = ep.resolve_language_codes(rules, 9, 1)
        assert "URDU" in missing, missing
    finally:
        if original is not None:
            S.SUBJECT_CODE_MAP[1]["URDU"] = original
    print("PASS test_language_missing_label_is_reported")


# ------------------------------------------------------------------ facility
def test_facility_blank_only_fill():
    import random
    rng = random.Random(1)
    current = {
        "heightInCm": "150",      # saved -> keep
        "weightInKg": "",         # blank -> fill
        "distanceFrmSchool": "",  # blank -> 2
        "parentEducation": "",    # blank -> 3
        "facilityYn": 1,          # saved -> keep
        "olympdsNlc": "",         # blank -> 2
    }
    updates = facility.build_facility_updates(current, cwsn=False, rng=rng)
    assert "heightInCm" not in updates, "saved height must be kept"
    assert "facilityYn" not in updates, "saved Yes/No must be kept"
    assert updates["distanceFrmSchool"] == "2"
    assert updates["parentEducation"] == "3"
    assert updates["olympdsNlc"] == 2
    assert 42 <= int(updates["weightInKg"]) <= 52, updates["weightInKg"]
    print("PASS test_facility_blank_only_fill")


def test_facility_generated_ranges():
    import random
    rng = random.Random(7)
    for _ in range(50):
        updates = facility.build_facility_updates(
            {"heightInCm": "", "weightInKg": ""}, cwsn=False, rng=rng)
        assert 146 <= int(updates["heightInCm"]) <= 160, updates["heightInCm"]
        assert 42 <= int(updates["weightInKg"]) <= 52, updates["weightInKg"]
    print("PASS test_facility_generated_ranges")


def test_facility_cwsn_field_skipped_for_non_cwsn():
    import random
    rng = random.Random(3)
    updates = facility.build_facility_updates({}, cwsn=False, rng=rng)
    assert "facProvidedCwsnYn" not in updates, "must not fill CWSN field for non-CWSN"
    updates = facility.build_facility_updates({}, cwsn=True, rng=rng)
    assert "facProvidedCwsnYn" in updates, "CWSN student should get the field"
    print("PASS test_facility_cwsn_field_skipped_for_non_cwsn")


def test_facility_generation_is_reproducible_with_seed():
    import random
    a = facility.build_facility_updates({"heightInCm": "", "weightInKg": ""},
                                        cwsn=False, rng=random.Random(42))
    b = facility.build_facility_updates({"heightInCm": "", "weightInKg": ""},
                                        cwsn=False, rng=random.Random(42))
    assert a == b, (a, b)
    print("PASS test_facility_generation_is_reproducible_with_seed")


def test_ep_rejects_unsupported_class():
    class FakeSession:
        students = []
        school_id = "1"
    try:
        ep.run_ep(FakeSession(), class_scope_name="XII")
    except ValueError as exc:
        assert "IX" in str(exc)
    else:
        raise AssertionError("XII must be rejected by EP")
    print("PASS test_ep_rejects_unsupported_class")


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
