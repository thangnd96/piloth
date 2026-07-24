# Validation

Tài liệu này mô tả những gì bản phân phối hiện tại đã được kiểm chứng, và các
giới hạn đã biết. Lịch sử thay đổi theo version: xem `CHANGELOG.md` ở root.

## Đã kiểm chứng qua vận hành

- **Rot detection**: phát hiện scope quá hạn được enforce bằng hook (inject cảnh
  báo vào context) và statusline (chỉ báo 🔴 cho người dùng); im lặng khi healthy.
- **Deliver gate**: phiên có thay đổi file phải có auto-log đã được cân nhắc và
  deliver receipt đủ `changed_files`, `affected_layers`, `verification_command`,
  `result`; nếu không verify được thì receipt phải có `limitation`.
- **Pre/Post edit mechanical gate**: `pre-edit` enforce task contract
  (`task_scope`, `affected_layers`, `allowed_paths`, `expected_evidence`,
  `out_of_scope_paths`), chặn sửa ngoài allowed paths và một số vi phạm layer
  cơ học. `post-edit` chỉ ghi diff facts, không judge đúng/sai.
- **Judgment checklist gate**: với thay đổi judgment-sensitive, hook chỉ kiểm
  checklist/evidence đã được trả lời; nội dung đúng/sai vẫn thuộc model/người.
- **Installer plan/apply**: thứ được approve là `install-plan.json`, engine
  thực thi đúng file đó (byte-identical) — loại bỏ cấu trúc khe hở "approve một
  đằng, apply một nẻo"; simulate toàn bộ trước khi chạm đĩa; auto-rollback.
- **Installer transactional**: `/pilothos-init` backup + manifest TRƯỚC mọi thay
  đổi; `/pilothos-uninstall` phục hồi nguyên trạng từ manifest; re-init/upgrade
  dùng `mode=upgrade`; approve có cấu trúc, điều chỉnh kèm approve không bị bỏ sót.
- **Unattended install**: engine có command `unattended` để sinh plan deterministic
  từ tham số explicit rồi chạy cùng validate/apply path.
- **Ghi log máy móc**: `log-append` tự điền ngày, chống vỡ bảng, từ chối Evidence
  path không tồn tại.
- **Self-hosting**: `self-host-check` verifies dogfood docs, required test
  runners, manifest entries, V1 guard mode coverage and receipt evidence for
  changed Piloth source when git status is available.
- **Asset discovery**: `asset-scan`, `asset-health`, `asset-sync` generate and
  preserve consumer/Piloth asset registry data with health statuses
  `healthy | missing | stale | needs_approval | failed | unknown`, plus
  deterministic `detected_signals` and Piloth-owned `manifest_status`. Discovery
  covers well-known assets and dynamic agent skill/command/script/test-runner
  locations.
- **Semantic/DS evidence**: `reuse-scan` and `ds-scan` produce deterministic
  candidates. Guards block only when high-confidence candidates exist in receipt
  evidence but no explicit review decision is recorded. `reuse-scan` also emits
  learning suggestions for high-confidence and repeated duplicate candidates
  based on local scheduler history. Receipts that declare
  `quality_gates.reuse_non_duplication.result` as `FAIL` cannot also mark the
  delivery as successful without a documented limitation.
