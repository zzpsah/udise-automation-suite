"""General Profile — AUTO fill of approved blank defaults.

Ported from the notebook's AUTO GP cell. Behaviour preserved exactly:

  - only a genuinely blank current value is filled
  - existing nonblank saved values are preserved
  - fresh CWSN=Yes skips the student entirely (manual review)
  - unexpected nonblank CWSN codes are also skipped
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
    CWSN_UNEXPECTED_SKIP,
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

    A rule applies to a field only when it is BLANK on the portal or already in
    `updates`. A value the portal already holds is never overridden — the same
    blank-only rule that governs every other field.
    """
    out = dict(updates)

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

    @property
    def confirmed(self) -> bool:
        return self.status in {
            "SUCCESS_CONFIRMED",
            "SUCCESS_CONFIRMED_AFTER_POST_ERROR",
        }


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
            print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
            continue

        # ------------------------------------------------ approved plan
        if approved_plan is not None:
            plan = approved_plan.get(pen) or approved_plan.get(sid)
            changes = plan.get("changes") if isinstance(plan, dict) else None
            if not isinstance(changes, dict) or not changes:
                result.status = "SKIPPED_NOT_IN_APPROVED_PLAN"
                result.detail = "Student was not eligible in the approved preview plan; no POST sent."
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            # CWSN confirmation is an explicit operator authorization to
            # change the live Yes value to No. It is expected that the fresh
            # read still shows Yes immediately before the POST, so this
            # authorized transition must not be treated as a state conflict.
            conflicts = [
                f for f, v in changes.items()
                if not (
                    f == "cwsnYN"
                    and str(v) == "2"
                    and str(fresh.get(f)) in CWSN_SKIP_CODES
                )
                and not is_blank(fresh.get(f))
                and str(fresh.get(f)) != str(v)
            ]
            if conflicts:
                result.status = "SKIPPED_STATE_CHANGED"
                result.detail = "Live GP values changed since preview: " + ", ".join(conflicts) + ". No POST sent."
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                continue
            updates = dict(changes)
            result.changes = updates
            if max_submissions > 0 and submissions >= max_submissions:
                result.status = "LIMIT_REACHED"
                result.detail = "AUTO_GP_MAX_SUBMISSIONS=%s reached." % max_submissions
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
                    break
            except Exception as exc:
                result.status = "UNCONFIRMED"
                result.detail = "POST transport error: %s; state unknown." % type(exc).__name__
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                break
            submissions += 1
            time.sleep(2)
            try:
                verify = session.student_detail(sid)
            except Exception as exc:
                result.status = "UNCONFIRMED"
                result.detail = "Read-back failed: %s: %s" % (type(exc).__name__, exc)
                results.append(result)
                print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
                break
            mismatches = read_back_matches(verify, updates)
            if mismatches:
                result.status = "UNCONFIRMED"
                result.detail = "Fresh GP does not confirm: " + ", ".join(mismatches) + "."
                results.append(result)
                break
            result.read_back = "All approved fields confirmed"
            result.status = "SUCCESS_CONFIRMED"
            result.detail = "Approved preview values saved and confirmed by fresh GP read-back."
            results.append(result)
            print(f"📋 GP_APPROVED_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue

        # ---------------------------------------------------------- CWSN safety
        fresh_cwsn = str(fresh.get("cwsnYN"))
        if fresh_cwsn in CWSN_SKIP_CODES:
            result.status = "CWSN_CONFIRM_REQUIRED"
            result.detail = "Fresh GP shows CWSN=Yes. User confirmation required before setting CWSN=No; no POST sent."
            result.changes = {"cwsnYN": 2}
            results.append(result)
            print(f"📋 GP_CWSN_CONFIRM_REQUIRED pen={pen} name={name} detail={result.detail}", flush=True)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue
        if fresh_cwsn in CWSN_UNEXPECTED_SKIP:
            result.status = "SKIPPED_CWSN_UNEXPECTED"
            result.detail = f"Unexpected CWSN code {fresh_cwsn}. Manual review."
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} name={name} detail={result.detail}", flush=True)
            continue

        # ------------------------------------------------- blank-only diff
        updates = {
            field_name: default
            for field_name, default in AUTO_GP_DEFAULTS.items()
            if is_blank(fresh.get(field_name))
        }

        # 4.1.12 Mother Tongue: a blank gets a randomised choice between the
        # generic default and the region option. Only ever set when blank.
        if "motherTongue" in updates:
            updates["motherTongue"] = pick_mother_tongue(student_rng(pen))

        # Then enforce the portal's cross-field rules on what we are writing.
        # A rule only adjusts a field already in `updates`; it never invents an
        # update for a field the student already has.
        updates = apply_gp_rules(fresh, updates)

        if not updates:
            result.status = "NO_CHANGE"
            result.detail = "Fresh GP has no approved blank AUTO fields."
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
            continue

        result.changes = updates

        if not allow_submit:
            result.status = "PREVIEW"
            result.detail = f"{len(updates)} blank field(s) would be filled."
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
            continue

        if max_submissions > 0 and submissions >= max_submissions:
            result.status = "LIMIT_REACHED"
            result.detail = f"AUTO_GP_MAX_SUBMISSIONS={max_submissions} reached."
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
            continue

        # --------------------------------------------------------- one write
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
                print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
                break
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
            print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
            break

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
            print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
        else:
            result.status = "UNCONFIRMED"
            result.detail = (
                f"Fresh GP does not confirm: {', '.join(mismatches)}. "
                "Manual review required."
            )
            results.append(result)
            print(f"📋 GP_RESULT status={result.status} pen={pen} detail={result.detail}", flush=True)
            break

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
