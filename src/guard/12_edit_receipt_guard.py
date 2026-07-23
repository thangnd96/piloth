# ---------------------------------------------------- edit/receipt guard modes

def task_contract_write(argv):
    try:
        contract, source = json_arg_or_stdin(argv, "contract-write")
    except Exception as e:
        print(f"FAIL contract-write: {e}")
        return
    errors = validate_task_contract(contract)
    if errors:
        print(json.dumps({"result": "contract_rejected", "errors": errors},
                         ensure_ascii=False, indent=2))
        return
    MARKER_DIR.mkdir(exist_ok=True)
    contract = dict(contract)
    contract["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if source:
        contract["source"] = str(source.relative_to(REPO_ROOT) if REPO_ROOT in source.resolve().parents else source)
    repo_state_file("task-contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK   task contract recorded: {repo_state_file('task-contract.json')}")


def pre_edit(hook_input):
    # Claude Code plan mode is read-only planning (harness restricts edits to the
    # plan file). Piloth's contract-before-edit gate is for execution, not
    # planning, so do not block during plan mode — governance re-engages the
    # moment the session leaves plan mode. `permission_mode` is the documented
    # PreToolUse hook field carrying the current mode ("plan" | "default" | ...).
    if hook_input.get("permission_mode") == "plan":
        return
    # Harness ghi plan file vào ~/.claude/plans (ngoài repo). Đó là artifact của
    # Claude Code, không phải code repo — cho phép kể cả khi harness không truyền
    # permission_mode=="plan" (safety-net bổ trợ). Chỉ allow khi MỌI target là
    # plan-path để không tạo khe hở ghi lẫn file repo.
    raw_targets = raw_edit_targets(hook_input)
    if raw_targets and all(is_harness_plan_path(t) for t in raw_targets):
        return
    contract, contract_path = load_task_contract(hook_input)
    if not contract:
        block_decision(
            "PILOTHOS PRE-EDIT: missing task contract. Before editing, record a "
            "contract with task_scope, affected_layers, allowed_paths, "
            "expected_evidence, out_of_scope_paths, and for non-doc/test work "
            "consumer_scope/context_evidence/reuse_evidence/decision_limits using "
            "`python3 pilothOS/scripts/pilothos_guard.py contract-write <contract.json>`."
        )
        return
    errors = validate_task_contract(contract)
    if errors:
        block_decision("PILOTHOS PRE-EDIT: invalid task contract: " + "; ".join(errors))
        return
    paths, path_errors = edit_paths_from_hook_input(hook_input)
    if path_errors:
        block_decision("PILOTHOS PRE-EDIT: " + "; ".join(path_errors))
        return
    if not paths:
        block_decision("PILOTHOS PRE-EDIT: edit hook did not include a target path.")
        return
    team_contract, team_contract_path = load_team_contract(hook_input)
    role = role_from_hook_input(hook_input)
    if role:
        if not team_contract:
            block_decision(
                "PILOTHOS PRE-EDIT: team role was supplied but no active team contract was found."
            )
            return
        team_errors = validate_team_contract(team_contract)
        if team_errors:
            block_decision("PILOTHOS PRE-EDIT: invalid team contract: " + "; ".join(team_errors))
            return
        permissions = team_contract.get("role_permissions", {})
        actions = permissions.get(role)
        if not isinstance(actions, list):
            block_decision(f"PILOTHOS PRE-EDIT: role is not in team contract: {role}")
            return
        if "edit" not in actions:
            block_decision(f"PILOTHOS PRE-EDIT: role {role} does not have edit permission.")
            return
        for rel in paths:
            if not path_matches(team_contract.get("allowed_paths", []), rel):
                block_decision(
                    f"PILOTHOS PRE-EDIT: team role {role} cannot edit outside team allowed_paths "
                    f"from {team_contract_path}: {rel}"
                )
                return
    allowed = contract.get("allowed_paths", [])
    out_of_scope = contract.get("out_of_scope_paths", [])
    for rel in paths:
        if path_matches(out_of_scope, rel):
            block_decision(f"PILOTHOS PRE-EDIT: {rel} is declared out of scope.")
            return
        if not path_matches(allowed, rel):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} is outside allowed_paths from "
                f"{contract_path}. allowed_paths={allowed}"
            )
            return
        if contract_docs_tests_only(contract) and rel.startswith("pilothOS/"):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} touches pilothOS core while the "
                "contract only declares Docs/Tests layers."
            )
            return
        if is_sensitive_runtime_path(rel) and not contract_has_layer(contract, RUNTIME_TOOL_LAYERS):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} is a sensitive runtime/tool file. "
                "Declare affected_layers with Tools/Runtime or Installer before editing it."
            )
            return
        if rel.startswith("adapters/") and not contract_has_layer(contract, ADAPTER_LAYERS):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} is an adapter path but affected_layers "
                "does not declare Adapters/Tools."
            )
            return
        if rel.startswith("adapters/") and contract_has_layer(contract, {"rules", "hooks"}):
            has_rule_source = any(
                path_matches(contract.get("allowed_paths", []), candidate)
                for candidate in (
                    "pilothOS/rules/index.md",
                    "pilothOS/rules/hooks.md",
                    "pilothOS/rules/coding-behavior.md",
                    "pilothOS/rules/evidence.md",
                    "pilothOS/rules/layer-boundary.md",
                )
            )
            if not has_rule_source:
                block_decision(
                    "PILOTHOS PRE-EDIT: adapter policy changes must be paired with "
                    "the pilothOS/rules source of truth in allowed_paths, otherwise "
                    "the adapter is likely replacing policy instead of bridging it."
                )
                return
        if (preset_requires_standard_evidence(contract)
                and is_ui_path(rel)
                and not contract_has_ui_design_system_evidence(contract)):
            block_decision(
                f"PILOTHOS PRE-EDIT: {rel} looks like a UI file. "
                "Add ui_design_system_evidence with source, checked, decision, "
                "and reason before editing UI paths."
            )
            return


