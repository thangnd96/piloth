# ------------------------------------------------------- evidence router core

# Evidence Router is deliberately deterministic and read-only.  It chooses the
# smallest evidence plan that can still meet the quality floor; lifecycle
# commands may persist the returned decision separately.

EVIDENCE_ITEM_FIELDS = {
    "type", "source", "required", "freshness", "coverage", "confidence",
    "estimated_cost", "trust", "fallback",
}
ADAPTER_CAPABILITY_STATUS = {"native", "emulated", "unavailable"}
ADAPTER_CAPABILITY_KEYS = (
    "pre_edit_hooks",
    "post_edit_hooks",
    "stop_hooks",
    "subagent_spawn",
    "parallel_execution",
    "role_permissions",
    "model_pinning",
    "token_telemetry",
    "model_telemetry",
    "cost_telemetry",
    "mcp_tool_discovery",
    "approval_controls",
    "sandbox_controls",
    "receipt_enforcement",
    "seal_enforcement",
)
EVIDENCE_ROUTER_ROLLOUT_MODES = {"off", "shadow", "advisory", "enforced"}
EVIDENCE_ROUTER_DEFAULT_BUDGET = {
    "max_roles": 3,
    "max_repair_loops": 1,
    "max_tool_calls": 40,
    "max_files": 200,
    "max_bytes": 2_000_000,
    "tool_timeout_seconds": 120,
}
EVIDENCE_ROUTER_SECRET_KEYS = re.compile(
    r"(secret|token|password|passwd|api[_-]?key|credential|authorization|bearer)",
    re.IGNORECASE,
)
EVIDENCE_ROUTER_NEGATIVE_CLAIM = re.compile(
    r"\b(no|none|never|without|does not|doesn't|isn't|not present|không|chưa)\b",
    re.IGNORECASE,
)
EVIDENCE_ROUTER_SECURITY_TERMS = (
    "security", "vulnerability", "cve", "auth", "authorization", "permission",
    "secret", "credential", "xss", "csrf", "injection", "exploit",
)
EVIDENCE_ROUTER_DESTRUCTIVE_TERMS = (
    "delete", "drop table", "truncate", "destroy", "overwrite", "force push",
    "rm -rf", "production migration", "data migration",
)


def evidence_router_default_matrix():
    """Fail-soft matrix used only when the distributed JSON is unavailable."""
    matrix = {}
    for key, route in TASK_SIGNAL_ROUTES.items():
        matrix[key] = {
            "task_class": {
                "bug fix": "localized_bug",
                "ui/component": "ui_change",
                "api/backend": "backend_change",
                "release/deploy": "release_change",
                "tool/mcp": "tooling_change",
                "architecture": "architecture_change",
                "security": "security_change",
            }.get(key, "small_task"),
            "risk_base": {
                "bug fix": 30,
                "ui/component": 28,
                "api/backend": 38,
                "tool/mcp": 45,
                "architecture": 62,
                "release/deploy": 78,
                "security": 82,
            }.get(key, 10),
            "evidence": [{
                "type": "source",
                "source": "affected source files",
                "required": True,
                "freshness": "current",
                "coverage": "affected_paths",
                "estimated_cost": "low",
                "trust": "source",
                "fallback": "read affected source directly",
            }],
            "context": list(route.get("context_layers", [])),
            "tools": [],
            "verification": ["targeted verification"],
        }
    return {
        "schema_version": 1,
        "quality_floor": {
            "max_non_inferiority_delta_pp": 2,
            "route_confidence": 0.80,
            "specialist_score": 70,
            "team_score": 60,
        },
        "task_matrix": matrix,
    }


def load_evidence_router_matrix():
    data = load_json_file(EVIDENCE_ROUTER_MATRIX)
    if (
        isinstance(data, dict)
        and isinstance(data.get("task_matrix"), dict)
        and isinstance(data.get("quality_floor"), dict)
    ):
        return data, "registry"
    return evidence_router_default_matrix(), "embedded_fallback"


def evidence_router_schema_payload():
    return {
        "result": "evidence_route_schema",
        "read_only": True,
        "input": {
            "intent": "string",
            "locale": "BCP-47 language tag; schema and IDs remain English",
            "task_signal": sorted(ASSET_ROUTING_SIGNALS),
            "affected_paths": ["relative/path"],
            "constraints": ["string"],
            "adapter": ["claude", "codex", "cursor", "antigravity"],
            "adapter_capabilities": {
                key: sorted(ADAPTER_CAPABILITY_STATUS)
                for key in ADAPTER_CAPABILITY_KEYS
            },
            "budget": "object",
            "user_overrides": {
                "rollout": sorted(EVIDENCE_ROUTER_ROLLOUT_MODES),
                "execution_mode": ["single", "team"],
                "kill_switch": "boolean",
            },
        },
        "output_required": [
            "decision_id", "task_class", "risk", "confidence",
            "evidence_plan", "context_plan", "execution_plan", "tool_plan",
            "verification_plan", "budgets", "fallbacks", "limitations",
            "decision_reasons",
        ],
        "quality_floor": {
            "max_non_inferiority_delta_pp": 2,
            "minimum_route_confidence": 0.80,
        },
    }


def load_adapter_capability_registry():
    data = load_json_file(ADAPTER_CAPABILITY_REGISTRY)
    if not isinstance(data, dict):
        data = {}
    adapters = data.get("adapters")
    return adapters if isinstance(adapters, dict) else {}


