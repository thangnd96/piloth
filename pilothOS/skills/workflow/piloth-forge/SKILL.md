# Piloth Forge — Governed Self-Extension

## Purpose

Cho agent/consumer **mở rộng PilothOS có quản trị** cho dự án của họ — thêm một
skill / rule / gate khi gặp **nhu cầu thật**, thay vì chờ maintainer sửa kernel.
Đây là năng lực khiến PilothOS là một *OS tự lớn lên được*. Bản Piloth của AOS
Forge + meta-harness.

> **construction ≠ activation** (AOS `authority.md` · Piloth `rules/index.md`):
> Forge chỉ **scaffold + verify + trình authority-delta**. Nó **KHÔNG** tự ghi
> file vào cây sống, **KHÔNG** tự thêm vào `capability-manifest.json`, **KHÔNG**
> tự cấp quyền. Activation là bước **human-approved, contract-gated, sealed**.
> "Generated code cannot self-promote."

> Đây là trigger nhỏ. Manual đầy đủ nằm ở `guides/` (nạp theo nhu cầu) —
> **đừng coi skill nén này là toàn bộ manual.**

## Preconditions

- Một **nhu cầu thật** (task/incident/pattern lặp) — extension rule
  (`pilothOS/README.md`): không tạo capability khi chưa có nhu cầu thật.

## Vòng lặp (7 bước)

1. **Notice** — phát hiện capability gap trong task thật.
2. **Inspect trước** — `python3 pilothOS/scripts/pilothos_guard.py os-inspect`
   xem cái gì đã tồn tại; `reuse-scan` — **reuse/extend trước khi tạo mới**.
3. **Chọn artifact bền nhỏ nhất** — memory → lesson → rule → skill → gate →
   adapter (AOS "smallest durable answer"). Chỉ leo thang khi bậc dưới không đủ.
4. **Scaffold** — viết spec `{kind, id, layer, intent, reason, authority?}` rồi:
   `python3 pilothOS/scripts/pilothos_guard.py forge-scaffold spec.json`
   → trả về `files` (nội dung đề xuất) + `manifest_entry`. Đọc `guides/skill-authoring.md`.
5. **Verify** — `forge-verify spec.json` (kind/layer/id/reason/authority hợp lệ,
   không trùng id). Đọc `guides/verify.md`.
6. **Plan + authority-delta** — `forge-plan spec.json` → xem **quyền sẽ cấp**
   (`widened`) + verify. **HUMAN duyệt** delta. Đọc `guides/capability-authority.md`.
7. **Activation (human-approved, sealed)** — chỉ sau khi duyệt:
   - `os-start` một contract khai `allowed_paths` gồm file mới,
   - ghi `files` vào cây, thêm `manifest_entry` vào `capability-manifest.json`,
   - `capability-check` PASS, `self-check` PASS,
   - `os-close` + seal, **append lesson** (`lessons-learned.md`) để retain.

## Non-Responsibilities

- **Không** tự ghi file/không tự cấp quyền (activation là bước human).
- **Không** tạo capability khi chưa có nhu cầu thật (extension rule).
- **Không** thay `os-inspect`/`capability-check`/`reuse-scan` — Forge dùng chúng.

## Verification

- `forge-verify` PASS + `forge-plan` cho authority-delta được duyệt.
- Sau activation: `capability-check` PASS, `self-check` PASS, os-run sealed,
  lesson appended.

## References

- Capability model: `pilothOS/runtime/capability-model.md`
- OS services / introspection: `pilothOS/runtime/os-services.md`
- Guides (progressive): `guides/capability-authority.md`, `guides/skill-authoring.md`, `guides/verify.md`
- Extension rules: `pilothOS/README.md`; layer taxonomy: `pilothOS/PilothOS.md`
