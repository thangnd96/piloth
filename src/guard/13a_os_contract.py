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
        or "adaptive"
    ).strip().lower()
    return raw if raw in OS_MODE_REQUESTS else "adaptive"


def mode_to_operational_preset(mode):
    if mode == "lean":
        return "light"
    if mode == "strict":
        return "strict"
    return "standard"


def path_pattern_is_broad(pattern):
    raw = str(pattern or "").strip()
    return raw in {"*", "**", "**/*", "."} or raw.endswith("/**")


def paths_look_docs_tests_only(paths, layers):
    normalized_layers = {normalize_layer(x) for x in layers}
    if normalized_layers and normalized_layers <= DOC_TEST_LAYERS:
        return True
    concrete = [path for path in paths if not path_pattern_is_broad(path)]
    return bool(concrete) and all(is_docs_path(path) or is_test_path(path) for path in concrete)


def choose_adaptive_mode(request, paths, layers, target):
    requested = request_os_mode(request)
    reasons = []
    if requested in OS_MODES:
        return requested, [{
            "mode": requested,
            "source": "request",
            "reason": f"explicit mode={requested}",
        }]

    task_signal = str(request.get("task_signal") or "").strip().lower()
    intent_blob = json.dumps(sanitize_state_value(request, limit=1000), ensure_ascii=False).lower()
    evidence_profile = request_evidence_profile(request)
    broad_paths = not paths or any(path_pattern_is_broad(path) for path in paths) or len(paths) > 6
    target_external = isinstance(target, dict) and bool(target.get("external"))
    docs_tests_only = paths_look_docs_tests_only(paths, layers)

    if evidence_profile == "design_tokens":
        reasons.append("design_tokens evidence profile requires strict coverage discipline")
        return "strict", [{"mode": "strict", "source": "adaptive", "reason": "; ".join(reasons)}]
    if "release/deploy" in task_signal or any(term in intent_blob for term in ("deploy", "production", "release")):
        reasons.append("release/deploy or production signal")
        return "strict", [{"mode": "strict", "source": "adaptive", "reason": "; ".join(reasons)}]
    if any(term in intent_blob for term in ("full design tokens", "all tokens", "entire library", "pixel-perfect", "1:1")):
        reasons.append("absolute/full-coverage claim risk")
        return "strict", [{"mode": "strict", "source": "adaptive", "reason": "; ".join(reasons)}]
    if broad_paths:
        reasons.append("broad target paths")
        return "standard", [{"mode": "standard", "source": "adaptive", "reason": "; ".join(reasons)}]
    if docs_tests_only:
        reasons.append("docs/tests-only narrow scope")
        return "lean", [{"mode": "lean", "source": "adaptive", "reason": "; ".join(reasons)}]
    if "ui/component" in task_signal and len(paths) <= 4:
        reasons.append("small UI/component scope")
        return "lean", [{"mode": "lean", "source": "adaptive", "reason": "; ".join(reasons)}]
    concrete_paths = [path for path in paths if not path_pattern_is_broad(path)]
    if concrete_paths and len(concrete_paths) <= SMALL_SCOPE_MAX_PATHS:
        reasons.append(f"small blast radius ({len(concrete_paths)} concrete paths)")
        return "lean", [{"mode": "lean", "source": "adaptive", "reason": "; ".join(reasons)}]
    if target_external:
        reasons.append("explicit external target with non-trivial scope")
        return "standard", [{"mode": "standard", "source": "adaptive", "reason": "; ".join(reasons)}]
    reasons.append("default non-trivial task scope")
    return "standard", [{"mode": "standard", "source": "adaptive", "reason": "; ".join(reasons)}]


def suggest_phase_plan(request, paths, layers, evidence_profile):
    """Advisory-only phase recommendation (recipe right-sizing).

    Mirrors aidlc's deterministic heuristicClassify: recommend the front-half
    phases that would prevent rework, without ever enabling them. This NEVER
    mutates requires_prototype / requires_discovery — a human opts in on a
    follow-up os-start. Surfaced in os-status / os-report so the operator sees
    the suggestion but keeps control (auto-enabling a heavy phase would add
    cost, the opposite of the intent).
    """
    signal = str(request.get("task_signal") or "").strip().lower()
    intent = json.dumps(sanitize_state_value(request, limit=1000), ensure_ascii=False).lower()
    paths = paths or []
    ui = (
        evidence_profile == "ui"
        or "ui/component" in signal
        or any(path_pattern_suggests_ui(p) for p in paths)
    )
    trivial = (
        paths_look_docs_tests_only(paths, layers)
        or "bugfix" in signal
        or "bug fix" in intent
    )
    high_impact = any(
        k in intent for k in
        ("architecture", "acceptance criteria", "out of scope", "unclear", "ambiguous", "not sure", "unknown")
    )
    broad = (not paths) or any(path_pattern_is_broad(p) for p in paths) or len(paths) > 6
    rec_proto = bool(ui and not trivial)
    rec_disc = bool((high_impact or broad) and not trivial)
    reasons = []
    if rec_proto:
        reasons.append("UI/component scope — a prototype round can de-risk the visual direction before implementation")
    if rec_disc:
        reasons.append("ambiguous or broad scope — a discovery gate can confirm open questions up front")
    if not reasons:
        reasons.append("scope looks narrow/clear — no extra front-half phase recommended")
    return {
        "recommend_discovery": rec_disc,
        "recommend_prototype": rec_proto,
        "reasons": reasons,
        "note": "suggestions only — pass requires_discovery / requires_prototype in a follow-up os-start to enable",
    }


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


