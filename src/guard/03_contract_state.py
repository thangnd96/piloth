# ------------------------------------------------------- task contract state

def repo_state_file(suffix):
    return MARKER_DIR / f"repo-{REPO_KEY}.{suffix}"


def scoped_state_file(hook_input, suffix):
    sid = hook_input.get("session_id")
    if sid:
        return marker(sid, suffix)
    return repo_state_file(suffix)


def fresh_state_file(path):
    try:
        return path.exists() and time.time() - path.stat().st_mtime <= MARKER_TTL_SECONDS
    except OSError:
        return False


def load_json_state(path):
    if not fresh_state_file(path):
        return None
    return load_json_file(path)


def load_json_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def env_state_path(name):
    raw = os.environ.get(name)
    if not raw:
        return None
    p = pathlib.Path(raw)
    if not p.is_absolute():
        p = REPO_ROOT / p
    return p


def load_task_contract(hook_input):
    candidates = []
    env_path = env_state_path("PILOTHOS_TASK_CONTRACT")
    if env_path:
        data = load_json_file(env_path)
        if data is not None:
            return data, env_path
    candidates.append(scoped_state_file(hook_input, "task-contract.json"))
    candidates.append(repo_state_file("task-contract.json"))
    for path in candidates:
        data = load_json_state(path)
        if data is not None:
            return data, path
    return None, None


def load_diff_facts(hook_input):
    data = load_json_state(scoped_state_file(hook_input, "diff-facts.json"))
    if data is None and hook_input.get("session_id"):
        data = load_json_state(repo_state_file("diff-facts.json"))
    if data is None:
        data = {
            "changed_files": {},
            "affected_layers": [],
            "has_tests": False,
            "has_docs": False,
            "evidence_commands": [],
            "warnings": [],
        }
    ensure_diff_fact_fields(data)
    return data


def save_diff_facts(hook_input, facts):
    MARKER_DIR.mkdir(exist_ok=True)
    ensure_diff_fact_fields(facts)
    facts["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    scoped_state_file(hook_input, "diff-facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Also publish the latest facts at repo scope so manual commands such as
    # receipt-write can validate against PostToolUse facts from a session hook.
    repo_state_file("diff-facts.json").write_text(
        json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_deliver_receipt(hook_input):
    candidates = []
    env_path = env_state_path("PILOTHOS_DELIVER_RECEIPT")
    if env_path:
        data = load_json_file(env_path)
        if data is not None:
            return data, env_path
    candidates.append(scoped_state_file(hook_input, "deliver-receipt.json"))
    candidates.append(repo_state_file("deliver-receipt.json"))
    for path in candidates:
        data = load_json_state(path)
        if data is not None:
            return data, path
    return None, None


def normalize_layer(layer):
    return re.sub(r"\s+", " ", str(layer)).strip().lower()


def operational_preset(*configs):
    for name in ("PILOTHOS_OPERATIONAL_PRESET", "PILOTHOS_PRESET"):
        raw = os.environ.get(name)
        if raw:
            return raw.strip().lower()
    for config in configs:
        if isinstance(config, dict):
            raw = config.get("operational_preset")
            if raw:
                return str(raw).strip().lower()
    return "standard"


def valid_operational_preset(value):
    return value in OPERATIONAL_PRESETS


def preset_requires_standard_evidence(*configs):
    return operational_preset(*configs) != "light"


def contract_layers(contract):
    return {normalize_layer(x) for x in contract.get("affected_layers", [])}


def contract_has_layer(contract, allowed):
    layers = contract_layers(contract)
    return bool(layers & allowed)


def normalize_relative_path_text(value):
    rel = str(value).replace("\\", "/").strip()
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def normalize_contract_path_pattern(pattern):
    return normalize_relative_path_text(pattern)


def path_pattern_docs_tests_only(pattern):
    rel = normalize_contract_path_pattern(pattern)
    if not rel or rel in {"*", "**", "**/*", "."}:
        return False
    if rel.startswith(("src/", "app/", "pages/", "components/", "ui/")):
        return False
    if rel.startswith((
        "pilothOS/scripts/",
        "pilothOS/rules/",
        "pilothOS/runtime/",
        "pilothOS/tools/",
        "adapters/",
        "templates/",
        "commands/",
    )):
        return False
    if rel.startswith(("docs/", "test/", "tests/", "__tests__/")):
        return True
    if rel in {"README.md", "CLAUDE.md", "AGENTS.md"}:
        return True
    if rel.endswith(".md") and layer_for_path(rel) == "Docs":
        return True
    return False


def contract_docs_tests_only(contract):
    layers = contract_layers(contract)
    allowed_paths = contract.get("allowed_paths")
    if not (layers and layers <= DOC_TEST_LAYERS):
        return False
    if not isinstance(allowed_paths, list) or not allowed_paths:
        return False
    return all(path_pattern_docs_tests_only(pattern) for pattern in allowed_paths)


def contract_requires_context_evidence(contract):
    return preset_requires_standard_evidence(contract) and not contract_docs_tests_only(contract)


def path_pattern_suggests_ui(pattern):
    rel = normalize_contract_path_pattern(pattern)
    if not rel or rel in {"*", "**", "**/*", "."}:
        return False
    return is_ui_path(rel)


def contract_requires_ui_design_system_evidence(contract):
    if not preset_requires_standard_evidence(contract):
        return False
    allowed_paths = contract.get("allowed_paths")
    if not isinstance(allowed_paths, list):
        return False
    return any(path_pattern_suggests_ui(pattern) for pattern in allowed_paths)


def contract_requires_energy_budget_reason(contract):
    if not preset_requires_standard_evidence(contract):
        return False
    text = " ".join(str(x) for x in contract.get("expected_evidence", []))
    text += " " + str(contract.get("task_scope", ""))
    lowered = text.lower()
    return any(token in lowered for token in (
        "tests/run_all.sh", "run_all.sh", "full suite", "broad scan", "all suites",
    ))


def non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())


def validate_object_list(value, field, required_keys):
    errors = []
    if not isinstance(value, list) or not value:
        return [f"{field} must be a non-empty list of objects"]
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{i}] must be an object")
            continue
        for key in required_keys:
            if not non_empty_string(item.get(key)):
                errors.append(f"{field}[{i}].{key} must be a non-empty string")
    return errors


