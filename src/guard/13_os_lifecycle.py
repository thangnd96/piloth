# --------------------------------------------------------- OS lifecycle modes

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


def contract_requires_ui_quality_evidence(contract, receipt=None):
    if isinstance(contract, dict) and contract.get("evidence_profile") == "ui":
        return True
    paths = []
    if isinstance(contract, dict):
        paths.extend(clean_string_list(contract.get("allowed_paths")))
        paths.extend(clean_string_list(contract.get("target_paths")))
    if isinstance(receipt, dict):
        paths.extend(clean_string_list(receipt.get("changed_files")))
    return any(path_pattern_suggests_ui(path) for path in paths)


def required_gates_for_task(contract, receipt=None, mode=None):
    paths = sorted(facts_paths({}, receipt))
    if isinstance(contract, dict):
        paths.extend(clean_string_list(contract.get("allowed_paths")))
    layers = set()
    if isinstance(contract, dict):
        layers |= {normalize_layer(x) for x in contract.get("affected_layers", [])}
    if isinstance(receipt, dict):
        layers |= {normalize_layer(x) for x in receipt.get("affected_layers", [])}
    effective_mode = mode or (contract.get("mode") if isinstance(contract, dict) else None) or "standard"
    gates = ["scope", "correctness", "disclosure"]
    if effective_mode != "lean":
        gates.insert(2, "traceability")
    if effective_mode != "lean" and (not layers or not layers <= DOC_TEST_LAYERS):
        gates.extend(["architecture", "reuse_non_duplication", "regression"])
    if any(path_pattern_suggests_ui(path) or is_ui_path(path) for path in paths):
        gates.append("design_system")
    if contract_requires_ui_quality_evidence(contract, receipt):
        gates.append("ui_quality")
    if (
        isinstance(contract, dict) and contract.get("evidence_profile") == "design_tokens"
    ) or (
        isinstance(receipt, dict) and receipt.get("evidence_profile") == "design_tokens"
    ):
        gates.append("design_token_coverage")
    signal_text = json.dumps({
        "contract": contract or {},
        "receipt": receipt or {},
    }, ensure_ascii=False).lower()
    if "release/deploy" in signal_text or "deploy" in signal_text:
        gates.append("operational_approval")
    if isinstance(contract, dict) and contract.get("requires_human_review"):
        gates.append("human_review")
    if isinstance(contract, dict) and contract.get("requires_prototype"):
        gates.append("prototype")
    return list(dict.fromkeys(gates))


def validate_required_quality_gates(receipt, required_gates):
    errors = []
    gates = receipt.get("quality_gates")
    if not isinstance(gates, dict):
        return ["quality_gates must be an object for os-close"]
    for gate in required_gates:
        item = gates.get(gate)
        if not isinstance(item, dict):
            errors.append(f"quality_gates.{gate} is required for os-close")
            continue
        result = item.get("result")
        if result not in QUALITY_GATE_RESULTS:
            errors.append(f"quality_gates.{gate}.result must be PASS, FAIL, or NOT_APPLICABLE")
        if not non_empty_string(item.get("evidence")):
            errors.append(f"quality_gates.{gate}.evidence must be a non-empty string")
        delivery_result = str(receipt.get("result", "")).strip().lower()
        if result == "FAIL" and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
            if not non_empty_string(receipt.get("limitation")):
                errors.append(f"limitation is required when quality_gates.{gate}.result is FAIL")
    return errors


def validate_review_feedback(value):
    """Validate the structured human-review feedback artifact (schema + enums).

    Faithful to annotron's structured feedback, translated into Piloth's gate
    vocabulary: findings carry a location (file and/or gate), a note, a severity
    and a disposition; the round carries a verdict and a finalized flag.
    """
    if not isinstance(value, dict):
        return ["review feedback must be a JSON object"]
    errors = []
    if value.get("verdict") not in REVIEW_VERDICTS:
        errors.append("verdict must be one of: " + ", ".join(sorted(REVIEW_VERDICTS)))
    if not isinstance(value.get("finalized"), bool):
        errors.append("finalized must be a boolean")
    findings = value.get("findings")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        return errors
    errors.extend(validate_object_list_enums(
        findings,
        "findings",
        ("id", "note", "severity", "disposition"),
        {"severity": REVIEW_SEVERITIES, "disposition": REVIEW_DISPOSITIONS},
    ))
    for i, finding in enumerate(findings):
        if not isinstance(finding, dict):
            continue
        loc = finding.get("location")
        if not isinstance(loc, dict) or not (
            non_empty_string(loc.get("file")) or non_empty_string(loc.get("gate"))
        ):
            errors.append(f"findings[{i}].location must include a file or a gate")
            continue
        if non_empty_string(loc.get("file")):
            _, err = repo_relative_path(loc.get("file"))
            if err:
                errors.append(f"findings[{i}].location.file {err}")
    return errors


def validate_human_review_gate(state, contract, receipt, os_evidence):
    """Machine cross-check for the human_review gate (anti-checkbox core).

    The guard never judges whether a finding is correct — only that a real,
    finalized, approving human artifact exists with no unresolved blocking
    findings. Returns (errors, summary) where summary.result is
    PASS / FAIL / NOT_APPLICABLE. Unresolved blocking findings surface in
    summary.unresolved so os-close can route the task back to Repair.
    """
    required = isinstance(contract, dict) and bool(contract.get("requires_human_review"))
    if not required:
        return [], {"result": "NOT_APPLICABLE"}
    task_id = state.get("task_id") if isinstance(state, dict) else None
    feedback = latest_review_feedback(task_id)
    if not feedback:
        return (
            ["human_review gate requires a review-feedback artifact; run review-request then review-feedback"],
            {"result": "FAIL", "reason": "no review feedback recorded"},
        )
    ferrors = validate_review_feedback(feedback)
    if ferrors:
        return (
            [f"review feedback invalid: {e}" for e in ferrors],
            {"result": "FAIL", "reason": "invalid review feedback"},
        )
    review_round = feedback.get("review_round")
    if feedback.get("finalized") is not True:
        return (
            ["human_review is not finalized (review round still open)"],
            {"result": "FAIL", "reason": "not finalized", "review_round": review_round},
        )
    unresolved = [
        finding.get("id")
        for finding in feedback.get("findings", [])
        if isinstance(finding, dict)
        and finding.get("severity") in REVIEW_BLOCKING_SEVERITIES
        and finding.get("disposition") == "request-changes"
    ]
    if unresolved:
        return (
            ["human_review has unresolved blocking findings routed to Repair: "
             + ", ".join(str(x) for x in unresolved)],
            {"result": "FAIL", "reason": "unresolved blocking findings",
             "unresolved": unresolved, "review_round": review_round},
        )
    if feedback.get("verdict") != "approve":
        return (
            ["human_review verdict is not approve"],
            {"result": "FAIL", "reason": "verdict not approve",
             "verdict": feedback.get("verdict"), "review_round": review_round},
        )
    summary = {
        "result": "PASS",
        "review_round": review_round,
        "verdict": "approve",
        "reviewer": feedback.get("reviewer", ""),
    }
    try:
        summary["feedback_path"] = review_feedback_path(task_id).relative_to(REPO_ROOT).as_posix()
    except (ValueError, TypeError):
        pass
    return [], summary


def latest_evidence_of_kind(os_evidence, kind):
    """Return the most recently recorded os-evidence record of a given kind."""
    matches = [
        item for item in (os_evidence or [])
        if isinstance(item, dict) and item.get("kind") == kind
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda item: str(item.get("recorded_at") or ""))[-1]


def validate_prototype_gate(state, contract, receipt, os_evidence):
    """Machine check for the thin prototype gate (evidence completeness only).

    Prototype reuses the human_review round-trip for the human sign-off; this
    gate only asserts prototype's own invariant — a valid design method, >=2
    options generated, and one chosen among them — read from the recorded
    prototype evidence. Anti-checkbox: a receipt that self-declares prototype
    PASS with no backing evidence record still FAILs. Returns a summary dict
    with result PASS / FAIL / NOT_APPLICABLE.
    """
    required = isinstance(contract, dict) and bool(contract.get("requires_prototype"))
    if not required:
        return {"result": "NOT_APPLICABLE"}
    ev = latest_evidence_of_kind(os_evidence, "prototype")
    if ev is None:
        return {"result": "FAIL", "reason": "no prototype evidence recorded"}
    everrors = validate_prototype_evidence(ev)
    if everrors:
        return {"result": "FAIL", "reason": "; ".join(everrors)}
    return {
        "result": "PASS",
        "method": ev.get("method"),
        "options": len([o for o in ev.get("options", []) if isinstance(o, dict)]),
        "chosen": ev.get("chosen"),
    }


def evidence_text_blob(receipt, facts, os_evidence):
    parts = []
    for item in os_evidence:
        parts.append(json.dumps(item, ensure_ascii=False))
    for item in facts.get("evidence_commands", []):
        parts.append(json.dumps(item, ensure_ascii=False))
    if isinstance(receipt, dict):
        parts.append(str(receipt.get("verification_command", "")))
        for item in receipt.get("tool_uses", []) if isinstance(receipt.get("tool_uses"), list) else []:
            if isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=False))
        gates = receipt.get("quality_gates")
        if isinstance(gates, dict):
            parts.append(json.dumps(gates, ensure_ascii=False))
    return "\n".join(parts).lower()


