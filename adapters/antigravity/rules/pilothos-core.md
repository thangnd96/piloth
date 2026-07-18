# PilothOS Core Rule

Use `pilothOS/bootstrap.md` as the OS entry point. Load context progressively and
identify affected layers before acting. Do not fork PilothOS policy in
Antigravity rules.

Before editing, record a task contract:

```bash
python3 pilothOS/scripts/pilothos_guard.py contract-write <contract.json>
```

The contract must include context/reuse evidence for non-doc/test work. Do not
bypass consumer skills, hooks, tools or design systems.

Before delivery, record a receipt:

```bash
python3 pilothOS/scripts/pilothos_guard.py receipt-write <receipt.json>
```
