# -------------------------------------------------------------- small helpers

def stable_slug(value):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug or "item"


def safe_task_id(value):
    return stable_slug(value)[:120]


def read_text_safe(path, limit=200000):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if limit and len(text) > limit:
        return text[:limit]
    return text


def git_changed_paths():
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
    except Exception:
        return []
    if out.returncode != 0:
        return []
    paths = []
    for line in out.stdout.splitlines():
        if not line:
            continue
        raw = line[3:] if len(line) > 3 else line
        if " -> " in raw:
            raw = raw.rsplit(" -> ", 1)[1]
        raw = raw.strip()
        if raw:
            paths.append(raw)
    return sorted(set(paths))


def git_changed_file_paths():
    paths = []
    commands = [
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only"],
        ["git", "-C", str(REPO_ROOT), "diff", "--name-only", "--cached"],
        ["git", "-C", str(REPO_ROOT), "ls-files", "--others", "--exclude-standard"],
    ]
    for command in commands:
        try:
            out = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        except Exception:
            continue
        if out.returncode == 0:
            paths.extend(line.strip() for line in out.stdout.splitlines() if line.strip())
    if paths:
        return sorted(set(paths))

    expanded = []
    for raw in git_changed_paths():
        rel = raw.rstrip("/")
        path = REPO_ROOT / rel
        if path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file():
                    expanded.append(item.relative_to(REPO_ROOT).as_posix())
        else:
            expanded.append(rel)
    return sorted(set(p for p in expanded if p))


def is_git_repo():
    """REPO_ROOT có nằm trong một git working tree hoạt động được không?

    Dùng để phân biệt 'working tree sạch' với 'git không khả dụng': khi không
    phải git repo, git_changed_file_paths() trả rỗng một cách mập mờ, nên gate
    phải fallback về hành vi mtime cũ thay vì tưởng nhầm mọi thứ đã deliver.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=5,
        )
    except Exception:
        return False
    return out.returncode == 0 and out.stdout.strip() == "true"


def json_print(payload):
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def write_json(path, obj):
    """Write obj as the canonical PilothOS state-file JSON: UTF-8, sorted keys,
    2-space indent, trailing newline. Single writer for every persisted
    state/contract/receipt/seal file so their on-disk format cannot drift."""
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_json(value):
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def redact_secret_text(value, limit=1000):
    text = str(value)
    for pattern in SECRET_VALUE_PATTERNS:
        text = pattern.sub(lambda match: match.group(0).split(match.group(1), 1)[0] + match.group(1) + "=[redacted]"
                           if len(match.groups()) else "[redacted]", text)
    if len(text) > limit:
        return text[:limit] + "...[truncated]"
    return text


def sanitize_state_value(value, limit=1000):
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if SECRET_KEY_RE.search(key_text):
                sanitized[key_text] = "[redacted]"
            else:
                sanitized[key_text] = sanitize_state_value(item, limit=limit)
        return sanitized
    if isinstance(value, list):
        return [sanitize_state_value(item, limit=limit) for item in value[:50]]
    if isinstance(value, str):
        return redact_secret_text(value, limit=limit)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_secret_text(value, limit=limit)


def os_run_dir(task_id):
    return OS_RUNS_DIR / safe_task_id(task_id)


def os_state_path(task_id, filename="state.json"):
    return os_run_dir(task_id) / filename


def os_evidence_path(task_id):
    return os_state_path(task_id, "evidence.jsonl")


def read_os_current_task_id():
    data = load_json_file(OS_CURRENT)
    if isinstance(data, dict) and non_empty_string(data.get("task_id")):
        return data["task_id"]
    return ""


def write_os_current_task_id(task_id):
    OS_CURRENT.parent.mkdir(parents=True, exist_ok=True)
    write_json(OS_CURRENT, {
        "task_id": task_id,
        "repo_key": REPO_KEY,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    })


def load_os_state(task_id=None):
    if not task_id:
        task_id = read_os_current_task_id()
    if task_id:
        path = os_state_path(task_id)
        data = load_json_file(path)
        if isinstance(data, dict):
            return data, path
    latest = latest_os_state()
    if latest:
        return latest
    return None, None


def latest_os_state(require_closed=False):
    if not OS_RUNS_DIR.exists():
        return None, None
    candidates = []
    for path in OS_RUNS_DIR.glob("*/state.json"):
        data = load_json_file(path)
        if not isinstance(data, dict):
            continue
        if data.get("repo_key") != REPO_KEY:
            continue
        if require_closed:
            status = data.get("status")
            if status not in {"closed", "sealed"}:
                continue
            if not non_empty_string(data.get("seal_sha256")):
                continue
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = 0
        candidates.append((mtime, data.get("updated_at", ""), data, path))
    if not candidates:
        return None, None
    _, _, data, path = sorted(candidates, key=lambda item: (item[0], item[1]))[-1]
    return data, path


def save_os_state(state):
    task_id = state.get("task_id")
    if not non_empty_string(task_id):
        raise ValueError("OS state missing task_id")
    state = dict(state)
    state["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    path = os_state_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, state)
    write_os_current_task_id(task_id)
    return path


def os_evidence_records(task_id):
    path = os_evidence_path(task_id)
    if not path.exists():
        return []
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
    except (OSError, json.JSONDecodeError):
        return []
    return records


def append_os_evidence(task_id, evidence):
    path = os_evidence_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(evidence, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def review_feedback_path(task_id):
    return os_state_path(task_id, "review-feedback.jsonl")


def append_review_feedback(task_id, record):
    """Append one human-review round to the append-only review-feedback ledger.

    Mirrors append_os_evidence: one JSON record per line, one line per review
    round. os-close reads the highest-round record for the human_review gate.
    """
    path = review_feedback_path(task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def review_feedback_records(task_id):
    path = review_feedback_path(task_id)
    if not path.exists():
        return []
    records = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    records.append(item)
    except (OSError, json.JSONDecodeError):
        return []
    return records


def latest_review_feedback(task_id):
    records = review_feedback_records(task_id)
    if not records:
        return None

    def _round(r):
        try:
            return int(r.get("review_round", 0))
        except (TypeError, ValueError):
            return 0

    return sorted(records, key=_round)[-1]


