#!/usr/bin/env bash
# Thin wrapper for deterministic Python staging. Keep this entry point stable for docs/tests.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/stage.py" "$@"
