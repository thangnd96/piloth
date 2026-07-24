#!/usr/bin/env bash
# Runner tong: each suite logs to a file and is guarded by Python process-group timeout.
set -uo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
RUNNER="$D/bin/run_with_timeout.py"
SUITE_TIMEOUT="${SUITE_TIMEOUT:-150}"
SUITES="engine install lifecycle evaluation docs benchmark benchmark/figma-ui unit"
fail=0

# Meta-guard: every declared suite must have a runner committed to the tree.
# Prevents the "gate references an untracked/missing suite" hole where a clean
# clone silently drops coverage instead of failing loudly.
for s in $SUITES; do
  if [ ! -f "$D/$s/run-tests.sh" ]; then
    echo "$s: FAIL MISSING (no $D/$s/run-tests.sh)"
    fail=1
  fi
done
[ "$fail" -ne 0 ] && { echo "ABORTED: declared suites missing from tree"; exit 1; }

for s in $SUITES; do
  t0=$(date +%s)
  LOG=$(mktemp)
  python3 "$RUNNER" "$SUITE_TIMEOUT" "$LOG" bash "$D/$s/run-tests.sh"
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "$s: PASS ($(( $(date +%s) - t0 ))s)"
  else
    [ "$rc" -eq 124 ] && echo "$s: FAIL TIMEOUT rc=$rc ($(( $(date +%s) - t0 ))s)" || echo "$s: FAIL rc=$rc ($(( $(date +%s) - t0 ))s)"
    tail -12 "$LOG" | sed "s/^/  /"
    fail=1
  fi
  rm -f "$LOG"
done
[ "$fail" -eq 0 ] && echo "ALL SUITES PASSED"
exit "$fail"
