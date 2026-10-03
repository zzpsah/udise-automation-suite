#!/usr/bin/env bash
set -euo pipefail
REPO="${UDISE_REPO:-$HOME/projects/udise-automation-suite}"
VENV="$REPO/hermes-vps/.venv"
LOCK="${UDISE_PROMOTE_LOCK:-$HOME/.hermes/state/udise-control/promote.lock}"
mkdir -p "$(dirname "$LOCK")"
exec 9>"$LOCK"
flock -n 9 || exit 0

cd "$REPO"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "SKIP: live repo has local changes"
  exit 0
fi

git fetch --quiet origin main
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
[[ "$LOCAL" == "$REMOTE" ]] && { echo "UP_TO_DATE $LOCAL"; exit 0; }

TMP=$(mktemp -d /tmp/udise-promote.XXXXXX)
cleanup(){ git -C "$REPO" worktree remove --force "$TMP" >/dev/null 2>&1 || true; rm -rf "$TMP"; }
trap cleanup EXIT
git worktree add --detach "$TMP" "$REMOTE" >/dev/null

cd "$TMP/hermes-vps"
"$VENV/bin/python" tests/test_offline.py >/dev/null
"$VENV/bin/python" tests/test_ep_facility.py >/dev/null
"$VENV/bin/python" tests/test_esk.py >/dev/null
"$VENV/bin/python" tests/test_facility.py >/dev/null
"$VENV/bin/python" tests/test_general_profile.py >/dev/null
"$VENV/bin/python" tests/test_snapshot.py >/dev/null
"$VENV/bin/python" tests/test_preview_report.py >/dev/null
"$VENV/bin/python" tests/test_control_api_synthetic.py >/dev/null
"$VENV/bin/python" -m py_compile udise_vps/*.py control_api/*.py 2>/dev/null || "$VENV/bin/python" -m py_compile udise_vps/*.py
bash -n install.sh run_tests.sh smoke_readonly.sh

cd "$REPO"
git merge --ff-only "$REMOTE"
"$VENV/bin/python" -m pip install --quiet -r hermes-vps/requirements-control.txt
install -m 755 hermes-vps/tools/promote_from_github.sh "$HOME/.local/bin/udise-promote"
systemctl --user restart udise-control-api.service
echo "PROMOTED $REMOTE"
