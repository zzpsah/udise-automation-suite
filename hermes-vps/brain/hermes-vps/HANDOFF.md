# Hermes VPS Runner — Handoff

> **Start with `../../../docs/AI_HANDOFF.md`.**

## Resume sequence

1. Read `../../../docs/AI_HANDOFF.md`
2. Read `../../../docs/ARCHITECTURE.md`
3. Read `../../../docs/LOGIN_FLOW.md`
4. Read `../../../docs/WORKFLOW_ENGINE.md`
5. Read `../../../docs/DEPLOYMENT.md`
6. Read `CURRENT_STATE.md`
7. Run `git status --short`
8. Run tests/build before material changes

## Current production facts

- UI: `https://udise-auto.vercel.app/`
- Oracle project: `/home/prashant/projects/udise-automation-suite`
- API service: `udise-control-api.service`
- local web service: `udise-web.service`
- login is Playwright browser-backed
- OAuth client: `udise-sdms-g0`
- success requires `/p0/check-session == 200`
- school scope comes from authenticated SDMS context
- for school login `regionType=6`, `userRegionId` is internal school context
- Advanced existing-browser-session fallback remains available

## Safety rule

Never report a write successful from POST alone. Fresh-read and verify persistence. Never blindly retry an ambiguous POST.

## Never commit

Passwords, cookies, bearer tokens, CAPTCHA data, raw student dumps or private result workbooks.
