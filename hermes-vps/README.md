# UDISE+ SDMS — Hermes Version (Linux/VPS runner)

A Linux/VPS command-line runner for UDISE+ SDMS school automation, ported from
the Colab notebook `UDISE_Automation_v2.8.0_2026-10-03.ipynb`.

**Generic by design** — works for any school. No school ID, name, or code is
hardcoded anywhere in `udise_vps/`.

---

## Evidence levels used in this document

| Label | Meaning |
|---|---|
| `IMPLEMENTED` | Code exists |
| `OFFLINE_TESTED` | Mocked/static tests only |
| `LIVE_READ` | Authenticated GET observed against the real portal |
| `LIVE_SAVE` | Reviewed write followed by a fresh matching read-back |

Never treat one as another. `HTTP 200` alone is **not** proof of a save.

---

## 1. Current status

| Component | Command | Status |
|---|---|---|
| Student roster export | `students` | `LIVE_READ` — 208 students |
| Full read snapshot | `snapshot` | `OFFLINE_TESTED` — combined stage workbook |
| Completion Overview | `completion` | `LIVE_READ` — 33 Class IX read |
| General Profile | `gp` | **`LIVE_SAVE`** — payload fixed and verified |
| **Enrollment Profile** | `ep` | **`LIVE_SAVE` — Class IX 33/33 complete** |
| **Facility Profile** | `facility` | **`LIVE_SAVE` — Class IX 33/33 complete** |
| **Finalize / Complete Data** | `finalize` | **`LIVE_SAVE` — Class IX 33/33 `formStatus=6`** |

**Test suite:** run `./run_tests.sh` for the current count. Every suite is
offline — no network, no credentials. The script discovers `tests/test_*.py`,
so a new suite cannot be silently skipped.
Run with `./run_tests.sh`.

### Per-class state (3 October 2026)

| Class | Students | `formStatus` | Complete |
|---|---|---|---|
| IX | 33 | all 6 | **33/33** |
| X | 38 | 1×21, 2×13, 6×4 | 4/38 |
| XI | 62 | all 1 | 0 — **EP blocked by the portal** |
| XII | 75 | all 1 | 0 — **EP blocked by the portal** |

Class X still needs 3 admission numbers, **21 missing subject sets**, FP for 38,
then finalize.

### Class XI/XII Enrollment is blocked server-side

The portal refuses the write outright:

```
Subject mapping for the selected Board and Class has not been configured yet.
The configuration is currently in progress and will be available shortly (1002)
```

Not a client bug. A probe of all 62 Class XI records found **0** with any
subject slot filled — nothing to copy, nothing safe to guess. Admission numbers
and streams for XI resolve fine (62/62) and will apply once the mapping exists.
Fail fast; do not retry in a loop.

---

## 1a. Getting the eShikshaKosh OTR report

The report supplies the Admission No. that UDISE leaves blank. Two sources, in
priority order:

```bash
# 1. An export you provide — no credentials needed
udise-vps ep --school 2497128 --class IX --report Student_OTR_Report.xlsx

# 2. Let it log in and fetch the report itself
udise-vps ep --school 2497128 --class IX --fetch-report --year 2026-27
```

Credentials resolve from `ESHIKSHAKOSH_UDISE` / `ESHIKSHAKOSH_PASSWORD`, else
`eshikshakosh.conf`. See `udise_vps/esk.py`.

### Admission-number priority

1. `kept_saved` — UDISE already has one; never overwritten
2. `eshikshakosh` — matched a report row
3. `roll_number` — no report match, roster has a roll number
4. `next_number` — generated, continuing after the class's highest

### Matching a student across the two portals

Class and DOB are **not** hard filters — the portals disagree about both often
enough that requiring them loses real matches. Requiring the class to agree
lost all 62 Class XI matches.

One hard rule: **Aadhaar last-4 present on both sides and different = different
person.** Everything else scores:

