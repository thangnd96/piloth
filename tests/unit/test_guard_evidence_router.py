"""Evidence Router contract, safety, routing, and statelessness gates."""

import hashlib
import json

import pytest


REQUIRED_ROUTE_FIELDS = {
    "decision_id",
    "task_class",
    "risk",
    "confidence",
    "evidence_plan",
    "context_plan",
    "execution_plan",
    "tool_plan",
    "verification_plan",
    "budgets",
    "fallbacks",
    "limitations",
    "decision_reasons",
}

REQUIRED_EVIDENCE_FIELDS = {
    "type",
    "source",
    "required",
    "freshness",
    "coverage",
    "confidence",
    "estimated_cost",
    "trust",
    "fallback",
}


@pytest.fixture()
def floor(guard):
    """The quality floor in force. Assertions read thresholds from here instead of
    repeating literals, so the tests move with the registry rather than pinning a
    second copy of the policy."""
    return guard.evidence_router_quality_floor()


def route(guard, **overrides):
    payload = {
        "intent": "fix localized parser regression",
        "task_signal": "bug fix",
        "affected_paths": ["src/parser.py", "tests/test_parser.py"],
        "adapter": "claude",
    }
    payload.update(overrides)
    return guard.evidence_route_payload(payload)


def test_route_has_canonical_shape_and_complete_evidence_items(guard):
    out = route(guard)
    assert out["result"] == "evidence_route"
    assert REQUIRED_ROUTE_FIELDS <= set(out)
    assert out["decision_id"].startswith("er-")
    assert out["evidence_plan"]
    for item in out["evidence_plan"]:
        assert REQUIRED_EVIDENCE_FIELDS <= set(item)
        assert 0 <= item["confidence"] <= 1
        assert item["estimated_cost"]["telemetry"] == "estimate_not_real_usage"


def test_route_is_deterministic_and_read_only(guard):
    first = route(guard)
    second = route(guard)
    assert first == second
    assert first["read_only"] is True
    assert not guard.SCHEDULER_HISTORY.exists()


def test_consumer_locale_localizes_summary_but_keeps_schema_ids_stable(guard):
    out = route(guard, locale="vi-VN")
    assert out["locale"] == "vi-vn"
    assert out["decision_id"].startswith("er-")
    assert out["task_class"] == "localized_bug"
    assert out["decision_summary"].startswith("Đã phân loại")


def test_unknown_task_signal_is_rejected_without_losing_output_contract(guard):
    out = route(guard, task_signal="invented domain")
    assert out["result"] == "evidence_route_rejected"
    assert REQUIRED_ROUTE_FIELDS <= set(out)
    assert out["execution_plan"]["team"] is False


@pytest.mark.parametrize(
    "payload,error",
    [
        ({"intent": 7}, "intent must be a string"),
        ({"affected_paths": "../secret"}, "affected_paths must be a list"),
        ({"affected_paths": ["../secret"]}, "unsafe pattern"),
        ({"affected_paths": ["/etc/passwd"]}, "unsafe pattern"),
        ({"constraints": ["safe", 4]}, "constraints must be a list"),
        ({"budget": []}, "budget must be an object"),
        ({"specialists": ["invented"]}, "specialists must be a list"),
        ({"specialists": [{}] * 101}, "specialists exceeds 100"),
    ],
)
def test_hostile_or_malformed_router_input_is_rejected(guard, payload, error):
    out = guard.evidence_route_payload(payload)
    assert out["result"] == "evidence_route_rejected"
    assert any(error in item for item in out["errors"])


@pytest.mark.parametrize("bad", [None, [], "native", 4])
def test_malformed_capability_map_is_rejected(guard, bad):
    out = guard.adapter_capabilities_payload({
        "adapter": "claude",
        "adapter_capabilities": bad,
    })
    if bad is None:
        # Omitted means use the explicit registry declaration.
        assert out["result"] == "adapter_capabilities"
    else:
        assert out["result"] == "adapter_capabilities_rejected"


