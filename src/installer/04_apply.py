# --------------------------------------------------------------------- apply

def do_apply(plan, plan_path):
    actions, notes = validate_and_simulate(plan)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    bdir = BACKUP_ROOT / ts
    bdir.mkdir(parents=True, exist_ok=False)
    created, modified, removed = [], [], []
    # backup TRUOC moi thay doi
    for a in actions:
        p = REPO_ROOT / a["target"]
        if p.exists():
            dest = bdir / a["target"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            if p.is_dir():
                shutil.copytree(p, dest)
            else:
                shutil.copy2(p, dest)
            entry = {"path": a["target"], "backup": str(dest.relative_to(REPO_ROOT))}
            (removed if a["kind"] == "remove" else modified).append(entry)
        else:
            created.append(a["target"])
    marker_rel = str(MARKER.relative_to(REPO_ROOT))
    marker_backup = bdir / marker_rel
    if MARKER.exists():
        marker_backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(MARKER, marker_backup)
        modified.append({"path": marker_rel, "backup": str(marker_backup.relative_to(REPO_ROOT))})
    else:
        created.append(marker_rel)
    manifest = {
        "pilothos_version": "2.0.2", "timestamp": ts, "mode": plan["mode"],
        "created": created, "modified": modified, "removed": removed,
        "notes": notes,
    }
    (bdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    applied = []
    try:
        for a in actions:
            p = REPO_ROOT / a["target"]
            if a["kind"] == "remove":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(a["content"], encoding="utf-8")
                if p.read_text(encoding="utf-8") != a["content"]:
                    raise IOError(f"postcondition fail: {a['target']}")
            applied.append(a)
        MARKER.write_text(json.dumps({
            "initialized_at": ts, "pilothos_version": "2.0.2",
            "mode": plan["mode"],
            "manifest": str((bdir / 'manifest.json').relative_to(REPO_ROOT)),
        }, indent=2) + "\n", encoding="utf-8")
        shutil.copy2(plan_path, bdir / "install-plan.json")
        self_check_log = bdir / "self-check.log"
        with self_check_log.open("w", encoding="utf-8") as fh:
            out = subprocess.run([sys.executable, str(GUARD), "self-check"],
                                 stdout=fh, stderr=subprocess.STDOUT,
                                 text=True, timeout=10)
        self_check_text = self_check_log.read_text(encoding="utf-8")
        if out.returncode != 0 or "SELF-CHECK PASSED" not in self_check_text:
            raise IOError("self-check FAILED sau apply:\n" + self_check_text)
    except Exception as e:  # AUTO-ROLLBACK
        for a in applied:
            p = REPO_ROOT / a["target"]
            src = bdir / a["target"]
            if src.exists():
                if p.exists():
                    shutil.rmtree(p) if p.is_dir() else p.unlink()
                if src.is_dir():
                    shutil.copytree(src, p)
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, p)
            elif p.exists():
                shutil.rmtree(p) if p.is_dir() else p.unlink()
        if marker_backup.exists():
            MARKER.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(marker_backup, MARKER)
        elif MARKER.exists():
            MARKER.unlink()
        fail(3, {"result": "rolled_back", "error": str(e),
                 "backup": str(bdir.relative_to(REPO_ROOT))})
    dm = PILOTHOS_DIR / "dist-manifest.json"
    missing = []
    if dm.exists():
        for item in json.loads(dm.read_text(encoding="utf-8"))["files"]:
            if item["class"] in ("verbatim", "consumer-owned"):
                if not (REPO_ROOT / item["path"]).exists():
                    missing.append(item["path"])
        if missing:
            notes.append({"completeness_missing": missing})
    receipt = {
        "result": "applied", "mode": plan["mode"], "notes": notes,
        "steps": [{"target": a["target"], "kind": a["kind"], "status": "ok"}
                  for a in actions],
        "manifest": str((bdir / "manifest.json").relative_to(REPO_ROOT)),
    }
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


