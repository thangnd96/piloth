# Elicitation Schemas

Exact `AskUserQuestion` JSON schemas for all 11 stages of the setup workflow. Each section: rationale + schema + follow-up logic + validation rules.

All user-facing questions MUST use `AskUserQuestion`. Plain-text question messages are FORBIDDEN.

---

## Stage 0a — Multi-team mode

Rationale: detect existing teams before overwriting anything.
Trigger: `<!-- AGENT-TEAM:START -->` found in CLAUDE.md. Parse inner `<!-- TEAM:<cmd>:START -->` markers to list existing team names.
Call: `AskUserQuestion` with 1 question.

```json
{
  "questions": [
    {
      "question": "Existing team(s) detected: <list existing commands>. What would you like to do?",
      "header": "Multi-team setup",
      "options": [
        { "label": "Update existing team", "description": "Re-configure one of the existing teams" },
        { "label": "Create new team", "description": "Add a second (or additional) team alongside existing" },
        { "label": "Cancel", "description": "Exit setup without changes" }
      ],
      "multiSelect": false
    }
  ]
}
```

Follow-up: if "Update existing team" → present list of existing command names; user picks via free-text (Other option). Proceed to Stage 1 with that command pre-filled.

---

## Stage 1 — Existing artifacts

Rationale: idempotency — ask per artifact rather than blanket overwrite.
Trigger: for each file that already exists from a prior setup run.
Call: `AskUserQuestion` once per detected existing file.

```json
{
  "questions": [
    {
      "question": "File already exists: <filepath>. What should we do with it?",
      "header": "Existing file: <filename>",
      "options": [
        { "label": "Overwrite", "description": "Replace with newly generated version" },
        { "label": "Keep", "description": "Skip this file, keep current version" },
        { "label": "Show diff first", "description": "Review differences before deciding" }
      ],
      "multiSelect": false
    }
  ]
}
```

Special case — existing `## Agent Team` section without sentinel markers:

```json
{
  "questions": [
    {
      "question": "CLAUDE.md has an '## Agent Team' section without sentinel markers. How should setup handle it?",
      "header": "CLAUDE.md agent-team section",
      "options": [
        { "label": "Wrap in sentinel", "description": "Add sentinel markers around existing content (preserves it)" },
        { "label": "Replace", "description": "Replace entire section with generated sentinel block" },
        { "label": "Skip CLAUDE.md", "description": "Leave CLAUDE.md unchanged" }
      ],
      "multiSelect": false
    }
  ]
}
```

---

## Stage 2 — Team meta (3 questions)

Rationale: establish team identity before eliciting members.
Call: single `AskUserQuestion` with 3 questions.

```json
{
  "questions": [
    {
      "question": "Command name for this team (used as slash command and team identifier)?",
      "header": "Team command name",
      "options": [
        { "label": "team-frontend", "description": "For frontend-focused teams" },
        { "label": "team-backend", "description": "For backend-focused teams" },
        { "label": "team-fullstack", "description": "For full-stack teams" },
        { "label": "piloth-team", "description": "Match existing piloth-team namespace" },
        { "label": "Other", "description": "Enter custom name (kebab-case, e.g. team-mobile)" }
      ],
      "multiSelect": false
    },
    {
      "question": "Which archetypes will this team include?",
      "header": "Team archetype catalog",
      "options": [
        { "label": "Executor", "description": "Strict implementer — code + co-located tests + execution logging" },
        { "label": "QA", "description": "Skeptical parallel QA — integration/regression/security/a11y tests" },
        { "label": "Reviewer", "description": "Read-only code reviewer — scoring rubric, APPROVED/NEED_FIX verdict" },
        { "label": "Specialist", "description": "Domain expert — design/security/perf/data analysis via MCP bridge" }
      ],
      "multiSelect": true
    },
    {
      "question": "Trigger phrases for this team (in addition to defaults)?",
      "header": "Trigger phrases",
      "options": [
        { "label": "Default only", "description": "VN: giao cho team, team làm, nhờ team | EN: delegate to team, let the team handle" },
        { "label": "Add custom phrases", "description": "Append project-specific triggers via Other" },
        { "label": "Other", "description": "Enter custom phrases (comma-separated)" }
      ],
      "multiSelect": false
    }
  ]
}
```