| Signal | Points |
|---|---|
| Aadhaar last-4 agrees | +5 |
| Name exact | +3 |
| Father exact | +2 |
| Name partial (shared token ≥ 4 chars) | +1 |
| Father partial | +1 |
| DOB agrees | +1 |
| DOB conflicts, no Aadhaar | −1 |

Same-class breaks ties only.

---

## 1b. Streams — the two portals number them oppositely

| Stream | eShikshaKosh | UDISE `academicStream` |
|---|---|---|
| Arts | 1 | **2** |
| Science | 2 | **1** |
| Commerce | 3 | 3 |

Translate **by name only**. Reusing a raw code from the report silently swaps
Arts and Science. The report's `Stream` column and its admission suffix
(`35/2026/SCI`, `19/ARTS/2026`) agree, giving two confirmations.

Class XI streams resolve from the report; if a student has no report row the
operator is asked (`--ask-stream`), or a value is forced (`--stream Science`).

---

## 1c. Facility Profile — sentinel values

The easy thing to get wrong:

| Field | Unset is reported as |
|---|---|
| `heightInCm`, `weightInKg` | **numeric `0`** (not null) |
| `nccYn`, `nssYn`, `scoutsYn`, `olympdsNlc` | **`9`** (never answered) |
| `distanceFrmSchool`, `parentEducation` | `0` or `9` |

A blank check testing only for `''` returns False for `0`, so **blank height and
weight are silently skipped for the whole roster**. Likewise `9` must read as
unanswered, not as a saved answer.

Blank-fill rules:

| Field | Rule |
|---|---|
| height (4.3.x) | whole number 146–160 cm |
| weight | whole number 42–52 kg |
| distance (4.3.6) | **randomly 2 (1–3 km) or 3 (3–5 km)** per student |
| parent education | 3 (Secondary or Equivalent) |
| blank Yes/No | 2 (No) |

Values are **seeded per student** (`sha256(seed:pen)`) so a re-run produces the
same numbers and read-back can compare. Plain `random.randint` makes every
re-run look like a mismatch.

---

## 1d. General Profile — blank-fill rules

GP was already complete for all 208 students when checked, so nothing was
written. The rules are implemented and tested anyway.

**Blank-only.** A value the portal already holds is never overwritten. Verified
live: 205 students carry `bloodGroup=9` (Under Investigation) and 3 carry real
groups (A+, B+, B-) — the three are left alone.

| Field | Blank becomes |
|---|---|
| Blood Group | **Under Investigation** (code 9) |
| 4.1.14 BPL beneficiary | No (2) |
| 4.1.16 EWS / Disadvantaged | No (2) |
| 4.1.17 CWSN | No (2) |
| 4.1.18 Indian National | **Yes** (1) |
| 4.1.19 Out-of-School-Child | No (2) |
| Mother Tongue (4.1.12) | randomised: **42 HINDI - Hindi** or **28 HINDI - Bhojpuri** |

### Cross-field rules

The portal pairs these fields. A rule fires **only on a field that is blank or
already being written** — a saved value is left alone, same as everywhere else.

| Rule | Behaviour |
|---|---|
| 4.1.15 AAY | BPL = No → AAY = **Not Applicable** (9). A student who is not BPL cannot be an AAY beneficiary. |
| 4.1.16 EWS | Social category SC / ST / OBC → EWS = **No** (2). A reserved-category student cannot also claim EWS. |
| Blood group | Code 0 ("Unknown") is offered by the UI but **rejected by the API**, so it is clamped to 9. |

**CWSN = Yes skips the student entirely** for manual review — never auto-filled.

### The GP write payload must be complete

The portal rejects a payload that omits the record's identity block with an
`INTERNAL_SERVER_ERROR` — **even when every value is unchanged**.

| Payload | Result |
|---|---|
| 14 fields (dropdowns only) | `INTERNAL_SERVER_ERROR` |
| **34 fields** (identity + contact + dropdowns) | **`status: true`** |