def validate_object_list_enums(value, field, required_keys, enum_fields):
    errors = validate_object_list(value, field, required_keys)
    if not isinstance(value, list):
        return errors
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        for key, allowed in enum_fields.items():
            raw = item.get(key)
            if not non_empty_string(raw):
                continue
            if raw.strip() not in allowed:
                errors.append(
                    f"{field}[{i}].{key} must be one of: "
                    + ", ".join(sorted(allowed))
                )
    return errors


def validate_reuse_evidence(value, field="reuse_evidence"):
    return validate_object_list_enums(
        value,
        field,
        ("asset", "decision", "reason"),
        {"decision": REUSE_EVIDENCE_DECISIONS},
    )


def validate_asset_routing(value, field="consumer_asset_routing"):
    return validate_object_list_enums(
        value,
        field,
        ASSET_ROUTING_FIELDS,
        {
            "task_signal": ASSET_ROUTING_SIGNALS,
            "asset_type": ASSET_ROUTING_TYPES,
            "decision": ASSET_ROUTING_DECISIONS,
        },
    )


def validate_ui_design_system_evidence(value, field="ui_design_system_evidence"):
    return validate_object_list_enums(
        value,
        field,
        ("source", "checked", "decision", "reason"),
        {"decision": UI_DESIGN_SYSTEM_DECISIONS},
    )


def candidate_confidence(candidate):
    try:
        return float(candidate.get("confidence", 0))
    except (TypeError, ValueError):
        return 0.0


def candidates_from_receipt(receipt, keys):
    candidates = []
    if not isinstance(receipt, dict):
        return candidates
    for key in keys:
        value = receipt.get(key)
        if isinstance(value, list):
            candidates.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            for nested_key in (
                "candidates", "high_confidence_candidates",
                "component_candidates", "token_candidates", "pattern_candidates",
            ):
                nested = value.get(nested_key)
                if isinstance(nested, list):
                    candidates.extend(item for item in nested if isinstance(item, dict))
    return candidates


def review_items(value, field):
    errors = []
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or not value:
        return [], [f"{field} must be a non-empty object or list of objects"]
    items = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{field}[{i}] must be an object")
            continue
        target = item.get("candidate") or item.get("candidate_id") or item.get("id") or item.get("path")
        if not non_empty_string(target):
            errors.append(f"{field}[{i}].candidate must be a non-empty string")
        decision = item.get("decision")
        if decision not in SEMANTIC_REVIEW_DECISIONS:
            errors.append(
                f"{field}[{i}].decision must be one of: "
                + ", ".join(sorted(SEMANTIC_REVIEW_DECISIONS))
            )
        if not non_empty_string(item.get("reason")):
            errors.append(f"{field}[{i}].reason must be a non-empty string")
        items.append({"candidate": str(target), "decision": decision, "reason": item.get("reason")})
    return items, errors


def validate_candidate_review(receipt, candidate_keys, review_field):
    errors = []
    candidates = candidates_from_receipt(receipt, candidate_keys)
    high = [
        c for c in candidates
        if candidate_confidence(c) >= HIGH_CONFIDENCE_THRESHOLD
    ]
    if not high:
        if review_field in receipt:
            _, review_errors = review_items(receipt.get(review_field), review_field)
            errors.extend(review_errors)
        return errors
    reviews, review_errors = review_items(receipt.get(review_field), review_field)
    errors.extend(review_errors)
    if review_errors:
        return errors
    covered = {item["candidate"] for item in reviews}
    covers_all = "all" in covered or "*" in covered
    for candidate in high:
        identifiers = {
            str(candidate.get("id", "")),
            str(candidate.get("path", "")),
            str(candidate.get("candidate", "")),
        }
        identifiers.discard("")
        if not covers_all and not (covered & identifiers):
            errors.append(
                f"{review_field} missing decision for high-confidence candidate: "
                + (candidate.get("id") or candidate.get("path") or "<unknown>")
            )
    return errors


def contract_has_ui_design_system_evidence(contract):
    if not isinstance(contract, dict):
        return False
    return not validate_ui_design_system_evidence(
        contract.get("ui_design_system_evidence"),
        "ui_design_system_evidence",
    )


