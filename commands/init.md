---
description: Install PilothOS into the current project (greenfield or brownfield)
---
# /piloth:init

1. Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/stage.sh"` — stages the full PilothOS distribution into the current project; never overwrites existing consumer files. If it errors (already initialized / pilothOS exists), report the message and stop.
2. Then follow the staged installer skill exactly: `pilothOS/skills/workflow/pilothos-init/SKILL.md` (Preflight → Detect → Audit+Elicit → Plan → Apply → Verify → Log).
3. All changes during Apply go through the engine (`pilothOS/scripts/pilothos_installer.py`) — never write files directly.
4. After the flow completes (including self-prune), remind the user to open a NEW session and APPROVE hooks.
