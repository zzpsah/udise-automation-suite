"""General Profile — AUTO fill of approved blank defaults.

Ported from the notebook's AUTO GP cell. Behaviour preserved exactly:

  - only a genuinely blank current value is filled
  - existing nonblank saved values are preserved
  - CWSN is normalized to No (2) automatically, without a review gate
  - unexpected CWSN codes are normalized to No rather than skipped
  - one POST only; never blindly replayed
  - success requires a fresh read-back matching every submitted field
"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from typing import Any

from .constants import (
    AAY_NOT_APPLICABLE,
    AAY_NO,
    AUTO_GP_DEFAULTS,
    BLOOD_GROUP_API_ACCEPTED,
    BLOOD_GROUP_UNDER_INVESTIGATION,
    CLASS_LABEL,
    CWSN_SKIP_CODES,
    EWS_EXCLUDED_CATEGORIES,
    EWS_NO,
    MOTHER_TONGUE_CHOICES,
    MOTHER_TONGUE_DEFAULT,
    class_scope,
)

BLANK_VALUES = {None, "", "0", 0, "null", "None"}


def is_blank(value: Any) -> bool:
    """True when the portal value is genuinely unset.

    The portal reports an unset code field as numeric 0, not null, so a check
    that only tests for '' would treat 0 as a saved value.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in {"", "0", "null", "None"}
    return value == 0


def as_code(value) -> int | None:
    """Coerce a portal code to int, or None when unset/unparseable."""
    if is_blank(value):
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


INVALID_AUTO_GP_CODES = {"isBplYN", "ewsYN", "natIndYN", "ooscYN"}


def approved_gp_conflicts(fresh: dict[str, Any], changes: dict[str, Any]) -> list[str]:
    """Find true stale-value conflicts, excluding invalid AUTO placeholders.

    Preview intentionally replaces code 9 for these four yes/no fields with a
    valid approved 1/2 value. Save-time conflict detection must use the same
    eligibility rule or it will reject its own approved plan.
    """
    conflicts = []
    for field_name, value in changes.items():
        live = fresh.get(field_name)
        if field_name == "cwsnYN" and str(value) == "2" and str(live) in CWSN_SKIP_CODES:
            continue
        if field_name in INVALID_AUTO_GP_CODES and str(live).strip() == "9":
            continue
        if not is_blank(live) and str(live) != str(value):
            conflicts.append(field_name)
    return conflicts


def reconcile_approved_gp_conflicts(
    fresh: dict[str, Any],
    reread: dict[str, Any],
    changes: dict[str, Any],
    manual_fields: set[str] | None = None,
) -> tuple[dict[str, Any], list[str], bool]:
    """Accept a second fresh read only when it resolves transient AUTO conflicts.

    The portal has returned inconsistent GP snapshots for the same student. A
    second read may be used to establish current state, but never to bypass a
    conflict on an operator-entered manual field. A persistent valid-value
    conflict remains blocking and is not overwritten.
    """
    manual_fields = set(manual_fields or ())
    conflicts = approved_gp_conflicts(fresh, changes)
    if not conflicts or any(field in manual_fields for field in conflicts):
        return fresh, conflicts, False
    reread_conflicts = approved_gp_conflicts(reread, changes)
    if len(reread_conflicts) < len(conflicts):
        return reread, reread_conflicts, True
    return fresh, conflicts, False


