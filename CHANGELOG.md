# Changelog

## Unreleased

Governed Visual Review — human-in-the-loop review + agent loop + hook bridge.

- **Piloth Review** (`pilothOS/tools/review/`): companion tool tái hiện annotron 1:1
  (Node built-ins, zero runtime dependency) — point-and-click annotation trên artifact
  MD/HTML, agent loop poll/reply/finalized, live activity mirror (SSE), remote
  permission gate (fail-open). Chạy độc lập được, disk sạch (SDK inject lúc serve).
- **Gate `human_review`** trong guard: 3 mode `review-request`/`review-feedback`/
  `review-verify`; structured feedback (verdict + findings gắn gate/severity/
  disposition) thành evidence `kind=human_review`; `os-close` enforce — task cần human
  review không Seal khi thiếu artifact `approve`+`finalized` hoặc còn blocker/major chưa
  xử lý; blocker/major route về Repair. Receipt tự khai `PASS` mà thiếu artifact backing
  bị reject (chống honor-system).
- **Governance bridge** (opt-in, fail-soft): companion tool khi bind `--task`/`--govern`
  forward feedback → `review-feedback` và quyết định permission → `os-evidence`; không
  bind → core chạy 1:1 standalone.
- Tests: `tests/lifecycle/cases/lc10-human-review-roundtrip.sh` (full os-close
  enforcement) + `tests/unit/test_guard_human_review.py`.
- Docs: quality-gates, task-lifecycle, os-control-plane, operational-controls.
- **Review hooks default-on**: bản cài bật sẵn activity mirror + permission gate
  của review tool (fail-open); tắt bằng `PILOTH_REVIEW=off` trong `.claude/settings.json`.
- **Plan-mode exemption**: `pre-edit` bỏ qua enforcement khi `permission_mode=plan`
  (fix Piloth chặn Claude ghi plan trong plan mode); governance enforce lại khi thực thi.
  Test: `tests/unit/test_guard_plan_mode.py`.

Prototype phase + Discovery gate + pipeline stepper + recipe suggestions
(reimplement 1:1 DNA của aidlc, build native cho Piloth trên hạ tầng review).

- **Prototype phase** (skill `piloth-prototype` + persona `agents/team-roles/designer.md`):
  sinh ≥2 UI options (Claude Artifacts/Figma/design-system/shadcn/lo-fi), human chọn
  **tái dùng** `human_review` round-trip. `requires_prototype` tự bật
  `requires_human_review`; gate `prototype` (mỏng) kiểm invariant qua
  `os-evidence kind=prototype` (method hợp lệ, ≥2 options, `chosen` ∈ options);
  thiếu → route Repair; receipt tự khai `PASS` mà thiếu evidence bị reject.
- **Discovery gate** (skill `piloth-discovery`): hỏi-xác nhận câu hỏi mở đầu phase qua
  Governed Visual Review (`## Q<n>` + `[x] Decide for me` default), ghi
  `os-evidence kind=discovery` + fold vào contract `discovery_decisions` (Traceability
  trace tới). Là gate judgment, không hook tự trigger; `DISCOVERY.md` là working doc.
- **Pipeline stepper + option-picker** trong review chrome (Piloth-layer, fail-soft):
  route `/pipeline` đọc `os-status` qua `govern.js`; stepper hiện phase/gate + hint
  `phase_plan_suggestion`; option-picker cho `PROTOTYPE-option*.html`. Ungoverned →
  ẩn, core 1:1 annotron không đổi.
- **Recipe suggest-only + model-hints** (advisory): `suggest_phase_plan` khuyến nghị
  discovery/prototype theo signal/scope (**không auto-enable**); `model_hints` gợi ý
  model per-phase; cả hai surface ở `os-status`/`os-report`. Budget ceiling hoãn tới
  khi có `real_token_telemetry`.
- Tests: `tests/unit/test_guard_{prototype_gate,discovery,recipe}.py` +
  `tests/lifecycle/cases/lc11-prototype-roundtrip.sh`.
- Docs: quality-gates, task-lifecycle, os-control-plane, energy-token-policy, skills/index.

## 1.9.0

Reproducibility, safety net và token optimization.

- Release gate reproducible: `run_all.sh` thêm meta-guard abort to tiếng khi một
  suite khai báo thiếu `run-tests.sh` trên clean clone; track các suite
  `evaluation`/`docs`/`benchmark` + lifecycle case `lc6–lc9` vốn còn untracked.
