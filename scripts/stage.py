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
import re
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

# Files upgrade neither overwrites nor preserves whole: it takes the vendor text
# and carries the installed file's marked region across.
#
# `runtime/consumer-assets.md` was overwritten by every upgrade, losing the
# registry `asset-sync` had written (thangnd96/piloth#13). Preserving it whole
# was tried first and is NOT viable: `self-check` asserts the file contains the
# current release's asset vocabulary, so a frozen v1 copy fails the check, which
# rolls the whole upgrade back. The file genuinely has two owners — the kernel
# owns the contract prose and vocabulary, `asset-sync` owns what is between the
# markers — so the only correct upgrade is a merge along that seam.
MARKER_MERGE = {
    "pilothOS/runtime/consumer-assets.md": (
        "<!-- PILOTHOS-GENERATED-ASSETS:START -->",
        "<!-- PILOTHOS-GENERATED-ASSETS:END -->",
    ),
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


def merge_marked_region(vendor: str, installed: str, start: str, end: str) -> str:
    """Vendor text with the installed file's start..end region spliced in.

    Returns the vendor text unchanged when either side lacks the markers — a v1
    install that predates them has no consumer region to carry, and a vendor file
    that lost them is a packaging bug this is not the place to paper over.
    """
    kept = re.search(re.escape(start) + r".*?" + re.escape(end), installed, re.S)
    if kept is None:
        return vendor
    return re.sub(
        re.escape(start) + r".*?" + re.escape(end),
        lambda _: kept.group(0), vendor, count=1, flags=re.S,
    )


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
    if rel_dest in MARKER_MERGE and dest.is_file():
        start, end = MARKER_MERGE[rel_dest]
        dest.write_text(merge_marked_region(
            src.read_text(encoding="utf-8"),
            dest.read_text(encoding="utf-8"), start, end,
        ), encoding="utf-8")
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


def read_manifest_paths(target: Path) -> Optional[set[str]]:
    """Paths the manifest ON DISK lists, or None when it cannot be read."""
    try:
        data = json.loads(
            (target / "pilothOS" / "dist-manifest.json").read_text(encoding="utf-8"))
        return {item["path"] for item in data["files"]}
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return None


def prune_orphans(target: Path, old_shipped: Optional[set[str]],
                  backup_root: Optional[Path], counts: dict[str, int]) -> list[str]:
    """Delete what a PREVIOUS release shipped and this one does not.

    The first version of this compared the disk against the new manifest and
    deleted anything absent from it. That treated "not in the manifest" as "stale
    distribution content", which is wrong for three groups that are never in a
    manifest: files the consumer writes, files the kernel generates at runtime
    (`*-archive.md` from state-janitor), and — worst — the directories
    `knowledge/index.md` explicitly invites the consumer to create. Architecture
    decisions, domain facts and standards were deleted, and the trailing rmdir
    took the directories too, so it looked like they had never existed
    (thangnd96/piloth#12).

    Comparing the two manifests instead says exactly what was meant all along:
    something this distribution used to ship and no longer does. Anything never
    shipped is by construction not our litter, with no preserve list to maintain
    — and a preserve list is the thing that drifted here in the first place.

    Deleting inside a consumer tree is not reversible through git (most consumers
    gitignore `pilothOS/`), so removals are copied into the same
    `.backup/stage-upgrade-<ts>` the overwrite path uses.
    """
    if old_shipped is None:
        print("Bo qua prune: khong doc duoc dist-manifest.json cu truoc khi stage. "
              "Xoa la thao tac khong lui duoc nen khi khong biet ban cu ship gi, "
              "khong go gi ca.")
        return []
    new_shipped = read_manifest_paths(target)
    if new_shipped is None:
        print("Bo qua prune: khong doc duoc dist-manifest.json moi.")
        return []
    stale = old_shipped - new_shipped
    removed = []
    for rel in sorted(stale):
        path = target / rel
        if not path.is_file():
            continue
        if backup_root is not None:
            backup_existing(path, rel, backup_root)
            counts["backed_up"] += 1
        path.unlink()
        removed.append(rel)
    for d in sorted((p for p in (target / "pilothOS").rglob("*") if p.is_dir()),
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
    # Read BEFORE the copy loop: the loop overwrites dist-manifest.json, and the
    # old one is the only record of what a previous release put on this disk.
    old_shipped = read_manifest_paths(target) if upgrade else None
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

    pruned = prune_orphans(target, old_shipped, backup_root, counts) if upgrade else []

    print(
        "OK: staging du — "
        f"copied={counts['copied']}, updated={counts['updated']}, "
        f"backed-up={counts['backed_up']}, skipped-vi-da-co={counts['skipped']}"
        + (f", pruned={len(pruned)}" if pruned else "")
    )
    if pruned:
        # Full list, never a count with an ellipsis: a delete that git cannot undo
        # has to be readable. "pruned=41" tells a consumer nothing about whether
        # one of those was theirs.
        print(f"Da go {len(pruned)} file ban phan phoi nay khong con ship:")
        for rel in pruned:
            print(f"  - {rel}")
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
