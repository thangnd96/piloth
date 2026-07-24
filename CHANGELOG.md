# Changelog

## Unreleased

## v1.12.0 — 2026-07-24 (preview / experimental)

### Agent-OS parity (T0–T6) — **preview / experimental**

Toward an inspectable, self-extending agent OS at parity with `unicity-aos/aos-ce`,
proven by none-vs-had consumer benchmarks. **Enforcement is advisory/partial by
design** (see `pilothOS/VALIDATION.md`) — this is a preview, not a stable-OS claim.

- **T0 Capability & Authority kernel** — `pilothOS/governance/capability-manifest.json`
  (fail-closed authority SSOT) + guard modes `capability-list` / `capability-check`
  / `authority-delta`; wired advisory into `self-check` + `control-plane-check`.
- **T1 Execution Broker / Airlock** (`broker-check`, PreToolUse:Bash) — unconditional
  hard-deny of catastrophic commands (fork bomb, `mkfs`, `dd`→block device,
  `rm`→protected root, redirect→device), with recursion into wrapper argv
  (sudo/env/xargs/nice/…), shell `-c`/`eval` payloads and `$()`/backtick
  substitution (deny-on-doubt). High-risk → ask (host prompt).
- **T2 Unified Introspection** (`os-inspect`) — one legible system-status report
  (version, capability/authority map, guard-mode surface, rot, health).
- **T3 Piloth Forge** (`forge-scaffold` / `forge-verify` / `forge-plan` + skill
  `piloth-forge` + templates) — governed self-extension: scaffold + verify +
  present authority-delta; construction ≠ activation (never self-grants).
- **T4 Supply-chain provenance** (`provenance`, `provenance --files`) — content-
  addressed dist-manifest: per-file `sha256` + reproducible `manifest_digest` +
  `source_commit`.
- **T5 Composability** (`skill-index`) — workspace-wins skill precedence (consumer
  override without forking) + `principal` (caller identity from context).
- **T6 Upgrade self-heal** (`upgrade-verify`) — verifies an upgrade preserved
  customization/state + kernel integrity; gated by `tests/install`.
- **Hardening** — audit-driven (3 independent audits + adversarial fuzz). Fixed a
  CRITICAL broker wrapper/substitution bypass; the none-vs-had `tests/benchmark`
  and `tests/install` upgrade suites now run in CI (were previously dark).
- New runtime docs: `capability-model`, `execution-broker`, `os-services`,
  `supply-chain`, `composability`.

## v1.11.0 — 2026-07-23

Update path first-class + drift-warning (vá thiếu sót "update plugin rồi thì bản đã init nâng cấp thế nào").

- **`/piloth:update` (skill `pilothos-update`)**: command first-class nâng bản PilothOS
  đã init lên version plugin hiện tại — re-stage kernel/adapter (`stage.sh --upgrade`,
  có backup) rồi đóng dấu version qua engine (`mode=upgrade` + `write_marker`). GIỮ nguyên
  `CLAUDE.md`/`AGENTS.md`/`.gitignore`/`.claude/settings.json` + state (rot registry,
  review-log, lessons-learned). SSOT của upgrade flow — section "Re-init/Upgrade" của
  `pilothos-init` rút thành pointer. Bridge `/pilothos-update` cho project đã cài. Đổi
  adapter vẫn dùng `/piloth:adapter`.
- **Drift-warning ở session-start** (fail-soft, advisory): guard so `pilothos_version`
  trong `pilothOS/.initialized` với version plugin ở `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`;
  plugin mới hơn → nhắc chạy `/piloth:update` (không chặn task). Thiếu marker / thiếu
  `CLAUDE_PLUGIN_ROOT` / parse lỗi → im lặng. **Forward-looking**: chỉ kích hoạt cho
  consumer đã ở version CÓ nó (v1.11.0+) — lần nhảy từ v1.10.0 chưa thấy vì guard cũ chưa có.
- **Fix release tooling**: `bump-version.sh` audit thêm exclude `pilothOS/memory/state/`
  (runtime state gitignored) — trước đây os-run state của release trước (chứa version cũ)
  làm audit false-positive mỗi lần bump.
- Tests: `tests/unit/test_guard_version_drift.py` (advisory fail-soft: newer→warn,
  equal/older/missing→silent). Docs: README `## Updating`, structure, workflow, skills/index.

## v1.10.0 — 2026-07-23

Init ergonomics từ consumer feedback (adapter selection, add-adapter, plan-write, gitignore).

- **Adapter selection giờ được enforce (fix "chọn claude+codex vẫn cài đủ 4")**:
  plan interactive khai báo field `adapters` (list adapter giữ lại, gồm `claude`);
  engine `normalize_plan` tự sinh `remove_path` cho adapter KHÔNG chọn ở dry-run
  (không còn phụ thuộc Claude gõ tay). Greenfield/brownfield BẮT BUỘC khai báo
  `adapters` khi có optional adapter đã staging.
- **`/piloth:adapter` (skill `pilothos-adapter`)**: thêm/bớt adapter SAU init mà
  không cần re-init. ADD dùng `stage.sh --add-adapters <names>` (targeted — chỉ
  copy adapter thiếu, không đụng kernel); REMOVE qua engine `remove_path` (có backup).
- **Guard không còn chặn Claude ghi plan file khi harness không truyền
  `permission_mode`**: `pre-edit` cho ghi khi mọi target nằm trong `~/.claude/plans/`
  (hoặc `$CLAUDE_CONFIG_DIR/plans/`) — plan file là artifact harness, không phải
  code repo. Safety-net bổ trợ cho exemption plan-mode.