def build_os_contract(request, route, scheduler, target=None):
    paths = request_paths(request) or ["**/*"]
    task_signal = route.get("task_signal") or request.get("task_signal") or "not_applicable"
    skeleton = scheduler.get("contract_skeleton") if isinstance(scheduler, dict) else {}
    if not isinstance(skeleton, dict):
        skeleton = {}
    layers = (
        clean_string_list(request.get("affected_layers"))
        or clean_string_list(skeleton.get("affected_layers"))
        or layers_for_requested_paths(paths)
    )
    mode, mode_decisions = choose_adaptive_mode(request, paths, layers, target)
    expected = (
        clean_string_list(request.get("expected_evidence"))
        or clean_string_list(scheduler.get("expected_evidence") if isinstance(scheduler, dict) else None)
        or clean_string_list(skeleton.get("expected_evidence"))
        or ["manual verification receipt"]
    )
    evidence_profile = request_evidence_profile(request)
    if evidence_profile == "design_tokens":
        expected = design_token_expected_evidence(expected)
    elif evidence_profile == "ui" or any(path_pattern_suggests_ui(path) for path in paths):
        expected = ui_expected_evidence(expected, request)
    route_context = route.get("context_evidence") if isinstance(route, dict) else []
    scheduler_context = skeleton.get("context_evidence")
    footprint_policy = request_target_footprint_policy(request, target or {})
    contract = {
        "task_scope": request_intent(request),
        "affected_layers": layers,
        "allowed_paths": paths,
        "expected_evidence": expected,
        "out_of_scope_paths": clean_string_list(request.get("out_of_scope_paths")),
        "consumer_scope": request.get("consumer_scope") or skeleton.get("consumer_scope") or "repo-local task scope from os-start",
        "target_paths": paths,
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "evidence_profile": evidence_profile,
        "mode": mode,
        "mode_decisions": mode_decisions,
        "adaptive_mode": request_os_mode(request) in {"adaptive", "auto"},
        "operational_preset": mode_to_operational_preset(mode),
        "execution_strategy": request.get("execution_strategy")
        or ("controlled_target" if isinstance(target, dict) and target.get("explicit") else "repo_local"),
        "target_footprint_policy": footprint_policy,
        "budget": request_budget(request),
        "success_metrics": request_success_metrics(request),
        "context_evidence": clean_string_list([]),
        "reuse_evidence": request.get("reuse_evidence") or skeleton.get("reuse_evidence") or default_reuse_evidence(task_signal),
        "decision_limits": clean_string_list(request.get("decision_limits"))
        or clean_string_list(skeleton.get("decision_limits"))
        or ["Do not expand scope without updating the OS task contract."],
        "consumer_asset_routing": request.get("consumer_asset_routing")
        or route.get("consumer_asset_routing")
        or skeleton.get("consumer_asset_routing")
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
        else merged_context_evidence(route_context, scheduler_context, [{
            "source": "pilothOS/runtime/os-control-plane.md",
            "reason": "OS lifecycle contract",
            "finding": "task is routed through os-start/os-close",
        }])
    )
    for optional in (
        "operational_preset", "allowed_entitlements", "requires_judgment",
        "benchmark_id", "requires_human_review", "requires_prototype",
        "requires_discovery", "discovery_decisions", "model_hints",
        "ui_design_system_evidence", "energy_budget_reason",
    ):
        if optional in request:
            contract[optional] = request[optional]
    # A prototype's human pick is recorded through the reused human_review
    # round-trip, so requiring a prototype implies requiring human review.
    if contract.get("requires_prototype"):
        contract["requires_human_review"] = True
    # Advisory recipe: recommend front-half phases without ever enabling them.
    contract["phase_plan_suggestion"] = suggest_phase_plan(request, paths, layers, evidence_profile)
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
