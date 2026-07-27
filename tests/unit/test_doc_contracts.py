"""Bind every doc that states a machine-enforced value back to the enforcer.

The repo keeps hitting one bug class, logged four times in
`pilothOS/memory/lessons-learned.md`: a file declares a condition ("ships
EMPTY", "these gates are required", "these are the valid signals") and nothing
checks that the declaration is still true. Each of these tests picks one such
declaration and makes it fail loudly when the doc and the code disagree.

Two rules for anything added here:

1. Parse the doc, never restate its content in the test. A hardcoded expected
   list is a fourth copy of the fact and drifts exactly like the other three —
   which is what `DOCUMENTED_REJECTED_CLAIMS` used to be.
2. Compare values, not shapes. `set(a) == set(b)` on keys passes while
   `route_confidence` silently drops from 0.80 to 0.5.
"""
import json
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
KERNEL = REPO / "pilothOS"
EVIDENCE_ROUTING = KERNEL / "runtime" / "evidence-routing.json"
EVIDENCE_ROUTER_DOC = KERNEL / "runtime" / "evidence-router.md"
CONTEXT_LOADING = KERNEL / "runtime" / "context-loading.md"
QUALITY_GATES = KERNEL / "evaluation" / "quality-gates.md"
OS_CONTROL_PLANE = KERNEL / "runtime" / "os-control-plane.md"
STATE_README = KERNEL / "memory" / "state" / "README.md"
KERNEL_README = KERNEL / "README.md"


def _read(path):
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------- quality floor

def test_routing_json_quality_floor_matches_the_guard_values(guard):
    """Key-set equality let a value drift silently.

    The previous gate asserted `set(json) == set(DEFAULT_QUALITY_FLOOR)`, so
    editing the shipped JSON to `route_confidence: 0.5` changed every routing
    decision and still passed the whole suite.
    """
    routing = json.loads(_read(EVIDENCE_ROUTING))["quality_floor"]
    assert routing == pytest.approx(guard.DEFAULT_QUALITY_FLOOR), (
        "evidence-routing.json quality_floor drifted from DEFAULT_QUALITY_FLOOR"
    )


def test_router_doc_states_the_same_floor_numbers_as_the_guard(guard):
    """The prose in evidence-router.md is bound to nothing; bind it."""
    doc = _read(EVIDENCE_ROUTER_DOC)
    floor = guard.DEFAULT_QUALITY_FLOOR
    expected = {
        "max_non_inferiority_delta_pp": rf"{floor['max_non_inferiority_delta_pp']} percentage points",
        "route_confidence": rf"`{floor['route_confidence']:.2f}`",
        "specialist_score": rf"at least {floor['specialist_score']}",
    }
    missing = [k for k, pat in expected.items() if not re.search(pat, doc)]
    assert not missing, (
        f"evidence-router.md no longer states these floor values: {missing}. "
        "Update the prose (or the guard) so they agree."
    )


# ------------------------------------------------------------- task signals

def _documented_signals():
    """The copy-paste enum a consumer reads out of context-loading.md."""
    match = re.search(r'"task_signal":\s*"([^"]+)"', _read(CONTEXT_LOADING))
    assert match, "context-loading.md no longer shows a task_signal enum"
    return {s.strip() for s in match.group(1).split("|")}


def test_documented_task_signal_enum_matches_the_validator(guard):
    """Two signals were missing from the doc for a whole release.

    `architecture` and `security` are accepted by the validator and have real
    routes, but the enum a consumer copies from listed neither — so no consumer
    could discover them.
    """
    assert _documented_signals() == {
        s.strip() for s in guard.ASSET_ROUTING_SIGNALS
    }


