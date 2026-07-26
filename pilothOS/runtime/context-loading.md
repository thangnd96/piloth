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

Routing chạy bên trong `os-start`: nó gọi Evidence Router, ghi
`consumer_asset_routing` và `context_evidence` thẳng vào contract. Không cần gọi
lệnh routing riêng — đọc contract mà `os-start` trả về.

Tám task signal hợp lệ, khớp `TASK_SIGNAL_ROUTES` trong guard:

| Task signal | Asset type to inspect | Load policy |
|---|---|---|
| UI/component | design-system, doc, skill | task-routed |
| API/backend | convention, doc, test-runner | task-routed |
| bug fix | test-runner, convention, doc | task-routed |
| release/deploy | command, tool, build-runner | approval-required |
| tool/MCP | tool, mcp, command | task-routed |
| architecture | specialist, agent, convention, doc | task-routed |
| security | specialist, agent, tool, test-runner | approval-required |
| not_applicable | not_applicable | never-auto |

Rules:

- Load index first.
- Load exact asset only when task signal requires it.
- If a consumer asset exists and task matches it, cite it in `context_evidence`.
- If an asset exists but is not loaded, receipt must explain why it is not
  applicable.
- Never move, rewrite or overwrite consumer skills/hooks/tools during routing.

## Structural Code Routing

Khi task cần caller/callee, impact hoặc cross-file architecture: dùng search
trực tiếp trên source (`rg`, glob, đọc file). Bắt đầu bằng truy vấn hẹp, chỉ mở
rộng khi kết quả chưa đủ.

Piloth không duy trì code graph. Bản trước có một index SQLite chỉ parse sâu
được Python và chưa từng được trích dẫn làm evidence trong bất kỳ task thật nào;
nó bị gỡ thay vì tiếp tục ship một engine tự khai là chưa đạt SLA của chính mình.
Kết luận âm ("không có chỗ nào gọi X") vẫn cần coverage rõ ràng: nêu đã tìm ở đâu
và bằng cách nào.

For non-doc/test work, contract and receipt should include:

```json
{
  "consumer_asset_routing": [
    {
      "task_signal": "UI/component|API/backend|bug fix|release/deploy|tool/MCP|architecture|security|not_applicable",
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
- Không dùng graph stale/partial thay cho live source.
- Không dùng Memory thay cho Knowledge hoặc ngược lại.
- Ghi nhận Rot nếu thường xuyên nạp thiếu hoặc thừa context.
- Resource budget và verification scope tuân theo `energy-token-policy.md`.
