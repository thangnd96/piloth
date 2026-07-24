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
- `os-inspect` gives a single legible system-status report — version,
  capability/authority map, guard-mode (syscall) surface, rot and control-plane
  health — the Piloth analog of `aos status`; see `runtime/os-services.md`;
- `review-request`, `review-feedback` and `review-verify` run the structured
  human-review round-trip that backs the `human_review` gate;
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

## Authoring a receipt (dry-run + gate-aware template)

Build the receipt without guessing which fields this run needs:

```bash
python3 pilothOS/scripts/pilothos_guard.py receipt-template        # scaffold
python3 pilothOS/scripts/pilothos_guard.py os-close --dry-run receipt.json
```

- `receipt-template` is **gate-aware**: it reads the active contract + diff facts
  and emits only the fields the run's `required_gates` actually require (a
  docs-only run omits the UI fields; a UI run includes `design_system_checked`
  etc.), with **valid default enum values** — not `<placeholder>`. Allowed enum
  values for each field are listed under the `_allowed_values` block; delete that
  block before the real close for a clean seal.
- `os-close --dry-run` runs the **full** close validation set (every quality gate,
  truth-in-seal, expected-evidence, footprint and janitor check — not just the
  core receipt validator) and returns `{would_pass, errors}` **without mutating
  state, sealing, or writing `target-diff.json`**. Iterate until `would_pass:true`,
  then run `os-close` for real.

## os-start request schema

Every field is optional; a bare `{}` opens a repo-local run. For the full,
machine-readable schema (fields, required flags, defaults, allowed values,
aliases) run:

```bash
python3 pilothOS/scripts/pilothos_guard.py os-start --explain
```

Key fields: `task_id`, `intent` (→ `task_scope`), `task_signal`, `target_repo`
(absolute; omit for repo-local), `target_paths`, `affected_layers`,
`expected_evidence`, `out_of_scope_paths`, `evidence_profile`
(`code|ui|design_tokens|docs|release|generic`), `mode`
(`lean|standard|strict|adaptive|auto`), `requires_prototype`/`requires_human_review`,
`budget`. `requires_prototype:true` also forces `requires_human_review:true`.

## Driving a target from another session (enforcement caveat)

The guard's git helpers are scoped to the control-plane repo. When you drive a
self-hosted or controlled target **from a different repo's Claude Code session**,
the target's own `PreToolUse`/`PostToolUse`/`Stop` hooks do not fire, so
`diff-facts` stays empty and the Stop-time deliver gate never runs. `os-close`
still seals using the git/manifest **target-diff**, but it emits a non-blocking
`enforcement_advisory` when diff-facts is empty while the target-diff shows
changes. For full hook coverage, run the lifecycle **inside the target's own
session**.

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
`ui_quality`, `browser_smoke`, `retry`, `verification`, `repair` and
`benchmark`. Exact token
cost may only be reported when a metric has `real_token_telemetry=true`. If the
adapter does not provide prompt/completion usage, the ledger must say
`real_tokens=unavailable`; artifact token estimates are only a proxy and cannot
support a “cheaper” claim. Cost or token-saving claims require `llm_usage`
evidence with `real_token_telemetry=true`.

The `token-telemetry` mode produces exactly that `llm_usage` metric from the
Claude Code session transcript (real `message.usage`), windowed to the run's
`created_at` and priced via `runtime/model-pricing.json`; it records
`cost_usd` + `subagent_scope=main_session_only`, and fails soft to
`real_token_telemetry=false` when no transcript is available. An optional
contract `budget.max_usd` yields an **advisory** `budget_status`
(`spent_usd`/`remaining_usd`/`over_budget`) in `os-status`/`os-report` — it never
blocks `os-close`. See `runtime/energy-token-policy.md`.

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

## Human Review Round-Trip

Khi `os-start` request khai `requires_human_review: true`, contract thêm gate
`human_review` và task không thể Seal nếu chưa có human review được ghi bằng chứng.
Vòng round-trip là Piloth-native (Python/MD/JSON), phỏng theo annotron:

```bash
python3 pilothOS/scripts/pilothos_guard.py review-request <task-id>
# reviewer tạo feedback.json (hoặc UI companion sinh ra), rồi:
python3 pilothOS/scripts/pilothos_guard.py review-feedback feedback.json
python3 pilothOS/scripts/pilothos_guard.py review-verify <task-id>
```

- `review-request` ghi `os-runs/<task>/review-request.json` (artifact under review,
  gates, questions, `request_sha256`).
- `review-feedback` validate + append một round vào
  `os-runs/<task>/review-feedback.jsonl`, đồng thời ghi evidence `kind=human_review`.
- Feedback schema: `{verdict: approve|request-changes|reject, finalized: bool,
  findings: [{id, location:{file?,gate?,line?}, note, severity:
  blocker|major|minor|nit, disposition: approve|request-changes}]}`.
