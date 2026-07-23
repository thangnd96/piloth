"""Unit tests for the advisory budget layer (budget_status).

Budget is advisory-only: it compares real token-telemetry spend to an optional
contract budget.max_usd and is surfaced in os-status / os-report, but it NEVER
blocks os-close (asserted structurally below).
"""


def _ledger_evidence(cost):
    return [{
        "kind": "metric", "metric_type": "llm_usage", "metric_name": "session-token-usage",
        "real_token_telemetry": True, "input_tokens": 1, "output_tokens": 1, "cost_usd": cost,
    }]


def test_budget_unavailable_without_ceiling(guard):
    st = guard.budget_status({}, _ledger_evidence(5.0))
    assert st["status"] == "advisory_unavailable"


def test_budget_unavailable_without_telemetry(guard):
    st = guard.budget_status({"budget": {"max_usd": 10}}, [])
    assert st["status"] == "advisory_unavailable"
    assert st["max_usd"] == 10.0


def test_budget_within(guard):
    st = guard.budget_status({"budget": {"max_usd": 10}}, _ledger_evidence(4.0))
    assert st["over_budget"] is False
    assert st["spent_usd"] == 4.0
    assert st["remaining_usd"] == 6.0


def test_budget_over(guard):
    st = guard.budget_status({"budget": {"max_usd": 10}}, _ledger_evidence(12.0))
    assert st["over_budget"] is True
    assert st["remaining_usd"] == -2.0


def test_budget_is_advisory_and_does_not_gate_os_close(guard):
    st = guard.budget_status({"budget": {"max_usd": 10}}, _ledger_evidence(12.0))
    assert st.get("advisory") is True and "note" in st
    # Structural guarantee: os_close_result never consults the budget, so an
    # over-budget run still seals — budget is advisory, not a gate.
    import inspect
    assert "budget_status" not in inspect.getsource(guard.os_close_result)
