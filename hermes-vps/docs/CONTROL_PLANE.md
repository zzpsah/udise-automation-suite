# UDISE Control Plane

## Goal

Keep the verified udise_vps runner as the execution engine while adding two
user-facing control surfaces: a Vercel web UI and Hermes messaging.

Both surfaces use the same Oracle-side control API. They do not duplicate UDISE
portal logic.

## Architecture

Vercel UI and WhatsApp/Telegram Hermes both call the Oracle Control API.
The API provides dynamic capabilities, secure runtime UDISE session handling,
job state, aggregate progress events, the udise-vps CLI runner, and protected
result files.

The API binds to localhost. A separately configured HTTPS path may expose only
the control API to the Vercel server. Job/session management endpoints require
a high-entropy bearer secret that is never committed.

## Dynamic capabilities

GET /api/v1/capabilities is the source of truth for GUI and messaging choices.

Current stage registry:

- students: read-only, executable in MVP
- snapshot: read-only, executable; combined all-student stage workbook
- completion: read-only, executable in MVP
- gp: preview Excel, explicit bounded approval, save, fresh read-back
- ep: preview Excel with masked eShikshaKosh source, explicit bounded approval,
  save, fresh read-back
- facility: preview Excel, explicit bounded approval, save, fresh read-back
- finalize: status-3 preview, explicit bounded approval, status-6 read-back

The UI must not maintain a second hard-coded class/stage availability matrix. Future runner
enhancements should update the capability registry and both control surfaces
should render that result.

## Secure UDISE session

The current runner authenticates with an existing browser Cookie header.

The control API creates a high-entropy, short-lived one-time session-entry link.
The user enters the Cookie header directly into the Oracle-hosted form.

The Cookie value never passes through WhatsApp or Vercel application code. It
is stored only under the user runtime directory (/run/user/...), expires
automatically, and disappears on user-runtime/server restart.

A future username/password/CAPTCHA flow can replace this input without changing
the job API.

## Job model

Each job has an opaque id, stage, optional class, school reference, status,
aggregate progress counters, human-readable events, and an optional workbook.

Preview workbooks and any fetched eShikshaKosh source stay in the private job
directory for 24 hours, then the control API removes the files. Job metadata is
retained for audit without the expired result path.

EP uses a separate one-time eShikshaKosh credential form hosted directly by
the Oracle control API. The password does not pass through chat and its runtime
file is removed as soon as the EP preview process starts.

Raw per-student CLI lines are not returned to the web UI. Progress is converted
to aggregate messages such as: Completion status: 12/38 students checked.

## Write safety

Direct non-preview job creation is rejected with HTTP 409. A write job can be
created only from one completed, unexpired preview through
`POST /api/v1/jobs/{preview_id}/approve`. The operator must type the exact
`SAVE <STAGE> <CLASS>` phrase, acknowledge the read-back requirement, and
choose a maximum of 1–500 records. A unique database constraint prevents the
same preview from being approved twice.

The approved job preserves the runner contract:

1. fresh GET
2. blank-only diff
3. exactly one POST
4. fresh matching read-back
5. stop the batch on mismatch

No public UI or messaging feature may bypass this boundary. Deployment and
code promotion do not approve or run a portal write.

## Vercel web app

Source: hermes-vps/web/

The app requires an application access code, keeps Oracle API credentials
server-side only, fetches capabilities dynamically, creates secure UDISE session
links, starts read/preview jobs, polls human-readable progress, proxies protected
result downloads, and exposes the preview-bound approval controls.

Required Vercel environment values are documented in web/.env.example.

## Private Oracle trial

The same source runs without Vercel as user-level `udise-web.service`, binding
Next.js to `127.0.0.1:3010`. Tailscale Serve publishes only
`https://oracle-server.tail2b7fe2.ts.net:3010/`. The Vercel production app is
`https://udise-auto.vercel.app/`; it reaches only the control API
through dedicated HTTPS Funnel port `10000`. The Oracle GUI remains tailnet-only.
The legacy `udise.vercel.app` alias is owned by another Vercel deployment and is
left unchanged for the operator to reassign later.

The GUI follows `docs/flow.html`: Phase 1 session/roster, Phase 2 class scope,
Phase 3 GP, Phase 4 EP/Facility, and Phase 5 completion/finalize. These labels
are operator guidance only and do not make a write stage executable.

Class scope is selected before the workflow. A stage that does not support the
selected class is shown as unavailable; the GUI never changes the operator's
class selection to make a stage fit.

## Browser session bridge

A bookmarklet is not a reliable session bridge. Page JavaScript cannot read an
`HttpOnly` session cookie and cannot forward another origin's authenticated
cookie automatically. The current one-time secure Cookie-header form remains
the cross-device fallback.

A desktop Chrome/Edge extension may use the browser Cookies API after a user
click and explicit host permission for UDISE, the Oracle console, and
`udise.vercel.app`. It sends the cookie only to a newly created short-lived Oracle
session request and must never log or persist the value. Mobile Chrome does not
support this extension path, so it does not replace the secure form on phones.

The unpacked extension is implemented in
`browser-extension/udise-session-bridge/`. It discovers only the one-time
session iframe already created by an authenticated console and accepts only the
configured Oracle host, HTTPS, port 10000, and a valid session-token path.

Saved schools are deployment configuration, not runner constants. Set
`UDISE_SCHOOL_PRESETS_JSON` in the private web service environment. The UI uses
the selected preset's internal portal ID while displaying its UDISE code and
school name.

## Hermes

Source skill: hermes-vps/hermes-skill/udise-control/SKILL.md
Local helper: hermes-vps/tools/control_client.py

The skill maps natural-language requests to the same API. Missing finite choices
use the existing structured poll behavior. Cookies and API tokens must never be
requested or displayed in chat.

WhatsApp follows the same five phases as the web UI and `docs/flow.html`.
Capabilities are fetched before presenting stage/class polls. A clear request
such as `Class X completion dekho` skips redundant questions; ambiguous requests
poll only for missing finite inputs. Phase 3, Phase 4, and Finalize remain
locked by the API.

## Automatic promotion

hermes-vps/tools/promote_from_github.sh checks remote main in a temporary Git
worktree. It promotes only after offline suites and syntax checks pass.

The live repository is fast-forwarded only after successful verification, then
the API service is restarted. A dirty live worktree causes promotion to skip.

This is code promotion, not authorization for automatic UDISE portal writes.
