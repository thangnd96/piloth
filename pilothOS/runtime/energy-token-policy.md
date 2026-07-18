# Energy / Token Policy

PilothOS treats model tokens, context window, tool runtime and build/test cycles
as finite runtime resources. The agent should spend them only when they improve
task evidence.

## Defaults

- Load indexes before exact files.
- Load exact files only when the task signal requires them.
- Prefer targeted search over broad repository scans.
- Prefer the narrowest verification command that proves the claim.
- Do not run build/test commands opportunistically; route them through the task
  contract, `tool-check` and receipt evidence when relevant.
- Do not keep expanding context after the contract has enough evidence to act.
- Do not install Piloth runtime/state into an explicit controlled target. The
  control plane should supervise from outside the target.

## Budgets

| Resource | Policy |
|---|---|
| Context | Progressive loading; avoid loading entire directories when an index or exact file is enough |
| Search | Start with targeted `rg` queries; broaden only when findings are insufficient |
| Build/Test | Run the smallest relevant command first; full suites are evidence for broad changes |
| Tools | Use explicit timeout, risk and evidence output |
| Target footprint | For controlled targets, task output only; `pilothOS/`, `.claude/`, `.codex/`, `.cursor/` and `.antigravity/` are overhead |
| External side effects | Require approval before high-risk mutation |

## Adaptive Runtime Modes

PilothOS chooses the lightest mode that can still prove the task:

- `lean` for narrow UI/docs/test tasks;
- `standard` for normal code or controlled-target work;
- `strict` for broad scope, release/deploy, full design-token coverage or
  absolute-claim risk.

The mode is part of the OS contract and must be visible in `os-status` and
`os-report`. If the selected mode adds overhead without improving cost,
fidelity, correctness or defect detection over `none-piloth`, Piloth must report
`consumer_value_failed` instead of claiming value.

## Contract / Receipt Signals

For non-trivial work, the task contract should make resource use visible through:

- `context_evidence`: why each context source was loaded;
- `reuse_evidence`: what existing asset avoided new code or extra exploration;
- `consumer_asset_routing`: which consumer tool/runner/catalog was routed;
- `expected_evidence`: which verification commands or artifacts are necessary.

The receipt should disclose:

- verification command and result;
- limitation when verification was skipped, failed or narrowed;
- `tool_uses` with timeout/result/evidence when tools were used;
- `warning_checklist.large_delta_reason` when the diff is large.

The OS run should also record cost metrics with `os-evidence kind=metric`:

- `llm_usage` with `real_token_telemetry=true` only when adapter telemetry is
  available;
- `tool_output` and `context_load` to expose tool/context bloat;
- `ui_quality` to expose browser/visual checks and UI defects;
- `retry` and `repair` to expose wandering;
- `benchmark` to compare `none-piloth` and `had-piloth`.

Artifact-size estimates are not LLM token telemetry and cannot support a
“cheaper” claim. A cheaper/token-saving claim is invalid unless the run records
real prompt/completion token telemetry.

## Pass-Through Rule

If Piloth cannot improve cost, UI fidelity, correctness, defect detection or
scope control for a task, it should run in the lightest controlled mode and
report `consumer_value_failed` or avoid claiming consumer value. Passing
through a small task with a target seal and a narrow UI/cost check is better
than adding broad scans, full suites or runtime files that the consumer did not
need.

## Guard Support

- `context-loading.md` defines progressive loading order.
- `tool-check` requires timeout, risk and expected evidence.
- `post-edit` records diff facts and warns on large deltas.
- `receipt-write` requires warning checklist entries when generated warnings
  apply.

## Review Checklist

- Did the agent load only the context needed for the task?
- Did searches start narrow before broadening?
- Was each build/test/tool command tied to expected evidence?
- Was a full suite justified by the blast radius?
- Were skipped or narrowed checks disclosed in the receipt?
- Did a controlled target stay free of Piloth/control-plane files?
- Are token savings backed by real adapter telemetry rather than estimates?
