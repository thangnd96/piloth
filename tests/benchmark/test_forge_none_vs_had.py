"""TB benchmark — none-piloth vs had-piloth for T3 Piloth Forge.

Probe #7 for T3: governed self-extension delivers consumer value that an
ungoverned agent does not. A bare agent that "just creates a file" accepts a
defective capability (duplicate id, wrong layer, no justification, undeclared
authority); Piloth Forge catches those defects AND still admits a valid
extension — governed growth without blocking legitimate work.
"""
import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pilothos_guard_forge_bench", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DEFECTIVE = {  # dup id (os-start), wrong layer, no reason, no authority
    "kind": "skill", "id": "os-start", "layer": "Rules", "intent": "x",
}
VALID = {
    "kind": "skill", "id": "deploy-smoke-check", "layer": "Skills",
    "intent": "Run a post-deploy smoke check",
    "reason": "Incident: deploy broke prod; need a repeatable smoke",
    "authority": {"guard_modes": ["os-evidence"]},
}


def _none_piloth(_spec):
    # Ungoverned: an agent just writes the file. No verification, no authority
    # declaration, no justification check — always "accepted".
    return {"accepted": True, "defects_caught": 0}


def _had_piloth(guard, spec):
    errors, _warnings = guard.forge_verify_findings(spec)
    return {"accepted": not errors, "defects_caught": len(errors)}


def test_none_vs_had_forge_benchmark():
    guard = _load_guard()

    none_defective = _none_piloth(DEFECTIVE)
    had_defective = _had_piloth(guard, DEFECTIVE)
    none_valid = _none_piloth(VALID)
    had_valid = _had_piloth(guard, VALID)

    # Ungoverned admits the defective capability; Forge rejects it.
    assert none_defective["accepted"] is True
    assert had_defective["accepted"] is False
    assert had_defective["defects_caught"] >= 1

    # Legitimate extension is NOT collateral-blocked by governance.
    assert none_valid["accepted"] is True
    assert had_valid["accepted"] is True

    consumer_value_passed = (
        had_defective["defects_caught"] > none_defective["defects_caught"]  # governance catches real defects
        and had_valid["accepted"] == none_valid["accepted"]                # no regression on valid work
    )
    assert consumer_value_passed, {"none_defective": none_defective, "had_defective": had_defective}
