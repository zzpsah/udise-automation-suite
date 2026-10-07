#!/usr/bin/env bash
# Vendor the browser-free login module into the serverless function directory.
#
# Vercel's Python runtime bundles only what sits inside the function's own
# directory, so api/index.py cannot import from ../../udise_vps/. This copies
# the single module it needs, so the two copies never drift silently — the
# checksum is written next to it and verified on every sync.
#
#   ./sync_module.sh          # copy and record the checksum
#   ./sync_module.sh --check  # verify only; non-zero exit if stale

set -euo pipefail
cd "$(dirname "$0")"

SRC="../udise_vps/login_http.py"
DST="api/udise_login.py"
SUM="api/.udise_login.sha256"

if [[ ! -f "$SRC" ]]; then
    echo "ERROR: $SRC not found" >&2
    exit 2
fi

current="$(sha256sum "$SRC" | cut -d' ' -f1)"

if [[ "${1:-}" == "--check" ]]; then
    if [[ ! -f "$SUM" ]]; then
        echo "STALE: $DST has never been synced" >&2
        exit 1
    fi
    recorded="$(cut -d' ' -f1 < "$SUM")"
    if [[ "$current" != "$recorded" ]]; then
        echo "STALE: $SRC changed since the last sync" >&2
        echo "       source   $current" >&2
        echo "       vendored $recorded" >&2
        echo "       run ./sync_module.sh" >&2
        exit 1
    fi
    echo "OK: vendored login module matches $SRC"
    exit 0
fi

cp "$SRC" "$DST"
echo "$current  login_http.py" > "$SUM"
echo "synced $SRC -> $DST"
echo "  sha256 $current"
