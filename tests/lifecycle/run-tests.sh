#!/usr/bin/env bash
# Lifecycle E2E — each case runs in a fresh workspace copied from a read-only
# pristine staging baseline. The baseline is never mutated; each case still has
# its own universe, while the suite stays fast enough for CI/harness limits.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
CASES_DIR="$REPO/tests/lifecycle/cases"
RUNNER="$REPO/tests/bin/run_with_timeout.py"
TO="${LC_TIMEOUT:-45}"
fail=0
BASE=$(mktemp -d)
BASE_LOG="$BASE/.stage.log"
python3 "$RUNNER" 30 "$BASE_LOG" bash "$REPO/scripts/stage.sh" "$BASE"
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "lifecycle FAIL (baseline stage rc=$rc)"
  tail -8 "$BASE_LOG" | sed 's/^/  /'
  rm -rf "$BASE"
  exit 1
fi
chmod -R a-w "$BASE" 2>/dev/null || true
for case_sh in "$CASES_DIR"/lc*.sh; do
  name="$(basename "$case_sh" .sh)"
  t0=$(date +%s)
  W=$(mktemp -d) ; LOG="$W/.case.log"
  echo "$name START"
  cp -a "$BASE/." "$W/" >> "$LOG" 2>&1
  chmod -R u+w "$W" 2>/dev/null || true
  python3 "$RUNNER" "$TO" "$LOG" bash "$case_sh" "$W"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "$name PASS ($(( $(date +%s) - t0 ))s)"
  else
    [ "$rc" -eq 124 ] && echo "$name FAIL (TIMEOUT ${TO}s, $(( $(date +%s) - t0 ))s)" || echo "$name FAIL (exit $rc, $(( $(date +%s) - t0 ))s)"
    echo "  --- 8 dong cuoi log ---"; tail -8 "$LOG" | sed 's/^/  /'
    fail=1
  fi
  rm -rf "$W"
done
chmod -R u+w "$BASE" 2>/dev/null || true
rm -rf "$BASE"
[ "$fail" -eq 0 ] && echo "LIFECYCLE SUITE: ALL PASS"
exit "$fail"
