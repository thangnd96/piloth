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
| 2026-07-26 | Runtime & tests | Hai lỗ quy trình: (1) `docs/` không nằm trong `dist-manifest` nên field consumer-facing doc ở đó là vô hình với consumer — đã tái diễn ngay trong cùng session với `superseded_token_snapshots`; (2) lệnh verify bắt buộc `tests/run_all.sh` tự sinh `.pytest_cache` mà artifact-janitor coi là artifact, làm thứ tự verify → control-plane-check không bao giờ xanh | Ratchet derive key runtime từ `cost_ledger_summary`+`budget_status` bind vào doc shipped (grandfather key cũ, allowlist chỉ co); redirect cache ra /tmp ở cả 2 call site pytest + test quét thay vì hardcode | tests/run_all.sh | Claude |
| 2026-07-26 | Installer | `rot/review-log.md` + `memory/lessons-learned.md` tự khai trong header là 'ship TRỐNG có chủ đích' nhưng ship `verbatim` kèm lịch sử vận hành của vendor; auto-log gate buộc append mỗi session nên payload consumer phình mãi và version không thể pin chúng | `stage.py` strip data row khi copy (`SHIP_EMPTY_LOGS` + `log_header_only`), repo vendor giữ lịch sử; manifest khai `ship_empty:true`; gate C10i kiểm cả hai chiều | tests/install/run-tests.sh | Claude |