- **`.gitignore` runtime rules nhất quán + opt-in `all`**: SSOT `PILOTHOS_GITIGNORE_LINES`;
  `normalize_plan` chèn `append_lines` cho `.gitignore` (idempotent) ở MỌI nhánh —
  vá gap greenfield-có-sẵn-.gitignore và brownfield-append-thiếu-dòng. `pilothOS/`
  vẫn commit theo thiết kế; `options.gitignore_scope="all"` (elicit/`--gitignore-scope all`)
  cho consumer chọn ignore toàn bộ `pilothOS/`.
- Tests: `test_installer_safety.py` (adapter_set, normalize_plan, gitignore, adapters
  required); `test_guard_plan_mode.py` (harness plan-path allow); install C10f/C10g/C10h;
  lifecycle/install fixtures khai báo `adapters`.

Lifecycle ergonomics + taxonomy hardening (từ dogfood build landing page).

- **`os-close --dry-run`**: chạy TOÀN BỘ validator của os-close (quality gates,
  truth-in-seal, expected-evidence, footprint, janitor — không chỉ validator lõi)
  và trả `{would_pass, errors}` mà KHÔNG mutate state / seal / ghi `target-diff.json`.
  Lặp tới khi `would_pass:true` rồi close thật.
- **`receipt-template` gate-aware**: chỉ in field mà run này thực sự cần (docs-only
  bỏ field UI), enum điền sẵn giá trị hợp lệ (không còn `<placeholder>`); allowed
  values gom trong `_allowed_values`.
- **`os-start --explain`**: in schema request (field/required/default/allowed/alias)
  — SSOT dạng máy, mirror `installer explain`.
- **`energy_budget_reason` passthrough**: `build_os_contract` giờ nhận field này từ
  request (trước đây gate full-suite đòi nó nhưng os-start không có cách cấp) — cũng
  liệt kê trong `os-start --explain`.
- **`browser_smoke`** thêm vào `METRIC_TYPES` (loại evidence UI tự nhiên).
- **Gộp vocab decision**: `SEMANTIC_REVIEW_DECISIONS` alias `UI_DESIGN_SYSTEM_DECISIONS`
  (một nguồn, chống drift); `ASSET_ROUTING_DECISIONS` giữ riêng (khác ngữ nghĩa).
- **Error message rõ hơn**: `learning_review.promoted_to` liệt kê target hợp lệ +
  cú pháp `<target>, upstream`; `lesson_decision` derive từ constant.
- **Cross-project advisory** (không chặn): `os-close` phát `enforcement_advisory` khi
  diff-facts rỗng nhưng target-diff có thay đổi (target hook không fire khi drive từ
  session khác) — seal vẫn dựa trên git/manifest target-diff.
- Tests: `tests/unit/test_guard_taxonomy.py`; lc7 mở rộng (dry-run + gate-aware
  template). Docs: os-control-plane, task-lifecycle.

State retention / janitor — dọn rác vòng đời task (Nhóm A đĩa + Nhóm B token).

- **`state-janitor`** (detect mặc định, `--fix`): dọn `os-runs/<task>/artifacts/` của
  run đã seal ngoài retention (giữ state/seal JSON), tail-truncate scheduler-history;
  `receipt-seals.jsonl` (hash-chain) chỉ WARN. `--kernel-logs` rotate lossless
  `lessons-learned.md`/`review-log.md` sang `*-archive.md` (không load context).
  `os-close` tự chạy safe subset sau seal (fail-soft). `state-doctor` thêm advisory bloat.
- Tests: `tests/unit/test_guard_state_janitor.py`. Docs: token-optimization,
  energy-token-policy, os-control-plane, memory/state/README.

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

Real token telemetry (`token-telemetry`) + advisory budget — unlocks cost claims.

- **`token-telemetry` guard mode**: reads real per-turn `message.usage` from the
  Claude Code session transcript (`~/.claude/projects/<slug>/<session>.jsonl`),
  windowed to the OS run's `created_at`, prices it via `runtime/model-pricing.json`
  (input/output + cache-write ~1.25× / cache-read ~0.1×), and records
  `os-evidence kind=metric metric_type=llm_usage real_token_telemetry=true`
  (`cost_usd`, `model`, `window_start`, `subagent_scope=main_session_only`).
  Fail-soft: no transcript → `real_token_telemetry=false` + `unavailable_reason`.
  This is what unblocks `os-close` cost/token claims (superiority still needs a
  benchmark).
- **Price map** `pilothOS/runtime/model-pricing.json` (advisory, `as_of` dated;
  helpers `load_model_pricing`/`model_price`/`compute_token_cost_usd`).
- **Metric schema extended**: `cache_creation_input_tokens`,
  `cache_read_input_tokens`, `cost_usd`, `model` (+ `pricing_source`,
  `window_start`, `subagent_scope`) on `llm_usage`; `cost_ledger_summary` surfaces
  cache tokens + total `cost_usd`.
- **Advisory budget**: optional contract `budget.max_usd` → `budget_status`
  (`spent_usd`/`remaining_usd`/`over_budget`) in `os-status`/`os-report`; **never
  blocks `os-close`**.
- Tests: `tests/unit/test_guard_token_telemetry.py` (pricing/cost, cost ledger,
  metric schema, transcript parse/window) + `tests/unit/test_guard_budget.py`.

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
