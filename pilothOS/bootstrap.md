# PilothOS Bootstrap

> Entry point duy nhất được nạp trực tiếp từ `CLAUDE.md`.

## Startup Contract

Trước mỗi task:

1. Đọc `PilothOS.md` để giữ đúng kiến trúc và responsibility.
2. Chỉ kiểm tra bảng trạng thái trong `rot/registry.md`; nếu scope quá hạn hoặc có trigger phù hợp, nhắc trước khi thực hiện. Không nạp Review Log hay Review Guide nếu chưa cần. Nếu không có scope nào quá hạn, không tường thuật trạng thái rot trong reply.
3. Đọc `rules/index.md` và áp dụng các Rule liên quan.
4. Đọc `runtime/index.md` để xác định lifecycle và success criteria.
5. Chỉ nạp thêm Memory, Knowledge, Skills, Agents, Tools, Governance hoặc Evaluation khi task cần.
6. Trước khi kết thúc một phiên có thay đổi file: append log phù hợp vào `rot/review-log.md` (finding/thay đổi kiến trúc) hoặc `memory/lessons-learned.md` (bài học tái sử dụng), hoặc nêu rõ "Không có finding hoặc lesson cần ghi" kèm lý do. Gate này được enforce tự động bởi Stop hook (auto-log gate).

## Progressive Context Loading

Không nạp toàn bộ `pilothOS/` vào context.

```text
Task
  ↓
Classify affected layers
  ↓
Load index.md of relevant layers
  ↓
Load only referenced files needed for execution
  ↓
Execute and verify
```

Chi tiết: `runtime/context-loading.md`.

## Instruction Precedence

Khi có xung đột, áp dụng theo thứ tự:

1. Yêu cầu an toàn và giới hạn hệ thống.
2. Identity trong `CLAUDE.md`.
3. Constitution trong `PilothOS.md`.
4. Rules & Hooks đã được phê duyệt.
5. Yêu cầu cụ thể của task.
6. Runtime, Skills và conventions mặc định.

Rule không được mâu thuẫn với Identity hoặc Constitution. Khi phát hiện mâu thuẫn, phải flag để review; không tự chọn một bên.

## Missing or Stale Documentation

Nếu tài liệu thiếu, mâu thuẫn hoặc lỗi thời:

- Không tự tạo policy mới.
- Nêu rõ khoảng trống và Evidence.
- Đề xuất cập nhật đúng layer.
- Ghi nhận Rot Signal nếu phù hợp.

## Adapter Loading

Adapter files (`.claude/`, `.cursor/`, `.codex/`, `.antigravity/`) chỉ giúp native tooling tìm tới PilothOS.

- Không xem adapter là source of truth.
- Không sửa adapter để thay đổi policy; sửa đúng file trong `pilothOS/` trước.
- Adapter là các thư mục tool ở root (`.claude/`, `.cursor/`, `.codex/`, `.antigravity/`) — bridge mỏng, chỉ xem khi có tool integration conflict.

## Agent Team Loading

Chỉ nạp `pilothOS/agent-teams/` khi task có dấu hiệu cần nhiều vai trò, ví dụ:

- cần generator/evaluator loop,
- cần review độc lập trước khi implement,
- cần contract negotiation giữa nhiều role,
- hoặc user yêu cầu rõ ràng dùng team.

Không tạo team mới nếu chưa có Evidence từ task thật hoặc workflow lặp lại.
