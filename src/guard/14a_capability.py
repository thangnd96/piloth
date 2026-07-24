# ---------------------------------------------------------------------------
# Capability & Authority kernel (T0).
#
# Reify "authority" thanh mot surface first-class, fail-closed, inspectable —
# ban Piloth cua AOS manifest-as-ACL + construction != activation. SSOT la
# pilothOS/governance/capability-manifest.json: moi capability (skill/rule/
# gate/adapter/guard-mode) khai mot authority block. Field thieu = quyen rong
# nhat (fail-closed), giong AOS "every field fails closed".
#
# Modes:
#   capability-list   liet ke capability + authority da resolve (fail-closed).
#   capability-check  validate manifest shape + fail-closed defaults.
#   authority-delta   in phan chenh quyen giua hai capability/authority de human
#                     duyet (khong tom tat long — AOS authority.md).
#
# construction != activation: guard KHONG BAO GIO tu cap quyen; day chi
# validate + trinh delta. Cap quyen la hanh vi human-approved, sealed.
# ---------------------------------------------------------------------------

CAPABILITY_MANIFEST = PILOTHOS_DIR / "governance" / "capability-manifest.json"

CAPABILITY_KINDS = {"skill", "rule", "gate", "adapter", "guard-mode"}
CAPABILITY_LAYERS = {
    "Identity", "Rules", "Memory", "Knowledge", "Skills", "Runtime", "Agents",
    "Tools", "Governance", "Evaluation", "Adapters", "AgentTeams",
}
# Fail-closed defaults: mot capability khong khai field authority nao thi field
# do la quyen rong nhat (list rong / writes_policy=False).
AUTHORITY_DEFAULTS = {
    "paths": [],
    "guard_modes": [],
    "entitlements": [],
    "enforcement_surface": [],
    "writes_policy": False,
}
AUTHORITY_LIST_FIELDS = ("paths", "guard_modes", "entitlements", "enforcement_surface")
CAPABILITY_TOP_FIELDS = {"id", "kind", "layer", "description", "source", "authority"}


def resolve_authority(cap):
    """Ap fail-closed defaults len authority block cua mot capability.

    Field khai sai kieu bi coi nhu default (fail-closed); capability-check se
    flag rieng. Luon tra ve du 5 field."""
    declared = {}
    if isinstance(cap, dict):
        raw = cap.get("authority")
        if isinstance(raw, dict):
            declared = raw
    resolved = {}
    for field in AUTHORITY_LIST_FIELDS:
        value = declared.get(field)
        resolved[field] = [str(x) for x in value] if isinstance(value, list) else []
    wp = declared.get("writes_policy")
    resolved["writes_policy"] = wp if isinstance(wp, bool) else False
    return resolved


def load_capability_manifest():
    data = load_json_file(CAPABILITY_MANIFEST)
    return data if isinstance(data, dict) else None


def capability_check_findings(manifest):
    """Validate shape cua capability-manifest. Tra (errors, warnings).

    errors = vi pham cung (chan capability-check PASS). warnings = advisory
    (field la, coverage partial...)."""
    errors = []
    warnings = []
    if not isinstance(manifest, dict):
        return (["capability-manifest.json thieu hoac khong phai JSON object"], [])
    if manifest.get("schema_version") != 1:
        errors.append("schema_version phai la 1")
    caps = manifest.get("capabilities")
    if not isinstance(caps, list):
        return (errors + ["capabilities phai la mot list"], warnings)
    coverage = manifest.get("coverage")
    if coverage not in {"partial", "full"}:
        warnings.append("coverage nen la 'partial' hoac 'full'")
    if coverage == "partial":
        warnings.append("coverage=partial: danh muc chua phu het; enforcement fail-closed chi bat khi coverage=full")
    seen_ids = set()
    for idx, cap in enumerate(caps):
        where = f"capabilities[{idx}]"
        if not isinstance(cap, dict):
            errors.append(f"{where} phai la object")
            continue
        cap_id = cap.get("id")
        if not non_empty_string(cap_id):
            errors.append(f"{where}.id thieu hoac rong")
        else:
            where = f"capability '{cap_id}'"
            if cap_id in seen_ids:
                errors.append(f"{where}: id trung lap")
            seen_ids.add(cap_id)
        if cap.get("kind") not in CAPABILITY_KINDS:
            errors.append(f"{where}.kind phai thuoc {sorted(CAPABILITY_KINDS)}")
        if cap.get("layer") not in CAPABILITY_LAYERS:
            errors.append(f"{where}.layer phai thuoc {sorted(CAPABILITY_LAYERS)}")
        for extra in set(cap) - CAPABILITY_TOP_FIELDS:
            warnings.append(f"{where}: field la '{extra}' bi bo qua")
        raw = cap.get("authority")
        if raw is not None:
            if not isinstance(raw, dict):
                errors.append(f"{where}.authority phai la object")
            else:
                for field in AUTHORITY_LIST_FIELDS:
                    if field in raw and not isinstance(raw[field], list):
                        errors.append(f"{where}.authority.{field} phai la list")
                if "writes_policy" in raw and not isinstance(raw["writes_policy"], bool):
                    errors.append(f"{where}.authority.writes_policy phai la bool")
                for extra in set(raw) - set(AUTHORITY_DEFAULTS):
                    warnings.append(f"{where}.authority: field la '{extra}' bi bo qua")
    return (errors, warnings)