def adapter_capabilities_payload(payload):
    if not isinstance(payload, dict):
        return {
            "result": "adapter_capabilities_rejected",
            "errors": ["capabilities request must be a JSON object"],
        }
    if payload.get("explain") is True:
        return {
            "result": "adapter_capabilities_schema",
            "read_only": True,
            "statuses": sorted(ADAPTER_CAPABILITY_STATUS),
            "capabilities": list(ADAPTER_CAPABILITY_KEYS),
        }
    adapter = str(payload.get("adapter") or "unknown").strip().lower()
    registry = load_adapter_capability_registry()
    declared = registry.get(adapter)
    if not isinstance(declared, dict):
        declared = {}
    supplied = payload.get("adapter_capabilities")
    if supplied is None:
        supplied = payload.get("capabilities")
    if supplied is None:
        supplied = {
            key: payload[key]
            for key in ADAPTER_CAPABILITY_KEYS
            if key in payload
        }
    if not isinstance(supplied, dict):
        return {
            "result": "adapter_capabilities_rejected",
            "adapter": adapter,
            "errors": ["adapter_capabilities must be an object"],
        }
    errors = []
    unknown = sorted(set(supplied) - set(ADAPTER_CAPABILITY_KEYS))
    if unknown:
        errors.append("unknown capabilities: " + ", ".join(unknown))
    for key, value in supplied.items():
        if key in ADAPTER_CAPABILITY_KEYS and value not in ADAPTER_CAPABILITY_STATUS:
            errors.append(
                f"{key} must be one of: "
                + ", ".join(sorted(ADAPTER_CAPABILITY_STATUS))
            )
    if errors:
        return {
            "result": "adapter_capabilities_rejected",
            "adapter": adapter,
            "errors": errors,
        }
    normalized = {}
    sources = {}
    for key in ADAPTER_CAPABILITY_KEYS:
        if key in supplied:
            normalized[key] = supplied[key]
            sources[key] = "request"
        elif declared.get(key) in ADAPTER_CAPABILITY_STATUS:
            normalized[key] = declared[key]
            sources[key] = "registry"
        else:
            normalized[key] = "unavailable"
            sources[key] = "missing"
    limitations = [
        f"{key} is unavailable; no native capability is claimed"
        for key, status in normalized.items()
        if status == "unavailable"
    ]
    degraded = [
        f"{key} uses an emulated adapter path"
        for key, status in normalized.items()
        if status == "emulated"
    ]
    return {
        "result": "adapter_capabilities",
        "read_only": True,
        "adapter": adapter,
        "capabilities": normalized,
        "sources": sources,
        "complete": len(normalized) == len(ADAPTER_CAPABILITY_KEYS),
        "limitations": limitations,
        "degraded": degraded,
    }


def adapter_capabilities(argv):
    if "--explain" in list(argv):
        json_print(adapter_capabilities_payload({"explain": True}))
        return
    try:
        payload, _ = json_arg_or_stdin(argv, "adapter-capabilities")
    except Exception as e:
        json_print({
            "result": "adapter_capabilities_rejected",
            "errors": [str(e)],
        })
        return
    json_print(adapter_capabilities_payload(payload))


def evidence_router_intent_blob(request):
    parts = [
        str(request.get("intent") or ""),
        " ".join(str(x) for x in request.get("constraints", []) if isinstance(x, str)),
        " ".join(request_paths(request)),
    ]
    return " ".join(parts).strip().lower()


def classify_evidence_task(request, matrix):
    raw = request.get("task_signal")
    normalized = normalize_task_signal(raw)
    known = set(matrix.get("task_matrix", {}))
    reasons = []
    if raw is not None and str(raw).strip():
        if normalized not in known:
            return None, 0.0, [], [
                "task_signal must be one of: "
                + ", ".join(sorted(
                    TASK_SIGNAL_ROUTES[k]["task_signal"]
                    for k in known if k in TASK_SIGNAL_ROUTES
                ))
            ]
        reasons.append(f"explicit task_signal={TASK_SIGNAL_ROUTES.get(normalized, {}).get('task_signal', normalized)}")
        return normalized, 0.96, reasons, []

    blob = evidence_router_intent_blob(request)
    inference = (
        ("security", EVIDENCE_ROUTER_SECURITY_TERMS),
        ("release/deploy", ("release", "deploy", "production rollout", "publish")),
        ("architecture", ("architecture", "boundary", "refactor system", "design system topology")),
        ("ui/component", ("component", "frontend", "visual", "css", "design token", "ui ")),
        ("api/backend", ("api", "backend", "endpoint", "database", "migration")),
        ("bug fix", ("bug", "fix", "regression", "crash", "incorrect")),
        ("tool/mcp", ("mcp", "tool", "cli", "command")),
    )
    for signal, terms in inference:
        if any(term in blob for term in terms):
            reasons.append(f"inferred {signal} from intent/path signal")
            return signal, 0.84, reasons, []
    reasons.append("no class signal found; conservative small-task fallback")
    return "not_applicable", 0.72, reasons, []


def evidence_router_risk(request, signal, task_row):
    score = int(task_row.get("risk_base", 10))
    reasons = [f"{signal} base risk={score}"]
    paths = request_paths(request)
    blob = evidence_router_intent_blob(request)
    if not paths or any(path_pattern_is_broad(path) for path in paths):
        score += 12
        reasons.append("broad or unresolved path coverage +12")
    elif len(paths) > 6:
        score += 10
        reasons.append("more than six affected paths +10")
    roots = {
        normalize_relative_path_text(path).split("/", 1)[0]
        for path in paths if path and not path_pattern_is_broad(path)
    }
    if len(roots) >= 3:
        score += 8
        reasons.append("cross-area change +8")
    if any(term in blob for term in EVIDENCE_ROUTER_SECURITY_TERMS) and signal != "security":
        score += 22
        reasons.append("security-sensitive intent +22")
    if any(term in blob for term in EVIDENCE_ROUTER_DESTRUCTIVE_TERMS):
        score += 20
        reasons.append("destructive or migration workflow +20")
    constraints = request.get("constraints")
    if isinstance(constraints, list) and any(
        "no test" in str(item).lower() or "skip test" in str(item).lower()
        for item in constraints
    ):
        score += 10
        reasons.append("verification constraint +10")
    return {"score": max(0, min(score, 100)), "reasons": reasons}


