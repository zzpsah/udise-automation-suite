# Hermes VPS Runner — Tasks

## Done

- [x] Package skeleton and CLI (`udise_vps/`)
- [x] Session layer — reads retry, writes do not
- [x] Roster export
- [x] Completion overview workbook
- [x] **Enrolment Profile** — Class IX live-saved and confirmed
- [x] **Facility Profile** — Class IX live-saved and confirmed
- [x] **Finalize / Complete Data** — Class IX 33/33 at `formStatus=6`
- [x] eShikshaKosh OTR report: operator export **and** live fetch
- [x] Admission-number priority chain, incl. roll-number fallback
- [x] Cross-portal matching that tolerates class and DOB disagreement
- [x] Stream resolution for Class XI, with operator prompt fallback
- [x] `None/Not Studying` auto rule for invalid exam results
- [x] Facility blank-detection for the `0` and `9` sentinels
- [x] Distance 4.3.6 randomised between 1–3 km and 3–5 km
- [x] 110 offline tests
- [x] Flow diagram (`docs/flow.html`)
- [x] DevOS + brain documentation

## Next — Class X

- [ ] Resolve 3 missing admission numbers
- [ ] Fill **21 missing subject sets** (earlier scans missed these — they only
      checked admission number and medium)
- [ ] Facility Profile for 38 students
- [ ] Finalize the 34 at status 1 or 2
- [ ] Re-verify the class with a per-student read

## Blocked — waiting on the portal

- [ ] Class XI/XII Enrolment. Error `1002`: no subject mapping configured for
      this Board and Class. Admission numbers and streams are resolved (62/62)
      and will apply once it is enabled. **Re-check periodically; do not loop.**

## Backlog

- [ ] General Profile write path — port AUTO GP, but only after live discovery.
      The notebook's CWSN=Yes skip rule needs verifying, not copying.
- [ ] Find the correct live subject-catalogue route. The one in the code is dead
      (404), so the verified static map is used.
- [ ] Make the eShikshaKosh captcha fallback non-interactive. It calls `input()`
      on auto-solve failure, which hangs an unattended run.
- [ ] Warn or error when `--report` and `--fetch-report` are both passed
      (`--report` currently wins silently).
- [ ] `run_ep` reads each enrolment record twice — once for admission inputs,
      once in the loop. Halves the portal load if merged.
- [ ] Decide on Class XII: `TARGET_CLASSES` excludes it, but students can be
      enrolled there and the portals disagree about class placement.

## Explicitly not planned

- Any write to eShikshaKosh. It is a read-only data source.
- Storing credentials or sessions.
- Scheduling / daemonising. It stays a CLI run deliberately.

## Control plane / UI / messaging

- [x] Mirror the repository on Oracle.
- [x] Add dynamic class/stage capability registry.
- [x] Add protected read-only job API and aggregate progress events.
- [x] Add one-time secure runtime UDISE session entry.
- [x] Keep all write stages locked in the control API.
- [x] Add Vercel Next.js GUI source and pass a production build.
- [x] Add Hermes natural-language skill and local control client.
- [x] Add verified GitHub candidate-test-and-promote workflow.
- [x] Run a private Oracle/Tailscale production GUI trial with Hermes VPS
      runner references and all write stages locked.
- [ ] Connect/deploy the Vercel project and set encrypted environment values.
- [ ] Add proactive WhatsApp progress push from job events.
- [ ] Add dedicated preview/approval workflow before enabling each write stage.
- [ ] Replace Cookie-header entry with direct username/password/CAPTCHA login
      when the live portal login contract is implemented.
