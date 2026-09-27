# Decisions

## 2026-09-23 — v2.7.3 baseline
Keep `UDISE_Automation_v2.7.3_2026-09-23.ipynb` as the maintained notebook until a reviewed successor is promoted.

## 2026-09-23 — Preview-first writes
Writes remain disabled by default and must be confirmed by fresh read-back.

## 2026-09-23 — No blind POST retries
Ambiguous transport failures trigger fresh read-back before any retry decision.

## 2026-09-23 — CWSN safety
CWSN=Yes records are excluded from AUTO GP and require manual review.

## 2026-09-27 — Vibe Coding baseline
Use READ -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST -> REVIEW -> FIX -> COMMIT -> UPDATE DOCUMENTATION for material work.
