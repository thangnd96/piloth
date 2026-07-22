# Task Lifecycle

## States

| State | Entry | Exit Evidence |
|---|---|---|
| Intake | `os-start request.json` | Scope, assumptions, target repo, target paths, affected layers, task id |
| Contract | `os-start` writes active contract | Scope, target-relative allowed paths, consumer scope, expected evidence, context evidence, reuse evidence, decision limits |
| Route | `os-start` routes assets/scheduler | Consumer asset routing, health notes, expected evidence, target snapshot |
| Prototype (optional) | Contract khai `requires_prototype` | ≥2 UI options + option đã chọn; `PROTOTYPE.md`; `os-evidence kind=prototype`; human pick qua human_review round-trip |
| Execute | Contract active | Implementation/output + post-edit diff facts |
| Tool/Evidence | Tool/checks run | `os-evidence evidence.json` entries; no full output/secrets |
| Review | Có output | Required quality gates, judgment checklist khi cần; với human-review: `review-request` → structured `review-feedback` (verdict + findings) |
| Repair | Review chưa đạt | Issues đã xử lý và re-verified; blocker/major từ human-review được xử lý trước khi finalize |
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
- Task khai `requires_human_review` trong contract không được Seal khi chưa có
  artifact `review-feedback` với `verdict=approve` + `finalized=true` và không còn
  blocker/major chưa xử lý; blocker/major route ngược về Repair. Guard chỉ kiểm
  sự tồn tại/đầy đủ của artifact, con người chịu trách nhiệm nội dung review.
- Task khai `requires_prototype` tự động bật `requires_human_review` (human pick
  tái dùng chính review round-trip). Gate `prototype` (mỏng) chỉ đạt khi
  `os-evidence kind=prototype` có method hợp lệ, ≥2 options và một `chosen` nằm
  trong options; thiếu → `os-close` route về Repair. Receipt tự khai
  `prototype: PASS` mà không có evidence backing vẫn FAIL (chống honor-system).
- Discovery gate là gate judgment phase chạy đầu (không phải hook tự trigger):
  khi có ≥3 câu hỏi mở hoặc 1 câu high-impact, dùng skill `piloth-discovery` để
  hỏi-xác nhận qua Governed Visual Review, rồi ghi `os-evidence kind=discovery`
  và fold quyết định vào contract `discovery_decisions` để Traceability trace tới.
  `DISCOVERY.md` là working doc, không thuộc `produces`/`depends_on`.
- `phase_plan_suggestion` trong contract là **advisory** (recipe right-sizing):
  khuyến nghị bật discovery/prototype, hiển thị ở `os-status`/`os-report`, nhưng
  không tự bật phase — con người quyết ở `os-start` kế tiếp.
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
# Human-review round-trip (khi contract khai requires_human_review):
python3 pilothOS/scripts/pilothos_guard.py review-request <task-id>
python3 pilothOS/scripts/pilothos_guard.py review-feedback feedback.json
python3 pilothOS/scripts/pilothos_guard.py review-verify <task-id>
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
