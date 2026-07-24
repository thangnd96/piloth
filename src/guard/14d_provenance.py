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
    if not root.is_absolute():
        root = REPO_ROOT / root  # cwd-independent: repo-relative manifest paths
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


def upgrade_verify_result(root, manifest=None):
    """Upgrade self-heal (T6): sau khi nang cap, ban cai co (a) kernel verbatim
    khop sha256 (da update dung), (b) file preserve-class (consumer-owned /
    personalize) VAN CON MAT (customization/state duoc bao ton). Analog cua
    upgrade-self-heal-ready gate cua AOS. Tai dung verify_manifest_files (T4) +
    marker class/personalize san co trong manifest (khong duplicate preserve-set
    cua stage.py)."""
    root_p = pathlib.Path(root)
    if not root_p.is_absolute():
        root_p = REPO_ROOT / root_p  # cwd-independent
    if manifest is None:
        manifest = _load_dist_manifest()
    kernel = verify_manifest_files(root_p, manifest=manifest)
    files_list = manifest.get("files", []) if isinstance(manifest, dict) else []
    preserved_present = 0
    preserved_missing = []
    for e in files_list:
        if not isinstance(e, dict):
            continue
        if e.get("class") == "consumer-owned" or e.get("personalize"):
            p = e.get("path")
            if not p:
                continue
            if (root_p / p).exists():
                preserved_present += 1
            else:
                preserved_missing.append(p)
    ok = kernel.get("result") == "provenance_files_ok" and not preserved_missing
    return {
        "result": "upgrade_verify_ok" if ok else "upgrade_verify_failed",
        "root": str(root),
        "kernel_integrity": kernel.get("result"),
        "kernel_mismatched": kernel.get("mismatched", []),
        "kernel_missing": kernel.get("missing", 0),
        "preserved_present": preserved_present,
        "preserved_missing": preserved_missing,
    }


def upgrade_verify(argv):
    files = [a for a in (argv or []) if not a.startswith("-")]
    json_print(upgrade_verify_result(files[0] if files else "."))
