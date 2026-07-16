# Team Orchestration

## Purpose

Định nghĩa protocol runtime khi một Agent Team được kích hoạt.

## Responsibilities

- Điều phối lifecycle của team execution.
- Chuẩn hóa handoff output.
- Xử lý conflict giữa role outputs.
- Dừng team loop khi đạt stop condition.

## Non-Responsibilities

- Không định nghĩa team nào tồn tại; team definitions thuộc `agent-teams/`.
- Không định nghĩa role identity; role thuộc `agents/` hoặc team contract.
- Không định nghĩa policy; policy thuộc Rules & Hooks.

## Handoff Protocol

Mỗi role output phải có:

- Role decision
- Evidence
- Risks
- Next handoff

## Conflict Protocol

Nếu roles bất đồng:

1. Xác định assumption đang xung đột.
2. Yêu cầu Evidence từ mỗi role.
3. Ưu tiên phương án đơn giản hơn và có thể verify.
4. Escalate sang Governance hoặc user nếu conflict phụ thuộc constraint chưa rõ.
