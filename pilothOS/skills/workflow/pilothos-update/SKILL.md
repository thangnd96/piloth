# PilothOS Update — Upgrade Installed Version (post-init)

## Purpose

Nâng bản PilothOS đã init trong project lên version của plugin hiện tại sau khi
consumer đã `/plugin update` — trả lời đúng thiếu sót "update plugin rồi thì bản
`pilothOS/` đã init nâng cấp thế nào". Đây là SSOT của upgrade flow (init chỉ trỏ về đây).

Kiến trúc như init: **Claude làm judgment + UI**, **staging/engine làm deterministic**.
- Re-stage: copy lại kernel + adapter `verbatim` từ **nguồn Piloth** bằng `stage.sh --upgrade`
  (có backup; GIỮ file consumer-owned + state). Staging cũng **gỡ** file kernel không
  còn trong bản phân phối mới — không có bước này thì mọi hệ con một release gỡ đi
  vẫn nằm lại trên đĩa của consumer.
- Ghi nhận: qua engine plan `mode=upgrade` (`write_marker`) — đóng dấu version mới vào
  `.initialized`/manifest. Uninstall vẫn phục hồi được (backup trong manifest).


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
| Re-stage | Xác định `<SOURCE>` (ưu tiên `${CLAUDE_PLUGIN_ROOT}`, else clone). Chạy `bash "<SOURCE>/scripts/stage.sh" --upgrade <project>` (target = cwd). Backup tự ghi vào `pilothOS/.backup/stage-upgrade-<ts>`; kernel/adapter `verbatim` bị ghi đè; **GIỮ**: `CLAUDE.md`/`AGENTS.md`/`.gitignore`/`.claude/settings.json`, `pilothOS/.initialized`, `pilothOS/rot/registry.md`, `pilothOS/rot/review-log.md`, `pilothOS/memory/lessons-learned.md`. **GỠ**: file dưới `pilothOS/` vắng mặt trong `dist-manifest.json` mới (backup trước khi xoá; state + marker + backup được giữ). Số file gỡ được in ra ở cuối. |
| Record | Ghi nhận version mới qua engine — plan tối thiểu `mode=upgrade`: `dry-run` (phải `plan_valid`) → `apply`. Engine đóng dấu `pilothos_version` mới vào `.initialized` + manifest. |
| Verify | Đọc RECEIPT (trường `completeness_missing` phải VẮNG). `python3 pilothOS/scripts/pilothos_guard.py self-check` → `SELF-CHECK PASSED`. Nhắc user mở session Claude Code **MỚI** (để hook/version mới có hiệu lực). |
| Log | `python3 pilothOS/scripts/pilothos_guard.py log-append review <scope> <findings> <action> <evidence> <reviewer>` — Evidence = manifest path từ stage Record. Upgrade thay hàng chục file kernel nên đây là phiên "có thay đổi file": Stop hook auto-log gate áp dụng đầy đủ. Dùng verb, đừng mở editor lên hai file log. |

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

- Upgrade re-stage TOÀN BỘ kernel/adapter verbatim, và gỡ file không còn được ship.
  Piloth chỉ ship một adapter (`claude`) nên không có "adapter selection" để đổi.
- `mode=upgrade` KHÔNG chạy lại greenfield/brownfield plan — không hỏi lại persona/goals.
  Không khai `adapters` trong plan ghi nhận.
- Engine tự chèn `prune_dead_hooks` ở `mode=upgrade`: hook trong `.claude/settings.json`
  trỏ tới file `pilothOS/` mà bản này không ship sẽ bị gỡ (hook riêng của consumer
  không bị chạm). Step này hiện ở `dry-run` trước khi bạn approve.
- Fail-soft: nếu `stage.sh` báo cần `--upgrade` (project đã init) mà bạn quên flag → thêm
  `--upgrade`. Nếu không tìm thấy nguồn Piloth → dừng, hướng dẫn user `/plugin update` hoặc clone.
- Không nhét business logic/policy vào đây; đây chỉ là re-stage bản phân phối + đóng dấu version.
