#!/usr/bin/env bash
# Install the VPS runner: a venv, dependencies, and an `udise-vps` launcher.
#
#   ./install.sh              # install into ~/.local
#   PREFIX=/opt/udise ./install.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-$HOME/.local}"
VENV="${VENV:-$HERE/.venv}"
BIN="$PREFIX/bin"

echo "== UDISE+ VPS runner install =="
echo "   source : $HERE"
echo "   venv   : $VENV"
echo "   bin    : $BIN"
echo

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: $PYTHON not found. Install Python 3.9+ first." >&2
  exit 2
fi

if [[ ! -d "$VENV" ]]; then
  echo "-- creating venv --"
  "$PYTHON" -m venv "$VENV"
fi

echo "-- installing dependencies --"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$HERE/requirements.txt"

echo "-- running offline tests --"
"$VENV/bin/python" "$HERE/test_offline.py" | tail -1

echo "-- installing launcher --"
mkdir -p "$BIN"
cat > "$BIN/udise-vps" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export PYTHONPATH="$HERE\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$VENV/bin/python" -m udise_vps.cli "\$@"
EOF
chmod 700 "$BIN/udise-vps"

echo
echo "READY"
echo "  launcher: $BIN/udise-vps"
echo
echo "Add to your shell if needed:"
echo "  export PATH=\"$BIN:\$PATH\""
echo
echo "Then:"
echo "  export UDISE_COOKIE_HEADER='JSESSIONID=...; XSRF-TOKEN=...'"
echo "  udise-vps completion --school 2497128 --class IX"
