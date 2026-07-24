# ---------------------------------------------------------------------------
# Piloth Forge (T3) — governed self-extension.
#
# Nang luc dinh-nghia-OS: cho agent/consumer MO RONG Piloth CO QUAN TRI cho du
# an cua ho — ban Piloth cua AOS Forge + meta-harness. Vong lap (SKILL.md):
#   notice gap that -> os-inspect (reuse truoc) -> chon artifact ben nho nhat
#   -> forge-scaffold -> forge-verify -> forge-plan (authority-delta) -> HUMAN
#   duyet -> ghi file duoi contract -> them capability-manifest -> os-close+seal
#   -> append lesson.
#
# construction != activation (AOS authority.md): Forge chi SCAFFOLD + VERIFY +
# TRINH authority-delta. No KHONG tu ghi file vao cay song, KHONG tu them vao
# capability-manifest, KHONG tu cap quyen. Activation la buoc human-approved,
# contract-gated, sealed. => cac mode forge-* deu READ-ONLY.
# ---------------------------------------------------------------------------

FORGE_KIND_LAYER = {"skill": "Skills", "rule": "Rules", "gate": "Evaluation"}
FORGE_SLUG_RE = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
FORGE_TEMPLATE_DIR = PILOTHOS_DIR / "templates" / "forge"

_FORGE_SKILL_FALLBACK = """# {{id}} — Workflow Skill

## Purpose
{{intent}}

## Non-Responsibilities
- (điều skill này KHÔNG làm)

## Preconditions
- (điều kiện trước khi chạy)

## Steps
1. (bước 1)

## Verification
- (bằng chứng chứng minh hoàn thành)

## Failure & Escalation
- (khi thất bại thì sao)

## References
- Capability authority: pilothOS/governance/capability-manifest.json (id: {{id}})
- Forge: pilothOS/skills/workflow/piloth-forge/SKILL.md
"""

_FORGE_RULE_FALLBACK = """# {{id}} — Rule

## Trigger
(khi nào rule này áp dụng — phải kiểm chứng được)

## Rule
{{intent}}

## Rationale
{{reason}}

## Enforcement
- (hook enforce được, hay contract khai trung thực)

## References
- Capability authority: pilothOS/governance/capability-manifest.json (id: {{id}})
"""


def _forge_template(kind):
    name = {"skill": "skill.SKILL.md.tmpl", "rule": "rule.md.tmpl"}.get(kind)
    if name:
        path = FORGE_TEMPLATE_DIR / name
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            pass
    return _FORGE_SKILL_FALLBACK if kind == "skill" else _FORGE_RULE_FALLBACK


def _forge_fill(template, spec):
    out = template
    for key in ("id", "kind", "layer", "intent", "reason"):
        out = out.replace("{{" + key + "}}", str(spec.get(key, "")))
    return out


def _forge_manifest_entry(spec):
    """Capability-manifest entry se them KHI ACTIVATION (human-approved), khong
    phai bay gio."""
    entry = {
        "id": spec.get("id"),
        "kind": spec.get("kind"),
        "layer": spec.get("layer"),
        "description": spec.get("intent", ""),
    }
    authority = spec.get("authority")
    if isinstance(authority, dict) and authority:
        entry["authority"] = authority
    return entry


def _forge_target_path(spec):
    kind, cid = spec.get("kind"), spec.get("id")
    if kind == "skill":
        return f"pilothOS/skills/workflow/{cid}/SKILL.md"
    if kind == "rule":
        return f"pilothOS/rules/{cid}.md"
    return None  # gate: khong scaffold file (can guard wiring — xem guides/verify.md)


