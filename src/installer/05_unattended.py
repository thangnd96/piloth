# --------------------------------------------------------------- unattended

def adapter_set(value):
    """Chuẩn hoá adapter selection từ list (plan.adapters) hoặc chuỗi CSV.

    Giữ lại để plan cũ khai `adapters` vẫn parse được; giờ chỉ `claude` hợp lệ,
    nên một plan xin cursor/codex/antigravity bị từ chối thay vì im lặng không
    cài gì."""
    if value is None:
        return set(ALLOWED_ADAPTERS)
    if isinstance(value, str):
        items = [x.strip().lower() for x in value.split(",") if x.strip()]
    elif isinstance(value, list):
        items = [x.strip().lower() for x in value
                 if isinstance(x, str) and x.strip()]
    else:
        raise PlanError(f"adapters phai la list hoac chuoi CSV: {value!r}")
    if not items:
        return set(ALLOWED_ADAPTERS)
    sel = set(items)
    unknown = sorted(sel - ALLOWED_ADAPTERS)
    if unknown:
        raise PlanError(f"unknown adapter(s): {', '.join(unknown)}")
    return sel


def selected_adapters(raw):
    return adapter_set(raw)


def _insert_before_marker(steps, new_steps):
    """Chèn new_steps ngay trước write_marker (hoặc cuối nếu chưa có marker),
    giữ write_marker luôn ở cuối."""
    if not new_steps:
        return
    idx = len(steps)
    for i, s in enumerate(steps):
        if isinstance(s, dict) and s.get("op") == "write_marker":
            idx = i
            break
    steps[idx:idx] = new_steps


def gitignore_append_step(plan, steps):
    """append_lines step cho .gitignore suy ra từ options.gitignore_scope, hoặc
    None nếu không cần. Idempotent: bỏ qua nếu đã có step .gitignore hoặc mọi dòng
    đã nằm trong file."""
    gi = REPO_ROOT / ".gitignore"
    if not gi.exists():
        return None
    if any(isinstance(s, dict) and s.get("op") == "append_lines"
           and s.get("target") == ".gitignore" for s in steps):
        return None
    scope = (
        plan.get("options") or {}
    ).get("gitignore_scope", DEFAULT_GITIGNORE_SCOPE)
    want = (
        PILOTHOS_GITIGNORE_ALL
        if scope == "all"
        else PILOTHOS_GITIGNORE_RUNTIME_LINES
    )
    current = set(gi.read_text(encoding="utf-8").splitlines())
    missing = [l for l in want if l not in current]
    if not missing:
        return None
    return {"op": "append_lines", "target": ".gitignore", "lines": ["", *missing]}


def normalize_plan(plan):
    """Suy ra các step deterministic từ ý định khai báo (`adapters`,
    `options.gitignore_scope`) — SSOT ở engine, Claude không gõ tay từng step.
    Chạy ở dry-run TRƯỚC khi user approve nên vẫn giữ byte-identical.
    Idempotent. Mutate plan tại chỗ; trả True nếu có thay đổi."""
    if not isinstance(plan, dict):
        return False
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return False
    new_steps = []
    # Upgrade preserves consumer settings.json by design, so a script this
    # version stopped shipping keeps being invoked. Engine-injected, same as the
    # gitignore step: deterministic, visible in dry-run, approved with the plan.
    if plan.get("mode") == "upgrade" and not any(
        isinstance(s_, dict) and s_.get("op") == "prune_dead_hooks" for s_ in steps
    ):
        new_steps.append({"op": "prune_dead_hooks", "target": ".claude/settings.json"})
    gi_step = gitignore_append_step(plan, steps)
    if gi_step:
        new_steps.append(gi_step)
    if not new_steps:
        return False
    _insert_before_marker(steps, new_steps)
    return True


def add_self_prune(steps):
    for target in SELF_PRUNE_ORDER:
        if (REPO_ROOT / target).exists():
            steps.append({"op": "remove_path", "target": target})


