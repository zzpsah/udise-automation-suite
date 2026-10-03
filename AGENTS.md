# Project AI Entry Point

This repository is managed by ChatGPT Development OS (DevOS).

Before substantial work:

1. Read `DEVOS.md`.
2. Read `PRD.md`, `RULES.md`, and `TASKS.md`.
3. Read `docs/AI_HANDOFF.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `docs/TEST_PLAN.md`, `docs/SECURITY.md`, `docs/DECISIONS.md`, and `docs/MEMORY.md`.
4. Read `.ai/PROJECT.md`, `.ai/CURRENT-STATE.md`, `.ai/ARCHITECTURE.md`, `.ai/DECISIONS.md`, and `.ai/TASKS.md`.
5. Inspect the maintained notebook, current source, and Git history before changing behavior.
6. Distinguish implemented, offline-tested, live-read, and live-save evidence.

## Two implementations

| | Path | Interface |
|---|---|---|
| Colab notebook | `UDISE_Automation_v2.7.3_*.ipynb` | Interactive |
| Headless runner | `hermes-vps/` | Command line |

The runner has its own context layer under `hermes-vps/brain/`. Read
`hermes-vps/brain/hermes-vps/HANDOFF.md` before changing it. Neither
implementation is school-specific — school identity comes from the portal at
runtime, so do not hardcode a school ID, name, or code.

## DevOS Vibe Coding baseline

```text
READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION
```

## Safety

- Keep write toggles off by default.
- Never blindly retry POST requests after an ambiguous failure; fresh read-back comes first.
- Do not invent student data, measurements, status meanings, or XI/XII portal contracts.
- No production deployment or consequential bulk portal mutation without explicit user approval.
- Never commit credentials, cookies, OTP/CAPTCHA material, student exports, screenshots, completed workbooks, or private student data.
