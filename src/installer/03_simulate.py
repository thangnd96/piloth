# ------------------------------------------------------------------ simulate

def validate_and_simulate(plan):
    """Trả về (actions, notes). actions: list {target, kind, content|None}.
    kind: create | modify | remove. KHÔNG chạm đĩa."""
    if not isinstance(plan, dict):
        raise PlanError("plan phai la JSON object")
    extra = set(plan) - PLAN_TOP_FIELDS
    if extra:
        raise PlanError(f"field la trong plan: {sorted(extra)}")
    if plan.get("plan_version") != 1:
        raise PlanError("plan_version phai la 1")
    if plan.get("mode") not in ("greenfield", "brownfield", "upgrade"):
        raise PlanError("mode phai la greenfield|brownfield|upgrade")
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise PlanError("steps phai la list khong rong")
    options = plan.get("options") or {}
    if set(options) - OPTION_FIELDS:
        raise PlanError(f"option la: {sorted(set(options) - OPTION_FIELDS)}")
    if "gitignore_scope" in options and options["gitignore_scope"] not in GITIGNORE_SCOPES:
        raise PlanError(f"options.gitignore_scope phai la {GITIGNORE_SCOPES}")
    if "adapters" in plan and "claude" not in adapter_set(plan.get("adapters")):
        raise PlanError("'adapters' phai gom 'claude' (adapter duy nhat Piloth ship)")
    fill = plan.get("fill") or {}
    if MARKER.exists() and plan.get("mode") != "upgrade":
        raise PlanError("pilothOS/.initialized da ton tai — re-init/upgrade can mode=upgrade")
    if plan.get("mode") == "upgrade" and not MARKER.exists():
        raise PlanError("mode=upgrade can pilothOS/.initialized ton tai")

    notes, actions = [], []
    virtual = {}  # target -> content sau simulate (de bat create-trung)

    def existing_content(target):
        if target in virtual:
            return virtual[target]
        p = REPO_ROOT / target
        return p.read_text(encoding="utf-8") if p.exists() and p.is_file() else None

    marker_seen = False
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise PlanError(f"step {i} phai la object")
        extra = set(step) - STEP_FIELDS
        if extra:
            raise PlanError(f"step {i}: field la {sorted(extra)}")
        op = step.get("op")
        if op not in OPS:
            raise PlanError(f"step {i}: op khong ho tro: {op}")
        if op == "write_marker":
            marker_seen = True
            continue
        target = safe_rel(step.get("target", ""))
        check_target_writable_zone(target, op)
        tpath = REPO_ROOT / target

        if op == "create_from_payload":
            if tpath.exists() or target in virtual:
                raise PlanError(f"step {i}: target da ton tai: {target}")
            content = load_payload(step.get("payload", ""), fill)
            virtual[target] = content
            actions.append({"target": target, "kind": "create", "content": content})
        elif op == "prepend_block":
            cur = existing_content(target)
            if cur is None:
                raise PlanError(f"step {i}: prepend vao file khong ton tai: {target}")
            block = load_payload(step.get("payload", ""), fill)
            content = block.rstrip("\n") + "\n\n" + cur
            virtual[target] = content
            actions.append({"target": target, "kind": "modify", "content": content})
        elif op == "append_lines":
            lines = step.get("lines")
            if (not isinstance(lines, list) or not lines
                    or any(not isinstance(l, str) or len(l) > 200 or "\n" in l
                           for l in lines)):
                raise PlanError(f"step {i}: lines phai la list chuoi ngan mot dong")
            cur = existing_content(target)
            base = (cur.rstrip("\n") + "\n") if cur else ""
            content = base + "\n".join(lines) + "\n"
            virtual[target] = content
            actions.append({"target": target,
                            "kind": "modify" if cur is not None else "create",
                            "content": content})
        elif op == "merge_settings":
            payload = json.loads(load_payload(step.get("payload", ""), {}))
            cur = existing_content(target)
            consumer = json.loads(cur) if cur else {}
            merged = merge_settings_content(consumer, payload, options, notes)
            content = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
            virtual[target] = content
            actions.append({"target": target,
                            "kind": "modify" if cur is not None else "create",
                            "content": content})
        elif op == "fill_placeholders":
            cur = existing_content(target)
            if cur is None:
                raise PlanError(f"step {i}: fill vao file khong ton tai: {target}")
            content = fill_text(cur, fill, target.endswith("rot/registry.md"))
            virtual[target] = content
            actions.append({"target": target, "kind": "modify", "content": content})
        elif op == "remove_path":
            if not tpath.exists():
                raise PlanError(f"step {i}: remove_path target khong ton tai: {target}")
            actions.append({"target": target, "kind": "remove", "content": None})
    if not marker_seen:
        raise PlanError("plan thieu write_marker (bat buoc, dat cuoi)")
    settings_rel = ".claude/settings.json"
    if settings_rel not in virtual and not (REPO_ROOT / settings_rel).exists():
        raise PlanError(
            "plan khong tao .claude/settings.json va file chua ton tai — "
            "self-check se FAIL; them step merge_settings")
    # dedupe theo target: giu action cuoi cung cho moi target
    final, seen = [], set()
    for a in reversed(actions):
        if a["target"] not in seen:
            seen.add(a["target"])
            final.append(a)
    final.reverse()
    return final, notes


