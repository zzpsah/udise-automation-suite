# Security and Data Handling

## Authority boundary

The public Vercel UI is not the authority boundary. Oracle control API + protected runtime session store are.

## Never commit

- UDISE password
- eShikshaKosh password
- bearer token
- JSESSIONID
- XSRF-TOKEN
- OAuth/login transaction secrets
- live CAPTCHA
- encrypted env values
- raw student API dumps
- private result workbooks

## Browser login

Username/password/CAPTCHA are forwarded for one live login attempt.

Project code does not intentionally persist the password.

## Vercel

Browser must never receive `UDISE_CONTROL_TOKEN`.

`hermes-vps/web/app/lib.ts` adds it server-side.

## Student privacy

Do not commit full Aadhaar, raw student dumps, private workbooks or screenshots with student data.

## Write safety

No blind POST retry.

A write is successful only after fresh read-back verifies persistence.

## Fallback bridge

The one-time fallback session bridge must remain short-lived, opaque-token based, protected and non-logging.

## Temporary eShikshaKosh credential lifecycle

eShikshaKosh passwords are temporary runtime material:
- login is verified against the official portal before the UI may display Connected;
- credentials are bound to the current UDISE session;
- the password is passed to the maintained exporter through the child-process environment, not command-line arguments;
- after a successful live source fetch, the password record is deleted;
- the generated workbook, not the password, is retained as the EP source for the preview/approved write.

## UDISE heartbeat

A local TTL must never be treated as proof of a live portal session. Heartbeats call the real /p0/check-session endpoint. Local expiry is extended only after a successful portal check.