def test_documented_routing_table_covers_every_route(guard):
    """The routing table and TASK_SIGNAL_ROUTES must name the same signals."""
    rows = re.findall(r"^\|\s*([A-Za-z/_ ]+?)\s*\|.*\|.*\|$",
                      _read(CONTEXT_LOADING), re.M)
    documented = {r.strip().lower() for r in rows} - {"task signal"}
    routed = set(guard.TASK_SIGNAL_ROUTES)
    assert routed <= documented, (
        f"context-loading.md routing table is missing routes: {sorted(routed - documented)}"
    )


def test_documented_load_policies_match_the_routes(guard):
    """A signal documented as task-routed while the guard requires approval is a
    consumer walking into an approval gate the doc said was not there."""
    table = re.findall(r"^\|\s*([A-Za-z/_ ]+?)\s*\|[^|]*\|\s*([a-z-]+)\s*\|$",
                       _read(CONTEXT_LOADING), re.M)
    documented = {sig.strip().lower(): policy.strip() for sig, policy in table}
    for signal, route in guard.TASK_SIGNAL_ROUTES.items():
        if signal in documented:
            assert documented[signal] == route["load_policy"], (
                f"{signal}: doc says {documented[signal]}, guard routes {route['load_policy']}"
            )


# ------------------------------------------------------------- required gates

def test_documented_base_gates_match_required_gates_for_task(guard):
    """quality-gates.md shipped a table that was false in `lean` mode.

    Both lean tiers are gone, so the unconditional statement is true again — this
    pins it, so a future mode cannot make the shipped doc lie a second time.
    """
    row = re.search(r"^\|\s*Any OS-closed task\s*\|\s*(.+?)\s*\|$",
                    _read(QUALITY_GATES), re.M)
    assert row, "quality-gates.md no longer has the 'Any OS-closed task' row"
    documented = {g.strip().strip("`") for g in row.group(1).split(",")}
    actual = set(guard.required_gates_for_task({}, {}))
    assert documented <= actual, (
        f"quality-gates.md promises gates the guard does not require: {sorted(documented - actual)}"
    )


def test_documented_code_change_gates_match_the_guard(guard):
    """The second row: code changes add architecture/reuse/regression."""
    row = re.search(r"^\|\s*Code/runtime/rules/adapter/tool changes\s*\|\s*(.+?)\s*\|$",
                    _read(QUALITY_GATES), re.M)
    assert row, "quality-gates.md no longer has the code-change row"
    documented = {g.strip().strip("`") for g in row.group(1).split(",")
                  if "base gates" not in g}
    actual = set(guard.required_gates_for_task(
        {"affected_layers": ["Tools/Runtime"]},
        {"changed_files": ["src/guard/00_header.py"]},
    ))
    assert documented <= actual, sorted(documented - actual)


# ----------------------------------------------------------------- constants

@pytest.mark.parametrize(("const", "doc", "pattern"), [
    ("STATE_RETENTION_KEEP_RUNS", OS_CONTROL_PLANE, r"`N={value}`"),
    ("STATE_RETENTION_KEEP_DAYS", OS_CONTROL_PLANE, r"`X={value}`"),
    ("KERNEL_LOG_KEEP_ROWS", OS_CONTROL_PLANE, r"default {value}"),
    ("RECEIPT_SEALS_WARN_LINES", OS_CONTROL_PLANE, r"{value} dòng|{value} lines"),
])
def test_retention_constants_are_documented_with_their_real_value(guard, const, doc, pattern):
    """Retention defaults lived in the guard and in three docs, bound by nothing.

    RECEIPT_SEALS_WARN_LINES was worse: it existed in code and was documented
    nowhere, so the threshold that triggers a warning was invisible to whoever
    had to act on it.
    """
    value = getattr(guard, const)
    assert re.search(pattern.format(value=value), _read(doc)), (
        f"{doc.name} does not state {const}={value}"
    )