- `os-close` PASS gate `human_review` ⇔ round mới nhất có `verdict=approve`,
  `finalized=true` và không còn finding `blocker`/`major` mang `request-changes`;
  ngược lại reject và set task về Repair. Guard không tự khai PASS được — receipt
  tự khai `human_review: PASS` mà thiếu artifact backing vẫn bị reject.
- Companion tool `pilothOS/tools/review/` (annotron-faithful) cung cấp UI
  point-and-click sinh ra chính feedback này — userland driver, không bắt buộc.
  Khi bind `--task <id>`/`--govern`, UI thêm **pipeline/gate stepper** (đọc qua
  `os-status`) và **option-picker** cho prototype; ungoverned thì stepper ẩn,
  core chạy 1:1 standalone với annotron.

## Prototype Phase & Discovery Gate

- `requires_prototype: true` ⇒ contract tự bật `requires_human_review: true` và
  thêm gate `prototype`. Skill `piloth-prototype` sinh ≥2 UI options
  (`PROTOTYPE-option{N}.*` + `PROTOTYPE.md`) trong `os-runs/<task>/artifacts/`,
  ghi `os-evidence kind=prototype` `{method, options:[{id,artifact,intent}],
  chosen}`. Human pick **tái dùng** vòng `review-request`/`review-feedback` (gate
  `human_review`) — không có cơ chế review riêng. Gate `prototype` (mỏng) chỉ
  kiểm invariant: method hợp lệ, ≥2 options, `chosen` ∈ options.
- Discovery gate (skill `piloth-discovery`) chạy đầu phase khi có ≥3 câu hỏi mở
  hoặc 1 câu high-impact: hỏi-xác nhận qua Governed Visual Review, ghi
  `os-evidence kind=discovery` `{decisions:[{q,answer,source}]}` và fold vào
  contract `discovery_decisions`. `DISCOVERY.md` là working doc (không
  produces/depends). Là gate judgment, không phải hook tự trigger.
- `phase_plan_suggestion` (recipe right-sizing, advisory): `os-start` khuyến nghị
  `recommend_discovery`/`recommend_prototype` dựa trên signal/scope, hiển thị ở
  `os-status`/`os-report`, **không tự bật phase** (auto-enable = thêm chi phí).
- `model_hints` (advisory): map phase → tier model (strong cho discovery/
  prototype/plan; cost cho execute/test). Chỉ harness pin được per-phase model
  (Claude Code frontmatter `model:`) mới enforce.

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

## State janitor (retention / GC)

`artifact-janitor` targets build cruft. `state-janitor` targets the task
lifecycle state that accumulates under `pilothOS/memory/state/` over time:

```bash
python3 pilothOS/scripts/pilothos_guard.py state-janitor          # detect only
python3 pilothOS/scripts/pilothos_guard.py state-janitor --fix    # apply
python3 pilothOS/scripts/pilothos_guard.py state-janitor --fix --kernel-logs
```

- **os-run artifacts** — the heavy `os-runs/<task-id>/artifacts/` (prototype
  HTML, screenshots) of **sealed** runs outside retention are removed; the
  lightweight `state.json`/`target-seal.json` audit records are kept. Retention
  keeps the active run + the last `N` runs + any run within `X` days
  (defaults `N=10`, `X=14`; override with `--runs`/`--days` or
  `PILOTHOS_RETENTION_RUNS`/`PILOTHOS_RETENTION_DAYS`). Unsealed/in-flight runs
  are never touched.
- **scheduler-history.jsonl** — tail-truncated to the last
  `PILOTHOS_SCHEDULER_KEEP` lines (default 200). Not chained, so dropping the
  oldest lines is safe.
- **receipt-seals.jsonl** — **warn only**. It is a hash-chained ledger
  (`previous_seal_sha256`); `state-janitor` never rewrites it. Archive it
  manually if it grows large.
- **kernel logs** (`--kernel-logs`, opt-in) — `lessons-learned.md` and
  `review-log.md` grow with every session and are re-loaded into context. Rows
  beyond `PILOTHOS_KERNEL_LOG_KEEP` (default 200) are moved **losslessly** to
  `*-archive.md` siblings that are not part of any context load set.

`state-janitor` is read-only by default, exactly like `artifact-janitor`.
`os-close` runs the **safe subset** (os-run artifacts + scheduler history, never
kernel logs) automatically after a successful seal. It is fail-soft: a cleanup
error is recorded in the close payload but never rejects the close. `state-doctor`
surfaces an advisory `state retention advisory` check so you know when to run it.

## Limits

This is not code signing, notarization, TCC, SIP, APFS snapshots, launchd or a
machine-level sandbox. That is intentional. PilothOS should be the real OS of
the consumer project: the project-local control plane that agents must use to
plan, mutate, verify and deliver work.
