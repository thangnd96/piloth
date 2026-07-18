"""Unit tests for choose_adaptive_mode — blast-radius-aware mode (P7.2).

A trivial change should not pay full standard governance. These pin the
small-scope -> lean rule while keeping strict/standard where risk warrants.
"""


def mode(guard, request, paths, layers=None, target=None):
    m, _decisions = guard.choose_adaptive_mode(request, paths, layers or [], target)
    return m


def test_small_code_scope_is_lean(guard):
    # e.g. a helper + its test — 2 concrete files.
    assert mode(guard, {"task_signal": "API/backend"},
                ["format_currency.py", "test_format_currency.py"]) == "lean"


def test_larger_scope_stays_standard(guard):
    # 4 concrete files exceed the small-scope threshold.
    assert mode(guard, {"task_signal": "API/backend"},
                ["index.html", "styles.css", "app.js", "server.py"]) == "standard"


def test_broad_wildcard_paths_are_not_lean(guard):
    assert mode(guard, {"task_signal": "API/backend"}, ["**/*"]) == "standard"


def test_release_signal_is_strict(guard):
    assert mode(guard, {"task_signal": "release/deploy", "intent": "deploy to prod"},
                ["deploy.sh"]) == "strict"


def test_explicit_mode_is_honored(guard):
    assert mode(guard, {"task_signal": "API/backend", "mode": "strict"},
                ["a.py"]) == "strict"


def test_small_scope_threshold_boundary(guard):
    # exactly SMALL_SCOPE_MAX_PATHS concrete paths is still lean; one more is not.
    n = guard.SMALL_SCOPE_MAX_PATHS
    at = [f"f{i}.py" for i in range(n)]
    over = [f"f{i}.py" for i in range(n + 1)]
    assert mode(guard, {"task_signal": "API/backend"}, at) == "lean"
    assert mode(guard, {"task_signal": "API/backend"}, over) == "standard"
