# Rot Review Guide

## Review Rules

- Mỗi scope phải có Owner, Cadence, Last Reviewed và Next Due hoặc Event Trigger.
- Mỗi lần review phải cập nhật `registry.md` và append `review-log.md`.
- Chỉ nạp checklist của scope liên quan; checklist cụ thể nằm trong `index.md` của từng layer hoặc cross-cutting system.
- Không đóng review khi chưa có Evidence.

## Identity Checklist (ngoại lệ)

Identity không có `index.md`; checklist được quản lý tại Rot system để tránh đưa công cụ review vào Identity.

- Persona còn phản ánh đúng phạm vi và trách nhiệm của implementation không?
- Mục tiêu còn phù hợp và đo được không?
- Giá trị cốt lõi có bị vi phạm lặp lại trong thực tế vận hành không?
- Ranh giới có cần siết hoặc nới dựa trên incident đã ghi nhận không?

## Rot Signals

- Lỗi hoặc câu hỏi giống nhau lặp lại.
- Exception và workaround tăng dần.
- Logic hoặc policy bị trùng lặp.
- Responsibility bắt đầu chồng chéo giữa các layer.
- Documentation lệch implementation.
- Agent phải suy diễn thay vì dựa trên Rule, Fact hoặc Evidence.
- Context nạp quá nhiều nhưng vẫn bỏ sót thông tin cần thiết.
- Thay đổi nhỏ gây ảnh hưởng dây chuyền qua nhiều layer.

## Review Workflow

```text
Detect → Identify Scope → Load Scope Checklist → Review → Refactor → Verify → Update Registry → Append Log
```

## Working Agreement

- Ưu tiên loại bỏ Rot thay vì thêm workaround.
- Khi nhiều scope cùng Rot, review theo Debugging Principle.
- Event-based vẫn phải review ngay khi có Trigger hoặc Rot Signal.

## Adapter and Agent Team Review

- Adapters không có `index.md` (adapter thật là các thư mục tool ở root:
  `.claude/`, `.cursor/`, `.codex/`, `.antigravity/`); checklist đặt tại đây:
  - Adapter còn trỏ đúng entry point không?
  - Có duplicate nội dung từ `pilothOS/` không?
  - Có mâu thuẫn instruction giữa adapter và OS không?
  - Có tool nào thay đổi cách đọc rules/settings không?
- Agent Team checklist nằm trong `pilothOS/agent-teams/index.md`.
- Không review adapter bằng cách đọc toàn bộ native config nếu task không liên quan đến adapter.
