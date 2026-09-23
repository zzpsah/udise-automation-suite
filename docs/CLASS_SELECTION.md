# Class selection — current baseline

Current baseline: `UDISE_Automation_v2.7.3_2026-09-23.ipynb`.

Class scope is module-specific; do not assume every module supports the same forms merely because a class ID can be selected.

## General Profile AUTO

`AUTO_GP_CLASS`:

- IX
- X
- XI
- XII
- IX and X
- IX to XI
- XI and XII
- All IX-XII

`AUTO_GP_RUN_MODE`:

- All students
- First N students

When First N is selected, `AUTO_GP_ROW_LIMIT` is applied before preview generation.

## Facility Profile

The UI exposes IX, X, XI, XII and grouped IX–XII scopes. Historical Facility discovery was performed on IX/X. XI/XII writes remain unverified until live-tested.

## Completion Overview

Supports IX, X, XI, XII and grouped IX–XII scopes. It reads General Profile status and does not itself submit Complete Data.

## Enrollment

Enrollment remains IX/X only. XI/XII has stream-specific requirements and must not be enabled simply by extending a numeric class selector.

## Safety

Changing a selector must clear/rebuild any stale reviewed/validated data for workflows that depend on the selected class. Never submit rows outside the currently reviewed scope.
