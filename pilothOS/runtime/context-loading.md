# Progressive Context Loading

## Goal

Nạp đúng context cần thiết, đúng thời điểm; tránh cả context bloat lẫn context thiếu.

## Loading Order

1. Identity và Bootstrap.
2. Constitution, Rot status và Rules index.
3. Runtime contract.
4. Index của layer liên quan.
5. Chỉ các file cụ thể cần cho task.

## Routing Guide

| Task cần | Load |
|---|---|
| Policy hoặc coding behavior | `rules/` |
| Trạng thái/lịch sử task | `memory/` |
| Spec, standards, domain fact | `knowledge/` |
| Quy trình/capability tái sử dụng | `skills/` |
| Lifecycle hoặc state | `runtime/` |
| Role/model/permissions | `agents/` |
| API/CLI/MCP | `tools/` |
| Approval, budget, escalation | `governance/` |
| Acceptance hoặc quality gate | `evaluation/` |

## Consumer Asset Routing

PilothOS điều phối tài sản consumer như OS điều phối userland apps/drivers. Load
`runtime/consumer-assets.md` hoặc index tương ứng trước; chỉ load asset cụ thể
khi task signal cần nó.

Scheduler helper:

```bash
python3 pilothOS/scripts/pilothos_guard.py route-task '{"task_signal":"UI/component"}'
```

`route-task` prints a deterministic routing suggestion from the consumer asset
audit. It does not load files, run tools or write state; use its
`context_evidence` and `consumer_asset_routing` output as contract input. Use
`skipped_assets` as receipt guidance when an existing consumer asset was not
loaded because the task signal did not need it.

| Task signal | Asset type to inspect | Load policy |
|---|---|---|
| UI/component | design-system, UI docs, component library | task-routed |
| API/backend | backend conventions, API docs, test runner | task-routed |
| Bug fix | relevant tests, logs, existing module patterns | task-routed |
| Release/deploy | release commands, deploy tools | approval-required |
| Tool/MCP work | tools index + MCP config | task-routed |

Rules:

- Load index first.
- Load exact asset only when task signal requires it.
- If a consumer asset exists and task matches it, cite it in `context_evidence`.
- If an asset exists but is not loaded, receipt must explain why it is not
  applicable.
- Never move, rewrite or overwrite consumer skills/hooks/tools during routing.

For non-doc/test work, contract and receipt should include:

```json
{
  "consumer_asset_routing": [
    {
      "task_signal": "UI/component|API/backend|bug fix|release/deploy|tool/MCP|not_applicable",
      "asset_type": "skill|hook|tool|mcp|command|design-system|doc|convention|test-runner|build-runner|not_applicable",
      "decision": "loaded|skipped|approval_required|not_applicable",
      "reason": "why exact asset was loaded or why not applicable"
    }
  ]
}
```

`reuse_evidence[].decision` is restricted to `reuse`, `not_applicable` or
`not_enough`. `ui_design_system_evidence[].decision` is restricted to `reuse`,
`extend`, `new` or `not_applicable`.

## Guardrails

- Không import toàn bộ thư mục khi index đủ để route.
- Không dùng Memory thay cho Knowledge hoặc ngược lại.
- Ghi nhận Rot nếu thường xuyên nạp thiếu hoặc thừa context.
- Resource budget và verification scope tuân theo `energy-token-policy.md`.
