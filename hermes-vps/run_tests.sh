#!/usr/bin/env bash
# Run every offline test suite. No network, no credentials needed.
set -uo pipefail

cd "$(dirname "$0")"

# Prefer an in-repo virtualenv, then python3, then python.
PY="${PY:-}"
if [[ -z "$PY" ]]; then
    if [[ -x ".venv/bin/python" ]]; then
        PY=".venv/bin/python"
    else
        PY="python3"
        command -v "$PY" >/dev/null 2>&1 || PY="python"
    fi
fi

# Discover suites so a new tests/test_*.py cannot be silently skipped.
suites=()
while IFS= read -r f; do suites+=("$f"); done < <(ls tests/test_*.py 2>/dev/null | sort)

if [[ ${#suites[@]} -eq 0 ]]; then
    echo "no tests found under tests/" >&2
    exit 1
fi

fail=0
for suite in "${suites[@]}"; do
    printf '%-34s ' "$suite"
    if out=$("$PY" "$suite" 2>&1); then
        echo "$out" | tail -1
    else
        echo "FAILED"
        echo "$out" | tail -20
        fail=1
    fi
done

echo
if [[ "$fail" -eq 0 ]]; then
    echo "all ${#suites[@]} suites passed"
else
    echo "one or more suites failed"
fi

exit "$fail"
