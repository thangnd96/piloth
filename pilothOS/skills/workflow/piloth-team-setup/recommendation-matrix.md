# Recommendations Matrix

Single source of truth for `(Recommended)` markers across all elicitation stages.

PilothOS Team Setup skill reads this file to build dynamic option lists. Per AskUserQuestion convention: recommended option goes **first** + label suffix `(Recommended)`. multiSelect: all recommended items get suffix, sorted to top by signal strength.

## How to apply

1. After Stage 2 (command_name) → look up Section 1 → seed Stage 2.5 default
2. After Stage 2.5 (team_profile chosen) → drives Sections 2, 5, 6, 7
3. Per member at Stage 4 → combine `(profile, archetype)` for Sections 2, 3, 4
4. Stage 6 → profile + Section 5/6/7

If profile = `custom` → fall back to archetype-only recommendations (skip profile-keyed columns).

---

## Section 1 — command_name → profile auto-suggest

| command_name pattern | suggested profile |
|---|---|
| `team-frontend*` | team-frontend |
| `team-backend*` | team-backend |
| `team-fullstack*`, `piloth-team` | team-fullstack |
| `team-qa*`, `team-qc*` | team-qa |
| (other) | custom |

---

## Section 2 — Domain reco matrix `(profile × archetype) → top 3 domains`

multiSelect, max 3, `general` exclusive. Top-N marked `(Recommended)` and reordered to top.

| profile | Executor | QA | Reviewer | Specialist |
|---|---|---|---|---|
| team-frontend | frontend, a11y, perf | a11y, frontend, perf | general | frontend |
| team-backend | backend, db, security | security, backend, db | general | backend |
| team-fullstack | frontend, backend, perf | security, a11y, perf | general | frontend |
| team-qa | a11y, security, perf | a11y, security, perf | general | security |
| custom | (archetype default) | (archetype default) | general | general |

Archetype default fallback (when profile=custom):
- Executor → `general`
- QA → `security, a11y` (top 2)
- Reviewer → `general`
- Specialist → `general`

Validation: `general` cannot coexist with any other domain. Re-elicit if violated.

---

## Section 3 — Model reco `archetype → model`

| Archetype | Recommended | Description hint |
|---|---|---|
| Executor | sonnet | Fast, capable for impl work |
| QA | sonnet | Skeptical analysis, fast |
| Reviewer | opus | Deep reasoning needed |
| Specialist | opus | Domain-deep analysis |

---

## Section 4 — Color reco `archetype → color`

| Archetype | Recommended |
|---|---|
| Executor | blue |
| QA | yellow |
| Reviewer | purple |
| Specialist | orange |

---

## Section 5 — MCP reco `profile → recommended MCPs`

multiSelect. Mark `(Recommended)` and sort to top.

| profile | Figma | Atlassian | Playwright | Database/SQL | GitHub |
|---|---|---|---|---|---|
| team-frontend | ✓ | ✓ | ✓ | | |
| team-backend | | ✓ | | ✓ | ✓ |
| team-fullstack | ✓ | ✓ | ✓ | ✓ | ✓ |
| team-qa | | ✓ | ✓ | | |
| custom | | ✓ | | | |

Atlassian recommended for all profiles (universal PM/docs).

`Other` and `None` never marked recommended.

---

## Section 6 — Stack + test framework reco `profile → stack + test/lint`

| profile | Recommended stack | Recommended test/lint |
|---|---|---|
| team-frontend | Frontend (React/Vue/Next.js) | Jest + RTL + ESLint/Prettier |
| team-backend | Backend API (Node/Python/Go) | Jest + ESLint/Prettier (or pytest+ruff) |
| team-fullstack | Full-stack | Jest + RTL + ESLint/Prettier |
| team-qa | (whatever stack project uses) | Vitest + ESLint/Prettier |
| custom | (no preset) | (no preset) |

Stack `Other` triggers free-text. Test/lint follows stack:
- Frontend → Jest+RTL or Vitest
- Backend Node → Jest
- Backend Python → pytest+ruff
- Backend Go → Go testing+gofmt

---

## Section 7 — Threshold preset reco `profile → preset`

| profile | Recommended | Optional add-ons recommended |
|---|---|---|
| team-frontend | Default (arch 8, code 7, tests 7) | + Accessibility (P0), + Performance budget |
| team-backend | Strict (arch 9, code 8, tests 8) | + Security gate |
| team-fullstack | Default | + Accessibility, + Security |
| team-qa | Strict | + Accessibility, + Security, + Performance |
| custom | Default | (none) |

---

## Marker rendering rules

1. **Single-select question**: recommended option goes first, label = `<original> (Recommended)`. Other options retain order.
2. **multiSelect question**: ALL recommended options sorted to top, each suffix `(Recommended)`. Non-recommended retain original order below.
3. **Conflict resolution**: when 2+ signals disagree (e.g., profile says X, archetype says Y), profile wins for stages 2.5/6/7; archetype wins for member-level stages (3/4).
4. **`custom` profile**: skip profile-keyed recos, fall back to archetype-only.
5. **Missing data**: if archetype not yet known at the question, use profile-only.

---

## Examples

### Example A — team-frontend Executor
- Stage 4 Sub-A Q3 (domain): options reordered to `[frontend (R), a11y (R), perf (R), backend, db, security, general, Other]`
- Stage 4 Sub-B Q1 (model): options reordered to `[sonnet (R), opus, haiku]`

### Example B — team-backend QA
- Stage 4 Sub-A Q3: `[security (R), backend (R), db (R), frontend, a11y, perf, general, Other]`
- Stage 6 Q3 (MCPs): `[Atlassian (R), Database/SQL (R), GitHub (R), Figma, Playwright/Browser, Other, None]`

### Example C — custom profile, Executor
- Stage 4 Sub-A Q3: `[general (R), frontend, backend, db, security, a11y, perf, Other]` (archetype-only fallback)
- Stage 6 Q3: `[Atlassian (R), Figma, Playwright/Browser, Database/SQL, GitHub, Other, None]` (universal Atlassian only)