def validate_expected_evidence_present(contract, receipt, facts, os_evidence):
    if not isinstance(contract, dict):
        return ["active OS contract is missing"]
    blob = evidence_text_blob(receipt, facts, os_evidence)
    errors = []
    for expected in contract.get("expected_evidence", []):
        if not non_empty_string(expected):
            continue
        needle = expected.strip().lower()
        if needle not in blob:
            errors.append(f"missing evidence for expected_evidence: {expected}")
    return errors


def collect_evidence_refs(receipt, os_evidence):
    refs = {"receipt", "verification_command"}
    for item in os_evidence:
        if non_empty_string(item.get("id")):
            refs.add(item["id"])
    gates = receipt.get("quality_gates") if isinstance(receipt, dict) else None
    if isinstance(gates, dict):
        for key in gates:
            refs.add(f"quality_gates.{key}")
    return refs


def unqualified_absolute_claim(text):
    lowered = str(text).lower()
    if not ABSOLUTE_CLAIM_RE.search(lowered):
        return False
    return not any(term in lowered for term in QUALIFIED_CLAIM_TERMS)


def truth_risk_flags(receipt, os_evidence, missing_evidence_errors):
    flags = []
    payloads = [receipt] + list(os_evidence)
    if missing_evidence_errors:
        flags.append("missing required evidence")
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        text = json.dumps(payload, ensure_ascii=False).lower()
        if non_empty_string(payload.get("limitation")):
            flags.append("limitation recorded")
        if any(term in text for term in ("not run", "not_run", "skipped", "blocked", "unable")):
            flags.append("verification skipped or blocked")
        if "missing font" in text:
            flags.append("missing font")
        if "pixel" in text and any(term in text for term in ("different", "failed", "mismatch")):
            flags.append("failed pixel diff")
        blockers = payload.get("blockers")
        try:
            if blockers is not None and int(blockers) > 0:
                flags.append("non-zero blockers")
        except (TypeError, ValueError):
            if blockers:
                flags.append("non-zero blockers")
        gates = payload.get("quality_gates")
        if isinstance(gates, dict):
            for name, gate in gates.items():
                if isinstance(gate, dict) and gate.get("result") == "FAIL":
                    flags.append(f"failed quality gate: {name}")
    return sorted(set(flags))


def validate_truth_claims(receipt, os_evidence, missing_evidence_errors=None, contract=None, state=None):
    errors = []
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]
    claims = receipt.get("claims")
    if not isinstance(claims, list) or not claims:
        return ["claims must be a non-empty list for os-close"]
    refs = collect_evidence_refs(receipt, os_evidence)
    risk_flags = truth_risk_flags(receipt, os_evidence, missing_evidence_errors or [])
    for i, item in enumerate(claims):
        if isinstance(item, str):
            errors.append(f"claims[{i}] must be an object with claim and evidence_refs")
            continue
        if not isinstance(item, dict):
            errors.append(f"claims[{i}] must be an object")
            continue
        text = item.get("claim")
        if not non_empty_string(text):
            errors.append(f"claims[{i}].claim must be a non-empty string")
            continue
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(not non_empty_string(ref) for ref in evidence_refs):
            errors.append(f"claims[{i}].evidence_refs must be a non-empty list of strings")
        else:
            missing = sorted(str(ref) for ref in evidence_refs if str(ref) not in refs)
            if missing:
                errors.append(f"claims[{i}].evidence_refs unknown: {', '.join(missing)}")
        if unqualified_absolute_claim(text) and risk_flags:
            errors.append(
                f"claims[{i}] uses an absolute claim but evidence has limitations: "
                + ", ".join(risk_flags)
            )
        if DESIGN_TOKEN_FULL_CLAIM_RE.search(str(text)) and unqualified_absolute_claim(text):
            ok, reason = full_design_token_coverage_ok(receipt, contract, state, os_evidence)
            if not ok:
                errors.append(f"claims[{i}] claims full design-token coverage without sufficient evidence: {reason}")
        if COST_CLAIM_RE.search(str(text)) and not has_real_llm_token_telemetry(os_evidence):
            errors.append(
                f"claims[{i}] claims lower token/cost usage without real llm_usage telemetry"
            )
        if SUPERIORITY_CLAIM_RE.search(str(text)) and not consumer_superiority_ok(receipt, os_evidence):
            errors.append(
                f"claims[{i}] claims Piloth consumer superiority/value without benchmark evidence proving all mandatory metrics are not worse and at least one consumer-visible metric wins"
            )
    return errors


def list_of_strings(value):
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [
        str(item).strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def evidence_source_refs(evidence):
    refs = []
    source_refs = evidence.get("source_refs")
    if isinstance(source_refs, list):
        for item in source_refs:
            if isinstance(item, str) and item.strip():
                refs.append(item.strip())
            elif isinstance(item, dict):
                file_key = item.get("fileKey") or item.get("file_key")
                node_id = item.get("nodeId") or item.get("node_id") or item.get("frameId") or item.get("frame_id")
                if non_empty_string(file_key) and non_empty_string(node_id):
                    refs.append(f"{file_key}:{node_id}")
    for file_key_name, node_key_name in (
        ("fileKey", "nodeId"),
        ("file_key", "node_id"),
        ("fileKey", "frameId"),
        ("file_key", "frame_id"),
    ):
        file_key = evidence.get(file_key_name)
        node_id = evidence.get(node_key_name)
        if non_empty_string(file_key) and non_empty_string(node_id):
            refs.append(f"{file_key}:{node_id}")
    return sorted(set(refs))


def validate_design_token_coverage(evidence):
    if not isinstance(evidence, dict):
        return ["design token coverage evidence must be an object"]
    if evidence.get("kind") != "design_token_coverage":
        return []
    errors = []
    if not evidence_source_refs(evidence):
        errors.append("design_token_coverage requires Figma/source refs (fileKey+nodeId/frameId or source_refs)")
    covered_groups = list_of_strings(evidence.get("covered_groups"))
    generated_surfaces = list_of_strings(evidence.get("generated_surfaces"))
    if not (
        covered_groups
        or generated_surfaces
        or non_empty_string(evidence.get("surface"))
        or non_empty_string(evidence.get("artifact_path"))
        or non_empty_string(evidence.get("target_path"))
    ):
        errors.append("design_token_coverage requires covered_groups, generated_surfaces, surface, artifact_path, or target_path")
    token_count = evidence.get("token_count")
    if token_count is not None:
        try:
            if int(token_count) < 0:
                errors.append("design_token_coverage.token_count must be non-negative")
        except (TypeError, ValueError):
            errors.append("design_token_coverage.token_count must be numeric when present")
    return errors


def validate_metric_evidence(evidence):
    if not isinstance(evidence, dict) or evidence.get("kind") != "metric":
        return []
    errors = []
    metric_type = str(evidence.get("metric_type") or "").strip()
    if metric_type not in METRIC_TYPES:
        errors.append("metric evidence requires metric_type one of: " + ", ".join(sorted(METRIC_TYPES)))
    if not non_empty_string(evidence.get("metric_name")):
        errors.append("metric evidence requires metric_name")
    for field in (
        "value", "count", "chars", "bytes", "duration_ms",
        "input_tokens", "output_tokens", "total_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd",
        "viewport_width", "viewport_height", "console_error_count",
        "page_error_count", "image_failure_count", "layout_overflow_count",
        "visual_diff_pixels", "visual_diff_ratio",
    ):
        if field in evidence and evidence.get(field) is not None:
            try:
                if float(evidence.get(field)) < 0:
                    errors.append(f"metric evidence {field} must be non-negative")
            except (TypeError, ValueError):
                errors.append(f"metric evidence {field} must be numeric when present")
    if metric_type == "llm_usage" and evidence.get("real_token_telemetry") is not True:
        if not non_empty_string(evidence.get("unavailable_reason")):
            errors.append("llm_usage metric without real_token_telemetry=true requires unavailable_reason")
    if metric_type == "ui_quality":
        ui_fields = (
            "viewport_width", "viewport_height", "required_text_ok",
            "console_errors", "console_error_count", "page_errors",
            "page_error_count", "image_failures", "image_failure_count",
            "horizontal_overflow", "vertical_overflow", "layout_overflow_count",
            "visual_diff_result", "screenshot_path", "comparison_artifact_path",
            "artifact_path",
        )
        if not any(field in evidence for field in ui_fields):
            errors.append("ui_quality metric requires browser/visual check fields")
    return errors


def has_real_llm_token_telemetry(os_evidence):
    return any(
        isinstance(item, dict)
        and item.get("kind") == "metric"
        and item.get("metric_type") == "llm_usage"
        and item.get("real_token_telemetry") is True
        for item in os_evidence
    )


def numeric_metric_value(item, *keys):
    for key in keys:
        if key not in item:
            continue
        try:
            return float(item.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def ui_quality_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict)
        and item.get("kind") == "metric"
        and item.get("metric_type") == "ui_quality"
    ]


def ui_quality_record_failed(item):
    failures = []
    if item.get("required_text_ok") is False:
        failures.append("required_text_ok=false")
    if item.get("horizontal_overflow") is True:
        failures.append("horizontal_overflow=true")
    if item.get("vertical_overflow") is True:
        failures.append("vertical_overflow=true")
    if numeric_metric_value(item, "console_error_count") > 0:
        failures.append("console_error_count>0")
    if numeric_metric_value(item, "page_error_count") > 0:
        failures.append("page_error_count>0")
    if numeric_metric_value(item, "image_failure_count", "image_failures") > 0:
        failures.append("image_failure_count>0")
    if numeric_metric_value(item, "layout_overflow_count") > 0:
        failures.append("layout_overflow_count>0")
    visual = str(item.get("visual_diff_result") or "").strip().lower()
    if visual in {"fail", "failed", "mismatch", "different", "regressed"}:
        failures.append("visual_diff_result=" + visual)
    return failures


