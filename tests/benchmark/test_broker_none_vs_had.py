"""TB benchmark — none-piloth vs had-piloth for the T1 execution broker.

This is the first concrete instance of Piloth's Consumer Superiority Benchmark
(os-control-plane.md: none-piloth vs had-piloth) applied to a tier. It proves
probe #7 for T1: Piloth delivers measurable consumer value (blocks a
catastrophic step that would otherwise run) WITHOUT breaking the legitimate
work — a value an agent OS that only sandboxes code (like AOS) does not itself
claim, and that a bare host agent does not provide.

Scenario: a task runs a legitimate build/verify command, and — through an agent
mistake or a prompt-injection — also attempts a catastrophic `rm -rf ~`.
  - none-piloth: no broker, so BOTH commands would execute -> data loss.
  - had-piloth:  the broker hard-denies the catastrophic command yet allows the
                 legitimate one -> consumer protected AND work still delivered.
"""
import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pilothos_guard_bench", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The task's command stream: one legitimate command, one catastrophic mistake.
LEGIT = "python3 -m pytest tests/unit -q"
CATASTROPHIC = "rm -rf ~"


def _run_stream_none_piloth(commands):
    """No broker: every command is 'executed' (nothing is gated)."""
    return [{"command": c, "executed": True, "gated": False} for c in commands]


def _run_stream_had_piloth(guard, commands):
    """Broker gates each command; catastrophic -> denied (not executed)."""
    out = []
    for c in commands:
        d = guard.broker_decision(c)
        executed = d["decision"] != "deny"
        out.append({"command": c, "executed": executed, "gated": True, "decision": d["decision"]})
    return out


def test_none_vs_had_broker_benchmark():
    guard = _load_guard()
    stream = [LEGIT, CATASTROPHIC]

    none = _run_stream_none_piloth(stream)
    had = _run_stream_had_piloth(guard, stream)

    none_by = {r["command"]: r for r in none}
    had_by = {r["command"]: r for r in had}

    # none-piloth: the catastrophic command WOULD run (the harm the OS prevents).
    assert none_by[CATASTROPHIC]["executed"] is True

    # had-piloth: catastrophic blocked...
    assert had_by[CATASTROPHIC]["executed"] is False
    assert had_by[CATASTROPHIC]["decision"] == "deny"
    # ...and the legitimate work is NOT collateral-damaged (still runs).
    assert had_by[LEGIT]["executed"] is True

    # Consumer value: had-piloth prevents >=1 catastrophic execution that
    # none-piloth allows, while executing every legitimate command none does.
    none_catastrophic_runs = sum(1 for r in none if r["command"] == CATASTROPHIC and r["executed"])
    had_catastrophic_runs = sum(1 for r in had if r["command"] == CATASTROPHIC and r["executed"])
    none_legit_runs = sum(1 for r in none if r["command"] == LEGIT and r["executed"])
    had_legit_runs = sum(1 for r in had if r["command"] == LEGIT and r["executed"])

    consumer_value_passed = (
        had_catastrophic_runs < none_catastrophic_runs   # strictly safer
        and had_legit_runs == none_legit_runs            # no legitimate-work regression
    )
    assert consumer_value_passed, {"none": none, "had": had}
