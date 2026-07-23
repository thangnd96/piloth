# PilothOS Init — Installer Skill (Plan/Apply)

## Purpose

Installer chính thức. Kiến trúc: **Claude làm judgment + UI** (audit, elicit,
soạn plan, trình duyệt, đọc receipt) · **Engine làm thực thi deterministic**
(`pilothOS/scripts/pilothos_installer.py`). Thứ user approve = file plan =
thứ engine thực thi, byte-identical — không có khe hở diễn giải lại.

## Non-Responsibilities

- Claude KHÔNG tự ghi/sửa file trong Apply — mọi thay đổi đi qua engine.
- Không tự rẽ nhánh detect; verdict chờ consumer confirm.
- Re-init/upgrade dùng staging `--upgrade` và plan `mode=upgrade`; không chạy
  lại greenfield/brownfield plan trên project đã có `.initialized`.
- Gỡ cài đặt: `/pilothos-uninstall` (lệnh riêng).

## Stages

| Stage | Nội dung | Bắt buộc |
|---|---|---|
| Preflight | `python3 pilothOS/scripts/pilothos_guard.py preflight` — FAIL → dừng. | ✅ |
| Detect | `... pilothos_guard.py detect` → trình VERDICT + EVIDENCE, **confirm bằng AskUserQuestion**. `dirty` → xử lý theo NOTE rồi dừng; `re-init` → dùng upgrade flow nếu user muốn nâng cấp. | ✅ |
| Audit + Elicit | Nạp đúng MỘT file nhánh (`greenfield.md`/`brownfield.md`). Audit tài sản (judgment). Elicit bằng AskUserQuestion: Persona, Mục tiêu, **tool adapters muốn giữ** (Claude/Cursor/Codex/Antigravity → field `adapters` gồm `claude`; engine tự sinh `remove_path` cho adapter không chọn ở dry-run), **.gitignore scope** (runtime mặc định / all). | ✅ |
| Plan | Soạn `pilothOS/.pending-plan.json` (schema + ops: xem `installer explain`). Chạy `installer dry-run` — phải `plan_valid`. Trình bản render (effects + quyết định merge) → **approve bằng AskUserQuestion**; "Approve kèm điều chỉnh" → sửa plan → dry-run lại → trình lại. | ✅ |
| Apply | `installer apply pilothOS/.pending-plan.json`. Engine tự: backup → manifest → thực thi → self-check → archive plan → RECEIPT. Exit 4 (needs_judgment) → xử lý đúng items rồi lặp từ Plan. Exit 3 → đã auto-rollback, báo user. | ✅ |
| Verify | Đọc RECEIPT — kiểm cả trường `completeness_missing` (phải vắng mặt); đối chiếu effects vs plan; xóa `.pending-plan.json`; in **First-Boot Checklist**. | ✅ |
| Log | `... pilothos_guard.py log-append review ...` — Evidence = manifest path từ receipt. | ✅ |

## Self-Prune (mặc định — installer chạy đúng một lần)

Plan PHẢI kèm các step dọn mặt tiền install (đặt ngay trước `write_marker`):

```json
{"op":"remove_path","target":".claude/commands/pilothos-init.md"},
{"op":"remove_path","target":".claude/skills/pilothos-init"},
{"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/SKILL.md"},
{"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/greenfield.md"},
{"op":"remove_path","target":"pilothOS/skills/workflow/pilothos-init/brownfield.md"}
```

- `payloads/` + `manifest-spec.md` Ở LẠI (engine + uninstall cần); engine từ chối xóa chúng.
- `/pilothos-uninstall` + engine Ở LẠI — đường rollback không bao giờ bị dọn.
- Mọi thứ bị dọn đều có backup trong manifest → `uninstall --confirm` phục hồi cả
  bộ install → cài lại được sau khi gỡ.

## Re-init / Upgrade

Nâng bản đã init lên version mới → `/piloth:update` (skill `pilothos-update`) — SSOT
của upgrade flow (`stage.sh --upgrade` + engine plan `mode=upgrade`, giữ customization +
state). KHÔNG chạy lại greenfield/brownfield plan trên project đã có `.initialized`.

**Thêm/bớt adapter sau init (không phải full upgrade):** dùng `/piloth:adapter`
(skill `pilothos-adapter`) — ADD copy targeted qua `stage.sh --add-adapters`,
REMOVE qua engine `remove_path`. Nhẹ hơn re-stage toàn bộ.

## Unattended Install

Engine hỗ trợ install không tương tác khi tất cả judgment input đã được truyền
rõ qua tham số:

```bash
python3 pilothOS/scripts/pilothos_installer.py unattended \
  --mode greenfield \
  --persona "..." \
  --goals "..." \
  --owner "..." \
  --adapters claude,codex
```

`unattended --dry-run` sinh `pilothOS/.pending-plan.json` và chỉ validate;
không bỏ qua simulate/backup/manifest/receipt.

## Token Budget Contract

- Đọc tối đa: SKILL.md + 1 file nhánh + file consumer cần audit + receipt.
  KHÔNG đọc payloads (engine tự nạp), KHÔNG đọc manifest-spec (engine tự ghi),
  KHÔNG đọc lại file sau Apply (tin receipt + postcondition của engine).
- Mục tiêu: **≤ 12 tool calls** cho ca không có NEEDS-JUDGMENT. Vượt → ghi
  finding "init token bloat" ở stage Log.

## First-Boot Checklist (in ở Verify)

```text
1. Mở session Claude Code MỚI; được hỏi approve hooks → APPROVE.
2. Statusline trống khi healthy là bình thường. Kiểm nhanh:
   python3 pilothOS/scripts/pilothos_guard.py self-check
3. Rà Persona/Mục tiêu trong CLAUDE.md.
4. Sau mọi lần sửa .claude/settings.json: chạy self-check trước khi mở session.
5. Muốn thêm/bớt tool adapter sau này: /piloth:adapter (không cần re-init).
```

## Supporting Files

| File | Vai trò |
|---|---|
| `greenfield.md` / `brownfield.md` | Judgment guide theo nhánh + plan mẫu |
| `payloads/` | Nội dung chuẩn — CHỈ engine đọc |
| `manifest-spec.md` | Contract manifest/backup — engine + uninstall dùng |
| `pilothos_installer.py explain` | **SSOT** của ops + merge semantics |
