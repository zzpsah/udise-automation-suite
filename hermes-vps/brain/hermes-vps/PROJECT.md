# Hermes VPS Runner — Project

## What this is

A headless Linux/VPS command-line runner for UDISE+ SDMS school automation.
The sibling of the Colab notebook in the repository root: same portal
operations, no notebook, no browser UI.

**It is generic, not school-specific.** It works for any UDISE+ school. School
identity is discovered from the portal's own responses at runtime — no school
ID, name, or code is hardcoded in `udise_vps/`.

## Why it exists

The notebook needs Colab and a human clicking cells. This runs unattended on a
server, is diffable in Git, and is testable offline.

## Scope

| In scope | Out of scope |
|---|---|
| Roster export, completion overview | Any portal not UDISE+ SDMS |
| General Profile | Fee, exam, or attendance modules |
| Enrolment Profile (EP) | Timetable, library, transport |
| Facility Profile (FP) | |
| Finalize / Complete Data | |
| eShikshaKosh OTR report (as a data source) | |

## Evidence levels

Used throughout the docs. Never treat one as another.

| Label | Meaning |
|---|---|
| `IMPLEMENTED` | Code exists |
| `OFFLINE_TESTED` | Mocked/static tests only |
| `LIVE_READ` | Authenticated GET observed against the real portal |
| `LIVE_SAVE` | Reviewed write followed by a fresh matching read-back |

`HTTP 200` alone is **not** proof of a save.

## Two portals, one workflow

- **UDISE+ SDMS** (`sdms.udiseplus.gov.in`) — the system of record. Everything
  is written here.
- **eShikshaKosh Bihar** (`eshikshakosh.bihar.gov.in`) — **read-only** source of
  the Admission No. and, for Class XI, the Stream. Never written to.

## Entry points

- CLI: `udise-vps <command> --school <id>`
- Package: `udise_vps/`
- Operational one-offs: `tools/`

## Maintainers

See `HANDOFF.md`.
