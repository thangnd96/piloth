"""End-to-end CLI dispatch tests (F10).

The other unit tests exercise pure functions; these invoke the shipped bundle
through the real COMMAND_TABLE → handler → stdout-JSON path the way a Claude Code
hook (stdin) or a consumer (argv) actually calls it — proving the I/O contract,
not just the decision logic.
"""
import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _run(mode, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(GUARD), mode, *args],
        input=stdin, capture_output=True, text=True,
    )


def _run_json(mode, *args, stdin=None):
    p = _run(mode, *args, stdin=stdin)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


# --- broker-check: the hook block contract (stdin -> block JSON) ---
def test_broker_check_cli_blocks_catastrophic():
    p = _run("broker-check", stdin=json.dumps({"tool_input": {"command": "rm -rf /"}}))
    assert p.returncode == 0
    assert '"decision": "block"' in p.stdout
    assert "PILOTHOS BROKER" in p.stdout


def test_broker_check_cli_blocks_wrapper_bypass():
    p = _run("broker-check", stdin=json.dumps({"tool_input": {"command": "bash -c 'rm -rf /'"}}))
    assert '"decision": "block"' in p.stdout


def test_broker_check_cli_allows_safe_silently():
    p = _run("broker-check", stdin=json.dumps({"tool_input": {"command": "ls -la"}}))
    assert p.returncode == 0
    assert p.stdout.strip() == ""


# --- capability / provenance / skill-index / os-inspect via CLI ---
def test_capability_check_cli():
    assert _run_json("capability-check")["result"] == "capability_check_passed"


def test_capability_list_cli():
    d = _run_json("capability-list")
    assert d["result"] == "capability_list" and d["count"] >= 1


def test_authority_delta_cli(tmp_path):
    before = tmp_path / "b.json"
    after = tmp_path / "a.json"
    before.write_text(json.dumps({"authority": {"paths": ["a/**"]}}), encoding="utf-8")
    after.write_text(json.dumps({"authority": {"paths": ["a/**", "b/**"], "writes_policy": True}}), encoding="utf-8")
    d = _run_json("authority-delta", str(before), str(after))
    assert d["result"] == "authority_delta" and d["widened"] is True


def test_provenance_cli():
    assert _run_json("provenance")["result"] == "provenance_ok"


def test_provenance_files_cli_on_empty_root(tmp_path):
    d = _run_json("provenance", "--files", str(tmp_path))
    # empty root: kernel files missing, none mismatched -> ok
    assert d["mismatched"] == []


def test_skill_index_cli():
    d = _run_json("skill-index")
    assert d["result"] == "skill_index" and d["kernel"] >= 7


def test_os_inspect_cli():
    d = _run_json("os-inspect")
    assert d["result"] in ("os_inspect_healthy", "os_inspect_attention")
    assert d["syscalls"]["guard_modes"] > 0


def test_forge_scaffold_cli(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "kind": "skill", "id": "cli-test-skill", "layer": "Skills",
        "intent": "e2e cli test skill", "reason": "cli dispatch test",
    }), encoding="utf-8")
    d = _run_json("forge-scaffold", str(spec))
    assert d["result"] == "forge_scaffold"
    assert "pilothOS/skills/workflow/cli-test-skill/SKILL.md" in d["files"]


def test_forge_verify_cli_rejects_bad_spec(tmp_path):
    spec = tmp_path / "bad.json"
    spec.write_text(json.dumps({"kind": "skill", "id": "os-start", "layer": "Rules"}), encoding="utf-8")
    d = _run_json("forge-verify", str(spec))
    assert d["result"] == "forge_verify_failed"
    assert d["errors"]


def test_forge_scaffold_cli_does_not_write_live(tmp_path):
    # construction != activation: forge-scaffold returns content, never writes live.
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "kind": "skill", "id": "noexist-skill", "layer": "Skills",
        "intent": "x", "reason": "y",
    }), encoding="utf-8")
    d = _run_json("forge-scaffold", str(spec))
    assert "pilothOS/skills/workflow/noexist-skill/SKILL.md" in d["files"]
    assert not (REPO / "pilothOS" / "skills" / "workflow" / "noexist-skill").exists()


def test_forge_plan_cli_shape(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "kind": "skill", "id": "plan-skill", "layer": "Skills",
        "intent": "x", "reason": "y",
        "authority": {"guard_modes": ["os-evidence"], "paths": ["a/**"]},
    }), encoding="utf-8")
    d = _run_json("forge-plan", str(spec))
    assert d["result"] == "forge_plan"
    assert d["approval_required"] is True
    assert d["widened"] is True
    assert "os-evidence" in d["authority_delta"]["guard_modes"]["added"]


def test_forge_verify_cli_rejects_missing_intent(tmp_path):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"kind": "skill", "id": "noreason-skill", "layer": "Skills"}), encoding="utf-8")
    d = _run_json("forge-verify", str(spec))
    assert d["result"] == "forge_verify_failed"
    assert any("intent" in e for e in d["errors"]) and any("reason" in e for e in d["errors"])
