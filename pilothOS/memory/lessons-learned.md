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
| 2026-07-26 | Bật chiều ngược của một gate đã bị waive bằng lời giải thích trong docstring | Câu waive '15 internal mode vắng mặt hợp lệ khỏi doc' chính là chỗ 9 verb mồ côi sống sót: không ai gọi, không doc nào nhắc, nên không gate nào có thể nhận ra chúng chết. Một waiver dạng văn xuôi là vùng mù có kích thước bằng đúng số nó nêu. Khi phải waive, waive bằng danh sách có tên cụ thể và gate luôn chính danh sách đó — HARNESS_INVOKED_MODES giờ bị kiểm là phải thật sự xuất hiện trong settings payload. | not_applicable |
| 2026-07-26 | Gỡ adapter dựa trên audit nói cả ba là 'prose thuần, không exec surface' | Đọc file mới thấy cursor/*.mdc dùng alwaysApply:true — cơ chế nạp thật của Cursor, không phải prose. Audit đúng về codex/antigravity, sai về cursor. Vẫn gỡ theo quyết định của user, nhưng phải nói rõ thứ mất đi là khả năng Cursor tự nạp PilothOS, không chỉ một lời quảng cáo sai. Bài học: khi audit phân loại nhiều thứ vào cùng một nhóm, mở từng cái ra trước khi hành động theo nhãn nhóm. | not_applicable |
| 2026-07-27 | Đo Piloth trên hai project công việc thật thay vì chỉ trên chính nó | Tỷ lệ đầu tư đang ngược với tỷ lệ sử dụng: auto-log gate (một hook, một câu hỏi, chấp nhận một dòng) được dùng 81 lần; OS control plane (hệ con lớn nhất kernel, 9 gate + ~15 field có cấu trúc cho receipt) được gọi 1 lần và không hoàn tất lần nào. Người dùng không bỏ vì task khó — họ đã verify xong, test 36/36 xanh — họ bỏ ở bước viết receipt. Gate nhẹ sống sót khi gặp công việc thật; lifecycle nặng thì không. | not_applicable |
| 2026-07-27 | Kiểm đường upgrade chứ không chỉ đường cài mới trước khi phát hành breaking change | Fresh install xanh không nói gì về upgrade. File consumer-owned được giữ nguyên có chủ đích, nên mọi thứ Piloth NGỪNG ship mà consumer vẫn trỏ tới sẽ thành tham chiếu chết — và chỉ lộ ra ở install đã tồn tại, không bao giờ lộ ở repo vendor. Quy tắc: xoá file được ship kèm hook thì phải kèm đường prune cho install cũ, và phải test bằng cách dựng lại một install phiên bản cũ. | not_applicable |
| 2026-07-27 | Ba issue từ consumer đầu tiên, cả ba là lỗi tham chiếu chết sau đợt cắt lớn | CI xanh suốt vì nó chạy trên repo vendor nơi file vừa bị xoá vẫn còn trong git history và trên đĩa của install cũ; consumer cài MỚI mới thấy. Gate cho lớp này phải đọc dist-manifest.json chứ không đọc filesystem — đọc đĩa là đọc đúng điểm mù. Và gate phải hẹp: bản 'mọi backtick phải tồn tại' cho 43 hit với 37 nhiễu (state.json, contract.json là tên khái niệm); bản ba luật cho 9 hit, 9 thật. Gate ồn sẽ bị tắt. | not_applicable |
| 2026-07-27 | Viết op sửa lỗi rồi test nó bằng fixture dựng sẵn điều kiện nó cần | prune_dead_hooks chỉ chạy khi file đã mất; fixture của tôi không bao giờ tạo file đó, nên test xanh trong khi op không chạy được trên đường thật một lần nào. Test đơn vị của một hàm không thay được test của ĐƯỜNG mà hàm phục vụ — nhất là khi hàm có tiền điều kiện do một component khác (staging) tạo ra. Quy tắc: op sinh ra để sửa một kịch bản thì phải có một test dựng lại đúng kịch bản đó từ đầu, không phải dựng lại trạng thái giữa chừng của nó. | not_applicable |
| 2026-07-27 | Chọn 'giữ nguyên cả file' cho consumer-assets.md mà không đọc self-check trước | Trong một loạt bug chủ đề 'Piloth xoá nội dung của consumer', giữ nguyên là lựa chọn có vẻ an toàn nhất — và nó qua hết fixture tổng hợp. Nó chỉ vỡ khi dựng lại một install v1.11.0 THẬT: self-check đòi file mang từ vựng asset của bản hiện tại, nên bản đóng băng ở v1 làm self-check FAIL → apply rolled_back → không nâng cấp được nữa. Lỗi nặng hơn lỗi đang vá. Quy tắc: trước khi quyết định giữ nguyên một file, kiểm xem có gate nào KIỂM nội dung file đó không — nếu có thì file có hai chủ và lời giải đúng là merge theo đường biên, không phải chọn một chủ. | not_applicable |
