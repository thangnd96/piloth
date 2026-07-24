#!/usr/bin/env python3
"""Amalgamate src/guard/*.py into the single distributed pilothos_guard.py.

The guard ships as ONE file: it is copied into an arbitrary consumer repo and
invoked directly as a Claude Code hook (`python pilothos_guard.py <mode>`), so
it cannot depend on an import path or a package layout in the consumer. We still
want to develop it in responsibility-sized pieces, so the source lives as
ordered fragments in src/guard/ and this tool concatenates them back into the
shipped file (SQLite-style amalgamation).

The fragments are contiguous slices of the original file cut at its section
banners; concatenating them in filename order reproduces the file exactly, so
the build is behaviour-preserving by construction. Fragments share one namespace
(imports + constants live in 00_header) and are NOT independently importable —
edit them, then run this tool; never edit pilothos_guard.py by hand.

Dev/build tooling only; scripts/ is not staged into a consumer.

Usage:
  python3 scripts/build_guard.py           # rebuild pilothos_guard.py from src/guard/
  python3 scripts/build_guard.py --check   # exit 1 if the shipped file is stale
  python3 scripts/build_guard.py --split   # (bootstrap) carve src/guard/ from the file
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC_DIR = REPO / "src" / "guard"
BUNDLE = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"

# (fragment name, 1-based start line in the original file). The end of each
# fragment is the start of the next. Starts sit on section-banner lines so every
# fragment begins and ends between complete top-level statements.
CUT_POINTS = [
    ("00_header", 1),
    ("01_helpers", 520),
    ("02_session", 825),
    ("03_contract_state", 860),
    ("04_rot", 2148),
    ("05_autolog", 2231),
    ("06_installer", 2350),
    ("07_context_budget", 3206),
    ("08_semantic_scan", 3337),
    ("09_scheduler", 3694),
    ("10_team", 4016),
    ("11_log_append", 4370),
    ("12_edit_receipt_guard", 4429),
    ("13_os_lifecycle", 5505),
    ("14_misc", 7801),
    ("15_selfcheck_cli", 8129),
]


def _fragments():
    return sorted(SRC_DIR.glob("*.py"))


def build_text():
    """Concatenate fragments in filename order into the shipped file's text."""
    return "".join(p.read_text(encoding="utf-8") for p in _fragments())


def do_split():
    # CUT_POINTS reflects the ORIGINAL monolith. Once src/guard has diverged
    # (fragments added beyond CUT_POINTS, e.g. 14a–14e), re-splitting by line
    # number would overwrite/duplicate the real fragments. Refuse rather than
    # corrupt the source of truth. --split is a one-time bootstrap only.
    if len(_fragments()) != len(CUT_POINTS):
        print(
            f"do_split refused: {len(_fragments())} fragment files vs "
            f"{len(CUT_POINTS)} CUT_POINTS — src/guard has diverged from the "
            "original monolith. Fragments are now the source of truth; edit them "
            "directly and run `build_guard.py` (no --split).",
            file=sys.stderr,
        )
        return 1
    lines = BUNDLE.read_text(encoding="utf-8").splitlines(keepends=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    for i, (name, start) in enumerate(CUT_POINTS):
        end = CUT_POINTS[i + 1][1] - 1 if i + 1 < len(CUT_POINTS) else len(lines)
        (SRC_DIR / f"{name}.py").write_text("".join(lines[start - 1:end]), encoding="utf-8")
    print(f"split: {len(CUT_POINTS)} fragments -> {SRC_DIR}")
    return 0


def do_build():
    BUNDLE.write_text(build_text(), encoding="utf-8")
    print(f"build: {len(_fragments())} fragments -> {BUNDLE}")
    return 0


def do_check():
    if build_text() == BUNDLE.read_text(encoding="utf-8"):
        print(f"build_guard --check OK: {BUNDLE.name} matches src/guard/")
        return 0
    print("build_guard --check FAILED: pilothos_guard.py is stale", file=sys.stderr)
    print("  fix: run `python3 scripts/build_guard.py`", file=sys.stderr)
    return 1


def main(argv):
    if "--split" in argv:
        return do_split()
    if "--check" in argv:
        return do_check()
    return do_build()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
