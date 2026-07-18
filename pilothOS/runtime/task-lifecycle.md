# Task Lifecycle

## States

| State | Entry | Exit Evidence |
|---|---|---|
| Intake | `os-start request.json` | Scope, assumptions, target repo, target paths, affected layers, task id |
| Contract | `os-start` writes active contract | Scope, target-relative allowed paths, consumer scope, expected evidence, context evidence, reuse evidence, decision limits |
| Route | `os-start` routes assets/scheduler | Consumer asset routing, health notes, expected evidence, target snapshot |
| Execute | Contract active | Implementation/output + post-edit diff facts |
| Tool/Evidence | Tool/checks run | `os-evidence evidence.json` entries; no full output/secrets |
| Review | Có output | Required quality gates, judgment checklist khi cần |
| Repair | Review chưa đạt | Issues đã xử lý và re-verified |
| Receipt | Tất cả gate đạt | Receipt with changed files/layers, verification, limitations and `claims[]` |
| Seal | `os-close receipt.json` | Recorded receipt seal, target seal, clean control-plane/target janitors, passing control-plane check |

## Rules

- Task trivial có thể gộp Intake và Plan, nhưng không bỏ verification.
- Không chuyển Deliver khi quality gate chưa đạt.
- Retry, timeout và escalation tuân theo Governance.
- Canonical path: `os-start` → edit/tool evidence → `os-evidence` →
  `os-close` → `os-verify`.
- For controlled-target work, pass an absolute `target_repo` to `os-start` and
  use `target_paths` plus target-relative receipt `changed_files`.
- Explicit controlled targets default to `execution_strategy=controlled_target`
  and `target_footprint_policy=no_control_plane_files`; the target must not get
  `pilothOS/`, `.claude/`, `.codex/`, `.cursor/` or `.antigravity/`.
- UI tasks must record `ui_quality` metric evidence before close. Browser
  smoke text alone is not enough when visual/browser defects could be present.
- Trước khi sửa file, phải có active contract. `os-start` tạo contract này;
  `contract-write` vẫn tồn tại cho adapter/test mỏng.
- Sau khi sửa, để `post-edit` ghi diff facts; không dùng diff facts làm judgment.
- Không Deliver khi phiên có thay đổi file mà chưa cân nhắc ghi log và chưa có
  deliver receipt đủ evidence (Stop hook enforce).
- Deliver receipt phải ở trong target-relative `allowed_paths` và không thuộc
  `out_of_scope_paths` của task contract hiện hành.
- Policy cần judgment phải có checklist/evidence; hook chỉ kiểm sự hiện diện,
  model/người chịu trách nhiệm đánh giá nội dung.
- `os-close` reject claim tuyệt đối (`1:1`, `production-ready`, `fully verified`,
  `no issues`, `full`, `complete`, `all tokens`, `entire library`) khi evidence
  có limitation, skipped check, failed pixel diff, missing font hoặc blocker
  chưa xử lý.
- `os-close` reject claim “rẻ hơn”, “tiết kiệm token” hoặc lower-cost khi không
  có `llm_usage` với `real_token_telemetry=true`.

## Canonical Commands

Repo-local default target:

```bash
python3 pilothOS/scripts/pilothos_guard.py os-start request.json
python3 pilothOS/scripts/pilothos_guard.py os-evidence evidence.json
python3 pilothOS/scripts/pilothos_guard.py os-close receipt.json
python3 pilothOS/scripts/pilothos_guard.py os-verify
```

External git or non-git target:

```json
{
  "task_id": "controlled-target",
  "intent": "Implement scoped target change",
  "target_repo": "/Users/me/work/vngg-ds",
  "execution_strategy": "controlled_target",
  "target_paths": ["packages/tokens/**", "docs/tokens.md"],
  "expected_evidence": ["pnpm typecheck"],
  "out_of_scope_paths": ["packages/components/**"]
}
```

```bash
python3 pilothOS/scripts/pilothos_guard.py os-start request.json
python3 pilothOS/scripts/pilothos_guard.py os-evidence evidence.json
python3 pilothOS/scripts/pilothos_guard.py os-close receipt.json
python3 pilothOS/scripts/pilothos_guard.py os-verify
```
