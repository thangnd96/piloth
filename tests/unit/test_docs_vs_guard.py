"""Bind human docs to the guard's machine SSOT so they cannot silently diverge.

The docs are prose — context-adapted and self-sufficient under progressive
context loading — so we DETECT drift rather than generate the prose (generating
into sentences would be invasive and low-value; see PR2 D10-vs-D11). Every claim
or field the docs promise must actually be backed by the guard's enforcing
constants; these tests fail if a doc out-runs the enforcer.
"""
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[2]
TOKEN_DOC = REPO / "docs" / "token-optimization.md"
# The SHIPPED home of token/cost policy. docs/ is vendor-side — it is not in
# dist-manifest.json, so anything documented only there is invisible to consumers.
ENERGY_DOC = REPO / "pilothOS" / "runtime" / "energy-token-policy.md"

# Absolute-claim terms the runtime docs (quality-gates / task-lifecycle /
# os-control-plane) state os-close rejects. If the matcher stops catching one,
# the docs would be lying — fail here rather than let enforcer/doc diverge.
DOCUMENTED_REJECTED_CLAIMS = [
    "1:1", "pixel-perfect", "production-ready", "fully verified",
    "no issues", "full", "complete", "all tokens", "entire library",
]


def test_documented_absolute_claims_are_enforced(guard):
    unmatched = [t for t in DOCUMENTED_REJECTED_CLAIMS
                 if not guard.ABSOLUTE_CLAIM_RE.search(t)]
    assert not unmatched, (
        "docs promise these absolute claims are rejected but ABSOLUTE_CLAIM_RE "
        f"no longer matches them: {unmatched}"
    )


def _documented_context_rows():
    """(task_signal, files, bytes, est_tokens) from the reference table.

    | not_applicable   |   7   | 22,084 |    5,521   |     92.6%      |    84.9%    |
    """
    row = re.compile(
        r"^\|\s*(?P<signal>[A-Za-z/_ ]+?)\s*\|\s*(?P<files>\d+)\s*\|"
        r"\s*(?P<bytes>[\d,]+)\s*\|\s*(?P<tokens>[\d,]+)\s*\|",
    )
    rows = []
    for line in TOKEN_DOC.read_text(encoding="utf-8").splitlines():
        found = row.match(line)
        if found:
            rows.append((
                found["signal"],
                int(found["files"]),
                int(found["bytes"].replace(",", "")),
                int(found["tokens"].replace(",", "")),
            ))
    return rows


def test_documented_context_footprints_match_the_meter(budget):
    """The published table drifted 16% behind the meter before this gate existed.

    docs/token-optimization.md claimed a bug fix loads 6,966 tokens against a
    57.9k full-kernel ceiling long after the real numbers were 8,069 and 74k, so
    the one artefact consumers read to judge the cost understated it.
    """
    rows = _documented_context_rows()
    assert len(rows) >= 5, f"reference table not parsed (found {len(rows)} rows)"
    for signal, files, num_bytes, tokens in rows:
        measured = budget.context_budget_payload({"task_signal": signal})
        assert measured["routed"] is True, signal
        assert (files, num_bytes, tokens) == (
            measured["loaded_count"],
            measured["loaded_bytes"],
            measured["loaded_tokens_est"],
        ), (
            f"docs/token-optimization.md row '{signal}' says "
            f"{files} files / {num_bytes} bytes / {tokens} tok but context-budget "
            f"measures {measured['loaded_count']} / {measured['loaded_bytes']} / "
            f"{measured['loaded_tokens_est']}. Re-run context-budget and update "
            "the table."
        )


def test_documented_kernel_denominators_match_the_meter(budget):
    """Both ceilings must be stated, and within 3% of the meter.

    Exact-match here would fail on any 200-byte kernel doc edit, which is noise:
    the claim being guarded is that the published ceiling is not materially
    understated, the way "57.9k" was once the real figure had reached 74k.
    """
    doc = TOKEN_DOC.read_text(encoding="utf-8")
    # Written as e.g. "77 file, ~74.7k token".
    stated = {
        int(files): float(tokens)
        for files, tokens in re.findall(
            r"(\d+) file, ~([\d.]+)k token", doc,
        )
    }
    measured = budget.context_budget_payload({"task_signal": "bug fix"})
    for files, tokens, label in (
        (measured["full_kernel_files"], measured["full_kernel_tokens_est"], "full"),
        (
            measured["routable_kernel_files"],
            measured["routable_kernel_tokens_est"],
            "routable",
        ),
    ):
        assert files in stated, (
            f"docs/token-optimization.md states no '{files} file, ~Xk token' "
            f"ceiling for the {label} kernel (measured {tokens} tok)"
        )
        assert abs(stated[files] * 1000 - tokens) <= tokens * 0.03, (
            f"{label} kernel ceiling in docs/token-optimization.md is "
            f"~{stated[files]}k but the meter says {tokens} tok; re-run "
            "context-budget and update it."
        )


