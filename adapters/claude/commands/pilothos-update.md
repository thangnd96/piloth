# /pilothos-update

Nâng bản PilothOS đã init lên version plugin hiện tại — re-stage kernel/adapter, giữ customization + state. Thêm/bớt adapter → `/pilothos-adapter`.

1. Require `pilothOS/.initialized`; otherwise run `/pilothos-init` first.
2. Follow `pilothOS/skills/workflow/pilothos-update/SKILL.md` (Detect → Re-stage `--upgrade` → Record via engine `mode=upgrade` → Verify + self-check) — the single source of truth for staging commands, plan shape, and the preserve list.
