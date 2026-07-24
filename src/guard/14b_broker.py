# ---------------------------------------------------------------------------
# Execution Broker / Airlock (T1).
#
# Nang bien tool-call tu honor-system thanh mot PDP that — ban Piloth cua AOS
# capsule-shell Process Airlock. Diem then chot credibility (probe #1): mot so
# lenh bi TU CHOI VO DIEU KIEN truoc bat ky approval nao (catastrophic hard-deny),
# dung nhu Airlock cua AOS. Cac lenh chuoi (&&/||/;/|) duoc tach va kiem TUNG
# sub-command doc lap.
#
# Phan tang (trung thuc, giong AOS: hard-deny la that, gating con lai advisory):
#   - deny (block that): catastrophic — fork bomb, mkfs, dd->block device,
#     rm tren protected root path, ghi ra block device. Luon block.
#   - ask: high-risk khong-catastrophic — surface trong decision; tren host co
#     native permission prompt (Claude Code) thi PASS-THROUGH (khong double-prompt).
#   - allow: sach.
#
# Entitlement fail-closed da song o tool-check (validate_payload_entitlements);
# broker-check lo bien Bash command noi tool-check khong phu.
#
# broker-check la HOOK mode (doc tool_input.command tu PreToolUse). Fail-OPEN
# khi loi noi bo: mot governance hook KHONG BAO GIO duoc brick session bang cach
# block tat ca (bai hoc settings.json). Catastrophic matching dung string op don
# gian, co guard — nhanh, khong ReDoS.
# ---------------------------------------------------------------------------

# Prefix cua block device (dia that). /dev/null|zero|random|tty... KHONG nam day.
BROKER_BLOCK_DEV_PREFIXES = (
    "/dev/sd", "/dev/disk", "/dev/nvme", "/dev/hd", "/dev/mmcblk",
    "/dev/vd", "/dev/xvd", "/dev/rdisk",
)
# Target ma `rm -r` (co/khong -f) coi la catastrophic (xoa root/system/home).
BROKER_PROTECTED_RM_TARGETS = {
    "/", "/*", "~", "~/", "~/*", "*", "$HOME", "${HOME}", "$HOME/*",
    "/etc", "/usr", "/bin", "/sbin", "/var", "/lib", "/lib64", "/boot",
    "/dev", "/opt", "/root", "/home", "/Users", "/System", "/Library",
    "/Applications",
}


def _broker_split_subcommands(command):
    """Tach command thanh sub-command theo &&/||/;/|/newline (linear, khong regex
    backtracking). Moi sub duoc kiem catastrophic doc lap."""
    tmp = command
    for op in ("&&", "||"):
        tmp = tmp.replace(op, "\x00")
    for ch in (";", "|", "\n"):
        tmp = tmp.replace(ch, "\x00")
    return [part for part in tmp.split("\x00") if part.strip()]


def _broker_tokens(sub):
    try:
        toks = shlex.split(sub)
    except ValueError:
        toks = sub.split()
    while toks and ENV_ASSIGNMENT_RE.fullmatch(toks[0]):
        toks = toks[1:]
    return toks


def _rm_targets_protected(toks):
    long_flags = {t for t in toks[1:] if t.startswith("--")}
    if "--no-preserve-root" in long_flags:
        return True
    short = "".join(t[1:] for t in toks[1:] if t.startswith("-") and not t.startswith("--"))
    recursive = ("r" in short.lower()) or ("--recursive" in long_flags)
    if not recursive:
        return False
    for t in toks[1:]:
        if t.startswith("-"):
            continue
        if t in BROKER_PROTECTED_RM_TARGETS or t.rstrip("/") in BROKER_PROTECTED_RM_TARGETS:
            return True
    return False


def _dd_to_block_device(toks):
    for t in toks:
        if t.startswith("of="):
            target = t[3:]
            if any(target.startswith(p) for p in BROKER_BLOCK_DEV_PREFIXES):
                return True
    return False


def _writes_block_device(command):
    compact = command.lower().replace(" ", "")
    return any(">" + p in compact for p in BROKER_BLOCK_DEV_PREFIXES)


def catastrophic_match(sub):
    """Tra ten rule catastrophic neu sub-command bi hard-deny, else None."""
    if not isinstance(sub, str):
        return None
    s = sub.strip()
    if not s:
        return None
    nospace = "".join(s.split())
    # fork bomb: classic :(){ :|:& };: va bien the copy-paste
    if ":(){" in nospace or ":|:&" in nospace:
        return "fork_bomb"
    if _writes_block_device(s):
        return "write_block_device"
    toks = _broker_tokens(s)
    if not toks:
        return None
    exe = pathlib.PurePosixPath(toks[0].replace("\\", "/")).name.lower()
    if exe == "mkfs" or exe.startswith("mkfs."):
        return "mkfs"
    if exe in ("rm", "grm") and _rm_targets_protected(toks):
        return "rm_protected_path"
    if exe == "dd" and _dd_to_block_device(toks):
        return "dd_block_device"
    return None


def broker_decision(command, contract=None, coverage=None):
    """Pure decision: allow | deny | ask. deny = catastrophic (hard-deny vo dieu
    kien). ask = high-risk non-catastrophic (consent). allow = sach."""
    if not isinstance(command, str) or not command.strip():
        return {"decision": "allow", "rule": "empty", "reason": "empty command"}
    # Kiem tung sub-command chuoi truoc (bat `foo && rm -rf /`)...
    for sub in _broker_split_subcommands(command):
        rule = catastrophic_match(sub)
        if rule:
            return {
                "decision": "deny",
                "rule": "catastrophic:" + rule,
                "reason": f"catastrophic command hard-denied ({rule}) — refused before any approval",
                "subcommand": sub.strip(),
            }
    # ...roi kiem toan bo lenh (bat lenh don khong chuoi).
    rule = catastrophic_match(command)
    if rule:
        return {
            "decision": "deny",
            "rule": "catastrophic:" + rule,
            "reason": f"catastrophic command hard-denied ({rule}) — refused before any approval",
            "subcommand": command.strip(),
        }
    if command_looks_high_risk(command):
        return {
            "decision": "ask",
            "rule": "high_risk",
            "reason": "high-risk command — requires explicit consent before running",
        }
    return {"decision": "allow", "rule": "clean", "reason": "no catastrophic or high-risk pattern"}


def broker_check(hook_input):
    """PreToolUse:Bash gate. Block CHI khi catastrophic (hard-deny). high-risk
    'ask' pass-through cho native permission prompt cua host (khong double-prompt).
    Fail-OPEN khi loi noi bo — governance hook khong duoc brick session."""
    try:
        command = ""
        if isinstance(hook_input, dict):
            tool_input = hook_input.get("tool_input")
            if isinstance(tool_input, dict):
                command = tool_input.get("command") or ""
            if not command:
                command = hook_input.get("command") or ""
        if not isinstance(command, str) or not command.strip():
            return
        contract, _ = load_task_contract(hook_input)
        status = capability_manifest_status()
        decision = broker_decision(command, contract, status.get("coverage"))
        if decision["decision"] == "deny":
            block_decision("PILOTHOS BROKER: " + decision["reason"])
        # ask/allow -> pass-through (host native prompt handles consent).
    except Exception:
        return
