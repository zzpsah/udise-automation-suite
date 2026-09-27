# Test Plan

## Static checks
- Notebook JSON remains valid.
- Modified Python cells parse successfully.
- Required variables/functions are defined before use.

## Read-only tests
- Login/session detection.
- School detection and roster fetch.
- GP/EP/FP fresh reads.
- Completion status grouping.
- Matching preview with representative source rows.

## Write tests
- Preview mode first.
- One reviewed record for first live test.
- Fresh read immediately before write.
- Single POST attempt.
- Fresh read-back after write.
- Record result as live-save only when expected state persists.

## Ambiguous failures
If a write may have been transmitted but the client saw timeout/connection loss:
1. do not replay automatically;
2. perform fresh read-back;
3. confirm persisted state if present;
4. otherwise stop for manual review.

## Regression focus
- Existing nonblank values preserved.
- CWSN=Yes skipped.
- status 6 never re-finalized.
- status 0/1/2/unknown never finalized.
- Enrollment IX/X behavior unchanged while XI work is added.
