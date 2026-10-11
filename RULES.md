# Development Rules

1. Start from the maintained baseline notebook unless a successor has been explicitly reviewed and promoted.
2. Follow: READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION.
3. Prefer preview/read-only behavior first.
4. Keep write toggles off by default.
5. Use bounded retries for safe GET/read operations only.
6. Never blindly retry POST/write requests after timeout or connection loss; perform fresh read-back first.
7. Do not call HTTP 200 a successful save without application-level confirmation or fresh read-back.
8. Preserve existing saved values unless the workflow explicitly authorizes an update.
9. CWSN=Yes is a hard AUTO GP skip/manual-review case.
10. Do not extend IX/X Enrollment rules to XI/XII without live form/API discovery.
11. Never invent measurements, identifiers, profile values, or portal contracts.
12. Never commit cookies, passwords, OTPs, CAPTCHA material, student exports, screenshots, completed workbooks, raw API responses with student data, or secrets.
13. First live write tests should be tightly bounded and followed by fresh read-back.
14. Update README, AI handoff, tasks, decisions, tests, and memory after material changes.

10. **Indian nationality (natIndYN):** blank defaults to Yes (`1`); explicit No (`2`) is corrected to Yes (`1`) because the school confirms all enrolled students are Indian nationals. Other saved values are not silently overwritten.

11. **Human-readable activity output:** For skipped students, display `SKIPPED`, the actual skip reason in plain language, and an action only when relevant. Remove generic messages such as “Preview if you expected a change.” Never claim “No change required” when the real reason is that the student is not in the approved plan. Do not imply a write occurred if no POST/write was sent.
12. **Keep status, reason, and action distinct:** Status describes the outcome; reason explains why; action describes what the runner did or did not do. Use the real per-student outcome and preserve approved-plan and no-blind-write safeguards.
13. **Production claims require evidence:** A pushed branch or open PR is not a production deployment. Verify merge commit, deployed version, service health, and relevant tests before marking a fix live.
