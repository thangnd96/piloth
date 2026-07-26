

# ------------------------------------------------------------ OS quality gates
def contract_requires_ui_quality_evidence(contract, receipt=None):
    if isinstance(contract, dict) and contract.get("evidence_profile") == "ui":
        return True
    paths = []
    if isinstance(contract, dict):
        paths.extend(clean_string_list(contract.get("allowed_paths")))
        paths.extend(clean_string_list(contract.get("target_paths")))
    if isinstance(receipt, dict):
        paths.extend(clean_string_list(receipt.get("changed_files")))
    return any(path_pattern_suggests_ui(path) for path in paths)


def required_gates_for_task(contract, receipt=None, mode=None):
    paths = sorted(facts_paths({}, receipt))
    if isinstance(contract, dict):
        paths.extend(clean_string_list(contract.get("allowed_paths")))
    layers = set()
    if isinstance(contract, dict):
        layers |= {normalize_layer(x) for x in contract.get("affected_layers", [])}
    if isinstance(receipt, dict):
        layers |= {normalize_layer(x) for x in receipt.get("affected_layers", [])}
    effective_mode = mode or (contract.get("mode") if isinstance(contract, dict) else None) or "standard"
    gates = ["scope", "correctness", "disclosure"]
    if effective_mode != "lean":
        gates.insert(2, "traceability")
    if effective_mode != "lean" and (not layers or not layers <= DOC_TEST_LAYERS):
        gates.extend(["architecture", "reuse_non_duplication", "regression"])
    if any(path_pattern_suggests_ui(path) or is_ui_path(path) for path in paths):
        gates.append("design_system")
    if contract_requires_ui_quality_evidence(contract, receipt):
        gates.append("ui_quality")
    if (
        isinstance(contract, dict) and contract.get("evidence_profile") == "design_tokens"
    ) or (
        isinstance(receipt, dict) and receipt.get("evidence_profile") == "design_tokens"
    ):
        gates.append("design_token_coverage")
    signal_text = json.dumps({
        "contract": contract or {},
        "receipt": receipt or {},
    }, ensure_ascii=False).lower()
    if "release/deploy" in signal_text or "deploy" in signal_text:
        gates.append("operational_approval")
    return list(dict.fromkeys(gates))


def validate_required_quality_gates(receipt, required_gates):
    errors = []
    gates = receipt.get("quality_gates")
    if not isinstance(gates, dict):
        return ["quality_gates must be an object for os-close"]
    for gate in required_gates:
        item = gates.get(gate)
        if not isinstance(item, dict):
            errors.append(f"quality_gates.{gate} is required for os-close")
            continue
        result = item.get("result")
        if result not in QUALITY_GATE_RESULTS:
            errors.append(f"quality_gates.{gate}.result must be PASS, FAIL, or NOT_APPLICABLE")
        if not non_empty_string(item.get("evidence")):
            errors.append(f"quality_gates.{gate}.evidence must be a non-empty string")
        delivery_result = str(receipt.get("result", "")).strip().lower()
        if result == "FAIL" and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
            if not non_empty_string(receipt.get("limitation")):
                errors.append(f"limitation is required when quality_gates.{gate}.result is FAIL")
    return errors


def evidence_text_blob(receipt, facts, os_evidence):
    parts = []
    for item in os_evidence:
        parts.append(json.dumps(item, ensure_ascii=False))
    for item in facts.get("evidence_commands", []):
        parts.append(json.dumps(item, ensure_ascii=False))
    if isinstance(receipt, dict):
        parts.append(str(receipt.get("verification_command", "")))
        for item in receipt.get("tool_uses", []) if isinstance(receipt.get("tool_uses"), list) else []:
            if isinstance(item, dict):
                parts.append(json.dumps(item, ensure_ascii=False))
        gates = receipt.get("quality_gates")
        if isinstance(gates, dict):
            parts.append(json.dumps(gates, ensure_ascii=False))
    return "\n".join(parts).lower()


def validate_expected_evidence_present(contract, receipt, facts, os_evidence):
    if not isinstance(contract, dict):
        return ["active OS contract is missing"]
    blob = evidence_text_blob(receipt, facts, os_evidence)
    errors = []
    for expected in contract.get("expected_evidence", []):
        if not non_empty_string(expected):
            continue
        needle = expected.strip().lower()
        if needle not in blob:
            errors.append(f"missing evidence for expected_evidence: {expected}")
    return errors


