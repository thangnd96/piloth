# Memory — Index

## Purpose

Lưu CONTEXT sống theo thời gian để agent kế thừa trạng thái và bài học.

## Responsibilities

- Task state, decisions tạm thời, history và lessons learned.
- Context có thời hạn hoặc phụ thuộc implementation.

## Non-Responsibilities

- Không lưu fact ổn định, spec hoặc standards.
- Không chứa policy hay workflow executable.

## Contents

| Path | Scope |
|---|---|
| `lessons-learned.md` | Bài học sau incident, append-only |
| `state/` | Trạng thái task đang chạy khi cần |

## Convention

Memory phải có nguồn, thời điểm và phạm vi áp dụng. Context hết hạn phải được cập nhật hoặc archive.

## Review Checklist

- Context còn đúng, còn cần thiết và còn trong thời hạn áp dụng không?
- Memory nào nên archive, cập nhật hoặc chuyển thành Knowledge ổn định?
- Lessons learned có nguồn, thời điểm và phạm vi rõ ràng không?
- Có task state nào bị bỏ quên hoặc gây hiểu nhầm cho session mới không?