Validation: command name must match `^[a-z][a-z0-9-]{1,30}$`. If "Other" entered and validation fails → re-elicit with error message via AskUserQuestion (max 3 retries, then use "team-custom" default + warn).

---

## Stage 2.5 — Team profile (mandatory)

Rationale: drive `(Recommended)` markers across Stages 4 and 6. Pinned single source of truth — see [recommendations.md](recommendations.md).
Auto-suggest based on `command_name` from Stage 2 (recommendations.md §1).
Call: `AskUserQuestion` with 1 question.

```json
{
  "questions": [
    {
      "question": "Team profile? Drives recommended options across subsequent stages.",
      "header": "Team profile",
      "options": [
        { "label": "team-frontend", "description": "Frontend-focused — Recommended if cmd starts with team-frontend" },
        { "label": "team-backend", "description": "Backend-focused — Recommended if cmd starts with team-backend" },
        { "label": "team-fullstack", "description": "Full-stack — Recommended for team-fullstack/piloth-team" },
        { "label": "team-qa", "description": "QA/QC-focused — Recommended if archetypes only QA" },
        { "label": "custom", "description": "No preset — fall back to archetype-only recommendations" }
      ],
      "multiSelect": false
    }
  ]
}
```

Apply rules per recommendations.md §1:
- cmd starts `team-frontend` → reorder so `team-frontend` is first + suffix `(Recommended)`
- cmd starts `team-backend` → `team-backend` first + `(Recommended)`
- cmd ∈ {`team-fullstack`, `piloth-team`} → `team-fullstack` first + `(Recommended)`
- archetypes (Stage 2) ⊆ {QA} → `team-qa` first + `(Recommended)`
- otherwise → no recommended marker; first option `custom`

Validation: enum required from set {`team-frontend`, `team-backend`, `team-fullstack`, `team-qa`, `custom`}. Re-elicit on invalid (max 3 retries). Mandatory — no skip path.

Output: store as `team_profile` for use in Stages 4 + 6.

---

## Stage 3 — Member count (1 question)

Rationale: drive the per-member loop iteration count.
Call: `AskUserQuestion` with 1 question.

```json
{
  "questions": [
    {
      "question": "How many team members (excluding Lead)?",
      "header": "Member count",
      "options": [
        { "label": "1", "description": "Single specialist or solo executor" },
        { "label": "2", "description": "Standard executor + QA pair" },
        { "label": "3", "description": "Executor + QA + Reviewer or Specialist" },
        { "label": "4+", "description": "Enter exact number" }
      ],
      "multiSelect": false
    }
  ]
}
```

Follow-up: if "4+" → request exact number via Other. Validate 1–10. If outside range → re-elicit (max 3 retries, then use 4 + warn).

---

## Stage 4 — Per-member loop (Sub-A + collision + Sub-B)

Repeat for each of N members. Per member: Sub-A `AskUserQuestion` (3q) → collision `AskUserQuestion` if needed (1q) → Sub-B `AskUserQuestion` (3-4q).

### Stage 4 Sub-A — Identity (3 questions)

```json
{
  "questions": [
    {
      "question": "Member <N> name (used as agent filename and sender ID)?",
      "header": "Member <N> — Name",
      "options": [
        { "label": "Other", "description": "Enter name (lowercase, letters/digits/hyphens, e.g. dev-alice)" }
      ],
      "multiSelect": false
    },
    {
      "question": "Archetype for member <N>?",
      "header": "Member <N> — Archetype",
      "options": [
        { "label": "Executor", "description": "Implementer — code + tests + logging" },
        { "label": "QA", "description": "Skeptical QA — integration/regression/edges" },
        { "label": "Reviewer", "description": "Read-only reviewer — rubric scoring" },
        { "label": "Specialist", "description": "Domain expert — analysis via MCP bridge" }
      ],
      "multiSelect": false
    },
    {
      "question": "Domain focus for member <N>? (multi-select, max 3 — `general` exclusive)",
      "header": "Member <N> — Domains",
      "options": [
        { "label": "frontend", "description": "UI, components, accessibility, browser" },
        { "label": "backend", "description": "API, services, auth, data access" },
        { "label": "db", "description": "Schema, migrations, queries, indexing" },
        { "label": "security", "description": "Auth/authz, injection, PII, secrets" },
        { "label": "a11y", "description": "Accessibility — WCAG, keyboard, ARIA" },
        { "label": "perf", "description": "Performance, latency, memory, bundle" },
        { "label": "general", "description": "No specific domain — exclusive (clears others)" },
        { "label": "Other", "description": "Enter custom domain" }
      ],
      "multiSelect": true
    }
  ]
}
```