def collect_evidence_refs(receipt, os_evidence):
    refs = {"receipt", "verification_command"}
    for item in os_evidence:
        if non_empty_string(item.get("id")):
            refs.add(item["id"])
    gates = receipt.get("quality_gates") if isinstance(receipt, dict) else None
    if isinstance(gates, dict):
        for key in gates:
            refs.add(f"quality_gates.{key}")
    return refs


def unqualified_absolute_claim(text):
    lowered = str(text).lower()
    if not ABSOLUTE_CLAIM_RE.search(lowered):
        return False
    return not any(term in lowered for term in QUALIFIED_CLAIM_TERMS)


def truth_risk_flags(receipt, os_evidence, missing_evidence_errors):
    flags = []
    payloads = [receipt] + list(os_evidence)
    if missing_evidence_errors:
        flags.append("missing required evidence")
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        text = json.dumps(payload, ensure_ascii=False).lower()
        if non_empty_string(payload.get("limitation")):
            flags.append("limitation recorded")
        if any(term in text for term in ("not run", "not_run", "skipped", "blocked", "unable")):
            flags.append("verification skipped or blocked")
        if "missing font" in text:
            flags.append("missing font")
        if "pixel" in text and any(term in text for term in ("different", "failed", "mismatch")):
            flags.append("failed pixel diff")
        blockers = payload.get("blockers")
        try:
            if blockers is not None and int(blockers) > 0:
                flags.append("non-zero blockers")
        except (TypeError, ValueError):
            if blockers:
                flags.append("non-zero blockers")
        gates = payload.get("quality_gates")
        if isinstance(gates, dict):
            for name, gate in gates.items():
                if isinstance(gate, dict) and gate.get("result") == "FAIL":
                    flags.append(f"failed quality gate: {name}")
    return sorted(set(flags))


def validate_truth_claims(receipt, os_evidence, missing_evidence_errors=None, contract=None, state=None):
    errors = []
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]
    claims = receipt.get("claims")
    if not isinstance(claims, list) or not claims:
        return ["claims must be a non-empty list for os-close"]
    refs = collect_evidence_refs(receipt, os_evidence)
    risk_flags = truth_risk_flags(receipt, os_evidence, missing_evidence_errors or [])
    for i, item in enumerate(claims):
        if isinstance(item, str):
            errors.append(f"claims[{i}] must be an object with claim and evidence_refs")
            continue
        if not isinstance(item, dict):
            errors.append(f"claims[{i}] must be an object")
            continue
        text = item.get("claim")
        if not non_empty_string(text):
            errors.append(f"claims[{i}].claim must be a non-empty string")
            continue
        evidence_refs = item.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(not non_empty_string(ref) for ref in evidence_refs):
            errors.append(f"claims[{i}].evidence_refs must be a non-empty list of strings")
        else:
            missing = sorted(str(ref) for ref in evidence_refs if str(ref) not in refs)
            if missing:
                errors.append(f"claims[{i}].evidence_refs unknown: {', '.join(missing)}")
        if unqualified_absolute_claim(text) and risk_flags:
            errors.append(
                f"claims[{i}] uses an absolute claim but evidence has limitations: "
                + ", ".join(risk_flags)
            )
        if DESIGN_TOKEN_FULL_CLAIM_RE.search(str(text)) and unqualified_absolute_claim(text):
            ok, reason = full_design_token_coverage_ok(receipt, contract, state, os_evidence)
            if not ok:
                errors.append(f"claims[{i}] claims full design-token coverage without sufficient evidence: {reason}")
        if COST_CLAIM_RE.search(str(text)) and not has_real_llm_token_telemetry(os_evidence):
            errors.append(
                f"claims[{i}] claims lower token/cost usage without real llm_usage telemetry"
            )
        if SUPERIORITY_CLAIM_RE.search(str(text)) and not consumer_superiority_ok(receipt, os_evidence):
            errors.append(
                f"claims[{i}] claims Piloth consumer superiority/value without benchmark evidence proving all mandatory metrics are not worse and at least one consumer-visible metric wins"
            )
    return errors


def list_of_strings(value):
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [
        str(item).strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ]


