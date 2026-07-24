# ---------------------------------------------------------------------------
# Execution Broker / Airlock (T1).
#
# Nang bien tool-call tu honor-system thanh mot PDP that — ban Piloth cua AOS
# capsule-shell Process Airlock. Diem then chot credibility (probe #1): mot so
# lenh bi TU CHOI VO DIEU KIEN truoc bat ky approval nao (catastrophic hard-deny),
# dung nhu Airlock cua AOS. Cac lenh chuoi (&&/||/;/|) duoc tach va kiem TUNG
# sub-command doc lap; lenh boc trong wrapper (sudo/env/xargs/time/nohup/...),
# shell `-c` payload, `eval`, va command-substitution `$(...)`/backtick deu duoc
# DE QUY vao ben trong (neu khong, `bash -c "rm -rf /"` se lach airlock).
#
# Phan tang (trung thuc, giong AOS: hard-deny la that, gating con lai advisory):
#   - deny (block that): catastrophic — fork bomb, mkfs, dd->block device,
#     rm tren protected root path (hoac target la command-substitution), ghi ra
#     block device, find <protected> -delete, chmod/chown -R <protected>, shred
#     block-device/critical-file. Luon block, khong bao gio fail-open.
#   - ask: high-risk khong-catastrophic — surface trong decision; tren host co
#     native permission prompt (Claude Code) thi PASS-THROUGH (khong double-prompt).
#   - allow: sach.
#
# Entitlement fail-closed da song o tool-check (validate_payload_entitlements);
# broker-check lo bien Bash command noi tool-check khong phu.
#
# broker-check la HOOK mode (doc tool_input.command tu PreToolUse). Quyet dinh
# catastrophic chay TRUOC va DOC LAP moi I/O (khong load contract/manifest) —
# de exception o subsystem khac khong the nuot viec block. Chi fail-OPEN khi
# chinh logic string loi (rat kho): governance hook khong duoc brick session
# bang cach block tat ca (bai hoc settings.json). Matching dung string op don
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
# Prefix wrapper: lenh that = cac token sau wrapper (bo cac flag/env cua no).
BROKER_ARG_WRAPPERS = {
    "sudo", "doas", "env", "xargs", "time", "nohup", "nice", "ionice",
    "stdbuf", "setsid", "command",
}
# Shell chay payload qua `-c` (inner command = arg sau -c).
BROKER_SHELL_EXES = {"bash", "sh", "zsh", "dash", "ash", "ksh", "fish"}
# Prefix he thong tro yeu (dung cho shred: shred /etc/passwd la catastrophic).
BROKER_CRITICAL_PREFIXES = (
    "/etc/", "/usr/", "/bin/", "/sbin/", "/boot/", "/var/", "/lib/",
    "/dev/", "/System/", "/Library/",
)


def _broker_split_subcommands(command):
    """Tach command thanh sub-command theo &&/||/;/|/newline (linear, khong regex
    backtracking). Moi sub duoc kiem catastrophic doc lap. (Toan bo lenh cung
    duoc kiem rieng o broker_decision de bat truong hop operator nam trong quote,
    vd `bash -c "a && rm -rf /"`.)"""
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


def _broker_exe(toks):
    if not toks:
        return ""
    return pathlib.PurePosixPath(toks[0].replace("\\", "/")).name.lower()


def _is_protected_target(t):
    """Target la protected root/system/home path, hoac command-substitution
    (opaque -> khong xac minh duoc -> danger)."""
    return (
        t in BROKER_PROTECTED_RM_TARGETS
        or t.rstrip("/") in BROKER_PROTECTED_RM_TARGETS
        or "$(" in t
        or "`" in t
    )


def _has_recursive_flag(toks):
    long_flags = {t for t in toks[1:] if t.startswith("--")}
    short = "".join(t[1:] for t in toks[1:] if t.startswith("-") and not t.startswith("--"))
    return ("r" in short.lower()) or ("--recursive" in long_flags)


def _rm_targets_protected(toks):
    if not _has_recursive_flag(toks):
        return False
    return any(_is_protected_target(t) for t in toks[1:] if not t.startswith("-"))


def _find_delete_protected(toks):
    # `find <paths...> ... -delete`: paths precede the first -expression.
    if "-delete" not in toks[1:]:
        return False
    for t in toks[1:]:
        if t.startswith("-"):
            break
        if _is_protected_target(t):
            return True
    return False


def _recursive_perm_protected(toks):
    # chmod/chown/chgrp -R tren protected path (vd chmod -R 000 /).
    if not _has_recursive_flag(toks):
        return False
    return any(_is_protected_target(t) for t in toks[1:] if not t.startswith("-"))


