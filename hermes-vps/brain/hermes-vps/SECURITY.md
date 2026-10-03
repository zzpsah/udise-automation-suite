# Hermes VPS Runner — Security

## Credentials

Nothing is stored by this runner.

| Secret | How it is supplied |
|---|---|
| UDISE cookie header | `UDISE_COOKIE_HEADER` env var, per run |
| eShikshaKosh UDISE id | `ESHIKSHAKOSH_UDISE`, or `eshikshakosh.conf` |
| eShikshaKosh password | `ESHIKSHAKOSH_PASSWORD`, or `eshikshakosh.conf` |

`eshikshakosh.conf` is plaintext on disk. Prefer the environment variables.
Never commit it — `.gitignore` covers it.

**If a credential is ever pasted into a chat, a log, or a commit, treat it as
compromised and rotate it.** A cookie is a full session for the school's portal.

The desktop session bridge requires an explicit user click and restricts host
permissions to UDISE SDMS and the private Oracle tailnet host. It submits the
cookie only to a valid, short-lived `/session/{token}` request already visible
in the authenticated console. It must not add storage, logging, analytics,
broader host permissions, or a background upload path.

## Never commit

- Cookies, session IDs, CSRF tokens
- Passwords, OTPs, CAPTCHA material
- Student exports, completed workbooks, roster spreadsheets
- Raw API responses containing student data
- Screenshots of portal pages

`.gitignore` excludes `*.xlsx`, `*.csv`, `*.log`, `smoke-out/`, `.env`,
`xi_probe.json` (which contains real student names), and `__pycache__/`.

The repository root `RULES.md` §12 states this as project policy.

## Write safety

- **Write toggles are off by default.** Reads are safe; writes need `--submit`.
- **One student at a time** for first runs, each followed by a read-back.
- **A read-back mismatch stops the batch.** Never continue past an unconfirmed
  write.
- **Never blindly retry a POST** after a timeout or connection loss. Read back
  first to learn whether it landed. A retry can duplicate a write.
- `HTTP 200` and `status:true` are **not** proof. Only a matching read-back is.

## Blank-only semantics

A value the portal already holds is **never overwritten**. This is a safety
property, not an optimisation: it means a re-run cannot corrupt a corrected
record, and it makes the tool idempotent.

## Sentinel traps

Two of these caused real bugs and are now covered by regression tests.

| Field | Unset is reported as | Consequence if misread |
|---|---|---|
| `heightInCm`, `weightInKg` | numeric **`0`**, not null | A blank check testing only for `''` returns `False` for `0`, so **every blank height and weight is silently skipped** |
| `nccYn`, `nssYn`, `scoutsYn`, `olympdsNlc` | **`9`** | Read as a saved answer, so the flag is never set |
| `distanceFrmSchool`, `parentEducation` | `0` or `9` | Same |

Zero is "not set" for a measurement. Nine is "not applicable / never answered"
for a code field.

## Data handling

- Student data stays on the portal. Nothing is persisted locally except the
  optional completion workbook, which is gitignored.
- The eShikshaKosh integration is **read-only**. That portal is a data source,
  never a target.
- `xi_probe.json` holds real student names and is gitignored. If it is ever
  regenerated, keep it out of Git.

## Approval boundary

Bulk portal mutations require explicit user approval. The `tools/` scripts that
write to the portal are operational, not routine — run them deliberately, with
the class scope named, and check the output.

## Reporting a problem

If a write is reported as successful but a read-back disagrees, **stop**. Record
the student id, the field, what was sent, and what came back. Do not retry until
the discrepancy is understood — the portal may have partially applied the write.

## Control-plane security

- The API bearer token is generated locally and never committed.
- UDISE Cookie material is accepted only by a high-entropy one-time form and is
  kept in the user runtime directory, not durable project state.
- Vercel never receives the UDISE Cookie.
- Raw per-student progress is not exposed to the web UI.
- The current control API rejects all write stages.
- Public exposure must target only the control API listener, not unrelated
  Oracle/Hermes services.
