#!/usr/bin/env python3
"""Context and tool-output footprint meters — vendor tooling, not shipped kernel.

These two meters exist to keep the ratchet tests honest, not to serve a task.
They used to be guard CLI verbs (`context-budget`, `payload-budget`), but the
only callers were this repo's own README and docs — neither of which ships — so
every consumer carried ~170 lines of measurement code that nothing on their side
could invoke. Measuring the kernel is the vendor's job; running on it is the
consumer's.

    context_budget  — kernel markdown a routed task pulls INTO context
    payload_budget  — JSON the guard prints BACK INTO context

Both are ~4 bytes/token estimates. Neither is llm_usage telemetry: they measure
footprint, and a byte reduction cannot on its own back a "cheaper" claim. Real
token and cost numbers come from the guard's `token-telemetry`, which reads the
adapter's own usage records.

Usage:
    python3 scripts/measure_budget.py context '{"task_signal":"bug fix"}'
    python3 scripts/measure_budget.py payload '{"task_signal":"bug fix"}'
"""
import importlib.util
import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
PILOTHOS_DIR = REPO_ROOT / "pilothOS"
BUNDLE = PILOTHOS_DIR / "scripts" / "pilothos_guard.py"


def load_guard():
    """Import the shipped guard bundle so the meters measure what really runs."""
    spec = importlib.util.spec_from_file_location("pilothos_guard", BUNDLE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load_guard()

# The kernel files bootstrap.md prescribes as always-loaded before any task.
BOOTSTRAP_CONTEXT_FILES = (
    "bootstrap.md",
    "PilothOS.md",
    "rules/index.md",
    "runtime/index.md",
    "rot/registry.md",
)

# Append-only ledgers whose size tracks how long an install has been running, not
# how big the kernel is: the auto-log gate appends to them on every session that
# changes files. They are also staged header-only, so they are ~0 bytes for a
# fresh consumer while this repo's own copies keep growing. Counting them would
# make both ceilings a moving target measured against the wrong install.
GROWING_LEDGERS = ("rot/review-log.md", "memory/lessons-learned.md")

# Docs that inflate the full-kernel ceiling without ever being routable context:
# skills/ payloads are only opened while that skill executes, and README/
# VALIDATION document the kernel to humans instead of instructing a task. Kept
# out of the honest denominator so the savings figure is not flattered by text a
# routed task could never have loaded.
NON_ROUTABLE_KERNEL = ("README.md", "VALIDATION.md", "CHANGELOG.md")


def kernel_file_bytes(rel):
    """Byte size of a kernel-relative file, or 0 when it does not exist."""
    try:
        return (PILOTHOS_DIR / rel).stat().st_size
    except OSError:
        return 0


def estimate_context_tokens(num_bytes):
    """Rough context-token estimate (~4 bytes/token). Diagnostic only."""
    return (num_bytes + 3) // 4


def kernel_md_paths():
    """Kernel markdown docs that count toward a ceiling."""
    for path in PILOTHOS_DIR.rglob("*.md"):
        if path.relative_to(PILOTHOS_DIR).as_posix() in GROWING_LEDGERS:
            continue
        yield path


def _footprint(routable_only):
    total = 0
    files = 0
    for path in kernel_md_paths():
        rel = path.relative_to(PILOTHOS_DIR)
        if routable_only and (
            rel.parts[0] == "skills" or rel.as_posix() in NON_ROUTABLE_KERNEL
        ):
            continue
        try:
            total += path.stat().st_size
            files += 1
        except OSError:
            continue
    return files, total


def full_kernel_footprint():
    """(file_count, total_bytes) of every kernel doc — the load-all ceiling."""
    return _footprint(routable_only=False)


def routable_kernel_footprint():
    """(file_count, total_bytes) of the kernel docs a routed task could load."""
    return _footprint(routable_only=True)


def context_budget_payload(payload):
    """Measure the deterministic context footprint of a routed task.

    Reuses the guard's own route_task_payload so the measured set is exactly what
    routing would load: the bootstrap set plus the routed index/context layers.
    """
    if not isinstance(payload, dict):
        return {
            "result": "context_budget_rejected",
            "errors": ["context-budget payload must be a JSON object"],
        }

    routed = []
    routed_ok = False
    if payload.get("task_signal"):
        route = guard.route_task_payload(payload)
        routed_ok = route.get("result") == "route_suggested"
        if routed_ok:
            routed = list(route.get("index_first", [])) + list(
                route.get("context_layers", [])
            )

    loaded = []
    seen = set()
    for rel in list(BOOTSTRAP_CONTEXT_FILES) + routed:
        if rel not in seen:
            seen.add(rel)
            loaded.append(rel)

    loaded_detail = [{"file": rel, "bytes": kernel_file_bytes(rel)} for rel in loaded]
    loaded_bytes = sum(item["bytes"] for item in loaded_detail)
    bootstrap_bytes = sum(kernel_file_bytes(rel) for rel in BOOTSTRAP_CONTEXT_FILES)

    kernel_files, kernel_bytes = full_kernel_footprint()
    saved_bytes = max(kernel_bytes - loaded_bytes, 0)
    savings_pct = round(saved_bytes / kernel_bytes * 100, 1) if kernel_bytes else 0.0
    routable_files, routable_bytes = routable_kernel_footprint()
    routable_savings_pct = (
        round(max(routable_bytes - loaded_bytes, 0) / routable_bytes * 100, 1)
        if routable_bytes else 0.0
    )

    return {
        "result": "context_budget",
        "metric": "context_load",
        "note": "kernel context footprint (bytes/estimated tokens); not llm_usage telemetry",
        "task_signal": payload.get("task_signal") or "not_routed",
        "context_mode": guard.context_mode_from_payload(payload),
        "routed": routed_ok,
        "loaded_files": loaded_detail,
        "loaded_count": len(loaded_detail),
        "loaded_bytes": loaded_bytes,
        "loaded_tokens_est": estimate_context_tokens(loaded_bytes),
        "bootstrap_bytes": bootstrap_bytes,
        "bootstrap_tokens_est": estimate_context_tokens(bootstrap_bytes),
        "full_kernel_files": kernel_files,
        "full_kernel_bytes": kernel_bytes,
        "full_kernel_tokens_est": estimate_context_tokens(kernel_bytes),
        "saved_bytes_vs_full_kernel": saved_bytes,
        "savings_pct_vs_full_kernel": savings_pct,
        # The honest comparison: routable docs only. Lower than the full-kernel
        # figure by design — quote this one when claiming a saving.
        "routable_kernel_files": routable_files,
        "routable_kernel_bytes": routable_bytes,
        "routable_kernel_tokens_est": estimate_context_tokens(routable_bytes),
        "savings_pct_vs_routable_kernel": routable_savings_pct,
    }


# The read-only commands a routed task actually calls, with the smallest
# realistic argument for each. Their JSON lands in the agent's context, so it
# costs tokens exactly like a loaded file — and context_budget never sees it.
PER_TASK_PAYLOAD_PROBES = (
    ("adapter-capabilities", lambda signal: guard.adapter_capabilities_payload({})),
    ("evidence-route", lambda signal: guard.evidence_route_digest(
        guard.evidence_route_payload({
            "task_signal": signal,
            "task_type": "code",
            "scope": "narrow",
        }),
    )),
)


def printed_payload_bytes(payload):
    """Bytes a payload occupies once the guard's json_print has written it."""
    return len(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)) + 1


def payload_budget_payload(payload=None):
    """Per-command tool-output footprint for one routed task."""
    payload = payload if isinstance(payload, dict) else {}
    signal = str(payload.get("task_signal") or "bug fix")
    commands = []
    for name, probe in PER_TASK_PAYLOAD_PROBES:
        try:
            num_bytes = printed_payload_bytes(probe(signal))
        except Exception as e:
            # A broken probe must degrade the meter, never break the caller.
            commands.append({"command": name, "error": str(e)})
            continue
        commands.append({
            "command": name,
            "bytes": num_bytes,
            "tokens_est": estimate_context_tokens(num_bytes),
        })
    total = sum(item.get("bytes", 0) for item in commands)
    return {
        "result": "payload_budget",
        "metric": "tool_output",
        "note": "per-command output footprint (bytes/estimated tokens); not llm_usage telemetry",
        "task_signal": signal,
        "commands": commands,
        "total_bytes": total,
        "total_tokens_est": estimate_context_tokens(total),
    }


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in {"context", "payload"}:
        print(__doc__.strip(), file=sys.stderr)
        return 1
    payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    result = (
        context_budget_payload(payload) if sys.argv[1] == "context"
        else payload_budget_payload(payload)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
