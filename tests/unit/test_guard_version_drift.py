"""Unit tests for the session-start version-drift advisory.

The advisory tells a consumer their initialized pilothOS/ is older than the
plugin they just updated, prompting /piloth:update. It MUST be fail-soft: any
missing marker / missing env / parse failure yields silence, never an exception.
"""
import json


def _write_marker(tmp_path, version):
    marker = tmp_path / ".initialized"
    marker.write_text(json.dumps({"pilothos_version": version}), encoding="utf-8")
    return marker


def _plugin_root(tmp_path, version):
    root = tmp_path / "plugin"
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"version": version}), encoding="utf-8")
    return root


def test_advisory_when_plugin_newer(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "INIT_MARKER", _write_marker(tmp_path, "0.0.1"))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(_plugin_root(tmp_path, "0.0.2")))
    advisory = guard.version_drift_advisory()
    assert advisory is not None
    assert "/piloth:update" in advisory
    assert "0.0.1" in advisory and "0.0.2" in advisory


def test_silent_when_equal(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "INIT_MARKER", _write_marker(tmp_path, "0.0.2"))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(_plugin_root(tmp_path, "0.0.2")))
    assert guard.version_drift_advisory() is None


def test_silent_when_plugin_older(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "INIT_MARKER", _write_marker(tmp_path, "0.0.2"))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(_plugin_root(tmp_path, "0.0.1")))
    assert guard.version_drift_advisory() is None


def test_silent_when_no_marker(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "INIT_MARKER", tmp_path / "missing" / ".initialized")
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(_plugin_root(tmp_path, "0.0.2")))
    assert guard.version_drift_advisory() is None


def test_silent_when_no_plugin_root(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "INIT_MARKER", _write_marker(tmp_path, "0.0.1"))
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    assert guard.version_drift_advisory() is None


def test_silent_on_bad_version(guard, tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "INIT_MARKER", _write_marker(tmp_path, "not-a-version"))
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(_plugin_root(tmp_path, "0.0.2")))
    assert guard.version_drift_advisory() is None


def test_parse_semver_fail_soft(guard):
    assert guard.parse_semver("1.2.3") == (1, 2, 3)
    assert guard.parse_semver("2.0") == (2, 0)
    assert guard.parse_semver("bad") is None
    assert guard.parse_semver(None) is None
