

# ---------------------------------------------------------- OS lifecycle modes
def os_start_schema_payload():
    """Machine-readable os-start request schema (SSOT for the doc page).

    Mirrors `installer explain`: field -> {required, default, allowed, aliases}.
    """
    return {
        "result": "os_start_schema",
        "note": "All fields optional; a bare {} opens a repo-local run. See runtime/os-control-plane.md.",
        "fields": {
            "task_id": {"required": False, "default": "task-<sha256[:12]> from intent", "aliases": ["id", "request_id"]},
            "intent": {"required": False, "default": "repo-local OS task", "aliases": ["task_scope", "summary", "title"], "note": "becomes contract.task_scope"},
            "task_signal": {"required": False, "default": "not_applicable", "allowed": sorted(ASSET_ROUTING_SIGNALS)},
            "target_repo": {"required": False, "default": "<control-plane repo>", "note": "absolute path; must exist and not be inside pilothOS/memory/state"},
            "target_kind": {"required": False, "allowed": sorted(TARGET_KINDS), "note": "cross-checked vs actual git detection"},
            "target_paths": {"required": False, "default": ["**/*"], "aliases": ["allowed_paths", "affected_paths", "paths"], "note": "each must be a safe glob"},
            "affected_layers": {"required": False, "default": "derived from paths", "note": "contract requires a non-empty list"},
            "expected_evidence": {"required": False, "default": ["manual verification receipt"]},
            "out_of_scope_paths": {"required": False, "default": []},
            "evidence_profile": {"required": False, "default": "generic", "allowed": sorted(EVIDENCE_PROFILES)},
            "mode": {"required": False, "default": "adaptive", "allowed": sorted(OS_MODE_REQUESTS), "aliases": ["os_mode", "piloth_mode"], "note": "adaptive/auto resolve to lean|standard|strict"},
            "operational_preset": {"required": False, "allowed": sorted(OPERATIONAL_PRESETS)},
            "target_footprint_policy": {"required": False, "allowed": sorted(TARGET_FOOTPRINT_POLICIES), "aliases": ["footprint_policy"], "default": "no_control_plane_files if explicit target else repo_local_state_allowed"},
            "execution_strategy": {"required": False, "default": "controlled_target if explicit target else repo_local"},
            "budget": {"required": False, "note": "object; budget.max_usd is an advisory cost ceiling"},
            "adapter": {"required": False, "allowed": ["claude", "codex", "cursor", "antigravity"], "note": "used for capability handshake; unknown adapters degrade explicitly"},
            "locale": {"required": False, "default": "en", "note": "localizes human-readable summary only; IDs and schema remain English"},
            "adapter_capabilities": {"required": False, "note": "native|emulated|unavailable map; request values override the conservative adapter registry"},
            "specialists": {"required": False, "note": "consumer specialist registry entries; healthy qualified consumer entries outrank Piloth fallbacks"},
            "work_packages": {"required": False, "note": "independent work packages used by the scored team gate"},
            "user_overrides": {"required": False, "note": "rollout/execution override; safety review remains mandatory"},
            "success_metrics": {"required": False},
            "requires_prototype": {"required": False, "default": False, "note": "true also forces requires_human_review"},
            "requires_human_review": {"required": False, "default": False},
            "requires_discovery": {"required": False, "default": False},
            "energy_budget_reason": {"required": "when expected_evidence names a full-suite/broad run", "note": "justify the blast radius of an expensive run"},
        },
    }


