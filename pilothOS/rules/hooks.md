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
| PreToolUse / PostToolUse | `pre-edit` / `post-edit` | Target no-op ổn định, siết dần khi có nhu cầu thật |
| Stop | `stop-check` | AUTO-LOG GATE: chặn kết thúc phiên có thay đổi file mà log chưa được cân nhắc; block đúng một lần, không loop |
| (thủ công) | `self-check` | Kiểm tra settings.json + registry sau mỗi lần sửa cấu hình |

## Auto-Log Gate

- Điều kiện "phiên có thay đổi file mà review-log/lessons-learned chưa được cập nhật"
  là máy móc → được enforce bằng Stop hook, đúng Enforcement Ladder.
- Khi bị chặn, agent phải: append log entry phù hợp, HOẶC nêu rõ trong reply cuối
  "Không có finding hoặc lesson cần ghi" kèm một câu lý do.
- Gate chỉ chặn MỘT lần mỗi lượt dừng (stop_hook_active) — không bao giờ tạo loop.
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
