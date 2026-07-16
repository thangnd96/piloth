# Runtime — Index

## Purpose

Điều phối ORCHESTRATION cho vòng đời task.

```text
Intake → Plan → Execute → Review → Repair → Deliver
```

## Responsibilities

- Xác định state, transition, retry và completion.
- Chọn Skills, Agents, Tools và context cần nạp.
- Yêu cầu Evidence trước khi chuyển state.

## Non-Responsibilities

- Không chứa business policy.
- Không tự thực thi tool call.
- Không lưu fact hoặc context lâu dài.

## Contents

| File | Scope |
|---|---|
| `task-lifecycle.md` | State machine và exit criteria |
| `context-loading.md` | Progressive context loading |

## Convention

Runtime điều phối; Agents thực thi; Evaluation phán định quality gate.

## Review Checklist

- State, transition và exit criteria còn rõ ràng không?
- Retry, repair hoặc escalation có gây loop không kiểm soát không?
- Context loading có nạp thừa hoặc bỏ sót dữ liệu cần thiết không?
- Runtime có đang sở hữu policy, capability hoặc integration sai responsibility không?

