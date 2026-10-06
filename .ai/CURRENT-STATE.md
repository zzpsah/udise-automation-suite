# Current State

Last documented: 2026-10-03

## Baseline
- Maintained notebook: `UDISE_Automation_v2.7.3_2026-09-23.ipynb`.
- AUTO GP is the preferred General Profile path.
- AUTO GP fills approved blank fields only.
- CWSN=Yes is skipped for manual review.
- Completion uses observed status progression 0 -> 1 -> 2 -> 3 -> 6.
- Finalize only writes fresh status 3 and requires fresh status 6 confirmation.
- Enrollment remains IX/X.
- Facility selectors extend through XII, but XI/XII live save evidence is still missing.

## Evidence boundary
- Implemented is not the same as live-verified.
- AUTO GP current-baseline live write still needs a reviewed test.
- Corrected Facility persistence still needs live verification.
- XI/XII Enrollment and Facility writes must not be assumed from IX/X behavior.
- A real status 3 -> Complete Data -> status 6 transition has live evidence.

## Next
Upload-driven AUTO EP for IX and XI, with strong matching, end-of-batch manual review, Admission Number prefill, stream selection for XI, and one-record-first live write testing.

## Headless runner (`hermes-vps/`)

Added 3 October 2026. A command-line sibling of the notebook: same portal
operations, no Colab, no browser. 110 offline tests.

Live evidence from that work:

- **Enrolment Profile, Class IX — 33/33** written and confirmed by read-back.
- **Facility Profile, Class IX — 33/33** written and confirmed by read-back.
- **Complete Data, Class IX — 33/33** at `formStatus=6`, verified by a fresh
  per-student read of all 33.

Class X remains: 3 admission numbers, 21 missing subject sets, FP for 38, then
finalize.

**Class XI/XII Enrollment is blocked server-side.** The portal returns error
`1002` — no subject mapping configured for this Board and Class. A probe of all
62 Class XI records found 0 with any subject slot filled. Admission numbers and
streams resolve 62/62 and will apply once UDISE enables it. This is a portal
configuration gap, not a client defect.

See `hermes-vps/brain/HANDOFF.md` for the full handoff, and
`hermes-vps/docs/flow.html` for the flow diagram.

## Private web trial — 2026-10-03

- The production Next.js GUI runs as user-level `udise-web.service` on Oracle,
  bound to loopback and exposed only through Tailscale Serve.
- GUI: `https://oracle-server.tail2b7fe2.ts.net:3010/`; the one-time secure
  session form is separately tailnet-only on port `10000`.
- The private Oracle trial still uses Tailscale Serve. GP/EP/Facility/Finalize
  now have a preview-bound approval implementation; deployment itself does not
  execute a write.
- GUI metadata follows the five phases in `hermes-vps/docs/flow.html`.
- The GUI uses formal English operational copy derived from the Hermes VPS flow
  and capability matrix; decorative labels and notebook references are absent.
- A synthetic control-plane test verifies preview job creation, workbook output,
  direct-write rejection, typed/acknowledged bounded approval, one approval per
  preview, EP source reuse, and the `--submit --max` runner boundary without
  portal credentials or network access.
- Class scope is selected before workflow selection; unsupported class/stage
  combinations are visibly unavailable and never rewrite the selected class.
- The desktop UDISE session bridge is implemented as a user-clicked Chrome/Edge
  extension, and eShikshaKosh export now selects its maintained Playwright
  environment instead of the UDISE runner environment.

## Vercel production deployment — 2026-10-03

- Project: `zzpsah/udise-automation-suite` (manual CLI deployment).
- Production URL: `https://udise-auto.vercel.app/`.
- Verified from production: access-code login, dynamic capabilities, Tetahali
  preset, secure one-time Oracle session-link creation, and API health.
- Oracle control API reaches Vercel through dedicated HTTPS Funnel port `10000`;
  the Oracle GUI on port `3010` remains tailnet-only.
- `https://udise.vercel.app/` is assigned to another Vercel deployment and was
  not changed or deleted; the operator can reassign it from that account later.
- No live UDISE portal write ran during deployment; writes remain preview-bound.

## eShikshaKosh Playwright export — 2026-10-04

- The maintained exporter is `~/projects/eshikshakosh-automation/local-script/esk_otr_api.py` on Oracle.
- CAPTCHA detection and arithmetic solving are working.
- A Playwright diagnostic captured the real login request: `POST /auth/login` returns HTTP 422 with `Invalid userId/Password.`
- The browser remains at `/login`; no token, localStorage value, or cookie is created because the portal rejects the supplied credentials.
- This is not currently a selector, CAPTCHA, or token-listener defect. A valid eShikshaKosh UDISE/password pair is required for the next live export test.
- Oracle runtime dependencies `nest-asyncio` and `playwright` were missing from the Hermes venv and have been installed; both are now declared in `hermes-vps/requirements.txt`.
- The Playwright listener now checks nested token fields, storage, and cookies after login for portal-version drift.
- Live export remains unverified until credentials are refreshed. No credentials or private reports are stored in Git.
- Next offline test: `hermes-vps/tests/test_esk.py` passed 10/10. The complete local suite could not run in the bare Windows interpreter because `fastapi` is not installed there; this is an environment limitation, not a test failure in the eShiksha module.
## Remote access handoff
- Canonical access instructions: `docs/REMOTE-ACCESS.md`.
- New AI chats must discover the current Desktop Commander device with `list_devices`, choose the online `oracle-server`, and verify it with `ping` before touching live runtime state.
- GitHub access alone does not provide Oracle VPS control.
