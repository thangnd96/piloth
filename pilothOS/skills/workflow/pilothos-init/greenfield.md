# Init — Nhánh Greenfield (judgment guide)

## Elicit (AskUserQuestion)

1. Persona (một câu) — Enter/bỏ trống = giữ placeholder, sửa sau.
2. Mục tiêu 6–12 tháng (1–3 dòng đo được) — bỏ trống = placeholder.
3. Tool adapters giữ lại (multi-select): Claude Code / Cursor / Codex / Antigravity.
   `claude` luôn giữ. Kết quả → field `adapters` trong plan (list adapter giữ lại,
   GỒM `claude`). Engine tự sinh `remove_path` cho adapter KHÔNG chọn — Claude
   KHÔNG gõ tay từng step remove.
4. .gitignore scope: **runtime** (mặc định — chỉ ignore state; `pilothOS/` vẫn
   commit để team share) hay **all** (ignore toàn bộ `pilothOS/` — chỉ chọn nếu
   consumer coi PilothOS là tooling cục bộ). `all` → `options.gitignore_scope="all"`.

## Plan mẫu (đã validate qua engine)

```json
{
  "plan_version": 1,
  "mode": "greenfield",
  "fill": {"PERSONA": "<từ elicit>", "GOALS": "<từ elicit>", "OWNER": "<từ elicit>"},
  "adapters": ["claude", "codex"],
  "steps": [
    {"op": "fill_placeholders", "target": "CLAUDE.md"},
    {"op": "fill_placeholders", "target": "pilothOS/rot/registry.md"},
    {"op": "remove_path", "target": ".claude/commands/pilothos-init.md"},
    {"op": "remove_path", "target": ".claude/skills/pilothos-init"},
    {"op": "remove_path", "target": "pilothOS/skills/workflow/pilothos-init/SKILL.md"},
    {"op": "remove_path", "target": "pilothOS/skills/workflow/pilothos-init/greenfield.md"},
    {"op": "remove_path", "target": "pilothOS/skills/workflow/pilothos-init/brownfield.md"},
    {"op": "write_marker"}
  ]
}
```

Ghi chú: staging (stage.sh) đã copy ĐỦ bản phân phối — CLAUDE.md/settings/
.gitignore/registry đều có sẵn dạng placeholder; plan chỉ điền và dọn.
- `adapters` là BẮT BUỘC khi có optional adapter đã staging. Ở dry-run, engine
  chèn deterministic: `remove_path` cho adapter không chọn + `append_lines` cho
  `.gitignore` (từ SSOT theo `gitignore_scope`). Vì chèn TRƯỚC khi user approve
  nên vẫn "thứ approve = thứ thực thi". KHÔNG gõ tay các step này.
- Chỉ 5 step self-prune (dọn mặt tiền init) là hand-author, đặt trước `write_marker`.
- Registry tự tính Next Due theo cadence — không còn bước sửa tay. Sau Apply, sửa
  `<owner>`/`<init>` trong `pilothOS/rot/registry.md` là task thường (có auto-log gate canh).
- Thêm/bớt adapter SAU init: dùng `/piloth:adapter` (skill `pilothos-adapter`).
