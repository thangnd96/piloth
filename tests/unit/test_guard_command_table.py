"""Completeness tests for the guard command dispatch table.

Regression guard for the dispatch-table refactor: mode registration must stay
in sync with the dispatch table and cover every required control-plane /
self-host mode. A previous version derived registered modes by regex-parsing
the source `if/elif mode == "..."` chain — replacing that chain silently
dropped every mode until this invariant was pinned.

GUARD_MODES (00_header) is now the single source for mode metadata and every
other list derives from it. The tests below pin that derivation AND check the
registry against the code it describes: a `mutates: False` claim is verified by
walking the call graph of the shipped bundle for reachable write primitives.
That check is what makes the registry evidence rather than an assertion — the
previous hand-maintained lists advertised `artifact-janitor --fix` as read-only
while it removes files.
"""
import ast
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD_SOURCE = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"

# Filesystem writes, as they appear in this codebase: helper wrappers plus the
# pathlib/shutil primitives they bottom out in.
WRITE_PRIMITIVES = {
    "write_json", "write_text", "write_bytes", "writelines", "append_jsonl",
    "mkdir", "unlink", "rmtree", "rename", "touch", "copy2", "copytree", "move",
}


@pytest.fixture(scope="module")
def bundle_functions():
    """Top-level functions of the shipped bundle, by name."""
    tree = ast.parse(GUARD_SOURCE.read_text(encoding="utf-8"))
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def _callee_name(func):
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _direct_writes(fn):
    hits = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node.func)
        if name == "open":
            modes = list(node.args[1:2]) + [k.value for k in node.keywords if k.arg == "mode"]
            for arg in modes:
                if (isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                        and any(c in arg.value for c in "wax")):
                    hits.add("open(write)")
        elif name in WRITE_PRIMITIVES:
            hits.add(name)
    return hits


def _callees(fn):
    """Callees, skipping calls that cannot write because the call site pins
    fix=False. The janitors only delete when fix=True, so control-plane-check /
    production-review / state-doctor calling them in detect mode is genuinely
    read-only — encoded as a proof about the call site, not an allowlist."""
    out = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _callee_name(node.func)
        if name is None:
            continue
        detect_only = any(
            kw.arg == "fix"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value is False
            for kw in node.keywords
        )
        if not detect_only:
            out.add(name)
    return out


def _write_path(name, funcs, seen):
    if name in seen:
        return None
    seen.add(name)
    fn = funcs.get(name)
    if fn is None:
        return None
    direct = sorted(_direct_writes(fn))
    if direct:
        return [name, direct[0]]
    for callee in sorted(_callees(fn)):
        sub = _write_path(callee, funcs, seen)
        if sub:
            return [name] + sub
    return None


def test_registry_and_handlers_cover_the_same_modes(guard):
    assert set(guard.GUARD_MODES) == set(guard.GUARD_HANDLERS)
    assert set(guard.COMMAND_TABLE) == set(guard.GUARD_MODES)


def test_command_table_arg_kind_comes_from_the_registry(guard):
    for mode, (_, kind) in guard.COMMAND_TABLE.items():
        assert kind == guard.GUARD_MODES[mode]["arg_kind"], mode


def test_derived_mode_sets_match_the_registry(guard):
    assert guard.READ_ONLY_GUARD_MODES == frozenset(
        m for m, v in guard.GUARD_MODES.items() if v["mutates"] is not True
    )
    assert set(guard.SELF_HOST_REQUIRED_GUARD_MODES) == {
        m for m, v in guard.GUARD_MODES.items() if v["self_host"]
    }
    assert guard.CONTROL_PLANE_REQUIRED_GUARD_MODES == frozenset(
        m for m, v in guard.GUARD_MODES.items() if v["control_plane"]
    )


def test_never_mutating_modes_reach_no_write_primitive(guard, bundle_functions):
    """A mode declared `mutates: False` must have no path to a write. This is the
    check that turns the registry into evidence."""
    offenders = []
    for mode, meta in sorted(guard.GUARD_MODES.items()):
        if meta["mutates"] is not False:
            continue
        handler = guard.GUARD_HANDLERS[mode].__name__
        path = _write_path(handler, bundle_functions, set())
        if path:
            offenders.append(f"{mode}: {' -> '.join(path)}")
    assert not offenders, (
        "modes declared non-mutating can reach a write primitive:\n  "
        + "\n  ".join(offenders)
    )


