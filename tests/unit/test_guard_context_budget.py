"""Unit tests for context_budget_payload — the progressive-loading footprint meter.

These lock in the token-saving guarantee: a routed task must pull far less
kernel text than loading the whole kernel, and routing must not silently bloat.
"""


def test_rejects_non_dict(guard):
    out = guard.context_budget_payload("nope")
    assert out["result"] == "context_budget_rejected"


def test_bootstrap_only_loads_the_five_bootstrap_files(guard):
    out = guard.context_budget_payload({})
    assert out["routed"] is False
    assert out["loaded_count"] == len(guard.BOOTSTRAP_CONTEXT_FILES)
    names = [f["file"] for f in out["loaded_files"]]
    assert names == list(guard.BOOTSTRAP_CONTEXT_FILES)


def test_routed_task_stays_far_under_full_kernel(guard):
    out = guard.context_budget_payload(
        {"task_signal": "bug fix", "affected_layers": ["Tools/Runtime"]}
    )
    assert out["routed"] is True
    assert out["loaded_bytes"] < out["full_kernel_bytes"]
    # Progressive loading must save a large majority vs loading everything.
    assert out["savings_pct_vs_full_kernel"] >= 50.0


def test_routed_context_is_bounded(guard):
    """Regression guard: if routing ever balloons, this fails loudly."""
    for signal in ("bug fix", "UI/component", "API/backend", "tool/MCP", "release/deploy"):
        out = guard.context_budget_payload({"task_signal": signal})
        assert out["loaded_count"] <= 12, f"{signal} loads too many files"


def test_savings_pct_is_a_valid_percentage(guard):
    out = guard.context_budget_payload({"task_signal": "not_applicable"})
    assert 0.0 <= out["savings_pct_vs_full_kernel"] <= 100.0


def test_token_estimate_tracks_bytes(guard):
    out = guard.context_budget_payload({"task_signal": "bug fix"})
    # ~4 bytes per token heuristic.
    assert out["loaded_tokens_est"] == (out["loaded_bytes"] + 3) // 4
    assert out["metric"] == "context_load"
