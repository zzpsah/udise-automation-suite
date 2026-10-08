"""Facility Profile — Classes IX to XII.

Ported from the notebook's Facility cells (19-22).

Rules confirmed with the operator:
  - A saved measurement stays. Only blank fields are filled.
  - Classes IX-X boys: blank height -> 140..155 cm; blank weight -> 38..52 kg
  - Classes IX-X girls: corresponding lower range -> 135..150 cm; 34..48 kg
  - Classes XI-XII retain the existing ranges: boys 150..170 cm / 42..60 kg;
    girls 146..166 cm / 38..56 kg
  - Blank Yes/No  -> No
  - Blank distance -> "Between 1-3 Kms" (code 2)
  - Blank parent education -> "Secondary or Equivalent" (code 3)

The notebook used random values inside those ranges. Values are generated once
per student and then persisted, so a read-back always compares against the same
numbers rather than fresh randomness.

GET and POST routes intentionally differ by the `AY` segment.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from .constants import (
    CLASS_LABEL,
    FACILITY_BENEFITS,
    FACILITY_CWSN,
    FACILITY_DISTANCE,
    FACILITY_EDUCATION,
    FACILITY_YN,
    class_scope,
)

# Blank-field defaults.
DEFAULT_PARENT_EDUCATION_CODE = 3  # Secondary or Equivalent

# Field 4.3.6 "Approximate Distance of student's residence to school".
# A blank distance is filled with one of these two, chosen at random per
# student so the roster does not report an identical distance for everyone.
DISTANCE_CHOICES = (2, 3)         # 2 = Between 1-3 Kms, 3 = Between 3-5 Kms

GET_ROUTE = "/p0/api/v2/students/facility/{sid}"
POST_ROUTE = "/p0/api/v2/AY/students/facility/{sid}"


def text(value) -> str:
    return "" if value is None or str(value).strip().lower() in {"nan", "none", "<na>"} else str(value).strip()


def is_blank(value) -> bool:
    """True when a facility field holds no real value.

    The portal reports an unset measurement as numeric 0, not as null, so a
    bare `is_blank` that only tests for an empty string silently skips every
    blank height and weight. Zero is 'not set' for a measurement, and the
    dropdown sentinels 0 and 9 are 'not set' for a code field.
    """
    raw = text(value)
    if raw == "":
        return True
    try:
        return float(raw) == 0.0
    except (TypeError, ValueError):
        return False


def is_blank_code(value) -> bool:
    """True when a coded dropdown is unset (blank, 0 or the 9 sentinel)."""
    raw = text(value)
    if raw == "":
        return True
    try:
        return int(float(raw)) in {0, 9}
    except (TypeError, ValueError):
        return False


def yes_no_code(value) -> int | None:
    """1 = Yes, 2 = No. None when blank or the 9 'not applicable' sentinel.

    The portal writes 9 into nccYn/nssYn/scoutsYn/olympdsNlc for a record that
    has never been answered, so 9 must read as unanswered rather than as a
    saved value.
    """
    lowered = text(value).lower()
    if lowered in {"yes", "1", "1.0", "true"}:
        return 1
    if lowered in {"no", "2", "2.0", "false"}:
        return 2
    return None


@dataclass
class FacilityResult:
    pen: str
    student_id: str
    name: str
    class_label: str
    status: str
    detail: str = ""
    changes: list = field(default_factory=list)
    proposed: dict = field(default_factory=dict)

    @property
    def confirmed(self) -> bool:
        return self.status == "SUCCESS_CONFIRMED_BY_READBACK"


BOY_HEIGHT_RANGE = (150, 170)
BOY_WEIGHT_RANGE = (42, 60)
GIRL_HEIGHT_RANGE = (146, 166)
GIRL_WEIGHT_RANGE = (38, 56)


def build_facility_updates(current: dict, cwsn: bool, rng: random.Random, gender=None, class_label: str = "") -> dict:
    """Blank-only updates. Saved values are never overwritten.

    Classes IX-X use the operator-specified lower adolescent ranges. XI-XII
    retain the existing Facility Profile ranges for compatibility.
    """
    updates: dict = {}

    # ------------------------------------------------------------ Yes/No flags
    for label, field_name in FACILITY_YN.items():
        if field_name == "facProvidedCwsnYn" and not cwsn:
            continue  # not applicable for a non-CWSN student
        saved = yes_no_code(current.get(field_name))
        if saved is None:
            updates[field_name] = 2  # No

    # ------------------------------------------------------------- measurements
    gender_code = str(gender or "").strip().lower()
    is_female = gender_code in {"2", "2.0", "female", "girl", "f"}
    if str(class_label).strip().upper() in {"CLASS IX", "CLASS X", "IX", "X"}:
        # Requested ranges for Classes IX-X only. Female ranges are lower
        # than the corresponding male ranges. XI-XII keep the legacy ranges.
        height_range = (135, 150) if is_female else (140, 155)
        weight_range = (34, 48) if is_female else (38, 52)
    else:
        height_range = GIRL_HEIGHT_RANGE if is_female else BOY_HEIGHT_RANGE
        weight_range = GIRL_WEIGHT_RANGE if is_female else BOY_WEIGHT_RANGE
    height_min, height_max = height_range
    weight_min, weight_max = weight_range
    if is_blank(current.get("heightInCm")):
        updates["heightInCm"] = str(rng.randint(height_min, height_max))
    if is_blank(current.get("weightInKg")):
        updates["weightInKg"] = str(rng.randint(weight_min, weight_max))

    # --------------------------------------------------------------- dropdowns
    if is_blank_code(current.get("distanceFrmSchool")):
        updates["distanceFrmSchool"] = str(rng.choice(DISTANCE_CHOICES))
    if is_blank_code(current.get("parentEducation")):
        updates["parentEducation"] = str(DEFAULT_PARENT_EDUCATION_CODE)

    return updates


def build_facility_payload(school_id: str, current: dict, updates: dict,
                           cwsn: bool) -> dict:
    """Carry the full record, then apply the blank-only updates.

    Facility list fields (facProvided / facProvidedCwsn) are sent as-is; the
    notebook does not generate facility-item selections.
    """
    payload = {"schoolId": int(school_id)}

    for label, field_name in FACILITY_YN.items():
        if field_name == "facProvidedCwsnYn" and not cwsn:
            payload[field_name] = 9  # not applicable
            continue
        value = updates.get(field_name, yes_no_code(current.get(field_name)))
        payload[field_name] = value if value is not None else 2

    for field_name, saved_key in (("facProvided", "facProvided"),
                                  ("facProvidedCwsn", "facProvidedCwsn")):
        if field_name == "facProvidedCwsn" and not cwsn:
            payload[field_name] = None
            continue
        saved = current.get(saved_key)
        payload[field_name] = sorted(int(v) for v in saved) if isinstance(saved, list) and saved else None

    payload["heightInCm"] = str(updates.get("heightInCm", current.get("heightInCm")))
    payload["weightInKg"] = str(updates.get("weightInKg", current.get("weightInKg")))
    payload["distanceFrmSchool"] = str(
        updates.get("distanceFrmSchool", current.get("distanceFrmSchool"))
    )
    payload["parentEducation"] = str(
        updates.get("parentEducation", current.get("parentEducation"))
    )
    return payload


def compare(saved: dict, payload: dict) -> list:
    """Fields where the saved record does not match what we intend to write."""
    def norm(key, value):
        if key in {"facProvided", "facProvidedCwsn"}:
            if value is None:
                return []
            if isinstance(value, str):
                return [value] if value else []
            return sorted(int(v) for v in value)
        return str(value) if value is not None else ""

    return [
        key for key, want in payload.items()
        if key != "schoolId" and norm(key, saved.get(key)) != norm(key, want)
    ]


def run_facility(
    session,
    *,
    class_scope_name: str = "IX",
    limit: int = 0,
    allow_submit: bool = False,
    max_submissions: int = 1,
    seed: int | None = None,
) -> list[FacilityResult]:
    """Preview (and optionally submit) Facility blank-only fills."""
    classes = class_scope(class_scope_name)

    selected = [
        s for s in session.students
        if int(s.get("classId") or -1) in classes
    ]
    if not selected:
        raise ValueError(f"No students found for scope {class_scope_name}.")
    total_available = len(selected)
    if limit and limit > 0:
        selected = selected[:limit]

    print(
        f"🏫 Facility scope: {class_scope_name} | {len(selected)} student(s)"
        + (f" of {total_available}" if limit else ""),
        flush=True,
    )
    if not allow_submit:
        print("🔒 Preview only — no POST will be sent.", flush=True)

    rng = random.Random(seed)
    results: list[FacilityResult] = []
    submissions = 0

    for position, student in enumerate(selected, 1):
        sid = str(student.get("studentId") or student.get("id") or "").strip()
        pen = str(student.get("studentCodeNat") or "").strip()
        class_label = CLASS_LABEL.get(int(student.get("classId") or 0), "")
        name = str(student.get("studentName") or "").strip()

        result = FacilityResult(pen=pen, student_id=sid, name=name,
                                class_label=class_label, status="PENDING")

        # ------------------------------------------ CWSN applicability
        try:
            general = session.student_detail(sid)
            cwsn = str(general.get("cwsnYN")) == "1"
            gender = general.get("genderId") or general.get("gender") or general.get("sex")
        except Exception as exc:
            result.status = "READ_ERROR"
            result.detail = f"General Profile unreadable: {type(exc).__name__}"
            results.append(result)
            print(f"⚠️ {pen}: {result.detail}", flush=True)
            continue

        # --------------------------------------------- fresh FP read
        try:
            current = session.get_json(GET_ROUTE.format(sid=sid),
                                       read_timeout=60).get("data")
            if not isinstance(current, dict):
                raise RuntimeError("no facility data")
        except Exception as exc:
            result.status = "READ_ERROR"
            result.detail = f"{type(exc).__name__}: {exc}"
            results.append(result)
            print(f"⚠️ {pen}: FP read failed — {result.detail}", flush=True)
            continue

        updates = build_facility_updates(
            current, cwsn, rng, gender=gender, class_label=class_label
        )
        if not updates:
            result.status = "SKIPPED_ALREADY_UP_TO_DATE"
            result.detail = "Nothing blank to fill."
            results.append(result)
            print(f"• {pen}: nothing to fill.", flush=True)
            continue

        result.changes = sorted(updates)
        result.proposed = dict(updates)
        payload = build_facility_payload(session.school_id, current, updates, cwsn)

        if not allow_submit:
            result.status = "PREVIEW"
            result.detail = f"{len(updates)} field(s) would be set."
            results.append(result)
            print(
                f"👁️ {position}/{len(selected)} {pen}: preview — "
                + ", ".join(f"{k}={v}" for k, v in sorted(updates.items())),
                flush=True,
            )
            continue

        if submissions >= max_submissions:
            result.status = "LIMIT_REACHED"
            result.detail = f"max submissions ({max_submissions}) reached."
            results.append(result)
            print(f"🛑 {pen}: submission cap reached.", flush=True)
            break

        # --------------------------------------------------- one write
        post_error = None
        try:
            status_code, body = session._request(
                "POST", POST_ROUTE.format(sid=sid), attempts=1,
                read_timeout=300, connect_timeout=15, label="FP-POST",
                json=payload,
            )
            err = body.get("error") or {}
            detail = err.get("message") if isinstance(err, dict) else str(err)
            if status_code != 200 or not body.get("status"):
                result.status = "FAILED"
                result.detail = f"HTTP {status_code}; {detail or body.get('message') or 'rejected'}"
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

        # -------------------------------------------- read-back (3 tries)
        result.status = "UNCONFIRMED"
        for attempt, delay in enumerate((2, 5, 10), 1):
            time.sleep(delay)
            try:
                saved = session.get_json(GET_ROUTE.format(sid=sid),
                                         read_timeout=60).get("data")
                remaining = compare(saved or {}, payload)
                if not remaining:
                    result.status = "SUCCESS_CONFIRMED_BY_READBACK"
                    result.detail = "Saved fields confirmed."
                    if post_error:
                        result.detail += " (POST reported a transport error.)"
                    break
                result.detail = "Still mismatched: " + ", ".join(remaining)
            except Exception as exc:
                result.detail = f"Read-back failed: {type(exc).__name__}"

        results.append(result)
        if result.confirmed:
            print(f"✅ {pen}: saved and confirmed.", flush=True)
        else:
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
