"""Enrollment Profile — Classes IX and X.

Ported from the notebook's Enrolment cells (14-17), with the admission-number
engine from v2.8.0.

Scope and rules (confirmed with the operator):
  - Classes IX and X only. XI/XII is deferred — it needs stream mapping that the
    notebook never implemented.
  - A value already saved on the portal stays. Only blank fields are filled.
  - Admission Number: if UDISE already has one, keep it. If UDISE is blank and
    the student matches the eShikshaKosh report, use the report value. If the
    student is not in the report, allocate the next number after the highest
    already used in that class.
  - Muslim students (minorityId=1): Subject 1 = URDU, Subject 2 = HIN (NLH).
    All others: Subject 1 = HINDI, Subject 2 = SANSKRIT.
    Both are resolved against the LIVE subject catalogue by name, never by
    hardcoded code.
  - Subjects 3-8 (Mathematics, Science, Social Science, English, ...) are left
    exactly as saved.
  - Roll number, admission date, previous class, marks and attendance are never
    generated — they differ per student.

Stream safety: the two portals number streams differently (eShikshaKosh 1=Arts,
2=Science; UDISE 1=Science, 2=Arts). Streams are therefore mapped by NAME only.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from .constants import CLASS_LABEL

# ---------------------------------------------------------------- scope + enums
TARGET_CLASSES = {9, 10, 11}
SUPPORTED_SCOPE = {
    "IX": {9},
    "X": {10},
    "XI": {11},
    "IX and X": {9, 10},
    "IX to XI": {9, 10, 11},
    "All IX-XI": {9, 10, 11},
}
# Classes whose EP form is the simple IX/X shape (no stream-specific subjects).
SIMPLE_EP_CLASSES = {9, 10}
# Class XI needs a stream and a stream-specific subject contract.
STREAM_EP_CLASSES = {11}

# Subject codes for Classes XI/XII are NOT live on UDISE yet. The EP form for
# those classes takes a stream, admission number and the previous-year block,
# but no subject slots, and the portal refuses the write outright:
#
#   {"error": {"message": "Subject mapping for the selected Board and Class has
#    not been configured yet. ... (1002)",
#    "type": "no_board_class_subject_mapping"}}
#
# Verified live against a real Class XI student. A probe of all 62 Class XI
# records found ZERO with any subject slot filled, so there is nothing to copy
# and nothing safe to guess. Class XI/XII EP is blocked until the portal
# configures the mapping — do not retry in a loop.
NO_SUBJECT_CLASSES = {11, 12}
# Classes whose EP write the portal currently rejects outright.
EP_BLOCKED_CLASSES = {11, 12}
EP_BLOCKED_REASON = (
    "UDISE has no subject mapping configured for this Board and Class "
    "(error 1002). Class XI/XII EP cannot be written yet."
)

# Streams a Class XI student may be in, in the order to offer them.
STREAM_CHOICES = ("Science", "Arts", "Commerce")

ENUM_LABELS = {
    "academicStream": {0: "Not applicable", 1: "Science", 2: "Arts", 3: "Commerce"},
    "enrStatusPY": {
        1: "Studied at Current/Same School", 2: "Studied at Other School",
        4: "None/Not Studying", 5: "Studying in Unrecognized/Open School",
    },
    "examResultPy": {
        1: "Promoted/Passed", 2: "Not Promoted/Not Passed/Repeater",
        3: "Promoted/Passed without Examination",
    },
}
ENUM_LABELS["classPY"] = {
    0: "Not applicable",
    **{n: f"Class {r}" for n, r in enumerate(
        ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"], 1)},
}

# Name -> UDISE academicStream code. The ONLY safe way to translate streams.
UDISE_STREAM_CODE = {
    "SCIENCE": 1,
    "ARTS": 2,
    "COMMERCE": 3,
    "COMM": 3,
    "NOT APPLICABLE": 0,
    "N/A": 0,
}

LANGUAGE_PLAN = {
    "muslim": {"subject1": "URDU", "subject2": "HIN (NLH)"},
    "other": {"subject1": "HINDI", "subject2": "SANSKRIT"},
}

# Fields compared on read-back.
COMPARE_FIELDS = [
    "admnNumber", "admnStartDate", "rollNumber", "moiId", "academicStream",
    "enrStatusPY", "classPY", "rteQuestion", "rteAmount", "examResultPy",
    "examMarksPy", "attendancePy",
] + [f"subject{i}" for i in range(1, 9)]


# -------------------------------------------------------------------- helpers
def clean_text(value) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() in {"", "nan", "none"} else text


def clean_number(value, default=0):
    text = clean_text(value)
    if not text:
        return default
    lowered = text.lower()
    if lowered in {"true", "yes"}:
        return 1
    if lowered in {"false", "no"}:
        return 0
    return int(float(text.split("-", 1)[0].strip()))


def is_blank(value) -> bool:
    return clean_text(value).lower() in {"", "nan", "none", "null"}


def norm_name(value) -> str:
    return re.sub(r"[^A-Z]", "", str(value or "").upper())


def norm_dob(value) -> str:
    """Normalise a date to DDMMYYYY so the two portals can be compared.

    Handles both observed formats:
      2012-03-02   ISO (UDISE roster and the eShikshaKosh OTR report)
      02-Mar-2012  day-month-name
      02/03/2012   slash separated
    """
    raw = clean_text(value)
    if not raw:
        return ""

    # ISO: YYYY-MM-DD
    iso = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", raw)
    if iso:
        y, m, d = iso.groups()
        return f"{int(d):02d}{int(m):02d}{y}"

    # Day-first with a month name: 02-Mar-2012
    mon = re.match(r"^(\d{1,2})[-/\s]([A-Za-z]{3,})[-/\s](\d{2,4})", raw)
    if mon:
        d, month, y = mon.groups()
        months = {m: i for i, m in enumerate(
            ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
             "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
        code = months.get(month[:3].upper())
        if code:
            if len(y) == 2:
                y = ("20" if int(y) < 50 else "19") + y
            return f"{int(d):02d}{code:02d}{y}"

    # Day-first numeric: DD/MM/YYYY
    dmy = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", raw)
    if dmy:
        d, m, y = dmy.groups()
        if len(y) == 2:
            y = ("20" if int(y) < 50 else "19") + y
        return f"{int(d):02d}{int(m):02d}{y}"

    # Already a compact run of digits.
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 8 and digits[:4] >= "1900":
        return digits[6:8] + digits[4:6] + digits[:4]
    return digits


def last4(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-4:] if len(digits) >= 4 else ""


# Sentinel values the portal stores for "Not Applicable" fields when the
# previous-year status is 4 (None/Not Studying). We transmit null for these,
# so a read-back must treat the stored sentinel as equivalent to blank.
NA_STORED_SENTINELS = {
    "classPY": {99},
    "examResultPy": {0},
    "examMarksPy": {999},
    "attendancePy": {0},
}


def comparable_value(field_name: str, value) -> str:
    """Normalise a value for read-back comparison."""
    raw = clean_text(value)

    # A stored "Not Applicable" sentinel must match the null we transmitted.
    if field_name in NA_STORED_SENTINELS:
        try:
            if int(float(raw)) in NA_STORED_SENTINELS[field_name]:
                return ""
        except (TypeError, ValueError):
            pass

    if field_name.startswith("subject"):
        # The portal reports an unset optional subject as None while we send 0
        # (and vice versa). Treat every blank form as equivalent so optional
        # slots 7/8 do not produce a false mismatch.
        if raw in {"", "0", "0.0", "9", "None", "null", "nan"}:
            return ""
        try:
            return str(int(float(raw.split("-", 1)[0].strip())))
        except (TypeError, ValueError):
            return raw
    if field_name == "rteQuestion":
        return "1" if raw.lower() in {"true", "yes", "1"} else "0"
    if field_name in {"moiId", "academicStream", "enrStatusPY", "classPY",
                      "rteAmount", "examResultPy", "examMarksPy", "attendancePy"}:
        try:
            return str(int(float(raw.split("-", 1)[0].strip())))
        except (TypeError, ValueError):
            return raw
    return raw


def readback_matches(saved: dict, expected: dict) -> tuple[bool, list]:
    fields = [f for f in COMPARE_FIELDS if f in expected]
    mismatches = [
        f for f in fields
        if comparable_value(f, saved.get(f)) != comparable_value(f, expected.get(f))
    ]
    return not mismatches, mismatches


def enum_label(field_name: str, value) -> str:
    if field_name == "rteQuestion":
        return "Yes" if str(value).strip().lower() in {"true", "1", "yes"} else "No"
    raw = clean_text(value)
    if not raw:
        return ""
    try:
        code = int(float(raw))
    except (TypeError, ValueError):
        return raw
    label = ENUM_LABELS.get(field_name, {}).get(code)
    return f"{code}-{label}" if label else raw


# ------------------------------------------------------- subject catalogue
# Route template for the per-class subject dropdown catalogue. Kept configurable
# because the portal has moved this path between versions. Placeholders:
#   {school}  internal school id
#   {class}   class id (9, 10, ...)
#   {a} {b}   portal's trailing selectors
SUBJECT_CATALOGUE_ROUTES = (
    "/p0/api/masters/subject/{school}/{class}/2/0",
    "/p0/api/master/subject/{school}/{class}/2/0",
)


def load_subject_rules(session, class_ids, route_template: str | None = None,
                       required: bool = False) -> dict:
    """Fetch the live subject dropdown catalogue per class.

    The portal has moved this route between versions, so by default a failure
    is non-fatal: we warn and let callers fall back to the verified static map
    in subjects.py. Pass required=True to fail hard instead.
    """
    templates = [route_template] if route_template else list(SUBJECT_CATALOGUE_ROUTES)
    rules = {}
    for class_id in sorted(class_ids):
        name = CLASS_LABEL.get(class_id, str(class_id))
        last_error = None
        body = None
        for template in templates:
            route = template.format(**{"school": session.school_id, "class": class_id,
                                       "a": 2, "b": 0})
            try:
                body = session.get_json(route, read_timeout=45)
                break
            except Exception as exc:
                last_error = exc
                continue
        if body is None:
            if required:
                joined = ", ".join(templates)
                raise RuntimeError(
                    f"Could not load the {name} subject catalogue from any known "
                    f"route ({joined}). Last error: {last_error}."
                )
            print(
                f"⚠️  {name} subject catalogue unavailable "
                f"({type(last_error).__name__}); using the verified static "
                "subject map instead.",
                flush=True,
            )
            continue
        selections = (body.get("data") or {}).get("subjectSelectionList") or []
        if not selections:
            if required:
                raise RuntimeError(
                    f"UDISE returned no {name} subject rules. "
                    "Refusing to continue without the live catalogue."
                )
            print(f"⚠️  {name} catalogue returned no rules; using static map.", flush=True)
            continue
        # Drop any null entries so downstream code can iterate safely.
        selections = [s for s in selections if isinstance(s, dict)]
        rules[class_id] = selections
        print(f"[EP] {name}: {len(selections)} subject fields loaded from the portal",
              flush=True)
    return rules


def _lang_norm(value) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def resolve_language_codes(rules: dict | None, class_id: int, minority_id) -> tuple[dict, list]:
    """Resolve the language plan to subject codes.

    Prefers the live catalogue when it is loaded and contains the label.
    Falls back to the verified static map (see subjects.py) when the catalogue
    is unavailable — the portal has moved that route between versions.

    Returns ({"plan":..., "codes": {...}, "source": ...}, missing_labels)
    """
    from . import subjects as subjects_mod

    plan_name = subjects_mod.plan_for_minority(minority_id)
    plan = LANGUAGE_PLAN[plan_name]
    chosen: dict = {}
    missing: list = []
    used_static = False
    used_live = False

    for field_name, label in plan.items():
        slot = int(field_name.replace("subject", ""))

        # 1. live catalogue, if we have it
        code = None
        if rules:
            options = next(
                (r.get("options") or [] for r in (rules.get(class_id) or [])
                 if r and r.get("fieldName") == field_name),
                [],
            )
            match = next(
                (o for o in options if o
                 and _lang_norm(o.get("subjectDesc")) == _lang_norm(label)),
                None,
            )
            if match is not None:
                code = match.get("subjectId")
                used_live = True

        # 2. verified static map
        if code is None:
            code = subjects_mod.static_code(slot, label)
            if code is not None:
                used_static = True

        if code is None:
            missing.append(label)
        else:
            chosen[field_name] = code

    source = "live" if used_live and not used_static else (
        "static" if used_static and not used_live else "mixed"
    )
    return {"plan": plan_name, "codes": chosen, "source": source}, missing


def subject_label(rules: dict | None, class_id: int, field_name: str, value) -> str:
    raw = clean_text(value)
    if raw in {"", "0", "0.0"}:
        return ""
    for rule in ((rules or {}).get(class_id) or []):
        if not rule or rule.get("fieldName") != field_name:
            continue
        for option in rule.get("options") or []:
            if option and str(option.get("subjectId")) == raw:
                return option.get("subjectDesc", raw)
    return raw


# --------------------------------------------------- eShikshaKosh report read
def read_esk_report(path: str) -> list[dict]:
    """Read the eShikshaKosh OTR report workbook into normalised rows."""
    from openpyxl import load_workbook

    wb = load_workbook(path, data_only=True)
    ws = wb.active
    headers = [clean_text(ws.cell(1, c).value) for c in range(1, ws.max_column + 1)]

    def col(*names):
        for n in names:
            if n in headers:
                return headers.index(n) + 1
        return None

    c_name = col("Student Name")
    c_father = col("Father's Name", "Father Name")
    c_mother = col("Mother's Name", "Mother Name")
    c_class = col("Class")
    c_dob = col("DOB", "Date of Birth")
    c_aadhaar = col("Aadhaar Number", "Masked Aadhaar")
    c_adm = col("Admission No", "Admission Number")
    c_stream = col("Stream")

    rows = []
    for r in range(2, ws.max_row + 1):
        def get(idx):
            return clean_text(ws.cell(r, idx).value) if idx else ""

        name = get(c_name)
        if not name:
            continue
        rows.append({
            "name": name,
            "father": get(c_father),
            "mother": get(c_mother),
            "class": get(c_class),
            "dob": get(c_dob),
            "aadhaar": get(c_aadhaar),
            "admission": get(c_adm),
            "stream": get(c_stream),
        })
    return rows


def report_class_id(value) -> int | None:
    """Map a class label to its numeric id.

    Handles both spellings used by the two portals: 'Class 9'/'9' and
    'IX'/'X'/'XI'/'XII'. Longer roman numerals are tested first so 'XI' does
    not match the 'X' branch.
    """
    text = str(value or "").upper()
    roman = re.search(r"\b(XII|XI|IX|X)\b", text)
    if roman:
        return {"IX": 9, "X": 10, "XI": 11, "XII": 12}[roman.group(1)]
    numeric = re.search(r"\b(9|10|11|12)\b", text)
    if numeric:
        return int(numeric.group(1))
    return None


def resolve_stream_for_xi(
    student: dict,
    report_rows: list[dict],
    *,
    ask=None,
) -> tuple[int | None, str, str]:
    """Resolve a Class XI student's stream.

    Returns (udise_code, stream_name, source).

    Order:
      1. 'saved'   — UDISE already holds a stream; never overwritten.
      2. 'report'  — matched the eShikshaKosh OTR report's Stream column.
      3. 'asked'   — ``ask(name, choices)`` returned a choice. This is how the
                     operator supplies a stream the report does not carry.
      4. (None, "", "unknown") — nothing resolved; the caller must skip.

    Streams are translated by NAME only. The two portals number them
    differently (eShikshaKosh 1=Arts, 2=Science; UDISE 1=Science, 2=Arts), so
    a raw code from either side is never reused.
    """
    saved = clean_number(student.get("academicStream"))
    if saved and saved in UDISE_STREAM_CODE.values() and saved != 0:
        return saved, stream_name_for_code(saved), "saved"

    match, _problem = match_report(student, report_rows)
    if match is not None:
        name = stream_name(match.get("stream"))
        code = UDISE_STREAM_CODE.get(name)
        if code is not None and code != 0:
            return code, name, "report"

    if ask is not None:
        chosen = ask(student.get("name"), list(STREAM_CHOICES))
        name = stream_name(chosen)
        code = UDISE_STREAM_CODE.get(name)
        if code is not None and code != 0:
            return code, name, "asked"

    return None, "", "unknown"


def stream_name_for_code(code) -> str:
    """Reverse of UDISE_STREAM_CODE, for display."""
    for name, value in UDISE_STREAM_CODE.items():
        if value == clean_number(code):
            return name
    return ""


def stream_name(value) -> str:
    """Map a stream label from either portal to a canonical name.

    Handles 'N/A' explicitly: the OTR report stores N/A for IX/X students,
    which must resolve to the UDISE 'Not applicable' code rather than blank.
    """
    raw = clean_text(value)
    if not raw:
        return ""
    if re.fullmatch(r"(?i)n\s*/?\s*a\.?", raw):
        return "NOT APPLICABLE"
    text = re.sub(r"[^A-Z]", " ", raw.upper())
    for token, name in (("SCIENCE", "SCIENCE"), ("SCI", "SCIENCE"),
                        ("ARTS", "ARTS"), ("COMMERCE", "COMMERCE"),
                        ("COMM", "COMMERCE")):
        if re.search(rf"\b{token}\b", text):
            return name
    return ""


# ------------------------------------------------------- admission numbering
def parse_admission(value, year_hint: str = ""):
    """Split an admission number into (number, year).

    Observed real formats: 12/2026, 08/2026, 4/2025, 5/25, 62/25, 038/2025
    and the malformed 142025 (a '14/2025' whose separator was lost).

    A 6-digit value with no separator is split as number + 4-digit year when
    that year looks plausible; otherwise the whole run is treated as the
    number. year_hint (e.g. the report's academic year) resolves ambiguity.
    """
    text = clean_text(value).upper()
    if not text:
        return None

    # Malformed glued form, e.g. '142025' -> ('14', '2025').
    glued = re.fullmatch(r"(\d{1,2})((?:19|20)\d{2})", text)
    if glued:
        return int(glued.group(1)), glued.group(2)

    lead = re.match(r"^(\d+)", text)
    if not lead:
        return None
    number = int(lead.group(1))

    # Prefer a 4-digit year; fall back to a 2-digit year after the separator.
    years4 = re.findall(r"(?:19|20)\d{2}", text)
    if years4:
        return number, years4[-1]
    tail = re.search(r"[-/]+\s*(\d{2})\s*$", text)
    if tail:
        return number, tail.group(1)
    return number, ""


def expand_year(year: str) -> str:
    """Normalise a 2- or 4-digit year to 4 digits."""
    year = clean_text(year)
    if not year:
        return ""
    if len(year) == 4:
        return year
    if len(year) == 2:
        return ("20" if int(year) < 50 else "19") + year
    return year


def format_admission(number: int, year: str, width: int = 0,
                     style: str = "plain") -> str:
    """Format an admission number.

    style='plain'      -> '34'      (what UDISE itself stores; default)
    style='slash_year' -> '34/2026' (the eShikshaKosh presentation form)

    UDISE's own records hold plain numbers ('1', '2', '3'), so 'plain' is the
    default. width>0 zero-pads the number (e.g. 01).
    """
    text = str(number).zfill(width) if width else str(number)
    if style == "slash_year":
        return f"{text}/{year or '2026'}"
    return text


def admission_number_part(value) -> str:
    """Extract just the numeric part of an admission number.

    '12/2026' -> '12'   '08/2026' -> '08'   '1' -> '1'
    """
    text = clean_text(value)
    if not text:
        return ""
    lead = re.match(r"^(\d+)", text)
    return lead.group(1) if lead else text


def match_report(student: dict, report_rows: list[dict], *, allow_class_mismatch: bool = True):
    """Match a UDISE student to eShikshaKosh rows using identity evidence.

    Neither class nor DOB is a hard filter. The two portals disagree about both
    often enough that requiring them loses real matches:

      - Class: a student UDISE holds in XI may sit in the report under X or XII.
      - DOB: the report frequently carries no Aadhaar at all, so a DOB
        difference cannot be resolved by Aadhaar and must not veto the match.

    Identity is therefore established by person. Policy:

      HARD REJECT — Aadhaar last-4 present on BOTH sides and different. That is
      a different person however the names read.

      QUALIFY — Aadhaar last-4 agrees, OR the name matches exactly, OR the
      father's name matches exactly with a partial name match.

      SCORE — Aadhaar agreement outweighs everything; name beats father; DOB
      corroborates; a DOB conflict without Aadhaar agreement is a penalty, not
      a veto.

    Returns (row, "") on a unique best match, (None, "ambiguous") when several
    tie, (None, "unmatched") otherwise.
    """
    dob = norm_dob(student.get("dob"))
    name = norm_name(student.get("name"))
    father = norm_name(student.get("father"))
    l4 = last4(student.get("aadhaar"))
    want_class = student.get("class_id")

    scored = []

    for row in report_rows:
        row_l4 = last4(row.get("aadhaar"))

        # Aadhaar last-4 is decisive: both present and different -> different
        # person, regardless of names.
        if l4 and row_l4 and l4 != row_l4:
            continue

        row_name = norm_name(row.get("name"))
        row_father = norm_name(row.get("father"))
        aadhaar_ok = bool(l4) and bool(row_l4) and l4 == row_l4
        name_exact = bool(name) and name == row_name
        father_exact = bool(father) and father == row_father
        name_partial = _shares_token(name, row_name)
        father_partial = _shares_token(father, row_father)

        qualifies = (
            aadhaar_ok
            or name_exact
            or (father_exact and name_partial)
            or (name_partial and father_partial)
        )
        if not qualifies:
            continue

        row_dob = norm_dob(row.get("dob"))
        dob_ok = bool(dob) and row_dob == dob
        dob_conflict = bool(dob) and bool(row_dob) and not dob_ok

        score = 0
        if aadhaar_ok:
            score += 5
        if name_exact:
            score += 3
        elif name_partial:
            score += 1
        if father_exact:
            score += 2
        elif father_partial:
            score += 1
        if dob_ok:
            score += 1
        elif dob_conflict and not aadhaar_ok:
            score -= 1

        scored.append((score, row.get("class_id") == want_class, row))

    if not scored:
        return None, "unmatched"

    best = max(s for s, _, _ in scored)
    top = [(sc, same, row) for sc, same, row in scored if sc == best]

    # Prefer a same-class candidate, but only to break a tie.
    same_class = [row for _sc, same, row in top if same]
    if len(same_class) == 1:
        return same_class[0], ""
    if len(top) == 1:
        return top[0][2], ""
    return None, "ambiguous"


def _shares_token(a: str, b: str) -> bool:
    """True when two names share a meaningful token.

    Handles transliteration drift such as 'JAMALUDDIN ANSARI' vs
    'MD ZAMAL ANSARI' (shared 'ANSARI') and 'MD SALIM' vs 'MOHAMMAD SALIM'.

    Accepts either raw ('MD ZAMAL ANSARI') or normalised ('MDZAMALANSARI')
    input. Word-splitting is only meaningful when the text still has spaces;
    for an unspaced run a longest-common-substring probe is used instead.
    """
    if not a or not b:
        return False

    text_a, text_b = str(a).upper(), str(b).upper()
    spaced = (" " in text_a.strip()) and (" " in text_b.strip())

    if spaced:
        ta = {t for t in re.sub(r"[^A-Z ]", " ", text_a).split() if len(t) >= 4}
        tb = {t for t in re.sub(r"[^A-Z ]", " ", text_b).split() if len(t) >= 4}
        return bool(ta & tb)

    # Unspaced runs (the norm_name form): probe for a shared run of at least
    # 4 characters so initials like 'MD' cannot manufacture a match.
    norm_a = re.sub(r"[^A-Z]", "", text_a)
    norm_b = re.sub(r"[^A-Z]", "", text_b)
    if not norm_a or not norm_b:
        return False
    for size in range(min(len(norm_a), len(norm_b)), 3, -1):
        for i in range(len(norm_a) - size + 1):
            if norm_a[i:i + size] in norm_b:
                return True
    return False


def assign_admission_numbers(
    students: list[dict],
    report_rows: list[dict],
    *,
    fallback_width: int = 4,
    style: str = "plain",
) -> list[dict]:
    """Decide the admission number for each student, in roster order.

    Returns one dict per student: {admission, source}.

    Priority:
      1. kept_saved      — UDISE already has a number; never overwritten.
      2. eshikshakosh    — matched a row in the eShikshaKosh report.
      3. roll_number     — no report match, but the roster has a roll number.
      4. next_number     — generated as 0001, 0002, … continuing after the
                           highest number already used in that class.
      5. manual_review   — an ambiguous report match; never auto-filled.

    fallback_width zero-pads generated numbers (default 4 -> 0001).
    style only affects generated values; report/roll values are used as-is.
    """
    # Every report row that carries an admission number is a match candidate,
    # including classes outside our scope: the portals disagree about a
    # student's class, so a Class XI student may sit in the report under X or
    # XII. Class is used only to seed the per-class numbering sequence.
    usable = []
    for row in report_rows or []:
        if is_blank(row.get("admission")):
            continue
        class_id = row.get("class_id") or report_class_id(row.get("class"))
        usable.append({**row, "class_id": class_id})

    results: list[dict] = []
    pending: list[int] = []
    temporary_review: set[int] = set()
    used = {clean_text(r.get("admission")).upper() for r in usable}

    # Seed the per-class sequences from SAVED UDISE numbers as well as report
    # numbers, so a generated fallback continues after the highest already in
    # use rather than restarting at 1.
    grouped: dict = defaultdict(list)
    years: dict = defaultdict(list)

    def seed(class_id, admission):
        parsed = parse_admission(admission)
        if not parsed:
            return
        number, year = parsed
        grouped[class_id].append(number)
        if year:
            years[class_id].append(year)

    for row in usable:
        seed(row.get("class_id"), row.get("admission"))

    for index, student in enumerate(students or []):
        class_id = student.get("class_id")
        current = clean_text(student.get("admission"))

        if class_id not in TARGET_CLASSES:
            results.append({"admission": current, "source": "not_applicable"})
            continue
        if current:
            used.add(current.upper())
            seed(class_id, current)
            results.append({"admission": current, "source": "kept_saved"})
            continue

        match, problem = match_report(student, usable)
        if match is not None:
            # UDISE stores the plain number, so strip any '/YYYY' suffix.
            admission = admission_number_part(match.get("admission"))
            used.add(admission.upper())
            seed(class_id, admission)
            results.append({"admission": admission, "source": "eshikshakosh"})
            continue

        if problem == "ambiguous":
            results.append({"admission": "", "source": "temporary_review"})
            pending.append(index)
            temporary_review.add(index)
            continue

        # No report match: fall back to the roster's roll number when present.
        roll = clean_text(student.get("roll"))
        if roll:
            used.add(roll.upper())
            seed(class_id, roll)
            results.append({"admission": roll, "source": "roll_number"})
            continue

        results.append({"admission": "", "source": "pending"})
        pending.append(index)

    # Allocate fresh numbers after the highest already used in that class.
    for index in pending:
        class_id = students[index]["class_id"]
        numbers = grouped.get(class_id, [])
        year = (
            Counter(expand_year(y) for y in years.get(class_id, []) if y).most_common(1)[0][0]
            if years.get(class_id) else "2026"
        )
        number = (max(numbers) if numbers else 0) + 1
        while True:
            admission = format_admission(number, year, fallback_width, style)
            if admission.upper() not in used:
                break
            number += 1
        used.add(admission.upper())
        grouped[class_id].append(number)
        years[class_id].append(year)
        results[index] = {"admission": admission, "source": "temporary_review" if index in temporary_review else "next_number"}

    return results


# ------------------------------------------------------------------- payload
def build_ep_payload(school_id: str, student_id: str, current: dict, updates: dict,
                     moi_id: int | None = None) -> dict:
    """Compact payload matching the portal's own Enrolment Profile UI.

    Read-only and group fields from the GET response are deliberately excluded.

    moi_id: value to use when the current Medium of Instruction is blank. The
    portal rejects moiId=0 with ER1096, so a blank must be filled with the
    school's actual medium (see subjects.DEFAULT_MOI_ID).
    """
    from . import subjects as subjects_mod

    saved_moi = current.get("moiId")
    try:
        saved_moi_num = int(float(clean_text(saved_moi) or 0))
    except (TypeError, ValueError):
        saved_moi_num = 0

    resolved_moi = saved_moi_num
    if saved_moi_num in subjects_mod.MOI_BLANK_CODES:
        resolved_moi = moi_id if moi_id is not None else subjects_mod.DEFAULT_MOI_ID

    payload = {
        "schoolId": str(school_id),
        "studentId": student_id,
        "admnNumber": clean_text(current.get("admnNumber")),
        "admnStartDate": clean_text(current.get("admnStartDate")),
        "rollNumber": clean_text(current.get("rollNumber")) or None,
        "moiId": resolved_moi,
        "academicStream": clean_number(current.get("academicStream")),
        "enrStatusPY": clean_number(current.get("enrStatusPY")),
        "classPY": clean_number(current.get("classPY")),
        "examResultPy": clean_number(current.get("examResultPy")),
        "examMarksPy": clean_number(current.get("examMarksPy")),
        "attendancePy": clean_number(current.get("attendancePy")),
        "certifiedCheckCount": clean_number(current.get("certifiedCheckCount")),
    }
    for n in range(1, 9):
        payload[f"subject{n}"] = clean_number(current.get(f"subject{n}"))

    payload.update(updates)
    return payload


# --------------------------------------------------------------------- runner
@dataclass
class EpResult:
    pen: str
    student_id: str
    name: str
    class_label: str
    status: str
    detail: str = ""
    changes: dict = field(default_factory=dict)
    admission_source: str = ""
    language_plan: str = ""
    stream: str = ""
    stream_source: str = ""
    current: dict = field(default_factory=dict)

    @property
    def confirmed(self) -> bool:
        return self.status in {
            "SUCCESS_CONFIRMED_BY_RESPONSE_AND_READBACK",
            "SUCCESS_CONFIRMED_BY_READBACK",
        }


def run_ep(
    session,
    *,
    class_scope_name: str = "IX",
    report_rows: list[dict] | None = None,
    limit: int = 0,
    allow_submit: bool = False,
    max_submissions: int = 1,
    fallback_width: int = 0,
    fix_languages: bool = False,
    subject_route: str | None = None,
    admission_style: str = "plain",
    moi_id: int | None = None,
    exam_result_override: int | None = None,
    not_studying_override: bool = False,
    auto_not_studying: bool = True,
    ask_stream=None,
) -> list[EpResult]:
    """Preview (and optionally submit) Enrollment Profile updates.

    allow_submit=False changes nothing on the portal.
    """
    if class_scope_name not in SUPPORTED_SCOPE:
        raise ValueError(
            f"Enrollment supports {', '.join(SUPPORTED_SCOPE)} only."
        )
    classes = SUPPORTED_SCOPE[class_scope_name]

    blocked = classes & EP_BLOCKED_CLASSES
    if blocked and not allow_submit:
        names = ", ".join(sorted(CLASS_LABEL.get(c, str(c)) for c in blocked))
        print(f"⚠️  Class {names}: EP is blocked on the portal "
              f"({EP_BLOCKED_REASON})", flush=True)

    rules = load_subject_rules(session, classes, route_template=subject_route)

    selected = [
        s for s in session.students
        if int(s.get("classId") or -1) in classes
    ]
    if not selected:
        raise ValueError(f"No {class_scope_name} students found in the roster.")
    total_available = len(selected)
    if limit and limit > 0:
        selected = selected[:limit]

    print(
        f"🎓 Enrollment scope: {class_scope_name} | "
        f"{len(selected)} student(s)"
        + (f" of {total_available}" if limit else ""),
        flush=True,
    )
    if not allow_submit:
        print("🔒 Preview only — no POST will be sent.", flush=True)

    # Report rows, annotated with their class. Rows from any class are kept:
    # the portals disagree about a student's class, so a Class IX student may
    # appear in the report under X (or vice versa) and must still match.
    annotated = []
    for row in (report_rows or []):
        cid = row.get("class_id") or report_class_id(row.get("class"))
        annotated.append({**row, "class_id": cid})
    if annotated:
        print(f"📄 eShikshaKosh report: {len(annotated)} row(s)", flush=True)

    # Decide admission numbers across the whole selected set first.
    admission_inputs = []
    for student in selected:
        sid = str(student.get("studentId") or "").strip()
        try:
            detail = session.student_detail(sid)
        except Exception:
            detail = {}
        # Read the saved admission number so an already-numbered student keeps
        # it (source 'kept_saved') and seeds the class sequence.
        try:
            enrolment = session.get_json(
                f"/p0/api/v2/students/enrolment/{sid}", read_timeout=60).get("data")
        except Exception:
            enrolment = {}
        if not isinstance(enrolment, dict):
            enrolment = {}
        admission_inputs.append({
            "class_id": int(student.get("classId") or -1),
            "name": detail.get("studentName") or student.get("studentName"),
            "father": detail.get("fatherName"),
            "dob": detail.get("dob"),
            "aadhaar": detail.get("uuid"),
            "admission": clean_text(enrolment.get("admnNumber")),
            "roll": student.get("rollNo") or student.get("rollNumber"),
        })

    decisions = assign_admission_numbers(
        admission_inputs, annotated, fallback_width=fallback_width,
        style=admission_style,
    )
    source_counts = {}
    for decision in decisions:
        source = decision.get("source", "pending")
        source_counts[source] = source_counts.get(source, 0) + 1
    print(
        "📊 eShikshaKosh matching: "
        f"report rows={len(annotated)} | matched={source_counts.get('eshikshakosh', 0)} | "
        f"already filled={source_counts.get('kept_saved', 0)} | "
        f"roll-number fallback={source_counts.get('roll_number', 0)} | "
        f"not found/pending={source_counts.get('pending', 0)} | "
        f"temporary 0001+ fallback={source_counts.get('temporary_review', 0) + source_counts.get('next_number', 0)} | "
        f"manual review={source_counts.get('manual_review', 0)}",
        flush=True,
    )
    if source_counts.get("temporary_review", 0) or source_counts.get("next_number", 0):
        print("ℹ️ Unmatched or ambiguous students receive sequential temporary numbers in the preview. Review them in Excel before approving the portal save.", flush=True)

    results: list[EpResult] = []
    submissions = 0

    for position, student in enumerate(selected, 1):
        sid = str(student.get("studentId") or student.get("id") or "").strip()
        pen = str(student.get("studentCodeNat") or "").strip()
        class_id = int(student.get("classId") or -1)
        class_label = CLASS_LABEL.get(class_id, "")
        name = str(student.get("studentName") or "").strip()

        result = EpResult(pen=pen, student_id=sid, name=name, class_label=class_label,
                          status="PENDING")

        # ------------------------------------------------- fresh EP read
        try:
            current = session.get_json(f"/p0/api/v2/students/enrolment/{sid}",
                                       read_timeout=60).get("data")
            if not isinstance(current, dict):
                raise RuntimeError("no enrolment data")
        except Exception as exc:
            result.status = "READ_ERROR"
            result.detail = f"{type(exc).__name__}: {exc}"
            results.append(result)
            print(f"⚠️ {pen}: EP read failed — {result.detail}", flush=True)
            continue

        result.current = {field: current.get(field) for field in COMPARE_FIELDS}
        updates: dict = {}

        # --------------------------------------------- admission number
        saved_admission = clean_text(current.get("admnNumber"))
        decision = decisions[position - 1] if position - 1 < len(decisions) else {}
        result.admission_source = decision.get("source", "")
        if is_blank(saved_admission) and decision.get("admission"):
            updates["admnNumber"] = decision["admission"]

        # ------------------------------------------- languages (1 and 2)
        try:
            general = session.student_detail(sid)
            minority_id = general.get("minorityId")
        except Exception:
            minority_id = None

        # ---------------------------------------- languages and subjects
        # Classes XI/XII have NO live subject codes on UDISE yet — the EP form
        # for those classes takes a stream, admission number and the
        # previous-year block, but no subject slots. Writing a code there is
        # rejected, and the IX/X catalogue does not apply. So for those classes
        # every subject slot is left exactly as saved.
        from . import subjects as subjects_mod
        if class_id in NO_SUBJECT_CLASSES:
            result.detail = "subjects not applicable for this class"
            print(f"• {pen}: class {class_label} — subjects left as saved "
                  f"(no live catalogue)", flush=True)
        else:
            plan, missing = resolve_language_codes(rules, class_id, minority_id)
            result.language_plan = plan["plan"]

            if missing:
                result.detail = f"catalogue has no {', '.join(missing)}; languages left as saved"
                print(f"⚠️ {pen}: {result.detail}", flush=True)
            else:
                for field_name, code in plan["codes"].items():
                    saved = current.get(field_name)
                    if fix_languages or is_blank(saved) or str(saved) in {"0", "0.0"}:
                        updates[field_name] = code

            # ------------------------------ mandatory fixed subjects 3-6
            # The portal rejects a write that leaves these at 0:
            # "Some mandatory fields value are incorrect or missing".
            for slot in subjects_mod.MANDATORY_SUBJECT_SLOTS:
                field_name = f"subject{slot}"
                saved = current.get(field_name)
                try:
                    saved_num = int(float(clean_text(saved) or 0))
                except (TypeError, ValueError):
                    saved_num = 0
                if saved_num in subjects_mod.SUBJECT_BLANK_CODES:
                    updates[field_name] = subjects_mod.SUBJECT_FIXED_CODES[slot]

        # ------------------------------------------ previous exam result
        # Field 4.2.5(a) status drives this.
        #
        # When the status is "None/Not Studying" (4) the portal disables the
        # dependent requirements — exam result (4.2.7a), marks (4.2.7b),
        # attendance (4.2.8) — so nothing needs to be supplied for them.
        #
        # A student recorded as having studied (status 1/2) DOES need a result,
        # and an out-of-range code on such a record is reported rather than
        # guessed, unless the operator explicitly asks to set not-studying.
        from . import subjects as subjects_mod
        try:
            enr_status = int(float(clean_text(current.get("enrStatusPY")) or 0))
        except (TypeError, ValueError):
            enr_status = 0
        try:
            exam_result = int(float(clean_text(current.get("examResultPy")) or 0))
        except (TypeError, ValueError):
            exam_result = 0

        # Should this student be treated as "None/Not Studying"?
        # Operator rule: for any student whose exam result is invalid (i.e. the
        # record cannot satisfy the requirement), use status 4 — the portal then
        # disables the exam-result, marks and attendance requirements.
        invalid_exam_result = bool(
            exam_result and exam_result not in subjects_mod.VALID_EXAM_RESULT_CODES
        )
        make_not_studying = (
            not_studying_override
            and enr_status != subjects_mod.ENR_STATUS_NOT_STUDYING
        ) or (
            auto_not_studying
            and invalid_exam_result
            and enr_status != subjects_mod.ENR_STATUS_NOT_STUDYING
        )
        if make_not_studying:
            updates["enrStatusPY"] = subjects_mod.ENR_STATUS_NOT_STUDYING
            enr_status = subjects_mod.ENR_STATUS_NOT_STUDYING
            if invalid_exam_result:
                result.detail = (
                    f"examResultPy={exam_result} invalid; set status to "
                    "None/Not Studying"
                )

        if enr_status == subjects_mod.ENR_STATUS_NOT_STUDYING:
            # Not studying -> the portal disables the dependent requirements
            # and requires these four fields to be Not Applicable. Carrying the
            # old values through is rejected. Transmit null; the portal stores
            # its own sentinels (99 / 0 / 999 / 0).
            updates.update(subjects_mod.NOT_STUDYING_NA_FIELDS)
        elif invalid_exam_result:
            if exam_result_override is None:
                result.status = "MANUAL_REVIEW"
                result.detail = (
                    f"examResultPy={exam_result} is not a valid code "
                    f"({', '.join(str(c) for c in subjects_mod.VALID_EXAM_RESULT_CODES)}). "
                    "The portal rejects this write. Supply --exam-result, "
                    "--not-studying, or allow the automatic rule."
                )
                results.append(result)
                print(f"⚠️ {pen}: {result.detail}", flush=True)
                continue
            updates["examResultPy"] = exam_result_override
        elif exam_result_override is not None and exam_result != exam_result_override:
            updates["examResultPy"] = exam_result_override

        # ------------------------------------------------- academic stream
        # Only Class XI carries a stream. Resolve by NAME from the eShikshaKosh
        # report; if the report has no row for this student, the operator is
        # asked. A saved stream is never overwritten.
        if class_id in STREAM_EP_CLASSES:
            stream_code, stream_label, stream_src = resolve_stream_for_xi(
                {**admission_inputs[position - 1], "academicStream":
                 current.get("academicStream")},
                annotated,
                ask=ask_stream,
            )
            result.stream_source = stream_src
            if stream_code is None:
                result.status = "STREAM_UNKNOWN"
                result.detail = (
                    "Class XI stream could not be resolved — no eShikshaKosh "
                    "row matched and none was supplied. Pass --stream or "
                    "answer the prompt."
                )
                results.append(result)
                print(f"⚠️ {pen}: {result.detail}", flush=True)
                continue
            result.stream = stream_label
            if clean_number(current.get("academicStream")) != stream_code:
                updates["academicStream"] = stream_code

        if not updates:
            result.status = "SKIPPED_ALREADY_UP_TO_DATE"
            result.detail = result.detail or "Nothing blank to fill."
            results.append(result)
            print(f"• {pen}: nothing to fill.", flush=True)
            continue

        result.changes = updates

        # ------------------------------------------------ preview only
        if not allow_submit:
            result.status = "PREVIEW"
            result.detail = f"{len(updates)} field(s) would be set."
            results.append(result)
            print(
                f"👁️ {position}/{len(selected)} {pen}: preview — "
                + ", ".join(updates),
                flush=True,
            )
            continue

        if submissions >= max_submissions:
            result.status = "LIMIT_REACHED"
            result.detail = f"max submissions ({max_submissions}) reached."
            results.append(result)
            print(f"🛑 {pen}: submission cap reached.", flush=True)
            continue

        # ---------------------------------------------------- one write
        payload = build_ep_payload(session.school_id, sid, current, updates,
                                   moi_id=moi_id)
        endpoint = f"/p0/api/v2/students/enrolment/{sid}"
        post_error = None
        response_success = False
        try:
            status_code, body = session._request(
                "POST", endpoint, attempts=1, read_timeout=300,
                connect_timeout=15, label="EP-POST", json=payload,
            )
            response_success = status_code == 200 and body.get("status") is True
            if not response_success:
                err = body.get("error")
                msg = err.get("message") if isinstance(err, dict) else err
                result.status = "FAILED"
                result.detail = f"HTTP {status_code}; {msg or body.get('message') or 'rejected'}"
                results.append(result)
                print(f"❌ {pen}: {result.detail}", flush=True)
                break
        except Exception as exc:
            post_error = exc
            print(
                f"⚠️ {pen}: POST transport error ({type(exc).__name__}). "
                "Not retrying; reading back…",
                flush=True,
            )

        submissions += 1

        # --------------------------------------------- read-back (3 tries)
        matched, mismatches, verified = False, [], False
        for attempt, delay in enumerate((2, 5, 10), 1):
            time.sleep(delay)
            try:
                saved = session.get_json(
                    f"/p0/api/v2/students/enrolment/{sid}", read_timeout=60
                ).get("data")
                if not isinstance(saved, dict):
                    continue
                verified = True
                matched, mismatches = readback_matches(saved, payload)
                if matched:
                    break
                print(f"   still different: {', '.join(mismatches)}", flush=True)
            except Exception:
                continue

        if matched:
            result.status = (
                "SUCCESS_CONFIRMED_BY_RESPONSE_AND_READBACK" if response_success
                else "SUCCESS_CONFIRMED_BY_READBACK"
            )
            result.detail = "Saved values confirmed by fresh read-back."
            if post_error:
                result.detail += " (POST reported a transport error.)"
            results.append(result)
            print(f"✅ {pen}: saved and confirmed.", flush=True)
        elif verified:
            result.status = "RESPONSE_SUCCESS_NOT_PERSISTED" if response_success else "FAILED"
            result.detail = "Read-back differs: " + ", ".join(mismatches)
            results.append(result)
            print(f"⚠️ {pen}: {result.detail}", flush=True)
            break
        else:
            result.status = "UNCONFIRMED"
            result.detail = "No usable read-back; check the portal before any retry."
            results.append(result)
            print(f"⚠️ {pen}: {result.detail}", flush=True)
            break

    confirmed = sum(1 for r in results if r.confirmed)
    preview = sum(1 for r in results if r.status == "PREVIEW")
    skipped = sum(1 for r in results if r.status.startswith("SKIPPED"))
    other = len(results) - confirmed - preview - skipped

    print("\n" + "━" * 30)
    print(f"✅ Saved + confirmed : {confirmed}")
    if preview:
        print(f"👁️  Preview only      : {preview}")
    if skipped:
        print(f"•  Nothing to fill   : {skipped}")
    if other:
        print(f"⚠️  Other             : {other}")
    print("━" * 30)

    return results
