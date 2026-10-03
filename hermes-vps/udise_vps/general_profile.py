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

import time
from dataclasses import dataclass, field
from typing import Any

from .constants import (
    AUTO_GP_DEFAULTS,
    CLASS_LABEL,
    CWSN_SKIP_CODES,
    CWSN_UNEXPECTED_SKIP,
    class_scope,
)

BLANK_VALUES = {None, "", "0", 0, "null", "None"}


def is_blank(value: Any) -> bool:
    """True when the portal value is genuinely unset."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() in {"", "0", "null", "None"}
    return value == 0


@dataclass
class GpResult:
    pen: str
    student_id: str
    name: str
    class_label: str
    status: str
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
    """Carry every untouched field across, then apply the approved updates.

    Mirrors the notebook's payload construction so no field is silently dropped.
    """
    payload = {
        "motherTongue": original.get("motherTongue"),
        "socCatId": original.get("socCatId"),
        "minorityId": original.get("minorityId"),
        "isBplYN": original.get("isBplYN"),
        "aayBplYN": original.get("aayBplYN"),
        "ewsYN": original.get("ewsYN"),
        "cwsnYN": original.get("cwsnYN"),
        "natIndYN": original.get("natIndYN"),
        "ooscYN": original.get("ooscYN"),
        "impairmentType": original.get("impairmentType"),
        "disabilityCerti": original.get("disabilityCerti"),
        "impairmentPercent": original.get("impairmentPercent"),
        "ooscMainstreamedYN": str(
            original.get("ooscMainstreamedYN")
            if not is_blank(original.get("ooscMainstreamedYN"))
            else "9"
        ),
        "bloodGroup": str(
            original.get("bloodGroup")
            if not is_blank(original.get("bloodGroup"))
            else "9"
        ),
    }

    payload.update(updates)

    # Non-CWSN representation, matching the manual GP workflow.
    if updates.get("cwsnYN") == 2:
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
            print(f"⚠️ {pen}: read failed — {result.detail}", flush=True)
            continue

        # ---------------------------------------------------------- CWSN safety
        fresh_cwsn = str(fresh.get("cwsnYN"))
        if fresh_cwsn in CWSN_SKIP_CODES:
            result.status = "SKIPPED_CWSN"
            result.detail = "Fresh GP shows CWSN=Yes. No POST sent. Manual review."
            results.append(result)
            print(f"⏭️ {pen}: CWSN=Yes — skipped for manual review.", flush=True)
            continue
        if fresh_cwsn in CWSN_UNEXPECTED_SKIP:
            result.status = "SKIPPED_CWSN_UNEXPECTED"
            result.detail = f"Unexpected CWSN code {fresh_cwsn}. Manual review."
            results.append(result)
            print(f"⏭️ {pen}: CWSN={fresh_cwsn} unexpected — manual review.", flush=True)
            continue

        # ------------------------------------------------- blank-only diff
        updates = {
            field_name: default
            for field_name, default in AUTO_GP_DEFAULTS.items()
            if is_blank(fresh.get(field_name))
        }

        if not updates:
            result.status = "NO_CHANGE"
            result.detail = "Fresh GP has no approved blank AUTO fields."
            results.append(result)
            print(f"• {pen}: nothing blank to fill.", flush=True)
            continue

        result.changes = updates

        if not allow_submit:
            result.status = "PREVIEW"
            result.detail = f"{len(updates)} blank field(s) would be filled."
            results.append(result)
            print(
                f"👁️ {position}/{len(selected)} {pen}: preview — "
                f"{', '.join(updates)}",
                flush=True,
            )
            continue

        if submissions >= max_submissions:
            result.status = "LIMIT_REACHED"
            result.detail = f"AUTO_GP_MAX_SUBMISSIONS={max_submissions} reached."
            results.append(result)
            print(f"🛑 {pen}: submission cap reached.", flush=True)
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
                print(f"❌ {pen}: {result.detail}", flush=True)
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
            print(f"⚠️ {pen}: could not confirm — check the portal.", flush=True)
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
            print(f"✅ {pen}: AUTO GP saved and confirmed.", flush=True)
        else:
            result.status = "UNCONFIRMED"
            result.detail = (
                f"Fresh GP does not confirm: {', '.join(mismatches)}. "
                "Manual review required."
            )
            results.append(result)
            print(f"⚠️ {pen}: {result.detail}", flush=True)
            break

    confirmed = sum(1 for r in results if r.confirmed)
    no_change = sum(1 for r in results if r.status == "NO_CHANGE")
    previewed = sum(1 for r in results if r.status == "PREVIEW")
    other = len(results) - confirmed - no_change - previewed

    print("\n" + "━" * 30)
    print(f"✅ Saved + confirmed : {confirmed}")
    print(f"•  No change needed  : {no_change}")
    if previewed:
        print(f"👁️  Preview only      : {previewed}")
    if other:
        print(f"⚠️  Skipped / other   : {other}")
    print("━" * 30)

    return results
