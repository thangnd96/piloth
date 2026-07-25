#!/usr/bin/env python3
"""PilothOS guard: hook + statusline cho cơ chế enforcement.

Các mode:
  session-start   Ghi marker phiên + inject cảnh báo Rot vào context khi mở session (hook SessionStart).
  prompt-check    Inject cảnh báo Rot ở mỗi lượt message, CHỈ MỘT LẦN mỗi phiên cho cùng
                  một trạng thái overdue — tối ưu token (hook UserPromptSubmit).
  stop-check      Deliver gate: khi agent kết thúc lượt mà repo có thay đổi,
                  yêu cầu auto-log đã được cân nhắc và deliver receipt đủ evidence.
  statusline      Dòng trạng thái Rot cho status line; chỉ hiện khi có scope quá hạn.
  self-check      Kiểm tra settings.json + registry + log files; dùng sau mỗi lần sửa cấu hình.
  preflight       Preflight của /pilothos-init: kiểm môi trường (quyền ghi, settings hợp lệ,
                  cây pilothOS đầy đủ) — fail sớm và rõ ràng.
  detect          Stage 0 của /pilothos-init: verdict greenfield/brownfield/re-init/dirty
                  kèm evidence; KHÔNG tự rẽ nhánh, chờ consumer confirm.
  audit-assets    Scan deterministic tài sản consumer và in bảng brownfield audit.
  registry-assets Scan deterministic tài sản consumer và in bảng registry 9 cột.
  self-host-check Verifies the Piloth repo dogfood contract surface.
  asset-scan      Deterministic JSON/markdown scan of repo assets.
  asset-health    Read-only health checks for detected assets.
  asset-sync      Writes generated asset registry section between markers.
  evidence-route  Canonical read-only task/risk/evidence/specialist/team route.
                 Prints the acting digest; `--verbose` prints the full decision.
  adapter-capabilities Normalize native|emulated|unavailable adapter handshake.
  route-task      Scheduler helper: gợi ý context/consumer asset routing từ task_signal.
  context-budget  Đo context footprint (bytes/token) mà routing nạp vs full kernel.
  payload-budget  Đo footprint output (bytes/token) của các command một task gọi.
  codebase-index  Tạo local SQLite code graph theo budget explicit.
  codebase-status Báo freshness/coverage count của code graph hiện tại.
  codebase-query  Query overview/search/trace/snippet/coverage/impact qua JSON.
  rot-status      Rot signal gọn (chỉ scope quá hạn) — lazy load thay vì cả registry.
  reuse-scan      Evidence-shaped semantic reuse candidate scan.
  ds-scan         Evidence-shaped design-system candidate scan.
  scheduler-suggest Recommend context/assets/evidence/tests from local history.
  scheduler-record  Append sanitized local scheduler history.
  state-doctor   Read-only health check for repo-local OS state.
  os-start       Open an adaptive OS task run and write the scoped contract.
                 `os-start --explain` prints the request schema (no run opened).
  os-status      Show active OS task status, mode and cost ledger.
                 `os-status --verbose` prints the full router decision too.
  os-evidence    Append sanitized command/tool/metric evidence to an OS run.
  os-close       Validate receipt, gates, truth claims and target seal.
                 `os-close --dry-run` runs the full validation without sealing.
  os-verify      Verify active receipt/control-plane/target seals.
  os-report      Summarize mode decisions, cost ledger and consumer value status.
  receipt-seal   Emit deterministic receipt/contract/file hash seal evidence.
  receipt-verify Verify current receipt/files against a prior seal.
  artifact-janitor Detect or explicitly clean deterministic local artifacts.
  state-janitor  Retention/GC rác vòng đời task: dọn artifacts/ của os-run cũ đã
                 seal (giữ state/seal JSON), tail-truncate scheduler-history;
                 --kernel-logs rotate lossless lessons/review-log. Detect mặc
                 định, chỉ đổi đĩa khi --fix. Tự chạy (safe subset) ở os-close.
  control-plane-check Verify project-local OS control-plane readiness.
  production-review Mechanical release readiness review.
  team-contract-write Record a multi-agent team contract.
  team-receipt-write  Record a multi-agent team receipt.
  log-append      Ghi một dòng log đúng format (review|lesson), Date tự điền,
                  verify Evidence path tồn tại — dùng cho Stage 5 và mọi lần ghi log.
  contract-write  Ghi task contract vào state guard trước khi sửa file.
  evidence-add    Ghi evidence command/result vào diff facts.
  tool-check      Kiểm tra tool command/risk/timeout/approval trước khi chạy.
  receipt-write   Ghi deliver receipt có changed files/layers/evidence/result.
  pre-edit        PreToolUse: enforce allowed paths + một số layer/path rule cơ học.
  post-edit       PostToolUse: ghi diff facts, không judge đúng/sai.

Ghi chú thiết kế:
- Đường dẫn neo theo vị trí file này, không phụ thuộc cwd khi hook chạy.
- Hooks của Claude Code truyền JSON qua stdin (session_id, stop_hook_active...);
  script đọc an toàn, chạy tay không có stdin vẫn hoạt động (degraded, không lỗi).
- Marker phiên đặt tại /tmp/pilothos/ và tự dọn sau 48h.
- stop-check dùng cơ chế block đúng chuẩn Stop hook: xuất JSON
  {"decision": "block", "reason": ...}; stop_hook_active=true nghĩa là đã block
  một lần rồi → luôn cho dừng, không bao giờ tạo vòng lặp.
- Bài học đã promote (rules/hooks.md): MUST máy móc → hook; settings hỏng →
  self-check; verify tại đích. Auto-log gate là hiện thực hóa của Enforcement
  Ladder: điều kiện "có thay đổi mà log chưa động" là máy móc nên hook được;
  chất lượng nội dung log vẫn cần judgment của model.
"""
# GENERATED FILE — assembled from src/guard/*.py by scripts/build_bundles.py.
# Edit the fragments and rebuild; hand-edits here are overwritten and caught by
# the bundle-up-to-date gate in tests/unit.
import sys
import ast
import re
import json
import time
import os
import fnmatch
import hashlib
import datetime
import pathlib
import shlex
import sqlite3
import subprocess
import shutil

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PILOTHOS_DIR = SCRIPT_DIR.parent            # <repo>/pilothOS
REPO_ROOT = PILOTHOS_DIR.parent             # <repo>
REGISTRY = PILOTHOS_DIR / "rot" / "registry.md"
CONSUMER_ASSETS = PILOTHOS_DIR / "runtime" / "consumer-assets.md"
SELF_HOSTING_DOC = PILOTHOS_DIR / "runtime" / "self-hosting.md"
SCHEDULER_HISTORY = PILOTHOS_DIR / "memory" / "state" / "scheduler-history.jsonl"
EVIDENCE_ROUTER_MATRIX = PILOTHOS_DIR / "runtime" / "evidence-routing.json"
# Embedded fallback for the Evidence Router quality floor — the ONLY place these
# numbers are written down. evidence-routing.json overrides them at runtime and
# every threshold decision reads the merged result via
# evidence_router_quality_floor(); the thresholds used to be duplicated as
# literals across the routing decisions, so editing the JSON changed the reported
# floor without changing a single decision.
#   route_confidence          - floor for the confidence of the route itself
#   evidence_item_confidence  - floor for ONE evidence item before it drags the
#                               route confidence down (a different question from
#                               route_confidence; kept separate on purpose)
DEFAULT_QUALITY_FLOOR = {
    "max_non_inferiority_delta_pp": 2,
    "route_confidence": 0.80,
    "evidence_item_confidence": 0.80,
    "specialist_score": 70,
    "team_score": 60,
}
ADAPTER_CAPABILITY_REGISTRY = PILOTHOS_DIR / "runtime" / "adapter-capabilities.json"
SPECIALIST_REGISTRY = PILOTHOS_DIR / "runtime" / "specialist-registry.json"
MODEL_CAPABILITY_REGISTRY = PILOTHOS_DIR / "runtime" / "model-capabilities.json"
RECEIPT_SEALS = PILOTHOS_DIR / "memory" / "state" / "receipt-seals.jsonl"
TEAM_RUNS_DIR = PILOTHOS_DIR / "memory" / "state" / "team-runs"
OS_RUNS_DIR = PILOTHOS_DIR / "memory" / "state" / "os-runs"
OS_CURRENT = OS_RUNS_DIR / "current.json"
CODEBASE_INDEX_DIR = PILOTHOS_DIR / "memory" / "state" / "codebase-index"
CODEBASE_INDEX_DB = CODEBASE_INDEX_DIR / "index.sqlite3"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
REVIEW_LOG = PILOTHOS_DIR / "rot" / "review-log.md"
LESSONS = PILOTHOS_DIR / "memory" / "lessons-learned.md"
MARKER_DIR = pathlib.Path("/tmp/pilothos")
ASSET_SYNC_START = "<!-- PILOTHOS-GENERATED-ASSETS:START -->"
ASSET_SYNC_END = "<!-- PILOTHOS-GENERATED-ASSETS:END -->"

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
MARKER_TTL_SECONDS = 48 * 3600
REPO_KEY = hashlib.sha256(str(REPO_ROOT.resolve()).encode("utf-8")).hexdigest()[:16]

# Thư mục/file bỏ qua khi quét thay đổi cho auto-log gate
SCAN_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
SCAN_EXCLUDE_FILES = {REVIEW_LOG.resolve(), LESSONS.resolve()}
IGNORE_NAMES = {".DS_Store", "Thumbs.db"}

CONTRACT_REQUIRED_FIELDS = {
    "task_scope", "affected_layers", "allowed_paths",
    "expected_evidence", "out_of_scope_paths",
}
RECEIPT_REQUIRED_FIELDS = {
    "changed_files", "affected_layers", "verification_command", "result",
}
REUSE_DISCIPLINE_FIELDS = {
    "existing_code_checked",
    "existing_component_checked",
    "existing_pattern_followed",
    "new_code_reason",
    "duplicate_risk",
    "kiss_dry_rationale",
}
LEARNING_REVIEW_FIELDS = {
    "mistake_checked",
    "lesson_decision",
    "promoted_to",
    "reason",
}
LEARNING_MISTAKE_CLASSES = {
    "guessed_without_context",
    "ignored_asset",
    "ignored_consumer_asset",
    "duplicated_helper",
    "duplicated_component",
    "bypassed_ds",
    "bypassed_design_system",
    "wrong_tool",
    "exceeded_scope",
    "unneeded_abstraction",
    "context_bloat",
    "skipped_verification",
    "none",
}
LEARNING_DECISIONS = {"recorded", "none", "deferred", "promoted"}
LEARNING_PROMOTION_TARGETS = {
    "rules",
    "rules/",
    "knowledge",
    "knowledge/",
    "skills",
    "skills/",
    "tools",
    "tools/index.md",
    "runtime",
    "runtime/",
    "evaluation",
    "evaluation/",
    "not_applicable",
}
LEARNING_PROMOTION_MARKERS = {"upstream"}
QUALITY_GATE_RESULTS = {"PASS", "FAIL", "NOT_APPLICABLE"}
RECEIPT_CONTEXT_FIELDS = {
    "source", "reason", "finding",
}
ASSET_ROUTING_FIELDS = {
    "task_signal", "asset_type", "decision", "reason",
}
REUSE_EVIDENCE_DECISIONS = {"reuse", "not_applicable", "not_enough"}
ASSET_ROUTING_DECISIONS = {"loaded", "skipped", "approval_required", "not_applicable"}
ASSET_ROUTING_SIGNALS = {
    "UI/component", "API/backend", "bug fix", "release/deploy",
    "tool/MCP", "architecture", "security", "not_applicable",
}
ASSET_ROUTING_TYPES = {
    "skill", "hook", "tool", "mcp", "command", "design-system", "doc",
    "convention", "test-runner", "build-runner", "agent", "specialist",
    "not_applicable",
}
UI_DESIGN_SYSTEM_DECISIONS = {"reuse", "extend", "new", "not_applicable"}
UI_RECEIPT_FIELDS = {
    "design_system_checked",
    "component_reuse_decision",
    "token_reuse_decision",
}
# Design-decision vocab (reuse/extend/new) is shared by every "what did you do
# with this candidate" review field. Alias one constant so the two names cannot
# drift apart. (Distinct from ASSET_ROUTING_DECISIONS, which is load-state, not
# a design decision.)
SEMANTIC_REVIEW_DECISIONS = UI_DESIGN_SYSTEM_DECISIONS
# Structured human-review vocabulary (Governed Visual Review round-trip).
REVIEW_SEVERITIES = {"blocker", "major", "minor", "nit"}
REVIEW_DISPOSITIONS = {"approve", "request-changes"}
REVIEW_VERDICTS = {"approve", "request-changes", "reject"}
REVIEW_BLOCKING_SEVERITIES = {"blocker", "major"}
# Prototype phase (visual UI proposal before implementation): the design method
# used to generate the >=2 UI variants a human then picks via human_review.
PROTOTYPE_METHODS = {"artifacts", "figma", "design_system", "shadcn", "lofi"}
TEAM_PERMISSION_ACTIONS = {"plan", "review", "edit", "qa", "advise"}
HIGH_CONFIDENCE_THRESHOLD = 0.80
TOOL_USE_REQUIRED_FIELDS = {
    "tool", "command", "risk", "timeout", "result", "evidence_output",
}
TOOL_CHECK_REQUIRED_FIELDS = {
    "tool", "command", "risk", "timeout", "expected_evidence",
}
ENTITLEMENT_RE = re.compile(r"[a-z][a-z0-9]*(?:[._:-][a-z0-9]+)*")
WARNING_CHECKLIST_RULES = (
    ("dependency file changed:", "dependency_change_reason"),
    ("new component-like file added:", "new_component_reason"),
    ("UI file changed without design system evidence:", "ui_design_system_gap_reason"),
    ("code changed without test/evidence", "code_without_test_reason"),
    ("large delta requires reuse discipline:", "large_delta_reason"),
)
HIGH_RISK_COMMAND_PATTERNS = (
    r"\brm\s+-rf\b",
    r"\bdeploy\b",
    r"\bproduction\b",
    r"\bprod\b",
    r"\bkubectl\b",
    r"\bterraform\s+apply\b",
    r"\bdb:migrate\b",
    r"\bprisma\s+migrate\s+deploy\b",
    r"\baws\b.*\b(delete|put|update|create|deploy)\b",
    r"\bgcloud\b.*\b(delete|deploy|update|create)\b",
    r"\bvercel\b.*\b--prod\b",
)
# --------------------------------------------------------- guard mode registry
# SSOT for everything the guard knows about its own modes. Four hand-maintained
# lists used to encode this separately (dispatch table, read-only set, self-host
# set, control-plane set) and had already drifted: `artifact-janitor --fix` was
# advertised read-only while it removes files, and `codebase-status` was not
# advertised read-only although it never writes. Every one of those lists is now
# derived from here, so a new mode cannot be half-registered.
#
# mutates:  False        -> never writes to disk
#           True         -> always writes
#           (flag, ...)  -> writes only when one of these argv flags is present
# Verified against a call-graph reachability check over the shipped bundle; the
# test suite re-runs that check so this table cannot silently drift from code.
def _guard_mode(arg_kind, mutates=False, self_host=False, control_plane=False):
    return {
        "arg_kind": arg_kind,
        "mutates": mutates,
        "self_host": self_host,
        "control_plane": control_plane,
    }


GUARD_MODES = {
    # hook modes (read hook JSON from stdin)
    "session-start": _guard_mode("hook", mutates=True),
    "prompt-check": _guard_mode("hook", mutates=True),
    "stop-check": _guard_mode("hook"),
    "pre-edit": _guard_mode("hook", self_host=True),
    "post-edit": _guard_mode("hook", mutates=True, self_host=True),
    # argv modes (JSON arg / file / stdin payload)
    "contract-write": _guard_mode("argv", mutates=True, self_host=True, control_plane=True),
    "evidence-add": _guard_mode("argv", mutates=True, control_plane=True),
    "tool-check": _guard_mode("argv", control_plane=True),
    "receipt-write": _guard_mode("argv", mutates=True, self_host=True, control_plane=True),
    "os-start": _guard_mode("argv", mutates=True, self_host=True, control_plane=True),
    "os-status": _guard_mode("argv", self_host=True, control_plane=True),
    "os-evidence": _guard_mode("argv", mutates=True, self_host=True, control_plane=True),
    "token-telemetry": _guard_mode("argv", mutates=True),
    "os-close": _guard_mode("argv", mutates=True, self_host=True, control_plane=True),
    "os-verify": _guard_mode("argv", self_host=True, control_plane=True),
    "os-report": _guard_mode("argv", self_host=True, control_plane=True),
    "review-request": _guard_mode("argv", mutates=True),
    "review-feedback": _guard_mode("argv", mutates=True),
    "review-verify": _guard_mode("argv"),
    "asset-scan": _guard_mode("argv", self_host=True, control_plane=True),
    "asset-health": _guard_mode("argv", self_host=True, control_plane=True),
    "asset-sync": _guard_mode("argv", mutates=True, self_host=True),
    "adapter-capabilities": _guard_mode("argv", self_host=True, control_plane=True),
    "evidence-route": _guard_mode("argv", self_host=True, control_plane=True),
    "route-task": _guard_mode("argv", self_host=True),
    "context-budget": _guard_mode("argv"),
    "payload-budget": _guard_mode("argv"),
    "codebase-index": _guard_mode("argv", mutates=True, self_host=True, control_plane=True),
    "codebase-status": _guard_mode("argv", self_host=True, control_plane=True),
    "codebase-query": _guard_mode("argv", self_host=True, control_plane=True),
    "reuse-scan": _guard_mode("argv", self_host=True),
    "ds-scan": _guard_mode("argv", self_host=True),
    "scheduler-suggest": _guard_mode("argv", self_host=True),
    "scheduler-record": _guard_mode("argv", mutates=True, self_host=True),
    "receipt-seal": _guard_mode("argv", mutates=True, self_host=True, control_plane=True),
    "receipt-verify": _guard_mode("argv", self_host=True, control_plane=True),
    # --fix removes artifact dirs/files; --target aims that removal at ANOTHER
    # repo, so it is a write even without --fix.
    "artifact-janitor": _guard_mode(
        "argv", mutates=("--fix", "--target"), self_host=True, control_plane=True,
    ),
    # --fix prunes sealed-run artifacts, truncates the scheduler tail and rotates
    # kernel logs.
    "state-janitor": _guard_mode("argv", mutates=("--fix",)),
    "control-plane-check": _guard_mode("argv", self_host=True, control_plane=True),
    "team-contract-write": _guard_mode("argv", mutates=True, self_host=True),
    "team-receipt-write": _guard_mode("argv", mutates=True, self_host=True),
    "log-append": _guard_mode("argv", mutates=True),
    # no-arg modes
    "rot-status": _guard_mode("none"),
    "receipt-template": _guard_mode("none"),
    "statusline": _guard_mode("none"),
    "self-check": _guard_mode("none"),
    "self-host-check": _guard_mode("none", self_host=True),
    "preflight": _guard_mode("none"),
    "detect": _guard_mode("none"),
    "audit-assets": _guard_mode("none"),
    "registry-assets": _guard_mode("none"),
    "state-doctor": _guard_mode("none", self_host=True),
    "production-review": _guard_mode("none", self_host=True, control_plane=True),
}
# Modes that MAY be treated as read-only: those that never write, plus the two
# janitors whose writes are flag-gated (the flag check lives in
# command_is_read_only_guard, which reads GUARD_MODES["mutates"] directly).
READ_ONLY_GUARD_MODES = frozenset(
    mode for mode, meta in GUARD_MODES.items() if meta["mutates"] is not True
)
SELF_HOST_REQUIRED_GUARD_MODES = tuple(
    sorted(mode for mode, meta in GUARD_MODES.items() if meta["self_host"])
)
CONTROL_PLANE_REQUIRED_GUARD_MODES = frozenset(
    mode for mode, meta in GUARD_MODES.items() if meta["control_plane"]
)


def mode_mutates(mode, args=()):
    """Whether running `mode` with `args` writes to disk.

    Answers straight from GUARD_MODES so no caller can disagree with the
    registry. An unrecognised mode counts as mutating: a mode this guard does not
    know about must never be handed a read-only exemption.
    """
    meta = GUARD_MODES.get(mode)
    if meta is None:
        return True
    mutates = meta["mutates"]
    if isinstance(mutates, bool):
        return mutates
    return any(
        arg == flag or arg.startswith(flag + "=")
        for arg in args
        for flag in mutates
    )


SAFE_READ_ONLY_GUARD_ENV_VARS = {"PYTHONPYCACHEPREFIX"}
SHELL_CONTROL_RE = re.compile(r"(&&|\|\||[;|`]|\$\()")
ENV_ASSIGNMENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*")
JUDGMENT_CHECKLIST_KEYS = {
    "layer_fit": "Thay đổi này có đúng layer không?",
    "abstraction": "Có abstraction mới không? Vì sao cần?",
    "scope": "Có vượt scope không?",
    "evidence": "Evidence có chứng minh claim không?",
}
DOC_TEST_LAYERS = {"docs", "documentation", "tests", "test"}
# A task touching this few concrete files is small enough for lean mode even
# when it is code — its blast radius does not justify full standard governance.
SMALL_SCOPE_MAX_PATHS = 3
ADAPTER_LAYERS = {"adapters", "adapter", "tools", "tools/runtime"}
RUNTIME_TOOL_LAYERS = {"tools", "runtime", "tools/runtime", "installer"}
JUDGMENT_LAYERS = {
    "rules", "hooks", "governance", "agents", "runtime",
    "agent teams", "adapters", "tools/runtime",
}
SENSITIVE_RUNTIME_PATHS = {
    "pilothOS/scripts/pilothos_guard.py",
    "pilothOS/scripts/pilothos_installer.py",
    "pilothOS/skills/workflow/pilothos-init/payloads/settings.json",
}
SOURCE_INSTALLER_PATHS = {
    "scripts/build_manifest.py",
    "scripts/stage.py",
    "scripts/stage.sh",
}
DEPENDENCY_FILE_NAMES = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json",
    "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",
    "requirements.txt", "requirements-dev.txt", "pyproject.toml",
    "poetry.lock", "Pipfile", "Pipfile.lock",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum",
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "settings.gradle.kts", "composer.json", "composer.lock",
    "Gemfile", "Gemfile.lock",
}
CODE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".go", ".rs", ".java", ".kt", ".kts", ".swift", ".rb",
    ".php", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp",
    ".css", ".scss", ".sass", ".vue", ".svelte",
}
OPERATIONAL_PRESETS = {"light", "standard", "strict"}
OS_MODES = {"lean", "standard", "strict"}
OS_MODE_REQUESTS = OS_MODES | {"adaptive", "auto"}
METRIC_TYPES = {
    "llm_usage",
    "tool_output",
    "context_load",
    "command",
    "ui_quality",
    "browser_smoke",
    "retry",
    "verification",
    "repair",
    "benchmark",
}
SUPERIORITY_CLAIM_RE = re.compile(
    r"\b(cheaper|lower cost|less tokens?|token saving|better|superior|consumer value|"
    r"more accurate|higher fidelity|rẻ hơn|tiết kiệm token|tốt hơn|đúng hơn|có ích hơn)\b",
    re.IGNORECASE,
)
COST_CLAIM_RE = re.compile(
    r"\b(cheaper|lower cost|less tokens?|token saving|token cost|cost saving|"
    r"rẻ hơn|tiết kiệm token|chi phí thấp hơn|giảm token)\b",
    re.IGNORECASE,
)
SUPERIORITY_PASS_RESULTS = {"consumer_value_passed", "passed", "pass", "superior", "better"}
PRODUCTION_FORBIDDEN_PATHS = {
    "pilothOS/scripts/pilothos_hostd.py",
    "pilothOS/runtime/host-control-plane.md",
}
ARTIFACT_JANITOR_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "playwright-report",
    "test-results",
}
ARTIFACT_JANITOR_FILE_NAMES = IGNORE_NAMES | {".coverage"}
ARTIFACT_JANITOR_SUFFIXES = (".pyc", ".pyo", ".tsbuildinfo")
ARTIFACT_JANITOR_SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "env",
}
ARTIFACT_JANITOR_MAX_FINDINGS = 200

# State janitor / retention (Nhóm A rác đĩa + Nhóm B token). Xem docs/token-optimization.md.
# Tất cả có thể override qua env, mirror pattern PILOTHOS_OPERATIONAL_PRESET.


def _env_int(name, default):
    try:
        value = int(os.environ.get(name, "").strip())
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


STATE_RETENTION_KEEP_RUNS = _env_int("PILOTHOS_RETENTION_RUNS", 10)
STATE_RETENTION_KEEP_DAYS = _env_int("PILOTHOS_RETENTION_DAYS", 14)
SCHEDULER_HISTORY_KEEP = _env_int("PILOTHOS_SCHEDULER_KEEP", 200)
KERNEL_LOG_KEEP_ROWS = _env_int("PILOTHOS_KERNEL_LOG_KEEP", 200)
RECEIPT_SEALS_WARN_LINES = _env_int("PILOTHOS_RECEIPT_SEALS_WARN", 500)
STATE_JANITOR_MAX_FINDINGS = 500
LESSONS_ARCHIVE = PILOTHOS_DIR / "memory" / "lessons-learned-archive.md"
REVIEW_LOG_ARCHIVE = PILOTHOS_DIR / "rot" / "review-log-archive.md"

SECRET_KEY_RE = re.compile(
    r"(secret|token|password|passwd|api[_-]?key|credential|authorization|bearer)",
    re.IGNORECASE,
)
SECRET_VALUE_PATTERNS = (
    re.compile(
        r"(?i)\b(api[_-]?key|token|password|passwd|secret|authorization)\s*[:=]\s*['\"]?[^,\s'\"]+"
    ),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
)
ABSOLUTE_CLAIM_RE = re.compile(
    r"\b(1:1|one-to-one|pixel[- ]?perfect|production[- ]ready|fully verified|fully complete|no issues|zero issues|perfect|full|complete|all tokens|entire library)\b",
    re.IGNORECASE,
)
DESIGN_TOKEN_FULL_CLAIM_RE = re.compile(
    r"\b(full|complete|all tokens|entire library)\b.*\b(token|tokens|variable|variables)\b|\b(token|tokens|variable|variables)\b.*\b(full|complete|all tokens|entire library)\b",
    re.IGNORECASE,
)
QUALIFIED_CLAIM_TERMS = (
    "not ",
    "blocked",
    "limitation",
    "limited",
    "except",
    "cannot",
    "unable",
    "missing",
    "partial",
    "qualified",
    "not claimed",
    "not claim",
)
EVIDENCE_PROFILES = {"code", "ui", "design_tokens", "docs", "release", "generic"}
OS_EVIDENCE_KINDS = {
    "command",
    "discovery",
    "human_review",
    "prototype",
    "figma_node",
    "design_token_coverage",
    "quality_gate",
    "artifact",
    "limitation",
    "metric",
}
DESIGN_TOKEN_SURFACES = {"ts", "css_vars", "tailwind_v3", "tailwind_v4"}
TARGET_KINDS = {"git", "non_git", "external"}
TARGET_FOOTPRINT_POLICIES = {"no_control_plane_files", "repo_local_state_allowed"}
CONTROL_PLANE_TARGET_DIRS = {"pilothOS", ".claude", ".codex", ".cursor", ".antigravity"}
CONTROL_PLANE_TARGET_FILES = {"CLAUDE.md", "AGENTS.md"}
SAFE_OS_EVIDENCE_METADATA_KEYS = {
    "fileKey", "file_key", "nodeId", "node_id", "frameId", "frame_id",
    "token_count", "covered_groups", "surface", "artifact_path",
    "target_path", "source_refs", "coverage_scope", "generated_surfaces",
    "verification", "limitations",
    "metric_type", "metric_name", "phase", "unit", "value", "count",
    "chars", "bytes", "duration_ms", "input_tokens", "output_tokens",
    "total_tokens", "real_token_telemetry", "unavailable_reason",
    "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd",
    # `unpriced_tokens` matches SECRET_KEY_RE on "token" — it is a count, not a
    # credential, so it needs the same exemption the other *_tokens counts have.
    "unpriced_tokens",
    "model", "pricing_source", "window_start", "subagent_scope",
    "consumer_value_result", "all_mandatory_not_worse",
    "consumer_visible_win", "mandatory_regressions", "wins",
    "viewport_width", "viewport_height", "browser", "browser_tool", "url",
    "required_text_ok", "console_errors", "console_error_count",
    "page_errors", "page_error_count", "image_failures", "image_failure_count",
    "horizontal_overflow", "vertical_overflow", "layout_overflow_count",
    "visual_diff_result", "visual_diff_pixels", "visual_diff_ratio",
    "screenshot_path", "baseline_screenshot_path", "comparison_artifact_path",
}
PRODUCTION_STALE_TERMS = (
    "pilothos_hostd.py",
    "host-control-plane.md",
    "PILOTH_HOST_ROOT",
    "macOS-inspired",
)
NOISE_TOKEN_A = "TO" + "DO"
NOISE_TOKEN_B = "FIX" + "ME"
NOISE_TOKEN_C = "HA" + "CK"
PRODUCTION_NOISE_PATTERNS = (
    re.compile(r"\b" + NOISE_TOKEN_A + r"\b"),
    re.compile(r"\b" + NOISE_TOKEN_B + r"\b"),
    re.compile(r"\b" + NOISE_TOKEN_C + r"\b"),
    re.compile(r"\bX" + r"XX\b"),
    re.compile("not " + "implemented", re.IGNORECASE),
    re.compile("temporary " + "workaround", re.IGNORECASE),
)
TASK_SIGNAL_ROUTES = {
    "ui/component": {
        "task_signal": "UI/component",
        "asset_types": ("design-system", "doc", "skill"),
        "load_policy": "task-routed",
        "context_layers": ("rules/ui-design-system.md", "runtime/context-loading.md"),
    },
    "api/backend": {
        "task_signal": "API/backend",
        "asset_types": ("convention", "doc", "test-runner"),
        "load_policy": "task-routed",
        "context_layers": ("runtime/context-loading.md", "tools/index.md"),
    },
    "bug fix": {
        "task_signal": "bug fix",
        "asset_types": ("test-runner", "convention", "doc"),
        "load_policy": "task-routed",
        "context_layers": ("rules/coding-behavior.md", "evaluation/quality-gates.md"),
    },
    "release/deploy": {
        "task_signal": "release/deploy",
        "asset_types": ("command", "tool", "build-runner"),
        "load_policy": "approval-required",
        "context_layers": ("governance/operational-controls.md", "tools/index.md"),
    },
    "tool/mcp": {
        "task_signal": "tool/MCP",
        "asset_types": ("tool", "mcp", "command"),
        "load_policy": "task-routed",
        "context_layers": ("tools/index.md", "runtime/context-loading.md"),
    },
    "architecture": {
        "task_signal": "architecture",
        "asset_types": ("specialist", "agent", "convention", "doc"),
        "load_policy": "task-routed",
        "context_layers": ("knowledge/architecture/README.md", "runtime/context-loading.md"),
    },
    "security": {
        "task_signal": "security",
        "asset_types": ("specialist", "agent", "tool", "test-runner"),
        "load_policy": "approval-required",
        "context_layers": ("governance/operational-controls.md", "evaluation/quality-gates.md"),
    },
    "not_applicable": {
        "task_signal": "not_applicable",
        "asset_types": ("not_applicable",),
        "load_policy": "never-auto",
        "context_layers": ("runtime/context-loading.md",),
    },
}
# -------------------------------------------------------------- small helpers

def stable_slug(value):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "item"


def safe_task_id(value):
    return stable_slug(value)[:120]


def read_text_safe(path, limit=200000):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if limit and len(text) > limit:
        return text[:limit]
    return text


def git_changed_paths():
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []
    paths = []
    for line in out.stdout.splitlines():
        if not line:
            continue
        raw = line[3:] if len(line) > 3 else line
        if " -> " in raw:
            raw = raw.rsplit(" -> ", 1)[1]
        raw = raw.strip()
        if raw:
            paths.append(raw)
    return sorted(set(paths))


def git_changed_file_paths():
    paths = []
    commands = [
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only"],
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only", "--cached"],
        ["git", "-C", str(REPO_ROOT), "ls-files", "--others", "--exclude-standard"],
    ]
    for command in commands:
        try:
            out = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        except Exception:
            continue
        if out.returncode == 0:
            paths.extend(line.strip() for line in out.stdout.splitlines() if line.strip())
    if paths:
        return sorted(set(paths))

    expanded = []
    for raw in git_changed_paths():
        rel = raw.rstrip("/")
        path = REPO_ROOT / rel
        if path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file():
                    expanded.append(item.relative_to(REPO_ROOT).as_posix())
        else:
            expanded.append(rel)
    return sorted(set(p for p in expanded if p))


def is_git_repo():
    """REPO_ROOT có nằm trong một git working tree hoạt động được không?

    Dùng để phân biệt 'working tree sạch' với 'git không khả dụng': khi không
    phải git repo, git_changed_file_paths() trả rỗng một cách mập mờ, nên gate
    phải fallback về hành vi mtime cũ thay vì tưởng nhầm mọi thứ đã deliver.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
    except Exception:
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def json_print(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def write_json(path, obj):
    """Write obj as the canonical PilothOS state-file JSON: UTF-8, sorted keys,
    2-space indent, trailing newline. Single writer for every persisted
    state/contract/receipt/seal file so their on-disk format cannot drift."""
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_json(value):
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def redact_secret_text(value, limit=1000):
    text = str(value)
    for pattern in SECRET_VALUE_PATTERNS:
        text = pattern.sub(lambda match: match.group(0).split(match.group(1), 1)[0] + match.group(1) + "=[redacted]"
                           if len(match.groups()) else "[redacted]", text)
    if len(text) > limit:
        return text[:limit] + "...[truncated]"
    return text


def sanitize_state_value(value, limit=1000):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if SECRET_KEY_RE.search(key_text):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_state_value(item, limit=limit)
        return sanitized
    if isinstance(value, list):
        return [sanitize_state_value(item, limit=limit) for item in value[:50]]
    if isinstance(value, str):
        return redact_secret_text(value, limit=limit)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_secret_text(value, limit=limit)


def os_run_dir(task_id):
    return OS_RUNS_DIR / safe_task_id(task_id)


def os_state_path(task_id, filename="state.json"):
    return os_run_dir(task_id) / filename


def os_evidence_path(task_id):
    return os_state_path(task_id, "evidence.jsonl")


def read_os_current_task_id():
    data = load_json_file(OS_CURRENT)
    if isinstance(data, dict) and non_empty_string(data.get("task_id")):
        return data["task_id"]
    return ""


def write_os_current_task_id(task_id):
    OS_CURRENT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OS_CURRENT, {
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })


def load_os_state(task_id=None):
    if not task_id:
        task_id = read_os_current_task_id()
    if task_id:
        path = os_state_path(task_id)
        data = load_json_file(path)
        if isinstance(data, dict):
            return data, path
    latest = latest_os_state()
    if latest:
        return latest
    return None, None


def latest_os_state(require_closed=False):
    if not OS_RUNS_DIR.exists():
        return None, None
    candidates = []
    for path in OS_RUNS_DIR.glob("*/state.json"):
        data = load_json_file(path)
        if not isinstance(data, dict):
            continue
        if data.get("repo_key") != REPO_KEY:
            continue
        if require_closed:
            status = data.get("status")
            if status not in {"closed", "sealed"}:
                continue
            if not non_empty_string(data.get("seal_sha256")):
                continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        candidates.append((mtime, data.get("updated_at", ""), data, path))
    if not candidates:
        return None, None
    _, _, data, path = sorted(candidates, key=lambda item: (item[0], item[1]))[-1]
    return data, path


def save_os_state(state):
    task_id = state.get("task_id")
    if not non_empty_string(task_id):
        raise ValueError("OS state missing task_id")
    state = dict(state)
    state["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = os_state_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, state)
    write_os_current_task_id(task_id)
    return path


def os_evidence_records(task_id):
    path = os_evidence_path(task_id)
    if not path.exists():
        return []
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
    except (OSError, json.JSONDecodeError):
        return []
    return records


def append_os_evidence(task_id, evidence):
    path = os_evidence_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(evidence, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def review_feedback_path(task_id):
    return os_state_path(task_id, "review-feedback.jsonl")


def append_review_feedback(task_id, record):
    """Append one human-review round to the append-only review-feedback ledger.

    Mirrors append_os_evidence: one JSON record per line, one line per review
    round. os-close reads the highest-round record for the human_review gate.
    """
    path = review_feedback_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def review_feedback_records(task_id):
    path = review_feedback_path(task_id)
    if not path.exists():
        return []
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
    except (OSError, json.JSONDecodeError):
        return []
    return records


def latest_review_feedback(task_id):
    records = review_feedback_records(task_id)
    if not records:
        return None

    def _round(r):
        try:
            return int(r.get("review_round", 0))
        except (TypeError, ValueError):
            return 0

    return sorted(records, key=_round)[-1]


# ---------------------------------------------------------------- stdin/session

def read_hook_input():
    """Đọc JSON hook input từ stdin an toàn. Trả về dict (có thể rỗng).
    Không bao giờ block vô hạn: tty → bỏ qua; pipe không có dữ liệu trong 0.5s
    → degraded về {} (chạy tay/không stdin vẫn hoạt động đúng như tuyên bố)."""
    try:
        if sys.stdin.isatty():
            return {}
        import select
        readable, _, _ = select.select([sys.stdin], [], [], 0.5)
        if not readable:
            return {}
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def cleanup_old_markers():
    if not MARKER_DIR.exists():
        return
    now = time.time()
    for f in MARKER_DIR.iterdir():
        try:
            if now - f.stat().st_mtime > MARKER_TTL_SECONDS:
                f.unlink()
        except OSError:
            pass


def marker(session_id, suffix):
    return MARKER_DIR / f"{session_id}.{suffix}"


# ------------------------------------------------------- task contract state

def repo_state_file(suffix):
    return MARKER_DIR / f"repo-{REPO_KEY}.{suffix}"


def scoped_state_file(hook_input, suffix):
    sid = hook_input.get("session_id")
    if sid:
        return marker(sid, suffix)
    return repo_state_file(suffix)


def fresh_state_file(path):
    try:
        return path.exists() and time.time() - path.stat().st_mtime <= MARKER_TTL_SECONDS
    except OSError:
        return False


def load_json_state(path):
    if not fresh_state_file(path):
        return None
    return load_json_file(path)


def load_json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def env_state_path(name):
    raw = os.environ.get(name)
    if not raw:
        return None
    p = pathlib.Path(raw)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def load_task_contract(hook_input):
    candidates = []
    env_path = env_state_path("PILOTHOS_TASK_CONTRACT")
    if env_path:
        data = load_json_file(env_path)
        if data is not None:
            return data, env_path
    candidates.append(scoped_state_file(hook_input, "task-contract.json"))
    candidates.append(repo_state_file("task-contract.json"))
    for path in candidates:
        data = load_json_state(path)
        if data is not None:
            return data, path
    return None, None


def load_diff_facts(hook_input):
    data = load_json_state(scoped_state_file(hook_input, "diff-facts.json"))
    if data is None and hook_input.get("session_id"):
        data = load_json_state(repo_state_file("diff-facts.json"))
    if data is None:
        data = {
            "changed_files": {},
            "affected_layers": [],
            "has_tests": False,
            "has_docs": False,
            "evidence_commands": [],
            "warnings": [],
        }
    ensure_diff_fact_fields(data)
    return data


def save_diff_facts(hook_input, facts):
    MARKER_DIR.mkdir(exist_ok=True)
    ensure_diff_fact_fields(facts)
    facts["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    scoped_state_file(hook_input, "diff-facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Also publish the latest facts at repo scope so manual commands such as
    # receipt-write can validate against PostToolUse facts from a session hook.
    repo_state_file("diff-facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_deliver_receipt(hook_input):
    candidates = []
    env_path = env_state_path("PILOTHOS_DELIVER_RECEIPT")
    if env_path:
        data = load_json_file(env_path)
        if data is not None:
            return data, env_path
    candidates.append(scoped_state_file(hook_input, "deliver-receipt.json"))
    candidates.append(repo_state_file("deliver-receipt.json"))
    for path in candidates:
        data = load_json_state(path)
        if data is not None:
            return data, path
    return None, None


def normalize_layer(layer):
    return re.sub(r"\s+", " ", str(layer)).strip().lower()


def operational_preset(*configs):
    for name in ("PILOTHOS_OPERATIONAL_PRESET", "PILOTHOS_PRESET"):
        raw = os.environ.get(name)
        if raw:
            return raw.strip().lower()
    for config in configs:
        if isinstance(config, dict):
            raw = config.get("operational_preset")
            if raw:
                return str(raw).strip().lower()
    return "standard"


def valid_operational_preset(value):
    return value in OPERATIONAL_PRESETS


def preset_requires_standard_evidence(*configs):
    return operational_preset(*configs) != "light"


def contract_layers(contract):
    return {normalize_layer(x) for x in contract.get("affected_layers", [])}


def contract_has_layer(contract, allowed):
    layers = contract_layers(contract)
    return bool(layers & allowed)


def normalize_relative_path_text(value):
    rel = str(value).replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def normalize_contract_path_pattern(pattern):
    return normalize_relative_path_text(pattern)


def path_pattern_docs_tests_only(pattern):
    rel = normalize_contract_path_pattern(pattern)
    if not rel or rel in {"*", "**", "**/*", "."}:
        return False
    if rel.startswith(("src/", "app/", "pages/", "components/", "ui/")):
        return False
    if rel.startswith((
        "pilothOS/scripts/",
        "pilothOS/rules/",
        "pilothOS/runtime/",
        "pilothOS/tools/",
        "adapters/",
        "templates/",
        "commands/",
    )):
        return False
    if rel.startswith(("docs/", "test/", "tests/", "__tests__/")):
        return True
    if rel in {"README.md", "CLAUDE.md", "AGENTS.md"}:
        return True
    if rel.endswith(".md") and layer_for_path(rel) == "Docs":
        return True
    return False


def contract_docs_tests_only(contract):
    layers = contract_layers(contract)
    allowed_paths = contract.get("allowed_paths")
    if not (layers and layers <= DOC_TEST_LAYERS):
        return False
    if not isinstance(allowed_paths, list) or not allowed_paths:
        return False
    return all(path_pattern_docs_tests_only(pattern) for pattern in allowed_paths)


def contract_requires_context_evidence(contract):
    return preset_requires_standard_evidence(contract) and not contract_docs_tests_only(contract)


def path_pattern_suggests_ui(pattern):
    rel = normalize_contract_path_pattern(pattern)
    if not rel or rel in {"*", "**", "**/*", "."}:
        return False
    return is_ui_path(rel)


def contract_requires_ui_design_system_evidence(contract):
    if not preset_requires_standard_evidence(contract):
        return False
    allowed_paths = contract.get("allowed_paths")
    if not isinstance(allowed_paths, list):
        return False
    return any(path_pattern_suggests_ui(pattern) for pattern in allowed_paths)


def contract_requires_energy_budget_reason(contract):
    if not preset_requires_standard_evidence(contract):
        return False
    text = " ".join(str(x) for x in contract.get("expected_evidence", []))
    text += " " + str(contract.get("task_scope", ""))
    lowered = text.lower()
    return any(token in lowered for token in (
        "tests/run_all.sh", "run_all.sh", "full suite", "broad scan", "all suites",
    ))


def non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_object_list(value, field, required_keys):
    errors = []
    if not isinstance(value, list) or not value:
        return [f"{field} must be a non-empty list of objects"]
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{i}] must be an object")
            continue
        for key in required_keys:
            if not non_empty_string(item.get(key)):
                errors.append(f"{field}[{i}].{key} must be a non-empty string")
    return errors


def validate_object_list_enums(value, field, required_keys, enum_fields):
    errors = validate_object_list(value, field, required_keys)
    if not isinstance(value, list):
        return errors
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        for key, allowed in enum_fields.items():
            raw = item.get(key)
            if not non_empty_string(raw):
                continue
            if raw.strip() not in allowed:
                errors.append(
                    f"{field}[{i}].{key} must be one of: "
                    + ", ".join(sorted(allowed))
                )
    return errors


def validate_reuse_evidence(value, field="reuse_evidence"):
    return validate_object_list_enums(
        value,
        field,
        ("asset", "decision", "reason"),
        {"decision": REUSE_EVIDENCE_DECISIONS},
    )


def validate_asset_routing(value, field="consumer_asset_routing"):
    return validate_object_list_enums(
        value,
        field,
        ASSET_ROUTING_FIELDS,
        {
            "task_signal": ASSET_ROUTING_SIGNALS,
            "asset_type": ASSET_ROUTING_TYPES,
            "decision": ASSET_ROUTING_DECISIONS,
        },
    )


def validate_ui_design_system_evidence(value, field="ui_design_system_evidence"):
    return validate_object_list_enums(
        value,
        field,
        ("source", "checked", "decision", "reason"),
        {"decision": UI_DESIGN_SYSTEM_DECISIONS},
    )


def candidate_confidence(candidate):
    try:
        return float(candidate.get("confidence", 0))
    except (TypeError, ValueError):
        return 0.0


def candidates_from_receipt(receipt, keys):
    candidates = []
    if not isinstance(receipt, dict):
        return candidates
    for key in keys:
        value = receipt.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            for nested_key in (
                "candidates", "high_confidence_candidates",
                "component_candidates", "token_candidates", "pattern_candidates",
            ):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    candidates.extend(item for item in nested if isinstance(item, dict))
    return candidates


def review_items(value, field):
    errors = []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or not value:
        return [], [f"{field} must be a non-empty object or list of objects"]
    items = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{i}] must be an object")
            continue
        target = item.get("candidate") or item.get("candidate_id") or item.get("id") or item.get("path")
        if not non_empty_string(target):
            errors.append(f"{field}[{i}].candidate must be a non-empty string")
        decision = item.get("decision")
        if decision not in SEMANTIC_REVIEW_DECISIONS:
            errors.append(
                f"{field}[{i}].decision must be one of: "
                + ", ".join(sorted(SEMANTIC_REVIEW_DECISIONS))
            )
        if not non_empty_string(item.get("reason")):
            errors.append(f"{field}[{i}].reason must be a non-empty string")
        items.append({"candidate": str(target), "decision": decision, "reason": item.get("reason")})
    return items, errors


def validate_candidate_review(receipt, candidate_keys, review_field):
    errors = []
    candidates = candidates_from_receipt(receipt, candidate_keys)
    high = [
        c for c in candidates
        if candidate_confidence(c) >= HIGH_CONFIDENCE_THRESHOLD
    ]
    if not high:
        if review_field in receipt:
            _, review_errors = review_items(receipt.get(review_field), review_field)
            errors.extend(review_errors)
        return errors
    reviews, review_errors = review_items(receipt.get(review_field), review_field)
    errors.extend(review_errors)
    if review_errors:
        return errors
    covered = {item["candidate"] for item in reviews}
    covers_all = "all" in covered or "*" in covered
    for candidate in high:
        identifiers = {
            str(candidate.get("id", "")),
            str(candidate.get("path", "")),
            str(candidate.get("candidate", "")),
        }
        identifiers.discard("")
        if not covers_all and not (covered & identifiers):
            errors.append(
                f"{review_field} missing decision for high-confidence candidate: "
                + (candidate.get("id") or candidate.get("path") or "<unknown>")
            )
    return errors


def contract_has_ui_design_system_evidence(contract):
    if not isinstance(contract, dict):
        return False
    return not validate_ui_design_system_evidence(
        contract.get("ui_design_system_evidence"),
        "ui_design_system_evidence",
    )


def path_pattern_is_safe(pattern):
    if not isinstance(pattern, str) or not pattern.strip():
        return False
    pattern = pattern.strip()
    if pattern.startswith("/") or pattern.startswith("~"):
        return False
    return ".." not in pathlib.PurePosixPath(pattern).parts


def path_matches(patterns, rel):
    rel = normalize_relative_path_text(rel)
    for pattern in patterns:
        pattern = normalize_relative_path_text(pattern)
        if pattern in ("*", "**", "**/*"):
            return True
        if pattern.endswith("/"):
            base = pattern.rstrip("/")
            if rel == base or rel.startswith(base + "/"):
                return True
        if any(ch in pattern for ch in "*?["):
            if fnmatch.fnmatchcase(rel, pattern):
                return True
        elif rel == pattern or rel.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def repo_relative_path(path_value):
    if not isinstance(path_value, str) or not path_value.strip():
        return None, "empty path"
    raw = path_value.strip()
    try:
        p = pathlib.Path(raw)
        if p.is_absolute():
            resolved = p.resolve()
            root = REPO_ROOT.resolve()
            if resolved != root and root not in resolved.parents:
                return None, f"path outside repo: {raw}"
            rel = resolved.relative_to(root).as_posix()
        else:
            pure = pathlib.PurePosixPath(raw.replace("\\", "/"))
            if ".." in pure.parts:
                return None, f"path traversal blocked: {raw}"
            rel = normalize_relative_path_text(pure.as_posix())
    except (OSError, ValueError) as e:
        return None, f"invalid path {raw}: {e}"
    if not rel:
        return None, "repo root edit is not allowed"
    return rel, None


def target_relative_path(path_value, target_repo):
    if not isinstance(path_value, str) or not path_value.strip():
        return None, "empty path"
    raw = path_value.strip()
    root = pathlib.Path(target_repo).resolve()
    try:
        p = pathlib.Path(raw)
        if p.is_absolute():
            resolved = p.resolve()
            if resolved != root and root not in resolved.parents:
                return None, f"path outside target repo: {raw}"
            rel = resolved.relative_to(root).as_posix()
        else:
            pure = pathlib.PurePosixPath(raw.replace("\\", "/"))
            if ".." in pure.parts:
                return None, f"path traversal blocked: {raw}"
            rel = normalize_relative_path_text(pure.as_posix())
    except (OSError, ValueError) as e:
        return None, f"invalid path {raw}: {e}"
    if not rel:
        return None, "target repo root is not a file path"
    return rel, None


def resolve_target_repo(request):
    raw = request.get("target_repo") if isinstance(request, dict) else None
    explicit_target = raw is not None and str(raw).strip() != ""
    if raw is None or str(raw).strip() == "":
        target = REPO_ROOT.resolve()
    else:
        if not isinstance(raw, str):
            return None, ["target_repo must be a string when present"]
        candidate = pathlib.Path(raw.strip()).expanduser()
        if not candidate.is_absolute():
            return None, ["target_repo must be an absolute path when present"]
        target = candidate.resolve()
    errors = []
    if not target.exists():
        errors.append(f"target_repo does not exist: {target}")
    elif not target.is_dir():
        errors.append(f"target_repo must be a directory: {target}")
    state_root = (PILOTHOS_DIR / "memory" / "state").resolve()
    if target == state_root or state_root in target.parents:
        errors.append("target_repo cannot be inside pilothOS/memory/state")
    requested_kind = str(request.get("target_kind", "")).strip() if isinstance(request, dict) else ""
    if requested_kind and requested_kind not in TARGET_KINDS:
        errors.append("target_kind must be git, non_git, or external")
    if errors:
        return None, errors

    git_info = git_worktree_info(target)
    actual_kind = "git" if git_info.get("is_git") else "non_git"
    if requested_kind == "git" and actual_kind != "git":
        errors.append("target_kind=git but target_repo is not a git worktree")
    if requested_kind == "non_git" and actual_kind == "git":
        errors.append("target_kind=non_git but target_repo is a git worktree")
    if errors:
        return None, errors

    target_kind = requested_kind if requested_kind == "external" else actual_kind
    marker = git_info.get("git_dir") if actual_kind == "git" else "non_git"
    target_id = sha256_json({
        "target_repo": str(target),
        "target_kind": target_kind,
        "marker": marker,
    })[:16]
    return {
        "target_repo": str(target),
        "target_kind": target_kind,
        "target_vcs": actual_kind,
        "target_id": target_id,
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "external": target != REPO_ROOT.resolve(),
        "explicit": explicit_target,
        "git": git_info,
    }, []


def git_worktree_info(root):
    info = {"is_git": False}
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        if top.returncode != 0:
            return info
        git_dir = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
    except Exception:
        return info
    top_path = pathlib.Path(top.stdout.strip()).resolve()
    raw_git_dir = git_dir.stdout.strip() if git_dir.returncode == 0 else ""
    git_path = pathlib.Path(raw_git_dir)
    if raw_git_dir and not git_path.is_absolute():
        git_path = (pathlib.Path(root) / git_path).resolve()
    return {
        "is_git": True,
        "worktree_root": str(top_path),
        "git_dir": str(git_path) if raw_git_dir else "",
        "head": head.stdout.strip() if head.returncode == 0 else "",
    }


def parse_git_status_paths(output):
    paths = []
    for line in output.splitlines():
        if not line:
            continue
        raw = line[3:] if len(line) > 3 else line
        if " -> " in raw:
            raw = raw.rsplit(" -> ", 1)[1]
        raw = raw.strip().strip('"')
        if raw:
            paths.append(raw)
    return sorted(set(paths))


def git_status_for_root(root):
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=8,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []
    return parse_git_status_paths(out.stdout)


def target_git_status_paths(target):
    root = pathlib.Path(target["target_repo"]).resolve()
    paths = git_status_for_root(root)
    return sorted(paths)


def non_git_snapshot_skip(rel_parts):
    if any(part in ARTIFACT_JANITOR_SKIP_DIRS for part in rel_parts):
        return True
    if rel_parts[:3] == ("pilothOS", "memory", "state"):
        return True
    return False


def target_manifest_snapshot(target_repo):
    root = pathlib.Path(target_repo).resolve()
    files = {}
    root_len = len(root.parts)
    for current, dirs, filenames in os.walk(root):
        current_path = pathlib.Path(current)
        rel_parts = current_path.parts[root_len:]
        dirs.sort()
        filenames.sort()
        dirs[:] = [
            dirname for dirname in dirs
            if not non_git_snapshot_skip(rel_parts + (dirname,))
        ]
        if non_git_snapshot_skip(rel_parts):
            continue
        for filename in filenames:
            if filename in IGNORE_NAMES:
                continue
            path = current_path / filename
            try:
                rel = path.relative_to(root).as_posix()
                data = path.read_bytes()
            except OSError:
                continue
            files[rel] = {
                "path": rel,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
    return files


def target_state_snapshot(target):
    root = pathlib.Path(target["target_repo"]).resolve()
    payload = {
        "schema_version": 1,
        "target_repo": str(root),
        "target_kind": target.get("target_kind"),
        "target_vcs": target.get("target_vcs"),
        "target_id": target.get("target_id"),
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if target.get("target_vcs") == "git":
        payload["git"] = target.get("git", {})
        payload["git_status_short"] = target_git_status_paths(target)
    else:
        files = target_manifest_snapshot(root)
        payload["files"] = files
        payload["file_count"] = len(files)
        payload["manifest_sha256"] = sha256_json(files)
    payload["snapshot_sha256"] = sha256_json(payload)
    return payload


def load_target_snapshot(state):
    if not isinstance(state, dict):
        return {}
    task_id = state.get("task_id")
    if non_empty_string(task_id):
        data = load_json_file(os_state_path(task_id, "target-snapshot.json"))
        if isinstance(data, dict):
            return data
    snap = state.get("target_snapshot")
    return snap if isinstance(snap, dict) else {}


def target_changed_paths(state):
    target = state.get("target") if isinstance(state, dict) else None
    if not isinstance(target, dict):
        return {
            "schema_version": 1,
            "result": "target_diff_unavailable",
            "changed_paths": [],
            "errors": ["OS state has no target metadata"],
        }
    snapshot = load_target_snapshot(state)
    root = pathlib.Path(target["target_repo"]).resolve()
    changed = []
    deleted = []
    created = []
    modified = []
    errors = []
    if target.get("target_vcs") == "git":
        baseline = sorted(snapshot.get("git_status_short") or [])
        current = target_git_status_paths(target)
        changed = sorted(set(baseline) | set(current))
        result = {
            "schema_version": 1,
            "result": "target_diff",
            "target_repo": str(root),
            "target_kind": target.get("target_kind"),
            "target_vcs": target.get("target_vcs"),
            "target_id": target.get("target_id"),
            "baseline_dirty_paths": baseline,
            "current_dirty_paths": current,
            "changed_paths": changed,
            "deleted_files": [],
        }
    else:
        baseline_files = snapshot.get("files") if isinstance(snapshot.get("files"), dict) else {}
        current_files = target_manifest_snapshot(root)
        baseline_paths = set(baseline_files)
        current_paths = set(current_files)
        created = sorted(current_paths - baseline_paths)
        deleted = sorted(baseline_paths - current_paths)
        modified = sorted(
            path for path in (baseline_paths & current_paths)
            if baseline_files[path].get("sha256") != current_files[path].get("sha256")
        )
        changed = sorted(set(created) | set(deleted) | set(modified))
        result = {
            "schema_version": 1,
            "result": "target_diff",
            "target_repo": str(root),
            "target_kind": target.get("target_kind"),
            "target_vcs": target.get("target_vcs"),
            "target_id": target.get("target_id"),
            "baseline_manifest_sha256": snapshot.get("manifest_sha256", ""),
            "current_manifest_sha256": sha256_json(current_files),
            "created_files": created,
            "modified_files": modified,
            "deleted_files": deleted,
            "changed_paths": changed,
        }
    result["errors"] = errors
    result["diff_sha256"] = sha256_json({
        "target_id": result.get("target_id"),
        "changed_paths": changed,
        "deleted_files": result.get("deleted_files", []),
        "created_files": created,
        "modified_files": modified,
        "baseline_dirty_paths": result.get("baseline_dirty_paths", []),
        "current_dirty_paths": result.get("current_dirty_paths", []),
    })
    return result


def facts_from_target_diff(target_diff, active_facts=None):
    facts = {
        "changed_files": {},
        "affected_layers": [],
        "has_tests": False,
        "has_docs": False,
        "evidence_commands": [],
        "warnings": [],
    }
    for rel in target_diff.get("changed_paths", []):
        if not non_empty_string(rel):
            continue
        facts["changed_files"][rel] = {
            "layer": layer_for_path(rel),
            "added": 0,
            "deleted": 0,
            "changed_lines": 0,
            "new_file": rel in set(target_diff.get("created_files") or []),
            "deleted_file": rel in set(target_diff.get("deleted_files") or []),
            "source": "target_diff",
        }
    if isinstance(active_facts, dict):
        facts["evidence_commands"] = list(active_facts.get("evidence_commands") or [])
        facts["warnings"] = list(active_facts.get("warnings") or [])
    update_diff_fact_derived(facts)
    return facts


def target_diff_from_active_facts(state, active_facts):
    target = state.get("target") if isinstance(state, dict) else {}
    changed = sorted((active_facts or {}).get("changed_files", {}))
    deleted = sorted(
        rel for rel, meta in ((active_facts or {}).get("changed_files") or {}).items()
        if isinstance(meta, dict) and meta.get("deleted_file")
    )
    payload = {
        "schema_version": 1,
        "result": "target_diff",
        "source": "active_diff_facts",
        "target_repo": target.get("target_repo", str(REPO_ROOT.resolve())),
        "target_kind": target.get("target_kind", "non_git"),
        "target_vcs": target.get("target_vcs", "non_git"),
        "target_id": target.get("target_id", ""),
        "changed_paths": changed,
        "deleted_files": deleted,
        "errors": [],
    }
    payload["diff_sha256"] = sha256_json({
        "target_id": payload.get("target_id"),
        "changed_paths": changed,
        "deleted_files": deleted,
        "source": "active_diff_facts",
    })
    return payload


def should_use_v1_target_diff(state):
    target = state.get("target") if isinstance(state, dict) else {}
    return (
        isinstance(target, dict)
        and not target.get("explicit")
        and target.get("target_vcs") == "non_git"
    )


def target_file_hash_entry(raw_path, target):
    root = pathlib.Path(target["target_repo"]).resolve()
    rel, err = target_relative_path(raw_path, root)
    if err:
        return {"path": str(raw_path), "status": "invalid", "reason": err}
    path = root / rel
    if not path.exists():
        return {"path": rel, "status": "missing"}
    if not path.is_file():
        return {"path": rel, "status": "not_file"}
    try:
        data = path.read_bytes()
    except OSError as e:
        return {"path": rel, "status": "failed", "reason": str(e)}
    return {
        "path": rel,
        "status": "sealed",
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def target_file_seal_items(target, changed_files):
    return [
        target_file_hash_entry(path, target)
        for path in sorted(
            p for p in (changed_files or [])
            if isinstance(p, str) and p.strip()
        )
    ]


def build_target_seal(state, receipt, target_diff):
    target = state.get("target") if isinstance(state, dict) else {}
    changed_files = receipt.get("changed_files") if isinstance(receipt, dict) else []
    payload = {
        "schema_version": 1,
        "repo_key": REPO_KEY,
        "task_id": state.get("task_id", ""),
        "target_repo": target.get("target_repo", ""),
        "target_kind": target.get("target_kind", ""),
        "target_vcs": target.get("target_vcs", ""),
        "target_id": target.get("target_id", ""),
        "target_diff_sha256": target_diff.get("diff_sha256", ""),
        "changed_paths": sorted(target_diff.get("changed_paths") or []),
        "deleted_files": sorted(target_diff.get("deleted_files") or []),
        "changed_files": target_file_seal_items(target, changed_files),
        "receipt_changed_files": sorted(changed_files or []),
        "limits": [
            "target SHA-256 seal only; not cryptographic code signing",
            "verify against the same target checkout/path and OS run state",
        ],
    }
    payload["target_seal_sha256"] = sha256_json(payload)
    return payload


def validate_target_receipt_coverage(receipt, target_diff):
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]
    receipt_files = {
        p for p in (receipt.get("changed_files") or [])
        if isinstance(p, str) and p.strip()
    }
    changed = set(target_diff.get("changed_paths") or [])
    missing = sorted(changed - receipt_files)
    if missing:
        return ["receipt missing target changed_files: " + ", ".join(missing)]
    return []


def request_target_footprint_policy(request, target):
    raw = ""
    if isinstance(request, dict):
        raw = str(
            request.get("target_footprint_policy")
            or request.get("footprint_policy")
            or ""
        ).strip()
    if raw in TARGET_FOOTPRINT_POLICIES:
        return raw
    if isinstance(target, dict) and target.get("explicit"):
        return "no_control_plane_files"
    return "repo_local_state_allowed"


def target_control_plane_path(rel):
    normalized = normalize_relative_path_text(str(rel or ""))
    if not normalized:
        return False
    parts = pathlib.PurePosixPath(normalized).parts
    if not parts:
        return False
    if parts[0] in CONTROL_PLANE_TARGET_DIRS:
        return True
    return normalized in CONTROL_PLANE_TARGET_FILES


def target_footprint_report(state, target_diff):
    contract = state.get("contract") if isinstance(state, dict) else {}
    target = state.get("target") if isinstance(state, dict) else {}
    policy = ""
    if isinstance(contract, dict):
        policy = str(contract.get("target_footprint_policy") or "").strip()
    if policy not in TARGET_FOOTPRINT_POLICIES:
        policy = "repo_local_state_allowed"
    changed_paths = sorted(
        str(path)
        for path in (target_diff.get("changed_paths") or [])
        if isinstance(path, str)
    )
    forbidden_changed = sorted(
        path for path in changed_paths
        if target_control_plane_path(path)
    )
    present = []
    blocking_present = []
    target_root = target.get("target_repo") if isinstance(target, dict) else ""
    if non_empty_string(target_root):
        root = pathlib.Path(target_root)
        for name in sorted(CONTROL_PLANE_TARGET_DIRS | CONTROL_PLANE_TARGET_FILES):
            try:
                if (root / name).exists():
                    present.append(name)
                    if name in CONTROL_PLANE_TARGET_DIRS:
                        blocking_present.append(name)
            except OSError:
                continue
    result = "target_footprint_passed"
    errors = []
    if policy == "no_control_plane_files" and forbidden_changed:
        result = "target_footprint_failed"
        errors.append(
            "controlled target changed Piloth/control-plane files: "
            + ", ".join(forbidden_changed)
        )
    if policy == "no_control_plane_files" and blocking_present:
        result = "target_footprint_failed"
        errors.append(
            "controlled target contains Piloth/control-plane directories: "
            + ", ".join(sorted(blocking_present))
        )
    return {
        "schema_version": 1,
        "result": result,
        "policy": policy,
        "changed_control_plane_paths": forbidden_changed,
        "present_control_plane_entries": present,
        "blocking_control_plane_entries": sorted(blocking_present),
        "errors": errors,
        "target_repo": target_root,
    }


def raw_edit_targets(hook_input):
    """Các path thô (chưa resolve) mà tool Edit/Write/MultiEdit sẽ ghi."""
    tool_input = (
        hook_input.get("tool_input")
        or hook_input.get("toolInput")
        or hook_input.get("input")
        or hook_input
    )
    raw_paths = []
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str):
                raw_paths.append(value)
        for key in ("files", "paths"):
            value = tool_input.get(key)
            if isinstance(value, list):
                raw_paths.extend(v for v in value if isinstance(v, str))
    return raw_paths


def claude_config_dir():
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env and env.strip():
        return pathlib.Path(env.strip()).expanduser()
    return pathlib.Path.home() / ".claude"


def is_harness_plan_path(raw):
    """True nếu raw trỏ vào thư mục plan của harness (~/.claude/plans hoặc
    $CLAUDE_CONFIG_DIR/plans). Plan file là artifact của Claude Code, không phải
    code repo — contract-before-edit gate không quản, cho ghi kể cả khi harness
    không truyền permission_mode=="plan"."""
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        target = pathlib.Path(raw.strip()).expanduser().resolve()
        plans = (claude_config_dir() / "plans").resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    return target == plans or plans in target.parents


def edit_paths_from_hook_input(hook_input):
    paths, errors = [], []
    for raw in raw_edit_targets(hook_input):
        rel, err = repo_relative_path(raw)
        if err:
            errors.append(err)
        elif rel not in paths:
            paths.append(rel)
    return paths, errors


def is_piloth_source_repo():
    return (
        (REPO_ROOT / ".claude-plugin" / "plugin.json").exists()
        and (REPO_ROOT / "scripts" / "stage.py").exists()
        and (REPO_ROOT / "scripts" / "build_manifest.py").exists()
    )


def is_source_installer_path(rel):
    return is_piloth_source_repo() and rel in SOURCE_INSTALLER_PATHS


def is_sensitive_runtime_path(rel):
    return rel in SENSITIVE_RUNTIME_PATHS or is_source_installer_path(rel)


def layer_for_path(rel):
    rel = normalize_relative_path_text(rel)
    if rel.startswith("pilothOS/rules/"):
        return "Rules"
    if rel.startswith("pilothOS/runtime/"):
        return "Runtime"
    if rel == "pilothOS/scripts/pilothos_installer.py" or is_source_installer_path(rel):
        return "Installer"
    if rel.startswith("pilothOS/scripts/") or rel.startswith("pilothOS/tools/"):
        return "Tools/Runtime"
    if rel.startswith("pilothOS/governance/"):
        return "Governance"
    if rel.startswith("pilothOS/evaluation/"):
        return "Evaluation"
    if rel.startswith("pilothOS/agents/"):
        return "Agents"
    if rel.startswith("pilothOS/agent-teams/"):
        return "Agent Teams"
    if rel.startswith("pilothOS/skills/"):
        return "Skills"
    if rel.startswith("pilothOS/memory/"):
        return "Memory"
    if rel.startswith("pilothOS/knowledge/"):
        return "Knowledge"
    if rel.startswith("adapters/") or rel.startswith("templates/") or rel.startswith("commands/"):
        return "Adapters"
    if rel.startswith("tests/") or rel.endswith(".test") or ".test." in rel:
        return "Tests"
    if rel.startswith("docs/") or rel.endswith(".md"):
        return "Docs"
    return "Consumer"


def path_parts(rel):
    return pathlib.PurePosixPath(rel.replace("\\", "/")).parts


def is_dependency_path(rel):
    return pathlib.PurePosixPath(rel).name in DEPENDENCY_FILE_NAMES


def is_ui_path(rel):
    rel = normalize_relative_path_text(rel)
    parts = path_parts(rel)
    suffix = pathlib.PurePosixPath(rel).suffix.lower()
    if "components" in parts or "ui" in parts:
        return True
    if rel.startswith(("app/", "pages/")):
        return True
    if rel.startswith("src/") and suffix in (".tsx", ".jsx"):
        return True
    return suffix in (".css", ".scss", ".html", ".htm")


def is_test_path(rel):
    layer = layer_for_path(rel)
    name = pathlib.PurePosixPath(rel).name.lower()
    return (
        layer == "Tests"
        or rel.startswith(("test/", "tests/", "__tests__/"))
        or ".test." in name
        or ".spec." in name
    )


def is_docs_path(rel):
    return layer_for_path(rel) == "Docs" or rel.startswith("docs/") or rel.endswith(".md")


def is_component_like_path(rel):
    rel = normalize_relative_path_text(rel)
    parts = path_parts(rel)
    suffix = pathlib.PurePosixPath(rel).suffix.lower()
    name = pathlib.PurePosixPath(rel).stem
    return (
        "components" in parts
        or (suffix in (".tsx", ".jsx", ".vue", ".svelte") and name[:1].isupper())
    )


def is_code_like_path(rel):
    suffix = pathlib.PurePosixPath(rel).suffix.lower()
    if is_test_path(rel) or is_docs_path(rel) or is_dependency_path(rel):
        return False
    return suffix in CODE_EXTENSIONS or layer_for_path(rel) not in ("Docs", "Tests")


def git_path_is_new(rel):
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", "--", rel],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        return out.returncode != 0 and (REPO_ROOT / rel).exists()
    except Exception:
        return False


GENERATED_WARNING_PREFIXES = (
    "dependency file changed:",
    "new component-like file added:",
    "UI file changed without design system evidence:",
    "code changed without test/evidence",
    "large delta requires reuse discipline:",
)


def ensure_diff_fact_fields(facts):
    facts.setdefault("changed_files", {})
    facts.setdefault("affected_layers", [])
    facts.setdefault("has_tests", False)
    facts.setdefault("has_docs", False)
    facts.setdefault("evidence_commands", [])
    facts.setdefault("warnings", [])
    facts.setdefault("new_files", [])
    facts.setdefault("new_files_count", 0)
    facts.setdefault("total_added", 0)
    facts.setdefault("total_deleted", 0)
    facts.setdefault("largest_file_delta", {"path": "", "changed_lines": 0})
    facts.setdefault("dependency_files_changed", [])
    facts.setdefault("ui_files_changed", [])
    facts.setdefault("test_files_changed", [])
    facts.setdefault("docs_files_changed", [])
    facts.setdefault("component_like_files_changed", [])


def generated_warnings_removed(warnings):
    kept = []
    for warning in warnings:
        text = str(warning)
        if not any(text.startswith(prefix) for prefix in GENERATED_WARNING_PREFIXES):
            kept.append(warning)
    return kept


def add_generated_warning(warnings, text):
    if text not in warnings:
        warnings.append(text)


def update_diff_fact_derived(facts, contract=None):
    ensure_diff_fact_fields(facts)
    changed = facts.get("changed_files", {})
    paths = sorted(changed)
    for rel, meta in changed.items():
        meta.setdefault("layer", layer_for_path(rel))
        meta.setdefault("added", 0)
        meta.setdefault("deleted", 0)
        meta.setdefault("changed_lines", int(meta.get("added", 0)) + int(meta.get("deleted", 0)))
        meta.setdefault("new_file", git_path_is_new(rel))

    facts["affected_layers"] = sorted({meta.get("layer") for meta in changed.values() if meta.get("layer")})
    facts["has_tests"] = any(is_test_path(p) for p in paths)
    facts["has_docs"] = any(is_docs_path(p) for p in paths)
    facts["new_files"] = sorted(p for p, meta in changed.items() if meta.get("new_file"))
    facts["new_files_count"] = len(facts["new_files"])
    facts["total_added"] = sum(int(meta.get("added", 0)) for meta in changed.values())
    facts["total_deleted"] = sum(int(meta.get("deleted", 0)) for meta in changed.values())
    if changed:
        largest_path, largest_meta = max(
            changed.items(), key=lambda item: int(item[1].get("changed_lines", 0))
        )
        facts["largest_file_delta"] = {
            "path": largest_path,
            "changed_lines": int(largest_meta.get("changed_lines", 0)),
        }
    else:
        facts["largest_file_delta"] = {"path": "", "changed_lines": 0}
    facts["dependency_files_changed"] = sorted(p for p in paths if is_dependency_path(p))
    facts["ui_files_changed"] = sorted(p for p in paths if is_ui_path(p))
    facts["test_files_changed"] = sorted(p for p in paths if is_test_path(p))
    facts["docs_files_changed"] = sorted(p for p in paths if is_docs_path(p))
    facts["component_like_files_changed"] = sorted(p for p in paths if is_component_like_path(p))

    warnings = generated_warnings_removed(facts.get("warnings", []))
    if facts["dependency_files_changed"]:
        add_generated_warning(
            warnings,
            "dependency file changed: " + ", ".join(facts["dependency_files_changed"]),
        )
    new_components = sorted(p for p in facts["component_like_files_changed"] if p in facts["new_files"])
    if new_components:
        add_generated_warning(
            warnings,
            "new component-like file added: " + ", ".join(new_components),
        )
    if facts["ui_files_changed"] and not contract_has_ui_design_system_evidence(contract):
        add_generated_warning(
            warnings,
            "UI file changed without design system evidence: " + ", ".join(facts["ui_files_changed"]),
        )
    code_changed = any(is_code_like_path(p) for p in paths)
    if code_changed and not facts["has_tests"] and not facts.get("evidence_commands"):
        add_generated_warning(warnings, "code changed without test/evidence")
    largest = facts.get("largest_file_delta", {})
    if int(largest.get("changed_lines", 0)) >= 250:
        add_generated_warning(
            warnings,
            f"large delta requires reuse discipline: {largest.get('path')} ({largest.get('changed_lines')} lines)",
        )
    facts["warnings"] = warnings
    return facts


def validate_task_contract(contract):
    errors = []
    if not isinstance(contract, dict):
        return ["contract must be a JSON object"]
    missing = sorted(CONTRACT_REQUIRED_FIELDS - set(contract))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    if "mode" in contract and str(contract.get("mode")) not in OS_MODES:
        errors.append("mode must be lean, standard, or strict")
    if "operational_preset" in contract and not valid_operational_preset(operational_preset(contract)):
        errors.append("operational_preset must be light, standard, or strict")
    if not isinstance(contract.get("task_scope"), str) or not contract.get("task_scope", "").strip():
        errors.append("task_scope must be a non-empty string")
    for field in ("affected_layers", "allowed_paths", "expected_evidence"):
        value = contract.get(field)
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
            errors.append(f"{field} must be a non-empty list of strings")
    out = contract.get("out_of_scope_paths")
    if not isinstance(out, list) or any(not isinstance(x, str) or not x.strip() for x in out):
        errors.append("out_of_scope_paths must be a list of strings")
    for field in ("allowed_paths", "out_of_scope_paths"):
        for pattern in contract.get(field, []):
            if not path_pattern_is_safe(pattern):
                errors.append(f"{field} contains unsafe pattern: {pattern}")
    if contract_requires_context_evidence(contract):
        if not non_empty_string(contract.get("consumer_scope")):
            errors.append("consumer_scope must be a non-empty string for code/runtime/rules/adapter changes")
        errors.extend(validate_object_list(
            contract.get("context_evidence"),
            "context_evidence",
            ("source", "reason", "finding"),
        ))
        errors.extend(validate_reuse_evidence(contract.get("reuse_evidence")))
        decision_limits = contract.get("decision_limits")
        if (not isinstance(decision_limits, list) or not decision_limits
                or any(not non_empty_string(x) for x in decision_limits)):
            errors.append("decision_limits must be a non-empty list of strings for code/runtime/rules/adapter changes")
        errors.extend(validate_asset_routing(contract.get("consumer_asset_routing")))
    else:
        if "context_evidence" in contract:
            errors.extend(validate_object_list(
                contract.get("context_evidence"),
                "context_evidence",
                ("source", "reason", "finding"),
            ))
        if "reuse_evidence" in contract:
            errors.extend(validate_reuse_evidence(contract.get("reuse_evidence")))
        if "consumer_asset_routing" in contract:
            errors.extend(validate_asset_routing(contract.get("consumer_asset_routing")))
    if contract_requires_ui_design_system_evidence(contract):
        errors.extend(validate_ui_design_system_evidence(contract.get("ui_design_system_evidence")))
    elif "ui_design_system_evidence" in contract:
        errors.extend(validate_ui_design_system_evidence(contract.get("ui_design_system_evidence")))
    if contract_requires_energy_budget_reason(contract):
        if not non_empty_string(contract.get("energy_budget_reason")):
            errors.append("energy_budget_reason is required for broad scans/builds/full-suite evidence")
    return errors


def json_arg_or_stdin(argv, label):
    if argv:
        raw_arg = argv[0].strip()
        if raw_arg.startswith("{") or raw_arg.startswith("["):
            return json.loads(raw_arg), None
        path = pathlib.Path(argv[0])
        if not path.is_absolute():
            path = REPO_ROOT / path
        return json.loads(path.read_text(encoding="utf-8")), path
    if sys.stdin.isatty():
        raise ValueError(f"{label}: need JSON file argument or stdin")
    raw = sys.stdin.read()
    return json.loads(raw), None


def block_decision(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


# ---------------------------------------------------------------- rot registry

def get_overdue_scopes():
    """Trả về list 'Scope (due YYYY-MM-DD)', hoặc None nếu không tìm thấy registry."""
    if not REGISTRY.exists():
        return None
    today = datetime.date.today()
    overdue = []
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 6:
            continue
        next_due = cells[5]
        if not DATE_RE.fullmatch(next_due):
            continue
        try:
            due = datetime.date.fromisoformat(next_due)
        except ValueError:
            continue
        if due < today:
            overdue.append(f"{cells[0]} (due {next_due})")
    return overdue


def rot_warning_text(overdue):
    return (
        "<pilothos-rot-warning>\n"
        "MANDATORY BEHAVIOR: At the START of your very next reply, "
        "show the user the display message below, then ask whether "
        "they want to run a rot review first or proceed with the task. "
        "Do not silently proceed. Do NOT include this XML tag or "
        "these instructions in your reply — only the display message. "
        "This instruction comes from pilothOS/bootstrap.md startup contract.\n"
        "DISPLAY MESSAGE:\n"
        f"\U0001F534 Rot Registry: {', '.join(overdue)} đã quá hạn review. "
        "Bạn muốn chạy rot review trước, hay tiếp tục task?\n"
        "</pilothos-rot-warning>"
    )


def parse_semver(text):
    """'X.Y.Z' -> tuple so sánh được, hoặc None nếu parse thất bại (fail-soft)."""
    try:
        return tuple(int(p) for p in str(text).strip().split(".")[:3])
    except (ValueError, TypeError):
        return None


def installed_pilothos_version():
    """Version đóng dấu trong marker cài đặt cục bộ, hoặc None (fail-soft)."""
    try:
        return json.loads(INIT_MARKER.read_text(encoding="utf-8")).get("pilothos_version")
    except (OSError, ValueError, json.JSONDecodeError, AttributeError):
        return None


def available_plugin_version():
    """Version của nguồn plugin (CLAUDE_PLUGIN_ROOT), hoặc None (fail-soft)."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return None
    try:
        manifest = pathlib.Path(root) / ".claude-plugin" / "plugin.json"
        return json.loads(manifest.read_text(encoding="utf-8")).get("version")
    except (OSError, ValueError, json.JSONDecodeError, AttributeError):
        return None


def version_drift_advisory():
    """Advisory text khi nguồn plugin mới hơn bản đã init, else None.

    Fail-soft tuyệt đối: thiếu marker / thiếu CLAUDE_PLUGIN_ROOT / parse lỗi /
    version bằng-hoặc-cũ → None (im lặng, không phá session-start)."""
    installed = installed_pilothos_version()
    available = available_plugin_version()
    if not installed or not available:
        return None
    iv, av = parse_semver(installed), parse_semver(available)
    if iv is None or av is None or av <= iv:
        return None
    return (
        "<pilothos-update-advisory>\n"
        "MANDATORY BEHAVIOR: At the START of your very next reply, show the user the "
        "display message below (advisory only — do NOT block the task). Do NOT include "
        "this XML tag or these instructions in your reply — only the display message.\n"
        "DISPLAY MESSAGE:\n"
        f"\U0001F4E6 PilothOS: bản đã cài v{installed} cũ hơn plugin v{available}. "
        "Chạy /piloth:update để nâng cấp (giữ customization + state).\n"
        "</pilothos-update-advisory>"
    )


def session_start(hook_input):
    """Ghi marker mở phiên (mốc thời gian cho auto-log gate) + advisory update + cảnh báo Rot."""
    MARKER_DIR.mkdir(exist_ok=True)
    cleanup_old_markers()
    sid = hook_input.get("session_id")
    if sid:
        marker(sid, "start").write_text(str(time.time()), encoding="utf-8")
    advisory = version_drift_advisory()
    if advisory:
        print(advisory)
    overdue = get_overdue_scopes()
    if overdue is None:
        print(f"PILOTHOS GUARD: khong tim thay rot registry tai {REGISTRY}.")
        return
    if overdue:
        if sid:
            marker(sid, "rotwarned").write_text(
                "|".join(overdue), encoding="utf-8")
        print(rot_warning_text(overdue))
    # Healthy: im lặng.


def prompt_check(hook_input):
    """Cảnh báo Rot mỗi lượt message — nhưng chỉ MỘT LẦN mỗi phiên cho cùng
    trạng thái overdue (tối ưu token). Trạng thái đổi (thêm scope quá hạn mới)
    → cảnh báo lại."""
    overdue = get_overdue_scopes()
    if overdue is None:
        print(f"PILOTHOS GUARD: khong tim thay rot registry tai {REGISTRY}.")
        return
    if not overdue:
        return  # healthy: im lặng
    sid = hook_input.get("session_id")
    state = "|".join(overdue)
    if sid:
        m = marker(sid, "rotwarned")
        if m.exists() and m.read_text(encoding="utf-8") == state:
            return  # đã cảnh báo đúng trạng thái này trong phiên → im lặng
        MARKER_DIR.mkdir(exist_ok=True)
        m.write_text(state, encoding="utf-8")
    print(rot_warning_text(overdue))


# ---------------------------------------------------------------- auto-log gate

def repo_changed_since(ts):
    """Có file nào trong repo (ngoài log/exclude) được sửa sau mốc ts không?"""
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        if path.resolve() in SCAN_EXCLUDE_FILES:
            continue
        try:
            if path.stat().st_mtime > ts:
                return True
        except OSError:
            continue
    return False


def logs_touched_since(ts):
    for log in (REVIEW_LOG, LESSONS):
        try:
            if log.exists() and log.stat().st_mtime > ts:
                return True
        except OSError:
            continue
    return False


def session_uncommitted_changes(ts):
    """File còn CHƯA commit (working tree/staged/untracked) và bị sửa sau mốc ts.

    Rỗng nghĩa là mọi thay đổi trong phiên đã được commit (hoặc revert) → coi như
    đã Deliver qua git. Giữ nguyên ngoại lệ review-log/lessons như repo_changed_since
    để việc auto-log không tự kích gate.
    """
    out = []
    for rel in git_changed_file_paths():
        path = REPO_ROOT / rel
        if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        try:
            if path.resolve() in SCAN_EXCLUDE_FILES:
                continue
            if path.is_file() and path.stat().st_mtime > ts:
                out.append(rel)
        except OSError:
            continue
    return sorted(out)


def stop_check(hook_input):
    """Deliver gate (hook Stop).

    Nếu phiên có thay đổi file CHƯA commit, kiểm tra hai phần máy móc:
    - auto-log gate: review-log/lessons-learned đã được cân nhắc.
    - deliver receipt gate: receipt có changed files/layers/evidence/result.

    Trong git repo, nếu mọi thay đổi của phiên đã được commit (hoặc revert) thì
    coi như đã Deliver qua git và bỏ qua toàn bộ gate. Ngoài git repo, giữ nguyên
    hành vi cũ (dựa mtime).

    stop_hook_active=true → đã block một lần rồi → luôn cho dừng (không loop).
    """
    if hook_input.get("stop_hook_active"):
        return  # đã qua một vòng gate → cho dừng
    sid = hook_input.get("session_id")
    if not sid:
        return  # không xác định được phiên (chạy tay) → không chặn
    m = marker(sid, "start")
    if not m.exists():
        return  # không có mốc phiên → không đủ dữ kiện để phán → cho dừng
    try:
        ts = float(m.read_text(encoding="utf-8"))
    except ValueError:
        return
    if not repo_changed_since(ts):
        return  # phiên chỉ đọc/hỏi đáp → không cần gate
    if is_git_repo() and not session_uncommitted_changes(ts):
        # Trong git repo: mọi thay đổi của phiên đã commit (hoặc revert) → đã
        # Deliver qua git. Miễn toàn bộ deliver gate (không đòi auto-log lẫn
        # receipt thủ công). Ngoài git repo, giữ nguyên hành vi mtime cũ.
        return
    reasons = []
    if not logs_touched_since(ts):
        reasons.append(
            "Auto-log missing: pilothOS/rot/review-log.md và "
            "pilothOS/memory/lessons-learned.md đều chưa được cập nhật. "
            "Append log phù hợp hoặc nêu rõ trong reply cuối: "
            "'Không có finding hoặc lesson cần ghi' kèm lý do."
        )
    contract, _ = load_task_contract(hook_input)
    facts = load_diff_facts(hook_input)
    receipt, receipt_path = load_deliver_receipt(hook_input)
    if receipt is None:
        reasons.append(
            "Deliver receipt missing: ghi receipt bằng "
            "`python3 pilothOS/scripts/pilothos_guard.py receipt-write <receipt.json>`. "
            "Receipt phải có changed_files, affected_layers, verification_command, result; "
            "nếu không test được thì thêm limitation."
        )
    else:
        receipt_errors = validate_deliver_receipt(receipt, contract, facts)
        if receipt_errors:
            reasons.append(
                f"Deliver receipt invalid ({receipt_path}): "
                + "; ".join(receipt_errors)
            )
    if not reasons:
        return
    print(json.dumps({
        "decision": "block",
        "reason": (
            "PILOTHOS DELIVER GATE: Phiên này có thay đổi file nhưng chưa đủ "
            "receipt/evidence để Deliver. " + " ".join(reasons)
        ),
    }, ensure_ascii=False))


# ---------------------------------------------------------------- installer

INIT_MARKER = PILOTHOS_DIR / ".initialized"
BACKUP_DIR = PILOTHOS_DIR / ".backup"
CORE_FILES = [PILOTHOS_DIR / "bootstrap.md", REGISTRY, CONSUMER_ASSETS,
              PILOTHOS_DIR / "PilothOS.md", REVIEW_LOG, LESSONS]
CONSUMER_ASSET_HINTS = ["package.json", "pyproject.toml", "go.mod", "Cargo.toml",
                        "pom.xml", "src", "app", "lib"]
# Adapter dirs do bản phân phối ship sẵn — chỉ là tài sản consumer khi chứa
# nội dung không thuộc PilothOS
ADAPTER_DIRS = [".claude", ".cursor", ".codex", ".antigravity"]
ADAPTER_CONFIGS = {
    ".claude": ("settings.json", "Claude adapter settings"),
    ".cursor": ("settings.json", "Cursor adapter settings"),
    ".codex": ("config.toml", "Codex adapter config"),
    ".antigravity": ("settings.json", "Antigravity adapter settings"),
}


def _non_pilothos_content(d):
    """File nào trong adapter dir KHÔNG thuộc bản phân phối PilothOS?"""
    known = ("pilothos", "piloth-team", "00-pilothos", "10-coding", "20-evidence",
             "30-layer", "settings.json", "config.toml", "README")
    found = []
    for f in d.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(REPO_ROOT))
        if not any(k in rel for k in known):
            found.append(rel)
    return found


def audit_cell(value):
    return str(value).replace("|", ";").replace("\n", " ").strip()


def add_audit_row(rows, seen, asset, typ, capability, owner="consumer",
                  risk="low", handling="index"):
    if asset in seen:
        return
    seen.add(asset)
    rows.append({
        "asset": asset,
        "type": typ,
        "capability": capability,
        "owner": owner,
        "risk": risk,
        "handling": handling,
    })


def classify_adapter_asset(rel):
    if rel.startswith(".claude/commands/"):
        return "command", "agent command", "medium", "route"
    return "doc", "consumer adapter file", "medium", "index"


def pilothos_owned_text(text):
    lowered = text.lower()
    return "pilothos" in lowered or "pilothos_guard.py" in lowered


def adapter_config_row(adir):
    spec = ADAPTER_CONFIGS.get(adir)
    if not spec:
        return None
    filename, capability = spec
    path = REPO_ROOT / adir / filename
    if not path.exists() or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    owner = "piloth" if pilothos_owned_text(text) else "consumer"
    handling = "index" if owner == "piloth" else "preserve"
    return path.relative_to(REPO_ROOT).as_posix(), capability, owner, handling


def package_script_assets(rows, seen):
    package_json = REPO_ROOT / "package.json"
    if not package_json.exists():
        return
    add_audit_row(rows, seen, "package.json", "tool",
                  "Node package manifest/scripts", risk="medium",
                  handling="route")
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        add_audit_row(rows, seen, "package.json:scripts", "command",
                      "package scripts (invalid JSON, needs review)",
                      risk="medium", handling="needs-judgment")
        return
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return
    for name, command in sorted(scripts.items()):
        if not isinstance(command, str):
            continue
        script_asset = f"package.json:scripts.{name}"
        lowered = name.lower()
        command_lower = command.lower()
        if "test" in lowered:
            add_audit_row(rows, seen, script_asset, "test-runner",
                          command, risk="low", handling="route")
        elif lowered in {"build", "compile"} or "build" in lowered:
            add_audit_row(rows, seen, script_asset, "build-runner",
                          command, risk="medium", handling="route")
        elif "lint" in lowered or "typecheck" in lowered or "check" in lowered:
            add_audit_row(rows, seen, script_asset, "command",
                          command, risk="low", handling="route")
        elif ("deploy" in lowered or "release" in lowered
              or command_looks_high_risk(command_lower)):
            add_audit_row(rows, seen, script_asset, "command",
                          command, risk="high", handling="wrap")
        else:
            add_audit_row(rows, seen, script_asset, "command",
                          command, risk="medium", handling="index")


def script_asset_kind(rel):
    lowered = rel.lower()
    if "test" in lowered:
        return "test-runner", "project test runner", "low"
    if "build" in lowered or "compile" in lowered:
        return "build-runner", "project build runner", "medium"
    if "lint" in lowered or "check" in lowered or "typecheck" in lowered:
        return "command", "project check command", "low"
    if "deploy" in lowered or "release" in lowered:
        return "command", "project release/deploy command", "high"
    return "command", "project script command", "medium"


def dynamic_script_assets(rows, seen):
    roots = [REPO_ROOT / "scripts", REPO_ROOT / "bin", REPO_ROOT / "tools"]
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name in IGNORE_NAMES:
                continue
            if path.suffix not in {".sh", ".py", ".js", ".mjs", ".ts"} and not os.access(path, os.X_OK):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            typ, capability, risk = script_asset_kind(rel)
            owner = "piloth" if layer_for_path(rel) == "Installer" else "consumer"
            add_audit_row(rows, seen, rel, typ, capability,
                          owner=owner, risk=risk,
                          handling="wrap" if risk == "high" else "route")
    tests_root = REPO_ROOT / "tests"
    if tests_root.exists() and tests_root.is_dir():
        for path in sorted(tests_root.rglob("run-tests.sh")):
            if path.is_file():
                rel = path.relative_to(REPO_ROOT).as_posix()
                add_audit_row(rows, seen, rel, "test-runner",
                              "project test runner", owner="piloth" if rel.startswith("tests/") else "consumer",
                              risk="low", handling="route")


def dynamic_agent_assets(rows, seen):
    skill_roots = [
        REPO_ROOT / ".agents" / "skills",
        REPO_ROOT / ".claude" / "skills",
        REPO_ROOT / ".codex" / "skills",
        REPO_ROOT / "skills",
    ]
    for root in skill_roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in sorted(p for p in root.iterdir() if p.is_dir()):
            rel = child.relative_to(REPO_ROOT).as_posix()
            owner = "piloth" if child.name.startswith("piloth") else "consumer"
            add_audit_row(rows, seen, rel, "skill", "agent skill",
                          owner=owner, risk="medium",
                          handling="index" if owner == "piloth" else "route")
    command_roots = [
        REPO_ROOT / ".agents" / "commands",
        REPO_ROOT / ".claude" / "commands",
        REPO_ROOT / ".codex" / "commands",
        REPO_ROOT / "commands",
    ]
    for root in command_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            owner = "piloth" if "piloth" in path.name.lower() else "consumer"
            add_audit_row(rows, seen, rel, "command", "agent command",
                          owner=owner, risk="medium",
                          handling="index" if owner == "piloth" else "route")
    agent_roots = [
        REPO_ROOT / ".agents" / "agents",
        REPO_ROOT / ".claude" / "agents",
        REPO_ROOT / "agents",
    ]
    for root in agent_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            add_audit_row(rows, seen, rel, "agent", "agent definition",
                          risk="medium", handling="index")
    specialist_roots = [
        REPO_ROOT / ".agents" / "specialists",
        REPO_ROOT / ".claude" / "specialists",
        REPO_ROOT / "specialists",
    ]
    for root in specialist_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            add_audit_row(rows, seen, rel, "specialist",
                          "explicit specialist definition",
                          risk="medium", handling="route")


def collect_consumer_asset_rows():
    rows, seen = [], set()

    for name in ("CLAUDE.md", "AGENTS.md"):
        path = REPO_ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            owner = "piloth" if "PilothOS" in text or "@pilothOS/bootstrap.md" in text else "consumer"
            handling = "preserve" if owner == "consumer" else "index"
            add_audit_row(rows, seen, name, "doc",
                          "agent instructions entry point", owner=owner,
                          risk="medium", handling=handling)

    for adir in ADAPTER_DIRS:
        d = REPO_ROOT / adir
        if not d.exists():
            continue
        extra = _non_pilothos_content(d)
        config = adapter_config_row(adir)
        adapter_owner = "consumer" if extra or (config and config[2] == "consumer") else "piloth"
        adapter_handling = "preserve" if adapter_owner == "consumer" else "index"
        adapter_capability = (
            "native agent adapter with consumer content"
            if adapter_owner == "consumer"
            else "native agent adapter bridge"
        )
        add_audit_row(rows, seen, adir, "tool",
                      adapter_capability, owner=adapter_owner,
                      risk="medium", handling=adapter_handling)
        if extra:
            for rel in extra[:20]:
                typ, capability, risk, handling = classify_adapter_asset(rel)
                add_audit_row(rows, seen, rel, typ,
                              capability, risk=risk,
                              handling=handling)
        if config:
            rel, capability, owner, handling = config
            add_audit_row(rows, seen, rel, "tool",
                          capability, owner=owner, risk="medium",
                          handling=handling)
        settings = d / "settings.json"
        if settings.exists():
            try:
                data = json.loads(settings.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                add_audit_row(rows, seen, f"{adir}/settings.json", "hook",
                              "adapter settings invalid JSON", risk="medium",
                              handling="needs-judgment")
                continue
            if isinstance(data, dict) and data.get("hooks"):
                add_audit_row(rows, seen, f"{adir}/settings.json:hooks", "hook",
                              "native hooks", risk="medium", handling="merge")
        skills_dir = d / "skills"
        if skills_dir.exists():
            for child in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
                rel = child.relative_to(REPO_ROOT).as_posix()
                owner = "piloth" if child.name.startswith("piloth") else "consumer"
                handling = "route" if owner == "consumer" else "index"
                add_audit_row(rows, seen, rel, "skill",
                              "agent skill", owner=owner,
                              risk="medium", handling=handling)

    for rel in (".mcp.json", "mcp.json", ".cursor/mcp.json", ".claude/mcp.json"):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "mcp",
                          "MCP/tool configuration", risk="medium",
                          handling="route")
    for rel in (".piloth/specialists.json", "piloth-specialists.json"):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "specialist",
                          "explicit consumer specialist registry",
                          owner="consumer", risk="medium", handling="route")

    for rel in ("scripts/test.sh", "scripts/test", "scripts/build.sh",
                "scripts/lint.sh", "Makefile"):
        if (REPO_ROOT / rel).exists():
            typ = "test-runner" if "test" in rel else "build-runner" if "build" in rel or rel == "Makefile" else "command"
            risk = "low" if typ == "test-runner" else "medium"
            add_audit_row(rows, seen, rel, typ,
                          "project script/runner", risk=risk,
                          handling="route")
    dynamic_script_assets(rows, seen)
    dynamic_agent_assets(rows, seen)

    # Piloth is also a first-class consumer of PilothOS. These rows let the
    # self-hosted repo route its own guard, installer, test, docs and runtime
    # assets through the same discovery path used for external consumers.
    for rel, capability in (
        ("pilothOS/scripts/pilothos_guard.py", "PilothOS guard/runtime CLI"),
        ("pilothOS/scripts/pilothos_installer.py", "PilothOS installer engine"),
        ("scripts/stage.py", "distribution staging tool"),
        ("scripts/build_manifest.py", "distribution manifest builder"),
    ):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "tool", capability,
                          owner="piloth", risk="medium", handling="route")

    for rel in (
        "tests/run_all.sh",
        "tests/evaluation/run-tests.sh",
        "tests/install/run-tests.sh",
        "tests/lifecycle/run-tests.sh",
        "tests/docs/run-tests.sh",
        "tests/engine/run-tests.sh",
    ):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "test-runner",
                          "PilothOS self-host test suite",
                          owner="piloth", risk="low", handling="route")

    for rel, capability in (
        ("docs", "Piloth user-facing documentation"),
        ("pilothOS/runtime", "PilothOS runtime contract docs"),
        ("pilothOS/rules", "PilothOS rule source of truth"),
        ("pilothOS/evaluation", "PilothOS quality gate docs"),
        ("pilothOS/agent-teams", "PilothOS team definitions"),
    ):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "doc", capability,
                          owner="piloth", risk="low", handling="index")

    package_script_assets(rows, seen)

    for rel in ("design-system", "docs/design-system.md", "tokens",
                "src/tokens", "components", "src/components", "ui", "src/ui"):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "design-system",
                          "UI components/tokens/patterns", risk="medium",
                          handling="route")

    for rel in ("CONTRIBUTING.md", "docs/conventions.md", ".editorconfig",
                ".prettierrc", ".prettierrc.json", "eslint.config.js",
                ".eslintrc", ".eslintrc.json", "tsconfig.json"):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "convention",
                          "project convention/config", risk="low",
                          handling="index")

    return sorted(rows, key=lambda r: r["asset"])


def audit_consumer_assets():
    rows = collect_consumer_asset_rows()
    print("| Asset | Type | Capability | Owner | Risk | Proposed Piloth Handling |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        print(
            "| {asset} | {type} | {capability} | {owner} | {risk} | {handling} |".format(
                asset=audit_cell(row["asset"]),
                type=audit_cell(row["type"]),
                capability=audit_cell(row["capability"]),
                owner=audit_cell(row["owner"]),
                risk=audit_cell(row["risk"]),
                handling=audit_cell(row["handling"]),
            )
        )
    if not rows:
        print("| _none detected_ | doc | no consumer asset signal | consumer | low | ignore |")


def registry_load_when(row):
    handling = row.get("handling")
    risk = row.get("risk")
    if handling in {"wrap", "needs-judgment"} or risk == "high":
        return "approval-required"
    if handling == "ignore":
        return "never-auto"
    return "task-routed"


def registry_health_check(row):
    asset = row.get("asset", "")
    typ = row.get("type", "")
    if asset.endswith(":hooks") or typ == "hook":
        return "settings JSON parses"
    if typ == "mcp":
        return "config exists; list tools succeeds"
    if asset.startswith("package.json:scripts."):
        return "package JSON parses"
    if typ in {"test-runner", "build-runner", "command"}:
        return "command exists or package script defined"
    return "path exists"


def registry_notes(row):
    handling = row.get("handling")
    if handling == "wrap":
        return "Route through approval/tool-control boundary"
    if handling == "merge":
        return "Merge by engine semantics; preserve consumer entries first"
    if handling == "preserve":
        return "Consumer-owned; do not move or overwrite"
    if handling == "needs-judgment":
        return "Stop for user/model judgment before changing behavior"
    return "Generated by audit-assets; confirm during brownfield audit"


def registry_consumer_assets():
    rows = collect_consumer_asset_rows()
    print("| Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes |")
    print("|---|---|---|---|---|---|---|---|---|")
    if not rows:
        print("| _none detected_ | doc | consumer | no consumer asset signal | N/A | low | never-auto | N/A | Nothing to route |")
        return
    for row in rows:
        print(
            "| {asset} | {type} | {owner} | {capability} | {config_path} | {risk} | {load_when} | {health_check} | {notes} |".format(
                asset=audit_cell(row["asset"]),
                type=audit_cell(row["type"]),
                owner=audit_cell(row["owner"]),
                capability=audit_cell(row["capability"]),
                config_path=audit_cell(row["asset"]),
                risk=audit_cell(row["risk"]),
                load_when=audit_cell(registry_load_when(row)),
                health_check=audit_cell(registry_health_check(row)),
                notes=audit_cell(registry_notes(row)),
            )
        )


def asset_id_for_row(row):
    return f"{row.get('type', 'asset')}:{stable_slug(row.get('asset', 'asset'))}"


def manifest_paths():
    manifest = PILOTHOS_DIR / "dist-manifest.json"
    data = load_json_file(manifest)
    if not isinstance(data, dict):
        return set()
    files = data.get("files")
    if not isinstance(files, list):
        return set()
    return {item.get("path") for item in files if isinstance(item, dict) and item.get("path")}


def normalize_asset_row(row):
    confidence = 0.95
    if row.get("handling") in {"needs-judgment", "wrap"}:
        confidence = 0.85
    if row.get("owner") == "consumer":
        confidence = min(confidence, 0.90)
    asset = row.get("asset", "")
    typ = row.get("type", "")
    signals = []
    if asset.startswith("package.json:scripts."):
        signals.append("package-script")
    if asset.endswith(":hooks") or typ == "hook":
        signals.append("hook-config")
    if typ == "mcp":
        signals.append("mcp-config")
    if typ == "design-system":
        signals.append("design-system-path")
    if typ in {"test-runner", "build-runner"}:
        signals.append("runner")
    if asset.startswith("pilothOS/") or row.get("owner") == "piloth":
        signals.append("piloth-owned")
    return {
        "id": asset_id_for_row(row),
        "asset": asset,
        "type": typ,
        "owner": row.get("owner", "consumer"),
        "capability": row.get("capability", ""),
        "config_path": asset,
        "risk": row.get("risk", "low"),
        "load_when": registry_load_when(row),
        "health_check": registry_health_check(row),
        "handling": row.get("handling", "index"),
        "detected_at": "repository-scan",
        "last_health": "unknown",
        "status": "unknown",
        "confidence": confidence,
        "detected_signals": signals or ["path"],
    }


def scanned_asset_rows():
    rows = [normalize_asset_row(row) for row in collect_consumer_asset_rows()]
    return sorted(rows, key=lambda row: (row["type"], row["asset"], row["id"]))


def asset_markdown(rows):
    lines = [
        "| Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Detected At | Last Health | Status | Confidence | Notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    if not rows:
        lines.append("| _none detected_ | doc | consumer | no asset signal | N/A | low | never-auto | N/A | repository-scan | unknown | unknown | 0.00 | Nothing to route |")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            "| {asset} | {type} | {owner} | {capability} | {config_path} | {risk} | {load_when} | {health_check} | {detected_at} | {last_health} | {status} | {confidence:.2f} | {notes} |".format(
                asset=audit_cell(row.get("asset", "")),
                type=audit_cell(row.get("type", "")),
                owner=audit_cell(row.get("owner", "")),
                capability=audit_cell(row.get("capability", "")),
                config_path=audit_cell(row.get("config_path", "")),
                risk=audit_cell(row.get("risk", "")),
                load_when=audit_cell(row.get("load_when", "")),
                health_check=audit_cell(row.get("health_check", "")),
                detected_at=audit_cell(row.get("detected_at", "")),
                last_health=audit_cell(row.get("last_health", "")),
                status=audit_cell(row.get("status", "")),
                confidence=float(row.get("confidence", 0.0)),
                notes=audit_cell(registry_notes(row)),
            )
        )
    return "\n".join(lines)


def asset_scan(argv):
    fmt = "json"
    args = list(argv)
    if "--format" in args:
        i = args.index("--format")
        if i + 1 >= len(args):
            json_print({"result": "asset_scan_rejected", "errors": ["--format requires json or md"]})
            return
        fmt = args[i + 1]
    for arg in args:
        if arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
    rows = scanned_asset_rows()
    if fmt == "md":
        print(asset_markdown(rows))
    elif fmt == "json":
        json_print({"result": "asset_scan", "assets": rows})
    else:
        json_print({"result": "asset_scan_rejected", "errors": ["--format must be json or md"]})


def asset_path_from_id(asset):
    if not isinstance(asset, str):
        return ""
    if asset.startswith("package.json:scripts."):
        return "package.json"
    if ":" in asset:
        return asset.split(":", 1)[0]
    return asset


def high_risk_health_requires_approval(row):
    if row.get("risk") != "high":
        return False
    if non_empty_string(os.environ.get("PILOTHOS_APPROVAL_EVIDENCE")):
        return False
    contract, _ = load_task_contract({})
    haystack = contract_tool_text(contract)
    return "approval" not in haystack


def health_for_asset(row):
    row = dict(row)
    asset = row.get("asset", "")
    status = "unknown"
    reason = "no deterministic low-risk health check available"
    if high_risk_health_requires_approval(row):
        status = "needs_approval"
        reason = "high-risk asset health requires active contract approval evidence"
    elif asset.startswith("package.json:scripts."):
        path = REPO_ROOT / "package.json"
        if not path.exists():
            status, reason = "missing", "package.json missing"
        else:
            data = load_json_file(path)
            script = asset.rsplit(".", 1)[-1]
            if not isinstance(data, dict):
                status, reason = "failed", "package.json does not parse"
            elif isinstance(data.get("scripts"), dict) and script in data["scripts"]:
                status, reason = "healthy", f"package script exists: {script}"
            else:
                status, reason = "missing", f"package script missing: {script}"
    else:
        path = REPO_ROOT / asset_path_from_id(asset)
        if path.exists():
            if path.suffix == ".json" or asset.endswith(":hooks") or row.get("type") == "mcp":
                target = path if path.is_file() else path / "settings.json"
                if target.exists() and target.is_file():
                    try:
                        json.loads(target.read_text(encoding="utf-8"))
                        status, reason = "healthy", f"JSON parses: {target.relative_to(REPO_ROOT).as_posix()}"
                    except json.JSONDecodeError as e:
                        status, reason = "failed", f"JSON parse failed: {e}"
                else:
                    status, reason = "healthy", "path exists"
            else:
                status, reason = "healthy", "path exists"
        else:
            status, reason = "missing", "path missing"

    manifest = manifest_paths()
    manifest_status = "not_applicable"
    if asset.startswith("pilothOS/") and manifest:
        manifest_status = "indexed" if (
            asset in manifest
            or any(str(item).startswith(asset.rstrip("/") + "/") for item in manifest)
        ) else "missing"
    if (
        status == "healthy"
        and asset.startswith("pilothOS/")
        and manifest
        and asset not in manifest
        and not any(str(item).startswith(asset.rstrip("/") + "/") for item in manifest)
    ):
        status = "stale"
        reason = "Piloth-owned asset is missing from dist-manifest.json"

    row["status"] = status
    row["last_health"] = "repository-scan"
    row["health_reason"] = reason
    row["manifest_status"] = manifest_status
    return row


def asset_health(argv):
    rows = scanned_asset_rows()
    by_id = {row["id"]: row for row in rows}
    by_asset = {row["asset"]: row for row in rows}
    target = argv[0] if argv else "--all"
    if target == "--all":
        json_print({
            "result": "asset_health",
            "assets": [health_for_asset(row) for row in rows],
        })
        return
    row = by_id.get(target) or by_asset.get(target)
    if not row:
        json_print({
            "result": "asset_health_rejected",
            "errors": [f"unknown asset: {target}"],
        })
        return
    json_print({"result": "asset_health", "asset": health_for_asset(row)})


def asset_sync(argv):
    source = None
    args = list(argv)
    if "--source" in args:
        i = args.index("--source")
        if i + 1 < len(args):
            source = args[i + 1]
    for arg in args:
        if arg.startswith("--source="):
            source = arg.split("=", 1)[1]
    if not source:
        json_print({"result": "asset_sync_rejected", "errors": ["--source scan.json is required"]})
        return
    path = pathlib.Path(source)
    if not path.is_absolute():
        path = REPO_ROOT / path
    data = load_json_file(path)
    if isinstance(data, dict):
        rows = data.get("assets")
    else:
        rows = data
    if not isinstance(rows, list):
        json_print({"result": "asset_sync_rejected", "errors": ["source must contain an assets array"]})
        return
    section = (
        ASSET_SYNC_START + "\n"
        + asset_markdown(rows) + "\n"
        + ASSET_SYNC_END
    )
    if CONSUMER_ASSETS.exists():
        text = CONSUMER_ASSETS.read_text(encoding="utf-8")
    else:
        text = "# Consumer Asset Registry\n\n"
    if ASSET_SYNC_START in text and ASSET_SYNC_END in text:
        pattern = re.compile(
            re.escape(ASSET_SYNC_START) + r".*?" + re.escape(ASSET_SYNC_END),
            re.S,
        )
        text = pattern.sub(section, text)
    else:
        text = text.rstrip() + "\n\n## Generated Registry\n\n" + section + "\n"
    CONSUMER_ASSETS.write_text(text, encoding="utf-8")
    json_print({
        "result": "asset_synced",
        "path": CONSUMER_ASSETS.relative_to(REPO_ROOT).as_posix(),
        "asset_count": len(rows),
        "preserved_manual_sections": True,
    })


def normalize_task_signal(value):
    raw = str(value or "").strip().lower()
    aliases = {
        "ui": "ui/component",
        "component": "ui/component",
        "backend": "api/backend",
        "api": "api/backend",
        "bug": "bug fix",
        "bugfix": "bug fix",
        "release": "release/deploy",
        "deploy": "release/deploy",
        "tool": "tool/mcp",
        "mcp": "tool/mcp",
        "n/a": "not_applicable",
        "none": "not_applicable",
    }
    return aliases.get(raw, raw)


# Context docs only needed once standard/strict evidence (quality gates,
# consumer-asset routing) actually runs. lean/micro tasks skip them to cut
# context tokens without losing the context needed to do the work correctly.
LEAN_DROPPED_CONTEXT = frozenset({
    "evaluation/quality-gates.md",
    "runtime/consumer-assets.md",
})
# lazy rot: lean/micro skip loading the full rot registry table and rely on the
# compact `rot-status` command instead (it only surfaces overdue scopes).
LEAN_DROPPED_BOOTSTRAP = frozenset({
    "rot/registry.md",
})
# micro (throwaway / pass-through work) additionally skips the Constitution — a
# script with no architecture impact does not need the full layer contract.
MICRO_DROPPED_BOOTSTRAP = LEAN_DROPPED_BOOTSTRAP | frozenset({"PilothOS.md"})


def context_mode_from_payload(payload):
    """micro | lean | standard | strict from payload.mode; default standard."""
    raw = str((payload or {}).get("mode", "")).strip().lower()
    if raw == "micro":
        return "micro"
    if raw in ("lean", "light"):
        return "lean"
    if raw == "strict":
        return "strict"
    return "standard"


def apply_context_mode(files, mode):
    """Drop standard-only context docs for lean/micro; keep order otherwise."""
    if mode in ("lean", "micro"):
        return [f for f in files if f not in LEAN_DROPPED_CONTEXT]
    return list(files)


def apply_bootstrap_mode(files, mode):
    """lean uses lazy rot; micro also skips the Constitution."""
    if mode == "micro":
        return [f for f in files if f not in MICRO_DROPPED_BOOTSTRAP]
    if mode == "lean":
        return [f for f in files if f not in LEAN_DROPPED_BOOTSTRAP]
    return list(files)


def route_task_asset_views(detected, route):
    """(detected_assets, consumer_asset_routing, context_evidence) for one route.

    Three views over the same asset set, kept together because they are derived
    from the same per-asset health lookup. Only the last two are contract shapes
    (validated on contract/receipt); `detected_assets` is a plain inventory view.
    """
    asset_rows = []
    routing = []
    context_evidence = []
    for row in detected:
        load_when = registry_load_when(row)
        health = health_for_asset(normalize_asset_row(row))
        health_status = health.get("status")
        # `reason` stays a non-empty string (the contract validator requires it),
        # but it should not restate what the entry already carries structurally:
        # the row has task_signal and asset_type, so the asset PATH is the only
        # new information — and it is load-bearing, because a routing entry has
        # no `asset` field to identify which asset it decided about.
        if health_status == "healthy":
            decision = "approval_required" if load_when == "approval-required" else "loaded"
            routing_reason = f"matched {row['asset']}"
        elif health_status == "needs_approval":
            decision = "approval_required"
            routing_reason = f"{row['asset']}: approval required ({health.get('health_reason')})"
        else:
            decision = "skipped"
            routing_reason = f"{row['asset']}: health {health_status} ({health.get('health_reason')})"
        # Inventory view, not a contract shape: nothing validates it and no doc
        # specifies it. `health_reason` mostly restated the asset path, and
        # `handling` was almost always "index" — both are available from
        # asset-scan / asset-health when the detail is actually wanted.
        asset_rows.append({
            "asset": row["asset"],
            "type": row["type"],
            "risk": row["risk"],
            "load_when": load_when,
            "health_status": health_status,
        })
        routing.append({
            "task_signal": route["task_signal"],
            "asset_type": row["type"],
            "decision": decision,
            "reason": routing_reason,
        })
        context_evidence.append({
            "source": row["asset"],
            # `source` already names the asset and the paired routing entry
            # already names the signal — the asset type is what this adds.
            "reason": f"routed as {row['type']}",
            "finding": f"{row['capability']} (health: {health_status})",
        })
    if not routing:
        routing.append({
            "task_signal": route["task_signal"],
            "asset_type": "not_applicable",
            "decision": "not_applicable",
            "reason": "no matching consumer asset detected by deterministic audit",
        })
        context_evidence.append({
            "source": "runtime/consumer-assets.md",
            "reason": f"{route['task_signal']} routing lookup",
            "finding": "no matching consumer asset detected by deterministic audit",
        })
    return asset_rows, routing, context_evidence


def route_task_payload(payload):
    if not isinstance(payload, dict):
        return {"result": "route_rejected", "errors": ["route payload must be a JSON object"]}
    key = normalize_task_signal(payload.get("task_signal"))
    route = TASK_SIGNAL_ROUTES.get(key)
    if not route:
        return {
            "result": "route_rejected",
            "errors": [
                "task_signal must be one of: "
                + ", ".join(sorted(r["task_signal"] for r in TASK_SIGNAL_ROUTES.values()))
            ],
        }
    asset_types = set(route["asset_types"])
    all_rows = collect_consumer_asset_rows()
    detected = [
        row for row in all_rows
        if row.get("type") in asset_types
    ]
    # Receipt guidance, not a validated contract shape. The rule is the same for
    # every row, so it is stated once as `skipped_reason` instead of repeated per
    # asset — the old per-row `reason`/`decision`/`risk` restated the row's own
    # type plus the response's task_signal, once per asset.
    skipped_assets = [
        {"asset": row["asset"], "type": row["type"]}
        for row in all_rows
        if row.get("type") not in asset_types
    ]
    asset_rows, routing, context_evidence = route_task_asset_views(detected, route)

    mode = context_mode_from_payload(payload)
    index_first = apply_context_mode(
        ["runtime/consumer-assets.md", "runtime/context-loading.md"], mode)
    context_layers = apply_context_mode(list(route["context_layers"]), mode)
    result = {
        "result": "route_suggested",
        "task_signal": route["task_signal"],
        "context_mode": mode,
        "load_policy": route["load_policy"],
        "index_first": index_first,
        "context_layers": context_layers,
        "inspect_asset_types": list(route["asset_types"]),
        "detected_assets": asset_rows,
        "skipped_assets": skipped_assets,
        "skipped_reason": (
            f"asset type is not routed for {route['task_signal']}"
            if skipped_assets else ""
        ),
        "context_evidence": context_evidence,
        "consumer_asset_routing": routing,
    }
    return route_task_attach_evidence_router(result, payload)


def route_task_attach_evidence_router(result, payload):
    """Add the canonical decision without changing any V1 wrapper field."""
    if payload.get("_router_compat_only") is True:
        return result
    router_request = dict(payload)
    router_request.setdefault("intent", payload.get("task_scope") or "")
    # Digest, not the full decision: this wrapper is a routing hint, and the full
    # blob was 5.8 KB of the 20 KB route-task printed. Callers that need all of
    # it call evidence-route --verbose.
    result["evidence_router"] = evidence_route_digest(
        evidence_route_payload(router_request),
    )
    return result


def route_task(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "route-task")
    except Exception as e:
        json_print({"result": "route_rejected", "errors": [str(e)]})
        return
    json_print(route_task_payload(payload))
# --------------------------------------------------------- context budget

# The kernel files bootstrap.md prescribes as always-loaded before any task.
BOOTSTRAP_CONTEXT_FILES = (
    "bootstrap.md",
    "PilothOS.md",
    "rules/index.md",
    "runtime/index.md",
    "rot/registry.md",
)


def kernel_file_bytes(rel):
    """Byte size of a kernel-relative file, or 0 when it does not exist."""
    try:
        return (PILOTHOS_DIR / rel).stat().st_size
    except OSError:
        return 0


def estimate_context_tokens(num_bytes):
    """Rough context-token estimate (~4 bytes/token). Diagnostic only.

    This is a ``context_load`` footprint metric, NOT ``llm_usage`` telemetry:
    per energy-token-policy.md it measures how much kernel text a task pulls
    into context and cannot on its own back a "cheaper" claim.
    """
    return (num_bytes + 3) // 4


def full_kernel_footprint():
    """(file_count, total_bytes) of every kernel markdown doc — the load-all ceiling."""
    total = 0
    files = 0
    for path in PILOTHOS_DIR.rglob("*.md"):
        try:
            total += path.stat().st_size
            files += 1
        except OSError:
            continue
    return files, total


# Docs that inflate the full-kernel ceiling without ever being routable context:
# skills/ payloads are only opened while that skill executes, and README/
# VALIDATION document the kernel to humans instead of instructing a task. Kept
# out of the honest denominator so the savings figure is not flattered by text a
# routed task could never have loaded.
NON_ROUTABLE_KERNEL = ("README.md", "VALIDATION.md", "CHANGELOG.md")


def routable_kernel_footprint():
    """(file_count, total_bytes) of the kernel docs a routed task could load."""
    total = 0
    files = 0
    for path in PILOTHOS_DIR.rglob("*.md"):
        rel = path.relative_to(PILOTHOS_DIR)
        if rel.parts[0] == "skills" or rel.as_posix() in NON_ROUTABLE_KERNEL:
            continue
        try:
            total += path.stat().st_size
            files += 1
        except OSError:
            continue
    return files, total


def context_budget_payload(payload):
    """Measure the deterministic context footprint of a routed task.

    Reuses route_task_payload so the measured set is exactly what routing would
    load: the bootstrap set plus the routed index/context layers. Reports the
    footprint against the full-kernel ceiling so progressive loading's token
    saving is an evidence number instead of a claim.
    """
    if not isinstance(payload, dict):
        return {
            "result": "context_budget_rejected",
            "errors": ["context-budget payload must be a JSON object"],
        }

    mode = context_mode_from_payload(payload)
    bootstrap = apply_bootstrap_mode(BOOTSTRAP_CONTEXT_FILES, mode)
    routed = []
    routed_ok = False
    if payload.get("task_signal"):
        route = route_task_payload(payload)
        routed_ok = route.get("result") == "route_suggested"
        if routed_ok:
            routed = list(route.get("index_first", [])) + list(route.get("context_layers", []))

    loaded = []
    seen = set()
    for rel in bootstrap + routed:
        if rel not in seen:
            seen.add(rel)
            loaded.append(rel)

    loaded_detail = [{"file": rel, "bytes": kernel_file_bytes(rel)} for rel in loaded]
    loaded_bytes = sum(item["bytes"] for item in loaded_detail)
    bootstrap_bytes = sum(kernel_file_bytes(rel) for rel in bootstrap)

    kernel_files, kernel_bytes = full_kernel_footprint()
    saved_bytes = max(kernel_bytes - loaded_bytes, 0)
    savings_pct = round(saved_bytes / kernel_bytes * 100, 1) if kernel_bytes else 0.0
    routable_files, routable_bytes = routable_kernel_footprint()
    routable_savings_pct = (
        round(max(routable_bytes - loaded_bytes, 0) / routable_bytes * 100, 1)
        if routable_bytes else 0.0
    )

    return {
        "result": "context_budget",
        "metric": "context_load",
        "note": "kernel context footprint (bytes/estimated tokens); not llm_usage telemetry",
        "task_signal": payload.get("task_signal") or "not_routed",
        "context_mode": context_mode_from_payload(payload),
        "routed": routed_ok,
        "loaded_files": loaded_detail,
        "loaded_count": len(loaded_detail),
        "loaded_bytes": loaded_bytes,
        "loaded_tokens_est": estimate_context_tokens(loaded_bytes),
        "bootstrap_bytes": bootstrap_bytes,
        "bootstrap_tokens_est": estimate_context_tokens(bootstrap_bytes),
        "full_kernel_files": kernel_files,
        "full_kernel_bytes": kernel_bytes,
        "full_kernel_tokens_est": estimate_context_tokens(kernel_bytes),
        "saved_bytes_vs_full_kernel": saved_bytes,
        "savings_pct_vs_full_kernel": savings_pct,
        # The honest comparison: routable docs only. Lower than the full-kernel
        # figure by design — quote this one when claiming a saving.
        "routable_kernel_files": routable_files,
        "routable_kernel_bytes": routable_bytes,
        "routable_kernel_tokens_est": estimate_context_tokens(routable_bytes),
        "savings_pct_vs_routable_kernel": routable_savings_pct,
    }


def context_budget(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "context-budget")
    except Exception as e:
        json_print({"result": "context_budget_rejected", "errors": [str(e)]})
        return
    json_print(context_budget_payload(payload))


# --------------------------------------------------------- payload budget

# The read-only commands a routed task actually calls, with the smallest
# realistic argument for each. Their JSON lands in the agent's context, so it
# costs tokens exactly like a loaded file — and context-budget never saw it.
PER_TASK_PAYLOAD_PROBES = (
    ("route-task", lambda signal: route_task_payload({"task_signal": signal})),
    ("rot-status", lambda signal: rot_status_payload()),
    ("codebase-status", lambda signal: codebase_status_payload()),
    ("adapter-capabilities", lambda signal: adapter_capabilities_payload({})),
    ("evidence-route", lambda signal: evidence_route_digest(
        evidence_route_payload({
            "task_signal": signal,
            "task_type": "code",
            "scope": "narrow",
        }),
    )),
)


def printed_payload_bytes(payload):
    """Bytes a payload occupies once json_print has written it."""
    return len(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    ) + 1


def payload_budget_payload(payload=None):
    """Per-command tool-output footprint for one routed task.

    Sibling of context_budget: that one measures the kernel text a task pulls
    into context, this one measures the JSON the task prints back into it. Both
    are ~4 bytes/token estimates and neither is llm_usage telemetry.
    """
    payload = payload if isinstance(payload, dict) else {}
    signal = str(payload.get("task_signal") or "bug fix")
    commands = []
    for name, probe in PER_TASK_PAYLOAD_PROBES:
        try:
            num_bytes = printed_payload_bytes(probe(signal))
        except Exception as e:
            # A broken probe must degrade the meter, never break the caller.
            commands.append({"command": name, "error": str(e)})
            continue
        commands.append({
            "command": name,
            "bytes": num_bytes,
            "tokens_est": estimate_context_tokens(num_bytes),
        })
    total = sum(item.get("bytes", 0) for item in commands)
    return {
        "result": "payload_budget",
        "metric": "tool_output",
        "note": "per-command output footprint (bytes/estimated tokens); not llm_usage telemetry",
        "task_signal": signal,
        "commands": commands,
        "total_bytes": total,
        "total_tokens_est": estimate_context_tokens(total),
    }


def payload_budget(argv):
    payload = {}
    if argv:
        try:
            payload, _ = json_arg_or_stdin(argv, "payload-budget")
        except Exception as e:
            json_print({"result": "payload_budget_rejected", "errors": [str(e)]})
            return
    json_print(payload_budget_payload(payload))


def rot_status_payload():
    """Compact rot signal for lazy loading: surface overdue scopes only.

    lean/micro tasks call this instead of loading the full rot registry table,
    saving context tokens when the repo is healthy (the common case).
    """
    overdue = get_overdue_scopes()
    if overdue is None:
        return {"result": "rot_status", "healthy": None, "overdue": [],
                "overdue_count": 0, "note": "registry not found"}
    return {"result": "rot_status", "healthy": not overdue, "overdue": overdue,
            "overdue_count": len(overdue),
            "note": "healthy" if not overdue else f"{len(overdue)} scope(s) overdue"}


def rot_status():
    json_print(rot_status_payload())


# ------------------------------------------------ codebase intelligence

# This stdlib reference engine locks Piloth's adapter-neutral contract. The
# maintained native fork can replace indexing/query execution behind the same
# SQLite/JSON boundary without moving orchestration into adapters.
CODEBASE_SCHEMA_VERSION = 2
CODEBASE_CONTRACT_VERSION = 1
CODEBASE_ENGINE_VERSION = 1
CODEBASE_DEFAULT_MAX_FILES = 50000
CODEBASE_DEFAULT_MAX_TOTAL_BYTES = 512 * 1024 * 1024
CODEBASE_MAX_FILE_BYTES = 2 * 1024 * 1024
CODEBASE_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", "node_modules",
    "vendor", "dist", "build", ".next", ".turbo", "coverage",
}
CODEBASE_GENERATED_MARKERS = (
    "generated file", "do not edit", "auto-generated", "autogenerated",
    "code generated",
)
CODEBASE_LANGUAGES = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin", ".c": "C", ".h": "C/C++",
    ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++",
    ".cs": "C#", ".php": "PHP", ".rb": "Ruby", ".swift": "Swift",
    ".scala": "Scala", ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".sql": "SQL", ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".vue": "Vue", ".svelte": "Svelte", ".dart": "Dart", ".ex": "Elixir",
    ".exs": "Elixir", ".erl": "Erlang", ".hrl": "Erlang", ".hs": "Haskell",
    ".lua": "Lua", ".r": "R", ".R": "R", ".m": "Objective-C/MATLAB",
    ".mm": "Objective-C++", ".pl": "Perl", ".pm": "Perl", ".fs": "F#",
    ".fsx": "F#", ".clj": "Clojure", ".cljs": "Clojure", ".zig": "Zig",
    ".sol": "Solidity", ".tf": "HCL", ".proto": "Protobuf", ".graphql": "GraphQL",
    ".gql": "GraphQL", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".json": "JSON", ".xml": "XML", ".md": "Markdown", ".rst": "reStructuredText",
}


def codebase_index_paths():
    """Resolve state paths dynamically so controlled-target tests can rebind roots."""
    state_dir = PILOTHOS_DIR / "memory" / "state" / "codebase-index"
    return state_dir, state_dir / "index.sqlite3"


def codebase_safe_index_paths():
    state_dir, db_path = codebase_index_paths()
    try:
        root = REPO_ROOT.resolve()
        if state_dir.is_symlink() or db_path.is_symlink():
            return None, None, "codebase index state must not use symlinks"
        resolved_parent = state_dir.parent.resolve()
        if os.path.commonpath((str(root), str(resolved_parent))) != str(root):
            return None, None, "codebase index state escapes repository root"
        if state_dir.exists():
            resolved_state = state_dir.resolve()
            if os.path.commonpath((str(root), str(resolved_state))) != str(root):
                return None, None, "codebase index state escapes repository root"
    except (OSError, ValueError) as exc:
        return None, None, f"cannot validate codebase index state: {exc}"
    return state_dir, db_path, None


def codebase_repo(payload):
    raw = str((payload or {}).get("repo_path") or REPO_ROOT)
    try:
        requested = pathlib.Path(raw).expanduser().resolve()
        controlled = REPO_ROOT.resolve()
    except OSError as exc:
        return None, f"cannot resolve repo_path: {exc}"
    if requested != controlled:
        return None, "repo_path must be the Piloth-controlled consumer repository"
    if not requested.is_dir():
        return None, "repo_path is not a directory"
    return requested, None


def codebase_git(root, *args, timeout=10):
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def codebase_git_state(root):
    head_run = codebase_git(root, "rev-parse", "HEAD")
    head = head_run.stdout.strip() if head_run and head_run.returncode == 0 else ""
    status_run = codebase_git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if not status_run or status_run.returncode != 0:
        return {"git": False, "head": "", "worktree": "", "dirty_paths": []}
    raw = status_run.stdout
    dirty = []
    for item in raw.split("\0"):
        if len(item) >= 4:
            rel = item[3:].strip()
            if rel and " -> " in rel:
                rel = rel.rsplit(" -> ", 1)[-1]
            if rel:
                dirty.append(rel)
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace"))
    for rel in sorted(set(dirty)):
        path = root / rel
        try:
            if path.is_file() and not path.is_symlink():
                digest.update(rel.encode("utf-8"))
                digest.update(hashlib.sha256(path.read_bytes()).digest())
        except OSError:
            digest.update(f"{rel}:missing".encode("utf-8"))
    return {
        "git": True,
        "head": head,
        "worktree": digest.hexdigest(),
        "dirty_paths": sorted(set(dirty)),
    }


def codebase_fallback_paths(root):
    paths = []
    state_dir, _ = codebase_index_paths()
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        current_path = pathlib.Path(current)
        dirs[:] = sorted(
            name for name in dirs
            if name not in CODEBASE_SKIP_DIRS
            and not (current_path / name).is_symlink()
        )
        for name in sorted(names):
            path = current_path / name
            try:
                if path.is_symlink() or state_dir in path.parents:
                    continue
                paths.append(path.relative_to(root).as_posix())
            except (OSError, ValueError):
                continue
    return paths


def codebase_discover_paths(root):
    tracked = codebase_git(
        root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    if tracked and tracked.returncode == 0:
        candidates = sorted(set(filter(None, tracked.stdout.split("\0"))))
    else:
        candidates = codebase_fallback_paths(root)
    state_rel = "pilothOS/memory/state/codebase-index/"
    paths = []
    for rel in candidates:
        if rel.startswith(state_rel):
            continue
        parts = pathlib.PurePosixPath(rel).parts
        if any(part in CODEBASE_SKIP_DIRS for part in parts[:-1]):
            continue
        paths.append(rel)
    return paths


def codebase_generated_source(data):
    header = data[:16384].decode("utf-8", errors="ignore").lower()
    return any(marker in header for marker in CODEBASE_GENERATED_MARKERS)


def codebase_file_record(root, rel):
    path = root / rel
    try:
        resolved = path.resolve()
        if os.path.commonpath((str(root), str(resolved))) != str(root):
            return None, ("excluded", "path escapes repository root")
        if path.is_symlink() or not path.is_file():
            return None, ("excluded", "symlink or non-file")
        stat = path.stat()
        if stat.st_size > CODEBASE_MAX_FILE_BYTES:
            return None, ("skipped", f"file exceeds {CODEBASE_MAX_FILE_BYTES} bytes")
        data = path.read_bytes()
    except OSError as exc:
        return None, ("skipped", f"read failed: {exc}")
    if b"\0" in data[:8192]:
        return None, ("excluded", "binary content")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    suffix = path.suffix
    language = CODEBASE_LANGUAGES.get(suffix, "Text")
    return {
        "path": rel,
        "language": language,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": hashlib.sha256(data).hexdigest(),
        "generated": codebase_generated_source(data),
        "text": text,
    }, None


def codebase_module_name(rel):
    path = pathlib.PurePosixPath(rel)
    without_suffix = str(path.with_suffix("")) if path.suffix else str(path)
    return without_suffix.replace("/", ".").replace("-", "_")


def codebase_call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def codebase_signature(source_lines, node):
    if node.lineno <= 0 or node.lineno > len(source_lines):
        return ""
    line = source_lines[node.lineno - 1].strip()
    return line[:500]


class CodebasePythonVisitor(ast.NodeVisitor):
    def __init__(self, module, source):
        self.module = module
        self.lines = source.splitlines()
        self.scope = []
        self.symbols = []
        self.calls = []
        self.imports = []

    def current_qn(self):
        return ".".join([self.module, *self.scope])

    def record_definition(self, node, kind):
        qn = ".".join([self.module, *self.scope, node.name])
        self.symbols.append({
            "kind": kind,
            "name": node.name,
            "qualified_name": qn,
            "start_line": node.lineno,
            "end_line": getattr(node, "end_lineno", node.lineno),
            "signature": codebase_signature(self.lines, node),
            "body_hash": hashlib.sha256(
                ast.dump(node, annotate_fields=True, include_attributes=False).encode("utf-8")
            ).hexdigest(),
        })
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_ClassDef(self, node):
        self.record_definition(node, "Class")

    def visit_FunctionDef(self, node):
        self.record_definition(node, "Function" if not self.scope else "Method")

    def visit_AsyncFunctionDef(self, node):
        self.record_definition(node, "Function" if not self.scope else "Method")

    def visit_Call(self, node):
        callee = codebase_call_name(node.func)
        if callee:
            self.calls.append({
                "caller_qn": self.current_qn(),
                "callee": callee,
                "line": getattr(node, "lineno", 0),
            })
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.append((alias.name, alias.asname or "", node.lineno))

    def visit_ImportFrom(self, node):
        module = node.module or ""
        for alias in node.names:
            target = f"{module}.{alias.name}".strip(".")
            self.imports.append((target, alias.asname or alias.name, node.lineno))


def codebase_parse_record(record):
    module = codebase_module_name(record["path"])
    module_symbol = {
        "kind": "Module",
        "name": pathlib.PurePosixPath(record["path"]).name,
        "qualified_name": module,
        "start_line": 1,
        "end_line": max(len(record["text"].splitlines()), 1),
        "signature": "",
        "body_hash": "",
    }
    if record["language"] != "Python":
        return [module_symbol], [], [], ("shallow", "no deep language adapter in reference engine")
    try:
        tree = ast.parse(record["text"], filename=record["path"])
    except (SyntaxError, ValueError) as exc:
        detail = f"{type(exc).__name__} at line {getattr(exc, 'lineno', 0) or 0}"
        return [module_symbol], [], [], ("partial", detail)
    visitor = CodebasePythonVisitor(module, record["text"])
    visitor.visit(tree)
    return [module_symbol, *visitor.symbols], visitor.calls, visitor.imports, ("deep", "")


def codebase_create_schema(db):
    db.executescript("""
        PRAGMA journal_mode=OFF;
        PRAGMA synchronous=OFF;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE files (
            id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, language TEXT NOT NULL,
            size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, sha256 TEXT NOT NULL,
            is_generated INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE coverage (
            path TEXT PRIMARY KEY, status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE symbols (
            id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, kind TEXT NOT NULL,
            name TEXT NOT NULL, qualified_name TEXT NOT NULL,
            start_line INTEGER NOT NULL, end_line INTEGER NOT NULL,
            signature TEXT NOT NULL DEFAULT '', body_hash TEXT NOT NULL DEFAULT '',
            is_generated INTEGER NOT NULL DEFAULT 0, canonical_symbol_id INTEGER
        );
        CREATE TABLE edges (
            id INTEGER PRIMARY KEY, source_symbol_id INTEGER NOT NULL,
            target_symbol_id INTEGER NOT NULL, type TEXT NOT NULL,
            confidence REAL NOT NULL, evidence TEXT NOT NULL DEFAULT '',
            UNIQUE(source_symbol_id, target_symbol_id, type)
        );
        CREATE TABLE raw_calls (
            caller_qn TEXT NOT NULL, callee TEXT NOT NULL, line INTEGER NOT NULL
        );
        CREATE TABLE imports (
            file_id INTEGER NOT NULL, module TEXT NOT NULL,
            alias TEXT NOT NULL DEFAULT '', line INTEGER NOT NULL
        );
        CREATE INDEX symbols_name ON symbols(name);
        CREATE INDEX symbols_qn ON symbols(qualified_name);
        CREATE INDEX edges_source ON edges(source_symbol_id, type);
        CREATE INDEX edges_target ON edges(target_symbol_id, type);
    """)


def codebase_insert_record(db, record, symbols, calls, imports, coverage):
    cursor = db.execute(
        "INSERT INTO files(path,language,size,mtime_ns,sha256,is_generated) VALUES(?,?,?,?,?,?)",
        (record["path"], record["language"], record["size"], record["mtime_ns"],
         record["sha256"], int(record["generated"])),
    )
    file_id = cursor.lastrowid
    module_id = None
    for symbol in symbols:
        inserted = db.execute(
            """INSERT INTO symbols(
                file_id,kind,name,qualified_name,start_line,end_line,signature,body_hash,is_generated
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (file_id, symbol["kind"], symbol["name"], symbol["qualified_name"],
             symbol["start_line"], symbol["end_line"], symbol["signature"],
             symbol["body_hash"], int(record["generated"])),
        ).lastrowid
        if symbol["kind"] == "Module":
            module_id = inserted
        elif module_id:
            db.execute(
                "INSERT OR IGNORE INTO edges VALUES(NULL,?,?,?,?,?)",
                (module_id, inserted, "DEFINES", 1.0, record["path"]),
            )
    db.executemany(
        "INSERT INTO raw_calls(caller_qn,callee,line) VALUES(?,?,?)",
        [(call["caller_qn"], call["callee"], call["line"]) for call in calls],
    )
    db.executemany(
        "INSERT INTO imports(file_id,module,alias,line) VALUES(?,?,?,?)",
        [(file_id, module, alias, line) for module, alias, line in imports],
    )
    db.execute(
        "INSERT OR REPLACE INTO coverage(path,status,detail) VALUES(?,?,?)",
        (record["path"], coverage[0], coverage[1]),
    )


def codebase_canonicalize_duplicates(db):
    groups = db.execute(
        """SELECT kind,name,body_hash FROM symbols
           WHERE body_hash <> '' GROUP BY kind,name,body_hash
           HAVING SUM(is_generated) > 0 AND SUM(is_generated) < COUNT(*)"""
    ).fetchall()
    aliases = 0
    for kind, name, body_hash in groups:
        rows = db.execute(
            """SELECT s.id,s.is_generated,f.path FROM symbols s
               JOIN files f ON f.id=s.file_id
               WHERE s.kind=? AND s.name=? AND s.body_hash=?""",
            (kind, name, body_hash),
        ).fetchall()
        sources = sorted(
            (row for row in rows if not row[1]),
            key=lambda row: (len(row[2]), row[2]),
        )
        canonical = sources[0][0]
        for row in rows:
            if not row[1]:
                continue
            db.execute(
                "UPDATE symbols SET canonical_symbol_id=? WHERE id=?",
                (canonical, row[0]),
            )
            aliases += 1
    return aliases


def codebase_resolve_calls(db):
    resolved = 0
    unresolved = 0
    for caller_qn, callee, line in db.execute(
            "SELECT caller_qn,callee,line FROM raw_calls").fetchall():
        caller = db.execute(
            """SELECT id,file_id FROM symbols
               WHERE qualified_name=? AND canonical_symbol_id IS NULL
               ORDER BY is_generated,start_line DESC,id DESC LIMIT 1""",
            (caller_qn,),
        ).fetchone()
        if not caller:
            unresolved += 1
            continue
        candidates = db.execute(
            """SELECT id,file_id FROM symbols
               WHERE name=? AND canonical_symbol_id IS NULL
               AND kind IN ('Function','Method','Class')""",
            (callee,),
        ).fetchall()
        local = [candidate for candidate in candidates if candidate[1] == caller[1]]
        chosen = local[0] if len(local) == 1 else (
            candidates[0] if len(candidates) == 1 else None)
        if not chosen:
            unresolved += 1
            continue
        confidence = 1.0 if chosen in local else 0.8
        db.execute(
            "INSERT OR IGNORE INTO edges VALUES(NULL,?,?,?,?,?)",
            (caller[0], chosen[0], "CALLS", confidence, f"line:{line}"),
        )
        resolved += 1
    return resolved, unresolved


def codebase_write_metadata(db, values):
    db.executemany(
        "INSERT INTO metadata(key,value) VALUES(?,?)",
        [(key, str(value)) for key, value in values.items()],
    )


def codebase_index_payload(payload):
    if not isinstance(payload, dict):
        return {"result": "codebase_index_rejected", "errors": ["payload must be an object"]}
    root, error = codebase_repo(payload)
    if error:
        return {"result": "codebase_index_rejected", "errors": [error]}
    try:
        max_files = int(payload.get("max_files", CODEBASE_DEFAULT_MAX_FILES))
        max_total_bytes = int(
            payload.get("max_total_bytes", CODEBASE_DEFAULT_MAX_TOTAL_BYTES))
    except (TypeError, ValueError):
        return {
            "result": "codebase_index_rejected",
            "errors": ["max_files and max_total_bytes must be integers"],
        }
    paths = codebase_discover_paths(root)
    if max_files < 1 or len(paths) > max_files:
        return {
            "result": "codebase_index_refused",
            "file_count": len(paths),
            "max_files": max_files,
            "errors": ["repository exceeds the explicit indexing file budget"],
        }
    if max_total_bytes < 1:
        return {
            "result": "codebase_index_refused",
            "max_total_bytes": max_total_bytes,
            "errors": ["max_total_bytes must be positive"],
        }
    state_dir, db_path, state_error = codebase_safe_index_paths()
    if state_error:
        return {"result": "codebase_index_rejected", "errors": [state_error]}
    state_dir.mkdir(parents=True, exist_ok=True)
    state_dir, db_path, state_error = codebase_safe_index_paths()
    if state_error:
        return {"result": "codebase_index_rejected", "errors": [state_error]}
    os.chmod(state_dir, 0o700)
    tmp_path = state_dir / f".index-{os.getpid()}.sqlite3"
    return codebase_build_index(
        root, paths, tmp_path, db_path, max_total_bytes=max_total_bytes)


def codebase_update_content_digest(digest, record):
    digest.update(record["path"].encode("utf-8"))
    digest.update(b":")
    digest.update(record["sha256"].encode("ascii"))
    digest.update(b"\0")


def codebase_discard_index(db, tmp_path):
    if db:
        try:
            db.close()
        except sqlite3.Error:
            pass
    try:
        tmp_path.unlink(missing_ok=True)
    except OSError:
        pass


def codebase_build_index(root, paths, tmp_path, db_path, max_total_bytes):
    git_state = codebase_git_state(root)
    structural = hashlib.sha256("\0".join(paths).encode()).hexdigest()
    content = hashlib.sha256()
    total_bytes = 0
    db = None
    try:
        if tmp_path.exists():
            tmp_path.unlink()
        db = sqlite3.connect(tmp_path)
        codebase_create_schema(db)
        for rel in paths:
            record, miss = codebase_file_record(root, rel)
            if miss:
                db.execute(
                    "INSERT OR REPLACE INTO coverage(path,status,detail) VALUES(?,?,?)",
                    (rel, miss[0], miss[1]),
                )
                continue
            total_bytes += record["size"]
            if total_bytes > max_total_bytes:
                raise OverflowError("repository exceeds the explicit indexing byte budget")
            codebase_update_content_digest(content, record)
            codebase_insert_record(db, record, *codebase_parse_record(record))
        aliases = codebase_canonicalize_duplicates(db)
        resolved, unresolved = codebase_resolve_calls(db)
        counts = codebase_db_counts(db)
        codebase_write_metadata(db, {
            "schema_version": CODEBASE_SCHEMA_VERSION,
            "contract_version": CODEBASE_CONTRACT_VERSION,
            "engine_version": CODEBASE_ENGINE_VERSION,
            "engine": "piloth-stdlib-reference",
            "repo_root": root,
            "indexed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "git_head": git_state["head"],
            "worktree_fingerprint": git_state["worktree"],
            "structural_fingerprint": structural,
            "content_fingerprint": content.hexdigest(),
            "indexed_bytes": total_bytes,
            "generated_aliases": aliases,
            "resolved_calls": resolved,
            "unresolved_calls": unresolved,
        })
        db.commit()
        db.close()
        db = None
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, db_path)
    except OverflowError as exc:
        codebase_discard_index(db, tmp_path)
        return {
            "result": "codebase_index_refused",
            "max_total_bytes": max_total_bytes,
            "indexed_bytes_before_refusal": total_bytes,
            "errors": [str(exc)],
        }
    except (OSError, sqlite3.Error, ValueError) as exc:
        codebase_discard_index(db, tmp_path)
        return {"result": "codebase_index_failed", "errors": [str(exc)]}
    return {
        "result": "codebase_indexed",
        "engine": "piloth-stdlib-reference",
        "database": str(db_path.relative_to(REPO_ROOT)),
        "files": counts["files"],
        "indexed_bytes": total_bytes,
        "symbols": counts["symbols"],
        "edges": counts["edges"],
        "coverage_gaps": counts["coverage_gaps"],
        "generated_aliases": aliases,
        "resolved_calls": resolved,
        "unresolved_calls": unresolved,
        "freshness": "fresh",
    }


def codebase_db_counts(db):
    files = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    symbols = db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    edges = db.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
    gaps = db.execute(
        "SELECT COUNT(*) FROM coverage WHERE status <> 'deep'").fetchone()[0]
    return {"files": files, "symbols": symbols, "edges": edges, "coverage_gaps": gaps}


def codebase_metadata(db):
    return dict(db.execute("SELECT key,value FROM metadata").fetchall())


def codebase_open():
    _, path, error = codebase_safe_index_paths()
    if error:
        return None, error
    if not path.exists():
        return None, "missing"
    try:
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        return db, None
    except sqlite3.Error as exc:
        return None, str(exc)


def codebase_content_fingerprint(root, paths):
    digest = hashlib.sha256()
    for rel in paths:
        record, _ = codebase_file_record(root, rel)
        if record:
            codebase_update_content_digest(digest, record)
    return digest.hexdigest()


def codebase_status_payload(payload=None):
    root, error = codebase_repo(payload or {})
    if error:
        return {"result": "codebase_status_rejected", "errors": [error]}
    db, open_error = codebase_open()
    if not db:
        if open_error != "missing":
            return {
                "result": "codebase_status",
                "status": "invalid",
                "errors": [open_error],
            }
        return {
            "result": "codebase_status",
            "status": "missing",
            "recommendation": "index_when_structural_context_is_needed",
        }
    try:
        meta = codebase_metadata(db)
        counts = codebase_db_counts(db)
        git_state = codebase_git_state(root)
        current_paths = codebase_discover_paths(root)
        current_structural = hashlib.sha256("\0".join(current_paths).encode()).hexdigest()
        if int(meta.get("schema_version", 0)) != CODEBASE_SCHEMA_VERSION:
            status, reason = "invalid", "schema version does not match engine"
        elif int(meta.get("contract_version", 0)) != CODEBASE_CONTRACT_VERSION:
            status, reason = "invalid", "contract version does not match engine"
        elif int(meta.get("engine_version", 0)) != CODEBASE_ENGINE_VERSION:
            status, reason = "invalid", "engine version does not match index"
        elif meta.get("repo_root") != str(root):
            status, reason = "invalid", "repository root does not match index"
        elif git_state["head"] != meta.get("git_head", ""):
            status, reason = "stale_structural", "git HEAD changed"
        elif current_structural != meta.get("structural_fingerprint"):
            status, reason = "stale_structural", "indexed path set changed"
        elif git_state["worktree"] != meta.get("worktree_fingerprint", ""):
            status, reason = "stale_content", "working-tree content changed"
        elif not git_state["git"] and codebase_content_fingerprint(
                root, current_paths) != meta.get("content_fingerprint"):
            status, reason = "stale_content", "source content changed"
        else:
            status, reason = "fresh", "generation matches repository state"
    except (sqlite3.Error, ValueError) as exc:
        db.close()
        return {"result": "codebase_status", "status": "invalid", "errors": [str(exc)]}
    db.close()
    return {
        "result": "codebase_status",
        "status": status,
        "reason": reason,
        "recommendation": "use_index" if status == "fresh" else "full_rebuild",
        "engine": meta.get("engine", "unknown"),
        "schema_version": int(meta.get("schema_version", 0)),
        "engine_version": int(meta.get("engine_version", 0)),
        "indexed_at": meta.get("indexed_at", ""),
        **counts,
    }


def codebase_symbol_rows(db, query, limit):
    pattern = f"%{query.lower()}%"
    rows = db.execute(
        """SELECT s.id,s.kind,s.name,s.qualified_name,s.start_line,s.end_line,
                  s.signature,s.is_generated,f.path,
                  (SELECT COUNT(*) FROM symbols a WHERE a.canonical_symbol_id=s.id) alias_count
           FROM symbols s JOIN files f ON f.id=s.file_id
           WHERE s.canonical_symbol_id IS NULL
             AND (lower(s.name) LIKE ? OR lower(s.qualified_name) LIKE ?)
           ORDER BY CASE WHEN lower(s.name)=? THEN 0 ELSE 1 END,
                    s.is_generated, length(s.qualified_name), s.qualified_name
           LIMIT ?""",
        (pattern, pattern, query.lower(), limit),
    ).fetchall()
    return [dict(row) for row in rows]


def codebase_resolve_symbol(db, value):
    rows = db.execute(
        """SELECT s.id,s.kind,s.name,s.qualified_name,s.start_line,s.end_line,
                  s.file_id,f.path,f.sha256
           FROM symbols s JOIN files f ON f.id=s.file_id
           WHERE s.canonical_symbol_id IS NULL
             AND (s.qualified_name=? OR s.name=?)
           ORDER BY CASE WHEN s.qualified_name=? THEN 0 ELSE 1 END,
                    s.is_generated, s.qualified_name, s.start_line DESC
           LIMIT 25""",
        (value, value, value),
    ).fetchall()
    exact = [row for row in rows if row["qualified_name"] == value]
    if len(exact) == 1:
        return exact[0], []
    if exact and len({row["path"] for row in exact}) == 1:
        return exact[0], []
    if len(rows) == 1:
        return rows[0], []
    return None, [
        {"qualified_name": row["qualified_name"], "kind": row["kind"], "path": row["path"]}
        for row in rows
    ]


def codebase_query_overview(db, payload):
    counts = codebase_db_counts(db)
    languages = [
        {"language": row[0], "files": row[1]}
        for row in db.execute(
            "SELECT language,COUNT(*) FROM files GROUP BY language ORDER BY COUNT(*) DESC,language"
        ).fetchall()
    ]
    coverage = [
        {"status": row[0], "files": row[1]}
        for row in db.execute(
            "SELECT status,COUNT(*) FROM coverage GROUP BY status ORDER BY status"
        ).fetchall()
    ]
    return {"action": "overview", **counts, "languages": languages, "coverage": coverage}


def codebase_query_search(db, payload):
    query = str(payload.get("query", "")).strip()
    if not query:
        return {"action": "search", "errors": ["query is required"]}
    limit = min(max(int(payload.get("limit", 20)), 1), 200)
    rows = codebase_symbol_rows(db, query, limit)
    return {"action": "search", "query": query, "results": rows, "returned": len(rows)}


def codebase_trace_leg(db, seed, direction, depth, limit):
    frontier = {seed}
    seen = {seed}
    results = []
    for hop in range(1, depth + 1):
        if not frontier or len(results) >= limit:
            break
        placeholders = ",".join("?" for _ in frontier)
        if direction == "outbound":
            sql = f"""SELECT e.source_symbol_id,e.target_symbol_id,e.confidence,
                             s.qualified_name,s.kind,f.path
                      FROM edges e JOIN symbols s ON s.id=e.target_symbol_id
                      JOIN files f ON f.id=s.file_id
                      WHERE e.type='CALLS' AND e.source_symbol_id IN ({placeholders})
                      ORDER BY e.source_symbol_id,e.target_symbol_id"""
        else:
            sql = f"""SELECT e.target_symbol_id,e.source_symbol_id,e.confidence,
                             s.qualified_name,s.kind,f.path
                      FROM edges e JOIN symbols s ON s.id=e.source_symbol_id
                      JOIN files f ON f.id=s.file_id
                      WHERE e.type='CALLS' AND e.target_symbol_id IN ({placeholders})
                      ORDER BY e.target_symbol_id,e.source_symbol_id"""
        rows = db.execute(sql, tuple(frontier)).fetchall()
        next_frontier = set()
        for row in rows:
            target_id = row[1]
            if target_id in seen:
                continue
            seen.add(target_id)
            next_frontier.add(target_id)
            results.append({
                "qualified_name": row[3], "kind": row[4], "path": row[5],
                "hop": hop, "confidence": row[2],
            })
            if len(results) >= limit:
                break
        frontier = next_frontier
    return results


def codebase_query_trace(db, payload):
    value = str(payload.get("symbol", "")).strip()
    if not value:
        return {"action": "trace", "errors": ["symbol is required"]}
    symbol, suggestions = codebase_resolve_symbol(db, value)
    if not symbol:
        return {
            "action": "trace",
            "status": "ambiguous" if suggestions else "not_found",
            "suggestions": suggestions,
        }
    direction = str(payload.get("direction", "both")).lower()
    if direction not in {"inbound", "outbound", "both"}:
        return {"action": "trace", "errors": ["direction must be inbound, outbound or both"]}
    depth = min(max(int(payload.get("depth", 2)), 1), 5)
    limit = min(max(int(payload.get("limit", 100)), 1), 1000)
    result = {
        "action": "trace",
        "symbol": symbol["qualified_name"],
        "direction": direction,
    }
    if direction in {"outbound", "both"}:
        result["outbound"] = codebase_trace_leg(db, symbol["id"], "outbound", depth, limit)
    if direction in {"inbound", "both"}:
        result["inbound"] = codebase_trace_leg(db, symbol["id"], "inbound", depth, limit)
    return result


def codebase_safe_source(root, rel):
    try:
        candidate = root / rel
        if candidate.is_symlink():
            return None
        source = candidate.resolve()
        if os.path.commonpath((str(root), str(source))) != str(root):
            return None
        if not source.is_file():
            return None
        return source
    except OSError:
        return None


def codebase_query_snippet(db, payload):
    value = str(payload.get("symbol", "")).strip()
    symbol, suggestions = codebase_resolve_symbol(db, value)
    if not symbol:
        return {
            "action": "snippet",
            "status": "ambiguous" if suggestions else "not_found",
            "suggestions": suggestions,
        }
    source = codebase_safe_source(REPO_ROOT.resolve(), symbol["path"])
    if not source:
        return {"action": "snippet", "status": "source_unavailable"}
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    neighbors = min(max(int(payload.get("neighbors", 0)), 0), 20)
    start = max(symbol["start_line"] - neighbors, 1)
    end = min(symbol["end_line"] + neighbors, len(lines), start + 499)
    current_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    return {
        "action": "snippet",
        "qualified_name": symbol["qualified_name"],
        "path": symbol["path"],
        "start_line": start,
        "end_line": end,
        "source": "\n".join(lines[start - 1:end]),
        "source_freshness": "metadata_match" if current_hash == symbol["sha256"] else "changed",
    }


def codebase_normalize_rel(value):
    rel = pathlib.PurePosixPath(str(value).replace("\\", "/"))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        return None
    return rel.as_posix()


def codebase_query_coverage(db, payload):
    paths = payload.get("paths")
    if not isinstance(paths, list) or not paths:
        return {"action": "coverage", "errors": ["paths must be a non-empty array"]}
    results = []
    for requested in paths[:200]:
        rel = codebase_normalize_rel(requested)
        if not rel:
            results.append({"path": str(requested), "status": "invalid_path"})
            continue
        row = db.execute(
            "SELECT status,detail FROM coverage WHERE path=?", (rel,)).fetchone()
        results.append({
            "path": rel,
            "status": row["status"] if row else "not_indexed",
            "detail": row["detail"] if row else "",
            "caveat": "best_effort_not_completeness_proof",
        })
    return {"action": "coverage", "paths": results}


def codebase_query_impact(db, payload):
    requested = payload.get("paths")
    if not isinstance(requested, list) or not requested:
        requested = codebase_git_state(REPO_ROOT.resolve())["dirty_paths"]
    paths = [codebase_normalize_rel(item) for item in requested[:200]]
    paths = [item for item in paths if item]
    if not paths:
        return {"action": "impact", "paths": [], "seeds": [], "impacted": []}
    placeholders = ",".join("?" for _ in paths)
    seeds = db.execute(
        f"""SELECT s.id,s.qualified_name,f.path FROM symbols s
            JOIN files f ON f.id=s.file_id
            WHERE s.canonical_symbol_id IS NULL AND f.path IN ({placeholders})""",
        tuple(paths),
    ).fetchall()
    impacted = []
    for seed in seeds:
        impacted.extend(codebase_trace_leg(db, seed["id"], "inbound", 3, 200))
    unique = {item["qualified_name"]: item for item in impacted}
    return {
        "action": "impact",
        "paths": paths,
        "seeds": [{"qualified_name": row["qualified_name"], "path": row["path"]} for row in seeds],
        "impacted": sorted(unique.values(), key=lambda item: (item["hop"], item["qualified_name"])),
    }


def codebase_query_payload(payload):
    if not isinstance(payload, dict):
        return {"result": "codebase_query_rejected", "errors": ["payload must be an object"]}
    action = str(payload.get("action", "")).strip().lower()
    handlers = {
        "overview": codebase_query_overview,
        "search": codebase_query_search,
        "trace": codebase_query_trace,
        "snippet": codebase_query_snippet,
        "coverage": codebase_query_coverage,
        "impact": codebase_query_impact,
    }
    if action not in handlers:
        return {
            "result": "codebase_query_rejected",
            "errors": ["action must be overview, search, trace, snippet, coverage or impact"],
        }
    freshness = codebase_status_payload(payload)
    if freshness.get("status") == "missing":
        return {
            "result": "codebase_query_unavailable",
            "freshness": freshness,
            "errors": ["index is missing; run codebase-index when structural context is needed"],
        }
    db, open_error = codebase_open()
    if not db:
        return {
            "result": "codebase_query_unavailable",
            "errors": [f"index is unavailable: {open_error}"],
        }
    try:
        output = handlers[action](db, payload)
    except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
        db.close()
        return {"result": "codebase_query_failed", "action": action, "errors": [str(exc)]}
    db.close()
    snippet_fresh = output.get("source_freshness") == "metadata_match"
    source_grounded = action == "snippet" and snippet_fresh
    output.update({
        "result": "codebase_query",
        "freshness": freshness.get("status"),
        "trust": "source_grounded" if source_grounded else "candidate_only",
        "coverage_signal": "best_effort",
        "source_fallback_required": (
            freshness.get("status") != "fresh"
            or (action == "snippet" and not snippet_fresh)
        ),
    })
    return output


def codebase_index(argv):
    if not argv:
        json_print({
            "result": "codebase_index_rejected",
            "errors": ["explicit JSON payload required; indexing is adaptive, never implicit"],
        })
        return
    try:
        payload, _ = json_arg_or_stdin(argv, "codebase-index")
        json_print(codebase_index_payload(payload))
    except Exception as exc:
        json_print({"result": "codebase_index_rejected", "errors": [str(exc)]})


def codebase_status(argv):
    try:
        payload = {}
        if argv:
            payload, _ = json_arg_or_stdin(argv, "codebase-status")
        json_print(codebase_status_payload(payload))
    except Exception as exc:
        json_print({"result": "codebase_status_rejected", "errors": [str(exc)]})


def codebase_query(argv):
    if not argv:
        json_print({
            "result": "codebase_query_rejected",
            "errors": ["explicit JSON payload with action is required"],
        })
        return
    try:
        payload, _ = json_arg_or_stdin(argv, "codebase-query")
        json_print(codebase_query_payload(payload))
    except Exception as exc:
        json_print({"result": "codebase_query_rejected", "errors": [str(exc)]})
# --------------------------------------------------------- semantic scan modes

def scan_request(argv, label):
    payload, _ = json_arg_or_stdin(argv, label)
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: request must be a JSON object")
    changed = payload.get("changed_paths")
    allowed = payload.get("allowed_paths")
    if not isinstance(changed, list) or any(not isinstance(x, str) for x in changed):
        raise ValueError(f"{label}: changed_paths must be a list of strings")
    if not isinstance(allowed, list) or any(not isinstance(x, str) for x in allowed):
        raise ValueError(f"{label}: allowed_paths must be a list of strings")
    return payload


def token_parts(value):
    stem = pathlib.PurePosixPath(str(value)).stem
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", stem)
    return {
        part.lower()
        for part in re.split(r"[^A-Za-z0-9]+", spaced)
        if len(part) >= 3
    }


def candidate_files_within(patterns):
    files = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if path_matches(patterns, rel):
            files.append(rel)
    return sorted(files)


def extract_symbols(text):
    symbols = []
    patterns = (
        r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*export\s+(?:function|const|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:function|const)\s+([A-Za-z_][A-Za-z0-9_]*)",
    )
    for pattern in patterns:
        symbols.extend(re.findall(pattern, text, flags=re.M))
    return sorted(set(symbols))[:12]


def extract_imports(text):
    imports = []
    patterns = (
        r"^\s*from\s+([A-Za-z0-9_./-]+)\s+import\b",
        r"^\s*import\s+([A-Za-z0-9_./-]+)",
        r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
        r"require\(['\"]([^'\"]+)['\"]\)",
    )
    for pattern in patterns:
        imports.extend(re.findall(pattern, text, flags=re.M))
    return sorted(set(imports))[:20]


def nearby_test_or_doc(rel):
    path = pathlib.PurePosixPath(rel)
    stem = path.stem.lower()
    parent = path.parent.as_posix()
    candidates = []
    for suffix in (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".test.py", ".md"):
        if parent == ".":
            candidates.append(stem + suffix)
        else:
            candidates.append(parent + "/" + stem + suffix)
    return [candidate for candidate in candidates if (REPO_ROOT / candidate).exists()]


def candidate_identifiers(candidate):
    values = {
        str(candidate.get("id", "")),
        str(candidate.get("path", "")),
        str(candidate.get("candidate", "")),
    }
    return {value for value in values if value}


def reuse_review_decision(receipt, candidate):
    identifiers = candidate_identifiers(candidate)
    review = receipt.get("semantic_reuse_review") if isinstance(receipt, dict) else None
    if isinstance(review, dict):
        review = [review]
    if not isinstance(review, list):
        return ""
    for item in review:
        if not isinstance(item, dict):
            continue
        target = item.get("candidate") or item.get("candidate_id") or item.get("id") or item.get("path")
        if target in {"all", "*"} or str(target) in identifiers:
            return str(item.get("decision", ""))
    return ""


def receipt_duplicate_findings(receipt):
    findings = []
    if not isinstance(receipt, dict):
        return findings
    for candidate in candidates_from_receipt(
        receipt,
        ("semantic_reuse_candidates", "reuse_scan", "semantic_reuse_scan"),
    ):
        if candidate_confidence(candidate) < HIGH_CONFIDENCE_THRESHOLD:
            continue
        findings.append({
            "id": candidate.get("id"),
            "path": candidate.get("path"),
            "confidence": candidate_confidence(candidate),
            "review_decision": reuse_review_decision(receipt, candidate),
        })
    return findings


def prior_duplicate_finding_keys():
    keys = set()
    if not SCHEDULER_HISTORY.exists():
        return keys
    try:
        with open(SCHEDULER_HISTORY, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("repo_key") != REPO_KEY:
                    continue
                for finding in item.get("duplicate_findings", []):
                    if not isinstance(finding, dict):
                        continue
                    keys |= candidate_identifiers(finding)
    except (OSError, json.JSONDecodeError):
        return set()
    return keys


def reuse_learning_suggestions(candidates):
    high = [
        candidate for candidate in candidates
        if candidate_confidence(candidate) >= HIGH_CONFIDENCE_THRESHOLD
    ]
    if not high:
        return []
    prior = prior_duplicate_finding_keys()
    suggestions = []
    for candidate in high:
        repeated = bool(candidate_identifiers(candidate) & prior)
        path = candidate.get("path") or candidate.get("id")
        component_like = path and is_component_like_path(str(path))
        suggestions.append({
            "candidate": candidate.get("id") or path,
            "mistake_checked": "duplicated_component" if component_like else "duplicated_helper",
            "lesson_decision": "recorded" if repeated else "deferred",
            "promoted_to": "not_applicable",
            "reason": (
                "Repeated high-confidence reuse candidate from local history; record or promote lesson if new code proceeds."
                if repeated
                else "High-confidence reuse candidate exists; defer lesson unless the receipt chooses new code or duplication recurs."
            ),
            "repeated": repeated,
        })
    return suggestions


def reuse_scan_payload(payload):
    changed = [normalize_relative_path_text(p) for p in payload.get("changed_paths", [])]
    allowed = payload.get("allowed_paths") or ["**/*"]
    candidates = []
    seen = set()
    changed_tokens = set()
    changed_import_tokens = set()
    for rel in changed:
        changed_tokens |= token_parts(rel)
        changed_tokens |= token_parts(payload.get("task_signal", ""))
        changed_text = read_text_safe(REPO_ROOT / rel, limit=60000)
        for imported in extract_imports(changed_text):
            changed_import_tokens |= token_parts(imported)
    helper_signal = bool(changed_tokens & {
        "helper", "helpers", "util", "utils", "validator", "validate",
        "guard", "component",
    })
    for rel in candidate_files_within(allowed):
        if rel in changed:
            continue
        suffix = pathlib.PurePosixPath(rel).suffix.lower()
        if suffix not in CODE_EXTENSIONS and suffix not in {".md", ".json"}:
            continue
        tokens = token_parts(rel)
        overlap = changed_tokens & tokens
        if not overlap and not helper_signal:
            continue
        text = read_text_safe(REPO_ROOT / rel, limit=80000)
        symbols = extract_symbols(text)
        imports = extract_imports(text)
        symbol_tokens = set()
        for symbol in symbols:
            symbol_tokens |= token_parts(symbol)
        import_tokens = set()
        for imported in imports:
            import_tokens |= token_parts(imported)
        symbol_overlap = changed_tokens & symbol_tokens
        import_overlap = changed_import_tokens & (tokens | symbol_tokens | import_tokens)
        score = 0.0
        reason_bits = []
        if changed_tokens:
            score += min(0.65, 0.65 * (len(overlap) / max(1, len(changed_tokens))))
        if helper_signal and (tokens & {"helper", "helpers", "util", "utils", "validator", "validate", "guard"}):
            score += 0.25
            reason_bits.append("helper/validator naming matches task signal")
        if symbol_overlap:
            score += 0.20
            reason_bits.append("exported symbols overlap changed path terms")
        if import_overlap:
            score += 0.15
            reason_bits.append("imports overlap changed file dependencies")
        nearby = nearby_test_or_doc(rel)
        if nearby:
            score += 0.05
            reason_bits.append("nearby tests/docs exist: " + ", ".join(nearby[:3]))
        if overlap:
            reason_bits.append("filename terms overlap: " + ", ".join(sorted(overlap)))
        if not reason_bits and helper_signal:
            reason_bits.append("helper-like path is in allowed search scope")
            score = max(score, 0.40)
        confidence = min(0.95, round(score, 2))
        if confidence < 0.40:
            continue
        candidate = {
            "id": f"reuse:{stable_slug(rel)}",
            "path": rel,
            "confidence": confidence,
            "reason": "; ".join(reason_bits),
            "source": "filename/symbol scan",
            "suggested_decision": "reuse" if confidence >= HIGH_CONFIDENCE_THRESHOLD else "extend",
            "symbols": symbols,
            "imports": imports,
            "nearby_evidence": nearby,
        }
        if candidate["id"] not in seen:
            candidates.append(candidate)
            seen.add(candidate["id"])
    candidates.sort(key=lambda item: (-float(item["confidence"]), item["path"]))
    candidates = candidates[:25]
    return {
        "result": "reuse_scan",
        "task_signal": payload.get("task_signal", "not_applicable"),
        "changed_paths": changed,
        "allowed_paths": allowed,
        "candidates": candidates,
        "high_confidence_candidates": [
            item for item in candidates
            if float(item.get("confidence", 0)) >= HIGH_CONFIDENCE_THRESHOLD
        ],
        "learning_suggestions": reuse_learning_suggestions(candidates),
    }


def reuse_scan(argv):
    try:
        payload = scan_request(argv, "reuse-scan")
        json_print(reuse_scan_payload(payload))
    except Exception as e:
        json_print({"result": "reuse_scan_rejected", "errors": [str(e)]})


def ds_scan_payload(payload):
    allowed = payload.get("allowed_paths") or ["**/*"]
    files = candidate_files_within(allowed)
    component_candidates = []
    token_candidates = []
    pattern_candidates = []
    seen = set()
    for rel in files:
        path = pathlib.PurePosixPath(rel)
        parts = set(path.parts)
        name = path.name.lower()
        suffix = path.suffix.lower()
        text = ""
        if suffix in {".css", ".scss", ".md", ".tsx", ".ts", ".jsx", ".js", ".json"}:
            text = read_text_safe(REPO_ROOT / rel, limit=60000)
        symbols = extract_symbols(text) if text else []
        css_variables = sorted(set(re.findall(r"--[A-Za-z0-9_-]+", text)))[:20]
        if ("components" in parts or "ui" in parts) and suffix in {".tsx", ".jsx", ".vue", ".svelte", ".md"}:
            key = f"component:{rel}"
            if key not in seen:
                component_candidates.append({
                    "id": key,
                    "path": rel,
                    "confidence": 0.90,
                    "reason": "component/UI path detected"
                    + (f"; symbols: {', '.join(symbols[:5])}" if symbols else ""),
                    "source": "path/symbol scan",
                    "suggested_decision": "reuse",
                    "symbols": symbols,
                })
                seen.add(key)
        if (
            "tokens" in parts or "theme" in name or "token" in name
            or name in {"tailwind.config.js", "tailwind.config.ts"}
            or css_variables
        ):
            key = f"token:{rel}"
            if key not in seen:
                token_candidates.append({
                    "id": key,
                    "path": rel,
                    "confidence": 0.88,
                    "reason": "token/theme/CSS variable signal detected",
                    "source": "path/content scan",
                    "suggested_decision": "reuse",
                    "css_variables": css_variables,
                })
                seen.add(key)
        if (
            "storybook" in rel.lower()
            or "design-system" in rel.lower()
            or "ui-design-system" in rel.lower()
            or "design system" in text.lower()
            or "component catalog" in text.lower()
        ):
            key = f"pattern:{rel}"
            if key not in seen:
                pattern_candidates.append({
                    "id": key,
                    "path": rel,
                    "confidence": 0.86,
                    "reason": "design-system docs/storybook signal detected",
                    "source": "path/content scan",
                    "suggested_decision": "reuse",
                    "symbols": symbols,
                })
                seen.add(key)
    return {
        "result": "ds_scan",
        "task_signal": payload.get("task_signal", "not_applicable"),
        "changed_paths": payload.get("changed_paths", []),
        "allowed_paths": allowed,
        "component_candidates": sorted(component_candidates, key=lambda item: item["path"])[:25],
        "token_candidates": sorted(token_candidates, key=lambda item: item["path"])[:25],
        "pattern_candidates": sorted(pattern_candidates, key=lambda item: item["path"])[:25],
    }


def ds_scan(argv):
    try:
        payload = scan_request(argv, "ds-scan")
        json_print(ds_scan_payload(payload))
    except Exception as e:
        json_print({"result": "ds_scan_rejected", "errors": [str(e)]})


# ------------------------------------------------------- evidence router core

# Evidence Router is deliberately deterministic and read-only.  It chooses the
# smallest evidence plan that can still meet the quality floor; lifecycle
# commands may persist the returned decision separately.

EVIDENCE_ITEM_FIELDS = {
    "type", "source", "required", "freshness", "coverage", "confidence",
    "estimated_cost", "trust", "fallback",
}
ADAPTER_CAPABILITY_STATUS = {"native", "emulated", "unavailable"}
ADAPTER_CAPABILITY_KEYS = (
    "pre_edit_hooks",
    "post_edit_hooks",
    "stop_hooks",
    "subagent_spawn",
    "parallel_execution",
    "role_permissions",
    "model_pinning",
    "token_telemetry",
    "model_telemetry",
    "cost_telemetry",
    "mcp_tool_discovery",
    "approval_controls",
    "sandbox_controls",
    "receipt_enforcement",
    "seal_enforcement",
)
# Presence of the variable is the signal, not its value. Each maps to an adapter
# id the capability registry must declare before detection may use it.
#
# Only variables the harness sets in the process that runs this guard belong here.
# Notably absent: CURSOR_CLI, which Cursor's integrated terminal sets even when a
# human is typing commands by hand — it says "a Cursor terminal", not "the Cursor
# agent is driving", so using it would claim cursor's capability profile for a
# session that never went through the agent.
ADAPTER_ENV_SIGNALS = (
    ("CLAUDECODE", "claude"),
    ("CLAUDE_PROJECT_DIR", "claude"),
    # Set by Cursor CLI while the agent runs a shell command. Cursor has an open
    # report of it not being set consistently, so treat a miss as "unknown".
    ("CURSOR_AGENT", "cursor"),
    # Codex sets this ("seatbelt" on macOS) on the child process it spawns for a
    # tool call — which is where this guard runs. Two caveats: it is undocumented
    # (Codex points at --sandbox / config.toml instead) and it only appears when
    # sandboxing is on, so `codex --sandbox danger-full-access` resolves to
    # "unknown". Both directions fail closed, never toward a wrong claim.
    ("CODEX_SANDBOX", "codex"),
)
EVIDENCE_ROUTER_ROLLOUT_MODES = {"off", "shadow", "advisory", "enforced"}
EVIDENCE_ROUTER_DEFAULT_BUDGET = {
    "max_roles": 3,
    "max_repair_loops": 1,
    "max_tool_calls": 40,
    "max_files": 200,
    "max_bytes": 2_000_000,
    "tool_timeout_seconds": 120,
}
EVIDENCE_ROUTER_SECRET_KEYS = re.compile(
    r"(secret|token|password|passwd|api[_-]?key|credential|authorization|bearer)",
    re.IGNORECASE,
)
EVIDENCE_ROUTER_NEGATIVE_CLAIM = re.compile(
    r"\b(no|none|never|without|does not|doesn't|isn't|not present|không|chưa)\b",
    re.IGNORECASE,
)
EVIDENCE_ROUTER_SECURITY_TERMS = (
    "security", "vulnerability", "cve", "auth", "authorization", "permission",
    "secret", "credential", "xss", "csrf", "injection", "exploit",
)
EVIDENCE_ROUTER_DESTRUCTIVE_TERMS = (
    "delete", "drop table", "truncate", "destroy", "overwrite", "force push",
    "rm -rf", "production migration", "data migration",
)


def evidence_router_default_matrix():
    """Fail-soft matrix used only when the distributed JSON is unavailable."""
    matrix = {}
    for key, route in TASK_SIGNAL_ROUTES.items():
        matrix[key] = {
            "task_class": {
                "bug fix": "localized_bug",
                "ui/component": "ui_change",
                "api/backend": "backend_change",
                "release/deploy": "release_change",
                "tool/mcp": "tooling_change",
                "architecture": "architecture_change",
                "security": "security_change",
            }.get(key, "small_task"),
            "risk_base": {
                "bug fix": 30,
                "ui/component": 28,
                "api/backend": 38,
                "tool/mcp": 45,
                "architecture": 62,
                "release/deploy": 78,
                "security": 82,
            }.get(key, 10),
            "evidence": [{
                "type": "source",
                "source": "affected source files",
                "required": True,
                "freshness": "current",
                "coverage": "affected_paths",
                "estimated_cost": "low",
                "trust": "source",
                "fallback": "read affected source directly",
            }],
            "context": list(route.get("context_layers", [])),
            "tools": [],
            "verification": ["targeted verification"],
        }
    return {
        "schema_version": 1,
        "quality_floor": dict(DEFAULT_QUALITY_FLOOR),
        "task_matrix": matrix,
    }


def load_evidence_router_matrix():
    data = load_json_file(EVIDENCE_ROUTER_MATRIX)
    if (
        isinstance(data, dict)
        and isinstance(data.get("task_matrix"), dict)
        and isinstance(data.get("quality_floor"), dict)
    ):
        return data, "registry"
    return evidence_router_default_matrix(), "embedded_fallback"


def evidence_router_quality_floor(matrix=None):
    """The quality floor in force: registry values layered over the embedded
    defaults, so a partial or malformed `quality_floor` block cannot drop a
    threshold. Every routing decision reads its thresholds from here — that is
    what makes evidence-routing.json actually govern policy instead of merely
    reporting it."""
    floor = dict(DEFAULT_QUALITY_FLOOR)
    if matrix is None:
        matrix, _ = load_evidence_router_matrix()
    declared = matrix.get("quality_floor") if isinstance(matrix, dict) else None
    if isinstance(declared, dict):
        for key, value in declared.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                floor[key] = value
    return floor


def evidence_router_schema_payload():
    return {
        "result": "evidence_route_schema",
        "read_only": True,
        "input": {
            "intent": "string",
            "locale": "BCP-47 language tag; schema and IDs remain English",
            "task_signal": sorted(ASSET_ROUTING_SIGNALS),
            "affected_paths": ["relative/path"],
            "constraints": ["string"],
            "adapter": ["claude", "codex", "cursor", "antigravity"],
            "adapter_capabilities": {
                key: sorted(ADAPTER_CAPABILITY_STATUS)
                for key in ADAPTER_CAPABILITY_KEYS
            },
            "budget": "object",
            "user_overrides": {
                "rollout": sorted(EVIDENCE_ROUTER_ROLLOUT_MODES),
                "execution_mode": ["single", "team"],
                "kill_switch": "boolean",
            },
        },
        "output_required": [
            "decision_id", "task_class", "risk", "confidence",
            "evidence_plan", "context_plan", "execution_plan", "tool_plan",
            "verification_plan", "budgets", "fallbacks", "limitations",
            "decision_reasons",
        ],
        # Same key names as evidence-routing.json / DEFAULT_QUALITY_FLOOR: this
        # block used to report `minimum_route_confidence`, a name that appears
        # nowhere else, so a consumer reading the schema could not match it to the
        # registry key it describes.
        "quality_floor": evidence_router_quality_floor(),
    }


def load_adapter_capability_registry():
    data = load_json_file(ADAPTER_CAPABILITY_REGISTRY)
    if not isinstance(data, dict):
        data = {}
    adapters = data.get("adapters")
    return adapters if isinstance(adapters, dict) else {}


def resolve_adapter(payload):
    """``(adapter_id, source)`` for a capability request.

    Precedence: explicit request > ``PILOTHOS_ADAPTER`` > harness env signal >
    ``"unknown"``.  Without this every caller defaults to ``unknown``, which is
    the worst path available: all 15 capabilities resolve to ``unavailable``, so
    an ``enforced`` rollout silently degrades to ``advisory`` even on a harness
    that does support hooks and seals.

    An explicit request keeps whatever id it names — declaring an unregistered
    harness is legitimate and simply resolves every capability to
    ``unavailable``.  Env detection is stricter and only yields ids the registry
    declares, so Piloth never invents a capability profile from a stray
    variable.  ``adapter_source`` travels with the answer so the resolution
    stays auditable instead of looking like a claim.
    """
    requested = str(payload.get("adapter") or "").strip().lower()
    if requested:
        return requested, "request"
    registry = load_adapter_capability_registry()
    declared = str(os.environ.get("PILOTHOS_ADAPTER") or "").strip().lower()
    if declared:
        # An explicit override that names nothing we know stays conservative
        # rather than falling through to detection behind the user's back.
        return (declared, "env") if declared in registry else ("unknown", "default")
    for var, adapter in ADAPTER_ENV_SIGNALS:
        if os.environ.get(var) and adapter in registry:
            return adapter, "detected"
    return "unknown", "default"


def adapter_capabilities_payload(payload):
    if not isinstance(payload, dict):
        return {
            "result": "adapter_capabilities_rejected",
            "errors": ["capabilities request must be a JSON object"],
        }
    if payload.get("explain") is True:
        return {
            "result": "adapter_capabilities_schema",
            "read_only": True,
            "statuses": sorted(ADAPTER_CAPABILITY_STATUS),
            "capabilities": list(ADAPTER_CAPABILITY_KEYS),
        }
    adapter, adapter_source = resolve_adapter(payload)
    registry = load_adapter_capability_registry()
    declared = registry.get(adapter)
    if not isinstance(declared, dict):
        declared = {}
    supplied = payload.get("adapter_capabilities")
    if supplied is None:
        supplied = payload.get("capabilities")
    if supplied is None:
        supplied = {
            key: payload[key]
            for key in ADAPTER_CAPABILITY_KEYS
            if key in payload
        }
    if not isinstance(supplied, dict):
        return {
            "result": "adapter_capabilities_rejected",
            "adapter": adapter,
            "errors": ["adapter_capabilities must be an object"],
        }
    errors = []
    unknown = sorted(set(supplied) - set(ADAPTER_CAPABILITY_KEYS))
    if unknown:
        errors.append("unknown capabilities: " + ", ".join(unknown))
    for key, value in supplied.items():
        if key in ADAPTER_CAPABILITY_KEYS and value not in ADAPTER_CAPABILITY_STATUS:
            errors.append(
                f"{key} must be one of: "
                + ", ".join(sorted(ADAPTER_CAPABILITY_STATUS))
            )
    if errors:
        return {
            "result": "adapter_capabilities_rejected",
            "adapter": adapter,
            "errors": errors,
        }
    normalized = {}
    sources = {}
    for key in ADAPTER_CAPABILITY_KEYS:
        if key in supplied:
            normalized[key] = supplied[key]
            sources[key] = "request"
        elif declared.get(key) in ADAPTER_CAPABILITY_STATUS:
            normalized[key] = declared[key]
            sources[key] = "registry"
        else:
            normalized[key] = "unavailable"
            sources[key] = "missing"
    # One aggregate line, not one line per key: the per-key statuses are already
    # in `capabilities`, and 15 boilerplate sentences both cost tokens and dilute
    # the limitations that carry real signal.
    unavailable = [
        key for key, status in normalized.items() if status == "unavailable"
    ]
    limitations = []
    if unavailable:
        limitations.append(
            f"{len(unavailable)} capability(ies) unavailable; no native path is "
            "claimed: " + ", ".join(unavailable)
        )
    # Emulated stays itemised — an emulated path is a decision input, not noise.
    degraded = [
        f"{key} uses an emulated adapter path"
        for key, status in normalized.items()
        if status == "emulated"
    ]
    return {
        "result": "adapter_capabilities",
        "read_only": True,
        "adapter": adapter,
        "adapter_source": adapter_source,
        "capabilities": normalized,
        # Only provenance that says something: "missing" is the default and is
        # recoverable from `capabilities` plus `sources_summary`.
        "sources": {
            key: value for key, value in sources.items() if value != "missing"
        },
        "sources_summary": {
            name: sum(1 for value in sources.values() if value == name)
            for name in ("request", "registry", "missing")
        },
        "complete": len(normalized) == len(ADAPTER_CAPABILITY_KEYS),
        "limitations": limitations,
        "degraded": degraded,
    }


def adapter_capabilities(argv):
    if "--explain" in list(argv):
        json_print(adapter_capabilities_payload({"explain": True}))
        return
    try:
        payload, _ = json_arg_or_stdin(argv, "adapter-capabilities")
    except Exception as e:
        json_print({
            "result": "adapter_capabilities_rejected",
            "errors": [str(e)],
        })
        return
    json_print(adapter_capabilities_payload(payload))


def evidence_router_intent_blob(request):
    parts = [
        str(request.get("intent") or ""),
        " ".join(str(x) for x in request.get("constraints", []) if isinstance(x, str)),
        " ".join(request_paths(request)),
    ]
    return " ".join(parts).strip().lower()


def classify_evidence_task(request, matrix):
    raw = request.get("task_signal")
    normalized = normalize_task_signal(raw)
    known = set(matrix.get("task_matrix", {}))
    reasons = []
    if raw is not None and str(raw).strip():
        if normalized not in known:
            return None, 0.0, [], [
                "task_signal must be one of: "
                + ", ".join(sorted(
                    TASK_SIGNAL_ROUTES[k]["task_signal"]
                    for k in known if k in TASK_SIGNAL_ROUTES
                ))
            ]
        reasons.append(f"explicit task_signal={TASK_SIGNAL_ROUTES.get(normalized, {}).get('task_signal', normalized)}")
        return normalized, 0.96, reasons, []

    blob = evidence_router_intent_blob(request)
    inference = (
        ("security", EVIDENCE_ROUTER_SECURITY_TERMS),
        ("release/deploy", ("release", "deploy", "production rollout", "publish")),
        ("architecture", ("architecture", "boundary", "refactor system", "design system topology")),
        ("ui/component", ("component", "frontend", "visual", "css", "design token", "ui ")),
        ("api/backend", ("api", "backend", "endpoint", "database", "migration")),
        ("bug fix", ("bug", "fix", "regression", "crash", "incorrect")),
        ("tool/mcp", ("mcp", "tool", "cli", "command")),
    )
    for signal, terms in inference:
        if any(term in blob for term in terms):
            reasons.append(f"inferred {signal} from intent/path signal")
            return signal, 0.84, reasons, []
    reasons.append("no class signal found; conservative small-task fallback")
    return "not_applicable", 0.72, reasons, []


def evidence_router_risk(request, signal, task_row):
    score = int(task_row.get("risk_base", 10))
    reasons = [f"{signal} base risk={score}"]
    paths = request_paths(request)
    blob = evidence_router_intent_blob(request)
    if not paths or any(path_pattern_is_broad(path) for path in paths):
        score += 12
        reasons.append("broad or unresolved path coverage +12")
    elif len(paths) > 6:
        score += 10
        reasons.append("more than six affected paths +10")
    roots = {
        normalize_relative_path_text(path).split("/", 1)[0]
        for path in paths if path and not path_pattern_is_broad(path)
    }
    if len(roots) >= 3:
        score += 8
        reasons.append("cross-area change +8")
    if any(term in blob for term in EVIDENCE_ROUTER_SECURITY_TERMS) and signal != "security":
        score += 22
        reasons.append("security-sensitive intent +22")
    if any(term in blob for term in EVIDENCE_ROUTER_DESTRUCTIVE_TERMS):
        score += 20
        reasons.append("destructive or migration workflow +20")
    constraints = request.get("constraints")
    if isinstance(constraints, list) and any(
        "no test" in str(item).lower() or "skip test" in str(item).lower()
        for item in constraints
    ):
        score += 10
        reasons.append("verification constraint +10")
    return {"score": max(0, min(score, 100)), "reasons": reasons}


def evidence_router_graph_state(request):
    graph = request.get("codebase_graph")
    if graph is None and isinstance(request.get("evidence_state"), dict):
        graph = request["evidence_state"].get("codebase_graph")
    return graph if isinstance(graph, dict) else {}


def evidence_cost_estimate(cost_class, evidence_type):
    cost_class = str(cost_class or "low").lower()
    relative = {"low": 1, "medium": 3, "high": 6}.get(cost_class, 3)
    tool_calls = relative
    if evidence_type in {"source", "manifest", "consumer_asset"}:
        tool_calls = max(1, relative - 1)
    return {
        "class": cost_class if cost_class in {"low", "medium", "high"} else "medium",
        "relative_units": relative,
        "tool_calls": tool_calls,
        "telemetry": "estimate_not_real_usage",
    }


def build_evidence_plan(request, task_row, classification_confidence):
    plan = []
    limitations = []
    fallbacks = []
    paths = request_paths(request)
    for raw in task_row.get("evidence", []):
        if not isinstance(raw, dict):
            continue
        item = {
            "type": str(raw.get("type") or "source"),
            "source": str(raw.get("source") or "affected source files"),
            "required": bool(raw.get("required", True)),
            "freshness": str(raw.get("freshness") or "current"),
            "coverage": str(raw.get("coverage") or "affected_paths"),
            "confidence": round(
                min(classification_confidence, 0.95 if paths else 0.76),
                2,
            ),
            "estimated_cost": evidence_cost_estimate(
                raw.get("estimated_cost"), raw.get("type"),
            ),
            "trust": str(raw.get("trust") or "source"),
            "fallback": str(raw.get("fallback") or "read affected source directly"),
        }
        plan.append(item)
        if item["fallback"] not in fallbacks:
            fallbacks.append(item["fallback"])

    graph = evidence_router_graph_state(request)
    if graph:
        freshness = str(graph.get("freshness") or graph.get("status") or "unknown").lower()
        coverage = str(graph.get("coverage") or "unknown").lower()
        graph_ok = freshness in {"fresh", "current", "loaded"} and coverage in {
            "full", "complete", "affected_paths",
        }
        plan.append({
            "type": "code_graph",
            "source": "repo-local codebase index",
            "required": False,
            "freshness": freshness,
            "coverage": coverage,
            "confidence": 0.90 if graph_ok else 0.45,
            "estimated_cost": evidence_cost_estimate("low", "code_graph"),
            "trust": "derived_index" if graph_ok else "untrusted_index",
            "fallback": "read source directly and run an independent verification",
        })
        if not graph_ok:
            limitations.append(
                "codebase graph is stale, partial, or ambiguous; it is not source-grounded evidence"
            )
            fallbacks.append("read source directly and run an independent verification")

    blob = evidence_router_intent_blob(request)
    if EVIDENCE_ROUTER_NEGATIVE_CLAIM.search(blob):
        plan.append({
            "type": "coverage_search",
            "source": "source tree and manifests",
            "required": True,
            "freshness": "current",
            "coverage": "complete_claim_scope",
            "confidence": 0.75,
            "estimated_cost": evidence_cost_estimate("medium", "coverage_search"),
            "trust": "source",
            "fallback": "ask the user to narrow the negative claim or verify every claimed surface",
        })
        limitations.append(
            "negative claim requires explicit coverage before it can be accepted"
        )
        fallbacks.append(
            "ask the user to narrow the negative claim or verify every claimed surface"
        )

    conflicts = request.get("evidence_conflicts")
    if isinstance(conflicts, list) and conflicts:
        limitations.append("evidence conflicts require source-first resolution")
        fallbacks.append("read source and run an independent verification before execution")
    return plan, sorted(set(fallbacks)), limitations


def evidence_router_context_plan(task_row, request):
    context = []
    for source in task_row.get("context", []):
        if not non_empty_string(source):
            continue
        context.append({
            "source": source,
            "reason": "declarative task/evidence matrix",
            "required": True,
            "estimated_cost": "low",
        })
    paths = request_paths(request)
    if paths:
        context.append({
            "source": paths,
            "reason": "affected source scope",
            "required": True,
            "estimated_cost": "bounded_by_budget",
        })
    return context


def evidence_router_tool_plan(task_row, capability_result):
    caps = capability_result.get("capabilities", {})
    plan = []
    for tool in task_row.get("tools", []):
        if not non_empty_string(tool):
            continue
        discovery = caps.get("mcp_tool_discovery", "unavailable")
        plan.append({
            "tool": tool,
            "required": False,
            "mode": discovery,
            "reason": "selected by task/evidence matrix",
            "fallback": "use the source or repository CLI directly",
        })
    return plan


def evidence_router_verification_plan(task_row, evidence_plan, mandatory_review):
    plan = []
    for method in task_row.get("verification", []):
        if not non_empty_string(method):
            continue
        plan.append({
            "method": method,
            "required": True,
            "evidence_types": sorted({
                item["type"] for item in evidence_plan if item.get("required")
            }),
        })
    if mandatory_review and not any("review" in str(x.get("method", "")).lower() for x in plan):
        plan.append({
            "method": "independent safety review",
            "required": True,
            "evidence_types": ["review"],
        })
    return plan


def evidence_router_budget(request, capability_result):
    supplied = request.get("budget")
    if not isinstance(supplied, dict):
        supplied = {}
    budget = dict(EVIDENCE_ROUTER_DEFAULT_BUDGET)
    for key in budget:
        value = supplied.get(key)
        if isinstance(value, int) and value >= 0:
            budget[key] = value
    budget["max_roles"] = min(budget["max_roles"], 3)
    budget["max_repair_loops"] = min(budget["max_repair_loops"], 1)
    for key in ("max_usd", "remaining_tool_calls", "remaining_seconds"):
        value = supplied.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            budget[key] = value
    exhausted = bool(supplied.get("exhausted"))
    if budget.get("max_tool_calls") == 0 or budget.get("remaining_tool_calls") == 0:
        exhausted = True
    caps = capability_result.get("capabilities", {})
    budget["model_cost"] = (
        "measured"
        if caps.get("cost_telemetry") == "native"
        and caps.get("token_telemetry") == "native"
        else "advisory"
    )
    budget["hard_limits"] = [
        "max_roles", "max_repair_loops", "max_tool_calls", "max_files",
        "max_bytes", "tool_timeout_seconds",
    ]
    budget["exhausted"] = exhausted
    return budget


def load_specialist_candidates(request):
    registry = load_json_file(SPECIALIST_REGISTRY)
    candidates = []
    if isinstance(registry, dict) and isinstance(registry.get("specialists"), list):
        candidates.extend(registry["specialists"])
    for rel in (".piloth/specialists.json", "piloth-specialists.json"):
        consumer_registry = load_json_file(REPO_ROOT / rel)
        rows = (
            consumer_registry.get("specialists")
            if isinstance(consumer_registry, dict)
            else None
        )
        if isinstance(rows, list):
            candidates = rows[:100] + candidates
    supplied = request.get("specialists")
    if isinstance(supplied, list):
        candidates = supplied[:100] + candidates
    deduped = []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("id") or "").strip()
        if not candidate_id or candidate_id in seen:
            continue
        seen.add(candidate_id)
        deduped.append(item)
    return deduped


def specialist_score_candidate(candidate, request, signal, task_class, evidence_types, floor=None):
    reasons = []
    disqualified = []
    owner = str(candidate.get("owner") or "consumer").strip().lower()
    domains = {
        normalize_task_signal(x) for x in candidate.get("domains", [])
        if isinstance(x, str)
    }
    task_types = {
        str(x).strip() for x in candidate.get("task_types", [])
        if isinstance(x, str)
    }
    domain_score = 35 if signal in domains or task_class in task_types else 0
    reasons.append(f"domain_match={domain_score}/35")

    supported_evidence = {
        str(x).strip() for x in candidate.get("evidence_types", [])
        if isinstance(x, str)
    }
    intersection = supported_evidence & evidence_types
    evidence_score = round(
        25 * len(intersection) / max(1, len(evidence_types)),
        2,
    )
    reasons.append(f"evidence_capability={evidence_score}/25")

    required_tools = {
        str(x).strip() for x in candidate.get("tools", [])
        if isinstance(x, str) and str(x).strip()
    }
    available_tools = {
        str(x).strip() for x in request.get("available_tools", [])
        if isinstance(x, str) and str(x).strip()
    }
    missing_tools = sorted(required_tools - available_tools)
    tool_score = 15 if not missing_tools else 0
    reasons.append(f"tool_readiness={tool_score}/15")
    if missing_tools:
        disqualified.append("missing tools: " + ", ".join(missing_tools))

    try:
        confidence = float(candidate.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))
    historical_score = round(confidence * 15, 2)
    reasons.append(f"historical_quality={historical_score}/15")

    cost_score = {"low": 10, "cheap": 10, "standard": 7, "high": 3, "premium": 3}.get(
        str(candidate.get("cost_class") or "").lower(),
        0,
    )
    reasons.append(f"cost={cost_score}/10")

    health = str(candidate.get("health") or "unknown").lower()
    if health not in {"healthy", "ready"}:
        disqualified.append(f"health={health}")
    adapter, _ = resolve_adapter(request)
    support = {
        str(x).lower() for x in candidate.get("adapter_support", [])
        if isinstance(x, str)
    }
    if support and adapter not in support:
        disqualified.append(f"adapter {adapter} unsupported")
    mandatory_review = evidence_router_requires_independent_review(request, signal)
    required_permission = "review" if mandatory_review else "edit"
    permissions = {
        str(x).lower() for x in candidate.get("permissions", [])
        if isinstance(x, str)
    }
    if required_permission not in permissions:
        disqualified.append(f"missing {required_permission} permission")

    score = round(domain_score + evidence_score + tool_score + historical_score + cost_score, 2)
    if floor is None:
        floor = evidence_router_quality_floor()
    return {
        "id": str(candidate.get("id") or ""),
        "owner": owner,
        "score": score,
        "qualified": score >= floor["specialist_score"] and not disqualified,
        "reasons": reasons,
        "disqualified_reasons": disqualified,
        "permissions": sorted(permissions),
    }


def select_specialist(request, signal, task_class, evidence_plan, floor=None):
    evidence_types = {
        item.get("type") for item in evidence_plan
        if isinstance(item, dict) and item.get("required")
    }
    if floor is None:
        floor = evidence_router_quality_floor()
    ranked = [
        specialist_score_candidate(
            item, request, signal, task_class, evidence_types, floor,
        )
        for item in load_specialist_candidates(request)
    ]
    ranked.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    qualified_consumers = [
        item for item in ranked
        if item["qualified"] and item["owner"] == "consumer"
    ]
    qualified_piloth = [
        item for item in ranked
        if item["qualified"] and item["owner"] == "piloth"
    ]
    selected = (
        qualified_consumers[0] if qualified_consumers
        else qualified_piloth[0] if qualified_piloth
        else None
    )
    return selected, ranked[:20]


def evidence_router_requires_independent_review(request, signal):
    blob = evidence_router_intent_blob(request)
    return (
        signal in {"security", "release/deploy"}
        or "data migration" in blob
        or any(term in blob for term in EVIDENCE_ROUTER_DESTRUCTIVE_TERMS)
    )


def evidence_router_work_packages(request):
    supplied = request.get("work_packages")
    packages = []
    if isinstance(supplied, list):
        for index, item in enumerate(supplied[:10]):
            if isinstance(item, str) and item.strip():
                packages.append({
                    "id": f"wp-{index + 1}",
                    "scope": item.strip(),
                    "independent": True,
                })
            elif isinstance(item, dict) and non_empty_string(item.get("scope") or item.get("id")):
                packages.append({
                    "id": safe_evidence_id(item.get("id")) or f"wp-{index + 1}",
                    "scope": str(item.get("scope") or item.get("id")).strip(),
                    "independent": item.get("independent") is True,
                })
    return packages


def evidence_router_team_score(request, risk, specialist, mandatory_review):
    paths = request_paths(request)
    packages = evidence_router_work_packages(request)
    independent_count = len([item for item in packages if item.get("independent")])
    complexity = min(
        20,
        (8 if len(paths) > 3 else 3 if paths else 5)
        + (7 if len({
            normalize_relative_path_text(p).split("/", 1)[0]
            for p in paths if p and not path_pattern_is_broad(p)
        }) >= 2 else 0)
        + (5 if len(paths) > 8 else 0),
    )
    components = {
        "risk": round(min(25, risk.get("score", 0) * 0.25), 2),
        "complexity": complexity,
        "specialist_need": 20 if specialist else (15 if mandatory_review else 5),
        "independent_review_value": 20 if mandatory_review else (12 if risk.get("score", 0) >= 55 else 4),
        "parallelism_value": min(15, independent_count * 7.5),
        "coordination_cost": 8 if independent_count >= 2 else 22,
    }
    score = round(
        components["risk"]
        + components["complexity"]
        + components["specialist_need"]
        + components["independent_review_value"]
        + components["parallelism_value"]
        - components["coordination_cost"],
        2,
    )
    return max(0, min(score, 100)), components, packages, independent_count


def load_model_tiers():
    registry = load_json_file(MODEL_CAPABILITY_REGISTRY)
    tiers = registry.get("tiers") if isinstance(registry, dict) else None
    if not isinstance(tiers, list):
        tiers = [
            {"id": "economy", "cost_order": 1, "max_risk": 35, "min_route_confidence": 0.9, "benchmarked": True},
            {"id": "standard", "cost_order": 2, "max_risk": 70, "min_route_confidence": 0.8, "benchmarked": True},
            {"id": "premium", "cost_order": 3, "max_risk": 100, "min_route_confidence": 0.0, "benchmarked": True},
        ]
    return sorted(
        [item for item in tiers if isinstance(item, dict)],
        key=lambda item: item.get("cost_order", 999),
    )


def select_model_tier(risk_score, confidence, request):
    failed_repairs = request.get("failed_repairs", 0)
    if isinstance(failed_repairs, int) and failed_repairs >= 1:
        return "premium", "raised after a failed repair"
    signal = normalize_task_signal(request.get("_classified_signal"))
    for tier in load_model_tiers():
        if tier.get("benchmarked") is not True:
            continue
        if risk_score > int(tier.get("max_risk", 0)):
            continue
        if confidence < float(tier.get("min_route_confidence", 1.0)):
            continue
        domains = {
            normalize_task_signal(item)
            for item in tier.get("domains", [])
            if isinstance(item, str)
        }
        if domains and signal not in domains:
            continue
        return str(tier.get("id") or "premium"), "cheapest benchmarked tier meeting risk/confidence floor"
    return "premium", "raised because no cheaper benchmarked tier meets the floor"


def evidence_router_execution_roles(
    team, mode, mandatory_review, specialist, max_roles, limitations,
):
    roles = []
    if team:
        roles = [
            {"id": "lead", "permissions": ["plan", "review"], "read_only": True},
            {"id": "executor", "permissions": ["edit"], "read_only": False},
            {"id": "reviewer", "permissions": ["review", "qa"], "read_only": True},
        ][:max_roles]
        if len(roles) < 3:
            team = False
            mode = "single_with_external_review" if mandatory_review else "single"
            limitations.append(
                "max_roles budget cannot preserve the three-role team contract"
            )
            roles = []
    if not team and mandatory_review and not roles:
        roles = [{
            "id": "external_reviewer",
            "permissions": ["review", "qa"],
            "read_only": True,
            "required": True,
        }]
    if specialist:
        target_role = "reviewer" if mandatory_review else "executor"
        for role in roles:
            if role.get("id") == target_role:
                role["specialist_id"] = specialist.get("id")
    return roles, team, mode


def evidence_router_execution_plan(
    request, risk, confidence, specialist, ranked, capability_result, budget, floor=None,
):
    if floor is None:
        floor = evidence_router_quality_floor()
    signal = request.get("_classified_signal", "not_applicable")
    mandatory_review = evidence_router_requires_independent_review(request, signal)
    team_score, components, packages, independent_count = evidence_router_team_score(
        request, risk, specialist, mandatory_review,
    )
    caps = capability_result.get("capabilities", {})
    overrides = request.get("user_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
    forced = str(
        overrides.get("execution_mode")
        or ("team" if overrides.get("force_team") is True else "")
        or ("single" if overrides.get("force_single") is True else "")
    ).lower()
    team_capable = (
        caps.get("subagent_spawn") in {"native", "emulated"}
        and caps.get("role_permissions") in {"native", "emulated"}
    )
    team_floor = floor["team_score"]
    team_eligible = team_score >= team_floor and independent_count >= 2 and not budget["exhausted"]
    reasons = [
        f"team score={team_score} (threshold {team_floor})",
        f"independent work packages={independent_count}",
    ]
    limitations = []
    if forced == "team":
        team_eligible = independent_count >= 2 and not budget["exhausted"]
        reasons.append("user forced team mode")
    elif forced == "single":
        team_eligible = False
        reasons.append("user forced single mode")

    if mandatory_review and forced == "single":
        reasons.append("safety reviewer overrides forced single acceptance")
    if mandatory_review and not team_capable:
        limitations.append(
            "adapter cannot spawn an independent reviewer; external independent review is required"
        )
        team = False
        mode = "single_with_external_review"
    elif mandatory_review:
        team = True
        mode = "team"
    elif team_eligible and team_capable:
        team = True
        mode = "team"
    else:
        team = False
        mode = "single"
        if team_eligible and not team_capable:
            limitations.append(
                "team score passed but adapter subagent spawn is unavailable; using single-agent fallback"
            )
    if budget["exhausted"]:
        team = False
        mode = "single_source_first"
        reasons.append("budget exhausted: parallelism disabled")

    roles, team, mode = evidence_router_execution_roles(
        team, mode, mandatory_review, specialist, budget["max_roles"], limitations,
    )
    for role in roles:
        role["allowed_paths"] = (
            request_paths(request) if role.get("id") == "executor" else []
        )
    if team and caps.get("parallel_execution") == "unavailable":
        limitations.append(
            "parallel execution unavailable; independent roles must run sequentially"
        )

    tier, tier_reason = select_model_tier(risk.get("score", 0), confidence, request)
    model_roles = [role["id"] for role in roles] or ["executor"]
    model_tiers = {role: tier for role in model_roles}
    if caps.get("model_pinning") == "unavailable":
        limitations.append("model tier is advisory because adapter model pinning is unavailable")
    return {
        "mode": mode,
        "team": team,
        "roles": roles,
        "model_tiers": model_tiers,
        "model_tier_reason": tier_reason,
        "specialist": specialist,
        "specialist_candidates": ranked,
        "team_score": team_score,
        "team_score_components": components,
        "work_packages": packages,
        "max_repair_loops": budget["max_repair_loops"],
        "mandatory_independent_review": mandatory_review,
        "decision_reasons": reasons,
    }, limitations


def evidence_router_rollout(request):
    overrides = request.get("user_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
    kill_switch = overrides.get("kill_switch") is True or os.environ.get(
        "PILOTHOS_EVIDENCE_ROUTER_KILL_SWITCH", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    if kill_switch:
        return "off", True
    raw = str(
        overrides.get("rollout")
        or request.get("router_mode")
        or os.environ.get("PILOTHOS_EVIDENCE_ROUTER_MODE", "advisory")
    ).strip().lower()
    return (raw if raw in EVIDENCE_ROUTER_ROLLOUT_MODES else "advisory"), False


def evidence_router_enforcement_capability_gaps(capability_result):
    caps = capability_result.get("capabilities", {})
    required = (
        "pre_edit_hooks", "post_edit_hooks", "stop_hooks",
        "approval_controls", "sandbox_controls",
        "receipt_enforcement", "seal_enforcement",
    )
    return [
        key for key in required
        if caps.get(key) not in {"native", "emulated"}
    ]


def evidence_route_rejected(errors):
    return {
        "result": "evidence_route_rejected",
        "decision_id": "",
        "task_class": "",
        "risk": {"score": 0, "reasons": []},
        "confidence": 0.0,
        "evidence_plan": [],
        "context_plan": [],
        "execution_plan": {
            "mode": "single",
            "team": False,
            "roles": [],
            "model_tiers": {},
        },
        "tool_plan": [],
        "verification_plan": [],
        "budgets": {},
        "fallbacks": [],
        "limitations": [],
        "decision_reasons": [],
        "errors": errors,
    }


def evidence_route_request_errors(request):
    errors = []
    if "intent" in request and not isinstance(request.get("intent"), str):
        errors.append("intent must be a string")
    elif len(request.get("intent") or "") > 10_000:
        errors.append("intent exceeds 10000 characters")
    if "locale" in request and not isinstance(request.get("locale"), str):
        errors.append("locale must be a string")
    for field in ("affected_paths", "changed_paths", "allowed_paths", "target_paths"):
        if field not in request:
            continue
        value = request.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            errors.append(f"{field} must be a list of strings")
            continue
        if len(value) > 1000:
            errors.append(f"{field} exceeds 1000 entries")
            continue
        for path in value:
            if not path_pattern_is_safe(path):
                errors.append(f"{field} contains unsafe pattern: {path}")
    constraints = request.get("constraints")
    if constraints is not None and (
        not isinstance(constraints, list)
        or any(not isinstance(item, str) for item in constraints)
    ):
        errors.append("constraints must be a list of strings")
    elif isinstance(constraints, list) and len(constraints) > 100:
        errors.append("constraints exceeds 100 entries")
    for field in ("budget", "user_overrides"):
        if field in request and not isinstance(request.get(field), dict):
            errors.append(f"{field} must be an object")
    specialists = request.get("specialists")
    if specialists is not None and (
        not isinstance(specialists, list)
        or any(not isinstance(item, dict) for item in specialists)
    ):
        errors.append("specialists must be a list of objects")
    elif isinstance(specialists, list) and len(specialists) > 100:
        errors.append("specialists exceeds 100 entries")
    return errors


def evidence_router_localized_summary(request, task_class, execution_plan):
    locale = str(request.get("locale") or request.get("language") or "en").lower()
    language = locale.split("-", 1)[0].split("_", 1)[0]
    mode = execution_plan.get("mode", "single")
    if language == "vi":
        summary = (
            f"Đã phân loại {task_class}; chọn chế độ {mode} với bằng chứng "
            "tối thiểu đáp ứng quality floor."
        )
    else:
        summary = (
            f"Classified {task_class}; selected {mode} with the smallest "
            "evidence set meeting the quality floor."
        )
    return locale, summary


def evidence_route_output(
    request, matrix, matrix_source, signal, task_class, class_reasons, risk,
    confidence, evidence_plan, context_plan, execution_plan, tool_plan,
    verification_plan, budget, capability_result, specialist, fallbacks,
    limitations, rollout, requested_rollout, kill_switch,
):
    decision_basis = {
        "request": sanitize_state_value(request, limit=1000),
        "signal": signal,
        "task_class": task_class,
        "risk": risk,
        "confidence": confidence,
        "rollout": rollout,
        "matrix_sha256": sha256_json(matrix),
        "evidence_plan": evidence_plan,
        "execution_plan": execution_plan,
        "adapter_capabilities": capability_result.get("capabilities", {}),
    }
    floor = evidence_router_quality_floor(matrix)
    reasons = class_reasons + [
        f"matrix_source={matrix_source}",
        f"rollout={rollout}",
        f"selected smallest declared evidence set for {task_class}",
    ] + execution_plan.pop("decision_reasons", [])
    if specialist:
        reasons.append(
            f"selected {specialist['owner']} specialist {specialist['id']} score={specialist['score']}"
        )
    else:
        reasons.append(
            f"no specialist met the {floor['specialist_score']}/100 "
            "health/tool/permission floor"
        )
    locale, localized_summary = evidence_router_localized_summary(
        request, task_class, execution_plan,
    )
    return {
        "result": "evidence_route",
        "schema_version": 1,
        "read_only": True,
        "locale": locale,
        "decision_summary": localized_summary,
        "decision_id": "er-" + sha256_json(decision_basis)[:16],
        "task_signal": TASK_SIGNAL_ROUTES.get(signal, {}).get("task_signal", signal),
        "task_class": task_class,
        "risk": risk,
        "confidence": confidence,
        "evidence_plan": evidence_plan,
        "context_plan": context_plan,
        "execution_plan": execution_plan,
        "tool_plan": tool_plan,
        "verification_plan": verification_plan,
        "budgets": budget,
        "fallbacks": sorted(set(fallbacks)),
        "limitations": sorted(set(limitations)),
        "decision_reasons": reasons,
        "adapter_capabilities": capability_result,
        "rollout": {
            "mode": rollout,
            "requested_mode": requested_rollout,
            "kill_switch": kill_switch,
            # The merged floor, i.e. the thresholds that actually governed this
            # decision — not the raw registry block, which may omit keys.
            "quality_floor": floor,
        },
    }


def evidence_route_digest(decision):
    """The acting half of a route decision; `--verbose` and state keep the rest.

    A full decision is ~1.8-2.3k tokens, and `os-start` plus every `os-status`
    reprinted it even though the same blob is already persisted to
    `contract.json` and the run state. The digest keeps what changes what the
    agent does next — plan, gates, budgets, limitations — and drops the
    provenance that gate logic reads from state rather than from stdout.
    """
    if not isinstance(decision, dict) or decision.get("result") != "evidence_route":
        return decision
    execution = decision.get("execution_plan") or {}
    capabilities = decision.get("adapter_capabilities") or {}
    rollout = decision.get("rollout") or {}
    specialist = execution.get("specialist") or {}

    def items(key):
        return [x for x in (decision.get(key) or []) if isinstance(x, dict)]

    return {
        "result": decision.get("result"),
        "schema_version": decision.get("schema_version"),
        "digest": True,
        "decision_id": decision.get("decision_id"),
        "decision_summary": decision.get("decision_summary"),
        "task_signal": decision.get("task_signal"),
        "task_class": decision.get("task_class"),
        "risk": decision.get("risk"),
        "confidence": decision.get("confidence"),
        "adapter": {
            "adapter": capabilities.get("adapter"),
            "source": capabilities.get("adapter_source"),
            "degraded": capabilities.get("degraded", []),
        },
        "rollout": {
            "mode": rollout.get("mode"),
            "kill_switch": rollout.get("kill_switch"),
        },
        "execution": {
            "mode": execution.get("mode"),
            "controls_execution": execution.get("controls_execution"),
            "team": execution.get("team"),
            "roles": execution.get("roles", []),
            "mandatory_independent_review": execution.get(
                "mandatory_independent_review",
            ),
            "max_repair_loops": execution.get("max_repair_loops"),
            "model_tiers": execution.get("model_tiers", {}),
            "specialist": specialist.get("id", ""),
        },
        "evidence_plan": [
            {
                "type": item.get("type"),
                "source": item.get("source"),
                "required": item.get("required"),
            }
            for item in items("evidence_plan")
        ],
        "verification_plan": [
            {"method": item.get("method"), "required": item.get("required")}
            for item in items("verification_plan")
        ],
        "context_plan": [item.get("source") for item in items("context_plan")],
        "tool_plan": [item.get("tool") for item in items("tool_plan")],
        # hard_limits only names keys that are already present alongside it.
        "budgets": {
            key: value
            for key, value in (decision.get("budgets") or {}).items()
            if key != "hard_limits"
        },
        "limitations": decision.get("limitations", []),
        "fallbacks": decision.get("fallbacks", []),
        "verbose_with": "--verbose (evidence-route/os-status) or the run's contract.json",
    }


def finalize_evidence_route(
    request, matrix, matrix_source, signal, task_class, class_reasons, risk, confidence, evidence_plan, context_plan,
    execution_plan, tool_plan, verification_plan, budget, capability_result, specialist, evidence_fallbacks, evidence_limitations, execution_limitations,
):
    rollout, kill_switch = evidence_router_rollout(request)
    requested_rollout = rollout
    limitations = (
        evidence_limitations
        + execution_limitations
        + capability_result.get("limitations", [])
    )
    fallbacks = list(evidence_fallbacks)
    floor = evidence_router_quality_floor(matrix)
    if confidence < floor["route_confidence"]:
        fallbacks.append(
            "read source, run another verification, or ask the user before relying on the route"
        )
    if budget["exhausted"]:
        fallbacks.extend([
            "stop parallelism and use single-agent source-first execution",
            "ask the user when the quality floor still cannot be demonstrated",
        ])
    if kill_switch or rollout == "off":
        execution_plan["mode"] = "legacy_source_only"
        execution_plan["team"] = False
        execution_plan["roles"] = []
        execution_plan["model_tiers"] = {}
        fallbacks.append("legacy scheduler and source-only routing")
    elif rollout == "shadow":
        execution_plan["controls_execution"] = False
    elif rollout == "advisory":
        execution_plan["controls_execution"] = False
        execution_plan["override_requires_reason"] = True
    elif rollout == "enforced":
        enforcement_gaps = evidence_router_enforcement_capability_gaps(
            capability_result,
        )
        if enforcement_gaps:
            rollout = "advisory"
            execution_plan["controls_execution"] = False
            execution_plan["override_requires_reason"] = True
            limitations.append(
                "enforced rollout unavailable; adapter capability gaps: "
                + ", ".join(enforcement_gaps)
            )
            fallbacks.append("use advisory routing until the adapter passes the capability contract")
        else:
            execution_plan["controls_execution"] = True
    else:
        execution_plan["controls_execution"] = False
    return evidence_route_output(
        request, matrix, matrix_source, signal, task_class, class_reasons, risk,
        confidence, evidence_plan, context_plan, execution_plan, tool_plan,
        verification_plan, budget, capability_result, specialist, fallbacks,
        limitations, rollout, requested_rollout, kill_switch,
    )


def evidence_router_review_evidence_present(receipt, os_evidence):
    review = receipt.get("independent_review")
    if isinstance(review, dict):
        result = str(review.get("result") or review.get("status") or "").upper()
        if result == "PASS" and non_empty_string(review.get("evidence")):
            return True
    for item in os_evidence or []:
        if not isinstance(item, dict):
            continue
        gate = str(item.get("quality_gate") or item.get("gate") or "").lower()
        result = str(item.get("result") or item.get("status") or "").lower()
        if "review" in gate and result in {"pass", "passed", "approve", "approved"}:
            return True
    return False


def evidence_router_receipt_errors(contract, receipt, os_evidence=None, floor=None):
    if not isinstance(contract, dict) or not isinstance(receipt, dict):
        return []
    router = contract.get("evidence_router")
    if not isinstance(router, dict):
        return []
    rollout = router.get("rollout")
    rollout_mode = rollout.get("mode") if isinstance(rollout, dict) else "advisory"
    if floor is None:
        # Judge the receipt against the floor that was in force when the route was
        # decided — the decision records it — rather than whatever the registry
        # says now. Editing the registry mid-task must not retroactively change
        # what an already-issued route demanded.
        recorded = rollout.get("quality_floor") if isinstance(rollout, dict) else None
        floor = evidence_router_quality_floor(
            {"quality_floor": recorded} if isinstance(recorded, dict) else None
        )
    execution = router.get("execution_plan")
    if not isinstance(execution, dict):
        execution = {}
    errors = []
    receipt_decision = receipt.get("decision_id")
    if receipt_decision and receipt_decision != router.get("decision_id"):
        errors.append("receipt decision_id does not match the active Evidence Router decision")
    actual_mode = receipt.get("execution_mode")
    planned_mode = execution.get("mode")
    if (
        non_empty_string(actual_mode)
        and actual_mode != planned_mode
        and not non_empty_string(receipt.get("router_override_reason"))
    ):
        errors.append("router_override_reason is required when execution_mode overrides the route")
    if rollout_mode != "enforced":
        return errors
    if not non_empty_string(receipt_decision):
        errors.append("decision_id is required by enforced Evidence Router rollout")
    if float(router.get("confidence", 0)) < floor["route_confidence"] and not non_empty_string(
        receipt.get("router_low_confidence_resolution")
    ):
        errors.append(
            "router_low_confidence_resolution is required before accepting an enforced low-confidence route"
        )
    required_types = {
        item.get("type")
        for item in router.get("evidence_plan", [])
        if isinstance(item, dict) and item.get("required") is True
    }
    context_used = receipt.get("context_used")
    if required_types & {"source", "manifest"} and not (
        isinstance(context_used, list) and context_used
    ):
        errors.append("enforced source/manifest evidence requires receipt context_used")
    command = str(receipt.get("verification_command") or "").lower()
    if "test" in required_types and (
        not command or any(term in command for term in ("not run", "skipped", "failed"))
    ):
        errors.append("enforced test evidence requires a clean verification_command")
    if "review" in required_types and not evidence_router_review_evidence_present(
        receipt, os_evidence or [],
    ):
        errors.append("enforced review evidence requires an independent PASS with evidence")
    if "consumer_asset" in required_types and not receipt.get("consumer_asset_routing"):
        errors.append("enforced consumer asset evidence requires consumer_asset_routing")
    if "coverage_search" in required_types and not receipt.get("coverage_evidence"):
        errors.append("enforced negative-claim evidence requires coverage_evidence")
    if "visual" in required_types:
        gates = receipt.get("quality_gates")
        ui = gates.get("ui_quality") if isinstance(gates, dict) else None
        if not isinstance(ui, dict) or ui.get("result") != "PASS":
            errors.append("enforced visual evidence requires quality_gates.ui_quality PASS")
    return errors


def evidence_route_payload(request):
    if not isinstance(request, dict):
        return evidence_route_rejected(["request must be a JSON object"])
    request_errors = evidence_route_request_errors(request)
    if request_errors:
        return evidence_route_rejected(request_errors)
    matrix, matrix_source = load_evidence_router_matrix()
    floor = evidence_router_quality_floor(matrix)
    signal, class_confidence, class_reasons, errors = classify_evidence_task(
        request, matrix,
    )
    if errors:
        return evidence_route_rejected(errors)
    task_row = matrix["task_matrix"].get(signal, {})
    task_class = str(task_row.get("task_class") or "small_task")
    risk = evidence_router_risk(request, signal, task_row)
    # Pass the request's adapter through untouched (absent stays absent) so
    # resolve_adapter can fall back to env detection instead of being pinned to
    # "unknown" before it ever runs.
    capability_request = {
        "adapter": request.get("adapter"),
        "adapter_capabilities": request.get("adapter_capabilities") or {},
    }
    capability_result = adapter_capabilities_payload(capability_request)
    if capability_result.get("result") == "adapter_capabilities_rejected":
        return evidence_route_rejected(capability_result.get("errors", []))
    evidence_plan, evidence_fallbacks, evidence_limitations = build_evidence_plan(
        request, task_row, class_confidence,
    )
    confidence = class_confidence
    if not request_paths(request):
        confidence -= 0.08
    # Per-evidence-item floor, a different question from route_confidence: one weak
    # item caps the route's confidence just below the route floor.
    if any(item.get("confidence", 1.0) < floor["evidence_item_confidence"] for item in evidence_plan):
        confidence = min(confidence, 0.78)
    conflicts = request.get("evidence_conflicts")
    if isinstance(conflicts, list) and conflicts:
        confidence = min(confidence, 0.65)
    confidence = round(max(0.0, min(confidence, 1.0)), 2)

    budget = evidence_router_budget(request, capability_result)
    specialist, ranked = select_specialist(
        request, signal, task_class, evidence_plan, floor,
    )
    execution_request = dict(request)
    execution_request["_classified_signal"] = signal
    execution_plan, execution_limitations = evidence_router_execution_plan(
        execution_request,
        risk,
        confidence,
        specialist,
        ranked,
        capability_result,
        budget,
        floor,
    )
    mandatory_review = execution_plan.get("mandatory_independent_review", False)
    context_plan = evidence_router_context_plan(task_row, request)
    tool_plan = evidence_router_tool_plan(task_row, capability_result)
    verification_plan = evidence_router_verification_plan(
        task_row, evidence_plan, mandatory_review,
    )
    return finalize_evidence_route(
        request, matrix, matrix_source, signal, task_class, class_reasons,
        risk, confidence, evidence_plan, context_plan, execution_plan,
        tool_plan, verification_plan, budget, capability_result, specialist,
        evidence_fallbacks, evidence_limitations, execution_limitations,
    )


def evidence_route(argv):
    argv = list(argv)
    if "--explain" in argv:
        json_print(evidence_router_schema_payload())
        return
    verbose = "--verbose" in argv
    argv = [a for a in argv if a != "--verbose"]
    try:
        request, _ = json_arg_or_stdin(argv, "evidence-route")
    except Exception as e:
        json_print({
            "result": "evidence_route_rejected",
            "errors": [str(e)],
        })
        return
    decision = evidence_route_payload(request)
    json_print(decision if verbose else evidence_route_digest(decision))

# -------------------------------------------------------------- scheduler v4

def scheduler_history_status():
    if not SCHEDULER_HISTORY.exists():
        return "missing"
    try:
        with open(SCHEDULER_HISTORY, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    json.loads(line)
        return "loaded"
    except (OSError, json.JSONDecodeError):
        return "fallback_corrupt_state"


def load_scheduler_history():
    status = scheduler_history_status()
    if status != "loaded":
        return status, []
    entries = []
    try:
        with open(SCHEDULER_HISTORY, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("repo_key") == REPO_KEY:
                    entries.append(item)
    except (OSError, json.JSONDecodeError):
        return "fallback_corrupt_state", []
    return status, entries[-50:]


DEPRECATED_HISTORY_TERMS = (
    "pilothos_hostd.py",
    "host-control-plane.md",
    "host authority",
    "host-level",
    "hostd",
    "PILOTH_HOST_ROOT",
    "macOS-inspired",
)


def scheduler_history_deprecated(item):
    if item.get("deprecated") is True:
        return True
    text = json.dumps(item, ensure_ascii=False)
    folded = text.casefold()
    return any(term.casefold() in folded for term in DEPRECATED_HISTORY_TERMS)


def scheduler_history_text_deprecated(value):
    if not non_empty_string(value):
        return False
    folded = str(value).casefold()
    return any(term.casefold() in folded for term in DEPRECATED_HISTORY_TERMS)


def scheduler_history_matches(entries, task_signal, layers):
    normalized_signal = normalize_task_signal(task_signal)
    layer_set = {normalize_layer(x) for x in layers}
    matches = []
    for item in reversed(entries):
        if scheduler_history_deprecated(item):
            continue
        item_signal = normalize_task_signal(item.get("task_signal"))
        item_layers = {normalize_layer(x) for x in item.get("changed_layers", [])}
        same_signal = item_signal == normalized_signal
        shared_layers = bool(layer_set & item_layers) if layer_set and item_layers else False
        result = str(item.get("result", "")).lower()
        if (same_signal or shared_layers) and "pass" in result:
            matches.append(item)
        if len(matches) >= 5:
            break
    return list(reversed(matches))


def scheduler_history_recommendations(matches):
    tests = []
    asset_types = []
    notes = []
    for item in matches:
        tests_run = item.get("tests_run")
        if non_empty_string(tests_run) and tests_run not in tests:
            tests.append(tests_run)
        for route in item.get("route_chosen", []):
            if isinstance(route, dict):
                asset_type = route.get("asset_type")
                decision = route.get("decision")
                if asset_type and decision in {"loaded", "approval_required"} and asset_type not in asset_types:
                    asset_types.append(asset_type)
        note = item.get("learning_decision")
        if non_empty_string(note) and note not in notes:
            notes.append(note)
    return {
        "tests": tests[:3],
        "asset_types": asset_types[:6],
        "notes": notes[:5],
    }


def scheduler_suite_for_paths(paths):
    rels = [normalize_relative_path_text(p) for p in paths]
    if not rels:
        return "tests/run_all.sh", "no paths supplied; full suite is the deterministic fallback"
    if all(is_docs_path(p) for p in rels):
        return "tests/docs/run-tests.sh", "docs-only change"
    if any(
        p.startswith("pilothOS/scripts/pilothos_installer.py")
        or is_source_installer_path(p)
        or p.startswith("tests/install/")
        for p in rels
    ):
        return "tests/install/run-tests.sh", "installer/staging change"
    if any("task-lifecycle" in p or "contract" in p or "receipt" in p or p.startswith("tests/lifecycle/") for p in rels):
        return "tests/lifecycle/run-tests.sh", "contract/receipt lifecycle change"
    if any(p.startswith("pilothOS/scripts/pilothos_guard.py") or p.startswith("pilothOS/evaluation/") or p.startswith("tests/evaluation/") for p in rels):
        return "tests/evaluation/run-tests.sh", "guard/evaluation policy change"
    layers = {layer_for_path(p) for p in rels}
    if len(layers) >= 3 or layers & {"Runtime", "Rules", "Tools/Runtime", "Installer", "Evaluation"}:
        return "tests/run_all.sh", "cross-layer PilothOS runtime/rules/evaluation change"
    if any(is_test_path(p) for p in rels):
        return "tests/lifecycle/run-tests.sh", "test/lifecycle-adjacent change"
    return "tests/run_all.sh", "conservative fallback"


def scheduler_context_for_paths(paths):
    context = {"pilothOS/runtime/context-loading.md", "pilothOS/runtime/energy-token-policy.md"}
    for rel in paths:
        layer = layer_for_path(str(rel))
        if layer == "Tools/Runtime":
            context.add("pilothOS/scripts/pilothos_guard.py")
            context.add("pilothOS/tools/index.md")
        elif layer == "Installer":
            context.add("pilothOS/scripts/pilothos_installer.py")
            context.add("scripts/stage.py")
            context.add("scripts/build_manifest.py")
            context.add("tests/install/run-tests.sh")
        elif layer == "Runtime":
            context.add("pilothOS/runtime/index.md")
        elif layer == "Rules":
            context.add("pilothOS/rules/index.md")
        elif layer == "Evaluation":
            context.add("pilothOS/evaluation/quality-gates.md")
        elif layer == "Agent Teams":
            context.add("pilothOS/runtime/team-orchestration.md")
            context.add("pilothOS/agent-teams/piloth-team.md")
    return sorted(context)


def scheduler_suggest_payload(payload):
    if not isinstance(payload, dict):
        return {"result": "scheduler_rejected", "errors": ["request must be a JSON object"]}
    paths = payload.get("affected_paths") or payload.get("changed_paths") or []
    if not isinstance(paths, list) or any(not isinstance(x, str) for x in paths):
        return {"result": "scheduler_rejected", "errors": ["affected_paths must be a list of strings"]}
    suite, suite_reason = scheduler_suite_for_paths(paths)
    task_signal = payload.get("task_signal", "not_applicable")
    route_key = normalize_task_signal(task_signal)
    route = TASK_SIGNAL_ROUTES.get(route_key, TASK_SIGNAL_ROUTES["not_applicable"])
    layers = sorted({layer_for_path(p) for p in paths})
    history, history_entries = load_scheduler_history()
    history_matches = scheduler_history_matches(history_entries, task_signal, layers)
    history_recs = scheduler_history_recommendations(history_matches)
    full_suite_expected = suite == "tests/run_all.sh"
    expected_evidence = [suite]
    if any(layer in {"Runtime", "Rules", "Tools/Runtime", "Installer", "Evaluation"} for layer in layers) and suite != "tests/run_all.sh":
        expected_evidence.append("tests/run_all.sh before release")
    for historical_test in history_recs["tests"]:
        if historical_test not in expected_evidence:
            expected_evidence.append(historical_test)
    recommended_asset_types = list(route["asset_types"])
    for asset_type in history_recs["asset_types"]:
        if asset_type not in recommended_asset_types:
            recommended_asset_types.append(asset_type)
    skeleton = {
        "task_scope": payload.get("intent") or f"{task_signal} task",
        "affected_layers": layers or ["Consumer"],
        "allowed_paths": paths or ["<fill allowed paths>"],
        "expected_evidence": expected_evidence,
        "out_of_scope_paths": [],
        "consumer_scope": "fill exact repo/userland scope",
        "context_evidence": [
            {
                "source": source,
                "reason": "scheduler-selected context",
                "finding": "load before editing affected layer",
            }
            for source in scheduler_context_for_paths(paths)[:8]
        ],
        "reuse_evidence": [
            {
                "asset": "reuse-scan",
                "decision": "reuse",
                "reason": "run reuse-scan before new helpers/components when code changes",
            }
        ],
        "decision_limits": ["Do not expand scope without updating this contract."],
        "consumer_asset_routing": [
            {
                "task_signal": route["task_signal"],
                "asset_type": asset_type,
                "decision": "loaded",
                "reason": "scheduler-selected asset type for task signal"
                + (" or successful local history" if asset_type in history_recs["asset_types"] else ""),
            }
            for asset_type in recommended_asset_types
        ],
    }
    if full_suite_expected:
        skeleton["energy_budget_reason"] = suite_reason
    result = {
        "result": "scheduler_suggested",
        "history_status": history,
        "history_matches": history_matches,
        "history_applied": bool(history_matches),
        "task_signal": task_signal,
        "affected_paths": paths,
        "recommended_context_files": scheduler_context_for_paths(paths),
        "recommended_consumer_asset_types": recommended_asset_types,
        "expected_evidence": expected_evidence,
        "risk_notes": [suite_reason] + [f"history learning decision: {note}" for note in history_recs["notes"]],
        "energy_budget": "broad" if full_suite_expected else "targeted",
        "energy_budget_reason": suite_reason,
        "contract_skeleton": skeleton,
        "fallback_used": history != "loaded",
    }
    # Compatibility wrapper for one major version. Existing scheduler fields
    # remain unchanged; new consumers should use evidence-route directly.
    if payload.get("_router_compat_only") is not True:
        result["evidence_router"] = evidence_route_digest(
            evidence_route_payload(payload),
        )
    return result


def scheduler_suggest(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "scheduler-suggest")
    except Exception as e:
        json_print({"result": "scheduler_rejected", "errors": [str(e)]})
        return
    json_print(scheduler_suggest_payload(payload))


def scheduler_record_task_signal(receipt):
    signal = receipt.get("task_signal")
    if non_empty_string(signal) and normalize_task_signal(signal) != "not_applicable":
        return signal
    routes = receipt.get("consumer_asset_routing")
    if isinstance(routes, list):
        for route in routes:
            if not isinstance(route, dict):
                continue
            candidate = route.get("task_signal")
            if non_empty_string(candidate) and normalize_task_signal(candidate) != "not_applicable":
                return candidate
    return "not_applicable"


def scheduler_record_changed_paths(receipt):
    paths = receipt.get("changed_files")
    if not isinstance(paths, list):
        return []
    return [
        path
        for path in paths
        if isinstance(path, str) and not scheduler_history_text_deprecated(path)
    ]


def scheduler_record_warnings(receipt):
    warnings = receipt.get("warning_checklist")
    if not isinstance(warnings, dict):
        return {}
    sanitized = {}
    for key, value in warnings.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, str) and scheduler_history_text_deprecated(value):
            sanitized[key] = "redacted deprecated history term"
        else:
            sanitized[key] = value
    return sanitized


def scheduler_record(argv):
    try:
        receipt, _ = json_arg_or_stdin(argv, "scheduler-record")
    except Exception as e:
        json_print({"result": "scheduler_record_rejected", "errors": [str(e)]})
        return
    if not isinstance(receipt, dict):
        json_print({"result": "scheduler_record_rejected", "errors": ["receipt must be a JSON object"]})
        return
    tool_uses = receipt.get("tool_uses") if isinstance(receipt.get("tool_uses"), list) else []
    entry = {
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repo_key": REPO_KEY,
        "task_signal": scheduler_record_task_signal(receipt),
        "changed_layers": receipt.get("affected_layers", []),
        "changed_paths": scheduler_record_changed_paths(receipt),
        "route_chosen": receipt.get("consumer_asset_routing", []),
        "tools_used": [
            {
                "tool": item.get("tool"),
                "risk": item.get("risk"),
                "result": item.get("result"),
            }
            for item in tool_uses
            if isinstance(item, dict)
        ],
        "tests_run": receipt.get("verification_command", ""),
        "warnings": scheduler_record_warnings(receipt),
        "duplicate_findings": receipt_duplicate_findings(receipt),
        "result": receipt.get("result", ""),
        "learning_decision": (
            receipt.get("learning_review", {}).get("lesson_decision")
            if isinstance(receipt.get("learning_review"), dict)
            else ""
        ),
    }
    SCHEDULER_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(SCHEDULER_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    json_print({
        "result": "scheduler_recorded",
        "path": SCHEDULER_HISTORY.relative_to(REPO_ROOT).as_posix(),
    })
# --------------------------------------------------------------- team v5

def team_definition_path(team):
    return PILOTHOS_DIR / "agent-teams" / f"{stable_slug(team)}.md"


def validate_team_contract(contract):
    errors = []
    if not isinstance(contract, dict):
        return ["team contract must be a JSON object"]
    required = {
        "task_id", "team", "roles", "allowed_paths", "role_permissions",
        "handoff_artifacts", "stop_condition", "max_repair_loops",
        "expected_evidence",
    }
    missing = sorted(required - set(contract))
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))
    for field in ("task_id", "team", "stop_condition"):
        if not non_empty_string(contract.get(field)):
            errors.append(f"{field} must be a non-empty string")
    for field in ("roles", "allowed_paths", "handoff_artifacts", "expected_evidence"):
        value = contract.get(field)
        if not isinstance(value, list) or not value or any(not non_empty_string(x) for x in value):
            errors.append(f"{field} must be a non-empty list of strings")
    if isinstance(contract.get("allowed_paths"), list):
        for pattern in contract.get("allowed_paths", []):
            if not path_pattern_is_safe(pattern):
                errors.append(f"allowed_paths contains unsafe pattern: {pattern}")
    try:
        loops = int(contract.get("max_repair_loops"))
        if loops < 0:
            errors.append("max_repair_loops must be >= 0")
    except (TypeError, ValueError):
        errors.append("max_repair_loops must be an integer")
    team_path = team_definition_path(contract.get("team", ""))
    if non_empty_string(contract.get("team")) and not team_path.exists():
        errors.append(f"team definition missing: {team_path.relative_to(REPO_ROOT).as_posix()}")
    permissions = contract.get("role_permissions")
    roles = set(contract.get("roles") or [])
    if not isinstance(permissions, dict) or not permissions:
        errors.append("role_permissions must be a non-empty object")
    else:
        for role in roles:
            actions = permissions.get(role)
            if not isinstance(actions, list) or not actions or any(action not in TEAM_PERMISSION_ACTIONS for action in actions):
                errors.append(
                    f"role_permissions.{role} must list actions from: "
                    + ", ".join(sorted(TEAM_PERMISSION_ACTIONS))
                )
    return errors


def team_contract_state_path(task_id):
    return TEAM_RUNS_DIR / safe_task_id(task_id) / "team-contract.json"


def team_receipt_state_path(task_id):
    return TEAM_RUNS_DIR / safe_task_id(task_id) / "team-receipt.json"


def load_team_contract(hook_input=None):
    env_path = env_state_path("PILOTHOS_TEAM_CONTRACT")
    if env_path:
        data = load_json_file(env_path)
        if data is not None:
            return data, env_path
    if hook_input and non_empty_string(hook_input.get("task_id")):
        path = team_contract_state_path(hook_input["task_id"])
        data = load_json_file(path)
        if data is not None:
            return data, path
    path = repo_state_file("team-contract.json")
    data = load_json_state(path)
    if data is not None:
        return data, path
    return None, None


def team_contract_write(argv):
    try:
        contract, _ = json_arg_or_stdin(argv, "team-contract-write")
    except Exception as e:
        json_print({"result": "team_contract_rejected", "errors": [str(e)]})
        return
    errors = validate_team_contract(contract)
    if errors:
        json_print({"result": "team_contract_rejected", "errors": errors})
        return
    contract = dict(contract)
    contract["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = team_contract_state_path(contract["task_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, contract)
    MARKER_DIR.mkdir(exist_ok=True)
    write_json(repo_state_file("team-contract.json"), contract)
    json_print({"result": "team_contract_recorded", "path": path.relative_to(REPO_ROOT).as_posix()})


def validate_team_receipt(receipt, contract):
    errors = []
    if not isinstance(receipt, dict):
        return ["team receipt must be a JSON object"]
    for field in ("task_id", "team", "final_lead_decision"):
        if not non_empty_string(receipt.get(field)):
            errors.append(f"{field} must be a non-empty string")
    if contract and receipt.get("task_id") != contract.get("task_id"):
        errors.append("team receipt task_id does not match active team contract")
    role_outputs = receipt.get("role_outputs")
    if not isinstance(role_outputs, list) or not role_outputs:
        errors.append("role_outputs must be a non-empty list")
    else:
        allowed_roles = set(contract.get("roles", [])) if isinstance(contract, dict) else set()
        permissions = contract.get("role_permissions", {}) if isinstance(contract, dict) else {}
        allowed_paths = contract.get("allowed_paths", []) if isinstance(contract, dict) else []
        for i, item in enumerate(role_outputs):
            if not isinstance(item, dict):
                errors.append(f"role_outputs[{i}] must be an object")
                continue
            for key in ("role", "output", "evidence"):
                if not non_empty_string(item.get(key)):
                    errors.append(f"role_outputs[{i}].{key} must be a non-empty string")
            if allowed_roles and item.get("role") not in allowed_roles:
                errors.append(f"role_outputs[{i}].role is not in team contract roles")
            edited_paths = item.get("edited_paths")
            if edited_paths is not None:
                if not isinstance(edited_paths, list) or any(not non_empty_string(x) for x in edited_paths):
                    errors.append(f"role_outputs[{i}].edited_paths must be a list of strings")
                else:
                    actions = permissions.get(item.get("role"), [])
                    if "edit" not in actions:
                        errors.append(f"role_outputs[{i}].edited_paths not allowed for role without edit permission")
                    for edited in edited_paths:
                        if not path_matches(allowed_paths, edited):
                            errors.append(f"role_outputs[{i}].edited_paths outside allowed_paths: {edited}")
    handoff_paths = receipt.get("handoff_paths")
    if not isinstance(handoff_paths, list):
        errors.append("handoff_paths must be a list")
    elif contract and isinstance(contract.get("handoff_artifacts"), list):
        allowed = contract.get("handoff_artifacts")
        for path in handoff_paths:
            if not non_empty_string(path):
                errors.append("handoff_paths must contain only strings")
            elif not path_matches(allowed, path):
                errors.append(f"handoff path outside handoff_artifacts: {path}")
    try:
        loops = int(receipt.get("repair_loop_count"))
    except (TypeError, ValueError):
        errors.append("repair_loop_count must be an integer")
        loops = 0
    if contract:
        try:
            max_loops = int(contract.get("max_repair_loops", 0))
            if loops > max_loops:
                errors.append("repair_loop_count exceeds max_repair_loops")
        except (TypeError, ValueError):
            pass
        roles = {str(role).lower() for role in contract.get("roles", [])}
        if "qa" in roles:
            verdict = receipt.get("qa_verdict")
            if not isinstance(verdict, dict):
                errors.append("qa_verdict is required when QA role exists")
            else:
                if verdict.get("result") not in {"PASS", "FAIL"}:
                    errors.append("qa_verdict.result must be PASS or FAIL")
                if not non_empty_string(verdict.get("evidence")):
                    errors.append("qa_verdict.evidence must be a non-empty string")
    return errors


def team_run_dir(task_id):
    return TEAM_RUNS_DIR / safe_task_id(task_id)


def team_artifact_rel(path):
    return path.relative_to(REPO_ROOT).as_posix()


def write_team_artifact(path, title, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"# {title}\n\n{body.strip()}\n"
    path.write_text(text, encoding="utf-8")
    return team_artifact_rel(path)


def materialize_team_artifacts(receipt, contract):
    task_id = receipt["task_id"]
    base = team_run_dir(task_id)
    artifacts = []
    for item in receipt.get("role_outputs", []):
        if not isinstance(item, dict):
            continue
        role = item.get("role", "role")
        body = (
            f"Role: {role}\n\n"
            f"Output:\n{item.get('output', '')}\n\n"
            f"Evidence:\n{item.get('evidence', '')}\n"
        )
        if item.get("edited_paths"):
            body += "\nEdited paths:\n" + "\n".join(f"- {p}" for p in item.get("edited_paths", [])) + "\n"
        artifacts.append(write_team_artifact(base / f"role-{stable_slug(role)}.md", f"Role Output: {role}", body))
    verdict = receipt.get("qa_verdict")
    if isinstance(verdict, dict):
        artifacts.append(write_team_artifact(
            base / "qa-verdict.md",
            "QA Verdict",
            f"Result: {verdict.get('result')}\n\nEvidence:\n{verdict.get('evidence', '')}",
        ))
    artifacts.append(write_team_artifact(
        base / "final-lead-decision.md",
        "Final Lead Decision",
        receipt.get("final_lead_decision", ""),
    ))
    handoff_paths = receipt.get("handoff_paths", [])
    artifacts.append(write_team_artifact(
        base / "handoff-summary.md",
        "Handoff Summary",
        "\n".join(f"- {path}" for path in handoff_paths) if handoff_paths else "No handoff paths recorded.",
    ))
    if isinstance(contract, dict):
        artifacts.append(write_team_artifact(
            base / "team-contract-summary.md",
            "Team Contract Summary",
            f"Team: {contract.get('team')}\n\nStop condition: {contract.get('stop_condition')}",
        ))
    return artifacts


def team_receipt_write(argv):
    try:
        receipt, _ = json_arg_or_stdin(argv, "team-receipt-write")
    except Exception as e:
        json_print({"result": "team_receipt_rejected", "errors": [str(e)]})
        return
    contract, _ = load_team_contract({"task_id": receipt.get("task_id")} if isinstance(receipt, dict) else {})
    errors = validate_team_receipt(receipt, contract)
    if errors:
        json_print({"result": "team_receipt_rejected", "errors": errors})
        return
    receipt = dict(receipt)
    receipt["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt["generated_artifacts"] = materialize_team_artifacts(receipt, contract)
    path = team_receipt_state_path(receipt["task_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, receipt)
    json_print({"result": "team_receipt_recorded", "path": path.relative_to(REPO_ROOT).as_posix()})


def role_from_hook_input(hook_input):
    for key in ("pilothos_role", "role", "team_role"):
        if non_empty_string(hook_input.get(key)):
            return hook_input.get(key)
    tool_input = (
        hook_input.get("tool_input")
        or hook_input.get("toolInput")
        or hook_input.get("input")
    )
    if isinstance(tool_input, dict):
        for key in ("pilothos_role", "role", "team_role"):
            if non_empty_string(tool_input.get(key)):
                return tool_input.get(key)
    return None


def preflight():
    """Preflight cua /pilothos-init: kiem tra moi truong, fail som va ro rang."""
    import os
    ok = True

    def check(cond, msg_ok, msg_fail):
        nonlocal ok
        if cond:
            print(f"OK   {msg_ok}")
        else:
            ok = False
            print(f"FAIL {msg_fail}")

    check(os.access(REPO_ROOT, os.W_OK),
          f"repo root ghi duoc: {REPO_ROOT}",
          f"repo root KHONG ghi duoc: {REPO_ROOT}")
    claude_dir = REPO_ROOT / ".claude"
    check(claude_dir.exists() and os.access(claude_dir, os.W_OK)
          or (not claude_dir.exists() and os.access(REPO_ROOT, os.W_OK)),
          ".claude/ ghi duoc hoac tao duoc",
          ".claude/ KHONG ghi duoc")
    if SETTINGS.exists():
        try:
            json.load(open(SETTINGS, encoding="utf-8"))
            print(f"OK   settings.json hien co hop le")
        except json.JSONDecodeError as e:
            ok = False
            print(f"FAIL settings.json hien co KHONG hop le: {e} — sua truoc khi init")
    else:
        print("OK   chua co settings.json (se duoc tao/merge o Apply)")
    missing = [f.name for f in CORE_FILES if not f.exists()]
    check(not missing,
          "cay pilothOS/ day du core files",
          f"cay pilothOS/ THIEU: {', '.join(missing)} — ban phan phoi loi hoac dirty install")
    print("PREFLIGHT " + ("PASSED" if ok else "FAILED"))


def detect():
    """Stage 0 cua /pilothos-init: verdict + evidence. KHONG tu re nhanh —
    agent phai trinh bay ket qua va CHO CONSUMER CONFIRM."""
    evidence = []
    if INIT_MARKER.exists():
        print("VERDICT: re-init")
        print(f"EVIDENCE: {INIT_MARKER} ton tai — "
              f"noi dung: {INIT_MARKER.read_text(encoding='utf-8').strip()}")
        print("NOTE: co the upgrade bang staging --upgrade va installer mode=upgrade; "
              "khong chay lai greenfield/brownfield plan tren project da init.")
        return
    missing = [f.name for f in CORE_FILES if not f.exists()]
    if missing:
        print("VERDICT: dirty")
        print(f"EVIDENCE: pilothOS/ ton tai nhung thieu core files: {', '.join(missing)}")
        print("NOTE: co the la lan init/copy truoc bi do dang. De xuat: xoa pilothOS/ "
              "va copy lai ban phan phoi, hoac phuc hoi tu .backup/manifest neu co.")
        return
    root_claude = REPO_ROOT / "CLAUDE.md"
    if root_claude.exists():
        content = root_claude.read_text(encoding="utf-8", errors="replace")
        if "@pilothOS/bootstrap.md" in content:
            evidence.append("CLAUDE.md o root da import bootstrap cua PilothOS (ban phan phoi full-copy)")
        else:
            evidence.append("CLAUDE.md o root la cua consumer (KHONG import bootstrap PilothOS)")
    for name in ("AGENTS.md",):
        f = REPO_ROOT / name
        if f.exists() and "PilothOS" not in f.read_text(encoding="utf-8", errors="replace"):
            evidence.append(f"{name} cua consumer ton tai")
    for hint in CONSUMER_ASSET_HINTS:
        if (REPO_ROOT / hint).exists():
            evidence.append(f"tai san consumer: {hint}")
    for adir in ADAPTER_DIRS:
        d = REPO_ROOT / adir
        if d.exists():
            extra = _non_pilothos_content(d)
            if extra:
                evidence.append(
                    f"tai san consumer trong {adir}/: {', '.join(extra[:5])}"
                    + (" ..." if len(extra) > 5 else ""))
    consumer_signals = [e for e in evidence if "consumer" in e or "tai san" in e]
    if consumer_signals:
        print("VERDICT: brownfield")
    else:
        print("VERDICT: greenfield")
    for e in evidence or ["repo chi chua ban phan phoi PilothOS, khong co tai san khac"]:
        print(f"EVIDENCE: {e}")
    print("NOTE: verdict chi la de xuat — agent PHAI trinh bay va cho consumer confirm truoc khi sang Stage 1.")


# ---------------------------------------------------------------- log append

def _sanitize(field):
    """Chống vỡ bảng markdown: thay | bằng ; và ép một dòng."""
    return field.replace("|", ";").replace("\n", " ").strip()


def log_append(argv):
    """Append MỘT dòng log đúng format — máy móc, hết lỗi typo/nuốt cột.

    Cách dùng:
      log-append review "<Scope>" "<Findings>" "<Action>" "<Evidence>" "<Reviewer>"
      log-append lesson "<Context>" "<Lesson>" "<PromotedTo>"

    - Date tự điền = hôm nay.
    - Nếu Evidence trông như đường dẫn trong repo mà KHÔNG tồn tại → FAIL,
      không append (chặn lớp lỗi Evidence-path sai từ lần adopt đầu tiên).
    """
    if not argv:
        print("FAIL log-append: thieu loai log (review|lesson)")
        return
    kind, fields = argv[0], [_sanitize(f) for f in argv[1:]]
    today = datetime.date.today().isoformat()
    if kind == "review":
        if len(fields) != 5:
            print("FAIL log-append review: can dung 5 truong "
                  "(Scope, Findings, Action, Evidence, Reviewer)")
            return
        evidence = fields[3]
        if "/" in evidence and " " not in evidence:
            if not (REPO_ROOT / evidence).exists():
                print(f"FAIL log-append: Evidence path khong ton tai: {evidence}")
                return
        row = f"| {today} | {fields[0]} | {fields[1]} | {fields[2]} | {fields[3]} | {fields[4]} |"
        target = REVIEW_LOG
    elif kind == "lesson":
        if len(fields) != 3:
            print("FAIL log-append lesson: can dung 3 truong "
                  "(Context, Lesson, PromotedTo)")
            return
        if not learning_promotion_target_valid(fields[2]):
            print(
                "FAIL log-append lesson: PromotedTo phai la target hop le "
                "hoac not_applicable"
            )
            return
        row = f"| {today} | {fields[0]} | {fields[1]} | {fields[2]} |"
        target = LESSONS
    else:
        print(f"FAIL log-append: loai khong ho tro: {kind}")
        return
    if not target.exists():
        print(f"FAIL log-append: khong tim thay {target}")
        return
    with open(target, "a", encoding="utf-8") as f:
        f.write(row + "\n")
    print(f"OK   da append vao {target.name}: {row}")


# ---------------------------------------------------- edit/receipt guard modes

def task_contract_write(argv):
    try:
        contract, source = json_arg_or_stdin(argv, "contract-write")
    except Exception as e:
        print(f"FAIL contract-write: {e}")
        return
    errors = validate_task_contract(contract)
    if errors:
        print(json.dumps({"result": "contract_rejected", "errors": errors},
                         ensure_ascii=False, indent=2))
        return
    MARKER_DIR.mkdir(exist_ok=True)
    contract = dict(contract)
    contract["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if source:
        contract["source"] = str(source.relative_to(REPO_ROOT) if REPO_ROOT in source.resolve().parents else source)
    repo_state_file("task-contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK   task contract recorded: {repo_state_file('task-contract.json')}")


def pre_edit(hook_input):
    # Claude Code plan mode is read-only planning (harness restricts edits to the
    # plan file). Piloth's contract-before-edit gate is for execution, not
    # planning, so do not block during plan mode — governance re-engages the
    # moment the session leaves plan mode. `permission_mode` is the documented
    # PreToolUse hook field carrying the current mode ("plan" | "default" | ...).
    if hook_input.get("permission_mode") == "plan":
        return
    # Harness ghi plan file vào ~/.claude/plans (ngoài repo). Đó là artifact của
    # Claude Code, không phải code repo — cho phép kể cả khi harness không truyền
    # permission_mode=="plan" (safety-net bổ trợ). Chỉ allow khi MỌI target là
    # plan-path để không tạo khe hở ghi lẫn file repo.
    raw_targets = raw_edit_targets(hook_input)
    if raw_targets and all(is_harness_plan_path(t) for t in raw_targets):
        return
    contract, contract_path = load_task_contract(hook_input)
    if not contract:
        block_decision(
            "PILOTHOS PRE-EDIT: missing task contract. Before editing, record a "
            "contract with task_scope, affected_layers, allowed_paths, "
            "expected_evidence, out_of_scope_paths, and for non-doc/test work "
            "consumer_scope/context_evidence/reuse_evidence/decision_limits using "
            "`python3 pilothOS/scripts/pilothos_guard.py contract-write <contract.json>`."
        )
        return
    errors = validate_task_contract(contract)
    if errors:
        block_decision("PILOTHOS PRE-EDIT: invalid task contract: " + "; ".join(errors))
        return
    paths, path_errors = edit_paths_from_hook_input(hook_input)
    if path_errors:
        block_decision("PILOTHOS PRE-EDIT: " + "; ".join(path_errors))
        return
    if not paths:
        block_decision("PILOTHOS PRE-EDIT: edit hook did not include a target path.")
        return
    team_contract, team_contract_path = load_team_contract(hook_input)
    role = role_from_hook_input(hook_input)
    if role:
        if not team_contract:
            block_decision(
                "PILOTHOS PRE-EDIT: team role was supplied but no active team contract was found."
            )
            return
        team_errors = validate_team_contract(team_contract)
        if team_errors:
            block_decision("PILOTHOS PRE-EDIT: invalid team contract: " + "; ".join(team_errors))
            return
        permissions = team_contract.get("role_permissions", {})
        actions = permissions.get(role)
        if not isinstance(actions, list):
            block_decision(f"PILOTHOS PRE-EDIT: role is not in team contract: {role}")
            return
        if "edit" not in actions:
            block_decision(f"PILOTHOS PRE-EDIT: role {role} does not have edit permission.")
            return
        for rel in paths:
            if not path_matches(team_contract.get("allowed_paths", []), rel):
                block_decision(
                    f"PILOTHOS PRE-EDIT: team role {role} cannot edit outside team allowed_paths "
                    f"from {team_contract_path}: {rel}"
                )
                return
    allowed = contract.get("allowed_paths", [])
    out_of_scope = contract.get("out_of_scope_paths", [])
    for rel in paths:
        if path_matches(out_of_scope, rel):
            block_decision(f"PILOTHOS PRE-EDIT: {rel} is declared out of scope.")
            return
        if not path_matches(allowed, rel):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} is outside allowed_paths from "
                f"{contract_path}. allowed_paths={allowed}"
            )
            return
        if contract_docs_tests_only(contract) and rel.startswith("pilothOS/"):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} touches pilothOS core while the "
                "contract only declares Docs/Tests layers."
            )
            return
        if is_sensitive_runtime_path(rel) and not contract_has_layer(contract, RUNTIME_TOOL_LAYERS):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} is a sensitive runtime/tool file. "
                "Declare affected_layers with Tools/Runtime or Installer before editing it."
            )
            return
        if rel.startswith("adapters/") and not contract_has_layer(contract, ADAPTER_LAYERS):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} is an adapter path but affected_layers "
                "does not declare Adapters/Tools."
            )
            return
        if rel.startswith("adapters/") and contract_has_layer(contract, {"rules", "hooks"}):
            has_rule_source = any(
                path_matches(contract.get("allowed_paths", []), candidate)
                for candidate in (
                    "pilothOS/rules/index.md",
                    "pilothOS/rules/hooks.md",
                    "pilothOS/rules/coding-behavior.md",
                    "pilothOS/rules/evidence.md",
                    "pilothOS/rules/layer-boundary.md",
                )
            )
            if not has_rule_source:
                block_decision(
                    "PILOTHOS PRE-EDIT: adapter policy changes must be paired with "
                    "the pilothOS/rules source of truth in allowed_paths, otherwise "
                    "the adapter is likely replacing policy instead of bridging it."
                )
                return
        if (preset_requires_standard_evidence(contract)
                and is_ui_path(rel)
                and not contract_has_ui_design_system_evidence(contract)):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} looks like a UI file. "
                "Add ui_design_system_evidence with source, checked, decision, "
                "and reason before editing UI paths."
            )
            return


def git_numstat(rel):
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff", "--numstat", "--", rel],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        if out.stdout.strip():
            first = out.stdout.strip().splitlines()[0].split()
            add = 0 if first[0] == "-" else int(first[0])
            delete = 0 if first[1] == "-" else int(first[1])
            return add, delete
        untracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--others",
             "--exclude-standard", "--", rel],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        if untracked.stdout.strip():
            p = REPO_ROOT / rel
            if p.exists() and p.is_file():
                return len(p.read_text(encoding="utf-8", errors="replace").splitlines()), 0
    except Exception:
        pass
    return 0, 0


def post_edit(hook_input):
    paths, path_errors = edit_paths_from_hook_input(hook_input)
    facts = load_diff_facts(hook_input)
    warnings = facts.setdefault("warnings", [])
    for err in path_errors:
        warnings.append(err)
    contract, _ = load_task_contract(hook_input)
    if not paths:
        warnings.append("post-edit hook did not include a target path")
        update_diff_fact_derived(facts, contract)
        save_diff_facts(hook_input, facts)
        print(json.dumps({"result": "diff_facts_recorded", "warnings": warnings[-1:]},
                         ensure_ascii=False))
        return
    changed = facts.setdefault("changed_files", {})
    for rel in paths:
        add, delete = git_numstat(rel)
        layer = layer_for_path(rel)
        changed[rel] = {"layer": layer, "added": add, "deleted": delete,
                        "changed_lines": add + delete,
                        "new_file": git_path_is_new(rel)}
    # Prune entry không còn trong working tree (đã commit hoặc revert) để diff facts
    # phản ánh delta CHƯA commit hiện tại, không tích luỹ snapshot cũ qua nhiều edit.
    # Chỉ prune khi thực sự trong git repo — ngoài git, git_changed_file_paths()
    # trả rỗng một cách mập mờ và sẽ xoá nhầm toàn bộ facts.
    if is_git_repo():
        live = set(git_changed_file_paths())
        for rel in list(changed):
            if rel not in live:
                del changed[rel]
    update_diff_fact_derived(facts, contract)
    save_diff_facts(hook_input, facts)
    print(json.dumps({
        "result": "diff_facts_recorded",
        "changed_files": changed,
        "affected_layers": facts["affected_layers"],
        "has_tests": facts["has_tests"],
        "has_docs": facts["has_docs"],
        "new_files": facts.get("new_files", []),
        "new_files_count": facts.get("new_files_count", 0),
        "total_added": facts.get("total_added", 0),
        "total_deleted": facts.get("total_deleted", 0),
        "largest_file_delta": facts.get("largest_file_delta", {}),
        "dependency_files_changed": facts.get("dependency_files_changed", []),
        "ui_files_changed": facts.get("ui_files_changed", []),
        "test_files_changed": facts.get("test_files_changed", []),
        "docs_files_changed": facts.get("docs_files_changed", []),
        "component_like_files_changed": facts.get("component_like_files_changed", []),
        "warnings": facts.get("warnings", []),
        "evidence_commands": facts.get("evidence_commands", []),
    }, ensure_ascii=False))


def evidence_add(argv):
    if not argv:
        print("FAIL evidence-add: need command string")
        return
    facts = load_diff_facts({})
    entry = {
        "command": argv[0],
        "result": argv[1] if len(argv) > 1 else "recorded",
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    facts.setdefault("evidence_commands", []).append(entry)
    contract, _ = load_task_contract({})
    update_diff_fact_derived(facts, contract)
    save_diff_facts({}, facts)
    print(f"OK   evidence recorded: {entry['command']} -> {entry['result']}")


def facts_paths(facts, receipt=None):
    paths = set((facts or {}).get("changed_files", {}))
    if isinstance(receipt, dict):
        changed = receipt.get("changed_files")
        if isinstance(changed, list):
            paths |= {p for p in changed if isinstance(p, str)}
    return paths


def validate_receipt_scope_against_contract(receipt, contract, facts):
    errors = []
    if not isinstance(contract, dict):
        return errors
    allowed = contract.get("allowed_paths")
    out_of_scope = contract.get("out_of_scope_paths") or []
    if not isinstance(allowed, list) or not allowed:
        return errors
    for raw_path in sorted(facts_paths(facts, receipt)):
        rel, reason = repo_relative_path(raw_path)
        if rel is None:
            errors.append(f"receipt changed path invalid: {raw_path} ({reason})")
            continue
        if isinstance(out_of_scope, list) and path_matches(out_of_scope, rel):
            errors.append(f"receipt changed path is out_of_scope: {rel}")
        elif not path_matches(allowed, rel):
            errors.append(f"receipt changed path is outside allowed_paths: {rel}")
    return errors


def receipt_requires_reuse_discipline(facts, receipt, contract=None):
    if not preset_requires_standard_evidence(contract, receipt):
        return False
    paths = facts_paths(facts, receipt)
    if not paths:
        return False
    for rel in paths:
        layer = layer_for_path(rel)
        if normalize_layer(layer) not in DOC_TEST_LAYERS:
            return True
    return False


def validate_receipt_delivery_story(receipt):
    errors = []
    if not non_empty_string(receipt.get("scope_evidence")):
        errors.append("scope_evidence is required for code/UI/runtime/rules/adapter changes")
    errors.extend(validate_object_list(
        receipt.get("context_used"),
        "context_used",
        RECEIPT_CONTEXT_FIELDS,
    ))
    errors.extend(validate_asset_routing(receipt.get("consumer_asset_routing")))
    errors.extend(validate_learning_review(receipt.get("learning_review")))
    gates = receipt.get("quality_gates")
    if not isinstance(gates, dict):
        errors.append("quality_gates must be an object")
    else:
        reuse_gate = gates.get("reuse_non_duplication")
        if not isinstance(reuse_gate, dict):
            errors.append("quality_gates.reuse_non_duplication must be an object")
        else:
            result = reuse_gate.get("result")
            if result not in QUALITY_GATE_RESULTS:
                errors.append("quality_gates.reuse_non_duplication.result must be PASS, FAIL, or NOT_APPLICABLE")
            if not non_empty_string(reuse_gate.get("evidence")):
                errors.append("quality_gates.reuse_non_duplication.evidence must be a non-empty string")
            delivery_result = str(receipt.get("result", "")).strip().lower()
            if result == "FAIL" and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
                errors.append(
                    "quality_gates.reuse_non_duplication.result cannot be FAIL when receipt result is successful"
                )
            if result == "FAIL" and not non_empty_string(receipt.get("limitation")):
                errors.append("limitation is required when quality_gates.reuse_non_duplication.result is FAIL")
    return errors


def validate_learning_review(value):
    errors = validate_string_object(value, "learning_review", LEARNING_REVIEW_FIELDS)
    if errors:
        return errors
    mistake = str(value.get("mistake_checked", "")).strip()
    decision = str(value.get("lesson_decision", "")).strip()
    promoted_to = str(value.get("promoted_to", "")).strip()
    if mistake not in LEARNING_MISTAKE_CLASSES:
        errors.append(
            "learning_review.mistake_checked must be one of: "
            + ", ".join(sorted(LEARNING_MISTAKE_CLASSES))
        )
    if decision not in LEARNING_DECISIONS:
        errors.append(
            "learning_review.lesson_decision must be one of: "
            + ", ".join(sorted(LEARNING_DECISIONS))
        )
    if mistake == "none" and decision in LEARNING_DECISIONS and decision != "none":
        errors.append(
            "learning_review.lesson_decision must be none when mistake_checked is none"
        )
    if mistake != "none" and mistake in LEARNING_MISTAKE_CLASSES and decision == "none":
        errors.append(
            "learning_review.lesson_decision must not be none when mistake_checked is not none"
        )
    if not learning_promotion_target_valid(promoted_to):
        errors.append(
            "learning_review.promoted_to must be one of: "
            + ", ".join(sorted(LEARNING_PROMOTION_TARGETS))
            + " (or '<target>, upstream' for cross-project lessons)"
        )
    if decision == "promoted" and promoted_to == "not_applicable":
        errors.append(
            "learning_review.promoted_to must name a promotion target when lesson_decision is promoted"
        )
    if decision == "none" and promoted_to != "not_applicable":
        errors.append(
            "learning_review.promoted_to must be not_applicable when lesson_decision is none"
        )
    return errors


def learning_promotion_target_valid(value):
    if not non_empty_string(value):
        return False
    target = value.strip()
    if target in LEARNING_PROMOTION_TARGETS:
        return True
    parts = [
        part.strip()
        for part in re.split(r"[,+]", target)
        if part.strip()
    ]
    if len(parts) < 2 or "upstream" not in parts:
        return False
    base_targets = set(LEARNING_PROMOTION_TARGETS) - {"not_applicable"}
    return all(part in base_targets or part in LEARNING_PROMOTION_MARKERS for part in parts)


def receipt_touches_ui(facts, receipt):
    paths = facts_paths(facts, receipt)
    return any(is_ui_path(p) for p in paths)


def current_ds_candidates_for_receipt(facts, receipt, contract=None):
    paths = sorted(facts_paths(facts, receipt))
    if not paths:
        return []
    allowed = ["**/*"]
    if isinstance(contract, dict) and isinstance(contract.get("allowed_paths"), list):
        allowed = contract.get("allowed_paths")
    # A UI receipt should inspect the repo's DS assets, not only the changed
    # file. Use broad but deterministic local patterns.
    scan = ds_scan_payload({
        "task_signal": "UI/component",
        "changed_paths": paths,
        "allowed_paths": allowed + [
            "components/**", "src/components/**", "ui/**", "src/ui/**",
            "tokens/**", "src/tokens/**", "pilothOS/rules/**", "docs/**",
            "tailwind.config.*", "**/*.css",
        ],
    })
    return (
        scan.get("component_candidates", [])
        + scan.get("token_candidates", [])
        + scan.get("pattern_candidates", [])
    )


def validate_design_system_candidate_review(receipt, facts, contract=None):
    errors = validate_candidate_review(
        receipt,
        ("design_system_candidates", "ds_scan", "design_system_scan"),
        "design_system_candidate_review",
    )
    if errors:
        return errors
    if not receipt_touches_ui(facts, receipt):
        return errors
    if "design_system_candidate_review" in receipt:
        _, review_errors = review_items(
            receipt.get("design_system_candidate_review"),
            "design_system_candidate_review",
        )
        errors.extend(review_errors)
        return errors
    if current_ds_candidates_for_receipt(facts, receipt, contract):
        errors.append(
            "design_system_candidate_review is required when UI files changed and design-system candidates exist"
        )
    return errors


def validate_string_object(value, field, required_keys):
    errors = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    for key in required_keys:
        if not non_empty_string(value.get(key)):
            errors.append(f"{field}.{key} must be a non-empty string")
    return errors


def dependency_reason_present(receipt):
    if non_empty_string(receipt.get("dependency_change_reason")):
        return True
    checklist = receipt.get("warning_checklist")
    return isinstance(checklist, dict) and non_empty_string(checklist.get("dependency_change_reason"))


def checklist_value_present(receipt, key):
    if non_empty_string(receipt.get(key)):
        return True
    checklist = receipt.get("warning_checklist")
    return isinstance(checklist, dict) and non_empty_string(checklist.get(key))


def validate_warning_checklist(receipt, facts):
    errors = []
    warnings = [str(w) for w in facts.get("warnings", [])]
    for prefix, key in WARNING_CHECKLIST_RULES:
        if any(w.startswith(prefix) for w in warnings):
            if not checklist_value_present(receipt, key):
                errors.append(f"warning_checklist.{key} is required for warning: {prefix}")
    return errors


def command_is_read_only_guard(command):
    if not isinstance(command, str):
        return False
    if SHELL_CONTROL_RE.search(command):
        return False
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return False
    while parts and ENV_ASSIGNMENT_RE.fullmatch(parts[0]):
        name, _, _ = parts[0].partition("=")
        assignment_text = parts[0].lower()
        if name not in SAFE_READ_ONLY_GUARD_ENV_VARS:
            return False
        if any(re.search(pattern, assignment_text) for pattern in HIGH_RISK_COMMAND_PATTERNS):
            return False
        parts = parts[1:]
    if len(parts) < 3:
        return False
    executable = pathlib.PurePosixPath(parts[0].replace("\\", "/")).name
    if executable not in {"python", "python3"}:
        return False
    if not parts[1].endswith("pilothOS/scripts/pilothos_guard.py"):
        return False
    mode = parts[2]
    meta = GUARD_MODES.get(mode)
    if meta is None:
        return False
    trailing_args = parts[3:]
    trailing_text = " ".join(trailing_args).lower()
    if any(re.search(pattern, trailing_text) for pattern in HIGH_RISK_COMMAND_PATTERNS):
        return False
    return not mode_mutates(mode, trailing_args)


def command_looks_high_risk(command):
    if not isinstance(command, str):
        return False
    if command_is_read_only_guard(command):
        return False
    lowered = command.lower()
    return any(re.search(pattern, lowered) for pattern in HIGH_RISK_COMMAND_PATTERNS)


def receipt_has_approval_evidence(receipt):
    if non_empty_string(receipt.get("approval_evidence")):
        return True
    checklist = receipt.get("warning_checklist")
    if isinstance(checklist, dict) and non_empty_string(checklist.get("approval_evidence")):
        return True
    tool_uses = receipt.get("tool_uses")
    if isinstance(tool_uses, list):
        return any(
            isinstance(item, dict) and non_empty_string(item.get("approval_evidence"))
            for item in tool_uses
        )
    return False


def entitlement_list(value, field):
    if value is None:
        return [], []
    raw_items = value if isinstance(value, list) else [value]
    if not raw_items:
        return [], [f"{field} must not be empty when present"]
    entitlements, errors = [], []
    for i, item in enumerate(raw_items):
        if not non_empty_string(item):
            errors.append(f"{field}[{i}] must be a non-empty string")
            continue
        entitlement = str(item).strip()
        if not ENTITLEMENT_RE.fullmatch(entitlement):
            errors.append(f"{field}[{i}] has invalid entitlement name: {entitlement}")
        elif entitlement not in entitlements:
            entitlements.append(entitlement)
    return entitlements, errors


def payload_entitlements(payload):
    if not isinstance(payload, dict):
        return [], []
    if "entitlements" in payload:
        return entitlement_list(payload.get("entitlements"), "entitlements")
    if "entitlement" in payload:
        return entitlement_list(payload.get("entitlement"), "entitlement")
    return [], []


def contract_allowed_entitlements(contract):
    if not isinstance(contract, dict):
        return set(), []
    allowed, errors = entitlement_list(
        contract.get("allowed_entitlements", contract.get("entitlements")),
        "allowed_entitlements",
    )
    return set(allowed), errors


def validate_payload_entitlements(payload, contract, field):
    entitlements, errors = payload_entitlements(payload)
    allowed, allowed_errors = contract_allowed_entitlements(contract)
    errors.extend(allowed_errors)
    if entitlements and not allowed:
        errors.append(f"{field} entitlements require active contract allowed_entitlements")
    for entitlement in entitlements:
        if allowed and entitlement not in allowed:
            errors.append(f"{field} entitlement not allowed by active contract: {entitlement}")
    return errors


def result_needs_limitation(result):
    if not isinstance(result, str):
        return False
    lowered = result.lower()
    return any(token in lowered for token in ("not run", "not_run", "skipped", "blocked", "failed", "unable"))


def valid_timeout_value(value):
    if not non_empty_string(value):
        return False
    return bool(re.fullmatch(r"[1-9][0-9]*(ms|s|m|h)", value.strip()))


def validate_tool_uses(receipt, facts, contract=None):
    errors = []
    tool_uses = receipt.get("tool_uses")
    if tool_uses is not None:
        if not isinstance(tool_uses, list):
            errors.append("tool_uses must be a list of objects")
        elif not tool_uses:
            errors.append("tool_uses must not be empty when present")
        else:
            for i, item in enumerate(tool_uses):
                if not isinstance(item, dict):
                    errors.append(f"tool_uses[{i}] must be an object")
                    continue
                for key in TOOL_USE_REQUIRED_FIELDS:
                    if not non_empty_string(item.get(key)):
                        errors.append(f"tool_uses[{i}].{key} must be a non-empty string")
                if non_empty_string(item.get("timeout")) and not valid_timeout_value(item.get("timeout")):
                    errors.append(f"tool_uses[{i}].timeout must be a duration like 30s, 5m, 1h, or 500ms")
                risk = str(item.get("risk", "")).strip().lower()
                if risk and risk not in {"low", "medium", "high"}:
                    errors.append(f"tool_uses[{i}].risk must be low, medium, or high")
                command = item.get("command")
                high_risk = risk == "high" or command_looks_high_risk(command)
                if command_looks_high_risk(command) and risk != "high":
                    errors.append(f"tool_uses[{i}].risk must be high for high-risk command")
                if high_risk and not (non_empty_string(item.get("approval_evidence")) or receipt_has_approval_evidence(receipt)):
                    errors.append(f"tool_uses[{i}].approval_evidence is required for high-risk tool use")
                errors.extend(validate_payload_entitlements(item, contract, f"tool_uses[{i}]"))
                if result_needs_limitation(item.get("result")) and not (
                        non_empty_string(item.get("limitation")) or non_empty_string(receipt.get("limitation"))):
                    errors.append(f"tool_uses[{i}].limitation is required when tool result was not cleanly successful")
                match_payload = {
                    "tool": item.get("tool"),
                    "command": item.get("command"),
                    "expected_evidence": item.get("evidence_output"),
                }
                if not tool_check_matches_contract(match_payload, contract, receipt):
                    errors.append(
                        f"tool_uses[{i}] must be referenced by active task contract"
                    )

    high_risk_evidence = [
        entry.get("command")
        for entry in facts.get("evidence_commands", [])
        if isinstance(entry, dict) and command_looks_high_risk(entry.get("command"))
    ]
    if command_looks_high_risk(receipt.get("verification_command")):
        high_risk_evidence.append(receipt.get("verification_command"))
    if high_risk_evidence and not receipt_has_approval_evidence(receipt):
        errors.append(
            "approval_evidence is required for high-risk tool/command evidence: "
            + "; ".join(str(x) for x in high_risk_evidence if x)
        )
    return errors


def contract_tool_text(contract):
    if not isinstance(contract, dict):
        return ""
    parts = []

    def collect(value):
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)

    for key in (
        "task_scope",
        "consumer_scope",
        "expected_evidence",
        "context_evidence",
        "reuse_evidence",
        "consumer_asset_routing",
        "ui_design_system_evidence",
    ):
        collect(contract.get(key))
    return "\n".join(parts).lower()


def tool_check_matches_contract(payload, contract, *configs):
    if not isinstance(contract, dict):
        return not preset_requires_standard_evidence(contract, *configs)
    if not preset_requires_standard_evidence(contract, *configs):
        return True
    haystack = contract_tool_text(contract)
    if not haystack:
        return False
    identifiers = [
        payload.get("tool"),
        payload.get("command"),
        payload.get("expected_evidence"),
    ]
    for raw in identifiers:
        if not non_empty_string(raw):
            continue
        needle = raw.strip().lower()
        if needle in haystack or haystack in needle:
            return True
    return False


def validate_tool_check_payload(payload, contract=None):
    errors = []
    if not isinstance(payload, dict):
        return ["tool check payload must be a JSON object"]
    for key in TOOL_CHECK_REQUIRED_FIELDS:
        if not non_empty_string(payload.get(key)):
            errors.append(f"{key} must be a non-empty string")
    if non_empty_string(payload.get("timeout")) and not valid_timeout_value(payload.get("timeout")):
        errors.append("timeout must be a duration like 30s, 5m, 1h, or 500ms")
    risk = str(payload.get("risk", "")).strip().lower()
    if risk and risk not in {"low", "medium", "high"}:
        errors.append("risk must be low, medium, or high")
    command = payload.get("command")
    high_risk = risk == "high" or command_looks_high_risk(command)
    if command_looks_high_risk(command) and risk != "high":
        errors.append("risk must be high for high-risk command")
    if high_risk and not non_empty_string(payload.get("approval_evidence")):
        errors.append("approval_evidence is required before high-risk tool use")
    errors.extend(validate_payload_entitlements(payload, contract, "tool-check"))
    if not errors and not tool_check_matches_contract(payload, contract):
        errors.append(
            "tool-check command/evidence must be referenced by active task contract"
        )
    return errors


def tool_check(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "tool-check")
    except Exception as e:
        print(f"FAIL tool-check: {e}")
        return
    contract, _ = load_task_contract({})
    errors = validate_tool_check_payload(payload, contract)
    if errors:
        block_decision("PILOTHOS TOOL CHECK: " + "; ".join(errors))
        return
    print("OK   tool check passed")


def receipt_needs_judgment(contract, facts, receipt):
    if contract and contract.get("requires_judgment"):
        return True
    layers = {normalize_layer(x) for x in (receipt.get("affected_layers") or [])}
    layers |= {normalize_layer(x) for x in facts.get("affected_layers", [])}
    if layers & JUDGMENT_LAYERS:
        return True
    for rel in facts.get("changed_files", {}):
        if rel.startswith(("pilothOS/rules/", "pilothOS/runtime/", "adapters/")):
            return True
    return False


def validate_deliver_receipt(receipt, contract, facts):
    errors = []
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]
    preset = operational_preset(contract, receipt)
    if not valid_operational_preset(preset):
        errors.append("operational_preset must be light, standard, or strict")
    update_diff_fact_derived(facts, contract)
    missing = sorted(RECEIPT_REQUIRED_FIELDS - set(receipt))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    for field in ("changed_files", "affected_layers"):
        value = receipt.get(field)
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
            errors.append(f"{field} must be a non-empty list of strings")
    command = receipt.get("verification_command")
    result = receipt.get("result")
    if not isinstance(command, str) or not command.strip():
        errors.append("verification_command must be a non-empty string")
    if not isinstance(result, str) or not result.strip():
        errors.append("result must be a non-empty string")
    lowered = f"{command} {result}".lower() if isinstance(command, str) and isinstance(result, str) else ""
    if any(token in lowered for token in ("not run", "not_run", "skipped", "blocked", "failed", "unable")):
        if not isinstance(receipt.get("limitation"), str) or not receipt.get("limitation", "").strip():
            errors.append("limitation is required when verification was not cleanly successful")
        if preset == "strict":
            errors.append("strict preset requires clean verification; not run/skipped/blocked/failed/unable is not accepted")
    fact_files = set(facts.get("changed_files", {}))
    receipt_files = set(receipt.get("changed_files") or [])
    missing_files = sorted(fact_files - receipt_files)
    if missing_files:
        errors.append(f"receipt missing changed_files from diff facts: {', '.join(missing_files)}")
    fact_layers = {normalize_layer(v.get("layer")) for v in facts.get("changed_files", {}).values()}
    receipt_layers = {normalize_layer(v) for v in (receipt.get("affected_layers") or [])}
    missing_layers = sorted(x for x in fact_layers - receipt_layers if x)
    if missing_layers:
        errors.append(f"receipt missing affected_layers from diff facts: {', '.join(missing_layers)}")
    errors.extend(validate_receipt_scope_against_contract(receipt, contract, facts))
    if preset_requires_standard_evidence(contract, receipt) and receipt_needs_judgment(contract, facts, receipt):
        checklist = receipt.get("judgment_checklist")
        if not isinstance(checklist, dict):
            errors.append("judgment_checklist is required for judgment-sensitive changes")
        else:
            for key, question in JUDGMENT_CHECKLIST_KEYS.items():
                value = checklist.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"judgment_checklist.{key} missing answer: {question}")
    if receipt_requires_reuse_discipline(facts, receipt, contract):
        errors.extend(validate_receipt_delivery_story(receipt))
        errors.extend(validate_string_object(
            receipt.get("reuse_discipline"),
            "reuse_discipline",
            REUSE_DISCIPLINE_FIELDS,
        ))
    errors.extend(validate_candidate_review(
        receipt,
        ("semantic_reuse_candidates", "reuse_scan", "semantic_reuse_scan"),
        "semantic_reuse_review",
    ))
    if preset_requires_standard_evidence(contract, receipt) and receipt_touches_ui(facts, receipt):
        if not contract_has_ui_design_system_evidence(contract):
            errors.append(
                "ui_design_system_evidence is required in the task contract when UI files changed"
            )
        for field in UI_RECEIPT_FIELDS:
            if not non_empty_string(receipt.get(field)):
                errors.append(f"{field} is required when UI files changed")
        errors.extend(validate_design_system_candidate_review(receipt, facts, contract))
    dependency_files = set(facts.get("dependency_files_changed") or [])
    dependency_files |= {p for p in (receipt.get("changed_files") or []) if is_dependency_path(p)}
    if preset_requires_standard_evidence(contract, receipt) and dependency_files and not dependency_reason_present(receipt):
        errors.append(
            "warning_checklist.dependency_change_reason is required when dependency files changed"
        )
    if preset_requires_standard_evidence(contract, receipt):
        errors.extend(validate_warning_checklist(receipt, facts))
    errors.extend(validate_tool_uses(receipt, facts, contract))
    return errors


def receipt_write(argv):
    try:
        receipt, _ = json_arg_or_stdin(argv, "receipt-write")
    except Exception as e:
        print(f"FAIL receipt-write: {e}")
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    errors = validate_deliver_receipt(receipt, contract, facts)
    if errors:
        print(json.dumps({"result": "receipt_rejected", "errors": errors},
                         ensure_ascii=False, indent=2))
        return
    MARKER_DIR.mkdir(exist_ok=True)
    receipt = dict(receipt)
    receipt["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    repo_state_file("deliver-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK   deliver receipt recorded: {repo_state_file('deliver-receipt.json')}")


def latest_receipt_seal_hash():
    record = latest_receipt_seal_record()
    return record.get("seal_sha256", "") if record else ""


def latest_receipt_seal_record():
    if not RECEIPT_SEALS.exists():
        return None
    latest = None
    try:
        with open(RECEIPT_SEALS, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("repo_key") == REPO_KEY and non_empty_string(item.get("seal_sha256")):
                    latest = item
    except (OSError, json.JSONDecodeError):
        return None
    return latest


def file_hash_entry(raw_path):
    rel, err = repo_relative_path(raw_path)
    if err:
        return {"path": str(raw_path), "status": "invalid", "reason": err}
    path = REPO_ROOT / rel
    if not path.exists():
        return {"path": rel, "status": "missing"}
    if not path.is_file():
        return {"path": rel, "status": "not_file"}
    try:
        data = path.read_bytes()
    except OSError as e:
        return {"path": rel, "status": "failed", "reason": str(e)}
    return {
        "path": rel,
        "status": "sealed",
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def load_receipt_for_seal(argv, label):
    if argv:
        return json_arg_or_stdin(argv, label)
    receipt, path = load_deliver_receipt({})
    if receipt is None:
        raise ValueError(f"{label}: missing active deliver receipt")
    return receipt, path


def build_receipt_seal(receipt, contract, facts, previous_seal_sha256=""):
    changed = sorted(
        p for p in (receipt.get("changed_files") or [])
        if isinstance(p, str) and p.strip()
    )
    payload = {
        "schema_version": 1,
        "repo_key": REPO_KEY,
        "receipt_sha256": sha256_json(receipt),
        "contract_sha256": sha256_json(contract or {}),
        "diff_facts_sha256": sha256_json({
            "affected_layers": facts.get("affected_layers", []),
            "changed_files": facts.get("changed_files", {}),
            "evidence_commands": facts.get("evidence_commands", []),
            "warnings": facts.get("warnings", []),
        }),
        "changed_files": [file_hash_entry(path) for path in changed],
        "previous_seal_sha256": previous_seal_sha256 or "",
        "limits": [
            "sha256 seal only; not cryptographic code signing",
            "verify against the same repo checkout and active receipt state",
        ],
    }
    payload["seal_sha256"] = sha256_json(payload)
    return payload


def receipt_seal(argv):
    args = list(argv)
    record = False
    if "--record" in args:
        args.remove("--record")
        record = True
    try:
        receipt, _ = load_receipt_for_seal(args, "receipt-seal")
    except Exception as e:
        json_print({"result": "receipt_seal_rejected", "errors": [str(e)]})
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    previous = latest_receipt_seal_hash() if record else ""
    seal = build_receipt_seal(receipt, contract, facts, previous)
    seal["result"] = "receipt_sealed"
    if record:
        RECEIPT_SEALS.parent.mkdir(parents=True, exist_ok=True)
        with open(RECEIPT_SEALS, "a", encoding="utf-8") as f:
            f.write(json.dumps(seal, ensure_ascii=False, sort_keys=True) + "\n")
        seal["recorded_to"] = RECEIPT_SEALS.relative_to(REPO_ROOT).as_posix()
    json_print(seal)


def receipt_verify(argv):
    try:
        expected, _ = json_arg_or_stdin(argv, "receipt-verify")
    except Exception as e:
        json_print({"result": "receipt_verify_rejected", "errors": [str(e)]})
        return
    if not isinstance(expected, dict):
        json_print({"result": "receipt_verify_rejected", "errors": ["seal must be a JSON object"]})
        return
    receipt, _ = load_deliver_receipt({})
    if receipt is None:
        json_print({"result": "receipt_verify_failed", "errors": ["missing active deliver receipt"]})
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    current = build_receipt_seal(receipt, contract, facts, expected.get("previous_seal_sha256", ""))
    comparisons = {
        "receipt_sha256": current.get("receipt_sha256") == expected.get("receipt_sha256"),
        "contract_sha256": current.get("contract_sha256") == expected.get("contract_sha256"),
        "diff_facts_sha256": current.get("diff_facts_sha256") == expected.get("diff_facts_sha256"),
        "changed_files": current.get("changed_files") == expected.get("changed_files"),
        "seal_sha256": current.get("seal_sha256") == expected.get("seal_sha256"),
    }
    errors = [name for name, ok in comparisons.items() if not ok]
    json_print({
        "result": "receipt_verify_passed" if not errors else "receipt_verify_failed",
        "comparisons": comparisons,
        "errors": errors,
        "current_seal_sha256": current.get("seal_sha256"),
        "expected_seal_sha256": expected.get("seal_sha256"),
    })


def receipt_template_router_fields(contract):
    router = contract.get("evidence_router") if isinstance(contract, dict) else None
    if not isinstance(router, dict) or not non_empty_string(router.get("decision_id")):
        return {}
    execution = router.get("execution_plan")
    if not isinstance(execution, dict):
        execution = {}
    fields = {
        "decision_id": router.get("decision_id"),
        "execution_mode": execution.get("mode", ""),
        "evidence_router": {
            "decision_id": router.get("decision_id"),
            "rollout": (router.get("rollout") or {}).get("mode", ""),
            "execution_mode": execution.get("mode", ""),
            "verification_methods": [
                item.get("method")
                for item in router.get("verification_plan", [])
                if isinstance(item, dict) and non_empty_string(item.get("method"))
            ],
            "limitations": router.get("limitations", []),
        },
    }
    rollout = router.get("rollout")
    rollout_mode = rollout.get("mode") if isinstance(rollout, dict) else "advisory"
    required_types = {
        item.get("type")
        for item in router.get("evidence_plan", [])
        if isinstance(item, dict) and item.get("required") is True
    }
    if rollout_mode == "enforced" and float(router.get("confidence", 0)) < 0.80:
        fields["router_low_confidence_resolution"] = "<source/verification/user resolution>"
    if rollout_mode == "enforced" and "review" in required_types:
        fields["independent_review"] = {
            "result": "PASS",
            "evidence": "<independent reviewer evidence>",
        }
    if rollout_mode == "enforced" and "coverage_search" in required_types:
        fields["coverage_evidence"] = "<complete negative-claim scope evidence>"
    return fields


def receipt_template():
    """Emit a gate-aware receipt skeleton.

    Instead of a static superset of every field os-close *might* demand, this
    reads the active contract + diff facts and emits ONLY the fields the current
    run actually needs, with valid default enum values (not `<placeholder>`) so
    the skeleton passes `os-close --dry-run` structurally — the human only fills
    real evidence. Allowed enum values are shown in a trailing `_allowed` hint.
    """
    facts = load_diff_facts({})
    contract, _ = load_task_contract({})
    update_diff_fact_derived(facts, contract)
    probe = {}  # proxy receipt so gate predicates can read paths from facts
    mode = contract.get("mode") if isinstance(contract, dict) else None
    required_gates = required_gates_for_task(contract, mode=mode)
    std_evidence = preset_requires_standard_evidence(contract)
    needs_reuse = receipt_requires_reuse_discipline(facts, probe, contract)
    touches_ui = receipt_touches_ui(facts, probe)
    needs_judgment = std_evidence and receipt_needs_judgment(contract, facts, probe)

    template = {
        "operational_preset": operational_preset(contract),
        "changed_files": sorted(facts.get("changed_files", {})),
        "affected_layers": facts.get("affected_layers", []),
        "verification_command": "<command or 'not run'>",
        "result": "passed",
        "limitation": "<required only if result is not run/failed/skipped>",
        "quality_gates": {
            gate: {"result": "PASS", "evidence": f"<evidence proving {gate}>"}
            for gate in required_gates
        },
        "claims": [
            {"claim": "<what you did, no absolute 1:1/complete/fully claims unless evidence backs it>",
             "evidence_refs": ["<os-evidence id>", "quality_gates.correctness"]}
        ],
    }
    template.update(receipt_template_router_fields(contract))

    if needs_judgment:
        template["judgment_checklist"] = dict(JUDGMENT_CHECKLIST_KEYS)

    # Enum hints live in one top-level block (validators ignore unknown keys);
    # delete `_allowed_values` before the real close if you want a clean seal.
    allowed = {}

    if needs_reuse:
        template["scope_evidence"] = "<why these changes were in scope>"
        template["context_used"] = [
            {"source": "<path-or-command>", "reason": "<why loaded>", "finding": "<what it proved>"}
        ]
        template["consumer_asset_routing"] = [
            {
                "task_signal": "not_applicable",
                "asset_type": "not_applicable",
                "decision": "not_applicable",
                "reason": "<why the exact asset was loaded, or why not applicable>",
            }
        ]
        template["reuse_discipline"] = {
            "existing_code_checked": "<paths/searches checked>",
            "existing_component_checked": "<component/design-system check or not_applicable>",
            "existing_pattern_followed": "<pattern reused>",
            "new_code_reason": "<why new code was needed>",
            "duplicate_risk": "<duplicate risk assessment>",
            "kiss_dry_rationale": "<why this stayed simple/non-duplicative>",
        }
        template["learning_review"] = {
            "mistake_checked": "none",
            "lesson_decision": "none",
            "promoted_to": "not_applicable",
            "reason": "<why no lesson was needed, or where it was recorded/promoted>",
        }
        allowed["consumer_asset_routing[].task_signal"] = sorted(ASSET_ROUTING_SIGNALS)
        allowed["consumer_asset_routing[].asset_type"] = sorted(ASSET_ROUTING_TYPES)
        allowed["consumer_asset_routing[].decision"] = sorted(ASSET_ROUTING_DECISIONS)
        allowed["learning_review.mistake_checked"] = sorted(LEARNING_MISTAKE_CLASSES)
        allowed["learning_review.lesson_decision"] = sorted(LEARNING_DECISIONS)
        allowed["learning_review.promoted_to"] = sorted(LEARNING_PROMOTION_TARGETS) + ["<target>, upstream"]

    if touches_ui and std_evidence:
        template["design_system_checked"] = "<existing DS/tokens checked; result>"
        template["component_reuse_decision"] = "not_applicable"
        template["token_reuse_decision"] = "not_applicable"
        template["design_system_candidate_review"] = [
            {"candidate": "all", "decision": "not_applicable", "reason": "<decision reason>"}
        ]
        allowed["component_reuse_decision / token_reuse_decision / design_system_candidate_review[].decision"] = sorted(UI_DESIGN_SYSTEM_DECISIONS)

    if allowed:
        template["_allowed_values"] = allowed

    print(json.dumps(template, ensure_ascii=False, indent=2))
# ---------------------------------------------------- OS contract construction

def clean_string_list(value):
    if isinstance(value, str) and value.strip():
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in cleaned:
            cleaned.append(item.strip())
    return cleaned


def safe_evidence_id(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", raw).strip("-._:")[:120]


def request_task_id(request):
    for key in ("task_id", "id", "request_id"):
        if non_empty_string(request.get(key)):
            return safe_task_id(request[key])
    basis = {
        "intent": request.get("intent") or request.get("task_scope") or request.get("request"),
        "task_signal": request.get("task_signal"),
        "affected_paths": request.get("affected_paths") or request.get("allowed_paths") or request.get("changed_paths"),
    }
    return "task-" + sha256_json(basis)[:12]


def request_intent(request):
    for key in ("intent", "task_scope", "request", "summary", "title"):
        if non_empty_string(request.get(key)):
            return request[key].strip()
    return "repo-local OS task"


def request_paths(request):
    return (
        clean_string_list(request.get("target_paths"))
        or clean_string_list(request.get("allowed_paths"))
        or clean_string_list(request.get("affected_paths"))
        or clean_string_list(request.get("changed_paths"))
        or clean_string_list(request.get("paths"))
    )


def layers_for_requested_paths(paths):
    concrete = [
        path for path in paths
        if path and path not in {"*", "**", "**/*"} and not any(ch in path for ch in "*?[")
    ]
    if not concrete:
        return ["Consumer"]
    return sorted({layer_for_path(path) for path in concrete})


def merged_context_evidence(*groups):
    merged = []
    seen = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            key = (
                item.get("source", ""),
                item.get("reason", ""),
                item.get("finding", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append({
                "source": str(item.get("source", "")).strip() or "os-start",
                "reason": str(item.get("reason", "")).strip() or "lifecycle context",
                "finding": str(item.get("finding", "")).strip() or "loaded by OS start",
            })
    return merged


def request_evidence_profile(request):
    profile = str(request.get("evidence_profile") or "generic").strip()
    return profile if profile in EVIDENCE_PROFILES else "generic"


def request_os_mode(request):
    raw = str(
        request.get("mode")
        or request.get("os_mode")
        or request.get("piloth_mode")
        or "adaptive"
    ).strip().lower()
    return raw if raw in OS_MODE_REQUESTS else "adaptive"


def mode_to_operational_preset(mode):
    if mode == "lean":
        return "light"
    if mode == "strict":
        return "strict"
    return "standard"


def path_pattern_is_broad(pattern):
    raw = str(pattern or "").strip()
    return raw in {"*", "**", "**/*", "."} or raw.endswith("/**")


def paths_look_docs_tests_only(paths, layers):
    normalized_layers = {normalize_layer(x) for x in layers}
    if normalized_layers and normalized_layers <= DOC_TEST_LAYERS:
        return True
    concrete = [path for path in paths if not path_pattern_is_broad(path)]
    return bool(concrete) and all(is_docs_path(path) or is_test_path(path) for path in concrete)


def choose_adaptive_mode(request, paths, layers, target):
    requested = request_os_mode(request)
    reasons = []
    if requested in OS_MODES:
        return requested, [{
            "mode": requested,
            "source": "request",
            "reason": f"explicit mode={requested}",
        }]

    task_signal = str(request.get("task_signal") or "").strip().lower()
    intent_blob = json.dumps(sanitize_state_value(request, limit=1000), ensure_ascii=False).lower()
    evidence_profile = request_evidence_profile(request)
    broad_paths = not paths or any(path_pattern_is_broad(path) for path in paths) or len(paths) > 6
    target_external = isinstance(target, dict) and bool(target.get("external"))
    docs_tests_only = paths_look_docs_tests_only(paths, layers)

    if evidence_profile == "design_tokens":
        reasons.append("design_tokens evidence profile requires strict coverage discipline")
        return "strict", [{"mode": "strict", "source": "adaptive", "reason": "; ".join(reasons)}]
    if "release/deploy" in task_signal or any(term in intent_blob for term in ("deploy", "production", "release")):
        reasons.append("release/deploy or production signal")
        return "strict", [{"mode": "strict", "source": "adaptive", "reason": "; ".join(reasons)}]
    if any(term in intent_blob for term in ("full design tokens", "all tokens", "entire library", "pixel-perfect", "1:1")):
        reasons.append("absolute/full-coverage claim risk")
        return "strict", [{"mode": "strict", "source": "adaptive", "reason": "; ".join(reasons)}]
    if broad_paths:
        reasons.append("broad target paths")
        return "standard", [{"mode": "standard", "source": "adaptive", "reason": "; ".join(reasons)}]
    if docs_tests_only:
        reasons.append("docs/tests-only narrow scope")
        return "lean", [{"mode": "lean", "source": "adaptive", "reason": "; ".join(reasons)}]
    if "ui/component" in task_signal and len(paths) <= 4:
        reasons.append("small UI/component scope")
        return "lean", [{"mode": "lean", "source": "adaptive", "reason": "; ".join(reasons)}]
    concrete_paths = [path for path in paths if not path_pattern_is_broad(path)]
    if concrete_paths and len(concrete_paths) <= SMALL_SCOPE_MAX_PATHS:
        reasons.append(f"small blast radius ({len(concrete_paths)} concrete paths)")
        return "lean", [{"mode": "lean", "source": "adaptive", "reason": "; ".join(reasons)}]
    if target_external:
        reasons.append("explicit external target with non-trivial scope")
        return "standard", [{"mode": "standard", "source": "adaptive", "reason": "; ".join(reasons)}]
    reasons.append("default non-trivial task scope")
    return "standard", [{"mode": "standard", "source": "adaptive", "reason": "; ".join(reasons)}]


def suggest_phase_plan(request, paths, layers, evidence_profile):
    """Advisory-only phase recommendation (recipe right-sizing).

    Mirrors aidlc's deterministic heuristicClassify: recommend the front-half
    phases that would prevent rework, without ever enabling them. This NEVER
    mutates requires_prototype / requires_discovery — a human opts in on a
    follow-up os-start. Surfaced in os-status / os-report so the operator sees
    the suggestion but keeps control (auto-enabling a heavy phase would add
    cost, the opposite of the intent).
    """
    signal = str(request.get("task_signal") or "").strip().lower()
    intent = json.dumps(sanitize_state_value(request, limit=1000), ensure_ascii=False).lower()
    paths = paths or []
    ui = (
        evidence_profile == "ui"
        or "ui/component" in signal
        or any(path_pattern_suggests_ui(p) for p in paths)
    )
    trivial = (
        paths_look_docs_tests_only(paths, layers)
        or "bugfix" in signal
        or "bug fix" in intent
    )
    high_impact = any(
        k in intent for k in
        ("architecture", "acceptance criteria", "out of scope", "unclear", "ambiguous", "not sure", "unknown")
    )
    broad = (not paths) or any(path_pattern_is_broad(p) for p in paths) or len(paths) > 6
    rec_proto = bool(ui and not trivial)
    rec_disc = bool((high_impact or broad) and not trivial)
    reasons = []
    if rec_proto:
        reasons.append("UI/component scope — a prototype round can de-risk the visual direction before implementation")
    if rec_disc:
        reasons.append("ambiguous or broad scope — a discovery gate can confirm open questions up front")
    if not reasons:
        reasons.append("scope looks narrow/clear — no extra front-half phase recommended")
    return {
        "recommend_discovery": rec_disc,
        "recommend_prototype": rec_proto,
        "reasons": reasons,
        "note": "suggestions only — pass requires_discovery / requires_prototype in a follow-up os-start to enable",
    }


def request_success_metrics(request):
    metrics = request.get("success_metrics") if isinstance(request, dict) else None
    if isinstance(metrics, list):
        return [
            str(item).strip()
            for item in metrics
            if isinstance(item, str) and item.strip()
        ]
    return [
        "not worse than none-piloth on mandatory fidelity/correctness/browser metrics",
        "win at least one consumer-visible metric before claiming consumer value",
    ]


def request_budget(request):
    budget = request.get("budget") if isinstance(request, dict) else None
    if isinstance(budget, dict):
        return sanitize_state_value(budget, limit=1000)
    return {
        "llm_tokens": "telemetry_required_for_exact_cost_claims",
        "context": "load only task-routed files",
        "verification": "smallest check that proves the claim",
    }


def design_token_expected_evidence(expected):
    required = [
        "figma_node",
        "design_token_coverage",
        "covered_groups",
        "generated_surfaces",
        "verification",
    ]
    merged = list(expected)
    for item in required:
        if item not in merged:
            merged.append(item)
    return merged


def request_has_figma_signal(request):
    if not isinstance(request, dict):
        return False
    text = json.dumps(sanitize_state_value(request, limit=1000), ensure_ascii=False).lower()
    return "figma" in text or "figma.com" in text


def ui_expected_evidence(expected, request):
    required = ["ui_quality"]
    if request_has_figma_signal(request):
        required.append("figma_node")
    merged = list(expected)
    for item in required:
        if item not in merged:
            merged.append(item)
    return merged


def default_reuse_evidence(task_signal):
    return [{
        "asset": "reuse-scan",
        "decision": "not_applicable",
        "reason": f"os-start lifecycle for {task_signal}; update with reuse-scan evidence before new code when applicable",
    }]


def build_os_contract(request, route, scheduler, target=None):
    paths = request_paths(request) or ["**/*"]
    task_signal = route.get("task_signal") or request.get("task_signal") or "not_applicable"
    skeleton = scheduler.get("contract_skeleton") if isinstance(scheduler, dict) else {}
    if not isinstance(skeleton, dict):
        skeleton = {}
    layers = (
        clean_string_list(request.get("affected_layers"))
        or clean_string_list(skeleton.get("affected_layers"))
        or layers_for_requested_paths(paths)
    )
    mode, mode_decisions = choose_adaptive_mode(request, paths, layers, target)
    expected = (
        clean_string_list(request.get("expected_evidence"))
        or clean_string_list(scheduler.get("expected_evidence") if isinstance(scheduler, dict) else None)
        or clean_string_list(skeleton.get("expected_evidence"))
        or ["manual verification receipt"]
    )
    evidence_profile = request_evidence_profile(request)
    if evidence_profile == "design_tokens":
        expected = design_token_expected_evidence(expected)
    elif evidence_profile == "ui" or any(path_pattern_suggests_ui(path) for path in paths):
        expected = ui_expected_evidence(expected, request)
    route_context = route.get("context_evidence") if isinstance(route, dict) else []
    scheduler_context = skeleton.get("context_evidence")
    footprint_policy = request_target_footprint_policy(request, target or {})
    contract = {
        "task_scope": request_intent(request),
        "affected_layers": layers,
        "allowed_paths": paths,
        "expected_evidence": expected,
        "out_of_scope_paths": clean_string_list(request.get("out_of_scope_paths")),
        "consumer_scope": request.get("consumer_scope") or skeleton.get("consumer_scope") or "repo-local task scope from os-start",
        "target_paths": paths,
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "evidence_profile": evidence_profile,
        "mode": mode,
        "mode_decisions": mode_decisions,
        "adaptive_mode": request_os_mode(request) in {"adaptive", "auto"},
        "operational_preset": mode_to_operational_preset(mode),
        "execution_strategy": request.get("execution_strategy")
        or ("controlled_target" if isinstance(target, dict) and target.get("explicit") else "repo_local"),
        "target_footprint_policy": footprint_policy,
        "budget": request_budget(request),
        "success_metrics": request_success_metrics(request),
        "context_evidence": clean_string_list([]),
        "reuse_evidence": request.get("reuse_evidence") or skeleton.get("reuse_evidence") or default_reuse_evidence(task_signal),
        "decision_limits": clean_string_list(request.get("decision_limits"))
        or clean_string_list(skeleton.get("decision_limits"))
        or ["Do not expand scope without updating the OS task contract."],
        "consumer_asset_routing": request.get("consumer_asset_routing")
        or route.get("consumer_asset_routing")
        or skeleton.get("consumer_asset_routing")
        or [{
            "task_signal": task_signal,
            "asset_type": "not_applicable",
            "decision": "not_applicable",
            "reason": "no task-routed consumer assets selected",
        }],
    }
    contract["context_evidence"] = (
        request.get("context_evidence")
        if isinstance(request.get("context_evidence"), list)
        else merged_context_evidence(route_context, scheduler_context, [{
            "source": "pilothOS/runtime/os-control-plane.md",
            "reason": "OS lifecycle contract",
            "finding": "task is routed through os-start/os-close",
        }])
    )
    for optional in (
        "operational_preset", "allowed_entitlements", "requires_judgment",
        "benchmark_id", "requires_human_review", "requires_prototype",
        "requires_discovery", "discovery_decisions", "model_hints",
        "ui_design_system_evidence", "energy_budget_reason",
    ):
        if optional in request:
            contract[optional] = request[optional]
    # A prototype's human pick is recorded through the reused human_review
    # round-trip, so requiring a prototype implies requiring human review.
    if contract.get("requires_prototype"):
        contract["requires_human_review"] = True
    # Advisory recipe: recommend front-half phases without ever enabling them.
    contract["phase_plan_suggestion"] = suggest_phase_plan(request, paths, layers, evidence_profile)
    if isinstance(target, dict):
        contract["target_repo"] = target.get("target_repo", "")
        contract["target_kind"] = target.get("target_kind", "")
        contract["target_id"] = target.get("target_id", "")
    if isinstance(request.get("coverage_claims"), dict):
        contract["coverage_claims"] = sanitize_state_value(request.get("coverage_claims"), limit=1000)
    if contract_requires_ui_design_system_evidence(contract) and "ui_design_system_evidence" not in contract:
        contract["ui_design_system_evidence"] = [{
            "source": "asset-scan",
            "checked": "deterministic design-system routing check",
            "decision": "not_applicable",
            "reason": "os-start found no explicit design-system evidence in the request; update the contract before UI edits if a design system applies",
        }]
    return contract


# ------------------------------------------------------------ OS quality gates
def contract_requires_ui_quality_evidence(contract, receipt=None):
    if isinstance(contract, dict) and contract.get("evidence_profile") == "ui":
        return True
    paths = []
    if isinstance(contract, dict):
        paths.extend(clean_string_list(contract.get("allowed_paths")))
        paths.extend(clean_string_list(contract.get("target_paths")))
    if isinstance(receipt, dict):
        paths.extend(clean_string_list(receipt.get("changed_files")))
    return any(path_pattern_suggests_ui(path) for path in paths)


def required_gates_for_task(contract, receipt=None, mode=None):
    paths = sorted(facts_paths({}, receipt))
    if isinstance(contract, dict):
        paths.extend(clean_string_list(contract.get("allowed_paths")))
    layers = set()
    if isinstance(contract, dict):
        layers |= {normalize_layer(x) for x in contract.get("affected_layers", [])}
    if isinstance(receipt, dict):
        layers |= {normalize_layer(x) for x in receipt.get("affected_layers", [])}
    effective_mode = mode or (contract.get("mode") if isinstance(contract, dict) else None) or "standard"
    gates = ["scope", "correctness", "disclosure"]
    if effective_mode != "lean":
        gates.insert(2, "traceability")
    if effective_mode != "lean" and (not layers or not layers <= DOC_TEST_LAYERS):
        gates.extend(["architecture", "reuse_non_duplication", "regression"])
    if any(path_pattern_suggests_ui(path) or is_ui_path(path) for path in paths):
        gates.append("design_system")
    if contract_requires_ui_quality_evidence(contract, receipt):
        gates.append("ui_quality")
    if (
        isinstance(contract, dict) and contract.get("evidence_profile") == "design_tokens"
    ) or (
        isinstance(receipt, dict) and receipt.get("evidence_profile") == "design_tokens"
    ):
        gates.append("design_token_coverage")
    signal_text = json.dumps({
        "contract": contract or {},
        "receipt": receipt or {},
    }, ensure_ascii=False).lower()
    if "release/deploy" in signal_text or "deploy" in signal_text:
        gates.append("operational_approval")
    if isinstance(contract, dict) and contract.get("requires_human_review"):
        gates.append("human_review")
    if isinstance(contract, dict) and contract.get("requires_prototype"):
        gates.append("prototype")
    return list(dict.fromkeys(gates))


def validate_required_quality_gates(receipt, required_gates):
    errors = []
    gates = receipt.get("quality_gates")
    if not isinstance(gates, dict):
        return ["quality_gates must be an object for os-close"]
    for gate in required_gates:
        item = gates.get(gate)
        if not isinstance(item, dict):
            errors.append(f"quality_gates.{gate} is required for os-close")
            continue
        result = item.get("result")
        if result not in QUALITY_GATE_RESULTS:
            errors.append(f"quality_gates.{gate}.result must be PASS, FAIL, or NOT_APPLICABLE")
        if not non_empty_string(item.get("evidence")):
            errors.append(f"quality_gates.{gate}.evidence must be a non-empty string")
        delivery_result = str(receipt.get("result", "")).strip().lower()
        if result == "FAIL" and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
            if not non_empty_string(receipt.get("limitation")):
                errors.append(f"limitation is required when quality_gates.{gate}.result is FAIL")
    return errors


def validate_review_feedback(value):
    """Validate the structured human-review feedback artifact (schema + enums).

    Faithful to annotron's structured feedback, translated into Piloth's gate
    vocabulary: findings carry a location (file and/or gate), a note, a severity
    and a disposition; the round carries a verdict and a finalized flag.
    """
    if not isinstance(value, dict):
        return ["review feedback must be a JSON object"]
    errors = []
    if value.get("verdict") not in REVIEW_VERDICTS:
        errors.append("verdict must be one of: " + ", ".join(sorted(REVIEW_VERDICTS)))
    if not isinstance(value.get("finalized"), bool):
        errors.append("finalized must be a boolean")
    findings = value.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        return errors
    errors.extend(validate_object_list_enums(
        findings,
        "findings",
        ("id", "note", "severity", "disposition"),
        {"severity": REVIEW_SEVERITIES, "disposition": REVIEW_DISPOSITIONS},
    ))
    for i, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        loc = finding.get("location")
        if not isinstance(loc, dict) or not (
            non_empty_string(loc.get("file")) or non_empty_string(loc.get("gate"))
        ):
            errors.append(f"findings[{i}].location must include a file or a gate")
            continue
        if non_empty_string(loc.get("file")):
            _, err = repo_relative_path(loc.get("file"))
            if err:
                errors.append(f"findings[{i}].location.file {err}")
    return errors


def validate_human_review_gate(state, contract, receipt, os_evidence):
    """Machine cross-check for the human_review gate (anti-checkbox core).

    The guard never judges whether a finding is correct — only that a real,
    finalized, approving human artifact exists with no unresolved blocking
    findings. Returns (errors, summary) where summary.result is
    PASS / FAIL / NOT_APPLICABLE. Unresolved blocking findings surface in
    summary.unresolved so os-close can route the task back to Repair.
    """
    required = isinstance(contract, dict) and bool(contract.get("requires_human_review"))
    if not required:
        return [], {"result": "NOT_APPLICABLE"}
    task_id = state.get("task_id") if isinstance(state, dict) else None
    feedback = latest_review_feedback(task_id)
    if not feedback:
        return (
            ["human_review gate requires a review-feedback artifact; run review-request then review-feedback"],
            {"result": "FAIL", "reason": "no review feedback recorded"},
        )
    ferrors = validate_review_feedback(feedback)
    if ferrors:
        return (
            [f"review feedback invalid: {e}" for e in ferrors],
            {"result": "FAIL", "reason": "invalid review feedback"},
        )
    review_round = feedback.get("review_round")
    if feedback.get("finalized") is not True:
        return (
            ["human_review is not finalized (review round still open)"],
            {"result": "FAIL", "reason": "not finalized", "review_round": review_round},
        )
    unresolved = [
        finding.get("id")
        for finding in feedback.get("findings", [])
        if isinstance(finding, dict)
        and finding.get("severity") in REVIEW_BLOCKING_SEVERITIES
        and finding.get("disposition") == "request-changes"
    ]
    if unresolved:
        return (
            ["human_review has unresolved blocking findings routed to Repair: "
             + ", ".join(str(x) for x in unresolved)],
            {"result": "FAIL", "reason": "unresolved blocking findings",
             "unresolved": unresolved, "review_round": review_round},
        )
    if feedback.get("verdict") != "approve":
        return (
            ["human_review verdict is not approve"],
            {"result": "FAIL", "reason": "verdict not approve",
             "verdict": feedback.get("verdict"), "review_round": review_round},
        )
    summary = {
        "result": "PASS",
        "review_round": review_round,
        "verdict": "approve",
        "reviewer": feedback.get("reviewer", ""),
    }
    try:
        summary["feedback_path"] = review_feedback_path(task_id).relative_to(REPO_ROOT).as_posix()
    except (ValueError, TypeError):
        pass
    return [], summary


def latest_evidence_of_kind(os_evidence, kind):
    """Return the most recently recorded os-evidence record of a given kind."""
    matches = [
        item for item in (os_evidence or [])
        if isinstance(item, dict) and item.get("kind") == kind
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda item: str(item.get("recorded_at") or ""))[-1]


def validate_prototype_gate(state, contract, receipt, os_evidence):
    """Machine check for the thin prototype gate (evidence completeness only).

    Prototype reuses the human_review round-trip for the human sign-off; this
    gate only asserts prototype's own invariant — a valid design method, >=2
    options generated, and one chosen among them — read from the recorded
    prototype evidence. Anti-checkbox: a receipt that self-declares prototype
    PASS with no backing evidence record still FAILs. Returns a summary dict
    with result PASS / FAIL / NOT_APPLICABLE.
    """
    required = isinstance(contract, dict) and bool(contract.get("requires_prototype"))
    if not required:
        return {"result": "NOT_APPLICABLE"}
    ev = latest_evidence_of_kind(os_evidence, "prototype")
    if ev is None:
        return {"result": "FAIL", "reason": "no prototype evidence recorded"}
    everrors = validate_prototype_evidence(ev)
    if everrors:
        return {"result": "FAIL", "reason": "; ".join(everrors)}
    return {
        "result": "PASS",
        "method": ev.get("method"),
        "options": len([o for o in ev.get("options", []) if isinstance(o, dict)]),
        "chosen": ev.get("chosen"),
    }


def evidence_text_blob(receipt, facts, os_evidence):
    parts = []
    for item in os_evidence:
        parts.append(json.dumps(item, ensure_ascii=False))
    for item in facts.get("evidence_commands", []):
        parts.append(json.dumps(item, ensure_ascii=False))
    if isinstance(receipt, dict):
        parts.append(str(receipt.get("verification_command", "")))
        for item in receipt.get("tool_uses", []) if isinstance(receipt.get("tool_uses"), list) else []:
            if isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=False))
        gates = receipt.get("quality_gates")
        if isinstance(gates, dict):
            parts.append(json.dumps(gates, ensure_ascii=False))
    return "\n".join(parts).lower()


def validate_expected_evidence_present(contract, receipt, facts, os_evidence):
    if not isinstance(contract, dict):
        return ["active OS contract is missing"]
    blob = evidence_text_blob(receipt, facts, os_evidence)
    errors = []
    for expected in contract.get("expected_evidence", []):
        if not non_empty_string(expected):
            continue
        needle = expected.strip().lower()
        if needle not in blob:
            errors.append(f"missing evidence for expected_evidence: {expected}")
    return errors


def collect_evidence_refs(receipt, os_evidence):
    refs = {"receipt", "verification_command"}
    for item in os_evidence:
        if non_empty_string(item.get("id")):
            refs.add(item["id"])
    gates = receipt.get("quality_gates") if isinstance(receipt, dict) else None
    if isinstance(gates, dict):
        for key in gates:
            refs.add(f"quality_gates.{key}")
    return refs


def unqualified_absolute_claim(text):
    lowered = str(text).lower()
    if not ABSOLUTE_CLAIM_RE.search(lowered):
        return False
    return not any(term in lowered for term in QUALIFIED_CLAIM_TERMS)


def truth_risk_flags(receipt, os_evidence, missing_evidence_errors):
    flags = []
    payloads = [receipt] + list(os_evidence)
    if missing_evidence_errors:
        flags.append("missing required evidence")
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        text = json.dumps(payload, ensure_ascii=False).lower()
        if non_empty_string(payload.get("limitation")):
            flags.append("limitation recorded")
        if any(term in text for term in ("not run", "not_run", "skipped", "blocked", "unable")):
            flags.append("verification skipped or blocked")
        if "missing font" in text:
            flags.append("missing font")
        if "pixel" in text and any(term in text for term in ("different", "failed", "mismatch")):
            flags.append("failed pixel diff")
        blockers = payload.get("blockers")
        try:
            if blockers is not None and int(blockers) > 0:
                flags.append("non-zero blockers")
        except (TypeError, ValueError):
            if blockers:
                flags.append("non-zero blockers")
        gates = payload.get("quality_gates")
        if isinstance(gates, dict):
            for name, gate in gates.items():
                if isinstance(gate, dict) and gate.get("result") == "FAIL":
                    flags.append(f"failed quality gate: {name}")
    return sorted(set(flags))


def validate_truth_claims(receipt, os_evidence, missing_evidence_errors=None, contract=None, state=None):
    errors = []
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]
    claims = receipt.get("claims")
    if not isinstance(claims, list) or not claims:
        return ["claims must be a non-empty list for os-close"]
    refs = collect_evidence_refs(receipt, os_evidence)
    risk_flags = truth_risk_flags(receipt, os_evidence, missing_evidence_errors or [])
    for i, item in enumerate(claims):
        if isinstance(item, str):
            errors.append(f"claims[{i}] must be an object with claim and evidence_refs")
            continue
        if not isinstance(item, dict):
            errors.append(f"claims[{i}] must be an object")
            continue
        text = item.get("claim")
        if not non_empty_string(text):
            errors.append(f"claims[{i}].claim must be a non-empty string")
            continue
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(not non_empty_string(ref) for ref in evidence_refs):
            errors.append(f"claims[{i}].evidence_refs must be a non-empty list of strings")
        else:
            missing = sorted(str(ref) for ref in evidence_refs if str(ref) not in refs)
            if missing:
                errors.append(f"claims[{i}].evidence_refs unknown: {', '.join(missing)}")
        if unqualified_absolute_claim(text) and risk_flags:
            errors.append(
                f"claims[{i}] uses an absolute claim but evidence has limitations: "
                + ", ".join(risk_flags)
            )
        if DESIGN_TOKEN_FULL_CLAIM_RE.search(str(text)) and unqualified_absolute_claim(text):
            ok, reason = full_design_token_coverage_ok(receipt, contract, state, os_evidence)
            if not ok:
                errors.append(f"claims[{i}] claims full design-token coverage without sufficient evidence: {reason}")
        if COST_CLAIM_RE.search(str(text)) and not has_real_llm_token_telemetry(os_evidence):
            errors.append(
                f"claims[{i}] claims lower token/cost usage without real llm_usage telemetry"
            )
        if SUPERIORITY_CLAIM_RE.search(str(text)) and not consumer_superiority_ok(receipt, os_evidence):
            errors.append(
                f"claims[{i}] claims Piloth consumer superiority/value without benchmark evidence proving all mandatory metrics are not worse and at least one consumer-visible metric wins"
            )
    return errors


def list_of_strings(value):
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [
        str(item).strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def evidence_source_refs(evidence):
    refs = []
    source_refs = evidence.get("source_refs")
    if isinstance(source_refs, list):
        for item in source_refs:
            if isinstance(item, str) and item.strip():
                refs.append(item.strip())
            elif isinstance(item, dict):
                file_key = item.get("fileKey") or item.get("file_key")
                node_id = item.get("nodeId") or item.get("node_id") or item.get("frameId") or item.get("frame_id")
                if non_empty_string(file_key) and non_empty_string(node_id):
                    refs.append(f"{file_key}:{node_id}")
    for file_key_name, node_key_name in (
        ("fileKey", "nodeId"),
        ("file_key", "node_id"),
        ("fileKey", "frameId"),
        ("file_key", "frame_id"),
    ):
        file_key = evidence.get(file_key_name)
        node_id = evidence.get(node_key_name)
        if non_empty_string(file_key) and non_empty_string(node_id):
            refs.append(f"{file_key}:{node_id}")
    return sorted(set(refs))


def validate_design_token_coverage(evidence):
    if not isinstance(evidence, dict):
        return ["design token coverage evidence must be an object"]
    if evidence.get("kind") != "design_token_coverage":
        return []
    errors = []
    if not evidence_source_refs(evidence):
        errors.append("design_token_coverage requires Figma/source refs (fileKey+nodeId/frameId or source_refs)")
    covered_groups = list_of_strings(evidence.get("covered_groups"))
    generated_surfaces = list_of_strings(evidence.get("generated_surfaces"))
    if not (
        covered_groups
        or generated_surfaces
        or non_empty_string(evidence.get("surface"))
        or non_empty_string(evidence.get("artifact_path"))
        or non_empty_string(evidence.get("target_path"))
    ):
        errors.append("design_token_coverage requires covered_groups, generated_surfaces, surface, artifact_path, or target_path")
    token_count = evidence.get("token_count")
    if token_count is not None:
        try:
            if int(token_count) < 0:
                errors.append("design_token_coverage.token_count must be non-negative")
        except (TypeError, ValueError):
            errors.append("design_token_coverage.token_count must be numeric when present")
    return errors


def validate_metric_evidence(evidence):
    if not isinstance(evidence, dict) or evidence.get("kind") != "metric":
        return []
    errors = []
    metric_type = str(evidence.get("metric_type") or "").strip()
    if metric_type not in METRIC_TYPES:
        errors.append("metric evidence requires metric_type one of: " + ", ".join(sorted(METRIC_TYPES)))
    if not non_empty_string(evidence.get("metric_name")):
        errors.append("metric evidence requires metric_name")
    for field in (
        "value", "count", "chars", "bytes", "duration_ms",
        "input_tokens", "output_tokens", "total_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd",
        "viewport_width", "viewport_height", "console_error_count",
        "page_error_count", "image_failure_count", "layout_overflow_count",
        "visual_diff_pixels", "visual_diff_ratio",
    ):
        if field in evidence and evidence.get(field) is not None:
            try:
                if float(evidence.get(field)) < 0:
                    errors.append(f"metric evidence {field} must be non-negative")
            except (TypeError, ValueError):
                errors.append(f"metric evidence {field} must be numeric when present")
    if metric_type == "llm_usage" and evidence.get("real_token_telemetry") is not True:
        if not non_empty_string(evidence.get("unavailable_reason")):
            errors.append("llm_usage metric without real_token_telemetry=true requires unavailable_reason")
    if metric_type == "ui_quality":
        ui_fields = (
            "viewport_width", "viewport_height", "required_text_ok",
            "console_errors", "console_error_count", "page_errors",
            "page_error_count", "image_failures", "image_failure_count",
            "horizontal_overflow", "vertical_overflow", "layout_overflow_count",
            "visual_diff_result", "screenshot_path", "comparison_artifact_path",
            "artifact_path",
        )
        if not any(field in evidence for field in ui_fields):
            errors.append("ui_quality metric requires browser/visual check fields")
    return errors


def has_real_llm_token_telemetry(os_evidence):
    return any(
        isinstance(item, dict)
        and item.get("kind") == "metric"
        and item.get("metric_type") == "llm_usage"
        and item.get("real_token_telemetry") is True
        for item in os_evidence
    )


def numeric_metric_value(item, *keys):
    for key in keys:
        if key not in item:
            continue
        try:
            return float(item.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def ui_quality_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict)
        and item.get("kind") == "metric"
        and item.get("metric_type") == "ui_quality"
    ]


def ui_quality_record_failed(item):
    failures = []
    if item.get("required_text_ok") is False:
        failures.append("required_text_ok=false")
    if item.get("horizontal_overflow") is True:
        failures.append("horizontal_overflow=true")
    if item.get("vertical_overflow") is True:
        failures.append("vertical_overflow=true")
    if numeric_metric_value(item, "console_error_count") > 0:
        failures.append("console_error_count>0")
    if numeric_metric_value(item, "page_error_count") > 0:
        failures.append("page_error_count>0")
    if numeric_metric_value(item, "image_failure_count", "image_failures") > 0:
        failures.append("image_failure_count>0")
    if numeric_metric_value(item, "layout_overflow_count") > 0:
        failures.append("layout_overflow_count>0")
    visual = str(item.get("visual_diff_result") or "").strip().lower()
    if visual in {"fail", "failed", "mismatch", "different", "regressed"}:
        failures.append("visual_diff_result=" + visual)
    return failures


def design_token_coverage_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict) and item.get("kind") == "design_token_coverage"
    ]


def design_token_profile_active(contract, receipt=None, state=None):
    for payload in (receipt, contract, state):
        if isinstance(payload, dict) and payload.get("evidence_profile") == "design_tokens":
            return True
    return False


def design_token_generated_surfaces(coverage):
    surfaces = set()
    for item in coverage:
        surfaces |= set(list_of_strings(item.get("generated_surfaces")))
        if non_empty_string(item.get("surface")):
            surfaces.add(str(item.get("surface")).strip())
    return surfaces


def validate_design_token_receipt(receipt, contract, state, os_evidence):
    if not design_token_profile_active(contract, receipt, state):
        return []
    errors = []
    coverage = design_token_coverage_records(os_evidence)
    if not coverage:
        errors.append("evidence_profile=design_tokens requires design_token_coverage evidence")
    if not any(item.get("kind") == "figma_node" for item in os_evidence):
        errors.append("evidence_profile=design_tokens requires figma_node evidence")
    for item in coverage:
        errors.extend(validate_design_token_coverage(item))
    surfaces = design_token_generated_surfaces(coverage)
    if not surfaces and not non_empty_string(receipt.get("limitation")):
        errors.append("design token coverage requires generated_surfaces/surface evidence or a receipt limitation")
    gates = receipt.get("quality_gates") if isinstance(receipt, dict) else None
    if not isinstance(gates, dict) or not isinstance(gates.get("design_token_coverage"), dict):
        errors.append("quality_gates.design_token_coverage is required for evidence_profile=design_tokens")
    return errors


def validate_ui_quality_receipt(receipt, contract, os_evidence):
    if not contract_requires_ui_quality_evidence(contract, receipt):
        return []
    errors = []
    records = ui_quality_records(os_evidence)
    if not records:
        errors.append("UI tasks require ui_quality metric evidence from browser/visual inspection")
    failed = []
    for item in records:
        for reason in ui_quality_record_failed(item):
            failed.append(f"{item.get('id', 'ui_quality')}: {reason}")
    delivery_result = str(receipt.get("result", "") if isinstance(receipt, dict) else "").strip().lower()
    if failed and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
        errors.append("UI quality evidence contains failing checks: " + ", ".join(failed))
    return errors


def full_design_token_coverage_ok(receipt, contract, state, os_evidence):
    if not design_token_profile_active(contract, receipt, state):
        return False, "receipt/contract evidence_profile is not design_tokens"
    coverage = design_token_coverage_records(os_evidence)
    full = [
        item for item in coverage
        if item.get("coverage_scope") == "full_declared_source"
    ]
    if not full:
        return False, "missing design_token_coverage coverage_scope=full_declared_source"
    if not all(evidence_source_refs(item) for item in full):
        return False, "full design-token coverage requires source refs"
    surfaces = design_token_generated_surfaces(full)
    missing_surfaces = sorted(DESIGN_TOKEN_SURFACES - surfaces)
    if missing_surfaces and not non_empty_string(receipt.get("limitation")):
        return False, "missing generated design-token surfaces: " + ", ".join(missing_surfaces)
    return True, ""


def evidence_payload_present(sanitized):
    if any(non_empty_string(sanitized.get(key)) for key in (
        "command", "summary", "artifact", "artifact_path", "target_path",
        "evidence_output", "quality_gate", "gate", "fileKey", "nodeId",
        "frameId", "coverage_scope", "surface", "metric_name", "metric_type",
        "consumer_value_result",
        "browser", "browser_tool", "url", "visual_diff_result",
        "screenshot_path", "comparison_artifact_path",
    )):
        return True
    if any(key in sanitized for key in (
        "required_text_ok", "console_errors", "console_error_count",
        "page_errors", "page_error_count", "image_failures",
        "image_failure_count", "horizontal_overflow", "vertical_overflow",
        "layout_overflow_count", "viewport_width", "viewport_height",
    )):
        return True
    if list_of_strings(sanitized.get("covered_groups")):
        return True
    if list_of_strings(sanitized.get("generated_surfaces")):
        return True
    if evidence_source_refs(sanitized):
        return True
    if isinstance(sanitized.get("options"), list) and sanitized.get("options"):
        return True
    if isinstance(sanitized.get("decisions"), list) and sanitized.get("decisions"):
        return True
    return False


def validate_prototype_evidence(evidence):
    """Validate a prototype evidence record (kind=prototype).

    Prototype's invariant: at least two design options were generated and one
    was chosen, via a valid design method. The human sign-off itself flows
    through the reused human_review round-trip, not here.
    """
    if not isinstance(evidence, dict) or evidence.get("kind") != "prototype":
        return []
    errors = []
    if evidence.get("method") not in PROTOTYPE_METHODS:
        errors.append("prototype evidence requires method one of: " + ", ".join(sorted(PROTOTYPE_METHODS)))
    options = evidence.get("options")
    if not isinstance(options, list):
        errors.append("prototype evidence requires an options list")
        return errors
    ids = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict) or not non_empty_string(opt.get("id")):
            errors.append(f"prototype options[{i}] requires an id")
            continue
        ids.append(opt.get("id"))
    if len(ids) < 2:
        errors.append("prototype evidence requires >=2 options with ids")
    chosen = evidence.get("chosen")
    if not non_empty_string(chosen):
        errors.append("prototype evidence requires a chosen option id")
    elif ids and chosen not in ids:
        errors.append("prototype chosen must be one of the generated option ids")
    return errors


def validate_discovery_evidence(evidence):
    """Validate a discovery evidence record (kind=discovery).

    Discovery is a judgment gate the phase runs up front; the only mechanical
    check is that the confirmed decisions are recorded as evidence the
    Traceability gate can trace to. Each decision names its question, answer and
    source (user vs a pre-ticked "decide for me" default).
    """
    if not isinstance(evidence, dict) or evidence.get("kind") != "discovery":
        return []
    errors = []
    decisions = evidence.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        errors.append("discovery evidence requires a non-empty decisions list")
        return errors
    for i, dec in enumerate(decisions):
        if not isinstance(dec, dict):
            errors.append(f"discovery decisions[{i}] must be an object")
            continue
        if not non_empty_string(dec.get("q")):
            errors.append(f"discovery decisions[{i}] requires a question 'q'")
        if not non_empty_string(dec.get("answer")):
            errors.append(f"discovery decisions[{i}] requires an 'answer'")
    return errors


def sanitize_os_evidence_payload(payload):
    if not isinstance(payload, dict):
        return None, ["evidence payload must be a JSON object"]
    allowed = {
        "id", "ref", "evidence_ref", "kind", "command", "result", "summary",
        "artifact", "path", "tool", "risk", "timeout", "evidence_output",
        "limitation", "quality_gate", "gate", "status", "blockers",
        "fileKey", "file_key", "nodeId", "node_id", "frameId", "frame_id",
        "token_count", "covered_groups", "surface", "artifact_path",
        "target_path", "source_refs", "coverage_scope", "generated_surfaces",
        "verification", "limitations",
        "method", "options", "chosen", "chosen_rationale",
        "prototype_doc", "prototype_sha256",
        "discovery_doc", "decisions", "unresolved",
        "metric_type", "metric_name", "phase", "unit", "value", "count",
        "chars", "bytes", "duration_ms", "input_tokens", "output_tokens",
        "total_tokens", "real_token_telemetry", "unavailable_reason",
        "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd",
        "cost_complete", "unpriced_models", "unpriced_tokens",
        "model", "pricing_source", "window_start", "subagent_scope",
        "consumer_value_result", "all_mandatory_not_worse",
        "consumer_visible_win", "mandatory_regressions", "wins",
        "viewport_width", "viewport_height", "browser", "browser_tool", "url",
        "required_text_ok", "console_errors", "console_error_count",
        "page_errors", "page_error_count", "image_failures", "image_failure_count",
        "horizontal_overflow", "vertical_overflow", "layout_overflow_count",
        "visual_diff_result", "visual_diff_pixels", "visual_diff_ratio",
        "screenshot_path", "baseline_screenshot_path", "comparison_artifact_path",
    }
    output_fields = {"stdout", "stderr", "output", "raw_output", "full_output", "logs", "log", "env", "environment"}
    sanitized = {}
    for key, value in payload.items():
        if key in output_fields:
            sanitized["output_redacted"] = True
            continue
        if key == "task_id":
            continue
        if key not in allowed:
            continue
        if SECRET_KEY_RE.search(str(key)) and key not in SAFE_OS_EVIDENCE_METADATA_KEYS:
            sanitized[str(key)] = "[redacted]"
        else:
            sanitized[str(key)] = sanitize_state_value(value, limit=1000)
    kind = sanitized.get("kind")
    if kind is not None and kind not in OS_EVIDENCE_KINDS:
        return None, ["kind must be one of: " + ", ".join(sorted(OS_EVIDENCE_KINDS))]
    if not evidence_payload_present(sanitized):
        return None, ["evidence must include command, summary, artifact, safe metadata, evidence_output, quality_gate, or gate"]
    coverage_errors = validate_design_token_coverage(sanitized)
    if coverage_errors:
        return None, coverage_errors
    metric_errors = validate_metric_evidence(sanitized)
    if metric_errors:
        return None, metric_errors
    prototype_errors = validate_prototype_evidence(sanitized)
    if prototype_errors:
        return None, prototype_errors
    discovery_errors = validate_discovery_evidence(sanitized)
    if discovery_errors:
        return None, discovery_errors
    evidence_id = (
        safe_evidence_id(sanitized.get("id"))
        or safe_evidence_id(sanitized.get("ref"))
        or safe_evidence_id(sanitized.get("evidence_ref"))
    )
    if not evidence_id:
        basis = dict(sanitized)
        evidence_id = "ev-" + sha256_json(basis)[:12]
    sanitized["id"] = evidence_id
    sanitized["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sanitized["repo_key"] = REPO_KEY
    return sanitized, []


# ------------------------------------------------- OS cost and token telemetry
def metric_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict) and item.get("kind") == "metric"
    ]


def metric_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def metric_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_model_pricing():
    """Load the advisory model price map (USD per MTok). Fail-soft → {} when the
    file is missing or malformed, so telemetry never breaks on a bad price map."""
    data = load_json_file(PILOTHOS_DIR / "runtime" / "model-pricing.json")
    if isinstance(data, dict) and isinstance(data.get("models"), dict):
        return data
    return {}


def model_price(model, pricing=None):
    """Return the price row {input, output, cache_write_5m, cache_read} for a
    model id in USD/MTok, or None when the model is unknown (cost then omitted)."""
    if not non_empty_string(model):
        return None
    pricing = pricing if isinstance(pricing, dict) else load_model_pricing()
    models = pricing.get("models") if isinstance(pricing, dict) else None
    row = models.get(model) if isinstance(models, dict) else None
    return row if isinstance(row, dict) else None


def compute_token_cost_usd(usage, model, pricing=None):
    """Cost of one usage record given a price row, or None when the model is
    unpriced. usage keys: input_tokens/output_tokens/cache_creation_input_tokens/
    cache_read_input_tokens. Cache tiers are priced separately (cache_read ~0.1x,
    cache_write ~1.25x input) — ignoring them would misstate cost badly."""
    row = model_price(model, pricing)
    if row is None:
        return None
    per_mtok = lambda tokens, rate: metric_float(tokens) / 1_000_000.0 * metric_float(rate)
    cost = (
        per_mtok(usage.get("input_tokens"), row.get("input"))
        + per_mtok(usage.get("output_tokens"), row.get("output"))
        + per_mtok(usage.get("cache_creation_input_tokens"), row.get("cache_write_5m"))
        + per_mtok(usage.get("cache_read_input_tokens"), row.get("cache_read"))
    )
    return round(cost, 6)


def parse_iso_timestamp(ts):
    """Parse an ISO-8601 timestamp (accepting a trailing Z) to a datetime, or
    None. Used to window transcript records by the OS run's created_at."""
    if not non_empty_string(ts):
        return None
    text = ts.strip().replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


def transcript_project_slug():
    """Claude Code encodes the project cwd into the transcript dir name by
    replacing '/' and '.' with '-' (e.g. -Users-me-VNG-tools-piloth)."""
    return re.sub(r"[/.]", "-", str(REPO_ROOT.resolve()))


def resolve_transcript_path(argv, hook_input=None):
    """Locate the Claude Code session transcript: explicit --transcript wins,
    then a hook's transcript_path, then the newest *.jsonl for this project.
    Returns a Path or None (None → telemetry unavailable, recorded honestly)."""
    argv = argv or []
    for i, arg in enumerate(argv):
        if arg == "--transcript" and i + 1 < len(argv):
            return pathlib.Path(argv[i + 1]).expanduser()
        if arg.startswith("--transcript="):
            return pathlib.Path(arg.split("=", 1)[1]).expanduser()
    if isinstance(hook_input, dict) and non_empty_string(hook_input.get("transcript_path")):
        return pathlib.Path(hook_input["transcript_path"]).expanduser()
    base = pathlib.Path.home() / ".claude" / "projects" / transcript_project_slug()
    if not base.exists():
        return None
    def _mtime(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0
    candidates = sorted(base.glob("*.jsonl"), key=_mtime)
    return candidates[-1] if candidates else None


TRANSCRIPT_USAGE_KEYS = (
    "input_tokens", "output_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens",
)
# Transcript `message.model` values that are not a model call. They carry a
# usage block, so they would otherwise be summed as real tokens and — being
# absent from the price map — reported as an unpriced model.
NON_BILLABLE_TRANSCRIPT_MODELS = frozenset({"<synthetic>"})


def sum_transcript_usage(path, since=None, pricing=None):
    """Sum real per-turn `message.usage` from a Claude Code transcript, windowed
    to records at/after `since` (a datetime). Returns a dict with summed usage,
    per-model token totals, the cost of the priced portion, and record/model
    counts — or None if the file can't be read.

    Cost is a subtotal, not all-or-nothing: an unpriced model used to void
    `cost_usd` for the entire run, silently, so a single turn on a model missing
    from the price map cost the caller every other turn's number too. Now the
    priced portion is summed and the gap is declared in `cost_complete` /
    `unpriced_models` / `unpriced_tokens`. `cost_usd` is None only when nothing
    at all could be priced.

    Attribution is main-session-only: background subagent transcripts are
    separate files and are not summed here (disclosed as subagent_scope)."""
    usage = {k: 0 for k in TRANSCRIPT_USAGE_KEYS}
    per_model_tokens = {}
    unpriced_models = {}
    records = 0
    cost_total = 0.0
    priced_records = 0
    pricing = pricing if isinstance(pricing, dict) else load_model_pricing()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if since is not None:
                    rec_ts = parse_iso_timestamp(rec.get("timestamp"))
                    if rec_ts is not None and rec_ts < since:
                        continue
                msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                u = msg.get("usage") if isinstance(msg, dict) else None
                if not isinstance(u, dict):
                    continue
                model = msg.get("model") if non_empty_string(msg.get("model")) else "unknown"
                if model in NON_BILLABLE_TRANSCRIPT_MODELS:
                    # Harness-generated turn, not a model call. Counting it would
                    # overstate real tokens and make the run look unpriced.
                    continue
                records += 1
                row = {k: metric_int(u.get(k)) for k in TRANSCRIPT_USAGE_KEYS}
                for k in TRANSCRIPT_USAGE_KEYS:
                    usage[k] += row[k]
                row_tokens = sum(row.values())
                per_model_tokens[model] = per_model_tokens.get(model, 0) + row_tokens
                c = compute_token_cost_usd(row, model, pricing)
                if c is None:
                    unpriced_models[model] = unpriced_models.get(model, 0) + row_tokens
                else:
                    cost_total += c
                    priced_records += 1
    except OSError:
        return None
    primary_model = max(per_model_tokens, key=per_model_tokens.get) if per_model_tokens else ""
    return {
        "usage": usage,
        "records": records,
        "models": sorted(per_model_tokens),
        "primary_model": primary_model,
        "cost_usd": round(cost_total, 6) if priced_records else None,
        "cost_complete": not unpriced_models,
        "unpriced_models": sorted(unpriced_models),
        "unpriced_tokens": sum(unpriced_models.values()),
        "pricing_source": pricing.get("source") if isinstance(pricing, dict) else "",
    }


def token_telemetry_payload(task_id, created_at, summed):
    """(evidence payload, result label) for a summed transcript, or for no data.

    Split out of token_telemetry so the mode function stays inside the
    function-length ratchet; it is also the unit under test for the cost fields.
    """
    base = {
        "task_id": task_id,
        "kind": "metric",
        "metric_type": "llm_usage",
        "metric_name": "session-token-usage",
        "subagent_scope": "main_session_only",
    }
    if not summed or summed.get("records", 0) == 0:
        base.update({
            "real_token_telemetry": False,
            "unavailable_reason": "no Claude Code transcript usage found for this session (harness may not expose per-turn token telemetry)",
            "summary": "token telemetry unavailable",
        })
        return base, "token_telemetry_unavailable"

    usage = summed["usage"]
    base.update({
        "real_token_telemetry": True,
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cache_creation_input_tokens": usage["cache_creation_input_tokens"],
        "cache_read_input_tokens": usage["cache_read_input_tokens"],
        "total_tokens": usage["input_tokens"] + usage["output_tokens"],
        "model": summed.get("primary_model") or "",
        "window_start": created_at or "",
        "summary": f"session token telemetry from Claude Code transcript ({summed['records']} turns)",
    })
    if summed.get("cost_usd") is not None:
        base["cost_usd"] = summed["cost_usd"]
        # Whether the cost covers every turn travels with the number, so a
        # subtotal is never mistaken for a complete bill.
        base["cost_complete"] = bool(summed.get("cost_complete"))
        if summed.get("unpriced_models"):
            base["unpriced_models"] = summed["unpriced_models"]
            base["unpriced_tokens"] = summed.get("unpriced_tokens", 0)
        if non_empty_string(summed.get("pricing_source")):
            base["pricing_source"] = summed["pricing_source"]
    elif summed.get("unpriced_models"):
        base["unavailable_reason"] = (
            "no model in this session is in runtime/model-pricing.json: "
            + ", ".join(summed["unpriced_models"])
        )
    return base, "token_telemetry_recorded"


def token_telemetry(argv):
    """Extract real LLM token telemetry from the Claude Code session transcript
    and record it as an `os-evidence kind=metric metric_type=llm_usage
    real_token_telemetry=true` for the active OS run. Windowed to the run's
    created_at; main-session-only (disclosed). Fails soft: no transcript →
    records real_token_telemetry=false + unavailable_reason.

    Usage: token-telemetry [--task <id>] [--transcript <path>]
    """
    argv = argv or []
    task_id = None
    for i, arg in enumerate(argv):
        if arg == "--task" and i + 1 < len(argv):
            task_id = argv[i + 1]
        elif arg.startswith("--task="):
            task_id = arg.split("=", 1)[1]
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "token_telemetry_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    if state.get("status") in {"closed", "sealed"}:
        json_print({"result": "token_telemetry_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]})
        return
    task_id = state["task_id"]
    created_at = state.get("created_at")
    since = parse_iso_timestamp(created_at)
    transcript = resolve_transcript_path(argv)
    summed = sum_transcript_usage(transcript, since=since) if transcript else None

    payload, result_label = token_telemetry_payload(task_id, created_at, summed)

    evidence, errors = sanitize_os_evidence_payload(payload)
    if errors:
        json_print({"result": "token_telemetry_rejected", "task_id": task_id, "errors": errors})
        return
    evidence["task_id"] = task_id
    append_os_evidence(task_id, evidence)
    state.setdefault("lifecycle", [])
    if "tool/evidence" not in state["lifecycle"]:
        state["lifecycle"].append("tool/evidence")
    state["evidence_count"] = len(os_evidence_records(task_id))
    save_os_state(state)
    out = {
        "result": result_label,
        "task_id": task_id,
        "evidence_ref": evidence["id"],
        "transcript": str(transcript) if transcript else None,
        "window_start": created_at or "",
        "real_token_telemetry": bool(payload.get("real_token_telemetry")),
        "subagent_scope": "main_session_only",
    }
    if result_label == "token_telemetry_recorded":
        out.update({
            "records": summed["records"],
            "models": summed["models"],
            "model": payload.get("model", ""),
            "tokens": summed["usage"],
            "cost_usd": payload.get("cost_usd", "unavailable_unpriced_model"),
        })
    json_print(out)


def cost_ledger_summary(os_evidence):
    metrics = metric_records(os_evidence)
    real_llm = [item for item in metrics if item.get("metric_type") == "llm_usage" and item.get("real_token_telemetry") is True]
    unavailable_llm = [
        item for item in metrics
        if item.get("metric_type") == "llm_usage" and item.get("real_token_telemetry") is not True
    ]
    benchmark = [
        item for item in metrics
        if item.get("metric_type") == "benchmark"
    ]
    # `token-telemetry` reports a CUMULATIVE figure for the whole run window, so
    # summing two of its records double-counts the same tokens — and it is safe to
    # run twice (mid-task, then before close), which the docs invite. Records
    # carrying `window_start` are cumulative by definition: keep the newest and
    # treat the rest as superseded. Manually recorded per-phase llm_usage (no
    # window_start) stays additive.
    cumulative = [item for item in real_llm if non_empty_string(item.get("window_start"))]
    superseded = 0
    if len(cumulative) > 1:
        newest = max(cumulative, key=lambda item: str(item.get("recorded_at") or ""))
        superseded = len(cumulative) - 1
        real_llm = [
            item for item in real_llm
            if item is newest or not non_empty_string(item.get("window_start"))
        ]
    real_tokens = None
    if real_llm:
        real_tokens = {
            "input_tokens": sum(metric_int(item.get("input_tokens")) for item in real_llm),
            "output_tokens": sum(metric_int(item.get("output_tokens")) for item in real_llm),
            "total_tokens": sum(metric_int(item.get("total_tokens")) for item in real_llm),
            "cache_creation_input_tokens": sum(metric_int(item.get("cache_creation_input_tokens")) for item in real_llm),
            "cache_read_input_tokens": sum(metric_int(item.get("cache_read_input_tokens")) for item in real_llm),
            "cost_usd": round(sum(metric_float(item.get("cost_usd")) for item in real_llm), 6),
            # Complete only if EVERY contributing record says so. A record with no
            # cost_usd at all also leaves the total a floor, so absence counts as
            # incomplete rather than as agreement.
            "cost_complete": all(
                item.get("cost_complete") is True for item in real_llm
            ),
            "unpriced_models": sorted({
                str(name).strip()
                for item in real_llm
                for name in (item.get("unpriced_models") or [])
                if str(name).strip()
            }),
        }
    return {
        "schema_version": 1,
        "metric_records": len(metrics),
        "real_tokens": real_tokens if real_tokens is not None else "unavailable",
        "real_token_telemetry": bool(real_llm),
        # Disclosed rather than silent: an earlier cumulative snapshot was dropped
        # in favour of the newest one instead of being added to it.
        "superseded_token_snapshots": superseded,
        "token_unavailable_reasons": sorted(set(
            str(item.get("unavailable_reason", "")).strip()
            for item in unavailable_llm
            if str(item.get("unavailable_reason", "")).strip()
        )),
        "tool_output_chars": sum(metric_int(item.get("chars")) for item in metrics if item.get("metric_type") == "tool_output"),
        "context_loads": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "context_load"),
        "commands": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "command"),
        "retries": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "retry"),
        "repairs": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "repair"),
        "duration_ms": sum(metric_int(item.get("duration_ms")) for item in metrics),
        "benchmark_results": [
            {
                "id": item.get("id"),
                "result": item.get("consumer_value_result", ""),
                "all_mandatory_not_worse": bool(item.get("all_mandatory_not_worse")),
                "consumer_visible_win": bool(item.get("consumer_visible_win")),
                "real_token_telemetry": bool(item.get("real_token_telemetry")),
                "wins": item.get("wins", []),
                "mandatory_regressions": item.get("mandatory_regressions", []),
            }
            for item in benchmark
        ],
    }


def budget_status(contract, os_evidence):
    """Advisory-only budget view: compare real spend (from token telemetry) to an
    optional contract budget.max_usd. Surfaced in os-status / os-report; it NEVER
    blocks os-close. Returns advisory_unavailable when no ceiling is set or no
    real-token cost has been recorded yet."""
    budget = contract.get("budget") if isinstance(contract, dict) else None
    max_usd = None
    if isinstance(budget, dict) and budget.get("max_usd") is not None:
        try:
            max_usd = float(budget.get("max_usd"))
        except (TypeError, ValueError):
            max_usd = None
    if max_usd is None:
        return {"status": "advisory_unavailable", "reason": "no budget.max_usd in contract"}
    ledger = cost_ledger_summary(os_evidence)
    real = ledger.get("real_tokens")
    spent = real.get("cost_usd") if isinstance(real, dict) else None
    if not isinstance(spent, (int, float)):
        return {
            "status": "advisory_unavailable",
            "reason": "no real token telemetry / cost recorded yet (run token-telemetry)",
            "max_usd": max_usd,
        }
    complete = real.get("cost_complete") is True
    status = {
        "advisory": True,
        "max_usd": max_usd,
        "spent_usd": round(float(spent), 6),
        "remaining_usd": round(max_usd - float(spent), 6),
        # A subtotal can only prove the budget IS exceeded, never that it isn't.
        "over_budget": float(spent) > max_usd,
        "cost_complete": complete,
        "note": "advisory only — does not block os-close",
    }
    if not complete:
        status["spent_is_floor"] = True
        status["note"] = (
            "advisory only — does not block os-close; spent_usd is a FLOOR "
            "(some turns ran on models missing from runtime/model-pricing.json)"
        )
        unpriced = real.get("unpriced_models") or []
        if unpriced:
            status["unpriced_models"] = unpriced
    return status


def record_checkpoint_from_evidence(state, evidence):
    phase = str(evidence.get("phase") or "").strip()
    if not phase:
        return
    checkpoints = state.setdefault("checkpoints", [])
    checkpoints.append({
        "phase": phase,
        "evidence_ref": evidence.get("id", ""),
        "kind": evidence.get("kind", ""),
        "recorded_at": evidence.get("recorded_at", ""),
        "summary": evidence.get("summary", ""),
        "metric_type": evidence.get("metric_type", ""),
    })


def update_state_runtime_cost(state, task_id):
    evidence = os_evidence_records(task_id)
    state["cost_ledger"] = cost_ledger_summary(evidence)
    return state["cost_ledger"]


def consumer_superiority_payloads(receipt, os_evidence):
    payloads = []
    if isinstance(receipt, dict) and isinstance(receipt.get("consumer_superiority"), dict):
        payloads.append(receipt.get("consumer_superiority"))
    for item in os_evidence:
        if isinstance(item, dict) and item.get("kind") == "metric" and item.get("metric_type") == "benchmark":
            payloads.append(item)
    return payloads


def consumer_superiority_ok(receipt, os_evidence):
    for payload in consumer_superiority_payloads(receipt, os_evidence):
        result = str(payload.get("result") or payload.get("consumer_value_result") or "").strip().lower()
        if (
            result in SUPERIORITY_PASS_RESULTS
            and payload.get("all_mandatory_not_worse") is True
            and payload.get("consumer_visible_win") is True
            and (
                payload.get("real_token_telemetry") is True
                or has_real_llm_token_telemetry(os_evidence)
            )
        ):
            return True
    return False


# ---------------------------------------------------------- OS lifecycle modes
def os_start_schema_payload():
    """Machine-readable os-start request schema (SSOT for the doc page).

    Mirrors `installer explain`: field -> {required, default, allowed, aliases}.
    """
    return {
        "result": "os_start_schema",
        "note": "All fields optional; a bare {} opens a repo-local run. See runtime/os-control-plane.md.",
        "fields": {
            "task_id": {"required": False, "default": "task-<sha256[:12]> from intent", "aliases": ["id", "request_id"]},
            "intent": {"required": False, "default": "repo-local OS task", "aliases": ["task_scope", "summary", "title"], "note": "becomes contract.task_scope"},
            "task_signal": {"required": False, "default": "not_applicable", "allowed": sorted(ASSET_ROUTING_SIGNALS)},
            "target_repo": {"required": False, "default": "<control-plane repo>", "note": "absolute path; must exist and not be inside pilothOS/memory/state"},
            "target_kind": {"required": False, "allowed": sorted(TARGET_KINDS), "note": "cross-checked vs actual git detection"},
            "target_paths": {"required": False, "default": ["**/*"], "aliases": ["allowed_paths", "affected_paths", "paths"], "note": "each must be a safe glob"},
            "affected_layers": {"required": False, "default": "derived from paths", "note": "contract requires a non-empty list"},
            "expected_evidence": {"required": False, "default": ["manual verification receipt"]},
            "out_of_scope_paths": {"required": False, "default": []},
            "evidence_profile": {"required": False, "default": "generic", "allowed": sorted(EVIDENCE_PROFILES)},
            "mode": {"required": False, "default": "adaptive", "allowed": sorted(OS_MODE_REQUESTS), "aliases": ["os_mode", "piloth_mode"], "note": "adaptive/auto resolve to lean|standard|strict"},
            "operational_preset": {"required": False, "allowed": sorted(OPERATIONAL_PRESETS)},
            "target_footprint_policy": {"required": False, "allowed": sorted(TARGET_FOOTPRINT_POLICIES), "aliases": ["footprint_policy"], "default": "no_control_plane_files if explicit target else repo_local_state_allowed"},
            "execution_strategy": {"required": False, "default": "controlled_target if explicit target else repo_local"},
            "budget": {"required": False, "note": "object; budget.max_usd is an advisory cost ceiling"},
            "adapter": {"required": False, "allowed": ["claude", "codex", "cursor", "antigravity"], "note": "used for capability handshake; unknown adapters degrade explicitly"},
            "locale": {"required": False, "default": "en", "note": "localizes human-readable summary only; IDs and schema remain English"},
            "adapter_capabilities": {"required": False, "note": "native|emulated|unavailable map; request values override the conservative adapter registry"},
            "specialists": {"required": False, "note": "consumer specialist registry entries; healthy qualified consumer entries outrank Piloth fallbacks"},
            "work_packages": {"required": False, "note": "independent work packages used by the scored team gate"},
            "user_overrides": {"required": False, "note": "rollout/execution override; safety review remains mandatory"},
            "success_metrics": {"required": False},
            "requires_prototype": {"required": False, "default": False, "note": "true also forces requires_human_review"},
            "requires_human_review": {"required": False, "default": False},
            "requires_discovery": {"required": False, "default": False},
            "energy_budget_reason": {"required": "when expected_evidence names a full-suite/broad run", "note": "justify the blast radius of an expensive run"},
        },
    }


def os_start(argv):
    if "--explain" in list(argv):
        json_print(os_start_schema_payload())
        return
    try:
        request, source = json_arg_or_stdin(argv, "os-start")
    except Exception as e:
        json_print({"result": "os_start_rejected", "errors": [str(e)]})
        return
    if not isinstance(request, dict):
        json_print({"result": "os_start_rejected", "errors": ["request must be a JSON object"]})
        return
    if "evidence_profile" in request and str(request.get("evidence_profile")) not in EVIDENCE_PROFILES:
        json_print({
            "result": "os_start_rejected",
            "errors": ["evidence_profile must be one of: " + ", ".join(sorted(EVIDENCE_PROFILES))],
        })
        return
    target, target_errors = resolve_target_repo(request)
    if target_errors:
        json_print({"result": "os_start_rejected", "errors": target_errors})
        return
    task_id = request_task_id(request)
    paths = request_paths(request)
    for pattern in paths:
        if not path_pattern_is_safe(pattern):
            json_print({
                "result": "os_start_rejected",
                "task_id": task_id,
                "errors": [f"target_paths contains unsafe pattern: {pattern}"],
            })
            return
    task_signal = request.get("task_signal") or "not_applicable"
    evidence_router = evidence_route_payload(request)
    if evidence_router.get("result") != "evidence_route":
        json_print({
            "result": "os_start_rejected",
            "task_id": task_id,
            "errors": evidence_router.get("errors", ["evidence router rejected request"]),
        })
        return
    routed_signal = evidence_router.get("task_signal") or task_signal
    route = route_task_payload({
        "task_signal": routed_signal,
        "intent": request_intent(request),
        "affected_paths": paths,
        "adapter": request.get("adapter"),
        "adapter_capabilities": request.get("adapter_capabilities"),
        "_router_compat_only": True,
    })
    scheduler = scheduler_suggest_payload({
        "task_signal": routed_signal,
        "affected_paths": paths,
        "intent": request_intent(request),
        "_router_compat_only": True,
    })
    contract = build_os_contract(request, route, scheduler, target=target)
    contract["evidence_router"] = evidence_router
    contract["decision_id"] = evidence_router.get("decision_id")
    contract["evidence_plan"] = evidence_router.get("evidence_plan", [])
    contract["execution_plan"] = evidence_router.get("execution_plan", {})
    contract["verification_plan"] = evidence_router.get("verification_plan", [])
    contract["router_limitations"] = evidence_router.get("limitations", [])
    contract_errors = validate_task_contract(contract)
    if contract_errors:
        json_print({"result": "os_start_rejected", "task_id": task_id, "errors": contract_errors})
        return
    health_rows = [health_for_asset(row) for row in scanned_asset_rows()]
    target_snapshot = target_state_snapshot(target)
    state = {
        "schema_version": 2,
        "repo_key": REPO_KEY,
        "task_id": task_id,
        "status": "open",
        "lifecycle": ["intake", "contract", "route"],
        "request": sanitize_state_value(request, limit=1000),
        "request_sha256": sha256_json(sanitize_state_value(request, limit=1000)),
        "request_source": str(source.relative_to(REPO_ROOT)) if source and source.is_relative_to(REPO_ROOT) else str(source or ""),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task_scope": contract["task_scope"],
        "affected_layers": contract["affected_layers"],
        "allowed_paths": contract["allowed_paths"],
        "target_paths": contract["target_paths"],
        "target": target,
        "target_snapshot_sha256": target_snapshot.get("snapshot_sha256", ""),
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "evidence_profile": contract.get("evidence_profile", "generic"),
        "mode": contract.get("mode", "standard"),
        "adaptive_mode": bool(contract.get("adaptive_mode")),
        "mode_decisions": contract.get("mode_decisions", []),
        "execution_strategy": contract.get("execution_strategy", ""),
        "target_footprint_policy": contract.get("target_footprint_policy", ""),
        "budget": contract.get("budget", {}),
        "success_metrics": contract.get("success_metrics", []),
        "benchmark_id": contract.get("benchmark_id", ""),
        "checkpoints": [],
        "cost_ledger": cost_ledger_summary([]),
        "coverage_claims": contract.get("coverage_claims", {}),
        "expected_evidence": contract["expected_evidence"],
        "required_gates": required_gates_for_task(contract, mode=contract.get("mode")),
        "contract": contract,
        "asset_routing": {
            "route": route,
            "asset_count": len(health_rows),
            "unhealthy_assets": [
                {
                    "id": row.get("id"),
                    "status": row.get("status"),
                    "reason": row.get("health_reason", ""),
                }
                for row in health_rows
                if row.get("status") not in {"healthy", "not_applicable"}
            ][:20],
        },
        "scheduler_suggestion": scheduler,
        "evidence_router": evidence_router,
    }
    state_path = save_os_state(state)
    write_json(os_state_path(task_id, "contract.json"), contract)
    write_json(os_state_path(task_id, "target-snapshot.json"), target_snapshot)
    repo_contract = dict(contract)
    repo_contract["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    repo_contract["source"] = state_path.relative_to(REPO_ROOT).as_posix()
    MARKER_DIR.mkdir(exist_ok=True)
    write_json(repo_state_file("task-contract.json"), repo_contract)
    empty_facts = {
        "changed_files": {},
        "affected_layers": [],
        "has_tests": False,
        "has_docs": False,
        "evidence_commands": [],
        "warnings": [],
    }
    update_diff_fact_derived(empty_facts, contract)
    save_diff_facts({}, empty_facts)
    try:
        repo_state_file("deliver-receipt.json").unlink()
    except OSError:
        pass
    json_print({
        "result": "os_started",
        "task_id": task_id,
        "state_path": state_path.relative_to(REPO_ROOT).as_posix(),
        "contract_path": os_state_path(task_id, "contract.json").relative_to(REPO_ROOT).as_posix(),
        "target_snapshot_path": os_state_path(task_id, "target-snapshot.json").relative_to(REPO_ROOT).as_posix(),
        "active_contract_path": repo_state_file("task-contract.json").as_posix(),
        "target": {
            "target_repo": target.get("target_repo"),
            "target_kind": target.get("target_kind"),
            "target_vcs": target.get("target_vcs"),
            "target_id": target.get("target_id"),
            "baseline_dirty_paths": target_snapshot.get("git_status_short", []),
            "file_count": target_snapshot.get("file_count"),
        },
        "required_gates": state["required_gates"],
        "expected_evidence": contract["expected_evidence"],
        "mode": state["mode"],
        "adaptive_mode": state["adaptive_mode"],
        "mode_decisions": state["mode_decisions"],
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "scheduler": {
            "expected_evidence": scheduler.get("expected_evidence") if isinstance(scheduler, dict) else [],
            "energy_budget": scheduler.get("energy_budget") if isinstance(scheduler, dict) else "",
        },
        "asset_routing": route,
        # The full decision is already persisted in the run state and in the
        # contract.json named above, so stdout carries the digest rather than a
        # second copy of the same ~2k tokens.
        "evidence_router": evidence_route_digest(evidence_router),
    })


def os_status(argv=None):
    argv = list(argv or [])
    verbose = "--verbose" in argv
    argv = [a for a in argv if not a.startswith("--")]
    task_id = argv[0] if argv else None
    state, path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_status_missing", "errors": ["no OS run state found"]})
        return
    evidence = os_evidence_records(state.get("task_id"))
    json_print({
        "result": "os_status",
        "task_id": state.get("task_id"),
        "status": state.get("status"),
        "state_path": path.relative_to(REPO_ROOT).as_posix() if path else "",
        "lifecycle": state.get("lifecycle", []),
        "affected_layers": state.get("affected_layers", []),
        # build_os_contract assigns both from the same resolved path list, and
        # target_paths declares allowed_paths as one of its aliases — so they are
        # identical unless the target repo differs from the control plane. Print
        # the alias only when it actually carries different information.
        **(
            {"allowed_paths": state.get("allowed_paths", [])}
            if state.get("allowed_paths", []) != state.get("target_paths", [])
            else {}
        ),
        "target_paths": state.get("target_paths", []),
        "target": state.get("target", {}),
        "evidence_profile": state.get("evidence_profile", "generic"),
        "mode": state.get("mode", ""),
        "adaptive_mode": state.get("adaptive_mode", False),
        "mode_decisions": state.get("mode_decisions", []),
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "budget": state.get("budget", {}),
        "cost_ledger": cost_ledger_summary(evidence),
        "budget_status": budget_status(state.get("contract") or {}, evidence),
        "expected_evidence": state.get("expected_evidence", []),
        "required_gates": state.get("required_gates", []),
        "phase_plan_suggestion": (state.get("contract") or {}).get("phase_plan_suggestion", {}),
        "model_hints": (state.get("contract") or {}).get("model_hints", {}),
        "evidence_router": (
            state.get("evidence_router", {}) if verbose
            else evidence_route_digest(state.get("evidence_router", {}))
        ),
        "requires_prototype": bool((state.get("contract") or {}).get("requires_prototype")),
        "requires_discovery": bool((state.get("contract") or {}).get("requires_discovery")),
        "prototype": state.get("prototype", {}),
        "human_review": state.get("human_review", {}),
        "discovery_recorded": latest_evidence_of_kind(evidence, "discovery") is not None,
        "evidence_count": len(evidence),
        "seal_sha256": state.get("seal_sha256", ""),
    })


def os_evidence(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "os-evidence")
    except Exception as e:
        json_print({"result": "os_evidence_rejected", "errors": [str(e)]})
        return
    task_id = payload.get("task_id") if isinstance(payload, dict) else None
    state, state_path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_evidence_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    if state.get("status") in {"closed", "sealed"}:
        json_print({"result": "os_evidence_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]})
        return
    evidence, errors = sanitize_os_evidence_payload(payload)
    if errors:
        json_print({"result": "os_evidence_rejected", "task_id": state.get("task_id"), "errors": errors})
        return
    task_id = state["task_id"]
    evidence["task_id"] = task_id
    evidence_path = append_os_evidence(task_id, evidence)
    facts = load_diff_facts({})
    facts.setdefault("evidence_commands", []).append({
        "command": evidence.get("command") or evidence.get("summary") or evidence.get("artifact") or evidence["id"],
        "result": evidence.get("result") or evidence.get("status") or "recorded",
        "recorded_at": evidence["recorded_at"],
        "evidence_ref": evidence["id"],
    })
    update_diff_fact_derived(facts, state.get("contract"))
    save_diff_facts({}, facts)
    state.setdefault("lifecycle", [])
    if "tool/evidence" not in state["lifecycle"]:
        state["lifecycle"].append("tool/evidence")
    record_checkpoint_from_evidence(state, evidence)
    state["evidence_count"] = len(os_evidence_records(task_id))
    update_state_runtime_cost(state, task_id)
    save_os_state(state)
    json_print({
        "result": "os_evidence_recorded",
        "task_id": task_id,
        "evidence_ref": evidence["id"],
        "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
        "sanitized": bool(evidence.get("output_redacted")),
    })


def write_active_receipt(receipt):
    MARKER_DIR.mkdir(exist_ok=True)
    receipt = dict(receipt)
    receipt["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_json(repo_state_file("deliver-receipt.json"), receipt)
    return receipt, repo_state_file("deliver-receipt.json")


def record_receipt_seal(receipt, contract, facts):
    previous = latest_receipt_seal_hash()
    seal = build_receipt_seal(receipt, contract, facts, previous)
    seal["result"] = "receipt_sealed"
    RECEIPT_SEALS.parent.mkdir(parents=True, exist_ok=True)
    with open(RECEIPT_SEALS, "a", encoding="utf-8") as f:
        f.write(json.dumps(seal, ensure_ascii=False, sort_keys=True) + "\n")
    seal["recorded_to"] = RECEIPT_SEALS.relative_to(REPO_ROOT).as_posix()
    return seal


def cross_project_enforcement_advisory(active_facts, target_diff):
    """Non-blocking advisory when hooks likely did not fire on the target.

    If diff-facts (populated only by the target's own PostToolUse hook) is empty
    yet the git/manifest target-diff shows changes, the run was almost certainly
    driven from a different session/repo, so the target's Stop-time deliver gate
    never ran. Enforcement then rests on the target-diff alone. Returns an
    advisory string (or "" when coverage looks normal).
    """
    if not (isinstance(active_facts, dict) and isinstance(target_diff, dict)):
        return ""
    if active_facts.get("changed_files") or not target_diff.get("changed_paths"):
        return ""
    return (
        "diff-facts empty but target-diff shows changes: the target's PostToolUse/"
        "Stop hooks likely did not fire (task driven from another session). "
        "Enforcement relied on the git/manifest target-diff only; run inside the "
        "target's own session for full hook coverage."
    )


def os_close_result(receipt, task_id=None, dry_run=False):
    state, state_path = load_os_state(task_id or (receipt.get("task_id") if isinstance(receipt, dict) else None))
    errors = []
    if not state:
        return {"result": "os_close_rejected", "errors": ["no active OS run; call os-start first"]}
    if state.get("status") in {"closed", "sealed"}:
        return {"result": "os_close_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]}
    contract = state.get("contract")
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    active_facts = load_diff_facts({})
    if should_use_v1_target_diff(state):
        target_diff = target_diff_from_active_facts(state, active_facts)
    else:
        target_diff = target_changed_paths(state)
    if not dry_run:
        write_json(os_state_path(state["task_id"], "target-diff.json"), target_diff)
    facts = facts_from_target_diff(target_diff, active_facts)
    enforcement_advisory = cross_project_enforcement_advisory(active_facts, target_diff)
    if enforcement_advisory:
        state["enforcement_advisory"] = enforcement_advisory
    os_evidence = os_evidence_records(state["task_id"])
    errors.extend(validate_deliver_receipt(receipt, contract, facts))
    errors.extend(evidence_router_receipt_errors(contract, receipt, os_evidence))
    errors.extend(validate_target_receipt_coverage(receipt, target_diff))
    required_gates = state.get("required_gates") or required_gates_for_task(contract, receipt, mode=state.get("mode"))
    if isinstance(contract, dict) and contract.get("requires_human_review") and "human_review" not in required_gates:
        required_gates = list(required_gates) + ["human_review"]
    errors.extend(validate_required_quality_gates(receipt, required_gates))
    hr_errors, hr_summary = validate_human_review_gate(state, contract, receipt, os_evidence)
    errors.extend(hr_errors)
    state["human_review"] = hr_summary
    if hr_summary.get("unresolved"):
        state["repair_required"] = True
        state["open_review_findings"] = hr_summary["unresolved"]
        state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["review", "repair"]))
    if isinstance(contract, dict) and contract.get("requires_prototype") and "prototype" not in required_gates:
        required_gates = list(required_gates) + ["prototype"]
        errors.extend(validate_required_quality_gates(receipt, ["prototype"]))
    proto_summary = validate_prototype_gate(state, contract, receipt, os_evidence)
    state["prototype"] = proto_summary
    if proto_summary.get("result") == "FAIL":
        errors.append("prototype gate failed: " + str(proto_summary.get("reason", "prototype evidence incomplete")))
        state["prototype_incomplete"] = proto_summary.get("reason", "")
        state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["prototype", "repair"]))
    missing_evidence = validate_expected_evidence_present(contract, receipt, facts, os_evidence)
    errors.extend(missing_evidence)
    errors.extend(validate_design_token_receipt(receipt, contract, state, os_evidence))
    errors.extend(validate_ui_quality_receipt(receipt, contract, os_evidence))
    errors.extend(validate_truth_claims(receipt, os_evidence, missing_evidence, contract=contract, state=state))
    target_footprint = target_footprint_report(state, target_diff)
    if target_footprint.get("result") != "target_footprint_passed":
        errors.extend(target_footprint.get("errors") or ["target footprint policy failed"])
    janitor = artifact_janitor_result(fix=False, root=REPO_ROOT)
    target_janitor = target_janitor_result(state, fix=False)
    if janitor.get("result") != "artifact_janitor_passed":
        errors.append("artifact janitor found local artifacts; run artifact-janitor --fix only if explicit cleanup is intended")
    target = state.get("target") if isinstance(state, dict) else {}
    if (
        isinstance(target, dict)
        and target.get("target_repo") != str(REPO_ROOT.resolve())
        and target_janitor.get("result") != "artifact_janitor_passed"
    ):
        errors.append("target artifact janitor found local artifacts; run artifact-janitor --target <path> --fix only if explicit cleanup is intended")
    if dry_run:
        result = {
            "result": "os_close_dry_run",
            "task_id": state["task_id"],
            "would_pass": not errors,
            "errors": errors,
            "required_gates": required_gates,
            "janitor": janitor,
            "target_janitor": target_janitor,
            "target_footprint": target_footprint,
        }
        if enforcement_advisory:
            result["enforcement_advisory"] = enforcement_advisory
        return result
    if errors:
        state["status"] = "close_rejected"
        state["last_close_errors"] = errors
        state["last_janitor"] = janitor
        state["last_target_janitor"] = target_janitor
        state["last_target_footprint"] = target_footprint
        state["last_target_diff_sha256"] = target_diff.get("diff_sha256", "")
        save_os_state(state)
        return {
            "result": "os_close_rejected",
            "task_id": state["task_id"],
            "errors": errors,
            "janitor": janitor,
            "target_janitor": target_janitor,
            "target_footprint": target_footprint,
            "target_diff": target_diff,
            "state_path": state_path.relative_to(REPO_ROOT).as_posix() if state_path else "",
            "enforcement_advisory": enforcement_advisory,
        }
    receipt, receipt_path = write_active_receipt(receipt)
    save_diff_facts({}, facts)
    seal = record_receipt_seal(receipt, contract, facts)
    target_seal = build_target_seal(state, receipt, target_diff)
    write_json(os_state_path(state["task_id"], "target-seal.json"), target_seal)
    state["status"] = "closed"
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + [
        "quality gates",
        "receipt",
        "seal",
        "janitor",
    ]))
    state["closed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["receipt_sha256"] = sha256_json(receipt)
    state["seal_sha256"] = seal.get("seal_sha256")
    state["seal"] = seal
    state["target_diff_sha256"] = target_diff.get("diff_sha256", "")
    state["target_seal_sha256"] = target_seal.get("target_seal_sha256", "")
    state["target_seal"] = target_seal
    state["receipt_path"] = receipt_path.as_posix()
    state["janitor"] = janitor
    state["target_janitor"] = target_janitor
    state["target_footprint"] = target_footprint
    state["cost_ledger"] = cost_ledger_summary(os_evidence)
    state["consumer_superiority"] = receipt.get("consumer_superiority", {})
    save_os_state(state)
    control = control_plane_check_result(active_policy="always")
    if control.get("result") != "control_plane_passed":
        state["status"] = "close_rejected"
        state["last_control_plane"] = control
        save_os_state(state)
        return {
            "result": "os_close_rejected",
            "task_id": state["task_id"],
            "errors": ["control-plane-check failed"],
            "control_plane": control,
            "seal_sha256": seal.get("seal_sha256"),
            "target_seal_sha256": target_seal.get("target_seal_sha256"),
            "recorded_to": seal.get("recorded_to"),
        }
    state["status"] = "sealed"
    state["control_plane"] = control
    # Auto-clean rác đĩa (Nhóm A) sau khi seal thành công. Run vừa seal là
    # active + mới nhất nên luôn được retention giữ lại; fail-soft tuyệt đối —
    # lỗi dọn dẹp KHÔNG bao giờ làm hỏng os-close.
    try:
        state["state_janitor"] = state_janitor_result(fix=True)
    except Exception as e:
        state["state_janitor"] = {"result": "state_janitor_error", "reason": str(e)}
    save_os_state(state)
    return {
        "result": "os_closed",
        "task_id": state["task_id"],
        "state_path": os_state_path(state["task_id"]).relative_to(REPO_ROOT).as_posix(),
        "receipt_path": receipt_path.as_posix(),
        "seal_sha256": seal.get("seal_sha256"),
        "target_seal_sha256": target_seal.get("target_seal_sha256"),
        "recorded_to": seal.get("recorded_to"),
        "required_gates": required_gates,
        "mode": state.get("mode", ""),
        "cost_ledger": state.get("cost_ledger", {}),
        "janitor": janitor,
        "target_janitor": target_janitor,
        "target_footprint": target_footprint,
        "target_diff_path": os_state_path(state["task_id"], "target-diff.json").relative_to(REPO_ROOT).as_posix(),
        "target_seal_path": os_state_path(state["task_id"], "target-seal.json").relative_to(REPO_ROOT).as_posix(),
        "control_plane": control.get("result"),
        "state_janitor": state.get("state_janitor"),
        "enforcement_advisory": enforcement_advisory,
    }


def os_close(argv):
    args = list(argv)
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args = [a for a in args if a != "--dry-run"]
    try:
        receipt, _ = json_arg_or_stdin(args, "os-close")
    except Exception as e:
        json_print({"result": "os_close_rejected", "errors": [str(e)]})
        return
    if not isinstance(receipt, dict):
        json_print({"result": "os_close_rejected", "errors": ["receipt must be a JSON object"]})
        return
    json_print(os_close_result(receipt, dry_run=dry_run))


def review_request(argv):
    """Emit the review-request artifact for the active OS run (Review state).

    Accepts an optional task id, or a JSON payload {task_id, questions}.
    """
    payload = {}
    task_id = None
    if argv:
        arg = argv[0].strip()
        if arg.startswith("{"):
            try:
                payload = json.loads(arg)
            except Exception as e:
                json_print({"result": "review_request_rejected", "errors": [str(e)]})
                return
            task_id = payload.get("task_id")
        else:
            task_id = argv[0]
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "review_request_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    task_id = state["task_id"]
    contract = state.get("contract") or {}
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    required_gates = state.get("required_gates") or required_gates_for_task(contract, None, mode=state.get("mode"))
    if isinstance(contract, dict) and contract.get("requires_human_review") and "human_review" not in required_gates:
        required_gates = list(required_gates) + ["human_review"]
    changed = sorted(facts_paths(load_diff_facts({}), None))
    contract_path = os_state_path(task_id, "contract.json")
    body = {
        "schema_version": 1,
        "kind": "review_request",
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "under_review": {
            "contract_path": contract_path.relative_to(REPO_ROOT).as_posix() if contract_path.exists() else "",
            "changed_files": changed,
        },
        "gates": required_gates,
        "questions": payload.get("questions") if isinstance(payload.get("questions"), list) else [],
        "requested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    body["request_sha256"] = sha256_json({
        "task_id": task_id, "under_review": body["under_review"],
        "gates": required_gates, "questions": body["questions"],
    })
    path = os_state_path(task_id, "review-request.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, body)
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["review"]))
    save_os_state(state)
    json_print({
        "result": "review_requested",
        "task_id": task_id,
        "gates": required_gates,
        "review_request_path": path.relative_to(REPO_ROOT).as_posix(),
        "request_sha256": body["request_sha256"],
    })


def review_feedback(argv):
    """Ingest a structured human-review round, record it as evidence, update state."""
    try:
        payload, _ = json_arg_or_stdin(argv, "review-feedback")
    except Exception as e:
        json_print({"result": "review_feedback_rejected", "errors": [str(e)]})
        return
    if not isinstance(payload, dict):
        json_print({"result": "review_feedback_rejected", "errors": ["feedback must be a JSON object"]})
        return
    state, _ = load_os_state(payload.get("task_id"))
    if not state:
        json_print({"result": "review_feedback_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    task_id = state["task_id"]
    errors = validate_review_feedback(payload)
    if errors:
        json_print({"result": "review_feedback_rejected", "task_id": task_id, "errors": errors})
        return
    existing = review_feedback_records(task_id)
    try:
        review_round = int(payload.get("review_round"))
    except (TypeError, ValueError):
        review_round = len(existing) + 1
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = sanitize_state_value({
        "schema_version": 1,
        "kind": "human_review",
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "reviewer": payload.get("reviewer") or "",
        "review_round": review_round,
        "verdict": payload.get("verdict"),
        "finalized": bool(payload.get("finalized")),
        "message": payload.get("message") or "",
        "findings": payload.get("findings") or [],
        "recorded_at": now,
    }, limit=4000)
    append_review_feedback(task_id, record)
    unresolved = [
        finding.get("id")
        for finding in record["findings"]
        if isinstance(finding, dict)
        and finding.get("severity") in REVIEW_BLOCKING_SEVERITIES
        and finding.get("disposition") == "request-changes"
    ]
    append_os_evidence(task_id, {
        "id": f"hr-round-{review_round}",
        "kind": "human_review",
        "review_round": review_round,
        "verdict": record["verdict"],
        "finalized": record["finalized"],
        "unresolved": unresolved,
        "reviewer": record["reviewer"],
        "recorded_at": now,
    })
    lifecycle_add = ["review"] + (["repair"] if unresolved else [])
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + lifecycle_add))
    if unresolved:
        state["repair_required"] = True
        state["open_review_findings"] = unresolved
    save_os_state(state)
    json_print({
        "result": "review_feedback_recorded",
        "task_id": task_id,
        "review_round": review_round,
        "verdict": record["verdict"],
        "finalized": record["finalized"],
        "unresolved": unresolved,
    })


def review_verify(argv):
    """Read-only status of the human_review gate for the active OS run."""
    state, _ = load_os_state(argv[0] if argv else None)
    if not state:
        json_print({"result": "review_verify_failed", "errors": ["no active OS run"]})
        return
    contract = state.get("contract") or {}
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    os_evidence = os_evidence_records(state["task_id"])
    hr_errors, hr_summary = validate_human_review_gate(state, contract, {}, os_evidence)
    json_print({
        "result": "review_verified" if not hr_errors else "review_incomplete",
        "task_id": state["task_id"],
        "human_review": hr_summary,
        "errors": hr_errors,
    })


def os_verify(argv):
    task_id = argv[0] if argv else None
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "os_verify_failed", "errors": ["no OS run state found"]})
        return
    seal = state.get("seal")
    if not isinstance(seal, dict):
        json_print({"result": "os_verify_failed", "task_id": state.get("task_id"), "errors": ["OS run has no recorded seal"]})
        return
    receipt, _ = load_deliver_receipt({})
    if receipt is None:
        json_print({"result": "os_verify_failed", "task_id": state.get("task_id"), "errors": ["missing active deliver receipt"]})
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    current = build_receipt_seal(receipt, contract, facts, seal.get("previous_seal_sha256", ""))
    control_comparisons = {
        "receipt_sha256": current.get("receipt_sha256") == seal.get("receipt_sha256"),
        "contract_sha256": current.get("contract_sha256") == seal.get("contract_sha256"),
        "diff_facts_sha256": current.get("diff_facts_sha256") == seal.get("diff_facts_sha256"),
        "changed_files": current.get("changed_files") == seal.get("changed_files"),
        "seal_sha256": current.get("seal_sha256") == seal.get("seal_sha256"),
    }
    target_expected = state.get("target_seal")
    if not isinstance(target_expected, dict):
        target_expected = load_json_file(os_state_path(state.get("task_id", ""), "target-seal.json"))
    target_comparisons = {}
    current_target_seal = {}
    if isinstance(target_expected, dict):
        if should_use_v1_target_diff(state):
            current_target_diff = target_diff_from_active_facts(state, facts)
        else:
            current_target_diff = target_changed_paths(state)
        current_target_seal = build_target_seal(state, receipt, current_target_diff)
        target_comparisons = {
            "target_metadata": (
                current_target_seal.get("target_repo") == target_expected.get("target_repo")
                and current_target_seal.get("target_id") == target_expected.get("target_id")
                and current_target_seal.get("target_kind") == target_expected.get("target_kind")
            ),
            "changed_paths": current_target_seal.get("changed_paths") == target_expected.get("changed_paths"),
            "deleted_files": current_target_seal.get("deleted_files") == target_expected.get("deleted_files"),
            "changed_files": current_target_seal.get("changed_files") == target_expected.get("changed_files"),
            "target_diff_sha256": current_target_seal.get("target_diff_sha256") == target_expected.get("target_diff_sha256"),
            "target_seal_sha256": current_target_seal.get("target_seal_sha256") == target_expected.get("target_seal_sha256"),
        }
    else:
        target_comparisons = {"target_seal": False}
    control_errors = [name for name, ok in control_comparisons.items() if not ok]
    target_errors = [name for name, ok in target_comparisons.items() if not ok]
    errors = [f"control_plane.{name}" for name in control_errors] + [f"target.{name}" for name in target_errors]
    json_print({
        "result": "os_verify_passed" if not errors else "os_verify_failed",
        "task_id": state.get("task_id"),
        "comparisons": {
            "control_plane": control_comparisons,
            "target": target_comparisons,
        },
        "errors": errors,
        "current_seal_sha256": current.get("seal_sha256"),
        "expected_seal_sha256": seal.get("seal_sha256"),
        "current_target_seal_sha256": current_target_seal.get("target_seal_sha256", ""),
        "expected_target_seal_sha256": target_expected.get("target_seal_sha256", "") if isinstance(target_expected, dict) else "",
    })


def os_report(argv):
    task_id = argv[0] if argv else None
    state, path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_report_missing", "errors": ["no OS run state found"]})
        return
    evidence = os_evidence_records(state.get("task_id"))
    receipt, receipt_path = load_deliver_receipt({})
    target_diff = load_json_file(os_state_path(state.get("task_id", ""), "target-diff.json"))
    target_seal = state.get("target_seal")
    if not isinstance(target_seal, dict):
        target_seal = load_json_file(os_state_path(state.get("task_id", ""), "target-seal.json"))
    target_footprint = state.get("target_footprint")
    if not isinstance(target_footprint, dict) and isinstance(target_diff, dict):
        target_footprint = target_footprint_report(state, target_diff)
    superiority_payloads = consumer_superiority_payloads(receipt or {}, evidence)
    superiority_passed = consumer_superiority_ok(receipt or {}, evidence)
    if superiority_payloads:
        superiority_result = "consumer_value_passed" if superiority_passed else "consumer_value_failed"
    else:
        superiority_result = "not_claimed"
    json_print({
        "result": "os_report",
        "task_id": state.get("task_id"),
        "status": state.get("status"),
        "state_path": path.relative_to(REPO_ROOT).as_posix() if path else "",
        "receipt_path": receipt_path.as_posix() if receipt_path else "",
        "mode": state.get("mode", ""),
        "adaptive_mode": state.get("adaptive_mode", False),
        "mode_decisions": state.get("mode_decisions", []),
        "phase_plan_suggestion": (state.get("contract") or {}).get("phase_plan_suggestion", {}),
        "model_hints": (state.get("contract") or {}).get("model_hints", {}),
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "budget": state.get("budget", {}),
        "success_metrics": state.get("success_metrics", []),
        "cost_ledger": cost_ledger_summary(evidence),
        "budget_status": budget_status(state.get("contract") or {}, evidence),
        "consumer_superiority": {
            "result": superiority_result,
            "payload_count": len(superiority_payloads),
            "policy": "not worse on every mandatory metric, real token telemetry present, and win at least one consumer-visible metric before claiming consumer value",
        },
        "target": state.get("target", {}),
        "target_footprint": target_footprint if isinstance(target_footprint, dict) else {},
        "target_diff": target_diff if isinstance(target_diff, dict) else {},
        "target_seal_sha256": target_seal.get("target_seal_sha256", "") if isinstance(target_seal, dict) else "",
        # Same reason as os-status: the full decision stays in state, and the
        # router limitations it carries are repeated under `limitations` below.
        "evidence_router": evidence_route_digest(state.get("evidence_router", {})),
        "required_gates": state.get("required_gates", []),
        "evidence_count": len(evidence),
        "limitations": [
            "exact LLM token usage is unavailable unless llm_usage metrics record real_token_telemetry=true",
            "artifact token estimates are not LLM cost telemetry",
        ] + (
            state.get("evidence_router", {}).get("limitations", [])
            if isinstance(state.get("evidence_router"), dict)
            else []
        ),
    })
# ---------------------------------------------------------------- misc modes

def statusline():
    overdue = get_overdue_scopes()
    if overdue is None:
        print("PilothOS: khong tim thay registry")
        return
    if overdue:
        scopes = ", ".join(s.split(" (")[0] for s in overdue)
        print(f"\U0001F534 ROT OVERDUE: {scopes} — chạy rot review")
    # Healthy: không in gì.


def consumer_assets_registry_ok():
    if not CONSUMER_ASSETS.exists():
        return False, f"khong tim thay consumer asset registry tai {CONSUMER_ASSETS}"
    text = CONSUMER_ASSETS.read_text(encoding="utf-8", errors="replace")
    header = "Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes"
    if header not in text:
        return False, "consumer asset registry thieu header contract"
    required_terms = [
        "skill", "hook", "tool", "mcp", "command", "design-system",
        "doc", "convention", "test-runner", "build-runner", "agent",
        "specialist",
        "low", "medium", "high",
        "always", "task-routed", "approval-required", "never-auto",
        "preserve", "index", "route", "wrap", "merge", "needs-judgment", "ignore",
    ]
    missing = [term for term in required_terms if term not in text]
    if missing:
        return False, "consumer asset registry thieu contract terms: " + ", ".join(missing)
    tools_index = PILOTHOS_DIR / "tools" / "index.md"
    if not tools_index.exists():
        return False, f"khong tim thay tools index tai {tools_index}"
    tools_text = tools_index.read_text(encoding="utf-8", errors="replace")
    if "pilothOS/runtime/consumer-assets.md" not in tools_text:
        return False, "tools index chua link consumer asset registry"
    if "Tool | Type | Capability | Config | Risk | Health Check | Approval | Timeout | Evidence Output" not in tools_text:
        return False, "tools index thieu tool registry contract"
    return True, "consumer asset registry hop le"


def self_host_required_manifest_paths():
    return {
        "pilothOS/runtime/self-hosting.md",
        "pilothOS/runtime/consumer-assets.md",
        "pilothOS/runtime/os-control-plane.md",
        "pilothOS/runtime/evidence-routing.json",
        "pilothOS/runtime/adapter-capabilities.json",
        "pilothOS/runtime/specialist-registry.json",
        "pilothOS/runtime/model-capabilities.json",
        "pilothOS/runtime/evidence-router-issues.json",
        "pilothOS/scripts/pilothos_guard.py",
        "pilothOS/scripts/pilothos_installer.py",
        "pilothOS/agent-teams/piloth-team.md",
        "pilothOS/memory/state/README.md",
    }


def self_host_check_result():
    checks = []

    def add_check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required_files = [
        SELF_HOSTING_DOC,
        CONSUMER_ASSETS,
        PILOTHOS_DIR / "runtime" / "task-lifecycle.md",
        PILOTHOS_DIR / "runtime" / "energy-token-policy.md",
        PILOTHOS_DIR / "runtime" / "os-control-plane.md",
        PILOTHOS_DIR / "runtime" / "evidence-routing.json",
        PILOTHOS_DIR / "runtime" / "adapter-capabilities.json",
        PILOTHOS_DIR / "runtime" / "specialist-registry.json",
        PILOTHOS_DIR / "runtime" / "model-capabilities.json",
        PILOTHOS_DIR / "agent-teams" / "piloth-team.md",
        PILOTHOS_DIR / "scripts" / "pilothos_guard.py",
    ]
    for path in required_files:
        add_check(
            f"required file {path.relative_to(REPO_ROOT).as_posix()}",
            path.exists(),
            "exists" if path.exists() else "missing",
        )
    test_files = [
        REPO_ROOT / "tests" / "run_all.sh",
        REPO_ROOT / "tests" / "evaluation" / "run-tests.sh",
        REPO_ROOT / "tests" / "install" / "run-tests.sh",
        REPO_ROOT / "tests" / "lifecycle" / "run-tests.sh",
        REPO_ROOT / "tests" / "docs" / "run-tests.sh",
    ]
    if (REPO_ROOT / "tests").exists():
        for path in test_files:
            add_check(
                f"required source test {path.relative_to(REPO_ROOT).as_posix()}",
                path.exists(),
                "exists" if path.exists() else "missing",
            )
    else:
        add_check(
            "source test runners",
            True,
            "tests/ not shipped in staged consumer copy; source repo still requires tests/run_all.sh",
        )

    if SELF_HOSTING_DOC.exists():
        text = read_text_safe(SELF_HOSTING_DOC)
        for needle in ("contract-write", "pre-edit", "post-edit", "receipt-write", "tests/run_all.sh"):
            add_check(
                f"self-hosting doc mentions {needle}",
                needle in text,
                "found" if needle in text else "missing",
            )

    registered_modes = guard_registered_modes()
    for mode in SELF_HOST_REQUIRED_GUARD_MODES:
        add_check(
            f"guard mode {mode}",
            mode in registered_modes,
            "registered" if mode in registered_modes else "missing",
        )

    assets_ok, assets_msg = consumer_assets_registry_ok()
    add_check("consumer asset registry contract", assets_ok, assets_msg)

    manifest = manifest_paths()
    missing_manifest = sorted(self_host_required_manifest_paths() - manifest)
    add_check(
        "dist manifest self-host paths",
        not missing_manifest,
        "all required paths indexed" if not missing_manifest else "missing: " + ", ".join(missing_manifest),
    )

    changed = [
        p for p in git_changed_paths()
        if p.startswith(("pilothOS/", "tests/", "scripts/", "docs/", "adapters/", "templates/", "commands/"))
    ]
    if changed:
        receipt, _ = load_deliver_receipt({})
        facts = load_diff_facts({})
        contract, _ = load_task_contract({})
        receipt_errors = ["missing receipt"] if receipt is None else validate_deliver_receipt(receipt, contract, facts)
        add_check(
            "dogfood receipt for changed Piloth source",
            not receipt_errors,
            "receipt valid for current changed source" if not receipt_errors else "; ".join(receipt_errors),
        )
    else:
        add_check("dogfood receipt for changed Piloth source", True, "no changed Piloth source detected")

    errors = [check["detail"] for check in checks if not check["ok"]]
    return {
        "result": "self_host_check_passed" if not errors else "self_host_check_failed",
        "repo": str(REPO_ROOT),
        "checks": checks,
        "errors": errors,
    }


def self_host_check():
    json_print(self_host_check_result())


def production_scan_paths():
    paths = set(manifest_paths())
    for root in ("pilothOS", "docs", "tests", "scripts", "templates", "adapters", "commands"):
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                rel = path.relative_to(REPO_ROOT).as_posix()
                if "/memory/state/" not in rel and not any(part in SCAN_EXCLUDE_DIRS for part in path_parts(rel)):
                    paths.add(rel)
    return sorted(paths)


def production_noise_findings():
    findings = []
    stale_scan_exts = {".md", ".txt", ".json", ".toml", ".yaml", ".yml"}
    for rel in production_scan_paths():
        path = REPO_ROOT / rel
        if not path.exists() or not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in CODE_EXTENSIONS and suffix not in stale_scan_exts and suffix != "":
            continue
        text = read_text_safe(path, limit=300000)
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern in PRODUCTION_NOISE_PATTERNS:
                if pattern.search(line):
                    findings.append({"path": rel, "line": lineno, "term": pattern.pattern})
        if suffix in stale_scan_exts:
            for term in PRODUCTION_STALE_TERMS:
                if term in text:
                    findings.append({"path": rel, "line": 0, "term": term})
    return findings


def artifact_janitor_findings(root=REPO_ROOT):
    findings = []
    root = pathlib.Path(root).resolve()
    root_len = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = pathlib.Path(current)
        rel_parts = current_path.parts[root_len:]
        dirs.sort()
        files.sort()
        if any(part in ARTIFACT_JANITOR_SKIP_DIRS for part in rel_parts):
            dirs[:] = []
            continue
        pruned = []
        for dirname in list(dirs):
            rel = (current_path / dirname).relative_to(root).as_posix()
            if dirname in ARTIFACT_JANITOR_SKIP_DIRS:
                pruned.append(dirname)
                continue
            if dirname in ARTIFACT_JANITOR_DIR_NAMES:
                findings.append({"path": rel, "kind": "dir", "action": "remove"})
                pruned.append(dirname)
        dirs[:] = [d for d in dirs if d not in pruned]
        for filename in files:
            if filename in ARTIFACT_JANITOR_FILE_NAMES or filename.endswith(ARTIFACT_JANITOR_SUFFIXES):
                rel = (current_path / filename).relative_to(root).as_posix()
                findings.append({"path": rel, "kind": "file", "action": "remove"})
        if len(findings) >= ARTIFACT_JANITOR_MAX_FINDINGS:
            findings.append({
                "path": "",
                "kind": "limit",
                "action": "stop",
                "reason": f"finding limit reached: {ARTIFACT_JANITOR_MAX_FINDINGS}",
            })
            break
    return findings


def artifact_janitor_apply(findings, root=REPO_ROOT):
    actions = []
    root = pathlib.Path(root).resolve()
    for item in findings:
        if item.get("action") != "remove" or not non_empty_string(item.get("path")):
            continue
        rel, err = target_relative_path(item["path"], root)
        if err:
            actions.append({"path": item.get("path"), "status": "skipped", "reason": err})
            continue
        path = root / rel
        try:
            if item.get("kind") == "dir" and path.is_dir():
                shutil.rmtree(path)
                actions.append({"path": rel, "status": "removed"})
            elif item.get("kind") == "file" and path.is_file():
                path.unlink()
                actions.append({"path": rel, "status": "removed"})
            else:
                actions.append({"path": rel, "status": "missing"})
        except OSError as e:
            actions.append({"path": rel, "status": "failed", "reason": str(e)})
    return actions


def artifact_janitor_result(fix=False, root=REPO_ROOT):
    root = pathlib.Path(root).resolve()
    findings = artifact_janitor_findings(root)
    actions = []
    if fix and findings:
        actions = artifact_janitor_apply(findings, root)
        findings = artifact_janitor_findings(root)
    result = "artifact_janitor_passed"
    if findings:
        result = "artifact_janitor_failed"
    elif fix and actions:
        result = "artifact_janitor_cleaned"
    return {
        "result": result,
        "mode": "fix" if fix else "detect",
        "root": str(root),
        "findings_count": len(findings),
        "findings": findings,
        "actions": actions,
        "policy": {
            "default": "read_only_detect",
            "fix": "explicit_remove_known_local_artifacts_only",
        },
    }


def target_janitor_result(state, fix=False):
    target = state.get("target") if isinstance(state, dict) else None
    if not isinstance(target, dict) or not non_empty_string(target.get("target_repo")):
        return {
            "result": "artifact_janitor_skipped",
            "mode": "fix" if fix else "detect",
            "reason": "OS state has no target metadata",
        }
    return artifact_janitor_result(fix=fix, root=target["target_repo"])


def artifact_janitor(argv):
    args = list(argv)
    fix = False
    target = None
    i = 0
    errors = []
    while i < len(args):
        arg = args[i]
        if arg == "--fix":
            fix = True
        elif arg == "--target":
            if i + 1 >= len(args):
                errors.append("--target requires an absolute directory path")
                break
            i += 1
            target = args[i]
        elif arg.startswith("--target="):
            target = arg.split("=", 1)[1]
        else:
            errors.append(f"unsupported argument: {arg}")
        i += 1
    if errors:
        json_print({
            "result": "artifact_janitor_rejected",
            "errors": errors,
        })
        return
    root = REPO_ROOT
    if target:
        candidate = pathlib.Path(target).expanduser()
        if not candidate.is_absolute() or not candidate.exists() or not candidate.is_dir():
            json_print({
                "result": "artifact_janitor_rejected",
                "errors": ["--target must be an existing absolute directory path"],
            })
            return
        root = candidate.resolve()
    json_print(artifact_janitor_result(fix=fix, root=root))
# ---------------------------------------------------------------------------
# State janitor: retention/GC cho rác vòng đời task.
#   Nhóm A (đĩa, gitignored): artifacts/ của os-run đã seal ngoài retention +
#     tail-truncate scheduler-history.jsonl. receipt-seals.jsonl chỉ WARN
#     (hash-chain — không tự sửa để khỏi gãy chuỗi).
#   Nhóm B (token, opt-in --kernel-logs): rotate lossless row cũ của
#     lessons-learned.md / review-log.md sang *-archive.md (không load context).
# Mirror artifact-janitor: detect mặc định, chỉ đổi đĩa khi fix=True.
# ---------------------------------------------------------------------------


def _count_jsonl_lines(path):
    if not path.exists():
        return 0
    count = 0
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    count += 1
    except OSError:
        return 0
    return count


def _artifacts_size_bytes(path):
    total = 0
    for current, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (pathlib.Path(current) / name).stat().st_size
            except OSError:
                continue
    return total


def _md_table_parts(path):
    """Tách file log markdown thành (prefix, rows).

    prefix = mọi thứ tính đến hết dòng separator `|---|` (kèm newline cuối);
    rows = các dòng data-row `| ... |` sau đó. Trả None nếu không có bảng.
    """
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    lines = text.splitlines()
    sep_idx = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and "-" in stripped and set(stripped) <= set("|-: "):
            sep_idx = idx
            break
    if sep_idx is None:
        return None
    prefix = "\n".join(lines[: sep_idx + 1]) + "\n"
    rows = [line.rstrip() for line in lines[sep_idx + 1:] if line.strip().startswith("|")]
    return prefix, rows


def _md_table_rowcount(path):
    parts = _md_table_parts(path)
    return len(parts[1]) if parts else 0


def os_run_retention_plan(keep_runs=None, keep_days=None):
    """Quyết định os-run nào giữ nguyên, os-run nào bị dọn artifacts/.

    Giữ = run active (current.json) + N run gần nhất + mọi run cập nhật trong
    X ngày. Chỉ run ĐÃ SEAL nằm ngoài cửa sổ đó mới đủ điều kiện dọn artifacts/;
    run đang dở (chưa seal) luôn giữ nguyên vẹn.
    """
    keep_runs = STATE_RETENTION_KEEP_RUNS if keep_runs is None else keep_runs
    keep_days = STATE_RETENTION_KEEP_DAYS if keep_days is None else keep_days
    plan = {"keep_runs": keep_runs, "keep_days": keep_days, "runs": []}
    if not OS_RUNS_DIR.exists():
        return plan
    active_task = read_os_current_task_id()
    active_dir = safe_task_id(active_task) if active_task else ""
    cutoff = time.time() - keep_days * 86400
    entries = []
    for state_path in OS_RUNS_DIR.glob("*/state.json"):
        data = load_json_file(state_path)
        if not isinstance(data, dict) or data.get("repo_key") != REPO_KEY:
            continue
        try:
            mtime = state_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        sealed = (
            data.get("status") in {"closed", "sealed"}
            and non_empty_string(data.get("seal_sha256"))
        )
        entries.append({
            "dir": state_path.parent,
            "name": state_path.parent.name,
            "mtime": mtime,
            "updated_at": data.get("updated_at", ""),
            "sealed": sealed,
        })
    entries.sort(key=lambda e: (e["mtime"], e["updated_at"]), reverse=True)
    for idx, entry in enumerate(entries):
        keep = (
            entry["name"] == active_dir
            or idx < keep_runs
            or entry["mtime"] >= cutoff
        )
        prunable = (
            (not keep)
            and entry["sealed"]
            and (entry["dir"] / "artifacts").is_dir()
        )
        plan["runs"].append({
            "name": entry["name"],
            "keep": keep,
            "sealed": entry["sealed"],
            "prune_artifacts": prunable,
        })
    return plan


def state_janitor_findings(keep_runs=None, keep_days=None, kernel_logs=False):
    findings = []
    plan = os_run_retention_plan(keep_runs=keep_runs, keep_days=keep_days)
    for run in plan["runs"]:
        if not run["prune_artifacts"]:
            continue
        artifacts = OS_RUNS_DIR / run["name"] / "artifacts"
        findings.append({
            "path": artifacts.relative_to(REPO_ROOT).as_posix(),
            "kind": "dir",
            "action": "remove",
            "reason": "sealed run outside retention (keeps state/seal JSON)",
            "bytes": _artifacts_size_bytes(artifacts),
        })
    sched_lines = _count_jsonl_lines(SCHEDULER_HISTORY)
    if sched_lines > SCHEDULER_HISTORY_KEEP:
        findings.append({
            "path": SCHEDULER_HISTORY.relative_to(REPO_ROOT).as_posix(),
            "kind": "jsonl-tail",
            "action": "truncate",
            "keep": SCHEDULER_HISTORY_KEEP,
            "lines": sched_lines,
        })
    seal_lines = _count_jsonl_lines(RECEIPT_SEALS)
    if seal_lines > RECEIPT_SEALS_WARN_LINES:
        findings.append({
            "path": RECEIPT_SEALS.relative_to(REPO_ROOT).as_posix(),
            "kind": "warn",
            "action": "none",
            "lines": seal_lines,
            "reason": "hash-chained ledger; archive manually to preserve chain",
        })
    if kernel_logs:
        for live, archive in ((LESSONS, LESSONS_ARCHIVE), (REVIEW_LOG, REVIEW_LOG_ARCHIVE)):
            rows = _md_table_rowcount(live)
            if rows > KERNEL_LOG_KEEP_ROWS:
                findings.append({
                    "path": live.relative_to(REPO_ROOT).as_posix(),
                    "kind": "md-rows",
                    "action": "rotate",
                    "keep": KERNEL_LOG_KEEP_ROWS,
                    "rows": rows,
                    "archive": archive.relative_to(REPO_ROOT).as_posix(),
                })
    if len(findings) > STATE_JANITOR_MAX_FINDINGS:
        findings = findings[:STATE_JANITOR_MAX_FINDINGS]
        findings.append({
            "path": "",
            "kind": "limit",
            "action": "stop",
            "reason": f"finding limit reached: {STATE_JANITOR_MAX_FINDINGS}",
        })
    return findings


def _prune_artifacts_dir(rel_path):
    abs_path = (REPO_ROOT / rel_path).resolve()
    runs_root = OS_RUNS_DIR.resolve()
    # Bất biến an toàn: chỉ bao giờ xoá thư mục tên "artifacts" ngay dưới một
    # os-run — không bao giờ đụng state/seal/receipt JSON hay thư mục run.
    if abs_path.name != "artifacts" or abs_path.parent.parent != runs_root:
        return {"path": rel_path, "status": "skipped", "reason": "not an os-run artifacts dir"}
    if not abs_path.is_dir():
        return {"path": rel_path, "status": "missing"}
    try:
        freed = _artifacts_size_bytes(abs_path)
        shutil.rmtree(abs_path)
        return {"path": rel_path, "status": "removed", "bytes": freed}
    except OSError as e:
        return {"path": rel_path, "status": "failed", "reason": str(e)}


def _truncate_jsonl_tail(path, keep):
    rel = path.relative_to(REPO_ROOT).as_posix()
    if not path.exists():
        return {"path": rel, "status": "missing"}
    try:
        with open(path, encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
    except OSError as e:
        return {"path": rel, "status": "failed", "reason": str(e)}
    if len(lines) <= keep:
        return {"path": rel, "status": "noop", "lines": len(lines)}
    kept = lines[-keep:]
    try:
        with open(path, "w", encoding="utf-8") as f:
            for line in kept:
                f.write(line if line.endswith("\n") else line + "\n")
    except OSError as e:
        return {"path": rel, "status": "failed", "reason": str(e)}
    return {"path": rel, "status": "truncated", "removed": len(lines) - keep, "kept": len(kept)}


def _rotate_md_log(rel_path, item):
    live = REPO_ROOT / rel_path
    archive = REPO_ROOT / item.get("archive", "")
    keep = item.get("keep", KERNEL_LOG_KEEP_ROWS)
    parts = _md_table_parts(live)
    if not parts:
        return {"path": rel_path, "status": "skipped", "reason": "no markdown table"}
    prefix, rows = parts
    if len(rows) <= keep:
        return {"path": rel_path, "status": "noop", "rows": len(rows)}
    moved = rows[:-keep]
    kept = rows[-keep:]
    archive_parts = _md_table_parts(archive)
    if archive_parts:
        archive_prefix, archive_rows = archive_parts
    else:
        archive_prefix, archive_rows = prefix, []
    new_archive_rows = archive_rows + moved
    try:
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_text(archive_prefix + "\n".join(new_archive_rows) + "\n", encoding="utf-8")
        live.write_text(prefix + "\n".join(kept) + "\n", encoding="utf-8")
    except OSError as e:
        return {"path": rel_path, "status": "failed", "reason": str(e)}
    return {
        "path": rel_path,
        "status": "rotated",
        "moved": len(moved),
        "kept": len(kept),
        "archive": item.get("archive"),
    }


def state_janitor_apply(findings):
    actions = []
    for item in findings:
        action = item.get("action")
        if action == "remove" and item.get("kind") == "dir":
            actions.append(_prune_artifacts_dir(item.get("path")))
        elif action == "truncate" and item.get("kind") == "jsonl-tail":
            actions.append(_truncate_jsonl_tail(SCHEDULER_HISTORY, item.get("keep", SCHEDULER_HISTORY_KEEP)))
        elif action == "rotate" and item.get("kind") == "md-rows":
            actions.append(_rotate_md_log(item.get("path"), item))
    return actions


def state_janitor_result(fix=False, keep_runs=None, keep_days=None, kernel_logs=False):
    actionable_kinds = {"remove", "truncate", "rotate"}
    findings = state_janitor_findings(keep_runs=keep_runs, keep_days=keep_days, kernel_logs=kernel_logs)
    actionable = [f for f in findings if f.get("action") in actionable_kinds]
    actions = []
    if fix and actionable:
        actions = state_janitor_apply(findings)
        findings = state_janitor_findings(keep_runs=keep_runs, keep_days=keep_days, kernel_logs=kernel_logs)
    if fix:
        result = "state_janitor_cleaned" if actions else "state_janitor_clean"
    else:
        result = "state_janitor_findings" if actionable else "state_janitor_clean"
    return {
        "result": result,
        "mode": "fix" if fix else "detect",
        "retention": {
            "keep_runs": STATE_RETENTION_KEEP_RUNS if keep_runs is None else keep_runs,
            "keep_days": STATE_RETENTION_KEEP_DAYS if keep_days is None else keep_days,
            "kernel_logs": kernel_logs,
        },
        "findings_count": len([f for f in findings if f.get("kind") != "limit"]),
        "findings": findings,
        "actions": actions,
        "policy": {
            "default": "read_only_detect",
            "artifacts": "remove_only_artifacts_dir_of_sealed_runs_outside_retention",
            "receipt_seals": "warn_only_hash_chain_preserved",
            "kernel_logs": "lossless_rotate_to_archive_opt_in",
        },
    }


def _parse_nonneg_int(value, flag, errors):
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        errors.append(f"{flag} requires a non-negative integer")
        return None
    if n < 0:
        errors.append(f"{flag} requires a non-negative integer")
        return None
    return n


def state_janitor(argv):
    args = list(argv)
    fix = False
    kernel_logs = False
    keep_runs = None
    keep_days = None
    errors = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--fix":
            fix = True
        elif arg == "--kernel-logs":
            kernel_logs = True
        elif arg == "--runs":
            if i + 1 >= len(args):
                errors.append("--runs requires a non-negative integer")
                break
            i += 1
            keep_runs = _parse_nonneg_int(args[i], "--runs", errors)
        elif arg.startswith("--runs="):
            keep_runs = _parse_nonneg_int(arg.split("=", 1)[1], "--runs", errors)
        elif arg == "--days":
            if i + 1 >= len(args):
                errors.append("--days requires a non-negative integer")
                break
            i += 1
            keep_days = _parse_nonneg_int(args[i], "--days", errors)
        elif arg.startswith("--days="):
            keep_days = _parse_nonneg_int(arg.split("=", 1)[1], "--days", errors)
        else:
            errors.append(f"unsupported argument: {arg}")
        i += 1
    if errors:
        json_print({"result": "state_janitor_rejected", "errors": errors})
        return
    json_print(state_janitor_result(
        fix=fix, keep_runs=keep_runs, keep_days=keep_days, kernel_logs=kernel_logs,
    ))


def jsonl_state_doctor(path):
    rel = path.relative_to(REPO_ROOT).as_posix()
    if not path.exists():
        return {"path": rel, "status": "missing", "ok": True, "records": 0, "repo_records": 0}
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as e:
                    return {
                        "path": rel,
                        "status": "corrupt",
                        "ok": False,
                        "line": lineno,
                        "reason": str(e),
                    }
                if not isinstance(item, dict):
                    return {
                        "path": rel,
                        "status": "corrupt",
                        "ok": False,
                        "line": lineno,
                        "reason": "record is not a JSON object",
                    }
                records.append(item)
    except OSError as e:
        return {"path": rel, "status": "failed", "ok": False, "reason": str(e)}
    repo_records = [item for item in records if item.get("repo_key") == REPO_KEY]
    return {
        "path": rel,
        "status": "loaded",
        "ok": True,
        "records": len(records),
        "repo_records": len(repo_records),
        "items": repo_records,
    }


def receipt_seal_chain_status(items):
    previous = ""
    for index, item in enumerate(items):
        seal = item.get("seal_sha256")
        if not non_empty_string(seal):
            return {"ok": False, "index": index, "reason": "missing seal_sha256"}
        declared_previous = item.get("previous_seal_sha256", "")
        if declared_previous != previous:
            return {
                "ok": False,
                "index": index,
                "reason": "previous_seal_sha256 does not match prior repo seal",
            }
        previous = seal
    return {"ok": True, "latest_seal_sha256": previous, "repo_records": len(items)}


def manifest_path_is_runtime_state(rel):
    return (
        (rel.startswith("pilothOS/memory/state/") and rel.endswith(".jsonl"))
        or rel.startswith("pilothOS/memory/state/os-runs/")
        or rel.startswith("pilothOS/memory/state/team-runs/")
        or rel.startswith("pilothOS/memory/state/codebase-index/")
    )


def state_doctor_result():
    checks = []

    def add_check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    scheduler = jsonl_state_doctor(SCHEDULER_HISTORY)
    scheduler_items = scheduler.pop("items", [])
    add_check(
        "scheduler history jsonl",
        scheduler.get("ok"),
        scheduler,
    )
    deprecated = [item for item in scheduler_items if scheduler_history_deprecated(item)]
    add_check(
        "scheduler deprecated history isolation",
        True,
        {"deprecated_repo_records_ignored": len(deprecated)},
    )

    seals = jsonl_state_doctor(RECEIPT_SEALS)
    seal_items = seals.pop("items", [])
    add_check(
        "receipt seals jsonl",
        seals.get("ok"),
        seals,
    )
    chain = receipt_seal_chain_status(seal_items)
    add_check(
        "receipt seal chain",
        seals.get("status") == "missing" or chain.get("ok"),
        chain if seal_items else {"ok": True, "repo_records": 0},
    )
    os_run_checks = []
    if OS_RUNS_DIR.exists():
        for state_path in sorted(OS_RUNS_DIR.glob("*/state.json")):
            rel = state_path.relative_to(REPO_ROOT).as_posix()
            state = load_json_file(state_path)
            if not isinstance(state, dict):
                os_run_checks.append({"path": rel, "ok": False, "reason": "state.json is not a JSON object"})
                continue
            evidence_status = jsonl_state_doctor(state_path.parent / "evidence.jsonl")
            os_run_checks.append({
                "path": rel,
                "ok": evidence_status.get("ok", False) and non_empty_string(state.get("task_id")),
                "task_id": state.get("task_id", ""),
                "status": state.get("status", ""),
                "evidence": {
                    "status": evidence_status.get("status"),
                    "records": evidence_status.get("records"),
                    "ok": evidence_status.get("ok"),
                },
            })
    os_run_errors = [item for item in os_run_checks if not item.get("ok")]
    add_check(
        "OS run state",
        not os_run_errors,
        {
            "runs": len(os_run_checks),
            "errors": os_run_errors,
        },
    )

    manifest = manifest_paths()
    shipped_state = sorted(
        rel for rel in manifest
        if manifest_path_is_runtime_state(rel)
    )
    add_check(
        "repo-local state excluded from manifest",
        not shipped_state,
        "no JSONL state files shipped" if not shipped_state else shipped_state,
    )

    # Advisory hygiene: surface state bloat so người dùng biết khi nào nên chạy
    # `state-janitor` (đặc biệt `--kernel-logs`). Luôn ok=True — không làm fail
    # state-doctor; retention là dọn dẹp tuỳ chọn, không phải điều kiện đúng đắn.
    total_runs = len(os_run_checks)
    janitor = state_janitor_result(fix=False)
    prunable = [f for f in janitor.get("findings", []) if f.get("action") == "remove"]
    reclaimable = sum(int(f.get("bytes", 0) or 0) for f in prunable)
    add_check(
        "state retention advisory",
        True,
        {
            "os_runs": total_runs,
            "keep_runs": janitor.get("retention", {}).get("keep_runs"),
            "keep_days": janitor.get("retention", {}).get("keep_days"),
            "prunable_artifact_dirs": len(prunable),
            "reclaimable_bytes": reclaimable,
            "scheduler_history_lines": _count_jsonl_lines(SCHEDULER_HISTORY),
            "receipt_seals_lines": _count_jsonl_lines(RECEIPT_SEALS),
            "lessons_rows": _md_table_rowcount(LESSONS),
            "review_log_rows": _md_table_rowcount(REVIEW_LOG),
            "hint": "run `state-janitor --fix` (add --kernel-logs to rotate logs)",
        },
    )

    errors = [check for check in checks if not check["ok"]]
    return {
        "result": "state_doctor_passed" if not errors else "state_doctor_failed",
        "checks": checks,
        "errors": errors,
    }


def state_doctor():
    json_print(state_doctor_result())


def guard_registered_modes():
    # Modes come from the dispatch table (the single source of truth for what
    # this guard registers), not from regex-parsing the source — the table is
    # authoritative and can't drift from the actual handlers.
    return set(COMMAND_TABLE)


def control_plane_check_result(active_policy="auto"):
    checks = []

    def add_check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    changed_paths = git_changed_paths()
    changed_file_paths = git_changed_file_paths()
    require_active = active_policy == "always" or (
        active_policy == "auto" and bool(changed_paths or changed_file_paths)
    )
    skip_active = active_policy == "never"

    manifest_data = load_json_file(PILOTHOS_DIR / "dist-manifest.json")
    manifest = manifest_paths()
    missing_manifest = sorted(self_host_required_manifest_paths() - manifest)
    shipped_state = sorted(
        rel for rel in manifest
        if manifest_path_is_runtime_state(rel)
    )
    add_check(
        "manifest",
        bool(manifest_data) and not missing_manifest and not shipped_state,
        {
            "schema_version": manifest_data.get("schema_version") if isinstance(manifest_data, dict) else None,
            "files": len(manifest),
            "missing_required": missing_manifest,
            "shipped_state": shipped_state,
        },
    )

    modes = guard_registered_modes()
    missing_modes = sorted(CONTROL_PLANE_REQUIRED_GUARD_MODES - modes)
    add_check(
        "guard control-plane modes",
        not missing_modes,
        "all required modes registered" if not missing_modes else missing_modes,
    )

    assets_ok, assets_msg = consumer_assets_registry_ok()
    scan_rows = scanned_asset_rows()
    add_check(
        "asset registry",
        assets_ok and bool(scan_rows),
        {
            "registry": assets_msg,
            "detected_assets": len(scan_rows),
        },
    )

    contract, contract_path = load_task_contract({})
    if skip_active:
        add_check("active task contract", True, "skipped by --no-active-task")
    elif contract is None:
        add_check(
            "active task contract",
            not require_active,
            "not required: no active changed checkout" if not require_active else "missing active task contract",
        )
    else:
        contract_errors = validate_task_contract(contract)
        add_check(
            "active task contract",
            not contract_errors,
            {
                "path": contract_path.as_posix() if contract_path else "unknown",
                "errors": contract_errors,
            },
        )

    facts = load_diff_facts({})
    has_evidence = bool(facts.get("changed_files") or facts.get("evidence_commands"))
    add_check(
        "evidence capture",
        skip_active or has_evidence or not require_active,
        {
            "required": require_active and not skip_active,
            "changed_files": sorted(facts.get("changed_files", {})),
            "evidence_commands": len(facts.get("evidence_commands", [])),
        },
    )

    quality_doc = PILOTHOS_DIR / "evaluation" / "quality-gates.md"
    add_check(
        "quality gates",
        quality_doc.exists(),
        "quality gate docs present" if quality_doc.exists() else "missing pilothOS/evaluation/quality-gates.md",
    )

    receipt, receipt_path = load_deliver_receipt({})
    if skip_active:
        add_check("active receipt", True, "skipped by --no-active-task")
        add_check("receipt seal", True, "skipped by --no-active-task")
    elif receipt is None:
        add_check(
            "active receipt",
            not require_active,
            "not required: no active changed checkout" if not require_active else "missing active deliver receipt",
        )
    else:
        receipt_errors = validate_deliver_receipt(receipt, contract, facts)
        quality_gates = receipt.get("quality_gates")
        if require_active and not isinstance(quality_gates, dict):
            receipt_errors.append("quality_gates object is required for active control-plane delivery")
        add_check(
            "active receipt",
            not receipt_errors,
            {
                "path": receipt_path.as_posix() if receipt_path else "unknown",
                "errors": receipt_errors,
            },
        )

        latest_record = latest_receipt_seal_record()
        if latest_record:
            current = build_receipt_seal(
                receipt,
                contract,
                facts,
                latest_record.get("previous_seal_sha256", ""),
            )
            sealed = current.get("seal_sha256") == latest_record.get("seal_sha256")
            file_statuses = [item.get("status") for item in current.get("changed_files", [])]
            sealed_file_statuses = {"sealed", "missing"}
            add_check(
                "receipt seal",
                sealed and all(status in sealed_file_statuses for status in file_statuses),
                {
                    "sealed": sealed,
                    "recorded_to": RECEIPT_SEALS.relative_to(REPO_ROOT).as_posix(),
                    "file_statuses": file_statuses,
                },
            )
        else:
            seal = build_receipt_seal(receipt, contract, facts, "")
            file_statuses = [item.get("status") for item in seal.get("changed_files", [])]
            sealed_file_statuses = {"sealed", "missing"}
            add_check(
                "receipt seal",
                not require_active and all(status in sealed_file_statuses for status in file_statuses),
                {
                    "recorded": False,
                    "buildable": seal.get("result", "buildable"),
                    "file_statuses": file_statuses,
                    "reason": "active delivery requires receipt-seal --record" if require_active else "no active seal record",
            },
        )

    if skip_active:
        add_check("closed OS run", True, "skipped by --no-active-task")
    elif require_active:
        os_state, os_state_file_path = latest_os_state(require_closed=True)
        latest_record = latest_receipt_seal_record()
        os_seal = os_state.get("seal_sha256", "") if isinstance(os_state, dict) else ""
        recorded_seal = latest_record.get("seal_sha256", "") if latest_record else ""
        add_check(
            "closed OS run",
            bool(os_state) and non_empty_string(os_seal) and (not recorded_seal or os_seal == recorded_seal),
            {
                "required": True,
                "state_path": os_state_file_path.relative_to(REPO_ROOT).as_posix() if os_state_file_path else "",
                "status": os_state.get("status") if isinstance(os_state, dict) else "missing",
                "seal_sha256": os_seal,
                "latest_recorded_seal": recorded_seal,
                "reason": "dirty active delivery requires os-close" if not os_state else "",
            },
        )
    else:
        add_check("closed OS run", True, "not required: no active changed checkout")

    if skip_active:
        add_check("git changed file coverage", True, "skipped by --no-active-task")
    elif receipt is None:
        add_check(
            "git changed file coverage",
            not require_active,
            "not required: no active changed checkout" if not require_active else "missing active receipt",
        )
    else:
        fact_files = set(facts.get("changed_files", {}))
        receipt_files = set(
            p for p in (receipt.get("changed_files") or [])
            if isinstance(p, str) and p.strip()
        )
        dirty_files = set(changed_file_paths)
        missing_from_facts = sorted(dirty_files - fact_files)
        missing_from_receipt = sorted(dirty_files - receipt_files)
        add_check(
            "git changed file coverage",
            not missing_from_facts and not missing_from_receipt,
            {
                "dirty_files": sorted(dirty_files),
                "missing_from_facts": missing_from_facts,
                "missing_from_receipt": missing_from_receipt,
            },
        )

    janitor = artifact_janitor_result(fix=False)
    add_check(
        "artifact janitor",
        janitor.get("result") == "artifact_janitor_passed",
        janitor,
    )

    state = state_doctor_result()
    add_check(
        "state doctor",
        state.get("result") == "state_doctor_passed",
        state.get("result", "unknown"),
    )

    errors = [check for check in checks if not check["ok"]]
    return {
        "result": "control_plane_passed" if not errors else "control_plane_failed",
        "active_policy": active_policy,
        "active_required": require_active,
        "changed_paths": changed_paths,
        "changed_file_paths": changed_file_paths,
        "checks": checks,
        "errors": errors,
    }


def control_plane_check(argv):
    args = set(argv)
    if args - {"--active-task", "--no-active-task"}:
        json_print({
            "result": "control_plane_rejected",
            "errors": ["supported arguments: --active-task, --no-active-task"],
        })
        return
    if "--active-task" in args and "--no-active-task" in args:
        json_print({
            "result": "control_plane_rejected",
            "errors": ["--active-task and --no-active-task conflict"],
        })
        return
    active_policy = "auto"
    if "--active-task" in args:
        active_policy = "always"
    elif "--no-active-task" in args:
        active_policy = "never"
    json_print(control_plane_check_result(active_policy=active_policy))


def production_review_result():
    checks = []

    def add_check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    self_host = self_host_check_result()
    add_check(
        "self-host-check",
        self_host.get("result") == "self_host_check_passed",
        self_host.get("result", "unknown"),
    )

    manifest = manifest_paths()
    forbidden_existing = sorted(rel for rel in PRODUCTION_FORBIDDEN_PATHS if (REPO_ROOT / rel).exists())
    forbidden_manifest = sorted(PRODUCTION_FORBIDDEN_PATHS & manifest)
    add_check(
        "removed deprecated host-level artifacts",
        not forbidden_existing and not forbidden_manifest,
        "absent from filesystem and manifest"
        if not forbidden_existing and not forbidden_manifest
        else "existing: " + ", ".join(forbidden_existing) + "; manifest: " + ", ".join(forbidden_manifest),
    )

    health_rows = [health_for_asset(row) for row in scanned_asset_rows()]
    unhealthy = [
        {"id": row.get("id"), "status": row.get("status"), "reason": row.get("health_reason", "")}
        for row in health_rows
        if row.get("status") not in {"healthy", "not_applicable"}
    ]
    add_check(
        "consumer asset health",
        not unhealthy,
        "all detected assets healthy" if not unhealthy else unhealthy,
    )

    missing_manifest = sorted(self_host_required_manifest_paths() - manifest)
    add_check(
        "required manifest entries",
        not missing_manifest,
        "all required paths indexed" if not missing_manifest else missing_manifest,
    )

    noise = production_noise_findings()
    add_check(
        "production noise scan",
        not noise,
        "no release-noise markers or stale host terms in shipped release paths" if not noise else noise[:20],
    )

    state = state_doctor_result()
    add_check(
        "state-doctor",
        state.get("result") == "state_doctor_passed",
        state.get("result", "unknown"),
    )

    janitor = artifact_janitor_result(fix=False)
    add_check(
        "artifact janitor",
        janitor.get("result") == "artifact_janitor_passed",
        janitor,
    )

    control_plane = control_plane_check_result(active_policy="never")
    add_check(
        "control-plane infrastructure",
        control_plane.get("result") == "control_plane_passed",
        control_plane.get("result", "unknown"),
    )

    errors = [check for check in checks if not check["ok"]]
    return {
        "result": "production_review_passed" if not errors else "production_review_failed",
        "checks": checks,
        "errors": errors,
    }


def production_review():
    json_print(production_review_result())


def self_check():
    ok = True
    if SETTINGS.exists():
        try:
            json.load(open(SETTINGS, encoding="utf-8"))
            print(f"OK   settings.json hop le: {SETTINGS}")
        except json.JSONDecodeError as e:
            ok = False
            print(f"FAIL settings.json KHONG HOP LE: {e}")
            print("     Toan bo hooks dang bi vo hieu hoa im lang cho den khi sua xong.")
    else:
        ok = False
        print(f"FAIL khong tim thay settings.json tai {SETTINGS}")

    overdue = get_overdue_scopes()
    if overdue is None:
        ok = False
        print(f"FAIL khong tim thay registry tai {REGISTRY}")
    else:
        print(f"OK   registry parse duoc: {len(overdue)} scope qua han"
              + (f" -> {', '.join(overdue)}" if overdue else ""))

    assets_ok, assets_msg = consumer_assets_registry_ok()
    if assets_ok:
        print(f"OK   {assets_msg}: {CONSUMER_ASSETS}")
    else:
        ok = False
        print(f"FAIL {assets_msg}")

    for log, name in ((REVIEW_LOG, "review-log.md"), (LESSONS, "lessons-learned.md")):
        if log.exists():
            print(f"OK   {name} ton tai (auto-log gate hoat dong)")
        else:
            ok = False
            print(f"FAIL khong tim thay {name} — auto-log gate se khong chinh xac")
    print("SELF-CHECK " + ("PASSED" if ok else "FAILED"))


# mode -> handler. The ONLY thing this table adds to GUARD_MODES (00_header) is
# the function binding, which has to live here because the handlers are defined
# above. Everything else about a mode — arg kind, mutability, self-host and
# control-plane membership — comes from the registry, so a mode can never be
# registered in one place and forgotten in another.
GUARD_HANDLERS = {
    "session-start": session_start,
    "prompt-check": prompt_check,
    "stop-check": stop_check,
    "pre-edit": pre_edit,
    "post-edit": post_edit,
    "contract-write": task_contract_write,
    "evidence-add": evidence_add,
    "tool-check": tool_check,
    "receipt-write": receipt_write,
    "os-start": os_start,
    "os-status": os_status,
    "os-evidence": os_evidence,
    "token-telemetry": token_telemetry,
    "os-close": os_close,
    "os-verify": os_verify,
    "os-report": os_report,
    "review-request": review_request,
    "review-feedback": review_feedback,
    "review-verify": review_verify,
    "asset-scan": asset_scan,
    "asset-health": asset_health,
    "asset-sync": asset_sync,
    "adapter-capabilities": adapter_capabilities,
    "evidence-route": evidence_route,
    "route-task": route_task,
    "context-budget": context_budget,
    "payload-budget": payload_budget,
    "codebase-index": codebase_index,
    "codebase-status": codebase_status,
    "codebase-query": codebase_query,
    "rot-status": rot_status,
    "reuse-scan": reuse_scan,
    "ds-scan": ds_scan,
    "scheduler-suggest": scheduler_suggest,
    "scheduler-record": scheduler_record,
    "receipt-seal": receipt_seal,
    "receipt-verify": receipt_verify,
    "artifact-janitor": artifact_janitor,
    "state-janitor": state_janitor,
    "control-plane-check": control_plane_check,
    "team-contract-write": team_contract_write,
    "team-receipt-write": team_receipt_write,
    "log-append": log_append,
    "receipt-template": receipt_template,
    "statusline": statusline,
    "self-check": self_check,
    "self-host-check": self_host_check,
    "preflight": preflight,
    "detect": detect,
    "audit-assets": audit_consumer_assets,
    "registry-assets": registry_consumer_assets,
    "state-doctor": state_doctor,
    "production-review": production_review,
}
# Command dispatch: mode -> (handler, arg_kind), derived from the registry.
# arg_kind selects how the handler is invoked:
#   "hook" -> handler(read_hook_input())   (only these modes read stdin)
#   "argv" -> handler(sys.argv[2:])
#   "none" -> handler()
# A mode present in exactly one of GUARD_MODES/GUARD_HANDLERS is a build error,
# not a silently missing command (pinned by tests/unit/test_guard_command_table).
COMMAND_TABLE = {
    mode: (GUARD_HANDLERS[mode], meta["arg_kind"])
    for mode, meta in GUARD_MODES.items()
    if mode in GUARD_HANDLERS
}


def main():
    # An unregistered mode must fail LOUDLY. This guard is wired into
    # settings.json as six entry points (five hooks + statusline); when a typo
    # exited 0 the harness read it as success and governance silently vanished.
    # Exit 1, not 2: for hook events only exit 2 blocks the action, so 1 surfaces
    # a `hook error` notice without blocking the user over a config typo. Every
    # REGISTERED mode must keep exiting 0 — Claude Code only parses hook JSON
    # (the block_decision payload) on exit 0.
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    entry = COMMAND_TABLE.get(mode)
    if entry is None:
        label = f"unknown mode {mode!r}" if mode else "missing mode argument"
        print(f"PilothOS guard: {label}", file=sys.stderr)
        print("  usage: python3 pilothos_guard.py <mode> [args]", file=sys.stderr)
        print("  modes: " + ", ".join(sorted(COMMAND_TABLE)), file=sys.stderr)
        sys.exit(1)
    handler, kind = entry
    if kind == "hook":
        handler(read_hook_input())
    elif kind == "argv":
        handler(sys.argv[2:])
    else:
        handler()
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