def os_start(argv):
    if "--explain" in list(argv):
        json_print(os_start_schema_payload())
        return
    try:
        request, source = json_arg_or_stdin(argv, "os-start")
    except Exception as e:
        json_print({"result": "os_start_rejected", "errors": [str(e)]})
        return
    if not isinstance(request, dict):
        json_print({"result": "os_start_rejected", "errors": ["request must be a JSON object"]})
        return
    if "evidence_profile" in request and str(request.get("evidence_profile")) not in EVIDENCE_PROFILES:
        json_print({
            "result": "os_start_rejected",
            "errors": ["evidence_profile must be one of: " + ", ".join(sorted(EVIDENCE_PROFILES))],
        })
        return
    target, target_errors = resolve_target_repo(request)
    if target_errors:
        json_print({"result": "os_start_rejected", "errors": target_errors})
        return
    task_id = request_task_id(request)
    paths = request_paths(request)
    for pattern in paths:
        if not path_pattern_is_safe(pattern):
            json_print({
                "result": "os_start_rejected",
                "task_id": task_id,
                "errors": [f"target_paths contains unsafe pattern: {pattern}"],
            })
            return
    task_signal = request.get("task_signal") or "not_applicable"
    evidence_router = evidence_route_payload(request)
    if evidence_router.get("result") != "evidence_route":
        json_print({
            "result": "os_start_rejected",
            "task_id": task_id,
            "errors": evidence_router.get("errors", ["evidence router rejected request"]),
        })
        return
    routed_signal = evidence_router.get("task_signal") or task_signal
    route = route_task_payload({
        "task_signal": routed_signal,
        "intent": request_intent(request),
        "affected_paths": paths,
        "adapter": request.get("adapter"),
        "adapter_capabilities": request.get("adapter_capabilities"),
        "_router_compat_only": True,
    })
    scheduler = scheduler_suggest_payload({
        "task_signal": routed_signal,
        "affected_paths": paths,
        "intent": request_intent(request),
        "_router_compat_only": True,
    })
    contract = build_os_contract(request, route, scheduler, target=target)
    contract["evidence_router"] = evidence_router
    contract["decision_id"] = evidence_router.get("decision_id")
    contract["evidence_plan"] = evidence_router.get("evidence_plan", [])
    contract["execution_plan"] = evidence_router.get("execution_plan", {})
    contract["verification_plan"] = evidence_router.get("verification_plan", [])
    contract["router_limitations"] = evidence_router.get("limitations", [])
    contract_errors = validate_task_contract(contract)
    if contract_errors:
        json_print({"result": "os_start_rejected", "task_id": task_id, "errors": contract_errors})
        return
    health_rows = [health_for_asset(row) for row in scanned_asset_rows()]
    target_snapshot = target_state_snapshot(target)
    state = {
        "schema_version": 2,
        "repo_key": REPO_KEY,
        "task_id": task_id,
        "status": "open",
        "lifecycle": ["intake", "contract", "route"],
        "request": sanitize_state_value(request, limit=1000),
        "request_sha256": sha256_json(sanitize_state_value(request, limit=1000)),
        "request_source": str(source.relative_to(REPO_ROOT)) if source and source.is_relative_to(REPO_ROOT) else str(source or ""),
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task_scope": contract["task_scope"],
        "affected_layers": contract["affected_layers"],
        "allowed_paths": contract["allowed_paths"],
        "target_paths": contract["target_paths"],
        "target": target,
        "target_snapshot_sha256": target_snapshot.get("snapshot_sha256", ""),
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "evidence_profile": contract.get("evidence_profile", "generic"),
        "mode": contract.get("mode", "standard"),
        "adaptive_mode": bool(contract.get("adaptive_mode")),
        "mode_decisions": contract.get("mode_decisions", []),
        "execution_strategy": contract.get("execution_strategy", ""),
        "target_footprint_policy": contract.get("target_footprint_policy", ""),
        "budget": contract.get("budget", {}),
        "success_metrics": contract.get("success_metrics", []),
        "benchmark_id": contract.get("benchmark_id", ""),
        "checkpoints": [],
        "cost_ledger": cost_ledger_summary([]),
        "coverage_claims": contract.get("coverage_claims", {}),
        "expected_evidence": contract["expected_evidence"],
        "required_gates": required_gates_for_task(contract, mode=contract.get("mode")),
        "contract": contract,
        "asset_routing": {
            "route": route,
            "asset_count": len(health_rows),
            "unhealthy_assets": [
                {
                    "id": row.get("id"),
                    "status": row.get("status"),
                    "reason": row.get("health_reason", ""),
                }
                for row in health_rows
                if row.get("status") not in {"healthy", "not_applicable"}
            ][:20],
        },
        "scheduler_suggestion": scheduler,
        "evidence_router": evidence_router,
    }
    state_path = save_os_state(state)
    write_json(os_state_path(task_id, "contract.json"), contract)
    write_json(os_state_path(task_id, "target-snapshot.json"), target_snapshot)
    repo_contract = dict(contract)
    repo_contract["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    repo_contract["source"] = state_path.relative_to(REPO_ROOT).as_posix()
    MARKER_DIR.mkdir(exist_ok=True)
    write_json(repo_state_file("task-contract.json"), repo_contract)
    empty_facts = {
        "changed_files": {},
        "affected_layers": [],
        "has_tests": False,
        "has_docs": False,
        "evidence_commands": [],
        "warnings": [],
    }
    update_diff_fact_derived(empty_facts, contract)
    save_diff_facts({}, empty_facts)
    try:
        repo_state_file("deliver-receipt.json").unlink()
    except OSError:
        pass
    json_print({
        "result": "os_started",
        "task_id": task_id,
        "state_path": state_path.relative_to(REPO_ROOT).as_posix(),
        "contract_path": os_state_path(task_id, "contract.json").relative_to(REPO_ROOT).as_posix(),
        "target_snapshot_path": os_state_path(task_id, "target-snapshot.json").relative_to(REPO_ROOT).as_posix(),
        "active_contract_path": repo_state_file("task-contract.json").as_posix(),
        "target": {
            "target_repo": target.get("target_repo"),
            "target_kind": target.get("target_kind"),
            "target_vcs": target.get("target_vcs"),
            "target_id": target.get("target_id"),
            "baseline_dirty_paths": target_snapshot.get("git_status_short", []),
            "file_count": target_snapshot.get("file_count"),
        },
        "required_gates": state["required_gates"],
        "expected_evidence": contract["expected_evidence"],
        "mode": state["mode"],
        "adaptive_mode": state["adaptive_mode"],
        "mode_decisions": state["mode_decisions"],
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "scheduler": {
            "expected_evidence": scheduler.get("expected_evidence") if isinstance(scheduler, dict) else [],
            "energy_budget": scheduler.get("energy_budget") if isinstance(scheduler, dict) else "",
        },
        "asset_routing": route,
        # The full decision is already persisted in the run state and in the
        # contract.json named above, so stdout carries the digest rather than a
        # second copy of the same ~2k tokens.
        "evidence_router": evidence_route_digest(evidence_router),
    })


def os_status(argv=None):
    argv = list(argv or [])
    verbose = "--verbose" in argv
    argv = [a for a in argv if not a.startswith("--")]
    task_id = argv[0] if argv else None
    state, path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_status_missing", "errors": ["no OS run state found"]})
        return
    evidence = os_evidence_records(state.get("task_id"))
    json_print({
        "result": "os_status",
        "task_id": state.get("task_id"),
        "status": state.get("status"),
        "state_path": path.relative_to(REPO_ROOT).as_posix() if path else "",
        "lifecycle": state.get("lifecycle", []),
        "affected_layers": state.get("affected_layers", []),
        # build_os_contract assigns both from the same resolved path list, and
        # target_paths declares allowed_paths as one of its aliases — so they are
        # identical unless the target repo differs from the control plane. Print
        # the alias only when it actually carries different information.
        **(
            {"allowed_paths": state.get("allowed_paths", [])}
            if state.get("allowed_paths", []) != state.get("target_paths", [])
            else {}
        ),
        "target_paths": state.get("target_paths", []),
        "target": state.get("target", {}),
        "evidence_profile": state.get("evidence_profile", "generic"),
        "mode": state.get("mode", ""),
        "adaptive_mode": state.get("adaptive_mode", False),
        "mode_decisions": state.get("mode_decisions", []),
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "budget": state.get("budget", {}),
        "cost_ledger": cost_ledger_summary(evidence),
        "budget_status": budget_status(state.get("contract") or {}, evidence),
        "expected_evidence": state.get("expected_evidence", []),
        "required_gates": state.get("required_gates", []),
        "phase_plan_suggestion": (state.get("contract") or {}).get("phase_plan_suggestion", {}),
        "model_hints": (state.get("contract") or {}).get("model_hints", {}),
        "evidence_router": (
            state.get("evidence_router", {}) if verbose
            else evidence_route_digest(state.get("evidence_router", {}))
        ),
        "requires_prototype": bool((state.get("contract") or {}).get("requires_prototype")),
        "requires_discovery": bool((state.get("contract") or {}).get("requires_discovery")),
        "prototype": state.get("prototype", {}),
        "human_review": state.get("human_review", {}),
        "discovery_recorded": latest_evidence_of_kind(evidence, "discovery") is not None,
        "evidence_count": len(evidence),
        "seal_sha256": state.get("seal_sha256", ""),
    })


def os_evidence(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "os-evidence")
    except Exception as e:
        json_print({"result": "os_evidence_rejected", "errors": [str(e)]})
        return
    task_id = payload.get("task_id") if isinstance(payload, dict) else None
    state, state_path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_evidence_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    if state.get("status") in {"closed", "sealed"}:
        json_print({"result": "os_evidence_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]})
        return
    evidence, errors = sanitize_os_evidence_payload(payload)
    if errors:
        json_print({"result": "os_evidence_rejected", "task_id": state.get("task_id"), "errors": errors})
        return
    task_id = state["task_id"]
    evidence["task_id"] = task_id
    evidence_path = append_os_evidence(task_id, evidence)
    facts = load_diff_facts({})
    facts.setdefault("evidence_commands", []).append({
        "command": evidence.get("command") or evidence.get("summary") or evidence.get("artifact") or evidence["id"],
        "result": evidence.get("result") or evidence.get("status") or "recorded",
        "recorded_at": evidence["recorded_at"],
        "evidence_ref": evidence["id"],
    })
    update_diff_fact_derived(facts, state.get("contract"))
    save_diff_facts({}, facts)
    state.setdefault("lifecycle", [])
    if "tool/evidence" not in state["lifecycle"]:
        state["lifecycle"].append("tool/evidence")
    record_checkpoint_from_evidence(state, evidence)
    state["evidence_count"] = len(os_evidence_records(task_id))
    update_state_runtime_cost(state, task_id)
    save_os_state(state)
    json_print({
        "result": "os_evidence_recorded",
        "task_id": task_id,
        "evidence_ref": evidence["id"],
        "path": evidence_path.relative_to(REPO_ROOT).as_posix(),
        "sanitized": bool(evidence.get("output_redacted")),
    })


def write_active_receipt(receipt):
    MARKER_DIR.mkdir(exist_ok=True)
    receipt = dict(receipt)
    receipt["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write_json(repo_state_file("deliver-receipt.json"), receipt)
    return receipt, repo_state_file("deliver-receipt.json")


def record_receipt_seal(receipt, contract, facts):
    previous = latest_receipt_seal_hash()
    seal = build_receipt_seal(receipt, contract, facts, previous)
    seal["result"] = "receipt_sealed"
    RECEIPT_SEALS.parent.mkdir(parents=True, exist_ok=True)
    with open(RECEIPT_SEALS, "a", encoding="utf-8") as f:
        f.write(json.dumps(seal, ensure_ascii=False, sort_keys=True) + "\n")
    seal["recorded_to"] = RECEIPT_SEALS.relative_to(REPO_ROOT).as_posix()
    return seal


def cross_project_enforcement_advisory(active_facts, target_diff):
    """Non-blocking advisory when hooks likely did not fire on the target.

    If diff-facts (populated only by the target's own PostToolUse hook) is empty
    yet the git/manifest target-diff shows changes, the run was almost certainly
    driven from a different session/repo, so the target's Stop-time deliver gate
    never ran. Enforcement then rests on the target-diff alone. Returns an
    advisory string (or "" when coverage looks normal).
    """
    if not (isinstance(active_facts, dict) and isinstance(target_diff, dict)):
        return ""
    if active_facts.get("changed_files") or not target_diff.get("changed_paths"):
        return ""
    return (
        "diff-facts empty but target-diff shows changes: the target's PostToolUse/"
        "Stop hooks likely did not fire (task driven from another session). "
        "Enforcement relied on the git/manifest target-diff only; run inside the "
        "target's own session for full hook coverage."
    )


def os_close_result(receipt, task_id=None, dry_run=False):
    state, state_path = load_os_state(task_id or (receipt.get("task_id") if isinstance(receipt, dict) else None))
    errors = []
    if not state:
        return {"result": "os_close_rejected", "errors": ["no active OS run; call os-start first"]}
    if state.get("status") in {"closed", "sealed"}:
        return {"result": "os_close_rejected", "task_id": state.get("task_id"), "errors": ["OS run is already closed"]}
    contract = state.get("contract")
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    active_facts = load_diff_facts({})
    if should_use_v1_target_diff(state):
        target_diff = target_diff_from_active_facts(state, active_facts)
    else:
        target_diff = target_changed_paths(state)
    if not dry_run:
        write_json(os_state_path(state["task_id"], "target-diff.json"), target_diff)
    facts = facts_from_target_diff(target_diff, active_facts)
    enforcement_advisory = cross_project_enforcement_advisory(active_facts, target_diff)
    if enforcement_advisory:
        state["enforcement_advisory"] = enforcement_advisory
    os_evidence = os_evidence_records(state["task_id"])
    errors.extend(validate_deliver_receipt(receipt, contract, facts))
    errors.extend(evidence_router_receipt_errors(contract, receipt, os_evidence))
    errors.extend(validate_target_receipt_coverage(receipt, target_diff))
    required_gates = state.get("required_gates") or required_gates_for_task(contract, receipt, mode=state.get("mode"))
    if isinstance(contract, dict) and contract.get("requires_human_review") and "human_review" not in required_gates:
        required_gates = list(required_gates) + ["human_review"]
    errors.extend(validate_required_quality_gates(receipt, required_gates))
    hr_errors, hr_summary = validate_human_review_gate(state, contract, receipt, os_evidence)
    errors.extend(hr_errors)
    state["human_review"] = hr_summary
    if hr_summary.get("unresolved"):
        state["repair_required"] = True
        state["open_review_findings"] = hr_summary["unresolved"]
        state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["review", "repair"]))
    if isinstance(contract, dict) and contract.get("requires_prototype") and "prototype" not in required_gates:
        required_gates = list(required_gates) + ["prototype"]
        errors.extend(validate_required_quality_gates(receipt, ["prototype"]))
    proto_summary = validate_prototype_gate(state, contract, receipt, os_evidence)
    state["prototype"] = proto_summary
    if proto_summary.get("result") == "FAIL":
        errors.append("prototype gate failed: " + str(proto_summary.get("reason", "prototype evidence incomplete")))
        state["prototype_incomplete"] = proto_summary.get("reason", "")
        state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["prototype", "repair"]))
    missing_evidence = validate_expected_evidence_present(contract, receipt, facts, os_evidence)
    errors.extend(missing_evidence)
    errors.extend(validate_design_token_receipt(receipt, contract, state, os_evidence))
    errors.extend(validate_ui_quality_receipt(receipt, contract, os_evidence))
    errors.extend(validate_truth_claims(receipt, os_evidence, missing_evidence, contract=contract, state=state))
    target_footprint = target_footprint_report(state, target_diff)
    if target_footprint.get("result") != "target_footprint_passed":
        errors.extend(target_footprint.get("errors") or ["target footprint policy failed"])
    janitor = artifact_janitor_result(fix=False, root=REPO_ROOT)
    target_janitor = target_janitor_result(state, fix=False)
    if janitor.get("result") != "artifact_janitor_passed":
        errors.append("artifact janitor found local artifacts; run artifact-janitor --fix only if explicit cleanup is intended")
    target = state.get("target") if isinstance(state, dict) else {}
    if (
        isinstance(target, dict)
        and target.get("target_repo") != str(REPO_ROOT.resolve())
        and target_janitor.get("result") != "artifact_janitor_passed"
    ):
        errors.append("target artifact janitor found local artifacts; run artifact-janitor --target <path> --fix only if explicit cleanup is intended")
    if dry_run:
        result = {
            "result": "os_close_dry_run",
            "task_id": state["task_id"],
            "would_pass": not errors,
            "errors": errors,
            "required_gates": required_gates,
            "janitor": janitor,
            "target_janitor": target_janitor,
            "target_footprint": target_footprint,
        }
        if enforcement_advisory:
            result["enforcement_advisory"] = enforcement_advisory
        return result
    if errors:
        state["status"] = "close_rejected"
        state["last_close_errors"] = errors
        state["last_janitor"] = janitor
        state["last_target_janitor"] = target_janitor
        state["last_target_footprint"] = target_footprint
        state["last_target_diff_sha256"] = target_diff.get("diff_sha256", "")
        save_os_state(state)
        return {
            "result": "os_close_rejected",
            "task_id": state["task_id"],
            "errors": errors,
            "janitor": janitor,
            "target_janitor": target_janitor,
            "target_footprint": target_footprint,
            "target_diff": target_diff,
            "state_path": state_path.relative_to(REPO_ROOT).as_posix() if state_path else "",
            "enforcement_advisory": enforcement_advisory,
        }
    receipt, receipt_path = write_active_receipt(receipt)
    save_diff_facts({}, facts)
    seal = record_receipt_seal(receipt, contract, facts)
    target_seal = build_target_seal(state, receipt, target_diff)
    write_json(os_state_path(state["task_id"], "target-seal.json"), target_seal)
    state["status"] = "closed"
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + [
        "quality gates",
        "receipt",
        "seal",
        "janitor",
    ]))
    state["closed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["receipt_sha256"] = sha256_json(receipt)
    state["seal_sha256"] = seal.get("seal_sha256")
    state["seal"] = seal
    state["target_diff_sha256"] = target_diff.get("diff_sha256", "")
    state["target_seal_sha256"] = target_seal.get("target_seal_sha256", "")
    state["target_seal"] = target_seal
    state["receipt_path"] = receipt_path.as_posix()
    state["janitor"] = janitor
    state["target_janitor"] = target_janitor
    state["target_footprint"] = target_footprint
    state["cost_ledger"] = cost_ledger_summary(os_evidence)
    state["consumer_superiority"] = receipt.get("consumer_superiority", {})
    save_os_state(state)
    control = control_plane_check_result(active_policy="always")
    if control.get("result") != "control_plane_passed":
        state["status"] = "close_rejected"
        state["last_control_plane"] = control
        save_os_state(state)
        return {
            "result": "os_close_rejected",
            "task_id": state["task_id"],
            "errors": ["control-plane-check failed"],
            "control_plane": control,
            "seal_sha256": seal.get("seal_sha256"),
            "target_seal_sha256": target_seal.get("target_seal_sha256"),
            "recorded_to": seal.get("recorded_to"),
        }
    state["status"] = "sealed"
    state["control_plane"] = control
    # Auto-clean rác đĩa (Nhóm A) sau khi seal thành công. Run vừa seal là
    # active + mới nhất nên luôn được retention giữ lại; fail-soft tuyệt đối —
    # lỗi dọn dẹp KHÔNG bao giờ làm hỏng os-close.
    try:
        state["state_janitor"] = state_janitor_result(fix=True)
    except Exception as e:
        state["state_janitor"] = {"result": "state_janitor_error", "reason": str(e)}
    save_os_state(state)
    return {
        "result": "os_closed",
        "task_id": state["task_id"],
        "state_path": os_state_path(state["task_id"]).relative_to(REPO_ROOT).as_posix(),
        "receipt_path": receipt_path.as_posix(),
        "seal_sha256": seal.get("seal_sha256"),
        "target_seal_sha256": target_seal.get("target_seal_sha256"),
        "recorded_to": seal.get("recorded_to"),
        "required_gates": required_gates,
        "mode": state.get("mode", ""),
        "cost_ledger": state.get("cost_ledger", {}),
        "janitor": janitor,
        "target_janitor": target_janitor,
        "target_footprint": target_footprint,
        "target_diff_path": os_state_path(state["task_id"], "target-diff.json").relative_to(REPO_ROOT).as_posix(),
        "target_seal_path": os_state_path(state["task_id"], "target-seal.json").relative_to(REPO_ROOT).as_posix(),
        "control_plane": control.get("result"),
        "state_janitor": state.get("state_janitor"),
        "enforcement_advisory": enforcement_advisory,
    }


def os_close(argv):
    args = list(argv)
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args = [a for a in args if a != "--dry-run"]
    try:
        receipt, _ = json_arg_or_stdin(args, "os-close")
    except Exception as e:
        json_print({"result": "os_close_rejected", "errors": [str(e)]})
        return
    if not isinstance(receipt, dict):
        json_print({"result": "os_close_rejected", "errors": ["receipt must be a JSON object"]})
        return
    json_print(os_close_result(receipt, dry_run=dry_run))


def review_request(argv):
    """Emit the review-request artifact for the active OS run (Review state).

    Accepts an optional task id, or a JSON payload {task_id, questions}.
    """
    payload = {}
    task_id = None
    if argv:
        arg = argv[0].strip()
        if arg.startswith("{"):
            try:
                payload = json.loads(arg)
            except Exception as e:
                json_print({"result": "review_request_rejected", "errors": [str(e)]})
                return
            task_id = payload.get("task_id")
        else:
            task_id = argv[0]
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "review_request_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    task_id = state["task_id"]
    contract = state.get("contract") or {}
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    required_gates = state.get("required_gates") or required_gates_for_task(contract, None, mode=state.get("mode"))
    if isinstance(contract, dict) and contract.get("requires_human_review") and "human_review" not in required_gates:
        required_gates = list(required_gates) + ["human_review"]
    changed = sorted(facts_paths(load_diff_facts({}), None))
    contract_path = os_state_path(task_id, "contract.json")
    body = {
        "schema_version": 1,
        "kind": "review_request",
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "under_review": {
            "contract_path": contract_path.relative_to(REPO_ROOT).as_posix() if contract_path.exists() else "",
            "changed_files": changed,
        },
        "gates": required_gates,
        "questions": payload.get("questions") if isinstance(payload.get("questions"), list) else [],
        "requested_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    body["request_sha256"] = sha256_json({
        "task_id": task_id, "under_review": body["under_review"],
        "gates": required_gates, "questions": body["questions"],
    })
    path = os_state_path(task_id, "review-request.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, body)
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + ["review"]))
    save_os_state(state)
    json_print({
        "result": "review_requested",
        "task_id": task_id,
        "gates": required_gates,
        "review_request_path": path.relative_to(REPO_ROOT).as_posix(),
        "request_sha256": body["request_sha256"],
    })


