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
