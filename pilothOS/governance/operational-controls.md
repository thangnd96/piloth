# Operational Controls

## Default Controls

- **Approval:** thay đổi destructive, irreversible hoặc có ảnh hưởng rộng cần human approval.
- **Permissions:** dùng least privilege; chỉ cấp quyền cần cho task hiện tại.
- **Retry:** retry chỉ khi lỗi có khả năng tạm thời và operation an toàn để lặp.
- **Timeout:** mọi external operation phải có giới hạn hợp lý.
- **Escalation:** dừng và escalate khi thiếu quyền, thiếu Evidence, conflict hoặc rủi ro vượt ngưỡng.
- **Budget:** tránh dùng model/tool đắt hơn nếu capability thấp hơn đã đủ.

## Operational Presets

Default: `standard`.

| Preset | Enforcement |
|---|---|
| light | receipt + basic verification evidence only; advanced context/reuse/UI/warning checklists are advisory |
| standard | task contract + context evidence + reuse evidence + receipt |
| strict | standard + clean verification required + high-risk tool approval |

Consumer có thể chọn thấp/cao hơn theo risk của project, nhưng PilothOS khuyến
nghị `standard` để giữ scope, context và reuse discipline đủ rõ.

Guard selection order:

1. `PILOTHOS_OPERATIONAL_PRESET` or `PILOTHOS_PRESET`
2. `operational_preset` in task contract or receipt
3. default `standard`

Valid values: `light`, `standard`, `strict`.

## Evidence

Mỗi approval hoặc escalation phải ghi reason, scope, decision và người/phần tử phê duyệt.

Human approval trên output không còn là checkbox danh dự: nó được ghi thành artifact
có cấu trúc, mang verdict, qua vòng `review-request` → `review-feedback` và được gate
`human_review` enforce ở `os-close` (xem `runtime/os-control-plane.md`). Quyết định
Allow/Deny của reviewer trên từng tool (khi dùng companion review UI) cũng được ghi
thành evidence `human_review` để truy vết.

Task khai `requires_prototype` tự bật `requires_human_review` — human chọn UI option
đi qua chính vòng review đó, kèm gate `prototype` (mỏng) kiểm ≥2 options + chosen.
Discovery gate (skill `piloth-discovery`) ghi quyết định thành evidence
`kind=discovery` fold vào contract; recipe `phase_plan_suggestion` chỉ khuyến nghị,
không tự bật phase (tránh thêm chi phí ngoài ý muốn).
