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
  self-host-check Verifies the Piloth repo dogfood contract surface.
  asset-scan      Deterministic JSON/markdown scan of repo assets.
  asset-health    Read-only health checks for detected assets.
  asset-sync      Writes generated asset registry section between markers.
  evidence-route  Canonical read-only task/risk/evidence/specialist route.
                 Prints the acting digest; `--verbose` prints the full decision.
  adapter-capabilities Normalize native|emulated|unavailable adapter handshake.
  state-doctor   Read-only health check for repo-local OS state.
  os-start       Open an adaptive OS task run and write the scoped contract.
                 `os-start --explain` prints the request schema (no run opened).
  os-status      Show active OS task status, mode and cost ledger.
                 `os-status --verbose` prints the full router decision too.
  os-evidence    Append sanitized command/tool/metric evidence to an OS run.
  os-close       Validate receipt, gates, truth claims and target seal.
                 `os-close --dry-run` runs the full validation without sealing.
  os-verify      Verify active receipt/control-plane/target seals.
  receipt-seal   Emit deterministic receipt/contract/file hash seal evidence.
  receipt-verify Verify current receipt/files against a prior seal.
  artifact-janitor Detect or explicitly clean deterministic local artifacts.
  state-janitor  Retention/GC rác vòng đời task: dọn artifacts/ của os-run cũ đã
                 seal (giữ state/seal JSON); --kernel-logs rotate lossless
                 lessons/review-log. Detect mặc định, chỉ đổi đĩa khi --fix.
                 Tự chạy (safe subset) ở os-close.
  control-plane-check Verify project-local OS control-plane readiness.
  production-review Mechanical release readiness review.
  log-append      Ghi một dòng log đúng format (review|lesson), Date tự điền,
                  verify Evidence path tồn tại — dùng cho Stage 5 và mọi lần ghi log.
  contract-write  Ghi task contract vào state guard trước khi sửa file.
  evidence-add    Ghi evidence command/result vào diff facts (đường V1, không cần OS run).
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
}
ADAPTER_CAPABILITY_REGISTRY = PILOTHOS_DIR / "runtime" / "adapter-capabilities.json"
SPECIALIST_REGISTRY = PILOTHOS_DIR / "runtime" / "specialist-registry.json"
MODEL_CAPABILITY_REGISTRY = PILOTHOS_DIR / "runtime" / "model-capabilities.json"
RECEIPT_SEALS = PILOTHOS_DIR / "memory" / "state" / "receipt-seals.jsonl"
OS_RUNS_DIR = PILOTHOS_DIR / "memory" / "state" / "os-runs"
OS_CURRENT = OS_RUNS_DIR / "current.json"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
REVIEW_LOG = PILOTHOS_DIR / "rot" / "review-log.md"
LESSONS = PILOTHOS_DIR / "memory" / "lessons-learned.md"
# The two files the Stop-hook auto-log gate accepts. One constant so the gate
# that DEMANDS a write and the guard that could BLOCK it can never disagree:
# pre-edit used to classify review-log.md as pilothOS core (via rot/ -> Docs)
# while letting lessons-learned.md through, so the target bootstrap.md names
# first was the one an agent could not write (thangnd96/piloth#11).
AUTO_LOG_TARGETS = (REVIEW_LOG, LESSONS)
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
    "asset-scan": _guard_mode("argv", self_host=True, control_plane=True),
    "asset-health": _guard_mode("argv", self_host=True, control_plane=True),
    "asset-sync": _guard_mode("argv", mutates=True, self_host=True),
    "adapter-capabilities": _guard_mode("argv", self_host=True, control_plane=True),
    "evidence-route": _guard_mode("argv", self_host=True, control_plane=True),
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
    "log-append": _guard_mode("argv", mutates=True),
    # no-arg modes
    "receipt-template": _guard_mode("none"),
    "statusline": _guard_mode("none"),
    "self-check": _guard_mode("none"),
    "self-host-check": _guard_mode("none", self_host=True),
    "preflight": _guard_mode("none"),
    "detect": _guard_mode("none"),
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
# Two modes, two behaviours. `lean` and `micro` were removed after 32 dogfood
# runs used neither (25 standard, 7 strict) and `strict` measured byte-identical
# to `standard` for context loading — four names for three behaviours, two of
# which no task had ever selected. Modes are explicit now: there is no adaptive
# resolver to guess one.
OS_MODES = {"standard", "strict"}
OS_MODE_REQUESTS = OS_MODES
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
        "context_layers": ("knowledge/index.md", "runtime/context-loading.md"),
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
