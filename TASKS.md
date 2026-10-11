# Tasks

## Active
- [ ] Keep v2.7.3 as the maintained baseline until a reviewed successor is promoted.
- [ ] Audit P4/information rules source-of-truth against the operator report that expected rules were not visible in the runtime rules view.
- [ ] Verify Facility Profile rule/help output exposes the protected existing-Yes behavior and correct IX–X gender-specific blank measurement ranges.
- [ ] Verify the Remember UDISE password on this Chrome profile control is actually present in the deployed login UI; test supported/unsupported Credential Management API behavior without persisting credentials server-side.
- [ ] Implement upload-driven AUTO EP architecture for Classes IX and XI.
- [ ] Build source-normalization and matching using DOB, Aadhaar last 4, normalized student/father names, and optional mother-name support.
- [ ] Process the full source file before presenting a serial-numbered manual-review queue.
- [ ] Prefill Admission Number only when UDISE is blank and the match is strong.
- [ ] Preserve conflicting nonblank Admission Number for manual review.
- [ ] Support XI Science / Arts / Commerce as a user-selected stream context.
- [ ] Discover the XI EP live form/API contract before any XI write.
- [ ] Run a one-record reviewed live AUTO GP write test on the maintained baseline.
- [ ] Live-verify corrected Facility persistence before claiming it verified.
- [x] Document protected existing Facility Yes values and current IX/X blank measurement ranges (140–160 cm / 38–55 kg boys; 135–155 cm / 34–50 kg girls).
- [x] Document browser-profile UDISE credential option and its Credential Management API boundary.
- [ ] Live-verify XI/XII Facility writes separately.

## Ongoing
- [ ] Keep evidence labels explicit: implemented / offline-tested / live-read / live-save.
- [ ] Keep write toggles disabled by default.
- [ ] Keep documentation synchronized with every promoted baseline.
- [ ] Keep private student data and credentials out of Git.

## Hermes/Vercel control plane

- [x] Mirror udise-automation-suite on Oracle.
- [x] Add read-only Oracle control API for roster/completion jobs.
- [x] Add dynamic capabilities for class/stage UI generation.
- [x] Add secure runtime UDISE session-entry flow.
- [x] Add Vercel UI source and production-build verification.
- [x] Add Hermes messaging skill/client.
- [x] Add test-gated future GitHub promotion timer.
- [x] Deploy `zzpsah/udise-automation-suite` with encrypted environment values;
      production is `https://udise-auto.vercel.app`. The requested
      `udise.vercel.app` alias is already owned by another Vercel deployment and
      remains a manual operator handoff.
- [x] Add explicit preview/approval flows with typed confirmation, acknowledgement,
      a per-run write cap, one approval per preview, and fresh read-back.

## Project separation / operator constraints

- [x] Document UDISE production and standalone eShikshaKosh deployment as separate projects.
- [x] Record that `udise-login-staging` must remain untouched.
- [ ] Resume UDISE runtime/UI audit only when UDISE work is resumed by the operator.

## October 10, 2026 — latest work
- [x] Continue EP batch after definitive student-level rejection; report skipped reason and do not count rejection against successful-save cap.
- [x] Expose EP prerequisite/save outcomes and correct save-limit vs approved-plan classifications.
- [x] Report GP incomplete/manual-review when no eligible blank AUTO-GP fields exist; do not send an empty POST.
- [x] Include PEN/name in GP result lines and normalize stored GP results into the activity table.
- [x] Push PR #10 with school-confirmed Indian nationality correction (`natIndYN` No -> Yes) and regression tests; PR is open and not deployed yet.
- [ ] Simplify activity wording: `SKIPPED` + actual plain-language reason + relevant action only; remove “Preview if you expected a change” and similar generic messages. Add/adjust tests for each real skip path.
- [ ] Merge PR #10 and verify the actual production deployed commit and health before reporting the nationality fix as live.
