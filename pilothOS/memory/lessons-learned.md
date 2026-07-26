# Lessons Learned

Append-only. Mỗi lesson nên dẫn tới Rule, Knowledge hoặc Skill nếu có giá trị tái sử dụng.

> File này ship TRỐNG có chủ đích: lesson sinh ra từ incident thật của từng
> implementation. Khi một vấn đề lặp lại hoặc một bài học đáng giữ xuất hiện,
> append một dòng — và nếu lesson đủ giá trị, promote nó thành Rule/Knowledge/Skill
> rồi ghi đích đến vào cột Promoted To.
> Lesson có giá trị cho MỌI project (không riêng implementation này) → Promoted To
> ghi thêm `upstream`; vendor định kỳ gặt các dòng `upstream` về nuôi bản phân phối.

Write a lesson when an agent makes one of these mistakes:

- guessed without context;
- ignored an existing consumer skill/tool;
- duplicated a helper/component;
- bypassed the design system;
- called the wrong tool;
- exceeded scope;
- created abstraction without need;
- loaded too much context;
- skipped verification.

Promotion rule:

- policy → `rules/`;
- stable fact → `knowledge/`;
- reusable workflow → `skills/`;
- tool behavior → `tools/index.md`;
- lifecycle/routing issue → `runtime/`;
- quality criterion → `evaluation/`.

For code/UI/runtime/rules/adapter changes, deliver receipt must include
`learning_review` with the checked mistake class, the lesson decision
(`recorded`, `none`, `deferred`, `promoted`), the promotion target or
`not_applicable`, and the reason.

Consistency rule: if `mistake_checked` is `none`, `lesson_decision` must be
`none`. If `mistake_checked` names a real mistake, `lesson_decision` must be
`recorded`, `deferred` or `promoted`; it cannot be `none`.

Accepted `mistake_checked` values:

- `guessed_without_context`
- `ignored_asset` or `ignored_consumer_asset`
- `duplicated_helper` or `duplicated_component`
- `bypassed_ds` or `bypassed_design_system`
- `wrong_tool`
- `exceeded_scope`
- `unneeded_abstraction`
- `context_bloat`
- `skipped_verification`
- `none`

Accepted `promoted_to` values:

- `rules` / `rules/`
- `knowledge` / `knowledge/`
- `skills` / `skills/`
- `tools` / `tools/index.md`
- `runtime` / `runtime/`
- `evaluation` / `evaluation/`
- `not_applicable`

For cross-project lessons, append `upstream` to a real target, for example
`tools/index.md, upstream`. `log-append lesson` enforces the same vocabulary.

| Date | Context | Lesson | Promoted To |
|---|---|---|---|
| 2026-07-26 | Kiểm ai đọc một field trước khi cắt nó khỏi output | Grep `src/` + `pilothOS/**` là chưa đủ — `tests/` cũng là consumer. Tôi kết luận `skipped_assets[].reason` không ai đọc rồi xoá, E19 vỡ. Quét cả tests/ trước khi bỏ field. | not_applicable |
| 2026-07-26 | Vá một call site rồi tưởng xong | Sửa `tests/unit/run-tests.sh` cho hết `.pytest_cache` nhưng còn `tests/benchmark/codebase-memory/run-tests.sh` cũng gọi pytest — verify vẫn sinh artifact. Grep hết call site trước khi vá, và cho test **quét** thay vì hardcode danh sách đã biết. | not_applicable |
| 2026-07-26 | Doc tự khai một hợp đồng mà không ai enforce | Ba lỗ liên tiếp cùng dạng: file/doc khai một điều kiện (`ship TRỐNG`, 'field phải doc ở doc shipped', 'verify không được để lại artifact') nhưng không có gate nào kiểm. Khi đọc thấy một câu khai định kiểu 'X có chủ đích', hãy kiểm ngay xem có gate không. | not_applicable |

| 2026-07-26 | Xoá 19 verb bằng AST dead-code analysis tới fixpoint; evidence-add bị xếp vào nhóm 'đã bị os-evidence thay thế' | Công cụ báo evidence-add chết chỉ vì tôi đã gỡ nó khỏi GUARD_HANDLERS trước — mà handler registry chính là tập root của phép phân tích. Vòng lặp tự khẳng định. Thực tế nó là người ghi duy nhất của evidence_commands trên đường V1 (contract-write -> receipt-write), thứ os-evidence không thay được vì os-evidence đòi một OS run đang mở. Khi một công cụ xác nhận đúng thứ vừa giả định, kiểm xem đầu vào của công cụ có do chính giả định đó tạo ra không. | not_applicable |
| 2026-07-26 | Task về DRY: gộp 4 closure add_check giống hệt nhau vào một class dùng chung | Class tốn 25 dòng để xoá 8 dòng trùng lặp — net +21 dòng, đúng loại abstraction thừa mà Constitution cấm, làm ra bên trong chính task có mục đích cắt bề mặt. Đã hoàn tác. Ngưỡng đáng gộp là khi các bản sao ĐÃ trôi khỏi nhau (bảng layer lệch 7 vs 8 dòng) hoặc khi chi phí lặp là O(n) theo số case (32 case x 3 dòng), không phải khi chúng chỉ trông giống nhau. | not_applicable |
