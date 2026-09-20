# Submission troubleshooting build v1.1.3 — 2026-09-20

The reported log ended at the third-row submission. That line alone did not establish whether the request was still active, interrupted or rejected. Earlier replies asserting it was definitely still running were not supported by a live runtime observation.

## Corrected defects

- POST and GET waits print elapsed-time heartbeats every ten seconds.
- Each response logs its HTTP status. POST errors are retained through failed verification requests.
- Missing/null/non-dictionary error bodies no longer obscure the original response.
- Read-back uses a 15-second connection timeout and a 60-second read timeout per attempt; POST keeps a 300-second read timeout.
- Before POST, the result workbook includes the pending row. Each completed row checkpoints the file, so a later failure does not hide earlier results. An interrupted pending row requires a fresh portal read before resubmission.
- Results include the build and a timestamped filename. Unavailable verification is UNCONFIRMED and stops the batch.

## Verification and limits

`python tools/test_submission.py` exercises the actual submission cell against a mocked transport using synthetic records. Cases cover two skipped records then successful third submission, null error body with mismatch, timeout with successful read-back, and rejection followed by failed read-backs. Each asserts exactly one POST.

The compact payload and subject mappings are unchanged from v1.1.2. This release fixes diagnostics and failure handling, not an identified third-student server validation rule. No authenticated portal test was performed for this release. Do not claim all submissions are fixed from local tests.

Open the new notebook URL and run the required setup, authentication, roster/rules and validation cells. Confirm the submission cell prints `v1.1.3`. After an earlier ambiguous request, use a fresh read/export to check saved state first. Preserve the final POST RESULT and VERIFY output for diagnosis.
