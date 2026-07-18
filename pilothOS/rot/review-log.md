# Review Log

Append-only operational history. Không sửa hoặc xóa lịch sử đã ghi.

> File này ship TRỐNG có chủ đích: lịch sử review thuộc về từng implementation
> và được tích lũy qua vận hành thật. Mỗi lần review hoặc phát hiện Rot,
> append một dòng mới theo format dưới đây — không chỉnh sửa dòng cũ.

| Date | Scope | Findings | Action | Evidence | Reviewer |
|---|---|---|---|---|---|
| 2026-07-16 | Rules & Hooks | Promoted task contract, pre/post edit facts, deliver receipt, unattended/upgrade support | Implemented mechanical gates and lifecycle/install tests | tests/run_all.sh | Codex |
| 2026-07-16 | Tools/Runtime | Fixed stale re-init/pre-edit docs, session diff facts handoff, stage flag parsing, upgrade dry-run marker kind, adapter typo validation | Added install/lifecycle/docs regressions | tests/run_all.sh | Codex |
