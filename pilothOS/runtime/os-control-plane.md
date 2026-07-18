# OS Control Plane

## Purpose

PilothOS is the operating layer for agent work. It is not the host machine OS
and should not become paperwork around the agent. The repo containing
`pilothOS/` is the control plane: it owns scope control, routing, tool policy,
UI defect checks, cost evidence, receipts, learning state and release evidence.
An OS run may control an explicit target repo such as `/Users/.../vngg-ds`; the
target can be a git worktree or a non-git directory.

For controlled targets, Piloth must act as a governor outside the target. The
target should receive the task output only. Installing `pilothOS/`, `.claude/`,
`.codex/`, `.cursor/` or `.antigravity/` into a controlled target is
consumer-visible overhead and is rejected by the default
`target_footprint_policy=no_control_plane_files`.

The project-local OS controls are deterministic, local and auditable:

- `os-start` opens a task run, resolves the controlled target, writes an active
  contract, records a target snapshot, routes consumer assets and records
  required gates;
- `os-evidence` appends sanitized command/tool evidence without full output or
  secrets;
- `os-close` validates the receipt against the target, required gates, evidence
  coverage, truth-in-seal claims, control-plane and target janitors, recorded
  receipt seal and target seal;
- `os-verify` compares the current control-plane receipt seal and target file
  hashes against the OS run seal;
- `os-report` summarizes mode decisions, target footprint, cost ledger, target
  seal and consumer superiority status;
- `control-plane-check` verifies the installed control-plane surface and, by
  default, requires active delivery evidence when the checkout has changes;
- contracts act like scoped policy profiles;
- `asset-scan`, `asset-health` and `asset-sync` maintain the consumer asset
  registry without overwriting manual notes;
- `evidence-add` and `post-edit` capture diff facts and command evidence;
- `tool-check` can validate declared tool entitlements against the active
  contract;
- receipts act like project package receipts;
- `receipt-seal` emits a hash seal over the active receipt, contract, diff facts
  and changed file contents;
- `receipt-verify` compares the current checkout against a prior seal.
- `artifact-janitor` detects local build/test/editor artifacts before release.

## Canonical Lifecycle

Use the OS lifecycle for normal task delivery. Without `target_repo`, the target
defaults to the repo containing `pilothOS/`:

```bash
python3 pilothOS/scripts/pilothos_guard.py os-start request.json
python3 pilothOS/scripts/pilothos_guard.py os-status
python3 pilothOS/scripts/pilothos_guard.py os-evidence evidence.json
python3 pilothOS/scripts/pilothos_guard.py os-close receipt.json
python3 pilothOS/scripts/pilothos_guard.py os-verify
```

`os-start` creates `pilothOS/memory/state/os-runs/<task-id>/state.json` and a
contract snapshot in the control-plane repo. It also chooses
`mode=lean|standard|strict` when the request uses the default adaptive mode. It
writes `target-snapshot.json`. For git targets, the snapshot records
`git status --porcelain`; for non-git targets, it records a deterministic
manifest of target file hashes. `os-evidence` appends to that run's
`evidence.jsonl` and also feeds the active diff facts used by receipt gates.
`os-close` writes `target-diff.json`, records the active receipt, rejects
control-plane footprint in controlled targets, runs `receipt-seal --record`
internally, then writes `target-seal.json` with target file hashes for receipt
`changed_files`. The older guard modes remain kernel primitives for adapters and
tests, but agents should use the OS lifecycle as the default path.

## Adaptive Mode And Cost Ledger

PilothOS defaults to adaptive control:

- `lean` for small UI/docs/test tasks where heavy receipt overhead would waste
  consumer budget;
- `standard` for non-trivial code or controlled-target work;
- `strict` for release/deploy, full design-token coverage, broad scope or
  absolute-claim risk.

Lean mode still requires task-specific proof. A UI/Figma task must record a
Figma source reference when the request references Figma, `ui_quality` evidence
from browser/visual inspection, disclosure for skipped visual diffs and a
design-system decision when relevant. Standard and strict mode add broader
traceability, architecture, reuse and regression gates.