def test_adapter_contract_is_complete_and_missing_capabilities_are_not_claimed(guard):
    out = guard.adapter_capabilities_payload({"adapter": "new-harness"})
    assert out["complete"] is True
    assert set(out["capabilities"]) == set(guard.ADAPTER_CAPABILITY_KEYS)
    assert set(out["capabilities"].values()) == {"unavailable"}
    # "missing" is the default provenance, so it is summarised rather than
    # repeated once per key; the count still proves nothing was claimed.
    assert out["sources"] == {}
    assert out["sources_summary"]["missing"] == len(guard.ADAPTER_CAPABILITY_KEYS)


def test_unavailable_capabilities_collapse_into_one_limitation(guard):
    """15 boilerplate lines cost tokens and bury the limitations that matter."""
    out = guard.adapter_capabilities_payload({"adapter": "new-harness"})
    assert len(out["limitations"]) == 1
    only = out["limitations"][0]
    assert "15 capability(ies) unavailable" in only
    # Every key is still named, so no information is lost.
    for key in guard.ADAPTER_CAPABILITY_KEYS:
        assert key in only


def test_adapter_resolution_precedence(guard, monkeypatch):
    """request > PILOTHOS_ADAPTER > harness env signal > unknown."""
    monkeypatch.setenv("PILOTHOS_ADAPTER", "cursor")
    monkeypatch.setenv("CLAUDECODE", "1")
    assert guard.resolve_adapter({"adapter": "codex"}) == ("codex", "request")
    assert guard.resolve_adapter({}) == ("cursor", "env")
    monkeypatch.delenv("PILOTHOS_ADAPTER")
    assert guard.resolve_adapter({}) == ("claude", "detected")
    monkeypatch.delenv("CLAUDECODE")
    assert guard.resolve_adapter({}) == ("unknown", "default")


def test_cursor_integrated_terminal_is_not_an_agent_signal(guard, monkeypatch):
    """`CURSOR_CLI` means "a Cursor terminal", not "the Cursor agent is driving".

    It is set even when a human types commands by hand, so treating it as a
    detection signal would claim cursor's capability profile for a session that
    never went through the agent.
    """
    monkeypatch.setenv("CURSOR_CLI", "/Applications/Cursor.app")
    assert guard.resolve_adapter({}) == ("unknown", "default")
    monkeypatch.setenv("CURSOR_AGENT", "1")
    assert guard.resolve_adapter({}) == ("cursor", "detected")


def test_every_detection_signal_maps_to_a_declared_adapter(guard):
    """A signal naming an adapter the registry doesn't declare would silently
    never fire — detection only yields ids adapter-capabilities.json declares."""
    registry = guard.load_adapter_capability_registry()
    for var, adapter in guard.ADAPTER_ENV_SIGNALS:
        assert adapter in registry, f"{var} maps to undeclared adapter {adapter!r}"


def test_unregistered_env_override_stays_conservative(guard, monkeypatch):
    """An override naming nothing we know must not silently fall back to detection."""
    monkeypatch.setenv("PILOTHOS_ADAPTER", "typo-harness")
    monkeypatch.setenv("CLAUDECODE", "1")
    assert guard.resolve_adapter({}) == ("unknown", "default")


def test_detected_adapter_unlocks_the_capability_profile(guard, monkeypatch):
    """Without detection every consumer ran the worst path: enforced -> advisory.

    `unknown` resolves all 15 capabilities to `unavailable`, which fails the
    enforcement gate, so the router downgrades an enforced rollout even on a
    harness that does support hooks and seals.
    """
    request = {
        "task_signal": "bug fix", "task_type": "code", "scope": "narrow",
        "router_mode": "enforced",
    }
    blind = guard.evidence_route_payload(dict(request))
    assert blind["adapter_capabilities"]["adapter"] == "unknown"
    assert blind["rollout"]["mode"] == "advisory"
    assert any("capability gaps" in item for item in blind["limitations"])

    monkeypatch.setenv("CLAUDECODE", "1")
    detected = guard.evidence_route_payload(dict(request))
    assert detected["adapter_capabilities"]["adapter_source"] == "detected"
    assert detected["rollout"]["mode"] == "enforced"
    # Cheaper as well as stronger: no boilerplate limitation survives.
    assert detected["limitations"] == []


