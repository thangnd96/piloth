"""TB benchmark — none-piloth vs had-piloth for T5 composability.

Genuine A/B: the SAME skill_index_result code is run two ways. none-piloth = no
consumer override skills (only the kernel skill exists, so customizing it means
editing the kernel — a fork); had-piloth = a consumer override wins via
workspace precedence while the kernel file stays pristine. Probe #7.
"""
import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pilothos_guard_compose_bench", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_none_vs_had_composability_benchmark(tmp_path):
    guard = _load_guard()

    # none-piloth: an EMPTY consumer skills dir — no override mechanism in play.
    empty = tmp_path / "none-skills"
    empty.mkdir()
    none = guard.skill_index_result(consumer_dir=str(empty))
    none_forge = next(s for s in none["skills"] if s["id"] == "piloth-forge")
    none_can_override = bool(none["overrides"]) or none_forge["source"] == "consumer"

    # had-piloth: a consumer override skill wins via precedence.
    consumer = tmp_path / "had-skills"
    (consumer / "piloth-forge").mkdir(parents=True)
    (consumer / "piloth-forge" / "SKILL.md").write_text(
        "# Piloth Forge (project override)\n", encoding="utf-8")
    had = guard.skill_index_result(consumer_dir=str(consumer))
    had_forge = next(s for s in had["skills"] if s["id"] == "piloth-forge")
    had_can_override = "piloth-forge" in had["overrides"] and had_forge["source"] == "consumer"

    assert none_can_override is False, none   # no override path without a consumer skill
    assert had_can_override is True, had      # override wins via precedence

    # ...and the kernel skill file is untouched (upstream stays updatable).
    kernel_forge = REPO / "pilothOS" / "skills" / "workflow" / "piloth-forge" / "SKILL.md"
    assert guard._skill_title(kernel_forge) == "Piloth Forge — Governed Self-Extension"

    consumer_value_passed = had_can_override and not none_can_override
    assert consumer_value_passed
