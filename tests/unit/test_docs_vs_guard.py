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


def test_documented_context_footprints_match_the_meter(guard):
    """The published table drifted 16% behind the meter before this gate existed.

    docs/token-optimization.md claimed a bug fix loads 6,966 tokens against a
    57.9k full-kernel ceiling long after the real numbers were 8,069 and 74k, so
    the one artefact consumers read to judge the cost understated it.
    """
    rows = _documented_context_rows()
    assert len(rows) >= 5, f"reference table not parsed (found {len(rows)} rows)"
    for signal, files, num_bytes, tokens in rows:
        measured = guard.context_budget_payload({"task_signal": signal})
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


def _documented_mode_rows():
    """(task_signal, standard, lean, micro) from the mode-aware table.

    | bug fix | ~8,069 | ~4,522 (−44%) | **~3,568 (−56%)** |
    """
    num = r"\*{0,2}~([\d,]+)\*{0,2}(?:\s*\([^)]*\))?\*{0,2}"
    row = re.compile(
        rf"^\|\s*(?P<signal>[A-Za-z/_ ]+?)\s*\|\s*{num}\s*\|\s*{num}\s*\|\s*{num}\s*\|",
    )
    rows = []
    for line in TOKEN_DOC.read_text(encoding="utf-8").splitlines():
        found = row.match(line)
        if found:
            rows.append((
                found["signal"],
                *(int(g.replace(",", "")) for g in found.groups()[1:]),
            ))
    return rows


def test_documented_mode_footprints_match_the_meter(guard):
    """The lean/micro table was unbound: its numbers carry a `~` prefix, which the
    reference-table regex skips, so it could drift while the standard table held."""
    rows = _documented_mode_rows()
    assert len(rows) >= 3, f"mode table not parsed (found {len(rows)} rows)"
    for signal, standard, lean, micro in rows:
        for mode, stated in (("standard", standard), ("lean", lean), ("micro", micro)):
            measured = guard.context_budget_payload(
                {"task_signal": signal, "mode": mode},
            )["loaded_tokens_est"]
            assert stated == measured, (
                f"docs/token-optimization.md mode table says {signal}/{mode} is "
                f"~{stated} tok but context-budget measures {measured}"
            )


def test_documented_kernel_denominators_match_the_meter(guard):
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
    measured = guard.context_budget_payload({"task_signal": "bug fix"})
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


def test_required_contract_receipt_fields_are_documented(guard):
    """rules/hooks.md is the enforcement bible; every field the guard REQUIRES
    on a contract/receipt must be documented there so the doc can't fall behind
    the enforcer as fields are added."""
    hooks = (REPO / "pilothOS" / "rules" / "hooks.md").read_text(encoding="utf-8")
    required = guard.CONTRACT_REQUIRED_FIELDS | guard.RECEIPT_REQUIRED_FIELDS
    missing = sorted(f for f in required if f not in hooks)
    assert not missing, f"rules/hooks.md missing required guard fields: {missing}"
