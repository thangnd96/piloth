"""Unit tests for payload_budget_payload — the tool-output footprint meter.

context-budget measured only half the bill. The other half is the JSON the
guard prints back: a full evidence-route decision was ~2.3k tokens and os-start,
os-status, route-task and scheduler-suggest each reprinted a copy of it, none of
which any meter or test could see. These lock that surface down the same way
CONTEXT_TOKEN_CEILINGS locks down loaded context.
"""
import json

import pytest


def test_meter_reports_every_probe_with_bytes_and_tokens(guard):
    out = guard.payload_budget_payload()
    assert out["result"] == "payload_budget"
    # Declared as tool_output, not llm_usage: it cannot back a "cheaper" claim.
    assert out["metric"] == "tool_output"
    names = [item["command"] for item in out["commands"]]
    assert names == [name for name, _probe in guard.PER_TASK_PAYLOAD_PROBES]
    for item in out["commands"]:
        assert item["bytes"] > 0, item
        assert item["tokens_est"] == (item["bytes"] + 3) // 4
    assert out["total_bytes"] == sum(i["bytes"] for i in out["commands"])


def test_meter_defaults_and_accepts_a_signal(guard):
    assert guard.payload_budget_payload()["task_signal"] == "bug fix"
    assert guard.payload_budget_payload(
        {"task_signal": "UI/component"},
    )["task_signal"] == "UI/component"
    # Non-dict input must degrade to the default, not raise.
    assert guard.payload_budget_payload("nope")["result"] == "payload_budget"


def test_printed_bytes_match_what_json_print_would_write(guard):
    payload = {"result": "x", "note": "ü"}
    expected = len(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
    ) + 1
    assert guard.printed_payload_bytes(payload) == expected


# Measured output per command plus headroom. LOWER only — raising one means every
# task pays more tokens. route-task is excluded: its size tracks how many assets
# the surrounding repo has, so it is guarded structurally below instead.
PAYLOAD_BYTE_CEILINGS = {
    "rot-status": 200,
    "codebase-status": 500,
    "adapter-capabilities": 1_700,
    # Measured on the unknown-adapter path (the fixture clears adapter env), i.e.
    # the worst case: it still carries the aggregate "unavailable" limitation.
    "evidence-route": 2_500,
}


@pytest.mark.parametrize("command", sorted(PAYLOAD_BYTE_CEILINGS))
def test_per_task_command_output_stays_under_its_ceiling(guard, command):
    sizes = {
        item["command"]: item["bytes"]
        for item in guard.payload_budget_payload()["commands"]
    }
    ceiling = PAYLOAD_BYTE_CEILINGS[command]
    assert sizes[command] <= ceiling, (
        f"{command} now prints {sizes[command]} bytes (ceiling {ceiling}). "
        "Trim the payload or raise the ceiling deliberately."
    )


def test_route_task_asset_rows_stay_minimal(guard):
    """Byte size here tracks how many assets the surrounding repo has, so the
    ratchet is on row *shape* instead: these two arrays are pure output (no
    validator, no documented shape), and they were four parallel views over the
    same asset set. Adding a field back re-inflates every row at once.
    """
    routed = guard.route_task_payload({"task_signal": "bug fix"})
    for row in routed["detected_assets"]:
        assert set(row) == {"asset", "type", "risk", "load_when", "health_status"}
    for row in routed["skipped_assets"]:
        assert set(row) == {"asset", "type"}
    # The skip rule is stated once, not per row — O(1) instead of O(assets).
    assert "not routed for" in routed["skipped_reason"]
    # The two contract-bound views keep their shape — validated elsewhere.
    for row in routed["consumer_asset_routing"]:
        assert set(row) == {"task_signal", "asset_type", "decision", "reason"}
    assert guard.validate_asset_routing(routed["consumer_asset_routing"]) == []


def test_contract_view_reasons_do_not_restate_their_own_row(guard):
    """The two contract shapes cannot be compacted (a validator requires every
    key as a non-empty string), so the saving here is in the guard-generated
    `reason` text: it used to repeat the task_signal that is already a field on
    the same entry, once per asset. The fields stay; the redundancy goes.
    """
    routed = guard.route_task_payload({"task_signal": "bug fix"})
    for row in routed["consumer_asset_routing"]:
        assert row["task_signal"] == "bug fix"
        assert "bug fix" not in row["reason"], row
    for row in routed["context_evidence"]:
        assert "bug fix" not in row["reason"], row
    # Still valid contract input after the rewording.
    assert guard.validate_asset_routing(routed["consumer_asset_routing"]) == []
    assert guard.validate_object_list(
        routed["context_evidence"], "context_evidence",
        ("source", "reason", "finding"),
    ) == []


def test_wrappers_attach_the_digest_not_the_full_decision(guard):
    """route-task carried 5.8 KB of full router decision inside a routing hint."""
    for payload in (
        guard.route_task_payload({"task_signal": "bug fix"}),
        guard.scheduler_suggest_payload(
            {"task_signal": "bug fix", "intent": "fix parser"},
        ),
    ):
        router = payload["evidence_router"]
        assert router["result"] == "evidence_route"   # v1 field kept
        assert router["digest"] is True
        assert "decision_reasons" not in router
