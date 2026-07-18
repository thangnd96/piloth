"""Unit tests for deterministic routing / reuse scan payloads.

These functions decide which context layers get loaded (token cost) and which
reuse candidates require a review decision (correctness), so their contracts
are worth pinning down.
"""

VALID_SIGNALS = {
    "API/backend",
    "UI/component",
    "bug fix",
    "not_applicable",
    "release/deploy",
    "tool/MCP",
}


def test_route_rejects_missing_task_signal(guard):
    out = guard.route_task_payload({})
    assert out["result"] == "route_rejected"
    assert any("task_signal must be one of" in e for e in out["errors"])


def test_route_rejects_unknown_task_signal(guard):
    out = guard.route_task_payload({"task_signal": "make-it-nice"})
    assert out["result"] == "route_rejected"


def test_route_accepts_valid_signal_and_routes_context(guard):
    out = guard.route_task_payload(
        {"task_signal": "tool/MCP", "task_scope": "add guard command", "affected_layers": ["Tools/Runtime"]}
    )
    assert out["result"] == "route_suggested"
    assert out["task_signal"] == "tool/MCP"
    # Routing must select a bounded context set, not "load everything".
    assert isinstance(out["context_layers"], list) and out["context_layers"]


def test_route_context_is_bounded_not_whole_kernel(guard):
    """Token guardrail: a routed task should not pull the entire kernel."""
    out = guard.route_task_payload(
        {"task_signal": "bug fix", "task_scope": "fix off-by-one", "affected_layers": ["Tools/Runtime"]}
    )
    # A routed context set is a short list, not dozens of files.
    assert len(out["context_layers"]) <= 8


def test_reuse_scan_has_stable_shape(guard):
    out = guard.reuse_scan_payload({"changed_files": ["pilothOS/scripts/pilothos_guard.py"]})
    for key in ("result", "candidates", "high_confidence_candidates", "learning_suggestions"):
        assert key in out
    assert out["result"] == "reuse_scan"
    assert isinstance(out["candidates"], list)


def test_reuse_scan_empty_changeset_has_no_candidates(guard):
    out = guard.reuse_scan_payload({"changed_files": []})
    assert out["candidates"] == []
    assert out["high_confidence_candidates"] == []
