# --------------------------------------------------------------- team v5

def team_definition_path(team):
    return PILOTHOS_DIR / "agent-teams" / f"{stable_slug(team)}.md"


def validate_team_contract(contract):
    errors = []
    if not isinstance(contract, dict):
        return ["team contract must be a JSON object"]
    required = {
        "task_id", "team", "roles", "allowed_paths", "role_permissions",
        "handoff_artifacts", "stop_condition", "max_repair_loops",
        "expected_evidence",
    }
    missing = sorted(required - set(contract))
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))
    for field in ("task_id", "team", "stop_condition"):
        if not non_empty_string(contract.get(field)):
            errors.append(f"{field} must be a non-empty string")
    for field in ("roles", "allowed_paths", "handoff_artifacts", "expected_evidence"):
        value = contract.get(field)
        if not isinstance(value, list) or not value or any(not non_empty_string(x) for x in value):
            errors.append(f"{field} must be a non-empty list of strings")
    if isinstance(contract.get("allowed_paths"), list):
        for pattern in contract.get("allowed_paths", []):
            if not path_pattern_is_safe(pattern):
                errors.append(f"allowed_paths contains unsafe pattern: {pattern}")
    try:
        loops = int(contract.get("max_repair_loops"))
        if loops < 0:
            errors.append("max_repair_loops must be >= 0")
    except (TypeError, ValueError):
        errors.append("max_repair_loops must be an integer")
    team_path = team_definition_path(contract.get("team", ""))
    if non_empty_string(contract.get("team")) and not team_path.exists():
        errors.append(f"team definition missing: {team_path.relative_to(REPO_ROOT).as_posix()}")
    permissions = contract.get("role_permissions")
    roles = set(contract.get("roles") or [])
    if not isinstance(permissions, dict) or not permissions:
        errors.append("role_permissions must be a non-empty object")
    else:
        for role in roles:
            actions = permissions.get(role)
            if not isinstance(actions, list) or not actions or any(action not in TEAM_PERMISSION_ACTIONS for action in actions):
                errors.append(
                    f"role_permissions.{role} must list actions from: "
                    + ", ".join(sorted(TEAM_PERMISSION_ACTIONS))
                )
    return errors


def team_contract_state_path(task_id):
    return TEAM_RUNS_DIR / safe_task_id(task_id) / "team-contract.json"


def team_receipt_state_path(task_id):
    return TEAM_RUNS_DIR / safe_task_id(task_id) / "team-receipt.json"


def load_team_contract(hook_input=None):
    env_path = env_state_path("PILOTHOS_TEAM_CONTRACT")
    if env_path:
        data = load_json_file(env_path)
        if data is not None:
            return data, env_path
    if hook_input and non_empty_string(hook_input.get("task_id")):
        path = team_contract_state_path(hook_input["task_id"])
        data = load_json_file(path)
        if data is not None:
            return data, path
    path = repo_state_file("team-contract.json")
    data = load_json_state(path)
    if data is not None:
        return data, path
    return None, None


