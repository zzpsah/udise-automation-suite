# UDISE Automation Suite

This private repository is the **single source of truth** for the UDISE+ automation project. It contains one maintained Google Colab notebook:

- `UDISE_Automation_Enhanced_v1.1.0_2026-09-20.ipynb`

Do not create parallel notebooks for fixes or experiments. Make changes in this notebook, test them safely, and use Git history to track versions.

## Open in Colab

[Open build v1.1.0 in Google Colab](https://colab.research.google.com/github/zzpsah/udise-automation-suite/blob/main/UDISE_Automation_Enhanced_v1.1.0_2026-09-20.ipynb)

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