def test_emulated_capabilities_stay_itemised(guard):
    out = guard.adapter_capabilities_payload({
        "adapter": "new-harness",
        "stop_hooks": "emulated",
        "seal_enforcement": "emulated",
    })
    assert len(out["degraded"]) == 2
    assert any("stop_hooks" in line for line in out["degraded"])


def test_adapter_handshake_accepts_direct_capability_file_shape(guard):
    out = guard.adapter_capabilities_payload({
        "adapter": "new-harness",
        "pre_edit_hooks": "native",
        "receipt_enforcement": "emulated",
    })
    assert out["capabilities"]["pre_edit_hooks"] == "native"
    assert out["capabilities"]["receipt_enforcement"] == "emulated"
    assert out["sources"]["pre_edit_hooks"] == "request"
    assert out["capabilities"]["stop_hooks"] == "unavailable"


def test_invalid_capability_status_and_unknown_key_are_rejected(guard):
    out = guard.adapter_capabilities_payload({
        "adapter": "codex",
        "adapter_capabilities": {
            "subagent_spawn": "probably",
            "magic_hook": "native",
        },
    })
    assert out["result"] == "adapter_capabilities_rejected"
    assert any("unknown capabilities" in error for error in out["errors"])
    assert any("subagent_spawn" in error for error in out["errors"])


def test_stale_partial_graph_never_becomes_source_grounded(guard, floor):
    out = route(
        guard,
        codebase_graph={"freshness": "stale", "coverage": "partial"},
    )
    graph = next(item for item in out["evidence_plan"] if item["type"] == "code_graph")
    assert graph["trust"] == "untrusted_index"
    assert graph["confidence"] < floor["evidence_item_confidence"]
    assert out["confidence"] < floor["route_confidence"]
    assert any("not source-grounded" in item for item in out["limitations"])
    assert any(item["type"] == "source" and item["required"] for item in out["evidence_plan"])


def test_negative_claim_forces_complete_coverage_and_low_confidence_fallback(guard, floor):
    out = route(
        guard,
        intent="prove there is no other parser implementation",
    )
    coverage = [
        item for item in out["evidence_plan"]
        if item["type"] == "coverage_search"
    ]
    assert coverage and coverage[0]["coverage"] == "complete_claim_scope"
    assert coverage[0]["required"] is True
    assert out["confidence"] < floor["route_confidence"]
    assert any("ask the user" in fallback for fallback in out["fallbacks"])


def test_conflicting_evidence_requires_source_first_resolution(guard, floor):
    out = route(guard, evidence_conflicts=["graph disagrees with source"])
    assert out["confidence"] < floor["route_confidence"]
    assert any("conflicts" in item for item in out["limitations"])
    assert any("source" in item for item in out["fallbacks"])


def test_pass_through_fixture_stays_single_agent(guard):
    out = guard.evidence_route_payload({
        "intent": "update one comment",
        "task_signal": "not_applicable",
        "affected_paths": ["src/comment.py"],
        "adapter": "claude",
    })
    assert out["execution_plan"]["mode"] == "single"
    assert out["execution_plan"]["team"] is False
    assert out["execution_plan"]["model_tiers"]["executor"] == "economy"


def test_team_requires_score_independence_capability_and_budget(guard, floor):
    out = guard.evidence_route_payload({
        "intent": "fix auth bypass across API and policy",
        "task_signal": "security",
        "affected_paths": ["src/auth.py", "src/policy.py", "tests/test_auth.py"],
        "work_packages": [
            {"id": "implementation", "scope": "auth implementation", "independent": True},
            {"id": "verification", "scope": "security verification", "independent": True},
        ],
        "adapter": "claude",
    })
    plan = out["execution_plan"]
    assert plan["team_score"] >= floor["team_score"]
    assert plan["team"] is True
    assert [role["id"] for role in plan["roles"]] == ["lead", "executor", "reviewer"]
    assert plan["mandatory_independent_review"] is True
    assert plan["max_repair_loops"] == 1


