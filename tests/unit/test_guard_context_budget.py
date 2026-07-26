"""Unit tests for context_budget_payload — the progressive-loading footprint meter.

These lock in the token-saving guarantee: a routed task must pull far less
kernel text than loading the whole kernel, and routing must not silently bloat.

The meter is vendor tooling (`scripts/measure_budget.py`), not a shipped guard
verb, so these use the `budget` fixture rather than `guard`. Mode-specific cases
are gone with `lean`/`micro`: both surviving modes load identical context.
"""
import pytest


def test_rejects_non_dict(budget):
    out = budget.context_budget_payload("nope")
    assert out["result"] == "context_budget_rejected"


def test_bootstrap_only_loads_the_five_bootstrap_files(budget):
    out = budget.context_budget_payload({})
    assert out["routed"] is False
    assert out["loaded_count"] == len(budget.BOOTSTRAP_CONTEXT_FILES)
    names = [f["file"] for f in out["loaded_files"]]
    assert names == list(budget.BOOTSTRAP_CONTEXT_FILES)


def test_routed_task_stays_far_under_full_kernel(budget):
    out = budget.context_budget_payload(
        {"task_signal": "bug fix", "affected_layers": ["Tools/Runtime"]}
    )
    assert out["routed"] is True
    assert out["loaded_bytes"] < out["full_kernel_bytes"]
    # Progressive loading must save a large majority vs loading everything.
    assert out["savings_pct_vs_full_kernel"] >= 50.0


def test_routed_context_is_bounded(budget):
    """Regression guard: if routing ever balloons, this fails loudly."""
    for signal in ("bug fix", "UI/component", "API/backend", "tool/MCP", "release/deploy"):
        out = budget.context_budget_payload({"task_signal": signal})
        assert out["loaded_count"] <= 12, f"{signal} loads too many files"


def test_savings_pct_is_a_valid_percentage(budget):
    out = budget.context_budget_payload({"task_signal": "not_applicable"})
    assert 0.0 <= out["savings_pct_vs_full_kernel"] <= 100.0


def test_token_estimate_tracks_bytes(budget):
    out = budget.context_budget_payload({"task_signal": "bug fix"})
    # ~4 bytes per token heuristic.
    assert out["loaded_tokens_est"] == (out["loaded_bytes"] + 3) // 4
    assert out["metric"] == "context_load"


# ---------------------------------------------- mode-aware context (P7.1)

def test_default_mode_is_standard_and_unchanged(budget):
    # No mode == standard: nothing dropped (backward compatible).
    std = budget.context_budget_payload({"task_signal": "bug fix"})
    names = [f["file"] for f in std["loaded_files"]]
    assert std["context_mode"] == "standard"
    assert "evaluation/quality-gates.md" in names  # still present in standard


# ------------------------------------------- token ceilings (anti-bloat ratchet)

# Measured footprint per (task_signal, mode) plus ~2% headroom. `loaded_count`
# and a >=50% savings floor were the only guards before, and neither noticed the
# bootstrap set growing 2,209 bytes (+552 tok/task) when the evidence router and
# codebase intelligence docs landed: file count did not change and the full-kernel
# denominator grew alongside, so the percentage even improved.
#
# These numbers may only be LOWERED. Raising one means every consumer task pays
# more, so it is a decision to take deliberately, not a test to relax.
CONTEXT_TOKEN_CEILINGS = {
    ("not_applicable", "standard"): 5_500,
    ("UI/component", "standard"): 5_950,
    ("API/backend", "standard"): 6_550,
    ("release/deploy", "standard"): 7_000,
    ("bug fix", "standard"): 7_550,
}


@pytest.mark.parametrize(("signal", "mode"), sorted(CONTEXT_TOKEN_CEILINGS))
def test_routed_context_stays_under_its_token_ceiling(budget, signal, mode):
    out = budget.context_budget_payload({"task_signal": signal, "mode": mode})
    ceiling = CONTEXT_TOKEN_CEILINGS[(signal, mode)]
    assert out["loaded_tokens_est"] <= ceiling, (
        f"{signal}/{mode} now loads {out['loaded_tokens_est']} tok (ceiling "
        f"{ceiling}). Shrink the routed docs, or raise the ceiling deliberately "
        "and update docs/token-optimization.md with the new measurement."
    )


def test_ceilings_do_not_drift_far_above_the_measurement(budget):
    """A ceiling nobody tightened is a ceiling that stopped guarding anything."""
    for (signal, mode), ceiling in CONTEXT_TOKEN_CEILINGS.items():
        actual = budget.context_budget_payload(
            {"task_signal": signal, "mode": mode},
        )["loaded_tokens_est"]
        assert ceiling <= actual * 1.15, (
            f"{signal}/{mode} ceiling {ceiling} is far above the measured "
            f"{actual}; lower it so the ratchet keeps biting."
        )


def test_routable_denominator_is_reported_and_stricter_than_full_kernel(budget):
    """`skills/**` is 45% of the .md ceiling but is never routable context.

    Quoting the full-kernel percentage flatters the saving, so the honest
    denominator ships alongside it.
    """
    out = budget.context_budget_payload({"task_signal": "bug fix"})
    assert out["routable_kernel_bytes"] < out["full_kernel_bytes"]
    assert out["routable_kernel_files"] < out["full_kernel_files"]
    assert (
        out["savings_pct_vs_routable_kernel"]
        < out["savings_pct_vs_full_kernel"]
    )
    assert out["savings_pct_vs_routable_kernel"] >= 50.0
