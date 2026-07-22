#!/usr/bin/env bash
set -euo pipefail
cd "$1"
cp CLAUDE.md goc.md
printf '{"plan_version":1,"mode":"greenfield","adapters":["claude","cursor","codex","antigravity"],"steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},{"op":"append_lines","target":".claude","lines":["x"]},{"op":"write_marker"}]}' > plan.json
python3 pilothOS/scripts/pilothos_installer.py apply plan.json > receipt.json 2>&1 && exit 1
grep -q rolled_back receipt.json
diff -q CLAUDE.md goc.md > /dev/null
[ ! -f pilothOS/.initialized ]
