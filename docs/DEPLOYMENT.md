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