def test_always_mutating_modes_do_reach_a_write_primitive(guard, bundle_functions):
    """The opposite direction: a `mutates: True` claim must be real, otherwise the
    registry is denying read-only status to a mode that deserves it (the bug that
    hid codebase-status/codebase-query)."""
    offenders = [
        mode for mode, meta in sorted(guard.GUARD_MODES.items())
        if meta["mutates"] is True
        and not _write_path(guard.GUARD_HANDLERS[mode].__name__, bundle_functions, set())
    ]
    assert not offenders, f"modes declared mutating never write: {offenders}"


@pytest.mark.parametrize("mode,args,expected", [
    ("artifact-janitor", [], False),
    ("artifact-janitor", ["--fix"], True),
    # --target aims the removal at ANOTHER repo, so it writes even without --fix.
    ("artifact-janitor", ["--target", "/tmp/x"], True),
    ("artifact-janitor", ["--target=/tmp/x"], True),
    ("state-janitor", [], False),
    ("state-janitor", ["--keep-runs", "5"], False),
    ("state-janitor", ["--fix", "--kernel-logs"], True),
    ("codebase-status", [], False),
    ("codebase-index", [], True),
    ("os-close", [], True),
    # An unknown mode must never be granted a read-only exemption.
    ("definitely-not-a-mode", [], True),
])
def test_mode_mutates_reads_flags(guard, mode, args, expected):
    assert guard.mode_mutates(mode, args) is expected


@pytest.mark.parametrize("suffix,read_only", [
    ("artifact-janitor", True),
    ("artifact-janitor --fix", False),
    ("artifact-janitor --target /tmp/x", False),
    ("state-janitor --fix --kernel-logs", False),
    ("codebase-status", True),
    ("codebase-query --symbol foo", True),
    ("os-status", True),
    ("contract-write plan.json", False),
    ("log-append review a b c d e", False),
    ("definitely-not-a-mode", False),
    # Existing hardening must survive the registry switch.
    ("os-status && rm -rf /", False),
    ("os-status --deploy prod", False),
])
def test_command_is_read_only_guard_end_to_end(guard, suffix, read_only):
    cmd = f"python3 pilothOS/scripts/pilothos_guard.py {suffix}"
    assert guard.command_is_read_only_guard(cmd) is read_only


def test_modes_named_in_shipped_docs_are_registered(guard):
    """Shipped docs must not advertise a mode that no longer exists. The reverse
    is deliberately NOT asserted: self-hosting.md / os-control-plane.md describe
    the self-hosting contract, not a full CLI reference, so 15 internal modes are
    legitimately absent from them."""
    pattern = re.compile(r"pilothos_guard\.py\s+([a-z][a-z0-9-]+)")
    ghosts = {}
    for doc in sorted((REPO / "pilothOS").rglob("*.md")):
        for mode in pattern.findall(doc.read_text(encoding="utf-8", errors="replace")):
            if mode not in guard.GUARD_MODES:
                ghosts.setdefault(mode, []).append(doc.relative_to(REPO).as_posix())
    assert not ghosts, f"docs reference unregistered modes: {ghosts}"


def test_every_handler_is_callable_with_valid_kind(guard):
    for mode, (handler, kind) in guard.COMMAND_TABLE.items():
        assert callable(handler), f"{mode} handler not callable"
        assert kind in {"hook", "argv", "none"}, f"{mode} has bad arg kind {kind}"


def test_registered_modes_match_command_table(guard):
    # guard_registered_modes() must reflect the dispatch table exactly.
    assert guard.guard_registered_modes() == set(guard.COMMAND_TABLE)


def test_hook_modes_are_exactly_the_stdin_reading_modes(guard):
    hook_modes = {m for m, (_, kind) in guard.COMMAND_TABLE.items() if kind == "hook"}
    assert hook_modes == {
        "session-start",
        "prompt-check",
        "stop-check",
        "pre-edit",
        "post-edit",
    }


def test_table_covers_read_only_guard_modes(guard):
    assert guard.READ_ONLY_GUARD_MODES <= set(guard.COMMAND_TABLE)


def test_table_covers_self_host_required_modes(guard):
    assert set(guard.SELF_HOST_REQUIRED_GUARD_MODES) <= set(guard.COMMAND_TABLE)


def test_core_lifecycle_modes_present(guard):
    for mode in ("os-start", "os-evidence", "os-close", "os-verify", "os-report",
                 "control-plane-check", "context-budget", "receipt-seal"):
        assert mode in guard.COMMAND_TABLE


def test_human_review_modes_present(guard):
    for mode in ("review-request", "review-feedback", "review-verify"):
        assert mode in guard.COMMAND_TABLE
    # review-verify is read-only and must be registered as such.
    assert "review-verify" in guard.READ_ONLY_GUARD_MODES
