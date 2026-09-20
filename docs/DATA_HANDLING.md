# Data handling rules

Keep this repository private. Never commit cookies, XSRF tokens, credentials, OTPs, CAPTCHA material, student exports, result reports, screenshots, or raw portal request/response bodies.

Store generated workbooks only in protected local or school-controlled storage. Review `git status` before every commit.

Logs should contain counts, row numbers, elapsed time, validation categories, and result classifications—not student data.

The school-account operator handles password, OTP, CAPTCHA, and the decision to enable a submission switch. A green completion indicator, tool completion, or HTTP `200` is not proof that UDISE saved a record.
