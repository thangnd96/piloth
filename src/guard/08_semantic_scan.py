# --------------------------------------------------------- semantic scan modes

def scan_request(argv, label):
    payload, _ = json_arg_or_stdin(argv, label)
    if not isinstance(payload, dict):
        raise ValueError(f"{label}: request must be a JSON object")
    changed = payload.get("changed_paths")
    allowed = payload.get("allowed_paths")
    if not isinstance(changed, list) or any(not isinstance(x, str) for x in changed):
        raise ValueError(f"{label}: changed_paths must be a list of strings")
    if not isinstance(allowed, list) or any(not isinstance(x, str) for x in allowed):
        raise ValueError(f"{label}: allowed_paths must be a list of strings")
    return payload


def token_parts(value):
    stem = pathlib.PurePosixPath(str(value)).stem
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", stem)
    return {
        part.lower()
        for part in re.split(r"[^A-Za-z0-9]+", spaced)
        if len(part) >= 3
    }


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


def extract_imports(text):
    imports = []
    patterns = (
        r"^\s*from\s+([A-Za-z0-9_./-]+)\s+import\b",
        r"^\s*import\s+([A-Za-z0-9_./-]+)",
        r"^\s*import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
        r"require\(['\"]([^'\"]+)['\"]\)",
    )
    for pattern in patterns:
        imports.extend(re.findall(pattern, text, flags=re.M))
    return sorted(set(imports))[:20]


def nearby_test_or_doc(rel):
    path = pathlib.PurePosixPath(rel)
    stem = path.stem.lower()
    parent = path.parent.as_posix()
    candidates = []
    for suffix in (".test.ts", ".test.tsx", ".spec.ts", ".spec.tsx", ".test.py", ".md"):
        if parent == ".":
            candidates.append(stem + suffix)
        else:
            candidates.append(parent + "/" + stem + suffix)
    return [candidate for candidate in candidates if (REPO_ROOT / candidate).exists()]


def candidate_identifiers(candidate):
    values = {
        str(candidate.get("id", "")),
        str(candidate.get("path", "")),
        str(candidate.get("candidate", "")),
    }
    return {value for value in values if value}


def reuse_review_decision(receipt, candidate):
    identifiers = candidate_identifiers(candidate)
    review = receipt.get("semantic_reuse_review") if isinstance(receipt, dict) else None
    if isinstance(review, dict):
        review = [review]
    if not isinstance(review, list):
        return ""
    for item in review:
        if not isinstance(item, dict):
            continue
        target = item.get("candidate") or item.get("candidate_id") or item.get("id") or item.get("path")
        if target in {"all", "*"} or str(target) in identifiers:
            return str(item.get("decision", ""))
    return ""


def receipt_duplicate_findings(receipt):
    findings = []
    if not isinstance(receipt, dict):
        return findings
    for candidate in candidates_from_receipt(
        receipt,
        ("semantic_reuse_candidates", "reuse_scan", "semantic_reuse_scan"),
    ):
        if candidate_confidence(candidate) < HIGH_CONFIDENCE_THRESHOLD:
            continue
        findings.append({
            "id": candidate.get("id"),
            "path": candidate.get("path"),
            "confidence": candidate_confidence(candidate),
            "review_decision": reuse_review_decision(receipt, candidate),
        })
    return findings


