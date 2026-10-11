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

## 2026-10-10 — GP/EP outcomes and nationality correction
- EP batch runner continues after definitive per-student rejection; rejected students receive explicit skipped outcomes and do not consume the successful-save cap. Blind POST retries remain prohibited.
- EP result reporting distinguishes prerequisite failures, approved-plan exclusions, and save-limit outcomes.
- GP incomplete records with no eligible blank AUTO-GP fields are routed to manual review rather than sending an empty write.
- GP results and activity tables include PEN/name identity and normalized stored GP result records.
- PR #10 (`fix/gp-nationality-clean`) adds the school-confirmed `natIndYN` No-to-Yes correction and tests. The branch is pushed; PR remains open at this checkpoint, so it is not production/deployed.
- Operator approved simpler activity wording: show `SKIPPED`, the real reason, and relevant action only; remove generic “Preview if you expected a change” text. This UX requirement is documented for implementation.
