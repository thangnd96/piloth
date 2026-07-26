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

## Runtime Modes

Two modes, chosen explicitly in the request:

- `standard` for normal code, docs or controlled-target work;
- `strict` for broad scope, release/deploy, full design-token coverage or
  absolute-claim risk.

The mode is part of the OS contract and must be visible in `os-status`. If the selected mode adds overhead without improving cost,
fidelity, correctness or defect detection over `none-piloth`, Piloth must report
`consumer_value_failed` instead of claiming value.

## Real token telemetry (`token-telemetry`)

Real per-turn LLM token usage is available on harnesses that expose it. For
Claude Code, `token-telemetry` reads the session transcript
(`~/.claude/projects/<slug>/<session>.jsonl`) where each assistant turn carries
`message.usage` (`input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
`cache_read_input_tokens`) + `message.model` + `timestamp` — genuine API usage,
not an estimate. It sums usage windowed to the OS run's `created_at`, prices it
via `runtime/model-pricing.json` (per-tier: input, output, cache-write ~1.25×,
cache-read ~0.1×), and records
`os-evidence kind=metric metric_type=llm_usage real_token_telemetry=true`
(`cost_usd`, `model`, `window_start`, `subagent_scope=main_session_only`).

```bash
python3 pilothOS/scripts/pilothos_guard.py token-telemetry [--task <id>] [--transcript <path>]
```

- **Attribution:** main-session transcript only; background subagent transcripts
  are separate files and are not summed (disclosed via `subagent_scope`). The
  per-turn numbers are real; the per-task figure (`total_tokens` = input + output)
  is a sum over the run window.
- **Safe to run twice.** Each run re-sums the whole window, so the figure is
  *cumulative*, not a delta — adding two of them would count the same tokens twice.
  The ledger keeps the newest and reports how many it replaced as
  `superseded_token_snapshots`. Hand-recorded per-phase `llm_usage` (no
  `window_start`) is a delta and stays additive.
- **Fail-soft:** no transcript / harness without per-turn telemetry → records
  `real_token_telemetry=false` + `unavailable_reason`.
- **Unlocks cost claims:** with a real `llm_usage` metric present, `os-close` no
  longer blocks a lower-cost/token claim. A **"cheaper than none-piloth" claim
  still requires the benchmark** (`had-piloth` vs `none-piloth`) — real tokens
  alone don't prove consumer savings.
- **Cache pricing dominates accuracy:** a long 1M-context session is mostly
  `cache_read`, so the price map must keep the cache tiers + `as_of` current.
- **Cost is a subtotal, and says so.** A model missing from
  `runtime/model-pricing.json` no longer voids the run's cost: the priced turns are
  summed and the gap is declared as `cost_complete: false` + `unpriced_models` +
  `unpriced_tokens`. `cost_usd: null` means *nothing* could be priced. Token totals
  stay complete either way — only the money is partial. Turns whose `model` is not a
  model call (`<synthetic>`) are excluded from both. The map has no `speed`
  dimension, so a fast-mode session is under-priced.

## Budget (advisory)

An optional contract `budget.max_usd` produces a `budget_status` in
`os-status`: `{max_usd, spent_usd, remaining_usd, over_budget}`
computed from the real token cost. It is **advisory only — it never blocks
`os-close`** (`advisory_unavailable` when no ceiling is set or no real cost is
recorded yet). Promoting it to a hard ceiling is a deliberate future step.

When the cost is a subtotal, `budget_status` adds `cost_complete: false` +
`spent_is_floor: true` + `unpriced_models`. Read `spent_usd` as a floor then: it can
prove the budget **is** exceeded, never that it isn't.

## State retention (advisory hygiene)

Task-lifecycle state accumulates on disk (`os-runs/`,
`receipt-seals.jsonl`) and two kernel logs (`lessons-learned.md`,
`review-log.md`) grow and re-load into context each session. `state-janitor`
keeps them bounded (see `os-control-plane.md`). Like `budget`, it is **advisory
hygiene, not enforcement**: `os-close` runs the safe subset automatically but
**fail-soft** — a cleanup error is recorded, never blocks the close — and the
kernel-log rotation is opt-in and lossless (rows move to `*-archive.md`, nothing
is deleted). `receipt-seals.jsonl` is hash-chained and never auto-pruned.

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
- Context and tool-output footprint are measured by
  `scripts/measure_budget.py` in the Piloth repo, not by a shipped guard verb:
  they are vendor meters that keep the ratchet tests honest. Both are
  `context_load` / `tool_output` footprint numbers and neither is `llm_usage`
  telemetry, so neither can back a "cheaper" claim.
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
