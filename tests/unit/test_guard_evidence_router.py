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
    assert set(out["sources"].values()) == {"missing"}


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


def test_stale_partial_graph_never_becomes_source_grounded(guard):
    out = route(
        guard,
        codebase_graph={"freshness": "stale", "coverage": "partial"},
    )
    graph = next(item for item in out["evidence_plan"] if item["type"] == "code_graph")
    assert graph["trust"] == "untrusted_index"
    assert graph["confidence"] < 0.8
    assert out["confidence"] < 0.8
    assert any("not source-grounded" in item for item in out["limitations"])
    assert any(item["type"] == "source" and item["required"] for item in out["evidence_plan"])


def test_negative_claim_forces_complete_coverage_and_low_confidence_fallback(guard):
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
    assert out["confidence"] < 0.8
    assert any("ask the user" in fallback for fallback in out["fallbacks"])


def test_conflicting_evidence_requires_source_first_resolution(guard):
    out = route(guard, evidence_conflicts=["graph disagrees with source"])
    assert out["confidence"] < 0.8
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


def test_team_requires_score_independence_capability_and_budget(guard):
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
    assert plan["team_score"] >= 60
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


def test_qualified_consumer_specialist_precedes_piloth_fallback(guard):
    out = route(guard, specialists=[_consumer_specialist()])
    selected = out["execution_plan"]["specialist"]
    assert selected["id"] == "consumer.parser-specialist"
    assert selected["owner"] == "consumer"
    assert selected["score"] >= 70


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

