# Colab runbook — v2.7.3 baseline

## Start

1. Open `UDISE_Automation_v2.7.3_2026-09-23.ipynb`.
2. Log into UDISE+ normally in the browser. User handles OTP/CAPTCHA.
3. Run **Setup environment**.
4. Run **Login**. It authenticates the Colab session, detects the school and fetches the roster.
5. Choose only the module needed.

## General Profile AUTO

1. Choose `AUTO_GP_CLASS`.
2. Choose `AUTO_GP_RUN_MODE`:
   - All students, or
   - First N students.
3. For First N, set `AUTO_GP_ROW_LIMIT`.
4. Keep `ALLOW_AUTO_GP_SUBMIT=False` for preview.
5. Review preview/result rows.
6. For the first live test, enable submission and keep `AUTO_GP_MAX_SUBMISSIONS=1`.
7. Treat only fresh read-back confirmation as a saved result.

AUTO GP fills only approved blank defaults. Existing values stay unchanged. Current CWSN=Yes is a hard skip/manual-review case.

## Manual GP Excel

Use only when AUTO GP is insufficient. Open the Manual GP fallback and use Reference Data → Download → Upload → Check → Submit.

## Enrollment

Enrollment remains IX/X. Export, edit, validate, review, then explicitly enable the write. Start with one record.

## Facility

Choose the desired class scope, export, edit, check, then explicitly enable submit. Use actual measurements. XI/XII selector support is present but XI/XII writes are not yet live-verified.

## Completion Overview

Choose class/group and run the overview. Only `formStatus=3` is considered Ready to Complete. Status 6 is already complete.

## Finalize

1. Prefer AUTO after a fresh Completion Overview.
2. Keep `ALLOW_FINALIZE=False` for preview.
3. For first live write, set `FINALIZE_MAX_SUBMISSIONS=1`.
4. Finalize performs fresh status checks before POST.
5. Never replay a timed-out POST blindly.
6. Success requires fresh `formStatus=6`.

## Common interpretation

| Result | Meaning |
| --- | --- |
| Preview / Checked / Ready | Read/validation succeeded; no write implied |
| No change | Current saved values already satisfy the workflow |
| Manual review / Blocked | No automatic write should occur |
| HTTP 200 + application error | Portal did not confirm success |
| POST ambiguity | Read back before any decision; do not replay |
| Saved / Success confirmed | Fresh portal state confirms persistence |
