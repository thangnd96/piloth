---
description: Add or remove PilothOS tool adapters (cursor/codex/antigravity) after init
---
# /piloth:adapter

1. Confirm the project is initialized (`pilothOS/.initialized` exists). If not, tell the user to run `/piloth:init` first and stop.
2. Follow the staged skill exactly: `pilothOS/skills/workflow/pilothos-adapter/SKILL.md` (Detect → Elicit → Add/Remove → Verify).
3. ADD copies adapter files from the plugin source: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/stage.sh" --add-adapters <names>` (target = current project). It only copies the missing adapter dirs; it never re-stages the kernel or touches other adapters.
4. REMOVE goes through the engine (`pilothOS/scripts/pilothos_installer.py`, op `remove_path` — keeps a backup). Removal needs explicit approval (destructive).
5. `claude` is the base adapter and is never added/removed here.
