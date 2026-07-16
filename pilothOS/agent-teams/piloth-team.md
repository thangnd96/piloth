# Piloth Team

> Team seed chính thức của PilothOS cho các task phức tạp cần **Solution Architect Lead + Generator/Evaluator loop + contract negotiation**.

## Purpose

Dùng nhiều vai trò để tạo, phản biện và chốt một hướng giải pháp duy nhất cho task có nhiều trade-off, rủi ro kiến trúc hoặc dễ bị single-agent suy diễn.

## When to Use

- Task có nhiều hướng tiếp cận hợp lý và cần so sánh trade-off.
- Task ảnh hưởng kiến trúc, layer boundary, runtime, rule hoặc skill quan trọng.
- Cần contract negotiation trước khi implement.
- Cần một vai trò tạo phương án và một vai trò phản biện độc lập.
- User yêu cầu rõ ràng dùng `piloth-team`.

## When Not to Use

- Task nhỏ, rõ, rủi ro thấp.
- Task chỉ cần dịch, viết lại, format hoặc chỉnh sửa nhỏ.
- Khi chưa đủ context để định nghĩa contract giữa các vai trò.
- Khi team loop làm tăng chi phí context nhưng không tăng chất lượng quyết định.

## Roles

| Role | Responsibility |
|---|---|
| Lead Solution Architect | Điều phối, giữ scope, đào sâu requirement, chốt contract và quyết định cuối khi có đủ Evidence |
| Solution Generator | Đề xuất phương án, implementation path, trade-off và contract proposal |
| Critical Evaluator | Phản biện, tìm lỗi, kiểm tra Evidence, risk, simplicity và layer boundary |

> Trong PilothOS, role-name phải phản ánh trách nhiệm. Không dùng nickname cá nhân, tên member kiểu `member-1`, hoặc slug không mô tả trách nhiệm làm identity của team role.

## Handoff Order

```text
Lead Solution Architect defines contract
  ↓
Solution Generator proposes solution
  ↓
Critical Evaluator challenges assumptions and risks
  ↓
Lead Solution Architect resolves conflict
  ↓
Single execution path is selected
```

## Required Evidence

- Task contract hoặc success criteria đã rõ.
- Ít nhất một Generator proposal.
- Ít nhất một Evaluator critique.
- Lead resolution nêu rõ trade-off, constraint và lý do chọn.

## Stop Condition

Dừng team loop khi:

- Contract đã đủ rõ.
- Critical Evaluator không còn blocking concern.
- Lead Solution Architect đã chọn một execution path cụ thể.

## Escalation

Nếu vẫn còn conflict sau một vòng generator/evaluator:

1. Xác định assumption hoặc constraint đang thiếu.
2. Escalate sang Governance hoặc hỏi user để chốt constraint.
3. Không tiếp tục tranh luận vô hạn.

## Related Skill

Workflow chi tiết để scaffold hoặc cập nhật team nằm tại:

```text
pilothOS/skills/workflow/piloth-team-setup/SKILL.md
```

## Review Checklist

- Team có được dùng cho task có complexity/risk thật không?
- Generator/Evaluator loop có tạo thêm Evidence hay chỉ làm tăng context cost?
- Role-name có phản ánh trách nhiệm thay vì tên cá nhân không?
- Contract negotiation có kết thúc bằng một execution path cụ thể không?
- Có conflict nào nên được chuyển thành Rule, Knowledge hoặc Skill không?
