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
# SSOT các dòng .gitignore của PilothOS. `runtime` = chỉ ignore runtime state
# (kernel pilothOS/ vẫn commit để team share); `all` = ignore toàn bộ pilothOS/
# (opt-in cho consumer coi PilothOS là tooling cục bộ). Đồng bộ với
# templates/gitignore (tests/docs D4 canh).
PILOTHOS_GITIGNORE_LINES = [
    "pilothOS/.backup/",
    "pilothOS/.pending-plan.json",
    "pilothOS/memory/state/scheduler-history.jsonl",
    "pilothOS/memory/state/receipt-seals.jsonl",
    "pilothOS/memory/state/*.jsonl",
    "pilothOS/memory/state/team-runs/",
    "pilothOS/memory/state/os-runs/",
]
PILOTHOS_GITIGNORE_ALL = ["pilothOS/"]
GITIGNORE_SCOPES = ("runtime", "all")
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


# ------------------------------------------------------------ placeholders

CADENCE_RE = re.compile(r"(\d+)\s*[–-]\s*(\d+)?\s*(tuần|tháng)")


def fill_text(text, fill, is_registry):
    today = datetime.date.today()
    text = _fill_persona_goals(text, fill)
    if fill.get("OWNER"):
        text = text.replace("<owner>", fill["OWNER"])
    if is_registry:
        out = []
        for line in text.splitlines():
            if "| <init> | <init> |" in line:
                m = CADENCE_RE.search(line)
                if m:
                    lo = int(m.group(1))
                    hi = int(m.group(2)) if m.group(2) else lo
                    unit = 7 if m.group(3) == "tuần" else 30
                    days = int((lo + hi) / 2 * unit)
                else:
                    days = 30
                nxt = (today + datetime.timedelta(days=days)).isoformat()
                line = line.replace("| <init> | <init> |",
                                    f"| {today.isoformat()} | {nxt} |")
            line = line.replace("<init>", today.isoformat())
            out.append(line)
        text = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    else:
        text = text.replace("<init>", today.isoformat())
    return text


# ------------------------------------------------------------- settings merge

def merge_settings_content(consumer, payload, options, notes):
    out = json.loads(json.dumps(consumer))
    judg = []
    # permissions
    cp = out.setdefault("permissions", {})
    pp = payload.get("permissions", {})
    for key in ("allow", "deny"):
        merged = list(cp.get(key, []))
        for item in pp.get(key, []):
            if item not in merged:
                merged.append(item)
        cp[key] = merged
    deny = set(cp.get("deny", []))
    kept_allow = []
    for item in cp.get("allow", []):
        if item in deny:
            notes.append(f"deny-thang: '{item}' bi loai khoi allow")
        else:
            kept_allow.append(item)
    cp["allow"] = kept_allow
    # env
    ce = out.setdefault("env", {})
    for k, v in payload.get("env", {}).items():
        if k in ce and ce[k] != v:
            judg.append({"type": "env_conflict", "key": k,
                         "consumer": ce[k], "pilothos": v})
        else:
            ce[k] = v
    # statusLine
    psl = payload.get("statusLine")
    if psl:
        csl = out.get("statusLine")
        if not csl:
            out["statusLine"] = psl
        elif json.dumps(csl, sort_keys=True) == json.dumps(psl, sort_keys=True):
            pass  # giong het -> khong phai conflict (dedupe principle)
        else:
            choice = (options or {}).get("statusline")
            if choice == "consumer":
                notes.append("statusLine: giu cua consumer (mat chi bao rot)")
            elif choice == "pilothos":
                out["statusLine"] = psl
            elif choice == "chain":
                a = csl.get("command", "")
                b = psl.get("command", "")
                out["statusLine"] = {
                    "type": "command",
                    "command": ("bash -c 'a=$(%s); b=$(%s); "
                                "echo \"$a${b:+ | }$b\"'" % (a, b)),
                }
            else:
                judg.append({"type": "statusline_conflict",
                             "hint": "khai options.statusline = consumer|pilothos|chain"})
    # hooks: consumer TRUOC, pilothos SAU; dedupe object giong het
    ch = out.setdefault("hooks", {})
    for event, entries in payload.get("hooks", {}).items():
        existing = ch.setdefault(event, [])
        for entry in entries:
            if not any(json.dumps(e, sort_keys=True) == json.dumps(entry, sort_keys=True)
                       for e in existing):
                existing.append(entry)
    if judg:
        raise NeedsJudgment(judg)
    return out


