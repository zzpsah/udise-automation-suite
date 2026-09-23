# UDISE Automation Suite

This repository is the **single source of truth** for the UDISE+ automation project. The maintained Google Colab baseline is:

- `UDISE_Automation_v2.6_2026-09-23.ipynb`

Previous v1.2.5–v1.2.11 and v2.0 notebooks remain as rollback copies. v2.6 keeps the maintained v2.0 Login/School/Roster, GP, Enrollment and Facility workflow and adds the live-tested Class Completion Overview and guarded Finalize workflow.

Do not create parallel notebooks for fixes or experiments. Make changes in this notebook, test them safely, and use Git history to track versions.

## Open in Colab

[▶ Open v2.6 baseline in Google Colab](https://colab.research.google.com/github/zzpsah/udise-automation-suite/blob/main/UDISE_Automation_v2.6_2026-09-23.ipynb)



**v2.6 baseline — 23 September 2026:** adds Class Completion Overview with the observed project status progression `0 → 1 → 2 → 3 → 6`, exports separate readiness sheets, exposes only `formStatus=3` as `completion_ready_pens`, and adds AUTO / MANUAL / FILE Finalize modes with preview, fresh pre-write status verification, one-shot Complete Data POST, and fresh read-back. Bulk Completion Overview GETs use short safe retries; Finalize GETs use stronger retries. POST is never blindly retried. A live test successfully finalized a fresh `formStatus=3` student and confirmed `formStatus=6` by read-back. The status mapping is observed project behaviour, not an official published UDISE enum.

**v2.0 — 23 September 2026:** corrects the supplied file's Facility POST to `/p0/api/v2/AY/students/facility/{studentId}` while retaining its GET route; prints the portal result immediately; handles non-dictionary error details; turns measurement generation off by default; and embeds the full API reference in a final notebook section. Use real measurements. Six synthetic v2.0 tests cover syntax/routes, matching read-back, rejection visibility, POST timeout, precheck timeout and unchanged records. **Corrected live Facility saving remains unverified.** No portal submission is part of these offline tests.

[API reference and verified paths](docs/API_REFERENCE.md) records all core routes, field mappings, browser discovery steps, the observed failure, and the distinction between source evidence and live-save proof. The original supplied notebook is left unchanged in Downloads. Build v2.0 with `tools/release_v2.py SOURCE.ipynb`; the older `release_facility.py` generator does not reproduce this supplied-based release.

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
- [API reference and verified paths](docs/API_REFERENCE.md)
- [Portal discovery and API evidence](docs/PORTAL_DISCOVERY.md)
- [AI browser navigation and information retrieval](docs/AI_BROWSER_RETRIEVAL.md)
- [Colab runbook](docs/COLAB_RUNBOOK.md)
- [Data handling rules](docs/DATA_HANDLING.md)

## Never commit

- browser cookies, session IDs, XSRF tokens, passwords, OTPs, or CAPTCHA material;
- student exports, result files, screenshots, or raw API responses;
- `.env` files or credentials; or
- completed notebook outputs containing student data.
