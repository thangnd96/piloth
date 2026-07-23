# Piloth Workflow

Tài liệu này mô tả cách **Piloth v1.10.0** hoạt động từ lúc được cài vào project đến khi AI agent nhận, thực hiện, kiểm chứng và bàn giao một task.

## Tổng quan

Piloth có hai workflow chính:

1. **Installation Workflow** — đưa PilothOS vào project an toàn bằng plan/apply transaction.
2. **Task Execution Workflow** — bootstrap context, route layer, thực hiện task, quality gate và ghi nhận learning.

```text
Install Piloth
    ↓
Initialize PilothOS
    ↓
Open new agent session
    ↓
Bootstrap + classify task
    ↓
Load minimum context
    ↓
Plan → Execute → Review → Repair → Deliver
    ↓
Append finding / lesson when appropriate
```

# 1. Installation Workflow

## 1.1 Entry Channels

### Claude Code Plugin

```text
/plugin marketplace add thangnd96/piloth
/plugin install piloth@piloth-marketplace
/piloth:init
```

`/piloth:init` gọi staging script của plugin, sau đó chuyển quyền điều phối cho installer skill trong project.

### Manual / Other Tools

```bash
git clone https://github.com/<github-user>/piloth /tmp/piloth
/tmp/piloth/scripts/stage.sh /path/to/project
```

Sau đó tool đọc:

```text
pilothOS/skills/workflow/pilothos-init/SKILL.md
```

Hai channel dùng cùng source và cùng installer engine.

## 1.2 Staging

`stage.sh` là wrapper gọi `stage.py`.

Staging có trách nhiệm:

- copy Piloth distribution vào project;
- không ghi đè file consumer đã tồn tại;
- stage kernel, adapters, templates và installer facade;
- dừng nếu project đã được init hoặc có trạng thái không an toàn.

Staging chưa phải Apply. Nó chỉ đưa installer và source cần thiết vào project.

## 1.3 Init Lifecycle

```text
Preflight
   ↓
Detect
   ↓
Audit + Elicit
   ↓
Plan
   ↓
Approve
   ↓
Apply
   ↓
Verify
   ↓
Log
   ↓
Self-Prune
```

### Preflight

```bash
python3 pilothOS/scripts/pilothos_guard.py preflight
```

Kiểm tra runtime prerequisites và trạng thái file cơ bản. Fail thì dừng ngay.

### Detect

```bash
python3 pilothOS/scripts/pilothos_guard.py detect
```

Phân loại project:

- `greenfield`;
- `brownfield`;
- `re-init`;
- `dirty` hoặc cần xử lý thủ công.

Agent phải trình verdict và Evidence để consumer xác nhận; không tự rẽ nhánh im lặng.
Với `re-init`, không chạy lại greenfield/brownfield plan; dùng upgrade flow
(`stage.sh --upgrade` + plan `mode=upgrade`) nếu user muốn nâng cấp.

### Audit + Elicit

Agent chỉ nạp đúng guide của nhánh:

- `greenfield.md`; hoặc
- `brownfield.md`.

Sau đó thu thập:

- Persona của implementation;
- Mục tiêu;
- adapters cần giữ: Claude, Cursor, Codex, Antigravity;
- các file hiện có cần preserve/merge;
- constraint và risk của project.

### Plan

Agent tạo:

```text
pilothOS/.pending-plan.json
```

Plan chứa các operation deterministic như:

- create/write file;
- merge supported content;
- remove adapter không chọn;
- write initialization marker;
- self-prune installer facade.

Plan được dry-run trước:

```bash
python3 pilothOS/scripts/pilothos_installer.py dry-run pilothOS/.pending-plan.json
```

Chỉ khi `plan_valid` mới được trình consumer approve.

### Approve

Consumer approve đúng file plan. Nếu có điều chỉnh:

```text
sửa plan → dry-run lại → trình lại → approve lại
```

Không tồn tại bước agent diễn giải lại plan trong Apply.

### Apply

```bash
python3 pilothOS/scripts/pilothos_installer.py apply pilothOS/.pending-plan.json
```

Engine thực hiện transaction:

```text
Validate plan
    ↓
Simulate operations
    ↓
Create backup + manifest
    ↓
Apply exact approved operations
    ↓
Run postconditions / self-check
    ↓
Success receipt
        hoặc
Auto-rollback
```

Agent không được tự sửa file bên ngoài engine trong giai đoạn này.

