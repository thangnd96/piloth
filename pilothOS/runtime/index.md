# Runtime — Index

## Purpose

Điều phối ORCHESTRATION cho vòng đời task: scope governor, UI defect check và
cost/footprint meter cho agent work.

```text
Intake → Plan → Execute → Review → Repair → Deliver
```

## Responsibilities

- Xác định state, transition, retry và completion.
- Chọn Skills, Agents, Tools và context cần nạp.
- Yêu cầu Evidence trước khi chuyển state.
- Giữ controlled target sạch khỏi control-plane runtime/state.

## Non-Responsibilities

- Không chứa business policy.
- Không tự thực thi tool call.
- Không lưu fact hoặc context lâu dài.

## Contents

| File | Scope |
|---|---|
| `task-lifecycle.md` | State machine và exit criteria |
| `context-loading.md` | Progressive context loading |
| `consumer-assets.md` | Registry và routing policy cho tài sản consumer |
| `energy-token-policy.md` | Resource budget cho context, search, build/test, target footprint và tool runtime |
| `os-control-plane.md` | Project-local OS lifecycle, controlled-target governor, UI quality evidence, real cost ledger, benchmark value policy, entitlement profile, truth-in-seal and receipt seal mechanics |
| `self-hosting.md` | Dogfood contract for operating the Piloth repo through PilothOS |
| `team-orchestration.md` | Multi-agent handoff, QA and stop-condition runtime protocol |

## Convention

Runtime điều phối; Agents thực thi; Evaluation phán định quality gate.

## Review Checklist

- State, transition và exit criteria còn rõ ràng không?
- Retry, repair hoặc escalation có gây loop không kiểm soát không?
- Context loading có nạp thừa hoặc bỏ sót dữ liệu cần thiết không?
- Resource budget có tránh scan/build/load quá mức không?
- Runtime có đang sở hữu policy, capability hoặc integration sai responsibility không?
