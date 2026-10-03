# brain/ — working context for the Hermes VPS runner

Read these before changing anything. Start with `HANDOFF.md`.

| File | What it is |
|---|---|
| [`hermes-vps/HANDOFF.md`](hermes-vps/HANDOFF.md) | **Start here.** Resume sequence, safe checks, sharp edges, known unknowns |
| [`hermes-vps/PROJECT.md`](hermes-vps/PROJECT.md) | What this is, scope, evidence levels |
| [`hermes-vps/CURRENT_STATE.md`](hermes-vps/CURRENT_STATE.md) | Verified state, open work, per-class numbers |
| [`hermes-vps/ARCHITECTURE.md`](hermes-vps/ARCHITECTURE.md) | Layering, the write contract, module responsibilities |
| [`hermes-vps/DECISIONS.md`](hermes-vps/DECISIONS.md) | Why things are the way they are — each a choice that was not obvious |
| [`hermes-vps/SECURITY.md`](hermes-vps/SECURITY.md) | Credentials, write safety, sentinel traps, approval boundary |
| [`hermes-vps/TESTS.md`](hermes-vps/TESTS.md) | What the 110 tests cover, and what they do not |
| [`hermes-vps/TASKS.md`](hermes-vps/TASKS.md) | Done, next, blocked, backlog |

## The three things worth knowing first

1. **Read-back is the only proof of a write.** `HTTP 200` and `status:true` are
   returned even for writes the portal silently rejects.
2. **A mismatch stops the batch.** Never continue past an unconfirmed write.
3. **Class XI/XII Enrolment is blocked by the portal** (error `1002`). Not a bug
   here. Do not retry in a loop.

## Related documentation

- [`../README.md`](../README.md) — full user documentation
- [`../docs/flow.html`](../docs/flow.html) — the flow, visually
- [`../docs/COMMANDS.md`](../docs/COMMANDS.md) — command reference
- [`../docs/DESIGN.md`](../docs/DESIGN.md) — design principles
- [`../docs/TEST_PLAN.md`](../docs/TEST_PLAN.md) — the layered test plan
- [`../../DEVOS.md`](../../DEVOS.md), [`../../RULES.md`](../../RULES.md),
  [`../../AGENTS.md`](../../AGENTS.md) — repo-level governance