def evidence_router_graph_state(request):
    graph = request.get("codebase_graph")
    if graph is None and isinstance(request.get("evidence_state"), dict):
        graph = request["evidence_state"].get("codebase_graph")
    return graph if isinstance(graph, dict) else {}


def evidence_cost_estimate(cost_class, evidence_type):
    cost_class = str(cost_class or "low").lower()
    relative = {"low": 1, "medium": 3, "high": 6}.get(cost_class, 3)
    tool_calls = relative
    if evidence_type in {"source", "manifest", "consumer_asset"}:
        tool_calls = max(1, relative - 1)
    return {
        "class": cost_class if cost_class in {"low", "medium", "high"} else "medium",
        "relative_units": relative,
        "tool_calls": tool_calls,
        "telemetry": "estimate_not_real_usage",
    }


def build_evidence_plan(request, task_row, classification_confidence):
    plan = []
    limitations = []
    fallbacks = []
    paths = request_paths(request)
    for raw in task_row.get("evidence", []):
        if not isinstance(raw, dict):
            continue
        item = {
            "type": str(raw.get("type") or "source"),
            "source": str(raw.get("source") or "affected source files"),
            "required": bool(raw.get("required", True)),
            "freshness": str(raw.get("freshness") or "current"),
            "coverage": str(raw.get("coverage") or "affected_paths"),
            "confidence": round(
                min(classification_confidence, 0.95 if paths else 0.76),
                2,
            ),
            "estimated_cost": evidence_cost_estimate(
                raw.get("estimated_cost"), raw.get("type"),
            ),
            "trust": str(raw.get("trust") or "source"),
            "fallback": str(raw.get("fallback") or "read affected source directly"),
        }
        plan.append(item)
        if item["fallback"] not in fallbacks:
            fallbacks.append(item["fallback"])

    graph = evidence_router_graph_state(request)
    if graph:
        freshness = str(graph.get("freshness") or graph.get("status") or "unknown").lower()
        coverage = str(graph.get("coverage") or "unknown").lower()
        graph_ok = freshness in {"fresh", "current", "loaded"} and coverage in {
            "full", "complete", "affected_paths",
        }
        plan.append({
            "type": "code_graph",
            "source": "repo-local codebase index",
            "required": False,
            "freshness": freshness,
            "coverage": coverage,
            "confidence": 0.90 if graph_ok else 0.45,
            "estimated_cost": evidence_cost_estimate("low", "code_graph"),
            "trust": "derived_index" if graph_ok else "untrusted_index",
            "fallback": "read source directly and run an independent verification",
        })
        if not graph_ok:
            limitations.append(
                "codebase graph is stale, partial, or ambiguous; it is not source-grounded evidence"
            )
            fallbacks.append("read source directly and run an independent verification")

    blob = evidence_router_intent_blob(request)
    if EVIDENCE_ROUTER_NEGATIVE_CLAIM.search(blob):
        plan.append({
            "type": "coverage_search",
            "source": "source tree and manifests",
            "required": True,
            "freshness": "current",
            "coverage": "complete_claim_scope",
            "confidence": 0.75,
            "estimated_cost": evidence_cost_estimate("medium", "coverage_search"),
            "trust": "source",
            "fallback": "ask the user to narrow the negative claim or verify every claimed surface",
        })
        limitations.append(
            "negative claim requires explicit coverage before it can be accepted"
        )
        fallbacks.append(
            "ask the user to narrow the negative claim or verify every claimed surface"
        )

    conflicts = request.get("evidence_conflicts")
    if isinstance(conflicts, list) and conflicts:
        limitations.append("evidence conflicts require source-first resolution")
        fallbacks.append("read source and run an independent verification before execution")
    return plan, sorted(set(fallbacks)), limitations


def evidence_router_context_plan(task_row, request):
    context = []
    for source in task_row.get("context", []):
        if not non_empty_string(source):
            continue
        context.append({
            "source": source,
            "reason": "declarative task/evidence matrix",
            "required": True,
            "estimated_cost": "low",
        })
    paths = request_paths(request)
    if paths:
        context.append({
            "source": paths,
            "reason": "affected source scope",
            "required": True,
            "estimated_cost": "bounded_by_budget",
        })
    return context


def evidence_router_tool_plan(task_row, capability_result):
    caps = capability_result.get("capabilities", {})
    plan = []
    for tool in task_row.get("tools", []):
        if not non_empty_string(tool):
            continue
        discovery = caps.get("mcp_tool_discovery", "unavailable")
        plan.append({
            "tool": tool,
            "required": False,
            "mode": discovery,
            "reason": "selected by task/evidence matrix",
            "fallback": "use the source or repository CLI directly",
        })
    return plan


def evidence_router_verification_plan(task_row, evidence_plan, mandatory_review):
    plan = []
    for method in task_row.get("verification", []):
        if not non_empty_string(method):
            continue
        plan.append({
            "method": method,
            "required": True,
            "evidence_types": sorted({
                item["type"] for item in evidence_plan if item.get("required")
            }),
        })
    if mandatory_review and not any("review" in str(x.get("method", "")).lower() for x in plan):
        plan.append({
            "method": "independent safety review",
            "required": True,
            "evidence_types": ["review"],
        })
    return plan


