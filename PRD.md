# Product Requirements Document

## Product
UDISE+ Automation Suite for UMV Tetahali.

## Goal
Provide a safe, reusable Colab workflow for authorized school-side UDISE+ work across General Profile (GP), Enrollment Profile (EP), Facility Profile (FP), completion review, and guarded finalization.

## Maintained baseline
`UDISE_Automation_v2.7.3_2026-09-23.ipynb`.

## Primary user
Authorized school operator using the notebook interactively.

## Core requirements
- Setup -> Login -> choose module -> preview/validate -> explicitly enable write -> fresh read-back.
- Credentials, cookies, OTP/CAPTCHA material, student exports, and raw private API data remain runtime-only.
- AUTO GP fills only approved blank fields and preserves existing nonblank values.
- Existing CWSN=Yes records are skipped for manual review.
- Completion logic uses the project-observed progression `0 -> 1 -> 2 -> 3 -> 6`; unknown values must not be invented.
- AUTO Finalize acts only on fresh status 3 records and confirms success only after fresh status 6 read-back.
- POST requests are never blindly retried after ambiguous transport failures.
- Facility XI/XII writes remain unverified until a reviewed live save proves them.
- Enrollment remains IX/X until XI/XII form/API discovery is complete.

## Next major feature
Upload-driven AUTO EP for Classes IX and XI using an e-ShikshaKosh export, with whole-file matching first and unresolved cases placed into an end-of-batch manual-review queue.

## Success criteria
A workflow is considered successful only when implementation state and evidence level are explicit: implemented, offline-tested, live-read, or live-save.

## Out of scope without new verification
- Assuming IX/X EP payloads apply to XI/XII.
- Inventing height/weight or official student data.
- Blind write retries.
- Treating HTTP 200 alone as persistence proof.
- Production deployment or bulk writes without explicit approval.
