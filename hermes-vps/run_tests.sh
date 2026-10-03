#!/usr/bin/env bash
# Run every offline test suite. No network, no credentials needed.
set -uo pipefail

cd "$(dirname "$0")"

PY="${PY:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

fail=0
for suite in tests/test_offline.py tests/test_ep_facility.py tests/test_esk.py tests/test_facility.py tests/test_general_profile.py tests/test_snapshot.py tests/test_preview_report.py; do
    printf '%-30s ' "$suite"
    if out=$("$PY" "$suite" 2>&1); then
        echo "$out" | tail -1
    else
        echo "FAILED"
        echo "$out" | tail -20
        fail=1
    fi
done

exit "$fail"
