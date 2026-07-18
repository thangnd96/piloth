#!/usr/bin/env bash
# Unit suite: pytest over guard pure functions.
# pytest is an optional local dependency, so a missing pytest is a loud SKIP
# (exit 0) rather than a hard failure here. CI installs pytest explicitly, so
# the unit gate is always enforced there — see .github/workflows/ci.yml.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

if ! python3 -m pytest --version >/dev/null 2>&1; then
  echo "unit: SKIP (pytest not installed; run 'python3 -m pip install pytest' to enable locally)"
  exit 0
fi

python3 -m pytest "$REPO/tests/unit" -q
