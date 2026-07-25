# Evidence Router

Piloth is an evidence control plane, not a general-purpose agent manager. The
router selects the smallest evidence set, specialist and execution mode that
can still satisfy the correctness floor.

```text
Intake
→ classify task and risk
→ inspect adapter capabilities
→ plan evidence
→ choose specialist, single/team and model tier
→ execute within hard budgets
→ verify required evidence
→ seal the task receipt
```

## Canonical read-only interfaces

```bash
python3 pilothOS/scripts/pilothos_guard.py evidence-route request.json
python3 pilothOS/scripts/pilothos_guard.py evidence-route --verbose request.json
python3 pilothOS/scripts/pilothos_guard.py evidence-route --explain
python3 pilothOS/scripts/pilothos_guard.py adapter-capabilities capabilities.json
```

`os-start` calls `evidence-route` directly and stores its decision in the task
contract, OS state and report. `route-task` and `scheduler-suggest` remain V1
compatibility wrappers and expose the new decision under `evidence_router`.

Every route contains:

```text
decision_id, task_class, risk, confidence, evidence_plan, context_plan,
execution_plan, tool_plan, verification_plan, budgets, fallbacks,
limitations, decision_reasons
```

Every evidence item contains `type`, `source`, `required`, `freshness`,
`coverage`, `confidence`, `estimated_cost`, `trust` and `fallback`.

## Digest by default

`evidence-route`, `os-start`, `os-status`, `route-task` and `scheduler-suggest`
print a **digest** of the decision: the fields that change what the agent does
next (plan, gates, budgets, limitations) plus `decision_id`. The full decision
is always written to the run's `contract.json` and OS state, and
`evidence-route --verbose` / `os-status --verbose` print it in full.

Reprinting the whole decision at each of those call sites cost ~1.8-2.3k tokens
per call for provenance that only gate logic reads, and gates read it from state.

## Adapter resolution

Adapter identity resolves in this order, and the answer carries
`adapter_source` so it stays auditable rather than looking like a claim:

| Order | Signal | `adapter_source` |
|---|---|---|
| 1 | `adapter` in the request | `request` |
| 2 | `PILOTHOS_ADAPTER` env | `env` |
| 3 | Harness env signal (table below) | `detected` |
| 4 | Nothing recognised | `default` (`unknown`) |

An explicit request keeps whatever id it names — declaring an unregistered
harness is legitimate and simply resolves every capability to `unavailable`.
Detection is stricter and only yields ids `adapter-capabilities.json` declares.
A `PILOTHOS_ADAPTER` value that names nothing known stays `unknown` instead of
falling through to detection.

Detection covers only variables the harness sets in the process that runs the
guard, and every gap fails closed to `unknown` rather than to a wrong claim:

| Adapter | Signal | Caveat |
|---|---|---|
| `claude` | `CLAUDECODE`, `CLAUDE_PROJECT_DIR` | — |
| `cursor` | `CURSOR_AGENT` | Cursor has an open report of it not being set consistently. `CURSOR_CLI` is deliberately **not** used: the integrated terminal sets it even for a human typing by hand. |
| `codex` | `CODEX_SANDBOX` | Undocumented, and only set when sandboxing is on — `--sandbox danger-full-access` resolves to `unknown`. |
| `antigravity` | none | Must declare `PILOTHOS_ADAPTER=antigravity`. |

`unknown` is not a neutral default: it resolves all 15 capabilities to
`unavailable`, so an `enforced` rollout degrades to `advisory` and every
capability gate fails. Detection exists so a supported harness is not penalised
for staying silent.

## Quality and trust gates

- Correctness may not regress more than 2 percentage points against baseline.
- Route confidence below `0.80` requires source reading, another verification
  or user input before relying on the decision.
- Stale, partial or ambiguous graph data is `untrusted_index`, never
  source-grounded evidence.
- Negative claims require complete, explicit claim-scope coverage.
- Missing adapter capability is `unavailable`; it is never represented as a
  native claim.
- Model cost remains advisory unless both real token and cost telemetry are
  native.

## Specialist and team policy

Specialists are scored as domain 35, evidence 25, tool readiness 15,
historical quality 15 and cost 10. Health, adapter, permission or tool gaps
disqualify the candidate; score must be at least 70. A qualified
consumer-owned specialist is preferred over a Piloth fallback.

Team score is:

```text
risk 0-25
+ complexity 0-20
+ specialist need 0-20
+ independent review value 0-20
+ parallelism value 0-15
- coordination cost 0-30
```

Normal team routing requires score at least 60, two declared independent work
packages and remaining budget. Teams have at most three roles and one repair
loop. Security, release, data migration and destructive workflows require an
independent reviewer; adapters without spawn support degrade to an explicit
external-review gate.

## Rollout and state boundary

`off`, `shadow`, `advisory` and `enforced` use the same decision schema.
`PILOTHOS_EVIDENCE_ROUTER_KILL_SWITCH=1` returns to legacy scheduler plus
source-only routing. Adapters must pass the full capability vocabulary before
enforced execution is enabled; otherwise the effective mode degrades to
`advisory` and records the exact gaps.

In `advisory`, changing `execution_mode` requires
`router_override_reason`. In `enforced`, the receipt must match `decision_id`
and cover every required evidence type. Low-confidence routes require an
explicit `router_low_confidence_resolution`; review-bearing routes require an
independent PASS with evidence. The gate runs inside `os-close`.

The Evidence Router is stateless: routing never creates or updates a database,
specialist score or policy. `scheduler-record` may append sanitized,
repo-local compatibility history to `memory/state/scheduler-history.jsonl`
when explicitly invoked. That history can advise legacy wrappers but cannot
mutate router policy, promote lessons or upload telemetry.