def path_pattern_is_safe(pattern):
    if not isinstance(pattern, str) or not pattern.strip():
        return False
    pattern = pattern.strip()
    if pattern.startswith("/") or pattern.startswith("~"):
        return False
    return ".." not in pathlib.PurePosixPath(pattern).parts


def path_matches(patterns, rel):
    rel = normalize_relative_path_text(rel)
    for pattern in patterns:
        pattern = normalize_relative_path_text(pattern)
        if pattern in ("*", "**", "**/*"):
            return True
        if pattern.endswith("/"):
            base = pattern.rstrip("/")
            if rel == base or rel.startswith(base + "/"):
                return True
        if any(ch in pattern for ch in "*?["):
            if fnmatch.fnmatchcase(rel, pattern):
                return True
        elif rel == pattern or rel.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def repo_relative_path(path_value):
    if not isinstance(path_value, str) or not path_value.strip():
        return None, "empty path"
    raw = path_value.strip()
    try:
        p = pathlib.Path(raw)
        if p.is_absolute():
            resolved = p.resolve()
            root = REPO_ROOT.resolve()
            if resolved != root and root not in resolved.parents:
                return None, f"path outside repo: {raw}"
            rel = resolved.relative_to(root).as_posix()
        else:
            pure = pathlib.PurePosixPath(raw.replace("\\", "/"))
            if ".." in pure.parts:
                return None, f"path traversal blocked: {raw}"
            rel = normalize_relative_path_text(pure.as_posix())
    except (OSError, ValueError) as e:
        return None, f"invalid path {raw}: {e}"
    if not rel:
        return None, "repo root edit is not allowed"
    return rel, None


def target_relative_path(path_value, target_repo):
    if not isinstance(path_value, str) or not path_value.strip():
        return None, "empty path"
    raw = path_value.strip()
    root = pathlib.Path(target_repo).resolve()
    try:
        p = pathlib.Path(raw)
        if p.is_absolute():
            resolved = p.resolve()
            if resolved != root and root not in resolved.parents:
                return None, f"path outside target repo: {raw}"
            rel = resolved.relative_to(root).as_posix()
        else:
            pure = pathlib.PurePosixPath(raw.replace("\\", "/"))
            if ".." in pure.parts:
                return None, f"path traversal blocked: {raw}"
            rel = normalize_relative_path_text(pure.as_posix())
    except (OSError, ValueError) as e:
        return None, f"invalid path {raw}: {e}"
    if not rel:
        return None, "target repo root is not a file path"
    return rel, None


def resolve_target_repo(request):
    raw = request.get("target_repo") if isinstance(request, dict) else None
    explicit_target = raw is not None and str(raw).strip() != ""
    if raw is None or str(raw).strip() == "":
        target = REPO_ROOT.resolve()
    else:
        if not isinstance(raw, str):
            return None, ["target_repo must be a string when present"]
        candidate = pathlib.Path(raw.strip()).expanduser()
        if not candidate.is_absolute():
            return None, ["target_repo must be an absolute path when present"]
        target = candidate.resolve()
    errors = []
    if not target.exists():
        errors.append(f"target_repo does not exist: {target}")
    elif not target.is_dir():
        errors.append(f"target_repo must be a directory: {target}")
    state_root = (PILOTHOS_DIR / "memory" / "state").resolve()
    if target == state_root or state_root in target.parents:
        errors.append("target_repo cannot be inside pilothOS/memory/state")
    requested_kind = str(request.get("target_kind", "")).strip() if isinstance(request, dict) else ""
    if requested_kind and requested_kind not in TARGET_KINDS:
        errors.append("target_kind must be git, non_git, or external")
    if errors:
        return None, errors

    git_info = git_worktree_info(target)
    actual_kind = "git" if git_info.get("is_git") else "non_git"
    if requested_kind == "git" and actual_kind != "git":
        errors.append("target_kind=git but target_repo is not a git worktree")
    if requested_kind == "non_git" and actual_kind == "git":
        errors.append("target_kind=non_git but target_repo is a git worktree")
    if errors:
        return None, errors

    target_kind = requested_kind if requested_kind == "external" else actual_kind
    marker = git_info.get("git_dir") if actual_kind == "git" else "non_git"
    target_id = sha256_json({
        "target_repo": str(target),
        "target_kind": target_kind,
        "marker": marker,
    })[:16]
    return {
        "target_repo": str(target),
        "target_kind": target_kind,
        "target_vcs": actual_kind,
        "target_id": target_id,
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "external": target != REPO_ROOT.resolve(),
        "explicit": explicit_target,
        "git": git_info,
    }, []


def git_worktree_info(root):
    info = {"is_git": False}
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        if top.returncode != 0:
            return info
        git_dir = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
    except Exception:
        return info
    top_path = pathlib.Path(top.stdout.strip()).resolve()
    raw_git_dir = git_dir.stdout.strip() if git_dir.returncode == 0 else ""
    git_path = pathlib.Path(raw_git_dir)
    if raw_git_dir and not git_path.is_absolute():
        git_path = (pathlib.Path(root) / git_path).resolve()
    return {
        "is_git": True,
        "worktree_root": str(top_path),
        "git_dir": str(git_path) if raw_git_dir else "",
        "head": head.stdout.strip() if head.returncode == 0 else "",
    }


