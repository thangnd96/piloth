# Hooks — Enforcement Rules

Hooks là cơ chế biến Rule dạng văn bản thành enforcement thật. Các rule dưới đây
được promote từ lessons học qua vận hành thực tế.

## Enforcement Ladder

- Hành vi mức **MUST** với điều kiện máy móc (so sánh ngày, kiểm tra file tồn tại,
  validate format) PHẢI có hook enforcement; prose một mình không đủ tin cậy.
- Hành vi mức **MUST** cần judgment (nhận diện policy, phát hiện speculation)
  không hook được — nguyên tắc chặn phải sống ở Identity (`CLAUDE.md` Ranh giới),
  nơi luôn có mặt trong context, không chỉ trong rule file được nạp theo nhu cầu.
- Hành vi chấp nhận best-effort phải được đánh dấu rõ là best-effort.

## Sau khi sửa cấu hình hook

- Sau MỌI thay đổi `.claude/settings.json`, chạy:
  `python3 pilothOS/scripts/pilothos_guard.py self-check`
  và chỉ mở session khi thấy `SELF-CHECK PASSED`.
- Lý do (lesson đã trả giá): settings.json hỏng sẽ vô hiệu hóa TOÀN BỘ hooks
  một cách im lặng — không lỗi, không cảnh báo.
- Hook mới hoặc hook bị sửa cần được approve lại trong Claude Code (`/hooks`).

## Plan Mode (Claude Code)

- `pre-edit` bỏ qua enforcement khi hook input có `permission_mode == "plan"`.
  Plan mode của harness là planning read-only; contract-before-edit chỉ dành cho
  thực thi. Không exempt thì Piloth chặn cả việc harness ghi plan file.
- Safety-net bổ trợ (độc lập với `permission_mode`): `pre-edit` cho ghi khi MỌI
  target nằm trong thư mục plan của harness — `~/.claude/plans/` hoặc
  `$CLAUDE_CONFIG_DIR/plans/`. Plan file là artifact của Claude Code (ngoài repo),
  không phải code repo nên gate không quản. Trước đây thiếu net này, plan file bị
  rule "path outside repo" chặn khi harness không truyền `permission_mode`.
- Governance (contract, gates, receipt) enforce lại ngay khi session rời plan mode
  (`default`/`acceptEdits`/…).

## Review Hooks (companion tool)

- Bản cài bật sẵn hook của `pilothOS/tools/review/` (activity mirror + permission
  gate), fail-open. Tắt bằng `PILOTH_REVIEW=off` trong `.claude/settings.json` env.
- Review hooks độc lập với hook governance; không thay thế contract/receipt gate.

## Consumer Hook Preservation

- Consumer hooks are preserved.
- Consumer hooks run before PilothOS hooks unless an explicit conflict requires
  judgment.
- PilothOS hooks enforce contract/receipt after consumer-specific workflow has
  run.
- Conflicts produce `NEEDS-JUDGMENT`, never silent overwrite.

`.claude/settings.json` merge semantics:

- Keep consumer hook entries first.
- Append PilothOS hook entries.
- Deduplicate exact same hook objects.
- If event/matcher is the same but command differs, keep both.
- If `env` or `statusLine` conflicts, return `NEEDS-JUDGMENT`.

## Verify tại đích

- Mỗi cơ chế có đích output riêng: hook SessionStart/UserPromptSubmit → context
  của model; statusline → status line UI; Pre/PostToolUse → transcript view
  (Ctrl+R), KHÔNG vào context; side-effect file → filesystem.
- Verify một cơ chế phải nhắm đúng đích của nó. "Không thấy trên terminal"
  không phải Evidence của "không chạy".
- Khi nghi ngờ, dùng side-effect file (ghi log ra /tmp) làm trọng tài cuối cùng.

## Hook Targets hiện có

| Event | Mode của guard script | Vai trò |
|---|---|---|
| SessionStart | `session-start` | Inject cảnh báo Rot vào context khi mở session |
| UserPromptSubmit | `prompt-check` | Inject cảnh báo Rot ở mỗi lượt message |
| statusLine | `statusline` | 🔴 trên UI khi có scope quá hạn; im lặng khi healthy |
| PreToolUse | `pre-edit` | Enforce task contract + allowed paths + layer/path checks cơ học |
| PostToolUse | `post-edit` | Ghi diff facts: files, layers, line counts, docs/tests/evidence flags |
| Stop | `stop-check` | DELIVER GATE: auto-log + deliver receipt đủ evidence; block đúng một lần, không loop |
| (thủ công) | `contract-write` | Ghi task contract trước khi sửa file |
| (thủ công) | `tool-check` | Kiểm tra risk/timeout/approval trước khi chạy tool command |
| (thủ công) | `receipt-write` | Ghi deliver receipt có changed files/layers/verification/result và kiểm lại scope với contract |
| (thủ công) | `self-check` | Kiểm tra settings.json + registry sau mỗi lần sửa cấu hình |

## Task Contract Gate

Trước khi sửa file, agent phải ghi task contract bằng:

```bash
python3 pilothOS/scripts/pilothos_guard.py contract-write <contract.json>
```

Contract tối thiểu:

