# Rules & Hooks

## Purpose

Quản lý **POLICY** của PilothOS: các quy tắc bắt buộc và cơ chế enforce.

## Responsibilities

- Định nghĩa rule đã được phê duyệt.
- Chuyển lỗi lặp lại thành rule hoặc hook.
- Giữ rule ngắn, rõ, enforce được.
- Phân biệt rule với skill, runtime và identity.

## Non-Responsibilities

- Không chứa workflow nhiều bước; workflow thuộc Skills hoặc Runtime.
- Không chứa persona hoặc mục tiêu dài hạn; đó là Identity.
- Không chứa documentation dài hạn; đó là Knowledge.
- Không chứa native adapter config; đó là Adapters.

## Contents

| File | Purpose |
|---|---|
| `coding-behavior.md` | Discipline khi code: đơn giản, surgical, evidence |
| `evidence.md` | Quy tắc kết luận dựa trên Evidence |
| `layer-boundary.md` | Quy tắc đặt đúng responsibility |
| `hooks.md` | Nguyên tắc cho hook enforcement |

## Convention

- Gặp vấn đề → phân tích nguyên nhân → viết thành Rule → không lặp lại.
- Agent không tự tạo, tự sửa hoặc bỏ qua Rule đã phê duyệt.
- Rule phải có trigger rõ ràng và có thể kiểm chứng.
- Hook chỉ enforce Rule đã tồn tại; không tự sinh policy mới.

## Review Checklist

- Có Rule nào dư thừa, trùng lặp hoặc mâu thuẫn không?
- Có issue nào lặp lại nên chuyển thành Rule mới không?
- Có Rule nào nên được enforce bằng Hook không?
- Có Rule nào đang chứa workflow hoặc implementation sai layer không?
