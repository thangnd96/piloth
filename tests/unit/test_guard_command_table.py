"""Completeness tests for the guard command dispatch table.

Regression guard for the dispatch-table refactor: mode registration must stay
in sync with the dispatch table and cover every required control-plane /
self-host mode. A previous version derived registered modes by regex-parsing
the source `if/elif mode == "..."` chain — replacing that chain silently
dropped every mode until this invariant was pinned.
"""


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