def capability_manifest_status():
    """Tom tat trang thai manifest — dung cho self-check advisory + mode."""
    manifest = load_capability_manifest()
    if manifest is None:
        return {
            "ok": False,
            "present": False,
            "errors": ["capability-manifest.json khong ton tai"],
            "warnings": [],
            "capabilities": 0,
            "coverage": None,
        }
    errors, warnings = capability_check_findings(manifest)
    caps = manifest.get("capabilities")
    return {
        "ok": not errors,
        "present": True,
        "errors": errors,
        "warnings": warnings,
        "capabilities": len(caps) if isinstance(caps, list) else 0,
        "coverage": manifest.get("coverage"),
    }


def _manifest_path_from_argv(argv):
    for arg in argv or []:
        if not arg.startswith("-"):
            return pathlib.Path(arg)
    return CAPABILITY_MANIFEST


def capability_check(argv):
    path = _manifest_path_from_argv(argv)
    manifest = load_json_file(path)
    manifest = manifest if isinstance(manifest, dict) else None
    if manifest is None:
        json_print({
            "result": "capability_check_failed",
            "path": path.as_posix(),
            "errors": ["capability-manifest.json thieu hoac khong phai JSON object"],
        })
        return
    errors, warnings = capability_check_findings(manifest)
    caps = manifest.get("capabilities")
    json_print({
        "result": "capability_check_passed" if not errors else "capability_check_failed",
        "path": path.as_posix(),
        "schema_version": manifest.get("schema_version"),
        "coverage": manifest.get("coverage"),
        "capabilities_count": len(caps) if isinstance(caps, list) else 0,
        "errors": errors,
        "warnings": warnings,
    })


def capability_list(argv):
    path = _manifest_path_from_argv(argv)
    manifest = load_json_file(path)
    if not isinstance(manifest, dict):
        json_print({"result": "capability_list", "path": path.as_posix(), "capabilities": [], "note": "no manifest"})
        return
    caps = manifest.get("capabilities")
    caps = caps if isinstance(caps, list) else []
    listed = []
    for cap in caps:
        if not isinstance(cap, dict):
            continue
        listed.append({
            "id": cap.get("id"),
            "kind": cap.get("kind"),
            "layer": cap.get("layer"),
            "authority": resolve_authority(cap),
        })
    json_print({
        "result": "capability_list",
        "path": path.as_posix(),
        "coverage": manifest.get("coverage"),
        "count": len(listed),
        "capabilities": listed,
    })


def _load_authority_source(path):
    """Doc mot file thanh authority block da resolve.

    Chap nhan: capability object (co 'authority'), authority object thuan, hoac
    manifest 1-capability. Tra (authority_dict | None, error | None)."""
    data = load_json_file(path)
    if not isinstance(data, dict):
        return None, f"{path.as_posix()}: khong phai JSON object"
    if "authority" in data:
        return resolve_authority(data), None
    if set(data) & set(AUTHORITY_DEFAULTS):
        return resolve_authority({"authority": data}), None
    return None, f"{path.as_posix()}: khong tim thay 'authority' hoac field authority nao"


def compute_authority_delta(before, after):
    """So sanh hai authority block da resolve. widened=True khi co them quyen
    (path/entitlement/guard_mode/enforcement moi hoac writes_policy False->True)."""
    delta = {}
    widened = False
    for field in AUTHORITY_LIST_FIELDS:
        before_set = set(before.get(field, []))
        after_set = set(after.get(field, []))
        added = sorted(after_set - before_set)
        removed = sorted(before_set - after_set)
        delta[field] = {"added": added, "removed": removed}
        if added:
            widened = True
    wp_before = bool(before.get("writes_policy", False))
    wp_after = bool(after.get("writes_policy", False))
    delta["writes_policy"] = {"before": wp_before, "after": wp_after}
    if wp_after and not wp_before:
        widened = True
    delta["widened"] = widened
    return delta


def authority_delta(argv):
    files = [a for a in (argv or []) if not a.startswith("-")]
    if len(files) != 2:
        json_print({
            "result": "authority_delta_rejected",
            "errors": ["can dung 2 duong dan: <before.json> <after.json>"],
        })
        return
    before, before_err = _load_authority_source(pathlib.Path(files[0]))
    after, after_err = _load_authority_source(pathlib.Path(files[1]))
    src_errors = [e for e in (before_err, after_err) if e]
    if src_errors:
        json_print({"result": "authority_delta_rejected", "errors": src_errors})
        return
    delta = compute_authority_delta(before, after)
    json_print({
        "result": "authority_delta",
        "before": files[0],
        "after": files[1],
        "widened": delta["widened"],
        "delta": delta,
    })