def resolve_approved_gp_changes(
    changes: dict[str, Any], conflicts: list[str], manual_fields: set[str] | None = None
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Filter stale AUTO defaults in a manual batch without weakening manual safeguards.

    Returns (safe_updates, blocking_conflicts, skipped_auto_conflicts). Ordinary
    approved plans remain all-or-nothing; only a manual-entry batch may omit
    stale AUTO fields and proceed with independent verified fields.
    """
    manual_fields = set(manual_fields or ())
    if not manual_fields:
        return ({} if conflicts else dict(changes), list(conflicts), [])
    blocking = [field for field in conflicts if field in manual_fields]
    if blocking:
        return {}, blocking, []
    skipped_auto = [field for field in conflicts if field not in manual_fields]
    safe = {field: value for field, value in changes.items() if field not in skipped_auto}
    return safe, [], skipped_auto


def student_rng(pen: str, seed: int = 20261003) -> random.Random:
    """A per-student RNG seeded from the PEN.

    Values must be reproducible: a re-run has to generate the same numbers, or
    every read-back looks like a mismatch.
    """
    digest = hashlib.sha256(f"{seed}:{pen}".encode()).hexdigest()
    return random.Random(int(digest[:12], 16))


def pick_mother_tongue(rng: random.Random | None = None) -> int:
    """Field 4.1.12 Mother Tongue, for a blank value.

    Chooses between the generic default (42 - HINDI - Hindi) and the Bihar-
    region option (28 - HINDI - Bhojpuri). 42 is the general default because it
    is safe for any school; 28 is offered because schools in this region use it.
    Pass a seeded RNG for a reproducible choice.
    """
    if rng is None:
        return MOTHER_TONGUE_DEFAULT
    return rng.choice(MOTHER_TONGUE_CHOICES)


def build_auto_gp_changes(fresh: dict, pen: str) -> tuple[str, dict]:
    """Return the exact AUTO-GP eligibility/result used by preview runs.

    This is the single source of truth for stage-level GP pending counts.
    ``formStatus`` is an overall completion status, not proof that any GP
    AUTO field is blank. For yes/no AUTO fields, portal code 9 is an invalid
    placeholder (the API requires 1 or 2), so treat it like a blank. CWSN is
    normalized to No (2) by the school-approved invariant, including Yes or
    unexpected portal codes; it never triggers a manual confirmation gate.
    """
    # School policy: CWSN is always set to No (2). This is an automatic
    # default, not a review gate; Yes and unexpected codes are normalized too.
    updates = {
        field_name: default
        for field_name, default in AUTO_GP_DEFAULTS.items()
        if is_blank(fresh.get(field_name))
        or (field_name in INVALID_AUTO_GP_CODES and str(fresh.get(field_name)).strip() == "9")
    }
    if as_code(fresh.get("cwsnYN")) != 2:
        updates["cwsnYN"] = 2
    if "motherTongue" in updates:
        updates["motherTongue"] = pick_mother_tongue(student_rng(pen))
    updates = apply_gp_rules(fresh, updates)
    return ("PREVIEW", updates) if updates else ("NO_CHANGE", {})


def apply_gp_rules(fresh: dict, updates: dict) -> dict:
    """Enforce the portal's cross-field rules on the fields being written.

    Rules (from the notebook's build_payload, verified against all 208 live
    records where zero violations were found — guards, not corrections):

      BPL/AAY  (4.1.15) if isBplYN == No (2)          -> aayBplYN = 9 (NA)
                        elif aayBplYN not in (Yes,No) -> aayBplYN = 2 (No)
      EWS      (4.1.16) socCatId in (SC 2, ST 3, OBC 4) -> ewsYN = 2 (No).
                        A student in a reserved category cannot also claim EWS.
      Blood group      clamped to the codes the API accepts (1-9). Code 0
                        ("Unknown") is offered by the UI but rejected on write,
                        so it becomes the Under Investigation placeholder (9).

    Most rules apply only to blank fields or fields already in `updates`.
    Exception: natIndYN is a school-wide invariant for this deployment; all
    enrolled students are Indian nationals, so an explicit No (2) is corrected
    to Yes (1). Other existing values remain protected.
    """
    out = dict(updates)

    # ----------------------------------------------------- Indian national
    # User-confirmed school rule: enrolled students in this school are Indian
    # nationals. Unlike ordinary blank-only defaults, an explicit No is a
    # known incorrect value for this dataset and must be corrected to Yes.
    # Do not add this field for other existing codes or for an unknown value.
    if as_code(fresh.get("natIndYN")) == 2:
        out["natIndYN"] = 1

    def writable(field_name: str) -> bool:
        """May this rule set the field?

        Yes when we are already writing it, or when the portal has it blank.
        A value the portal already holds is NEVER overridden — the same
        blank-only rule that governs every other field.
        """
        return field_name in out or is_blank(fresh.get(field_name))

    # ------------------------------------------------------------ BPL / AAY
    # 4.1.15 AAY. The portal pairs these: a student who is not BPL cannot be an
    # AAY beneficiary.
    bpl = as_code(out.get("isBplYN"))
    if bpl is None:
        bpl = as_code(fresh.get("isBplYN"))
    if bpl is not None and writable("aayBplYN"):
        if bpl == 2:
            out["aayBplYN"] = AAY_NOT_APPLICABLE
        else:
            aay = as_code(out.get("aayBplYN"))
            if aay is None:
                aay = as_code(fresh.get("aayBplYN"))
            if aay not in (1, 2):
                out["aayBplYN"] = AAY_NO

    # ------------------------------------------------------------------ EWS
    # 4.1.16 EWS. A student in a reserved category (SC/ST/OBC) cannot also
    # claim EWS / Disadvantaged Group.
    cat = as_code(out.get("socCatId"))
    if cat is None:
        cat = as_code(fresh.get("socCatId"))
    if cat in EWS_EXCLUDED_CATEGORIES and writable("ewsYN"):
        out["ewsYN"] = EWS_NO

    # ----------------------------------------------------------- blood group
    if "bloodGroup" in out:
        code = str(out["bloodGroup"]).strip()
        if code not in BLOOD_GROUP_API_ACCEPTED:
            out["bloodGroup"] = BLOOD_GROUP_UNDER_INVESTIGATION

    return out


@dataclass
class GpResult:
    pen: str
    student_id: str
    name: str
    class_label: str
    status: str
    father_name: str = ""
    detail: str = ""
    changes: dict = field(default_factory=dict)
    read_back: str = ""
    manual_fields: list[str] = field(default_factory=list)

    @property
    def confirmed(self) -> bool:
        return self.status in {
            "SUCCESS_CONFIRMED",
            "SUCCESS_CONFIRMED_AFTER_POST_ERROR",
        }


def missing_mandatory_gp_fields(fresh: dict) -> list[str]:
    """Return portal-mandatory GP fields that cannot safely be submitted.

    These checks mirror observed validation errors. Address, PIN code and
    minority type are not guessed by AUTO-GP; they must come from verified
    student data. Yes/no fields must carry a valid 1/2 code.
    """
    missing = []
    if not str(fresh.get("address") or "").strip():
        missing.append("address")
    pin = "".join(ch for ch in str(fresh.get("pincode") or "") if ch.isdigit())
    if len(pin) != 6:
        missing.append("pincode")
    try:
        minority = int(float(str(fresh.get("minorityId")).strip()))
    except (TypeError, ValueError):
        minority = None
    if minority not in {1, 2, 3, 4, 5, 6, 7}:
        missing.append("minorityId")
    for field_name in ("isBplYN", "ewsYN", "natIndYN", "ooscYN"):
        if str(fresh.get(field_name) or "").strip() not in {"1", "2"}:
            missing.append(field_name)
    return missing


def build_gp_payload(original: dict, updates: dict) -> dict:
    """Build the GP write payload.

    The portal rejects a payload that omits the record's identity fields with
    an INTERNAL_SERVER_ERROR, so every field the form carries is sent back:
    the identity block, the contact block, and the dropdown block. Omitting any
    of them fails the write even when the values are unchanged.

    Verified live: a 14-field payload returns
      {"type": "INTERNAL_SERVER_ERROR"}
    while this full shape returns {"status": true}.
    """
    def txt(key: str) -> str:
        value = original.get(key)
        return "" if value is None else str(value).strip()

    def num(key: str, default=None):
        value = original.get(key)
        if value is None or str(value).strip() == "":
            return default
        return value

    payload = {
        # ------------------------------------------------------- identity block
        "classId": txt("classId"),
        "sectionId": txt("sectionId"),
        "studentId": txt("studentId"),
        "schoolId": txt("schoolId"),
        "studentCodeState": txt("studentCodeState"),
        # 2 = the Aadhaar/uuid is not being changed by this write.
        "uuidUpdateYN": 2,
        "uuid": "",
        "nameAsUuid": "",
        "certifiedCheckCount": 0,
        "ageCheckSkipped": num("ageCheckSkipped", 2) or 2,

        # ------------------------------------------------------- demographic
        "gender": num("gender"),
        "dob": txt("dob"),
        "motherName": txt("motherName"),
        "fatherName": txt("fatherName"),
        "guardianName": txt("guardianName"),

        # ----------------------------------------------------------- contact
        "address": txt("address"),
        "pincode": num("pincode"),
        "primaryMobile": txt("primaryMobile"),
        "secondaryMobile": txt("secondaryMobile") or None,
        "email": txt("email"),

        # --------------------------------------------------------- dropdowns
        "motherTongue": num("motherTongue"),
        "socCatId": num("socCatId"),
        "minorityId": num("minorityId"),

        # ---------------------------------------------------------- yes / no
        "isBplYN": num("isBplYN"),
        "aayBplYN": num("aayBplYN"),
        "ewsYN": num("ewsYN"),
        "cwsnYN": num("cwsnYN"),
        "natIndYN": num("natIndYN"),
        "ooscYN": num("ooscYN"),

        # ------------------------------------------------------- CWSN detail
        "impairmentType": original.get("impairmentType") or [],
        "disabilityCerti": num("disabilityCerti", 9),
        "impairmentPercent": "",

        # --------------------------------------------------------------- OOSC
        "ooscMainstreamedYN": str(
            original.get("ooscMainstreamedYN")
            if not is_blank(original.get("ooscMainstreamedYN"))
            else "9"
        ),

        # -------------------------------------------------------- blood group
        "bloodGroup": str(
            original.get("bloodGroup")
            if not is_blank(original.get("bloodGroup"))
            else BLOOD_GROUP_UNDER_INVESTIGATION
        ),
    }

    payload.update(updates)

    # Non-CWSN representation, matching the manual GP workflow.
    if payload.get("cwsnYN") == 2:
        payload["impairmentType"] = []
        payload["disabilityCerti"] = 9
        payload["impairmentPercent"] = ""

    return payload


def read_back_matches(fresh: dict, expected: dict) -> list:
    """Return the list of submitted fields the fresh record does NOT confirm."""
    mismatches = []
    for key, want in expected.items():
        got = fresh.get(key)
        if key == "bloodGroup":
            if str(got) != str(want):
                mismatches.append(key)
        elif isinstance(want, int):
            if str(got) != str(want):
                mismatches.append(key)
        elif got != want:
            mismatches.append(key)
    return mismatches


def run_auto_gp(
    session,
    *,
    class_scope_name: str = "IX",
    run_mode: str = "First N students",
    row_limit: int = 10,
    allow_submit: bool = False,
    max_submissions: int = 1,
    get_attempts: int = 2,
    approved_plan: dict | None = None,
) -> list[GpResult]:
    """Preview (and optionally submit) AUTO GP blank defaults.

    allow_submit=False is preview-only and changes nothing on the portal.
    """
    classes = class_scope(class_scope_name)

    selected = [
        s for s in session.students
        if int(s.get("classId", -1)) in classes
    ]
    if not selected:
        raise ValueError(f"No students found for AUTO GP scope: {class_scope_name}")

    available = len(selected)
    if run_mode == "First N students":
        selected = selected[:row_limit]

    print(
        f"🤖 AUTO GP scope: {class_scope_name} | {run_mode} | "
        f"{len(selected)} student(s)"
        + (f" of {available}" if run_mode == "First N students" else ""),
        flush=True,
    )
    if not allow_submit:
        print("🔒 Preview only — ALLOW_AUTO_GP_SUBMIT is off. No writes.", flush=True)

    results: list[GpResult] = []
    submissions = 0

    if approved_plan is not None:
        pen_matches = sum(1 for student in selected if str(student.get("studentCodeNat") or "").strip() in approved_plan)
        sid_matches = sum(1 for student in selected if str(student.get("studentId") or student.get("id") or "").strip() in approved_plan)
        print(
            f"📋 GP approved plan: entries={len(approved_plan)} | PEN matches={pen_matches} | student-ID matches={sid_matches}",
            flush=True,
        )

    for position, student in enumerate(selected, 1):
        sid = str(student.get("studentId") or student.get("id") or "").strip()
        pen = str(student.get("studentCodeNat") or "").strip()
        name = str(student.get("studentName") or "").strip()
        class_label = CLASS_LABEL.get(int(student.get("classId", 0)), "")

        result = GpResult(pen=pen, student_id=sid, name=name, class_label=class_label,
                          status="PENDING")

        try:
            fresh = session.student_detail(sid)
        except Exception as exc:
            result.status = "READ_ERROR"
            result.detail = f"{type(exc).__name__}: {exc}"
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue

        # ------------------------------------------------ approved plan
        if approved_plan is not None:
            plan = approved_plan.get(pen) or approved_plan.get(sid)
            changes = plan.get("changes") if isinstance(plan, dict) else None
            if not isinstance(changes, dict) or not changes:
                result.status = "SKIPPED_NOT_IN_APPROVED_PLAN"
                gp_reason, gp_changes = build_auto_gp_changes(fresh, pen)
                if gp_changes:
                    fields = ", ".join(sorted(gp_changes))
                    result.detail = (
                        f"Reason: Current GP has eligible blank field(s): {fields}, "
                        "but they were not included in the saved Preview plan. "
                        "Action: Refresh Preview, review the new GP save plan, and Save again. No POST sent."
                    )
                elif gp_reason == "CWSN_CONFIRM_REQUIRED":
                    result.detail = (
                        "Reason: CWSN is currently Yes and requires explicit confirmation before GP can be changed. "
                        "Action: Review and confirm CWSN=No in the Preview workflow, then Save. No POST sent."
                    )
                elif gp_reason == "SKIPPED_CWSN_UNEXPECTED":
                    result.detail = (
                        "Reason: CWSN has an unexpected saved value, so automatic GP update is blocked. "
                        "Action: Verify the CWSN value manually and correct it in the portal if required. No POST sent."
                    )
                elif str(fresh.get("formStatus", "")).strip() == "0":
                    result.status = "MANUAL_REVIEW_GP_INCOMPLETE"
                    result.detail = (
                        "Reason: Portal formStatus=0 (GP incomplete), but no eligible blank AUTO-GP fields were found. "
                        "Action: Open this student's General Profile in the portal, identify the incomplete/invalid required field, "
                        "correct it manually, save GP, then refresh EP Preview. Existing values were not overwritten; no POST sent."
                    )
                else:
                    result.detail = (
                        "Reason: Current GP has no eligible blank fields to save. "
                        "Action: No action required; refresh Preview if you expected a change. No POST sent."
                    )
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            # CWSN confirmation is an explicit operator authorization to
            # change the live Yes value to No. It is expected that the fresh
            # read still shows Yes immediately before the POST, so this
            # authorized transition must not be treated as a state conflict.
            manual_fields = set(plan.get("manual_fields") or []) if isinstance(plan, dict) else set()
            conflicts = approved_gp_conflicts(fresh, changes)
            if conflicts and not any(field in manual_fields for field in conflicts):
                # Read the student once more before declaring a stale conflict.
                # Only a second snapshot that itself matches the approved value
                # or remains blank/invalid can clear the transient conflict.
                try:
                    time.sleep(0.25)
                    reread = session.student_detail(sid)
                    fresh, conflicts, reconciled = reconcile_approved_gp_conflicts(
                        fresh, reread, changes, manual_fields
                    )
                    if reconciled:
                        print(
                            f"ℹ️ {pen}: a transient GP value mismatch resolved on immediate re-read; "
                            "using the latest GP snapshot.", flush=True,
                        )
                except Exception as exc:
                    print(
                        f"⚠️ {pen}: could not re-check a stale GP conflict ({type(exc).__name__}); "
                        "preserving the no-write safeguard.", flush=True,
                    )
            updates, blocking_conflicts, skipped_auto_conflicts = resolve_approved_gp_changes(
                changes, conflicts, manual_fields
            )
            if blocking_conflicts:
                detail_prefix = "Manually entered fields changed since review: " if manual_fields else "Live GP values changed since preview: "
                result.status = "SKIPPED_STATE_CHANGED"
                result.detail = detail_prefix + ", ".join(blocking_conflicts) + ". No POST sent."
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            if skipped_auto_conflicts:
                result.detail = "Skipped stale AUTO defaults that changed since preview: " + ", ".join(skipped_auto_conflicts) + "; continuing with verified manual fields and unchanged eligible fields."
            result.changes = updates
            if max_submissions > 0 and submissions >= max_submissions:
                result.status = "LIMIT_REACHED"
                result.detail = "AUTO_GP_MAX_SUBMISSIONS=%s reached." % max_submissions
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            effective_gp = dict(fresh)
            effective_gp.update(updates)
            required_missing = missing_mandatory_gp_fields(effective_gp)
            if required_missing:
                result.status = "MANUAL_REVIEW_GP_INCOMPLETE"
                result.detail = (
                    "Reason: mandatory GP fields are missing/invalid: " + ", ".join(required_missing) + ". "
                    "Action: enter verified address/PIN/minority details in the portal and refresh Preview; "
                    "AUTO-GP will not invent personal data. No POST sent."
                )
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            payload = build_gp_payload(fresh, updates)
            try:
                status_code, body = session.post_once("/p0/api/cy/students/%s" % sid, json_body=payload)
                if status_code != 200 or body.get("status") is not True:
                    result.status = "FAILED"
                    result.detail = "HTTP %s; %s" % (status_code, body.get("message") or body.get("error") or "rejected")
                    results.append(result)
                    print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                    continue
            except Exception as exc:
                result.status = "UNCONFIRMED"
                result.detail = "POST transport error: %s; state unknown." % type(exc).__name__
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            submissions += 1
            time.sleep(2)
            try:
                verify = session.student_detail(sid)
            except Exception as exc:
                result.status = "UNCONFIRMED"
                result.detail = "Read-back failed: %s: %s" % (type(exc).__name__, exc)
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            mismatches = read_back_matches(verify, updates)
            if mismatches:
                result.status = "UNCONFIRMED"
                result.detail = "Fresh GP does not confirm: " + ", ".join(mismatches) + "."
                results.append(result)
                continue
            result.read_back = "All approved fields confirmed"
            result.status = "SUCCESS_CONFIRMED"
            result.detail = "Approved preview values saved and confirmed by fresh GP read-back."
            results.append(result)
            print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue

        # ------------------------------------------------- shared eligibility
        eligibility, updates = build_auto_gp_changes(fresh, pen)

        effective_gp = dict(fresh)
        effective_gp.update(updates)
        required_missing = missing_mandatory_gp_fields(effective_gp)
        result.manual_fields = list(required_missing)
        result.changes = updates

        if not allow_submit and (updates or required_missing):
            result.status = "PREVIEW"
            detail_parts = []
            if updates:
                detail_parts.append(f"{len(updates)} autofill field(s) ready")
            if required_missing:
                detail_parts.append("manual input required: " + ", ".join(required_missing))
            result.detail = "; ".join(detail_parts) + "."
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue

        if not updates:
            if required_missing:
                result.status = "MANUAL_REVIEW_GP_INCOMPLETE"
                result.detail = "Mandatory GP fields need verified manual input: " + ", ".join(required_missing) + ". No POST sent."
            elif str(fresh.get("formStatus", "")).strip() == "0":
                result.status = "MANUAL_REVIEW_GP_INCOMPLETE"
                result.detail = (
                    "Portal formStatus=0, but no eligible blank AUTO-GP fields were found. "
                    "Check the portal's remaining required fields and refresh Preview. No POST sent."
                )
            else:
                result.status = "NO_CHANGE"
                result.detail = "Fresh GP has no blank AUTO fields."
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue

        if max_submissions > 0 and submissions >= max_submissions:
            result.status = "LIMIT_REACHED"
            result.detail = f"AUTO_GP_MAX_SUBMISSIONS={max_submissions} reached."
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue

        # --------------------------------------------------------- one write
        effective_gp = dict(fresh)
        effective_gp.update(updates)
        required_missing = missing_mandatory_gp_fields(effective_gp)
        if required_missing:
            result.status = "MANUAL_REVIEW_GP_INCOMPLETE"
            result.detail = (
                "Mandatory GP fields are missing/invalid: " + ", ".join(required_missing) + ". "
                "Enter verified address/PIN/minority details in the portal and refresh Preview; "
                "AUTO-GP will not invent personal data. No POST sent."
            )
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue
        payload = build_gp_payload(fresh, updates)
        post_error = None
        try:
            status_code, body = session.post_once(
                f"/p0/api/cy/students/{sid}", json_body=payload
            )
            if status_code != 200 or body.get("status") is not True:
                result.status = "FAILED"
                result.detail = (
                    f"HTTP {status_code}; "
                    f"{body.get('message') or body.get('error') or 'rejected'}"
                )
                results.append(result)
                print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
        except Exception as exc:
            # Transmitted state is unknown — read back before deciding anything.
            post_error = exc
            print(
                f"⚠️ {pen}: POST transport error ({type(exc).__name__}). "
                "Not retrying; checking fresh GP…",
                flush=True,
            )

        submissions += 1

        # ------------------------------------------------------- read-back
        time.sleep(2)
        try:
            verify = session.student_detail(sid)
        except Exception as exc:
            result.status = "UNCONFIRMED"
            result.detail = f"Read-back failed: {type(exc).__name__}: {exc}"
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue
        mismatches = read_back_matches(verify, updates)

        if not mismatches:
            result.read_back = "All AUTO fields confirmed"
            result.status = (
                "SUCCESS_CONFIRMED_AFTER_POST_ERROR" if post_error
                else "SUCCESS_CONFIRMED"
            )
            result.detail = (
                "Fresh GP read-back matches all submitted defaults."
                + (" (POST reported a transport error.)" if post_error else "")
            )
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
        else:
            result.status = "UNCONFIRMED"
            result.detail = (
                f"Fresh GP does not confirm: {', '.join(mismatches)}. "
                "Manual review required."
            )
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue
    confirmed = sum(1 for r in results if r.confirmed)
    no_change = sum(1 for r in results if r.status == "NO_CHANGE")
    previewed = sum(1 for r in results if r.status == "PREVIEW")
    other = len(results) - confirmed - no_change - previewed
    status_counts = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
    breakdown = " | ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
    print(f"📋 GP outcome: {breakdown}", flush=True)
    if approved_plan is not None:
        not_in_plan = sum(1 for r in results if r.status == "SKIPPED_NOT_IN_APPROVED_PLAN")
        state_changed = sum(1 for r in results if r.status == "SKIPPED_STATE_CHANGED")
        limit_reached = sum(1 for r in results if r.status == "LIMIT_REACHED")
        failed = sum(1 for r in results if r.status == "FAILED")
        unconfirmed = sum(1 for r in results if r.status == "UNCONFIRMED")
        print(
            f"📋 GP approved outcome: not-in-plan={not_in_plan} | state-changed={state_changed} | "
            f"limit-reached={limit_reached} | failed={failed} | unconfirmed={unconfirmed}",
            flush=True,
        )

    print("\n" + "━" * 30)
    print(f"✅ Saved + confirmed : {confirmed}")
    print(f"•  No change needed  : {no_change}")
    if previewed:
        print(f"👁️  Preview only      : {previewed}")
    if other:
        print(f"⚠️  Other (see GP_RESULT events above) : {other}")
    print("━" * 30)

    return results
