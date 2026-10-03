# Hermes VPS Runner — Tests

## Running

```bash
cd hermes-vps
./run_tests.sh
```

144 tests, **no network and no credentials required**. Runs in about two
seconds. Individual suites:

```bash
python3 tests/test_offline.py          # 24 — core: session, constants, students
python3 tests/test_ep_facility.py      # 68 — Enrolment Profile + Facility rules
python3 tests/test_esk.py              #  8 — eShikshaKosh report source
python3 tests/test_facility.py         # 10 — Facility blank-detection, sentinels
python3 tests/test_general_profile.py  # 27 — GP blank-fill, cross-field rules, mother tongue
```

## What is covered

### Cross-portal matching

- class mismatch does **not** block a match (the regression that lost 62 matches)
- Aadhaar last-4 conflict **does** block — the one hard rule
- Aadhaar agreement outweighs a DOB conflict
- a DOB conflict alone does not block an exact name + father match
- same-class breaks a tie; a genuine tie reports `ambiguous`, never guesses
- transliterated father names match via a shared token
  (`JAMALUDDIN ANSARI` vs `MD ZAMAL ANSARI`)
- initials cannot manufacture a match (`MD` vs `MD`)
- DOB alone, with no name/father/Aadhaar agreement, is not a match

### Admission numbering

- a saved value is never overwritten
- a report match beats a roll number; a roll number beats generation
- generated values continue after the class's highest (`0034` after `33`)
- generation is zero-padded 4-wide
- classes do not consume each other's sequence
- `142025` parses as `14/2025` (a lost separator), not as the number 142025
- `Class 11` / `Class 12` / `XI` / `XII` all map — missing these dropped 153
  report rows
- `XI` is not read as `X`

### Enrolment rules

- Muslim students get `638` URDU + `1102` HIN (NLH); others `629` + `637`
- mandatory subjects 3–6 are filled when blank
- valid exam-result codes are **1, 3, 4** — not 1, 2, 3
- an invalid exam result triggers the auto `None/Not Studying` rule
- the auto rule can be disabled and reports for manual review instead
- status 4 sends `null` for the four dependent fields, never `0/0/4/0`
- the stored sentinels `99/0/999/0` compare equal to the `null` we sent

### Streams

- UDISE direction is pinned: `1=Science`, `2=Arts` (the opposite of eShikshaKosh)
- both portals' labels map to canonical names
- a saved stream is never overwritten
- a report row supplies the stream
- with no report row the operator is asked
- a nonsense prompt answer is rejected, not written

### Facility

- `0` reads as unset for measurements — the bug that skipped every blank height
  and weight
- `9` reads as unanswered for Yes/No flags
- blank height/weight produce an update in the documented ranges
- saved measurements are never overwritten
- distance is only ever `2` (1–3 km) or `3` (3–5 km), and actually varies
- a saved distance is kept
- CWSN facility fields are skipped for non-CWSN students

### General Profile

- `0` reads as unset for a code field
- a blank blood group fills with **Under Investigation** (9); code `0` is clamped
  to 9 because the API rejects it
- a filled blood group is never included in updates
- BPL = No forces AAY = Not Applicable (9)
- BPL = Yes with an invalid AAY becomes No (2)
- SC/ST/OBC can never be EWS
- **the AAY and EWS rules skip a field the portal already holds** — the
  blank-only rule applies to cross-field rules too
- a fully filled GP record proposes no updates at all
- mother tongue: default is 42, both 42 and 28 are offered, the pick is seeded
  and reproducible, and a filled value (28/42/144/20) is always skipped
- the payload carries every untouched field, so nothing is silently dropped

### eShikshaKosh report source

- `eshikshakosh.conf` parses; missing, malformed, and half-filled files return
  an empty result rather than raising
- a missing credential produces an actionable error, not a stack trace
- the export invokes the bundled script with the right arguments
- a script failure surfaces the real login error
- a missing script points the user at `--report`

## What is NOT covered

- **No live network tests.** Everything is offline by design, so the suite is
  safe to run anywhere and cannot touch a real portal.
- **No test of a real portal write.** Writes are verified in operation by
  read-back, not by the test suite. The tests cover payload construction and
  comparison logic.
- **The GP payload's required field set is not asserted.** The 34-field shape
  was found empirically; a test pins the identity fields being present, but not
  that the portal accepts them. Re-verify live if the portal changes.
- **General Profile write path** — never exercised live, so untested.

## Adding a test

Put it in the suite that owns the behaviour. Every bug fixed in this codebase
got a named regression test with a comment saying what it cost. Keep doing that
— the comment is what stops someone reintroducing it.

```python
def test_something_that_broke_once():
    """REGRESSION: what went wrong and what it cost."""
    ...
    print("PASS test_something_that_broke_once")
```