### Verify

Agent đọc receipt và xác nhận:

- apply thành công;
- effects khớp plan;
- `completeness_missing` không tồn tại;
- initialization marker đã ghi;
- self-check pass;
- `.pending-plan.json` được xóa.

### Log

Kết quả installation được append vào review log bằng guard:

```bash
python3 pilothOS/scripts/pilothos_guard.py log-append review ...
```

Evidence trỏ tới manifest/receipt thật.

### Self-Prune

Installer facade chạy một lần được dọn khỏi project:

- init command/skill facade;
- branch guide chỉ phục vụ lần cài đầu.

Các thành phần sau vẫn được giữ:

- installer engine;
- uninstall command;
- manifest và backup;
- guard;
- runtime và kernel.

Nhờ đó project có thể uninstall và restore an toàn.

## 1.4 First Boot

Sau install:

1. Mở session agent mới.
2. Approve hooks nếu tool yêu cầu.
3. Chạy:

```bash
python3 pilothOS/scripts/pilothos_guard.py self-check
```

4. Rà lại Persona/Mục tiêu trong `CLAUDE.md`.
5. Bắt đầu task thật đầu tiên.

# 2. Startup Workflow Cho Mỗi Task

`CLAUDE.md` hoặc `AGENTS.md` dẫn agent vào:

```text
pilothOS/bootstrap.md
```

Bootstrap contract:

```text
Identity
  ↓
Constitution
  ↓
Rot status
  ↓
Rules index
  ↓
Runtime index
  ↓
Affected layer indexes
  ↓
Only required files
```

## 2.1 Check Rot

Agent chỉ đọc bảng trạng thái trong:

```text
pilothOS/rot/registry.md
```

- Có scope quá hạn/trigger phù hợp → nhắc trước khi làm task.
- Không quá hạn → không tạo noise trong reply.
- Không mặc định đọc review log hoặc review guide.

## 2.2 Classify Affected Layers

Ví dụ:

| Loại task | Layer cần nạp |
|---|---|
| Coding policy | Rules |
| Project state/history | Memory |
| Architecture/domain/standards | Knowledge |
| Workflow tái sử dụng | Skills |
| Lifecycle/state/handoff | Runtime |
| Role/model/permission | Agents |
| API/MCP/CLI | Tools |
| Approval/risk/escalation | Governance |
| Acceptance/quality | Evaluation |

Agent phải chỉ rõ layer bị tác động nếu task có thay đổi kiến trúc.

## 2.3 Progressive Context Loading

```text
Classify task
   ↓
Load layer index
   ↓
Follow Contents references
   ↓
Load only files needed
```

Không nạp toàn bộ `pilothOS/`, toàn bộ Knowledge hoặc toàn bộ Skills chỉ để “phòng khi cần”.

# 3. Task Execution Lifecycle

```text
Intake
  ↓
Plan
  ↓
Execute
  ↓
Review
  ↓
Repair
  ↓
Deliver
```

## Intake

Đầu ra bắt buộc:

- scope;
- assumptions;
- affected layers;
- ambiguity/risk quan trọng.

## Plan

Định nghĩa:

- các bước ngắn;
- success criteria;
- verification cho từng bước;
- approval cần thiết.

Task nhỏ có thể gộp Intake + Plan nhưng không được bỏ verification.

## Execute

Agent:

- chỉ thay đổi đúng phạm vi;
- tuân theo coding behavior;
- không refactor phần không liên quan;
- dùng Skills nếu có workflow đã được validate;
- dùng Tools thông qua adapter/integration phù hợp.

## Review

Evaluation kiểm tra quality gates:

- correctness;
- scope discipline;
- evidence;
- regression risk;
- layer responsibility;
- test/verification result.

Không Deliver khi gate chưa đạt. Task khai `requires_prototype` thêm gate
`prototype` (≥2 UI options + chosen) và tự bật `human_review`; discovery gate ghi
`os-evidence kind=discovery` cho Traceability. Xem `pilothOS/evaluation/quality-gates.md`.

## Repair

Nếu Review fail:

```text
Finding
  ↓
Root cause
  ↓
Minimal repair
  ↓
Re-verify
```

Không che finding bằng workaround nếu root cause có thể xử lý đúng layer.

## Deliver

Output cuối gồm:

- kết quả;
- Evidence;
- tests/checks đã chạy;
- limitation/trade-off còn lại;
- finding hoặc lesson cần ghi.