def review_feedback(argv):
    """Ingest a structured human-review round, record it as evidence, update state."""
    try:
        payload, _ = json_arg_or_stdin(argv, "review-feedback")
    except Exception as e:
        json_print({"result": "review_feedback_rejected", "errors": [str(e)]})
        return
    if not isinstance(payload, dict):
        json_print({"result": "review_feedback_rejected", "errors": ["feedback must be a JSON object"]})
        return
    state, _ = load_os_state(payload.get("task_id"))
    if not state:
        json_print({"result": "review_feedback_rejected", "errors": ["no active OS run; call os-start first"]})
        return
    task_id = state["task_id"]
    errors = validate_review_feedback(payload)
    if errors:
        json_print({"result": "review_feedback_rejected", "task_id": task_id, "errors": errors})
        return
    existing = review_feedback_records(task_id)
    try:
        review_round = int(payload.get("review_round"))
    except (TypeError, ValueError):
        review_round = len(existing) + 1
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = sanitize_state_value({
        "schema_version": 1,
        "kind": "human_review",
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "reviewer": payload.get("reviewer") or "",
        "review_round": review_round,
        "verdict": payload.get("verdict"),
        "finalized": bool(payload.get("finalized")),
        "message": payload.get("message") or "",
        "findings": payload.get("findings") or [],
        "recorded_at": now,
    }, limit=4000)
    append_review_feedback(task_id, record)
    unresolved = [
        finding.get("id")
        for finding in record["findings"]
        if isinstance(finding, dict)
        and finding.get("severity") in REVIEW_BLOCKING_SEVERITIES
        and finding.get("disposition") == "request-changes"
    ]
    append_os_evidence(task_id, {
        "id": f"hr-round-{review_round}",
        "kind": "human_review",
        "review_round": review_round,
        "verdict": record["verdict"],
        "finalized": record["finalized"],
        "unresolved": unresolved,
        "reviewer": record["reviewer"],
        "recorded_at": now,
    })
    lifecycle_add = ["review"] + (["repair"] if unresolved else [])
    state["lifecycle"] = list(dict.fromkeys(state.get("lifecycle", []) + lifecycle_add))
    if unresolved:
        state["repair_required"] = True
        state["open_review_findings"] = unresolved
    save_os_state(state)
    json_print({
        "result": "review_feedback_recorded",
        "task_id": task_id,
        "review_round": review_round,
        "verdict": record["verdict"],
        "finalized": record["finalized"],
        "unresolved": unresolved,
    })


