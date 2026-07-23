# Piloth Prototype — Workflow Skill (visual UI proposal before implementation)

## Purpose

Propose the UI **visually, with ≥2 design options, before technical design or
implementation** — so the visual direction is confirmed by a human before any
code is written. Reimplemented 1:1 from aidlc's `prototype` phase DNA, built for
Piloth: options are reviewed and **picked through the reused Governed Visual
Review / `human_review` round-trip**, and the outcome is recorded as Piloth
evidence (`kind=prototype`).

You are the **Designer (DES)** for this phase — load
`pilothOS/agents/team-roles/designer.md` before starting.

Recommended model: **strong** (design reasoning). Carried via contract
`model_hints` (e.g. `{"prototype": "strong"}`); advisory where per-phase models
cannot be pinned.

## Non-Responsibilities

- Does **not** finalize the technical design or implement the chosen UI — that
  is the Execute phase, which reads `PROTOTYPE.md` + the chosen option.
- Does **not** invent a parallel review mechanism: the human pick reuses
  `review-request` / `review-feedback` / `review-verify` (the `human_review`
  gate). `requires_prototype` implies `requires_human_review`.

## Preconditions

- An active OS run whose contract sets `requires_prototype: true` (which the
  guard expands to `requires_human_review: true`). Recommended for UI/component
  work; `suggest_phase_plan` may recommend it in `os-status`.

## Paths

- Review CLI: `R = pilothOS/tools/review/bin/review`
- Artifacts dir: `A = pilothOS/memory/state/os-runs/<task-id>/artifacts`
- Options: `$A/PROTOTYPE-option{1..N}.html` · Summary: `$A/PROTOTYPE.md`

## Steps

### 1. Read context
- Task intent / PRD and any `## Discovery decisions`.
- Project design system: `pilothOS/rules/ui-design-system.md` and consumer
  `CLAUDE.md` for brand/tokens.
- Any existing tech design hints.

### 2. Choose the design method (run the discovery gate)
Invoke `../piloth-discovery/SKILL.md` with the single question **"Which design
method?"** and these options (Claude Artifacts is the default):

1. **Claude Artifacts** — fast self-contained HTML prototypes, no deps *(default)*
2. **Figma** — high-fidelity, design-system tokens (requires Figma MCP auth)
3. **shadcn/ui + Tailwind** — code-aligned mockups using real components
4. **Project Design System** — on-brand hi-fi using the consumer's design system
5. **Lo-fi wireframe** — ASCII / low-fidelity for quick structural exploration

Record the chosen method.

### 3. Generate ≥2 UI options
Produce **2–3 visually distinct variants** that each answer: layout (columns /
nav / density), visual hierarchy (primary action, emphasis), component choices
(design-system patterns reused), colour/branding, responsive (mobile, touch
targets ≥48px), dark mode.

| Method | Output | How |
|---|---|---|
| Claude Artifacts | `PROTOTYPE-option{N}.html` | via the `artifact-design` skill; each a self-contained, theme-aware HTML artifact |
| Figma | `PROTOTYPE-option{N}.figma-link.md` + screenshot | via Figma MCP; capture link + screenshot |
| shadcn/ui | `PROTOTYPE-option{N}.html` | shadcn/ui + Tailwind, self-contained |
| Design System | `PROTOTYPE-option{N}.figma-link.md` | consumer tokens/components in Figma |
| Lo-fi | `PROTOTYPE-option{N}.md` (ASCII) | structural wireframe + notes |

Write all option files into `$A`.

### 4. Annotate & compare
For each option document: **intent** (what makes it distinct), **key UX
decisions**, **component notes** (design-system patterns used), **tradeoffs**,
**responsive notes**.

### 5. Let the human pick (reuse human_review round-trip)
- Open the options in the review tool: `$R open "$A/PROTOTYPE-option1.html"
  --agent` (and/or the summary), so the human sees each variant and the
  option-picker.
- Drive the standard human-review round-trip so the pick is a first-class,
  finalized approval:
  `python3 pilothOS/scripts/pilothos_guard.py review-request <task-id>` →
  reviewer sends → `review-feedback feedback.json` (verdict `approve`,
  `finalized: true`; the chosen option in the finding note/message) →
  `review-verify <task-id>`.

### 6. Write PROTOTYPE.md + record evidence
- Write `$A/PROTOTYPE.md` with `status: awaiting_review` → the method + rationale,
  each option's intent/decisions, the **chosen option** + rationale, design
  details (layout, components, accessibility/WCAG, responsive, dark mode), and
  next steps for Execute.
- Record the prototype evidence (the guard validates ≥2 options + a chosen id +
  a valid method):
  `python3 pilothOS/scripts/pilothos_guard.py os-evidence '{"kind":"prototype",
  "method":"artifacts","prototype_doc":"<$A/PROTOTYPE.md>",
  "options":[{"id":"option1","artifact":"<$A/PROTOTYPE-option1.html>","intent":"…"},
  {"id":"option2","artifact":"<$A/PROTOTYPE-option2.html>","intent":"…"}],
  "chosen":"option2","chosen_rationale":"…"}'`

The Execute phase then reads `PROTOTYPE.md` + the chosen option and implements to
match.

## Verification

- `os-evidence kind=prototype` recorded → `prototype` gate PASS at `os-close`
  (≥2 options, chosen ∈ options, valid method).
- `human_review` gate PASS (verdict `approve`, finalized, no unresolved
  blocker/major) — the human actually picked.
- `PROTOTYPE.md` records method, options, chosen option, design details.

## Failure & Escalation

- Fewer than 2 distinct options → the `prototype` gate FAILs and `os-close`
  routes back to Repair; generate a genuine second variant.
- Human requests changes (blocker/major) → routed to Repair; regenerate/adjust
  and re-run the pick.

## References

- Governed Visual Review: `pilothOS/tools/review/README.md`
- Discovery gate: `../piloth-discovery/SKILL.md`
- Designer persona: `pilothOS/agents/team-roles/designer.md`
- UI design system rule: `pilothOS/rules/ui-design-system.md`
- Gates & lifecycle: `pilothOS/evaluation/quality-gates.md`, `pilothOS/runtime/task-lifecycle.md`
