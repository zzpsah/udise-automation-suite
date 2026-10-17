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
- GP manual review is independent of eligible approved-plan saves.
- GP individual Skip and Skip All defer candidates without writing their data.
- GP skip/queue lifecycle is covered for Class IX, X, XI, and XII.
- GP grouped class scope is preserved from selector through job metadata; no implicit fallback to IX.
- GP result workbook and activity events retain student identity, status, and actionable reason.
- Manual review appears after the automatic save child reaches a terminal state; skipped students do not inflate the eligible save count.
