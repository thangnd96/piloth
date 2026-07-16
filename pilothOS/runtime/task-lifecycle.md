# Task Lifecycle

## States

| State | Entry | Exit Evidence |
|---|---|---|
| Intake | Nhận yêu cầu | Scope, assumptions, affected layers |
| Plan | Scope đã rõ | Plan ngắn và success criteria |
| Execute | Plan được chấp nhận hoặc đủ rõ | Implementation/output tạo xong |
| Review | Có output | Findings và quality-gate result |
| Repair | Review chưa đạt | Issues đã xử lý và re-verified |
| Deliver | Tất cả gate đạt | Summary, Evidence, limitations |

## Rules

- Task trivial có thể gộp Intake và Plan, nhưng không bỏ verification.
- Không chuyển Deliver khi quality gate chưa đạt.
- Retry, timeout và escalation tuân theo Governance.
- Không Deliver khi phiên có thay đổi file mà chưa cân nhắc ghi log; nếu không có finding, nêu rõ và lý do (auto-log gate enforce bằng Stop hook).