def evidence_source_refs(evidence):
    refs = []
    source_refs = evidence.get("source_refs")
    if isinstance(source_refs, list):
        for item in source_refs:
            if isinstance(item, str) and item.strip():
                refs.append(item.strip())
            elif isinstance(item, dict):
                file_key = item.get("fileKey") or item.get("file_key")
                node_id = item.get("nodeId") or item.get("node_id") or item.get("frameId") or item.get("frame_id")
                if non_empty_string(file_key) and non_empty_string(node_id):
                    refs.append(f"{file_key}:{node_id}")
    for file_key_name, node_key_name in (
        ("fileKey", "nodeId"),
        ("file_key", "node_id"),
        ("fileKey", "frameId"),
        ("file_key", "frame_id"),
    ):
        file_key = evidence.get(file_key_name)
        node_id = evidence.get(node_key_name)
        if non_empty_string(file_key) and non_empty_string(node_id):
            refs.append(f"{file_key}:{node_id}")
    return sorted(set(refs))


def validate_design_token_coverage(evidence):
    if not isinstance(evidence, dict):
        return ["design token coverage evidence must be an object"]
    if evidence.get("kind") != "design_token_coverage":
        return []
    errors = []
    if not evidence_source_refs(evidence):
        errors.append("design_token_coverage requires Figma/source refs (fileKey+nodeId/frameId or source_refs)")
    covered_groups = list_of_strings(evidence.get("covered_groups"))
    generated_surfaces = list_of_strings(evidence.get("generated_surfaces"))
    if not (
        covered_groups
        or generated_surfaces
        or non_empty_string(evidence.get("surface"))
        or non_empty_string(evidence.get("artifact_path"))
        or non_empty_string(evidence.get("target_path"))
    ):
        errors.append("design_token_coverage requires covered_groups, generated_surfaces, surface, artifact_path, or target_path")
    token_count = evidence.get("token_count")
    if token_count is not None:
        try:
            if int(token_count) < 0:
                errors.append("design_token_coverage.token_count must be non-negative")
        except (TypeError, ValueError):
            errors.append("design_token_coverage.token_count must be numeric when present")
    return errors


def validate_metric_evidence(evidence):
    if not isinstance(evidence, dict) or evidence.get("kind") != "metric":
        return []
    errors = []
    metric_type = str(evidence.get("metric_type") or "").strip()
    if metric_type not in METRIC_TYPES:
        errors.append("metric evidence requires metric_type one of: " + ", ".join(sorted(METRIC_TYPES)))
    if not non_empty_string(evidence.get("metric_name")):
        errors.append("metric evidence requires metric_name")
    for field in (
        "value", "count", "chars", "bytes", "duration_ms",
        "input_tokens", "output_tokens", "total_tokens",
        "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd",
        "viewport_width", "viewport_height", "console_error_count",
        "page_error_count", "image_failure_count", "layout_overflow_count",
        "visual_diff_pixels", "visual_diff_ratio",
    ):
        if field in evidence and evidence.get(field) is not None:
            try:
                if float(evidence.get(field)) < 0:
                    errors.append(f"metric evidence {field} must be non-negative")
            except (TypeError, ValueError):
                errors.append(f"metric evidence {field} must be numeric when present")
    if metric_type == "llm_usage" and evidence.get("real_token_telemetry") is not True:
        if not non_empty_string(evidence.get("unavailable_reason")):
            errors.append("llm_usage metric without real_token_telemetry=true requires unavailable_reason")
    if metric_type == "ui_quality":
        ui_fields = (
            "viewport_width", "viewport_height", "required_text_ok",
            "console_errors", "console_error_count", "page_errors",
            "page_error_count", "image_failures", "image_failure_count",
            "horizontal_overflow", "vertical_overflow", "layout_overflow_count",
            "visual_diff_result", "screenshot_path", "comparison_artifact_path",
            "artifact_path",
        )
        if not any(field in evidence for field in ui_fields):
            errors.append("ui_quality metric requires browser/visual check fields")
    return errors


def has_real_llm_token_telemetry(os_evidence):
    return any(
        isinstance(item, dict)
        and item.get("kind") == "metric"
        and item.get("metric_type") == "llm_usage"
        and item.get("real_token_telemetry") is True
        for item in os_evidence
    )


def numeric_metric_value(item, *keys):
    for key in keys:
        if key not in item:
            continue
        try:
            return float(item.get(key) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def ui_quality_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict)
        and item.get("kind") == "metric"
        and item.get("metric_type") == "ui_quality"
    ]


