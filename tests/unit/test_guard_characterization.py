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
import shutil
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"

# Preset env vars would change gate-aware output; strip them so a developer's
# shell settings cannot make these subprocess snapshots non-deterministic.
_STRIP_ENV = ("PILOTHOS_OPERATIONAL_PRESET", "PILOTHOS_PRESET")


@pytest.fixture(scope="session")
def sandbox_guard(tmp_path_factory):
    """A copy of the engine whose state directory is disposable.

    The all-modes tests below dispatch EVERY registered mode, and 21 of them are
    declared `mutates=True` — run against the real repo they append to whatever
    OS run happens to be open, so a developer running the suite mid-task gets
    fabricated evidence in their own run. It stayed hidden because a closed or
    sealed run rejects the write; only an *open* run is corrupted.

    The engine resolves its state from its own __file__, not from cwd, so
    isolating it means running a copied guard. os-runs is deliberately not
    copied: with no active run, mutating modes degrade to "no active OS run"
    (still exit 0), which is exactly what the dispatch check needs.
    """
    root = tmp_path_factory.mktemp("guard-sandbox") / "repo"
    shutil.copytree(
        REPO, root,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".backup", ".pytest_cache", "os-runs",
        ),
    )
    return root / "pilothOS" / "scripts" / "pilothos_guard.py"


def _run(args, stdin="", guard_path=GUARD):
    env = {k: v for k, v in os.environ.items() if k not in _STRIP_ENV}
    return subprocess.run(
        [sys.executable, str(guard_path), *args],
        input=stdin, capture_output=True, text=True, timeout=60, env=env,
    )


def _run_mode(guard, mode, sandbox_guard, stdin=""):
    """Dispatch one mode, sending state-mutating ones to the sandbox copy."""
    declared = guard.GUARD_MODES.get(mode) or {}
    target = sandbox_guard if declared.get("mutates") else GUARD
    return _run([mode], stdin=stdin, guard_path=target)


def test_every_mode_dispatches_via_cli(guard, sandbox_guard):
    """Every registered mode runs from the CLI with empty stdin (degraded but
    never crashing). This is the primary amalgamation-breakage detector."""
    failures = []
    for mode in sorted(guard.COMMAND_TABLE):
        r = _run_mode(guard, mode, sandbox_guard)
        if r.returncode != 0 or "Traceback (most recent call last)" in r.stderr:
            failures.append(f"{mode}: rc={r.returncode} stderr={r.stderr.strip()[:300]}")
    assert not failures, "modes failed to dispatch:\n" + "\n".join(failures)


def test_unregistered_mode_fails_loudly():
    """A typo'd mode must not look like success. The guard is wired into
    settings.json as hook commands, so an exit-0 no-op silently disabled
    governance instead of reporting the bad config."""
    r = _run(["definitely-not-a-mode"])
    assert r.returncode == 1, f"expected rc=1, got {r.returncode}: {r.stdout}{r.stderr}"
    assert "definitely-not-a-mode" in r.stderr
    assert not r.stdout, "diagnostics must go to stderr so hook stdout stays JSON-only"


def test_missing_mode_argument_fails_loudly():
    r = _run([])
    assert r.returncode == 1, f"expected rc=1, got {r.returncode}"
    assert "missing mode argument" in r.stderr


def test_registered_modes_never_exit_nonzero(guard, sandbox_guard):
    """Claude Code only parses hook JSON on exit 0, so block_decision depends on
    every registered mode exiting 0. Pinned separately from the dispatch smoke
    test because it is a protocol requirement, not just a crash check."""
    offenders = [
        mode for mode in sorted(guard.COMMAND_TABLE)
        if _run_mode(guard, mode, sandbox_guard).returncode != 0
    ]
    assert not offenders, f"modes exited non-zero (breaks hook JSON parsing): {offenders}"


def test_all_modes_smoke_leaves_the_live_run_untouched(guard, sandbox_guard):
    """Regression guard for the isolation above: dispatching every mode must not
    append to the repo's own evidence ledger."""
    run_dirs = sorted((REPO / "pilothOS" / "memory" / "state" / "os-runs").glob("*"))
    before = {
        p: (p / "evidence.jsonl").stat().st_size
        for p in run_dirs if (p / "evidence.jsonl").is_file()
    }
    for mode in sorted(guard.COMMAND_TABLE):
        _run_mode(guard, mode, sandbox_guard)
    after = {
        p: (p / "evidence.jsonl").stat().st_size
        for p in before
    }
    grew = [p.name for p in before if after[p] != before[p]]
    assert not grew, f"all-modes smoke wrote into live OS run evidence: {grew}"


# Pure, input-determined modes only (no timestamps / hashes / repo or git scan)
# -> exact snapshot. NB: receipt-template is intentionally NOT here — it embeds
# the current working-tree changed_files, so it is state-dependent; the smoke
# test covers that it dispatches.
GOLDEN_CASES = [
    ("os-start-explain", ["os-start", "--explain"], ""),
]


def test_bundles_match_their_fragments():
    """Every shipped single-file engine must equal a fresh amalgamation of its
    fragments (pilothos_guard.py from src/guard/, pilothos_installer.py from
    src/installer/). Hand-edits to a bundle instead of the fragments are drift and
    are rejected here."""
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "build_bundles.py"), "--check"],
        capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stdout + r.stderr


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
