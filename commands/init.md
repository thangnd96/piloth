---
description: Install PilothOS into the current project (greenfield or brownfield)
---
# /piloth:init

1. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/stage.sh"` — stages the full PilothOS distribution into the current project; never overwrites existing consumer files. If it errors (already initialized / pilothOS exists), report the message and stop.
2. Then follow `pilothOS/skills/workflow/pilothos-init/SKILL.md` exactly. That skill is the single source of truth for the stage table, engine calls, exit-code handling and the First-Boot Checklist — do not restate its steps here.

Never write files directly during Apply; the engine does.
