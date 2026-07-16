#!/usr/bin/env python3
"""PilothOS guard: hook + statusline cho cơ chế enforcement.

Các mode:
  session-start   Ghi marker phiên + inject cảnh báo Rot vào context khi mở session (hook SessionStart).
  prompt-check    Inject cảnh báo Rot ở mỗi lượt message, CHỈ MỘT LẦN mỗi phiên cho cùng
                  một trạng thái overdue — tối ưu token (hook UserPromptSubmit).
  stop-check      AUTO-LOG GATE: khi agent kết thúc lượt mà repo có thay đổi nhưng
                  review-log/lessons-learned chưa được cập nhật trong phiên, chặn một lần
                  và yêu cầu agent append log hoặc tuyên bố rõ "không có finding" (hook Stop).
  statusline      Dòng trạng thái Rot cho status line; chỉ hiện khi có scope quá hạn.
  self-check      Kiểm tra settings.json + registry + log files; dùng sau mỗi lần sửa cấu hình.
  preflight       Preflight của /pilothos-init: kiểm môi trường (quyền ghi, settings hợp lệ,
                  cây pilothOS đầy đủ) — fail sớm và rõ ràng.
  detect          Stage 0 của /pilothos-init: verdict greenfield/brownfield/re-init/dirty
                  kèm evidence; KHÔNG tự rẽ nhánh, chờ consumer confirm.
  log-append      Ghi một dòng log đúng format (review|lesson), Date tự điền,
                  verify Evidence path tồn tại — dùng cho Stage 5 và mọi lần ghi log.
  pre-edit        Hook target cho PreToolUse (placeholder, không chặn).
  post-edit       Hook target cho PostToolUse (placeholder, không chặn).

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
import sys
import re
import json
import time
import datetime
import pathlib

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PILOTHOS_DIR = SCRIPT_DIR.parent            # <repo>/pilothOS
REPO_ROOT = PILOTHOS_DIR.parent             # <repo>
REGISTRY = PILOTHOS_DIR / "rot" / "registry.md"
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
REVIEW_LOG = PILOTHOS_DIR / "rot" / "review-log.md"
LESSONS = PILOTHOS_DIR / "memory" / "lessons-learned.md"
MARKER_DIR = pathlib.Path("/tmp/pilothos")

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
MARKER_TTL_SECONDS = 48 * 3600

# Thư mục/file bỏ qua khi quét thay đổi cho auto-log gate
SCAN_EXCLUDE_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
SCAN_EXCLUDE_FILES = {REVIEW_LOG.resolve(), LESSONS.resolve()}


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


def session_start(hook_input):
    """Ghi marker mở phiên (mốc thời gian cho auto-log gate) + cảnh báo Rot."""
    MARKER_DIR.mkdir(exist_ok=True)
    cleanup_old_markers()
    sid = hook_input.get("session_id")
    if sid:
        marker(sid, "start").write_text(str(time.time()), encoding="utf-8")
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


def stop_check(hook_input):
    """AUTO-LOG GATE (hook Stop).

    Nếu phiên có thay đổi file mà cả review-log lẫn lessons-learned đều chưa
    được cập nhật → block MỘT LẦN, yêu cầu agent: append log entry phù hợp,
    hoặc tuyên bố rõ trong reply rằng không có finding/lesson và vì sao.
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
        return  # phiên chỉ đọc/hỏi đáp → không cần log
    if logs_touched_since(ts):
        return  # đã có ghi nhận trong phiên → đạt
    print(json.dumps({
        "decision": "block",
        "reason": (
            "PILOTHOS AUTO-LOG GATE: Phiên này có thay đổi file nhưng "
            "pilothOS/rot/review-log.md và pilothOS/memory/lessons-learned.md "
            "đều chưa được cập nhật. Trước khi kết thúc, hãy làm MỘT trong hai: "
            "(1) append dòng log phù hợp (review-log cho finding/thay đổi kiến trúc, "
            "lessons-learned cho bài học đáng tái sử dụng — đúng format bảng, "
            "append-only), hoặc (2) nêu rõ trong reply cuối: 'Không có finding "
            "hoặc lesson cần ghi' kèm một câu lý do. Đây là Deliver gate theo "
            "pilothOS/bootstrap.md."
        ),
    }))


# ---------------------------------------------------------------- installer

INIT_MARKER = PILOTHOS_DIR / ".initialized"
BACKUP_DIR = PILOTHOS_DIR / ".backup"
CORE_FILES = [PILOTHOS_DIR / "bootstrap.md", REGISTRY,
              PILOTHOS_DIR / "PilothOS.md", REVIEW_LOG, LESSONS]
CONSUMER_ASSET_HINTS = ["package.json", "pyproject.toml", "go.mod", "Cargo.toml",
                        "pom.xml", "src", "app", "lib"]
# Adapter dirs do bản phân phối ship sẵn — chỉ là tài sản consumer khi chứa
# nội dung không thuộc PilothOS
ADAPTER_DIRS = [".claude", ".cursor", ".codex", ".antigravity"]


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
        print("NOTE: re-init/upgrade chua ho tro — ghi finding vao review-log va dung.")
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

    for log, name in ((REVIEW_LOG, "review-log.md"), (LESSONS, "lessons-learned.md")):
        if log.exists():
            print(f"OK   {name} ton tai (auto-log gate hoat dong)")
        else:
            ok = False
            print(f"FAIL khong tim thay {name} — auto-log gate se khong chinh xac")
    print("SELF-CHECK " + ("PASSED" if ok else "FAILED"))


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    hook_input = read_hook_input() if mode in (
        "session-start", "prompt-check", "stop-check") else {}
    if mode == "session-start":
        session_start(hook_input)
    elif mode == "prompt-check":
        prompt_check(hook_input)
    elif mode == "stop-check":
        stop_check(hook_input)
    elif mode == "statusline":
        statusline()
    elif mode == "self-check":
        self_check()
    elif mode == "preflight":
        preflight()
    elif mode == "detect":
        detect()
    elif mode == "log-append":
        log_append(sys.argv[2:])
    else:
        print(f"PilothOS guard: {mode}")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
