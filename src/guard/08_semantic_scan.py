# --------------------------------------------------------- semantic scan modes

def candidate_files_within(patterns):
    files = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SCAN_EXCLUDE_DIRS for part in path.parts):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        if path_matches(patterns, rel):
            files.append(rel)
    return sorted(files)


def extract_symbols(text):
    symbols = []
    patterns = (
        r"^\s*def\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*export\s+(?:function|const|class)\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"^\s*(?:function|const)\s+([A-Za-z_][A-Za-z0-9_]*)",
    )
    for pattern in patterns:
        symbols.extend(re.findall(pattern, text, flags=re.M))
    return sorted(set(symbols))[:12]


def ds_scan_payload(payload):
    allowed = payload.get("allowed_paths") or ["**/*"]
    files = candidate_files_within(allowed)
    component_candidates = []
    token_candidates = []
    pattern_candidates = []
    seen = set()
    for rel in files:
        path = pathlib.PurePosixPath(rel)
        parts = set(path.parts)
        name = path.name.lower()
        suffix = path.suffix.lower()
        text = ""
        if suffix in {".css", ".scss", ".md", ".tsx", ".ts", ".jsx", ".js", ".json"}:
            text = read_text_safe(REPO_ROOT / rel, limit=60000)
        symbols = extract_symbols(text) if text else []
        css_variables = sorted(set(re.findall(r"--[A-Za-z0-9_-]+", text)))[:20]
        if ("components" in parts or "ui" in parts) and suffix in {".tsx", ".jsx", ".vue", ".svelte", ".md"}:
            key = f"component:{rel}"
            if key not in seen:
                component_candidates.append({
                    "id": key,
                    "path": rel,
                    "confidence": 0.90,
                    "reason": "component/UI path detected"
                    + (f"; symbols: {', '.join(symbols[:5])}" if symbols else ""),
                    "source": "path/symbol scan",
                    "suggested_decision": "reuse",
                    "symbols": symbols,
                })
                seen.add(key)
        if (
            "tokens" in parts or "theme" in name or "token" in name
            or name in {"tailwind.config.js", "tailwind.config.ts"}
            or css_variables
        ):
            key = f"token:{rel}"
            if key not in seen:
                token_candidates.append({
                    "id": key,
                    "path": rel,
                    "confidence": 0.88,
                    "reason": "token/theme/CSS variable signal detected",
                    "source": "path/content scan",
                    "suggested_decision": "reuse",
                    "css_variables": css_variables,
                })
                seen.add(key)
        if (
            "storybook" in rel.lower()
            or "design-system" in rel.lower()
            or "ui-design-system" in rel.lower()
            or "design system" in text.lower()
            or "component catalog" in text.lower()
        ):
            key = f"pattern:{rel}"
            if key not in seen:
                pattern_candidates.append({
                    "id": key,
                    "path": rel,
                    "confidence": 0.86,
                    "reason": "design-system docs/storybook signal detected",
                    "source": "path/content scan",
                    "suggested_decision": "reuse",
                    "symbols": symbols,
                })
                seen.add(key)
    return {
        "result": "ds_scan",
        "task_signal": payload.get("task_signal", "not_applicable"),
        "changed_paths": payload.get("changed_paths", []),
        "allowed_paths": allowed,
        "component_candidates": sorted(component_candidates, key=lambda item: item["path"])[:25],
        "token_candidates": sorted(token_candidates, key=lambda item: item["path"])[:25],
        "pattern_candidates": sorted(pattern_candidates, key=lambda item: item["path"])[:25],
    }