def design_token_coverage_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict) and item.get("kind") == "design_token_coverage"
    ]


def design_token_profile_active(contract, receipt=None, state=None):
    for payload in (receipt, contract, state):
        if isinstance(payload, dict) and payload.get("evidence_profile") == "design_tokens":
            return True
    return False


def design_token_generated_surfaces(coverage):
    surfaces = set()
    for item in coverage:
        surfaces |= set(list_of_strings(item.get("generated_surfaces")))
        if non_empty_string(item.get("surface")):
            surfaces.add(str(item.get("surface")).strip())
    return surfaces


def validate_design_token_receipt(receipt, contract, state, os_evidence):
    if not design_token_profile_active(contract, receipt, state):
        return []
    errors = []
    coverage = design_token_coverage_records(os_evidence)
    if not coverage:
        errors.append("evidence_profile=design_tokens requires design_token_coverage evidence")
    if not any(item.get("kind") == "figma_node" for item in os_evidence):
        errors.append("evidence_profile=design_tokens requires figma_node evidence")
    for item in coverage:
        errors.extend(validate_design_token_coverage(item))
    surfaces = design_token_generated_surfaces(coverage)
    if not surfaces and not non_empty_string(receipt.get("limitation")):
        errors.append("design token coverage requires generated_surfaces/surface evidence or a receipt limitation")
    gates = receipt.get("quality_gates") if isinstance(receipt, dict) else None
    if not isinstance(gates, dict) or not isinstance(gates.get("design_token_coverage"), dict):
        errors.append("quality_gates.design_token_coverage is required for evidence_profile=design_tokens")
    return errors


def validate_ui_quality_receipt(receipt, contract, os_evidence):
    if not contract_requires_ui_quality_evidence(contract, receipt):
        return []
    errors = []
    records = ui_quality_records(os_evidence)
    if not records:
        errors.append("UI tasks require ui_quality metric evidence from browser/visual inspection")
    failed = []
    for item in records:
        for reason in ui_quality_record_failed(item):
            failed.append(f"{item.get('id', 'ui_quality')}: {reason}")
    delivery_result = str(receipt.get("result", "") if isinstance(receipt, dict) else "").strip().lower()
    if failed and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
        errors.append("UI quality evidence contains failing checks: " + ", ".join(failed))
    return errors


def full_design_token_coverage_ok(receipt, contract, state, os_evidence):
    if not design_token_profile_active(contract, receipt, state):
        return False, "receipt/contract evidence_profile is not design_tokens"
    coverage = design_token_coverage_records(os_evidence)
    full = [
        item for item in coverage
        if item.get("coverage_scope") == "full_declared_source"
    ]
    if not full:
        return False, "missing design_token_coverage coverage_scope=full_declared_source"
    if not all(evidence_source_refs(item) for item in full):
        return False, "full design-token coverage requires source refs"
    surfaces = design_token_generated_surfaces(full)
    missing_surfaces = sorted(DESIGN_TOKEN_SURFACES - surfaces)
    if missing_surfaces and not non_empty_string(receipt.get("limitation")):
        return False, "missing generated design-token surfaces: " + ", ".join(missing_surfaces)
    return True, ""


def evidence_payload_present(sanitized):
    if any(non_empty_string(sanitized.get(key)) for key in (
        "command", "summary", "artifact", "artifact_path", "target_path",
        "evidence_output", "quality_gate", "gate", "fileKey", "nodeId",
        "frameId", "coverage_scope", "surface", "metric_name", "metric_type",
        "consumer_value_result",
        "browser", "browser_tool", "url", "visual_diff_result",
        "screenshot_path", "comparison_artifact_path",
    )):
        return True
    if any(key in sanitized for key in (
        "required_text_ok", "console_errors", "console_error_count",
        "page_errors", "page_error_count", "image_failures",
        "image_failure_count", "horizontal_overflow", "vertical_overflow",
        "layout_overflow_count", "viewport_width", "viewport_height",
    )):
        return True
    if list_of_strings(sanitized.get("covered_groups")):
        return True
    if list_of_strings(sanitized.get("generated_surfaces")):
        return True
    if evidence_source_refs(sanitized):
        return True
    if isinstance(sanitized.get("options"), list) and sanitized.get("options"):
        return True
    if isinstance(sanitized.get("decisions"), list) and sanitized.get("decisions"):
        return True
    return False


def validate_prototype_evidence(evidence):
    """Validate a prototype evidence record (kind=prototype).

    Prototype's invariant: at least two design options were generated and one
    was chosen, via a valid design method. The human sign-off itself flows
    through the reused human_review round-trip, not here.
    """
    if not isinstance(evidence, dict) or evidence.get("kind") != "prototype":
        return []
    errors = []
    if evidence.get("method") not in PROTOTYPE_METHODS:
        errors.append("prototype evidence requires method one of: " + ", ".join(sorted(PROTOTYPE_METHODS)))
    options = evidence.get("options")
    if not isinstance(options, list):
        errors.append("prototype evidence requires an options list")
        return errors
    ids = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict) or not non_empty_string(opt.get("id")):
            errors.append(f"prototype options[{i}] requires an id")
            continue
        ids.append(opt.get("id"))
    if len(ids) < 2:
        errors.append("prototype evidence requires >=2 options with ids")
    chosen = evidence.get("chosen")
    if not non_empty_string(chosen):
        errors.append("prototype evidence requires a chosen option id")
    elif ids and chosen not in ids:
        errors.append("prototype chosen must be one of the generated option ids")
    return errors


def validate_discovery_evidence(evidence):
    """Validate a discovery evidence record (kind=discovery).

    Discovery is a judgment gate the phase runs up front; the only mechanical
    check is that the confirmed decisions are recorded as evidence the
    Traceability gate can trace to. Each decision names its question, answer and
    source (user vs a pre-ticked "decide for me" default).
    """
    if not isinstance(evidence, dict) or evidence.get("kind") != "discovery":
        return []
    errors = []
    decisions = evidence.get("decisions")
    if not isinstance(decisions, list) or not decisions:
        errors.append("discovery evidence requires a non-empty decisions list")
        return errors
    for i, dec in enumerate(decisions):
        if not isinstance(dec, dict):
            errors.append(f"discovery decisions[{i}] must be an object")
            continue
        if not non_empty_string(dec.get("q")):
            errors.append(f"discovery decisions[{i}] requires a question 'q'")
        if not non_empty_string(dec.get("answer")):
            errors.append(f"discovery decisions[{i}] requires an 'answer'")
    return errors


def sanitize_os_evidence_payload(payload):
    if not isinstance(payload, dict):
        return None, ["evidence payload must be a JSON object"]
    allowed = {
        "id", "ref", "evidence_ref", "kind", "command", "result", "summary",
        "artifact", "path", "tool", "risk", "timeout", "evidence_output",
        "limitation", "quality_gate", "gate", "status", "blockers",
        "fileKey", "file_key", "nodeId", "node_id", "frameId", "frame_id",
        "token_count", "covered_groups", "surface", "artifact_path",
        "target_path", "source_refs", "coverage_scope", "generated_surfaces",
        "verification", "limitations",
        "method", "options", "chosen", "chosen_rationale",
        "prototype_doc", "prototype_sha256",
        "discovery_doc", "decisions", "unresolved",
        "metric_type", "metric_name", "phase", "unit", "value", "count",
        "chars", "bytes", "duration_ms", "input_tokens", "output_tokens",
        "total_tokens", "real_token_telemetry", "unavailable_reason",
        "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd",
        "model", "pricing_source", "window_start", "subagent_scope",
        "consumer_value_result", "all_mandatory_not_worse",
        "consumer_visible_win", "mandatory_regressions", "wins",
        "viewport_width", "viewport_height", "browser", "browser_tool", "url",
        "required_text_ok", "console_errors", "console_error_count",
        "page_errors", "page_error_count", "image_failures", "image_failure_count",
        "horizontal_overflow", "vertical_overflow", "layout_overflow_count",
        "visual_diff_result", "visual_diff_pixels", "visual_diff_ratio",
        "screenshot_path", "baseline_screenshot_path", "comparison_artifact_path",
    }
    output_fields = {"stdout", "stderr", "output", "raw_output", "full_output", "logs", "log", "env", "environment"}
    sanitized = {}
    for key, value in payload.items():
        if key in output_fields:
            sanitized["output_redacted"] = True
            continue
        if key == "task_id":
            continue
        if key not in allowed:
            continue
        if SECRET_KEY_RE.search(str(key)) and key not in SAFE_OS_EVIDENCE_METADATA_KEYS:
            sanitized[str(key)] = "[redacted]"
        else:
            sanitized[str(key)] = sanitize_state_value(value, limit=1000)
    kind = sanitized.get("kind")
    if kind is not None and kind not in OS_EVIDENCE_KINDS:
        return None, ["kind must be one of: " + ", ".join(sorted(OS_EVIDENCE_KINDS))]
    if not evidence_payload_present(sanitized):
        return None, ["evidence must include command, summary, artifact, safe metadata, evidence_output, quality_gate, or gate"]
    coverage_errors = validate_design_token_coverage(sanitized)
    if coverage_errors:
        return None, coverage_errors
    metric_errors = validate_metric_evidence(sanitized)
    if metric_errors:
        return None, metric_errors
    prototype_errors = validate_prototype_evidence(sanitized)
    if prototype_errors:
        return None, prototype_errors
    discovery_errors = validate_discovery_evidence(sanitized)
    if discovery_errors:
        return None, discovery_errors
    evidence_id = (
        safe_evidence_id(sanitized.get("id"))
        or safe_evidence_id(sanitized.get("ref"))
        or safe_evidence_id(sanitized.get("evidence_ref"))
    )
    if not evidence_id:
        basis = dict(sanitized)
        evidence_id = "ev-" + sha256_json(basis)[:12]
    sanitized["id"] = evidence_id
    sanitized["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sanitized["repo_key"] = REPO_KEY
    return sanitized, []


def metric_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict) and item.get("kind") == "metric"
    ]


