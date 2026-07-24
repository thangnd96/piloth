"""TB benchmark — none-piloth vs had-piloth for T5 composability.

Probe #7 for T5: a consumer can customize a kernel skill without forking it.
none-piloth: to change a shipped skill you must edit the kernel file in place
(a fork) — which diverges from upstream and forfeits future kernel updates.
had-piloth: a consumer override wins via skill-index precedence while the kernel
file stays pristine (upstream still updatable).
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

    # Consumer customizes piloth-forge for their project (an override, not a fork).
    consumer = tmp_path / "skills"
    (consumer / "piloth-forge").mkdir(parents=True)
    (consumer / "piloth-forge" / "SKILL.md").write_text(
        "# Piloth Forge (project override)\n", encoding="utf-8")

    idx = guard.skill_index_result(consumer_dir=str(consumer))
    forge = next(s for s in idx["skills"] if s["id"] == "piloth-forge")

    # had-piloth: the override wins via precedence...
    had_override_wins = forge["source"] == "consumer" and forge["overrides"] == "kernel"
    # ...and the kernel skill file is untouched (upstream stays updatable).
    kernel_forge = REPO / "pilothOS" / "skills" / "workflow" / "piloth-forge" / "SKILL.md"
    had_kernel_pristine = guard._skill_title(kernel_forge) == "Piloth Forge — Governed Self-Extension"

    # none-piloth: customizing a shipped skill requires editing the kernel file
    # in place (a fork) — divergence + lost upstream updates.
    none_requires_fork = True

    consumer_value_passed = had_override_wins and had_kernel_pristine and none_requires_fork
    assert consumer_value_passed, {"forge": forge, "kernel_title": guard._skill_title(kernel_forge)}
