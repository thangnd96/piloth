"""Taxonomy + error-clarity locks (fixes from the landing-page dogfood).

Guards against silent drift between enum constants, their validators, their
error messages and the docs — and pins the ergonomics fixes (browser_smoke
metric type, gate predicates, cross-project advisory, os-start --explain).
"""


def test_browser_smoke_is_an_accepted_metric_type(guard):
    assert "browser_smoke" in guard.METRIC_TYPES
    errors = guard.validate_metric_evidence(
        {"kind": "metric", "metric_type": "browser_smoke", "metric_name": "render smoke"}
    )
    assert not any("metric_type" in e for e in errors)


def test_unknown_metric_type_still_rejected(guard):
    errors = guard.validate_metric_evidence(
        {"kind": "metric", "metric_type": "bogus", "metric_name": "x"}
    )
    assert any("metric_type" in e for e in errors)


def test_design_decision_vocab_is_single_source(guard):
    # The two names must be the SAME object so they cannot drift apart.
    assert guard.SEMANTIC_REVIEW_DECISIONS is guard.UI_DESIGN_SYSTEM_DECISIONS
    # Asset-routing decisions are a DIFFERENT concept and must stay distinct.
    assert guard.ASSET_ROUTING_DECISIONS != guard.UI_DESIGN_SYSTEM_DECISIONS


def test_metric_types_are_all_documented(guard):
    doc = (guard.PILOTHOS_DIR / "runtime" / "os-control-plane.md").read_text(encoding="utf-8")
    for metric_type in guard.METRIC_TYPES:
        assert f"`{metric_type}`" in doc, f"{metric_type} missing from os-control-plane.md"


def test_promoted_to_error_lists_valid_targets(guard):
    errors = guard.validate_learning_review(
        {"mistake_checked": "wrong_tool", "lesson_decision": "promoted",
         "promoted_to": "bogus", "reason": "x"}
    )
    msg = " ".join(e for e in errors if "promoted_to" in e)
    assert "tools/index.md" in msg and "upstream" in msg


def test_lesson_decision_error_lists_valid_values(guard):
    errors = guard.validate_learning_review(
        {"mistake_checked": "none", "lesson_decision": "ignored",
         "promoted_to": "not_applicable", "reason": "x"}
    )
    msg = " ".join(e for e in errors if "lesson_decision" in e)
    assert "deferred" in msg and "promoted" in msg


def test_cross_project_advisory_fires_only_when_hooks_missed(guard):
    empty = {"changed_files": {}}
    dirty_target = {"changed_paths": ["index.html"]}
    # empty diff-facts + non-empty target-diff -> advisory
    assert guard.cross_project_enforcement_advisory(empty, dirty_target)
    # diff-facts populated (hooks fired) -> no advisory
    assert guard.cross_project_enforcement_advisory({"changed_files": {"a": 1}}, dirty_target) == ""
    # nothing changed on the target -> no advisory
    assert guard.cross_project_enforcement_advisory(empty, {"changed_paths": []}) == ""


def test_os_start_explain_schema(guard):
    payload = guard.os_start_schema_payload()
    assert payload["result"] == "os_start_schema"
    assert "mode" in payload["fields"]
    assert "adaptive" in payload["fields"]["mode"]["allowed"]
    assert payload["fields"]["evidence_profile"]["allowed"] == sorted(guard.EVIDENCE_PROFILES)
