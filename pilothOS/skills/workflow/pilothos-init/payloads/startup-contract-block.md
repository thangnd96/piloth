# PilothOS Startup Contract

> Bản sao cho các tool không đọc bootstrap. Nguồn chuẩn: `pilothOS/bootstrap.md`
> — khi hai bản lệch nhau, bootstrap thắng.

1. Đọc `pilothOS/PilothOS.md` để giữ đúng kiến trúc và responsibility.
2. Kiểm tra bảng trạng thái `pilothOS/rot/registry.md`; scope quá hạn → nhắc trước khi làm.
3. Đọc `pilothOS/rules/index.md`, áp dụng Rule liên quan.
4. Đọc `pilothOS/runtime/index.md` để xác định lifecycle + success criteria.
5. Nạp thêm Memory/Knowledge/Skills/Agents/Tools/Governance/Evaluation chỉ khi task cần.

**Auto-log gate:** trước khi kết thúc phiên có thay đổi file, append log vào
`pilothOS/rot/review-log.md` hoặc `pilothOS/memory/lessons-learned.md`, hoặc nêu rõ
"Không có finding hoặc lesson cần ghi" kèm lý do. Gate này được Stop hook enforce.

---
