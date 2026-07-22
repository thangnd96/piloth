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

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", SCRIPT_DIR.parent)).resolve()

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

IGNORE_NAMES = {".DS_Store", "Thumbs.db"}
IGNORE_DIRS = {"__pycache__"}
LOCAL_STATE_FILES = {"memory/state/scheduler-history.jsonl", "memory/state/receipt-seals.jsonl"}
LOCAL_STATE_DIRS = {"memory/state/team-runs", "memory/state/os-runs"}
CONSUMER_OWNED = {"CLAUDE.md", "AGENTS.md", ".gitignore", ".claude/settings.json"}
UPGRADE_PRESERVE = CONSUMER_OWNED | {
    "pilothOS/.initialized",
    "pilothOS/rot/registry.md",
    "pilothOS/rot/review-log.md",
    "pilothOS/memory/lessons-learned.md",
}
OPTIONAL_ADAPTER_ROOTS = {
    "cursor": ".cursor",
    "codex": ".codex",
    "antigravity": ".antigravity",
}
INSTALLER_VALUE_OPTIONS = {
    "--mode", "--persona", "--goals", "--owner", "--adapters", "--statusline",
}
INSTALLER_FLAG_OPTIONS = {"--dry-run", "--print-plan"}


def fail(msg: str, code: int = 1) -> None:
    print(f"LOI: {msg}", file=sys.stderr)
    raise SystemExit(code)


def parse_args(argv: list[str]) -> tuple[Path, bool, bool, Optional[set[str]], list[str]]:
    upgrade = False
    unattended = False
    add_adapters: Optional[set[str]] = None
    installer_args: list[str] = []
    targets: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg in ("--upgrade", "--reinit"):
            upgrade = True
        elif arg == "--unattended":
            unattended = True
        elif arg == "--add-adapters":
            if i + 1 < len(argv):
                i += 1
                add_adapters = {x.strip().lower() for x in argv[i].split(",") if x.strip()}
        elif arg.startswith("--add-adapters="):
            add_adapters = {x.strip().lower()
                            for x in arg.split("=", 1)[1].split(",") if x.strip()}
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
    return target, upgrade, unattended, add_adapters, installer_args


def requested_adapter_roots(installer_args: list[str]) -> Optional[set[str]]:
    raw = None
    for i, arg in enumerate(installer_args):
        if arg == "--adapters" and i + 1 < len(installer_args):
            raw = installer_args[i + 1]
        elif arg.startswith("--adapters="):
            raw = arg.split("=", 1)[1]
    if raw is None:
        return None
    names = {x.strip().lower() for x in raw.split(",") if x.strip()}
    return {root for name, root in OPTIONAL_ADAPTER_ROOTS.items() if name in names}


def optional_adapter_root(rel_dest: str) -> Optional[str]:
    first = rel_dest.split("/", 1)[0]
    if first in OPTIONAL_ADAPTER_ROOTS.values():
        return first
    return None


def ignored_distribution_artifact(path: Path) -> bool:
    rel = path.as_posix()
    return (
        path.name in IGNORE_NAMES
        or any(part in IGNORE_DIRS for part in path.parts)
        or rel in LOCAL_STATE_FILES
        or (rel.startswith("memory/state/") and path.suffix == ".jsonl")
        or any(rel == item or rel.startswith(item + "/") for item in LOCAL_STATE_DIRS)
    )


def backup_existing(dest: Path, rel_dest: str, backup_root: Path) -> None:
    backup = backup_root / rel_dest
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest, backup)