# ------------------------------------------------------------------ simulate

def validate_and_simulate(plan):
    """Trả về (actions, notes). actions: list {target, kind, content|None}.
    kind: create | modify | remove. KHÔNG chạm đĩa."""
    if not isinstance(plan, dict):
        raise PlanError("plan phai la JSON object")
    extra = set(plan) - PLAN_TOP_FIELDS
    if extra:
        raise PlanError(f"field la trong plan: {sorted(extra)}")
    if plan.get("plan_version") != 1:
        raise PlanError("plan_version phai la 1")
    if plan.get("mode") not in ("greenfield", "brownfield", "upgrade"):
        raise PlanError("mode phai la greenfield|brownfield|upgrade")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PlanError("steps phai la list khong rong")
    options = plan.get("options") or {}
    if set(options) - OPTION_FIELDS:
        raise PlanError(f"option la: {sorted(set(options) - OPTION_FIELDS)}")
    if "gitignore_scope" in options and options["gitignore_scope"] not in GITIGNORE_SCOPES:
        raise PlanError(f"options.gitignore_scope phai la {GITIGNORE_SCOPES}")
    if "adapters" in plan:
        if "claude" not in adapter_set(plan.get("adapters")):
            raise PlanError("'adapters' phai gom 'claude' (khong the go adapter claude)")
    elif plan.get("mode") in ("greenfield", "brownfield"):
        # Bắt buộc khai báo selection KHI có optional adapter đã staging — đúng
        # bối cảnh init thật (staging luôn copy đủ .cursor/.codex/.antigravity).
        # Plan engine tối giản (không staging adapter) không bị ràng buộc.
        staged = sorted(t for t in OPTIONAL_ADAPTER_PATHS.values()
                        if (REPO_ROOT / t).exists())
        if staged:
            raise PlanError(
                "co optional adapter da staging (%s) nhung plan khong khai bao "
                "'adapters' — khai bao list adapter giu lai (gom 'claude') de engine "
                "sinh remove_path cho adapter khong chon" % ", ".join(staged))
    fill = plan.get("fill") or {}
    if MARKER.exists() and plan.get("mode") != "upgrade":
        raise PlanError("pilothOS/.initialized da ton tai — re-init/upgrade can mode=upgrade")
    if plan.get("mode") == "upgrade" and not MARKER.exists():
        raise PlanError("mode=upgrade can pilothOS/.initialized ton tai")

    notes, actions = [], []
    virtual = {}  # target -> content sau simulate (de bat create-trung)

    def existing_content(target):
        if target in virtual:
            return virtual[target]
        p = REPO_ROOT / target
        return p.read_text(encoding="utf-8") if p.exists() and p.is_file() else None

    marker_seen = False
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise PlanError(f"step {i} phai la object")
        extra = set(step) - STEP_FIELDS
        if extra:
            raise PlanError(f"step {i}: field la {sorted(extra)}")
        op = step.get("op")
        if op not in OPS:
            raise PlanError(f"step {i}: op khong ho tro: {op}")
        if op == "write_marker":
            marker_seen = True
            continue
        target = safe_rel(step.get("target", ""))
        check_target_writable_zone(target, op)
        tpath = REPO_ROOT / target

        if op == "create_from_payload":
            if tpath.exists() or target in virtual:
                raise PlanError(f"step {i}: target da ton tai: {target}")
            content = load_payload(step.get("payload", ""), fill)
            virtual[target] = content
            actions.append({"target": target, "kind": "create", "content": content})
        elif op == "prepend_block":
            cur = existing_content(target)
            if cur is None:
                raise PlanError(f"step {i}: prepend vao file khong ton tai: {target}")
            block = load_payload(step.get("payload", ""), fill)
            content = block.rstrip("\n") + "\n\n" + cur
            virtual[target] = content
            actions.append({"target": target, "kind": "modify", "content": content})
        elif op == "append_lines":
            lines = step.get("lines")
            if (not isinstance(lines, list) or not lines
                    or any(not isinstance(l, str) or len(l) > 200 or "\n" in l
                           for l in lines)):
                raise PlanError(f"step {i}: lines phai la list chuoi ngan mot dong")
            cur = existing_content(target)
            base = (cur.rstrip("\n") + "\n") if cur else ""
            content = base + "\n".join(lines) + "\n"
            virtual[target] = content
            actions.append({"target": target,
                            "kind": "modify" if cur is not None else "create",
                            "content": content})
        elif op == "merge_settings":
            payload = json.loads(load_payload(step.get("payload", ""), {}))
            cur = existing_content(target)
            consumer = json.loads(cur) if cur else {}
            merged = merge_settings_content(consumer, payload, options, notes)
            content = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
            virtual[target] = content
            actions.append({"target": target,
                            "kind": "modify" if cur is not None else "create",
                            "content": content})
        elif op == "fill_placeholders":
            cur = existing_content(target)
            if cur is None:
                raise PlanError(f"step {i}: fill vao file khong ton tai: {target}")
            content = fill_text(cur, fill, target.endswith("rot/registry.md"))
            virtual[target] = content
            actions.append({"target": target, "kind": "modify", "content": content})
        elif op == "remove_path":
            if not tpath.exists():
                raise PlanError(f"step {i}: remove_path target khong ton tai: {target}")
            actions.append({"target": target, "kind": "remove", "content": None})
    if not marker_seen:
        raise PlanError("plan thieu write_marker (bat buoc, dat cuoi)")
    settings_rel = ".claude/settings.json"
    if settings_rel not in virtual and not (REPO_ROOT / settings_rel).exists():
        raise PlanError(
            "plan khong tao .claude/settings.json va file chua ton tai — "
            "self-check se FAIL; them step merge_settings")
    # dedupe theo target: giu action cuoi cung cho moi target
    final, seen = [], set()
    for a in reversed(actions):
        if a["target"] not in seen:
            seen.add(a["target"])
            final.append(a)
    final.reverse()
    return final, notes


