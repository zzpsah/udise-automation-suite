# Design

## Notebook UX principle
Normal flow should be simple and safe:

```text
Setup environment
-> Login
-> choose module
-> preview/validate
-> explicitly enable write
-> fresh read-back
```

AUTO workflows are the preferred path for approved, repetitive rules. Manual Excel workflows remain fallback paths for exceptions.

## General Profile
- AUTO GP controls should remain compact.
- Help/default details may remain collapsed.
- Preview must show KEEP vs AUTO values, change count, and skip/manual-review reasons.
- CWSN=Yes must be visibly flagged and untouched.

## Enrollment Profile
Planned order:
1. e-ShikshaKosh source upload
2. source normalization
3. automatic matching
4. AUTO EP preview
5. end-of-batch manual-review queue
6. final preview
7. guarded submit
8. existing Manual EP Excel fallback

## Completion / Finalize
Only fresh status 3 is eligible. Finalize must stop on unsafe, rejected, or unconfirmed outcomes rather than continuing optimistically.
