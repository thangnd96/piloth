# Consumer Asset Registry

PilothOS là control plane. Tài sản của consumer là userland apps/drivers:
PilothOS inventory, classify, route, sandbox, observe và learn từ chúng; PilothOS
không sở hữu, move hoặc overwrite các skill, hook, tool, MCP, design system hay
convention riêng của consumer.

## Registry Contract

Generate a deterministic baseline from repo signals:

```bash
python3 pilothOS/scripts/pilothos_guard.py asset-scan --format json
python3 pilothOS/scripts/pilothos_guard.py asset-scan --format md
python3 pilothOS/scripts/pilothos_guard.py asset-health --all
```

`asset-scan` is the generated
source for V2 routing. It is a baseline for routing; the model/user still applies
judgment for missing capabilities, ambiguous ownership or project-specific risk.
JSON output also includes `detected_signals` and asset health output includes
`manifest_status` for Piloth-owned assets.
Discovery includes static well-known locations and dynamic local repo signals:
agent skills/commands under `.agents/`, `.claude/`, `.codex/` and `commands/`,
script runners under `scripts/`, `bin/`, `tools/` and test suite runners under
`tests/**/run-tests.sh`.

| Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes |
|---|---|---|---|---|---|---|---|---|
| `.claude/skills/design-system` | skill | consumer | UI component lookup | `.claude/skills/design-system` | medium | UI tasks | file exists | Load before building UI when present |
| `scripts/test.sh` | command | consumer | verification | `scripts/test.sh` | low | test evidence | `bash scripts/test.sh --help` | Use as evidence command when contract allows |
| `.mcp.json:Figma` | mcp | consumer | design context | `.mcp.json` | medium | UI/design tasks | list tools succeeds | Load only when task needs design context |

Generated registry sections must use these markers:

```text
<!-- PILOTHOS-GENERATED-ASSETS:START -->
...
<!-- PILOTHOS-GENERATED-ASSETS:END -->
```

Only `asset-sync --source scan.json` may rewrite that marked section; it
preserves notes outside the markers. Upgrade keeps only the marked section and
retakes the rest from the release, because `self-check` requires the vocabulary
below to be current. Notes that must survive an upgrade go in
`pilothOS/knowledge/`.

Generated table contract:

| Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Detected At | Last Health | Status | Confidence | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `_example_` | doc | consumer | example capability | `_example_` | low | task-routed | path exists | repository-scan | unknown | unknown | 0.90 | Generated section example |

## Types

`skill`, `hook`, `tool`, `mcp`, `command`, `design-system`, `doc`,
`convention`, `test-runner`, `build-runner`, `agent`, `specialist`.

`agent` identifies an executable or advisory agent definition. `specialist`
is narrower and is routed only through the Evidence Router registry contract:

```text
id, owner, domains, task_types, capabilities, tools, evidence_types,
permissions, health, confidence, cost_class, adapter_support
```

Consumer-owned qualified specialists are selected before Piloth fallbacks.
Entries below 70/100, unhealthy entries, or entries missing a required tool or
permission are never routed as specialists.

Explicit consumer registries may live at `.piloth/specialists.json` or
`piloth-specialists.json` with a top-level `specialists` array. Request-local
entries may also be passed to `evidence-route`; the router never derives a
specialist entry from a generic agent description.

## Risk

`low`, `medium`, `high`.

High-risk examples: deploy commands, destructive scripts, production database
access, external write APIs and secret-bearing commands.

## Load Policy

`always`, `task-routed`, `approval-required`, `never-auto`.

- Load the registry/index before loading a specific consumer asset.
- Load exact assets only when the task signal requires them.
- If an asset exists and matches the task, cite it in `context_evidence`.
- Healthy match routes as `loaded`.
- Missing or stale match routes as `skipped` with a limitation.
- Approval-required or high-risk health routes as `approval_required`.
- If an asset exists but is not loaded, explain why it is not applicable in the
  receipt or limitation.

## Handling

| Handling | Meaning |
|---|---|
| preserve | Leave the asset in place and unchanged |
| index | Record it in this registry or a layer index |
| route | Use it when task signals match |
| wrap | Call it through a PilothOS contract/approval boundary |
| merge | Merge by engine semantics without overwriting consumer entries |
| needs-judgment | Stop for user/model judgment before changing behavior |
| ignore | Do not load or change because it is irrelevant/noise |