def test_security_degrades_to_external_review_when_spawn_unavailable(guard):
    out = guard.evidence_route_payload({
        "intent": "fix auth bypass",
        "task_signal": "security",
        "affected_paths": ["src/auth.py"],
        "adapter": "codex",
    })
    plan = out["execution_plan"]
    assert plan["team"] is False
    assert plan["mode"] == "single_with_external_review"
    assert plan["roles"][0]["id"] == "external_reviewer"
    assert any("external independent review" in item for item in out["limitations"])


def test_safety_reviewer_overrides_forced_single_acceptance(guard):
    out = guard.evidence_route_payload({
        "intent": "fix auth bypass",
        "task_signal": "security",
        "affected_paths": ["src/auth.py"],
        "adapter": "claude",
        "user_overrides": {"execution_mode": "single"},
    })
    assert out["execution_plan"]["team"] is True
    assert out["execution_plan"]["mandatory_independent_review"] is True
    assert any("overrides forced single" in reason for reason in out["decision_reasons"])


def test_budget_exhaustion_stops_parallelism_and_asks_user_if_needed(guard):
    out = guard.evidence_route_payload({
        "intent": "fix auth bypass",
        "task_signal": "security",
        "affected_paths": ["src/auth.py"],
        "work_packages": ["implementation", "verification"],
        "adapter": "claude",
        "budget": {"remaining_tool_calls": 0},
    })
    assert out["execution_plan"]["mode"] == "single_source_first"
    assert out["execution_plan"]["team"] is False
    assert out["budgets"]["exhausted"] is True
    assert any("ask the user" in item for item in out["fallbacks"])


def test_model_tier_raises_after_low_confidence_or_failed_repair(guard):
    low_confidence = route(
        guard,
        intent="prove there is no other parser implementation",
    )
    assert set(low_confidence["execution_plan"]["model_tiers"].values()) == {"premium"}
    repaired = route(guard, failed_repairs=1)
    assert set(repaired["execution_plan"]["model_tiers"].values()) == {"premium"}
    assert "failed repair" in repaired["execution_plan"]["model_tier_reason"]


def _consumer_specialist(**overrides):
    candidate = {
        "id": "consumer.parser-specialist",
        "owner": "consumer",
        "domains": ["bug fix"],
        "task_types": ["localized_bug"],
        "capabilities": ["implementation"],
        "tools": [],
        "evidence_types": ["source", "test"],
        "permissions": ["edit", "qa"],
        "health": "healthy",
        "confidence": 1.0,
        "cost_class": "low",
        "adapter_support": ["claude"],
    }
    candidate.update(overrides)
    return candidate


def test_qualified_consumer_specialist_precedes_piloth_fallback(guard, floor):
    out = route(guard, specialists=[_consumer_specialist()])
    selected = out["execution_plan"]["specialist"]
    assert selected["id"] == "consumer.parser-specialist"
    assert selected["owner"] == "consumer"
    assert selected["score"] >= floor["specialist_score"]


def test_explicit_consumer_registry_is_discovered_without_inventing_specialist(
    guard, monkeypatch, tmp_path,
):
    repo = tmp_path / "consumer"
    registry = repo / ".piloth" / "specialists.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({
        "specialists": [_consumer_specialist(id="consumer.registry-parser")],
    }), encoding="utf-8")
    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    out = route(guard)
    assert out["execution_plan"]["specialist"]["id"] == "consumer.registry-parser"


@pytest.mark.parametrize(
    "overrides,reason",
    [
        ({"health": "stale"}, "health=stale"),
        ({"tools": ["missing-tool"]}, "missing tools"),
        ({"permissions": ["review"]}, "missing edit permission"),
        ({"adapter_support": ["cursor"]}, "unsupported"),
    ],
)
def test_unready_specialist_is_never_routed(guard, overrides, reason):
    candidate = _consumer_specialist(**overrides)
    out = route(guard, specialists=[candidate], available_tools=[])
    row = next(
        item for item in out["execution_plan"]["specialist_candidates"]
        if item["id"] == candidate["id"]
    )
    assert row["qualified"] is False
    assert any(reason in item for item in row["disqualified_reasons"])
    assert out["execution_plan"]["specialist"]["id"] != candidate["id"]


