# Init — Nhánh Greenfield (judgment guide)

## Elicit (AskUserQuestion)

1. Persona (một câu) — Enter/bỏ trống = giữ placeholder, sửa sau.
2. Mục tiêu 6–12 tháng (1–3 dòng đo được) — bỏ trống = placeholder.
3. Tool adapters giữ lại (multi-select): Claude Code / Cursor / Codex / Antigravity.

## Plan mẫu (đã validate qua engine)

```json
{
  "plan_version": 1,
  "mode": "greenfield",
  "fill": {"PERSONA": "<từ elicit>", "GOALS": "<từ elicit>", "OWNER": "<từ elicit>"},
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
Registry tự tính Next Due theo cadence — không còn bước sửa tay. Adapter không
chọn → thêm
`{"op":"remove_path","target":".cursor"}` (tương tự `.codex`, `.antigravity`).
Registry baseline: sau Apply, sửa `<owner>`/`<init>` trong
`pilothOS/rot/registry.md` là task thường (ngoài engine, có auto-log gate canh).
