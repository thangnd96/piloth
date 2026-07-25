# Review Log

Append-only operational history. Không sửa hoặc xóa lịch sử đã ghi.

> File này ship TRỐNG có chủ đích: lịch sử review thuộc về từng implementation
> và được tích lũy qua vận hành thật. Mỗi lần review hoặc phát hiện Rot,
> append một dòng mới theo format dưới đây — không chỉnh sửa dòng cũ.

| Date | Scope | Findings | Action | Evidence | Reviewer |
|---|---|---|---|---|---|
| 2026-07-16 | Rules & Hooks | Promoted task contract, pre/post edit facts, deliver receipt, unattended/upgrade support | Implemented mechanical gates and lifecycle/install tests | tests/run_all.sh | Codex |
| 2026-07-16 | Tools/Runtime | Fixed stale re-init/pre-edit docs, session diff facts handoff, stage flag parsing, upgrade dry-run marker kind, adapter typo validation | Added install/lifecycle/docs regressions | tests/run_all.sh | Codex |
| 2026-07-25 | Codebase intelligence | Deep scout found generated-source ambiguity, unsafe source collapsing, stale trust, state symlink and RAM retention risks | Added provenance-aware canonicalization, streaming budgets, freshness/coverage contract, tests and full-parity roadmap | docs/codebase-memory-deep-scout.md | Codex |
| 2026-07-26 | Tools/Runtime | Dogfood release v1.12.0 phát hiện 2 bug: smoke test `test_guard_characterization` dispatch mọi mode CLI gồm 21 mode `mutates=True` vào OS run đang mở của repo thật (latent — run đã seal thì bị reject nên không ai thấy); `token-telemetry` phát số cumulative nhưng `cost_ledger_summary` cộng dồn nên chạy 2 lần là gấp đôi hóa đơn ($49,45 vs $12,09) | Route mode mutates sang bản copy sandbox + thêm regression test; ledger lấy snapshot mới nhất theo `window_start` và khai `superseded_token_snapshots` | tests/run_all.sh | Claude |

