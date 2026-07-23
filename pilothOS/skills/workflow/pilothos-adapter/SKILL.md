# PilothOS Adapter — Add/Remove Tool Adapter (post-init)

## Purpose

Thêm hoặc bớt tool adapter (`.cursor` / `.codex` / `.antigravity`) sau khi project
đã init — trả lời đúng feedback "chọn claude rồi muốn add codex mà không biết cách".
`claude` (`.claude`) là adapter nền, luôn giữ, không thao tác được ở đây.

Kiến trúc như init: **Claude làm judgment + UI**, **engine/staging làm deterministic**.
- ADD: copy file adapter từ **nguồn Piloth** bằng staging targeted (`--add-adapters`)
  — chỉ copy adapter thiếu, KHÔNG tái stage kernel hay đụng adapter khác.
- REMOVE: qua engine (`op remove_path` — có backup, nằm trong allowlist), rồi
  `write_marker`. Uninstall vẫn phục hồi được (backup trong manifest).

## Preconditions

- `pilothOS/.initialized` PHẢI tồn tại. Không → dừng, hướng dẫn chạy `/piloth:init` trước.
- ADD cần truy cập **nguồn Piloth** (chứa `scripts/stage.sh` + `adapters/`):
  plugin `${CLAUDE_PLUGIN_ROOT}` (thường có sẵn nếu init bằng plugin), hoặc một
  clone Piloth. Không có nguồn → không copy được adapter; báo user và dừng.

## Stages

| Stage | Nội dung |
|---|---|
| Detect | Liệt kê adapter đang có trên đĩa: `.claude` (luôn), `.cursor`/`.codex`/`.antigravity` (kiểm `exists`). |
| Elicit | AskUserQuestion: **Add hay Remove**; rồi chọn adapter (multi-select trong cursor/codex/antigravity). |
| Add | Xác định `<SOURCE>` (ưu tiên `${CLAUDE_PLUGIN_ROOT}`, else clone). Chạy `bash "<SOURCE>/scripts/stage.sh" --add-adapters <names>` (target = cwd). Ghi nhận: plan `mode=upgrade` chỉ `write_marker` → dry-run → apply. **KHÔNG** khai báo `adapters` trong plan này (tránh engine sinh `remove_path` cho adapter khác). |
| Remove | Soạn `pilothOS/.pending-plan.json` = `mode=upgrade`, mỗi adapter một `{"op":"remove_path","target":".codex"}` + `{"op":"write_marker"}` cuối. `dry-run` → **approve bằng AskUserQuestion** (thao tác có xóa) → `apply`. |
| Verify | Đọc RECEIPT; xác nhận adapter dir đã add/remove đúng; xóa `.pending-plan.json`; báo user (add rồi thì mở session mới nếu adapter cần hook riêng). |

## Plan mẫu

Add (ghi nhận sau khi staging targeted đã copy file):

```json
{"plan_version": 1, "mode": "upgrade", "steps": [{"op": "write_marker"}]}
```

Remove `.codex`:

```json
{"plan_version": 1, "mode": "upgrade",
 "steps": [{"op": "remove_path", "target": ".codex"}, {"op": "write_marker"}]}
```

## Notes

- Chỉ optional adapter (`cursor`/`codex`/`antigravity`) add/remove được; `remove_path`
  của engine cũng chỉ cho phép đúng ba dir này (allowlist).
- Đổi selection nhiều adapter cùng lúc: gộp names trong một lần `--add-adapters`
  (add) hoặc nhiều `remove_path` trong một plan (remove).
- Không nhét business logic/policy vào adapter; đây chỉ là bật/tắt bản phân phối adapter.
