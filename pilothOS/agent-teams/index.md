# Agent Teams

## Purpose

Quản lý **role composition đã validate** cho task cần nhiều vai trò.

Agent Teams là cross-cutting scope: team definition nằm ở đây, nhưng orchestration vẫn thuộc Runtime và role execution vẫn thuộc Agents.

## Responsibilities

- Định nghĩa khi nào dùng team.
- Định nghĩa role composition, lead role, evaluator/generator split và stop condition.
- Định nghĩa handoff expectation ở mức team.
- Giữ danh sách team tối thiểu, chỉ thêm khi có Evidence từ task thật hoặc workflow lặp lại.

## Non-Responsibilities

- Không sở hữu lifecycle chung; lifecycle thuộc Runtime.
- Không sở hữu policy; policy thuộc Rules & Hooks.
- Không sở hữu role contract chi tiết; role thuộc Agents.
- Không chứa implementation hoặc tool command cụ thể; integration thuộc Tools/Adapters.
- Không tạo team generic chưa được validate.

## Contents

| File | Purpose |
|---|---|
| `team-contract.md` | Contract bắt buộc khi tạo hoặc dùng team |
| `task-routing.md` | Quy tắc chọn team tối thiểu |
| `piloth-team.md` | Team seed duy nhất đã được xác định từ workflow thật |

## Convention

- Default là **single agent**.
- Chỉ dùng team khi task có complexity hoặc risk đủ lớn.
- Chỉ thêm team mới khi có Evidence trong `review-log.md` hoặc task thật yêu cầu lặp lại.
- Không tạo team để “cho đủ vai trò”.

## Review Checklist

- Team có Evidence vận hành thật không?
- Team có làm trùng responsibility của Runtime hoặc Agents không?
- Handoff có rõ input/output không?
- Có role nào generic, không cần thiết hoặc chưa được chứng minh không?
- Team có làm tăng context cost mà không tăng chất lượng không?