def test_adapter_capability_count_is_derived_not_hardcoded(guard):
    """Five places said '15 capabilities'. Only the registry decides."""
    count = len(guard.ADAPTER_CAPABILITY_KEYS)
    doc = _read(EVIDENCE_ROUTER_DOC)
    stated = {int(n) for n in re.findall(r"all (\d+) capabilities", doc)}
    assert stated in ({count}, set()), (
        f"evidence-router.md states {stated} capabilities, registry has {count}"
    )
    registry = json.loads(_read(KERNEL / "runtime" / "adapter-capabilities.json"))
    profiles = registry.get("adapters") or registry
    for name, profile in profiles.items():
        if isinstance(profile, dict) and "capabilities" in profile:
            assert set(profile["capabilities"]) == set(guard.ADAPTER_CAPABILITY_KEYS), (
                f"adapter {name} declares a different capability set than the guard"
            )


# ------------------------------------------------------- absolute-claim terms

def test_absolute_claim_terms_in_docs_are_all_actually_rejected(guard):
    """Three docs listed the rejected terms and disagreed with each other, while
    the test carried a hardcoded fourth copy. Parse instead: every term a shipped
    doc promises to reject must really be rejected."""
    docs = [KERNEL / "runtime" / "task-lifecycle.md", QUALITY_GATES, OS_CONTROL_PLANE]
    claimed = set()
    for path in docs:
        for line in _read(path).splitlines():
            if "1:1" not in line:
                continue
            claimed |= {t.strip("`.,;:()") for t in re.findall(r"`([^`]+)`", line)}
    claimed = {t for t in claimed if t and not t.startswith("os-")}
    assert claimed, "no doc lists the rejected absolute claims any more"
    survivors = [t for t in sorted(claimed) if not guard.ABSOLUTE_CLAIM_RE.search(t)]
    assert not survivors, (
        f"docs promise to reject these but the guard accepts them: {survivors}"
    )


# --------------------------------------------------------- layer index contract

def test_every_layer_index_declares_its_boundary():
    """`pilothOS/README.md` states the contract; this is what makes it true.

    The contract used to list six sections "khi áp dụng" — an escape hatch that
    made it unenforceable, and half the index files used it. It now names three
    unconditional sections, so it can be checked.
    """
    required = ["Purpose", "Responsibilities", "Non-Responsibilities"]
    contract = _read(KERNEL_README)
    for section in required:
        assert f"`{section}`" in contract, (
            f"pilothOS/README.md no longer requires {section}; this test and the "
            "contract must be changed together"
        )
    offenders = {}
    for index in sorted(KERNEL.glob("*/index.md")):
        heads = set(re.findall(r"^##+\s+(.+?)\s*$", _read(index), re.M))
        missing = [s for s in required if s not in heads]
        if missing:
            offenders[index.relative_to(REPO).as_posix()] = missing
    assert not offenders, f"index files missing boundary sections: {offenders}"


# ------------------------------------------- references resolve to shipped files

DIST_MANIFEST = KERNEL / "dist-manifest.json"
# index.md / SKILL.md / README.md exist all over the kernel: naming one bare is a
# reference to a KIND of file, not to a location. Anything else is a path claim.
STRUCTURAL_FILENAMES = {"index.md", "SKILL.md", "README.md"}
MD_REF_RE = re.compile(r"`([A-Za-z0-9._/-]+\.md)`")


def _shipped_paths():
    return {item["path"] for item in json.loads(_read(DIST_MANIFEST))["files"]}


def _resolves_to_shipped(index_path, ref, shipped):
    """sibling → kernel root → repo root.

    Three bases because index tables legitimately use all three: a layer index
    names its own siblings, a cross-layer note uses a kernel-relative path, and
    `agents/index.md` points at the consumer's root `CLAUDE.md` (Identity lives
    outside the kernel by design, and CLAUDE.md does ship).
    """
    for candidate in (index_path.parent / ref, KERNEL / ref, REPO / ref):
        try:
            rel = candidate.resolve().relative_to(REPO).as_posix()
        except ValueError:
            continue
        if rel in shipped:
            return True
    return False


