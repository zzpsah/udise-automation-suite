# Hermes VPS version

A Linux/VPS command-line runner for UDISE+ SDMS school automation.

This is the **headless** sibling of the Colab notebook: same portal operations,
no notebook, no browser UI. It runs on a server and is driven from the shell.

- **Full documentation:** [`README.md`](README.md)
- **Flow diagram:** [`docs/flow.html`](docs/flow.html) — open in a browser

## Layout

| Path | What it is |
|---|---|
| `udise_vps/` | The package — all portal logic |
| `tests/` | Offline test suites (110 tests, no network) |
| `tools/` | One-off operational scripts (previews, batch writers, probes) |
| `docs/flow.html` | Flow diagram |
| `run_tests.sh` | Runs every offline suite |
| `install.sh` | Dependency setup |
| `smoke_readonly.sh` | Read-only smoke test against the live portal |

## Quick start

```bash
./install.sh                 # dependencies
./run_tests.sh               # 110 offline tests, no credentials needed

export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...; NSC_tent...'
udise-vps students   --school 2497128              # roster (read-only)
udise-vps completion --school 2497128 --class IX   # completion overview
udise-vps ep         --school 2497128 --class IX --fetch-report   # preview
```

Writes are **off by default**. `--submit` enables them, one student at a time,
each followed by a fresh read-back. See `README.md` §5.

## Design rules

Carried from `RULES.md` at the repo root, and enforced in the code:

1. Preview first; write toggles off by default.
2. Never blindly retry a POST. Fresh read-back instead.
3. `HTTP 200` is not proof of a save — only a matching read-back is.
4. Never overwrite a value the portal already holds.
5. Never invent a measurement, identifier, or portal contract.

## Generic by design

No school ID, name, or code is hardcoded in `udise_vps/`. School identity comes
from the portal's own responses at runtime.

## Never commit

Cookies, passwords, OTPs, CAPTCHA material, student exports, completed
workbooks, or raw API responses containing student data. See `.gitignore` and
`RULES.md` §12.