def ui_quality_record_failed(item):
    failures = []
    if item.get("required_text_ok") is False:
        failures.append("required_text_ok=false")
    if item.get("horizontal_overflow") is True:
        failures.append("horizontal_overflow=true")
    if item.get("vertical_overflow") is True:
        failures.append("vertical_overflow=true")
    if numeric_metric_value(item, "console_error_count") > 0:
        failures.append("console_error_count>0")
    if numeric_metric_value(item, "page_error_count") > 0:
        failures.append("page_error_count>0")
    if numeric_metric_value(item, "image_failure_count", "image_failures") > 0:
        failures.append("image_failure_count>0")
    if numeric_metric_value(item, "layout_overflow_count") > 0:
        failures.append("layout_overflow_count>0")
    visual = str(item.get("visual_diff_result") or "").strip().lower()
    if visual in {"fail", "failed", "mismatch", "different", "regressed"}:
        failures.append("visual_diff_result=" + visual)
    return failures


def design_token_coverage_records(os_evidence):
    return [
        item for item in os_evidence
        if isinstance(item, dict) and item.get("kind") == "design_token_coverage"
    ]


def design_token_profile_active(contract, receipt=None, state=None):
    for payload in (receipt, contract, state):
        if isinstance(payload, dict) and payload.get("evidence_profile") == "design_tokens":
            return True
    return False


def design_token_generated_surfaces(coverage):
    surfaces = set()
    for item in coverage:
        surfaces |= set(list_of_strings(item.get("generated_surfaces")))
        if non_empty_string(item.get("surface")):
            surfaces.add(str(item.get("surface")).strip())
    return surfaces


def validate_design_token_receipt(receipt, contract, state, os_evidence):
    if not design_token_profile_active(contract, receipt, state):
        return []
    errors = []
    coverage = design_token_coverage_records(os_evidence)
    if not coverage:
        errors.append("evidence_profile=design_tokens requires design_token_coverage evidence")
    if not any(item.get("kind") == "figma_node" for item in os_evidence):
        errors.append("evidence_profile=design_tokens requires figma_node evidence")
    for item in coverage:
        errors.extend(validate_design_token_coverage(item))
    surfaces = design_token_generated_surfaces(coverage)
    if not surfaces and not non_empty_string(receipt.get("limitation")):
        errors.append("design token coverage requires generated_surfaces/surface evidence or a receipt limitation")
    gates = receipt.get("quality_gates") if isinstance(receipt, dict) else None
    if not isinstance(gates, dict) or not isinstance(gates.get("design_token_coverage"), dict):
        errors.append("quality_gates.design_token_coverage is required for evidence_profile=design_tokens")
    return errors


def validate_ui_quality_receipt(receipt, contract, os_evidence):
    if not contract_requires_ui_quality_evidence(contract, receipt):
        return []
    errors = []
    records = ui_quality_records(os_evidence)
    if not records:
        errors.append("UI tasks require ui_quality metric evidence from browser/visual inspection")
    failed = []
    for item in records:
        for reason in ui_quality_record_failed(item):
            failed.append(f"{item.get('id', 'ui_quality')}: {reason}")
    delivery_result = str(receipt.get("result", "") if isinstance(receipt, dict) else "").strip().lower()
    if failed and delivery_result in {"pass", "passed", "success", "successful", "ok"}:
        errors.append("UI quality evidence contains failing checks: " + ", ".join(failed))
    return errors


def full_design_token_coverage_ok(receipt, contract, state, os_evidence):
    if not design_token_profile_active(contract, receipt, state):
        return False, "receipt/contract evidence_profile is not design_tokens"
    coverage = design_token_coverage_records(os_evidence)
    full = [
        item for item in coverage
        if item.get("coverage_scope") == "full_declared_source"
    ]
    if not full:
        return False, "missing design_token_coverage coverage_scope=full_declared_source"
    if not all(evidence_source_refs(item) for item in full):
        return False, "full design-token coverage requires source refs"
    surfaces = design_token_generated_surfaces(full)
    missing_surfaces = sorted(DESIGN_TOKEN_SURFACES - surfaces)
    if missing_surfaces and not non_empty_string(receipt.get("limitation")):
        return False, "missing generated design-token surfaces: " + ", ".join(missing_surfaces)
    return True, ""


