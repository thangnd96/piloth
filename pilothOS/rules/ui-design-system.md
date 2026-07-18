# UI Design System Rule

When a project has a design system, component library, token catalog or UI
convention, agents must check it before creating or changing UI.

## Required Behavior

- Check the consumer design system/component library before building UI.
- Reuse existing components, tokens, spacing and patterns by default.
- Do not invent colors, spacing, variants or components when a matching design
  system asset exists.
- Create a new component only when the design system was checked, an existing
  component gap is identified, and the reason for the new component is recorded.
- Verify UI with a screenshot, visual test or UI harness when the project has
  one.

## Contract Evidence

UI contracts must include:

```json
{
  "ui_design_system_evidence": [
    {
      "source": "path/tool/component catalog",
      "checked": "component/token/pattern",
      "decision": "reuse|extend|new|not_applicable",
      "reason": "short reason"
    }
  ]
}
```

Path-based guard detection is conservative. If a UI-looking path is not actually
UI, record `not_applicable` with the reason instead of omitting the evidence.
When `allowed_paths` already includes a clear UI path pattern, `contract-write`
requires this evidence before the edit starts. For broad patterns that only
become UI after a concrete file path is known, `pre-edit` enforces the same
requirement.

## Receipt Evidence

For UI changes, receipt must state:

- `design_system_checked`
- `component_reuse_decision`
- `token_reuse_decision`
- `warning_checklist.new_component_reason` when a new component-like file is
  added

The guard checks that these fields exist; quality still requires model judgment
and, when available, screenshot/test evidence.
