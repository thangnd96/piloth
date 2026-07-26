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
| Runtime | `pilothOS/runtime/**` | lifecycle docs, routing behavior, docs tests |
| Rules | `pilothOS/rules/**` | rule index, adapter bridge checks, docs tests |
| Tools/Runtime | `pilothOS/scripts/**`, `pilothOS/tools/**` | `python3 -m py_compile`, evaluation tests |
| Installer | `pilothOS/scripts/pilothos_installer.py`; in the Piloth source repo: `scripts/stage.py`, `scripts/build_manifest.py` | `tests/install/run-tests.sh` |
| Evaluation | `pilothOS/evaluation/**`, `tests/evaluation/**` | `tests/evaluation/run-tests.sh` |
| Docs | `README.md`, `docs/**`, runtime docs | `tests/docs/run-tests.sh` |
| Adapters | `adapters/**`, templates, commands | adapter bridge checks, docs tests |

`tests/run_all.sh` is the default full release gate. Targeted suites are allowed
only when the receipt states the limitation or when the router selected a
narrow suite for a narrow change.

### Shipped Engines Are Amalgamations

`pilothos_guard.py` (~12k dòng) và `pilothos_installer.py` là file amalgamated.

- Đừng `Read`/`grep` nguyên file để hiểu behavior — nạp cả `pilothos_guard.py`
  tốn ~120k token. Dùng `<command> --explain` hoặc `selfcheck` trước.
- Trong Piloth source repo: không sửa file shipped: sửa fragment `src/guard/*.py`
  / `src/installer/*.py` rồi chạy `python3 scripts/build_bundles.py`
  (`--check` là release gate). Line budget của hai engine được gate ở
  `tests/unit/test_repo_hygiene.py` trong source repo.

## Discovery And Routing

Piloth source assets are consumer assets for self-hosting. Use:

```bash
python3 pilothOS/scripts/pilothos_guard.py asset-scan --format json
python3 pilothOS/scripts/pilothos_guard.py asset-health --all
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

## Which Suite To Run

| Change | Suite |
|---|---|
| Guard/evaluation policy | `tests/evaluation/run-tests.sh` |
| Installer/staging | `tests/install/run-tests.sh` |
| Contract/receipt lifecycle | `tests/lifecycle/run-tests.sh` |
| Docs-only | `tests/docs/run-tests.sh` |
| Cross-layer release | `tests/run_all.sh` |

This is a lookup table, not a learned policy. An earlier build kept a scheduler
that recorded local history and replayed it as a suggestion; nothing downstream
ever read its output, so the history is gone and the mapping is stated directly.

Use `state-doctor` before release to audit repo-local OS state:

```bash
python3 pilothOS/scripts/pilothos_guard.py state-doctor
```

The doctor is read-only. It checks receipt seal JSONL,
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
