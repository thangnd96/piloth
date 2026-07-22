"""Unit tests for the thin prototype gate.

Prototype reuses the human_review round-trip for the human sign-off; the
prototype gate only asserts prototype's own invariant — a valid design method,
>=2 options generated, and one chosen among them — read from the recorded
prototype evidence. Covered here:
  - required_gates_for_task: gate appears iff the contract requests it;
  - validate_prototype_evidence: schema + enum + >=2-options + chosen checks;
  - validate_prototype_gate: PASS/FAIL/NOT_APPLICABLE, including the loophole
    where a receipt self-declares PASS with no backing evidence record.

validate_prototype_gate reads the os_evidence list passed in, so tests never
touch the filesystem.
"""


def _proto(**over):
    base = {
        "kind": "prototype",
        "method": "artifacts",
        "options": [
            {"id": "option1", "artifact": "a1.html", "intent": "compact sidebar"},
            {"id": "option2", "artifact": "a2.html", "intent": "top-nav wide"},
        ],
        "chosen": "option2",
    }
    base.update(over)
    return base


# ---- required_gates_for_task ----

def test_required_gates_includes_prototype_when_flagged(guard):
    gates = guard.required_gates_for_task(
        {"requires_prototype": True, "affected_layers": ["Docs"], "mode": "standard"})
    assert "prototype" in gates


def test_required_gates_excludes_prototype_by_default(guard):
    gates = guard.required_gates_for_task(
        {"affected_layers": ["Docs"], "mode": "standard"})
    assert "prototype" not in gates


# ---- validate_prototype_evidence ----

def test_evidence_accepts_wellformed(guard):
    assert guard.validate_prototype_evidence(_proto()) == []


def test_evidence_rejects_single_option(guard):
    errs = guard.validate_prototype_evidence(_proto(options=[{"id": "option1"}]))
    assert any(">=2 options" in e for e in errs)


def test_evidence_rejects_bad_method(guard):
    errs = guard.validate_prototype_evidence(_proto(method="powerpoint"))
    assert any("method" in e for e in errs)


def test_evidence_rejects_chosen_not_in_options(guard):
    errs = guard.validate_prototype_evidence(_proto(chosen="option9"))
    assert any("chosen" in e for e in errs)


def test_evidence_rejects_missing_chosen(guard):
    errs = guard.validate_prototype_evidence(_proto(chosen=""))
    assert any("chosen" in e for e in errs)


def test_evidence_ignores_other_kinds(guard):
    assert guard.validate_prototype_evidence({"kind": "metric"}) == []


def test_prototype_is_a_known_evidence_kind(guard):
    assert "prototype" in guard.OS_EVIDENCE_KINDS


# ---- validate_prototype_gate ----

def test_gate_not_applicable_when_not_required(guard):
    summary = guard.validate_prototype_gate(
        {"task_id": "t"}, {"requires_prototype": False}, {}, [])
    assert summary["result"] == "NOT_APPLICABLE"


def test_gate_fails_when_no_evidence_even_if_receipt_claims_pass(guard):
    # Loophole closure: receipt self-declares PASS, but no backing evidence → FAIL.
    receipt = {"quality_gates": {"prototype": {"result": "PASS", "evidence": "x"}}}
    summary = guard.validate_prototype_gate(
        {"task_id": "t"}, {"requires_prototype": True}, receipt, [])
    assert summary["result"] == "FAIL"


def test_gate_fails_on_incomplete_evidence(guard):
    ev = [_proto(options=[{"id": "option1"}], recorded_at="2026-01-01T00:00:00")]
    summary = guard.validate_prototype_gate(
        {"task_id": "t"}, {"requires_prototype": True}, {}, ev)
    assert summary["result"] == "FAIL"


def test_gate_passes_on_complete_evidence(guard):
    ev = [_proto(recorded_at="2026-01-01T00:00:00")]
    summary = guard.validate_prototype_gate(
        {"task_id": "t"}, {"requires_prototype": True}, {}, ev)
    assert summary["result"] == "PASS"
    assert summary["options"] == 2 and summary["chosen"] == "option2"


def test_gate_uses_latest_evidence(guard):
    ev = [
        _proto(chosen="option1", recorded_at="2026-01-01T00:00:00"),
        _proto(chosen="option2", recorded_at="2026-01-02T00:00:00"),
    ]
    summary = guard.validate_prototype_gate(
        {"task_id": "t"}, {"requires_prototype": True}, {}, ev)
    assert summary["chosen"] == "option2"
