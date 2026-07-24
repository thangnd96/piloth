"""Unit tests for T5 composability — skill precedence + principal.

The Piloth analog of AOS capsule-skills: a consumer can override or add a skill
without forking the kernel (workspace-wins precedence). principal is read from
context (env), never a payload claim.
"""


def test_kernel_skills_discovered(guard):
    r = guard.skill_index_result()
    assert r["kernel"] >= 7
    ids = {s["id"] for s in r["skills"]}
    assert {"piloth-forge", "piloth-prototype", "piloth-discovery"} <= ids
    assert all(s["source"] == "kernel" for s in r["skills"])


def test_consumer_override_wins(guard, tmp_path):
    (tmp_path / "piloth-forge").mkdir()
    (tmp_path / "piloth-forge" / "SKILL.md").write_text("# Forge Override\n", encoding="utf-8")
    (tmp_path / "my-skill").mkdir()
    (tmp_path / "my-skill" / "SKILL.md").write_text("# My Skill\n", encoding="utf-8")
    r = guard.skill_index_result(consumer_dir=str(tmp_path))
    assert "piloth-forge" in r["overrides"]
    forge = next(s for s in r["skills"] if s["id"] == "piloth-forge")
    assert forge["source"] == "consumer"
    assert forge["overrides"] == "kernel"
    assert forge["title"] == "Forge Override"
    # new consumer-only skill is added (not an override)
    mine = next(s for s in r["skills"] if s["id"] == "my-skill")
    assert mine["source"] == "consumer" and mine["overrides"] is None


def test_no_consumer_dir_is_kernel_only(guard, monkeypatch):
    monkeypatch.delenv("PILOTHOS_CONSUMER_SKILLS", raising=False)
    r = guard.skill_index_result(consumer_dir=None)
    assert r["consumer"] == 0
    assert r["overrides"] == []


def test_principal_default_and_env(guard, monkeypatch):
    monkeypatch.delenv("PILOTHOS_PRINCIPAL", raising=False)
    assert guard.current_principal() == "local"
    monkeypatch.setenv("PILOTHOS_PRINCIPAL", "alice")
    assert guard.current_principal() == "alice"


def test_skill_title_parse(guard, tmp_path):
    p = tmp_path / "SKILL.md"
    p.write_text("---\nx: 1\n---\n\n#  Hello World  \nbody\n", encoding="utf-8")
    assert guard._skill_title(p) == "Hello World"


def test_consumer_dir_from_env(guard, monkeypatch, tmp_path):
    (tmp_path / "env-skill").mkdir()
    (tmp_path / "env-skill" / "SKILL.md").write_text("# Env Skill\n", encoding="utf-8")
    monkeypatch.setenv("PILOTHOS_CONSUMER_SKILLS", str(tmp_path))
    r = guard.skill_index_result(consumer_dir=None)  # falls back to env
    assert any(s["id"] == "env-skill" and s["source"] == "consumer" for s in r["skills"])


def test_skill_index_registered_read_only(guard):
    assert "skill-index" in guard.COMMAND_TABLE
    _handler, kind = guard.COMMAND_TABLE["skill-index"]
    assert kind == "argv"
    assert "skill-index" in guard.READ_ONLY_GUARD_MODES


def test_os_inspect_surfaces_principal(guard):
    r = guard.os_inspect_result()
    assert "principal" in r
    assert isinstance(r["principal"], str) and r["principal"]
