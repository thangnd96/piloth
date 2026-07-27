"""Anti-rot structural gates — keep the cleanup from silently regressing.

- function-length ratchet: no NEW god-function; the existing long ones are
  grandfathered and the allowlist may only shrink (refactor one -> remove it).
- skill structure: every SKILL.md keeps a title and a Purpose section.
- engine size: the shipped single-file engines stay within a declared budget.
"""
import ast
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
GUARD = REPO / "pilothOS" / "scripts" / "pilothos_guard.py"
INSTALLER = REPO / "pilothOS" / "scripts" / "pilothos_installer.py"

MAX_FUNCTION_LINES = 100
# Grandfathered debt at the time this gate landed. Shrink over time by splitting
# these; when one drops to <= MAX it must be removed here (enforced below).
KNOWN_LONG_FUNCTIONS = {
    "control_plane_check_result",
    "os_close_result",
    "os_start",
    "collect_consumer_asset_rows",
}


def _long_functions():
    tree = ast.parse(GUARD.read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            length = node.end_lineno - node.lineno + 1
            if length > MAX_FUNCTION_LINES:
                out[node.name] = length
    return out


def test_no_new_god_functions():
    offenders = {n: ln for n, ln in _long_functions().items()
                 if n not in KNOWN_LONG_FUNCTIONS}
    assert not offenders, (
        f"function(s) over {MAX_FUNCTION_LINES} lines that are not grandfathered "
        f"(split them): {offenders}"
    )


def test_god_function_allowlist_only_shrinks():
    long_now = set(_long_functions())
    stale = sorted(KNOWN_LONG_FUNCTIONS - long_now)
    assert not stale, (
        f"these are no longer over {MAX_FUNCTION_LINES} lines — remove them from "
        f"KNOWN_LONG_FUNCTIONS to keep the ratchet honest: {stale}"
    )


# The shipped engines are amalgamated single files, so they are the one place in
# the payload where growth has no natural brake: pilothos_guard.py went from
# ~8.5k to ~12k lines across two feature commits without any gate noticing.
# Size matters twice over — reading the whole file costs an agent ~120k tokens,
# and a consumer repo carries the file verbatim.
#
# LOWER only. Raising a budget is a deliberate call: split the work into a new
# src/ fragment first and check whether the growth belongs in the engine at all.
ENGINE_LINE_BUDGETS = {
    GUARD: 9_500,
    # Raised 900 -> 920 for `load_plan_arg`: the engine has to accept the plan
    # shape its own documented commands use, and that is input handling, not
    # something a separate fragment would make clearer. Deliberate, per the rule
    # above — check first whether the growth belongs in the engine at all.
    INSTALLER: 920,
}


@pytest.mark.parametrize("engine", sorted(ENGINE_LINE_BUDGETS, key=str))
def test_shipped_engine_stays_within_its_line_budget(engine):
    lines = len(engine.read_text(encoding="utf-8").splitlines())
    budget = ENGINE_LINE_BUDGETS[engine]
    assert lines <= budget, (
        f"{engine.name} is {lines} lines (budget {budget}). Split it or raise "
        "the budget deliberately — this file ships to every consumer."
    )


def test_engine_budgets_stay_close_to_the_measurement():
    """A budget nobody tightened after a refactor stops being a ratchet."""
    for path, budget in ENGINE_LINE_BUDGETS.items():
        lines = len(path.read_text(encoding="utf-8").splitlines())
        assert budget <= lines * 1.35, (
            f"{path.name} budget {budget} is far above its actual {lines}; "
            "lower it so the ratchet keeps biting."
        )


def test_every_pytest_call_site_keeps_its_caches_out_of_the_repo():
    """The mandated verification command must not create work for the janitor.

    `bash tests/run_all.sh` is what the self-hosting contract requires before
    delivery, and artifact-janitor counts `.pytest_cache` / `__pycache__` as local
    artifacts requiring explicit cleanup. A suite that writes them makes
    control-plane-check fail *because* verification had just run — the natural
    order (verify, then check the control plane) could never be green.

    Every call site is discovered by scanning rather than listed: fixing only the
    one suite that was noticed left a second, and a hardcoded list would go stale
    the next time someone adds a pytest invocation.
    """
    offenders = {}
    for script in sorted((REPO / "tests").rglob("run-tests.sh")):
        text = script.read_text(encoding="utf-8")
        invokes = [
            line for line in text.splitlines()
            if "-m pytest" in line and not line.lstrip().startswith("#")
        ]
        if not invokes:
            continue
        missing = [
            setting for setting in ("PYTHONPYCACHEPREFIX=/tmp/", "cache_dir=/tmp/")
            if setting not in text
        ]
        if missing:
            offenders[str(script.relative_to(REPO))] = missing
    assert not offenders, (
        "these suites run pytest without redirecting its caches out of the repo, "
        f"so verification leaves artifacts behind: {offenders}"
    )


def test_every_skill_has_title_and_purpose():
    for skill in sorted((REPO / "pilothOS" / "skills").rglob("SKILL.md")):
        text = skill.read_text(encoding="utf-8")
        rel = skill.relative_to(REPO)
        assert any(line.startswith("# ") for line in text.splitlines()), f"{rel}: no '# ' title"
        assert "## Purpose" in text, f"{rel}: no '## Purpose' section"