def metric_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def metric_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_model_pricing():
    """Load the advisory model price map (USD per MTok). Fail-soft → {} when the
    file is missing or malformed, so telemetry never breaks on a bad price map."""
    data = load_json_file(PILOTHOS_DIR / "runtime" / "model-pricing.json")
    if isinstance(data, dict) and isinstance(data.get("models"), dict):
        return data
    return {}


def model_price(model, pricing=None):
    """Return the price row {input, output, cache_write_5m, cache_read} for a
    model id in USD/MTok, or None when the model is unknown (cost then omitted)."""
    if not non_empty_string(model):
        return None
    pricing = pricing if isinstance(pricing, dict) else load_model_pricing()
    models = pricing.get("models") if isinstance(pricing, dict) else None
    row = models.get(model) if isinstance(models, dict) else None
    return row if isinstance(row, dict) else None


def compute_token_cost_usd(usage, model, pricing=None):
    """Cost of one usage record given a price row, or None when the model is
    unpriced. usage keys: input_tokens/output_tokens/cache_creation_input_tokens/
    cache_read_input_tokens. Cache tiers are priced separately (cache_read ~0.1x,
    cache_write ~1.25x input) — ignoring them would misstate cost badly."""
    row = model_price(model, pricing)
    if row is None:
        return None
    per_mtok = lambda tokens, rate: metric_float(tokens) / 1_000_000.0 * metric_float(rate)
    cost = (
        per_mtok(usage.get("input_tokens"), row.get("input"))
        + per_mtok(usage.get("output_tokens"), row.get("output"))
        + per_mtok(usage.get("cache_creation_input_tokens"), row.get("cache_write_5m"))
        + per_mtok(usage.get("cache_read_input_tokens"), row.get("cache_read"))
    )
    return round(cost, 6)


def parse_iso_timestamp(ts):
    """Parse an ISO-8601 timestamp (accepting a trailing Z) to a datetime, or
    None. Used to window transcript records by the OS run's created_at."""
    if not non_empty_string(ts):
        return None
    text = ts.strip().replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(text)
    except ValueError:
        return None


def transcript_project_slug():
    """Claude Code encodes the project cwd into the transcript dir name by
    replacing '/' and '.' with '-' (e.g. -Users-me-VNG-tools-piloth)."""
    return re.sub(r"[/.]", "-", str(REPO_ROOT.resolve()))


def resolve_transcript_path(argv, hook_input=None):
    """Locate the Claude Code session transcript: explicit --transcript wins,
    then a hook's transcript_path, then the newest *.jsonl for this project.
    Returns a Path or None (None → telemetry unavailable, recorded honestly)."""
    argv = argv or []
    for i, arg in enumerate(argv):
        if arg == "--transcript" and i + 1 < len(argv):
            return pathlib.Path(argv[i + 1]).expanduser()
        if arg.startswith("--transcript="):
            return pathlib.Path(arg.split("=", 1)[1]).expanduser()
    if isinstance(hook_input, dict) and non_empty_string(hook_input.get("transcript_path")):
        return pathlib.Path(hook_input["transcript_path"]).expanduser()
    base = pathlib.Path.home() / ".claude" / "projects" / transcript_project_slug()
    if not base.exists():
        return None
    def _mtime(p):
        try:
            return p.stat().st_mtime
        except OSError:
            return 0
    candidates = sorted(base.glob("*.jsonl"), key=_mtime)
    return candidates[-1] if candidates else None


TRANSCRIPT_USAGE_KEYS = (
    "input_tokens", "output_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens",
)


def sum_transcript_usage(path, since=None, pricing=None):
    """Sum real per-turn `message.usage` from a Claude Code transcript, windowed
    to records at/after `since` (a datetime). Returns a dict with summed usage,
    per-model token totals, a summed cost (or None when any model is unpriced),
    and record/model counts — or None if the file can't be read.

    Attribution is main-session-only: background subagent transcripts are
    separate files and are not summed here (disclosed as subagent_scope)."""
    usage = {k: 0 for k in TRANSCRIPT_USAGE_KEYS}
    per_model_tokens = {}
    records = 0
    cost_total = 0.0
    cost_available = True
    pricing = pricing if isinstance(pricing, dict) else load_model_pricing()
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if since is not None:
                    rec_ts = parse_iso_timestamp(rec.get("timestamp"))
                    if rec_ts is not None and rec_ts < since:
                        continue
                msg = rec.get("message") if isinstance(rec.get("message"), dict) else {}
                u = msg.get("usage") if isinstance(msg, dict) else None
                if not isinstance(u, dict):
                    continue
                records += 1
                row = {k: metric_int(u.get(k)) for k in TRANSCRIPT_USAGE_KEYS}
                for k in TRANSCRIPT_USAGE_KEYS:
                    usage[k] += row[k]
                model = msg.get("model") if non_empty_string(msg.get("model")) else "unknown"
                per_model_tokens[model] = per_model_tokens.get(model, 0) + sum(row.values())
                c = compute_token_cost_usd(row, model, pricing)
                if c is None:
                    cost_available = False
                else:
                    cost_total += c
    except OSError:
        return None
    primary_model = max(per_model_tokens, key=per_model_tokens.get) if per_model_tokens else ""
    return {
        "usage": usage,
        "records": records,
        "models": sorted(per_model_tokens),
        "primary_model": primary_model,
        "cost_usd": round(cost_total, 6) if cost_available else None,
        "pricing_source": pricing.get("source") if isinstance(pricing, dict) else "",
    }


def token_telemetry(argv):
    """Extract real LLM token telemetry from the Claude Code session transcript
    and record it as an `os-evidence kind=metric metric_type=llm_usage
    real_token_telemetry=true` for the active OS run. Windowed to the run's
    created_at; main-session-only (disclosed). Fails soft: no transcript →
    records real_token_telemetry=false + unavailable_reason.

    Usage: token-telemetry [--task <id>] [--transcript <path>]
    """
    argv = argv or []
    task_id = None
    for i, arg in enumerate(argv):
        if arg == "--task" and i + 1 < len(argv):
            task_id = argv[i + 1]
        elif arg.startswith("--task="):
            task_id = arg.split("=", 1)[1]
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "token_telemetry_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    if state.get("status") in {"closed", "sealed"}:
        json_print({"result": "token_telemetry_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]})
        return
    task_id = state["task_id"]
    created_at = state.get("created_at")
    since = parse_iso_timestamp(created_at)
    transcript = resolve_transcript_path(argv)
    summed = sum_transcript_usage(transcript, since=since) if transcript else None

    if not summed or summed.get("records", 0) == 0:
        payload = {
            "task_id": task_id,
            "kind": "metric",
            "metric_type": "llm_usage",
            "metric_name": "session-token-usage",
            "real_token_telemetry": False,
            "unavailable_reason": "no Claude Code transcript usage found for this session (harness may not expose per-turn token telemetry)",
            "subagent_scope": "main_session_only",
            "summary": "token telemetry unavailable",
        }
        result_label = "token_telemetry_unavailable"
    else:
        usage = summed["usage"]
        payload = {
            "task_id": task_id,
            "kind": "metric",
            "metric_type": "llm_usage",
            "metric_name": "session-token-usage",
            "real_token_telemetry": True,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "cache_creation_input_tokens": usage["cache_creation_input_tokens"],
            "cache_read_input_tokens": usage["cache_read_input_tokens"],
            "total_tokens": usage["input_tokens"] + usage["output_tokens"],
            "model": summed.get("primary_model") or "",
            "window_start": created_at or "",
            "subagent_scope": "main_session_only",
            "summary": f"session token telemetry from Claude Code transcript ({summed['records']} turns)",
        }
        if summed.get("cost_usd") is not None:
            payload["cost_usd"] = summed["cost_usd"]
            if non_empty_string(summed.get("pricing_source")):
                payload["pricing_source"] = summed["pricing_source"]
        result_label = "token_telemetry_recorded"

    evidence, errors = sanitize_os_evidence_payload(payload)
    if errors:
        json_print({"result": "token_telemetry_rejected", "task_id": task_id, "errors": errors})
        return
    evidence["task_id"] = task_id
    append_os_evidence(task_id, evidence)
    state.setdefault("lifecycle", [])
    if "tool/evidence" not in state["lifecycle"]:
        state["lifecycle"].append("tool/evidence")
    state["evidence_count"] = len(os_evidence_records(task_id))
    save_os_state(state)
    out = {
        "result": result_label,
        "task_id": task_id,
        "evidence_ref": evidence["id"],
        "transcript": str(transcript) if transcript else None,
        "window_start": created_at or "",
        "real_token_telemetry": bool(payload.get("real_token_telemetry")),
        "subagent_scope": "main_session_only",
    }
    if result_label == "token_telemetry_recorded":
        out.update({
            "records": summed["records"],
            "models": summed["models"],
            "model": payload.get("model", ""),
            "tokens": summed["usage"],
            "cost_usd": payload.get("cost_usd", "unavailable_unpriced_model"),
        })
    json_print(out)


def cost_ledger_summary(os_evidence):
    metrics = metric_records(os_evidence)
    real_llm = [item for item in metrics if item.get("metric_type") == "llm_usage" and item.get("real_token_telemetry") is True]
    unavailable_llm = [
        item for item in metrics
        if item.get("metric_type") == "llm_usage" and item.get("real_token_telemetry") is not True
    ]
    benchmark = [
        item for item in metrics
        if item.get("metric_type") == "benchmark"
    ]
    real_tokens = None
    if real_llm:
        real_tokens = {
            "input_tokens": sum(metric_int(item.get("input_tokens")) for item in real_llm),
            "output_tokens": sum(metric_int(item.get("output_tokens")) for item in real_llm),
            "total_tokens": sum(metric_int(item.get("total_tokens")) for item in real_llm),
            "cache_creation_input_tokens": sum(metric_int(item.get("cache_creation_input_tokens")) for item in real_llm),
            "cache_read_input_tokens": sum(metric_int(item.get("cache_read_input_tokens")) for item in real_llm),
            "cost_usd": round(sum(metric_float(item.get("cost_usd")) for item in real_llm), 6),
        }
    return {
        "schema_version": 1,
        "metric_records": len(metrics),
        "real_tokens": real_tokens if real_tokens is not None else "unavailable",
        "real_token_telemetry": bool(real_llm),
        "token_unavailable_reasons": sorted(set(
            str(item.get("unavailable_reason", "")).strip()
            for item in unavailable_llm
            if str(item.get("unavailable_reason", "")).strip()
        )),
        "tool_output_chars": sum(metric_int(item.get("chars")) for item in metrics if item.get("metric_type") == "tool_output"),
        "context_loads": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "context_load"),
        "commands": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "command"),
        "retries": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "retry"),
        "repairs": sum(metric_int(item.get("count") or 1) for item in metrics if item.get("metric_type") == "repair"),
        "duration_ms": sum(metric_int(item.get("duration_ms")) for item in metrics),
        "benchmark_results": [
            {
                "id": item.get("id"),
                "result": item.get("consumer_value_result", ""),
                "all_mandatory_not_worse": bool(item.get("all_mandatory_not_worse")),
                "consumer_visible_win": bool(item.get("consumer_visible_win")),
                "real_token_telemetry": bool(item.get("real_token_telemetry")),
                "wins": item.get("wins", []),
                "mandatory_regressions": item.get("mandatory_regressions", []),
            }
            for item in benchmark
        ],
    }