def _shred_catastrophic(toks):
    # shred block device hoac file he thong (shred /dev/sda, shred /etc/passwd).
    for t in toks[1:]:
        if t.startswith("-"):
            continue
        if any(t.startswith(p) for p in BROKER_BLOCK_DEV_PREFIXES):
            return True
        if _is_protected_target(t):
            return True
        if any(t.startswith(p) for p in BROKER_CRITICAL_PREFIXES):
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


def _nested_command_strings(sub):
    """Tra cac command string 'an' ben trong: wrapper argv (sudo/env/xargs/...),
    shell `-c` payload, `eval` args, va command-substitution $(...)/backtick.
    Dung de kiem catastrophic DE QUY (chong lach airlock qua wrapper)."""
    out = []
    toks = _broker_tokens(sub)
    if toks:
        exe = _broker_exe(toks)
        if exe in BROKER_ARG_WRAPPERS:
            # Grammar option cua wrapper khac nhau (nice -n 10, sudo -u x, env -i,
            # xargs -n1, stdbuf -oL...). Thay vi parse tung loai, coi MOI suffix la
            # candidate inner command (fail-safe: over-generate; airlock nen
            # deny-on-doubt). shlex.quote giu nguyen -c arg khi re-tokenize.
            for i in range(1, min(len(toks), 8)):
                out.append(" ".join(shlex.quote(t) for t in toks[i:]))
        elif exe == "eval":
            arg = " ".join(t for t in toks[1:] if not t.startswith("-"))
            if arg:
                out.append(arg)
        elif exe in BROKER_SHELL_EXES:
            for i in range(1, len(toks) - 1):
                if toks[i] == "-c":
                    out.append(toks[i + 1])
                    break
    for m in re.finditer(r"\$\(([^()]*)\)", sub):
        if m.group(1).strip():
            out.append(m.group(1))
    for m in re.finditer(r"`([^`]*)`", sub):
        if m.group(1).strip():
            out.append(m.group(1))
    return out


def _direct_catastrophic(sub):
    """Kiem catastrophic TRUC TIEP tren mot sub-command (khong de quy)."""
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
    exe = _broker_exe(toks)
    if exe == "mkfs" or exe.startswith("mkfs."):
        return "mkfs"
    if exe in ("rm", "grm") and _rm_targets_protected(toks):
        return "rm_protected_path"
    if exe == "dd" and _dd_to_block_device(toks):
        return "dd_block_device"
    if exe == "find" and _find_delete_protected(toks):
        return "find_delete_protected"
    if exe in ("chmod", "chown", "chgrp") and _recursive_perm_protected(toks):
        return "recursive_perm_protected"
    if exe == "shred" and _shred_catastrophic(toks):
        return "shred_critical"
    return None


def catastrophic_match(sub, _depth=0):
    """Tra ten rule catastrophic neu sub-command bi hard-deny, else None.
    De quy vao wrapper/`-c`/eval/substitution (gioi han do sau chong loop)."""
    if not isinstance(sub, str):
        return None
    rule = _direct_catastrophic(sub)
    if rule:
        return rule
    if _depth >= 4:
        return None
    for inner in _nested_command_strings(sub):
        for piece in _broker_split_subcommands(inner):
            r = catastrophic_match(piece, _depth + 1)
            if r:
                return r
    return None


def broker_decision(command):
    """Pure decision: allow | deny | ask. deny = catastrophic (hard-deny vo dieu
    kien, ke ca khi boc trong wrapper/`-c`/substitution). ask = high-risk
    non-catastrophic (consent). allow = sach. Chi phu thuoc chuoi `command` —
    khong doc contract/manifest/I/O (de khong the fail-open qua exception ngoai)."""
    if not isinstance(command, str) or not command.strip():
        return {"decision": "allow", "rule": "empty", "reason": "empty command"}
    # Kiem toan bo lenh (bat wrapper + operator-trong-quote), roi tung sub-command.
    candidates = [command] + _broker_split_subcommands(command)
    for cand in candidates:
        rule = catastrophic_match(cand)
        if rule:
            return {
                "decision": "deny",
                "rule": "catastrophic:" + rule,
                "reason": f"catastrophic command hard-denied ({rule}) — refused before any approval",
                "subcommand": cand.strip(),
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
    Catastrophic quyet dinh TRUOC, chi tu chuoi command — khong load contract/
    manifest — nen exception subsystem khac khong the nuot viec block. Fail-OPEN
    chi khi chinh logic loi (rat kho): hook khong duoc brick session."""
    command = ""
    if isinstance(hook_input, dict):
        tool_input = hook_input.get("tool_input")
        if isinstance(tool_input, dict):
            command = tool_input.get("command") or ""
        if not command:
            command = hook_input.get("command") or ""
    if not isinstance(command, str) or not command.strip():
        return
    try:
        decision = broker_decision(command)
    except Exception:
        return  # fail-open only on internal logic error
    if decision["decision"] == "deny":
        block_decision("PILOTHOS BROKER: " + decision["reason"])
    # ask/allow -> pass-through (host native prompt handles consent).
