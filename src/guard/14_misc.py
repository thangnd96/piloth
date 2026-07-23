# ---------------------------------------------------------------- misc modes

def statusline():
    overdue = get_overdue_scopes()
    if overdue is None:
        print("PilothOS: khong tim thay registry")
        return
    if overdue:
        scopes = ", ".join(s.split(" (")[0] for s in overdue)
        print(f"\U0001F534 ROT OVERDUE: {scopes} — chạy rot review")
    # Healthy: không in gì.


def consumer_assets_registry_ok():
    if not CONSUMER_ASSETS.exists():
        return False, f"khong tim thay consumer asset registry tai {CONSUMER_ASSETS}"
    text = CONSUMER_ASSETS.read_text(encoding="utf-8", errors="replace")
    header = "Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes"
    if header not in text:
        return False, "consumer asset registry thieu header contract"
    required_terms = [
        "skill", "hook", "tool", "mcp", "command", "design-system",
        "doc", "convention", "test-runner", "build-runner",
        "low", "medium", "high",
        "always", "task-routed", "approval-required", "never-auto",
        "preserve", "index", "route", "wrap", "merge", "needs-judgment", "ignore",
    ]
    missing = [term for term in required_terms if term not in text]
    if missing:
        return False, "consumer asset registry thieu contract terms: " + ", ".join(missing)
    tools_index = PILOTHOS_DIR / "tools" / "index.md"
    if not tools_index.exists():
        return False, f"khong tim thay tools index tai {tools_index}"
    tools_text = tools_index.read_text(encoding="utf-8", errors="replace")
    if "pilothOS/runtime/consumer-assets.md" not in tools_text:
        return False, "tools index chua link consumer asset registry"
    if "Tool | Type | Capability | Config | Risk | Health Check | Approval | Timeout | Evidence Output" not in tools_text:
        return False, "tools index thieu tool registry contract"
    return True, "consumer asset registry hop le"


def self_host_required_manifest_paths():
    return {
        "pilothOS/runtime/self-hosting.md",
        "pilothOS/runtime/consumer-assets.md",
        "pilothOS/runtime/os-control-plane.md",
        "pilothOS/scripts/pilothos_guard.py",
        "pilothOS/scripts/pilothos_installer.py",
        "pilothOS/agent-teams/piloth-team.md",
        "pilothOS/memory/state/README.md",
    }


