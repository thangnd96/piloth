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


def test_pre_edit_allows_harness_plan_path_without_plan_mode(guard, monkeypatch, tmp_path, capsys):
    # Writing the harness plan file (~/.claude/plans/*.md) must not be blocked even
    # when permission_mode != "plan" — it is a Claude Code artifact, not repo code.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(guard, "load_task_contract", lambda hi: ({}, None))
    plan_file = str(tmp_path / "plans" / "my-plan.md")
    guard.pre_edit({"permission_mode": "default", "tool_input": {"file_path": plan_file}})
    assert capsys.readouterr().out == ""


def test_pre_edit_blocks_when_repo_path_mixed_with_plan_path(guard, monkeypatch, tmp_path, capsys):
    # A repo target alongside a plan target must NOT slip through the plan-path allow.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(guard, "load_task_contract", lambda hi: ({}, None))
    plan_file = str(tmp_path / "plans" / "my-plan.md")
    guard.pre_edit({"permission_mode": "default",
                    "tool_input": {"paths": [plan_file, "pilothOS/x.py"]}})
    assert '"decision": "block"' in capsys.readouterr().out
