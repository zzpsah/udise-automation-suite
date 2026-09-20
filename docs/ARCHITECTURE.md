# Architecture

## One-notebook design

`UDISE_Automation_Enhanced.ipynb` is the sole operational artifact. It contains setup, authentication, school detection, roster fetch, General Profile workflow, and Class IX/X Enrollment workflow in ordered sections.

```
Manual UDISE browser login
        |
Cookie header in private Colab runtime
        |
Session validation -> school URL -> school ID
        |
Roster + live reference rules -> Excel export -> local validation
        |
Optional guarded one-record update -> response/read-back result
```

The notebook has no telemetry or Apps Script call. Its only external workflow destination is the UDISE+ portal used by the signed-in school account.

## Submission boundary

Submission toggles default to `False`. Enrollment starts with `ENROLMENT_MAX_SUBMISSIONS = 1`.

GET requests may retry after timeout. POST requests never retry automatically, because a timeout may still mean the portal received the record. After a failed or ambiguous response, the notebook fetches the record again and reports `SUCCESS_CONFIRMED_BY_RESPONSE`, `SUCCESS_CONFIRMED_BY_READBACK`, or `FAILED`.

## Versioning

Commit every intended notebook change with: the affected section, reason, evidence (syntax, local, or live read-only test), and remaining unknowns.
