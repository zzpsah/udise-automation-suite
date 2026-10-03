# Hermes VPS Runner — Current State

Last verified: **2026-10-03**. Portal **v3.2.0**.

## Evidence summary

| Component | Command | Status |
|---|---|---|
| Roster export | `students` | `LIVE_READ` — 208 students |
| Completion overview | `completion` | `LIVE_READ` |
| General Profile | `gp` | `LIVE_READ` (preview only) |
| Enrolment Profile | `ep` | `LIVE_SAVE` — Class IX 33/33 |
| Facility Profile | `facility` | `LIVE_SAVE` — Class IX 33/33 |
| Finalize | `finalize` | `LIVE_SAVE` — Class IX 33/33 |
| eShikshaKosh fetch | `esk.export_report` | `LIVE_READ` — 220 rows |

## Per-class state (school used for verification)

| Class | Students | `formStatus` | Complete |
|---|---|---|---|
| IX | 33 | all 6 | **33/33** |
| X | 38 | 1×21, 2×13, 6×4 | 4/38 |
| XI | 62 | all 1 | 0 — **EP blocked by the portal** |
| XII | 75 | all 1 | 0 — **EP blocked by the portal** |

## How the Class IX result was reached

1. **EP** — 33 students. Admission numbers resolved from the eShikshaKosh
   report; languages and subjects filled blank-only; two students whose exam
   result was invalid were set to `None/Not Studying` (status 4).
2. **FP** — 33 students. Height, weight, distance, parent education, and the
   Yes/No flags filled blank-only.
3. **Finalize** — 28 eligible (`formStatus=3`) written one at a time; 5 were
   already `6`.

Every write was confirmed by fresh read-back. The whole class was then
re-verified with a per-student read: **33/33 at `formStatus=6`**.

## Open work

### Class X — next

- 3 admission numbers missing
- **21 missing subject sets.** An earlier scan reported these as complete
  because it only checked admission number and medium, never the subject slots.
- FP for 38 students
- Then finalize the 34 at status 1 or 2

### Class XI/XII — blocked

EP write is refused by the portal (error `1002`, no subject mapping configured
for this Board and Class). Admission numbers and streams for Class XI resolve
62/62 and are waiting. Re-check periodically; do not retry in a loop.

### General Profile

Read path works. The write path has never been exercised live from this runner.
The notebook implements AUTO GP with a CWSN=Yes skip rule — port it only after
live discovery, not from the notebook's tables.

## Verification commands

```bash
cd hermes-vps
./run_tests.sh
```

```bash
# live, read-only
export UDISE_COOKIE_HEADER='...'
python3 -m udise_vps.cli completion --school <id> --class IX
```
