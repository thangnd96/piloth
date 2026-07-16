# Architecture Principles

11 principles baked into every team. Based on [Anthropic's harness design docs](https://www.anthropic.com/engineering/harness-design-long-running-apps) + battle-tested patterns.

Each principle answers: **what is it? how to do it right? what are the anti-patterns?** Rigor is intentional — these are the gates between "team looks like it works" and "team actually produces quality output".

## Conditional application

Not all principles apply to every team composition. The setup skill activates principles based on which archetypes are present.

| Principle | Always active | Requires archetype |
|---|---|---|
| #1 SA-Led Lead | YES | — |
| #2 Contract Negotiation | NO | Executor |
| #3 Execution Logging | NO | Executor |
| #4 Gradable Review Criteria | YES | — |
| #5 Skeptical QA Tuning | NO | QA |
| #6 Parallel QA | NO | QA + Executor |
| #7 Test Ownership Split | NO | QA + Executor |
| #8 Pivot Option | NO | Executor |
| #9 Simplicity Gate | YES | — |
| #10 MCP Bridge Pattern | NO | Specialist (or any MCP-using member) |
| #11 Approach Debate | NO | Executor |

When generating the runtime skill template, include only principles relevant to the elicited team composition. Always-active principles (#1, #4, #9) are always included.

## Contents

1. SA-Led Lead
2. Contract Negotiation
3. Execution Logging
4. Gradable Review Criteria
5. Skeptical QA Tuning
6. Parallel QA
7. Test Ownership Split
8. Pivot Option
9. Simplicity Gate
10. MCP Bridge Pattern
11. Approach Debate

---

## 1. SA-Led Lead

Lead là **Solution Architect**, không phải task coordinator. Mọi hành động của Lead phải thể hiện architectural reasoning, không phải routing hay aggregation.

### Lead phải

- **Excavate requirements** — khai thác theo 5 dimensions:
  - **Problem** (what & why)
  - **Domain** (context & invariants)
  - **Constraints** (hard/soft limits)
  - **Future** (extension & scale)
  - **Risk** (failure modes & blast radius)

  Không accept requirement bề mặt — luôn đào đến root cause.

- **Exhaustive brainstorming** — generate **5-10+ distinct approaches**, không cap ở 2-3. Mỗi approach phải khác nhau về **strategy**, không phải minor variations:
  - ❌ Same strategy, different tech: "dùng Postgres" vs "dùng MySQL"
  - ✅ Different strategy: "sync write-through cache" vs "async event-sourced projection" vs "CQRS với read replica"

  **Distinctness test**: nếu 2 approaches dẫn đến cùng outcome và cùng trade-off profile, chúng là variations — gộp lại.

- **Architecture-grade planning** — mỗi plan phải có:
  1. Problem statement (crisp, 1-2 câu)
  2. Architecture decision (chosen approach + rationale)
  3. Red-team analysis (attack surface, failure modes, edge cases)
  4. Extension points (what changes khi requirements evolve)

- **Contract negotiation** — trước khi executor chạy, Lead phải thống nhất với executor về: input/output contract, invariants phải giữ, error handling strategy, và definition of done. Không handoff mơ hồ.

- **Advisor, not delegator** — khi member hỏi, Lead phải đưa ra authoritative architectural reasoning ("chọn X vì Y, trade-off là Z"), **không** trả lời kiểu "your call" / "tùy bạn" / "both work". Lead có opinion và defend được opinion đó.

- **SA-grade review** — review không chỉ check correctness. Lead phải verify:
  - (a) implementation giữ được architectural intent đã plan
  - (b) không vi phạm invariants
  - (c) extension points còn nguyên
  - (d) không tạo technical debt ngầm

  Code đúng nhưng sai intent = reject.

### Anti-patterns

- Lead route message giữa members thay vì quyết định
- Lead accept requirement đầu tiên mà không excavate (skip root cause)
- Brainstorming 3 options rồi pick option đầu "vì quen thuộc nhất"
- Plan không có rationale — chỉ là list of tasks
- "Both approaches work, pick one" — non-answer
- Review approve vì "tests pass", bỏ qua architectural drift

---

## 2. Contract Negotiation

Bridge giữa high-level plan và implementation. Insight: planner không nên over-specify (cascade errors); executor không nên invent implementation (no architectural context).

### Flow

1. Executor đọc Lead's plan
2. Executor propose specific implementation + testable behaviors
3. Lead review — verify solving right problem, conform architecture
4. Iterate until agreed
5. Write to `./plans/contracts/<task-id>-contract.md`
6. Executor builds against contract; QA verifies against contract

Contract authoritative cho implementation; plan authoritative cho architecture.

### Contract structure (minimum fields)

```markdown
# Contract — <task-id>

## Interfaces

- Inputs: <exact shapes, types, validation rules>
- Outputs: <exact shapes, success & error cases>

## Invariants (must hold at all times)

- <list of rules implementation cannot violate>

## Error handling strategy

- <error categories + how each is surfaced>

## Testable behaviors (acceptance)

- <list of behaviors QA can write tests against>

## Out of scope for this contract

- <explicit non-goals, to prevent scope creep>
```

### When to renegotiate

- Executor discovers plan unclear về một invariant → stop, negotiate
- New edge case found mid-execution → pause, extend contract
- Lead changes plan → executor proposes updated contract → iterate

**Do NOT** continue coding "based on interpretation" when contract unclear.

### Anti-patterns

- Contract = copy-paste của plan (không thêm value) → skip negotiation thay vì fake
- Contract over-specifies (line-by-line code) → handoff có cascade errors
- Executor submit contract một lần và coding ngay — không đợi Lead review
- Lead rubber-stamp contract ("OK proceed") không check invariants
- Contract bỏ "Error handling" → executor improv, error strategy không đồng nhất

---

## 3. Execution Logging (resumable handoff artifacts)

Executor logs mỗi step to `./plans/execution-logs/<task-id>/<executor>-log.md`.

### Format (append-only, structured handoff)

```markdown
## Step <N> — <title> — <ISO timestamp>

**Status**: STARTED | IN_PROGRESS | DONE | BLOCKED

**Files touched**:

- `<path>`: <what changed>

**Commands run**:

- `<cmd>` → <brief result>

**Observations**:

- <finding>

**Current state** (for resume if session restarts):

- <partial progress>
- <assumptions made>

**Next action**:

- <what's next>

**Open questions** (blocking: Y/N):

- <question for Lead, or "none">
```

### Granularity rules

- **Log per step** của contract, không phải per-line-of-code
- Một step = một meaningful unit (VD: "implement validator", không phải "add if-statement")
- Step dài >30 phút → break thành sub-steps, log mỗi cái

### Không log

- Internal reasoning Claude có thể re-derive từ code
- Verbatim code snippets (code ở file, không repeat trong log)
- Noise (tool call successes without learnings)

### Resume protocol

Khi session restart:

1. Next executor instance đọc log
2. Identify last step với `Status: IN_PROGRESS` hoặc `BLOCKED`
3. Continue từ `Next action` của step đó
4. Append new entry với status `RESUMED` trước khi tiếp tục

### Cleanup

Lead runs `./.claude/scripts/cleanup-logs.sh <task-id>` sau delivery. Logs là ephemeral, không check in git, không persist.

### Anti-patterns

- Log rewritten (violates append-only) → mất audit trail
- Log là giấc mơ ("will do X") thay vì actual state → không resumable
- Step quá lớn (log 1 lần cho toàn task) → không useful khi resume
- Log quá chi tiết (per-line) → noise, Lead không đọc được
- Không clean up logs → git diff pollution across tasks

---

## 4. Gradable Review Criteria

Review không binary. Criteria scored 0-10 với per-criterion hard thresholds. ANY criterion dưới threshold → FAIL.

### Default thresholds

| Criterion              | Threshold | Type                                 |
| ---------------------- | --------- | ------------------------------------ |
| Correctness            | PASS      | Binary — all acceptance criteria met |
| Architectural fidelity | ≥8/10     | Gradient                             |
| Code quality           | ≥7/10     | Gradient                             |
| Test coverage          | ≥7/10     | Gradient                             |

### Optional (per project)

- **Accessibility**: P0 for UI — keyboard, ARIA, contrast must pass
- **Performance**: within stated budget (latency/memory/bundle)
- **Security**: no P0 vulnerabilities (injection, auth bypass, PII leak)

### Rubric anchors (for 0-10 gradient)

Reviewers cần calibration — same score across reviewers:

- **9-10**: Exemplary. Có thể dùng làm reference cho project khác.
- **8**: Solid. Passes threshold. Minor polish possible but not required.
- **7**: Acceptable for code/test quality. Architectural fidelity 7 = FAIL (threshold 8).
- **6**: Noticeable gaps. Works but shows erosion of principles.
- **4-5**: Partial correctness with real issues. Below threshold.
- **≤3**: Fundamentally broken or wrong approach.

### Anti-patterns

- **Averaging to save FAIL**: arch 6 + code 9 + tests 9 = "average 8, PASS" ❌. Each criterion gates independently.
- **Grade inflation**: "it works, 9/10" without verifying architectural fidelity
- **Grade deflation**: punishing acceptable code for subjective preferences
- **Moving thresholds mid-review**: changing 8 → 7 to pass borderline case
- **Reviewing without rubric**: "feels like a 7" — not reproducible

---

## 5. Skeptical QA Tuning

Insight from docs: "Out of the box, Claude is a poor QA agent. It identifies legitimate issues, then talks itself into deciding they weren't a big deal."

### Anti-leniency rules (in QA agent prompt)

- **Default stance**: skeptical. Bar là "prove it works", không phải "looks fine"
- **Probe edges first**, không phải happy path (happy path usually works; bugs hide in edges)
- **Self-challenge**: "What would senior engineer complain về?"
- **Don't rationalize** ("probably harmless" → investigate instead)
- **Each criterion verified independently** — không "overall good" skip
- **Reproduce before classifying** bugs

### Probe patterns (actionable)

- Empty/null/undefined inputs cho every entry point
- Boundary values (0, -1, MAX_INT, MAX_INT+1, empty array, 1-element array)
- Concurrent access nếu async
- Malformed input (wrong type, missing field, extra field)
- Error paths (what happens khi dependency fails?)
- State transitions (invalid state changes rejected?)

### Few-shot calibration (show in agent)

❌ **Too lenient**:

> "All core features work. Minor edge case issue when input is empty but user probably won't do that. PASS."

✅ **Properly skeptical**:

> "Core features work for happy path. **BUG**: empty input causes unhandled exception (reproduced 3x). P1 — likely to trigger in real usage. **BUG**: integer overflow at 2^31 (reproduced). P2 — unlikely in practice but violates stated invariant. Verdict: **FAIL** — 2 bugs, P1 alone blocks ship."

### Anti-patterns

- "Probably won't happen" → investigate OR file as P2, không skip
- "Edge case, not critical" → define criticality per rubric, không by feeling
- Report 1 bug khi thấy 3 to appear "fair" — list all found
- Approve vì "tests pass" without running tests
- Test only happy path vì "negative tests too easy to fail" (that's the point)

---

## 6. Parallel QA

QA bắt đầu ngay khi plan ready, parallel với executor. Không đợi code.

### Phases

**Phase 1 (parallel với executor)**: read plan → write test plan → `./tests/qa/qa-plan-<task-id>.md`. Signal `STAGE: test-plan-ready`.

**Phase 2 (after executor `done`)**: review co-located tests for gaps (report, don't edit) → write QA tests → execute (QA + co-located regression + existing suite) → report verdict.

### Mid-execution plan changes

Nếu Lead update plan mid-execution (discovered issue):

1. Lead notify `<qa>` về update
2. QA re-read plan, update test plan (append delta section)
3. QA continue — không restart from scratch

Lead update plan mà không notify QA → QA tests stale plan → false failures. Supervision responsibility.

### Handoff executor → QA

Executor `STAGE: done` message phải include:

- Files changed list
- Co-located tests written
- Known gaps (nếu có)

QA read handoff, review co-located, plan test work. Không ask executor implementation questions — đọc code.

### Anti-patterns

- QA wait for executor done trước khi write test plan → bottleneck, double wall-clock
- QA edit executor's co-located tests to "fix" gaps → ownership violation
- QA start Phase 2 khi executor chưa signal `done` → tests against partial code, false failures
- Plan change mid-execution không notify QA → tests stale

---

## 7. Test Ownership Split

Hai owners, separate territories, strict boundaries.

| Owner    | Location                        | Scope                                                         |
| -------- | ------------------------------- | ------------------------------------------------------------- |
| Executor | `src/**/*.test.ts` (co-located) | Happy path + obvious edges per contract                       |
| QA       | `./tests/qa/<task-id>/`         | Integration, regression, security, perf, advanced edges, a11y |

### Naming conventions

- Co-located: `<component>.test.ts` cạnh `<component>.ts`
- QA tests: `./tests/qa/<task-id>/<category>-<description>.test.ts`
  - Categories: `integration`, `regression`, `security`, `perf`, `a11y`, `edges`

### Conflict resolution

Nếu QA nghĩ một test "thuộc co-located" nhưng executor chưa viết:

1. QA report `STAGE: co-located-gap` to Lead với specific case
2. Lead decide:
   - Gap real → route về executor để thêm (co-located)
   - Borderline → QA cover trong QA tests (không ideal nhưng OK)
   - False positive → clarify với QA

**Never**:

- QA edit co-located test directly
- Executor write test trong `./tests/qa/`

### Anti-patterns

- "Duplicate tests" across ownership (same case tested co-located AND QA) → maintenance burden
- QA skip category vì "executor should have covered" → gap không filled
- Executor stub co-located test để "pass" cho QA viết lại → incentive misalignment
- Boundaries blur qua các tasks → eventually ownership collapse

---

## 8. Pivot Option

**Scope: impl-level only.** Pivot triggers after 2 same-issue impl iterations during execution. For approach-level disagreement *before* implementation, see Principle #11 (Approach Debate) at Stage 2.7.

Sau 2 iterations same issue, executor CAN flag `STAGE: approach-stuck` + propose 1-2 alternatives. Prevents endless fix cycles chasing symptoms khi approach is wrong.

### "Same issue" defined

Cùng root cause symptom xuất hiện sau fix attempts:

- Fix 1: adjust parameter → bug reappears in different shape
- Fix 2: add handling → bug still manifests
- **At this point**: approach may be wrong, not just implementation

**Not** "same issue":

- Two different bugs that happen to fail same test
- Bug fixed, new bug appeared (normal progression)

### Alternative quality bar

Proposed alternatives phải:

- **Address root cause**, không patch symptom
- **Reasoned** — 1-2 câu về why approach khác sẽ work
- **Concrete** — specific enough để Lead evaluate
- **Bounded** — max 2 alternatives (avoid decision fatigue)

❌ Low quality: "try different library", "maybe rewrite"
✅ High quality: "switch from polling to event-driven — root cause is timing assumption invalid under load. Webhook from provider X instead."

### Lead's response options

1. **Pick alternative** → update contract, continue execution
2. **Trigger replan** → back to Stage 3 (exhaustive brainstorming với new context)
3. **Reject both + guide** → architectural reasoning về why neither works, new direction

Never: ignore pivot flag, force executor to continue same approach.

### Anti-patterns

- Executor flag pivot trên iteration 1 (without giving approach chance)
- "Alternative" = same approach với cosmetic change
- Lead force continue past pivot flag → waste tokens chasing symptoms
- Pivot flag becomes escape from hard problems → abused

---

## 9. Simplicity Gate

Không phải task nào cần full pipeline. Insight: "every component in a harness encodes an assumption about what the model can't do on its own."

### Sizing heuristics

- **Trivial** — Lead xử lý trực tiếp, no team:
  - Single-line edit, typo fix, comment update
  - Pure Q&A without deliverable
  - File rename, directory move
  - < ~20 lines change in single file, no behavior change

- **Simple** — light pipeline (skip Stage 2 exhaustive brainstorm, skip Stage 4 contract):
  - Single-file change với clear path
  - Well-understood pattern (CRUD endpoint, standard component)
  - Low risk (isolated module, reversible)
  - ~20-150 lines, ≤3 files

- **Complex** — full 10-stage pipeline:
  - Multiple files / cross-module changes
  - Architectural implications (new pattern, abstraction change)
  - Integration with external systems
  - High risk (security, data, core infra)
  - > 150 lines hoặc >3 files hoặc unknown territory

### Edge cases

- Task "looks simple" but touches core module → treat as complex
- Task "looks complex" but mostly config → may be simple
- Mixed: main task simple + incidental refactor complex → split into 2 tasks

### If sized wrong

Sized trivial but complexity discovered:

1. Lead stop, reset
2. Re-size as simple or complex
3. Start appropriate pipeline
4. Token waste: acceptable — better than continuing wrong pipeline

Never: "push through" wrong sizing to save face.

### User override

- "force full pipeline" → complex pipeline regardless of heuristic
- "minimal please" → accept simple or trivial if heuristic allows
- "skip review/QA" → **refuse**, offer: cancel + direct, reduce scope, or full pipeline

### Anti-patterns

- Default to "complex" for safety → token burn, user friction
- Default to "trivial" to save tokens → quality holes
- Size by line-count alone → misses architectural risk
- Accept user's "make it simple" when task clearly complex → later failure

---

## 10. MCP Bridge Pattern

Claude Code Agent Teams doesn't share MCP connections giữa main session và teammates. Hard architectural constraint.

### Workaround

1. **Lead extracts** MCP data via tools (Figma, Notion, DB, etc.)
2. **Writes to file**: `./plans/<domain>/<task-id>-<type>.md`
   - Design: `./plans/design/<task-id>-figma-raw.md`
   - Data: `./plans/data/<task-id>-schema.md`
   - Docs: `./plans/notion/<task-id>-context.md`
3. **Teammates read files** (via Read tool)
4. **Teammates request more** via `STAGE: info-request` → Lead extracts additional, appends to file

File = single source of truth. Survives session restarts.

### Staleness handling

External source (Figma, Notion) may update mid-task:

- Lead timestamps extractions
- Teammate notice mismatch (file says X, behavior expects Y) → `STAGE: info-request` to re-extract
- Lead re-extracts, appends "## Update <timestamp>" section (không rewrite history)

### Size budget

Large extractions (toàn Figma file, entire DB schema):

- Extract **relevant subset**, không dump everything
- Target: <500 lines mỗi file. Nếu lớn hơn, split by domain:
  - `./plans/design/<task-id>-tokens.md`
  - `./plans/design/<task-id>-components.md`
  - `./plans/design/<task-id>-screens.md`

Lead judges scope at extraction time.

### Anti-patterns

- Teammate ask Lead to "query MCP for me" via message → should extract to file first
- Lead pass MCP data via message text → not persistent, lost on session restart
- File grow unbounded (never clean) → context cost
- Extract too early (before plan) → wasted if task pivots
- Extract too late (mid-execution) → blocks teammate

---

## 11. Approach Debate

Lead's Stage 2 brainstorm picks a winner unilaterally. That's a known failure mode: approach mismatch is caught only after fix loops, when executor finally pushes back during impl. **Approach Debate** is the missing collaborative pre-plan check: Lead shortlists 2-3 approaches → Executor (+ Specialist + QA if present) critique each → Lead converges via consensus or tiebreak. Hard 3-turn cap.

**Scope: approach-level, pre-impl only.** For impl-level discoveries during execution, use Principle #8 (Pivot Option). Debate (#11) and Pivot (#8) never overlap: #11 fires before Stage 3; #8 fires during Stage 6.

### Activation

Active when **`has_executor == true` AND task sized Complex** (per Simplicity Gate #9). Trivial / Simple skip — single-message Lead decision is fine. No new setup-time elicitation; auto-activates by team composition.

### Participants

| Role | Required | Duty |
|---|---|---|
| Lead | YES | Propose 2-3 shortlisted approaches with rationale + trade-offs + red-team note. Tiebreak after turn cap with mandatory written reasoning. |
| Executor | YES | MUST critique ≥1 approach. Per-approach verdict (agree / disagree+rationale / needs-clarification). NOT allowed to defer ("your call", "both work"). |
| Specialist | If present | Domain-risk per approach (P0 risks, blockers). Critique batched into turn 2. |
| QA | If present | Testability per approach (acceptance feasibility). Critique batched into turn 2. |
| Reviewer | NEVER | Stays out — preserves Stage 7 review independence. |

### Turn protocol (hard cap 3)

| Turn | Sender | STAGE | Content |
|---|---|---|---|
| 1 | Lead | `approach-proposal` | 2-3 approaches, each: name, rationale, trade-offs, red-team. |
| 2 | Executor (+ Specialist + QA, single batch) | `approach-critique` | Per-approach verdict + risks + missed cases + optional alternative. MUST critique ≥1. |
| 3a | Lead (consensus) | `approach-decision` | Chosen approach + integrated critiques + outstanding open questions. |
| 3b | Lead (no consensus) | `approach-tiebreak` | MUST address each unresolved critique by name. Architectural reasoning required. |

**No turn 4.** Disagreement after 3b: executor logs disagreement in debate.md; Lead's decision stands.

### Turn formats

See `templates/agent-base.md` "Approach-debate participation" section for copy-pastable schemas (proposal table, critique verdict table, decision/tiebreak block).

### Persistence

Append-only transcript: `./plans/debates/<task-id>-debate.md`. Format: per-turn timestamped sections + Final decision block. Survives session restarts (Principle #3 spirit applied to architectural discourse).

```markdown
# Debate — <task-id>

## Turn 1 — Lead proposal — <ISO timestamp>
<approach-proposal content>

## Turn 2 — Executor critique — <ISO timestamp>
<approach-critique content>

## Turn 3 — Lead decision — <ISO timestamp>
<approach-decision OR approach-tiebreak content>

## Final decision
- Chosen approach: <N>
- Outstanding disagreements: <list or "none">
- Lead reasoning (if tiebreak): <text>
```

### Anti-bypass guardrails

- Executor cannot skip turn 2 → no critique = blocking failure; Lead must request.
- Executor "agree to all" without rationale = invalid; Lead requests rationale.
- Lead cannot pick winner before turn 2 received.
- Lead's tiebreak in 3b MUST address each unresolved critique by name (no blanket "I disagree").
- Stage 4 contract opens with `Approach: <name>; debate ref: ./plans/debates/<task-id>-debate.md`. Mismatch → re-debate (return to Stage 2.7).

### Anti-patterns

- Lead picks winner before reading critiques (turn 2 ignored)
- Executor rubber-stamps all approaches to please Lead
- Reviewer pulled into debate → contaminates Stage 7 independence
- Tiebreak as blanket veto without addressing each critique
- Debate transcript not persisted → architectural disagreement lost
- Debate fired on Trivial/Simple tasks → token waste
- Approach drift mid-impl without re-debate → silent abandonment of agreed approach

---

## Why this set (not something else)?

Each principle addresses a specific observed failure:

| Principle               | Addresses failure                                         |
| ----------------------- | --------------------------------------------------------- |
| #1 SA-Led               | Shallow planning → wrong implementation → many fix cycles |
| #2 Contract Negotiation | Handoff ambiguity → executor interprets wrong             |
| #3 Execution Logging    | Context loss across session boundaries → can't resume     |
| #4 Gradable Review      | Binary review misses nuanced quality issues               |
| #5 Skeptical QA         | LLM grading LLM is inherently lenient                     |
| #6 Parallel QA          | Sequential QA blocks critical path                        |
| #7 Test Ownership       | Overlap causes conflicts; gaps cause missed coverage      |
| #8 Pivot Option         | Fix loops chase symptoms when root cause is architectural |
| #9 Simplicity Gate      | Over-engineering simple tasks wastes tokens               |
| #10 MCP Bridge          | Hard constraint — no architectural workaround available   |
| #11 Approach Debate     | Approach mismatch caught only after fix loops; executor lacks voice on direction |

Origin of insights #2, #4, #5, #8, #9: [harness design docs](https://www.anthropic.com/engineering/harness-design-long-running-apps).
