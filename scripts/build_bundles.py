#!/usr/bin/env python3
"""Amalgamate src/<name>/*.py into the single-file engines shipped in pilothOS/.

Both engines ship as ONE file each: they are copied into an arbitrary consumer
repo and invoked directly (`python pilothos_guard.py <mode>` as a Claude Code
hook, `python pilothos_installer.py apply <plan>` as the install executor), so
neither can depend on an import path or a package layout in the consumer. We
still want to develop them in responsibility-sized pieces, so the source lives as
ordered fragments in src/ and this tool concatenates them back into the shipped
files (SQLite-style amalgamation).

The fragments are contiguous slices cut at section banners; concatenating them in
filename order reproduces each file exactly, so the build is behaviour-preserving
by construction. Fragments share one namespace per bundle (imports + constants
live in 00_header) and are NOT independently importable — edit them, then run
this tool; never edit the shipped files by hand.

Dev/build tooling only; scripts/ is not staged into a consumer.

Usage:
  python3 scripts/build_bundles.py           # rebuild every bundle from src/
  python3 scripts/build_bundles.py --check   # exit 1 if any shipped file is stale
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (source fragment dir, shipped single file). Adding a bundle here is all it takes
# for --check to start guarding it in the release gate.
BUNDLES = [
    (REPO / "src" / "guard", REPO / "pilothOS" / "scripts" / "pilothos_guard.py"),
    (REPO / "src" / "installer", REPO / "pilothOS" / "scripts" / "pilothos_installer.py"),
]


def fragments(src_dir):
    return sorted(src_dir.glob("*.py"))


def build_text(src_dir):
    """Concatenate fragments in filename order into the shipped file's text."""
    return "".join(p.read_text(encoding="utf-8") for p in fragments(src_dir))


def do_build():
    for src_dir, bundle in BUNDLES:
        bundle.write_text(build_text(src_dir), encoding="utf-8")
        print(f"build: {len(fragments(src_dir))} fragments -> {bundle.name}")
    return 0


def do_check():
    stale = []
    for src_dir, bundle in BUNDLES:
        if build_text(src_dir) != bundle.read_text(encoding="utf-8"):
            stale.append(f"{bundle.name} is stale vs {src_dir.relative_to(REPO)}/")
    if stale:
        print("build_bundles --check FAILED:\n  " + "\n  ".join(stale), file=sys.stderr)
        print("  fix: run `python3 scripts/build_bundles.py`", file=sys.stderr)
        return 1
    names = ", ".join(bundle.name for _, bundle in BUNDLES)
    print(f"build_bundles --check OK: {names} match src/")
    return 0


def main(argv):
    if "--check" in argv:
        return do_check()
    return do_build()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