- CI: GitHub Actions chạy full gate (Python 3.9/3.11/3.13) + `self-host-check`
  + `production-review` + `pytest` trên mỗi push/PR.
- Unit safety net: `tests/unit/` pytest cho các hàm quyết định của guard/installer
  (`validate_deliver_receipt`, routing, reuse, context-budget, `safe_rel`
  path-traversal, `check_target_writable_zone`, `merge_settings_content`,
  `choose_adaptive_mode`) — 59 unit test, lần đầu guard có coverage đơn vị.
- Dispatch table: `main()` thay ~45 nhánh `if/elif` bằng `COMMAND_TABLE`;
  `guard_registered_modes()` derive từ table thay vì regex-parse source (fix một
  class regression control-plane-check bắt được bởi benchmark).
- Giảm code: bỏ 4 hàm chết trong `pilothos_guard.py` (−28 dòng), hành vi giữ nguyên.
- **Token optimization**:
  - `context-budget` đo footprint context (bytes/token) routing nạp vs full kernel
    (~88–91% nhỏ hơn); nhãn `context_load`, không phải `llm_usage` telemetry.
  - Mode-aware context: `route-task`/`context-budget` nhận `mode`. `lean` bỏ
    gate/asset docs + lazy rot (`rot-status` thay cả bảng registry); `micro` bỏ
    thêm Constitution. standard→lean −27–40%, micro −43–54%.
  - Blast-radius-aware mode: `choose_adaptive_mode` tự chọn `lean` cho task ≤3 file
    cụ thể (không cần khai). Guide: `docs/token-optimization.md`.
- `real_token_telemetry` verified: os-evidence `llm_usage` (cần `metric_name` +
  `real_token_telemetry:true`) mở khóa cost claim ở os-close; thiếu → claim
  "rẻ hơn" bị từ chối.
- Init greenfield end-to-end verify `SELF-CHECK PASSED`.

Đã hoãn có chủ đích:
- Tách `pilothos_guard.py` thành package vật lý — rủi ro regression cao so với lợi
  ích; dispatch table đã lấy phần lớn lợi ích maintainability.
- Condense kernel docs (`agent-core` vs `extended`) — ROI thấp hơn, rủi ro cắt lố.
- Nguồn token telemetry thật phụ thuộc adapter harness expose prompt/completion.

## 1.8.3
- Harden staging for release: replace Bash process substitution with deterministic Python-backed staging and keep `stage.sh` as a thin stable wrapper.
- Add `pilothOS/dist-manifest.json` to the version-bump contract so the fifth version location is updated by process, not luck.
- Ship-clean audit: lifecycle tests must pass from a fresh unzip and the package must contain no cache, backup, init marker, pending plan, or stale generated artifacts.
- Harden test runners with process-group timeouts so timed-out cases cannot leave orphaned grandchildren holding deleted workspaces or pipes.

## 1.8.2
- Test: thêm lifecycle E2E suite (apply+receipt+marker, completeness từ engine thật, crash rollback, self-prune+uninstall round-trip, guard regression) — mỗi case một workspace riêng, output ra file, hard timeout; hang trở thành FAIL to tiếng.
- Test: C10d quay về assert bằng receipt thật của engine (`completeness_missing`), bỏ logic đọc manifest tĩnh trùng lặp.
- Guard (thay đổi engine-adjacent, gọi tên riêng): `read_hook_input` thêm `select` 0.5s — hook modes không còn block vô hạn khi stdin là pipe non-interactive không dữ liệu; docstring hết overclaim.
- Release tooling: `bump-version.sh` tự regenerate `pilothOS/dist-manifest.json` sau khi bump (vị trí version thứ 5 vào quy trình, hết phụ thuộc may mắn của audit).
- Runner tổng: per-suite timeout + timing.

## 1.8.1
- Sửa release-readiness findings: test runner báo cáo theo suite rõ ràng, engine/install suite có timeout cục bộ để tránh hang im lặng.
- Sửa wording README và VALIDATION.md để phân biệt enforcement cơ học với judgment-based contracts; không overclaim hook chặn những việc chưa thể máy móc hóa.
- `dist-manifest.json` thêm `schema_version`, `piloth_version`, `generated_at` để phục vụ upgrade/debug sau này.
- Giữ model plugin/runtime của 1.8.0, không thêm feature speculative.

