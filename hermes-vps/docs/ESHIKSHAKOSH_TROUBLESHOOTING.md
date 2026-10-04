# eShikshaKosh export troubleshooting

## Current verified finding (2026-10-04)

The Oracle Playwright exporter reaches the eShikshaKosh login page, reads the
arithmetic CAPTCHA, solves it, and submits the login form. The portal responds
with:

```text
POST /auth/login
HTTP 422
Invalid userId/Password.
```

The browser remains on `/login` and no token, localStorage value, or cookie is
created. Therefore the failure occurs before report export or student-list
retrieval. This is an invalid/expired credential result, not an Excel or UDISE
session failure.

## Retry sequence

1. Open the eShikshaKosh Report tile in the GUI.
2. Replace the saved eShikshaKosh UDISE code and password.
3. Save the credentials temporarily.
4. Run **Download eShikshaKosh report** again.
5. Record login success, report rows, matched rows, and download output as
   separate evidence.

Do not send passwords through WhatsApp or commit them to Git.

## Runtime requirements

The Oracle Hermes virtual environment must include `nest-asyncio` and
`playwright`; both are declared in `hermes-vps/requirements.txt`. The
maintained script is outside this repository at:

```text
~/projects/eshikshakosh-automation/local-script/esk_otr_api.py
```

The exporter also performs post-login token discovery from nested response
fields, browser storage, and cookies to tolerate portal response-shape drift.
