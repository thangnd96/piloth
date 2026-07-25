"""Single source of truth for the Piloth distribution model.

stage.py (copies the tree into a consumer) and build_manifest.py (writes the
completeness SSOT dist-manifest.json) walk the SAME source->dest MAP and skip
the SAME local/runtime artifacts. Keeping that model here lets the two tools
provably agree instead of drifting (guarded by tests/install + tests/docs).

Only distribution tooling imports this module; it is never staged into a
consumer (scripts/ is not part of the MAP below).
"""
import pathlib

# source (repo-relative) -> dest (consumer-relative).
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

# Artifacts present in the working tree that must never be distributed.
IGNORE_NAMES = {".DS_Store", "Thumbs.db"}
IGNORE_DIRS = {"__pycache__"}
LOCAL_STATE_FILES = {
    "memory/state/scheduler-history.jsonl",
    "memory/state/receipt-seals.jsonl",
}
LOCAL_STATE_DIRS = {
    "memory/state/team-runs",
    "memory/state/os-runs",
    "memory/state/codebase-index",
}

# Dest paths the consumer owns: never clobbered on stage, classed non-verbatim.
CONSUMER_OWNED = {"CLAUDE.md", "AGENTS.md", ".gitignore", ".claude/settings.json"}

# Append-only ledgers that each say, in their own header, that they ship EMPTY:
# the history belongs to the implementation that produced it. They are real
# operational state in the Piloth repo — and the auto-log gate requires appending
# to them on every session that changes files — so they cannot simply be blanked
# here. Instead the vendor's rows are stripped as they are staged, so a fresh
# install starts with the table header and nothing else.
SHIP_EMPTY_LOGS = {
    "pilothOS/rot/review-log.md",
    "pilothOS/memory/lessons-learned.md",
}


def log_header_only(text):
    """Markdown log text with its data rows removed, header/table intact.

    Keeps everything through the table's `|---|` separator and drops the table
    rows after it, so the staged file reads exactly like the empty file the
    header promises.
    """
    out = []
    seen_separator = False
    for line in text.splitlines():
        stripped = line.strip()
        is_row = stripped.startswith("|") and stripped.endswith("|")
        if seen_separator and is_row:
            continue
        out.append(line)
        if is_row and set(stripped) <= set("|-: "):
            seen_separator = True
    return "\n".join(out).rstrip("\n") + "\n"


def ignored_distribution_artifact(path):
    """True if a distribution-tree path is a local/runtime artifact that must
    never be staged or listed in the manifest. Accepts any PurePath-like
    (Path or PurePosixPath), relative to its distribution root."""
    rel = pathlib.PurePosixPath(str(path))
    rel_text = rel.as_posix()
    return (
        rel.name in IGNORE_NAMES
        or any(part in IGNORE_DIRS for part in rel.parts)
        or rel_text in LOCAL_STATE_FILES
        or (rel_text.startswith("memory/state/") and rel.suffix == ".jsonl")
        or any(rel_text == item or rel_text.startswith(item + "/") for item in LOCAL_STATE_DIRS)
    )
