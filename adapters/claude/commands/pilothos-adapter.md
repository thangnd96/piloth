# /pilothos-adapter

Add/remove PilothOS tool adapters (`cursor`/`codex`/`antigravity`) after init. `claude` is the base adapter — never touched here.

1. Require `pilothOS/.initialized`; otherwise run `/pilothos-init` first.
2. Follow `pilothOS/skills/workflow/pilothos-adapter/SKILL.md` (Detect → Elicit → Add/Remove → Verify).
3. ADD needs the Piloth source (plugin `${CLAUDE_PLUGIN_ROOT}` or a clone): `bash "<source>/scripts/stage.sh" --add-adapters <names>` (target = current project) — copies only the missing adapter dirs, then record via engine `mode=upgrade` + `write_marker`.
4. REMOVE goes through the engine: op `remove_path` (backup kept, uninstall can restore). Get explicit approval first.