The required block is `classId`, `sectionId`, `studentId`, `schoolId`,
`gender`, `dob`, `motherName`, `fatherName`, `guardianName`, `address`,
`pincode`, `primaryMobile`, `email`, `studentCodeState`, and the
`uuidUpdateYN` / `uuid` / `nameAsUuid` trio.

Verified live on 4 students: accepted, and a fresh read-back confirmed every
value preserved.

**Mother Tongue (4.1.12)** — a blank gets a randomised pick between the generic
default `42 - HINDI - Hindi` and the region option `28 - HINDI - Bhojpuri`.
Values are seeded per student (`sha256(seed:pen)`) so a re-run reproduces the
same choice. Live data shows the school already uses 28 (189 students), 42 (9),
144 - Urdu (3) and 20 - Awadh (7) — **all four are left untouched.**

These rules were verified against all 208 live records: **zero violations**, so
they are guards, not corrections.

---

## 1e. Which file does what

| Path | Responsibility |
|---|---|
| `udise_vps/cli.py` | Argument parsing and command dispatch |
| `udise_vps/session.py` | HTTP session, auth headers, read/write primitives. Reads retry; writes do not |
| `udise_vps/constants.py` | Enums, class labels, facility tables, GP defaults and rule values |
| `udise_vps/general_profile.py` | **GP** — blank fill, CWSN skip, AAY/EWS rules, blood-group clamp |
| `udise_vps/ep.py` | **Enrolment Profile** — admission numbering, cross-portal matching, languages, subjects, streams |
| `udise_vps/subjects.py` | Subject codes, language plans, exam-result enums, status-4 null rule |
| `udise_vps/facility.py` | **Facility Profile** — blank fill, 0/9 sentinels, seeded generation |
| `udise_vps/finalize.py` | **Complete Data** — status gating, pre-POST re-read, read-back |
| `udise_vps/esk.py` | eShikshaKosh OTR report — your export, or a live fetch |
| `udise_vps/students.py` | Roster export |
| `udise_vps/completion.py` | Completion overview workbook |
| `udise_vps/snapshot.py` | **Read-only stage-wise workbook** — Students, GP, EP, Facility, Completion and Issues sheets. Masks Aadhaar-like values; never writes secret-like fields |
| `udise_vps/preview_report.py` | Excel report for a read-only preview of a write stage |
| `tests/` | Offline suites — run `./run_tests.sh` for the count. No network |
| `tools/` | One-off operational scripts |
| `brain/` | Working context — handoff, architecture, decisions, security |

---

## 1f. Operational tools (`tools/`)

Run deliberately, not routinely. Each names its scope and reports before acting.

| Tool | Purpose |
|---|---|
| `write_batch.py` | Bounded EP writer for N students |
| `write_facility.py` | Facility writer for a class |
| `finalize_class.py` | Complete Data for a class. Dry run unless `FIN_ALLOW=1` |
| `preview_rules.py` | Show which students the blank-fill rules would touch. Read-only |
| `preview_batch.py` | Preview EP changes before writing. Read-only |
| `probe_xi_codes.py` | Probe which subject codes a class actually holds. Read-only |
| `verify_written.py` | Independent read-back of written students |
| `trial_write_five.py` | Bounded write test — re-sends values unchanged to exercise the POST path |
| `test_gp_ep_five.py` | Bounded GP + EP test on 5 students |
| `control_client.py` | Client for the local control API |
| `list_bad_exam_result.py` | List students whose exam result is invalid. Read-only |
| `write_not_studying.py` | Write the `None/Not Studying` rule for specific students |
| `write_xi_one.py` | Single-student Class XI write test |
| `send_one_write.py`, `send_valid_write.py` | Early single-write probes, kept for reference |