def evidence_router_budget(request, capability_result):
    supplied = request.get("budget")
    if not isinstance(supplied, dict):
        supplied = {}
    budget = dict(EVIDENCE_ROUTER_DEFAULT_BUDGET)
    for key in budget:
        value = supplied.get(key)
        if isinstance(value, int) and value >= 0:
            budget[key] = value
    budget["max_roles"] = min(budget["max_roles"], 3)
    budget["max_repair_loops"] = min(budget["max_repair_loops"], 1)
    for key in ("max_usd", "remaining_tool_calls", "remaining_seconds"):
        value = supplied.get(key)
        if isinstance(value, (int, float)) and value >= 0:
            budget[key] = value
    exhausted = bool(supplied.get("exhausted"))
    if budget.get("max_tool_calls") == 0 or budget.get("remaining_tool_calls") == 0:
        exhausted = True
    caps = capability_result.get("capabilities", {})
    budget["model_cost"] = (
        "measured"
        if caps.get("cost_telemetry") == "native"
        and caps.get("token_telemetry") == "native"
        else "advisory"
    )
    budget["hard_limits"] = [
        "max_roles", "max_repair_loops", "max_tool_calls", "max_files",
        "max_bytes", "tool_timeout_seconds",
    ]
    budget["exhausted"] = exhausted
    return budget


def load_specialist_candidates(request):
    registry = load_json_file(SPECIALIST_REGISTRY)
    candidates = []
    if isinstance(registry, dict) and isinstance(registry.get("specialists"), list):
        candidates.extend(registry["specialists"])
    for rel in (".piloth/specialists.json", "piloth-specialists.json"):
        consumer_registry = load_json_file(REPO_ROOT / rel)
        rows = (
            consumer_registry.get("specialists")
            if isinstance(consumer_registry, dict)
            else None
        )
        if isinstance(rows, list):
            candidates = rows[:100] + candidates
    supplied = request.get("specialists")
    if isinstance(supplied, list):
        candidates = supplied[:100] + candidates
    deduped = []
    seen = set()
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_id = str(item.get("id") or "").strip()
        if not candidate_id or candidate_id in seen:
            continue
        seen.add(candidate_id)
        deduped.append(item)
    return deduped


def specialist_score_candidate(candidate, request, signal, task_class, evidence_types):
    reasons = []
    disqualified = []
    owner = str(candidate.get("owner") or "consumer").strip().lower()
    domains = {
        normalize_task_signal(x) for x in candidate.get("domains", [])
        if isinstance(x, str)
    }
    task_types = {
        str(x).strip() for x in candidate.get("task_types", [])
        if isinstance(x, str)
    }
    domain_score = 35 if signal in domains or task_class in task_types else 0
    reasons.append(f"domain_match={domain_score}/35")

    supported_evidence = {
        str(x).strip() for x in candidate.get("evidence_types", [])
        if isinstance(x, str)
    }
    intersection = supported_evidence & evidence_types
    evidence_score = round(
        25 * len(intersection) / max(1, len(evidence_types)),
        2,
    )
    reasons.append(f"evidence_capability={evidence_score}/25")

    required_tools = {
        str(x).strip() for x in candidate.get("tools", [])
        if isinstance(x, str) and str(x).strip()
    }
    available_tools = {
        str(x).strip() for x in request.get("available_tools", [])
        if isinstance(x, str) and str(x).strip()
    }
    missing_tools = sorted(required_tools - available_tools)
    tool_score = 15 if not missing_tools else 0
    reasons.append(f"tool_readiness={tool_score}/15")
    if missing_tools:
        disqualified.append("missing tools: " + ", ".join(missing_tools))

    try:
        confidence = float(candidate.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(confidence, 1.0))
    historical_score = round(confidence * 15, 2)
    reasons.append(f"historical_quality={historical_score}/15")

    cost_score = {"low": 10, "cheap": 10, "standard": 7, "high": 3, "premium": 3}.get(
        str(candidate.get("cost_class") or "").lower(),
        0,
    )
    reasons.append(f"cost={cost_score}/10")

    health = str(candidate.get("health") or "unknown").lower()
    if health not in {"healthy", "ready"}:
        disqualified.append(f"health={health}")
    adapter = str(request.get("adapter") or "unknown").lower()
    support = {
        str(x).lower() for x in candidate.get("adapter_support", [])
        if isinstance(x, str)
    }
    if support and adapter not in support:
        disqualified.append(f"adapter {adapter} unsupported")
    mandatory_review = evidence_router_requires_independent_review(request, signal)
    required_permission = "review" if mandatory_review else "edit"
    permissions = {
        str(x).lower() for x in candidate.get("permissions", [])
        if isinstance(x, str)
    }
    if required_permission not in permissions:
        disqualified.append(f"missing {required_permission} permission")

    score = round(domain_score + evidence_score + tool_score + historical_score + cost_score, 2)
    return {
        "id": str(candidate.get("id") or ""),
        "owner": owner,
        "score": score,
        "qualified": score >= 70 and not disqualified,
        "reasons": reasons,
        "disqualified_reasons": disqualified,
        "permissions": sorted(permissions),
    }


def select_specialist(request, signal, task_class, evidence_plan):
    evidence_types = {
        item.get("type") for item in evidence_plan
        if isinstance(item, dict) and item.get("required")
    }
    ranked = [
        specialist_score_candidate(
            item, request, signal, task_class, evidence_types,
        )
        for item in load_specialist_candidates(request)
    ]
    ranked.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    qualified_consumers = [
        item for item in ranked
        if item["qualified"] and item["owner"] == "consumer"
    ]
    qualified_piloth = [
        item for item in ranked
        if item["qualified"] and item["owner"] == "piloth"
    ]
    selected = (
        qualified_consumers[0] if qualified_consumers
        else qualified_piloth[0] if qualified_piloth
        else None
    )
    return selected, ranked[:20]


