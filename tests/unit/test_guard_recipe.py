"""Unit tests for suggest_phase_plan (recipe right-sizing, advisory-only).

The recipe layer recommends the front-half phases that would prevent rework but
NEVER enables them — auto-enabling a heavy phase would add cost, the opposite of
the intent. These tests pin the heuristic and, critically, that it never mutates
the request or turns on requires_prototype / requires_discovery.
"""


def test_bugfix_recommends_neither(guard):
    r = guard.suggest_phase_plan({"task_signal": "bugfix"}, ["src/x.ts"], ["code"], "code")
    assert r["recommend_prototype"] is False
    assert r["recommend_discovery"] is False


def test_docs_only_recommends_neither(guard):
    r = guard.suggest_phase_plan({}, ["docs/x.md"], ["docs"], "docs")
    assert r["recommend_prototype"] is False
    assert r["recommend_discovery"] is False


def test_ui_recommends_prototype(guard):
    r = guard.suggest_phase_plan({"task_signal": "ui/component"}, ["src/Button.tsx"], ["code"], "ui")
    assert r["recommend_prototype"] is True


def test_ambiguous_recommends_discovery(guard):
    r = guard.suggest_phase_plan(
        {"intent": "the architecture is unclear and the scope is ambiguous"},
        ["src/x.ts"], ["code"], "code")
    assert r["recommend_discovery"] is True


def test_broad_scope_recommends_discovery(guard):
    r = guard.suggest_phase_plan({}, ["**/*"], [], "generic")
    assert r["recommend_discovery"] is True


def test_suggestion_never_mutates_request(guard):
    req = {"task_signal": "ui/component"}
    guard.suggest_phase_plan(req, ["src/Button.tsx"], ["code"], "ui")
    assert "requires_prototype" not in req
    assert "requires_discovery" not in req


def test_suggestion_has_note_and_reasons(guard):
    r = guard.suggest_phase_plan({"task_signal": "ui/component"}, ["src/Button.tsx"], ["code"], "ui")
    assert r["note"]
    assert isinstance(r["reasons"], list) and r["reasons"]