SLASH_CMD_RE = re.compile(r"`?/piloth:([a-z][a-z0-9-]*)`?")


def _reference_docs(shipped):
    """index.md + SKILL.md — the two kinds a consumer follows to act.

    index.md is how progressive context loading decides what to open; SKILL.md is
    a procedure someone types. A dead reference in either sends the reader after
    something that is not there, which is worse than dead prose.
    """
    for pattern in ("**/index.md", "skills/**/SKILL.md"):
        for doc in sorted(KERNEL.glob(pattern)):
            if doc.relative_to(REPO).as_posix() in shipped:
                yield doc


def test_every_documented_slash_command_ships_a_command_file():
    """`/piloth:adapter` survived in pilothos-update/SKILL.md through v2.0.1.

    Rule 1 missed it twice over: it is not a `.md` path, and it is not in an
    index.md (thangnd96/piloth#9). For a CLI's own docs a verb name is a
    first-class reference — same as a path.
    """
    shipped = _shipped_paths()
    verbs = {
        path.rsplit("/", 1)[-1].removeprefix("pilothos-").removesuffix(".md")
        for path in shipped if path.startswith(".claude/commands/")
    }
    offenders = []
    for doc in _reference_docs(shipped):
        rel = doc.relative_to(REPO).as_posix()
        for lineno, line in enumerate(_read(doc).splitlines(), 1):
            for verb in SLASH_CMD_RE.findall(line):
                if verb not in verbs:
                    offenders.append(f"{rel}:{lineno} -> /piloth:{verb}")
    assert not offenders, (
        f"doc names a slash command with no shipped command file (have: "
        f"{sorted(verbs)}):\n  " + "\n  ".join(offenders)
    )


def test_every_index_reference_resolves_to_a_shipped_file():
    """An index that names a file the distribution does not contain.

    v2.0.0 deleted four subsystems and left six references behind: three
    team-role rows in agents/index.md, two rows in runtime/index.md and a line in
    tools/index.md. A consumer's first real upgrade found them
    (thangnd96/piloth#5, #6). Nothing caught it because D1b only asks whether a
    backticked path is vendor-only, never whether it exists.

    Upgrade from v1.x hides this class of defect: staging does not prune, so the
    v1 file stays on disk and the path still resolves. Only a fresh install sees
    it — which is why this gate reads dist-manifest.json rather than the disk.
    """
    shipped = _shipped_paths()
    offenders = []
    for index_path in _reference_docs(shipped):
        rel = index_path.relative_to(REPO).as_posix()
        for lineno, line in enumerate(_read(index_path).splitlines(), 1):
            for ref in MD_REF_RE.findall(line):
                if "/" not in ref and ref in STRUCTURAL_FILENAMES:
                    continue
                if not _resolves_to_shipped(index_path, ref, shipped):
                    offenders.append(f"{rel}:{lineno} -> {ref}")
    assert not offenders, (
        "index references a file the distribution does not ship:\n  "
        + "\n  ".join(offenders)
    )


def test_every_routed_context_path_is_shipped(guard):
    """Routing that loads a file which is not there.

    `task_signal: architecture` routed to knowledge/architecture/README.md for
    the whole v2.0.0 release. These paths are kernel-relative by construction, so
    unlike prose there is nothing to disambiguate — either the file ships or the
    route is broken.
    """
    shipped = _shipped_paths()
    offenders = []
    matrix = json.loads(_read(EVIDENCE_ROUTING)).get("task_matrix", {})
    for signal, row in matrix.items():
        for path in row.get("context", []):
            if f"pilothOS/{path}" not in shipped:
                offenders.append(f"evidence-routing.json[{signal}].context -> {path}")
    for signal, route in guard.TASK_SIGNAL_ROUTES.items():
        for path in route["context_layers"]:
            if f"pilothOS/{path}" not in shipped:
                offenders.append(f"TASK_SIGNAL_ROUTES[{signal}] -> {path}")
    for path in guard.BOOTSTRAP_CONTEXT_FILES if hasattr(
        guard, "BOOTSTRAP_CONTEXT_FILES") else ():
        if f"pilothOS/{path}" not in shipped:
            offenders.append(f"BOOTSTRAP_CONTEXT_FILES -> {path}")
    assert not offenders, "routed context path is not shipped:\n  " + "\n  ".join(offenders)


