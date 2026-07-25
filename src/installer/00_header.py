#!/usr/bin/env python3
"""PilothOS Installer Engine — plan/apply deterministic executor.

Vai trò: Claude (hoặc người dùng) soạn install-plan.json; engine này validate,
backup, thực thi ĐÚNG plan — không hơn một byte — rồi trả RECEIPT.
Thứ được approve = file plan = thứ được thực thi.

Cách dùng:
  python3 pilothos_installer.py validate <plan.json>
  python3 pilothos_installer.py dry-run  <plan.json>
  python3 pilothos_installer.py apply    <plan.json>
  python3 pilothos_installer.py unattended --mode greenfield --persona ... --goals ... --owner ...
  python3 pilothos_installer.py uninstall [--confirm]
  python3 pilothos_installer.py explain

Exit codes: 0 OK · 2 plan không hợp lệ (0 ghi) · 3 apply lỗi, ĐÃ rollback ·
4 NEEDS-JUDGMENT (0 ghi; in JSON liệt kê đúng mục cần quyết định) · 5 uninstall lỗi.

Thiết kế:
- Hai pha: SIMULATE (tính toàn bộ kết quả trong bộ nhớ, bắt mọi lỗi và
  NEEDS-JUDGMENT trước khi chạm đĩa) → COMMIT (backup → manifest → ghi → verify).
- Fail-closed: op lạ, field lạ, path tuyệt đối/traversal, target cấm → từ chối
  toàn bộ plan.
- SSOT merge semantics nằm TẠI ĐÂY (xem `explain`); tài liệu chỉ trỏ về.
"""
# GENERATED FILE — assembled from src/installer/*.py by scripts/build_bundles.py.
# Edit the fragments and rebuild; hand-edits here are overwritten and caught by
# the bundle-up-to-date gate in tests/unit.
import sys
import os
import re
import json
import shutil
import datetime
import subprocess
import pathlib
import argparse

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PILOTHOS_DIR = SCRIPT_DIR.parent
REPO_ROOT = PILOTHOS_DIR.parent
PAYLOAD_DIR = PILOTHOS_DIR / "skills" / "workflow" / "pilothos-init" / "payloads"
BACKUP_ROOT = PILOTHOS_DIR / ".backup"
MARKER = PILOTHOS_DIR / ".initialized"
GUARD = SCRIPT_DIR / "pilothos_guard.py"

OPS = {"create_from_payload", "prepend_block", "append_lines",
       "merge_settings", "write_marker", "remove_path", "fill_placeholders"}
FILL_PILOTHOS_ALLOWED = {"pilothOS/rot/registry.md"}
REMOVE_ALLOWLIST = (".cursor", ".codex", ".antigravity")
# Self-prune: installer tự dọn mặt tiền install sau khi cài (mặc định).
# CHỈ các path chính xác dưới đây — payloads/ và manifest-spec.md KHÔNG BAO GIỜ
# xóa được (uninstall và engine cần chúng).
SELF_PRUNE_ORDER = [
    ".claude/commands/pilothos-init.md",
    ".claude/skills/pilothos-init",
    "pilothOS/skills/workflow/pilothos-init/SKILL.md",
    "pilothOS/skills/workflow/pilothos-init/greenfield.md",
    "pilothOS/skills/workflow/pilothos-init/brownfield.md",
]
SELF_PRUNE_ALLOWED = set(SELF_PRUNE_ORDER)
OPTIONAL_ADAPTER_PATHS = {
    "cursor": ".cursor",
    "codex": ".codex",
    "antigravity": ".antigravity",
}
ALLOWED_ADAPTERS = {"claude", "cursor", "codex", "antigravity"}
# SSOT .gitignore của PilothOS. Consumer mặc định coi pilothOS/ là tooling cục
# bộ và ignore toàn cây. `runtime` được giữ như compatibility opt-in cho team
# muốn commit kernel nhưng bỏ qua state phát sinh.
PILOTHOS_GITIGNORE_RUNTIME_LINES = [
    "pilothOS/.backup/",
    "pilothOS/.pending-plan.json",
    "pilothOS/memory/state/scheduler-history.jsonl",
    "pilothOS/memory/state/receipt-seals.jsonl",
    "pilothOS/memory/state/*.jsonl",
    "pilothOS/memory/state/team-runs/",
    "pilothOS/memory/state/os-runs/",
    "pilothOS/memory/state/codebase-index/",
]
PILOTHOS_GITIGNORE_ALL = ["pilothOS/"]
PILOTHOS_GITIGNORE_LINES = PILOTHOS_GITIGNORE_ALL
GITIGNORE_SCOPES = ("runtime", "all")
DEFAULT_GITIGNORE_SCOPE = "all"
PLAN_TOP_FIELDS = {"plan_version", "mode", "fill", "options", "steps", "adapters"}
STEP_FIELDS = {"op", "payload", "target", "lines"}
OPTION_FIELDS = {"statusline", "gitignore_scope"}