def parse_git_status_paths(output):
    paths = []
    for line in output.splitlines():
        if not line:
            continue
        raw = line[3:] if len(line) > 3 else line
        if " -> " in raw:
            raw = raw.rsplit(" -> ", 1)[1]
        raw = raw.strip().strip('"')
        if raw:
            paths.append(raw)
    return sorted(set(paths))


def git_status_for_root(root):
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=8,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []
    return parse_git_status_paths(out.stdout)


def target_git_status_paths(target):
    root = pathlib.Path(target["target_repo"]).resolve()
    paths = git_status_for_root(root)
    return sorted(paths)


def non_git_snapshot_skip(rel_parts):
    if any(part in ARTIFACT_JANITOR_SKIP_DIRS for part in rel_parts):
        return True
    if rel_parts[:3] == ("pilothOS", "memory", "state"):
        return True
    return False


def target_manifest_snapshot(target_repo):
    root = pathlib.Path(target_repo).resolve()
    files = {}
    root_len = len(root.parts)
    for current, dirs, filenames in os.walk(root):
        current_path = pathlib.Path(current)
        rel_parts = current_path.parts[root_len:]
        dirs.sort()
        filenames.sort()
        dirs[:] = [
            dirname for dirname in dirs
            if not non_git_snapshot_skip(rel_parts + (dirname,))
        ]
        if non_git_snapshot_skip(rel_parts):
            continue
        for filename in filenames:
            if filename in IGNORE_NAMES:
                continue
            path = current_path / filename
            try:
                rel = path.relative_to(root).as_posix()
                data = path.read_bytes()
            except OSError:
                continue
            files[rel] = {
                "path": rel,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
            }
    return files


