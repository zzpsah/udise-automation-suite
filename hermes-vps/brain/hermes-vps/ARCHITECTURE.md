# Hermes VPS Runner — Architecture

## Shape

```
hermes-vps/
  udise_vps/        the package — all portal logic
    cli.py            argument parsing and command dispatch
    session.py        HTTP session, headers, read/write primitives
    constants.py      enums, class labels, facility tables
    students.py       roster export
    completion.py     completion overview workbook
    general_profile.py GP read + (unexercised) write
    ep.py             Enrolment Profile — the bulk of the logic
    subjects.py       subject codes, language plans, exam-result enums
    facility.py       Facility Profile
    finalize.py       Complete Data
    esk.py            eShikshaKosh OTR report (export or live fetch)
  tests/            offline suites, no network
  tools/            one-off operational scripts
  docs/flow.html    flow diagram
  brain/            this folder
```

## Layering

```
cli.py  →  module.run_*()  →  session  →  portal
```

Modules never build their own HTTP client. Everything goes through
`session.py`, which owns retries (reads only), timeouts, and the auth headers.
That keeps the "never blindly retry a POST" rule enforceable in one place.

## The session

- Auth is a cookie header supplied at runtime. **Nothing is persisted.**
- Reads retry with backoff. **Writes do not retry.**
- The portal is intermittently slow: use generous timeouts, and low concurrency.
  Eight parallel reads caused a read timeout in practice.

## The write contract

Every write path follows the same four steps:

1. **Fresh GET** of the record.
2. Compute **blank-only** updates. A saved value is never overwritten.
3. **One POST.**
4. **Fresh GET** and compare every written field.

A mismatch stops the batch. This is not a convention — it is the reason a
read-back bug was caught instead of silently corrupting records.

### Read-back normalisation

Sentinel values must be normalised or every legitimate write looks like a
failure:

| Field | We send | Portal stores |
|---|---|---|
| `classPY` (status 4) | `null` | `99` |
| `examResultPy` (status 4) | `null` | `0` |
| `examMarksPy` (status 4) | `null` | `999` |
| `attendancePy` (status 4) | `null` | `0` |

Optional subject slots report `None` where we send `0`; both must compare equal.

## General Profile

Per student:

1. **Fresh GP read.**
2. **CWSN = Yes skips the student entirely** for manual review. Never
   auto-filled.
3. **Blank-only diff** against `AUTO_GP_DEFAULTS`. A saved value is never
   included.
4. **Cross-field rules** (`apply_gp_rules`) adjust only a field that is blank or
   already in the update set:

   | Rule | Behaviour |
   |---|---|
   | 4.1.15 AAY | BPL = No → AAY = Not Applicable (9) |
   | 4.1.16 EWS | SC/ST/OBC → EWS = No (2) |
   | Blood group | code 0 is clamped to 9; the API rejects 0 |

   Mother Tongue (4.1.12) is a special case: a blank gets a **seeded random**
   pick between 42 (Hindi, the generic default) and 28 (Bhojpuri, the region
   option). Seeded per student so a re-run is reproducible.

5. **POST the full record**, then read-back every submitted field.

Verified against all 208 live records: **zero violations**, so the rules are
guards, not corrections.

## Enrolment Profile

The most complex module. Per student:

1. **Admission number** — priority chain: `kept_saved` → `eshikshakosh` →
   `roll_number` → `next_number`. UDISE stores the plain number (`12`), not
   `12/2026`. Generated values are zero-padded and continue after the class's
   highest.
2. **Languages** — by name against the catalogue. Muslim students
   (`minorityId=1`) get URDU + HIN (NLH); others HINDI + SANSKRIT.
3. **Mandatory subjects 3–6** — 401/402/404/612. The portal rejects a write
   that leaves these at 0.
4. **Exam result** — valid codes are **1, 3, 4 only**. An invalid code triggers
   the auto rule: set status 4 (`None/Not Studying`) and send `null` for the
   four dependent fields.
5. **Stream** — Class XI only. Resolved by name from the report; if no row
   matches, the operator is asked.

### Class XI/XII is blocked

The portal refuses the EP write:

```
Subject mapping for the selected Board and Class has not been configured yet.
The configuration is currently in progress and will be available shortly (1002)
```

A probe of all 62 Class XI records found **0** with any subject slot filled —
nothing to copy, nothing safe to guess. `EP_BLOCKED_CLASSES` makes it fail fast.

## Facility Profile

GET and POST routes differ by an `AY` segment — easy to get wrong:

```
GET  /p0/api/v2/students/facility/{sid}
POST /p0/api/v2/AY/students/facility/{sid}
```

Blank-fill rules and the sentinel traps are documented in `SECURITY.md` and
covered by tests. Values are **seeded per student** (`sha256(seed:pen)`) so a
re-run reproduces the same numbers and read-back can compare.

## Finalize

Only `formStatus == 3` is eligible. `6` means already complete. The module
re-reads immediately before the POST and stops if the state changed. Read-back
must show `6`.

Status codes: `1` draft · `2` submitted · `3` eligible · `6` complete.

## Cross-portal matching

Class and DOB are **soft signals, not filters**. Requiring the class to agree
lost all 62 Class XI matches. One hard rule: Aadhaar last-4 present on both
sides and different = different person. Everything else scores — see
`docs/flow.html` for the table.

## What is NOT here

- No database. State lives on the portal.
- No scheduler or daemon. It is a CLI, run when you want it.
- No credential storage. Cookies are runtime-only.
- No school-specific configuration in the package.
