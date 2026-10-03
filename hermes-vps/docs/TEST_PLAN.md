# Hermes VPS Runner — Test Plan

## Objective

Prove the runner does what it claims, without touching a live portal during
routine checks, and without ever reporting a write as successful on evidence
that does not support it.

## Evidence levels

| Label | Meaning | How established |
|---|---|---|
| `IMPLEMENTED` | Code exists | Reading it |
| `OFFLINE_TESTED` | Behaviour pinned by tests | `./run_tests.sh` |
| `LIVE_READ` | Authenticated GET observed | A read against the real portal |
| `LIVE_SAVE` | Write persisted | A POST followed by a matching fresh read-back |

Never promote one to another. `HTTP 200` is not `LIVE_SAVE`.

## Layer 1 — offline (automated, always run)

`./run_tests.sh` — 110 tests, no network, no credentials, ~2s.

Covers: cross-portal matching and its scoring, admission-number priority and
parsing, language plans, exam-result validity, the status-4 null rule, sentinel
normalisation, stream direction, Facility blank-detection and ranges,
eShikshaKosh credential and export handling.

A bug fixed here gets a named regression test whose docstring says what it cost.
That comment is what stops it coming back.

## Layer 2 — read-only live

Confirms the session and the read contracts. Changes nothing.

```bash
export UDISE_COOKIE_HEADER='...'
udise-vps students   --school <id>
udise-vps completion --school <id> --class IX
udise-vps ep         --school <id> --class IX            # preview, sends nothing
udise-vps facility   --school <id> --class IX            # preview
```

Pass criteria: the roster count matches the portal; previews list only blank
fields; nothing is sent.

## Layer 3 — bounded live write

**One student.** Not one class.

```bash
udise-vps ep --school <id> --class IX --report otr.xlsx --limit 1 --submit
```

Pass criteria:

1. the POST returns `status: true` **and**
2. a fresh GET shows every written field matching what was sent

Only then widen the scope. If step 2 fails, stop — the write contract is not
understood yet.

## Layer 4 — class scope

```bash
udise-vps ep       --school <id> --class IX --report otr.xlsx --submit
udise-vps facility --school <id> --class IX --submit
```

Pass criteria: every student confirmed by read-back, or the batch stops on the
first failure with the cause named.

## Layer 5 — finalize

```bash
FIN_CLASS=9 python3 tools/finalize_class.py            # dry run
FIN_CLASS=9 FIN_ALLOW=1 python3 tools/finalize_class.py
```

Pass criteria: only `formStatus=3` students are submitted; read-back shows `6`;
`6` and `1/2` students are skipped untouched.

## Layer 6 — independent verification

Do not trust the batch summary. Re-read the class and count.

```bash
python3 - <<'EOF'
# read every student's formStatus fresh and count the 6s
EOF
```

The Class IX result was established this way: a per-student read of all 33,
not the writer's own report.

## Negative tests (must be done deliberately)

| Scenario | Expected |
|---|---|
| Expired cookie | Clear "session expired" message, no writes attempted |
| Read-back mismatch | Batch **stops**, cause named |
| Class XI EP | Portal error `1002` surfaced, no retry loop |
| `--report` file missing | Clear error, nothing sent |
| No eShikshaKosh credentials | Actionable message pointing at the alternatives |
| Duplicate PEN in report | `ambiguous` — reported, never guessed |

## What this plan does not cover

- No live test runs in CI. All automated tests are offline by design.
- General Profile write path — never exercised live.
- Class XI/XII EP — blocked by the portal, cannot be tested until it is enabled.

## Regression log

Bugs found in operation, each now pinned by a test:

| Bug | Cost if unnoticed |
|---|---|
| Blank check missed numeric `0` | Every blank height and weight skipped, silently |
| `9` read as a saved Yes/No | Flags never set on the whole roster |
| Class required for a match | All 62 Class XI matches lost |
| DOB conflict vetoed a match | Real students unmatched (no Aadhaar in the report) |
| `142025` parsed as the number | Class sequence poisoned to `142026` |
| `Class 11`/`XII` unmapped | 153 report rows silently discarded |
| Exam-result codes `1,2,3` | Wrong values written to government records |
| Stream codes reused raw | Arts and Science swapped |
