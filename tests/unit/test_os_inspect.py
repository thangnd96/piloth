"""Unit tests for the T2 unified introspection mode (`os-inspect`).

os-inspect is Piloth's analog of `aos status` + capsule-system: one legible
system-status report that AGGREGATES existing result-functions (control-plane
health, capability/authority, rot, guard-mode surface, version) without
duplicating them. It is also the "inspect the world first" precondition for
Forge (T3).
"""


def test_report_has_expected_shape(guard):
    r = guard.os_inspect_result()
    for key in ("result", "version", "capabilities", "syscalls", "rot", "health", "attention", "advisories"):
        assert key in r, f"missing key: {key}"
    assert r["result"] in ("os_inspect_healthy", "os_inspect_attention")


def test_attention_is_consistent_with_result(guard):
    r = guard.os_inspect_result()
    if r["attention"]:
        assert r["result"] == "os_inspect_attention"
    else:
        assert r["result"] == "os_inspect_healthy"
    # every attention item names a failing health check
    failing = {h["name"] for h in r["health"] if not h["ok"]}
    assert set(r["attention"]) == failing


def test_capabilities_reflect_manifest(guard):
    r = guard.os_inspect_result()
    manifest = guard.load_capability_manifest()
    expected = len(manifest.get("capabilities", [])) if isinstance(manifest, dict) else 0
    assert r["capabilities"]["count"] == expected
    # kinds breakdown sums to the count
    assert sum(r["capabilities"]["kinds"].values()) == expected


def test_syscalls_surface_matches_dispatch_table(guard):
    r = guard.os_inspect_result()
    assert r["syscalls"]["guard_modes"] == len(guard.COMMAND_TABLE)
    for mode in ("os-inspect", "broker-check", "capability-check"):
        assert mode in r["syscalls"]["modes"]


def test_attention_path_forced_when_a_health_check_fails(guard, monkeypatch):
    # F11: force a health check to fail and prove the verdict flips.
    monkeypatch.setattr(guard, "provenance_result", lambda *a, **k: {"result": "provenance_mismatch"})
    r = guard.os_inspect_result()
    assert r["result"] == "os_inspect_attention"
    assert "supply-chain provenance" in r["attention"]


def test_transient_artifacts_excluded_from_verdict(guard):
    # F7: artifact-janitor is advisory, never part of the health verdict, so a
    # stray .DS_Store / __pycache__ must not flip healthy -> attention.
    r = guard.os_inspect_result()
    names = {h["name"] for h in r["health"]}
    assert "artifact janitor" not in names


def test_rot_key_present(guard):
    r = guard.os_inspect_result()
    assert isinstance(r["rot"]["registry_found"], bool)
    assert isinstance(r["rot"]["overdue"], list)


def test_os_inspect_registered_and_read_only(guard):
    assert "os-inspect" in guard.COMMAND_TABLE
    _handler, kind = guard.COMMAND_TABLE["os-inspect"]
    assert kind == "none"
    # introspection must be classed read-only (safe under tool-check).
    assert "os-inspect" in guard.READ_ONLY_GUARD_MODES