Recommendation reorder (per recommendations.md §2): top-N options based on `(team_profile, archetype)` get suffix `(Recommended)` and sort to top.

Examples:
- profile=team-frontend, archetype=Executor → reorder `[frontend (Recommended), a11y (Recommended), perf (Recommended), backend, db, security, general, Other]`
- profile=team-backend, archetype=QA → reorder `[security (Recommended), backend (Recommended), db (Recommended), frontend, a11y, perf, general, Other]`
- profile=custom → archetype default only (Executor/Reviewer/Specialist → `general (Recommended)`; QA → `security (Recommended), a11y (Recommended)`)

Validation:
- name must match `^[a-z][a-z0-9-]{1,30}$`. Re-elicit on fail (max 3 retries).
- domains: array length 1-3.
- `general` exclusive — cannot coexist with any other domain. If user picks `general` + others → reject with message "general is exclusive — pick general alone OR pick specific domains" and re-elicit (max 3 retries).

### Stage 4 — Collision check (1 question, triggered if agent file exists)

Trigger: `.claude/agents/<name>.md` exists.

```json
{
  "questions": [
    {
      "question": "Agent file .claude/agents/<name>.md already exists (team: <existing-team>). What should we do?",
      "header": "Agent name collision",
      "options": [
        { "label": "Reuse", "description": "Keep existing agent file as-is (same agent, multiple teams)" },
        { "label": "Pick different name", "description": "Go back and enter a different name for this member" },
        { "label": "Overwrite", "description": "Replace existing agent file with new configuration" }
      ],
      "multiSelect": false
    }
  ]
}
```

Follow-up: if "Pick different name" → loop back to Sub-A name question for this member.

### Stage 4 Sub-B — Configuration (3-4 questions)

```json
{
  "questions": [
    {
      "question": "Model for member <name>?",
      "header": "Member <name> — Model",
      "options": [
        { "label": "sonnet", "description": "Recommended for Executor and QA (fast, capable)" },
        { "label": "haiku", "description": "Fastest, lowest cost — simple tasks only" },
        { "label": "opus", "description": "Recommended for Specialist and Reviewer (deep reasoning)" }
      ],
      "multiSelect": false
    },
    {
      "question": "Color for member <name> (used in agent UI)?",
      "header": "Member <name> — Color",
      "options": [
        { "label": "blue", "description": "Default for Executor" },
        { "label": "yellow", "description": "Default for QA" },
        { "label": "purple", "description": "Default for Reviewer" },
        { "label": "orange", "description": "Default for Specialist" },
        { "label": "green", "description": "" },
        { "label": "red", "description": "" },
        { "label": "cyan", "description": "" },
        { "label": "gray", "description": "" }
      ],
      "multiSelect": false
    },
    {
      "question": "Tools allowlist for member <name>? (pre-filled with archetype defaults)",
      "header": "Member <name> — Tools",
      "options": [
        { "label": "Read", "description": "Read files" },
        { "label": "Write", "description": "Write files" },
        { "label": "Edit", "description": "Edit files" },
        { "label": "Grep", "description": "Search content" },
        { "label": "Glob", "description": "Find files" },
        { "label": "Bash", "description": "Run shell commands" },
        { "label": "WebSearch", "description": "Web search" },
        { "label": "WebFetch", "description": "Fetch URLs" }
      ],
      "multiSelect": true
    }
  ]
}
```

Fourth question (Executor archetype only):

```json
{
  "questions": [
    {
      "question": "Path scope for executor <name>? (glob pattern — files this member owns)",
      "header": "Member <name> — Path scope",
      "options": [
        { "label": "src/**", "description": "Standard frontend/backend source" },
        { "label": "src/frontend/**", "description": "Frontend only in monorepo" },
        { "label": "src/backend/**", "description": "Backend only in monorepo" },
        { "label": "Other", "description": "Enter custom glob pattern" }
      ],
      "multiSelect": false
    }
  ]
}
```

