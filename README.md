# UDISE Automation Suite

This private repository is the **single source of truth** for the UDISE+ automation project. It contains one maintained Google Colab notebook:

- `UDISE_Automation_Enhanced_v1.2.11_2026-09-23.ipynb`

The previous v1.2.5–v1.2.10 notebooks remain in the repository as rollback copies; use v1.2.11 for the current workflow.

Do not create parallel notebooks for fixes or experiments. Make changes in this notebook, test them safely, and use Git history to track versions.

## Open in Colab

[Open build v1.2.11 in Google Colab](https://colab.research.google.com/github/zzpsah/udise-automation-suite/blob/main/UDISE_Automation_Enhanced_v1.2.11_2026-09-23.ipynb)

Build v1.2.11 retries timed-out read-only Facility and CWSN submission pre-checks once; if they remain unavailable, no save is sent. It also removes an unnecessary leading semicolon from the result detail. POST requests are never automatically retried.

Build v1.2.10 retries timed-out read-only Facility export requests once after a short pause, identifies whether Facility details or CWSN status failed, and prominently warns when the workbook is incomplete. Submission POST behavior is unchanged; it is never automatically retried.

Build v1.2.9 shows a persistent text percentage bar and included/failed counts during Facility export, even when the notebook progress widget is not displayed. The Facility request behavior and timeouts are unchanged.

Build v1.2.8 removes manual UDISE-code and school-name fields from Detect School. Paste the school URL or its 7-digit internal ID; the confirmed school identity is displayed automatically when available.

Build v1.2.7 retains the working v1.2.5 workflow and Detect School behavior. Facility export prefills unanswered Yes/No fields as No, unanswered distance as `2 - Between 1-3 Kms`, and missing Parent/Guardian Education as `3 - Secondary or Equivalent`; saved values and measurements remain unchanged. Facility export reads the portal; upload validation checks the Excel sheet only and sends no portal request. The separate reviewed submission cell performs the save and read-back check. Code cells appear as Colab forms by default. Live Facility saving has not been verified.

Build v1.2.1 adds conditional Facility benefit dropdowns, protected non-CWSN cells based on current General Profile, and measurement input messages/range checks. Generate a fresh Facility export to obtain these controls. Enter actual height and weight; no random or gender-based values are generated.

Build v1.2.0 adds Facility Profile after Enrollment: class selection, prefilled Excel with dropdowns, conditional validation, reviewed submission, progress and fresh read-back. Existing enrollment cells are retained. Facility API/field discovery was performed in the authenticated portal; Facility submission has passed mocked tests but has not been live-tested. See [Facility Profile](docs/FACILITY_PROFILE.md).

Build v1.1.4 adds one enrollment class selector to the working v1.1.3 flow. In **Load IX/X subject rules**, choose **IX**, **X**, or **IX and X**, then run that cell. Export, validation and submission use this selection. To switch class, rerun that cell and validate the corresponding workbook again. Export filenames show the selected class. The working payload, heartbeats, timeouts and read-back behavior are retained.

The user supplied a v1.1.3 run log showing three already-current records and one successful update confirmed by response and fresh read-back. This is user-reported live evidence. v1.1.4 passed offline selection checks and four mocked submission regression tests; its Colab dropdown appearance and live submission have not been independently tested.

**Next development: Class XI/XII enrollment.** Their streams, subjects and form requirements need separate discovery and implementation. They are not enabled in this release.

Because the repository is private, Colab may ask to read your private GitHub repositories.

## What the notebook does

1. Authenticates from a manually supplied active UDISE browser Cookie header, retained in the Colab runtime only.
2. Detects the school ID from a UDISE school URL.
3. Fetches and indexes the current academic-session roster with verbose progress.
4. Exports and validates General Profile workbooks.
5. Exports and validates Class IX/X Enrollment Profile workbooks using live UDISE subject rules.
6. Provides separately gated submission cells, disabled by default.

## Enrollment Profile status

The IX/X module supports live dropdown rules, Subjects 1–6 as required, Subjects 7–8 as optional, clean Excel export, local validation, five-minute profile requests, a one-record initial test, and server read-back after an ambiguous save response.

An HTTP `200` alone is not treated as a saved record. The portal must report success, or server read-back must match the submitted values.

## Safe development workflow

1. Work on `main` in this repository.
2. Make one documented change in the notebook.
3. Run setup, authentication, school detection, rule loading, and export/validation before any write test.
4. Keep submission toggles off until a reviewed one-record test is explicitly intended.
5. Commit the reason, verification evidence, and remaining unknowns.

Read the detailed guides before changing an API call or submission payload:

- [Architecture](docs/ARCHITECTURE.md)
- [Portal discovery and API evidence](docs/PORTAL_DISCOVERY.md)
- [AI browser navigation and information retrieval](docs/AI_BROWSER_RETRIEVAL.md)
- [Colab runbook](docs/COLAB_RUNBOOK.md)
- [Data handling rules](docs/DATA_HANDLING.md)

## Never commit

- browser cookies, session IDs, XSRF tokens, passwords, OTPs, or CAPTCHA material;
- student exports, result files, screenshots, or raw API responses;
- `.env` files or credentials; or
- completed notebook outputs containing student data.
