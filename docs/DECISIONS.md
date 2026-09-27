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

## Planned AUTO EP
First source mode is uploaded e-ShikshaKosh data. Matching remains storage-independent so later adapters may reuse the same normalized schema.