def test_rollout_modes_and_kill_switch_preserve_schema(guard, monkeypatch):
    shadow = route(guard, user_overrides={"rollout": "shadow"})
    assert shadow["rollout"]["mode"] == "shadow"
    assert shadow["execution_plan"]["controls_execution"] is False

    enforced = route(guard, user_overrides={"rollout": "enforced"})
    assert enforced["execution_plan"]["controls_execution"] is True

    off = route(guard, user_overrides={"rollout": "off"})
    assert off["execution_plan"]["mode"] == "legacy_source_only"
    assert off["execution_plan"]["team"] is False
    monkeypatch.setenv("PILOTHOS_EVIDENCE_ROUTER_KILL_SWITCH", "1")
    killed = route(guard)
    assert killed["rollout"]["kill_switch"] is True
    assert killed["execution_plan"]["mode"] == "legacy_source_only"


def test_enforced_rollout_degrades_when_adapter_contract_has_gaps(guard):
    out = route(
        guard,
        adapter="cursor",
        user_overrides={"rollout": "enforced"},
    )
    assert out["rollout"]["requested_mode"] == "enforced"
    assert out["rollout"]["mode"] == "advisory"
    assert out["execution_plan"]["controls_execution"] is False
    assert any("capability gaps" in item for item in out["limitations"])


def test_advisory_execution_override_requires_reason(guard):
    decision = route(guard)
    contract = {"evidence_router": decision}
    receipt = {"execution_mode": "team"}
    errors = guard.evidence_router_receipt_errors(contract, receipt)
    assert any("router_override_reason" in error for error in errors)
    receipt["router_override_reason"] = "user explicitly requested independent packages"
    assert guard.evidence_router_receipt_errors(contract, receipt) == []


def test_enforced_receipt_requires_decision_and_planned_evidence(guard):
    decision = route(guard, user_overrides={"rollout": "enforced"})
    contract = {"evidence_router": decision}
    errors = guard.evidence_router_receipt_errors(contract, {
        "execution_mode": decision["execution_plan"]["mode"],
        "verification_command": "not run",
    })
    assert any("decision_id" in error for error in errors)
    assert any("context_used" in error for error in errors)
    assert any("verification_command" in error for error in errors)

    receipt = {
        "decision_id": decision["decision_id"],
        "execution_mode": decision["execution_plan"]["mode"],
        "verification_command": "pytest tests/test_parser.py",
        "context_used": [{"source": "src/parser.py"}],
    }
    assert guard.evidence_router_receipt_errors(contract, receipt) == []


def test_enforced_security_receipt_requires_independent_review_evidence(guard):
    decision = guard.evidence_route_payload({
        "intent": "fix auth bypass",
        "task_signal": "security",
        "affected_paths": ["src/auth.py"],
        "adapter": "claude",
        "user_overrides": {"rollout": "enforced"},
    })
    contract = {"evidence_router": decision}
    receipt = {
        "decision_id": decision["decision_id"],
        "execution_mode": decision["execution_plan"]["mode"],
        "verification_command": "pytest tests/test_auth.py",
        "context_used": [{"source": "src/auth.py"}],
    }
    errors = guard.evidence_router_receipt_errors(contract, receipt)
    assert any("independent PASS" in error for error in errors)
    receipt["independent_review"] = {
        "result": "PASS",
        "evidence": "reviewer verified the changed trust boundary",
    }
    assert guard.evidence_router_receipt_errors(contract, receipt) == []


