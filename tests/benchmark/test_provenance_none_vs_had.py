"""TB benchmark — none-piloth vs had-piloth for T4 supply-chain provenance.

Probe #7 for T4: a content-addressed manifest lets a consumer detect a corrupted
or tampered install that a bare distribution cannot. none-piloth ships files with
no per-file hash -> corruption is silent; had-piloth verifies every file against
its sha256 -> corruption is caught.
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
    sha = hashlib.sha256(official).hexdigest()
    manifest = {"files": [{"path": "pilothOS/kernel.md", "class": "verbatim", "sha256": sha}]}

    # Install where the file was corrupted after shipping (bit-rot / tamper / bad copy).
    (tmp_path / "pilothOS").mkdir()
    (tmp_path / "pilothOS" / "kernel.md").write_bytes(b"corrupted!!!")

    # none-piloth: no content-addressed manifest -> corruption is undetectable.
    none_detected = False

    # had-piloth: provenance verifies every shipped file against its sha256.
    r = guard.verify_manifest_files(tmp_path, manifest=manifest)
    had_detected = r["result"] == "provenance_files_mismatch"

    assert none_detected is False
    assert had_detected is True

    consumer_value_passed = had_detected and not none_detected
    assert consumer_value_passed, {"had": r}
