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
        if (
            rel.startswith("pilothOS/memory/state/") and rel.endswith(".jsonl")
        )
        or rel.startswith("pilothOS/memory/state/os-runs/")
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
        if (
            rel.startswith("pilothOS/memory/state/") and rel.endswith(".jsonl")
        )
        or rel.startswith("pilothOS/memory/state/os-runs/")
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
    required_modes = {
        "contract-write",
        "os-start",
        "os-status",
        "os-evidence",
        "os-close",
        "os-verify",
        "os-report",
        "asset-scan",
        "asset-health",
        "evidence-add",
        "tool-check",
        "receipt-write",
        "receipt-seal",
        "receipt-verify",
        "artifact-janitor",
        "control-plane-check",
        "production-review",
    }
    missing_modes = sorted(required_modes - modes)
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


# Command dispatch: mode -> (handler, arg_kind). One source of truth for every
# guard mode, replacing a long if/elif chain. arg_kind selects how the handler
# is invoked:
#   "hook" -> handler(read_hook_input())   (only these modes read stdin)
#   "argv" -> handler(sys.argv[2:])
#   "none" -> handler()
COMMAND_TABLE = {
    # hook modes (read hook JSON from stdin)
    "session-start": (session_start, "hook"),
    "prompt-check": (prompt_check, "hook"),
    "stop-check": (stop_check, "hook"),
    "pre-edit": (pre_edit, "hook"),
    "post-edit": (post_edit, "hook"),
    # argv modes (JSON arg / file / stdin payload)
    "contract-write": (task_contract_write, "argv"),
    "evidence-add": (evidence_add, "argv"),
    "tool-check": (tool_check, "argv"),
    "receipt-write": (receipt_write, "argv"),
    "os-start": (os_start, "argv"),
    "os-status": (os_status, "argv"),
    "os-evidence": (os_evidence, "argv"),
    "token-telemetry": (token_telemetry, "argv"),
    "os-close": (os_close, "argv"),
    "os-verify": (os_verify, "argv"),
    "os-report": (os_report, "argv"),
    "review-request": (review_request, "argv"),
    "review-feedback": (review_feedback, "argv"),
    "review-verify": (review_verify, "argv"),
    "asset-scan": (asset_scan, "argv"),
    "asset-health": (asset_health, "argv"),
    "asset-sync": (asset_sync, "argv"),
    "route-task": (route_task, "argv"),
    "context-budget": (context_budget, "argv"),
    "rot-status": (rot_status, "none"),
    "reuse-scan": (reuse_scan, "argv"),
    "ds-scan": (ds_scan, "argv"),
    "scheduler-suggest": (scheduler_suggest, "argv"),
    "scheduler-record": (scheduler_record, "argv"),
    "receipt-seal": (receipt_seal, "argv"),
    "receipt-verify": (receipt_verify, "argv"),
    "artifact-janitor": (artifact_janitor, "argv"),
    "state-janitor": (state_janitor, "argv"),
    "control-plane-check": (control_plane_check, "argv"),
    "team-contract-write": (team_contract_write, "argv"),
    "team-receipt-write": (team_receipt_write, "argv"),
    "log-append": (log_append, "argv"),
    # no-arg modes
    "receipt-template": (receipt_template, "none"),
    "statusline": (statusline, "none"),
    "self-check": (self_check, "none"),
    "self-host-check": (self_host_check, "none"),
    "preflight": (preflight, "none"),
    "detect": (detect, "none"),
    "audit-assets": (audit_consumer_assets, "none"),
    "registry-assets": (registry_consumer_assets, "none"),
    "state-doctor": (state_doctor, "none"),
    "production-review": (production_review, "none"),
}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    entry = COMMAND_TABLE.get(mode)
    if entry is None:
        print(f"PilothOS guard: {mode}")
        sys.exit(0)
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