# 4. Enforcement Workflow

## Session and Prompt Hooks

Guard có thể inject Rot warning tại:

- `SessionStart`;
- `UserPromptSubmit`;
- statusline.

Healthy thì im lặng.

## Pre/Post Tool Hooks

`pre-edit` enforce các điều kiện máy kiểm được từ task contract:

- đã có `task_scope`, `affected_layers`, `allowed_paths`, `expected_evidence`,
  `out_of_scope_paths`;
- edit nằm trong `allowed_paths` và không nằm trong `out_of_scope_paths`;
- file runtime/tool nhạy cảm phải khai `Tools/Runtime`;
- adapter change phải khai layer adapter/tool phù hợp.

`pre-edit` **bỏ qua khi Claude ở plan mode** (`permission_mode=plan` trong hook
input): plan mode là planning read-only, contract-before-edit chỉ áp dụng khi thực
thi. Governance enforce lại ngay khi rời plan mode.

`post-edit` chỉ ghi diff facts: file đổi, layer bị đụng, số dòng đổi, có docs/test
liên quan không, evidence command đã ghi chưa. Hook không judge đúng/sai.

## Review Hooks (Governed Visual Review)

Bản cài bật sẵn hook của companion tool `pilothOS/tools/review/` (activity mirror +
remote permission gate). Chúng **fail-open**: khi không chạy review server, curl fail
nhanh và agent không bị chặn (~0 chi phí).

Tắt review hooks: đặt `PILOTH_REVIEW=off` trong `env` của `.claude/settings.json`
(hook thành no-op hoàn toàn), hoặc xóa 4 entry `review-hook.sh` trong `settings.json`.
Chúng độc lập với các hook governance của guard.

## Deliver Gate

Trước khi session có thay đổi file kết thúc, Stop hook kiểm tra auto-log và
deliver receipt.

Agent phải:

- append vào `rot/review-log.md`; hoặc
- append vào `memory/lessons-learned.md`; hoặc
- nêu rõ không có finding/lesson và lý do.

Receipt phải có:

- changed files;
- affected layers;
- verification command;
- result;
- limitation nếu không test được.

Gate chỉ chặn một lần để không tạo loop.

# 5. Agent Team Workflow

Chỉ kích hoạt team khi có Evidence task cần nhiều vai trò:

- generator/evaluator loop;
- independent review;
- contract negotiation;
- user yêu cầu team rõ ràng.

```text
Runtime identifies team need
    ↓
Load validated team contract
    ↓
Assign role responsibilities
    ↓
Execute handoff protocol
    ↓
Resolve conflict bằng Evidence
    ↓
Stop khi đạt team condition
```

Mỗi handoff phải có:

- role decision;
- Evidence;
- risks;
- next handoff.

Agent Teams định nghĩa composition; Runtime vẫn sở hữu orchestration; Agents vẫn sở hữu role execution.

# 6. Debugging Workflow

Khi hệ thống hành xử lạ, kiểm tra từ ngoài vào trong:

```text
Tools
→ Agents
→ Runtime
→ Skills
→ Memory & Knowledge
→ Rules & Hooks
→ Identity
```

Không sửa Identity hoặc policy ổn định khi chưa loại trừ tool, adapter, runtime và context loading.

# 7. Learning and Rot Workflow

```text
Incident / repeated friction
    ↓
Collect Evidence
    ↓
Identify owning layer
    ↓
Record finding or lesson
    ↓
Promote to Rule / Knowledge / Skill khi đủ Evidence
    ↓
Update registry and review log
```

Nguyên tắc:

- Lỗi lặp lại → Rule, Knowledge hoặc Skill phù hợp.
- Review log là append-only.
- Không sửa lịch sử để phù hợp tên hoặc trạng thái mới.
- Vendor lessons không được ghi sẵn vào consumer logs.
- Event-based không có nghĩa là miễn review; Rot Signals vẫn kích hoạt review.

# 8. Uninstall Workflow

```text
/piloth:uninstall
    ↓
Read install manifest
    ↓
Validate backup and current state
    ↓
Restore consumer files
    ↓
Remove staged Piloth files
    ↓
Verify restoration
```

Uninstall dùng manifest và backup do Apply tạo. Vì installer facade được backup trước self-prune, uninstall có thể phục hồi cả trạng thái trước khi cài.
