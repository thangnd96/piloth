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

# Keep pytest's caches OUT of the repo. artifact-janitor treats .pytest_cache and
# __pycache__ as local artifacts needing explicit cleanup, so a suite that writes
# them makes control-plane-check fail immediately after the verification command
# the self-hosting contract requires — verify -> check could never be green
# without an artifact-janitor --fix wedged in between. Same convention the
# benchmark suites already use (PYTHONPYCACHEPREFIX=/tmp/piloth-*).
# cache_dir is redirected rather than disabled so --lf/--ff still work.
PYTHONPYCACHEPREFIX=/tmp/piloth-unit-pycache \
  python3 -m pytest "$REPO/tests/unit" -q -o cache_dir=/tmp/piloth-unit-pytest-cache
