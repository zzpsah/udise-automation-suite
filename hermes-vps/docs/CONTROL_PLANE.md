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
- completion: read-only, executable in MVP
- gp: known write stage, visible but execution locked
- ep: known write stage, visible but execution locked
- facility: known write stage, visible but execution locked
- finalize: known write stage, visible but execution locked

The UI must not maintain a second hard-coded class/stage matrix. Future runner
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

Raw per-student CLI lines are not returned to the web UI. Progress is converted
to aggregate messages such as: Completion status: 12/38 students checked.

## Write safety

The control API currently rejects write stages with HTTP 409.

When write workflows are added they must preserve the runner contract:

1. fresh GET
2. blank-only diff
3. exactly one POST
4. fresh matching read-back
5. stop the batch on mismatch

No public UI or messaging feature may bypass this boundary.

## Vercel web app

Source: hermes-vps/web/

The app requires an application access code, keeps Oracle API credentials
server-side only, fetches capabilities dynamically, creates secure UDISE session
links, starts read-only jobs, polls human-readable progress, and proxies
protected result downloads.

Required Vercel environment values are documented in web/.env.example.

## Private Oracle trial

The same source runs without Vercel as user-level `udise-web.service`, binding
Next.js to `127.0.0.1:3010`. Tailscale Serve publishes only
`https://oracle-server.tail2b7fe2.ts.net:3010/`. The one-time session form
stays on the separately tailnet-only control API path at port `10000`; no public
Funnel is used.

The GUI follows `docs/flow.html`: Phase 1 session/roster, Phase 2 class scope,
Phase 3 GP, Phase 4 EP/Facility, and Phase 5 completion/finalize. These labels
are operator guidance only and do not make a write stage executable.

## Hermes

Source skill: hermes-vps/hermes-skill/udise-control/SKILL.md
Local helper: hermes-vps/tools/control_client.py

The skill maps natural-language requests to the same API. Missing finite choices
use the existing structured poll behavior. Cookies and API tokens must never be
requested or displayed in chat.

## Automatic promotion

hermes-vps/tools/promote_from_github.sh checks remote main in a temporary Git
worktree. It promotes only after offline suites and syntax checks pass.

The live repository is fast-forwarded only after successful verification, then
the API service is restarted. A dirty live worktree causes promotion to skip.

This is code promotion, not authorization for automatic UDISE portal writes.