def budget_status(contract, os_evidence):
    """Advisory-only budget view: compare real spend (from token telemetry) to an
    optional contract budget.max_usd. Surfaced in os-status / os-report; it NEVER
    blocks os-close. Returns advisory_unavailable when no ceiling is set or no
    real-token cost has been recorded yet."""
    budget = contract.get("budget") if isinstance(contract, dict) else None
    max_usd = None
    if isinstance(budget, dict) and budget.get("max_usd") is not None:
        try:
            max_usd = float(budget.get("max_usd"))
        except (TypeError, ValueError):
            max_usd = None
    if max_usd is None:
        return {"status": "advisory_unavailable", "reason": "no budget.max_usd in contract"}
    ledger = cost_ledger_summary(os_evidence)
    real = ledger.get("real_tokens")
    spent = real.get("cost_usd") if isinstance(real, dict) else None
    if not isinstance(spent, (int, float)):
        return {
            "status": "advisory_unavailable",
            "reason": "no real token telemetry / cost recorded yet (run token-telemetry)",
            "max_usd": max_usd,
        }
    return {
        "advisory": True,
        "max_usd": max_usd,
        "spent_usd": round(float(spent), 6),
        "remaining_usd": round(max_usd - float(spent), 6),
        "over_budget": float(spent) > max_usd,
        "note": "advisory only — does not block os-close",
    }


def record_checkpoint_from_evidence(state, evidence):
    phase = str(evidence.get("phase") or "").strip()
    if not phase:
        return
    checkpoints = state.setdefault("checkpoints", [])
    checkpoints.append({
        "phase": phase,
        "evidence_ref": evidence.get("id", ""),
        "kind": evidence.get("kind", ""),
        "recorded_at": evidence.get("recorded_at", ""),
        "summary": evidence.get("summary", ""),
        "metric_type": evidence.get("metric_type", ""),
    })


def update_state_runtime_cost(state, task_id):
    evidence = os_evidence_records(task_id)
    state["cost_ledger"] = cost_ledger_summary(evidence)
    return state["cost_ledger"]


def consumer_superiority_payloads(receipt, os_evidence):
    payloads = []
    if isinstance(receipt, dict) and isinstance(receipt.get("consumer_superiority"), dict):
        payloads.append(receipt.get("consumer_superiority"))
    for item in os_evidence:
        if isinstance(item, dict) and item.get("kind") == "metric" and item.get("metric_type") == "benchmark":
            payloads.append(item)
    return payloads


def consumer_superiority_ok(receipt, os_evidence):
    for payload in consumer_superiority_payloads(receipt, os_evidence):
        result = str(payload.get("result") or payload.get("consumer_value_result") or "").strip().lower()
        if (
            result in SUPERIORITY_PASS_RESULTS
            and payload.get("all_mandatory_not_worse") is True
            and payload.get("consumer_visible_win") is True
            and (
                payload.get("real_token_telemetry") is True
                or has_real_llm_token_telemetry(os_evidence)
            )
        ):
            return True
    return False


def os_start_schema_payload():
    """Machine-readable os-start request schema (SSOT for the doc page).

    Mirrors `installer explain`: field -> {required, default, allowed, aliases}.
    """
    return {
        "result": "os_start_schema",
        "note": "All fields optional; a bare {} opens a repo-local run. See runtime/os-control-plane.md.",
        "fields": {
            "task_id": {"required": False, "default": "task-<sha256[:12]> from intent", "aliases": ["id", "request_id"]},
            "intent": {"required": False, "default": "repo-local OS task", "aliases": ["task_scope", "summary", "title"], "note": "becomes contract.task_scope"},
            "task_signal": {"required": False, "default": "not_applicable", "allowed": sorted(ASSET_ROUTING_SIGNALS)},
            "target_repo": {"required": False, "default": "<control-plane repo>", "note": "absolute path; must exist and not be inside pilothOS/memory/state"},
            "target_kind": {"required": False, "allowed": sorted(TARGET_KINDS), "note": "cross-checked vs actual git detection"},
            "target_paths": {"required": False, "default": ["**/*"], "aliases": ["allowed_paths", "affected_paths", "paths"], "note": "each must be a safe glob"},
            "affected_layers": {"required": False, "default": "derived from paths", "note": "contract requires a non-empty list"},
            "expected_evidence": {"required": False, "default": ["manual verification receipt"]},
            "out_of_scope_paths": {"required": False, "default": []},
            "evidence_profile": {"required": False, "default": "generic", "allowed": sorted(EVIDENCE_PROFILES)},
            "mode": {"required": False, "default": "adaptive", "allowed": sorted(OS_MODE_REQUESTS), "aliases": ["os_mode", "piloth_mode"], "note": "adaptive/auto resolve to lean|standard|strict"},
            "operational_preset": {"required": False, "allowed": sorted(OPERATIONAL_PRESETS)},
            "target_footprint_policy": {"required": False, "allowed": sorted(TARGET_FOOTPRINT_POLICIES), "aliases": ["footprint_policy"], "default": "no_control_plane_files if explicit target else repo_local_state_allowed"},
            "execution_strategy": {"required": False, "default": "controlled_target if explicit target else repo_local"},
            "budget": {"required": False, "note": "object; budget.max_usd is an advisory cost ceiling"},
            "success_metrics": {"required": False},
            "requires_prototype": {"required": False, "default": False, "note": "true also forces requires_human_review"},
            "requires_human_review": {"required": False, "default": False},
            "requires_discovery": {"required": False, "default": False},
            "energy_budget_reason": {"required": "when expected_evidence names a full-suite/broad run", "note": "justify the blast radius of an expensive run"},
        },
    }


