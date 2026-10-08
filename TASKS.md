# Tasks

## Active
- [ ] Keep v2.7.3 as the maintained baseline until a reviewed successor is promoted.
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
