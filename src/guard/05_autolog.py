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