def target_state_snapshot(target):
    root = pathlib.Path(target["target_repo"]).resolve()
    payload = {
        "schema_version": 1,
        "target_repo": str(root),
        "target_kind": target.get("target_kind"),
        "target_vcs": target.get("target_vcs"),
        "target_id": target.get("target_id"),
        "control_plane_repo": str(REPO_ROOT.resolve()),
        "captured_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    if target.get("target_vcs") == "git":
        payload["git"] = target.get("git", {})
        payload["git_status_short"] = target_git_status_paths(target)
    else:
        files = target_manifest_snapshot(root)
        payload["files"] = files
        payload["file_count"] = len(files)
        payload["manifest_sha256"] = sha256_json(files)
    payload["snapshot_sha256"] = sha256_json(payload)
    return payload


def load_target_snapshot(state):
    if not isinstance(state, dict):
        return {}
    task_id = state.get("task_id")
    if non_empty_string(task_id):
        data = load_json_file(os_state_path(task_id, "target-snapshot.json"))
        if isinstance(data, dict):
            return data
    snap = state.get("target_snapshot")
    return snap if isinstance(snap, dict) else {}


def target_changed_paths(state):
    target = state.get("target") if isinstance(state, dict) else None
    if not isinstance(target, dict):
        return {
            "schema_version": 1,
            "result": "target_diff_unavailable",
            "changed_paths": [],
            "errors": ["OS state has no target metadata"],
        }
    snapshot = load_target_snapshot(state)
    root = pathlib.Path(target["target_repo"]).resolve()
    changed = []
    deleted = []
    created = []
    modified = []
    errors = []
    if target.get("target_vcs") == "git":
        baseline = sorted(snapshot.get("git_status_short") or [])
        current = target_git_status_paths(target)
        changed = sorted(set(baseline) | set(current))
        result = {
            "schema_version": 1,
            "result": "target_diff",
            "target_repo": str(root),
            "target_kind": target.get("target_kind"),
            "target_vcs": target.get("target_vcs"),
            "target_id": target.get("target_id"),
            "baseline_dirty_paths": baseline,
            "current_dirty_paths": current,
            "changed_paths": changed,
            "deleted_files": [],
        }
    else:
        baseline_files = snapshot.get("files") if isinstance(snapshot.get("files"), dict) else {}
        current_files = target_manifest_snapshot(root)
        baseline_paths = set(baseline_files)
        current_paths = set(current_files)
        created = sorted(current_paths - baseline_paths)
        deleted = sorted(baseline_paths - current_paths)
        modified = sorted(
            path for path in (baseline_paths & current_paths)
            if baseline_files[path].get("sha256") != current_files[path].get("sha256")
        )
        changed = sorted(set(created) | set(deleted) | set(modified))
        result = {
            "schema_version": 1,
            "result": "target_diff",
            "target_repo": str(root),
            "target_kind": target.get("target_kind"),
            "target_vcs": target.get("target_vcs"),
            "target_id": target.get("target_id"),
            "baseline_manifest_sha256": snapshot.get("manifest_sha256", ""),
            "current_manifest_sha256": sha256_json(current_files),
            "created_files": created,
            "modified_files": modified,
            "deleted_files": deleted,
            "changed_paths": changed,
        }
    result["errors"] = errors
    result["diff_sha256"] = sha256_json({
        "target_id": result.get("target_id"),
        "changed_paths": changed,
        "deleted_files": result.get("deleted_files", []),
        "created_files": created,
        "modified_files": modified,
        "baseline_dirty_paths": result.get("baseline_dirty_paths", []),
        "current_dirty_paths": result.get("current_dirty_paths", []),
    })
    return result


def facts_from_target_diff(target_diff, active_facts=None):
    facts = {
        "changed_files": {},
        "affected_layers": [],
        "has_tests": False,
        "has_docs": False,
        "evidence_commands": [],
        "warnings": [],
    }
    for rel in target_diff.get("changed_paths", []):
        if not non_empty_string(rel):
            continue
        facts["changed_files"][rel] = {
            "layer": layer_for_path(rel),
            "added": 0,
            "deleted": 0,
            "changed_lines": 0,
            "new_file": rel in set(target_diff.get("created_files") or []),
            "deleted_file": rel in set(target_diff.get("deleted_files") or []),
            "source": "target_diff",
        }
    if isinstance(active_facts, dict):
        facts["evidence_commands"] = list(active_facts.get("evidence_commands") or [])
        facts["warnings"] = list(active_facts.get("warnings") or [])
    update_diff_fact_derived(facts)
    return facts


def target_diff_from_active_facts(state, active_facts):
    target = state.get("target") if isinstance(state, dict) else {}
    changed = sorted((active_facts or {}).get("changed_files", {}))
    deleted = sorted(
        rel for rel, meta in ((active_facts or {}).get("changed_files") or {}).items()
        if isinstance(meta, dict) and meta.get("deleted_file")
    )
    payload = {
        "schema_version": 1,
        "result": "target_diff",
        "source": "active_diff_facts",
        "target_repo": target.get("target_repo", str(REPO_ROOT.resolve())),
        "target_kind": target.get("target_kind", "non_git"),
        "target_vcs": target.get("target_vcs", "non_git"),
        "target_id": target.get("target_id", ""),
        "changed_paths": changed,
        "deleted_files": deleted,
        "errors": [],
    }
    payload["diff_sha256"] = sha256_json({
        "target_id": payload.get("target_id"),
        "changed_paths": changed,
        "deleted_files": deleted,
        "source": "active_diff_facts",
    })
    return payload


def should_use_v1_target_diff(state):
    target = state.get("target") if isinstance(state, dict) else {}
    return (
        isinstance(target, dict)
        and not target.get("explicit")
        and target.get("target_vcs") == "non_git"
    )


def target_file_hash_entry(raw_path, target):
    root = pathlib.Path(target["target_repo"]).resolve()
    rel, err = target_relative_path(raw_path, root)
    if err:
        return {"path": str(raw_path), "status": "invalid", "reason": err}
    path = root / rel
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


def target_file_seal_items(target, changed_files):
    return [
        target_file_hash_entry(path, target)
        for path in sorted(
            p for p in (changed_files or [])
            if isinstance(p, str) and p.strip()
        )
    ]


def build_target_seal(state, receipt, target_diff):
    target = state.get("target") if isinstance(state, dict) else {}
    changed_files = receipt.get("changed_files") if isinstance(receipt, dict) else []
    payload = {
        "schema_version": 1,
        "repo_key": REPO_KEY,
        "task_id": state.get("task_id", ""),
        "target_repo": target.get("target_repo", ""),
        "target_kind": target.get("target_kind", ""),
        "target_vcs": target.get("target_vcs", ""),
        "target_id": target.get("target_id", ""),
        "target_diff_sha256": target_diff.get("diff_sha256", ""),
        "changed_paths": sorted(target_diff.get("changed_paths") or []),
        "deleted_files": sorted(target_diff.get("deleted_files") or []),
        "changed_files": target_file_seal_items(target, changed_files),
        "receipt_changed_files": sorted(changed_files or []),
        "limits": [
            "target SHA-256 seal only; not cryptographic code signing",
            "verify against the same target checkout/path and OS run state",
        ],
    }
    payload["target_seal_sha256"] = sha256_json(payload)
    return payload


def validate_target_receipt_coverage(receipt, target_diff):
    if not isinstance(receipt, dict):
        return ["receipt must be a JSON object"]
    receipt_files = {
        p for p in (receipt.get("changed_files") or [])
        if isinstance(p, str) and p.strip()
    }
    changed = set(target_diff.get("changed_paths") or [])
    missing = sorted(changed - receipt_files)
    if missing:
        return ["receipt missing target changed_files: " + ", ".join(missing)]
    return []


def request_target_footprint_policy(request, target):
    raw = ""
    if isinstance(request, dict):
        raw = str(
            request.get("target_footprint_policy")
            or request.get("footprint_policy")
            or ""
        ).strip()
    if raw in TARGET_FOOTPRINT_POLICIES:
        return raw
    if isinstance(target, dict) and target.get("explicit"):
        return "no_control_plane_files"
    return "repo_local_state_allowed"


def target_control_plane_path(rel):
    normalized = normalize_relative_path_text(str(rel or ""))
    if not normalized:
        return False
    parts = pathlib.PurePosixPath(normalized).parts
    if not parts:
        return False
    if parts[0] in CONTROL_PLANE_TARGET_DIRS:
        return True
    return normalized in CONTROL_PLANE_TARGET_FILES


def target_footprint_report(state, target_diff):
    contract = state.get("contract") if isinstance(state, dict) else {}
    target = state.get("target") if isinstance(state, dict) else {}
    policy = ""
    if isinstance(contract, dict):
        policy = str(contract.get("target_footprint_policy") or "").strip()
    if policy not in TARGET_FOOTPRINT_POLICIES:
        policy = "repo_local_state_allowed"
    changed_paths = sorted(
        str(path)
        for path in (target_diff.get("changed_paths") or [])
        if isinstance(path, str)
    )
    forbidden_changed = sorted(
        path for path in changed_paths
        if target_control_plane_path(path)
    )
    present = []
    blocking_present = []
    target_root = target.get("target_repo") if isinstance(target, dict) else ""
    if non_empty_string(target_root):
        root = pathlib.Path(target_root)
        for name in sorted(CONTROL_PLANE_TARGET_DIRS | CONTROL_PLANE_TARGET_FILES):
            try:
                if (root / name).exists():
                    present.append(name)
                    if name in CONTROL_PLANE_TARGET_DIRS:
                        blocking_present.append(name)
            except OSError:
                continue
    result = "target_footprint_passed"
    errors = []
    if policy == "no_control_plane_files" and forbidden_changed:
        result = "target_footprint_failed"
        errors.append(
            "controlled target changed Piloth/control-plane files: "
            + ", ".join(forbidden_changed)
        )
    if policy == "no_control_plane_files" and blocking_present:
        result = "target_footprint_failed"
        errors.append(
            "controlled target contains Piloth/control-plane directories: "
            + ", ".join(sorted(blocking_present))
        )
    return {
        "schema_version": 1,
        "result": result,
        "policy": policy,
        "changed_control_plane_paths": forbidden_changed,
        "present_control_plane_entries": present,
        "blocking_control_plane_entries": sorted(blocking_present),
        "errors": errors,
        "target_repo": target_root,
    }


def raw_edit_targets(hook_input):
    """Các path thô (chưa resolve) mà tool Edit/Write/MultiEdit sẽ ghi."""
    tool_input = (
        hook_input.get("tool_input")
        or hook_input.get("toolInput")
        or hook_input.get("input")
        or hook_input
    )
    raw_paths = []
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "notebook_path"):
            value = tool_input.get(key)
            if isinstance(value, str):
                raw_paths.append(value)
        for key in ("files", "paths"):
            value = tool_input.get(key)
            if isinstance(value, list):
                raw_paths.extend(v for v in value if isinstance(v, str))
    return raw_paths