def os_start(argv):
    if "--explain" in list(argv):
        json_print(os_start_schema_payload())
        return
    try:
        request, source = json_arg_or_stdin(argv, "os-start")
    except Exception as e:
        json_print({"result": "os_start_rejected", "errors": [str(e)]})
        return
    if not isinstance(request, dict):
        json_print({"result": "os_start_rejected", "errors": ["request must be a JSON object"]})
        return
    if "evidence_profile" in request and str(request.get("evidence_profile")) not in EVIDENCE_PROFILES:
        json_print({
            "result": "os_start_rejected",
            "errors": ["evidence_profile must be one of: " + ", ".join(sorted(EVIDENCE_PROFILES))],
        })
        return
    target, target_errors = resolve_target_repo(request)
    if target_errors:
        json_print({"result": "os_start_rejected", "errors": target_errors})
        return
    task_id = request_task_id(request)
    paths = request_paths(request)
    for pattern in paths:
        if not path_pattern_is_safe(pattern):
            json_print({
                "result": "os_start_rejected",
                "task_id": task_id,
                "errors": [f"target_paths contains unsafe pattern: {pattern}"],
            })
            return
    task_signal = request.get("task_signal") or "not_applicable"
    route = route_task_payload({"task_signal": task_signal})
    scheduler = scheduler_suggest_payload({
        "task_signal": task_signal,
        "affected_paths": paths,
        "intent": request_intent(request),
    })
    contract = build_os_contract(request, route, scheduler, target=target)
    contract_errors = validate_task_contract(contract)
    if contract_errors:
        json_print({"result": "os_start_rejected", "task_id": task_id, "errors": contract_errors})
        return
    health_rows = [health_for_asset(row) for row in scanned_asset_rows()]
    target_snapshot = target_state_snapshot(target)
    state = {
        "schema_version": 2,
        "repo_key": REPO_KEY,
        "task_id": task_id,
        "status": "open",
        "lifecycle": ["intake", "contract", "route"],
        "request": sanitize_state_value(request, limit=1000),
        "request_sha256": sha256_json(sanitize_state_value(request, limit=1000)),
        "request_source": str(source.relative_to(REPO_ROOT)) if source and source.is_relative_to(REPO_ROOT) else str(source or ""),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task_scope": contract["task_scope"],
        "affected_layers": contract["affected_layers"],
        "allowed_paths": contract["allowed_paths"],
        "target_paths": contract["target_paths"],
        "target": target,
        "target_snapshot_sha256": target_snapshot.get("snapshot_sha256", ""),
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "evidence_profile": contract.get("evidence_profile", "generic"),
        "mode": contract.get("mode", "standard"),
        "adaptive_mode": bool(contract.get("adaptive_mode")),
        "mode_decisions": contract.get("mode_decisions", []),
        "execution_strategy": contract.get("execution_strategy", ""),
        "target_footprint_policy": contract.get("target_footprint_policy", ""),
        "budget": contract.get("budget", {}),
        "success_metrics": contract.get("success_metrics", []),
        "benchmark_id": contract.get("benchmark_id", ""),
        "checkpoints": [],
        "cost_ledger": cost_ledger_summary([]),
        "coverage_claims": contract.get("coverage_claims", {}),
        "expected_evidence": contract["expected_evidence"],
        "required_gates": required_gates_for_task(contract, mode=contract.get("mode")),
        "contract": contract,
        "asset_routing": {
            "route": route,
            "asset_count": len(health_rows),
            "unhealthy_assets": [
                {
                    "id": row.get("id"),
                    "status": row.get("status"),
                    "reason": row.get("health_reason", ""),
                }
                for row in health_rows
                if row.get("status") not in {"healthy", "not_applicable"}
            ][:20],
        },
        "scheduler_suggestion": scheduler,
    }
    state_path = save_os_state(state)
    os_state_path(task_id, "contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os_state_path(task_id, "target-snapshot.json").write_text(
        json.dumps(target_snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    repo_contract = dict(contract)
    repo_contract["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    repo_contract["source"] = state_path.relative_to(REPO_ROOT).as_posix()
    MARKER_DIR.mkdir(exist_ok=True)
    repo_state_file("task-contract.json").write_text(
        json.dumps(repo_contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    empty_facts = {
        "changed_files": {},
        "affected_layers": [],
        "has_tests": False,
        "has_docs": False,
        "evidence_commands": [],
        "warnings": [],
    }
    update_diff_fact_derived(empty_facts, contract)
    save_diff_facts({}, empty_facts)
    try:
        repo_state_file("deliver-receipt.json").unlink()
    except OSError:
        pass
    json_print({
        "result": "os_started",
        "task_id": task_id,
        "state_path": state_path.relative_to(REPO_ROOT).as_posix(),
        "contract_path": os_state_path(task_id, "contract.json").relative_to(REPO_ROOT).as_posix(),
        "target_snapshot_path": os_state_path(task_id, "target-snapshot.json").relative_to(REPO_ROOT).as_posix(),
        "active_contract_path": repo_state_file("task-contract.json").as_posix(),
        "target": {
            "target_repo": target.get("target_repo"),
            "target_kind": target.get("target_kind"),
            "target_vcs": target.get("target_vcs"),
            "target_id": target.get("target_id"),
            "baseline_dirty_paths": target_snapshot.get("git_status_short", []),
            "file_count": target_snapshot.get("file_count"),
        },
        "required_gates": state["required_gates"],
        "expected_evidence": contract["expected_evidence"],
        "mode": state["mode"],
        "adaptive_mode": state["adaptive_mode"],
        "mode_decisions": state["mode_decisions"],
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "scheduler": {
            "expected_evidence": scheduler.get("expected_evidence") if isinstance(scheduler, dict) else [],
            "energy_budget": scheduler.get("energy_budget") if isinstance(scheduler, dict) else "",
        },
        "asset_routing": route,
    })


def os_status(argv=None):
    task_id = argv[0] if argv else None
    state, path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_status_missing", "errors": ["no OS run state found"]})
        return
    evidence = os_evidence_records(state.get("task_id"))
    json_print({
        "result": "os_status",
        "task_id": state.get("task_id"),
        "status": state.get("status"),
        "state_path": path.relative_to(REPO_ROOT).as_posix() if path else "",
        "lifecycle": state.get("lifecycle", []),
        "affected_layers": state.get("affected_layers", []),
        "allowed_paths": state.get("allowed_paths", []),
        "target_paths": state.get("target_paths", []),
        "target": state.get("target", {}),
        "evidence_profile": state.get("evidence_profile", "generic"),
        "mode": state.get("mode", ""),
        "adaptive_mode": state.get("adaptive_mode", False),
        "mode_decisions": state.get("mode_decisions", []),
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "budget": state.get("budget", {}),
        "cost_ledger": cost_ledger_summary(evidence),
        "budget_status": budget_status(state.get("contract") or {}, evidence),
        "expected_evidence": state.get("expected_evidence", []),
        "required_gates": state.get("required_gates", []),
        "phase_plan_suggestion": (state.get("contract") or {}).get("phase_plan_suggestion", {}),
        "model_hints": (state.get("contract") or {}).get("model_hints", {}),
        "requires_prototype": bool((state.get("contract") or {}).get("requires_prototype")),
        "requires_discovery": bool((state.get("contract") or {}).get("requires_discovery")),
        "prototype": state.get("prototype", {}),
        "human_review": state.get("human_review", {}),
        "discovery_recorded": latest_evidence_of_kind(evidence, "discovery") is not None,
        "evidence_count": len(evidence),
        "seal_sha256": state.get("seal_sha256", ""),
    })


def os_evidence(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "os-evidence")
    except Exception as e:
        json_print({"result": "os_evidence_rejected", "errors": [str(e)]})
        return
    task_id = payload.get("task_id") if isinstance(payload, dict) else None
    state, state_path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_evidence_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    if state.get("status") in {"closed", "sealed"}:
        json_print({"result": "os_evidence_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]})
        return
    evidence, errors = sanitize_os_evidence_payload(payload)
    if errors:
        json_print({"result": "os_evidence_rejected", "task_id": state.get("task_id"), "errors": errors})
        return
    task_id = state["task_id"]
    evidence["task_id"] = task_id
    evidence_path = append_os_evidence(task_id, evidence)
    facts = load_diff_facts({})
    facts.setdefault("evidence_commands", []).append({
        "command": evidence.get("command") or evidence.get("summary") or evidence.get("artifact") or evidence["id"],
        "result": evidence.get("result") or evidence.get("status") or "recorded",
        "recorded_at": evidence["recorded_at"],
        "evidence_ref": evidence["id"],
    })
    update_diff_fact_derived(facts, state.get("contract"))
    save_diff_facts({}, facts)
    state.setdefault("lifecycle", [])
    if "tool/evidence" not in state["lifecycle"]:
        state["lifecycle"].append("tool/evidence")
    record_checkpoint_from_evidence(state, evidence)
    state["evidence_count"] = len(os_evidence_records(task_id))
    update_state_runtime_cost(state, task_id)
    save_os_state(state)
    json_print({
        "result": "os_evidence_recorded",
        "task_id": task_id,
        "evidence_ref": evidence["id"],
        "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
        "sanitized": bool(evidence.get("output_redacted")),
    })


def write_active_receipt(receipt):
    MARKER_DIR.mkdir(exist_ok=True)
    receipt = dict(receipt)
    receipt["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    repo_state_file("deliver-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt, repo_state_file("deliver-receipt.json")


def record_receipt_seal(receipt, contract, facts):
    previous = latest_receipt_seal_hash()
    seal = build_receipt_seal(receipt, contract, facts, previous)
    seal["result"] = "receipt_sealed"
    RECEIPT_SEALS.parent.mkdir(parents=True, exist_ok=True)
    with open(RECEIPT_SEALS, "a", encoding="utf-8") as f:
        f.write(json.dumps(seal, ensure_ascii=False, sort_keys=True) + "\n")
    seal["recorded_to"] = RECEIPT_SEALS.relative_to(REPO_ROOT).as_posix()
    return seal


def cross_project_enforcement_advisory(active_facts, target_diff):
    """Non-blocking advisory when hooks likely did not fire on the target.

    If diff-facts (populated only by the target's own PostToolUse hook) is empty
    yet the git/manifest target-diff shows changes, the run was almost certainly
    driven from a different session/repo, so the target's Stop-time deliver gate
    never ran. Enforcement then rests on the target-diff alone. Returns an
    advisory string (or "" when coverage looks normal).
    """
    if not (isinstance(active_facts, dict) and isinstance(target_diff, dict)):
        return ""
    if active_facts.get("changed_files") or not target_diff.get("changed_paths"):
        return ""
    return (
        "diff-facts empty but target-diff shows changes: the target's PostToolUse/"
        "Stop hooks likely did not fire (task driven from another session). "
        "Enforcement relied on the git/manifest target-diff only; run inside the "
        "target's own session for full hook coverage."
    )


def os_close_result(receipt, task_id=None, dry_run=False):
    state, state_path = load_os_state(task_id or (receipt.get("task_id") if isinstance(receipt, dict) else None))
    errors = []
    if not state:
        return {"result": "os_close_rejected", "errors": ["no active OS run; call os-start first"]}
    if state.get("status") in {"closed", "sealed"}:
        return {"result": "os_close_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]}
    contract = state.get("contract")
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    active_facts = load_diff_facts({})
    if should_use_v1_target_diff(state):
        target_diff = target_diff_from_active_facts(state, active_facts)
    else:
        target_diff = target_changed_paths(state)
    if not dry_run:
        os_state_path(state["task_id"], "target-diff.json").write_text(
            json.dumps(target_diff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    facts = facts_from_target_diff(target_diff, active_facts)
    enforcement_advisory = cross_project_enforcement_advisory(active_facts, target_diff)
    if enforcement_advisory:
        state["enforcement_advisory"] = enforcement_advisory
    os_evidence = os_evidence_records(state["task_id"])
    errors.extend(validate_deliver_receipt(receipt, contract, facts))
    errors.extend(validate_target_receipt_coverage(receipt, target_diff))
    required_gates = state.get("required_gates") or required_gates_for_task(contract, receipt, mode=state.get("mode"))
    if isinstance(contract, dict) and contract.get("requires_human_review") and "human_review" not in required_gates:
        required_gates = list(required_gates) + ["human_review"]
    errors.extend(validate_required_quality_gates(receipt, required_gates))
    hr_errors, hr_summary = validate_human_review_gate(state, contract, receipt, os_evidence)
    errors.extend(hr_errors)
    state["human_review"] = hr_summary
    if hr_summary.get("unresolved"):
        state["repair_required"] = True
        state["open_review_findings"] = hr_summary["unresolved"]
        state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["review", "repair"]))
    if isinstance(contract, dict) and contract.get("requires_prototype") and "prototype" not in required_gates:
        required_gates = list(required_gates) + ["prototype"]
        errors.extend(validate_required_quality_gates(receipt, ["prototype"]))
    proto_summary = validate_prototype_gate(state, contract, receipt, os_evidence)
    state["prototype"] = proto_summary
    if proto_summary.get("result") == "FAIL":
        errors.append("prototype gate failed: " + str(proto_summary.get("reason", "prototype evidence incomplete")))
        state["prototype_incomplete"] = proto_summary.get("reason", "")
        state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["prototype", "repair"]))
    missing_evidence = validate_expected_evidence_present(contract, receipt, facts, os_evidence)
    errors.extend(missing_evidence)
    errors.extend(validate_design_token_receipt(receipt, contract, state, os_evidence))
    errors.extend(validate_ui_quality_receipt(receipt, contract, os_evidence))
    errors.extend(validate_truth_claims(receipt, os_evidence, missing_evidence, contract=contract, state=state))
    target_footprint = target_footprint_report(state, target_diff)
    if target_footprint.get("result") != "target_footprint_passed":
        errors.extend(target_footprint.get("errors") or ["target footprint policy failed"])
    janitor = artifact_janitor_result(fix=False, root=REPO_ROOT)
    target_janitor = target_janitor_result(state, fix=False)
    if janitor.get("result") != "artifact_janitor_passed":
        errors.append("artifact janitor found local artifacts; run artifact-janitor --fix only if explicit cleanup is intended")
    target = state.get("target") if isinstance(state, dict) else {}
    if (
        isinstance(target, dict)
        and target.get("target_repo") != str(REPO_ROOT.resolve())
        and target_janitor.get("result") != "artifact_janitor_passed"
    ):
        errors.append("target artifact janitor found local artifacts; run artifact-janitor --target <path> --fix only if explicit cleanup is intended")
    if dry_run:
        result = {
            "result": "os_close_dry_run",
            "task_id": state["task_id"],
            "would_pass": not errors,
            "errors": errors,
            "required_gates": required_gates,
            "janitor": janitor,
            "target_janitor": target_janitor,
            "target_footprint": target_footprint,
        }
        if enforcement_advisory:
            result["enforcement_advisory"] = enforcement_advisory
        return result
    if errors:
        state["status"] = "close_rejected"
        state["last_close_errors"] = errors
        state["last_janitor"] = janitor
        state["last_target_janitor"] = target_janitor
        state["last_target_footprint"] = target_footprint
        state["last_target_diff_sha256"] = target_diff.get("diff_sha256", "")
        save_os_state(state)
        return {
            "result": "os_close_rejected",
            "task_id": state["task_id"],
            "errors": errors,
            "janitor": janitor,
            "target_janitor": target_janitor,
            "target_footprint": target_footprint,
            "target_diff": target_diff,
            "state_path": state_path.relative_to(REPO_ROOT).as_posix() if state_path else "",
            "enforcement_advisory": enforcement_advisory,
        }
    receipt, receipt_path = write_active_receipt(receipt)
    save_diff_facts({}, facts)
    seal = record_receipt_seal(receipt, contract, facts)
    target_seal = build_target_seal(state, receipt, target_diff)
    os_state_path(state["task_id"], "target-seal.json").write_text(
        json.dumps(target_seal, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state["status"] = "closed"
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + [
        "quality gates",
        "receipt",
        "seal",
        "janitor",
    ]))
    state["closed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["receipt_sha256"] = sha256_json(receipt)
    state["seal_sha256"] = seal.get("seal_sha256")
    state["seal"] = seal
    state["target_diff_sha256"] = target_diff.get("diff_sha256", "")
    state["target_seal_sha256"] = target_seal.get("target_seal_sha256", "")
    state["target_seal"] = target_seal
    state["receipt_path"] = receipt_path.as_posix()
    state["janitor"] = janitor
    state["target_janitor"] = target_janitor
    state["target_footprint"] = target_footprint
    state["cost_ledger"] = cost_ledger_summary(os_evidence)
    state["consumer_superiority"] = receipt.get("consumer_superiority", {})
    save_os_state(state)
    control = control_plane_check_result(active_policy="always")
    if control.get("result") != "control_plane_passed":
        state["status"] = "close_rejected"
        state["last_control_plane"] = control
        save_os_state(state)
        return {
            "result": "os_close_rejected",
            "task_id": state["task_id"],
            "errors": ["control-plane-check failed"],
            "control_plane": control,
            "seal_sha256": seal.get("seal_sha256"),
            "target_seal_sha256": target_seal.get("target_seal_sha256"),
            "recorded_to": seal.get("recorded_to"),
        }
    state["status"] = "sealed"
    state["control_plane"] = control
    # Auto-clean rác đĩa (Nhóm A) sau khi seal thành công. Run vừa seal là
    # active + mới nhất nên luôn được retention giữ lại; fail-soft tuyệt đối —
    # lỗi dọn dẹp KHÔNG bao giờ làm hỏng os-close.
    try:
        state["state_janitor"] = state_janitor_result(fix=True)
    except Exception as e:
        state["state_janitor"] = {"result": "state_janitor_error", "reason": str(e)}
    save_os_state(state)
    return {
        "result": "os_closed",
        "task_id": state["task_id"],
        "state_path": os_state_path(state["task_id"]).relative_to(REPO_ROOT).as_posix(),
        "receipt_path": receipt_path.as_posix(),
        "seal_sha256": seal.get("seal_sha256"),
        "target_seal_sha256": target_seal.get("target_seal_sha256"),
        "recorded_to": seal.get("recorded_to"),
        "required_gates": required_gates,
        "mode": state.get("mode", ""),
        "cost_ledger": state.get("cost_ledger", {}),
        "janitor": janitor,
        "target_janitor": target_janitor,
        "target_footprint": target_footprint,
        "target_diff_path": os_state_path(state["task_id"], "target-diff.json").relative_to(REPO_ROOT).as_posix(),
        "target_seal_path": os_state_path(state["task_id"], "target-seal.json").relative_to(REPO_ROOT).as_posix(),
        "control_plane": control.get("result"),
        "state_janitor": state.get("state_janitor"),
        "enforcement_advisory": enforcement_advisory,
    }


def os_close(argv):
    args = list(argv)
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args = [a for a in args if a != "--dry-run"]
    try:
        receipt, _ = json_arg_or_stdin(args, "os-close")
    except Exception as e:
        json_print({"result": "os_close_rejected", "errors": [str(e)]})
        return
    if not isinstance(receipt, dict):
        json_print({"result": "os_close_rejected", "errors": ["receipt must be a JSON object"]})
        return
    json_print(os_close_result(receipt, dry_run=dry_run))


def review_request(argv):
    """Emit the review-request artifact for the active OS run (Review state).

    Accepts an optional task id, or a JSON payload {task_id, questions}.
    """
    payload = {}
    task_id = None
    if argv:
        arg = argv[0].strip()
        if arg.startswith("{"):
            try:
                payload = json.loads(arg)
            except Exception as e:
                json_print({"result": "review_request_rejected", "errors": [str(e)]})
                return
            task_id = payload.get("task_id")
        else:
            task_id = argv[0]
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "review_request_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    task_id = state["task_id"]
    contract = state.get("contract") or {}
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    required_gates = state.get("required_gates") or required_gates_for_task(contract, None, mode=state.get("mode"))
    if isinstance(contract, dict) and contract.get("requires_human_review") and "human_review" not in required_gates:
        required_gates = list(required_gates) + ["human_review"]
    changed = sorted(facts_paths(load_diff_facts({}), None))
    contract_path = os_state_path(task_id, "contract.json")
    body = {
        "schema_version": 1,
        "kind": "review_request",
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "under_review": {
            "contract_path": contract_path.relative_to(REPO_ROOT).as_posix() if contract_path.exists() else "",
            "changed_files": changed,
        },
        "gates": required_gates,
        "questions": payload.get("questions") if isinstance(payload.get("questions"), list) else [],
        "requested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    body["request_sha256"] = sha256_json({
        "task_id": task_id, "under_review": body["under_review"],
        "gates": required_gates, "questions": body["questions"],
    })
    path = os_state_path(task_id, "review-request.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["review"]))
    save_os_state(state)
    json_print({
        "result": "review_requested",
        "task_id": task_id,
        "gates": required_gates,
        "review_request_path": path.relative_to(REPO_ROOT).as_posix(),
        "request_sha256": body["request_sha256"],
    })


def review_feedback(argv):
    """Ingest a structured human-review round, record it as evidence, update state."""
    try:
        payload, _ = json_arg_or_stdin(argv, "review-feedback")
    except Exception as e:
        json_print({"result": "review_feedback_rejected", "errors": [str(e)]})
        return
    if not isinstance(payload, dict):
        json_print({"result": "review_feedback_rejected", "errors": ["feedback must be a JSON object"]})
        return
    state, _ = load_os_state(payload.get("task_id"))
    if not state:
        json_print({"result": "review_feedback_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    task_id = state["task_id"]
    errors = validate_review_feedback(payload)
    if errors:
        json_print({"result": "review_feedback_rejected", "task_id": task_id, "errors": errors})
        return
    existing = review_feedback_records(task_id)
    try:
        review_round = int(payload.get("review_round"))
    except (TypeError, ValueError):
        review_round = len(existing) + 1
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = sanitize_state_value({
        "schema_version": 1,
        "kind": "human_review",
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "reviewer": payload.get("reviewer") or "",
        "review_round": review_round,
        "verdict": payload.get("verdict"),
        "finalized": bool(payload.get("finalized")),
        "message": payload.get("message") or "",
        "findings": payload.get("findings") or [],
        "recorded_at": now,
    }, limit=4000)
    append_review_feedback(task_id, record)
    unresolved = [
        finding.get("id")
        for finding in record["findings"]
        if isinstance(finding, dict)
        and finding.get("severity") in REVIEW_BLOCKING_SEVERITIES
        and finding.get("disposition") == "request-changes"
    ]
    append_os_evidence(task_id, {
        "id": f"hr-round-{review_round}",
        "kind": "human_review",
        "review_round": review_round,
        "verdict": record["verdict"],
        "finalized": record["finalized"],
        "unresolved": unresolved,
        "reviewer": record["reviewer"],
        "recorded_at": now,
    })
    lifecycle_add = ["review"] + (["repair"] if unresolved else [])
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + lifecycle_add))
    if unresolved:
        state["repair_required"] = True
        state["open_review_findings"] = unresolved
    save_os_state(state)
    json_print({
        "result": "review_feedback_recorded",
        "task_id": task_id,
        "review_round": review_round,
        "verdict": record["verdict"],
        "finalized": record["finalized"],
        "unresolved": unresolved,
    })


def review_verify(argv):
    """Read-only status of the human_review gate for the active OS run."""
    state, _ = load_os_state(argv[0] if argv else None)
    if not state:
        json_print({"result": "review_verify_failed", "errors": ["no active OS run"]})
        return
    contract = state.get("contract") or {}
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    os_evidence = os_evidence_records(state["task_id"])
    hr_errors, hr_summary = validate_human_review_gate(state, contract, {}, os_evidence)
    json_print({
        "result": "review_verified" if not hr_errors else "review_incomplete",
        "task_id": state["task_id"],
        "human_review": hr_summary,
        "errors": hr_errors,
    })


def os_verify(argv):
    task_id = argv[0] if argv else None
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "os_verify_failed", "errors": ["no OS run state found"]})
        return
    seal = state.get("seal")
    if not isinstance(seal, dict):
        json_print({"result": "os_verify_failed", "task_id": state.get("task_id"), "errors": ["OS run has no recorded seal"]})
        return
    receipt, _ = load_deliver_receipt({})
    if receipt is None:
        json_print({"result": "os_verify_failed", "task_id": state.get("task_id"), "errors": ["missing active deliver receipt"]})
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    current = build_receipt_seal(receipt, contract, facts, seal.get("previous_seal_sha256", ""))
    control_comparisons = {
        "receipt_sha256": current.get("receipt_sha256") == seal.get("receipt_sha256"),
        "contract_sha256": current.get("contract_sha256") == seal.get("contract_sha256"),
        "diff_facts_sha256": current.get("diff_facts_sha256") == seal.get("diff_facts_sha256"),
        "changed_files": current.get("changed_files") == seal.get("changed_files"),
        "seal_sha256": current.get("seal_sha256") == seal.get("seal_sha256"),
    }
    target_expected = state.get("target_seal")
    if not isinstance(target_expected, dict):
        target_expected = load_json_file(os_state_path(state.get("task_id", ""), "target-seal.json"))
    target_comparisons = {}
    current_target_seal = {}
    if isinstance(target_expected, dict):
        if should_use_v1_target_diff(state):
            current_target_diff = target_diff_from_active_facts(state, facts)
        else:
            current_target_diff = target_changed_paths(state)
        current_target_seal = build_target_seal(state, receipt, current_target_diff)
        target_comparisons = {
            "target_metadata": (
                current_target_seal.get("target_repo") == target_expected.get("target_repo")
                and current_target_seal.get("target_id") == target_expected.get("target_id")
                and current_target_seal.get("target_kind") == target_expected.get("target_kind")
            ),
            "changed_paths": current_target_seal.get("changed_paths") == target_expected.get("changed_paths"),
            "deleted_files": current_target_seal.get("deleted_files") == target_expected.get("deleted_files"),
            "changed_files": current_target_seal.get("changed_files") == target_expected.get("changed_files"),
            "target_diff_sha256": current_target_seal.get("target_diff_sha256") == target_expected.get("target_diff_sha256"),
            "target_seal_sha256": current_target_seal.get("target_seal_sha256") == target_expected.get("target_seal_sha256"),
        }
    else:
        target_comparisons = {"target_seal": False}
    control_errors = [name for name, ok in control_comparisons.items() if not ok]
    target_errors = [name for name, ok in target_comparisons.items() if not ok]
    errors = [f"control_plane.{name}" for name in control_errors] + [f"target.{name}" for name in target_errors]
    json_print({
        "result": "os_verify_passed" if not errors else "os_verify_failed",
        "task_id": state.get("task_id"),
        "comparisons": {
            "control_plane": control_comparisons,
            "target": target_comparisons,
        },
        "errors": errors,
        "current_seal_sha256": current.get("seal_sha256"),
        "expected_seal_sha256": seal.get("seal_sha256"),
        "current_target_seal_sha256": current_target_seal.get("target_seal_sha256", ""),
        "expected_target_seal_sha256": target_expected.get("target_seal_sha256", "") if isinstance(target_expected, dict) else "",
    })


def os_report(argv):
    task_id = argv[0] if argv else None
    state, path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_report_missing", "errors": ["no OS run state found"]})
        return
    evidence = os_evidence_records(state.get("task_id"))
    receipt, receipt_path = load_deliver_receipt({})
    target_diff = load_json_file(os_state_path(state.get("task_id", ""), "target-diff.json"))
    target_seal = state.get("target_seal")
    if not isinstance(target_seal, dict):
        target_seal = load_json_file(os_state_path(state.get("task_id", ""), "target-seal.json"))
    target_footprint = state.get("target_footprint")
    if not isinstance(target_footprint, dict) and isinstance(target_diff, dict):
        target_footprint = target_footprint_report(state, target_diff)
    superiority_payloads = consumer_superiority_payloads(receipt or {}, evidence)
    superiority_passed = consumer_superiority_ok(receipt or {}, evidence)
    if superiority_payloads:
        superiority_result = "consumer_value_passed" if superiority_passed else "consumer_value_failed"
    else:
        superiority_result = "not_claimed"
    json_print({
        "result": "os_report",
        "task_id": state.get("task_id"),
        "status": state.get("status"),
        "state_path": path.relative_to(REPO_ROOT).as_posix() if path else "",
        "receipt_path": receipt_path.as_posix() if receipt_path else "",
        "mode": state.get("mode", ""),
        "adaptive_mode": state.get("adaptive_mode", False),
        "mode_decisions": state.get("mode_decisions", []),
        "phase_plan_suggestion": (state.get("contract") or {}).get("phase_plan_suggestion", {}),
        "model_hints": (state.get("contract") or {}).get("model_hints", {}),
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "budget": state.get("budget", {}),
        "success_metrics": state.get("success_metrics", []),
        "cost_ledger": cost_ledger_summary(evidence),
        "budget_status": budget_status(state.get("contract") or {}, evidence),
        "consumer_superiority": {
            "result": superiority_result,
            "payload_count": len(superiority_payloads),
            "policy": "not worse on every mandatory metric, real token telemetry present, and win at least one consumer-visible metric before claiming consumer value",
        },
        "target": state.get("target", {}),
        "target_footprint": target_footprint if isinstance(target_footprint, dict) else {},
        "target_diff": target_diff if isinstance(target_diff, dict) else {},
        "target_seal_sha256": target_seal.get("target_seal_sha256", "") if isinstance(target_seal, dict) else "",
        "required_gates": state.get("required_gates", []),
        "evidence_count": len(evidence),
        "limitations": [
            "exact LLM token usage is unavailable unless llm_usage metrics record real_token_telemetry=true",
            "artifact token estimates are not LLM cost telemetry",
        ],
    })


