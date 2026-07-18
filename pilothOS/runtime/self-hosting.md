# Self-Hosting Contract

## Purpose

Piloth repo is both the PilothOS source tree and a special consumer project.
Starting with V2, Piloth development must be operated through the same
PilothOS contract, routing, tool-control, receipt, learning and quality gates
that Piloth applies to external repos.

## Required Lifecycle

Every Piloth code, doc, runtime, adapter, installer, evaluation or test change
must use:

1. `os-start` before editing to create the active contract and route assets.
2. `pre-edit` before each edit when a harness can call it.
3. `post-edit` after each edit when a harness can call it.
4. `os-evidence` for verification/tool evidence.
5. `os-close` before delivery.
6. `os-verify` when checking a sealed delivery later.

The receipt must include changed files, affected layers, verification command,
result, scope evidence, context used, consumer asset routing, reuse discipline,
learning review, required quality gates and truth-in-seal `claims[]` when
required by the active preset. Direct `contract-write`, `receipt-write`,
`receipt-seal` and `receipt-verify` remain kernel primitives for thin
adapters/tests.

## Piloth-Owned Layers

Piloth task contracts must identify affected layers using these names where
applicable:

| Layer | Examples | Default Evidence |
|---|---|---|
| Runtime | `pilothOS/runtime/**` | lifecycle docs, scheduler/route behavior, docs tests |
| Rules | `pilothOS/rules/**` | rule index, adapter bridge checks, docs tests |
| Tools/Runtime | `pilothOS/scripts/**`, `pilothOS/tools/**` | `python3 -m py_compile`, evaluation tests |
| Installer | `pilothOS/scripts/pilothos_installer.py`; in the Piloth source repo: `scripts/stage.py`, `scripts/build_manifest.py` | `tests/install/run-tests.sh` |
| Evaluation | `pilothOS/evaluation/**`, `tests/evaluation/**` | `tests/evaluation/run-tests.sh` |
| Docs | `README.md`, `docs/**`, runtime docs | `tests/docs/run-tests.sh` |
| Adapters | `adapters/**`, templates, commands | adapter bridge checks, docs tests |
| Agent Teams | `pilothOS/agent-teams/**` | team contract/receipt tests |

`tests/run_all.sh` is the default full release gate. Targeted suites are allowed
only when the receipt states the limitation or when the scheduler selected a
narrow suite for a narrow change.

## Discovery And Routing

Piloth source assets are consumer assets for self-hosting. Use:

```bash
python3 pilothOS/scripts/pilothos_guard.py asset-scan --format json
python3 pilothOS/scripts/pilothos_guard.py asset-health --all
python3 pilothOS/scripts/pilothos_guard.py route-task '{"task_signal":"tool/MCP"}'
```

Generated registry content must be written only by:

```bash
python3 pilothOS/scripts/pilothos_guard.py asset-sync --source scan.json
```

`asset-sync` writes between Piloth-owned markers and must not overwrite manual
notes outside those markers.

`asset-scan` includes deterministic `detected_signals` such as
`package-script`, `hook-config`, `mcp-config`, `runner`, `design-system-path`
and `piloth-owned`. `asset-health` includes `manifest_status` for Piloth-owned
assets so stale distribution coverage is visible.

## Semantic Reuse

For Piloth runtime, tools, evaluation and tests changes, run `reuse-scan`
against the relevant allowed paths before adding new helpers or validators.
Receipts must include `semantic_reuse_review` when high-confidence candidates
exist. A new guard helper must state why an existing validator/helper was not
reused.

Piloth being packaged as a plugin does not relax DRY/KISS. For code, runtime,
rules, adapter or installer changes, the deliver receipt must include
`reuse_discipline` and a `quality_gates.reuse_non_duplication` result. A receipt
that declares this gate `FAIL` cannot also claim a successful delivery without a
documented limitation.

`reuse-scan` reports `learning_suggestions` when high-confidence duplicate or
reuse candidates appear. If the same candidate recurs in local scheduler history,
the suggestion marks it as repeated and points the receipt toward
`learning_review.mistake_checked` such as `duplicated_helper` or
`duplicated_component`.

For UI-facing code or docs, run `ds-scan` when relevant and include
`design_system_candidate_review` before new UI code or UI guidance.

## OS-Like Integrity Controls

Use `pilothOS/runtime/os-control-plane.md` as the reference for project-local OS
controls. Piloth contracts may declare `allowed_entitlements`; tools that claim
`entitlement` or `entitlements` must match that contract list. The canonical
wrapper is:

