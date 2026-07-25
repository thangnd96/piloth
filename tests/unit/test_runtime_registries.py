"""Schema gates for the JSON registries shipped in pilothOS/runtime/.

These files are policy and contract, not documentation: the guard reads
evidence-routing.json to decide routes, and self-host-check requires
evidence-router-issues.json to exist. Until now nothing validated their shape, so
a typo or a stale entry shipped silently.

evidence-router-issues.json in particular had drifted into a development log —
four of eight entries were `status: "closed"` fixed bugs — while
pilothOS/README.md promises the distribution carries no development history. It
now states present-tense constraints only, and that is enforced here.
"""
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
RUNTIME = REPO / "pilothOS" / "runtime"
ROUTER_ISSUES = RUNTIME / "evidence-router-issues.json"
EVIDENCE_ROUTING = RUNTIME / "evidence-routing.json"

ISSUE_KINDS = {"known_limitation", "invariant", "regression_owner", "merge_gate"}
ISSUE_STATUSES = {"open", "active"}
REQUIRED_ISSUE_FIELDS = {"id", "kind", "status", "owner", "summary"}


@pytest.fixture(scope="module")
def router_issues():
    return json.loads(ROUTER_ISSUES.read_text(encoding="utf-8"))


def test_every_issue_has_the_required_fields(router_issues):
    for issue in router_issues["issues"]:
        missing = REQUIRED_ISSUE_FIELDS - set(issue)
        assert not missing, f"{issue.get('id', '?')} missing {sorted(missing)}"
        for field in REQUIRED_ISSUE_FIELDS:
            assert isinstance(issue[field], str) and issue[field].strip(), (
                f"{issue['id']}.{field} must be a non-empty string"
            )


def test_issue_kinds_and_statuses_are_from_the_closed_vocabulary(router_issues):
    for issue in router_issues["issues"]:
        assert issue["kind"] in ISSUE_KINDS, f"{issue['id']}: unknown kind {issue['kind']}"
        assert issue["status"] in ISSUE_STATUSES, (
            f"{issue['id']}: unknown status {issue['status']}"
        )


def test_no_closed_entry_is_shipped(router_issues):
    """pilothOS/README.md: the distribution ships no development history. A closed
    bug or a removed-scope note is history — it belongs vendor-side."""
    history = [
        issue["id"] for issue in router_issues["issues"]
        if issue["status"] == "closed" or issue["kind"] in {"fixed_bug", "removed_scope"}
    ]
    assert not history, f"development history shipped to consumers: {history}"


def test_issue_ids_are_unique_and_documented_kinds_are_declared(router_issues):
    ids = [issue["id"] for issue in router_issues["issues"]]
    assert len(ids) == len(set(ids)), f"duplicate issue ids: {ids}"
    # The file explains its own vocabulary so a consumer can read it unaided.
    assert set(router_issues["kinds"]) == ISSUE_KINDS
    assert router_issues["contract"].strip()


def test_summaries_are_present_tense_constraints(router_issues):
    """A summary written in the past tense is a changelog line, not a constraint."""
    past_markers = (" was removed", " were removed", " has been fixed", " now lowers")
    offenders = [
        issue["id"] for issue in router_issues["issues"]
        if any(marker in issue["summary"].lower() for marker in past_markers)
    ]
    assert not offenders, f"summaries read as history rather than constraints: {offenders}"


def test_evidence_routing_declares_every_quality_floor_key(guard):
    """The registry must carry the full floor. A missing key still resolves via the
    embedded default, but then the shipped JSON no longer shows the real policy."""
    routing = json.loads(EVIDENCE_ROUTING.read_text(encoding="utf-8"))
    assert set(routing["quality_floor"]) == set(guard.DEFAULT_QUALITY_FLOOR)
    for key, value in routing["quality_floor"].items():
        assert isinstance(value, (int, float)) and not isinstance(value, bool), key


def test_self_host_check_still_requires_the_router_registries(guard):
    """These files are load-bearing: self-host-check fails without them, which is
    why the fix for a stale ledger is to rewrite it, never to delete it."""
    required = guard.self_host_required_manifest_paths()
    assert "pilothOS/runtime/evidence-router-issues.json" in required
    assert "pilothOS/runtime/evidence-routing.json" in required
