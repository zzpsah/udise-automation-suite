# Hermes VPS Runner — Handoff

Resume here. Read this before changing anything.

## Resume sequence

1. Read `PROJECT.md`, `CURRENT_STATE.md`, `ARCHITECTURE.md`, `SECURITY.md`,
   `TESTS.md`, `TASKS.md` (all in this folder).
2. Read `../../RULES.md` and `../../DEVOS.md` at the repo root.
3. `git status --short` before any change.
4. Run `../../hermes-vps/run_tests.sh` — 110 tests, no network, ~2 seconds.
5. Distinguish implemented / offline-tested / live-read / live-save evidence.
   Never upgrade one to another without a fresh read-back.

## The one rule that matters most

**Never report a write as successful from the POST response.** `status:true` and
`HTTP 200` are not proof. Re-GET the record and compare normalised values. Every
write path in this package already does this — keep it that way.

## Safe checks

```bash
cd hermes-vps
./run_tests.sh                      # all offline suites
python3 -m py_compile udise_vps/*.py tests/*.py tools/*.py
bash -n install.sh smoke_readonly.sh run_tests.sh
python3 -m udise_vps.cli --help
git diff --check
```

Read-only live check (needs a cookie, changes nothing):

```bash
export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...; NSC_tent...'
python3 -m udise_vps.cli students --school <id>
```

## Before touching a write path

- Write toggles stay **off** by default. `--submit` enables them.
- Test on **one** student first, with a fresh read-back.
- A read-back mismatch must **stop the batch**. Do not continue.
- Never blindly retry a POST after a timeout — read back first.

## Where the sharp edges are

- **Class XI/XII EP is blocked server-side.** Error `1002`. Do not retry in a
  loop; the portal has no subject mapping configured. Details in
  `ARCHITECTURE.md`.
- **Facility sentinels.** Unset measurements are numeric `0`, not null;
  unanswered Yes/No is `9`. A naive blank check silently skips them. See
  `SECURITY.md` and the regression tests.
- **Streams are numbered oppositely** by the two portals. Translate by name.
- **Cross-portal matching** treats class and DOB as soft signals. Do not
  reintroduce them as hard filters — that cost 62 matches once.

## Known unknowns

- Whether Class XI/XII EP will accept the already-resolved admission numbers and
  streams once UDISE configures the subject mapping. Unknown until it does.
- The correct live subject-catalogue route. The one in the code is dead (404),
  so the verified static map is used. Not a guess, but not live either.
- General Profile write path has never been exercised live from this runner.

## Do not

- Implement a portal contract from a guess or from the notebook's tables — the
  notebook's enum tables are wrong in places this code has corrected.
- Commit credentials, cookies, student exports, or completed workbooks.
- Make bulk portal mutations without explicit user approval.
