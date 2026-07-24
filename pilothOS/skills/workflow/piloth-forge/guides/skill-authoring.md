# Forge Guide — Skill Authoring

> Chương này của manual Forge (nạp theo nhu cầu).

## Spec

```json
{
  "kind": "skill",
  "id": "my-project-deploy-check",
  "layer": "Skills",
  "intent": "Một câu: skill này làm gì.",
  "reason": "Task/incident thật biện minh cho việc tạo (extension rule).",
  "authority": { "guard_modes": ["os-evidence"], "paths": ["pilothOS/memory/state/os-runs/**/artifacts/**"] }
}
```

- `id`: kebab-slug, duy nhất (không trùng capability-manifest).
- `layer` phải khớp `kind`: skill→`Skills`, rule→`Rules`, gate→`Evaluation`.
- `reason` **bắt buộc** — extension rule của Piloth: không tạo capability khi chưa
  có nhu cầu thật.

## Cấu trúc SKILL.md (template sinh sẵn)

Purpose · Non-Responsibilities · Preconditions · Steps · Verification ·
Failure & Escalation · References. Giữ **Non-Responsibilities** rõ (điều skill
KHÔNG làm) và **Verification** cụ thể (bằng chứng, không phải lời hứa).

## Scaffold

```bash
python3 pilothOS/scripts/pilothos_guard.py forge-scaffold spec.json
```
Trả `files` (nội dung đề xuất, CHƯA ghi) + `manifest_entry`. Reuse trước: chạy
`os-inspect` + `reuse-scan` để chắc chưa có skill tương đương.