```bash
FIN_CLASS=9 python3 tools/finalize_class.py            # dry run
FIN_CLASS=9 FIN_ALLOW=1 python3 tools/finalize_class.py
BATCH_SIZE=5 python3 tools/write_batch.py
FP_CLASS=9 python3 tools/write_facility.py
python3 tools/preview_rules.py
```

---

## 2. What the portal actually does

Verified live on 3 October 2026. **The portal is v3.2.0** and has moved on from
the notebook's assumptions in several places.

### Working endpoints

| Purpose | Route | Result |
|---|---|---|
| Session check | `GET /p0/check-session` | 200 |
| School/user info | `GET /p0/api/user` | 200 |
| Roster | `GET /p0/api/cy/students/all/{schoolId}` | 200 |
| GP record | `GET /p0/api/cy/students/{studentId}` | 200 |
| EP record | `GET /p0/api/v2/students/enrolment/{studentId}` | 200 |
| **EP write** | `POST /p0/api/v2/students/enrolment/{studentId}` | **200, persists** |
| FP record | `GET /p0/api/v2/students/facility/{studentId}` | 200 |
| FP write | `POST /p0/api/v2/AY/students/facility/{studentId}` | not exercised |
| Finalize | `POST /p0/api/v2/students/submit/{studentId}` | not exercised |
| Privileges | `GET /p0/api/privileges` | 200 |

### Dead endpoints

| Route | Result |
|---|---|
| `GET /p0/api/masters/subject/{school}/{class}/2/0` | **404** |
| `GET /p0/api/master/subject/...` (any variant) | **404** |

The subject catalogue route the notebook depends on **no longer exists**. ~20
route shapes and the app's own JS bundles were probed; the route could not be
located. Because the Enrolment page is not currently reachable in this school's
menu, the browser never calls it, so it cannot be observed in traffic either.

**This is handled** — see §4.

### Misleading portal banner

The dashboard displays:

> *"Only GP Form Save is allowed."*

**This is wrong.** EP writes are accepted and persist. Verified by a real save
with `tnxReqNo` returned. Do not treat that banner as a capability statement.

---

## 3. Authentication

UDISE login involves OTP/CAPTCHA, which stays with the human. The runner never
logs in — it consumes a browser session cookie.

```bash
export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...'
```

Get it from: log in → F12 → Network → any `sdms.udiseplus.gov.in` request →
Request Headers → `Cookie:`.

**The session expires** (observed after a few hours). A 302 from
`check-session` means refresh the cookie.

Cookies are runtime-only. Never logged, never written to disk. To keep the value
out of shell history:

```bash
export UDISE_COOKIE_FROM_STDIN=1
vault kv get -field=cookie secret/udise | udise-vps completion --school <id>
```

---

## 4. Subject codes — the verified map

The live catalogue is unreachable, so codes come from a **verified static map**
derived by joining two independent sources:

- the **names** in a real UDISE enrolment export (`UDISE_EP_Update_*.xlsx`)
- the **codes** the live portal returns for the same students

Matched one student at a time across 38 Class X students, no conflicts:

| Subject | Name | Code | Evidence |
|---|---|---|---|
| 1 | HINDI | `629` | AMAN KUMAR SAH, HINDI ↔ 629 |
| 1 | URDU | `638` | AFRIN KHATOON, URDU ↔ 638 |
| 2 | SANSKRIT | `637` | AMAN KUMAR SAH, SANSKRIT ↔ 637 |
| 2 | **HIN (NLH)** | **`1102`** | AFRIN KHATOON, HIN (NLH) ↔ 1102 |
| 3 | MATHEMATICS | `401` | mandatory, all complete records |
| 4 | SCIENCE | `402` | mandatory |
| 5 | SOCIAL SCIENCE | `404` | mandatory |
| 6 | ENGLISH | `612` | mandatory |

**On `HIN (NLH)` vs `NON-HINDI`:** the portal displays code `1102` as
`NON-HINDI` in some screens while the catalogue calls it `HIN (NLH)`. **They are
the same code.** The name used in the code is the catalogue name.