def forge_verify_findings(spec):
    """Verify mot spec capability de xuat. Tra (errors, warnings)."""
    errors, warnings = [], []
    if not isinstance(spec, dict):
        return (["spec phai la mot JSON object"], [])
    kind = spec.get("kind")
    if kind not in ("skill", "rule", "gate"):
        errors.append("kind phai thuoc skill|rule|gate")
    cid = spec.get("id")
    if not non_empty_string(cid):
        errors.append("id thieu")
    elif not FORGE_SLUG_RE.fullmatch(cid):
        errors.append(f"id phai la kebab-slug (a-z0-9-): {cid}")
    else:
        manifest = load_capability_manifest()
        if isinstance(manifest, dict):
            existing = {c.get("id") for c in manifest.get("capabilities", []) if isinstance(c, dict)}
            if cid in existing:
                errors.append(f"id da ton tai trong capability-manifest: {cid} — reuse/extend thay vi tao moi")
    layer = spec.get("layer")
    if kind in FORGE_KIND_LAYER and layer != FORGE_KIND_LAYER[kind]:
        errors.append(f"layer cho kind={kind} phai la {FORGE_KIND_LAYER[kind]} (got {layer})")
    if not non_empty_string(spec.get("intent")):
        errors.append("intent thieu")
    if not non_empty_string(spec.get("reason")):
        errors.append("reason thieu — extension rule: phai co task/incident/nhu cau lap that (pilothOS/README.md)")
    # Authority shape: tai dung capability-check tren mot manifest tong hop.
    synth_cap = {
        "id": cid if non_empty_string(cid) else "candidate",
        "kind": kind if kind in CAPABILITY_KINDS else "skill",
        "layer": layer if layer in CAPABILITY_LAYERS else "Skills",
        "description": spec.get("intent", ""),
    }
    if spec.get("authority") is not None:
        synth_cap["authority"] = spec.get("authority")
    cap_errors, cap_warnings = capability_check_findings(
        {"schema_version": 1, "coverage": "partial", "capabilities": [synth_cap]}
    )
    errors.extend(e for e in cap_errors if "authority" in e)
    warnings.extend(w for w in cap_warnings if "authority" in w)
    if not spec.get("authority"):
        warnings.append("authority chua khai — se fail-closed (quyen rong nhat); khai neu can path/entitlement")
    return (errors, warnings)


def forge_verify(argv):
    try:
        spec, _ = json_arg_or_stdin(argv, "forge-verify")
    except Exception as e:
        json_print({"result": "forge_verify_rejected", "errors": [str(e)]})
        return
    errors, warnings = forge_verify_findings(spec)
    json_print({
        "result": "forge_verify_passed" if not errors else "forge_verify_failed",
        "id": spec.get("id") if isinstance(spec, dict) else None,
        "errors": errors,
        "warnings": warnings,
    })


def forge_scaffold(argv):
    try:
        spec, _ = json_arg_or_stdin(argv, "forge-scaffold")
    except Exception as e:
        json_print({"result": "forge_scaffold_rejected", "errors": [str(e)]})
        return
    errors, warnings = forge_verify_findings(spec)
    if errors:
        json_print({"result": "forge_scaffold_rejected", "errors": errors, "warnings": warnings})
        return
    kind = spec.get("kind")
    files = {}
    target = _forge_target_path(spec)
    if target:
        files[target] = _forge_fill(_forge_template(kind), spec)
    json_print({
        "result": "forge_scaffold",
        "id": spec.get("id"),
        "kind": kind,
        "files": files,
        "manifest_entry": _forge_manifest_entry(spec),
        "warnings": warnings,
        "note": "SCAFFOLD ONLY — chua ghi file, chua cap quyen. Forge khong tu kich hoat.",
        "next_steps": [
            "1. Doc lai files + manifest_entry.",
            "2. forge-plan de xem authority-delta (quyen se cap) + verify.",
            "3. HUMAN duyet authority-delta.",
            "4. Ghi file duoi mot active contract (os-start).",
            "5. Them manifest_entry vao capability-manifest.json roi capability-check.",
            "6. os-close + seal; append lesson (retain).",
        ] if target else [
            "kind=gate: khong scaffold file — gate can guard wiring.",
            "Xem pilothOS/skills/workflow/piloth-forge/guides/verify.md.",
        ],
    })


def forge_plan(argv):
    try:
        spec, _ = json_arg_or_stdin(argv, "forge-plan")
    except Exception as e:
        json_print({"result": "forge_plan_rejected", "errors": [str(e)]})
        return
    errors, warnings = forge_verify_findings(spec)
    after = resolve_authority(spec if isinstance(spec, dict) else {})
    empty = resolve_authority({})
    delta = compute_authority_delta(empty, after)
    json_print({
        "result": "forge_plan",
        "id": spec.get("id") if isinstance(spec, dict) else None,
        "verify": {"passed": not errors, "errors": errors, "warnings": warnings},
        "authority_delta": delta,
        "widened": delta["widened"],
        "manifest_entry": _forge_manifest_entry(spec) if isinstance(spec, dict) else None,
        "approval_required": True,
        "note": "construction != activation: Forge trinh delta de HUMAN duyet; khong tu cap quyen.",
    })