Cost is recorded through `os-evidence` records with `kind=metric`. Supported
metric types include `llm_usage`, `tool_output`, `context_load`, `command`,
`ui_quality`, `retry`, `verification`, `repair` and `benchmark`. Exact token
cost may only be reported when a metric has `real_token_telemetry=true`. If the
adapter does not provide prompt/completion usage, the ledger must say
`real_tokens=unavailable`; artifact token estimates are only a proxy and cannot
support a “cheaper” claim. Cost or token-saving claims require `llm_usage`
evidence with `real_token_telemetry=true`.

## Consumer Superiority Benchmark

PilothOS must not claim consumer value merely because it produced a receipt or
seal. A `none-piloth` vs `had-piloth` benchmark is the proof path:

- `none-piloth` must have no `pilothOS/`, no OS state and no command log entries
  for `pilothos_guard.py`, `stage.sh` or other Piloth commands;
- `had-piloth` must be controlled by Piloth without receiving control-plane
  files; the Piloth runtime/state live in a separate control-plane repo;
- `had-piloth` must run through `os-start`, evidence, `os-close`, target seal and
  `os-verify`;
- both runs must use the same task, target seed and browser/visual checks;
- Piloth may claim consumer value only when every mandatory metric is not worse,
  real token telemetry is present and at least one consumer-visible metric wins.

If the UI output is the same but Piloth costs more, lacks real cost telemetry or
adds only governance overhead, the result is `consumer_value_failed`. Claims
such as “Piloth is cheaper”, “better”, “superior”, “more accurate” or “has
consumer value” are rejected unless mapped to benchmark evidence with
`consumer_value_passed`.

## UI Quality Evidence

For UI surfaces (`.html`, `.css`, `.tsx`, `.jsx`, `components/**`, `ui/**`,
`app/**` or `pages/**`), `os-close` requires a `ui_quality` metric. The metric
should record the smallest browser/visual check that can catch consumer-visible
defects:

- viewport dimensions and browser/tool name;
- required text or semantic content result;
- console and page error counts;
- image failure count when images are used;
- horizontal/vertical overflow or layout overflow count;
- visual diff result and screenshot/artifact paths when available.

A successful receipt is rejected when `ui_quality` evidence reports required
text missing, browser errors, failed images, overflow or failed visual diff.
Skipped pixel diff is allowed only as a disclosed limitation; it cannot support
`1:1` or `pixel-perfect` claims.

## Controlled Targets

Example target request:

```json
{
  "task_id": "tokens-v2",
  "intent": "Generate token surfaces for the design-system repo",
  "target_repo": "/Users/me/work/vngg-ds",
  "task_signal": "UI/component",
  "affected_layers": ["Docs"],
  "target_paths": ["packages/tokens/**", "docs/tokens.md"],
  "expected_evidence": ["pnpm typecheck"],
  "out_of_scope_paths": ["packages/components/**"]
}
```

`target_repo` must be an existing absolute directory and cannot be inside
`pilothOS/memory/state`. `target_paths` are relative to the target, not the
control-plane repo. Receipts should also list target-relative `changed_files`.
When `target_repo` is explicit, the default execution strategy is
`controlled_target` and the default target footprint policy is
`no_control_plane_files`.

For git targets, `os-close` requires every dirty target path from the baseline or
current target status to appear in the receipt. For non-git targets, `os-close`
diffs the baseline manifest against the current manifest, seals the receipt
files by SHA-256 and treats deleted files as an explicit `missing` state.

`os-verify` reports comparisons in two groups:

- `control_plane`: active receipt, contract, diff facts and receipt seal;
- `target`: target metadata, changed paths, deleted files, target file hashes
  and target seal hash.

## Design Token Profile

For design-token work, set `"evidence_profile": "design_tokens"` in the
`os-start` request. The contract then expects at least:

- `figma_node` evidence with `fileKey` and `nodeId` or `frameId`;
- `design_token_coverage` evidence with source refs, covered groups and
  generated surfaces;
- generated surfaces such as `ts`, `css_vars`, `tailwind_v3`, `tailwind_v4`, or
  a clear limitation;
- verification evidence such as build/typecheck/visual check output, or a
  limitation when verification is blocked.

Structured evidence example:

```json
{
  "id": "token-coverage",
  "kind": "design_token_coverage",
  "fileKey": "FILE123",
  "nodeId": "1:2",
  "coverage_scope": "sampled_frames",
  "covered_groups": ["semantic.content", "dimension.scale"],
  "generated_surfaces": ["ts", "css_vars"],
  "token_count": 12,
  "verification": "pnpm typecheck passed"
}
```

