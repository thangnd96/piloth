#!/usr/bin/env bash
set -euo pipefail
cd "$1"
G="pilothOS/scripts/pilothos_guard.py"
out=$(python3 $G self-check); grep -q PASSED <<< "$out"
[ -z "$(python3 $G statusline < /dev/null)" ]              # im lang khi healthy
echo '{}' | python3 $G stop-check > /dev/null              # hook modes: stdin tuong minh
echo '{}' | python3 $G session-start > /dev/null
echo '{}' | python3 $G prompt-check > /dev/null