### Language plan

| Condition | Subject 1 | Subject 2 |
|---|---|---|
| `minorityId = 1` (Muslim) | URDU (`638`) | HIN (NLH) (`1102`) |
| otherwise | HINDI (`629`) | SANSKRIT (`637`) |

Resolution order: **live catalogue if available → verified static map**.
`subjects.py` holds the map; a live catalogue always wins when well-formed.

---

## 5. Bugs found in the notebook (all fixed here)

Every one of these was found by running against the real portal. None were
findable offline.

### 5.1 Cross-portal matching was completely broken

`_norm_dob` only handled 8-digit runs, so `2012-03-02` became `022012`.
**No student would ever have matched the eShikshaKosh report.** Real DOBs are
ISO format in both sources.

### 5.2 Stream codes collide between the two portals

| Code | eShikshaKosh | UDISE |
|---|---|---|
| 1 | Arts | **Science** |
| 2 | **Science** | Arts |
| 3 | Commerce | Commerce |

Passing the eShikshaKosh code straight through would **swap Science and Arts for
every XI/XII student** — and the portal would accept it, since both codes are
valid. The notebook has no translation layer.

**Fix:** map by **name only**, never by numeric code (`UDISE_STREAM_CODE`).
Reachable only for XI, which is why it was never hit before.

### 5.3 Admission-number year parsing

Regex only matched 4-digit years. Real data contains `5/25` and `62/25`.
Fixed to accept 2- and 4-digit years.

### 5.4 Generated numbers restarted at 1

Saved UDISE numbers were not counted toward "highest used", so a blank student
would get `1` when the class already reached `33`. Now continues from the
highest.

### 5.5 Wrong admission-number format

UDISE stores a **plain number** (`1`, `2`, `3`), not `N/YYYY`. The notebook's
`_format_next` produces `34/2026`. Fixed; `--admission-style slash_year`
available if ever needed.

### 5.6 `moiId: 0` rejected — `ER1096`

> *"Selected Medium of Instruction not available for your school"*

28 of 33 Class IX students have `moiId = 0`. The notebook passes it through
blindly. Fixed: a blank medium is filled with the school's actual medium,
derived from the students whose records are already complete (`4` = Hindi).
Override with `--moi-id`.

### 5.7 Mandatory subjects left at 0

> *"Some mandatory fields value are incorrect or missing"*

Subjects 3–6 are **mandatory**. The operator's rule was "leave them as saved" —
but "saved" here is `0`, which the portal rejects. Fixed: filled when blank.

### 5.8 Invalid `examResultPy` passed through

> `{"errorFields": {"examResultPy": "Invalid Exam Result Selected"}}`

Valid codes are **1, 2, 3** only. Two students carry `5`. **The runner does not
guess** — that field states whether a student was promoted, a factual claim.
Those rows are reported for manual review. Override with `--exam-result`.

### 5.9 False read-back mismatch

The portal reports unset optional subjects as `None` while the payload sends `0`.
Normalised so slots 7/8 do not produce a phantom mismatch.

### 5.10 Crash on null catalogue entries

`AttributeError` on `None` options. Guarded.

### 5.11 School name showed a teacher's name

`/p0/api/user` returns the logged-in **person**, not the school. Now read from a
student record (`schoolName` / `schUdiseCode`).

### 5.12 `--out` did not create its directory

The first live attempt failed at `wb.save()` with `FileNotFoundError` after auth
and roster fetch had already succeeded. Fixed with `mkdir(parents=True,
exist_ok=True)`.

---

## 6. General Profile — nothing to do

Every Class IX student read is `formStatus=6` (**complete**), and the GP fields
already hold the specified values.

