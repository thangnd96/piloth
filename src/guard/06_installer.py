# ---------------------------------------------------------------- installer

INIT_MARKER = PILOTHOS_DIR / ".initialized"
BACKUP_DIR = PILOTHOS_DIR / ".backup"
CORE_FILES = [PILOTHOS_DIR / "bootstrap.md", REGISTRY, CONSUMER_ASSETS,
              PILOTHOS_DIR / "PilothOS.md", REVIEW_LOG, LESSONS]
CONSUMER_ASSET_HINTS = ["package.json", "pyproject.toml", "go.mod", "Cargo.toml",
                        "pom.xml", "src", "app", "lib"]
# Adapter dirs do bản phân phối ship sẵn — chỉ là tài sản consumer khi chứa
# nội dung không thuộc PilothOS
ADAPTER_DIRS = [".claude", ".cursor", ".codex", ".antigravity"]
ADAPTER_CONFIGS = {
    ".claude": ("settings.json", "Claude adapter settings"),
    ".cursor": ("settings.json", "Cursor adapter settings"),
    ".codex": ("config.toml", "Codex adapter config"),
    ".antigravity": ("settings.json", "Antigravity adapter settings"),
}


def _non_pilothos_content(d):
    """File nào trong adapter dir KHÔNG thuộc bản phân phối PilothOS?"""
    known = ("pilothos", "piloth-team", "00-pilothos", "10-coding", "20-evidence",
             "30-layer", "settings.json", "config.toml", "README")
    found = []
    for f in d.rglob("*"):
        if not f.is_file():
            continue
        rel = str(f.relative_to(REPO_ROOT))
        if not any(k in rel for k in known):
            found.append(rel)
    return found


def audit_cell(value):
    return str(value).replace("|", ";").replace("\n", " ").strip()


def add_audit_row(rows, seen, asset, typ, capability, owner="consumer",
                  risk="low", handling="index"):
    if asset in seen:
        return
    seen.add(asset)
    rows.append({
        "asset": asset,
        "type": typ,
        "capability": capability,
        "owner": owner,
        "risk": risk,
        "handling": handling,
    })


def classify_adapter_asset(rel):
    if rel.startswith(".claude/commands/"):
        return "command", "agent command", "medium", "route"
    return "doc", "consumer adapter file", "medium", "index"


def pilothos_owned_text(text):
    lowered = text.lower()
    return "pilothos" in lowered or "pilothos_guard.py" in lowered


def adapter_config_row(adir):
    spec = ADAPTER_CONFIGS.get(adir)
    if not spec:
        return None
    filename, capability = spec
    path = REPO_ROOT / adir / filename
    if not path.exists() or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    owner = "piloth" if pilothos_owned_text(text) else "consumer"
    handling = "index" if owner == "piloth" else "preserve"
    return path.relative_to(REPO_ROOT).as_posix(), capability, owner, handling


def package_script_assets(rows, seen):
    package_json = REPO_ROOT / "package.json"
    if not package_json.exists():
        return
    add_audit_row(rows, seen, "package.json", "tool",
                  "Node package manifest/scripts", risk="medium",
                  handling="route")
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        add_audit_row(rows, seen, "package.json:scripts", "command",
                      "package scripts (invalid JSON, needs review)",
                      risk="medium", handling="needs-judgment")
        return
    scripts = data.get("scripts") if isinstance(data, dict) else None
    if not isinstance(scripts, dict):
        return
    for name, command in sorted(scripts.items()):
        if not isinstance(command, str):
            continue
        script_asset = f"package.json:scripts.{name}"
        lowered = name.lower()
        command_lower = command.lower()
        if "test" in lowered:
            add_audit_row(rows, seen, script_asset, "test-runner",
                          command, risk="low", handling="route")
        elif lowered in {"build", "compile"} or "build" in lowered:
            add_audit_row(rows, seen, script_asset, "build-runner",
                          command, risk="medium", handling="route")
        elif "lint" in lowered or "typecheck" in lowered or "check" in lowered:
            add_audit_row(rows, seen, script_asset, "command",
                          command, risk="low", handling="route")
        elif ("deploy" in lowered or "release" in lowered
              or command_looks_high_risk(command_lower)):
            add_audit_row(rows, seen, script_asset, "command",
                          command, risk="high", handling="wrap")
        else:
            add_audit_row(rows, seen, script_asset, "command",
                          command, risk="medium", handling="index")