- **Project-local OS controls**: `os-start`, `os-status`, `os-evidence`,
  `os-close` and `os-verify` provide the canonical task lifecycle. The control
  plane remains the repo containing `pilothOS/`, while a run can control an
  explicit target repo through absolute `target_repo` and target-relative
  `target_paths`. `os-start` writes repo-local run state, an active task
  contract, asset routing, scheduler suggestions and `target-snapshot.json`.
  Git targets record dirty status; non-git targets record a deterministic file
  manifest/hash snapshot. `os-evidence` appends sanitized evidence without full
  command output or secrets and supports structured `command`, `figma_node`,
  `design_token_coverage`, `quality_gate`, `artifact`, `limitation` and
  `metric` entries. Explicit controlled targets default to
  `target_footprint_policy=no_control_plane_files`; `os-close` rejects
  consumer targets that contain or change Piloth/control-plane directories such
  as `pilothOS/`, `.claude/`, `.codex/`, `.cursor/` or `.antigravity/`.
  `os-close` validates the receipt against the target, required quality gates,
  expected evidence, UI quality evidence, truth-in-seal claims,
  control-plane/target janitors, recorded receipt seal, `target-diff.json`,
  `target-seal.json` and active control-plane check. `os-verify` fails when the
  active receipt, control-plane seal, target changed paths or target file hashes
  no longer match the sealed OS run.
  `tool-check` and receipt `tool_uses[]` validate
  declared entitlements against active contract `allowed_entitlements`.
  `receipt-seal` emits deterministic SHA-256 evidence over the active receipt,
  contract, diff facts and changed files. `receipt-verify` fails when the active
  receipt or changed file contents no longer match a prior seal.
  `control-plane-check` verifies the project-local OS surface: manifest,
  registered guard modes, asset registry, active task contract, evidence capture,
  quality gates, active receipt, recorded seal, artifact janitor and state health.
  In active mode, dirty git file paths must also be present in both post-edit
  facts and the active receipt so a delivery cannot silently ignore modified,
  deleted or untracked files. Dirty active delivery also requires a closed,
  sealed OS run.
  Active receipt seals treat deleted files as an explicit `missing` state so
  cleanup/deprecation work can be sealed instead of blocked as noise.
- **Truth-in-seal**: OS receipts require `claims[]`, each mapped to
  `evidence_refs[]`. Unqualified absolute claims such as `1:1`,
  `pixel-perfect`, `production-ready`, `fully verified`, `no issues`, `full`,
  `complete`, `all tokens` or `entire library` are rejected when evidence
  contains limitations, skipped/blocked checks, failed pixel diffs, missing
  fonts, failed gates or non-zero blockers. For `evidence_profile=design_tokens`,
  full design-token claims additionally require `design_token_coverage` evidence
  with `coverage_scope=full_declared_source`, source refs and generated surface
  coverage. Claims that Piloth is cheaper or saves tokens require real
  `llm_usage` telemetry with `real_token_telemetry=true`; artifact-size
  estimates are not accepted as token cost evidence. Qualified limitation claims
  are accepted.
- **Artifact janitor**: `artifact-janitor` runs read-only by default and detects
  deterministic local build/test/editor artifacts such as `.DS_Store`,
  `__pycache__`, cache directories, reports and coverage output. `--fix` removes
  only those known local artifacts and never rewrites consumer source files.
- **Scheduler**: `scheduler-suggest` recommends context/assets/evidence/test
  suites from affected paths and local history; corrupt/missing scheduler state
  falls back to deterministic routing. Valid same-repo successful history can
  add prior evidence commands, asset types and risk notes. Deprecated host-level
  history is ignored so removed control-plane experiments do not steer future
  project-local OS work. `scheduler-record` appends sanitized repo-local history
  only, infers missing task signals from asset routing and does not preserve
  deprecated cleanup paths in new learning summaries.
- **State doctor**: `state-doctor` checks repo-local scheduler history, OS run
  state, receipt seal JSONL shape, receipt seal chain continuity and confirms
  generated runtime state is excluded from the distribution manifest.
- **Production review**: `production-review` runs a mechanical release-readiness
  check over self-hosting, manifest coverage, detected asset health, removed
  deprecated host-level artifacts, artifact janitor, control-plane infrastructure,
  state-doctor and release-noise markers.
  Tool-control treats exact local read-only guard review commands as low-risk
  evidence while preserving high-risk handling for deploy/delete commands,
  production/deploy env context and composite shell command strings.
- **Team control plane**: `team-contract-write`, role-aware `pre-edit`, and
  `team-receipt-write` enforce team definition, role permissions, allowed paths,
  handoff artifacts, QA verdicts and repair loop limits. Team receipts generate
  repo-local role, QA, handoff and lead-decision artifacts under
  `pilothOS/memory/state/team-runs/<task-id>/`.