def test_enforced_low_confidence_route_requires_recorded_resolution(guard):
    decision = route(
        guard,
        intent="prove there is no other parser implementation",
        user_overrides={"rollout": "enforced"},
    )
    receipt = {
        "decision_id": decision["decision_id"],
        "execution_mode": decision["execution_plan"]["mode"],
        "verification_command": "pytest tests/test_parser.py",
        "context_used": [{"source": "src/parser.py"}],
        "coverage_evidence": "full repository search plus manifests",
    }
    errors = guard.evidence_router_receipt_errors(
        {"evidence_router": decision}, receipt,
    )
    assert any("router_low_confidence_resolution" in error for error in errors)
    receipt["router_low_confidence_resolution"] = "read sources and ran independent search"
    assert guard.evidence_router_receipt_errors(
        {"evidence_router": decision}, receipt,
    ) == []


# ------------------------------------------------- route digest (token budget)

def test_digest_is_much_smaller_but_keeps_the_acting_fields(guard):
    """os-start and every os-status reprinted the full decision; digest replaces it."""
    decision = route(guard)
    digest = guard.evidence_route_digest(decision)
    full_bytes = len(json.dumps(decision))
    digest_bytes = len(json.dumps(digest))
    assert digest_bytes < full_bytes / 2, (full_bytes, digest_bytes)
    # decision_id is the join key between contract, receipt and seal — losing it
    # would break receipt validation, not just readability.
    assert digest["decision_id"] == decision["decision_id"]
    assert digest["digest"] is True
    for key in ("evidence_plan", "verification_plan", "limitations", "fallbacks"):
        assert key in digest
    assert len(digest["evidence_plan"]) == len(decision["evidence_plan"])
    assert digest["execution"]["mode"] == decision["execution_plan"]["mode"]
    assert digest["rollout"]["mode"] == decision["rollout"]["mode"]


def test_digest_passes_rejections_and_non_decisions_through(guard):
    rejected = guard.evidence_route_payload({"task_signal": 5})
    assert guard.evidence_route_digest(rejected) is rejected
    assert guard.evidence_route_digest({}) == {}


def test_compatibility_wrappers_keep_v1_result_and_attach_router(guard):
    routed = guard.route_task_payload({
        "task_signal": "bug fix",
        "task_scope": "fix parser",
        "affected_paths": ["src/parser.py"],
    })
    assert routed["result"] == "route_suggested"
    assert routed["task_signal"] == "bug fix"
    assert routed["evidence_router"]["result"] == "evidence_route"

    scheduled = guard.scheduler_suggest_payload({
        "task_signal": "bug fix",
        "intent": "fix parser",
        "affected_paths": ["src/parser.py"],
    })
    assert scheduled["result"] == "scheduler_suggested"
    assert "contract_skeleton" in scheduled
    assert scheduled["evidence_router"]["result"] == "evidence_route"


def test_os_start_persists_router_in_contract_state_and_report_without_learning_db(
    guard, monkeypatch, tmp_path, capsys,
):
    repo = tmp_path / "consumer"
    piloth = repo / "pilothOS"
    state = piloth / "memory" / "state"
    state.mkdir(parents=True)
    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    monkeypatch.setattr(guard, "PILOTHOS_DIR", piloth)
    monkeypatch.setattr(guard, "REPO_KEY", hashlib.sha256(
        str(repo.resolve()).encode("utf-8")
    ).hexdigest()[:16])
    monkeypatch.setattr(guard, "OS_RUNS_DIR", state / "os-runs")
    monkeypatch.setattr(guard, "OS_CURRENT", state / "os-runs" / "current.json")
    monkeypatch.setattr(guard, "SCHEDULER_HISTORY", state / "scheduler-history.jsonl")
    monkeypatch.setattr(guard, "MARKER_DIR", repo / ".tmp-markers")

    guard.os_start([json.dumps({
        "task_id": "router-integration",
        "intent": "fix parser regression",
        "task_signal": "bug fix",
        "affected_paths": ["src/parser.py", "tests/test_parser.py"],
        "adapter": "claude",
    })])
    started = json.loads(capsys.readouterr().out)
    assert started["result"] == "os_started"
    assert started["evidence_router"]["decision_id"].startswith("er-")
    assert "evidence_learning" not in started
    assert not list(state.glob("evidence-router.sqlite3*"))
    assert not guard.SCHEDULER_HISTORY.exists()

    contract = json.loads(
        (state / "os-runs/router-integration/contract.json").read_text(encoding="utf-8")
    )
    os_state = json.loads(
        (state / "os-runs/router-integration/state.json").read_text(encoding="utf-8")
    )
    assert contract["decision_id"] == started["evidence_router"]["decision_id"]
    assert contract["execution_plan"]["mode"] == "single"
    assert os_state["evidence_router"]["decision_id"] == contract["decision_id"]

    guard.os_report(["router-integration"])
    report = json.loads(capsys.readouterr().out)
    assert report["evidence_router"]["decision_id"] == contract["decision_id"]
    assert "evidence_learning" not in report

    fields = guard.receipt_template_router_fields(contract)
    assert fields["decision_id"] == contract["decision_id"]
    assert fields["evidence_router"]["verification_methods"]


