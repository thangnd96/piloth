# Forge Guide — Verify & Activation

> Chương này của manual Forge (nạp theo nhu cầu).

## Verify (trước activation)

```bash
python3 pilothOS/scripts/pilothos_guard.py forge-verify spec.json
```
Kiểm: `kind` ∈ skill|rule|gate · `id` kebab-slug + không trùng · `layer` khớp
kind · `intent`/`reason` có · `authority` đúng shape (fail-closed). FAIL → sửa spec.

## Activation (human-approved, sealed — construction ≠ activation)

Forge **không** tự làm các bước sau; đây là việc human/agent làm sau khi duyệt
`forge-plan`:

1. `os-start` một contract khai `allowed_paths` gồm file mới + `capability-manifest.json`.
2. Ghi `files` (từ `forge-scaffold`) vào cây.
3. Thêm `manifest_entry` vào `pilothOS/governance/capability-manifest.json`.
4. `capability-check` PASS + `self-check` PASS.
5. `os-close` + seal; **append lesson** (`pilothOS/memory/lessons-learned.md`) để retain.

## Gate (kind=gate)

Forge **không** scaffold file cho gate — gate được cưỡng chế trong guard
(`required_gates_for_task` + `validate_required_quality_gates`). Tạo gate mới cần
sửa fragment guard + `build_guard.py` (xem `pilothOS/evaluation/quality-gates.md`
và `[[piloth-guard-amalgamation]]`). forge-plan vẫn trình được authority-delta cho
`enforcement_surface` của gate để duyệt trước khi wiring.
