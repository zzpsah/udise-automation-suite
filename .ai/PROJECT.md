# Project — UDISE Automation Suite

## Identity
- Canonical repository: `zzpsah/udise-automation-suite`
- Managed by: ChatGPT Development OS
- Maintained baseline: `UDISE_Automation_v2.7.3_2026-09-23.ipynb`
- Headless runner: `hermes-vps/` (see `hermes-vps/brain/`)

## Purpose
Authorized UDISE+ automation using a conservative workflow with read/preview
first, explicit write enablement, and fresh read-back.

Two implementations of the same portal operations:

| | Interface | Best for |
|---|---|---|
| `UDISE_Automation_v2.7.3_*.ipynb` | Colab notebook | Interactive, guided work |
| `hermes-vps/` | Command line | Repeatable runs on a server |

Both follow the same safety rules. Neither is school-specific: school identity
comes from the portal at runtime.

## Source of truth
Current source, Git history, README, `docs/AI_HANDOFF.md`, project docs, and
verified live evidence. Chat memory is supplementary only.
