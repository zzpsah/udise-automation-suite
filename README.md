# UDISE Automation Suite


## Current production architecture — 8 October 2026

> **Current production is the Vercel + Oracle control-plane implementation under `hermes-vps/`.**
>
> The Colab notebook remains a historical/interactive fallback, not the best starting point for production work.

**Production:** `https://udise-auto.vercel.app/`

Current path:

`Vercel UI → Oracle control API → Playwright Students Module login → authenticated runtime session → udise_vps runner → SDMS APIs`

After login the UI is designed to show **Students Module connected**, school name, UDISE code and a live session countdown before Class + Workflow controls.

### Production write model — 8 October 2026

For write-capable workflows (**GP, EP, Facility/FP, Complete Data**), **Run & Save is now server-durable**. The UI requests a preview with `auto_save=true` plus a user-selected save limit (1–500). After a successful preview, the Oracle Control API creates exactly one bounded write child job using that exact approved limit and runs it server-side. A browser refresh, background suspension, or disconnect therefore does not cancel the Preview → Write transition.

The write child still performs its own fresh pre-write read, sends only permitted POSTs, and requires fresh read-back verification. Read-only stages (**Students, Full Snapshot, Completion Overview**) never create a write child. The manual approval endpoint remains available as a recovery path.

The current production class/write capability boundary is:

| Workflow | Classes | Mode |
|---|---|---|
| Student Roster | IX–XII | Read |
| Full Snapshot | IX–XII | Read, class-scoped |
| General Profile | IX–XII | Write |
| Enrollment Profile | IX–X | Write |
| Facility Profile | IX–XII | Write |
| Completion Overview | IX–XII | Read |
| Complete Data / Finalize | IX–XII | Write |

EP XI/XII is intentionally excluded until the portal's stream/subject mapping is independently discovered and verified; this is a portal contract limitation, not a disabled write permission.

A Full Snapshot class-selection regression is also fixed: the Control API now forwards the selected `--class` to the runner, so a Class X request cannot silently fall back to the Class IX/default scope.


### AI / developer start here

1. [AI handoff](docs/AI_HANDOFF.md)
2. [Architecture](docs/ARCHITECTURE.md)
3. [Visual flows](docs/VISUAL_FLOWS.md)
4. [API reference](docs/API_REFERENCE.md)
5. [Login flow](docs/LOGIN_FLOW.md)
6. [Workflow engine](docs/WORKFLOW_ENGINE.md)
7. [Deployment / hosting](docs/DEPLOYMENT.md)
8. [Troubleshooting](docs/TROUBLESHOOTING.md)
9. [Security](docs/SECURITY.md)
10. [Repository map](docs/REPOSITORY_MAP.md)


This private repository is the **single source of truth** for the UDISE+ school automation notebook used for UMV Tetahali.

## Current baseline

**Maintained notebook:** `UDISE_Automation_v2.7.3_2026-09-23.ipynb`

