# Architecture

The maintained artifact is a Colab notebook with the safe flow:

```text
Setup -> Login -> detect school/roster -> choose module
-> fresh reads -> preview/validate -> explicitly enable write
-> one-shot POST where authorized -> fresh read-back
```

Primary modules:
- General Profile
- Enrollment Profile
- Facility Profile
- Completion Overview
- Finalize / Complete Data

Write safety is based on explicit toggles, fresh pre-write state, no blind POST retries, and fresh post-write confirmation.