def _matrix_with_floor(guard, tmp_path, **floor_overrides):
    """The shipped matrix with an edited quality_floor, pointed at by the guard.

    Uses the real task_matrix so only the floor differs from production.
    """
    matrix = json.loads(guard.EVIDENCE_ROUTER_MATRIX.read_text(encoding="utf-8"))
    matrix["quality_floor"].update(floor_overrides)
    path = tmp_path / "evidence-routing.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    return path


def test_default_quality_floor_matches_the_shipped_registry(guard):
    """The embedded fallback and the shipped JSON must agree, otherwise the router
    silently changes policy when the registry is unreadable."""
    shipped = json.loads(guard.EVIDENCE_ROUTER_MATRIX.read_text(encoding="utf-8"))
    assert shipped["quality_floor"] == guard.DEFAULT_QUALITY_FLOOR
    assert guard.evidence_router_default_matrix()["quality_floor"] == guard.DEFAULT_QUALITY_FLOOR


def test_registry_floor_overrides_the_embedded_default(guard, monkeypatch, tmp_path):
    monkeypatch.setattr(
        guard, "EVIDENCE_ROUTER_MATRIX",
        _matrix_with_floor(guard, tmp_path, specialist_score=95, team_score=99),
    )
    resolved = guard.evidence_router_quality_floor()
    assert resolved["specialist_score"] == 95
    assert resolved["team_score"] == 99
    # Keys the registry does not mention still come from the default.
    assert resolved["route_confidence"] == guard.DEFAULT_QUALITY_FLOOR["route_confidence"]


def test_partial_registry_floor_cannot_drop_a_threshold(guard, monkeypatch, tmp_path):
    """A malformed or truncated quality_floor must not remove a floor — the
    defaults backfill every key the registry omits."""
    matrix = json.loads(guard.EVIDENCE_ROUTER_MATRIX.read_text(encoding="utf-8"))
    matrix["quality_floor"] = {"specialist_score": 42, "team_score": "not-a-number"}
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(matrix), encoding="utf-8")
    monkeypatch.setattr(guard, "EVIDENCE_ROUTER_MATRIX", path)
    resolved = guard.evidence_router_quality_floor()
    assert resolved["specialist_score"] == 42
    # Non-numeric values are ignored rather than accepted as a threshold.
    assert resolved["team_score"] == guard.DEFAULT_QUALITY_FLOOR["team_score"]
    assert set(resolved) == set(guard.DEFAULT_QUALITY_FLOOR)