## 1.8.0
- Tái cấu trúc repo production-shape: kernel `pilothOS/` và `adapters/<tool>/` visible ở root, không còn `dist/`; mỗi tài liệu một bản (diệt duplicate-SSOT — đã bắt được drift thật ở settings.json).
- `stage.sh` duy nhất cho cả hai kênh (plugin + clone); settings staged từ payload (SSOT).
- Docs + LICENSE của PilothOS đi theo `pilothOS/` trong project — root project của consumer không còn bị chiếm chỗ; LICENSE không còn vô tình áp lên code consumer.
- Test suite sống trong repo: `tests/run_all.sh` (engine C1–C9, install C10, sync-templates guard).
- Version automation: `.version-bump.json` + `scripts/bump-version.sh` (audit chuỗi version sót).
- Kênh feedback: issue templates khớp cột review-log, chảy thẳng vào quy trình upstream.

## 1.7.0
- Sửa bug hoàn chỉnh (feedback consumer): bản cài giờ ĐẦY ĐỦ như bản phân phối — install.sh v2 staging theo toàn bộ cây (adapters, bridges, AGENTS.md, docs), file của consumer không bao giờ bị đè.
- `dist-manifest.json`: SSOT của "bản cài hoàn chỉnh", sinh tự động lúc đóng gói; engine kiểm completeness sau apply và báo trong receipt.
- Op mới `fill_placeholders`: cá nhân hóa in-place (CLAUDE.md, registry — registry tự tính Next Due theo cadence, bỏ bước sửa tay khỏi First-Boot).

## 1.6.1
- Self-prune mặc định: sau khi cài, installer tự dọn mặt tiền install (command init, docs nhánh, skill bridge) bằng chính các step `remove_path` trong plan — có backup, `uninstall` phục hồi cả bộ install để cài lại được. Engine + `/pilothos-uninstall` + payloads không bao giờ bị dọn.

## 1.6.0
- Installer chuyển sang mô hình **plan/apply**: Claude soạn `install-plan.json`, engine deterministic (`pilothos_installer.py`) validate → backup → thực thi → receipt; auto-rollback khi lỗi giữa chừng.
- Bộ ops đóng (6 ops, xem `installer explain`) — SSOT merge semantics chuyển vào engine.
- Chọn tool adapters lúc init (Claude/Cursor/Codex/Antigravity); adapter không chọn được gỡ có backup, uninstall phục hồi.
- Bootstrapper `install.sh`: một lệnh terminal dàn dựng file vào project.
- Hỗ trợ unattended: gọi thẳng engine với plan tự viết.
- Prune: gỡ `pilothOS/adapters/` (trùng vai với adapter thật ở root; checklist dời vào review-guide) và `templates/review.md` (trùng per-layer checklists).
- Thêm `LICENSE` (MIT).

## 1.5.1
- Tài liệu phân phối viết lại hướng consumer; lịch sử phát triển tách khỏi bản ship.
- `CLAUDE.md` và `rot/registry.md` ship dạng placeholder — `/pilothos-init` điền.
- Quy ước `upstream` cho lessons-learned: lesson generalize được đánh dấu để gặt về bản phân phối.
- Sửa chuỗi version cũ còn sót trong `AGENTS.md`.

## 1.5.0
- Thêm `payloads/`: nội dung chuẩn cho installer (settings, identity, startup contract).
- Approve/confirm của installer chuyển sang câu hỏi có cấu trúc; điều chỉnh kèm approve được echo và xác nhận trước Apply.
- Guard mode `log-append`: ghi log máy móc, verify Evidence path.
- Token Budget Contract cho installer.

## 1.4.0
- Installer `/pilothos-init` (một lệnh cho cả greenfield lẫn brownfield, detect + confirm).
- Backup + manifest transactional; `/pilothos-uninstall` phục hồi nguyên trạng.
- Preflight, First-Boot Checklist, merge semantics cố định cho hooks/permissions/env/statusLine.

## 1.3.0
- Auto-log gate (Stop hook): phiên có thay đổi file phải append log hoặc tuyên bố không có finding.
- Cảnh báo Rot tối ưu token: một lần mỗi phiên cho cùng trạng thái.

## 1.2.0
- Enforcement baseline: hooks (SessionStart/UserPromptSubmit), statusline, self-check, pre-action gate trong Identity.

## 1.1.x
- Multi-tool adapters (Claude Code, Codex, Cursor, Antigravity); team `piloth-team`; skill `piloth-team-setup`.

## 1.0.0
- Kiến trúc lõi 7 layer + cross-cutting (Governance, Evaluation); Rot Management; templates.