MERGE_SEMANTICS = """MERGE SEMANTICS (SSOT — tài liệu chỉ trỏ về đây):
- hooks: với mỗi event, entries của consumer đứng TRƯỚC, của PilothOS đứng SAU;
  trùng event+matcher nhưng khác command → GIỮ CẢ HAI (đều chạy);
  trùng tuyệt đối (object giống hệt) → giữ một.
- permissions.allow / deny: union, giữ thứ tự consumer trước; một mục vừa nằm
  allow bên này vừa deny bên kia → DENY THẮNG (mục bị loại khỏi allow, ghi notes).
- env: trùng key cùng giá trị → OK; trùng key khác giá trị → NEEDS-JUDGMENT.
- statusLine: consumer chưa có → dùng PilothOS. Consumer đã có → plan phải khai
  options.statusline = consumer | pilothos | chain; thiếu → NEEDS-JUDGMENT.
  chain = gộp output hai lệnh, phần PilothOS rỗng khi healthy.
OPS (bộ từ vựng đóng — ngoài bộ này là việc của judgment, không vào plan):
- create_from_payload{payload,target}: tạo file mới từ payload; target đã tồn tại → reject.
- prepend_block{payload,target}: chèn payload lên đầu file đã tồn tại.
- append_lines{target,lines[]}: nối các dòng ngắn vào cuối (tạo file nếu chưa có).
- merge_settings{payload,target?}: merge settings.json theo semantics trên.
- write_marker{}: ghi pilothOS/.initialized (chỉ engine được ghi vào pilothOS/).
- fill_placeholders{target}: điền PERSONA/GOALS/OWNER/<init>=hôm nay vào file đã\n  staging (CLAUDE.md, registry — registry tự tính Next Due theo cadence từng dòng).\n- remove_path{target}: xóa có backup; CHỈ cho phép dưới: %s,
  hoặc self-prune whitelist (mặt tiền installer: command init + docs nhánh —
  payloads/ và manifest-spec.md không bao giờ xóa được). Uninstall phục hồi tất cả.
""" % ", ".join(REMOVE_ALLOWLIST)


class PlanError(Exception):
    pass


class NeedsJudgment(Exception):
    def __init__(self, items):
        self.items = items
        super().__init__("NEEDS-JUDGMENT")


def fail(code, payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(code)


def safe_rel(path_str):
    """Path phải relative, không traversal, resolve nằm trong repo."""
    if not path_str or path_str.startswith("/") or path_str.startswith("~"):
        raise PlanError(f"path phai la relative: {path_str}")
    p = pathlib.PurePosixPath(path_str)
    if ".." in p.parts:
        raise PlanError(f"path traversal bi cam: {path_str}")
    resolved = (REPO_ROOT / path_str).resolve()
    if REPO_ROOT.resolve() not in resolved.parents and resolved != REPO_ROOT.resolve():
        raise PlanError(f"path thoat khoi repo: {path_str}")
    return path_str


def check_target_writable_zone(path_str, op):
    inside_pilothos = path_str == "pilothOS" or path_str.startswith("pilothOS/")
    if op == "write_marker":
        return
    if op == "fill_placeholders":
        if path_str in FILL_PILOTHOS_ALLOWED or not inside_pilothos:
            return
        raise PlanError(
            f"fill_placeholders trong pilothOS/ chi cho phep: {FILL_PILOTHOS_ALLOWED}")
    if op == "remove_path":
        if path_str in SELF_PRUNE_ALLOWED:
            return
        if path_str.startswith(REMOVE_ALLOWLIST):
            return
        raise PlanError(
            f"remove_path chi cho phep duoi {REMOVE_ALLOWLIST} "
            f"hoac self-prune whitelist: {path_str}")
    if inside_pilothos:
        raise PlanError(
            f"target trong pilothOS/ bi cam voi op {op}: {path_str} "
            "(core khong duoc plan sua; marker dung write_marker)")


def _fill_persona_goals(text, fill):
    """PERSONA + GOALS placeholder substitution shared by payload baking
    (load_payload) and generic placeholder filling (fill_text)."""
    if fill.get("PERSONA"):
        text = re.sub(r"<PERSONA[^>]*>", fill["PERSONA"], text)
    if fill.get("GOALS"):
        text = re.sub(r"<MỤC TIÊU[^>]*>", fill["GOALS"], text)
    return text


def load_payload(name, fill):
    p = (PAYLOAD_DIR / name)
    if not p.resolve().parent == PAYLOAD_DIR.resolve():
        raise PlanError(f"payload phai nam truc tiep trong payloads/: {name}")
    if not p.exists():
        raise PlanError(f"payload khong ton tai: {name}")
    return _fill_persona_goals(p.read_text(encoding="utf-8"), fill)


