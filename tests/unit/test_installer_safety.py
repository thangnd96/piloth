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
