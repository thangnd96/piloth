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

## Guardrails

- Không import toàn bộ thư mục khi index đủ để route.
- Không dùng Memory thay cho Knowledge hoặc ngược lại.
- Ghi nhận Rot nếu thường xuyên nạp thiếu hoặc thừa context.