```bash
python3 pilothOS/scripts/pilothos_guard.py os-start request.json
python3 pilothOS/scripts/pilothos_guard.py os-evidence evidence.json
python3 pilothOS/scripts/pilothos_guard.py os-close receipt.json
python3 pilothOS/scripts/pilothos_guard.py os-verify
```

Recorded seals live in `pilothOS/memory/state/receipt-seals.jsonl` and remain
repo-local state. OS run state lives under `pilothOS/memory/state/os-runs/`.
Dirty Piloth source checkouts must have a closed/sealed OS run before
`control-plane-check` can pass in active mode. Seals make receipt/file tampering
visible but are not code signing or notarization.

## Scheduler

Use `scheduler-suggest` before broad Piloth work. The scheduler should prefer:

| Change | Suggested Suite |
|---|---|
| Guard/evaluation policy | `tests/evaluation/run-tests.sh` |
| Installer/staging | `tests/install/run-tests.sh` |
| Contract/receipt lifecycle | `tests/lifecycle/run-tests.sh` |
| Docs-only | `tests/docs/run-tests.sh` |
| Cross-layer release | `tests/run_all.sh` |

Scheduler history is local repo memory under
`pilothOS/memory/state/scheduler-history.jsonl`. It is append-only and must not
store secrets or full command output.

When history is present and valid, `scheduler-suggest` may apply successful
repo-local entries with matching task signal or affected layers. `scheduler-record`
appends sanitized receipt summaries after successful delivery, including route,
tools, tests, warnings and learning decision. History can add prior evidence
commands, asset types and risk notes to the suggestion. Missing or corrupt
history falls back to deterministic routing and must not block work.
When a receipt omits `task_signal`, the recorder derives it from routed assets;
deprecated host cleanup paths must not make a new project-local OS entry unusable.

Use `state-doctor` before release to audit repo-local OS state:

```bash
python3 pilothOS/scripts/pilothos_guard.py state-doctor
```

The doctor is read-only. It checks scheduler history JSONL, receipt seal JSONL,
receipt seal chain continuity and confirms JSONL state files are not shipped in
the distribution manifest. Missing state is acceptable; corrupt existing state is
not release-ready.
Exact local read-only guard modes such as `state-doctor` and `production-review`
are classified by command shape, not by noisy keywords in the mode name.
Only benign env prefixes such as `PYTHONPYCACHEPREFIX` may keep that low-risk
classification; production/deploy env context is not read-only evidence.
Composite shell commands are not read-only guard evidence; split them and route
each command through the contract.

Use the project control-plane gate before delivery:

```bash
python3 pilothOS/scripts/pilothos_guard.py control-plane-check
```

The default gate checks manifest coverage, guard modes, asset registry, active
task contract, evidence capture, quality gates, receipt/seal, artifact janitor
and state doctor. `--no-active-task` is reserved for release infrastructure
checks that must ignore stale active task state. `--active-task` forces contract,
receipt and recorded seal evidence even when git status is unavailable.

Run the artifact janitor before release:

```bash
python3 pilothOS/scripts/pilothos_guard.py artifact-janitor
```

The janitor is read-only by default and detects deterministic local artifacts.
Explicit `--fix` may remove only known local artifacts such as `.DS_Store`,
`__pycache__`, `.pytest_cache`, Playwright reports and `test-results`.

## Team Control Plane

Release-level or cross-layer Piloth work may use `piloth-team` through
`team-contract-write` and `team-receipt-write`. Single-file or trivial work
should remain single-agent. Team policy lives in `pilothOS/agent-teams/` and
runtime docs; adapters stay thin.

Team receipts materialize role outputs, QA verdicts, handoff summaries and final
lead decisions under `pilothOS/memory/state/team-runs/<task-id>/`. Receipt-level
`edited_paths` are checked against role permissions and team `allowed_paths`.

## Self-Check

Run this before considering a Piloth release complete:

```bash
python3 pilothOS/scripts/pilothos_guard.py self-host-check
python3 pilothOS/scripts/pilothos_guard.py state-doctor
python3 pilothOS/scripts/pilothos_guard.py artifact-janitor
python3 pilothOS/scripts/pilothos_guard.py control-plane-check
python3 pilothOS/scripts/pilothos_guard.py production-review
```

The check verifies dogfood docs, tests, manifest entries, V1 guard coverage and
receipt evidence for changed Piloth source when git status is available.
`production-review` adds release-readiness checks for required manifest entries,
asset health, artifact janitor, control-plane infrastructure, removed deprecated
host-level artifacts and noisy release tokens.
