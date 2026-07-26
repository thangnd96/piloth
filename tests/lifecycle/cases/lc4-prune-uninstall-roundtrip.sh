#!/usr/bin/env bash
set -euo pipefail
cd "$1"
# Self-prune removes the installer facade; uninstall must bring every pruned path
# back. This used to prove the property with `.codex`, an optional adapter dir —
# those are gone, and remove_path is now restricted to the self-prune whitelist,
# so the same round-trip is exercised entirely inside that whitelist.
cat > plan.json << 'EOP'
{"plan_version":1,"mode":"greenfield","fill":{"PERSONA":"P","GOALS":"G","OWNER":"O"},
 "adapters":["claude"],
 "steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},
  {"op":"remove_path","target":".claude/commands/pilothos-init.md"},
  {"op":"remove_path","target":".claude/skills/pilothos-init"},
  {"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/SKILL.md"},
  {"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/greenfield.md"},
  {"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/brownfield.md"},
  {"op":"write_marker"}]}
EOP
python3 pilothOS/scripts/pilothos_installer.py apply plan.json > /dev/null
# facade pruned, but payloads/ (uninstall and the engine need it) survives
[ ! -f .claude/commands/pilothos-init.md ] && [ ! -d .claude/skills/pilothos-init ] \
  && [ ! -f pilothOS/skills/workflow/pilothos-init/SKILL.md ] \
  && [ -d pilothOS/skills/workflow/pilothos-init/payloads ]
python3 pilothOS/scripts/pilothos_installer.py uninstall --confirm > /dev/null
[ -f .claude/commands/pilothos-init.md ] && [ -d .claude/skills/pilothos-init ] \
  && [ -f pilothOS/skills/workflow/pilothos-init/SKILL.md ] \
  && [ ! -f pilothOS/.initialized ]
python3 pilothOS/scripts/pilothos_installer.py validate plan.json > /dev/null
