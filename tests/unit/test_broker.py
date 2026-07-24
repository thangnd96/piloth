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