Validation: scope must be non-empty, no `../`, no leading `/`. Sanitize on input. Re-elicit on invalid (max 3 retries).

---

## Stage 5 — Multi-executor conflict (re-elicit on overlap)

Trigger: 2 or more Executor archetype members with overlapping path scopes (simple substring check).
Call: `AskUserQuestion` with 1 question per detected overlap.

```json
{
  "questions": [
    {
      "question": "Executors <name-A> (scope: <scope-A>) and <name-B> (scope: <scope-B>) have overlapping path scopes. Fix the conflict?",
      "header": "Executor scope conflict",
      "options": [
        { "label": "Re-enter scope for <name-A>", "description": "Adjust first executor's scope" },
        { "label": "Re-enter scope for <name-B>", "description": "Adjust second executor's scope" },
        { "label": "Keep overlap", "description": "Proceed anyway (overlap is intentional)" }
      ],
      "multiSelect": false
    }
  ]
}
```

Follow-up: if re-enter → show Sub-B scope question for chosen member. Repeat check after new input.

---

## Stage 6 — Project context (4 questions)

Rationale: parameterize generated runtime skill with project-specific stack + thresholds.
Call: single `AskUserQuestion` with 4 questions.

```json
{
  "questions": [
    {
      "question": "Project type and primary stack?",
      "header": "Project stack",
      "options": [
        { "label": "Frontend (React/Vue/Next.js)", "description": "UI-focused SPA or SSR" },
        { "label": "Backend API (Node/Python/Go)", "description": "REST or GraphQL service" },
        { "label": "Full-stack", "description": "Frontend + backend in same repo" },
        { "label": "Mobile (React Native/Flutter)", "description": "Mobile application" },
        { "label": "CLI / Library / SDK", "description": "Developer tooling" },
        { "label": "Other", "description": "Enter description" }
      ],
      "multiSelect": false
    },
    {
      "question": "Test framework and lint tooling?",
      "header": "Test + lint",
      "options": [
        { "label": "Jest + RTL + ESLint/Prettier", "description": "React/Node standard" },
        { "label": "Vitest + ESLint/Prettier", "description": "Vite-based projects" },
        { "label": "pytest + ruff", "description": "Python" },
        { "label": "Go testing + gofmt", "description": "Go" },
        { "label": "Other", "description": "Enter framework + lint tool names" }
      ],
      "multiSelect": false
    },
    {
      "question": "MCPs configured in your main session?",
      "header": "MCPs available",
      "options": [
        { "label": "Figma", "description": "Design extraction (frontend/fullstack)" },
        { "label": "Atlassian", "description": "Jira/Confluence — universal PM/docs" },
        { "label": "Playwright/Browser", "description": "Interactive UI testing + QC automation" },
        { "label": "Database/SQL", "description": "Schema + query (backend/fullstack)" },
        { "label": "GitHub", "description": "PRs, issues, code search (backend/fullstack)" },
        { "label": "Other", "description": "Enter MCP names" },
        { "label": "None", "description": "No MCPs configured" }
      ],
      "multiSelect": true
    },
    {
      "question": "Review thresholds and optional criteria?",
      "header": "Review standards",
      "options": [
        { "label": "Default (arch 8, code 7, tests 7)", "description": "Standard project bar" },
        { "label": "Strict (arch 9, code 8, tests 8)", "description": "High-quality production systems" },
        { "label": "MVP (arch 7, code 6, tests 6)", "description": "Speed over rigor" },
        { "label": "Custom thresholds", "description": "Specify each value" },
        { "label": "+ Accessibility (P0)", "description": "Add keyboard/ARIA/contrast gate" },
        { "label": "+ Performance budget", "description": "Add latency/memory threshold" },
        { "label": "+ Security gate", "description": "Add no-P0-vuln requirement" }
      ],
      "multiSelect": true
    }
  ]
}
```

Follow-up (based on answers):
- "Other" stack → enter description via free text
- "Other" test/lint → enter framework + lint tool names
- "Other" MCP → enter MCP names comma-separated (max 5 entries)
- Recommendation reorder per recommendations.md §5: Atlassian universal `(Recommended)`; profile=frontend → Figma + Playwright also `(Recommended)`; profile=backend → Database/SQL + GitHub also `(Recommended)`; profile=fullstack → all 5 `(Recommended)`
- "Custom thresholds" → enter values for each criterion (architectural, code quality, test coverage)
- "+ Performance budget" → enter budget string (e.g. `<200ms p95`, `Lighthouse >90`)

