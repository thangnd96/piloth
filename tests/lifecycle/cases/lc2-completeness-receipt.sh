#!/usr/bin/env bash
set -euo pipefail
cd "$1"
rm AGENTS.md
printf '{"plan_version":1,"mode":"greenfield","fill":{"PERSONA":"P","GOALS":"G","OWNER":"O"},"adapters":["claude","cursor","codex","antigravity"],"steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},{"op":"write_marker"}]}' > plan.json
python3 pilothOS/scripts/pilothos_installer.py apply plan.json > receipt.json
grep -q '"AGENTS.md"' receipt.json   # engine receipt that, khong doc manifest tinh
