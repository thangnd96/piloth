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


# ---------------------------------------------- mode-aware context (P7.1)

def test_lean_mode_loads_fewer_tokens_than_standard(guard):
    std = guard.context_budget_payload({"task_signal": "bug fix"})
    lean = guard.context_budget_payload({"task_signal": "bug fix", "mode": "lean"})
    assert lean["context_mode"] == "lean"
    assert std["context_mode"] == "standard"
    assert lean["loaded_tokens_est"] < std["loaded_tokens_est"]


def test_lean_mode_drops_standard_only_context_docs(guard):
    lean = guard.context_budget_payload({"task_signal": "bug fix", "mode": "lean"})
    names = [f["file"] for f in lean["loaded_files"]]
    for dropped in guard.LEAN_DROPPED_CONTEXT:
        assert dropped not in names


def test_default_mode_is_standard_and_unchanged(guard):
    # No mode == standard: nothing dropped (backward compatible).
    std = guard.context_budget_payload({"task_signal": "bug fix"})
    names = [f["file"] for f in std["loaded_files"]]
    assert std["context_mode"] == "standard"
    assert "evaluation/quality-gates.md" in names  # still present in standard


def test_micro_mode_loads_less_than_lean_than_standard(guard):
    std = guard.context_budget_payload({"task_signal": "bug fix"})
    lean = guard.context_budget_payload({"task_signal": "bug fix", "mode": "lean"})
    micro = guard.context_budget_payload({"task_signal": "bug fix", "mode": "micro"})
    assert micro["context_mode"] == "micro"
    assert micro["loaded_tokens_est"] < lean["loaded_tokens_est"] < std["loaded_tokens_est"]


def test_lean_uses_lazy_rot_dropping_registry(guard):
    lean = guard.context_budget_payload({"task_signal": "bug fix", "mode": "lean"})
    std = guard.context_budget_payload({"task_signal": "bug fix"})
    lean_names = [f["file"] for f in lean["loaded_files"]]
    std_names = [f["file"] for f in std["loaded_files"]]
    assert "rot/registry.md" in std_names        # standard keeps the full table
    assert "rot/registry.md" not in lean_names    # lean uses rot-status instead


def test_rot_status_is_compact_and_reports_health(guard):
    out = guard.rot_status_payload()
    assert out["result"] == "rot_status"
    assert set(out) >= {"healthy", "overdue", "overdue_count", "note"}
    assert isinstance(out["overdue"], list)


def test_micro_mode_drops_constitution_and_rot_from_bootstrap(guard):
    micro = guard.context_budget_payload({"task_signal": "bug fix", "mode": "micro"})
    names = [f["file"] for f in micro["loaded_files"]]
    for dropped in guard.MICRO_DROPPED_BOOTSTRAP:
        assert dropped not in names
    # still keeps the bare orientation entry point
    assert "bootstrap.md" in names and "rules/index.md" in names


def test_route_lean_drops_docs_but_standard_keeps_them(guard):
    lean = guard.route_task_payload({"task_signal": "bug fix", "mode": "lean"})
    std = guard.route_task_payload({"task_signal": "bug fix"})
    lean_ctx = lean["index_first"] + lean["context_layers"]
    std_ctx = std["index_first"] + std["context_layers"]
    assert "runtime/consumer-assets.md" in std_ctx
    assert "runtime/consumer-assets.md" not in lean_ctx
