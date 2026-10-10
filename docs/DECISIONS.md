# Decisions

## 2026-09-23 — v2.7.3 maintained baseline
Use `UDISE_Automation_v2.7.3_2026-09-23.ipynb` as the maintained notebook until a successor is reviewed and promoted.

## 2026-09-23 — Preview-first writes
Keep write toggles disabled by default. A write is successful only after application/read-back confirmation.

## 2026-09-23 — No blind POST retry
After timeout/connection loss, re-read before deciding whether any retry is safe.

## 2026-09-23 — Status model
Treat `0 -> 1 -> 2 -> 3 -> 6` as project-observed behavior, not an official UDISE enum. Do not invent meanings for other codes.

## 2026-09-23 — CWSN safety
If fresh GP has CWSN=Yes, skip AUTO GP completely and require manual review.

## 2026-09-27 — Vibe Coding as DevOS baseline
All substantial changes follow READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION.

## 2026-10-03 — Preview-bound control-plane approval
The GUI may create a write job only from one completed, unexpired preview. The
operator must choose a write cap, acknowledge fresh read-back, and type the
stage/class confirmation phrase. One preview can authorize at most one write
job. Direct non-preview job creation remains rejected, and deployment never
executes a portal write automatically.

## Planned AUTO EP
First source mode is uploaded e-ShikshaKosh data. Matching remains storage-independent so later adapters may reuse the same normalized schema.

## 2026-10-10 — Human-readable skipped outcomes
The activity UI is for school staff, not developers. Show a concise `SKIPPED` status, a specific plain-language reason, and an action only when it adds useful information. Remove generic “Preview if you expected a change” instructions. Do not collapse “not in approved plan” into “no change required.” Approved-plan gates and truthful no-write reporting remain mandatory.

## 2026-10-10 — School-confirmed Indian nationality correction
For this school, the operator confirms all enrolled students are Indian nationals. GP may propose explicit `natIndYN=2` (No) -> `natIndYN=1` (Yes); blank defaults to Yes. Preserve existing Yes and do not silently rewrite unknown codes or unrelated populated fields. Implementation and tests are on PR #10; until merge and production verification, this is not considered deployed.
