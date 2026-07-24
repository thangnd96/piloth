"""Unit tests for T4 supply-chain provenance (probe #5).

Content-addressed dist-manifest: every shipped file carries a sha256; a
manifest_digest makes the manifest tamper-evident and reproducible;
verify_manifest_files lets a consumer confirm an install matches the release —
the Piloth analog of AOS's BLAKE3 manifest + content-addressed verification.
"""
import copy
import hashlib


def test_manifest_has_provenance(guard):
    m = guard._load_dist_manifest()
    assert isinstance(m, dict)
    assert m.get("manifest_digest")
    assert "source_commit" in m
    for e in m["files"]:
        assert e.get("sha256"), f"file entry missing sha256: {e.get('path')}"


def test_provenance_ok_on_real_manifest(guard):
    r = guard.provenance_result()
    assert r["result"] == "provenance_ok", r
    assert r["digest_ok"] is True
    assert r["files_missing_hash"] == 0


def test_recompute_matches_stored_digest(guard):
    m = guard._load_dist_manifest()
    digest, missing = guard.recompute_manifest_digest(m)
    assert digest == m["manifest_digest"]
    assert missing == 0


def test_tampered_manifest_detected(guard):
    m = copy.deepcopy(guard._load_dist_manifest())
    m["files"][0]["sha256"] = "0" * 64  # flip a declared hash without updating digest
    r = guard.provenance_result(manifest=m)
    assert r["result"] == "provenance_mismatch"
    assert r["digest_ok"] is False


def test_verify_files_match(guard, tmp_path):
    content = b"hello piloth"
    sha = hashlib.sha256(content).hexdigest()
    (tmp_path / "pilothOS").mkdir()
    (tmp_path / "pilothOS" / "x.md").write_bytes(content)
    manifest = {"files": [{"path": "pilothOS/x.md", "class": "verbatim", "sha256": sha}]}
    r = guard.verify_manifest_files(tmp_path, manifest=manifest)
    assert r["result"] == "provenance_files_ok"
    assert r["matched"] == 1


def test_verify_files_detects_tamper(guard, tmp_path):
    sha = hashlib.sha256(b"official").hexdigest()
    (tmp_path / "pilothOS").mkdir()
    (tmp_path / "pilothOS" / "x.md").write_bytes(b"TAMPERED")
    manifest = {"files": [{"path": "pilothOS/x.md", "class": "verbatim", "sha256": sha}]}
    r = guard.verify_manifest_files(tmp_path, manifest=manifest)
    assert r["result"] == "provenance_files_mismatch"
    assert "pilothOS/x.md" in r["mismatched"]


def test_verify_skips_consumer_owned_and_personalize(guard, tmp_path):
    manifest = {"files": [
        {"path": "CLAUDE.md", "class": "consumer-owned", "sha256": "0" * 64},
        {"path": "pilothOS/rot/registry.md", "class": "verbatim", "sha256": "0" * 64, "personalize": True},
    ]}
    r = guard.verify_manifest_files(tmp_path, manifest=manifest)
    assert r["result"] == "provenance_files_ok"
    assert r["matched"] == 0 and r["missing"] == 0


def test_provenance_registered_read_only(guard):
    assert "provenance" in guard.COMMAND_TABLE
    _handler, kind = guard.COMMAND_TABLE["provenance"]
    assert kind == "argv"
    assert "provenance" in guard.READ_ONLY_GUARD_MODES
