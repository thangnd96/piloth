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


