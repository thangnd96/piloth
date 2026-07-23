# Piloth Discovery — Workflow Skill (front-of-phase discovery gate)

## Purpose

Confirm **open questions before a phase commits**, instead of asking them
one-at-a-time in chat or silently guessing. Turn the questions into a
point-and-click questionnaire (`DISCOVERY.md`), open it in the **Governed Visual
Review** tool, let the human answer/annotate, then resume the phase from the
confirmed choices. This is the mirror image of a finished-artifact review: it
runs at the **start** of a phase (most often Plan, also Prototype/Design).

Reimplemented 1:1 from aidlc's `discovery-gate` DNA, but built for Piloth: the
review surface is `pilothOS/tools/review` (not annotron), and the durable record
is Piloth **evidence + contract**, not a pipeline artifact.

Recommended model: **strong** (reasoning-heavy). Carried mechanically via the
contract `model_hints` (e.g. `{"discovery": "strong"}`); advisory on harnesses
that cannot pin a per-phase model.

## Non-Responsibilities

- **`DISCOVERY.md` is a working doc — never a `produces` / `depends_on`
  artifact.** The durable output is a `## Discovery decisions` section written
  into the phase's real artifact (PRD/plan) **plus** `os-evidence kind=discovery`.
- Does not decide policy or run the phase's implementation.
- Does not edit the rendered HTML (see MD-canonical rule).

## When to invoke (the gate rule)

Run this gate **instead of asking inline** when either holds:

- there are **≥ 3 open questions** before you can write a good artifact, **or**
- there is **any single high-impact question** — scope, architecture, or
  acceptance criteria.

A small / clear task with no such questions **skips the gate** — write the
artifact directly, no review round. This is a rule the phase skill follows, not
automatic behaviour (`suggest_phase_plan` may *recommend* discovery in
`os-status`, but never enables it).

## Tools & paths

Zero-dependency, Node built-ins only (the review tool renders Markdown itself —
no separate render step):

- Review CLI: `R = pilothOS/tools/review/bin/review`
- Artifacts dir: `A = pilothOS/memory/state/os-runs/<task-id>/artifacts`
- Working doc: `MD = $A/DISCOVERY.md`

**MD-canonical rule:** Markdown is the source; the browser renders it. Feedback
arrives as selectors/notes on the rendered view, but you **always apply edits to
`$MD`**, then let the tool live-reload. Never hand-edit rendered HTML.

## Loop

1. **Compose the questionnaire.** Write `$MD` — a `# Discovery — <task>` doc
   where each open question is its own `## Q<n>: <question>` section with:
   - a checkbox list of concrete options (`- [ ] Option A`, `- [ ] Option B`, …);
   - an `- [ ] Other / notes:` line with a blank for freeform input;
   - a `- [x] Decide for me` **default the agent pre-ticks** — so a human who
     just clicks Finalize still resolves every question (pick a sensible default
     and say so).

   Keep questions decision-shaped and mutually exclusive where possible. Group
   by topic (scope, users, data, density, edge cases, boundaries). One question
   per behaviour.

2. **Open.** `$R open "$MD" --agent` — starts the loopback server (if needed),
   registers the file, opens the editor in the browser. Print the editor URL.
   Tell the user: turn on annotate, tick the options / add notes on the "Other"
   lines, then **Send** — or type a message. The pre-ticked "Decide for me"
   defaults stand for anything left untouched. They can end by clicking Finalize
   or typing "done" / "xong" and Send.

3. **Wait for feedback.** `$R poll "$MD"` — blocks until the user sends. Read the
   JSON: `items[]` (each `{kind, selector, text, note}`), `message`, and
   `finalized`. Empty/timeout with nothing → run it again.

   **End signal:** `finalized: true`, OR a `message` that is essentially just
   "done" / "xong" / "finalize" / "stop" with no `items` → go to step 5.

4. **Apply answers to `$MD` (only this file).** Tick/clear checkboxes, record
   selected values and "Other" notes, fold text annotations into the matching
   question. Then re-arm: `$R poll "$MD" --reply "<short summary of what you
   captured>"` — the browser live-reloads. Loop back to step 3. During the loop
   edit **only** `$MD`.

5. **Finalize — record decisions, hand back (do NOT re-arm).**
   - Append a `## Decisions` section to `$MD`: one line per resolved question →
     chosen answer (including any "Decide for me" defaults that stood).
   - Record the durable evidence:
     `python3 pilothOS/scripts/pilothos_guard.py os-evidence '{"kind":"discovery",
     "discovery_doc":"<$MD>","decisions":[{"q":"…","answer":"…","source":"user|decide_for_me_default"}]}'`
   - **Do not call `poll` again** (`--reply` re-arms and would hang). Optionally
     `$R stop`.
   - Return to the calling phase, which writes the decisions into its **real
     artifact** (Plan → a `## Discovery decisions` section) and proceeds. If the
     run was opened with `requires_discovery`, this evidence is what the
     Traceability gate traces to.

## Verification

- `os-evidence kind=discovery` recorded with a non-empty `decisions[]`
  (validated by the guard: each decision needs `q` + `answer`).
- `## Decisions` present in `$MD`; the phase artifact carries the folded
  decisions.
- `$MD` is **not** listed in any `produces` / `depends_on`.

## Failure & Escalation

- Server down → the review tool is fail-open; fall back to asking the top 1–2
  high-impact questions inline and disclose that discovery ran degraded.
- User never finalizes → after a reasonable prompt, record the "Decide for me"
  defaults as the decisions and disclose the assumption.

## References

- Governed Visual Review: `pilothOS/tools/review/README.md`
- Prototype phase (uses this gate to pick a design method): `../piloth-prototype/SKILL.md`
- Lifecycle & evidence: `pilothOS/runtime/task-lifecycle.md`, `pilothOS/runtime/os-control-plane.md`
