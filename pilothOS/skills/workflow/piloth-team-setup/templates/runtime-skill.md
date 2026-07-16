# Template: Runtime Skill

Write to `.claude/skills/<command>/SKILL.md`. Substitute all `{{placeholders}}` at generate time.
Conditional sections marked `<!-- IF: condition -->...<!-- ENDIF -->` — strip non-matching at generate time.

---

```yaml
---
name: {{command}}
description: Dispatch task to {{command}} agent team with Lead as Solution Architect. Team: {{member_roster}}. Triggers: {{triggers}} — VN "giao cho team", "team làm", "nhờ team" + EN "delegate to team", "let the team handle". Do NOT trigger for trivial tasks (single-line edits, typos, Q&A) or tasks user wants done in current session.
---
```

# {{command}} — SA-Led Team Dispatch

Lead is Solution Architect, not coordinator.

## STRICT ELICITATION — mandatory at every user-facing question

ALL clarifying questions to user MUST use `AskUserQuestion` tool.
Plain-text question messages are FORBIDDEN.

❌ Forbidden:
- "Could you clarify what you mean by X?"
- "Before I proceed, please answer: A, B, C..."
- "Please confirm by typing 'yes' or 'no'"
- Bullet-list questions in chat without tool call

✅ Required:
`AskUserQuestion({ questions: [{ question, header, options, multiSelect }] })`

This rule applies at EVERY stage that requires user input — Stage 1 excavation, Stage 6 advisor, Stage 9 pivot, any mid-task scope change.

## Agent-teams gotchas

- Subagent `tools` and `model` frontmatter apply when run as teammate
- `skills` and `mcpServers` frontmatter do NOT apply to teammates (loaded from project/user settings)
- MCP Bridge: Lead extracts data to files; teammates read files; never share session/credentials

## Workflow

<!-- IF: has_executor -->
Active stages for this team: 1, 2, 2.7, 3, 4, 5, 6, 7, 8 (if QA), 9, 10
<!-- ENDIF -->
<!-- IF: no_executor -->
Active stages for this team: 1, 2, 3, 5, 6, 7, 8 (if QA), 10
<!-- ENDIF -->

### Stage 1 — Requirements excavation

## STRICT ELICITATION

Batch ALL clarifying questions into ONE `AskUserQuestion` call. Do NOT proceed without answers. Do NOT ask questions via plain text.

Excavate across 5 dimensions:
- **Problem**: why, who, success metric, no-op consequence
- **Domain**: system context, patterns, data shape, user journey
- **Constraints**: tech, perf, security, timeline, capability, budget
- **Future**: evolution, extension points, risky abstractions
- **Risk**: failure modes, irreversibility, hidden assumptions

Deep codebase survey (Read/Grep/Glob): similar implementations, conventions, test patterns, dependencies, reusable utilities.

<!-- IF: has_specialist -->
External MCP gathering (extract before spawning Specialist):
- Design (Figma) → `./plans/design/<task-id>-figma-raw.md`
- Data/DB → `./plans/data/<task-id>-schema.md`
- Other → `./plans/<domain>/<task-id>-raw.md`
<!-- ENDIF -->

Generate task ID: `<YYYYMMDD>-<slug>`

### Stage 2 — Exhaustive brainstorming

Generate 5-10+ distinct approaches (not 2-3, not minor variations):
- Industry standard patterns
- Optimized for different axes (simple / perf / extensible / fast-ship / cheap-ops)
- Adjacent problem patterns; build vs buy vs reuse; quick fix vs proper fix
- Different abstraction levels; different scope sizes