def evidence_router_requires_independent_review(request, signal):
    blob = evidence_router_intent_blob(request)
    return (
        signal in {"security", "release/deploy"}
        or "data migration" in blob
        or any(term in blob for term in EVIDENCE_ROUTER_DESTRUCTIVE_TERMS)
    )


def evidence_router_work_packages(request):
    supplied = request.get("work_packages")
    packages = []
    if isinstance(supplied, list):
        for index, item in enumerate(supplied[:10]):
            if isinstance(item, str) and item.strip():
                packages.append({
                    "id": f"wp-{index + 1}",
                    "scope": item.strip(),
                    "independent": True,
                })
            elif isinstance(item, dict) and non_empty_string(item.get("scope") or item.get("id")):
                packages.append({
                    "id": safe_evidence_id(item.get("id")) or f"wp-{index + 1}",
                    "scope": str(item.get("scope") or item.get("id")).strip(),
                    "independent": item.get("independent") is True,
                })
    return packages


def evidence_router_team_score(request, risk, specialist, mandatory_review):
    paths = request_paths(request)
    packages = evidence_router_work_packages(request)
    independent_count = len([item for item in packages if item.get("independent")])
    complexity = min(
        20,
        (8 if len(paths) > 3 else 3 if paths else 5)
        + (7 if len({
            normalize_relative_path_text(p).split("/", 1)[0]
            for p in paths if p and not path_pattern_is_broad(p)
        }) >= 2 else 0)
        + (5 if len(paths) > 8 else 0),
    )
    components = {
        "risk": round(min(25, risk.get("score", 0) * 0.25), 2),
        "complexity": complexity,
        "specialist_need": 20 if specialist else (15 if mandatory_review else 5),
        "independent_review_value": 20 if mandatory_review else (12 if risk.get("score", 0) >= 55 else 4),
        "parallelism_value": min(15, independent_count * 7.5),
        "coordination_cost": 8 if independent_count >= 2 else 22,
    }
    score = round(
        components["risk"]
        + components["complexity"]
        + components["specialist_need"]
        + components["independent_review_value"]
        + components["parallelism_value"]
        - components["coordination_cost"],
        2,
    )
    return max(0, min(score, 100)), components, packages, independent_count


def load_model_tiers():
    registry = load_json_file(MODEL_CAPABILITY_REGISTRY)
    tiers = registry.get("tiers") if isinstance(registry, dict) else None
    if not isinstance(tiers, list):
        tiers = [
            {"id": "economy", "cost_order": 1, "max_risk": 35, "min_route_confidence": 0.9, "benchmarked": True},
            {"id": "standard", "cost_order": 2, "max_risk": 70, "min_route_confidence": 0.8, "benchmarked": True},
            {"id": "premium", "cost_order": 3, "max_risk": 100, "min_route_confidence": 0.0, "benchmarked": True},
        ]
    return sorted(
        [item for item in tiers if isinstance(item, dict)],
        key=lambda item: item.get("cost_order", 999),
    )


def select_model_tier(risk_score, confidence, request):
    failed_repairs = request.get("failed_repairs", 0)
    if isinstance(failed_repairs, int) and failed_repairs >= 1:
        return "premium", "raised after a failed repair"
    signal = normalize_task_signal(request.get("_classified_signal"))
    for tier in load_model_tiers():
        if tier.get("benchmarked") is not True:
            continue
        if risk_score > int(tier.get("max_risk", 0)):
            continue
        if confidence < float(tier.get("min_route_confidence", 1.0)):
            continue
        domains = {
            normalize_task_signal(item)
            for item in tier.get("domains", [])
            if isinstance(item, str)
        }
        if domains and signal not in domains:
            continue
        return str(tier.get("id") or "premium"), "cheapest benchmarked tier meeting risk/confidence floor"
    return "premium", "raised because no cheaper benchmarked tier meets the floor"


def evidence_router_execution_roles(
    team, mode, mandatory_review, specialist, max_roles, limitations,
):
    roles = []
    if team:
        roles = [
            {"id": "lead", "permissions": ["plan", "review"], "read_only": True},
            {"id": "executor", "permissions": ["edit"], "read_only": False},
            {"id": "reviewer", "permissions": ["review", "qa"], "read_only": True},
        ][:max_roles]
        if len(roles) < 3:
            team = False
            mode = "single_with_external_review" if mandatory_review else "single"
            limitations.append(
                "max_roles budget cannot preserve the three-role team contract"
            )
            roles = []
    if not team and mandatory_review and not roles:
        roles = [{
            "id": "external_reviewer",
            "permissions": ["review", "qa"],
            "read_only": True,
            "required": True,
        }]
    if specialist:
        target_role = "reviewer" if mandatory_review else "executor"
        for role in roles:
            if role.get("id") == target_role:
                role["specialist_id"] = specialist.get("id")
    return roles, team, mode


