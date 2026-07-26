# ---------------------------------------------------- OS contract construction

def clean_string_list(value):
    if isinstance(value, str) and value.strip():
        value = [value]
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in cleaned:
            cleaned.append(item.strip())
    return cleaned


def safe_evidence_id(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", raw).strip("-._:")[:120]


def request_task_id(request):
    for key in ("task_id", "id", "request_id"):
        if non_empty_string(request.get(key)):
            return safe_task_id(request[key])
    basis = {
        "intent": request.get("intent") or request.get("task_scope") or request.get("request"),
        "task_signal": request.get("task_signal"),
        "affected_paths": request.get("affected_paths") or request.get("allowed_paths") or request.get("changed_paths"),
    }
    return "task-" + sha256_json(basis)[:12]


def request_intent(request):
    for key in ("intent", "task_scope", "request", "summary", "title"):
        if non_empty_string(request.get(key)):
            return request[key].strip()
    return "repo-local OS task"


def request_paths(request):
    return (
        clean_string_list(request.get("target_paths"))
        or clean_string_list(request.get("allowed_paths"))
        or clean_string_list(request.get("affected_paths"))
        or clean_string_list(request.get("changed_paths"))
        or clean_string_list(request.get("paths"))
    )


def layers_for_requested_paths(paths):
    concrete = [
        path for path in paths
        if path and path not in {"*", "**", "**/*"} and not any(ch in path for ch in "*?[")
    ]
    if not concrete:
        return ["Consumer"]
    return sorted({layer_for_path(path) for path in concrete})


def merged_context_evidence(*groups):
    merged = []
    seen = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, dict):
                continue
            key = (
                item.get("source", ""),
                item.get("reason", ""),
                item.get("finding", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append({
                "source": str(item.get("source", "")).strip() or "os-start",
                "reason": str(item.get("reason", "")).strip() or "lifecycle context",
                "finding": str(item.get("finding", "")).strip() or "loaded by OS start",
            })
    return merged


def request_evidence_profile(request):
    profile = str(request.get("evidence_profile") or "generic").strip()
    return profile if profile in EVIDENCE_PROFILES else "generic"


def request_os_mode(request):
    raw = str(
        request.get("mode")
        or request.get("os_mode")
        or request.get("piloth_mode")
        or "standard"
    ).strip().lower()
    return raw if raw in OS_MODE_REQUESTS else "standard"


def mode_to_operational_preset(mode):
    return "strict" if mode == "strict" else "standard"


def path_pattern_is_broad(pattern):
    raw = str(pattern or "").strip()
    return raw in {"*", "**", "**/*", "."} or raw.endswith("/**")


def request_success_metrics(request):
    metrics = request.get("success_metrics") if isinstance(request, dict) else None
    if isinstance(metrics, list):
        return [
            str(item).strip()
            for item in metrics
            if isinstance(item, str) and item.strip()
        ]
    return [
        "not worse than none-piloth on mandatory fidelity/correctness/browser metrics",
        "win at least one consumer-visible metric before claiming consumer value",
    ]


def request_budget(request):
    budget = request.get("budget") if isinstance(request, dict) else None
    if isinstance(budget, dict):
        return sanitize_state_value(budget, limit=1000)
    return {
        "llm_tokens": "telemetry_required_for_exact_cost_claims",
        "context": "load only task-routed files",
        "verification": "smallest check that proves the claim",
    }


def design_token_expected_evidence(expected):
    required = [
        "figma_node",
        "design_token_coverage",
        "covered_groups",
        "generated_surfaces",
        "verification",
    ]
    merged = list(expected)
    for item in required:
        if item not in merged:
            merged.append(item)
    return merged


def request_has_figma_signal(request):
    if not isinstance(request, dict):
        return False
    text = json.dumps(sanitize_state_value(request, limit=1000), ensure_ascii=False).lower()
    return "figma" in text or "figma.com" in text


def ui_expected_evidence(expected, request):
    required = ["ui_quality"]
    if request_has_figma_signal(request):
        required.append("figma_node")
    merged = list(expected)
    for item in required:
        if item not in merged:
            merged.append(item)
    return merged


def default_reuse_evidence(task_signal):
    return [{
        "asset": "reuse-scan",
        "decision": "not_applicable",
        "reason": f"os-start lifecycle for {task_signal}; update with reuse-scan evidence before new code when applicable",
    }]


def build_os_contract(request, route, target=None):
    paths = request_paths(request) or ["**/*"]
    task_signal = route.get("task_signal") or request.get("task_signal") or "not_applicable"
    layers = (
        clean_string_list(request.get("affected_layers"))
        or layers_for_requested_paths(paths)
    )
    mode = request_os_mode(request)
    expected = (
        clean_string_list(request.get("expected_evidence"))
        or ["manual verification receipt"]
    )
    evidence_profile = request_evidence_profile(request)
    if evidence_profile == "design_tokens":
        expected = design_token_expected_evidence(expected)
    elif evidence_profile == "ui" or any(path_pattern_suggests_ui(path) for path in paths):
        expected = ui_expected_evidence(expected, request)
    route_context = route.get("context_evidence") if isinstance(route, dict) else []
    footprint_policy = request_target_footprint_policy(request, target or {})
    contract = {
        "task_scope": request_intent(request),
        "affected_layers": layers,
        "allowed_paths": paths,
        "expected_evidence": expected,
        "out_of_scope_paths": clean_string_list(request.get("out_of_scope_paths")),
        "consumer_scope": request.get("consumer_scope") or "repo-local task scope from os-start",
        "target_paths": paths,
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "evidence_profile": evidence_profile,
        "mode": mode,
        "operational_preset": mode_to_operational_preset(mode),
        "execution_strategy": request.get("execution_strategy")
        or ("controlled_target" if isinstance(target, dict) and target.get("explicit") else "repo_local"),
        "target_footprint_policy": footprint_policy,
        "budget": request_budget(request),
        "success_metrics": request_success_metrics(request),
        "context_evidence": clean_string_list([]),
        "reuse_evidence": request.get("reuse_evidence") or default_reuse_evidence(task_signal),
        "decision_limits": clean_string_list(request.get("decision_limits"))
        or ["Do not expand scope without updating the OS task contract."],
        "consumer_asset_routing": request.get("consumer_asset_routing")
        or route.get("consumer_asset_routing")
        or [{
            "task_signal": task_signal,
            "asset_type": "not_applicable",
            "decision": "not_applicable",
            "reason": "no task-routed consumer assets selected",
        }],
    }
    contract["context_evidence"] = (
        request.get("context_evidence")
        if isinstance(request.get("context_evidence"), list)
        else merged_context_evidence(route_context, [{
            "source": "pilothOS/runtime/os-control-plane.md",
            "reason": "OS lifecycle contract",
            "finding": "task is routed through os-start/os-close",
        }])
    )
    for optional in (
        "operational_preset", "allowed_entitlements", "requires_judgment",
        "benchmark_id", "model_hints",
        "ui_design_system_evidence", "energy_budget_reason",
    ):
        if optional in request:
            contract[optional] = request[optional]
    if isinstance(target, dict):
        contract["target_repo"] = target.get("target_repo", "")
        contract["target_kind"] = target.get("target_kind", "")
        contract["target_id"] = target.get("target_id", "")
    if isinstance(request.get("coverage_claims"), dict):
        contract["coverage_claims"] = sanitize_state_value(request.get("coverage_claims"), limit=1000)
    if contract_requires_ui_design_system_evidence(contract) and "ui_design_system_evidence" not in contract:
        contract["ui_design_system_evidence"] = [{
            "source": "asset-scan",
            "checked": "deterministic design-system routing check",
            "decision": "not_applicable",
            "reason": "os-start found no explicit design-system evidence in the request; update the contract before UI edits if a design system applies",
        }]
    return contract
