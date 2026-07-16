# Tools / MCP / CLI — Index

## Purpose

Quản lý INTEGRATION với thế giới bên ngoài.

## Responsibilities

- Liệt kê tool, capability, config location và health check.
- Theo dõi API/schema/dependency changes.

## Non-Responsibilities

- Không chứa business logic hoặc policy.
- Không nhúng credentials vào markdown.
- Không nạp mặc định vào Identity context.

## Tools

| Tool | Type | Capability | Config | Health Check |
|---|---|---|---|---|
| Không có Tool bắt buộc | N/A | PilothOS hoạt động độc lập với tool cụ thể | N/A | N/A |

## Convention

Tool chỉ là adapter. Mọi thay đổi API/schema phải cập nhật index và Rot Log.

## Review Checklist

- API, schema, dependency hoặc CLI contract có thay đổi không?
- Tool nào deprecated, lỗi health check hoặc không còn được sử dụng?
- Credentials và configuration có được tách khỏi markdown không?
- Adapter có đang chứa business logic hoặc policy không?

