# Hermes VPS version

A Linux/VPS command-line runner for UDISE+ SDMS school automation.

This is the **headless** sibling of the Colab notebook: same portal operations,
no notebook, no browser UI. It runs on a server and is driven from the shell.

- **Full documentation:** [`README.md`](README.md)
- **Flow diagram:** [`docs/flow.html`](docs/flow.html) — open in a browser
- **Working context for contributors:** [`brain/`](brain/README.md)

## Layout

| Path | What it is |
|---|---|
| `udise_vps/` | The package — all portal logic |
| `tests/` | Offline test suites (138 tests, no network) |
| `tools/` | One-off operational scripts (previews, batch writers, probes) |
| `brain/` | Working notes — handoff, architecture, decisions, security |
| `docs/flow.html` | Flow diagram |
| `docs/COMMANDS.md` | Command reference |
| `docs/DESIGN.md` | Design principles |
| `docs/TEST_PLAN.md` | Layered test plan |
| `run_tests.sh` | Runs every offline suite |
| `install.sh` | Dependency setup |
| `smoke_readonly.sh` | Read-only smoke test against the live portal |

## Quick start

```bash
./install.sh                 # dependencies
./run_tests.sh               # 110 offline tests, no credentials needed

export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...; NSC_tent...'
udise-vps students   --school <id>              # roster (read-only)
udise-vps completion --school <id> --class IX   # completion overview
udise-vps ep         --school <id> --class IX --fetch-report   # preview
```

Writes are **off by default**. `--submit` enables them, one student at a time,
each followed by a fresh read-back. See `README.md` §5.

## New here?

Read [`brain/hermes-vps/HANDOFF.md`](brain/hermes-vps/HANDOFF.md) first. Then
[`brain/hermes-vps/ARCHITECTURE.md`](brain/hermes-vps/ARCHITECTURE.md) and
[`brain/hermes-vps/DECISIONS.md`](brain/hermes-vps/DECISIONS.md).

Three things worth knowing before you touch anything:

1. **Read-back is the only proof of a write.** `HTTP 200` and `status:true` are
   returned even for writes the portal silently rejects.
2. **A mismatch stops the batch.** Never continue past an unconfirmed write.
3. **Class XI/XII Enrolment is blocked by the portal** (error `1002`). Not a bug
   here — do not retry in a loop.

## Generic, not school-specific

This runs against **any** UDISE+ school. No school ID, name, or code is
hardcoded in `udise_vps/` — identity comes from the portal at runtime. The
examples above take `--school <id>` for that reason.

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
