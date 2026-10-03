# Hermes VPS Runner — Current State

Last verified: **2026-10-03**. Portal **v3.2.0**.

## Evidence summary

| Component | Command | Status |
|---|---|---|
| Roster export | `students` | `LIVE_READ` — 208 students |
| Full read snapshot | `snapshot` | `DEPLOYED` + `OFFLINE_TESTED`; fresh live session needed |
| Completion overview | `completion` | `LIVE_READ` |
| General Profile | `gp` | **`LIVE_SAVE`** — payload fixed, write verified on 4 students |
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

**Already complete for all 208 students** — a live census found zero blank AUTO
fields in any class, so nothing needed writing.

The rules are implemented and covered by tests regardless, because they must
hold for any school:

- blank blood group → Under Investigation (9); code 0 clamped to 9
- 4.1.14 BPL → No · 4.1.16 EWS → No · 4.1.17 CWSN → No
- 4.1.18 Indian National → Yes · 4.1.19 Out-of-School-Child → No
- Mother Tongue → HINDI - Hindi (42)
- 4.1.15 AAY: BPL = No → AAY = Not Applicable
- 4.1.16 EWS: SC/ST/OBC can never be EWS

Live evidence: 205 students carry `bloodGroup=9`, 3 carry real groups (A+, B+,
B-). The three are left untouched — the blank-only rule works.

**Live write verified** (3 Oct 2026) after fixing the payload.

The first attempt failed on every student with `INTERNAL_SERVER_ERROR`. The
cause: our payload sent only the 14 dropdown fields, while the portal requires
the record's identity block too. A short payload fails **even when every value
is unchanged**.

| Payload | Result |
|---|---|
| 14 fields | `INTERNAL_SERVER_ERROR` |
| 34 fields | `status: true`, values preserved |

Verified on 4 students — `lastModifiedOn` stamped, and a fresh read-back
confirmed every field unchanged. GP is still complete for all 208, so no real
gap-fill has been needed.

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

## Control-plane MVP — 2026-10-03

- Oracle control API is implemented and running from the mirrored repository.
- Dynamic capabilities expose IX/X/XI/XII and all known stages.
- Read-only API execution is enabled for Student Roster, Full Read Snapshot,
  and Completion.
- GP/EP/Facility/Finalize job creation is rejected until write approval exists.
- Secure one-time UDISE session entry is implemented; Cookie material is kept
  in the user runtime directory rather than durable project state.
- Public HTTPS reachability for the dedicated control API has been verified.
- Vercel Next.js UI source builds successfully in production mode.
- Hermes udise-control skill and local control client are installed.
- Offline Python baseline is 145/145, including the synthetic control-plane preview
  lifecycle and write-lock test.
- Periodic GitHub promotion tooling is installed; dirty worktrees skip safely.

## Private GUI trial — 2026-10-03

- `udise-web.service` is a production Next.js user service bound to
  `127.0.0.1:3010` and published only through Tailscale Serve.
- The control API/session form is tailnet-only at port 10000; Funnel is off.
- Smoke evidence: UI login 200, dynamic capabilities, one-time secure session
  link/form, and a GP job request rejected with `409`.
- No Cookie was entered and no portal job or write ran.

## Full read snapshot — 2026-10-03

- `snapshot` performs GP, EP, and Facility GETs for every roster student and
  derives the Completion sheet from the fresh GP read.
- The workbook contains Students, GP, EP, Facility, Completion, and Issues
  sheets. Aadhaar-like values are masked; secret-like fields are redacted.
- The control API and WhatsApp capability flow expose the stage as read-only.
- Live Oracle deployment and authenticated portal execution remain to be
  verified; do not promote this line to `LIVE_READ` without that evidence.
- The Oracle deployment passed 140/140, production Next.js build, service
  restart, private login, dynamic capability, secure-link, and HTTP 409
  write-lock checks.
- The available runtime UDISE session was rejected by the portal with HTTP 302
  before roster loading. No student read and no write occurred. A fresh Cookie
  must be entered through the private one-time form before live snapshot proof.

## Compact preview UI — 2026-10-03

- The private GUI is a compact control/output workspace rather than stacked
  cards. Session entry opens inline in a secure modal; no separate tab needed.
- GP, EP, Facility, and Finalize tiles can run no-POST previews. Each returns
  an Excel listing proposed values and reasons. EP also embeds a masked
  eShikshaKosh source sheet.
- Preview files are private and expire after 24 hours. Actual saves remain
  locked behind a future explicit approval endpoint.
- eShikshaKosh credentials use a separate inline one-time Oracle form. The
  password file is consumed/deleted when EP preview starts; WhatsApp gets only
  the secure link and never the password.
- Web copy is formal English and follows the same Phase 1–5 descriptions and
  stage restrictions as `docs/flow.html`, capabilities, and the Hermes skill.
- Class scope is selected before workflow selection. The selected class is
  preserved, and unsupported stages are disabled rather than silently changing
  the operator's class choice.
- The eShikshaKosh export wrapper selects the maintained eShikshaKosh project's
  own virtual environment so Playwright and its browser are available. Failures
  are flattened into one actionable job error rather than losing the script's
  diagnostic tail.
- A desktop Chrome/Edge Manifest V3 session bridge can submit the current SDMS
  cookies to an already-created one-time Oracle session request after a user
  click. It does not display, log or persist cookie values.
