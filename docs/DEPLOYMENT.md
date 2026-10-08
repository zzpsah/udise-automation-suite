# Deployment and Hosting

## GitHub

Repository: `zzpsah/udise-automation-suite`
Branch: `main`
Oracle clone: `/home/prashant/projects/udise-automation-suite`

## Vercel

Project: `zzpsah/udise-automation-suite`
Production: `https://udise-auto.vercel.app/`
Root Directory: `hermes-vps/web`

Deploy from repo root:

```bash
cd /home/prashant/projects/udise-automation-suite
npx --yes vercel@latest deploy --prod --yes --scope zzpsah
```

Do not deploy from inside `hermes-vps/web` when the Vercel Root Directory is already configured there.

## Oracle

Control API:
- service `udise-control-api.service`
- bind `127.0.0.1:9135`
- working directory `/home/prashant/projects/udise-automation-suite/hermes-vps`
- exec `.venv/bin/uvicorn control_api.app:app --host 127.0.0.1 --port 9135`

Local web:
- service `udise-web.service`
- bind `127.0.0.1:3010`

Known host:
`oracle-server.tail2b7fe2.ts.net`

Historically:
- private web via Tailscale Serve on `3010`
- Vercel→Oracle control path via dedicated HTTPS/Funnel configuration, historically `10000`

Authoritative control URL is `UDISE_ORACLE_API_URL`; do not hard-code it in browser code.

## Environment variables

Server-side:
- `UDISE_ORACLE_API_URL`
- `UDISE_CONTROL_TOKEN`
- `UDISE_SCHOOL_PRESETS_JSON` where retained for fallback/display

Never commit values.

## Restart

```bash
UIDN=$(id -u)
export XDG_RUNTIME_DIR=/run/user/$UIDN
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UIDN/bus
systemctl --user restart udise-control-api.service udise-web.service
systemctl --user is-active udise-control-api.service
systemctl --user is-active udise-web.service
```

## Verification

```bash
cd /home/prashant/projects/udise-automation-suite/hermes-vps
.venv/bin/python -m py_compile control_api/app.py udise_vps/*.py
npm --prefix web run build
cd ..
git diff --check
```

Distinguish Git push, Oracle restart, Vercel Ready, alias update and live verification.


## Deployment verification record — 8 October 2026

- Latest synchronized documentation/code head: `a6bd1d0`.
- Vercel project linkage in `hermes-vps/web/.vercel/project.json` points to project `udise-automation-suite`.
- Production URL returns HTTP 200, but a production-content check previously showed that the earlier `1735ec27` UI styling change was not yet present in the served production CSS.
- A `x-vercel-cache: HIT` response is not, by itself, proof that the latest Git commit is deployed.
- After documentation commits are pushed, verify the new production build by checking both the Vercel deployment state and a production-content marker. Do not call deployment complete merely because the URL returns 200.

### Deployment acceptance

```text
GitHub main updated
→ Vercel deployment triggered
→ Build succeeds / Ready
→ production alias points to new deployment
→ production marker/content matches current commit
→ live smoke test
```

If Git→Vercel does not trigger, use the documented repo-root Vercel command. Do not create a second deployment project or change the production alias without review.