| Field | Specified | On portal |
|---|---|---|
| motherTongue | Hindi | `28` ✅ |
| bloodGroup | Under Investigation | `9` ✅ |
| cwsnYN | No | `2` ✅ |
| natIndYN | Yes | `1` ✅; if the fresh saved value is `2` (No), AUTO GP corrects it to `1` (Yes) under the school-confirmed Indian-national rule |
| isBplYN | No | `1` ⚠️ (this is *Yes*) |

**No GP writes are needed.** Preview confirms "nothing blank to fill".

`isBplYN=1` is worth an operator check — it reads as BPL *Yes*, while the spec
said No. Not changed, since saved values are preserved.

---

## 7. The verified live save

First successful EP write, 3 October 2026:

```
TARGET : ANSHU KUMARI  (PEN 22426748555, Class IX)
POST   : /p0/api/v2/students/enrolment/1557000339
RESULT : HTTP 200  status=true  tnxReqNo=TXNBR0310261042066278780

READ-BACK: CONFIRMED
  admnNumber   None -> '14'
  moiId           0 -> 4        (Hindi)
  subject1        0 -> 629      (HINDI)
  subject2        0 -> 637      (SANSKRIT)
  subject3        0 -> 401      (MATHEMATICS)
```

Payload shape (21 fields): `schoolId`, `studentId`, `admnNumber`,
`admnStartDate`, `rollNumber`, `moiId`, `academicStream`, `enrStatusPY`,
`classPY`, `examResultPy`, `examMarksPy`, `attendancePy`,
`certifiedCheckCount`, `subject1`–`subject8`.

---

## 8. Safety model

Carried over from the notebook, not relaxed:

- **Preview by default.** Every write command needs `--submit`.
- **Write caps.** `--max` bounds writes per run (default 1).
- **Blank-only fill.** Saved values preserved.
- **CWSN=Yes skips entirely** (GP).
- **No blind POST retry.** Ambiguous failure → fresh read-back, never replay.
- **Read-back required.** Confirmed only when a fresh read matches the payload.
- **Batch stops on uncertainty.**
- **Finalize gated** to fresh `formStatus=3`; status 6 never re-finalized.
- **Never guess factual values.** Invalid `examResultPy` is reported, not filled.

---

## 9. Install and usage

```bash
cd udise-hermes-version
./install.sh                       # venv + deps + ~/.local/bin/udise-vps
export PATH="$HOME/.local/bin:$PATH"
export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...'

# Read-only
udise-vps students   --school <URL-or-7-digit-ID>
udise-vps snapshot   --school <id>
udise-vps completion --school <id> --class IX

# Preview (writes nothing)
udise-vps gp       --school <id> --class IX
udise-vps ep       --school <id> --class IX --report otr.xlsx --limit 8
udise-vps facility --school <id> --class IX

# Write (one student)
udise-vps ep --school <id> --class IX --report otr.xlsx --limit 8 --submit --max 1

# Finalize
udise-vps finalize --school <id> --pen <PEN>
udise-vps finalize --school <id> --from-completion --submit --max 1
```

`--school` accepts the school URL or the 7-digit internal ID.
Class scopes: `IX`, `X`, `XI`, `XII`, `IX and X`, `IX to XI`, `XI and XII`,
`All IX-XII`. EP currently supports `IX`, `X`, `IX and X`.

### EP flags

| Flag | Purpose |
|---|---|
| `--report` | eShikshaKosh OTR workbook (admission numbers) |
| `--limit N` | Process first N students only |
| `--max N` | Cap writes in this run |
| `--moi-id N` | Medium of Instruction for blank values (default 4 = Hindi) |
| `--exam-result {1,2,3}` | Override an out-of-range `examResultPy` |
| `--admission-style` | `plain` (default) or `slash_year` |
| `--fallback-width N` | Zero-pad generated numbers (`2` → `01`) |
| `--fix-languages` | Also correct Subject 1/2 when already saved |

---

## 10. Tests

```bash
python3 test_offline.py      # 24 core safety tests
python3 test_ep_facility.py  # 39 EP/Facility tests
```