def git_numstat(rel):
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff", "--numstat", "--", rel],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        if out.stdout.strip():
            first = out.stdout.strip().splitlines()[0].split()
            add = 0 if first[0] == "-" else int(first[0])
            delete = 0 if first[1] == "-" else int(first[1])
            return add, delete
        untracked = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--others",
             "--exclude-standard", "--", rel],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        if untracked.stdout.strip():
            p = REPO_ROOT / rel
            if p.exists() and p.is_file():
                return len(p.read_text(encoding="utf-8", errors="replace").splitlines()), 0
    except Exception:
        pass
    return 0, 0


def post_edit(hook_input):
    paths, path_errors = edit_paths_from_hook_input(hook_input)
    facts = load_diff_facts(hook_input)
    warnings = facts.setdefault("warnings", [])
    for err in path_errors:
        warnings.append(err)
    contract, _ = load_task_contract(hook_input)
    if not paths:
        warnings.append("post-edit hook did not include a target path")
        update_diff_fact_derived(facts, contract)
        save_diff_facts(hook_input, facts)
        print(json.dumps({"result": "diff_facts_recorded", "warnings": warnings[-1:]},
                         ensure_ascii=False))
        return
    changed = facts.setdefault("changed_files", {})
    for rel in paths:
        add, delete = git_numstat(rel)
        layer = layer_for_path(rel)
        changed[rel] = {"layer": layer, "added": add, "deleted": delete,
                        "changed_lines": add + delete,
                        "new_file": git_path_is_new(rel)}
    # Prune entry không còn trong working tree (đã commit hoặc revert) để diff facts
    # phản ánh delta CHƯA commit hiện tại, không tích luỹ snapshot cũ qua nhiều edit.
    # Chỉ prune khi thực sự trong git repo — ngoài git, git_changed_file_paths()
    # trả rỗng một cách mập mờ và sẽ xoá nhầm toàn bộ facts.
    if is_git_repo():
        live = set(git_changed_file_paths())
        for rel in list(changed):
            if rel not in live:
                del changed[rel]
    update_diff_fact_derived(facts, contract)
    save_diff_facts(hook_input, facts)
    print(json.dumps({
        "result": "diff_facts_recorded",
        "changed_files": changed,
        "affected_layers": facts["affected_layers"],
        "has_tests": facts["has_tests"],
        "has_docs": facts["has_docs"],
        "new_files": facts.get("new_files", []),
        "new_files_count": facts.get("new_files_count", 0),
        "total_added": facts.get("total_added", 0),
        "total_deleted": facts.get("total_deleted", 0),
        "largest_file_delta": facts.get("largest_file_delta", {}),
        "dependency_files_changed": facts.get("dependency_files_changed", []),
        "ui_files_changed": facts.get("ui_files_changed", []),
        "test_files_changed": facts.get("test_files_changed", []),
        "docs_files_changed": facts.get("docs_files_changed", []),
        "component_like_files_changed": facts.get("component_like_files_changed", []),
        "warnings": facts.get("warnings", []),
        "evidence_commands": facts.get("evidence_commands", []),
    }, ensure_ascii=False))


