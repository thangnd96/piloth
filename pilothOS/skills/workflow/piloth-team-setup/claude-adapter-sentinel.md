# CLAUDE.md Sentinel Template

Outer block + per-team inner block templates for auto-managed CLAUDE.md injection.

---

## Outer block template

The outer block wraps ALL teams for this project. Injected once; updated in-place on subsequent setups.

```markdown
<!-- AGENT-TEAM:START — managed by piloth-team-setup, do not edit manually -->
## Agent Team

This project has <N> team(s) configured via piloth-team-setup. Dispatch tasks via the team's slash command.

<TEAM_BLOCKS>

### Lead (shared across all teams)

Lead (main session) is **Solution Architect** — not coordinator. Lead excavates requirements, brainstorms exhaustively (5-10+ approaches), designs architecture, negotiates execution contracts, supervises all teammates, and performs SA-grade review. Non-delegable.

### Re-run setup

To add a new team or update an existing team: activate `piloth-team-setup` skill ("setup team", "tạo team"). Setup is idempotent — existing teams are preserved; only the target team is updated.

<!-- AGENT-TEAM:END -->
```

`<TEAM_BLOCKS>` is substituted with one or more per-team inner blocks (sorted alphabetically by command name).

---

## Per-team inner block template

One inner block per team. Replace `<command>`, `<purpose>`, member rows, trigger phrases, thresholds, etc.

```markdown
<!-- TEAM:<command>:START -->
### Team: `<command>` (<purpose>)

**Composition**:

| Member | Model | Color | Archetype | Domain | Owns |
|---|---|---|---|---|---|
<MEMBER_ROWS>

**Dispatch** — trigger phrases:
- VN: <vn_triggers>
- EN: <en_triggers>
- Slash command: `/<command> <task>`

**Pipeline** (<N> active stages):
<PIPELINE_STAGES>

**Review thresholds**:
- Correctness: PASS
- Architectural fidelity: <threshold_architectural>/10
- Code quality: <threshold_code>/10
- Test coverage: <threshold_tests>/10
<OPTIONAL_CRITERIA_ROWS>

**Test ownership** (if applicable):
<TEST_OWNERSHIP_TABLE>

**Runtime skill**: `.claude/skills/<command>/SKILL.md`
**Workflow rules**: `.claude/rules/team-workflow.md`
<!-- TEAM:<command>:END -->
```

### Member row format

Each member row in the composition table:

```
| `<name>` | <model> | <color> | <Archetype> | <domains> (comma-joined) | `<scope>` |
```

### Pipeline stages format (conditional)

Include only stages applicable to the team's archetype composition:

```markdown
1. Requirements excavation (Lead)
2. Exhaustive brainstorming (Lead) — if complex tasks expected
3. Architecture-grade plan (Lead)
4. Contract negotiation (Lead + Executor) — *if Executor present*
5. Spawn team (parallel)
6. Active supervision (Lead)
7. SA-grade review (Lead)
8. QA trigger (after code approved) — *if QA present*
9. Fix loops with pivot option — *if Executor present*
10. Delivery + log cleanup
```

### Optional criteria rows format

```markdown
- Accessibility (P0): keyboard, ARIA, contrast, reduced-motion — *if enabled*
- Performance: <budget> — *if enabled*
- Security: no P0 vulns — *if enabled*
```

### Test ownership table format (conditional — only if both Executor and QA present)

```markdown
| Owner | Location | Scope |
|---|---|---|
| `<executor-name>` | co-located (`src/**/*.test.*`) | Happy path + obvious edges |
| `<qa-name>` | `./tests/qa/<task-id>/` | Integration, regression, security, perf, edges, a11y |
```

---

## Regex reference (for parse algorithm in SKILL.md)

- Outer extract: `<!-- AGENT-TEAM:START[\s\S]*?<!-- AGENT-TEAM:END -->`
- Inner extract: `<!-- TEAM:([a-z][a-z0-9-]+):START -->[\s\S]*?<!-- TEAM:\1:END -->`
- Command name format: `^[a-z][a-z0-9-]{1,30}$`

Fallback parse (if backreference `\1` fails): find `<!-- TEAM:<cmd>:START -->` then scan forward for nearest `<!-- TEAM:<cmd>:END -->` where `<cmd>` matches.