---

## Stage 7 — QA verdict hook opt-in (1 question, only if QA archetype present)

Rationale: optional enforcement gate — only meaningful when team has QA member.
Call: `AskUserQuestion` with 1 question. Skip entirely if no QA archetype in team.

```json
{
  "questions": [
    {
      "question": "Enable QA verdict gate hook? When enabled, TaskCompleted events are blocked until QA report shows Verdict: PASS.",
      "header": "QA verdict hook (optional)",
      "options": [
        { "label": "Yes, enable hook", "description": "Adds TaskCompleted hook to .claude/settings.json — enforces QA gate" },
        { "label": "No, skip hook", "description": "No settings.json changes — QA verdict is advisory only" }
      ],
      "multiSelect": false
    }
  ]
}
```

Note: skipped entirely when team has no QA archetype member.

---

## Stage 8 — Confirm (1 question)

Rationale: final summary before any files are written.
Call: `AskUserQuestion` with 1 question. Show full config summary before presenting.

```json
{
  "questions": [
    {
      "question": "Ready to generate team files with the above configuration?",
      "header": "Confirm setup",
      "options": [
        { "label": "Proceed — generate files", "description": "Write all files now" },
        { "label": "Adjust configuration", "description": "Go back and change a specific stage" },
        { "label": "Cancel", "description": "Exit without writing any files" }
      ],
      "multiSelect": false
    }
  ]
}
```

Follow-up: if "Adjust" → ask which stage to re-elicit (0a / 1 / 2 / 2.5 / 3 / 4 / 5 / 6 / 7) via AskUserQuestion single-select.

---

## Validation rules

| Field | Regex / Rule | Re-elicit on fail |
|---|---|---|
| Member name | `^[a-z][a-z0-9-]{1,30}$` | Yes, max 3 retries then error |
| Command name | `^[a-z][a-z0-9-]{1,30}$` | Yes, max 3 retries then "team-custom" |
| Team profile | enum `{team-frontend, team-backend, team-fullstack, team-qa, custom}` | Yes, max 3 retries (mandatory — no default) |
| Domains | array length 1-3, items ∈ enum, `general` exclusive | Yes, max 3 retries |
| Path scope | non-empty, no `../`, no leading `/` | Yes, max 3 retries |
| Member count | integer 1–10 | Yes, max 3 retries then 4 |
| Thresholds | integer 1–10 per criterion | Default on invalid |

---

## Fallback — AskUserQuestion unavailable

When `AskUserQuestion` tool is not in the current environment, fall back to batched text prompt. This is the ONLY case where plain-text questions are acceptable.

```
Setup info needed (reply each line, or "default" for all):

MULTI-TEAM (Stage 0a — skip if first setup):
0a. Existing team action: [update / new / cancel]

TEAM META (Stage 2):
2a. Command name: [team-frontend / team-backend / team-fullstack / piloth-team / custom]
2b. Archetypes: [executor, qa, reviewer, specialist — comma-separated]
2c. Trigger phrases: [default / custom phrases comma-separated]

TEAM PROFILE (Stage 2.5 — mandatory):
2.5. Team profile: [team-frontend / team-backend / team-fullstack / team-qa / custom]

MEMBERS (Stage 3-4 — repeat block per member):
3. Member count: [1 / 2 / 3 / 4+]
4a-N. Member N name: <lowercase-kebab>
4b-N. Member N archetype: [executor / qa / reviewer / specialist]
4c-N. Member N domains: <comma-separated, max 3, `general` exclusive — e.g. "frontend,a11y,perf" OR "general">

4d-N. Member N model: [sonnet / haiku / opus]
4e-N. Member N scope (executor only): <glob pattern>

PROJECT CONTEXT (Stage 6):
6a. Stack: [frontend / backend / fullstack / mobile / cli / other]
6b. Test + lint: [jest-rtl / vitest / pytest / go / other]
6c. MCPs: [figma, atlassian, playwright, db, github, other, none — comma-separated]
6d. Thresholds: [default / strict / mvp / custom] + optional: [a11y, perf, security]

QA HOOK (Stage 7 — only if QA in team):
7. Enable QA verdict hook: [yes / no]
```
