#!/usr/bin/env bash
set -euo pipefail
cd "$1"
cat > plan.json << 'EOP'
{"plan_version":1,"mode":"greenfield","fill":{"PERSONA":"P","GOALS":"G","OWNER":"O"},
 "steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},{"op":"remove_path","target":".codex"},
  {"op":"remove_path","target":".claude/commands/pilothos-init.md"},
  {"op":"remove_path","target":".claude/skills/pilothos-init"},
  {"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/SKILL.md"},
  {"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/greenfield.md"},
  {"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/brownfield.md"},
  {"op":"write_marker"}]}
EOP
python3 pilothOS/scripts/pilothos_installer.py apply plan.json > /dev/null
[ ! -d .codex ] && [ ! -f .claude/commands/pilothos-init.md ] && [ -d pilothOS/skills/workflow/pilothos-init/payloads ]
python3 pilothOS/scripts/pilothos_installer.py uninstall --confirm > /dev/null
[ -d .codex ] && [ -f .claude/commands/pilothos-init.md ] && [ ! -f pilothOS/.initialized ]
python3 pilothOS/scripts/pilothos_installer.py validate plan.json > /dev/null
