# Hermes VPS Runner — Commands

## Setup

```bash
cd hermes-vps
./install.sh
./run_tests.sh                 # 110 tests, no network
```

## Session

Every live command needs a cookie header copied from the browser's Network tab:

```bash
export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...; NSC_tent...'
```

Reads are safe. Writes need `--submit`.

## Read-only

```bash
# roster
udise-vps students --school <id>

# completion overview workbook
udise-vps completion --school <id> --class IX

# all students: Students, GP, EP, Facility, Completion and Issues sheets
udise-vps snapshot --school <id>

# preview EP changes — sends nothing
udise-vps ep --school <id> --class IX

# preview EP with admission numbers from the OTR report
udise-vps ep --school <id> --class IX --report Student_OTR_Report.xlsx

# fetch the OTR report live, then preview
udise-vps ep --school <id> --class IX --fetch-report --year 2026-27

# preview Facility changes
udise-vps facility --school <id> --class IX
```

## Writing

```bash
# one student first — always
udise-vps ep --school <id> --class IX --report otr.xlsx --limit 1 --submit

# then the class
udise-vps ep --school <id> --class IX --report otr.xlsx --submit

udise-vps facility --school <id> --class IX --submit
```

Every write is followed by a fresh read-back. A mismatch stops the batch.

## Class XI

```bash
# stream comes from the OTR report
udise-vps ep --school <id> --class XI --fetch-report --submit

# prompt for students the report has no row for
udise-vps ep --school <id> --class XI --fetch-report --ask-stream --submit

# force one stream for every unresolved student
udise-vps ep --school <id> --class XI --fetch-report --stream Science --submit
```

**Class XI/XII EP is currently refused by the portal** (error `1002`). It fails
fast rather than looping. Admission numbers and streams still resolve.

## Operational tools

These live in `tools/` and are run deliberately, not routinely.

```bash
# finalize a class (Complete Data). Dry run unless FIN_ALLOW=1.
FIN_CLASS=9 python3 tools/finalize_class.py
FIN_CLASS=9 FIN_ALLOW=1 python3 tools/finalize_class.py
FIN_CLASS=9 FIN_ONLY='ANSHU KUMARI' FIN_ALLOW=1 python3 tools/finalize_class.py

# write EP for a batch of N
BATCH_SIZE=5 python3 tools/write_batch.py

# write Facility for a class
FP_CLASS=9 python3 tools/write_facility.py

# preview which students the new rules would touch
python3 tools/preview_rules.py

# probe what subject codes a class actually holds (read-only)
python3 tools/probe_xi_codes.py
```

## eShikshaKosh credentials

```bash
export ESHIKSHAKOSH_UDISE='...'
export ESHIKSHAKOSH_PASSWORD='...'
```

Or a `eshikshakosh.conf` file:

```ini
[eshikshakosh]
udise = <school udise>
password = <password>
year = 2026-27
```

Prefer the environment variables — the file is plaintext on disk.

## Checks before committing

```bash
./run_tests.sh
python3 -m py_compile udise_vps/*.py tests/*.py tools/*.py
bash -n install.sh smoke_readonly.sh run_tests.sh
git diff --check
```

## Troubleshooting

**`check-session` returns HTML instead of JSON** — that is the SPA shell, which
means the session has expired. Paste a fresh cookie.

**A read times out** — the portal is intermittently slow. Use generous timeouts
and avoid concurrency; eight parallel reads caused a timeout in practice.

**A read-back reports a mismatch on a Facility write** — check the sentinel
handling. Unset measurements are `0`, unanswered flags are `9`; both must
normalise before comparison.

**Class XI EP returns `1002`** — expected. Server-side configuration gap. Do not
retry.
