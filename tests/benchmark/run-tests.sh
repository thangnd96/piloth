#!/usr/bin/env bash
# none-vs-had A/B benchmarks (probe #7 — consumer value). Runs the pytest
# none-vs-had proofs so they are enforced in CI instead of dark. The figma-ui
# benchmark is its own declared suite; this runner covers the top-level *.py.
set -euo pipefail
D="$(cd "$(dirname "$0")" && pwd)"
python3 -m pytest "$D"/*.py -q
echo "BENCHMARK (none-vs-had): ALL PASS"
