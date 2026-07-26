# Knowledge — Index

## Purpose

Lưu FACT: specification, documentation, standards và domain knowledge lâu dài.

## Responsibilities

- Cung cấp nguồn sự thật có thể trích dẫn.
- Đồng bộ tài liệu với implementation.

## Non-Responsibilities

- Không lưu task state hoặc context ngắn hạn.
- Không chứa policy bắt buộc nếu policy thuộc Rules.

## Contents

| Path | Scope |
|---|---|
| `architecture/` | Quyết định và mô tả kiến trúc |
| `domain/` | Thuật ngữ và fact nghiệp vụ |
| `standards/` | Standards được dự án chấp nhận |

Ba thư mục trên **chưa tồn tại trên đĩa** — tạo khi có fact đầu tiên cần ghi.
Bản trước ship mỗi thư mục kèm một README ba dòng lặp lại đúng ô mô tả ở bảng
này; một thư mục chỉ chứa lời giải thích về sự trống rỗng của nó thì bảng này
nói được rồi.

## Convention

Mỗi fact quan trọng phải có source hoặc Evidence. Documentation lệch implementation là Rot Signal.

## Review Checklist

- Documentation và implementation còn đồng bộ không?
- Fact quan trọng có source hoặc Evidence truy vết được không?
- Knowledge nào đã lỗi thời, trùng lặp hoặc mâu thuẫn?
- Nội dung nào đang là context tạm thời và nên chuyển về Memory?