def build_unattended_plan(argv):
    parser = argparse.ArgumentParser(prog="unattended")
    parser.add_argument("--mode", choices=("greenfield", "brownfield", "upgrade"),
                        default="greenfield")
    parser.add_argument("--persona", default="")
    parser.add_argument("--goals", default="")
    parser.add_argument("--owner", default="")
    parser.add_argument("--adapters", default="claude")
    parser.add_argument("--statusline", choices=("consumer", "pilothos", "chain"))
    parser.add_argument("--gitignore-scope", choices=GITIGNORE_SCOPES,
                        default=DEFAULT_GITIGNORE_SCOPE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--print-plan", action="store_true")
    args = parser.parse_args(argv)

    plan = {
        "plan_version": 1,
        "mode": args.mode,
        "fill": {"PERSONA": args.persona, "GOALS": args.goals, "OWNER": args.owner},
        "adapters": sorted(adapter_set(args.adapters)),
        "steps": [],
    }
    options = {}
    if args.statusline:
        options["statusline"] = args.statusline
    if args.gitignore_scope != DEFAULT_GITIGNORE_SCOPE:
        options["gitignore_scope"] = args.gitignore_scope
    if options:
        plan["options"] = options
    steps = plan["steps"]

    if args.mode == "greenfield":
        if (REPO_ROOT / "CLAUDE.md").exists():
            steps.append({"op": "fill_placeholders", "target": "CLAUDE.md"})
        if (REPO_ROOT / "pilothOS/rot/registry.md").exists():
            steps.append({"op": "fill_placeholders", "target": "pilothOS/rot/registry.md"})
    elif args.mode == "brownfield":
        if (REPO_ROOT / "pilothOS/rot/registry.md").exists():
            steps.append({"op": "fill_placeholders", "target": "pilothOS/rot/registry.md"})
        claude = REPO_ROOT / "CLAUDE.md"
        if claude.exists():
            text = claude.read_text(encoding="utf-8", errors="replace")
            if "@pilothOS/bootstrap.md" in text:
                steps.append({"op": "fill_placeholders", "target": "CLAUDE.md"})
            else:
                steps.append({"op": "prepend_block", "payload": "identity-block.md",
                              "target": "CLAUDE.md"})
        agents = REPO_ROOT / "AGENTS.md"
        if agents.exists():
            text = agents.read_text(encoding="utf-8", errors="replace")
            if "PilothOS Startup Contract" not in text:
                steps.append({"op": "prepend_block", "payload": "startup-contract-block.md",
                              "target": "AGENTS.md"})
        if (REPO_ROOT / ".claude/settings.json").exists():
            steps.append({"op": "merge_settings", "payload": "settings.json",
                          "target": ".claude/settings.json"})

    add_self_prune(steps)
    steps.append({"op": "write_marker"})
    # Adapter removals + .gitignore suy ra deterministic từ `adapters` /
    # `options.gitignore_scope` (SSOT — cùng đường với luồng interactive).
    normalize_plan(plan)
    return plan, args


def do_unattended(argv):
    try:
        plan, args = build_unattended_plan(argv)
    except PlanError as pe:
        fail(2, {"result": "plan_rejected", "error": str(pe)})
    if args.print_plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    pending = PILOTHOS_DIR / ".pending-plan.json"
    pending.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    try:
        actions, notes = validate_and_simulate(plan)
    except NeedsJudgment as nj:
        fail(4, {"result": "needs_judgment", "items": nj.items,
                 "pending_plan": str(pending.relative_to(REPO_ROOT))})
    except PlanError as pe:
        fail(2, {"result": "plan_rejected", "error": str(pe),
                 "pending_plan": str(pending.relative_to(REPO_ROOT))})
    if args.dry_run:
        print(json.dumps({
            "result": "plan_valid", "notes": notes,
            "pending_plan": str(pending.relative_to(REPO_ROOT)),
            "effects": [{"target": a["target"], "kind": a["kind"]}
                        for a in actions] + [{"target": "pilothOS/.initialized",
                                              "kind": "create" if not MARKER.exists() else "modify"}],
        }, ensure_ascii=False, indent=2))
        return
    do_apply(plan, pending)


