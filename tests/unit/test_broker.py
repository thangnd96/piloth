"""Unit tests for the T1 execution broker / airlock.

The credibility linchpin (probe #1): catastrophic commands are hard-denied
unconditionally, before any approval — the Piloth analog of AOS's Process
Airlock. Chained sub-commands are checked independently. High-risk (non-
catastrophic) commands surface as `ask`; clean commands `allow`.
"""

CATASTROPHIC = [
    "rm -rf /",
    "rm -rf /*",
    "rm -rf ~",
    "rm -r /etc",
    "rm -rf --no-preserve-root /",
    ":(){ :|:& };:",
    "dd if=/dev/zero of=/dev/sda bs=1M",
    "mkfs.ext4 /dev/sdb1",
    "mkfs /dev/disk2",
    "cat payload > /dev/sda",
    "echo hi && rm -rf ~",
    "true; mkfs.ext4 /dev/sda",
    "foo || dd if=/dev/zero of=/dev/nvme0n1",
]

HIGH_RISK = [
    "kubectl delete pod x",
    "rm -rf ./build",
    "terraform apply",
    "aws s3 delete-object --bucket b --key k",
]

SAFE = [
    "ls -la",
    "python3 pilothOS/scripts/pilothos_guard.py self-check",
    "dd if=/dev/sda of=backup.img",     # reading a disk into a file is safe
    "cat README.md",
    "grep -rn foo src/",
    "echo done",
]


def test_catastrophic_are_denied(guard):
    for cmd in CATASTROPHIC:
        d = guard.broker_decision(cmd)
        assert d["decision"] == "deny", f"should hard-deny: {cmd} -> {d}"
        assert d["rule"].startswith("catastrophic:"), f"{cmd} -> {d}"


def test_high_risk_ask(guard):
    for cmd in HIGH_RISK:
        d = guard.broker_decision(cmd)
        assert d["decision"] == "ask", f"should ask (consent): {cmd} -> {d}"


def test_safe_allow(guard):
    for cmd in SAFE:
        d = guard.broker_decision(cmd)
        assert d["decision"] == "allow", f"should allow: {cmd} -> {d}"


def test_chained_subcommands_checked_independently(guard):
    # A safe head must not hide a catastrophic tail.
    d = guard.broker_decision("echo ok && rm -rf /")
    assert d["decision"] == "deny"
    assert d["subcommand"].strip().startswith("rm -rf")


def test_dd_direction_matters(guard):
    assert guard.broker_decision("dd if=x of=/dev/sda")["decision"] == "deny"
    assert guard.broker_decision("dd if=/dev/sda of=x.img")["decision"] == "allow"


def test_empty_command_allows(guard):
    assert guard.broker_decision("")["decision"] == "allow"
    assert guard.broker_decision("   ")["decision"] == "allow"


def test_catastrophic_match_returns_rule(guard):
    assert guard.catastrophic_match("rm -rf /") == "rm_protected_path"
    assert guard.catastrophic_match("mkfs.ext4 /dev/sda") == "mkfs"
    assert guard.catastrophic_match("ls -la") is None


def test_broker_check_fails_open_on_bad_input(guard):
    # A governance hook must never raise / brick the session.
    assert guard.broker_check({}) is None
    assert guard.broker_check({"tool_input": {"command": ""}}) is None
    assert guard.broker_check("not-a-dict") is None


def test_broker_check_blocks_catastrophic(guard, capsys):
    guard.broker_check({"tool_name": "Bash", "tool_input": {"command": "rm -rf /"}})
    out = capsys.readouterr().out
    assert '"decision": "block"' in out
    assert "PILOTHOS BROKER" in out


