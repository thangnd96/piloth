---
description: Add or remove PilothOS tool adapters (cursor/codex/antigravity) after init
---
# /piloth:adapter

Add/remove optional tool adapters after init. `claude` is the base adapter — never added/removed here. REMOVE is destructive (needs explicit approval).

1. Confirm the project is initialized (`pilothOS/.initialized` exists). If not, tell the user to run `/piloth:init` first and stop.
2. Follow the staged skill exactly: `pilothOS/skills/workflow/pilothos-adapter/SKILL.md` (Detect → Elicit → Add/Remove → Verify) — the single source of truth for staging (`stage.sh --add-adapters`), plan shape, and the removal approval gate.
