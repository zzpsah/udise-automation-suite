# EP Batch Rejection Handling — Fix Record

**Status:** Code merged to `main`; automated regression checks passed. Oracle runtime activation is **not yet verified**.

## Summary

The EP (Enrollment Profile) save batch previously stopped after a definitive student-level rejection. This meant a selected save limit of five could result in only one attempted save even when later students in the approved plan were eligible to be processed.

The fix allows the batch to continue after definitive student-level portal rejections, while preserving the safety stop for uncertain outcomes.

## Behavior after the fix

- **ER1010 / GP prerequisite:** A response indicating that the General Profile must be saved first is classified as `SKIPPED_GP_REQUIRED`. The result explains the prerequisite and the batch continues to the next student.
- **Other definitive portal rejections:** The student is recorded as `FAILED`; the batch continues to the next student.
- **Successful-save limit:** The configured limit counts successful submissions, not previews or rejected students. A rejection does not consume a successful-save slot.
- **Uncertain outcomes:** Transport failures or outcomes where the system cannot safely determine whether a save occurred remain safety stops; the runner must not blindly continue or retry an ambiguous write.
- **Precheck:** If the student-detail status indicates GP is not saved, the runner skips that student as GP-required without sending the EP save request. If the precheck itself cannot be read, the result is marked for manual review and no save POST is sent.
- **Results UI:** `SKIPPED_GP_REQUIRED` is shown as **GP required**.
- **Completion message:** The UI says the run finished and directs the operator to review saved, skipped/already-filled, failed, and other counts instead of implying every student succeeded.

## Regression coverage

The regression tests cover:
1. An ER1010 rejection followed by five successful saves with `max_submissions=5`: the rejected student is classified GP-required and does not consume one of the five successful-save slots.
2. The regular EP save path continues after a definitive student-level rejection.
3. The result table displays the GP-required label.

The GitHub Actions workflow **EP batch regression** runs Python syntax compilation and the targeted EP regression/result-table tests.

- Successful workflow run: https://github.com/zzpsah/udise-automation-suite/actions/runs/38064111045
- Pull request for the implementation: https://github.com/zzpsah/udise-automation-suite/pull/2
- Implementation merge commit: `46e34ffe3b112483a3227d4ffed6e62518a2d2bb`

## Deployment and operational status

### Vercel

Vercel reported a production-target deployment in **Ready** state for implementation commit `46e34ffe3b112483a3227d4ffed6e62518a2d2bb`. This confirms deployment metadata only; a live browser/UI smoke test and the public production alias were not verified as part of this fix.

Production UI: https://udise-auto.vercel.app/

### Oracle VPS runner — verification still required

The actual EP runner executes on the Oracle VPS, separately from the Vercel UI. At the time this document was written, remote command execution was unavailable, so it has **not** been confirmed that the Oracle checkout/service has loaded the merged code. Do not describe the fix as live on Oracle until the service is updated and verified.

Documented Oracle checkout: `/home/prashant/projects/udise-automation-suite`

Documented control API service: `udise-control-api.service`

After the repository update has been promoted to the Oracle checkout, the operator should:

1. Check the checkout is at the intended `main` commit and inspect any local changes before updating.
2. Compile the changed Python modules and tests.
3. Restart the user services using the deployment procedure in [DEPLOYMENT.md](DEPLOYMENT.md), if needed.
4. Confirm `udise-control-api.service` is active and inspect its logs for startup errors.
5. Run a controlled EP save from the UI and review per-student statuses and final counts before increasing the batch size.

The existing Oracle promotion timer may update the checkout automatically, but this was not verified for this commit. Do not assume it has promoted the change.

## Data-safety notes

- No live student records were modified during the code/CI validation described above.
- A GP-required result is an individual student's portal response/status; it does not prove that the entire class's GP workflow failed. Investigate that student's state rather than rerunning GP for every student by default.
- Preview coverage and save execution are distinct. The selected save limit governs successful save submissions, not how many students the preview may inspect.