Claims like “full design tokens”, “all tokens”, “entire library”, `1:1`,
`pixel-perfect`, `production-ready` or “fully verified” are rejected unless the
receipt maps the claim to evidence strong enough to support it. Full
design-token claims require `coverage_scope=full_declared_source`, Figma source
refs and generated surface coverage. Qualified claims are valid when they state
the actual coverage and limitation, for example: “Semantic content tokens and
dimension scale from nodes X/Y were implemented; full Figma variable library
enumeration is not claimed.”

## Control-Plane Check

Run the default control-plane check during delivery:

```bash
python3 pilothOS/scripts/pilothos_guard.py control-plane-check
```

Default behavior is `active_policy=auto`: if git reports changed files, the
check requires a valid active task contract, captured evidence, deliver receipt,
quality gates, recorded receipt seal and a closed OS run. For release
infrastructure checks that must ignore stale active task state, use:

```bash
python3 pilothOS/scripts/pilothos_guard.py control-plane-check --no-active-task
```

For a hard delivery gate even when git status is unavailable, use:

```bash
python3 pilothOS/scripts/pilothos_guard.py control-plane-check --active-task
```

The check covers the distribution manifest, guard modes, consumer asset
registry, task contract, evidence capture, quality gate docs, receipt/seal,
closed OS run, artifact janitor and repo-local state doctor.

## Truth In Seal

Receipts closed through `os-close` include `claims[]`. Each claim must name the
evidence references that support it:

```json
{
  "claims": [
    {
      "claim": "Layout metrics were checked; pixel-perfect verification is blocked by the missing font.",
      "evidence_refs": ["pixel-diff", "quality_gates.correctness"]
    }
  ]
}
```

Unqualified absolute claims such as `1:1`, `pixel-perfect`,
`production-ready`, `fully verified` or `no issues` are rejected when the
evidence contains a limitation, skipped/blocked verification, failed pixel diff,
missing font, failed quality gate or non-zero blockers. Qualified disclosure is
allowed; the seal should state what was verified and what remains limited.

## Entitlement Profile

Contracts may include:

```json
{
  "allowed_entitlements": [
    "tool.test-runner",
    "network.localhost",
    "deploy.production"
  ]
}
```

`tool-check` and receipt `tool_uses[]` may include `entitlement` or
`entitlements`. If a tool declares entitlements, every entitlement must be listed
in the active contract `allowed_entitlements`. This is PilothOS project policy,
not a host-kernel permission grant.

## Receipt Seal

After `receipt-write`, seal the delivery:

```bash
python3 pilothOS/scripts/pilothos_guard.py receipt-seal > seal.json
```

The seal includes:

- active receipt SHA-256;
- active contract SHA-256;
- diff facts SHA-256;
- SHA-256 and byte count for every changed file in the receipt;
- optional previous seal hash when run with `--record`.

Verify later with:

```bash
python3 pilothOS/scripts/pilothos_guard.py receipt-verify seal.json
```

`receipt-verify` fails when the active receipt, contract, diff facts or changed
file contents no longer match the seal.

## Local State

`receipt-seal --record` appends to
`pilothOS/memory/state/receipt-seals.jsonl`. OS runs live under
`pilothOS/memory/state/os-runs/`. These are repo-local state and must not be
shipped in staged consumer copies.

## Artifact Janitor

Run read-only artifact detection before release:

```bash
python3 pilothOS/scripts/pilothos_guard.py artifact-janitor
```

The janitor reports deterministic local artifacts such as `.DS_Store`,
`__pycache__`, `.pytest_cache`, Playwright reports, `test-results`, `.pyc` and
`*.tsbuildinfo`. It is read-only by default. Explicit cleanup requires:

```bash
python3 pilothOS/scripts/pilothos_guard.py artifact-janitor --fix
```

`production-review` runs the janitor in detect mode by default and fails when
artifacts remain.

## Limits

This is not code signing, notarization, TCC, SIP, APFS snapshots, launchd or a
machine-level sandbox. That is intentional. PilothOS should be the real OS of
the consumer project: the project-local control plane that agents must use to
plan, mutate, verify and deliver work.
