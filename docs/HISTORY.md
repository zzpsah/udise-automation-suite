# Project History

## 2026-09-23
- v2.7.3 established as maintained baseline.
- Preferred AUTO GP UI retained.
- Blank-only AUTO GP defaults documented.
- CWSN=Yes hard skip/manual-review rule documented.
- IX-XII class selectors exposed where supported.
- Completion model 0 -> 1 -> 2 -> 3 -> 6 documented from project observations.
- Guarded Finalize confirmed around fresh status 3 and status 6 read-back.

## 2026-09-27
- DevOS Vibe Coding baseline adopted.
- Project-specific PRD, rules, tasks, design, test, security, decisions, memory, commands, and history layer populated.
- AUTO EP remains the next major development direction.

## 2026-10-09 — UI/rules audit checkpoint
- Operator reported that expected height/weight rules were not visible in the P4/information rules view and that the Remember UDISE password control was not visible in the UI screenshot.
- Added explicit verification tasks; existing documentation is not treated as proof of deployed UI/runtime behavior.
- Reaffirmed the Facility blank-only rule and protection of existing Yes values.
- Recorded that the standalone eShikshaKosh downloader is a separate deployment at https://eshikakoshapp.vercel.app; its secure report backend/download flow remains pending.
- UDISE production remains https://udise-auto.vercel.app. Do not modify the separate udise-login-staging project.
