---
description: Update an already-initialized PilothOS install to the current plugin version
---
# /piloth:update

Nâng bản PilothOS đã init trong project lên version của plugin hiện tại — re-stage kernel + adapter, giữ nguyên customization (`CLAUDE.md`/`AGENTS.md`/`.gitignore`/`settings.json`) và state. Thêm/bớt adapter (không phải full upgrade) → dùng `/piloth:adapter`.

1. Confirm the project is initialized (`pilothOS/.initialized` exists). If not, tell the user to run `/piloth:init` first and stop.
2. Follow the staged skill exactly: `pilothOS/skills/workflow/pilothos-update/SKILL.md` (Detect → Re-stage → Record → Verify) — the single source of truth for upgrade staging (`stage.sh --upgrade`), the `mode=upgrade` engine plan, and the preserve list.
