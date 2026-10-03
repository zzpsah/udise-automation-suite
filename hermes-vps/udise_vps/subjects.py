"""Subject code catalogue for Enrollment Profile (Classes IX and X).

Two sources, in priority order:

  1. LIVE catalogue, when the portal route is reachable. Authoritative.
  2. VERIFIED static map below, used when the route is unavailable.

The static map is not a guess. It was derived by joining the subject NAMES in a
real UDISE enrolment export against the subject CODES returned by the live
portal for the same students, matched one student at a time:

    AFRIN KHATOON    export: URDU  / HIN (NLH)   live: 638 / 1102
    AMAN KUMAR SAH   export: HINDI / SANSKRIT    live: 629 / 637

Both language plans resolved with no conflicts across 38 Class X students.

Note on labels: the portal displays code 1102 as "NON-HINDI" in some screens
while the subject catalogue calls it "HIN (NLH)". They are the same code. The
name used here is the catalogue name, which is what the portal accepts.
"""

from __future__ import annotations

# ------------------------------------------------------------- verified codes
# class-independent: the language catalogue is shared across IX/X.
SUBJECT_CODE_MAP: dict[int, dict[str, int]] = {
    1: {
        "HINDI": 629,
        "URDU": 638,
    },
    2: {
        "SANSKRIT": 637,
        "HIN (NLH)": 1102,
    },
}

# Codes observed for the fixed subjects 3-6, derived from the live portal:
# the students whose EP record is already complete all carry exactly these.
# They are MANDATORY: the portal rejects a write that leaves them at 0 with
# "Some mandatory fields value are incorrect or missing".
SUBJECT_FIXED_CODES: dict[int, int] = {
    3: 401,   # MATHEMATICS
    4: 402,   # SCIENCE
    5: 404,   # SOCIAL SCIENCE
    6: 612,   # ENGLISH
}

# Subject slots that are mandatory on the IX/X EP form.
MANDATORY_SUBJECT_SLOTS = (3, 4, 5, 6)
# Values meaning "not set" for a subject slot.
SUBJECT_BLANK_CODES = {0, 9}

# ------------------------------------------------- previous exam result
# AUTHORITATIVE enum, read from the portal's own EP response field
# `previousClassExamResult`:
#     {"1": "Promoted/Passed",
#      "3": "Not Promoted/Not Passed/Repeater",
#      "4": "Promoted/Passed without Examination"}
#
# NOTE: the notebook's ENUM_LABELS is WRONG here — it lists 2 and 3 for these
# meanings. The portal rejects 2 and accepts 4.
VALID_EXAM_RESULT_CODES = {
    1: "Promoted/Passed",
    3: "Not Promoted/Not Passed/Repeater",
    4: "Promoted/Passed without Examination",
}

# Code used when the student was not studying in the previous year, so no exam
# result applies. The portal accepts 4 and the dependent exam fields are then
# not required.
EXAM_RESULT_NOT_APPLICABLE = 4

# ------------------------------------------- previous-year schooling status
# Field 4.2.5(a) "Status of student in Previous Academic Year of Schooling".
# From the notebook's ENUM_LABELS and the EP export dropdown:
#     1 = Studied at Current/Same School
#     2 = Studied at Other School
#     4 = None/Not Studying
#     5 = Studying in Unrecognized/Open School
ENR_STATUS_PY_CODES = {
    1: "Studied at Current/Same School",
    2: "Studied at Other School",
    4: "None/Not Studying",
    5: "Studying in Unrecognized/Open School",
}
ENR_STATUS_NOT_STUDYING = 4

# ---------------------------------------------------- "Not Applicable" values
# When 4.2.5(a) is "None/Not Studying" the portal disables the dependent
# requirements and demands they be marked Not Applicable. Writing carried-over
# values is rejected with:
#   errorFields: {classPY: 'Not Applicable', attendancePy: 'Not Applicable',
#                 examMarksPy: 'Not Applicable', examResultPy: 'Not Applicable'}
#
# Send null for those four fields. The portal then stores its own canonical
# Not Applicable codes, observed from a fresh read after an accepted write:
#   classPY      -> 99      (Not Applicable)
#   examResultPy -> 0
#   examMarksPy  -> 999.0   (Not Applicable)
#   attendancePy -> 0
#
# Sending 0/0/4/0 instead is REJECTED. The values below are what to transmit.
NOT_STUDYING_NA_FIELDS = {
    "classPY": None,
    "examResultPy": None,
    "examMarksPy": None,
    "attendancePy": None,
}

# What the portal stores after such a write (for read-back comparison).
NOT_STUDYING_STORED = {
    "classPY": 99,
    "examResultPy": 0,
    "examMarksPy": 999,
    "attendancePy": 0,
}

# ------------------------------------------------- medium of instruction
# The portal rejects a write carrying moiId=0 with ER1096
# ("Selected Medium of Instruction not available for your school").
#
# Derived from the live portal, not assumed: the students in this school whose
# EP record is already complete all carry moiId=4, and the school's own export
# labels it '04 - Hindi'. So a blank moiId must be filled with the value the
# school already uses.
#
# Override per school with --moi-id when a school's medium differs.
DEFAULT_MOI_ID = 4          # 04 - Hindi
MOI_BLANK_CODES = {0, 9}    # values meaning "not set"

# Subject 7 and 8 are optional and were empty for every observed student.
SUBJECT_OPTIONAL_SLOTS = (7, 8)

# --------------------------------------------------------------- language plan
LANGUAGE_PLAN = {
    "muslim": {"subject1": "URDU", "subject2": "HIN (NLH)"},
    "other": {"subject1": "HINDI", "subject2": "SANSKRIT"},
}

# minorityId 1 = Muslim.
MUSLIM_MINORITY_IDS = {"1", "1.0"}


def normalise_label(value) -> str:
    """Loose comparison key for a subject name."""
    import re
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def static_code(slot: int, label: str) -> int | None:
    """Look up a subject code in the verified static map."""
    wanted = normalise_label(label)
    for name, code in SUBJECT_CODE_MAP.get(slot, {}).items():
        if normalise_label(name) == wanted:
            return code
    return None


def plan_for_minority(minority_id) -> str:
    """Return 'muslim' or 'other'."""
    return "muslim" if str(minority_id).strip() in MUSLIM_MINORITY_IDS else "other"
