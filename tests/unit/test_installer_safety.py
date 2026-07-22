"""Unit tests for installer safety invariants — the fail-closed core.

The installer's promise is "what is approved is exactly what is applied, not one
byte more". These pin the path-safety and writable-zone guards, plus the
settings-merge conflict rules, so a regression there can't silently widen what a
plan is allowed to touch.
"""
import pytest


# ------------------------------------------------------------------ safe_rel

def test_safe_rel_accepts_relative_in_repo(installer):
    assert installer.safe_rel("pilothOS/rot/registry.md") == "pilothOS/rot/registry.md"


@pytest.mark.parametrize("bad", ["/etc/passwd", "~/secret", "", "../outside", "pilothOS/../../etc/passwd"])
def test_safe_rel_rejects_unsafe_paths(installer, bad):
    with pytest.raises(installer.PlanError):
        installer.safe_rel(bad)


# ----------------------------------------------- check_target_writable_zone

def test_write_marker_always_allowed(installer):
    # returns None (no raise) for the marker op regardless of location
    assert installer.check_target_writable_zone("pilothOS/.initialized", "write_marker") is None


def test_core_pilothos_write_is_rejected(installer):
    with pytest.raises(installer.PlanError):
        installer.check_target_writable_zone("pilothOS/scripts/pilothos_guard.py", "create_from_payload")


def test_fill_placeholders_only_on_allowed_pilothos_file(installer):
    # allowed file: no raise
    assert installer.check_target_writable_zone("pilothOS/rot/registry.md", "fill_placeholders") is None
    # other pilothOS file: rejected
    with pytest.raises(installer.PlanError):
        installer.check_target_writable_zone("pilothOS/rules/index.md", "fill_placeholders")


def test_remove_path_restricted_to_allowlist(installer):
    # adapter dirs are removable
    assert installer.check_target_writable_zone(".cursor", "remove_path") is None
    # arbitrary paths are not
    with pytest.raises(installer.PlanError):
        installer.check_target_writable_zone("src/app.py", "remove_path")


def test_consumer_root_file_write_allowed(installer):
    # A non-pilothOS target with a normal op is allowed (no raise).
    assert installer.check_target_writable_zone("CLAUDE.md", "create_from_payload") is None


# --------------------------------------------- merge_settings_content rules

def test_deny_wins_over_allow(installer):
    consumer = {"permissions": {"allow": ["Bash(rm:*)"], "deny": []}}
    payload = {"permissions": {"deny": ["Bash(rm:*)"]}}
    notes = []
    out = installer.merge_settings_content(consumer, payload, {}, notes)
    assert "Bash(rm:*)" not in out["permissions"]["allow"]
    assert "Bash(rm:*)" in out["permissions"]["deny"]
    assert any("deny" in n for n in notes)


def test_allow_is_deduped(installer):
    consumer = {"permissions": {"allow": ["Bash(ls:*)"], "deny": []}}
    payload = {"permissions": {"allow": ["Bash(ls:*)"]}}
    out = installer.merge_settings_content(consumer, payload, {}, [])
    assert out["permissions"]["allow"].count("Bash(ls:*)") == 1


def test_env_conflict_needs_judgment(installer):
    consumer = {"env": {"PILOTHOS_VERSION": "1.0.0"}}
    payload = {"env": {"PILOTHOS_VERSION": "2.0.0"}}
    with pytest.raises(installer.NeedsJudgment):
        installer.merge_settings_content(consumer, payload, {}, [])


def test_identical_statusline_is_not_a_conflict(installer):
    sl = {"type": "command", "command": "echo hi"}
    out = installer.merge_settings_content({"statusLine": sl}, {"statusLine": sl}, {}, [])
    assert out["statusLine"] == sl


def test_hooks_merge_consumer_first_and_dedup(installer):
    entry = {"matcher": "*", "hooks": [{"type": "command", "command": "x"}]}
    consumer = {"hooks": {"PreToolUse": [entry]}}
    payload = {"hooks": {"PreToolUse": [entry]}}
    out = installer.merge_settings_content(consumer, payload, {}, [])
    assert out["hooks"]["PreToolUse"].count(entry) == 1


# --------------------------------------------------------------- adapter_set

def test_adapter_set_from_list_and_csv(installer):
    assert installer.adapter_set(["claude", "codex"]) == {"claude", "codex"}
    assert installer.adapter_set("claude,codex") == {"claude", "codex"}


