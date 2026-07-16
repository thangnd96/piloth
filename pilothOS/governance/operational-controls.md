# Operational Controls

## Default Controls

- **Approval:** thay đổi destructive, irreversible hoặc có ảnh hưởng rộng cần human approval.
- **Permissions:** dùng least privilege; chỉ cấp quyền cần cho task hiện tại.
- **Retry:** retry chỉ khi lỗi có khả năng tạm thời và operation an toàn để lặp.
- **Timeout:** mọi external operation phải có giới hạn hợp lý.
- **Escalation:** dừng và escalate khi thiếu quyền, thiếu Evidence, conflict hoặc rủi ro vượt ngưỡng.
- **Budget:** tránh dùng model/tool đắt hơn nếu capability thấp hơn đã đủ.

## Evidence

Mỗi approval hoặc escalation phải ghi reason, scope, decision và người/phần tử phê duyệt.