# ------------------- cost ledger / budget fields must ship their documentation

# Grandfathered: ledger metrics that predate this gate. May only SHRINK — the
# companion test below fails if one of these is documented but left listed.
# Deliberately not documented in bulk: energy-token-policy.md is routable kernel
# context, and adding ~700 bytes of field glossary would work against the very
# footprint the release measures. The gate exists to stop NEW consumer-visible
# fields from shipping undocumented, which is the failure that actually happened.
UNDOCUMENTED_LEDGER_KEYS = {
    "benchmark_results",
    "context_loads",
    "duration_ms",
    "metric_records",
    "note",
    "real_tokens",
    "repairs",
    "retries",
    "schema_version",
    "token_unavailable_reasons",
    "tool_output_chars",
}


def _ledger_and_budget_keys(guard):
    """Every key `os-status` / `os-report` expose from the cost ledger + budget.

    Derived by calling the producers instead of hardcoding a list, so a field
    added later is caught automatically with nothing to keep in sync.
    """
    llm = {
        "kind": "metric", "metric_type": "llm_usage",
        "metric_name": "session-token-usage", "real_token_telemetry": True,
        "input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
        "cache_creation_input_tokens": 1, "cache_read_input_tokens": 1,
        "cost_usd": 0.1, "cost_complete": False,
        "unpriced_models": ["x-model"], "unpriced_tokens": 5,
        "window_start": "2026-01-01T00:00:00Z",
        "recorded_at": "2026-01-01T00:01:00Z",
    }
    ledger = guard.cost_ledger_summary([llm])
    budget = guard.budget_status({"budget": {"max_usd": 1.0}}, [llm])
    keys = set(ledger) | set(budget)
    real = ledger.get("real_tokens")
    if isinstance(real, dict):
        keys |= set(real)
    return keys


def test_cost_ledger_fields_are_documented_in_a_shipped_doc(guard):
    """A consumer-visible field documented only in docs/ never reaches consumers.

    That already happened once: the cost subtotal semantics landed in
    docs/token-optimization.md, which dist-manifest does not ship. Checking "any
    shipped doc" would be too weak — a field name can appear in a shipped
    rot/review-log.md row without being documented at all — so this binds to the
    doc that owns the topic.
    """
    doc = ENERGY_DOC.read_text(encoding="utf-8")
    missing = sorted(
        key for key in _ledger_and_budget_keys(guard)
        if key not in UNDOCUMENTED_LEDGER_KEYS and key not in doc
    )
    assert not missing, (
        "cost ledger/budget fields exposed to consumers but absent from "
        f"{ENERGY_DOC.relative_to(REPO)}: {missing}. Document them there (docs/ "
        "is vendor-side and is not shipped), or grandfather them explicitly."
    )


def test_undocumented_ledger_allowlist_only_shrinks(guard):
    """Document a grandfathered key and it must leave the allowlist."""
    doc = ENERGY_DOC.read_text(encoding="utf-8")
    keys = _ledger_and_budget_keys(guard)
    stale = sorted(k for k in UNDOCUMENTED_LEDGER_KEYS if k in doc)
    assert not stale, (
        "these are documented now — remove them from UNDOCUMENTED_LEDGER_KEYS to "
        f"keep the ratchet honest: {stale}"
    )
    gone = sorted(k for k in UNDOCUMENTED_LEDGER_KEYS if k not in keys)
    assert not gone, (
        "these are no longer emitted by the ledger/budget — drop them from "
        f"UNDOCUMENTED_LEDGER_KEYS: {gone}"
    )


def test_required_contract_receipt_fields_are_documented(guard):
    """rules/hooks.md is the enforcement bible; every field the guard REQUIRES
    on a contract/receipt must be documented there so the doc can't fall behind
    the enforcer as fields are added."""
    hooks = (REPO / "pilothOS" / "rules" / "hooks.md").read_text(encoding="utf-8")
    required = guard.CONTRACT_REQUIRED_FIELDS | guard.RECEIPT_REQUIRED_FIELDS
    missing = sorted(f for f in required if f not in hooks)
    assert not missing, f"rules/hooks.md missing required guard fields: {missing}"
