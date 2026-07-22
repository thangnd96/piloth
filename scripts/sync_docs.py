#!/usr/bin/env python3
"""Regenerate derived documentation blocks from a single source (SSOT).

Some content must physically exist in more than one file — for cross-tool
portability, and for progressive context loading where each doc must stay
self-sufficient when loaded alone (a link is not enough). Rather than hand-
maintaining copies that drift, each copy lives between generated markers and is
rewritten here from ONE source file. tests/docs runs `--check` to fail on drift.

Dev/build tooling only; scripts/ is not staged into a consumer.

Usage:
  python3 scripts/sync_docs.py          # rewrite each target block from its source
  python3 scripts/sync_docs.py --check  # exit 1 if any target block is stale
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# (name, source, target): the block between the START/END markers in `target`
# is regenerated verbatim from the whole of `source`.
DERIVATIONS = [
    (
        "IDENTITY",
        "pilothOS/skills/workflow/pilothos-init/payloads/identity-block.md",
        "templates/CLAUDE.md",
    ),
]


def _sentinels(name):
    return (
        f"PILOTHOS-GENERATED:{name}:START",
        f"PILOTHOS-GENERATED:{name}:END",
    )


def _render(target_text, name, source_text):
    """Return target_text with the region between the START/END marker lines
    replaced by source_text. Raises if either marker is missing."""
    start_key, end_key = _sentinels(name)
    lines = target_text.splitlines(keepends=True)
    start = next((i for i, l in enumerate(lines) if start_key in l), None)
    end = next((i for i, l in enumerate(lines) if end_key in l), None)
    if start is None or end is None or end < start:
        raise SystemExit(f"sync_docs: markers for {name} not found/ordered in target")
    block = source_text if source_text.endswith("\n") else source_text + "\n"
    return "".join(lines[: start + 1]) + block + "".join(lines[end:])


def main(argv):
    check = "--check" in argv
    stale = []
    for name, source_rel, target_rel in DERIVATIONS:
        source = (REPO / source_rel).read_text(encoding="utf-8")
        target_path = REPO / target_rel
        current = target_path.read_text(encoding="utf-8")
        rendered = _render(current, name, source)
        if rendered == current:
            continue
        if check:
            stale.append(f"{target_rel} (block {name} drifted from {source_rel})")
        else:
            target_path.write_text(rendered, encoding="utf-8")
            print(f"synced: {target_rel} <- {source_rel} [{name}]")
    if check and stale:
        print("sync_docs --check FAILED:\n  " + "\n  ".join(stale), file=sys.stderr)
        print("  fix: run `python3 scripts/sync_docs.py`", file=sys.stderr)
        return 1
    if check:
        print(f"sync_docs --check OK: {len(DERIVATIONS)} derivation(s) in sync")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
