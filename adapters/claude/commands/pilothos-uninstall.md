# /pilothos-uninstall

1. Run `python3 pilothOS/scripts/pilothos_installer.py uninstall` — shows the reverse-plan only.
2. Present the plan; get explicit approval via AskUserQuestion (destructive — Governance requires it).
3. Run again with `--confirm`. Report the result.
4. Ask explicitly whether to also remove the `pilothOS/` tree (default: KEEP).
