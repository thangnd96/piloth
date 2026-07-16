# Rot — Index

## Purpose

Quản lý operational state và quy trình review Rot của PilothOS.

## Contents

| File | Scope | Startup |
|---|---|---|
| `registry.md` | Bảng trạng thái hiện tại; nguồn sự thật cho due date | Luôn kiểm tra |
| `review-guide.md` | Rules, signals, workflow và convention review | Chỉ nạp khi review hoặc có Rot Signal |
| `review-log.md` | Lịch sử review append-only | Chỉ nạp khi cần truy vết |

## Convention

- Startup chỉ đọc bảng trong `registry.md`; không nạp Review Guide hoặc Review Log mặc định.
- `registry.md` giữ ngắn, chỉ chứa operational state hiện tại.
- Mọi review phải cập nhật Registry và append Review Log.
