# ---------------------------------------------------------------------------
# Supply-chain provenance (T4) — content-addressed distribution + integrity.
#
# Ban Piloth cua BLAKE3-manifest + verify-content-addressed cua AOS. dist-manifest
# giờ mo ta moi file bang sha256 + mot manifest_digest (tamper-evident,
# reproducible). Bo sung hash-chained receipt-seals.jsonl san co.
#
#   provenance            self-consistency: recompute manifest_digest tu entries,
#                         so voi digest da luu -> tamper-evident + reproducible.
#   provenance --files R  so file tren dia (duoi root R) vs sha256 -> consumer
#                         kiem tinh toan ven ban cai (integrity/tamper/drift).
#
# Gioi han trung thuc: SHA-256 self-describing manifest + hash-chain, KHONG phai
# code signing/notarization/Sigstore; channels + upgrade-self-heal la buoc CI
# tiep theo (xem runtime/supply-chain.md).
# ---------------------------------------------------------------------------


def _load_dist_manifest():
    return load_json_file(PILOTHOS_DIR / "dist-manifest.json")


def recompute_manifest_digest(manifest):
    """Recompute digest tu file entries (sorted 'path:sha256'). Tra (digest,
    files_missing_hash). Phai khop cach build_manifest.py tinh."""
    lines = []
    missing = 0
    for e in (manifest.get("files") or []):
        if isinstance(e, dict) and e.get("sha256") and e.get("path"):
            lines.append(f"{e['path']}:{e['sha256']}")
        else:
            missing += 1
    digest = hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()
    return digest, missing


def provenance_result(manifest=None):
    if manifest is None:
        manifest = _load_dist_manifest()
    if not isinstance(manifest, dict):
        return {"result": "provenance_failed", "errors": ["dist-manifest.json thieu hoac khong hop le"]}
    if not isinstance(manifest.get("files"), list):
        return {"result": "provenance_failed", "errors": ["manifest.files thieu"]}
    recomputed, missing_hash = recompute_manifest_digest(manifest)
    stored = manifest.get("manifest_digest")
    digest_ok = bool(stored) and recomputed == stored
    return {
        "result": "provenance_ok" if (digest_ok and missing_hash == 0) else "provenance_mismatch",
        "digest_ok": digest_ok,
        "manifest_digest": stored,
        "recomputed_digest": recomputed,
        "files": len(manifest["files"]),
        "files_missing_hash": missing_hash,
        "piloth_version": manifest.get("piloth_version"),
        "source_commit": manifest.get("source_commit"),
    }


def verify_manifest_files(root, manifest=None):
    """So file tren dia (duoi root) vs sha256 trong manifest. Bo qua
    consumer-owned/personalize (co chu dinh khac sau cai). Cho consumer kiem
    tinh toan ven ban cai."""
    root = pathlib.Path(root)
    if manifest is None:
        manifest = _load_dist_manifest()
    files = manifest.get("files", []) if isinstance(manifest, dict) else []
    matched, mismatched, missing = 0, [], 0
    for e in files:
        if not isinstance(e, dict):
            continue
        if e.get("class") == "consumer-owned" or e.get("personalize"):
            continue
        sha, path = e.get("sha256"), e.get("path")
        if not sha or not path:
            continue
        fp = root / path
        if not fp.is_file():
            missing += 1
            continue
        actual = hashlib.sha256(fp.read_bytes()).hexdigest()
        if actual == sha:
            matched += 1
        else:
            mismatched.append(path)
    return {
        "result": "provenance_files_ok" if not mismatched else "provenance_files_mismatch",
        "root": str(root),
        "matched": matched,
        "mismatched": mismatched,
        "missing": missing,
    }


def provenance(argv):
    args = list(argv or [])
    if "--files" in args:
        idx = args.index("--files")
        root = args[idx + 1] if idx + 1 < len(args) else "."
        json_print(verify_manifest_files(root))
        return
    json_print(provenance_result())
