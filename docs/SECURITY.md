# Security and Data Handling

- Credentials, cookies, session IDs, XSRF/JSESSIONID values, passwords, OTPs, CAPTCHA material, student exports, screenshots, raw student API responses, and completed result workbooks must not be committed.
- Keep secrets runtime-only.
- Use real student data only in an explicitly reviewed authorized test.
- Do not fabricate official values to satisfy portal validation.
- Write operations require explicit enablement.
- Read-only discovery may be automated; consequential writes remain review-gated.
- Never blindly retry POST requests.
- Stop on selector/schema uncertainty or unconfirmed write state.
- No production deployment or bulk portal mutation without explicit user approval.
