"""Unit tests for T3 Piloth Forge (governed self-extension).

Forge is the OS-defining capability: an agent can extend Piloth under governance.
construction != activation — forge-* modes are read-only (scaffold + verify +
present authority-delta); they never write files or grant authority.
"""

GOOD = {
    "kind": "skill",
    "id": "deploy-smoke-check",
    "layer": "Skills",
    "intent": "Run a post-deploy smoke check",
    "reason": "Incident: deploy broke prod; need a repeatable smoke",
    "authority": {"guard_modes": ["os-evidence"], "paths": ["pilothOS/memory/state/os-runs/**/artifacts/**"]},
}


def test_verify_good_spec_passes(guard):
    errors, _ = guard.forge_verify_findings(GOOD)
    assert errors == [], errors


def test_verify_catches_duplicate_id(guard):
    spec = dict(GOOD, id="os-start")  # already a guard-mode capability
    errors, _ = guard.forge_verify_findings(spec)
    assert any("da ton tai" in e for e in errors)


def test_verify_catches_layer_mismatch(guard):
    spec = dict(GOOD, layer="Rules")  # skill must be Skills
    errors, _ = guard.forge_verify_findings(spec)
    assert any("layer cho kind=skill" in e for e in errors)


def test_verify_requires_reason(guard):
    spec = dict(GOOD)
    spec.pop("reason")
    errors, _ = guard.forge_verify_findings(spec)
    assert any("reason thieu" in e for e in errors)


def test_verify_catches_bad_kind(guard):
    spec = dict(GOOD, kind="capsule")
    errors, _ = guard.forge_verify_findings(spec)
    assert any("kind phai thuoc" in e for e in errors)


def test_verify_catches_bad_authority_shape(guard):
    spec = dict(GOOD, authority={"paths": "should-be-list"})
    errors, _ = guard.forge_verify_findings(spec)
    assert any("authority" in e for e in errors)


def test_verify_warns_when_no_authority(guard):
    spec = dict(GOOD)
    spec.pop("authority")
    errors, warnings = guard.forge_verify_findings(spec)
    assert errors == []
    assert any("fail-closed" in w for w in warnings)


def test_target_paths_by_kind(guard):
    assert guard._forge_target_path(GOOD) == "pilothOS/skills/workflow/deploy-smoke-check/SKILL.md"
    assert guard._forge_target_path(dict(GOOD, kind="rule", layer="Rules")) == "pilothOS/rules/deploy-smoke-check.md"
    assert guard._forge_target_path(dict(GOOD, kind="gate", layer="Evaluation")) is None


def test_scaffold_fills_placeholders(guard):
    content = guard._forge_fill(guard._forge_template("skill"), GOOD)
    assert "{{id}}" not in content and "{{intent}}" not in content
    assert "deploy-smoke-check" in content
    assert GOOD["intent"] in content


def test_manifest_entry_shape(guard):
    entry = guard._forge_manifest_entry(GOOD)
    assert entry["id"] == "deploy-smoke-check"
    assert entry["kind"] == "skill"
    assert entry["authority"] == GOOD["authority"]


def test_plan_authority_delta_widens(guard):
    after = guard.resolve_authority(GOOD)
    delta = guard.compute_authority_delta(guard.resolve_authority({}), after)
    assert delta["widened"] is True
    assert "os-evidence" in delta["guard_modes"]["added"]


def test_scaffold_rule_fills_template(guard):
    spec = dict(GOOD, kind="rule", layer="Rules")
    content = guard._forge_fill(guard._forge_template("rule"), spec)
    assert "{{" not in content
    assert spec["intent"] in content and spec["reason"] in content


def test_verify_rejects_non_kebab_slug(guard):
    spec = dict(GOOD, id="Deploy_Check")
    errors, _ = guard.forge_verify_findings(spec)
    assert any("kebab-slug" in e for e in errors)


def test_forge_modes_registered_read_only(guard):
    for mode in ("forge-scaffold", "forge-verify", "forge-plan"):
        assert mode in guard.COMMAND_TABLE
        _handler, kind = guard.COMMAND_TABLE[mode]
        assert kind == "argv"
        assert mode in guard.READ_ONLY_GUARD_MODES


def test_governed_activation_keeps_manifest_valid(guard):
    # The governed loop: verify -> scaffold content -> (human) add manifest entry
    # -> capability-check still PASSES. A valid new capability doesn't corrupt.
    import copy
    spec = {
        "kind": "skill", "id": "part-d-check", "layer": "Skills",
        "intent": "a real project check", "reason": "recurring real need",
        "authority": {"guard_modes": ["os-evidence"]},
    }
    assert guard.forge_verify_findings(spec)[0] == []            # verify passes
    content = guard._forge_fill(guard._forge_template("skill"), spec)
    assert "{{" not in content and spec["intent"] in content     # scaffold content ready
    manifest = copy.deepcopy(guard.load_capability_manifest())
    manifest["capabilities"].append(guard._forge_manifest_entry(spec))
    assert guard.capability_check_findings(manifest)[0] == []    # activation keeps manifest valid


def test_gate_kind_scaffolds_no_file(guard):
    # gate needs guard wiring -> no file target (only skill/rule scaffold files).
    assert guard._forge_target_path({"kind": "gate", "id": "x", "layer": "Evaluation"}) is None
