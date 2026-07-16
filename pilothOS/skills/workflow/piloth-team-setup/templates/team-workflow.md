# Template: team-workflow.md

Write to `.claude/rules/team-workflow.md`. Substitute `{{command}}`, `{{member_roster_lines}}`, `{{threshold_architectural}}`, `{{threshold_code}}`, `{{threshold_tests}}`, and conditional blocks.
Conditional sections marked `<!-- IF: condition -->...<!-- ENDIF -->` — strip non-matching at generate time.

---

```markdown
# Team Workflow — {{command}}

Authoritative reference for team coordination. Details in `.claude/skills/{{command}}/SKILL.md`.

## Architecture: SA-Led (Principle #1 — always active)

Lead (main session) = Solution Architect. Excavates requirements, brainstorms exhaustively (5-10+), designs architecture, negotiates contracts, supervises, reviews. Non-delegable.

Applicable when: always.

{{member_roster_lines}}

## Principle #2 — Contract Negotiation

<!-- IF: has_executor -->
Flow: executor reads plan → proposes implementation + testable behaviors → Lead reviews → iterate → write `./plans/contracts/<task-id>-contract.md`. Contract authoritative for implementation; plan for architecture.
Turn cap: 3 rounds + Lead tiebreak. See runtime-skill Stage 4.

Applicable when: Executor archetype present + task is complex (not "simple" via simplicity gate).
<!-- ENDIF -->
<!-- IF: no_executor -->
Not applicable — no Executor archetype in this team.
<!-- ENDIF -->

## Principle #3 — Execution Logging

<!-- IF: has_executor -->
Executor logs to `./plans/execution-logs/<task-id>/{{executor_name}}-log.md`. Append-only. Format: step title + status + files touched + commands run + observations + current state + next action + open questions.
Purpose: resumability across session restarts, audit trail, Lead's supervision input.
Cleanup: Lead runs `./.claude/scripts/cleanup-logs.sh <task-id>` after delivery.

Applicable when: Executor archetype present.
<!-- ENDIF -->
<!-- IF: no_executor -->
Not applicable — no Executor archetype in this team.
<!-- ENDIF -->

## Principle #4 — Gradable Review Criteria (always active)

| Criterion | Threshold |
|---|---|
| Correctness | PASS |
| Architectural fidelity | {{threshold_architectural}}/10 |
| Code quality | {{threshold_code}}/10 |
| Test coverage | {{threshold_tests}}/10 |
{{optional_criteria_rows}}

ANY below threshold → FAIL. Can't average. Rubric: 9-10 exemplary; 8 solid; 7 acceptable (arch 7 = FAIL); ≤6 below bar.

Applicable when: always (at SA-grade review, Stage 7).

## Principle #5 — Skeptical QA Tuning

<!-- IF: has_qa -->
QA tuned anti-leniency. Default stance: skeptical. Bar: "prove it works". Each criterion independently. Reproduce before classifying. See QA agent file for few-shot calibration examples.

Applicable when: QA archetype present.
<!-- ENDIF -->
<!-- IF: no_qa -->
Not applicable — no QA archetype in this team.
<!-- ENDIF -->

## Principle #6 — Parallel QA

<!-- IF: has_qa -->
QA starts immediately when plan is ready (parallel with executor, not after). Phase 1: test plan. Phase 2 (after executor done): QA tests + full suite execution.

Applicable when: QA + Executor both present.
<!-- ENDIF -->
<!-- IF: no_qa -->
Not applicable — no QA archetype in this team.
<!-- ENDIF -->

## Principle #7 — Test Ownership Split

<!-- IF: has_executor and has_qa -->
| Owner | Location | Scope |
|---|---|---|
| `{{executor_name}}` | co-located (`src/**/*.test.*`) | Happy path + obvious edges per contract |
| `{{qa_name}}` | `./tests/qa/<task-id>/` | Integration, regression, security, perf, edges, a11y |

Strict boundaries. QA spots co-located gap → `STAGE: co-located-gap` to Lead, never edit directly.

Applicable when: Executor + QA both present.
<!-- ENDIF -->
<!-- IF: no_executor or no_qa -->
Not applicable — requires both Executor and QA archetypes.
<!-- ENDIF -->

## Principle #8 — Pivot Option

<!-- IF: has_executor -->
Impl-level only. Approach-level disagreement → Principle #11 at Stage 2.7.
After 2 iterations same issue: executor sends `STAGE: approach-stuck` + 1-2 alternatives. Lead picks alternative OR triggers replan (Stage 3). After 3 QA cycles same bug class → always replan.

Applicable when: Executor archetype present.
<!-- ENDIF -->
<!-- IF: no_executor -->
Not applicable — no Executor archetype in this team.
<!-- ENDIF -->

## Principle #9 — Simplicity Gate (always active)

Lead sizes task at intake: **Trivial** (solo, no team) | **Simple** (light pipeline, skip contract + exhaustive brainstorm) | **Complex** (full pipeline). User override: "force full pipeline" or "minimal please".

Applicable when: always.

## Principle #10 — MCP Bridge Pattern

<!-- IF: has_specialist or has_mcps -->
Lead has MCPs in main session. Teammates cannot access MCPs directly.
1. Lead extracts MCP data → `./plans/<domain>/<task-id>-raw.md`
2. Teammates read file (never MCP directly)
3. Need more → `STAGE: info-request` to Lead → Lead extracts + appends to file

Applicable when: Specialist archetype present, or any MCP configured for Lead.
<!-- ENDIF -->
<!-- IF: no_specialist and no_mcps -->
Not applicable — no MCPs configured and no Specialist archetype in this team.
<!-- ENDIF -->

## Principle #11 — Approach Debate

<!-- IF: has_executor -->
Active Stage 2.7 (Complex tasks only): Lead proposes 2-3 approaches → executor (+ specialist + QA if present) critique → Lead decision or tiebreak. Hard 3-turn cap. Reviewer NOT included.
Persistence: `./plans/debates/<task-id>-debate.md` (append-only).
Stage 4 contract MUST reference debate verdict; mismatch → re-debate.

Applicable when: Executor archetype + Complex sizing.
<!-- ENDIF -->
<!-- IF: no_executor -->
Not applicable — no Executor archetype in this team.
<!-- ENDIF -->

## STRICT ELICITATION (Lead — mandatory)

All clarifying questions to user MUST use `AskUserQuestion` tool. Plain-text question messages are FORBIDDEN at every stage.

## Message format

```
FROM: <sender> | TO: <recipient> | STAGE: <stage> | REF: <task-id>
---
<content>
```

## STAGE vocabulary

Executor → Lead: `confirm`, `progress`, `advice-needed`, `approach-stuck`, `done`, `fix-complete`, `blocker`, `approach-critique`, `contract-counter`
QA → Lead: `test-plan-ready`, `qa-tests-written`, `test-complete`, `co-located-gap`, `advice-needed`, `approach-critique`
Specialist → Lead: `<domain>-plan-ready`, `info-request`, `<DOMAIN>_APPROVED`, `<DOMAIN>_NEED_FIX`, `approach-critique`
Reviewer → Lead: `review-complete`, `advice-needed`
Lead → any: `decision`, `review`, `fix`, `stop`, `check-in`, `go-test`, `approach-proposal`, `approach-decision`, `approach-tiebreak`, `pre-handoff-confirm`, `contract-decision`

## Supervision red flags (Lead → `STAGE: stop` immediately)

- Plan deviation / scope creep / unplanned file
- Tech decisions without Lead approval
- Ambiguity acted on without asking
- Silent >10min
- Destructive command not in contract
- Architectural drift: wrong abstraction, hidden coupling, test coverage illusion

## Token discipline

~3-5x solo for 2-member team. SA overhead (Stages 1-3) recovered via fewer fix cycles. Shut down teammates after their work completes. Trivial tasks → solo session.

## Failure modes

| Symptom | Action |
|---|---|
| Lead skips excavation | Self-enforce: empty clarifying = red flag |
| Brainstorm <5 options | Continue until exhausted |
| Executor hallucinates | `STAGE: stop`, intervene |
| Executor silent >10min | Ping |
| QA surface-level | Request depth |
| Fix loop >3 same issue | Replan |
| Lead answers "your call" | Provide architectural reason instead |
| Approach mismatch caught only at fix loop | Debate at Stage 2.7 before plan (Principle #11) |
| Contract iterations unbounded → ping-pong | Stage 4 hard cap 3 turns + Lead tiebreak |
| Silent disagreement before Stage 5 spawn | Pre-handoff confirm message |
```
