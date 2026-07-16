# /pilothos-init

Use `pilothOS/skills/workflow/pilothos-init/SKILL.md` (Plan/Apply flow).

1. Preflight + Detect via guard; confirm verdict via AskUserQuestion.
2. Load ONE branch file; audit (judgment) + elicit (persona, goals, adapters).
3. Write `pilothOS/.pending-plan.json`; run installer `dry-run`; present; approve via AskUserQuestion.
4. Run installer `apply`; on exit 4 resolve listed items and re-plan; on exit 3 report rollback.
5. Read RECEIPT, print First-Boot Checklist, `log-append` with manifest path.
Never write files directly during Apply — the engine does.
