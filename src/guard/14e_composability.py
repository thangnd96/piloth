# ---------------------------------------------------------------------------
# Composability (T5) — workspace-wins skill precedence + principal.
#
# Ban Piloth cua capsule-skills cua AOS: consumer them/OVERRIDE mot skill cho du
# an cua ho MA KHONG PHAI FORK kernel. skill-index scan skill kernel
# (pilothOS/skills/workflow) + skill consumer, workspace(consumer)-WINS tren trung
# id. Pair voi Forge (T3): Forge scaffold mot project skill, skill-index tim thay
# no voi precedence.
#
# principal: caller identity tu context (env), KHONG tu payload claim (giong AOS
# "kernel-stamped identity, never a payload claim"). Multi-tenant attribution
# tren receipt la buoc future (xem composability.md).
# ---------------------------------------------------------------------------


def _skill_title(path):
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("# "):
                return s[2:].strip()
    except OSError:
        pass
    return ""


def _rel_or_str(p):
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(p)


def _scan_skills(root):
    out = {}
    root = pathlib.Path(root)
    if not root.is_dir():
        return out
    for skill_md in sorted(root.glob("*/SKILL.md")):
        sid = skill_md.parent.name
        out[sid] = {"id": sid, "path": _rel_or_str(skill_md), "title": _skill_title(skill_md)}
    return out


def current_principal():
    """Caller identity tu context (env), never a payload claim. Default 'local'."""
    p = os.environ.get("PILOTHOS_PRINCIPAL")
    return p.strip() if p and p.strip() else "local"


def skill_index_result(consumer_dir=None):
    kernel = _scan_skills(PILOTHOS_DIR / "skills" / "workflow")
    skills = {sid: dict(e, source="kernel", overrides=None) for sid, e in kernel.items()}
    if consumer_dir is None:
        consumer_dir = os.environ.get("PILOTHOS_CONSUMER_SKILLS")
    consumer = _scan_skills(consumer_dir) if consumer_dir else {}
    for sid, e in consumer.items():
        # workspace(consumer)-wins: consumer override kernel tren trung id.
        skills[sid] = dict(e, source="consumer", overrides=("kernel" if sid in kernel else None))
    overrides = sorted(sid for sid, e in skills.items() if e.get("overrides") == "kernel")
    return {
        "result": "skill_index",
        "count": len(skills),
        "kernel": len(kernel),
        "consumer": len(consumer),
        "overrides": overrides,
        "consumer_dir": str(consumer_dir) if consumer_dir else None,
        "principal": current_principal(),
        "skills": [skills[k] for k in sorted(skills)],
    }


def skill_index(argv):
    args = list(argv or [])
    consumer_dir = None
    if "--consumer" in args:
        idx = args.index("--consumer")
        consumer_dir = args[idx + 1] if idx + 1 < len(args) else None
    json_print(skill_index_result(consumer_dir=consumer_dir))
