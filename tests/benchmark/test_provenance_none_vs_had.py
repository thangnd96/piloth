"""TB benchmark — none-piloth vs had-piloth for T4 supply-chain provenance.

Genuine A/B: the SAME verify code (verify_manifest_files) is run against two real
manifest shapes. none-piloth = a pre-content-addressing manifest (no per-file
sha256) which structurally cannot detect a corrupted file; had-piloth = a
content-addressed manifest (per-file sha256) which catches it. Probe #7.
"""
import hashlib
import importlib.util
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD_PATH = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"


def _load_guard():
    spec = importlib.util.spec_from_file_location("pilothos_guard_prov_bench", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_none_vs_had_provenance_benchmark(tmp_path):
    guard = _load_guard()

    official = b"official kernel content"
    good_sha = hashlib.sha256(official).hexdigest()
    (tmp_path / "pilothOS").mkdir()
    # File was corrupted after shipping (bit-rot / tamper / bad copy).
    (tmp_path / "pilothOS" / "kernel.md").write_bytes(b"corrupted!!!")

    # none-piloth: manifest has NO per-file sha256 -> same verify code has nothing
    # to compare -> corruption is invisible.
    none_manifest = {"files": [{"path": "pilothOS/kernel.md", "class": "verbatim"}]}
    none = guard.verify_manifest_files(tmp_path, manifest=none_manifest)
    none_detected = none["result"] == "provenance_files_mismatch"

    # had-piloth: content-addressed manifest -> corruption caught.
    had_manifest = {"files": [{"path": "pilothOS/kernel.md", "class": "verbatim", "sha256": good_sha}]}
    had = guard.verify_manifest_files(tmp_path, manifest=had_manifest)
    had_detected = had["result"] == "provenance_files_mismatch"

    assert none_detected is False, none   # no hash -> file skipped -> corruption invisible
    assert had_detected is True, had      # hash present -> corruption caught
    assert "pilothOS/kernel.md" in had["mismatched"]

    consumer_value_passed = had_detected and not none_detected
    assert consumer_value_passed, {"none": none, "had": had}