def claude_config_dir():
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env and env.strip():
        return pathlib.Path(env.strip()).expanduser()
    return pathlib.Path.home() / ".claude"


def is_harness_plan_path(raw):
    """True nếu raw trỏ vào thư mục plan của harness (~/.claude/plans hoặc
    $CLAUDE_CONFIG_DIR/plans). Plan file là artifact của Claude Code, không phải
    code repo — contract-before-edit gate không quản, cho ghi kể cả khi harness
    không truyền permission_mode=="plan"."""
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        target = pathlib.Path(raw.strip()).expanduser().resolve()
        plans = (claude_config_dir() / "plans").resolve()
    except (OSError, ValueError, RuntimeError):
        return False
    return target == plans or plans in target.parents


def edit_paths_from_hook_input(hook_input):
    paths, errors = [], []
    for raw in raw_edit_targets(hook_input):
        rel, err = repo_relative_path(raw)
        if err:
            errors.append(err)
        elif rel not in paths:
            paths.append(rel)
    return paths, errors


def is_piloth_source_repo():
    return (
        (REPO_ROOT / ".claude-plugin" / "plugin.json").exists()
        and (REPO_ROOT / "scripts" / "stage.py").exists()
        and (REPO_ROOT / "scripts" / "build_manifest.py").exists()
    )


def is_source_installer_path(rel):
    return is_piloth_source_repo() and rel in SOURCE_INSTALLER_PATHS


def is_sensitive_runtime_path(rel):
    return rel in SENSITIVE_RUNTIME_PATHS or is_source_installer_path(rel)


def layer_for_path(rel):
    rel = normalize_relative_path_text(rel)
    if rel.startswith("pilothOS/rules/"):
        return "Rules"
    if rel.startswith("pilothOS/runtime/"):
        return "Runtime"
    if rel == "pilothOS/scripts/pilothos_installer.py" or is_source_installer_path(rel):
        return "Installer"
    if rel.startswith("pilothOS/scripts/") or rel.startswith("pilothOS/tools/"):
        return "Tools/Runtime"
    if rel.startswith("pilothOS/governance/"):
        return "Governance"
    if rel.startswith("pilothOS/evaluation/"):
        return "Evaluation"
    if rel.startswith("pilothOS/agents/"):
        return "Agents"
    if rel.startswith("pilothOS/agent-teams/"):
        return "Agent Teams"
    if rel.startswith("pilothOS/skills/"):
        return "Skills"
    if rel.startswith("pilothOS/memory/"):
        return "Memory"
    if rel.startswith("pilothOS/knowledge/"):
        return "Knowledge"
    if rel.startswith("adapters/") or rel.startswith("templates/") or rel.startswith("commands/"):
        return "Adapters"
    if rel.startswith("tests/") or rel.endswith(".test") or ".test." in rel:
        return "Tests"
    if rel.startswith("docs/") or rel.endswith(".md"):
        return "Docs"
    return "Consumer"


