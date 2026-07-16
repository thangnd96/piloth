#!/usr/bin/env python3
"""Deterministic Piloth staging.

Two channels:
- Plugin (Claude Code): source = CLAUDE_PLUGIN_ROOT, target = cwd
- Clone/manual: scripts/stage.sh /path/to/project

Never overwrites consumer-owned files. This implementation intentionally avoids
Bash process substitution and producer pipes so test runners cannot hang while
waiting for pipe EOF from descendant processes.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", SCRIPT_DIR.parent)).resolve()
TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd()).resolve()

MAP = [
    ("pilothOS", "pilothOS"),
    ("adapters/claude", ".claude"),
    ("adapters/cursor", ".cursor"),
    ("adapters/codex", ".codex"),
    ("adapters/antigravity", ".antigravity"),
    ("templates/CLAUDE.md", "CLAUDE.md"),
    ("templates/AGENTS.md", "AGENTS.md"),
    ("templates/gitignore", ".gitignore"),
    ("pilothOS/skills/workflow/pilothos-init/payloads/settings.json", ".claude/settings.json"),
    ("LICENSE", "pilothOS/LICENSE"),
    ("CHANGELOG.md", "pilothOS/CHANGELOG.md"),
]

CONSUMER_OWNED = {"CLAUDE.md", "AGENTS.md", ".gitignore", ".claude/settings.json"}


def fail(msg: str, code: int = 1) -> None:
    print(f"LOI: {msg}", file=sys.stderr)
    raise SystemExit(code)


def copy_one(src: Path, rel_dest: str, counts: dict[str, int]) -> None:
    dest = TARGET / rel_dest
    if rel_dest in CONSUMER_OWNED and dest.exists():
        counts["skipped"] += 1
        return
    if dest.exists():
        counts["skipped"] += 1
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    counts["copied"] += 1


def main() -> int:
    if not (REPO / "pilothOS").is_dir():
        fail(f"khong tim thay nguon PilothOS tai {REPO}")
    if (TARGET / "pilothOS" / ".initialized").exists():
        fail("project da init PilothOS — re-init chua ho tro.")
    if (TARGET / "pilothOS").is_dir():
        fail(f"{TARGET / 'pilothOS'} da ton tai — xoa hoac phuc hoi truoc.")

    counts = {"copied": 0, "skipped": 0}
    for src_rel, dest_rel in MAP:
        src = REPO / src_rel
        if src.is_file():
            copy_one(src, dest_rel, counts)
        elif src.is_dir():
            for child in sorted(p for p in src.rglob("*") if p.is_file()):
                rel = child.relative_to(src).as_posix()
                copy_one(child, f"{dest_rel}/{rel}", counts)

    print(f"OK: staging du — copied={counts['copied']}, skipped-vi-da-co={counts['skipped']}")
    print("Tiep theo: lam theo pilothOS/skills/workflow/pilothos-init/SKILL.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
