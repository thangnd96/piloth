# Manifest Spec — Backup & Uninstall Contract

> Dùng bởi Stage 3 Apply của `/pilothos-init` và bởi `/pilothos-uninstall`.

## Vị trí

```text
pilothOS/.backup/<ISO-timestamp>/
├── manifest.json
├── install-plan.json   ← plan đã được approve và thực thi (engine tự archive)
└── <bản sao nguyên trạng của mọi file bị sửa, giữ nguyên cấu trúc đường dẫn>
```

`pilothOS/.backup/` PHẢI nằm trong `.gitignore` (Apply tự đảm bảo).

## Format manifest.json

```json
{
  "pilothos_version": "<version hiện hành>",
  "timestamp": "<ISO-8601>",
  "mode": "greenfield | brownfield",
  "created": ["<đường dẫn file được TẠO MỚI — uninstall sẽ XÓA>"],
  "removed": [
    { "path": "<file/dir bị XÓA (remove_path) — uninstall sẽ PHỤC HỒI>", "backup": "<bản sao trong .backup>" }
  ],
  "modified": [
    { "path": "<file bị SỬA>", "backup": "<đường dẫn bản sao trong .backup — uninstall sẽ PHỤC HỒI>" }
  ],
  "notes": "<quyết định merge quan trọng, vd: statusLine chọn phương án chain>"
}
```

## Bất biến

1. Backup + manifest được ghi **TRƯỚC** mọi thay đổi (không tồn tại trạng thái
   "đã sửa mà chưa backup").
2. Manifest là append-only theo nghĩa: mỗi lần init tạo thư mục timestamp MỚI,
   không sửa manifest cũ.
3. Uninstall dùng manifest MỚI NHẤT; phục hồi xong không xóa backup (giữ làm chứng cứ),
   chỉ báo cho consumer tự dọn nếu muốn.

## Uninstall protocol (cho /pilothos-uninstall)

1. Tìm manifest mới nhất trong `pilothOS/.backup/*/manifest.json`. Không có → báo
   "chưa từng init bằng installer, không có gì để phục hồi an toàn" và DỪNG.
2. Trình bày plan: các file sẽ XÓA (created) + các file sẽ PHỤC HỒI (modified).
   **CHỜ APPROVE** — đây là thao tác destructive, Governance yêu cầu human approval.
3. Thực hiện: phục hồi modified từ backup → xóa created → xóa `pilothOS/.initialized`.
4. Hỏi consumer có muốn xóa luôn cây `pilothOS/` không (mặc định: GIỮ — xóa cây
   là quyết định riêng, phải hỏi tường minh).
5. In xác nhận những gì đã làm. Không cần append log — log có thể đã bị gỡ theo;
   nếu cây pilothOS/ được giữ, append một dòng uninstall vào review-log.