def script_asset_kind(rel):
    lowered = rel.lower()
    if "test" in lowered:
        return "test-runner", "project test runner", "low"
    if "build" in lowered or "compile" in lowered:
        return "build-runner", "project build runner", "medium"
    if "lint" in lowered or "check" in lowered or "typecheck" in lowered:
        return "command", "project check command", "low"
    if "deploy" in lowered or "release" in lowered:
        return "command", "project release/deploy command", "high"
    return "command", "project script command", "medium"


def dynamic_script_assets(rows, seen):
    roots = [REPO_ROOT / "scripts", REPO_ROOT / "bin", REPO_ROOT / "tools"]
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name in IGNORE_NAMES:
                continue
            if path.suffix not in {".sh", ".py", ".js", ".mjs", ".ts"} and not os.access(path, os.X_OK):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            typ, capability, risk = script_asset_kind(rel)
            owner = "piloth" if layer_for_path(rel) == "Installer" else "consumer"
            add_audit_row(rows, seen, rel, typ, capability,
                          owner=owner, risk=risk,
                          handling="wrap" if risk == "high" else "route")
    tests_root = REPO_ROOT / "tests"
    if tests_root.exists() and tests_root.is_dir():
        for path in sorted(tests_root.rglob("run-tests.sh")):
            if path.is_file():
                rel = path.relative_to(REPO_ROOT).as_posix()
                add_audit_row(rows, seen, rel, "test-runner",
                              "project test runner", owner="piloth" if rel.startswith("tests/") else "consumer",
                              risk="low", handling="route")


def dynamic_agent_assets(rows, seen):
    skill_roots = [
        REPO_ROOT / ".agents" / "skills",
        REPO_ROOT / ".claude" / "skills",
        REPO_ROOT / ".codex" / "skills",
        REPO_ROOT / "skills",
    ]
    for root in skill_roots:
        if not root.exists() or not root.is_dir():
            continue
        for child in sorted(p for p in root.iterdir() if p.is_dir()):
            rel = child.relative_to(REPO_ROOT).as_posix()
            owner = "piloth" if child.name.startswith("piloth") else "consumer"
            add_audit_row(rows, seen, rel, "skill", "agent skill",
                          owner=owner, risk="medium",
                          handling="index" if owner == "piloth" else "route")
    command_roots = [
        REPO_ROOT / ".agents" / "commands",
        REPO_ROOT / ".claude" / "commands",
        REPO_ROOT / ".codex" / "commands",
        REPO_ROOT / "commands",
    ]
    for root in command_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            owner = "piloth" if "piloth" in path.name.lower() else "consumer"
            add_audit_row(rows, seen, rel, "command", "agent command",
                          owner=owner, risk="medium",
                          handling="index" if owner == "piloth" else "route")
    agent_roots = [
        REPO_ROOT / ".agents" / "agents",
        REPO_ROOT / ".claude" / "agents",
        REPO_ROOT / "agents",
    ]
    for root in agent_roots:
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            add_audit_row(rows, seen, rel, "doc", "agent definition",
                          risk="medium", handling="index")