def team_contract_write(argv):
    try:
        contract, _ = json_arg_or_stdin(argv, "team-contract-write")
    except Exception as e:
        json_print({"result": "team_contract_rejected", "errors": [str(e)]})
        return
    errors = validate_team_contract(contract)
    if errors:
        json_print({"result": "team_contract_rejected", "errors": errors})
        return
    contract = dict(contract)
    contract["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = team_contract_state_path(contract["task_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MARKER_DIR.mkdir(exist_ok=True)
    repo_state_file("team-contract.json").write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    json_print({"result": "team_contract_recorded", "path": path.relative_to(REPO_ROOT).as_posix()})


def validate_team_receipt(receipt, contract):
    errors = []
    if not isinstance(receipt, dict):
        return ["team receipt must be a JSON object"]
    for field in ("task_id", "team", "final_lead_decision"):
        if not non_empty_string(receipt.get(field)):
            errors.append(f"{field} must be a non-empty string")
    if contract and receipt.get("task_id") != contract.get("task_id"):
        errors.append("team receipt task_id does not match active team contract")
    role_outputs = receipt.get("role_outputs")
    if not isinstance(role_outputs, list) or not role_outputs:
        errors.append("role_outputs must be a non-empty list")
    else:
        allowed_roles = set(contract.get("roles", [])) if isinstance(contract, dict) else set()
        permissions = contract.get("role_permissions", {}) if isinstance(contract, dict) else {}
        allowed_paths = contract.get("allowed_paths", []) if isinstance(contract, dict) else []
        for i, item in enumerate(role_outputs):
            if not isinstance(item, dict):
                errors.append(f"role_outputs[{i}] must be an object")
                continue
            for key in ("role", "output", "evidence"):
                if not non_empty_string(item.get(key)):
                    errors.append(f"role_outputs[{i}].{key} must be a non-empty string")
            if allowed_roles and item.get("role") not in allowed_roles:
                errors.append(f"role_outputs[{i}].role is not in team contract roles")
            edited_paths = item.get("edited_paths")
            if edited_paths is not None:
                if not isinstance(edited_paths, list) or any(not non_empty_string(x) for x in edited_paths):
                    errors.append(f"role_outputs[{i}].edited_paths must be a list of strings")
                else:
                    actions = permissions.get(item.get("role"), [])
                    if "edit" not in actions:
                        errors.append(f"role_outputs[{i}].edited_paths not allowed for role without edit permission")
                    for edited in edited_paths:
                        if not path_matches(allowed_paths, edited):
                            errors.append(f"role_outputs[{i}].edited_paths outside allowed_paths: {edited}")
    handoff_paths = receipt.get("handoff_paths")
    if not isinstance(handoff_paths, list):
        errors.append("handoff_paths must be a list")
    elif contract and isinstance(contract.get("handoff_artifacts"), list):
        allowed = contract.get("handoff_artifacts")
        for path in handoff_paths:
            if not non_empty_string(path):
                errors.append("handoff_paths must contain only strings")
            elif not path_matches(allowed, path):
                errors.append(f"handoff path outside handoff_artifacts: {path}")
    try:
        loops = int(receipt.get("repair_loop_count"))
    except (TypeError, ValueError):
        errors.append("repair_loop_count must be an integer")
        loops = 0
    if contract:
        try:
            max_loops = int(contract.get("max_repair_loops", 0))
            if loops > max_loops:
                errors.append("repair_loop_count exceeds max_repair_loops")
        except (TypeError, ValueError):
            pass
        roles = {str(role).lower() for role in contract.get("roles", [])}
        if "qa" in roles:
            verdict = receipt.get("qa_verdict")
            if not isinstance(verdict, dict):
                errors.append("qa_verdict is required when QA role exists")
            else:
                if verdict.get("result") not in {"PASS", "FAIL"}:
                    errors.append("qa_verdict.result must be PASS or FAIL")
                if not non_empty_string(verdict.get("evidence")):
                    errors.append("qa_verdict.evidence must be a non-empty string")
    return errors


def team_run_dir(task_id):
    return TEAM_RUNS_DIR / safe_task_id(task_id)


def team_artifact_rel(path):
    return path.relative_to(REPO_ROOT).as_posix()


def write_team_artifact(path, title, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"# {title}\n\n{body.strip()}\n"
    path.write_text(text, encoding="utf-8")
    return team_artifact_rel(path)


def materialize_team_artifacts(receipt, contract):
    task_id = receipt["task_id"]
    base = team_run_dir(task_id)
    artifacts = []
    for item in receipt.get("role_outputs", []):
        if not isinstance(item, dict):
            continue
        role = item.get("role", "role")
        body = (
            f"Role: {role}\n\n"
            f"Output:\n{item.get('output', '')}\n\n"
            f"Evidence:\n{item.get('evidence', '')}\n"
        )
        if item.get("edited_paths"):
            body += "\nEdited paths:\n" + "\n".join(f"- {p}" for p in item.get("edited_paths", [])) + "\n"
        artifacts.append(write_team_artifact(base / f"role-{stable_slug(role)}.md", f"Role Output: {role}", body))
    verdict = receipt.get("qa_verdict")
    if isinstance(verdict, dict):
        artifacts.append(write_team_artifact(
            base / "qa-verdict.md",
            "QA Verdict",
            f"Result: {verdict.get('result')}\n\nEvidence:\n{verdict.get('evidence', '')}",
        ))
    artifacts.append(write_team_artifact(
        base / "final-lead-decision.md",
        "Final Lead Decision",
        receipt.get("final_lead_decision", ""),
    ))
    handoff_paths = receipt.get("handoff_paths", [])
    artifacts.append(write_team_artifact(
        base / "handoff-summary.md",
        "Handoff Summary",
        "\n".join(f"- {path}" for path in handoff_paths) if handoff_paths else "No handoff paths recorded.",
    ))
    if isinstance(contract, dict):
        artifacts.append(write_team_artifact(
            base / "team-contract-summary.md",
            "Team Contract Summary",
            f"Team: {contract.get('team')}\n\nStop condition: {contract.get('stop_condition')}",
        ))
    return artifacts


def team_receipt_write(argv):
    try:
        receipt, _ = json_arg_or_stdin(argv, "team-receipt-write")
    except Exception as e:
        json_print({"result": "team_receipt_rejected", "errors": [str(e)]})
        return
    contract, _ = load_team_contract({"task_id": receipt.get("task_id")} if isinstance(receipt, dict) else {})
    errors = validate_team_receipt(receipt, contract)
    if errors:
        json_print({"result": "team_receipt_rejected", "errors": errors})
        return
    receipt = dict(receipt)
    receipt["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt["generated_artifacts"] = materialize_team_artifacts(receipt, contract)
    path = team_receipt_state_path(receipt["task_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    json_print({"result": "team_receipt_recorded", "path": path.relative_to(REPO_ROOT).as_posix()})


def role_from_hook_input(hook_input):
    for key in ("pilothos_role", "role", "team_role"):
        if non_empty_string(hook_input.get(key)):
            return hook_input.get(key)
    tool_input = (
        hook_input.get("tool_input")
        or hook_input.get("toolInput")
        or hook_input.get("input")
    )
    if isinstance(tool_input, dict):
        for key in ("pilothos_role", "role", "team_role"):
            if non_empty_string(tool_input.get(key)):
                return tool_input.get(key)
    return None


def preflight():
    """Preflight cua /pilothos-init: kiem tra moi truong, fail som va ro rang."""
    import os
    ok = True

    def check(cond, msg_ok, msg_fail):
        nonlocal ok
        if cond:
            print(f"OK   {msg_ok}")
        else:
            ok = False
            print(f"FAIL {msg_fail}")

    check(os.access(REPO_ROOT, os.W_OK),
          f"repo root ghi duoc: {REPO_ROOT}",
          f"repo root KHONG ghi duoc: {REPO_ROOT}")
    claude_dir = REPO_ROOT / ".claude"
    check(claude_dir.exists() and os.access(claude_dir, os.W_OK)
          or (not claude_dir.exists() and os.access(REPO_ROOT, os.W_OK)),
          ".claude/ ghi duoc hoac tao duoc",
          ".claude/ KHONG ghi duoc")
    if SETTINGS.exists():
        try:
            json.load(open(SETTINGS, encoding="utf-8"))
            print(f"OK   settings.json hien co hop le")
        except json.JSONDecodeError as e:
            ok = False
            print(f"FAIL settings.json hien co KHONG hop le: {e} — sua truoc khi init")
    else:
        print("OK   chua co settings.json (se duoc tao/merge o Apply)")
    missing = [f.name for f in CORE_FILES if not f.exists()]
    check(not missing,
          "cay pilothOS/ day du core files",
          f"cay pilothOS/ THIEU: {', '.join(missing)} — ban phan phoi loi hoac dirty install")
    print("PREFLIGHT " + ("PASSED" if ok else "FAILED"))


def detect():
    """Stage 0 cua /pilothos-init: verdict + evidence. KHONG tu re nhanh —
    agent phai trinh bay ket qua va CHO CONSUMER CONFIRM."""
    evidence = []
    if INIT_MARKER.exists():
        print("VERDICT: re-init")
        print(f"EVIDENCE: {INIT_MARKER} ton tai — "
              f"noi dung: {INIT_MARKER.read_text(encoding='utf-8').strip()}")
        print("NOTE: co the upgrade bang staging --upgrade va installer mode=upgrade; "
              "khong chay lai greenfield/brownfield plan tren project da init.")
        return
    missing = [f.name for f in CORE_FILES if not f.exists()]
    if missing:
        print("VERDICT: dirty")
        print(f"EVIDENCE: pilothOS/ ton tai nhung thieu core files: {', '.join(missing)}")
        print("NOTE: co the la lan init/copy truoc bi do dang. De xuat: xoa pilothOS/ "
              "va copy lai ban phan phoi, hoac phuc hoi tu .backup/manifest neu co.")
        return
    root_claude = REPO_ROOT / "CLAUDE.md"
    if root_claude.exists():
        content = root_claude.read_text(encoding="utf-8", errors="replace")
        if "@pilothOS/bootstrap.md" in content:
            evidence.append("CLAUDE.md o root da import bootstrap cua PilothOS (ban phan phoi full-copy)")
        else:
            evidence.append("CLAUDE.md o root la cua consumer (KHONG import bootstrap PilothOS)")
    for name in ("AGENTS.md",):
        f = REPO_ROOT / name
        if f.exists() and "PilothOS" not in f.read_text(encoding="utf-8", errors="replace"):
            evidence.append(f"{name} cua consumer ton tai")
    for hint in CONSUMER_ASSET_HINTS:
        if (REPO_ROOT / hint).exists():
            evidence.append(f"tai san consumer: {hint}")
    for adir in ADAPTER_DIRS:
        d = REPO_ROOT / adir
        if d.exists():
            extra = _non_pilothos_content(d)
            if extra:
                evidence.append(
                    f"tai san consumer trong {adir}/: {', '.join(extra[:5])}"
                    + (" ..." if len(extra) > 5 else ""))
    consumer_signals = [e for e in evidence if "consumer" in e or "tai san" in e]
    if consumer_signals:
        print("VERDICT: brownfield")
    else:
        print("VERDICT: greenfield")
    for e in evidence or ["repo chi chua ban phan phoi PilothOS, khong co tai san khac"]:
        print(f"EVIDENCE: {e}")
    print("NOTE: verdict chi la de xuat — agent PHAI trinh bay va cho consumer confirm truoc khi sang Stage 1.")


