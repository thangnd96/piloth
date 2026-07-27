# ------------------------------------------------------------- settings merge

def merge_settings_content(consumer, payload, options, notes):
    out = json.loads(json.dumps(consumer))
    judg = []
    # permissions
    cp = out.setdefault("permissions", {})
    pp = payload.get("permissions", {})
    for key in ("allow", "deny"):
        merged = list(cp.get(key, []))
        for item in pp.get(key, []):
            if item not in merged:
                merged.append(item)
        cp[key] = merged
    deny = set(cp.get("deny", []))
    kept_allow = []
    for item in cp.get("allow", []):
        if item in deny:
            notes.append(f"deny-thang: '{item}' bi loai khoi allow")
        else:
            kept_allow.append(item)
    cp["allow"] = kept_allow
    # env
    ce = out.setdefault("env", {})
    for k, v in payload.get("env", {}).items():
        if k in ce and ce[k] != v:
            judg.append({"type": "env_conflict", "key": k,
                         "consumer": ce[k], "pilothos": v})
        else:
            ce[k] = v
    # statusLine
    psl = payload.get("statusLine")
    if psl:
        csl = out.get("statusLine")
        if not csl:
            out["statusLine"] = psl
        elif json.dumps(csl, sort_keys=True) == json.dumps(psl, sort_keys=True):
            pass  # giong het -> khong phai conflict (dedupe principle)
        else:
            choice = (options or {}).get("statusline")
            if choice == "consumer":
                notes.append("statusLine: giu cua consumer (mat chi bao rot)")
            elif choice == "pilothos":
                out["statusLine"] = psl
            elif choice == "chain":
                a = csl.get("command", "")
                b = psl.get("command", "")
                out["statusLine"] = {
                    "type": "command",
                    "command": ("bash -c 'a=$(%s); b=$(%s); "
                                "echo \"$a${b:+ | }$b\"'" % (a, b)),
                }
            else:
                judg.append({"type": "statusline_conflict",
                             "hint": "khai options.statusline = consumer|pilothos|chain"})
    # hooks: consumer TRUOC, pilothos SAU; dedupe object giong het
    ch = out.setdefault("hooks", {})
    for event, entries in payload.get("hooks", {}).items():
        existing = ch.setdefault(event, [])
        for entry in entries:
            if not any(json.dumps(e, sort_keys=True) == json.dumps(entry, sort_keys=True)
                       for e in existing):
                existing.append(entry)
    if judg:
        raise NeedsJudgment(judg)
    return out




# Piloth-owned hook commands name a path under pilothOS/. When an upgrade stops
# shipping a script, the consumer's settings.json keeps pointing at it — the file
# is consumer-owned, so upgrade preserves it by design. The result is a hook that
# fires on every matching tool use and exits 127. v2 removes tools/review/, which
# every v1.10+ install still references three times.
PILOTHOS_PATH_RE = re.compile(r"pilothOS/[^\s\"']+")


def _shipped_kernel_paths():
    """Paths this version actually ships, from dist-manifest.json."""
    try:
        data = json.loads(
            (PILOTHOS_DIR / "dist-manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {item.get("path") for item in data.get("files", [])}


def dead_pilothos_hook_paths(command):
    """pilothOS/ paths a hook names that THIS VERSION does not ship.

    Manifest, not disk. `.exists()` made the op unable to fire on the one path it
    exists for: staging did not prune, so the old script was still sitting there,
    the hook was not "dead", nothing was removed (thangnd96/piloth#7). A hook
    keeping a removed subsystem alive is drift even while it runs.

    Falls back to the disk check when the manifest is unreadable — a corrupt
    manifest must not turn pruning into "remove everything".
    """
    shipped = _shipped_kernel_paths()
    refs = PILOTHOS_PATH_RE.findall(str(command or ""))
    if shipped is None:
        return [ref for ref in refs if not (REPO_ROOT / ref).exists()]
    return [ref for ref in refs if ref not in shipped]


def prune_dead_hooks(settings):
    """Drop hook entries whose Piloth script is gone. Returns (settings, removed).

    Only entries naming a missing pilothOS/ path are touched: a consumer hook
    that never mentions pilothOS/ is invisible to this, and a Piloth hook whose
    script still exists stays. Empty groups and empty events are cleaned up so an
    upgrade does not leave `"Notification": []` behind.
    """
    out = json.loads(json.dumps(settings))
    removed = []
    hooks = out.get("hooks")
    if not isinstance(hooks, dict):
        return out, removed
    for event in list(hooks):
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        kept_groups = []
        for group in groups:
            if not isinstance(group, dict):
                kept_groups.append(group)
                continue
            entries = group.get("hooks")
            if not isinstance(entries, list):
                kept_groups.append(group)
                continue
            kept = []
            for entry in entries:
                dead = dead_pilothos_hook_paths(
                    entry.get("command") if isinstance(entry, dict) else "")
                if dead:
                    removed.append({"event": event, "missing": dead[0],
                                    "command": str(entry.get("command"))[:120]})
                else:
                    kept.append(entry)
            if kept:
                group = dict(group, hooks=kept)
                kept_groups.append(group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]
    return out, removed
