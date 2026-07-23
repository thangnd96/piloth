# PilothOS Update — Upgrade Installed Version (post-init)

## Purpose

Nâng bản PilothOS đã init trong project lên version của plugin hiện tại sau khi
consumer đã `/plugin update` — trả lời đúng thiếu sót "update plugin rồi thì bản
`pilothOS/` đã init nâng cấp thế nào". Đây là SSOT của upgrade flow (init chỉ trỏ về đây).

Kiến trúc như init: **Claude làm judgment + UI**, **staging/engine làm deterministic**.
- Re-stage: copy lại kernel + adapter `verbatim` từ **nguồn Piloth** bằng `stage.sh --upgrade`
  (có backup; GIỮ file consumer-owned + state).
- Ghi nhận: qua engine plan `mode=upgrade` (`write_marker`) — đóng dấu version mới vào
  `.initialized`/manifest. Uninstall vẫn phục hồi được (backup trong manifest).

Thêm/bớt adapter (không phải full upgrade) → `/piloth:adapter` (`pilothos-adapter`), nhẹ hơn.

## Preconditions

- `pilothOS/.initialized` PHẢI tồn tại. Không → dừng, hướng dẫn chạy `/piloth:init` trước.
- Cần truy cập **nguồn Piloth** (chứa `scripts/stage.sh` + bản phân phối mới): plugin
  `${CLAUDE_PLUGIN_ROOT}` (thường có sẵn nếu init bằng plugin, và đã `/plugin update`),
  hoặc một clone Piloth ở version đích. Không có nguồn → không re-stage được; báo user và dừng.
- Git working tree nên sạch trước khi upgrade (dễ review diff + rollback).

## Stages

| Stage | Nội dung |
|---|---|
| Detect | `python3 pilothOS/scripts/pilothos_guard.py detect` → kỳ vọng verdict `re-init`. Đọc version đã cài ở `pilothOS/.initialized` (`pilothos_version`) và version đích ở `<SOURCE>/.claude-plugin/plugin.json`; trình delta cho user. Đọc `pilothOS/CHANGELOG.md` + migration notes (nếu có). Xác nhận tree sạch. |
| Re-stage | Xác định `<SOURCE>` (ưu tiên `${CLAUDE_PLUGIN_ROOT}`, else clone). Chạy `bash "<SOURCE>/scripts/stage.sh" --upgrade <project>` (target = cwd). Backup tự ghi vào `pilothOS/.backup/stage-upgrade-<ts>`; kernel/adapter `verbatim` bị ghi đè; **GIỮ**: `CLAUDE.md`/`AGENTS.md`/`.gitignore`/`.claude/settings.json`, `pilothOS/.initialized`, `pilothOS/rot/registry.md`, `pilothOS/rot/review-log.md`, `pilothOS/memory/lessons-learned.md`. Đổi adapter selection: thêm `--adapters <csv>` (mặc định GIỮ nguyên, KHÔNG tự resurrect adapter đã remove). |
| Record | Ghi nhận version mới qua engine — plan tối thiểu `mode=upgrade`: `dry-run` (phải `plan_valid`) → `apply`. Engine đóng dấu `pilothos_version` mới vào `.initialized` + manifest. |
| Verify | Đọc RECEIPT (trường `completeness_missing` phải VẮNG). `python3 pilothOS/scripts/pilothos_guard.py self-check` → `SELF-CHECK PASSED`. Nhắc user mở session Claude Code **MỚI** (để hook/version mới có hiệu lực). |

## Plan mẫu

Ghi nhận upgrade (sau khi `stage.sh --upgrade` đã re-stage file):

```json
{"plan_version": 1, "mode": "upgrade", "steps": [{"op": "write_marker"}]}
```

Lệnh engine:

```bash
python3 pilothOS/scripts/pilothos_installer.py dry-run '{"plan_version":1,"mode":"upgrade","steps":[{"op":"write_marker"}]}'
python3 pilothOS/scripts/pilothos_installer.py apply   '{"plan_version":1,"mode":"upgrade","steps":[{"op":"write_marker"}]}'
```

## Notes

- Upgrade re-stage TOÀN BỘ kernel/adapter verbatim; muốn chỉ bật/tắt adapter thì dùng
  `/piloth:adapter` (targeted, không đụng kernel).
- `mode=upgrade` KHÔNG chạy lại greenfield/brownfield plan — không hỏi lại persona/goals.
  Không khai `adapters` trong plan ghi nhận (tránh engine sinh `remove_path` cho adapter khác);
  đổi adapter selection chỉ qua flag `--adapters` của staging.
- Fail-soft: nếu `stage.sh` báo cần `--upgrade` (project đã init) mà bạn quên flag → thêm
  `--upgrade`. Nếu không tìm thấy nguồn Piloth → dừng, hướng dẫn user `/plugin update` hoặc clone.
- Không nhét business logic/policy vào đây; đây chỉ là re-stage bản phân phối + đóng dấu version.
