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


# Append-only ledgers whose size tracks how long an install has been running, not
# how big the kernel is: the auto-log gate appends to them on every session that
# changes files. They are also staged header-only, so they are ~0 bytes for a fresh
# consumer while the Piloth repo's own copies keep growing. Counting them would make
# both ceilings a moving target measured against the wrong install.
GROWING_LEDGERS = ("rot/review-log.md", "memory/lessons-learned.md")


def kernel_md_paths():
    """Kernel markdown docs that count toward a ceiling, newest state excluded."""
    for path in PILOTHOS_DIR.rglob("*.md"):
        if path.relative_to(PILOTHOS_DIR).as_posix() in GROWING_LEDGERS:
            continue
        yield path


def full_kernel_footprint():
    """(file_count, total_bytes) of every kernel markdown doc — the load-all ceiling."""
    total = 0
    files = 0
    for path in kernel_md_paths():
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
    for path in kernel_md_paths():
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


