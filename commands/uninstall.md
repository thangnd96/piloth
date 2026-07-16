---
description: Uninstall PilothOS from the current project (restores pre-install state)
---
# /piloth:uninstall

1. Run `python3 pilothOS/scripts/pilothos_installer.py uninstall` — shows the reverse-plan only (restore/delete lists). If it reports nothing to restore, say so and stop.
2. Present the plan; get explicit approval via AskUserQuestion (destructive action).
3. Run again with `--confirm`. Report the result.
4. Ask explicitly whether to also remove the `pilothOS/` tree (default: KEEP).
