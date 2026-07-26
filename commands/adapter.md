---
description: Add or remove PilothOS tool adapters (cursor/codex/antigravity) after init
---
# /piloth:adapter

Add/remove optional tool adapters after init. `claude` is the base adapter — never added or removed here. REMOVE is destructive and needs explicit approval.

1. Confirm the project is initialized (`pilothOS/.initialized` exists). If not, tell the user to run `/piloth:init` first and stop.
2. Follow `pilothOS/skills/workflow/pilothos-adapter/SKILL.md` exactly — single source of truth for staging, plan shape and the removal approval gate.