# --------------------------------------------------------------------- apply

def do_apply(plan, plan_path):
    actions, notes = validate_and_simulate(plan)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    bdir = BACKUP_ROOT / ts
    bdir.mkdir(parents=True, exist_ok=False)
    created, modified, removed = [], [], []
    # backup TRUOC moi thay doi
    for a in actions:
        p = REPO_ROOT / a["target"]
        if p.exists():
            dest = bdir / a["target"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            if p.is_dir():
                shutil.copytree(p, dest)
            else:
                shutil.copy2(p, dest)
            entry = {"path": a["target"], "backup": str(dest.relative_to(REPO_ROOT))}
            (removed if a["kind"] == "remove" else modified).append(entry)
        else:
            created.append(a["target"])
    marker_rel = str(MARKER.relative_to(REPO_ROOT))
    marker_backup = bdir / marker_rel
    if MARKER.exists():
        marker_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MARKER, marker_backup)
        modified.append({"path": marker_rel, "backup": str(marker_backup.relative_to(REPO_ROOT))})
    else:
        created.append(marker_rel)
    manifest = {
        "pilothos_version": "1.9.0", "timestamp": ts, "mode": plan["mode"],
        "created": created, "modified": modified, "removed": removed,
        "notes": notes,
    }
    (bdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    applied = []
    try:
        for a in actions:
            p = REPO_ROOT / a["target"]
            if a["kind"] == "remove":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(a["content"], encoding="utf-8")
                if p.read_text(encoding="utf-8") != a["content"]:
                    raise IOError(f"postcondition fail: {a['target']}")
            applied.append(a)
        MARKER.write_text(json.dumps({
            "initialized_at": ts, "pilothos_version": "1.9.0",
            "mode": plan["mode"],
            "manifest": str((bdir / 'manifest.json').relative_to(REPO_ROOT)),
        }, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(plan_path, bdir / "install-plan.json")
        self_check_log = bdir / "self-check.log"
        with self_check_log.open("w", encoding="utf-8") as fh:
            out = subprocess.run([sys.executable, str(GUARD), "self-check"],
                                 stdout=fh, stderr=subprocess.STDOUT,
                                 text=True, timeout=10)
        self_check_text = self_check_log.read_text(encoding="utf-8")
        if out.returncode != 0 or "SELF-CHECK PASSED" not in self_check_text:
            raise IOError("self-check FAILED sau apply:\n" + self_check_text)
    except Exception as e:  # AUTO-ROLLBACK
        for a in applied:
            p = REPO_ROOT / a["target"]
            src = bdir / a["target"]
            if src.exists():
                if p.exists():
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
                if src.is_dir():
                    shutil.copytree(src, p)
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, p)
            elif p.exists():
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        if marker_backup.exists():
            MARKER.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(marker_backup, MARKER)
        elif MARKER.exists():
            MARKER.unlink()
        fail(3, {"result": "rolled_back", "error": str(e),
                 "backup": str(bdir.relative_to(REPO_ROOT))})
    dm = PILOTHOS_DIR / "dist-manifest.json"
    missing = []
    if dm.exists():
        for item in json.loads(dm.read_text(encoding="utf-8"))["files"]:
            if item["class"] in ("verbatim", "consumer-owned"):
                if not (REPO_ROOT / item["path"]).exists():
                    missing.append(item["path"])
        if missing:
            notes.append({"completeness_missing": missing})
    receipt = {
        "result": "applied", "mode": plan["mode"], "notes": notes,
        "steps": [{"target": a["target"], "kind": a["kind"], "status": "ok"}
                  for a in actions],
        "manifest": str((bdir / "manifest.json").relative_to(REPO_ROOT)),
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


# --------------------------------------------------------------- unattended

def adapter_set(value):
    """Chuẩn hoá adapter selection từ list (plan.adapters) hoặc chuỗi CSV
    (--adapters). None/rỗng → cả bốn. Reject adapter lạ."""
    if value is None:
        return set(ALLOWED_ADAPTERS)
    if isinstance(value, str):
        items = [x.strip().lower() for x in value.split(",") if x.strip()]
    elif isinstance(value, list):
        items = [x.strip().lower() for x in value
                 if isinstance(x, str) and x.strip()]
    else:
        raise PlanError(f"adapters phai la list hoac chuoi CSV: {value!r}")
    if not items:
        return set(ALLOWED_ADAPTERS)
    sel = set(items)
    unknown = sorted(sel - ALLOWED_ADAPTERS)
    if unknown:
        raise PlanError(f"unknown adapter(s): {', '.join(unknown)}")
    return sel


def selected_adapters(raw):
    return adapter_set(raw)


def optional_adapter_removal_steps(adapters, skip_targets=()):
    """remove_path steps cho các optional adapter KHÔNG chọn mà còn trên đĩa.
    Bỏ qua target đã có step (idempotent)."""
    skip = set(skip_targets)
    out = []
    for name, target in OPTIONAL_ADAPTER_PATHS.items():
        if (name not in adapters and target not in skip
                and (REPO_ROOT / target).exists()):
            out.append({"op": "remove_path", "target": target})
    return out


def add_optional_adapter_removals(steps, adapters):
    existing = {s.get("target") for s in steps
                if isinstance(s, dict) and s.get("op") == "remove_path"}
    steps.extend(optional_adapter_removal_steps(adapters, existing))


def _insert_before_marker(steps, new_steps):
    """Chèn new_steps ngay trước write_marker (hoặc cuối nếu chưa có marker),
    giữ write_marker luôn ở cuối."""
    if not new_steps:
        return
    idx = len(steps)
    for i, s in enumerate(steps):
        if isinstance(s, dict) and s.get("op") == "write_marker":
            idx = i
            break
    steps[idx:idx] = new_steps


def gitignore_append_step(plan, steps):
    """append_lines step cho .gitignore suy ra từ options.gitignore_scope, hoặc
    None nếu không cần. Idempotent: bỏ qua nếu đã có step .gitignore hoặc mọi dòng
    đã nằm trong file."""
    gi = REPO_ROOT / ".gitignore"
    if not gi.exists():
        return None
    if any(isinstance(s, dict) and s.get("op") == "append_lines"
           and s.get("target") == ".gitignore" for s in steps):
        return None
    scope = (plan.get("options") or {}).get("gitignore_scope", "runtime")
    want = PILOTHOS_GITIGNORE_ALL if scope == "all" else PILOTHOS_GITIGNORE_LINES
    current = set(gi.read_text(encoding="utf-8").splitlines())
    missing = [l for l in want if l not in current]
    if not missing:
        return None
    return {"op": "append_lines", "target": ".gitignore", "lines": ["", *missing]}


def normalize_plan(plan):
    """Suy ra các step deterministic từ ý định khai báo (`adapters`,
    `options.gitignore_scope`) — SSOT ở engine, Claude không gõ tay từng step.
    Chạy ở dry-run TRƯỚC khi user approve nên vẫn giữ byte-identical.
    Idempotent. Mutate plan tại chỗ; trả True nếu có thay đổi."""
    if not isinstance(plan, dict):
        return False
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return False
    new_steps = []
    if "adapters" in plan:
        existing = {s.get("target") for s in steps
                    if isinstance(s, dict) and s.get("op") == "remove_path"}
        new_steps += optional_adapter_removal_steps(
            adapter_set(plan.get("adapters")), existing)
    gi_step = gitignore_append_step(plan, steps)
    if gi_step:
        new_steps.append(gi_step)
    if not new_steps:
        return False
    _insert_before_marker(steps, new_steps)
    return True


def add_self_prune(steps):
    for target in SELF_PRUNE_ORDER:
        if (REPO_ROOT / target).exists():
            steps.append({"op": "remove_path", "target": target})


def build_unattended_plan(argv):
    parser = argparse.ArgumentParser(prog="unattended")
    parser.add_argument("--mode", choices=("greenfield", "brownfield", "upgrade"),
                        default="greenfield")
    parser.add_argument("--persona", default="")
    parser.add_argument("--goals", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--adapters", default="claude,cursor,codex,antigravity")
    parser.add_argument("--statusline", choices=("consumer", "pilothos", "chain"))
    parser.add_argument("--gitignore-scope", choices=GITIGNORE_SCOPES,
                        default="runtime")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-plan", action="store_true")
    args = parser.parse_args(argv)

    plan = {
        "plan_version": 1,
        "mode": args.mode,
        "fill": {"PERSONA": args.persona, "GOALS": args.goals, "OWNER": args.owner},
        "adapters": sorted(adapter_set(args.adapters)),
        "steps": [],
    }
    options = {}
    if args.statusline:
        options["statusline"] = args.statusline
    if args.gitignore_scope != "runtime":
        options["gitignore_scope"] = args.gitignore_scope
    if options:
        plan["options"] = options
    steps = plan["steps"]

    if args.mode == "greenfield":
        if (REPO_ROOT / "CLAUDE.md").exists():
            steps.append({"op": "fill_placeholders", "target": "CLAUDE.md"})
        if (REPO_ROOT / "pilothOS/rot/registry.md").exists():
            steps.append({"op": "fill_placeholders", "target": "pilothOS/rot/registry.md"})
    elif args.mode == "brownfield":
        if (REPO_ROOT / "pilothOS/rot/registry.md").exists():
            steps.append({"op": "fill_placeholders", "target": "pilothOS/rot/registry.md"})
        claude = REPO_ROOT / "CLAUDE.md"
        if claude.exists():
            text = claude.read_text(encoding="utf-8", errors="replace")
            if "@pilothOS/bootstrap.md" in text:
                steps.append({"op": "fill_placeholders", "target": "CLAUDE.md"})
            else:
                steps.append({"op": "prepend_block", "payload": "identity-block.md",
                              "target": "CLAUDE.md"})
        agents = REPO_ROOT / "AGENTS.md"
        if agents.exists():
            text = agents.read_text(encoding="utf-8", errors="replace")
            if "PilothOS Startup Contract" not in text:
                steps.append({"op": "prepend_block", "payload": "startup-contract-block.md",
                              "target": "AGENTS.md"})
        if (REPO_ROOT / ".claude/settings.json").exists():
            steps.append({"op": "merge_settings", "payload": "settings.json",
                          "target": ".claude/settings.json"})

    add_self_prune(steps)
    steps.append({"op": "write_marker"})
    # Adapter removals + .gitignore suy ra deterministic từ `adapters` /
    # `options.gitignore_scope` (SSOT — cùng đường với luồng interactive).
    normalize_plan(plan)
    return plan, args


def do_unattended(argv):
    try:
        plan, args = build_unattended_plan(argv)
    except PlanError as pe:
        fail(2, {"result": "plan_rejected", "error": str(pe)})
    if args.print_plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    pending = PILOTHOS_DIR / ".pending-plan.json"
    pending.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    try:
        actions, notes = validate_and_simulate(plan)
    except NeedsJudgment as nj:
        fail(4, {"result": "needs_judgment", "items": nj.items,
                 "pending_plan": str(pending.relative_to(REPO_ROOT))})
    except PlanError as pe:
        fail(2, {"result": "plan_rejected", "error": str(pe),
                 "pending_plan": str(pending.relative_to(REPO_ROOT))})
    if args.dry_run:
        print(json.dumps({
            "result": "plan_valid", "notes": notes,
            "pending_plan": str(pending.relative_to(REPO_ROOT)),
            "effects": [{"target": a["target"], "kind": a["kind"]}
                        for a in actions] + [{"target": "pilothOS/.initialized",
                                              "kind": "create" if not MARKER.exists() else "modify"}],
        }, ensure_ascii=False, indent=2))
        return
    do_apply(plan, pending)


# ----------------------------------------------------------------- uninstall

def do_uninstall(confirm):
    manifests = sorted(BACKUP_ROOT.glob("*/manifest.json"))
    if not manifests:
        fail(5, {"result": "nothing_to_restore",
                 "hint": "chua tung init bang installer"})
    mpath = manifests[-1]
    m = json.loads(mpath.read_text(encoding="utf-8"))
    plan = {"restore": [e["path"] for e in m.get("modified", []) + m.get("removed", [])],
            "delete": m.get("created", []), "manifest": str(mpath.relative_to(REPO_ROOT))}
    if not confirm:
        print(json.dumps({"result": "plan_only", "reverse_plan": plan,
                          "hint": "chay lai voi --confirm de thuc hien"},
                         ensure_ascii=False, indent=2))
        return
    for entry in m.get("modified", []) + m.get("removed", []):
        src = REPO_ROOT / entry["backup"]
        dst = REPO_ROOT / entry["path"]
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for c in m.get("created", []):
        p = REPO_ROOT / c
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    if MARKER.exists():
        MARKER.unlink()
    print(json.dumps({"result": "uninstalled", "restored": plan["restore"],
                      "deleted": plan["delete"],
                      "backup_kept": str(mpath.parent.relative_to(REPO_ROOT))},
                     ensure_ascii=False, indent=2))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    cmd = args[0]
    if cmd == "explain":
        print(MERGE_SEMANTICS)
        return
    if cmd == "unattended":
        do_unattended(args[1:])
        return
    if cmd == "uninstall":
        do_uninstall("--confirm" in args)
        return
    if cmd in ("validate", "dry-run", "apply"):
        if len(args) < 2:
            fail(2, {"error": f"{cmd} can duong dan plan.json"})
        plan_path = pathlib.Path(args[1])
        if not plan_path.exists():
            fail(2, {"error": f"plan khong ton tai: {plan_path}"})
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            fail(2, {"error": f"plan khong phai JSON hop le: {e}"})
        # Normalize: sinh remove_path (adapter khong chon) + append_lines
        # (.gitignore) deterministic từ ý định khai báo. Chạy ở dry-run/apply
        # và ghi lại file để "thứ approve = thứ thực thi". `validate` giữ
        # non-mutating (chỉ kiểm plan như đã cho).
        try:
            changed = normalize_plan(plan)
        except PlanError as pe:
            fail(2, {"result": "plan_rejected", "error": str(pe)})
        if changed and cmd in ("dry-run", "apply"):
            plan_path.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        try:
            actions, notes = validate_and_simulate(plan)
        except NeedsJudgment as nj:
            fail(4, {"result": "needs_judgment", "items": nj.items})
        except PlanError as pe:
            fail(2, {"result": "plan_rejected", "error": str(pe)})
        if cmd in ("validate", "dry-run"):
            print(json.dumps({
                "result": "plan_valid", "notes": notes,
                "effects": [{"target": a["target"], "kind": a["kind"]}
                            for a in actions] + [{"target": "pilothOS/.initialized",
                                                  "kind": "modify" if MARKER.exists() else "create"}],
            }, ensure_ascii=False, indent=2))
            return
        do_apply(plan, plan_path)
        return
    fail(2, {"error": f"lenh khong ho tro: {cmd}"})


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