def review_verify(argv):
    """Read-only status of the human_review gate for the active OS run."""
    state, _ = load_os_state(argv[0] if argv else None)
    if not state:
        json_print({"result": "review_verify_failed", "errors": ["no active OS run"]})
        return
    contract = state.get("contract") or {}
    active_contract, _ = load_task_contract({})
    if isinstance(active_contract, dict):
        contract = active_contract
    os_evidence = os_evidence_records(state["task_id"])
    hr_errors, hr_summary = validate_human_review_gate(state, contract, {}, os_evidence)
    json_print({
        "result": "review_verified" if not hr_errors else "review_incomplete",
        "task_id": state["task_id"],
        "human_review": hr_summary,
        "errors": hr_errors,
    })


def os_verify(argv):
    task_id = argv[0] if argv else None
    state, _ = load_os_state(task_id)
    if not state:
        json_print({"result": "os_verify_failed", "errors": ["no OS run state found"]})
        return
    seal = state.get("seal")
    if not isinstance(seal, dict):
        json_print({"result": "os_verify_failed", "task_id": state.get("task_id"), "errors": ["OS run has no recorded seal"]})
        return
    receipt, _ = load_deliver_receipt({})
    if receipt is None:
        json_print({"result": "os_verify_failed", "task_id": state.get("task_id"), "errors": ["missing active deliver receipt"]})
        return
    contract, _ = load_task_contract({})
    facts = load_diff_facts({})
    current = build_receipt_seal(receipt, contract, facts, seal.get("previous_seal_sha256", ""))
    control_comparisons = {
        "receipt_sha256": current.get("receipt_sha256") == seal.get("receipt_sha256"),
        "contract_sha256": current.get("contract_sha256") == seal.get("contract_sha256"),
        "diff_facts_sha256": current.get("diff_facts_sha256") == seal.get("diff_facts_sha256"),
        "changed_files": current.get("changed_files") == seal.get("changed_files"),
        "seal_sha256": current.get("seal_sha256") == seal.get("seal_sha256"),
    }
    target_expected = state.get("target_seal")
    if not isinstance(target_expected, dict):
        target_expected = load_json_file(os_state_path(state.get("task_id", ""), "target-seal.json"))
    target_comparisons = {}
    current_target_seal = {}
    if isinstance(target_expected, dict):
        if should_use_v1_target_diff(state):
            current_target_diff = target_diff_from_active_facts(state, facts)
        else:
            current_target_diff = target_changed_paths(state)
        current_target_seal = build_target_seal(state, receipt, current_target_diff)
        target_comparisons = {
            "target_metadata": (
                current_target_seal.get("target_repo") == target_expected.get("target_repo")
                and current_target_seal.get("target_id") == target_expected.get("target_id")
                and current_target_seal.get("target_kind") == target_expected.get("target_kind")
            ),
            "changed_paths": current_target_seal.get("changed_paths") == target_expected.get("changed_paths"),
            "deleted_files": current_target_seal.get("deleted_files") == target_expected.get("deleted_files"),
            "changed_files": current_target_seal.get("changed_files") == target_expected.get("changed_files"),
            "target_diff_sha256": current_target_seal.get("target_diff_sha256") == target_expected.get("target_diff_sha256"),
            "target_seal_sha256": current_target_seal.get("target_seal_sha256") == target_expected.get("target_seal_sha256"),
        }
    else:
        target_comparisons = {"target_seal": False}
    control_errors = [name for name, ok in control_comparisons.items() if not ok]
    target_errors = [name for name, ok in target_comparisons.items() if not ok]
    errors = [f"control_plane.{name}" for name in control_errors] + [f"target.{name}" for name in target_errors]
    json_print({
        "result": "os_verify_passed" if not errors else "os_verify_failed",
        "task_id": state.get("task_id"),
        "comparisons": {
            "control_plane": control_comparisons,
            "target": target_comparisons,
        },
        "errors": errors,
        "current_seal_sha256": current.get("seal_sha256"),
        "expected_seal_sha256": seal.get("seal_sha256"),
        "current_target_seal_sha256": current_target_seal.get("target_seal_sha256", ""),
        "expected_target_seal_sha256": target_expected.get("target_seal_sha256", "") if isinstance(target_expected, dict) else "",
    })


