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
    return {
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
    json_print({"result": "scheduler_recorded", "path": SCHEDULER_HISTORY.relative_to(REPO_ROOT).as_posix()})