def collect_consumer_asset_rows():
    rows, seen = [], set()

    for name in ("CLAUDE.md", "AGENTS.md"):
        path = REPO_ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            owner = "piloth" if "PilothOS" in text or "@pilothOS/bootstrap.md" in text else "consumer"
            handling = "preserve" if owner == "consumer" else "index"
            add_audit_row(rows, seen, name, "doc",
                          "agent instructions entry point", owner=owner,
                          risk="medium", handling=handling)

    for adir in ADAPTER_DIRS:
        d = REPO_ROOT / adir
        if not d.exists():
            continue
        extra = _non_pilothos_content(d)
        config = adapter_config_row(adir)
        adapter_owner = "consumer" if extra or (config and config[2] == "consumer") else "piloth"
        adapter_handling = "preserve" if adapter_owner == "consumer" else "index"
        adapter_capability = (
            "native agent adapter with consumer content"
            if adapter_owner == "consumer"
            else "native agent adapter bridge"
        )
        add_audit_row(rows, seen, adir, "tool",
                      adapter_capability, owner=adapter_owner,
                      risk="medium", handling=adapter_handling)
        if extra:
            for rel in extra[:20]:
                typ, capability, risk, handling = classify_adapter_asset(rel)
                add_audit_row(rows, seen, rel, typ,
                              capability, risk=risk,
                              handling=handling)
        if config:
            rel, capability, owner, handling = config
            add_audit_row(rows, seen, rel, "tool",
                          capability, owner=owner, risk="medium",
                          handling=handling)
        settings = d / "settings.json"
        if settings.exists():
            try:
                data = json.loads(settings.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                add_audit_row(rows, seen, f"{adir}/settings.json", "hook",
                              "adapter settings invalid JSON", risk="medium",
                              handling="needs-judgment")
                continue
            if isinstance(data, dict) and data.get("hooks"):
                add_audit_row(rows, seen, f"{adir}/settings.json:hooks", "hook",
                              "native hooks", risk="medium", handling="merge")
        skills_dir = d / "skills"
        if skills_dir.exists():
            for child in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
                rel = child.relative_to(REPO_ROOT).as_posix()
                owner = "piloth" if child.name.startswith("piloth") else "consumer"
                handling = "route" if owner == "consumer" else "index"
                add_audit_row(rows, seen, rel, "skill",
                              "agent skill", owner=owner,
                              risk="medium", handling=handling)

    for rel in (".mcp.json", "mcp.json", ".cursor/mcp.json", ".claude/mcp.json"):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "mcp",
                          "MCP/tool configuration", risk="medium",
                          handling="route")

    for rel in ("scripts/test.sh", "scripts/test", "scripts/build.sh",
                "scripts/lint.sh", "Makefile"):
        if (REPO_ROOT / rel).exists():
            typ = "test-runner" if "test" in rel else "build-runner" if "build" in rel or rel == "Makefile" else "command"
            risk = "low" if typ == "test-runner" else "medium"
            add_audit_row(rows, seen, rel, typ,
                          "project script/runner", risk=risk,
                          handling="route")
    dynamic_script_assets(rows, seen)
    dynamic_agent_assets(rows, seen)

    # Piloth is also a first-class consumer of PilothOS. These rows let the
    # self-hosted repo route its own guard, installer, test, docs and runtime
    # assets through the same discovery path used for external consumers.
    for rel, capability in (
        ("pilothOS/scripts/pilothos_guard.py", "PilothOS guard/runtime CLI"),
        ("pilothOS/scripts/pilothos_installer.py", "PilothOS installer engine"),
        ("scripts/stage.py", "distribution staging tool"),
        ("scripts/build_manifest.py", "distribution manifest builder"),
    ):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "tool", capability,
                          owner="piloth", risk="medium", handling="route")

    for rel in (
        "tests/run_all.sh",
        "tests/evaluation/run-tests.sh",
        "tests/install/run-tests.sh",
        "tests/lifecycle/run-tests.sh",
        "tests/docs/run-tests.sh",
        "tests/engine/run-tests.sh",
    ):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "test-runner",
                          "PilothOS self-host test suite",
                          owner="piloth", risk="low", handling="route")

    for rel, capability in (
        ("docs", "Piloth user-facing documentation"),
        ("pilothOS/runtime", "PilothOS runtime contract docs"),
        ("pilothOS/rules", "PilothOS rule source of truth"),
        ("pilothOS/evaluation", "PilothOS quality gate docs"),
        ("pilothOS/agent-teams", "PilothOS team definitions"),
    ):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "doc", capability,
                          owner="piloth", risk="low", handling="index")

    package_script_assets(rows, seen)

    for rel in ("design-system", "docs/design-system.md", "tokens",
                "src/tokens", "components", "src/components", "ui", "src/ui"):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "design-system",
                          "UI components/tokens/patterns", risk="medium",
                          handling="route")

    for rel in ("CONTRIBUTING.md", "docs/conventions.md", ".editorconfig",
                ".prettierrc", ".prettierrc.json", "eslint.config.js",
                ".eslintrc", ".eslintrc.json", "tsconfig.json"):
        if (REPO_ROOT / rel).exists():
            add_audit_row(rows, seen, rel, "convention",
                          "project convention/config", risk="low",
                          handling="index")

    return sorted(rows, key=lambda r: r["asset"])


def audit_consumer_assets():
    rows = collect_consumer_asset_rows()
    print("| Asset | Type | Capability | Owner | Risk | Proposed Piloth Handling |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        print(
            "| {asset} | {type} | {capability} | {owner} | {risk} | {handling} |".format(
                asset=audit_cell(row["asset"]),
                type=audit_cell(row["type"]),
                capability=audit_cell(row["capability"]),
                owner=audit_cell(row["owner"]),
                risk=audit_cell(row["risk"]),
                handling=audit_cell(row["handling"]),
            )
        )
    if not rows:
        print("| _none detected_ | doc | no consumer asset signal | consumer | low | ignore |")


