# Commands and Runbook

## Open maintained notebook
Use the Colab link from README for `UDISE_Automation_v2.7.3_2026-09-23.ipynb`.

## Safe execution sequence
```text
Setup environment
-> Login
-> choose module
-> preview/validate
-> explicitly enable write
-> fresh read-back
```

## Evidence labels
```text
IMPLEMENTED
OFFLINE_TESTED
LIVE_READ
LIVE_SAVE
```

Do not promote a result to LIVE_SAVE without fresh persisted read-back.

## Development loop
```text
READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION
```
