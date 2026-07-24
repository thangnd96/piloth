# Composability (T5)

## Purpose

Cho consumer **thêm / override một skill** cho dự án của họ **mà không phải fork
kernel** — bản Piloth của `capsule-skills` (workspace-wins precedence) của AOS.
Pair với Forge (T3): Forge scaffold một project skill, `skill-index` tìm thấy nó
với precedence.

## Skill precedence

```bash
python3 pilothOS/scripts/pilothos_guard.py skill-index                    # chỉ kernel
python3 pilothOS/scripts/pilothos_guard.py skill-index --consumer <dir>   # kernel + consumer
# hoặc set env PILOTHOS_CONSUMER_SKILLS=<dir>
```

- Scan kernel (`pilothOS/skills/workflow/*/SKILL.md`) + consumer dir.
- **workspace(consumer)-wins**: consumer skill trùng `id` (tên thư mục) override
  kernel; entry ghi `overrides: "kernel"`. Skill mới của consumer thêm vào index.
- Kernel **không bị đụng** → nâng cấp kernel (`/piloth:update`) vẫn giữ, override
  của consumer vẫn thắng. Không mất upstream (đối lập với fork).

## Principal

`current_principal()` đọc `PILOTHOS_PRINCIPAL` (env), default `local`. Nguyên tắc:
**caller identity từ context, không từ payload claim** (giống AOS "kernel-stamped
identity, never a payload claim"). Surfaced trong `os-inspect`.

## Non-Responsibilities / Giới hạn (ghi cùng `VALIDATION.md`)

- `skill-index` chỉ **liệt kê + precedence**; nó không thực thi skill (agent đọc
  SKILL.md như thường).
- **Multi-tenant attribution đầy đủ** (gắn principal vào mọi receipt/seal, per-
  principal state) là **future** — hiện `principal` chỉ surface ở introspection.
- Precedence theo `id` = tên thư mục; không merge nội dung (override toàn phần).