def test_raising_specialist_floor_disqualifies_a_qualified_candidate(
    guard, monkeypatch, tmp_path,
):
    """The decisive test for the registry being real policy: the same candidate
    that qualifies under the shipped floor must stop qualifying when the JSON
    raises it. Before this, the floor was loaded, echoed into the payload, and
    then ignored by the decision, which used a hard-coded 70."""
    baseline = route(guard, specialists=[_consumer_specialist()])
    selected = baseline["execution_plan"]["specialist"]
    # This candidate scores a perfect 100 under the shipped floor, so the raised
    # floor has to exceed 100 to change the outcome.
    assert selected is not None and selected["score"] <= 100

    monkeypatch.setattr(
        guard, "EVIDENCE_ROUTER_MATRIX",
        _matrix_with_floor(guard, tmp_path, specialist_score=101),
    )
    raised = route(guard, specialists=[_consumer_specialist()])
    assert raised["execution_plan"]["specialist"] is None
    assert any("101/100" in reason for reason in raised["decision_reasons"])
    assert raised["rollout"]["quality_floor"]["specialist_score"] == 101


def test_raising_team_floor_disables_team_execution(guard, monkeypatch, tmp_path):
    """Team must be reached via team_score here, NOT via a mandatory independent
    review: for security / release-deploy signals the safety reviewer deliberately
    overrides the score threshold, so such a route would stay team-mode no matter
    what the floor says. This payload qualifies on score alone."""
    payload = {
        "intent": "restructure module boundaries across api, core and worker layers",
        "task_signal": "architecture",
        "affected_paths": [
            "src/api/a.py", "src/api/b.py", "src/core/c.py", "src/core/d.py",
            "src/worker/e.py", "src/worker/f.py", "src/db/g.py", "src/db/h.py",
            "tests/test_all.py",
        ],
        "work_packages": [
            {"id": "impl", "scope": "module split", "independent": True},
            {"id": "verify", "scope": "boundary verification", "independent": True},
        ],
        "specialists": [_consumer_specialist(
            id="consumer.arch-specialist",
            domains=["architecture"],
            task_types=["architecture_change"],
        )],
        "adapter": "claude",
    }
    baseline = guard.evidence_route_payload(dict(payload))
    assert baseline["execution_plan"]["mandatory_independent_review"] is False
    assert baseline["execution_plan"]["team"] is True

    monkeypatch.setattr(
        guard, "EVIDENCE_ROUTER_MATRIX",
        _matrix_with_floor(guard, tmp_path, team_score=101),
    )
    raised = guard.evidence_route_payload(dict(payload))
    assert raised["execution_plan"]["team"] is False
    assert any("threshold 101" in reason for reason in raised["decision_reasons"])


def test_receipt_errors_use_the_floor_recorded_in_the_decision(guard, monkeypatch, tmp_path):
    """A receipt is judged against the floor that was in force when the route was
    decided, so editing the registry mid-task cannot retroactively change what an
    already-issued route demanded."""
    contract = {
        "evidence_router": {
            "decision_id": "er-abc",
            "confidence": 0.75,
            "execution_plan": {"mode": "single"},
            "rollout": {"mode": "enforced", "quality_floor": {"route_confidence": 0.70}},
            "evidence_plan": [],
        },
    }
    receipt = {"decision_id": "er-abc", "execution_mode": "single"}
    # 0.75 clears the recorded 0.70 floor -> no low-confidence resolution demanded.
    errors = guard.evidence_router_receipt_errors(contract, receipt)
    assert not any("low_confidence_resolution" in e for e in errors)

    # Same receipt, decision recorded under the stricter shipped floor -> demanded.
    contract["evidence_router"]["rollout"]["quality_floor"] = {"route_confidence": 0.80}
    errors = guard.evidence_router_receipt_errors(contract, receipt)
    assert any("router_low_confidence_resolution" in e for e in errors)


def test_router_json_round_trip_has_no_non_json_values(guard):
    payloads = [
        {"intent": "", "task_signal": "not_applicable"},
        {"intent": "UI button", "task_signal": "UI/component", "affected_paths": ["src/Button.tsx"]},
        {"intent": "architecture", "task_signal": "architecture", "affected_paths": ["**/*"]},
        {"intent": "release", "task_signal": "release/deploy", "budget": {"max_roles": 999}},
    ]
    for payload in payloads:
        encoded = json.dumps(guard.evidence_route_payload(payload))
        decoded = json.loads(encoded)
        assert REQUIRED_ROUTE_FIELDS <= set(decoded)