- `task_scope`
- `consumer_scope` (bắt buộc cho non-doc/test work)
- `affected_layers`
- `allowed_paths`
- `expected_evidence`
- `out_of_scope_paths`
- `context_evidence` (bắt buộc cho non-doc/test work)
- `reuse_evidence` (bắt buộc cho non-doc/test work)
- `decision_limits` (bắt buộc cho non-doc/test work)
- `consumer_asset_routing` (bắt buộc cho non-doc/test work; có thể ghi
  `not_applicable` kèm lý do)
- `ui_design_system_evidence` (bắt buộc khi contract khai UI path rõ ràng,
  và khi UI path cụ thể được sửa)

`pre-edit` chặn máy móc khi thiếu contract, sửa ngoài `allowed_paths`, sửa
`out_of_scope_paths`, sửa core runtime/tool nhạy cảm mà không khai
`Tools/Runtime`, sửa adapter mà không khai adapter/tool layer phù hợp, hoặc sửa
UI path mà thiếu design-system evidence. Docs/test-only work không bắt buộc các
field context/reuse mới nhưng vẫn nên ghi khi có. Miễn trừ docs/test chỉ áp
dụng khi cả `affected_layers` và `allowed_paths` đều là docs/test thực sự; nếu
contract khai `Docs` nhưng path là code/runtime/rules/adapter/UI, guard vẫn
yêu cầu `consumer_scope`, `context_evidence`, `reuse_evidence`,
`decision_limits`, và `consumer_asset_routing`.

`receipt-write` cũng đối chiếu lại toàn bộ changed files từ diff facts và receipt
với contract hiện hành. Nếu receipt khai file ngoài `allowed_paths` hoặc thuộc
`out_of_scope_paths`, deliver receipt bị reject dù `pre-edit` từng pass trước đó.

Operational preset:

- `light`: giữ basic path/receipt evidence, nhưng không block các checklist nâng
  cao như context/reuse/UI/warning.
- `standard`: mặc định; enforce context/reuse/UI/warning receipt shape.
- `strict`: `standard` + verification phải sạch; `not run`, `skipped`, `failed`,
  `blocked`, `unable` không được chấp nhận dù có limitation.

## Deliver Gate

- Điều kiện "phiên có thay đổi file mà review-log/lessons-learned chưa được cập nhật"
  là máy móc → được enforce bằng Stop hook, đúng Enforcement Ladder.
- Khi bị chặn, agent phải: append log entry phù hợp, HOẶC nêu rõ trong reply cuối
  "Không có finding hoặc lesson cần ghi" kèm một câu lý do.
- Receipt phải có `changed_files`, `affected_layers`, `verification_command`,
  `result`; nếu verify không chạy/failed/skipped thì phải có `limitation`.
- Với code/UI/runtime/rules/adapter changes, receipt phải có `scope_evidence`
  và `context_used` để người nhận thấy rõ vì sao thay đổi nằm trong scope và
  context nào đã được dùng.
- Với code/UI/runtime/rules/adapter changes, receipt phải có
  `consumer_asset_routing` để nêu asset consumer nào được route hoặc vì sao
  không áp dụng.
- Với code/UI/runtime/rules/adapter changes, receipt phải có `learning_review`
  để ghi rõ có lesson/finding cần append/promote không. Hook chỉ kiểm shape;
  model/người chịu trách nhiệm đánh giá nội dung.
- Với code/UI/runtime/rules/adapter changes, receipt phải có
  `quality_gates.reuse_non_duplication.result` và `evidence` với result là
  `PASS`, `FAIL` hoặc `NOT_APPLICABLE`.
- Với code/UI/runtime/rules/adapter changes, receipt phải có
  `reuse_discipline`.
- Với UI changes, receipt phải có `design_system_checked`,
  `component_reuse_decision`, `token_reuse_decision`.
- Với dependency file changes, receipt phải có
  `warning_checklist.dependency_change_reason`.
- Với warning generated bởi `post-edit`, receipt phải có checklist tương ứng:
  `dependency_change_reason`, `new_component_reason`,
  `ui_design_system_gap_reason`, `code_without_test_reason`, hoặc
  `large_delta_reason`.
- Nếu receipt khai `tool_uses`, mỗi tool use phải có `tool`, `command`, `risk`,
  `timeout`, `result`, `evidence_output`; high-risk tool/command phải có
  `approval_evidence`; skipped/failed tool phải có `limitation`.
- Với thay đổi cần judgment, receipt phải trả lời checklist: đúng layer, abstraction,
  scope, evidence. Hook chỉ kiểm checklist có câu trả lời, không tự phán nội dung.
- Gate chỉ chặn MỘT lần mỗi lượt dừng (`stop_hook_active`) — không bao giờ tạo loop.
- Giới hạn trung thực: gate đảm bảo câu hỏi "có gì đáng ghi không?" LUÔN được đặt ra;
  chất lượng câu trả lời (nhận diện đúng lesson) vẫn cần judgment của model.
- Cảnh báo Rot qua UserPromptSubmit chỉ phát MỘT LẦN mỗi phiên cho cùng trạng thái
  overdue (tối ưu token); trạng thái đổi → cảnh báo lại.

## Default Markdown Hooks (checklist hành vi)

### Before Coding

- Identify affected layer.
- Check relevant rules.
- Define success criteria.

### Before Editing

- Confirm scope.
- Avoid unrelated refactor.
- Check for required approval.

### Before Delivery

- Verify result.
- Report evidence.
- Log Rot if found.
