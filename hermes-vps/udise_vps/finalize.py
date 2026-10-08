"""Finalize / Complete Data — the highest-risk write path.

Ported from the notebook's Finalize cell. Every guard is preserved:

  1. AUTO mode uses only completion_ready_pens (formStatus=3).
  2. MANUAL/FILE modes may select other PENs, but every student gets a fresh GET.
  3. Only fresh formStatus=3 is eligible for POST.
  4. Fresh status 6 means already complete — do not POST.
  5. Status 0/1/2/unknown is blocked.
  6. Immediately before POST, re-read again.
  7. POST is never blindly retried.
  8. After a successful-looking POST, a fresh GET must show status 6.
  9. If the POST connection fails after transmission, perform fresh GET
     recovery. Status 6 => confirmed-after-error; otherwise stop for review.
 10. Stop the batch on an unsafe/unconfirmed/rejected result.

Observed endpoint: POST /p0/api/v2/students/submit/{studentId}
Body: the student ID string (Content-Type: text/plain).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

SUBMIT_ROUTE = "/p0/api/v2/students/submit/{student_id}"


@dataclass
class FinalizeResult:
    pen: str
    student_id: str
    name: str
    status: str
    detail: str = ""
    reason: str = ""
    proposed: dict = field(default_factory=dict)

    @property
    def confirmed(self) -> bool:
        return self.status in {
            "SUCCESS_CONFIRMED",
            "SUCCESS_CONFIRMED_AFTER_POST_ERROR",
        }


def _submit_once(session, student_id: str):
    """One POST with a text/plain body. Never retried here."""
    headers = dict(session.headers)
    headers["Content-Type"] = "text/plain"
    return session.session.post(
        session.base_url + SUBMIT_ROUTE.format(student_id=student_id),
        headers=headers,
        data=str(student_id),
        timeout=(20, 300),
        allow_redirects=False,
    )


def finalize(
    session,
    pens: list[str],
    *,
    allow_finalize: bool = False,
    max_submissions: int = 1,
    get_attempts: int = 4,
    approved_plan: dict | None = None,
) -> list[FinalizeResult]:
    """Finalize the given PENs after fresh status verification.

    allow_finalize=False performs the fresh status check and reports what would
    happen, without sending any POST.
    """
    pens = [str(p).strip() for p in pens if str(p).strip()]
    if not pens:
        raise ValueError("No PENs supplied for Finalize.")

    by_pen = {
        str(s.get("studentCodeNat") or "").strip(): s
        for s in session.students
    }

    results: list[FinalizeResult] = []
    submissions = 0
    approved_plan = approved_plan or None

    if not allow_finalize:
        print("🔒 Preview only — ALLOW_FINALIZE is off. No POST will be sent.", flush=True)

    for pen in pens:
        student = by_pen.get(pen)
        if not student:
            results.append(FinalizeResult(
                pen=pen, student_id="", name="", status="NOT_FOUND",
                detail="PEN not present in the loaded roster.",
            ))
            print(f"❌ {pen}: not in roster.", flush=True)
            continue

        sid = str(student.get("studentId") or student.get("id") or "").strip()
        name = str(student.get("studentName") or "").strip()
        result = FinalizeResult(pen=pen, student_id=sid, name=name, status="PENDING")

        # ---------------------------------------------- fresh status read
        try:
            fresh = session.student_detail(sid)
            before = fresh.get("formStatus")
            before = int(before) if before is not None else None
        except Exception as exc:
            result.status = "READ_ERROR"
            result.detail = f"{type(exc).__name__}: {exc}"
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⚠️ {pen}: fresh read failed — {result.detail}", flush=True)
            break

        if before == 6:
            result.status = "SKIPPED_ALREADY_COMPLETE"
            result.detail = "Fresh read shows formStatus=6."
            result.reason = "Already complete; no POST sent."
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⏭️ {pen}: already complete (6).", flush=True)
            continue

        if before != 3:
            result.status = "SKIPPED_NOT_READY"
            result.detail = f"Fresh formStatus={before}; expected 3."
            result.reason = "Only status 3 is eligible."
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⏭️ {pen}: blocked — formStatus={before}.", flush=True)
            continue

        result.reason = "Fresh read confirms formStatus=3."

        if approved_plan is not None:
            plan_item = approved_plan.get(pen) or approved_plan.get(sid)
            if not plan_item:
                result.status = "SKIPPED_NOT_IN_APPROVED_PLAN"
                result.detail = "Student was not eligible in the approved preview plan; no POST sent."
                results.append(result)
                print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
                continue
            expected = plan_item.get("expected_form_status", 3)
            if int(before) != int(expected):
                result.status = "SKIPPED_STATE_CHANGED"
                result.detail = f"Fresh formStatus={before}; approved preview expected {expected}."
                results.append(result)
                print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
                continue

        if not allow_finalize:
            result.status = "PREVIEW"
            result.proposed = {"expected_form_status": 3}
            result.detail = "Eligible: fresh formStatus=3."
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"👁️ {pen}: preview — eligible for Complete Data.", flush=True)
            continue

        if max_submissions > 0 and submissions >= max_submissions:
            result.status = "LIMIT_REACHED"
            result.detail = f"FINALIZE_MAX_SUBMISSIONS={max_submissions} reached."
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"🛑 {pen}: submission cap reached.", flush=True)
            break

        # ------------------------------------- re-read immediately before POST
        try:
            again = session.student_detail(sid)
            gate = again.get("formStatus")
            gate = int(gate) if gate is not None else None
        except Exception as exc:
            result.status = "UNCONFIRMED"
            result.detail = f"Pre-POST re-read failed: {type(exc).__name__}: {exc}"
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⚠️ {pen}: {result.detail}", flush=True)
            break

        if gate != 3:
            result.status = "SKIPPED_STATE_CHANGED"
            result.detail = f"State changed between reads: {before} -> {gate}."
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⏭️ {pen}: state changed to {gate} — not submitting.", flush=True)
            break

        # ------------------------------------------------------------ one POST
        post_error = None
        try:
            response = _submit_once(session, sid)
            try:
                body = response.json()
            except ValueError:
                body = {}
            if response.status_code != 200:
                result.status = "FAILED"
                result.detail = f"HTTP {response.status_code}"
                results.append(result)
                print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
                print(f"❌ {pen}: POST HTTP {response.status_code}.", flush=True)
                break
        except Exception as exc:
            post_error = exc
            print(
                f"⚠️ {pen}: POST transport error ({type(exc).__name__}). "
                "Not retrying; performing fresh read-back…",
                flush=True,
            )

        submissions += 1

        # --------------------------------------------------------- read-back
        time.sleep(2)
        try:
            verify = session.student_detail(sid)
            after = verify.get("formStatus")
            after = int(after) if after is not None else None
        except Exception as exc:
            result.status = "UNCONFIRMED"
            result.detail = f"Read-back failed: {type(exc).__name__}: {exc}"
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⚠️ {pen}: could not confirm — check the portal.", flush=True)
            break

        if after == 6:
            result.status = (
                "SUCCESS_CONFIRMED_AFTER_POST_ERROR" if post_error
                else "SUCCESS_CONFIRMED"
            )
            result.detail = (
                "Complete Data accepted and fresh read confirms formStatus=6."
                + (" (POST reported a transport error.)" if post_error else "")
            )
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"✅ {pen}: finalized and confirmed.", flush=True)
        else:
            result.status = "UNCONFIRMED"
            result.detail = (
                f"POST accepted but fresh read shows formStatus={after}, "
                "not 6. Manual review required."
            )
            results.append(result)
            print(f"📋 FINALIZE_RESULT status={result.status} pen={result.pen} name={result.name} detail={result.detail}", flush=True)
            print(f"⚠️ {pen}: {result.detail}", flush=True)
            break

    success = sum(1 for r in results if r.confirmed)
    preview = sum(1 for r in results if r.status == "PREVIEW")
    skipped = sum(1 for r in results if r.status.startswith("SKIPPED"))
    other = len(results) - success - preview - skipped
    failed = sum(1 for r in results if r.status == "FAILED")
    unconfirmed = sum(1 for r in results if r.status == "UNCONFIRMED")
    limit_reached = sum(1 for r in results if r.status == "LIMIT_REACHED")
    state_changed = sum(1 for r in results if r.status == "SKIPPED_STATE_CHANGED")
    read_errors = sum(1 for r in results if r.status == "READ_ERROR")
    print(
        f"📋 FINALIZE outcome: confirmed={success} | skipped={skipped} | state-changed={state_changed} | "
        f"limit-reached={limit_reached} | failed={failed} | unconfirmed={unconfirmed} | read-errors={read_errors}", flush=True
    )

    print("\n" + "━" * 30)
    print(f"✅ Finalized + confirmed : {success}")
    if preview:
        print(f"👁️  Preview only         : {preview}")
    if skipped:
        print(f"⏭️  Skipped              : {skipped}")
    if other:
        print(f"⚠️  Other                : {other}")
    print("━" * 30)

    return results