def path_parts(rel):
    return pathlib.PurePosixPath(rel.replace("\\", "/")).parts


def is_dependency_path(rel):
    return pathlib.PurePosixPath(rel).name in DEPENDENCY_FILE_NAMES


def is_ui_path(rel):
    rel = normalize_relative_path_text(rel)
    parts = path_parts(rel)
    suffix = pathlib.PurePosixPath(rel).suffix.lower()
    if "components" in parts or "ui" in parts:
        return True
    if rel.startswith(("app/", "pages/")):
        return True
    if rel.startswith("src/") and suffix in (".tsx", ".jsx"):
        return True
    return suffix in (".css", ".scss", ".html", ".htm")


def is_test_path(rel):
    layer = layer_for_path(rel)
    name = pathlib.PurePosixPath(rel).name.lower()
    return (
        layer == "Tests"
        or rel.startswith(("test/", "tests/", "__tests__/"))
        or ".test." in name
        or ".spec." in name
    )


def is_docs_path(rel):
    return layer_for_path(rel) == "Docs" or rel.startswith("docs/") or rel.endswith(".md")


def is_component_like_path(rel):
    rel = normalize_relative_path_text(rel)
    parts = path_parts(rel)
    suffix = pathlib.PurePosixPath(rel).suffix.lower()
    name = pathlib.PurePosixPath(rel).stem
    return (
        "components" in parts
        or (suffix in (".tsx", ".jsx", ".vue", ".svelte") and name[:1].isupper())
    )


def is_code_like_path(rel):
    suffix = pathlib.PurePosixPath(rel).suffix.lower()
    if is_test_path(rel) or is_docs_path(rel) or is_dependency_path(rel):
        return False
    return suffix in CODE_EXTENSIONS or layer_for_path(rel) not in ("Docs", "Tests")


def git_path_is_new(rel):
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", "--", rel],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
        return out.returncode != 0 and (REPO_ROOT / rel).exists()
    except Exception:
        return False


GENERATED_WARNING_PREFIXES = (
    "dependency file changed:",
    "new component-like file added:",
    "UI file changed without design system evidence:",
    "code changed without test/evidence",
    "large delta requires reuse discipline:",
)


def ensure_diff_fact_fields(facts):
    facts.setdefault("changed_files", {})
    facts.setdefault("affected_layers", [])
    facts.setdefault("has_tests", False)
    facts.setdefault("has_docs", False)
    facts.setdefault("evidence_commands", [])
    facts.setdefault("warnings", [])
    facts.setdefault("new_files", [])
    facts.setdefault("new_files_count", 0)
    facts.setdefault("total_added", 0)
    facts.setdefault("total_deleted", 0)
    facts.setdefault("largest_file_delta", {"path": "", "changed_lines": 0})
    facts.setdefault("dependency_files_changed", [])
    facts.setdefault("ui_files_changed", [])
    facts.setdefault("test_files_changed", [])
    facts.setdefault("docs_files_changed", [])
    facts.setdefault("component_like_files_changed", [])


def generated_warnings_removed(warnings):
    kept = []
    for warning in warnings:
        text = str(warning)
        if not any(text.startswith(prefix) for prefix in GENERATED_WARNING_PREFIXES):
            kept.append(warning)
    return kept


def add_generated_warning(warnings, text):
    if text not in warnings:
        warnings.append(text)


