# Troubleshooting

## Login connected but roster denied

Typical message:

`Action denied. You do not have permissions to update student data for students outside your region.`

Meaning: session is authenticated but requested internal school ID is outside the account region.

Fix:
- read `/p0/api/user`
- if `regionType=6`, use `userRegionId`
- do not silently reuse stale preset

## CAPTCHA

CAPTCHA must come from the same live Chromium page used for submission.

## False login success

Bootstrap cookies are not proof. Require `/p0/check-session == 200`.

## Vercel Root Directory error

Deploy from repository root, because project root is already `hermes-vps/web`.

## Roster HTTP 200 but status false

Log only safe diagnostics:
- HTTP status
- top-level keys
- message/error
- error ID

Never log cookies/tokens.

## EP error 1002

Portal Board/Class subject mapping unavailable. Do not loop retries.

## POST timeout

Never blindly replay. Fresh-read first.

## Stale UI

Verify:
1. GitHub commit
2. Vercel Ready
3. alias
4. live content

## Oracle services

```bash
UIDN=$(id -u)
export XDG_RUNTIME_DIR=/run/user/$UIDN
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$UIDN/bus
systemctl --user status udise-control-api.service
systemctl --user status udise-web.service
```