def evidence_add(argv):
    if not argv:
        print("FAIL evidence-add: need command string")
        return
    facts = load_diff_facts({})
    entry = {
        "command": argv[0],
        "result": argv[1] if len(argv) > 1 else "recorded",
        "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    facts.setdefault("evidence_commands", []).append(entry)
    contract, _ = load_task_contract({})
    update_diff_fact_derived(facts, contract)
    save_diff_facts({}, facts)
    print(f"OK   evidence recorded: {entry['command']} -> {entry['result']}")


def facts_paths(facts, receipt=None):
    paths = set((facts or {}).get("changed_files", {}))
    if isinstance(receipt, dict):
        changed = receipt.get("changed_files")
        if isinstance(changed, list):
            paths |= {p for p in changed if isinstance(p, str)}
    return paths


def validate_receipt_scope_against_contract(receipt, contract, facts):
    errors = []
    if not isinstance(contract, dict):
        return errors
    allowed = contract.get("allowed_paths")
    out_of_scope = contract.get("out_of_scope_paths") or []
    if not isinstance(allowed, list) or not allowed:
        return errors
    for raw_path in sorted(facts_paths(facts, receipt)):
        rel, reason = repo_relative_path(raw_path)
        if rel is None:
            errors.append(f"receipt changed path invalid: {raw_path} ({reason})")
            continue
        if isinstance(out_of_scope, list) and path_matches(out_of_scope, rel):
            errors.append(f"receipt changed path is out_of_scope: {rel}")
        elif not path_matches(allowed, rel):
            errors.append(f"receipt changed path is outside allowed_paths: {rel}")
    return errors


def receipt_requires_reuse_discipline(facts, receipt, contract=None):
    if not preset_requires_standard_evidence(contract, receipt):
        return False
    paths = facts_paths(facts, receipt)
    if not paths:
        return False
    for rel in paths:
        layer = layer_for_path(rel)
        if normalize_layer(layer) not in DOC_TEST_LAYERS:
            return True
    return False


def validate_receipt_delivery_story(receipt):
    errors = []
    if not non_empty_string(receipt.get("scope_evidence")):
        errors.append("scope_evidence is required for code/UI/runtime/rules/adapter changes")
    errors.extend(validate_object_list(
        receipt.get("context_used"),
        "context_used",
        RECEIPT_CONTEXT_FIELDS,
    ))
    errors.extend(validate_asset_routing(receipt.get("consumer_asset_routing")))
    errors.extend(validate_learning_review(receipt.get("learning_review")))
    gates = receipt.get("quality_gates")
    if not isinstance(gates, dict):
        errors.append("quality_gates must be an object")
    else:
        reuse_gate = gates.get("reuse_non_duplication")
        if not isinstance(reuse_gate, dict):
            errors.append("quality_gates.reuse_non_duplication must be an object")
        else:
            result = reuse_gate.get("result")
            if result not in QUALITY_GATE_RESULTS:
                errors.append("quality_gates.reuse_non_duplication.result must be PASS, FAIL, or NOT_APPLICABLE")
            if not non_empty_string(reuse_gate.get("evidence")):
                errors.append("quality_gates.reuse_non_duplication.evidence must be a non-empty string")
            delivery_result = str(receipt.get("result", "")).strip().lower()
            if result == "FAIL" and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
                errors.append(
                    "quality_gates.reuse_non_duplication.result cannot be FAIL when receipt result is successful"
                )
            if result == "FAIL" and not non_empty_string(receipt.get("limitation")):
                errors.append("limitation is required when quality_gates.reuse_non_duplication.result is FAIL")
    return errors


def validate_learning_review(value):
    errors = validate_string_object(value, "learning_review", LEARNING_REVIEW_FIELDS)
    if errors:
        return errors
    mistake = str(value.get("mistake_checked", "")).strip()
    decision = str(value.get("lesson_decision", "")).strip()
    promoted_to = str(value.get("promoted_to", "")).strip()
    if mistake not in LEARNING_MISTAKE_CLASSES:
        errors.append(
            "learning_review.mistake_checked must be one of: "
            + ", ".join(sorted(LEARNING_MISTAKE_CLASSES))
        )
    if decision not in LEARNING_DECISIONS:
        errors.append(
            "learning_review.lesson_decision must be one of: "
            + ", ".join(sorted(LEARNING_DECISIONS))
        )
    if mistake == "none" and decision in LEARNING_DECISIONS and decision != "none":
        errors.append(
            "learning_review.lesson_decision must be none when mistake_checked is none"
        )
    if mistake != "none" and mistake in LEARNING_MISTAKE_CLASSES and decision == "none":
        errors.append(
            "learning_review.lesson_decision must not be none when mistake_checked is not none"
        )
    if not learning_promotion_target_valid(promoted_to):
        errors.append(
            "learning_review.promoted_to must be one of: "
            + ", ".join(sorted(LEARNING_PROMOTION_TARGETS))
            + " (or '<target>, upstream' for cross-project lessons)"
        )
    if decision == "promoted" and promoted_to == "not_applicable":
        errors.append(
            "learning_review.promoted_to must name a promotion target when lesson_decision is promoted"
        )
    if decision == "none" and promoted_to != "not_applicable":
        errors.append(
            "learning_review.promoted_to must be not_applicable when lesson_decision is none"
        )
    return errors


def learning_promotion_target_valid(value):
    if not non_empty_string(value):
        return False
    target = value.strip()
    if target in LEARNING_PROMOTION_TARGETS:
        return True
    parts = [
        part.strip()
        for part in re.split(r"[,+]", target)
        if part.strip()
    ]
    if len(parts) < 2 or "upstream" not in parts:
        return False
    base_targets = set(LEARNING_PROMOTION_TARGETS) - {"not_applicable"}
    return all(part in base_targets or part in LEARNING_PROMOTION_MARKERS for part in parts)


def receipt_touches_ui(facts, receipt):
    paths = facts_paths(facts, receipt)
    return any(is_ui_path(p) for p in paths)


def current_ds_candidates_for_receipt(facts, receipt, contract=None):
    paths = sorted(facts_paths(facts, receipt))
    if not paths:
        return []
    allowed = ["**/*"]
    if isinstance(contract, dict) and isinstance(contract.get("allowed_paths"), list):
        allowed = contract.get("allowed_paths")
    # A UI receipt should inspect the repo's DS assets, not only the changed
    # file. Use broad but deterministic local patterns.
    scan = ds_scan_payload({
        "task_signal": "UI/component",
        "changed_paths": paths,
        "allowed_paths": allowed + [
            "components/**", "src/components/**", "ui/**", "src/ui/**",
            "tokens/**", "src/tokens/**", "pilothOS/rules/**", "docs/**",
            "tailwind.config.*", "**/*.css",
        ],
    })
    return (
        scan.get("component_candidates", [])
        + scan.get("token_candidates", [])
        + scan.get("pattern_candidates", [])
    )


def validate_design_system_candidate_review(receipt, facts, contract=None):
    errors = validate_candidate_review(
        receipt,
        ("design_system_candidates", "ds_scan", "design_system_scan"),
        "design_system_candidate_review",
    )
    if errors:
        return errors
    if not receipt_touches_ui(facts, receipt):
        return errors
    if "design_system_candidate_review" in receipt:
        _, review_errors = review_items(
            receipt.get("design_system_candidate_review"),
            "design_system_candidate_review",
        )
        errors.extend(review_errors)
        return errors
    if current_ds_candidates_for_receipt(facts, receipt, contract):
        errors.append(
            "design_system_candidate_review is required when UI files changed and design-system candidates exist"
        )
    return errors


def validate_string_object(value, field, required_keys):
    errors = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    for key in required_keys:
        if not non_empty_string(value.get(key)):
            errors.append(f"{field}.{key} must be a non-empty string")
    return errors


def dependency_reason_present(receipt):
    if non_empty_string(receipt.get("dependency_change_reason")):
        return True
    checklist = receipt.get("warning_checklist")
    return isinstance(checklist, dict) and non_empty_string(checklist.get("dependency_change_reason"))


def checklist_value_present(receipt, key):
    if non_empty_string(receipt.get(key)):
        return True
    checklist = receipt.get("warning_checklist")
    return isinstance(checklist, dict) and non_empty_string(checklist.get(key))


def validate_warning_checklist(receipt, facts):
    errors = []
    warnings = [str(w) for w in facts.get("warnings", [])]
    for prefix, key in WARNING_CHECKLIST_RULES:
        if any(w.startswith(prefix) for w in warnings):
            if not checklist_value_present(receipt, key):
                errors.append(f"warning_checklist.{key} is required for warning: {prefix}")
    return errors


def command_is_read_only_guard(command):
    if not isinstance(command, str):
        return False
    if SHELL_CONTROL_RE.search(command):
        return False
    try:
        parts = shlex.split(command.strip())
    except ValueError:
        return False
    while parts and ENV_ASSIGNMENT_RE.fullmatch(parts[0]):
        name, _, _ = parts[0].partition("=")
        assignment_text = parts[0].lower()
        if name not in SAFE_READ_ONLY_GUARD_ENV_VARS:
            return False
        if any(re.search(pattern, assignment_text) for pattern in HIGH_RISK_COMMAND_PATTERNS):
            return False
        parts = parts[1:]
    if len(parts) < 3:
        return False
    executable = pathlib.PurePosixPath(parts[0].replace("\\", "/")).name
    if executable not in {"python", "python3"}:
        return False
    if not parts[1].endswith("pilothOS/scripts/pilothos_guard.py"):
        return False
    mode = parts[2]
    if mode not in READ_ONLY_GUARD_MODES:
        return False
    trailing_args = parts[3:]
    trailing_text = " ".join(trailing_args).lower()
    if any(re.search(pattern, trailing_text) for pattern in HIGH_RISK_COMMAND_PATTERNS):
        return False
    if mode == "receipt-verify":
        return "--record" not in trailing_args
    return True


def command_looks_high_risk(command):
    if not isinstance(command, str):
        return False
    if command_is_read_only_guard(command):
        return False
    lowered = command.lower()
    return any(re.search(pattern, lowered) for pattern in HIGH_RISK_COMMAND_PATTERNS)


def receipt_has_approval_evidence(receipt):
    if non_empty_string(receipt.get("approval_evidence")):
        return True
    checklist = receipt.get("warning_checklist")
    if isinstance(checklist, dict) and non_empty_string(checklist.get("approval_evidence")):
        return True
    tool_uses = receipt.get("tool_uses")
    if isinstance(tool_uses, list):
        return any(
            isinstance(item, dict) and non_empty_string(item.get("approval_evidence"))
            for item in tool_uses
        )
    return False


def entitlement_list(value, field):
    if value is None:
        return [], []
    raw_items = value if isinstance(value, list) else [value]
    if not raw_items:
        return [], [f"{field} must not be empty when present"]
    entitlements, errors = [], []
    for i, item in enumerate(raw_items):
        if not non_empty_string(item):
            errors.append(f"{field}[{i}] must be a non-empty string")
            continue
        entitlement = str(item).strip()
        if not ENTITLEMENT_RE.fullmatch(entitlement):
            errors.append(f"{field}[{i}] has invalid entitlement name: {entitlement}")
        elif entitlement not in entitlements:
            entitlements.append(entitlement)
    return entitlements, errors


def payload_entitlements(payload):
    if not isinstance(payload, dict):
        return [], []
    if "entitlements" in payload:
        return entitlement_list(payload.get("entitlements"), "entitlements")
    if "entitlement" in payload:
        return entitlement_list(payload.get("entitlement"), "entitlement")
    return [], []


def contract_allowed_entitlements(contract):
    if not isinstance(contract, dict):
        return set(), []
    allowed, errors = entitlement_list(
        contract.get("allowed_entitlements", contract.get("entitlements")),
        "allowed_entitlements",
    )
    return set(allowed), errors


def validate_payload_entitlements(payload, contract, field):
    entitlements, errors = payload_entitlements(payload)
    allowed, allowed_errors = contract_allowed_entitlements(contract)
    errors.extend(allowed_errors)
    if entitlements and not allowed:
        errors.append(f"{field} entitlements require active contract allowed_entitlements")
    for entitlement in entitlements:
        if allowed and entitlement not in allowed:
            errors.append(f"{field} entitlement not allowed by active contract: {entitlement}")
    return errors


def result_needs_limitation(result):
    if not isinstance(result, str):
        return False
    lowered = result.lower()
    return any(token in lowered for token in ("not run", "not_run", "skipped", "blocked", "failed", "unable"))


def valid_timeout_value(value):
    if not non_empty_string(value):
        return False
    return bool(re.fullmatch(r"[1-9][0-9]*(ms|s|m|h)", value.strip()))


def validate_tool_uses(receipt, facts, contract=None):
    errors = []
    tool_uses = receipt.get("tool_uses")
    if tool_uses is not None:
        if not isinstance(tool_uses, list):
            errors.append("tool_uses must be a list of objects")
        elif not tool_uses:
            errors.append("tool_uses must not be empty when present")
        else:
            for i, item in enumerate(tool_uses):
                if not isinstance(item, dict):
                    errors.append(f"tool_uses[{i}] must be an object")
                    continue
                for key in TOOL_USE_REQUIRED_FIELDS:
                    if not non_empty_string(item.get(key)):
                        errors.append(f"tool_uses[{i}].{key} must be a non-empty string")
                if non_empty_string(item.get("timeout")) and not valid_timeout_value(item.get("timeout")):
                    errors.append(f"tool_uses[{i}].timeout must be a duration like 30s, 5m, 1h, or 500ms")
                risk = str(item.get("risk", "")).strip().lower()
                if risk and risk not in {"low", "medium", "high"}:
                    errors.append(f"tool_uses[{i}].risk must be low, medium, or high")
                command = item.get("command")
                high_risk = risk == "high" or command_looks_high_risk(command)
                if command_looks_high_risk(command) and risk != "high":
                    errors.append(f"tool_uses[{i}].risk must be high for high-risk command")
                if high_risk and not (non_empty_string(item.get("approval_evidence")) or receipt_has_approval_evidence(receipt)):
                    errors.append(f"tool_uses[{i}].approval_evidence is required for high-risk tool use")
                errors.extend(validate_payload_entitlements(item, contract, f"tool_uses[{i}]"))
                if result_needs_limitation(item.get("result")) and not (
                        non_empty_string(item.get("limitation")) or non_empty_string(receipt.get("limitation"))):
                    errors.append(f"tool_uses[{i}].limitation is required when tool result was not cleanly successful")
                match_payload = {
                    "tool": item.get("tool"),
                    "command": item.get("command"),
                    "expected_evidence": item.get("evidence_output"),
                }
                if not tool_check_matches_contract(match_payload, contract, receipt):
                    errors.append(
                        f"tool_uses[{i}] must be referenced by active task contract"
                    )

    high_risk_evidence = [
        entry.get("command")
        for entry in facts.get("evidence_commands", [])
        if isinstance(entry, dict) and command_looks_high_risk(entry.get("command"))
    ]
    if command_looks_high_risk(receipt.get("verification_command")):
        high_risk_evidence.append(receipt.get("verification_command"))
    if high_risk_evidence and not receipt_has_approval_evidence(receipt):
        errors.append(
            "approval_evidence is required for high-risk tool/command evidence: "
            + "; ".join(str(x) for x in high_risk_evidence if x)
        )
    return errors


def contract_tool_text(contract):
    if not isinstance(contract, dict):
        return ""
    parts = []

    def collect(value):
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)

    for key in (
        "task_scope",
        "consumer_scope",
        "expected_evidence",
        "context_evidence",
        "reuse_evidence",
        "consumer_asset_routing",
        "ui_design_system_evidence",
    ):
        collect(contract.get(key))
    return "\n".join(parts).lower()


