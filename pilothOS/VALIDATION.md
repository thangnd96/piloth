# Validation

Tài liệu này mô tả những gì bản phân phối hiện tại đã được kiểm chứng, và các
giới hạn đã biết. Lịch sử thay đổi theo version: xem `CHANGELOG.md` ở root.

## Đã kiểm chứng qua vận hành

- **Rot detection**: phát hiện scope quá hạn được enforce bằng hook (inject cảnh
  báo vào context) và statusline (chỉ báo 🔴 cho người dùng); im lặng khi healthy.
- **Auto-log gate**: phiên có thay đổi file không thể kết thúc khi chưa append log
  hoặc tuyên bố rõ "không có finding" — enforce bằng Stop hook, chặn đúng một lần,
  không tạo vòng lặp.
- **Layer-boundary & speculation gate**: được enforce ở mức Identity, adapter
  instruction và review workflow. `pre-edit` / `post-edit` hiện là hook target
  no-op có chủ đích để siết dần khi điều kiện kiểm tra có thể máy móc hóa;
  release này không overclaim rằng judgment-based violations đã bị hook chặn
  trước khi thực hiện.
- **Installer plan/apply**: thứ được approve là `install-plan.json`, engine
  thực thi đúng file đó (byte-identical) — loại bỏ cấu trúc khe hở "approve một
  đằng, apply một nẻo"; simulate toàn bộ trước khi chạm đĩa; auto-rollback.
- **Installer transactional**: `/pilothos-init` backup + manifest TRƯỚC mọi thay
  đổi; `/pilothos-uninstall` phục hồi nguyên trạng từ manifest; detect chống
  init-đè; approve có cấu trúc, điều chỉnh kèm approve không bị bỏ sót.
- **Ghi log máy móc**: `log-append` tự điền ngày, chống vỡ bảng, từ chối Evidence
  path không tồn tại.

## Giới hạn đã biết

- Nhánh brownfield của installer: khung + merge semantics đã cố định; heuristics
  chi tiết tiếp tục tích lũy qua các lần adopt (xem Heuristics trong
  `skills/workflow/pilothos-init/brownfield.md`).
- Re-init/upgrade: chưa hỗ trợ — detect nhận diện và dừng có ghi nhận.
- Unattended install (không tương tác): chưa hỗ trợ.
- Việc nhận diện ĐÚNG nội dung đáng ghi log thuộc judgment của model; gate chỉ
  đảm bảo câu hỏi luôn được đặt ra.

## Trạng thái phân phối

- `rot/review-log.md`, `memory/lessons-learned.md`, Persona/Mục tiêu trong
  `CLAUDE.md`, Owner/dates trong `rot/registry.md` ship ở trạng thái trống hoặc
  placeholder có chủ đích — `/pilothos-init` điền cho từng implementation.