def test_routing_json_and_guard_declare_the_same_context(guard):
    """The same context list lives in two files; nothing compared them.

    thangnd96/piloth#5 guessed that duplicating the literal was the root cause of
    the architecture drift. It already was: `ui/component` had drifted too —
    consumer-assets.md in the JSON, context-loading.md in the guard — and no one
    noticed, because the two were never compared. Same failure mode the quality
    floor had before this file started comparing values instead of key sets.
    """
    matrix = json.loads(_read(EVIDENCE_ROUTING)).get("task_matrix", {})
    mismatches = []
    for signal, route in guard.TASK_SIGNAL_ROUTES.items():
        documented = list(matrix.get(signal, {}).get("context", []))
        enforced = list(route["context_layers"])
        if documented != enforced:
            mismatches.append(f"{signal}: json={documented} guard={enforced}")
    assert not mismatches, (
        "evidence-routing.json and TASK_SIGNAL_ROUTES disagree:\n  "
        + "\n  ".join(mismatches)
    )


STAGE_SCRIPT = REPO / "scripts" / "stage.py"
UPDATE_SKILL = KERNEL / "skills" / "workflow" / "pilothos-update" / "SKILL.md"


def test_every_staging_flag_the_docs_mention_is_handled_explicitly():
    """A documented flag that no branch knows about is worse than a missing one.

    `--adapters` was documented for staging and never implemented
    (thangnd96/piloth#8). Because `parse_args` ends in a catch-all
    `elif arg.startswith("--")`, the space form pushed its value into `targets`
    and hard-failed with "qua nhieu target", while the `=` form was forwarded and
    silently did nothing — the consumer believed they had selected an adapter.

    The same catch-all hides `--gitignore-scope`, a flag that IS real. Nobody
    reported that one; it was found by comparing the two tables.
    """
    stage_src = _read(STAGE_SCRIPT)
    known = set(re.findall(r'"(--[a-z][a-z-]*)"', stage_src))
    documented = set(re.findall(r"`(--[a-z][a-z-]*)[ =`]", _read(UPDATE_SKILL)))
    unknown = sorted(documented - known)
    assert not unknown, (
        f"pilothos-update/SKILL.md documents staging flags that stage.py never "
        f"names: {unknown}. Implement them or stop documenting them — the "
        "catch-all branch turns an unknown flag into a silent no-op."
    )


def test_staging_knows_every_value_flag_the_installer_accepts():
    """stage.py's option table is a hand-copy of the installer's argparse.

    It drifted: `--adapters` and `--gitignore-scope` both take a value, and
    stage.py did not know it, so `--gitignore-scope runtime <target>` read the
    value as a second target and failed. Forwarding is only safe when the wrapper
    knows the arity.
    """
    installer_src = _read(REPO / "src" / "installer" / "05_unattended.py")
    takes_value = {
        flag for flag in re.findall(r'add_argument\("(--[a-z-]+)"', installer_src)
        if f'add_argument("{flag}", action="store_true")' not in installer_src
    }
    stage_src = _read(STAGE_SCRIPT)
    block = re.search(r"INSTALLER_VALUE_OPTIONS = \{(.*?)\}", stage_src, re.S).group(1)
    known = set(re.findall(r'"(--[a-z-]+)"', block))
    missing = sorted(takes_value - known)
    assert not missing, (
        f"installer takes a value for {missing} but stage.py's "
        "INSTALLER_VALUE_OPTIONS does not list them; the space form will be "
        "parsed as an extra target"
    )