def tool_check_matches_contract(payload, contract, *configs):
    if not isinstance(contract, dict):
        return not preset_requires_standard_evidence(contract, *configs)
    if not preset_requires_standard_evidence(contract, *configs):
        return True
    haystack = contract_tool_text(contract)
    if not haystack:
        return False
    identifiers = [
        payload.get("tool"),
        payload.get("command"),
        payload.get("expected_evidence"),
    ]
    for raw in identifiers:
        if not non_empty_string(raw):
            continue
        needle = raw.strip().lower()
        if needle in haystack or haystack in needle:
            return True
    return False


def validate_tool_check_payload(payload, contract=None):
    errors = []
    if not isinstance(payload, dict):
        return ["tool check payload must be a JSON object"]
    for key in TOOL_CHECK_REQUIRED_FIELDS:
        if not non_empty_string(payload.get(key)):
            errors.append(f"{key} must be a non-empty string")
    if non_empty_string(payload.get("timeout")) and not valid_timeout_value(payload.get("timeout")):
        errors.append("timeout must be a duration like 30s, 5m, 1h, or 500ms")
    risk = str(payload.get("risk", "")).strip().lower()
    if risk and risk not in {"low", "medium", "high"}:
        errors.append("risk must be low, medium, or high")
    command = payload.get("command")
    high_risk = risk == "high" or command_looks_high_risk(command)
    if command_looks_high_risk(command) and risk != "high":
        errors.append("risk must be high for high-risk command")
    if high_risk and not non_empty_string(payload.get("approval_evidence")):
        errors.append("approval_evidence is required before high-risk tool use")
    errors.extend(validate_payload_entitlements(payload, contract, "tool-check"))
    if not errors and not tool_check_matches_contract(payload, contract):
        errors.append(
            "tool-check command/evidence must be referenced by active task contract"
        )
    return errors


