#!/usr/bin/env bash
set -euo pipefail
cd "$1"
cat > plan.json << 'EOP'
{"plan_version":1,"mode":"greenfield","fill":{"PERSONA":"P","GOALS":"G","OWNER":"O"},
 "adapters":["claude","cursor","codex","antigravity"],
 "steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},{"op":"fill_placeholders","target":"pilothOS/rot/registry.md"},{"op":"write_marker"}]}
EOP
python3 pilothOS/scripts/pilothos_installer.py apply plan.json > receipt.json
grep -q '"result": "applied"' receipt.json
grep -q completeness_missing receipt.json && exit 1
[ -f pilothOS/.initialized ]
out=$(python3 pilothOS/scripts/pilothos_installer.py validate plan.json 2>&1 || true)
grep -q "re-init" <<< "$out"
