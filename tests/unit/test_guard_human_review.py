"""Unit tests for the structured human_review gate.

Covers the pure decision functions behind the Governed Visual Review round-trip:
  - required_gates_for_task: gate appears iff the contract requests it;
  - validate_review_feedback: schema + enum + location validation;
  - validate_human_review_gate: PASS/FAIL/NOT_APPLICABLE, including the
    loophole where a receipt self-declares PASS with no backing artifact.

latest_review_feedback is monkeypatched so tests never touch the filesystem.
"""


def _fb(**over):
    base = {
        "verdict": "approve",
        "finalized": True,
        "review_round": 1,
        "findings": [
            {"id": "f1", "location": {"gate": "scope"}, "note": "n",
             "severity": "minor", "disposition": "approve"},
        ],
    }
    base.update(over)
    return base


# ---- required_gates_for_task ----

def test_required_gates_includes_human_review_when_flagged(guard):
    gates = guard.required_gates_for_task(
        {"requires_human_review": True, "affected_layers": ["Docs"], "mode": "standard"})
    assert "human_review" in gates


def test_required_gates_excludes_human_review_by_default(guard):
    gates = guard.required_gates_for_task(
        {"affected_layers": ["Docs"], "mode": "standard"})
    assert "human_review" not in gates


# ---- validate_review_feedback ----

def test_feedback_accepts_wellformed(guard):
    assert guard.validate_review_feedback(_fb()) == []


def test_feedback_rejects_bad_severity(guard):
    errs = guard.validate_review_feedback(_fb(findings=[
        {"id": "f1", "location": {"gate": "scope"}, "note": "n",
         "severity": "critical", "disposition": "approve"}]))
    assert any("severity" in e for e in errs)


def test_feedback_rejects_bad_disposition(guard):
    errs = guard.validate_review_feedback(_fb(findings=[
        {"id": "f1", "location": {"gate": "scope"}, "note": "n",
         "severity": "minor", "disposition": "maybe"}]))
    assert any("disposition" in e for e in errs)


def test_feedback_rejects_bad_verdict(guard):
    assert any("verdict" in e for e in guard.validate_review_feedback(_fb(verdict="lgtm")))


def test_feedback_rejects_non_bool_finalized(guard):
    assert any("finalized" in e for e in guard.validate_review_feedback(_fb(finalized="yes")))


def test_feedback_rejects_findings_not_list(guard):
    assert any("findings" in e for e in guard.validate_review_feedback(_fb(findings="nope")))


def test_feedback_rejects_location_without_file_or_gate(guard):
    errs = guard.validate_review_feedback(_fb(findings=[
        {"id": "f1", "location": {}, "note": "n", "severity": "minor", "disposition": "approve"}]))
    assert any("location" in e for e in errs)


# ---- validate_human_review_gate ----

def test_gate_not_applicable_when_not_required(guard):
    errs, summary = guard.validate_human_review_gate(
        {"task_id": "t"}, {"requires_human_review": False}, {}, [])
    assert errs == [] and summary["result"] == "NOT_APPLICABLE"


def test_gate_fails_when_no_feedback_even_if_receipt_claims_pass(guard, monkeypatch):
    # Loophole closure: receipt self-declares PASS, but no backing artifact → FAIL.
    monkeypatch.setattr(guard, "latest_review_feedback", lambda tid: None)
    receipt = {"quality_gates": {"human_review": {"result": "PASS", "evidence": "x"}}}
    errs, summary = guard.validate_human_review_gate(
        {"task_id": "t"}, {"requires_human_review": True}, receipt, [])
    assert errs and summary["result"] == "FAIL"


def test_gate_fails_when_not_finalized(guard, monkeypatch):
    monkeypatch.setattr(guard, "latest_review_feedback", lambda tid: _fb(finalized=False))
    errs, _ = guard.validate_human_review_gate(
        {"task_id": "t"}, {"requires_human_review": True}, {}, [])
    assert any("not finalized" in e for e in errs)


def test_gate_fails_with_unresolved_blocker(guard, monkeypatch):
    fb = _fb(verdict="request-changes", finalized=True, review_round=2, findings=[
        {"id": "f9", "location": {"gate": "correctness"}, "note": "x",
         "severity": "blocker", "disposition": "request-changes"}])
    monkeypatch.setattr(guard, "latest_review_feedback", lambda tid: fb)
    errs, summary = guard.validate_human_review_gate(
        {"task_id": "t"}, {"requires_human_review": True}, {}, [])
    assert summary["result"] == "FAIL" and "f9" in summary.get("unresolved", [])


def test_gate_fails_when_verdict_not_approve(guard, monkeypatch):
    monkeypatch.setattr(guard, "latest_review_feedback",
                        lambda tid: _fb(verdict="request-changes", finalized=True))
    errs, summary = guard.validate_human_review_gate(
        {"task_id": "t"}, {"requires_human_review": True}, {}, [])
    assert summary["result"] == "FAIL" and any("verdict" in e for e in errs)


def test_gate_passes_on_approve_finalized(guard, monkeypatch):
    monkeypatch.setattr(guard, "latest_review_feedback",
                        lambda tid: _fb(verdict="approve", finalized=True, review_round=3, reviewer="qa"))
    errs, summary = guard.validate_human_review_gate(
        {"task_id": "t"}, {"requires_human_review": True}, {}, [])
    assert errs == [] and summary["result"] == "PASS" and summary["review_round"] == 3