def tool_check(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "tool-check")
    except Exception as e:
        print(f"FAIL tool-check: {e}")
        return
    contract, _ = load_task_contract({})
    errors = validate_tool_check_payload(payload, contract)
    if errors:
        block_decision("PILOTHOS TOOL CHECK: " + "; ".join(errors))
        return
    print("OK   tool check passed")


def receipt_needs_judgment(contract, facts, receipt):
    if contract and contract.get("requires_judgment"):
        return True
    layers = {normalize_layer(x) for x in (receipt.get("affected_layers") or [])}
    layers |= {normalize_layer(x) for x in facts.get("affected_layers", [])}
    if layers & JUDGMENT_LAYERS:
        return True
    for rel in facts.get("changed_files", {}):
        if rel.startswith(("pilothOS/rules/", "pilothOS/runtime/", "adapters/")):
            return True
    return False


def validate_deliver_receipt(receipt, contract, facts):
    errors = []
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]
    preset = operational_preset(contract, receipt)
    if not valid_operational_preset(preset):
        errors.append("operational_preset must be light, standard, or strict")
    update_diff_fact_derived(facts, contract)
    missing = sorted(RECEIPT_REQUIRED_FIELDS - set(receipt))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    for field in ("changed_files", "affected_layers"):
        value = receipt.get(field)
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
            errors.append(f"{field} must be a non-empty list of strings")
    command = receipt.get("verification_command")
    result = receipt.get("result")
    if not isinstance(command, str) or not command.strip():
        errors.append("verification_command must be a non-empty string")
    if not isinstance(result, str) or not result.strip():
        errors.append("result must be a non-empty string")
    lowered = f"{command} {result}".lower() if isinstance(command, str) and isinstance(result, str) else ""
    if any(token in lowered for token in ("not run", "not_run", "skipped", "blocked", "failed", "unable")):
        if not isinstance(receipt.get("limitation"), str) or not receipt.get("limitation", "").strip():
            errors.append("limitation is required when verification was not cleanly successful")
        if preset == "strict":
            errors.append("strict preset requires clean verification; not run/skipped/blocked/failed/unable is not accepted")
    fact_files = set(facts.get("changed_files", {}))
    receipt_files = set(receipt.get("changed_files") or [])
    missing_files = sorted(fact_files - receipt_files)
    if missing_files:
        errors.append(f"receipt missing changed_files from diff facts: {', '.join(missing_files)}")
    fact_layers = {normalize_layer(v.get("layer")) for v in facts.get("changed_files", {}).values()}
    receipt_layers = {normalize_layer(v) for v in (receipt.get("affected_layers") or [])}
    missing_layers = sorted(x for x in fact_layers - receipt_layers if x)
    if missing_layers:
        errors.append(f"receipt missing affected_layers from diff facts: {', '.join(missing_layers)}")
    errors.extend(validate_receipt_scope_against_contract(receipt, contract, facts))
    if preset_requires_standard_evidence(contract, receipt) and receipt_needs_judgment(contract, facts, receipt):
        checklist = receipt.get("judgment_checklist")
        if not isinstance(checklist, dict):
            errors.append("judgment_checklist is required for judgment-sensitive changes")
        else:
            for key, question in JUDGMENT_CHECKLIST_KEYS.items():
                value = checklist.get(key)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"judgment_checklist.{key} missing answer: {question}")
    if receipt_requires_reuse_discipline(facts, receipt, contract):
        errors.extend(validate_receipt_delivery_story(receipt))
        errors.extend(validate_string_object(
            receipt.get("reuse_discipline"),
            "reuse_discipline",
            REUSE_DISCIPLINE_FIELDS,
        ))
    errors.extend(validate_candidate_review(
        receipt,
        ("semantic_reuse_candidates", "reuse_scan", "semantic_reuse_scan"),
        "semantic_reuse_review",
    ))
    if preset_requires_standard_evidence(contract, receipt) and receipt_touches_ui(facts, receipt):
        if not contract_has_ui_design_system_evidence(contract):
            errors.append(
                "ui_design_system_evidence is required in the task contract when UI files changed"
            )
        for field in UI_RECEIPT_FIELDS:
            if not non_empty_string(receipt.get(field)):
                errors.append(f"{field} is required when UI files changed")
        errors.extend(validate_design_system_candidate_review(receipt, facts, contract))
    dependency_files = set(facts.get("dependency_files_changed") or [])
    dependency_files |= {p for p in (receipt.get("changed_files") or []) if is_dependency_path(p)}
    if preset_requires_standard_evidence(contract, receipt) and dependency_files and not dependency_reason_present(receipt):
        errors.append(
            "warning_checklist.dependency_change_reason is required when dependency files changed"
        )
    if preset_requires_standard_evidence(contract, receipt):
        errors.extend(validate_warning_checklist(receipt, facts))
    errors.extend(validate_tool_uses(receipt, facts, contract))
    return errors


