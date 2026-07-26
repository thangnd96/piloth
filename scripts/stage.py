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
import datetime
import subprocess
from pathlib import Path
from typing import Optional

from _distribution import (
    CONSUMER_OWNED,
    MAP,
    SHIP_EMPTY_LOGS,
    ignored_distribution_artifact,
    log_header_only,
)

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", SCRIPT_DIR.parent)).resolve()

UPGRADE_PRESERVE = CONSUMER_OWNED | {
    "pilothOS/.initialized",
    "pilothOS/rot/registry.md",
    "pilothOS/rot/review-log.md",
    "pilothOS/memory/lessons-learned.md",
}
INSTALLER_VALUE_OPTIONS = {
    "--mode", "--persona", "--goals", "--owner", "--statusline",
}
INSTALLER_FLAG_OPTIONS = {"--dry-run", "--print-plan"}


def fail(msg: str, code: int = 1) -> None:
    print(f"LOI: {msg}", file=sys.stderr)
    raise SystemExit(code)


def parse_args(argv: list[str]) -> tuple[Path, bool, bool, list[str]]:
    upgrade = False
    unattended = False
    installer_args: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--upgrade", "--reinit"):
            upgrade = True
        elif arg == "--unattended":
            unattended = True
        elif arg == "--":
            installer_args.extend(argv[i + 1:])
            break
        elif arg in INSTALLER_VALUE_OPTIONS:
            installer_args.append(arg)
            if i + 1 < len(argv):
                i += 1
                installer_args.append(argv[i])
        elif arg in INSTALLER_FLAG_OPTIONS or arg.startswith(tuple(f"{opt}=" for opt in INSTALLER_VALUE_OPTIONS)):
            installer_args.append(arg)
        elif arg.startswith("--"):
            installer_args.append(arg)
        else:
            targets.append(arg)
        i += 1
    if len(targets) > 1:
        fail(f"qua nhieu target: {targets}")
    target = Path(targets[0] if targets else os.getcwd()).resolve()
    return target, upgrade, unattended, installer_args


def backup_existing(dest: Path, rel_dest: str, backup_root: Path) -> None:
    backup = backup_root / rel_dest
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest, backup)


def place_one(src: Path, dest: Path, rel_dest: str) -> None:
    """Put one staged file in place: byte copy, or header-only for ship-empty logs.

    The vendor's own review-log / lessons-learned rows are its operational
    history, not seed content for a new install — each file says so in its own
    header. Stripping the rows here keeps that promise without deleting the
    history from the Piloth repo, where the auto-log gate keeps appending to it.
    """
    if rel_dest in SHIP_EMPTY_LOGS:
        dest.write_text(
            log_header_only(src.read_text(encoding="utf-8")), encoding="utf-8",
        )
        return
    shutil.copy2(src, dest)


def copy_one(src: Path, rel_dest: str, counts: dict[str, int],
             target: Path, upgrade: bool, backup_root: Optional[Path]) -> None:
    dest = target / rel_dest
    if rel_dest in CONSUMER_OWNED and dest.exists():
        counts["skipped"] += 1
        return
    if dest.exists():
        if upgrade and rel_dest not in UPGRADE_PRESERVE:
            if backup_root is not None:
                backup_existing(dest, rel_dest, backup_root)
                counts["backed_up"] += 1
            place_one(src, dest, rel_dest)
            counts["updated"] += 1
        else:
            counts["skipped"] += 1
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    place_one(src, dest, rel_dest)
    counts["copied"] += 1


def main() -> int:
    target, upgrade, unattended, installer_args = parse_args(sys.argv[1:])
    if not (REPO / "pilothOS").is_dir():
        fail(f"khong tim thay nguon PilothOS tai {REPO}")
    initialized = (target / "pilothOS" / ".initialized").exists()
    if initialized and not upgrade:
        fail("project da init PilothOS — dung --upgrade de re-stage/upgrade.")
    if (target / "pilothOS").is_dir() and not upgrade:
        fail(f"{target / 'pilothOS'} da ton tai — xoa/phuc hoi truoc hoac dung --upgrade.")

    counts = {"copied": 0, "updated": 0, "backed_up": 0, "skipped": 0}
    backup_root = None
    if upgrade:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        backup_root = target / "pilothOS" / ".backup" / f"stage-upgrade-{ts}"
    for src_rel, dest_rel in MAP:
        src = REPO / src_rel
        if src.is_file():
            if ignored_distribution_artifact(src.relative_to(REPO)):
                continue
            copy_one(src, dest_rel, counts, target, upgrade, backup_root)
        elif src.is_dir():
            for child in sorted(p for p in src.rglob("*") if p.is_file()):
                if ignored_distribution_artifact(child.relative_to(src)):
                    continue
                rel = child.relative_to(src).as_posix()
                copy_one(child, f"{dest_rel}/{rel}", counts, target, upgrade,
                         backup_root)

    print(
        "OK: staging du — "
        f"copied={counts['copied']}, updated={counts['updated']}, "
        f"backed-up={counts['backed_up']}, skipped-vi-da-co={counts['skipped']}"
    )
    if backup_root and counts["backed_up"]:
        print(f"Backup upgrade: {backup_root}")
    if unattended:
        cmd = [
            sys.executable,
            str(target / "pilothOS" / "scripts" / "pilothos_installer.py"),
            "unattended",
        ] + installer_args
        subprocess.run(cmd, cwd=target, check=True)
    else:
        print("Tiep theo: lam theo pilothOS/skills/workflow/pilothos-init/SKILL.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
