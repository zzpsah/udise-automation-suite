# Architecture

## Current baseline

The maintained operational artifact is:

`UDISE_Automation_v2.7.3_2026-09-23.ipynb`

The repository keeps older notebooks as rollback/history, but v2.7.3 is the current baseline.

## Runtime flow

```
Manual UDISE browser login
        |
active session information -> private Colab runtime
        |
Setup -> Login -> detect school -> fetch roster
        |
        +-> General Profile AUTO (preferred)
        |      -> choose class/run scope
        |      -> fresh GP reads
        |      -> blank-only defaults
        |      -> preview
        |      -> optional gated POST
        |      -> fresh read-back
        |
        +-> Manual GP Excel fallback
        |
        +-> Enrollment IX/X
        |
        +-> Facility Profile
        |
        +-> Completion Overview
               -> formStatus grouping
               -> status 3 ready list
               -> guarded Finalize
               -> fresh status 6 confirmation
```

## Write boundary

All write workflows must be explicitly enabled. Read-only GETs may use bounded retries. POST requests are never blindly retried because the portal may have received a request even when the client saw a timeout.

A transport HTTP 200 is not sufficient proof of persistence. A save is confirmed only when the application response and/or a fresh read-back establishes the expected stored state.

## General Profile AUTO rules

AUTO GP modifies only the approved fields that are blank. Existing values are kept. A current CWSN=Yes record is skipped in full and sent to manual review.

AUTO GP class scope supports IX–XII combinations; run scope supports All students or First N students.

## Status-driven completion

The observed project status progression is `0 → 1 → 2 → 3 → 6`. Only fresh status 3 is eligible for Complete Data. Status 6 means already complete.

This mapping is empirical project evidence, not an official API contract.

## External destinations

The notebook communicates with the authenticated UDISE+ portal. It has no telemetry destination. Credentials remain runtime-only.

## Versioning rule

Promote one reviewed notebook as the baseline. Record the change reason, evidence type, remaining unknowns, and update README + `docs/AI_HANDOFF.md`.
