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


