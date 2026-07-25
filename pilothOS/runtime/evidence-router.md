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