def test_broker_check_allows_safe_silently(guard, capsys):
    guard.broker_check({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert capsys.readouterr().out.strip() == ""


# --- F1: wrapper / substitution / double-wrapper evasions must be hard-denied ---
WRAPPER_EVASIONS = [
    "bash -c 'rm -rf /'",
    'bash -c "rm --recursive --force /"',
    "sh -c 'mkfs.ext4 /dev/sda'",
    "sudo rm -rf /",
    "sudo dd if=/dev/zero of=/dev/sda",
    "xargs rm -rf /",
    "env rm -rf /",
    "env -i rm -rf /",
    "time rm -rf /",
    "nohup rm -rf /",
    "eval 'rm -rf /'",
    "rm -rf $(echo /)",
    "rm -rf `echo /`",
    "echo $(rm -rf /)",
    "bash -c 'a && rm -rf /'",
    "sudo bash -c 'rm -rf /home'",
    "sudo env bash -c 'rm -rf /'",
    "nice -n 10 sudo rm -rf /",
    "sudo -u root rm -rf /",
    "stdbuf -oL rm -rf /",
]

# Safe commands that merely wrap benign work — must NOT be hard-denied.
WRAPPER_SAFE = [
    "sudo apt install foo",
    "bash -c 'ls -la'",
    "sudo systemctl restart nginx",
    "sudo rm -rf ./cache",       # not a protected target
    "nice -n 5 python train.py",
    "rm --no-preserve-root notes.txt",  # not recursive -> safe (F16)
]


def test_wrapper_and_substitution_evasions_denied(guard):
    for cmd in WRAPPER_EVASIONS:
        d = guard.broker_decision(cmd)
        assert d["decision"] == "deny", f"evasion not blocked: {cmd} -> {d}"


def test_wrappers_no_false_deny_on_safe(guard):
    for cmd in WRAPPER_SAFE:
        d = guard.broker_decision(cmd)
        assert d["decision"] != "deny", f"false-deny on safe wrapper: {cmd} -> {d}"


def test_no_preserve_root_alone_is_not_catastrophic(guard):
    # F16: --no-preserve-root without recursion + protected target must not deny.
    assert guard.broker_decision("rm --no-preserve-root notes.txt")["decision"] != "deny"
    # but with recursion on a protected target it still denies (target check).
    assert guard.broker_decision("rm -rf --no-preserve-root /")["decision"] == "deny"


def test_broker_decision_takes_only_command(guard):
    # F2: dead contract/coverage params removed — single-arg signature.
    import inspect
    params = list(inspect.signature(guard.broker_decision).parameters)
    assert params == ["command"], f"broker_decision should take only 'command', got {params}"


# --- Part C: expanded catastrophic classes found by gap investigation ---
# find <protected> -delete / chmod|chown -R <protected> / shred <block-dev|critical>.
CATASTROPHIC_EXPANDED = [
    "find / -delete", "find /etc -delete", "find ~ -delete", "sudo find / -delete",
    "bash -c 'find / -delete'",
    "chmod -R 000 /", "chmod -R 777 /", "chmod -R 000 ~", "chown -R root /",
    "chgrp -R staff /etc", "sudo chmod -R 000 /", "bash -c 'chmod -R 000 /'",
    "shred /dev/sda", "shred -u /etc/passwd", "shred /boot/vmlinuz", "shred /dev/rdisk0",
]
# Safe variants of the same tools — must NOT be denied (no false-positive).
SAFE_EXPANDED = [
    "find . -name '*.pyc' -delete", "find . -type f", "find /etc -name hosts",
    "chmod -R 755 ./build", "chmod 644 file.txt", "chown -R me ./project",
    "shred ./scratch.tmp", "shred -u ./secret-local.txt",
    "rm -rf ./node_modules", "sudo apt-get update", "git commit -m 'wip'",
    "timeout 5 ./run.sh",
]


def test_expanded_catastrophic_denied(guard):
    for cmd in CATASTROPHIC_EXPANDED:
        assert guard.broker_decision(cmd)["decision"] == "deny", f"should deny: {cmd}"


def test_expanded_safe_not_denied(guard):
    for cmd in SAFE_EXPANDED:
        assert guard.broker_decision(cmd)["decision"] != "deny", f"false-deny: {cmd}"


def test_find_delete_only_on_protected(guard):
    assert guard.broker_decision("find / -delete")["decision"] == "deny"
    assert guard.broker_decision("find . -delete")["decision"] != "deny"       # non-protected path
    assert guard.broker_decision("find /etc -name x")["decision"] != "deny"    # no -delete


def test_recursive_perm_only_on_protected_and_recursive(guard):
    assert guard.broker_decision("chmod -R 000 /")["decision"] == "deny"
    assert guard.broker_decision("chmod 000 /")["decision"] != "deny"          # not recursive
    assert guard.broker_decision("chmod -R 000 ./x")["decision"] != "deny"     # not protected


def test_shred_block_device_and_critical(guard):
    assert guard.broker_decision("shred /dev/sda")["decision"] == "deny"
    assert guard.broker_decision("shred /etc/passwd")["decision"] == "deny"
    assert guard.broker_decision("shred ./local.tmp")["decision"] != "deny"