def self_host_check_result():
    checks = []

    def add_check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    required_files = [
        SELF_HOSTING_DOC,
        CONSUMER_ASSETS,
        PILOTHOS_DIR / "runtime" / "task-lifecycle.md",
        PILOTHOS_DIR / "runtime" / "energy-token-policy.md",
        PILOTHOS_DIR / "runtime" / "os-control-plane.md",
        PILOTHOS_DIR / "agent-teams" / "piloth-team.md",
        PILOTHOS_DIR / "scripts" / "pilothos_guard.py",
    ]
    for path in required_files:
        add_check(
            f"required file {path.relative_to(REPO_ROOT).as_posix()}",
            path.exists(),
            "exists" if path.exists() else "missing",
        )
    test_files = [
        REPO_ROOT / "tests" / "run_all.sh",
        REPO_ROOT / "tests" / "evaluation" / "run-tests.sh",
        REPO_ROOT / "tests" / "install" / "run-tests.sh",
        REPO_ROOT / "tests" / "lifecycle" / "run-tests.sh",
        REPO_ROOT / "tests" / "docs" / "run-tests.sh",
    ]
    if (REPO_ROOT / "tests").exists():
        for path in test_files:
            add_check(
                f"required source test {path.relative_to(REPO_ROOT).as_posix()}",
                path.exists(),
                "exists" if path.exists() else "missing",
            )
    else:
        add_check(
            "source test runners",
            True,
            "tests/ not shipped in staged consumer copy; source repo still requires tests/run_all.sh",
        )

    if SELF_HOSTING_DOC.exists():
        text = read_text_safe(SELF_HOSTING_DOC)
        for needle in ("contract-write", "pre-edit", "post-edit", "receipt-write", "tests/run_all.sh"):
            add_check(
                f"self-hosting doc mentions {needle}",
                needle in text,
                "found" if needle in text else "missing",
            )

    registered_modes = guard_registered_modes()
    for mode in SELF_HOST_REQUIRED_GUARD_MODES:
        add_check(
            f"guard mode {mode}",
            mode in registered_modes,
            "registered" if mode in registered_modes else "missing",
        )

    assets_ok, assets_msg = consumer_assets_registry_ok()
    add_check("consumer asset registry contract", assets_ok, assets_msg)

    manifest = manifest_paths()
    missing_manifest = sorted(self_host_required_manifest_paths() - manifest)
    add_check(
        "dist manifest self-host paths",
        not missing_manifest,
        "all required paths indexed" if not missing_manifest else "missing: " + ", ".join(missing_manifest),
    )

    changed = [
        p for p in git_changed_paths()
        if p.startswith(("pilothOS/", "tests/", "scripts/", "docs/", "adapters/", "templates/", "commands/"))
    ]
    if changed:
        receipt, _ = load_deliver_receipt({})
        facts = load_diff_facts({})
        contract, _ = load_task_contract({})
        receipt_errors = ["missing receipt"] if receipt is None else validate_deliver_receipt(receipt, contract, facts)
        add_check(
            "dogfood receipt for changed Piloth source",
            not receipt_errors,
            "receipt valid for current changed source" if not receipt_errors else "; ".join(receipt_errors),
        )
    else:
        add_check("dogfood receipt for changed Piloth source", True, "no changed Piloth source detected")

    errors = [check["detail"] for check in checks if not check["ok"]]
    return {
        "result": "self_host_check_passed" if not errors else "self_host_check_failed",
        "repo": str(REPO_ROOT),
        "checks": checks,
        "errors": errors,
    }


def self_host_check():
    json_print(self_host_check_result())


def production_scan_paths():
    paths = set(manifest_paths())
    for root in ("pilothOS", "docs", "tests", "scripts", "templates", "adapters", "commands"):
        base = REPO_ROOT / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                rel = path.relative_to(REPO_ROOT).as_posix()
                if "/memory/state/" not in rel and not any(part in SCAN_EXCLUDE_DIRS for part in path_parts(rel)):
                    paths.add(rel)
    return sorted(paths)


def production_noise_findings():
    findings = []
    stale_scan_exts = {".md", ".txt", ".json", ".toml", ".yaml", ".yml"}
    for rel in production_scan_paths():
        path = REPO_ROOT / rel
        if not path.exists() or not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix not in CODE_EXTENSIONS and suffix not in stale_scan_exts and suffix != "":
            continue
        text = read_text_safe(path, limit=300000)
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern in PRODUCTION_NOISE_PATTERNS:
                if pattern.search(line):
                    findings.append({"path": rel, "line": lineno, "term": pattern.pattern})
        if suffix in stale_scan_exts:
            for term in PRODUCTION_STALE_TERMS:
                if term in text:
                    findings.append({"path": rel, "line": 0, "term": term})
    return findings


