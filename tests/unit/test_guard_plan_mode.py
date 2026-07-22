"""Unit tests for the plan-mode exemption in pre_edit.

Claude Code plan mode is read-only planning; Piloth must not block edits with the
contract-before-edit gate while `permission_mode == "plan"`. Governance re-engages
as soon as the session leaves plan mode.
"""


def test_pre_edit_skips_block_in_plan_mode(guard, capsys):
    # No contract, but plan mode → no block decision emitted.
    guard.pre_edit({"permission_mode": "plan", "tool_input": {"file_path": "pilothOS/x.py"}})
    assert capsys.readouterr().out == ""


def test_pre_edit_blocks_without_contract_when_not_plan(guard, monkeypatch, capsys):
    monkeypatch.setattr(guard, "load_task_contract", lambda hi: ({}, None))
    guard.pre_edit({"permission_mode": "default", "tool_input": {"file_path": "pilothOS/x.py"}})
    assert '"decision": "block"' in capsys.readouterr().out


def test_pre_edit_blocks_without_contract_when_mode_absent(guard, monkeypatch, capsys):
    # Missing permission_mode must behave like before (not treated as plan).
    monkeypatch.setattr(guard, "load_task_contract", lambda hi: ({}, None))
    guard.pre_edit({"tool_input": {"file_path": "pilothOS/x.py"}})
    assert '"decision": "block"' in capsys.readouterr().out