def evidence_router_execution_plan(
    request, risk, confidence, specialist, ranked, capability_result, budget,
):
    signal = request.get("_classified_signal", "not_applicable")
    mandatory_review = evidence_router_requires_independent_review(request, signal)
    team_score, components, packages, independent_count = evidence_router_team_score(
        request, risk, specialist, mandatory_review,
    )
    caps = capability_result.get("capabilities", {})
    overrides = request.get("user_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
    forced = str(
        overrides.get("execution_mode")
        or ("team" if overrides.get("force_team") is True else "")
        or ("single" if overrides.get("force_single") is True else "")
    ).lower()
    team_capable = (
        caps.get("subagent_spawn") in {"native", "emulated"}
        and caps.get("role_permissions") in {"native", "emulated"}
    )
    team_eligible = team_score >= 60 and independent_count >= 2 and not budget["exhausted"]
    reasons = [
        f"team score={team_score} (threshold 60)",
        f"independent work packages={independent_count}",
    ]
    limitations = []
    if forced == "team":
        team_eligible = independent_count >= 2 and not budget["exhausted"]
        reasons.append("user forced team mode")
    elif forced == "single":
        team_eligible = False
        reasons.append("user forced single mode")

    if mandatory_review and forced == "single":
        reasons.append("safety reviewer overrides forced single acceptance")
    if mandatory_review and not team_capable:
        limitations.append(
            "adapter cannot spawn an independent reviewer; external independent review is required"
        )
        team = False
        mode = "single_with_external_review"
    elif mandatory_review:
        team = True
        mode = "team"
    elif team_eligible and team_capable:
        team = True
        mode = "team"
    else:
        team = False
        mode = "single"
        if team_eligible and not team_capable:
            limitations.append(
                "team score passed but adapter subagent spawn is unavailable; using single-agent fallback"
            )
    if budget["exhausted"]:
        team = False
        mode = "single_source_first"
        reasons.append("budget exhausted: parallelism disabled")

    roles, team, mode = evidence_router_execution_roles(
        team, mode, mandatory_review, specialist, budget["max_roles"], limitations,
    )
    for role in roles:
        role["allowed_paths"] = (
            request_paths(request) if role.get("id") == "executor" else []
        )
    if team and caps.get("parallel_execution") == "unavailable":
        limitations.append(
            "parallel execution unavailable; independent roles must run sequentially"
        )

    tier, tier_reason = select_model_tier(risk.get("score", 0), confidence, request)
    model_roles = [role["id"] for role in roles] or ["executor"]
    model_tiers = {role: tier for role in model_roles}
    if caps.get("model_pinning") == "unavailable":
        limitations.append("model tier is advisory because adapter model pinning is unavailable")
    return {
        "mode": mode,
        "team": team,
        "roles": roles,
        "model_tiers": model_tiers,
        "model_tier_reason": tier_reason,
        "specialist": specialist,
        "specialist_candidates": ranked,
        "team_score": team_score,
        "team_score_components": components,
        "work_packages": packages,
        "max_repair_loops": budget["max_repair_loops"],
        "mandatory_independent_review": mandatory_review,
        "decision_reasons": reasons,
    }, limitations


def evidence_router_rollout(request):
    overrides = request.get("user_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
    kill_switch = overrides.get("kill_switch") is True or os.environ.get(
        "PILOTHOS_EVIDENCE_ROUTER_KILL_SWITCH", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    if kill_switch:
        return "off", True
    raw = str(
        overrides.get("rollout")
        or request.get("router_mode")
        or os.environ.get("PILOTHOS_EVIDENCE_ROUTER_MODE", "advisory")
    ).strip().lower()
    return (raw if raw in EVIDENCE_ROUTER_ROLLOUT_MODES else "advisory"), False


def evidence_router_enforcement_capability_gaps(capability_result):
    caps = capability_result.get("capabilities", {})
    required = (
        "pre_edit_hooks", "post_edit_hooks", "stop_hooks",
        "approval_controls", "sandbox_controls",
        "receipt_enforcement", "seal_enforcement",
    )
    return [
        key for key in required
        if caps.get(key) not in {"native", "emulated"}
    ]


def evidence_route_rejected(errors):
    return {
        "result": "evidence_route_rejected",
        "decision_id": "",
        "task_class": "",
        "risk": {"score": 0, "reasons": []},
        "confidence": 0.0,
        "evidence_plan": [],
        "context_plan": [],
        "execution_plan": {
            "mode": "single",
            "team": False,
            "roles": [],
            "model_tiers": {},
        },
        "tool_plan": [],
        "verification_plan": [],
        "budgets": {},
        "fallbacks": [],
        "limitations": [],
        "decision_reasons": [],
        "errors": errors,
    }


def evidence_route_request_errors(request):
    errors = []
    if "intent" in request and not isinstance(request.get("intent"), str):
        errors.append("intent must be a string")
    elif len(request.get("intent") or "") > 10_000:
        errors.append("intent exceeds 10000 characters")
    if "locale" in request and not isinstance(request.get("locale"), str):
        errors.append("locale must be a string")
    for field in ("affected_paths", "changed_paths", "allowed_paths", "target_paths"):
        if field not in request:
            continue
        value = request.get(field)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            errors.append(f"{field} must be a list of strings")
            continue
        if len(value) > 1000:
            errors.append(f"{field} exceeds 1000 entries")
            continue
        for path in value:
            if not path_pattern_is_safe(path):
                errors.append(f"{field} contains unsafe pattern: {path}")
    constraints = request.get("constraints")
    if constraints is not None and (
        not isinstance(constraints, list)
        or any(not isinstance(item, str) for item in constraints)
    ):
        errors.append("constraints must be a list of strings")
    elif isinstance(constraints, list) and len(constraints) > 100:
        errors.append("constraints exceeds 100 entries")
    for field in ("budget", "user_overrides"):
        if field in request and not isinstance(request.get(field), dict):
            errors.append(f"{field} must be an object")
    specialists = request.get("specialists")
    if specialists is not None and (
        not isinstance(specialists, list)
        or any(not isinstance(item, dict) for item in specialists)
    ):
        errors.append("specialists must be a list of objects")
    elif isinstance(specialists, list) and len(specialists) > 100:
        errors.append("specialists exceeds 100 entries")
    return errors


def evidence_router_localized_summary(request, task_class, execution_plan):
    locale = str(request.get("locale") or request.get("language") or "en").lower()
    language = locale.split("-", 1)[0].split("_", 1)[0]
    mode = execution_plan.get("mode", "single")
    if language == "vi":
        summary = (
            f"Đã phân loại {task_class}; chọn chế độ {mode} với bằng chứng "
            "tối thiểu đáp ứng quality floor."
        )
    else:
        summary = (
            f"Classified {task_class}; selected {mode} with the smallest "
            "evidence set meeting the quality floor."
        )
    return locale, summary


def evidence_route_output(
    request, matrix, matrix_source, signal, task_class, class_reasons, risk,
    confidence, evidence_plan, context_plan, execution_plan, tool_plan,
    verification_plan, budget, capability_result, specialist, fallbacks,
    limitations, rollout, requested_rollout, kill_switch,
):
    decision_basis = {
        "request": sanitize_state_value(request, limit=1000),
        "signal": signal,
        "task_class": task_class,
        "risk": risk,
        "confidence": confidence,
        "rollout": rollout,
        "matrix_sha256": sha256_json(matrix),
        "evidence_plan": evidence_plan,
        "execution_plan": execution_plan,
        "adapter_capabilities": capability_result.get("capabilities", {}),
    }
    reasons = class_reasons + [
        f"matrix_source={matrix_source}",
        f"rollout={rollout}",
        f"selected smallest declared evidence set for {task_class}",
    ] + execution_plan.pop("decision_reasons", [])
    if specialist:
        reasons.append(
            f"selected {specialist['owner']} specialist {specialist['id']} score={specialist['score']}"
        )
    else:
        reasons.append("no specialist met the 70/100 health/tool/permission floor")
    locale, localized_summary = evidence_router_localized_summary(
        request, task_class, execution_plan,
    )
    return {
        "result": "evidence_route",
        "schema_version": 1,
        "read_only": True,
        "locale": locale,
        "decision_summary": localized_summary,
        "decision_id": "er-" + sha256_json(decision_basis)[:16],
        "task_signal": TASK_SIGNAL_ROUTES.get(signal, {}).get("task_signal", signal),
        "task_class": task_class,
        "risk": risk,
        "confidence": confidence,
        "evidence_plan": evidence_plan,
        "context_plan": context_plan,
        "execution_plan": execution_plan,
        "tool_plan": tool_plan,
        "verification_plan": verification_plan,
        "budgets": budget,
        "fallbacks": sorted(set(fallbacks)),
        "limitations": sorted(set(limitations)),
        "decision_reasons": reasons,
        "adapter_capabilities": capability_result,
        "rollout": {
            "mode": rollout,
            "requested_mode": requested_rollout,
            "kill_switch": kill_switch,
            "quality_floor": matrix.get("quality_floor", {}),
        },
    }


def finalize_evidence_route(
    request, matrix, matrix_source, signal, task_class, class_reasons, risk, confidence, evidence_plan, context_plan,
    execution_plan, tool_plan, verification_plan, budget, capability_result, specialist, evidence_fallbacks, evidence_limitations, execution_limitations,
):
    rollout, kill_switch = evidence_router_rollout(request)
    requested_rollout = rollout
    limitations = (
        evidence_limitations
        + execution_limitations
        + capability_result.get("limitations", [])
    )
    fallbacks = list(evidence_fallbacks)
    if confidence < 0.80:
        fallbacks.append(
            "read source, run another verification, or ask the user before relying on the route"
        )
    if budget["exhausted"]:
        fallbacks.extend([
            "stop parallelism and use single-agent source-first execution",
            "ask the user when the quality floor still cannot be demonstrated",
        ])
    if kill_switch or rollout == "off":
        execution_plan["mode"] = "legacy_source_only"
        execution_plan["team"] = False
        execution_plan["roles"] = []
        execution_plan["model_tiers"] = {}
        fallbacks.append("legacy scheduler and source-only routing")
    elif rollout == "shadow":
        execution_plan["controls_execution"] = False
    elif rollout == "advisory":
        execution_plan["controls_execution"] = False
        execution_plan["override_requires_reason"] = True
    elif rollout == "enforced":
        enforcement_gaps = evidence_router_enforcement_capability_gaps(
            capability_result,
        )
        if enforcement_gaps:
            rollout = "advisory"
            execution_plan["controls_execution"] = False
            execution_plan["override_requires_reason"] = True
            limitations.append(
                "enforced rollout unavailable; adapter capability gaps: "
                + ", ".join(enforcement_gaps)
            )
            fallbacks.append("use advisory routing until the adapter passes the capability contract")
        else:
            execution_plan["controls_execution"] = True
    else:
        execution_plan["controls_execution"] = False
    return evidence_route_output(
        request, matrix, matrix_source, signal, task_class, class_reasons, risk,
        confidence, evidence_plan, context_plan, execution_plan, tool_plan,
        verification_plan, budget, capability_result, specialist, fallbacks,
        limitations, rollout, requested_rollout, kill_switch,
    )


def evidence_router_review_evidence_present(receipt, os_evidence):
    review = receipt.get("independent_review")
    if isinstance(review, dict):
        result = str(review.get("result") or review.get("status") or "").upper()
        if result == "PASS" and non_empty_string(review.get("evidence")):
            return True
    for item in os_evidence or []:
        if not isinstance(item, dict):
            continue
        gate = str(item.get("quality_gate") or item.get("gate") or "").lower()
        result = str(item.get("result") or item.get("status") or "").lower()
        if "review" in gate and result in {"pass", "passed", "approve", "approved"}:
            return True
    return False


def evidence_router_receipt_errors(contract, receipt, os_evidence=None):
    if not isinstance(contract, dict) or not isinstance(receipt, dict):
        return []
    router = contract.get("evidence_router")
    if not isinstance(router, dict):
        return []
    rollout = router.get("rollout")
    rollout_mode = rollout.get("mode") if isinstance(rollout, dict) else "advisory"
    execution = router.get("execution_plan")
    if not isinstance(execution, dict):
        execution = {}
    errors = []
    receipt_decision = receipt.get("decision_id")
    if receipt_decision and receipt_decision != router.get("decision_id"):
        errors.append("receipt decision_id does not match the active Evidence Router decision")
    actual_mode = receipt.get("execution_mode")
    planned_mode = execution.get("mode")
    if (
        non_empty_string(actual_mode)
        and actual_mode != planned_mode
        and not non_empty_string(receipt.get("router_override_reason"))
    ):
        errors.append("router_override_reason is required when execution_mode overrides the route")
    if rollout_mode != "enforced":
        return errors
    if not non_empty_string(receipt_decision):
        errors.append("decision_id is required by enforced Evidence Router rollout")
    if float(router.get("confidence", 0)) < 0.80 and not non_empty_string(
        receipt.get("router_low_confidence_resolution")
    ):
        errors.append(
            "router_low_confidence_resolution is required before accepting an enforced low-confidence route"
        )
    required_types = {
        item.get("type")
        for item in router.get("evidence_plan", [])
        if isinstance(item, dict) and item.get("required") is True
    }
    context_used = receipt.get("context_used")
    if required_types & {"source", "manifest"} and not (
        isinstance(context_used, list) and context_used
    ):
        errors.append("enforced source/manifest evidence requires receipt context_used")
    command = str(receipt.get("verification_command") or "").lower()
    if "test" in required_types and (
        not command or any(term in command for term in ("not run", "skipped", "failed"))
    ):
        errors.append("enforced test evidence requires a clean verification_command")
    if "review" in required_types and not evidence_router_review_evidence_present(
        receipt, os_evidence or [],
    ):
        errors.append("enforced review evidence requires an independent PASS with evidence")
    if "consumer_asset" in required_types and not receipt.get("consumer_asset_routing"):
        errors.append("enforced consumer asset evidence requires consumer_asset_routing")
    if "coverage_search" in required_types and not receipt.get("coverage_evidence"):
        errors.append("enforced negative-claim evidence requires coverage_evidence")
    if "visual" in required_types:
        gates = receipt.get("quality_gates")
        ui = gates.get("ui_quality") if isinstance(gates, dict) else None
        if not isinstance(ui, dict) or ui.get("result") != "PASS":
            errors.append("enforced visual evidence requires quality_gates.ui_quality PASS")
    return errors


def evidence_route_payload(request):
    if not isinstance(request, dict):
        return evidence_route_rejected(["request must be a JSON object"])
    request_errors = evidence_route_request_errors(request)
    if request_errors:
        return evidence_route_rejected(request_errors)
    matrix, matrix_source = load_evidence_router_matrix()
    signal, class_confidence, class_reasons, errors = classify_evidence_task(
        request, matrix,
    )
    if errors:
        return evidence_route_rejected(errors)
    task_row = matrix["task_matrix"].get(signal, {})
    task_class = str(task_row.get("task_class") or "small_task")
    risk = evidence_router_risk(request, signal, task_row)
    capability_request = {
        "adapter": request.get("adapter") or "unknown",
        "adapter_capabilities": request.get("adapter_capabilities") or {},
    }
    capability_result = adapter_capabilities_payload(capability_request)
    if capability_result.get("result") == "adapter_capabilities_rejected":
        return evidence_route_rejected(capability_result.get("errors", []))
    evidence_plan, evidence_fallbacks, evidence_limitations = build_evidence_plan(
        request, task_row, class_confidence,
    )
    confidence = class_confidence
    if not request_paths(request):
        confidence -= 0.08
    if any(item.get("confidence", 1.0) < 0.80 for item in evidence_plan):
        confidence = min(confidence, 0.78)
    conflicts = request.get("evidence_conflicts")
    if isinstance(conflicts, list) and conflicts:
        confidence = min(confidence, 0.65)
    confidence = round(max(0.0, min(confidence, 1.0)), 2)

    budget = evidence_router_budget(request, capability_result)
    specialist, ranked = select_specialist(
        request, signal, task_class, evidence_plan,
    )
    execution_request = dict(request)
    execution_request["_classified_signal"] = signal
    execution_plan, execution_limitations = evidence_router_execution_plan(
        execution_request,
        risk,
        confidence,
        specialist,
        ranked,
        capability_result,
        budget,
    )
    mandatory_review = execution_plan.get("mandatory_independent_review", False)
    context_plan = evidence_router_context_plan(task_row, request)
    tool_plan = evidence_router_tool_plan(task_row, capability_result)
    verification_plan = evidence_router_verification_plan(
        task_row, evidence_plan, mandatory_review,
    )
    return finalize_evidence_route(
        request, matrix, matrix_source, signal, task_class, class_reasons,
        risk, confidence, evidence_plan, context_plan, execution_plan,
        tool_plan, verification_plan, budget, capability_result, specialist,
        evidence_fallbacks, evidence_limitations, execution_limitations,
    )


def evidence_route(argv):
    if "--explain" in list(argv):
        json_print(evidence_router_schema_payload())
        return
    try:
        request, _ = json_arg_or_stdin(argv, "evidence-route")
    except Exception as e:
        json_print({
            "result": "evidence_route_rejected",
            "errors": [str(e)],
        })
        return
    json_print(evidence_route_payload(request))

