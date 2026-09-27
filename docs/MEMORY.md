# Project Memory

## Current baseline
- Maintained notebook: `UDISE_Automation_v2.7.3_2026-09-23.ipynb`.
- AUTO GP is the preferred General Profile path.
- AUTO GP fills approved blank fields only.
- CWSN=Yes is skipped and flagged for manual review.
- Completion uses project-observed statuses 0/1/2/3/6.
- Finalize only writes fresh status 3 and requires fresh status 6 confirmation.
- Enrollment is currently IX/X.
- XI/XII Enrollment requires separate live discovery.
- Facility selector support extends through XII, but XI/XII live persistence is not yet verified.
- A real status 3 -> Complete Data -> status 6 transition has live evidence.

## Next major work
Upload-driven AUTO EP for IX and XI with strong matching, end-of-batch manual review, Admission Number prefill, XI stream selection, and one-record-first live-write discipline.

## Memory rule
Store only non-secret, non-student operational state. Never put credentials, cookies, tokens, OTPs, private student records, screenshots, or exported workbooks here.