def registry_load_when(row):
    handling = row.get("handling")
    risk = row.get("risk")
    if handling in {"wrap", "needs-judgment"} or risk == "high":
        return "approval-required"
    if handling == "ignore":
        return "never-auto"
    return "task-routed"


def registry_health_check(row):
    asset = row.get("asset", "")
    typ = row.get("type", "")
    if asset.endswith(":hooks") or typ == "hook":
        return "settings JSON parses"
    if typ == "mcp":
        return "config exists; list tools succeeds"
    if asset.startswith("package.json:scripts."):
        return "package JSON parses"
    if typ in {"test-runner", "build-runner", "command"}:
        return "command exists or package script defined"
    return "path exists"


def registry_notes(row):
    handling = row.get("handling")
    if handling == "wrap":
        return "Route through approval/tool-control boundary"
    if handling == "merge":
        return "Merge by engine semantics; preserve consumer entries first"
    if handling == "preserve":
        return "Consumer-owned; do not move or overwrite"
    if handling == "needs-judgment":
        return "Stop for user/model judgment before changing behavior"
    return "Generated by audit-assets; confirm during brownfield audit"


def registry_consumer_assets():
    rows = collect_consumer_asset_rows()
    print("| Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes |")
    print("|---|---|---|---|---|---|---|---|---|")
    if not rows:
        print("| _none detected_ | doc | consumer | no consumer asset signal | N/A | low | never-auto | N/A | Nothing to route |")
        return
    for row in rows:
        print(
            "| {asset} | {type} | {owner} | {capability} | {config_path} | {risk} | {load_when} | {health_check} | {notes} |".format(
                asset=audit_cell(row["asset"]),
                type=audit_cell(row["type"]),
                owner=audit_cell(row["owner"]),
                capability=audit_cell(row["capability"]),
                config_path=audit_cell(row["asset"]),
                risk=audit_cell(row["risk"]),
                load_when=audit_cell(registry_load_when(row)),
                health_check=audit_cell(registry_health_check(row)),
                notes=audit_cell(registry_notes(row)),
            )
        )


def asset_id_for_row(row):
    return f"{row.get('type', 'asset')}:{stable_slug(row.get('asset', 'asset'))}"


def manifest_paths():
    manifest = PILOTHOS_DIR / "dist-manifest.json"
    data = load_json_file(manifest)
    if not isinstance(data, dict):
        return set()
    files = data.get("files")
    if not isinstance(files, list):
        return set()
    return {item.get("path") for item in files if isinstance(item, dict) and item.get("path")}


def normalize_asset_row(row):
    confidence = 0.95
    if row.get("handling") in {"needs-judgment", "wrap"}:
        confidence = 0.85
    if row.get("owner") == "consumer":
        confidence = min(confidence, 0.90)
    asset = row.get("asset", "")
    typ = row.get("type", "")
    signals = []
    if asset.startswith("package.json:scripts."):
        signals.append("package-script")
    if asset.endswith(":hooks") or typ == "hook":
        signals.append("hook-config")
    if typ == "mcp":
        signals.append("mcp-config")
    if typ == "design-system":
        signals.append("design-system-path")
    if typ in {"test-runner", "build-runner"}:
        signals.append("runner")
    if asset.startswith("pilothOS/") or row.get("owner") == "piloth":
        signals.append("piloth-owned")
    return {
        "id": asset_id_for_row(row),
        "asset": asset,
        "type": typ,
        "owner": row.get("owner", "consumer"),
        "capability": row.get("capability", ""),
        "config_path": asset,
        "risk": row.get("risk", "low"),
        "load_when": registry_load_when(row),
        "health_check": registry_health_check(row),
        "handling": row.get("handling", "index"),
        "detected_at": "repository-scan",
        "last_health": "unknown",
        "status": "unknown",
        "confidence": confidence,
        "detected_signals": signals or ["path"],
    }


def scanned_asset_rows():
    rows = [normalize_asset_row(row) for row in collect_consumer_asset_rows()]
    return sorted(rows, key=lambda row: (row["type"], row["asset"], row["id"]))


