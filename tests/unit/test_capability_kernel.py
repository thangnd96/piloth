"""Unit tests for the T0 capability & authority kernel.

Covers the pure decision functions behind capability-list / capability-check /
authority-delta: fail-closed resolution, manifest validation, and authority
delta (widening detection). These are the foundation the execution broker (T1)
and Forge (T3) build on, so their invariants are pinned here.
"""


def test_shipped_manifest_is_valid(guard):
    manifest = guard.load_capability_manifest()
    assert manifest is not None, "capability-manifest.json must exist and parse"
    errors, _warnings = guard.capability_check_findings(manifest)
    assert errors == [], f"shipped manifest must be valid, got: {errors}"


def test_manifest_status_reports_ok(guard):
    status = guard.capability_manifest_status()
    assert status["present"] is True
    assert status["ok"] is True
    assert status["capabilities"] >= 1


def test_resolve_authority_fail_closed_on_empty(guard):
    # No authority declared -> most-restrictive everything (fail-closed).
    resolved = guard.resolve_authority({})
    assert resolved == {
        "paths": [],
        "guard_modes": [],
        "entitlements": [],
        "enforcement_surface": [],
        "writes_policy": False,
    }


def test_resolve_authority_fills_missing_fields(guard):
    resolved = guard.resolve_authority({"authority": {"paths": ["a/**"], "writes_policy": True}})
    assert resolved["paths"] == ["a/**"]
    assert resolved["writes_policy"] is True
    # Undeclared fields default to empty (fail-closed), not inherited.
    assert resolved["entitlements"] == []
    assert resolved["guard_modes"] == []


def test_resolve_authority_coerces_wrong_types_to_failclosed(guard):
    # Wrong-typed fields are treated as the restrictive default, not trusted.
    resolved = guard.resolve_authority({"authority": {"paths": "not-a-list", "writes_policy": "yes"}})
    assert resolved["paths"] == []
    assert resolved["writes_policy"] is False


def test_capability_check_rejects_bad_manifest(guard):
    bad = {
        "schema_version": 2,
        "coverage": "partial",
        "capabilities": [
            {"id": "dup", "kind": "skill", "layer": "Skills"},
            {"id": "dup", "kind": "not-a-kind", "layer": "Nowhere",
             "authority": {"paths": "should-be-list", "writes_policy": "nope"}},
            {"kind": "gate", "layer": "Evaluation"},
        ],
    }
    errors, _warnings = guard.capability_check_findings(bad)
    joined = " ".join(errors)
    assert "schema_version" in joined
    assert any("trung lap" in e for e in errors)            # duplicate id
    assert any("kind" in e for e in errors)                 # bad kind
    assert any("layer" in e for e in errors)                # bad layer
    assert any("paths" in e for e in errors)                # wrong authority type
    assert any("writes_policy" in e for e in errors)        # wrong authority type
    assert any("id" in e for e in errors)                   # missing id


def test_capability_check_warns_unknown_fields(guard):
    manifest = {
        "schema_version": 1,
        "coverage": "full",
        "capabilities": [
            {"id": "x", "kind": "gate", "layer": "Evaluation",
             "authority": {"paths": [], "bogus_field": 1}, "extra_top": 2},
        ],
    }
    errors, warnings = guard.capability_check_findings(manifest)
    assert errors == []
    joined = " ".join(warnings)
    assert "bogus_field" in joined
    assert "extra_top" in joined


def test_authority_delta_detects_widening(guard):
    before = guard.resolve_authority({"authority": {"paths": ["a/**"]}})
    after = guard.resolve_authority({"authority": {
        "paths": ["a/**", "b/**"], "entitlements": ["deploy.production"], "writes_policy": True}})
    delta = guard.compute_authority_delta(before, after)
    assert delta["widened"] is True
    assert delta["paths"]["added"] == ["b/**"]
    assert delta["entitlements"]["added"] == ["deploy.production"]
    assert delta["writes_policy"] == {"before": False, "after": True}


def test_authority_delta_removal_only_not_widened(guard):
    before = guard.resolve_authority({"authority": {"paths": ["a/**", "b/**"], "writes_policy": True}})
    after = guard.resolve_authority({"authority": {"paths": ["a/**"], "writes_policy": True}})
    delta = guard.compute_authority_delta(before, after)
    assert delta["widened"] is False
    assert delta["paths"]["removed"] == ["b/**"]


def test_capability_modes_registered(guard):
    for mode in ("capability-list", "capability-check", "authority-delta"):
        assert mode in guard.COMMAND_TABLE, f"{mode} not registered"
        _handler, kind = guard.COMMAND_TABLE[mode]
        assert kind == "argv"
