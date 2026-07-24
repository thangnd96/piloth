# Execution Broker / Airlock (T1)

## Purpose

Nâng biên tool-call của PilothOS từ honor-system thành một **PDP thật** — phiên
bản Piloth của **Process Airlock** trong AOS (`capsule-shell`). Đây là điểm then
chốt credibility (probe #1 "enforcement là thật hay prompt-theater?"): một số
lệnh bị **từ chối vô điều kiện, trước bất kỳ approval nào** (catastrophic
hard-deny), thay vì chỉ dựa vào prose hay honor-system.

## Cơ chế

Guard mode `broker-check` (hook) wired vào `PreToolUse` matcher `Bash`
(`pilothos-init/payloads/settings.json`). Nó đọc `tool_input.command`, tách theo
`&&`/`||`/`;`/`|`/newline và kiểm **từng sub-command độc lập** (một đầu an toàn
không che được đuôi nguy hiểm), rồi quyết định:

| Quyết định | Khi nào | Hành vi hook |
|---|---|---|
| **deny** | **catastrophic** (bên dưới) | `block_decision` — chặn thật, vô điều kiện |
| **ask** | high-risk không-catastrophic (`HIGH_RISK_COMMAND_PATTERNS`: `rm -rf`, deploy, kubectl, terraform apply, aws/gcloud mutate…) | pass-through cho **native permission prompt** của host (không double-prompt) |
| **allow** | sạch | chạy bình thường |

### Catastrophic hard-deny (copy kỷ luật `capsule-shell` của AOS)

- **fork bomb** — `:(){ :|:& };:` và biến thể copy-paste
- **mkfs** — format filesystem (`mkfs`, `mkfs.*`)
- **dd → block device** — `dd ... of=/dev/{sd,disk,nvme,hd,mmcblk,vd,xvd,rdisk}…`
  (đọc từ đĩa `if=/dev/sda of=file` thì **an toàn** — chỉ chặn GHI ra đĩa)
- **rm → protected root path** — `rm -r[f]` (hoặc `--no-preserve-root`) nhắm `/`,
  `/*`, `~`, `$HOME`, `*`, hoặc top-level system dir (`/etc`, `/usr`, `/bin`,
  `/var`, `/System`, `/Library`, …)
- **ghi ra block device** — redirect `> /dev/sd…`

## Nguyên tắc thiết kế

- **Hard-deny là thật; phần còn lại trung thực là advisory** — đúng như AOS
  (native-tool gating "honestly ADVISORY, fail-open"; hard-deny vô điều kiện).
- **Fail-OPEN khi lỗi nội bộ** — một governance hook **không bao giờ** được brick
  session bằng cách block tất cả (bài học settings.json). Catastrophic matching
  dùng string op đơn giản, có guard; nếu handler lỗi → allow (disclosed).
- **No-regex ở hot path chính** — tách sub-command bằng `str.replace`/`split`
  tuyến tính (không ReDoS); tokenize bằng `shlex`.
- **Chỉ thu hẹp** — broker chỉ thêm deny, không nới quyền Claude Code sẵn có
  (deny-list `settings.json` vẫn còn hiệu lực; broker bổ sung, không thay thế).

## Non-Responsibilities / Giới hạn (ghi cùng `VALIDATION.md`)

- **Không** sandbox thực thi token-level của model (không phải WASM kernel); broker
  cưỡng chế tại **biên tool-call** — đúng nơi Airlock/PDP của AOS hoạt động cho
  host-tool, không phải toàn bộ enforcement của AOS.
- **Thật chỉ trên harness có hook** (Claude Code); trên Codex/Cursor/Antigravity là
  **advisory** tới khi adapter route tool-call qua guard.
- **Consent ("ask")** dựa vào native permission prompt của host; broker không tự
  dựng UI prompt.
- **Command-substitution evasion** (`rm -rf $(echo /)`) là giới hạn đã biết —
  tách sub-command không mở `$(...)`. Ưu tiên bắt các dạng trực tiếp/chuỗi phổ biến.
- Entitlement fail-closed cho tool KHAI entitlement đã sống ở `tool-check`
  (`validate_payload_entitlements`); broker lo biên Bash command nơi tool-check
  không phủ. Tích hợp đọc entitlement từ `capability-manifest` sẽ bật cứng khi
  `coverage=full` (T0).

## Verify

```bash
python3 -m pytest tests/unit/test_broker.py -q        # deny/ask/allow + chained + fail-open
python3 -m pytest tests/benchmark -q                  # none-vs-had (probe #7)
printf '{"tool_input":{"command":"rm -rf /"}}' | python3 pilothOS/scripts/pilothos_guard.py broker-check
```
