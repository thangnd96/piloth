"""Black-box characterization net for the guard CLI.

Protects the PR4 guard amalgamation (src/guard/*.py -> single distributed
pilothos_guard.py): the bundled file must behave identically to the pre-split
file. These hit the real CLI/subprocess boundary (dispatch, stdin, exit codes)
that the import-level unit tests do not exercise.

- smoke: every COMMAND_TABLE mode must dispatch and run without crashing —
  catches a handler dropped or an import broken by concatenation.
- golden: deterministic pure-output modes must stay byte-stable. Regenerate with
  PILOTH_REGEN_GOLDEN=1 only when an output change is intended (never mid-refactor).
"""
import os
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"

# Preset env vars would change gate-aware output; strip them so a developer's
# shell settings cannot make these subprocess snapshots non-deterministic.
_STRIP_ENV = ("PILOTHOS_OPERATIONAL_PRESET", "PILOTHOS_PRESET")


def _run(args, stdin=""):
    env = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV}
    return subprocess.run(
        [sys.executable, str(GUARD), *args],
        input=stdin, capture_output=True, text=True, timeout=60, env=env,
    )


def test_every_mode_dispatches_via_cli(guard):
    """Every registered mode runs from the CLI with empty stdin (degraded but
    never crashing). This is the primary amalgamation-breakage detector."""
    failures = []
    for mode in sorted(guard.COMMAND_TABLE):
        r = _run([mode], stdin="")
        if r.returncode != 0 or "Traceback (most recent call last)" in r.stderr:
            failures.append(f"{mode}: rc={r.returncode} stderr={r.stderr.strip()[:300]}")
    assert not failures, "modes failed to dispatch:\n" + "\n".join(failures)


# Pure, input-determined modes (no timestamps / hashes / repo scan) -> exact snapshot.
GOLDEN_CASES = [
    ("os-start-explain", ["os-start", "--explain"], ""),
    ("receipt-template", ["receipt-template"], ""),
]


@pytest.mark.parametrize("name,args,stdin", GOLDEN_CASES)
def test_golden_output_is_stable(name, args, stdin):
    r = _run(args, stdin)
    assert r.returncode == 0, r.stderr
    golden = GOLDEN_DIR / f"{name}.txt"
    if os.environ.get("PILOTH_REGEN_GOLDEN") or not golden.exists():
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_text(r.stdout, encoding="utf-8")
        pytest.skip(f"golden captured: {name}")
    assert r.stdout == golden.read_text(encoding="utf-8"), (
        f"{name} output drifted from golden. A refactor must be behaviour-"
        f"preserving; if the change is intended run PILOTH_REGEN_GOLDEN=1."
    )
