# /pilothos-init

Follow `pilothOS/skills/workflow/pilothos-init/SKILL.md` exactly. That skill is
the single source of truth for the stage table, engine calls, exit-code handling
and the First-Boot Checklist.

The distribution is already staged when this command exists, so there is no
`stage.sh` step. Never write files directly during Apply; the engine does.