No network. They assert the safety rules actually hold: previews never write,
CWSN=Yes never POSTs, a transport error does not cause a second POST, an
unconfirmed read-back stops the batch, Finalize refuses status 0/1/2/6, stream
codes map by name not number, and a blank `moiId` is filled rather than sent as 0.

The core fake is a **stateful portal simulator** — a write it accepts is visible
to the next read, which is what makes the read-back assertions meaningful rather
than tautological.

### Live read smoke test

```bash
export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...'
./smoke_readonly.sh <school-id> IX
```

Read-only: roster export, completion overview, AUTO GP preview. Sends no writes.

---

## 11. Layout

```
udise-hermes-version/
├── udise_vps/
│   ├── __init__.py          version + baseline notebook reference
│   ├── constants.py         endpoints, class scopes, status model, dropdowns
│   ├── session.py           auth, roster, detail reads, single-POST helper
│   ├── subjects.py          verified subject / moi / exam-result code maps
│   ├── general_profile.py   AUTO GP defaults, Indian-national correction + read-back
│   ├── ep.py                Enrollment Profile (IX/X) + admission numbering
│   ├── facility.py          Facility Profile blank-only fill
│   ├── completion.py        Completion Overview status scan
│   ├── finalize.py          Finalize / Complete Data with all guards
│   ├── students.py          masked-Aadhaar student export
│   ├── snapshot.py          combined stage-wise read-only workbook
│   └── cli.py               command line
├── test_offline.py          24 core safety tests
├── test_ep_facility.py      39 EP/Facility tests
├── smoke_readonly.sh        live read-only smoke test
├── install.sh               venv + launcher
├── verify_ep_live.py        live admission/subject resolution check
├── preview_one_write.py     shows the exact payload before sending
├── send_valid_write.py      one write for a student with valid examResultPy
├── diag_ep_post.py          raw POST + full error body (diagnostics)
└── requirements.txt
```

---

## 12. Open items

| Item | Status |
|---|---|
| 2 students with `examResultPy=5` | **Needs operator decision** — correct in portal or `--exam-result` |
| Subject catalogue route | Unresolved (portal v3.2.0). Static map covers it. |
| Facility Profile write | Never run live |
| Finalize | Never run live |
| Class XI EP | Needs stream contract; stream mapping ready |
| `isBplYN=1` on complete students | Reads as BPL *Yes* vs spec "No" — operator check |
| Remaining Class IX EP blanks | ~26 students ready, not yet written |

---

## 13. Data handling

Never commit or log: cookies, JSESSIONID/XSRF values, passwords, OTPs, CAPTCHA
material, raw student API responses, or completed student workbooks.
`.gitignore` excludes `*.xlsx`, `*.csv`, `*.log`, `smoke-out/`, `.env`.

The `smoke-out/` workbooks contain student data — delete when no longer needed.

## 7. Oracle control plane, Vercel and Hermes

The verified CLI remains the execution engine. A control-plane layer under
control_api exposes dynamic class/stage capabilities, secure runtime UDISE
session entry, read-only jobs, aggregate progress events and protected results.

Students, snapshot, and completion execute as read-only API stages. GP, EP,
Facility, and Finalize start as no-POST previews and return a proposed-change
Excel. A completed preview can authorize one bounded write only after the
operator reviews the workbook, chooses a cap, acknowledges fresh read-back,
and types the stage/class confirmation phrase. Direct write-job creation stays
blocked. Preview workbooks and temporary eShikshaKosh source files expire after
24 hours.

The Vercel source is in web/. The Hermes natural-language skill and local client
are in hermes-skill/udise-control/ and tools/control_client.py.

Future GitHub main updates can be verified and fast-forward promoted by
tools/promote_from_github.sh. Promotion runs offline tests first and never means
automatic portal writes.

See docs/CONTROL_PLANE.md.