def evidence_payload_present(sanitized):
    if any(non_empty_string(sanitized.get(key)) for key in (
        "command", "summary", "artifact", "artifact_path", "target_path",
        "evidence_output", "quality_gate", "gate", "fileKey", "nodeId",
        "frameId", "coverage_scope", "surface", "metric_name", "metric_type",
        "consumer_value_result",
        "browser", "browser_tool", "url", "visual_diff_result",
        "screenshot_path", "comparison_artifact_path",
    )):
        return True
    if any(key in sanitized for key in (
        "required_text_ok", "console_errors", "console_error_count",
        "page_errors", "page_error_count", "image_failures",
        "image_failure_count", "horizontal_overflow", "vertical_overflow",
        "layout_overflow_count", "viewport_width", "viewport_height",
    )):
        return True
    if list_of_strings(sanitized.get("covered_groups")):
        return True
    if list_of_strings(sanitized.get("generated_surfaces")):
        return True
    if evidence_source_refs(sanitized):
        return True
    if isinstance(sanitized.get("options"), list) and sanitized.get("options"):
        return True
    if isinstance(sanitized.get("decisions"), list) and sanitized.get("decisions"):
        return True
    return False


def sanitize_os_evidence_payload(payload):
    if not isinstance(payload, dict):
        return None, ["evidence payload must be a JSON object"]
    allowed = {
        "id", "ref", "evidence_ref", "kind", "command", "result", "summary",
        "artifact", "path", "tool", "risk", "timeout", "evidence_output",
        "limitation", "quality_gate", "gate", "status", "blockers",
        "fileKey", "file_key", "nodeId", "node_id", "frameId", "frame_id",
        "token_count", "covered_groups", "surface", "artifact_path",
        "target_path", "source_refs", "coverage_scope", "generated_surfaces",
        "verification", "limitations",
        "method", "options", "chosen", "chosen_rationale",
        "prototype_doc", "prototype_sha256",
        "discovery_doc", "decisions", "unresolved",
        "metric_type", "metric_name", "phase", "unit", "value", "count",
        "chars", "bytes", "duration_ms", "input_tokens", "output_tokens",
        "total_tokens", "real_token_telemetry", "unavailable_reason",
        "cache_creation_input_tokens", "cache_read_input_tokens", "cost_usd",
        "cost_complete", "unpriced_models", "unpriced_tokens",
        "model", "pricing_source", "window_start", "subagent_scope",
        "consumer_value_result", "all_mandatory_not_worse",
        "consumer_visible_win", "mandatory_regressions", "wins",
        "viewport_width", "viewport_height", "browser", "browser_tool", "url",
        "required_text_ok", "console_errors", "console_error_count",
        "page_errors", "page_error_count", "image_failures", "image_failure_count",
        "horizontal_overflow", "vertical_overflow", "layout_overflow_count",
        "visual_diff_result", "visual_diff_pixels", "visual_diff_ratio",
        "screenshot_path", "baseline_screenshot_path", "comparison_artifact_path",
    }
    output_fields = {"stdout", "stderr", "output", "raw_output", "full_output", "logs", "log", "env", "environment"}
    sanitized = {}
    for key, value in payload.items():
        if key in output_fields:
            sanitized["output_redacted"] = True
            continue
        if key == "task_id":
            continue
        if key not in allowed:
            continue
        if SECRET_KEY_RE.search(str(key)) and key not in SAFE_OS_EVIDENCE_METADATA_KEYS:
            sanitized[str(key)] = "[redacted]"
        else:
            sanitized[str(key)] = sanitize_state_value(value, limit=1000)
    kind = sanitized.get("kind")
    if kind is not None and kind not in OS_EVIDENCE_KINDS:
        return None, ["kind must be one of: " + ", ".join(sorted(OS_EVIDENCE_KINDS))]
    if not evidence_payload_present(sanitized):
        return None, ["evidence must include command, summary, artifact, safe metadata, evidence_output, quality_gate, or gate"]
    coverage_errors = validate_design_token_coverage(sanitized)
    if coverage_errors:
        return None, coverage_errors
    metric_errors = validate_metric_evidence(sanitized)
    if metric_errors:
        return None, metric_errors
    evidence_id = (
        safe_evidence_id(sanitized.get("id"))
        or safe_evidence_id(sanitized.get("ref"))
        or safe_evidence_id(sanitized.get("evidence_ref"))
    )
    if not evidence_id:
        basis = dict(sanitized)
        evidence_id = "ev-" + sha256_json(basis)[:12]
    sanitized["id"] = evidence_id
    sanitized["recorded_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    sanitized["repo_key"] = REPO_KEY
    return sanitized, []
