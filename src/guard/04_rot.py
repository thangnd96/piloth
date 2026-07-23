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


