# Capability & Authority Model (T0)

## Purpose

Reify "authority" của PilothOS từ trạng thái ngầm/rải rác thành một surface
**first-class, fail-closed, inspectable** — phiên bản Piloth của mô hình
*manifest-as-ACL* + *construction ≠ activation* mà một agent OS đúng nghĩa phải
có. Đây là nền móng (T0) mà Execution Broker (T1) và Piloth Forge (T3) dựa lên.

Trước T0: entitlement khai rời trong contract (`allowed_entitlements`), guard tự
nhận đây là "project policy, not a host-kernel permission grant", và không có
nơi duy nhất mô tả *một capability được phép làm gì*. T0 tạo nơi đó.

## SSOT

`pilothOS/governance/capability-manifest.json` — mỗi capability (kind ∈
`skill | rule | gate | adapter | guard-mode`) khai một `authority` block:

| Field | Ý nghĩa | Default (fail-closed) |
|---|---|---|
| `paths` | Glob path capability được ghi | `[]` |
| `guard_modes` | Guard mode capability được gọi | `[]` |
| `entitlements` | Entitlement cần (khớp contract `allowed_entitlements`) | `[]` |
| `enforcement_surface` | Gate mà capability tham gia cưỡng chế | `[]` |
| `writes_policy` | Có sửa policy/rule không | `false` |

## Nguyên tắc

- **Fail-closed**: field `authority` thiếu = quyền rỗng nhất. Field khai sai kiểu
  bị coi như default (không tin), và `capability-check` flag riêng. Giống AOS
  *"every field fails closed"*.
- **construction ≠ activation**: guard **không bao giờ** tự cấp quyền cho
  capability do agent tạo. Nó chỉ *validate* và *trình authority-delta* để human
  duyệt. Ánh xạ `rules/index.md` ("Agent không tự tạo/sửa/bỏ qua Rule") + AOS
  *"generated code cannot self-promote"*.
- **coverage tăng dần**: `coverage: "partial"` — danh mục bổ sung qua vận hành
  thật (và Forge/T3 giúp giữ đầy đủ). Enforcement **fail-closed cứng** (tool-check
  từ chối entitlement chưa khai) chỉ bật khi `coverage: "full"`. Trong lúc partial,
  wiring vào `self-check`/`control-plane-check` là **advisory/fail-soft**
  (forward-looking, giống drift-warning v1.11) — không phá install hiện có.

## Guard modes

```bash
python3 pilothOS/scripts/pilothos_guard.py capability-list      # liệt kê + authority đã resolve
python3 pilothOS/scripts/pilothos_guard.py capability-check     # validate shape + fail-closed defaults
python3 pilothOS/scripts/pilothos_guard.py authority-delta <before.json> <after.json>
```

- `capability-check`: `capability_check_passed|failed` + `errors`/`warnings`.
- `authority-delta`: in phần chênh quyền; `widened: true` khi có thêm
  path/entitlement/guard_mode/enforcement mới **hoặc** `writes_policy` False→True.
  Dùng khi thêm/sửa capability (Forge/T3) hoặc khi task xin entitlement ngoài
  contract — human duyệt delta trước khi kích hoạt.

## Non-Responsibilities

- Không định nghĩa capability (chúng sống ở layer tương ứng: skills/, rules/,
  evaluation/, adapters/); đây chỉ là nơi khai **authority**.
- Không phải host-kernel permission grant, không phải code signing/sandbox thật.
  Enforcement cơ học tại biên tool-call là việc của T1 (Execution Broker).

## Roadmap tích hợp

- **T1**: `tool-check` đọc entitlement từ SSOT này (một khai báo, không drift);
  broker fail-closed khi `coverage: "full"`.
- **T3**: Forge sinh capability mới → `capability-check` + `authority-delta` là
  bước verify + trình duyệt bắt buộc trước khi install.