def prior_duplicate_finding_keys():
    keys = set()
    if not SCHEDULER_HISTORY.exists():
        return keys
    try:
        with open(SCHEDULER_HISTORY, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if item.get("repo_key") != REPO_KEY:
                    continue
                for finding in item.get("duplicate_findings", []):
                    if not isinstance(finding, dict):
                        continue
                    keys |= candidate_identifiers(finding)
    except (OSError, json.JSONDecodeError):
        return set()
    return keys


def reuse_learning_suggestions(candidates):
    high = [
        candidate for candidate in candidates
        if candidate_confidence(candidate) >= HIGH_CONFIDENCE_THRESHOLD
    ]
    if not high:
        return []
    prior = prior_duplicate_finding_keys()
    suggestions = []
    for candidate in high:
        repeated = bool(candidate_identifiers(candidate) & prior)
        path = candidate.get("path") or candidate.get("id")
        component_like = path and is_component_like_path(str(path))
        suggestions.append({
            "candidate": candidate.get("id") or path,
            "mistake_checked": "duplicated_component" if component_like else "duplicated_helper",
            "lesson_decision": "recorded" if repeated else "deferred",
            "promoted_to": "not_applicable",
            "reason": (
                "Repeated high-confidence reuse candidate from local history; record or promote lesson if new code proceeds."
                if repeated
                else "High-confidence reuse candidate exists; defer lesson unless the receipt chooses new code or duplication recurs."
            ),
            "repeated": repeated,
        })
    return suggestions


def reuse_scan_payload(payload):
    changed = [normalize_relative_path_text(p) for p in payload.get("changed_paths", [])]
    allowed = payload.get("allowed_paths") or ["**/*"]
    candidates = []
    seen = set()
    changed_tokens = set()
    changed_import_tokens = set()
    for rel in changed:
        changed_tokens |= token_parts(rel)
        changed_tokens |= token_parts(payload.get("task_signal", ""))
        changed_text = read_text_safe(REPO_ROOT / rel, limit=60000)
        for imported in extract_imports(changed_text):
            changed_import_tokens |= token_parts(imported)
    helper_signal = bool(changed_tokens & {
        "helper", "helpers", "util", "utils", "validator", "validate",
        "guard", "component",
    })
    for rel in candidate_files_within(allowed):
        if rel in changed:
            continue
        suffix = pathlib.PurePosixPath(rel).suffix.lower()
        if suffix not in CODE_EXTENSIONS and suffix not in {".md", ".json"}:
            continue
        tokens = token_parts(rel)
        overlap = changed_tokens & tokens
        if not overlap and not helper_signal:
            continue
        text = read_text_safe(REPO_ROOT / rel, limit=80000)
        symbols = extract_symbols(text)
        imports = extract_imports(text)
        symbol_tokens = set()
        for symbol in symbols:
            symbol_tokens |= token_parts(symbol)
        import_tokens = set()
        for imported in imports:
            import_tokens |= token_parts(imported)
        symbol_overlap = changed_tokens & symbol_tokens
        import_overlap = changed_import_tokens & (tokens | symbol_tokens | import_tokens)
        score = 0.0
        reason_bits = []
        if changed_tokens:
            score += min(0.65, 0.65 * (len(overlap) / max(1, len(changed_tokens))))
        if helper_signal and (tokens & {"helper", "helpers", "util", "utils", "validator", "validate", "guard"}):
            score += 0.25
            reason_bits.append("helper/validator naming matches task signal")
        if symbol_overlap:
            score += 0.20
            reason_bits.append("exported symbols overlap changed path terms")
        if import_overlap:
            score += 0.15
            reason_bits.append("imports overlap changed file dependencies")
        nearby = nearby_test_or_doc(rel)
        if nearby:
            score += 0.05
            reason_bits.append("nearby tests/docs exist: " + ", ".join(nearby[:3]))
        if overlap:
            reason_bits.append("filename terms overlap: " + ", ".join(sorted(overlap)))
        if not reason_bits and helper_signal:
            reason_bits.append("helper-like path is in allowed search scope")
            score = max(score, 0.40)
        confidence = min(0.95, round(score, 2))
        if confidence < 0.40:
            continue
        candidate = {
            "id": f"reuse:{stable_slug(rel)}",
            "path": rel,
            "confidence": confidence,
            "reason": "; ".join(reason_bits),
            "source": "filename/symbol scan",
            "suggested_decision": "reuse" if confidence >= HIGH_CONFIDENCE_THRESHOLD else "extend",
            "symbols": symbols,
            "imports": imports,
            "nearby_evidence": nearby,
        }
        if candidate["id"] not in seen:
            candidates.append(candidate)
            seen.add(candidate["id"])
    candidates.sort(key=lambda item: (-float(item["confidence"]), item["path"]))
    candidates = candidates[:25]
    return {
        "result": "reuse_scan",
        "task_signal": payload.get("task_signal", "not_applicable"),
        "changed_paths": changed,
        "allowed_paths": allowed,
        "candidates": candidates,
        "high_confidence_candidates": [
            item for item in candidates
            if float(item.get("confidence", 0)) >= HIGH_CONFIDENCE_THRESHOLD
        ],
        "learning_suggestions": reuse_learning_suggestions(candidates),
    }


def reuse_scan(argv):
    try:
        payload = scan_request(argv, "reuse-scan")
        json_print(reuse_scan_payload(payload))
    except Exception as e:
        json_print({"result": "reuse_scan_rejected", "errors": [str(e)]})


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


def ds_scan(argv):
    try:
        payload = scan_request(argv, "ds-scan")
        json_print(ds_scan_payload(payload))
    except Exception as e:
        json_print({"result": "ds_scan_rejected", "errors": [str(e)]})


