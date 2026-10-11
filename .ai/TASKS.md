# Tasks

## Active
- Implement upload-driven AUTO EP for IX and XI.
- Refresh eShikshaKosh credentials and rerun the Oracle Playwright export smoke test; record HTTP login result and report download separately from UDISE workflow evidence.
- Keep whole-file processing before manual review.
- Discover XI EP form/API contract before writes.
- Run reviewed live AUTO GP and Facility verification tests.
- Keep documentation synchronized with baseline changes.

## Guarded
- XI/XII Enrollment writes.
- XI/XII Facility writes.
- Bulk writes without explicit approval and fresh read-back.

## Completed
- Private Oracle/Tailscale GUI trial: production build, user service, Hermes
  VPS runner-reference metadata, secure session-link smoke check, and locked
  write-stage check.
- Professional English GUI aligned with the five-phase Hermes VPS flow, plus a
  synthetic preview-lifecycle and write-lock integration test.
- Class-first operation scope with unsupported workflows disabled.
- Desktop UDISE session bridge and corrected eShikshaKosh export interpreter.
- Preview-bound write approval for GP, EP, Facility, and Complete Data with a
  typed phrase, explicit read-back acknowledgement, bounded writes, and no
  automatic live execution during deployment.

## Deployment

- [x] Deploy the production Vercel control surface with encrypted Oracle/API
  configuration and verify login, capabilities, secure session-link creation,
  and the preview-bound write lock.

## 2026-10-10 update
- [x] EP batch continues after definitive per-student rejection; no blind POST retry; rejected records do not consume successful-save limit.
- [x] Improve EP result/prerequisite classifications and GP incomplete/manual-review outcomes.
- [x] Include student PEN/name in GP output and parse normalized GP results into activity results table.
- [x] Push PR #10 for school-confirmed nationality No-to-Yes correction; branch is pushed but PR remains open/not deployed.
- [ ] Replace developer-facing generic skip copy with concise `SKIPPED`, actual reason, and relevant action; test reason/action accuracy and preserve approved-plan safety.
- [ ] Verify merge + production deployed commit/health before claiming PR #10 is live.
