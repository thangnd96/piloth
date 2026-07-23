"""Unit tests for the discovery gate wiring.

Discovery is a judgment gate the phase runs up front (not a mechanical hook);
the only mechanical parts are:
  - the contract carries requires_discovery / discovery_decisions / model_hints
    (passthrough), and requires_prototype implies requires_human_review;
  - every contract carries an advisory phase_plan_suggestion;
  - discovery decisions are recordable as os-evidence (kind=discovery) so the
    Traceability gate has something to trace to.
"""


# ---- contract passthrough ----

def test_contract_passes_through_discovery_fields(guard):
    c = guard.build_os_contract(
        {"requires_discovery": True,
         "discovery_decisions": [{"q": "Layout?", "answer": "sidebar", "source": "user"}],
         "model_hints": {"discovery": "strong"},
         "allowed_paths": ["docs/x.md"]},
        {}, {})
    assert c.get("requires_discovery") is True
    assert c.get("discovery_decisions") == [{"q": "Layout?", "answer": "sidebar", "source": "user"}]
    assert c.get("model_hints") == {"discovery": "strong"}


def test_requires_prototype_implies_human_review(guard):
    c = guard.build_os_contract(
        {"requires_prototype": True, "allowed_paths": ["src/App.tsx"]}, {}, {})
    assert c.get("requires_prototype") is True
    assert c.get("requires_human_review") is True


def test_contract_has_phase_plan_suggestion(guard):
    c = guard.build_os_contract({"allowed_paths": ["docs/x.md"]}, {}, {})
    suggestion = c.get("phase_plan_suggestion")
    assert isinstance(suggestion, dict)
    assert "recommend_prototype" in suggestion and "recommend_discovery" in suggestion


# ---- discovery evidence validation ----

def _disc(**over):
    base = {
        "kind": "discovery",
        "decisions": [{"q": "Layout?", "answer": "sidebar", "source": "user"}],
    }
    base.update(over)
    return base


def test_discovery_evidence_accepts_wellformed(guard):
    assert guard.validate_discovery_evidence(_disc()) == []


def test_discovery_evidence_rejects_empty_decisions(guard):
    assert guard.validate_discovery_evidence(_disc(decisions=[])) != []


def test_discovery_evidence_rejects_missing_answer(guard):
    errs = guard.validate_discovery_evidence(_disc(decisions=[{"q": "Layout?"}]))
    assert any("answer" in e for e in errs)


def test_discovery_evidence_rejects_missing_question(guard):
    errs = guard.validate_discovery_evidence(_disc(decisions=[{"answer": "sidebar"}]))
    assert any("q" in e or "question" in e for e in errs)


def test_discovery_evidence_ignores_other_kinds(guard):
    assert guard.validate_discovery_evidence({"kind": "metric"}) == []


def test_discovery_is_a_known_evidence_kind(guard):
    assert "discovery" in guard.OS_EVIDENCE_KINDS


# ---- end-to-end evidence sanitization (keys survive the allow-list) ----

def test_discovery_payload_survives_sanitization(guard):
    sanitized, errors = guard.sanitize_os_evidence_payload(_disc())
    assert errors == []
    assert sanitized.get("decisions") == [{"q": "Layout?", "answer": "sidebar", "source": "user"}]


def test_prototype_payload_survives_sanitization(guard):
    payload = {
        "kind": "prototype",
        "method": "artifacts",
        "options": [{"id": "option1", "artifact": "a1.html"}, {"id": "option2", "artifact": "a2.html"}],
        "chosen": "option2",
    }
    sanitized, errors = guard.sanitize_os_evidence_payload(payload)
    assert errors == []
    assert sanitized.get("chosen") == "option2" and len(sanitized.get("options")) == 2