def os_report(argv):
    task_id = argv[0] if argv else None
    state, path = load_os_state(task_id)
    if not state:
        json_print({"result": "os_report_missing", "errors": ["no OS run state found"]})
        return
    evidence = os_evidence_records(state.get("task_id"))
    receipt, receipt_path = load_deliver_receipt({})
    target_diff = load_json_file(os_state_path(state.get("task_id", ""), "target-diff.json"))
    target_seal = state.get("target_seal")
    if not isinstance(target_seal, dict):
        target_seal = load_json_file(os_state_path(state.get("task_id", ""), "target-seal.json"))
    target_footprint = state.get("target_footprint")
    if not isinstance(target_footprint, dict) and isinstance(target_diff, dict):
        target_footprint = target_footprint_report(state, target_diff)
    superiority_payloads = consumer_superiority_payloads(receipt or {}, evidence)
    superiority_passed = consumer_superiority_ok(receipt or {}, evidence)
    if superiority_payloads:
        superiority_result = "consumer_value_passed" if superiority_passed else "consumer_value_failed"
    else:
        superiority_result = "not_claimed"
    json_print({
        "result": "os_report",
        "task_id": state.get("task_id"),
        "status": state.get("status"),
        "state_path": path.relative_to(REPO_ROOT).as_posix() if path else "",
        "receipt_path": receipt_path.as_posix() if receipt_path else "",
        "mode": state.get("mode", ""),
        "adaptive_mode": state.get("adaptive_mode", False),
        "mode_decisions": state.get("mode_decisions", []),
        "phase_plan_suggestion": (state.get("contract") or {}).get("phase_plan_suggestion", {}),
        "model_hints": (state.get("contract") or {}).get("model_hints", {}),
        "execution_strategy": state.get("execution_strategy", ""),
        "target_footprint_policy": state.get("target_footprint_policy", ""),
        "budget": state.get("budget", {}),
        "success_metrics": state.get("success_metrics", []),
        "cost_ledger": cost_ledger_summary(evidence),
        "budget_status": budget_status(state.get("contract") or {}, evidence),
        "consumer_superiority": {
            "result": superiority_result,
            "payload_count": len(superiority_payloads),
            "policy": "not worse on every mandatory metric, real token telemetry present, and win at least one consumer-visible metric before claiming consumer value",
        },
        "target": state.get("target", {}),
        "target_footprint": target_footprint if isinstance(target_footprint, dict) else {},
        "target_diff": target_diff if isinstance(target_diff, dict) else {},
        "target_seal_sha256": target_seal.get("target_seal_sha256", "") if isinstance(target_seal, dict) else "",
        # Same reason as os-status: the full decision stays in state, and the
        # router limitations it carries are repeated under `limitations` below.
        "evidence_router": evidence_route_digest(state.get("evidence_router", {})),
        "required_gates": state.get("required_gates", []),
        "evidence_count": len(evidence),
        "limitations": [
            "exact LLM token usage is unavailable unless llm_usage metrics record real_token_telemetry=true",
            "artifact token estimates are not LLM cost telemetry",
        ] + (
            state.get("evidence_router", {}).get("limitations", [])
            if isinstance(state.get("evidence_router"), dict)
            else []
        ),
    })
