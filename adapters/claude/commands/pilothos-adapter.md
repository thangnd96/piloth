# /pilothos-adapter

Add/remove PilothOS tool adapters (`cursor`/`codex`/`antigravity`) after init. `claude` is the base adapter — never touched here. REMOVE is destructive (needs explicit approval).

1. Require `pilothOS/.initialized`; otherwise run `/pilothos-init` first.
2. Follow `pilothOS/skills/workflow/pilothos-adapter/SKILL.md` (Detect → Elicit → Add/Remove → Verify) — the single source of truth for staging commands, plan shape, and the removal approval gate.