def update_diff_fact_derived(facts, contract=None):
    ensure_diff_fact_fields(facts)
    changed = facts.get("changed_files", {})
    paths = sorted(changed)
    for rel, meta in changed.items():
        meta.setdefault("layer", layer_for_path(rel))
        meta.setdefault("added", 0)
        meta.setdefault("deleted", 0)
        meta.setdefault("changed_lines", int(meta.get("added", 0)) + int(meta.get("deleted", 0)))
        meta.setdefault("new_file", git_path_is_new(rel))

    facts["affected_layers"] = sorted({meta.get("layer") for meta in changed.values() if meta.get("layer")})
    facts["has_tests"] = any(is_test_path(p) for p in paths)
    facts["has_docs"] = any(is_docs_path(p) for p in paths)
    facts["new_files"] = sorted(p for p, meta in changed.items() if meta.get("new_file"))
    facts["new_files_count"] = len(facts["new_files"])
    facts["total_added"] = sum(int(meta.get("added", 0)) for meta in changed.values())
    facts["total_deleted"] = sum(int(meta.get("deleted", 0)) for meta in changed.values())
    if changed:
        largest_path, largest_meta = max(
            changed.items(), key=lambda item: int(item[1].get("changed_lines", 0))
        )
        facts["largest_file_delta"] = {
            "path": largest_path,
            "changed_lines": int(largest_meta.get("changed_lines", 0)),
        }
    else:
        facts["largest_file_delta"] = {"path": "", "changed_lines": 0}
    facts["dependency_files_changed"] = sorted(p for p in paths if is_dependency_path(p))
    facts["ui_files_changed"] = sorted(p for p in paths if is_ui_path(p))
    facts["test_files_changed"] = sorted(p for p in paths if is_test_path(p))
    facts["docs_files_changed"] = sorted(p for p in paths if is_docs_path(p))
    facts["component_like_files_changed"] = sorted(p for p in paths if is_component_like_path(p))

    warnings = generated_warnings_removed(facts.get("warnings", []))
    if facts["dependency_files_changed"]:
        add_generated_warning(
            warnings,
            "dependency file changed: " + ", ".join(facts["dependency_files_changed"]),
        )
    new_components = sorted(p for p in facts["component_like_files_changed"] if p in facts["new_files"])
    if new_components:
        add_generated_warning(
            warnings,
            "new component-like file added: " + ", ".join(new_components),
        )
    if facts["ui_files_changed"] and not contract_has_ui_design_system_evidence(contract):
        add_generated_warning(
            warnings,
            "UI file changed without design system evidence: " + ", ".join(facts["ui_files_changed"]),
        )
    code_changed = any(is_code_like_path(p) for p in paths)
    if code_changed and not facts["has_tests"] and not facts.get("evidence_commands"):
        add_generated_warning(warnings, "code changed without test/evidence")
    largest = facts.get("largest_file_delta", {})
    if int(largest.get("changed_lines", 0)) >= 250:
        add_generated_warning(
            warnings,
            f"large delta requires reuse discipline: {largest.get('path')} ({largest.get('changed_lines')} lines)",
        )
    facts["warnings"] = warnings
    return facts


def validate_task_contract(contract):
    errors = []
    if not isinstance(contract, dict):
        return ["contract must be a JSON object"]
    missing = sorted(CONTRACT_REQUIRED_FIELDS - set(contract))
    if missing:
        errors.append(f"missing required fields: {', '.join(missing)}")
    if "mode" in contract and str(contract.get("mode")) not in OS_MODES:
        errors.append("mode must be lean, standard, or strict")
    if "operational_preset" in contract and not valid_operational_preset(operational_preset(contract)):
        errors.append("operational_preset must be light, standard, or strict")
    if not isinstance(contract.get("task_scope"), str) or not contract.get("task_scope", "").strip():
        errors.append("task_scope must be a non-empty string")
    for field in ("affected_layers", "allowed_paths", "expected_evidence"):
        value = contract.get(field)
        if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
            errors.append(f"{field} must be a non-empty list of strings")
    out = contract.get("out_of_scope_paths")
    if not isinstance(out, list) or any(not isinstance(x, str) or not x.strip() for x in out):
        errors.append("out_of_scope_paths must be a list of strings")
    for field in ("allowed_paths", "out_of_scope_paths"):
        for pattern in contract.get(field, []):
            if not path_pattern_is_safe(pattern):
                errors.append(f"{field} contains unsafe pattern: {pattern}")
    if contract_requires_context_evidence(contract):
        if not non_empty_string(contract.get("consumer_scope")):
            errors.append("consumer_scope must be a non-empty string for code/runtime/rules/adapter changes")
        errors.extend(validate_object_list(
            contract.get("context_evidence"),
            "context_evidence",
            ("source", "reason", "finding"),
        ))
        errors.extend(validate_reuse_evidence(contract.get("reuse_evidence")))
        decision_limits = contract.get("decision_limits")
        if (not isinstance(decision_limits, list) or not decision_limits
                or any(not non_empty_string(x) for x in decision_limits)):
            errors.append("decision_limits must be a non-empty list of strings for code/runtime/rules/adapter changes")
        errors.extend(validate_asset_routing(contract.get("consumer_asset_routing")))
    else:
        if "context_evidence" in contract:
            errors.extend(validate_object_list(
                contract.get("context_evidence"),
                "context_evidence",
                ("source", "reason", "finding"),
            ))
        if "reuse_evidence" in contract:
            errors.extend(validate_reuse_evidence(contract.get("reuse_evidence")))
        if "consumer_asset_routing" in contract:
            errors.extend(validate_asset_routing(contract.get("consumer_asset_routing")))
    if contract_requires_ui_design_system_evidence(contract):
        errors.extend(validate_ui_design_system_evidence(contract.get("ui_design_system_evidence")))
    elif "ui_design_system_evidence" in contract:
        errors.extend(validate_ui_design_system_evidence(contract.get("ui_design_system_evidence")))
    if contract_requires_energy_budget_reason(contract):
        if not non_empty_string(contract.get("energy_budget_reason")):
            errors.append("energy_budget_reason is required for broad scans/builds/full-suite evidence")
    return errors


def json_arg_or_stdin(argv, label):
    if argv:
        raw_arg = argv[0].strip()
        if raw_arg.startswith("{") or raw_arg.startswith("["):
            return json.loads(raw_arg), None
        path = pathlib.Path(argv[0])
        if not path.is_absolute():
            path = REPO_ROOT / path
        return json.loads(path.read_text(encoding="utf-8")), path
    if sys.stdin.isatty():
        raise ValueError(f"{label}: need JSON file argument or stdin")
    raw = sys.stdin.read()
    return json.loads(raw), None


def block_decision(reason):
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


