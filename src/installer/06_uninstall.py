# ----------------------------------------------------------------- uninstall

def do_uninstall(confirm):
    manifests = sorted(BACKUP_ROOT.glob("*/manifest.json"))
    if not manifests:
        fail(5, {"result": "nothing_to_restore",
                 "hint": "chua tung init bang installer"})
    mpath = manifests[-1]
    m = json.loads(mpath.read_text(encoding="utf-8"))
    plan = {"restore": [e["path"] for e in m.get("modified", []) + m.get("removed", [])],
            "delete": m.get("created", []), "manifest": str(mpath.relative_to(REPO_ROOT))}
    if not confirm:
        print(json.dumps({"result": "plan_only", "reverse_plan": plan,
                          "hint": "chay lai voi --confirm de thuc hien"},
                         ensure_ascii=False, indent=2))
        return
    for entry in m.get("modified", []) + m.get("removed", []):
        src = REPO_ROOT / entry["backup"]
        dst = REPO_ROOT / entry["path"]
        if dst.exists():
            shutil.rmtree(dst) if dst.is_dir() else dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for c in m.get("created", []):
        p = REPO_ROOT / c
        if p.exists():
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    if MARKER.exists():
        MARKER.unlink()
    print(json.dumps({"result": "uninstalled", "restored": plan["restore"],
                      "deleted": plan["delete"],
                      "backup_kept": str(mpath.parent.relative_to(REPO_ROOT))},
                     ensure_ascii=False, indent=2))


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    cmd = args[0]
    if cmd == "explain":
        print(MERGE_SEMANTICS)
        return
    if cmd == "unattended":
        do_unattended(args[1:])
        return
    if cmd == "uninstall":
        do_uninstall("--confirm" in args)
        return
    if cmd in ("validate", "dry-run", "apply"):
        if len(args) < 2:
            fail(2, {"error": f"{cmd} can duong dan plan.json hoac inline JSON"})
        plan, plan_path = load_plan_arg(args[1], cmd)
        # Normalize: sinh remove_path (adapter khong chon) + append_lines
        # (.gitignore) deterministic từ ý định khai báo. Chạy ở dry-run/apply
        # và ghi lại file để "thứ approve = thứ thực thi". `validate` giữ
        # non-mutating (chỉ kiểm plan như đã cho).
        try:
            changed = normalize_plan(plan)
        except PlanError as pe:
            fail(2, {"result": "plan_rejected", "error": str(pe)})
        if changed and cmd in ("dry-run", "apply"):
            plan_path.write_text(
                json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        try:
            actions, notes = validate_and_simulate(plan)
        except NeedsJudgment as nj:
            fail(4, {"result": "needs_judgment", "items": nj.items})
        except PlanError as pe:
            fail(2, {"result": "plan_rejected", "error": str(pe)})
        if cmd in ("validate", "dry-run"):
            print(json.dumps({
                "result": "plan_valid", "notes": notes,
                "effects": [{"target": a["target"], "kind": a["kind"]}
                            for a in actions] + [{"target": "pilothOS/.initialized",
                                                  "kind": "modify" if MARKER.exists() else "create"}],
            }, ensure_ascii=False, indent=2))
            return
        do_apply(plan, plan_path)
        return
    fail(2, {"error": f"lenh khong ho tro: {cmd}"})


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
