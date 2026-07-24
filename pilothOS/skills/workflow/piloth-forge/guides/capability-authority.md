# Forge Guide — Capability & Authority

> Chương này của manual Forge (nạp theo nhu cầu). Xem cơ sở: `pilothOS/runtime/capability-model.md`.

## Authority block

Mỗi capability khai `authority` (fail-closed — thiếu = quyền rỗng nhất):

| Field | Ý nghĩa | Default |
|---|---|---|
| `paths` | glob path được ghi | `[]` |
| `guard_modes` | guard mode được gọi | `[]` |
| `entitlements` | entitlement cần (khớp contract `allowed_entitlements`) | `[]` |
| `enforcement_surface` | gate mà capability tham gia cưỡng chế | `[]` |
| `writes_policy` | có sửa policy/rule không | `false` |

## Nguyên tắc

- **Khai tối thiểu (least-privilege).** Chỉ khai path/entitlement thật sự cần.
  `authority-delta` sẽ phơi bày mọi thứ bạn xin — "đừng tóm tắt một network grant
  rộng thành chỉ 'API access'".
- **construction ≠ activation.** `forge-plan` chỉ *trình* authority-delta để human
  duyệt. Việc thêm entry vào `capability-manifest.json` (cấp quyền thật) là bước
  human làm sau khi duyệt — Forge không tự làm.
- **`widened=true`** nghĩa là spec xin thêm quyền so với rỗng → cần duyệt kỹ.

## Kiểm

```bash
python3 pilothOS/scripts/pilothos_guard.py forge-plan spec.json   # authority-delta + verify
```
`writes_policy: true` (sửa rule/policy) là quyền nhạy cảm — chỉ khai cho rule.