def copy_one(src: Path, rel_dest: str, counts: dict[str, int],
             target: Path, upgrade: bool, backup_root: Optional[Path],
             requested_adapters: Optional[set[str]]) -> None:
    dest = target / rel_dest
    adapter_root = optional_adapter_root(rel_dest)
    if upgrade and adapter_root and not (target / adapter_root).exists():
        if requested_adapters is None or adapter_root not in requested_adapters:
            counts["skipped"] += 1
            return
    if rel_dest in CONSUMER_OWNED and dest.exists():
        counts["skipped"] += 1
        return
    if dest.exists():
        if upgrade and rel_dest not in UPGRADE_PRESERVE:
            if backup_root is not None:
                backup_existing(dest, rel_dest, backup_root)
                counts["backed_up"] += 1
            shutil.copy2(src, dest)
            counts["updated"] += 1
        else:
            counts["skipped"] += 1
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    counts["copied"] += 1


def add_adapters_targeted(target: Path, names: set[str]) -> int:
    """Targeted add: CHỈ copy các optional adapter được nêu vào project đã init;
    KHÔNG tái stage kernel hay adapter khác. File đã tồn tại được giữ nguyên
    (không clobber). Dùng cho lệnh add-adapter sau init."""
    if not (target / "pilothOS" / ".initialized").exists():
        fail("project chua init PilothOS — chay init truoc khi add adapter.")
    if not names:
        fail("--add-adapters can it nhat mot adapter.")
    valid = sorted(OPTIONAL_ADAPTER_ROOTS)
    unknown = sorted(n for n in names if n not in OPTIONAL_ADAPTER_ROOTS)
    if unknown:
        fail(f"chi add duoc optional adapter {valid} (claude luon co san): {unknown}")
    counts = {"copied": 0, "updated": 0, "backed_up": 0, "skipped": 0}
    for name in sorted(names):
        root = OPTIONAL_ADAPTER_ROOTS[name]
        src = REPO / "adapters" / name
        if not src.is_dir():
            fail(f"khong tim thay nguon adapter: adapters/{name}")
        for child in sorted(p for p in src.rglob("*") if p.is_file()):
            if ignored_distribution_artifact(child.relative_to(src)):
                continue
            rel = child.relative_to(src).as_posix()
            copy_one(child, f"{root}/{rel}", counts, target,
                     upgrade=False, backup_root=None, requested_adapters=None)
    print(
        f"OK: add adapters {sorted(names)} — copied={counts['copied']}, "
        f"skipped-vi-da-co={counts['skipped']}"
    )
    print("Tiep theo: ghi nhan qua engine (plan mode=upgrade, op write_marker) "
          "theo skill pilothos-adapter.")
    return 0


def main() -> int:
    target, upgrade, unattended, add_adapters, installer_args = parse_args(sys.argv[1:])
    if not (REPO / "pilothOS").is_dir():
        fail(f"khong tim thay nguon PilothOS tai {REPO}")
    if add_adapters is not None:
        return add_adapters_targeted(target, add_adapters)
    initialized = (target / "pilothOS" / ".initialized").exists()
    if initialized and not upgrade:
        fail("project da init PilothOS — dung --upgrade de re-stage/upgrade.")
    if (target / "pilothOS").is_dir() and not upgrade:
        fail(f"{target / 'pilothOS'} da ton tai — xoa/phuc hoi truoc hoac dung --upgrade.")

    counts = {"copied": 0, "updated": 0, "backed_up": 0, "skipped": 0}
    requested_adapters = requested_adapter_roots(installer_args)
    backup_root = None
    if upgrade:
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        backup_root = target / "pilothOS" / ".backup" / f"stage-upgrade-{ts}"
    for src_rel, dest_rel in MAP:
        src = REPO / src_rel
        if src.is_file():
            if ignored_distribution_artifact(src.relative_to(REPO)):
                continue
            copy_one(src, dest_rel, counts, target, upgrade, backup_root,
                     requested_adapters)
        elif src.is_dir():
            for child in sorted(p for p in src.rglob("*") if p.is_file()):
                if ignored_distribution_artifact(child.relative_to(src)):
                    continue
                rel = child.relative_to(src).as_posix()
                copy_one(child, f"{dest_rel}/{rel}", counts, target, upgrade,
                         backup_root, requested_adapters)

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
