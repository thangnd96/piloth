# Tools / MCP / CLI — Index

## Purpose

Quản lý INTEGRATION với thế giới bên ngoài.

## Responsibilities

- Liệt kê tool, capability, config location và health check.
- Theo dõi API/schema/dependency changes.

## Non-Responsibilities

- Không chứa business logic hoặc policy.
- Không nhúng credentials vào markdown.
- Không nạp mặc định vào Identity context.

## Tools

| Tool | Type | Capability | Config | Risk | Health Check | Approval | Timeout | Evidence Output |
|---|---|---|---|---|---|---|---|---|
| Không có Tool bắt buộc | N/A | PilothOS hoạt động độc lập với tool cụ thể | N/A | low | N/A | N/A | N/A | N/A |

Consumer Asset Registry liên quan: `pilothOS/runtime/consumer-assets.md`.
Consumer assets có type `tool`, `mcp`, `command`, `test-runner` hoặc
`build-runner` phải được route qua index này khi task cần integration.

## Approval Defaults

| Risk | Default |
|---|---|
| low | May run when referenced by the active task contract |
| medium | Run only when task evidence needs it |
| high | Require approval before mutation or external side effect |

High-risk examples:

- deploy;
- destructive scripts;
- production DB;
- external write APIs;
- secret-bearing commands.

## Pre-Run Tool Check

Before running a tool command with mutation, external side effects or uncertain
risk, run:

```bash
python3 pilothOS/scripts/pilothos_guard.py tool-check <tool-check.json>
```

Payload:

```json
{
  "tool": "tool name",
  "command": "command to run",
  "risk": "low|medium|high",
  "timeout": "timeout to use, e.g. 500ms, 30s, 5m, or 1h",
  "expected_evidence": "what output/artifact will prove the command result",
  "approval_evidence": "required before high-risk tool use"
}
```

Under `standard` or `strict`, `tool-check` requires an active task contract and
the tool name, command or expected evidence must be referenced in the contract
evidence/routing fields. This keeps low/medium-risk tools tied to the current
task evidence instead of being run opportunistically. `light` preset keeps only
the basic payload/risk/approval checks.

## Receipt Requirements

- If a receipt cites a tool command, the result must be recorded.
- If a tool was skipped, the receipt must include the limitation.
- If a high-risk tool is used, the receipt must include approval evidence.
- Under `standard` or `strict`, each `tool_uses` entry requires an active task
  contract and must be referenced by that contract through the tool name,
  command or evidence output.

Tool evidence shape in receipt:

```json
{
  "tool_uses": [
    {
      "tool": "tool name",
      "command": "command if applicable",
      "risk": "low|medium|high",
      "timeout": "timeout used, e.g. 500ms, 30s, 5m, or 1h",
      "result": "result/output summary",
      "evidence_output": "stdout/stderr/artifact summary or path",
      "approval_evidence": "required for high risk",
      "limitation": "required when skipped/failed/not run"
    }
  ],
  "approval_evidence": "receipt-level approval evidence when applicable"
}
```

## Convention

Tool chỉ là adapter. Mọi thay đổi API/schema phải cập nhật index và Rot Log.

## Review Checklist

- API, schema, dependency hoặc CLI contract có thay đổi không?
- Tool nào deprecated, lỗi health check hoặc không còn được sử dụng?
- Credentials và configuration có được tách khỏi markdown không?
- Adapter có đang chứa business logic hoặc policy không?
