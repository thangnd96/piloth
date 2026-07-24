"""TB benchmark — none-piloth vs had-piloth for T3 Piloth Forge.

GENUINE A/B: both arms run the real capability-check validator against real
manifests. none-piloth = an ungoverned agent appends a defective capability
straight into the manifest -> capability-check FAILS (the defect really lands).
had-piloth = forge-verify rejects the same spec BEFORE any write -> the manifest
is never mutated -> capability-check still PASSES. Probe #7 — governed growth
keeps the system valid; ungoverned growth corrupts it.
"""
import copy
import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pilothos_guard_forge_bench", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Defective: id collides with an existing guard-mode capability, wrong layer,
# no justification, no authority.
DEFECTIVE = {"kind": "skill", "id": "os-start", "layer": "Rules", "intent": "x"}


def test_none_vs_had_forge_benchmark():
    guard = _load_guard()
    shipped = guard.load_capability_manifest()
    assert shipped is not None and shipped.get("capabilities")

    # none-piloth: ungoverned agent just appends the capability into the manifest.
    none_manifest = copy.deepcopy(shipped)
    none_manifest["capabilities"].append(dict(DEFECTIVE))
    none_errors, _ = guard.capability_check_findings(none_manifest)
    none_manifest_valid = not none_errors

    # had-piloth: forge-verify rejects the defective spec BEFORE any write.
    had_verify_errors, _ = guard.forge_verify_findings(DEFECTIVE)
    had_blocked = bool(had_verify_errors)
    # ...so the real manifest is never mutated and stays valid.
    had_manifest_valid = not guard.capability_check_findings(shipped)[0]

    assert none_manifest_valid is False, "ungoverned append must corrupt the manifest (duplicate id)"
    assert had_blocked is True, "forge-verify must reject the defective spec pre-write"
    assert had_manifest_valid is True, "governed path keeps the manifest valid"

    consumer_value_passed = (not none_manifest_valid) and had_blocked and had_manifest_valid
    assert consumer_value_passed