[▶ Open current baseline in Google Colab](https://colab.research.google.com/github/zzpsah/udise-automation-suite/blob/main/UDISE_Automation_v2.7.3_2026-09-23.ipynb)

**Headless runner:** [`hermes-vps/`](hermes-vps/HERMES-VPS.md) — the same portal
operations from the command line, for servers and repeatable runs. 110 offline
tests. Start at [`hermes-vps/brain/hermes-vps/HANDOFF.md`](hermes-vps/brain/hermes-vps/HANDOFF.md).

| | Interface | Best for |
|---|---|---|
| `UDISE_Automation_v2.7.3_*.ipynb` | Colab notebook | Interactive, guided work |
| `hermes-vps/` | Command line | Repeatable runs on a server |

Both follow the same safety rules. Neither is school-specific — school identity
comes from the portal at runtime.

For another AI or developer taking over this project, read **[docs/AI_HANDOFF.md](docs/AI_HANDOFF.md) first**.

### Baseline status — 23 September 2026

v2.7.3 keeps the v2.7 workflow and adds the current preferred General Profile UI:

- AUTO GP is the normal path.
- AUTO GP help/default information is collapsed by default.
- GP Reference Data and Manual GP Excel are grouped as a fallback and do not need to be part of the normal AUTO flow.
- AUTO GP can target IX, X, XI, XII, IX+X, IX–XI, XI+XII, or all IX–XII.
- AUTO GP can scan **All students** or the **First N students**.
- AUTO GP fills only approved fields that are currently blank; existing saved values are preserved.
- Existing CWSN=Yes students are skipped completely and flagged for manual review.
- Facility Profile and Completion Overview expose IX–XII class scopes.
- Completion Overview uses the project-observed status progression `0 → 1 → 2 → 3 → 6`.
- AUTO Finalize consumes only fresh `formStatus=3` students and confirms success only when fresh read-back becomes `formStatus=6`.
- Write POSTs are never blindly retried.

The status mapping is observed project behavior, not an official published UDISE enum.

## Start here

Normal notebook flow:

`Setup environment → Login → choose module → preview/validate → explicitly enable write → fresh read-back`

Login authenticates the runtime, detects the school, and fetches the current roster. Credentials/cookies remain runtime-only.

## Modules

### General Profile

AUTO GP defaults are applied **only when the portal value is blank**:

| Field | AUTO value |
| --- | --- |
| Mother Tongue | 42 - HINDI - Hindi |
| BPL Beneficiary | No |
| EWS / Disadvantaged Group | No |
| CWSN | No |
| Indian National | Yes |
| Out-of-School Child | No |
| Blood Group | Under Investigation - Result will be updated soon |

If current CWSN is already **Yes**, AUTO GP makes no change for that student and marks the record for manual review.

AUTO GP has two independent scopes:

- **Class scope:** IX, X, XI, XII, IX and X, IX to XI, XI and XII, All IX–XII.
- **Run scope:** All students or First N students.

Submission is gated by `ALLOW_AUTO_GP_SUBMIT`; preview-only is the safe default. `AUTO_GP_MAX_SUBMISSIONS` limits actual writes in a run.

Manual GP Excel remains available for records that need editing outside the AUTO defaults.

### Enrollment Profile

The maintained Enrollment workflow remains **IX/X**. XI/XII enrollment requires separate discovery of stream-specific forms, subjects, and mandatory fields before implementation.

### Facility Profile

The notebook now exposes IX–XII class scopes. The maintained server runner uses these blank-only generation ranges for IX/X: boys 140–155 cm and 38–52 kg; girls 135–150 cm and 34–48 kg. XI/XII retains the previous ranges. Existing saved measurements are never overwritten. **XI/XII Facility writes are not yet live-verified.** Actual measured values remain the authoritative input; generated values are only workflow defaults for unset fields.

### Completion Overview

Completion Overview reads each student's current General Profile record and groups students by the project-observed `formStatus`:

- `0` — GP + EP + FP pending
- `1` — GP completed; EP + FP pending
- `2` — GP + EP completed; FP pending
- `3` — GP + EP + FP completed; ready for Complete Data
- `6` — Complete Data completed

Only status 3 is exposed to AUTO Finalize.

### Finalize / Complete Data

Finalize supports AUTO, MANUAL PEN entry, and file-based PEN selection. Before every write it performs a fresh status read. Only current status 3 can be submitted. A Complete Data POST is sent once and never automatically replayed. Success requires a fresh read showing status 6.

A live test has confirmed a real status 3 → Complete Data → status 6 transition.

## Verification boundaries

Do not confuse these evidence types:

- **Implemented** — code exists.
- **Offline tested** — mocked/static test only.
- **Live read** — authenticated GET observed.
- **Live save** — reviewed write followed by fresh matching read-back.

Current important limits:

- AUTO GP behavior is implemented and its durable Preview → Write transition is covered by synthetic Control API tests; this does not by itself constitute a new live GP write test.
- Facility IX/X measurement generation is live in the server runner for blank fields only; the requested IX/X ranges are 140–155 cm / 38–52 kg for boys and 135–150 cm / 34–48 kg for girls. Existing saved values are never overwritten.
- Facility live write acceptance remains a separate verification boundary; XI/XII Facility writes remain unverified.
- Full Snapshot is class-scoped end-to-end; the selected IX/X/XI/XII class is forwarded explicitly to the runner.
- Enrollment remains IX/X only.
- Finalize status 3 → 6 has live proof.

## Development rules

1. Treat this notebook as the maintained baseline.
2. Do not create another repository baseline until the candidate notebook has been reviewed/tested.
3. Keep write toggles off by default.
4. GET/read-only operations may use bounded retries.
5. Never blindly retry a POST after timeout or connection loss; use fresh read-back first.
6. Do not call HTTP 200 a successful save unless application status/read-back confirms persistence.
7. Preserve user-entered/saved values unless a workflow explicitly says to update them.
8. Keep private student data and credentials out of Git.

## DevOS / Vibe Coding project context

This repository now carries the full project-context layer used by DevOS:

- [PRD](PRD.md)
- [Development rules](RULES.md)
- [Tasks](TASKS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Design](docs/DESIGN.md)
- [Test plan](docs/TEST_PLAN.md)
- [Security](docs/SECURITY.md)
- [Decisions](docs/DECISIONS.md)
- [Project memory](docs/MEMORY.md)
- [Commands / runbook](docs/COMMANDS.md)
- [History](docs/HISTORY.md)
- [AI handoff](docs/AI_HANDOFF.md)

Material work follows:

```text
READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION
```

## Documentation

- [AI handoff / current project state](docs/AI_HANDOFF.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Colab runbook](docs/COLAB_RUNBOOK.md)
- [Class selection](docs/CLASS_SELECTION.md)
- [API reference and verification record](docs/API_REFERENCE.md)
- [Facility Profile](docs/FACILITY_PROFILE.md)
- [Portal discovery](docs/PORTAL_DISCOVERY.md)
- [AI browser retrieval](docs/AI_BROWSER_RETRIEVAL.md)
- [Data handling](docs/DATA_HANDLING.md)


## Next development plan — AUTO Enrollment Profile (EP)

Priority: **Class IX and Class XI**, with Class XI stream-wise processing.

### Goal

Add a cross-portal AUTO EP workflow that uses an uploaded **eShikshaKosh export** to supply the key EP value that is difficult to re-enter manually: **Admission Number**.

The first implementation should be upload-driven and must not require eShikshaKosh authentication inside the UDISE notebook. Automatic eShikshaKosh retrieval can remain a later optional adapter.

### Placement in the notebook

AUTO EP should live **inside the Enrollment Profile section** and run before the existing manual EP Excel fallback:

1. eShikshaKosh source upload
2. Cross-portal student matching
3. AUTO EP preview
4. End-of-batch Manual Review queue
5. Final EP preview
6. Guarded AUTO EP submit
7. Existing Manual EP Excel fallback

### eShikshaKosh upload assumptions

The uploaded export is expected to provide enough identity evidence to match students even when PEN is absent. Expected useful fields include:

- Student name
- Father name
- Mother name when available
- DOB
- Aadhaar last 4 digits
- Admission Number
- Class / section may be present but must not be used as hard identity keys

For Class XI, **stream is not expected as a file column**. The user will select the stream before upload, and the uploaded file is assumed to contain only that selected stream.

### Matching rules

The new eShikshaKosh export may not contain PEN, so matching should use identity evidence:

- DOB
- Aadhaar last 4
- normalized student name
- normalized father name
- mother name as supporting evidence when available

Class and section are informational only and may differ between portals.

Recommended behavior:

- strong evidence → AUTO MATCH
- ambiguous candidate(s) → MANUAL REVIEW
- no confident candidate → NO MATCH
- Aadhaar/DOB conflict → do not auto-match
- never use Aadhaar last 4 as a standalone unique key

The entire file should be processed first. **Manual review must happen at the end of the batch**, not interrupt student-by-student processing.

Each unresolved record should keep a serial number so it can be reviewed by Sr. No. after automatic processing finishes.

### Admission Number mapping

For matched students:

- UDISE Admission Number blank + eShikshaKosh value available → PREFILL
- same nonblank value already in UDISE → KEEP
- different nonblank UDISE value → CONFLICT / MANUAL REVIEW
- no confident student match → MANUAL REVIEW / NO MATCH

Do not overwrite an existing conflicting Admission Number automatically.

### Class XI stream-wise workflow

AUTO EP should support:

- XI Science
- XI Arts
- XI Commerce

Preferred UI structure:

- AUTO_EP_CLASS = XI
- AUTO_EP_STREAM = Science / Arts / Commerce
- upload the eShikshaKosh export for that selected stream

For Class XI, the selected stream becomes the EP stream for all matched rows from that uploaded file.

### Class XI first-pass field rules

Subject to final live discovery of the XI EP form/API contract:

- Admission Number = from eShikshaKosh upload
- Roll Number = same as Admission Number
- Class Roll Number = leave blank
- Stream = selected stream (Science / Arts / Commerce)

The XI EP form contract still needs dedicated portal discovery before these values are submitted live. Do not assume IX/X EP payloads or subject rules apply to XI.

### Safety / submission

AUTO EP should follow the same safety model as AUTO GP:

- preview first
- ALLOW_AUTO_EP_SUBMIT=False by default
- first live test limit = 1
- fresh EP read before write
- no blind POST retry
- fresh read-back required to confirm persistence
- stop on ambiguous/unconfirmed failure

### Future optional source modes

Keep the mapping engine storage-independent so the same normalized input can later come from:

- uploaded Excel/CSV (first implementation)
- existing eShikshaKosh automation/retrieval helper
- optional Supabase-backed snapshot

Supabase must remain optional so the notebook can be reused for other schools without centralizing every school's data.


## Never commit

- browser cookies, session IDs, XSRF tokens, passwords, OTPs or CAPTCHA material;
- student exports, result files, screenshots or raw API responses containing student data;
- completed GP/Enrollment/Facility workbooks;
- `.env` files, secrets, or credentials.

Older notebooks remain in Git history/repository as rollback evidence. They are not the maintained baseline.