## Giới hạn đã biết

- Nhánh brownfield của installer: khung + merge semantics đã cố định; heuristics
  chi tiết tiếp tục tích lũy qua các lần adopt (xem Heuristics trong
  `skills/workflow/pilothos-init/brownfield.md`).
- Việc nhận diện ĐÚNG nội dung đáng ghi log thuộc judgment của model; gate chỉ
  đảm bảo câu hỏi luôn được đặt ra.
- Codex/Cursor/Antigravity không có cùng native hook surface như Claude Code;
  mức enforcement tương đương phụ thuộc việc adapter/harness gọi cùng guard CLI
  (`contract-write`, `pre-edit`, `post-edit`, `receipt-write`, `stop-check`).
- Semantic reuse and design-system scans are evidence-assisted. They do not
  decide semantic correctness; they only require the receipt to record a decision
  for generated high-confidence candidates.
- Scheduler learning is local JSONL memory, not telemetry. Missing/corrupt state
  is non-blocking and falls back to deterministic routing.
- Team contracts enforce shape and mechanical path/role boundaries only; quality
  of role reasoning remains a model/user judgment.
- OS seals and target seals are local delivery evidence only. They are not
  cryptographic code signing, notarization, host sandboxing, OS permissions,
  TCC/SIP enforcement or proof that code is production-ready beyond the recorded
  local evidence.
- `ui_quality` evidence proves only the recorded browser/visual checks. A
  skipped pixel diff must be disclosed and cannot support `1:1` or
  `pixel-perfect` claims.
- Exact token totals are unavailable unless the adapter records real
  prompt/completion telemetry. Artifact bytes or rough token estimates are
  diagnostic only.

### Agent-OS parity (T0–T6) — preview limits

- **T0–T6 ở trạng thái PREVIEW/experimental**: chứng minh qua none-vs-had
  benchmark; không phải claim "stable OS". Enforcement advisory/partial theo thiết kế.
- **Execution broker (`broker-check`)** là enforcement THẬT chỉ trên harness có hook
  (Claude Code); **advisory** trên Codex/Cursor/Antigravity tới khi adapter route
  tool-call qua guard. Broker cưỡng chế tại **biên tool-call**, KHÔNG sandbox
  token-level của model; "ask" (high-risk) dựa vào native permission prompt của host.
  Catastrophic hard-deny phủ: fork bomb, `mkfs`, `dd`→block device, `rm -r`→
  protected/subst, redirect→block device, `find <protected> -delete`,
  `chmod/chown -R <protected>`, `shred` block-device/critical-file.
  **Giới hạn đã biết (chưa deny — high-risk, không phải system-catastrophic):**
  `mv <x> /dev/null`, `truncate` file hệ thống, command-substitution lồng nhiều
  lớp, fork-bomb đổi tên. deny-on-doubt phủ phần lớn wrapper/`sudo`/`$()`/backtick.
- **Capability/authority model** advisory/fail-soft khi `coverage=partial`; fail-closed
  cứng chỉ khi `coverage=full` (hiện `partial`).
- **Provenance** (per-file `sha256` + `manifest_digest`) là content-addressed,
  tamper-evident, reproducible — KHÔNG phải code signing / Sigstore / notarization;
  ký digest + channels stable/dev/nightly là bước CI tương lai.
- **Multi-tenant / principal attribution** là tương lai: `principal` hiện chỉ surface
  ở introspection (`os-inspect`), chưa gắn vào receipt/state.
- **Forge** chỉ scaffold + verify + trình authority-delta (READ-ONLY); activation
  (ghi file + thêm capability-manifest + cấp quyền) là bước human-approved, sealed —
  guard không tự kích hoạt (construction ≠ activation).

## Trạng thái phân phối

- `rot/review-log.md`, `memory/lessons-learned.md`, Persona/Mục tiêu trong
  `CLAUDE.md`, Owner/dates trong `rot/registry.md` ship ở trạng thái trống hoặc
  placeholder có chủ đích — `/pilothos-init` điền cho từng implementation.