def asset_markdown(rows):
    lines = [
        "| Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Detected At | Last Health | Status | Confidence | Notes |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    if not rows:
        lines.append("| _none detected_ | doc | consumer | no asset signal | N/A | low | never-auto | N/A | repository-scan | unknown | unknown | 0.00 | Nothing to route |")
        return "\n".join(lines)
    for row in rows:
        lines.append(
            "| {asset} | {type} | {owner} | {capability} | {config_path} | {risk} | {load_when} | {health_check} | {detected_at} | {last_health} | {status} | {confidence:.2f} | {notes} |".format(
                asset=audit_cell(row.get("asset", "")),
                type=audit_cell(row.get("type", "")),
                owner=audit_cell(row.get("owner", "")),
                capability=audit_cell(row.get("capability", "")),
                config_path=audit_cell(row.get("config_path", "")),
                risk=audit_cell(row.get("risk", "")),
                load_when=audit_cell(row.get("load_when", "")),
                health_check=audit_cell(row.get("health_check", "")),
                detected_at=audit_cell(row.get("detected_at", "")),
                last_health=audit_cell(row.get("last_health", "")),
                status=audit_cell(row.get("status", "")),
                confidence=float(row.get("confidence", 0.0)),
                notes=audit_cell(registry_notes(row)),
            )
        )
    return "\n".join(lines)


def asset_scan(argv):
    fmt = "json"
    args = list(argv)
    if "--format" in args:
        i = args.index("--format")
        if i + 1 >= len(args):
            json_print({"result": "asset_scan_rejected", "errors": ["--format requires json or md"]})
            return
        fmt = args[i + 1]
    for arg in args:
        if arg.startswith("--format="):
            fmt = arg.split("=", 1)[1]
    rows = scanned_asset_rows()
    if fmt == "md":
        print(asset_markdown(rows))
    elif fmt == "json":
        json_print({"result": "asset_scan", "assets": rows})
    else:
        json_print({"result": "asset_scan_rejected", "errors": ["--format must be json or md"]})


def asset_path_from_id(asset):
    if not isinstance(asset, str):
        return ""
    if asset.startswith("package.json:scripts."):
        return "package.json"
    if ":" in asset:
        return asset.split(":", 1)[0]
    return asset


def high_risk_health_requires_approval(row):
    if row.get("risk") != "high":
        return False
    if non_empty_string(os.environ.get("PILOTHOS_APPROVAL_EVIDENCE")):
        return False
    contract, _ = load_task_contract({})
    haystack = contract_tool_text(contract)
    return "approval" not in haystack


def health_for_asset(row):
    row = dict(row)
    asset = row.get("asset", "")
    status = "unknown"
    reason = "no deterministic low-risk health check available"
    if high_risk_health_requires_approval(row):
        status = "needs_approval"
        reason = "high-risk asset health requires active contract approval evidence"
    elif asset.startswith("package.json:scripts."):
        path = REPO_ROOT / "package.json"
        if not path.exists():
            status, reason = "missing", "package.json missing"
        else:
            data = load_json_file(path)
            script = asset.rsplit(".", 1)[-1]
            if not isinstance(data, dict):
                status, reason = "failed", "package.json does not parse"
            elif isinstance(data.get("scripts"), dict) and script in data["scripts"]:
                status, reason = "healthy", f"package script exists: {script}"
            else:
                status, reason = "missing", f"package script missing: {script}"
    else:
        path = REPO_ROOT / asset_path_from_id(asset)
        if path.exists():
            if path.suffix == ".json" or asset.endswith(":hooks") or row.get("type") == "mcp":
                target = path if path.is_file() else path / "settings.json"
                if target.exists() and target.is_file():
                    try:
                        json.loads(target.read_text(encoding="utf-8"))
                        status, reason = "healthy", f"JSON parses: {target.relative_to(REPO_ROOT).as_posix()}"
                    except json.JSONDecodeError as e:
                        status, reason = "failed", f"JSON parse failed: {e}"
                else:
                    status, reason = "healthy", "path exists"
            else:
                status, reason = "healthy", "path exists"
        else:
            status, reason = "missing", "path missing"

    manifest = manifest_paths()
    manifest_status = "not_applicable"
    if asset.startswith("pilothOS/") and manifest:
        manifest_status = "indexed" if (
            asset in manifest
            or any(str(item).startswith(asset.rstrip("/") + "/") for item in manifest)
        ) else "missing"
    if (
        status == "healthy"
        and asset.startswith("pilothOS/")
        and manifest
        and asset not in manifest
        and not any(str(item).startswith(asset.rstrip("/") + "/") for item in manifest)
    ):
        status = "stale"
        reason = "Piloth-owned asset is missing from dist-manifest.json"

    row["status"] = status
    row["last_health"] = "repository-scan"
    row["health_reason"] = reason
    row["manifest_status"] = manifest_status
    return row


def asset_health(argv):
    rows = scanned_asset_rows()
    by_id = {row["id"]: row for row in rows}
    by_asset = {row["asset"]: row for row in rows}
    target = argv[0] if argv else "--all"
    if target == "--all":
        json_print({
            "result": "asset_health",
            "assets": [health_for_asset(row) for row in rows],
        })
        return
    row = by_id.get(target) or by_asset.get(target)
    if not row:
        json_print({
            "result": "asset_health_rejected",
            "errors": [f"unknown asset: {target}"],
        })
        return
    json_print({"result": "asset_health", "asset": health_for_asset(row)})


def asset_sync(argv):
    source = None
    args = list(argv)
    if "--source" in args:
        i = args.index("--source")
        if i + 1 < len(args):
            source = args[i + 1]
    for arg in args:
        if arg.startswith("--source="):
            source = arg.split("=", 1)[1]
    if not source:
        json_print({"result": "asset_sync_rejected", "errors": ["--source scan.json is required"]})
        return
    path = pathlib.Path(source)
    if not path.is_absolute():
        path = REPO_ROOT / path
    data = load_json_file(path)
    if isinstance(data, dict):
        rows = data.get("assets")
    else:
        rows = data
    if not isinstance(rows, list):
        json_print({"result": "asset_sync_rejected", "errors": ["source must contain an assets array"]})
        return
    section = (
        ASSET_SYNC_START + "\n"
        + asset_markdown(rows) + "\n"
        + ASSET_SYNC_END
    )
    if CONSUMER_ASSETS.exists():
        text = CONSUMER_ASSETS.read_text(encoding="utf-8")
    else:
        text = "# Consumer Asset Registry\n\n"
    if ASSET_SYNC_START in text and ASSET_SYNC_END in text:
        pattern = re.compile(
            re.escape(ASSET_SYNC_START) + r".*?" + re.escape(ASSET_SYNC_END),
            re.S,
        )
        text = pattern.sub(section, text)
    else:
        text = text.rstrip() + "\n\n## Generated Registry\n\n" + section + "\n"
    CONSUMER_ASSETS.write_text(text, encoding="utf-8")
    json_print({
        "result": "asset_synced",
        "path": CONSUMER_ASSETS.relative_to(REPO_ROOT).as_posix(),
        "asset_count": len(rows),
        "preserved_manual_sections": True,
    })


def normalize_task_signal(value):
    raw = str(value or "").strip().lower()
    aliases = {
        "ui": "ui/component",
        "component": "ui/component",
        "backend": "api/backend",
        "api": "api/backend",
        "bug": "bug fix",
        "bugfix": "bug fix",
        "release": "release/deploy",
        "deploy": "release/deploy",
        "tool": "tool/mcp",
        "mcp": "tool/mcp",
        "n/a": "not_applicable",
        "none": "not_applicable",
    }
    return aliases.get(raw, raw)


# Context docs only needed once standard/strict evidence (quality gates,
# consumer-asset routing) actually runs. lean/micro tasks skip them to cut
# context tokens without losing the context needed to do the work correctly.
LEAN_DROPPED_CONTEXT = frozenset({
    "evaluation/quality-gates.md",
    "runtime/consumer-assets.md",
})
# lazy rot: lean/micro skip loading the full rot registry table and rely on the
# compact `rot-status` command instead (it only surfaces overdue scopes).
LEAN_DROPPED_BOOTSTRAP = frozenset({
    "rot/registry.md",
})
# micro (throwaway / pass-through work) additionally skips the Constitution — a
# script with no architecture impact does not need the full layer contract.
MICRO_DROPPED_BOOTSTRAP = LEAN_DROPPED_BOOTSTRAP | frozenset({"PilothOS.md"})


def context_mode_from_payload(payload):
    """micro | lean | standard | strict from payload.mode; default standard."""
    raw = str((payload or {}).get("mode", "")).strip().lower()
    if raw == "micro":
        return "micro"
    if raw in ("lean", "light"):
        return "lean"
    if raw == "strict":
        return "strict"
    return "standard"


def apply_context_mode(files, mode):
    """Drop standard-only context docs for lean/micro; keep order otherwise."""
    if mode in ("lean", "micro"):
        return [f for f in files if f not in LEAN_DROPPED_CONTEXT]
    return list(files)


def apply_bootstrap_mode(files, mode):
    """lean uses lazy rot; micro also skips the Constitution."""
    if mode == "micro":
        return [f for f in files if f not in MICRO_DROPPED_BOOTSTRAP]
    if mode == "lean":
        return [f for f in files if f not in LEAN_DROPPED_BOOTSTRAP]
    return list(files)


def route_task_payload(payload):
    if not isinstance(payload, dict):
        return {"result": "route_rejected", "errors": ["route payload must be a JSON object"]}
    key = normalize_task_signal(payload.get("task_signal"))
    route = TASK_SIGNAL_ROUTES.get(key)
    if not route:
        return {
            "result": "route_rejected",
            "errors": [
                "task_signal must be one of: "
                + ", ".join(sorted(r["task_signal"] for r in TASK_SIGNAL_ROUTES.values()))
            ],
        }

    asset_types = set(route["asset_types"])
    all_rows = collect_consumer_asset_rows()
    detected = [
        row for row in all_rows
        if row.get("type") in asset_types
    ]
    skipped_assets = [
        {
            "asset": row["asset"],
            "type": row["type"],
            "risk": row["risk"],
            "decision": "skipped",
            "reason": f"{row['type']} is not routed for {route['task_signal']}",
        }
        for row in all_rows
        if row.get("type") not in asset_types
    ]
    asset_rows = []
    routing = []
    context_evidence = []
    for row in detected:
        load_when = registry_load_when(row)
        health = health_for_asset(normalize_asset_row(row))
        health_status = health.get("status")
        if health_status == "healthy":
            decision = "approval_required" if load_when == "approval-required" else "loaded"
            routing_reason = f"{row['asset']} matched {route['task_signal']} routing"
        elif health_status == "needs_approval":
            decision = "approval_required"
            routing_reason = f"{row['asset']} matched but health requires approval: {health.get('health_reason')}"
        elif health_status in {"missing", "stale"}:
            decision = "skipped"
            routing_reason = f"{row['asset']} matched but health is {health_status}: {health.get('health_reason')}"
        else:
            decision = "skipped"
            routing_reason = f"{row['asset']} matched but health is {health_status}: {health.get('health_reason')}"
        asset_rows.append({
            "asset": row["asset"],
            "type": row["type"],
            "risk": row["risk"],
            "handling": row["handling"],
            "load_when": load_when,
            "health_status": health_status,
            "health_reason": health.get("health_reason"),
        })
        routing.append({
            "task_signal": route["task_signal"],
            "asset_type": row["type"],
            "decision": decision,
            "reason": routing_reason,
        })
        context_evidence.append({
            "source": row["asset"],
            "reason": f"{row['type']} matched {route['task_signal']} routing",
            "finding": f"{row['capability']} (health: {health_status})",
        })
    if not routing:
        routing.append({
            "task_signal": route["task_signal"],
            "asset_type": "not_applicable",
            "decision": "not_applicable",
            "reason": "no matching consumer asset detected by deterministic audit",
        })
        context_evidence.append({
            "source": "runtime/consumer-assets.md",
            "reason": f"{route['task_signal']} routing lookup",
            "finding": "no matching consumer asset detected by deterministic audit",
        })

    mode = context_mode_from_payload(payload)
    index_first = apply_context_mode(
        ["runtime/consumer-assets.md", "runtime/context-loading.md"], mode)
    context_layers = apply_context_mode(list(route["context_layers"]), mode)
    return {
        "result": "route_suggested",
        "task_signal": route["task_signal"],
        "context_mode": mode,
        "load_policy": route["load_policy"],
        "index_first": index_first,
        "context_layers": context_layers,
        "inspect_asset_types": list(route["asset_types"]),
        "detected_assets": asset_rows,
        "skipped_assets": skipped_assets,
        "context_evidence": context_evidence,
        "consumer_asset_routing": routing,
    }


def route_task(argv):
    try:
        payload, _ = json_arg_or_stdin(argv, "route-task")
    except Exception as e:
        json_print({"result": "route_rejected", "errors": [str(e)]})
        return
    json_print(route_task_payload(payload))


