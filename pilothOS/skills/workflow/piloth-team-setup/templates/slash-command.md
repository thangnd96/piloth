# Template: Slash Command

Write to `.claude/commands/{{command}}.md`. Substitute `{{command}}`.

---

```markdown
---
description: Dispatch task to {{command}} agent team (Lead as Solution Architect). Bypasses size-rejection since user explicitly invoked.
---

Activate the `{{command}}` skill to dispatch this task:

$ARGUMENTS

Follow `.claude/skills/{{command}}/SKILL.md`. User explicit-invoked — skip size-rejection. Still apply pre-flight + simplicity gate.

Details: `.claude/rules/team-workflow.md`
```
