"""T6 upgrade self-heal gate — stage --upgrade preserves consumer customization
and state while updating the kernel.

The Piloth analog of AOS's `upgrade-self-heal-ready` release gate: a candidate
must preserve a prior install's customization + state on upgrade. Covers both the
real stage.py --upgrade flow (preservation) and the upgrade-verify guard mode
(post-upgrade integrity).
"""
import hashlib
import importlib.util
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
STAGE = REPO / "scripts" / "stage.py"
GUARD_PATH = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pilothos_guard_upgrade_test", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stage(target, *args):
    subprocess.run([sys.executable, str(STAGE), str(target), *args],
                   check=True, capture_output=True, text=True)


def test_upgrade_preserves_customization_and_state(tmp_path):
    target = tmp_path / "consumer"
    target.mkdir()

    # Fresh install.
    _stage(target)
    assert (target / "pilothOS" / "PilothOS.md").is_file(), "kernel not staged"

    # Consumer customization + state + a consumer-added file (not in the MAP).
    claude = target / "CLAUDE.md"
    claude.write_text(claude.read_text(encoding="utf-8") + "\n# MY CUSTOMIZATION\n", encoding="utf-8")
    (target / "pilothOS" / "rot" / "registry.md").write_text("# my rot state\n", encoding="utf-8")
    state = target / "pilothOS" / "memory" / "state" / "os-runs" / "foo"
    state.mkdir(parents=True)
    (state / "state.json").write_text('{"task":"x"}', encoding="utf-8")
    (target / "pilothOS" / ".initialized").write_text('{"pilothos_version":"1.0.0"}', encoding="utf-8")
    consumer_added = target / "pilothOS" / "knowledge" / "my-project-notes.md"
    consumer_added.write_text("project notes", encoding="utf-8")

    # Upgrade.
    _stage(target, "--upgrade")

    # Preservation invariants.
    assert "MY CUSTOMIZATION" in claude.read_text(encoding="utf-8"), "consumer-owned clobbered"
    assert (target / "pilothOS" / "rot" / "registry.md").read_text(encoding="utf-8") == "# my rot state\n"
    assert (state / "state.json").read_text(encoding="utf-8") == '{"task":"x"}', "state clobbered"
    assert consumer_added.read_text(encoding="utf-8") == "project notes", "consumer-added file clobbered"
    # Kernel re-staged + a backup was created for overwritten kernel files.
    assert (target / "pilothOS" / "PilothOS.md").is_file()
    assert (target / "pilothOS" / ".backup").is_dir(), "no upgrade backup"


def test_upgrade_verify_ok_on_clean_install(tmp_path):
    guard = _load_guard()
    content = b"kernel content"
    sha = hashlib.sha256(content).hexdigest()
    (tmp_path / "pilothOS").mkdir()
    (tmp_path / "pilothOS" / "x.md").write_bytes(content)
    (tmp_path / "CLAUDE.md").write_text("customized", encoding="utf-8")  # preserved present
    manifest = {"files": [
        {"path": "pilothOS/x.md", "class": "verbatim", "sha256": sha},
        {"path": "CLAUDE.md", "class": "consumer-owned", "sha256": "0" * 64},
    ]}
    r = guard.upgrade_verify_result(tmp_path, manifest=manifest)
    assert r["result"] == "upgrade_verify_ok", r
    assert r["preserved_present"] == 1
    assert r["preserved_missing"] == []


def test_upgrade_verify_detects_missing_preserved(tmp_path):
    guard = _load_guard()
    content = b"kernel content"
    sha = hashlib.sha256(content).hexdigest()
    (tmp_path / "pilothOS").mkdir()
    (tmp_path / "pilothOS" / "x.md").write_bytes(content)
    # CLAUDE.md (consumer-owned) missing -> upgrade wiped customization.
    manifest = {"files": [
        {"path": "pilothOS/x.md", "class": "verbatim", "sha256": sha},
        {"path": "CLAUDE.md", "class": "consumer-owned", "sha256": "0" * 64},
    ]}
    r = guard.upgrade_verify_result(tmp_path, manifest=manifest)
    assert r["result"] == "upgrade_verify_failed"
    assert "CLAUDE.md" in r["preserved_missing"]


def test_upgrade_verify_detects_kernel_tamper(tmp_path):
    guard = _load_guard()
    sha = hashlib.sha256(b"official").hexdigest()
    (tmp_path / "pilothOS").mkdir()
    (tmp_path / "pilothOS" / "x.md").write_bytes(b"TAMPERED")
    (tmp_path / "CLAUDE.md").write_text("customized", encoding="utf-8")
    manifest = {"files": [
        {"path": "pilothOS/x.md", "class": "verbatim", "sha256": sha},
        {"path": "CLAUDE.md", "class": "consumer-owned", "sha256": "0" * 64},
    ]}
    r = guard.upgrade_verify_result(tmp_path, manifest=manifest)
    assert r["result"] == "upgrade_verify_failed"
    assert "pilothOS/x.md" in r["kernel_mismatched"]


def test_upgrade_verify_registered_read_only():
    guard = _load_guard()
    assert "upgrade-verify" in guard.COMMAND_TABLE
    _handler, kind = guard.COMMAND_TABLE["upgrade-verify"]
    assert kind == "argv"
    assert "upgrade-verify" in guard.READ_ONLY_GUARD_MODES
