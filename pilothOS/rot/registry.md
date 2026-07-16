# PilothOS — Rot Registry

> Operational state hiện tại. Startup chỉ cần kiểm tra bảng này.

## Registry

| Scope | Owner | Rot Rate | Cadence | Last Reviewed | Next Due | Status | Trigger |
|---|---|---:|---|---|---|---|---|
| Identity | <owner> | Low | 6–12 tháng | <init> | <init> | 🟢 Healthy | Tầm nhìn, persona hoặc mục tiêu thay đổi |
| Rules & Hooks | <owner> | Medium | 1–3 tháng | <init> | <init> | 🟢 Healthy | Exception, workaround hoặc rule conflict tăng |
| Memory & Knowledge | <owner> | Medium | Theo thay đổi | <init> | Event | 🟢 Event-based | Context, docs, spec hoặc domain thay đổi |
| Skills | <owner> | High | 2–4 tuần | <init> | <init> | 🟢 Healthy | Workflow đổi, logic lặp hoặc skill phình to |
| Runtime | <owner> | Medium | Theo workflow | <init> | Event | 🟢 Event-based | Lifecycle, state machine hoặc orchestration đổi |
| Agents | <owner> | Very High | Mỗi model update | <init> | Event | 🟢 Event-based | Model, role, permission hoặc prompt đổi |
| Tools / MCP / CLI | <owner> | High | Theo API/schema | <init> | Event | 🟢 Event-based | API, MCP, CLI, dependency hoặc schema đổi |
| Governance | <owner> | Medium | 1–3 tháng | <init> | <init> | 🟢 Healthy | Approval, budget, risk hoặc escalation đổi |
| Evaluation | <owner> | High | 2–4 tuần | <init> | <init> | 🟢 Healthy | Quality gate, metric hoặc acceptance đổi |
| Context Loading | <owner> | High | 2–4 tuần | <init> | <init> | 🟢 Healthy | Context bloat, thiếu context hoặc routing sai |
| Adapters | <owner> | Medium | Theo native tool change | <init> | Event | 🟢 Event-based | Claude/Codex/Cursor/Antigravity thay đổi cách đọc rules/settings |
| Agent Teams | <owner> | High | Theo validated workflow | <init> | Event | 🟢 Event-based | Workflow cần multi-role hoặc team contract thay đổi |

### Status

- 🟢 Healthy / Event-based
- 🟠 Due Soon
- 🔴 Overdue

## Evaluation Rule

- Nếu `Next Due < Today`, scope là **Overdue** và phải được nhắc trước task.
- `Status` là dữ liệu dẫn xuất; khi mâu thuẫn, `Next Due` là nguồn sự thật.
- Giá trị `Event` được kích hoạt bởi Trigger hoặc Rot Signal, không có nghĩa là miễn review.