{{#if skills_brainstorm}}Invoke `brainstorm` skill to augment generation.{{/if}}

Evaluate each: codebase fit, complexity, perf, extensibility, testability, rollback pain, token cost, failure mode.
Shortlist 2-4. Pick with explicit trade-off reasoning. Red-team winner (attack own choice).

<!-- IF: has_executor -->
### Stage 2.7 — Approach Debate (Complex tasks only)

Pre-conditions: Stage 2 shortlist of 2-3 approaches ready; task sized Complex (per Simplicity Gate). Trivial / Simple skip.

#### Participants

- Lead (proposes)
- {{executor_name}} (MUST critique ≥1)
<!-- IF: has_specialist -->- {{specialist_name}} (domain risk per approach)<!-- ENDIF -->
<!-- IF: has_qa -->- {{qa_name}} (testability per approach)<!-- ENDIF -->
- Reviewer NOT included (preserves Stage 7 independence)

#### Turn protocol (hard cap 3)

1. Lead `STAGE: approach-proposal` — 2-3 approaches with rationale + trade-offs + red-team note.
2. {{executor_name}} (+ Specialist + QA in same batch) `STAGE: approach-critique` — per-approach verdict + risks. MUST critique ≥1.
3a. Lead `STAGE: approach-decision` — chosen approach + integrated critiques + open questions.
3b. Lead `STAGE: approach-tiebreak` (if no consensus) — MUST address each unresolved critique by name.

No turn 4. Disagreement after tiebreak: log in debate.md; Lead's decision stands.

#### Persistence

Append-only transcript: `./plans/debates/<task-id>-debate.md`. Format: per-turn timestamped sections + Final decision block. Survives session restarts.

#### Anti-bypass

- Cannot pick winner before turn 2 received.
- "Agree all without rationale" = invalid; request rationale.
- Tiebreak without addressing each critique = invalid.

#### Format blocks

See `agent-base.md` "Approach-debate participation" — copy-pastable schemas for proposal / critique / decision / tiebreak.
<!-- ENDIF -->

### Stage 3 — Architecture-grade plan

{{#if skills_gk_plan}}Invoke `gk-plan` skill for structure.{{/if}}

Required sections: problem statement, requirements (explicit + derived + out-of-scope), architecture decision (chosen + why + rejected + trade-offs + red-team), design (data model, components, API, error strategy, test strategy), numbered steps, files touched, global edge cases, Definition of Done, test hints for QA.

Write to `./plans/<task-id>-plan.md`.

Self-check: "Could a different executor produce identical code from this plan?" If not → rewrite weak parts.

<!-- IF: has_executor -->
### Stage 4 — Contract negotiation

Pre-condition: Stage 2.7 debate verdict ready (Complex tasks). Contract opens with line:
`Approach: <name>; debate ref: ./plans/debates/<task-id>-debate.md`

1. Spawn executor, send plan, request proposal
2. Executor proposes specific implementation + testable behaviors
3. Lead reviews: solving right problem? Conforms architecture?
4. Iterate until agreed
5. Write to `./plans/contracts/<task-id>-contract.md`

#### Turn discipline (hard cap 3)

1. Executor proposes contract (`STAGE: confirm` with proposal).
2. Lead reviews — accept, or `STAGE: contract-counter` requesting change (executor may counter back same stage).
3. Lead `STAGE: contract-decision` — accept, or tiebreak.

After turn 3 Lead's contract stands; executor logs disagreement in contract.md if any but proceeds.

If executor's proposal contradicts debated approach → STOP, return to Stage 2.7 for re-debate. Do NOT silently accept.

Contract authoritative for implementation; plan authoritative for architecture.
Skip Stage 4 ONLY for "simple" tasks (simplicity gate below).
<!-- ENDIF -->

### Stage 5 — Spawn team

<!-- IF: has_executor -->
**Pre-handoff confirm**: before spawning teammates, Lead sends `STAGE: pre-handoff-confirm` to debate participants ({{executor_name}}<!-- IF: has_specialist --> + {{specialist_name}}<!-- ENDIF --><!-- IF: has_qa --> + {{qa_name}}<!-- ENDIF -->) listing (a) chosen approach, (b) contract path, (c) explicit ask "any blocking concerns?". Wait for each participant's `STAGE: confirm` or `STAGE: blocker` reply. If `blocker` → re-open Stage 2.7 or Stage 4 as appropriate. Single check-in, NOT a new debate round.
<!-- ENDIF -->

Pre-flight: plan ready; <!-- IF: has_executor -->contract ready; pre-handoff confirm received; <!-- ENDIF -->no active team (else `Clean up the team` first).

<!-- TEAM_MEMBERS_TABLE -->

Spawn instructions per archetype:
<!-- IF: has_executor -->
- **Executor** (`{{executor_name}}`): read plan + contract → confirm → execute + co-located tests → log to `./plans/execution-logs/<task-id>/` → report every step
<!-- ENDIF -->
<!-- IF: has_qa -->
- **QA** (`{{qa_name}}`): read plan immediately → write test plan to `./tests/qa/qa-plan-<task-id>.md` → `STAGE: test-plan-ready` → wait for executor done → write QA tests → run full suite → report verdict
<!-- ENDIF -->
<!-- IF: has_reviewer -->
- **Reviewer** (`{{reviewer_name}}`): spawn at Stage 7 — after executor done, before QA trigger
<!-- ENDIF -->
<!-- IF: has_specialist -->
- **Specialist** (`{{specialist_name}}`): spawn FIRST (Stage 1-2) — domain analysis feeds plan; review domain fidelity after executor done
<!-- ENDIF -->

### Stage 6 — Active supervision

Read every report. Read execution logs.

## STRICT ELICITATION

When consulting user about ambiguity mid-task: use `AskUserQuestion`. Do NOT post plain-text questions.

**Procedural red flags → `STAGE: stop` immediately**:
- Plan deviation / scope creep / unplanned file
- Tech decisions without Lead approval
- Guessing on ambiguity (acting without asking)
- Silent >10min
- Destructive command not in contract

**Architectural red flags → intervene**:
- Design drift (diverges from plan's chosen pattern)
- Wrong abstraction forming; hidden coupling
- Test coverage illusion (tests exist but don't exercise real behavior)

**Advisor mode**: when teammate sends `STAGE: advice-needed` → reply with architectural reasoning. Never "your call" — provide principle + rationale.

### Stage 7 — SA-grade review

After executor `done`, review preserves architectural intent, not just correctness.

Dimensions: structural match (boundaries, shape), behavioral match, conventions, test quality (contract not just happy cases), no architecture shifts, readable in 6 months.

{{#if criteria_accessibility}}UI review: tokens, states, responsive, accessibility P0 (keyboard, ARIA, contrast, reduced-motion).{{/if}}

| Criterion | Threshold |
|---|---|
| Correctness | PASS |
| Architectural fidelity | {{threshold_architectural}}/10 |
| Code quality | {{threshold_code}}/10 |
| Test coverage | {{threshold_tests}}/10 |
{{optional_criteria_rows}}

ANY below threshold → NEED_FIX. Can't average.

Verdict format:
```
🔴 Architectural (must fix): <specific + file + line>
🟡 Quality (should fix): <specific>
🟢 Polish (optional): <specific>
```

<!-- IF: has_qa -->
### Stage 8 — Trigger QA execution

After code APPROVED:
```
FROM: lead | TO: {{qa_name}} | STAGE: go-test | REF: <task-id>
---
Code approved. Write QA tests in ./tests/qa/<task-id>/, run full suite, report verdict.
```
<!-- ENDIF -->

<!-- IF: has_executor -->
### Stage 9 — Fix loops (with pivot option)

On NEED_FIX:
```
FROM: lead | TO: {{executor_name}} | STAGE: fix | REF: <task-id>
---
Issues (priority): 🔴 <specific + file + line + expected vs actual>  🟡 <specific>
Fix exactly. No scope addition.
```

After 2 iterations same issue: executor sends `STAGE: approach-stuck`. Lead: pick alternative OR replan (Stage 3).
After 3 failed QA cycles same bug class → always replan.

## STRICT ELICITATION

If pivot requires user input on direction or scope change: use `AskUserQuestion`. Do NOT ask via plain text.
<!-- ENDIF -->

### Stage 10 — Delivery + log cleanup

When QA PASS (or no QA: when review APPROVED):

```markdown
## Task Complete — <title>

**Architectural summary**: <pattern, trade-offs, extensibility>
**Plan**: `./plans/<task-id>-plan.md`
**Files**: <create/modify/delete list>
**Tests**: co-located <n> + QA <n>
**QA report**: `./tests/qa/qa-report-<task-id>.md`
**Deferred**: <list or "none">
**Iterations**: <review cycles> + <QA cycles>
```

Then run log cleanup:
```bash
./.claude/scripts/cleanup-logs.sh <task-id>
```

Execution logs are ephemeral — cleanup is mandatory at delivery.

## Simplicity gate

Size task at intake:
- **Trivial** (single-line, typo, Q&A, <30 line single-file, no deliverable): handle in session, no team
- **Simple** (single-file, happy path clear, low risk): light pipeline — skip Stage 2<!-- IF: has_executor -->, Stage 2.7, Stage 4<!-- ENDIF -->; shrink Stage 6 (pre-handoff confirm still runs — 1 message, cheap insurance)
- **Complex**: full pipeline

User override: "force full pipeline" or "minimal please". Refusing to skip review/QA gates: offer (A) cancel+direct, (B) reduce scope, (C) full pipeline.

## Multi-team note

This team activates when user dispatches via `/{{command}}`. One team active per task — clean up before switching teams.

## What this skill does NOT do

- Doesn't handle trivial tasks (Lead does in-session)
- Doesn't delegate planning, review, or MCP access to teammates
- Doesn't let executor suggest plan changes mid-execution (except via `approach-stuck`)
<!-- IF: has_qa -->
- Doesn't let QA wait for executor to start test plan (parallel from plan-ready)
<!-- ENDIF -->
- Doesn't skip criteria thresholds (hard gates, can't average)
