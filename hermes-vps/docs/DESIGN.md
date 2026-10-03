# Hermes VPS Runner — Design

## Principles

**Blank-only.** A value the portal already holds is never overwritten. This
makes the tool safe to re-run and means a corrected record cannot be undone by
a later pass.

**Verify, never assume.** `HTTP 200` is not proof of a save. Only a fresh
read-back that matches is.

**Stop on doubt.** A mismatch halts the batch. Better to stop at record 3 than
to write 30 more on a broken contract.

**Preview first.** Write toggles are off by default. You see exactly what would
change before anything is sent.

**Generic.** No school identity in the package. Same code, any school.

## What it is not

- Not a daemon. It is a CLI you run deliberately.
- Not a database. State lives on the portal.
- Not a credential store. Sessions are runtime-only.
- Not a scraper. It uses the portal's own JSON API.

## The four-step write

```
1. fresh GET      → learn what the portal holds
2. diff           → compute blank-only updates
3. one POST       → never retried
4. fresh GET      → compare every written field
```

A mismatch at step 4 stops everything.

## Why a CLI and not more notebook

The notebook needs Colab and a human clicking cells. This runs on a server, is
diffable in Git, and is testable offline. Both exist because they suit different
situations: the notebook for interactive work, this for anything repeatable.

## Reading order for a new maintainer

1. `brain/hermes-vps/HANDOFF.md` — where to start
2. `brain/hermes-vps/PROJECT.md` — what this is
3. `brain/hermes-vps/ARCHITECTURE.md` — how it fits together
4. `brain/hermes-vps/DECISIONS.md` — why it is this way
5. `docs/flow.html` — the flow, visually
6. `brain/hermes-vps/SECURITY.md` — before touching a write path

## Naming

- Commands are verbs: `students`, `completion`, `ep`, `facility`, `finalize`.
- Result dataclasses carry `status`, `detail`, and a `confirmed` property.
- A `status` beginning `SKIPPED_` means nothing was sent, by design.
- Sources in admission numbering are named for where the value came from:
  `kept_saved`, `eshikshakosh`, `roll_number`, `next_number`.

## Error handling

- Reads: bounded retries with backoff, then a clear error.
- Writes: one attempt, then read-back to learn what happened.
- A portal rejection surfaces the portal's own message and `errorFields`, not a
  generic failure.

## Documentation layers

| Layer | Purpose |
|---|---|
| Repo root (`DEVOS.md`, `RULES.md`, `docs/`) | The project as a whole |
| `hermes-vps/README.md` | Full user documentation |
| `hermes-vps/brain/` | Working notes for someone inside this runner |
| `hermes-vps/docs/` | Flow diagram and command reference |

`brain/HANDOFF.md` is the entry point for anyone picking this up.
