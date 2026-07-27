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

import json
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
# Which installer options take a value. This has to match the engine's argparse
# exactly: the wrapper needs the arity to know whether the next token is the
# option's value or the target directory. It used to be a hand-copy and it
# drifted — `--adapters` and `--gitignore-scope` were both missing, so
# `--gitignore-scope runtime <target>` read "runtime" as a second target and died
# with "qua nhieu target" (thangnd96/piloth#8). Pinned by a test against the
# installer source; keep it a literal so staging stays importable on its own.
INSTALLER_VALUE_OPTIONS = {
    "--mode", "--persona", "--goals", "--owner", "--statusline",
    "--adapters", "--gitignore-scope",
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
            # No silent forwarding: an unknown flag used to be passed straight
            # through, which is how `--adapters` looked like it worked while
            # doing nothing at all. Failing here is louder and cheaper than a
            # consumer believing a selection took effect.
            fail(f"flag khong nhan ra: {arg} "
                 f"(staging biet: {', '.join(sorted(INSTALLER_VALUE_OPTIONS | INSTALLER_FLAG_OPTIONS))})")
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


# Runtime state and the manifest itself are never listed IN the manifest, so a
# naive "delete anything not in the manifest" would take out the marker, the
# pending plan, the backups it just wrote — and the manifest that drives the
# whole comparison.
PRUNE_PRESERVE_FILES = {
    "pilothOS/dist-manifest.json",
    "pilothOS/.initialized",
    "pilothOS/.pending-plan.json",
}
PRUNE_PRESERVE_PREFIXES = ("pilothOS/.backup/", "pilothOS/memory/state/")


def prune_orphans(target: Path, backup_root: Optional[Path],
                  counts: dict[str, int]) -> list[str]:
    """Delete kernel files this version no longer ships. Backed up first.

    Staging used to only ever add and overwrite, so every subsystem a release
    removed stayed on the consumer's disk: after v1.11 -> v2.0.1 that was 41
    files, and `dist-manifest.json` stopped describing the tree it is supposed to
    be the source of truth for. Worse, the leftover files kept their hooks alive
    and gave `os-close` / rot / routing two versions of the same doc to read
    (thangnd96/piloth#7).

    Deleting inside a consumer tree is not reversible through git — most
    consumers gitignore `pilothOS/` — so every removal is copied into the same
    `.backup/stage-upgrade-<ts>` the overwrite path already uses.
    """
    manifest_path = target / "pilothOS" / "dist-manifest.json"
    try:
        shipped = {item["path"] for item in
                   json.loads(manifest_path.read_text(encoding="utf-8"))["files"]}
    except (OSError, KeyError, json.JSONDecodeError) as e:
        fail(f"khong doc duoc dist-manifest.json de prune: {e}")
    removed = []
    kernel = target / "pilothOS"
    for path in sorted(p for p in kernel.rglob("*") if p.is_file()):
        rel = path.relative_to(target).as_posix()
        if (rel in shipped or rel in PRUNE_PRESERVE_FILES
                or rel.startswith(PRUNE_PRESERVE_PREFIXES)):
            continue
        if backup_root is not None:
            backup_existing(path, rel, backup_root)
            counts["backed_up"] += 1
        path.unlink()
        removed.append(rel)
    for d in sorted((p for p in kernel.rglob("*") if p.is_dir()),
                    key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    return removed


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

    pruned = prune_orphans(target, backup_root, counts) if upgrade else []

    print(
        "OK: staging du — "
        f"copied={counts['copied']}, updated={counts['updated']}, "
        f"backed-up={counts['backed_up']}, skipped-vi-da-co={counts['skipped']}"
        + (f", pruned={len(pruned)}" if pruned else "")
    )
    if pruned:
        print(f"Da go {len(pruned)} file khong con trong ban phan phoi nay:")
        for rel in pruned[:8]:
            print(f"  - {rel}")
        if len(pruned) > 8:
            print(f"  ... va {len(pruned) - 8} file nua (xem backup)")
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
