#!/usr/bin/env bash
# Live read-only smoke test against the UDISE+ SDMS portal.
#
# Performs authenticated reads only. Sends no writes.
#
#   export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...'
#   ./smoke_readonly.sh 2497128 IX
#
# Evidence label: LIVE_READ (never LIVE_SAVE — this script cannot write).

set -euo pipefail

SCHOOL="${1:-2497128}"
SCOPE="${2:-IX}"
OUT="${3:-./smoke-out}"

if [[ -z "${UDISE_COOKIE_HEADER:-}" ]]; then
  echo "ERROR: UDISE_COOKIE_HEADER is not set." >&2
  echo "Copy the complete Cookie request header from an authenticated browser session." >&2
  exit 2
fi

PY="${PYTHON:-python3}"
if [[ -x "../.venv/bin/python" ]]; then
  PY="../.venv/bin/python"
fi

mkdir -p "$OUT"

echo "== LIVE_READ smoke test =="
echo "   school : $SCHOOL"
echo "   scope  : $SCOPE"
echo "   output : $OUT"
echo "   (no writes will be performed)"
echo

echo "-- 1/3 student roster export --"
"$PY" -m udise_vps.cli students --school "$SCHOOL" --out "$OUT"

echo
echo "-- 2/3 completion overview --"
"$PY" -m udise_vps.cli completion --school "$SCHOOL" --class "$SCOPE" --out "$OUT"

echo
echo "-- 3/3 AUTO GP preview (no --submit, so nothing is written) --"
"$PY" -m udise_vps.cli gp --school "$SCHOOL" --class "$SCOPE" \
      --run-mode "First N students" --limit 3

echo
echo "== LIVE_READ smoke test complete =="
echo "Evidence level: LIVE_READ (no writes were sent)."