def receipt_write(argv):
    try:
        receipt, _ = json_arg_or_stdin(argv, "receipt-write")
    except Exception as e:
        print(f"FAIL receipt-write: {e}")
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    errors = validate_deliver_receipt(receipt, contract, facts)
    if errors:
        print(json.dumps({"result": "receipt_rejected", "errors": errors},
                         ensure_ascii=False, indent=2))
        return
    MARKER_DIR.mkdir(exist_ok=True)
    receipt = dict(receipt)
    receipt["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    repo_state_file("deliver-receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK   deliver receipt recorded: {repo_state_file('deliver-receipt.json')}")


def latest_receipt_seal_hash():
    record = latest_receipt_seal_record()
    return record.get("seal_sha256", "") if record else ""


def latest_receipt_seal_record():
    if not RECEIPT_SEALS.exists():
        return None
    latest = None
    try:
        with open(RECEIPT_SEALS, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("repo_key") == REPO_KEY and non_empty_string(item.get("seal_sha256")):
                    latest = item
    except (OSError, json.JSONDecodeError):
        return None
    return latest


def file_hash_entry(raw_path):
    rel, err = repo_relative_path(raw_path)
    if err:
        return {"path": str(raw_path), "status": "invalid", "reason": err}
    path = REPO_ROOT / rel
    if not path.exists():
        return {"path": rel, "status": "missing"}
    if not path.is_file():
        return {"path": rel, "status": "not_file"}
    try:
        data = path.read_bytes()
    except OSError as e:
        return {"path": rel, "status": "failed", "reason": str(e)}
    return {
        "path": rel,
        "status": "sealed",
        "bytes": len(data),
        "sha256": sha256_bytes(data),
    }


def load_receipt_for_seal(argv, label):
    if argv:
        return json_arg_or_stdin(argv, label)
    receipt, path = load_deliver_receipt({})
    if receipt is None:
        raise ValueError(f"{label}: missing active deliver receipt")
    return receipt, path


def build_receipt_seal(receipt, contract, facts, previous_seal_sha256=""):
    changed = sorted(
        p for p in (receipt.get("changed_files") or [])
        if isinstance(p, str) and p.strip()
    )
    payload = {
        "schema_version": 1,
        "repo_key": REPO_KEY,
        "receipt_sha256": sha256_json(receipt),
        "contract_sha256": sha256_json(contract or {}),
        "diff_facts_sha256": sha256_json({
            "affected_layers": facts.get("affected_layers", []),
            "changed_files": facts.get("changed_files", {}),
            "evidence_commands": facts.get("evidence_commands", []),
            "warnings": facts.get("warnings", []),
        }),
        "changed_files": [file_hash_entry(path) for path in changed],
        "previous_seal_sha256": previous_seal_sha256 or "",
        "limits": [
            "sha256 seal only; not cryptographic code signing",
            "verify against the same repo checkout and active receipt state",
        ],
    }
    payload["seal_sha256"] = sha256_json(payload)
    return payload


def receipt_seal(argv):
    args = list(argv)
    record = False
    if "--record" in args:
        args.remove("--record")
        record = True
    try:
        receipt, _ = load_receipt_for_seal(args, "receipt-seal")
    except Exception as e:
        json_print({"result": "receipt_seal_rejected", "errors": [str(e)]})
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    previous = latest_receipt_seal_hash() if record else ""
    seal = build_receipt_seal(receipt, contract, facts, previous)
    seal["result"] = "receipt_sealed"
    if record:
        RECEIPT_SEALS.parent.mkdir(parents=True, exist_ok=True)
        with open(RECEIPT_SEALS, "a", encoding="utf-8") as f:
            f.write(json.dumps(seal, ensure_ascii=False, sort_keys=True) + "\n")
        seal["recorded_to"] = RECEIPT_SEALS.relative_to(REPO_ROOT).as_posix()
    json_print(seal)


def receipt_verify(argv):
    try:
        expected, _ = json_arg_or_stdin(argv, "receipt-verify")
    except Exception as e:
        json_print({"result": "receipt_verify_rejected", "errors": [str(e)]})
        return
    if not isinstance(expected, dict):
        json_print({"result": "receipt_verify_rejected", "errors": ["seal must be a JSON object"]})
        return
    receipt, _ = load_deliver_receipt({})
    if receipt is None:
        json_print({"result": "receipt_verify_failed", "errors": ["missing active deliver receipt"]})
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    current = build_receipt_seal(receipt, contract, facts, expected.get("previous_seal_sha256", ""))
    comparisons = {
        "receipt_sha256": current.get("receipt_sha256") == expected.get("receipt_sha256"),
        "contract_sha256": current.get("contract_sha256") == expected.get("contract_sha256"),
        "diff_facts_sha256": current.get("diff_facts_sha256") == expected.get("diff_facts_sha256"),
        "changed_files": current.get("changed_files") == expected.get("changed_files"),
        "seal_sha256": current.get("seal_sha256") == expected.get("seal_sha256"),
    }
    errors = [name for name, ok in comparisons.items() if not ok]
    json_print({
        "result": "receipt_verify_passed" if not errors else "receipt_verify_failed",
        "comparisons": comparisons,
        "errors": errors,
        "current_seal_sha256": current.get("seal_sha256"),
        "expected_seal_sha256": expected.get("seal_sha256"),
    })


def receipt_template():
    """Emit a gate-aware receipt skeleton.

    Instead of a static superset of every field os-close *might* demand, this
    reads the active contract + diff facts and emits ONLY the fields the current
    run actually needs, with valid default enum values (not `<placeholder>`) so
    the skeleton passes `os-close --dry-run` structurally — the human only fills
    real evidence. Allowed enum values are shown in a trailing `_allowed` hint.
    """
    facts = load_diff_facts({})
    contract, _ = load_task_contract({})
    update_diff_fact_derived(facts, contract)
    probe = {}  # proxy receipt so gate predicates can read paths from facts
    mode = contract.get("mode") if isinstance(contract, dict) else None
    required_gates = required_gates_for_task(contract, mode=mode)
    std_evidence = preset_requires_standard_evidence(contract)
    needs_reuse = receipt_requires_reuse_discipline(facts, probe, contract)
    touches_ui = receipt_touches_ui(facts, probe)
    needs_judgment = std_evidence and receipt_needs_judgment(contract, facts, probe)

    template = {
        "operational_preset": operational_preset(contract),
        "changed_files": sorted(facts.get("changed_files", {})),
        "affected_layers": facts.get("affected_layers", []),
        "verification_command": "<command or 'not run'>",
        "result": "passed",
        "limitation": "<required only if result is not run/failed/skipped>",
        "quality_gates": {
            gate: {"result": "PASS", "evidence": f"<evidence proving {gate}>"}
            for gate in required_gates
        },
        "claims": [
            {"claim": "<what you did, no absolute 1:1/complete/fully claims unless evidence backs it>",
             "evidence_refs": ["<os-evidence id>", "quality_gates.correctness"]}
        ],
    }

    if needs_judgment:
        template["judgment_checklist"] = dict(JUDGMENT_CHECKLIST_KEYS)

    # Enum hints live in one top-level block (validators ignore unknown keys);
    # delete `_allowed_values` before the real close if you want a clean seal.
    allowed = {}

    if needs_reuse:
        template["scope_evidence"] = "<why these changes were in scope>"
        template["context_used"] = [
            {"source": "<path-or-command>", "reason": "<why loaded>", "finding": "<what it proved>"}
        ]
        template["consumer_asset_routing"] = [
            {
                "task_signal": "not_applicable",
                "asset_type": "not_applicable",
                "decision": "not_applicable",
                "reason": "<why the exact asset was loaded, or why not applicable>",
            }
        ]
        template["reuse_discipline"] = {
            "existing_code_checked": "<paths/searches checked>",
            "existing_component_checked": "<component/design-system check or not_applicable>",
            "existing_pattern_followed": "<pattern reused>",
            "new_code_reason": "<why new code was needed>",
            "duplicate_risk": "<duplicate risk assessment>",
            "kiss_dry_rationale": "<why this stayed simple/non-duplicative>",
        }
        template["learning_review"] = {
            "mistake_checked": "none",
            "lesson_decision": "none",
            "promoted_to": "not_applicable",
            "reason": "<why no lesson was needed, or where it was recorded/promoted>",
        }
        allowed["consumer_asset_routing[].task_signal"] = sorted(ASSET_ROUTING_SIGNALS)
        allowed["consumer_asset_routing[].asset_type"] = sorted(ASSET_ROUTING_TYPES)
        allowed["consumer_asset_routing[].decision"] = sorted(ASSET_ROUTING_DECISIONS)
        allowed["learning_review.mistake_checked"] = sorted(LEARNING_MISTAKE_CLASSES)
        allowed["learning_review.lesson_decision"] = sorted(LEARNING_DECISIONS)
        allowed["learning_review.promoted_to"] = sorted(LEARNING_PROMOTION_TARGETS) + ["<target>, upstream"]

    if touches_ui and std_evidence:
        template["design_system_checked"] = "<existing DS/tokens checked; result>"
        template["component_reuse_decision"] = "not_applicable"
        template["token_reuse_decision"] = "not_applicable"
        template["design_system_candidate_review"] = [
            {"candidate": "all", "decision": "not_applicable", "reason": "<decision reason>"}
        ]
        allowed["component_reuse_decision / token_reuse_decision / design_system_candidate_review[].decision"] = sorted(UI_DESIGN_SYSTEM_DECISIONS)

    if allowed:
        template["_allowed_values"] = allowed

    print(json.dumps(template, ensure_ascii=False, indent=2))


