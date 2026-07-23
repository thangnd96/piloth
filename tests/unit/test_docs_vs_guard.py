"""Bind human docs to the guard's machine SSOT so they cannot silently diverge.

The docs are prose — context-adapted and self-sufficient under progressive
context loading — so we DETECT drift rather than generate the prose (generating
into sentences would be invasive and low-value; see PR2 D10-vs-D11). Every claim
or field the docs promise must actually be backed by the guard's enforcing
constants; these tests fail if a doc out-runs the enforcer.
"""
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

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


def test_required_contract_receipt_fields_are_documented(guard):
    """rules/hooks.md is the enforcement bible; every field the guard REQUIRES
    on a contract/receipt must be documented there so the doc can't fall behind
    the enforcer as fields are added."""
    hooks = (REPO / "pilothOS" / "rules" / "hooks.md").read_text(encoding="utf-8")
    required = guard.CONTRACT_REQUIRED_FIELDS | guard.RECEIPT_REQUIRED_FIELDS
    missing = sorted(f for f in required if f not in hooks)
    assert not missing, f"rules/hooks.md missing required guard fields: {missing}"
