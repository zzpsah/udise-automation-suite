# DevOS Project Rule

This project is governed by the DevOS Vibe Coding Standard.

Canonical framework: `zzpsah/chatgpt-development-os`  
Canonical standard: `DEVOS-VIBE-CODING-STANDARD.md` in the DevOS repository.

## Required working loop

```text
READ → UNDERSTAND → PLAN → IMPLEMENT → TEST → REVIEW → FIX → COMMIT → UPDATE DOCUMENTATION
```

Before substantial work, recover this repository's current state from its existing source, Git history, README, AGENTS.md, `.ai/` context, and project documentation.

Maintain the following project-context layer where relevant:

```text
PRD.md
RULES.md
TASKS.md
README.md
.env.example
docs/ARCHITECTURE.md
docs/DESIGN.md
docs/TEST_PLAN.md
docs/SECURITY.md
docs/DECISIONS.md
docs/MEMORY.md
docs/COMMANDS.md
docs/HISTORY.md
```

Do not overwrite stronger existing documentation simply to match the template. Fill missing documents only from verified project evidence; mark unknowns instead of inventing facts.

## Non-negotiable guardrails

- No production deployment without explicit user approval.
- No secrets, passwords, API keys, tokens, cookies, OTPs, private keys, or secret environment values in Git.
- Keep private school documents and unnecessary student/personally identifying data out of Git.
- Prefer read-only/least-privilege workflows where possible.
- Do not make consequential portal/database/bulk-data changes without the established approval boundary.
- Do not claim completion without verification.
- After material work, update durable documentation so the next AI/session can recover what changed, why, how it was verified, and what remains.

## Remote access / Desktop Commander

For authorized Oracle VPS access, read [`docs/REMOTE-ACCESS.md`](docs/REMOTE-ACCESS.md). A new AI chat must use Desktop Commander `list_devices`, select the online `oracle-server`, ping it, and only then operate on the live server. Do not confuse GitHub access with VPS/runtime access.
