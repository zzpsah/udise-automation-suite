"""Facility Profile — Classes IX to XII.

Ported from the notebook's Facility cells (19-22).

Rules confirmed with the operator:
  - A saved measurement stays. Only blank fields are filled.
  - Classes IX-X boys: blank height -> 140..160 cm; blank weight -> 38..55 kg
  - Classes IX-X girls: corresponding lower range -> 135..155 cm; 34..50 kg
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
    """Normalize every known UDISE Yes/No representation.

    The portal can return a coded value as a number (1/2), a boolean, or a
    display string such as "1 - Yes" / "2 - No". The preview and save-read
    paths must interpret all of those identically; otherwise an existing Yes
    can be mistaken for blank during preview and then appear as a state change
    during the protected save step.

    Code 9 (and blank/0) means unanswered for these fields. Code 1 is Yes and
    code 2 is No, so a real Yes remains protected from an automatic No write.
    """
    lowered = text(value).strip().lower()
    if lowered in {"yes", "1", "1.0", "true"}:
        return 1
    if lowered in {"no", "2", "2.0", "false"}:
        return 2

    # Portal display/catalogue variants: "1 - Yes", "Yes - 1",
    # "1: Yes", "Yes (1)", etc. Prefer an explicit Yes/No label over
    # incidental digits elsewhere in the string.
    if "yes" in lowered:
        return 1
    if "no" in lowered:
        return 2
    if lowered in {"0", "0.0", "9", "9.0"}:
        return None
    return None


def approved_yn_conflict(live, proposed) -> bool:
    """Return True only when a fresh saved Yes/No conflicts with approval.

    P4 rule: an approved No (2) is specifically intended to resolve a live
    unanswered field. Therefore live blank/0/9 is compatible with approved No.
    A live Yes (1) is a real protected value and must stop the write.
    """
    live_norm = yes_no_code(live)
    proposed_norm = yes_no_code(proposed)
    if proposed_norm == 2 and live_norm is None:
        return False
    return live_norm is not None and live_norm != proposed_norm


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

    # If Facilities Provided = No, the dependent activity flags are No when
    # unanswered. Existing Yes values are never overwritten.
    facility_value = updates.get("facilityYn", yes_no_code(current.get("facilityYn")))
    if facility_value == 2:
        for field_name in ("olympdsNlc", "nccYn", "nssYn", "scoutsYn"):
            if yes_no_code(current.get(field_name)) is None:
                updates[field_name] = 2

    # ------------------------------------------------------------- measurements
    gender_code = str(gender or "").strip().lower()
    is_female = gender_code in {"2", "2.0", "female", "girl", "f"}
    if str(class_label).strip().upper() in {"CLASS IX", "CLASS X", "IX", "X"}:
        # Requested ranges for Classes IX-X only. Female ranges are lower
        # than the corresponding male ranges. XI-XII keep the legacy ranges.
        height_range = (135, 155) if is_female else (140, 160)
        weight_range = (34, 50) if is_female else (38, 55)
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
    approved_plan: dict | None = None,
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
    approved_plan = approved_plan or None
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
            print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
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
            print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⚠️ {pen}: FP read failed — {result.detail}", flush=True)
            continue

        plan_item = None
        if approved_plan is not None:
            plan_item = approved_plan.get(pen) or approved_plan.get(sid)
            if not plan_item:
                # "Not in approved plan" is an internal write-safety state, not
                # an operator-useful explanation. Re-evaluate the current live
                # record with the same eligibility rules so the result tells the
                # operator whether the student is actually complete or whether
                # the saved preview is stale/missing this student.
                fresh_eligible = build_facility_updates(
                    current, cwsn, rng, gender=gender, class_label=class_label
                )
                result.status = "SKIPPED_NOT_IN_APPROVED_PLAN"
                if fresh_eligible:
                    fields = ", ".join(sorted(fresh_eligible))
                    result.detail = (
                        "Current FP still has eligible blank/unanswered field(s): "
                        f"{fields}. Student was not included in the saved preview plan; "
                        "refresh Preview before Save. No POST sent."
                    )
                else:
                    result.detail = (
                        "Current FP has no eligible blank/unanswered fields. "
                        "Nothing to save; no POST sent."
                    )
                results.append(result)
                print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
                continue
            updates = dict(plan_item.get("changes") or {})
            conflicts = []
            for field, proposed in updates.items():
                live = current.get(field)
                if field in FACILITY_YN.values():
                    if approved_yn_conflict(live, proposed):
                        conflicts.append(field)
                elif not is_blank(live) and text(live) != text(proposed):
                    conflicts.append(field)
            if conflicts:
                result.status = "SKIPPED_STATE_CHANGED"
                result.detail = "Fresh FP differs from save preview for: " + ", ".join(conflicts)
                results.append(result)
                print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
                continue
        else:
            updates = build_facility_updates(
                current, cwsn, rng, gender=gender, class_label=class_label
            )
        if not updates:
            result.status = "SKIPPED_ALREADY_UP_TO_DATE"
            result.detail = "Nothing blank to fill."
            results.append(result)
            print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"• {pen}: nothing to fill.", flush=True)
            continue

        result.changes = sorted(updates)
        result.proposed = dict(updates)
        payload = build_facility_payload(session.school_id, current, updates, cwsn)

        if not allow_submit:
            result.status = "PREVIEW"
            result.detail = f"{len(updates)} field(s) would be set."
            results.append(result)
            print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(
                f"👁️ {position}/{len(selected)} {pen}: preview — "
                + ", ".join(f"{k}={v}" for k, v in sorted(updates.items())),
                flush=True,
            )
            continue

        if max_submissions > 0 and submissions >= max_submissions:
            result.status = "LIMIT_REACHED"
            result.detail = f"max submissions ({max_submissions}) reached."
            results.append(result)
            print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
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
                print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
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
        print(f"📋 FP_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
        if result.confirmed:
            print(f"✅ {pen}: saved and confirmed.", flush=True)
        else:
            print(f"⚠️ {pen}: {result.detail}", flush=True)
            break

    confirmed = sum(1 for r in results if r.confirmed)
    preview = sum(1 for r in results if r.status == "PREVIEW")
    skipped = sum(1 for r in results if r.status.startswith("SKIPPED"))
    other = len(results) - confirmed - preview - skipped
    failed = sum(1 for r in results if r.status == "FAILED")
    unconfirmed = sum(1 for r in results if r.status == "UNCONFIRMED")
    limit_reached = sum(1 for r in results if r.status == "LIMIT_REACHED")
    read_errors = sum(1 for r in results if r.status == "READ_ERROR")
    print(
        f"📋 FP outcome: confirmed={confirmed} | skipped={skipped} | limit-reached={limit_reached} | "
        f"failed={failed} | unconfirmed={unconfirmed} | read-errors={read_errors}", flush=True
    )

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