def artifact_janitor_findings(root=REPO_ROOT):
    findings = []
    root = pathlib.Path(root).resolve()
    root_len = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = pathlib.Path(current)
        rel_parts = current_path.parts[root_len:]
        dirs.sort()
        files.sort()
        if any(part in ARTIFACT_JANITOR_SKIP_DIRS for part in rel_parts):
            dirs[:] = []
            continue
        pruned = []
        for dirname in list(dirs):
            rel = (current_path / dirname).relative_to(root).as_posix()
            if dirname in ARTIFACT_JANITOR_SKIP_DIRS:
                pruned.append(dirname)
                continue
            if dirname in ARTIFACT_JANITOR_DIR_NAMES:
                findings.append({"path": rel, "kind": "dir", "action": "remove"})
                pruned.append(dirname)
        dirs[:] = [d for d in dirs if d not in pruned]
        for filename in files:
            if filename in ARTIFACT_JANITOR_FILE_NAMES or filename.endswith(ARTIFACT_JANITOR_SUFFIXES):
                rel = (current_path / filename).relative_to(root).as_posix()
                findings.append({"path": rel, "kind": "file", "action": "remove"})
        if len(findings) >= ARTIFACT_JANITOR_MAX_FINDINGS:
            findings.append({
                "path": "",
                "kind": "limit",
                "action": "stop",
                "reason": f"finding limit reached: {ARTIFACT_JANITOR_MAX_FINDINGS}",
            })
            break
    return findings


def artifact_janitor_apply(findings, root=REPO_ROOT):
    actions = []
    root = pathlib.Path(root).resolve()
    for item in findings:
        if item.get("action") != "remove" or not non_empty_string(item.get("path")):
            continue
        rel, err = target_relative_path(item["path"], root)
        if err:
            actions.append({"path": item.get("path"), "status": "skipped", "reason": err})
            continue
        path = root / rel
        try:
            if item.get("kind") == "dir" and path.is_dir():
                shutil.rmtree(path)
                actions.append({"path": rel, "status": "removed"})
            elif item.get("kind") == "file" and path.is_file():
                path.unlink()
                actions.append({"path": rel, "status": "removed"})
            else:
                actions.append({"path": rel, "status": "missing"})
        except OSError as e:
            actions.append({"path": rel, "status": "failed", "reason": str(e)})
    return actions


def artifact_janitor_result(fix=False, root=REPO_ROOT):
    root = pathlib.Path(root).resolve()
    findings = artifact_janitor_findings(root)
    actions = []
    if fix and findings:
        actions = artifact_janitor_apply(findings, root)
        findings = artifact_janitor_findings(root)
    result = "artifact_janitor_passed"
    if findings:
        result = "artifact_janitor_failed"
    elif fix and actions:
        result = "artifact_janitor_cleaned"
    return {
        "result": result,
        "mode": "fix" if fix else "detect",
        "root": str(root),
        "findings_count": len(findings),
        "findings": findings,
        "actions": actions,
        "policy": {
            "default": "read_only_detect",
            "fix": "explicit_remove_known_local_artifacts_only",
        },
    }


def target_janitor_result(state, fix=False):
    target = state.get("target") if isinstance(state, dict) else None
    if not isinstance(target, dict) or not non_empty_string(target.get("target_repo")):
        return {
            "result": "artifact_janitor_skipped",
            "mode": "fix" if fix else "detect",
            "reason": "OS state has no target metadata",
        }
    return artifact_janitor_result(fix=fix, root=target["target_repo"])


def artifact_janitor(argv):
    args = list(argv)
    fix = False
    target = None
    i = 0
    errors = []
    while i < len(args):
        arg = args[i]
        if arg == "--fix":
            fix = True
        elif arg == "--target":
            if i + 1 >= len(args):
                errors.append("--target requires an absolute directory path")
                break
            i += 1
            target = args[i]
        elif arg.startswith("--target="):
            target = arg.split("=", 1)[1]
        else:
            errors.append(f"unsupported argument: {arg}")
        i += 1
    if errors:
        json_print({
            "result": "artifact_janitor_rejected",
            "errors": errors,
        })
        return
    root = REPO_ROOT
    if target:
        candidate = pathlib.Path(target).expanduser()
        if not candidate.is_absolute() or not candidate.exists() or not candidate.is_dir():
            json_print({
                "result": "artifact_janitor_rejected",
                "errors": ["--target must be an existing absolute directory path"],
            })
            return
        root = candidate.resolve()
    json_print(artifact_janitor_result(fix=fix, root=root))


