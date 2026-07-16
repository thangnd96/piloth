# PilothOS — Agentic Operating System

> **Stable things guide change. Change must never redefine stability.**

PilothOS là kiến trúc vận hành trung lập với model dành cho hệ thống AI Agent. Mỗi layer có trách nhiệm, vòng đời và mức độ thay đổi riêng.

## Architecture

```text
Identity
    ↓
Rules & Hooks
    ↓
Memory & Knowledge
    ↓
Skills
    ↓
Runtime
    ↓
Agents
    ↓
Tools / MCP / CLI
```

Governance, Evaluation, Adapters và Agent Teams là các hệ thống **cắt ngang**.

- **Governance** kiểm soát quyền hạn, rủi ro và escalation.
- **Evaluation** xác nhận chất lượng bằng Evidence.
- **Adapters** bridge PilothOS sang từng native agent tooling, không định nghĩa lại source of truth.
- **Agent Teams** mô tả role composition đã validate cho task phức tạp; team là composition tạm thời của Agents do Runtime điều phối, không thay thế responsibility của Runtime hoặc Agents.

## Core Philosophy

- **Identity** định hướng hệ thống.
- **Rules & Hooks** ràng buộc hành vi.
- **Memory & Knowledge** cung cấp ngữ cảnh và sự thật.
- **Skills** hiện thực năng lực.
- **Runtime** điều phối thực thi.
- **Agents** thực hiện công việc.
- **Tools / MCP / CLI** kết nối thế giới bên ngoài.
- **Governance** kiểm soát quyền hạn, rủi ro và escalation.
- **Evaluation** xác nhận chất lượng bằng Evidence.
- **Adapters** kết nối PilothOS với native agent tooling.
- **Agent Teams** mô tả role composition đã validate cho task phức tạp.

## Layer Responsibility

| Layer | Responsibility |
|---|---|
| Identity | WHY |
| Rules & Hooks | POLICY |
| Memory | CONTEXT |
| Knowledge | FACT |
| Skills | CAPABILITY |
| Runtime | ORCHESTRATION |
| Agents | EXECUTION |
| Tools / MCP / CLI | INTEGRATION |

> Thành phần nằm sai responsibility phải được flag và refactor về đúng layer.

## Debugging Principle

Kiểm tra từ ngoài vào trong:

```text
Tools → Agents → Runtime → Skills → Memory & Knowledge → Rules & Hooks → Identity
```

Không thay đổi layer ổn định khi chưa loại trừ nguyên nhân ở layer biến động hơn.

## Design Principles

- Identity không chứa implementation.
- Rules là Single Source of Truth cho policy.
- Memory lưu context; Knowledge lưu fact.
- Skills không chứa policy; Agents không chứa business logic.
- Runtime điều phối nhưng không sở hữu capability hoặc integration.
- Tools chỉ là adapter.
- Mọi quyết định quan trọng phải có Evidence và có thể truy vết.
- Mọi lỗi lặp lại phải trở thành Rule, Knowledge hoặc Skill phù hợp.
- Context được nạp theo nhu cầu, không nạp toàn bộ mặc định.

## Cross-Cutting Boundaries

- **Runtime** owns orchestration: lifecycle, handoff protocol và conflict protocol.
- **Agents** own execution roles: role, model, permission và responsibility.
- **Agent Teams** own validated role composition: khi nào dùng team nào, role nào tham gia, stop condition là gì.
- **Agent Teams không được** chứa lifecycle chung của Runtime, business policy của Rules hoặc implementation chi tiết của Tools.
- **Adapters không được** duplicate OS source of truth; adapter chỉ trỏ về `pilothOS/`.

## Working Agreement

- Mọi thiết kế phải chỉ rõ layer tương ứng.
- Không tạo abstraction hoặc layer mới nếu responsibility hiện tại đã bao phủ.
- Ưu tiên mở rộng bằng Rules hoặc Skills trước khi thay đổi Identity.
- Khi phát hiện Rot, phải cảnh báo và đề xuất xử lý.
- Nếu `rot/registry.md` quá hạn, phải nhắc trước khi làm task.