def test_adapter_set_none_or_empty_is_all(installer):
    allf = {"claude", "cursor", "codex", "antigravity"}
    assert installer.adapter_set(None) == allf
    assert installer.adapter_set("") == allf
    assert installer.adapter_set([]) == allf


def test_adapter_set_rejects_unknown(installer):
    with pytest.raises(installer.PlanError):
        installer.adapter_set(["claude", "codez"])


# ------------------------------------- normalize_plan: adapters + gitignore

@pytest.fixture()
def staged_repo(installer, monkeypatch, tmp_path):
    """A tmp REPO_ROOT with all optional adapter dirs + a bare .gitignore staged,
    mimicking the post-staging state of a real install."""
    for d in (".cursor", ".codex", ".antigravity"):
        (tmp_path / d).mkdir()
    (tmp_path / ".gitignore").write_text("node_modules/\n", encoding="utf-8")
    monkeypatch.setattr(installer, "REPO_ROOT", tmp_path)
    return tmp_path


def test_normalize_injects_removals_for_unselected(installer, staged_repo):
    plan = {"plan_version": 1, "mode": "greenfield",
            "adapters": ["claude", "codex"], "steps": [{"op": "write_marker"}]}
    assert installer.normalize_plan(plan) is True
    removed = {s["target"] for s in plan["steps"] if s["op"] == "remove_path"}
    assert removed == {".cursor", ".antigravity"}   # codex kept, claude never optional
    assert plan["steps"][-1]["op"] == "write_marker"  # marker stays last


def test_normalize_gitignore_runtime_appends_missing(installer, staged_repo):
    plan = {"plan_version": 1, "mode": "greenfield",
            "adapters": ["claude", "cursor", "codex", "antigravity"],
            "steps": [{"op": "write_marker"}]}
    installer.normalize_plan(plan)
    gi = [s for s in plan["steps"]
          if s["op"] == "append_lines" and s["target"] == ".gitignore"]
    assert len(gi) == 1
    assert set(installer.PILOTHOS_GITIGNORE_LINES) <= set(gi[0]["lines"])
    assert "pilothOS/" not in gi[0]["lines"]


def test_normalize_gitignore_all_scope(installer, staged_repo):
    plan = {"plan_version": 1, "mode": "greenfield",
            "adapters": ["claude", "cursor", "codex", "antigravity"],
            "options": {"gitignore_scope": "all"}, "steps": [{"op": "write_marker"}]}
    installer.normalize_plan(plan)
    gi = [s for s in plan["steps"]
          if s["op"] == "append_lines" and s["target"] == ".gitignore"][0]
    assert "pilothOS/" in gi["lines"]


def test_normalize_is_idempotent(installer, staged_repo):
    plan = {"plan_version": 1, "mode": "greenfield",
            "adapters": ["claude", "codex"], "steps": [{"op": "write_marker"}]}
    installer.normalize_plan(plan)
    n = len(plan["steps"])
    assert installer.normalize_plan(plan) is False
    assert len(plan["steps"]) == n


def test_normalize_gitignore_skips_when_all_present(installer, monkeypatch, tmp_path):
    for d in (".cursor", ".codex", ".antigravity"):
        (tmp_path / d).mkdir()
    (tmp_path / ".gitignore").write_text(
        "\n".join(installer.PILOTHOS_GITIGNORE_LINES) + "\n", encoding="utf-8")
    monkeypatch.setattr(installer, "REPO_ROOT", tmp_path)
    plan = {"plan_version": 1, "mode": "greenfield",
            "adapters": ["claude", "cursor", "codex", "antigravity"],
            "steps": [{"op": "write_marker"}]}
    installer.normalize_plan(plan)
    assert [s for s in plan["steps"] if s.get("target") == ".gitignore"] == []


def test_validate_requires_adapters_when_optional_staged(installer, staged_repo):
    plan = {"plan_version": 1, "mode": "greenfield", "steps": [{"op": "write_marker"}]}
    with pytest.raises(installer.PlanError):
        installer.validate_and_simulate(plan)


def test_validate_adapters_must_include_claude(installer, staged_repo):
    plan = {"plan_version": 1, "mode": "greenfield",
            "adapters": ["codex"], "steps": [{"op": "write_marker"}]}
    with pytest.raises(installer.PlanError):
        installer.validate_and_simulate(plan)
