#!/usr/bin/env bash
# Docs/release smoke checks: local links, release bump config, and staged ignore rules.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

echo "== D1 local markdown links =="
python3 - <<'PY'
import pathlib
import re
import sys
from urllib.parse import unquote

repo = pathlib.Path.cwd().resolve()
docs = [pathlib.Path("README.md")] + sorted(pathlib.Path("docs").glob("*.md"))
link_re = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
failures = []

for doc in docs:
    text = doc.read_text(encoding="utf-8")
    for raw in link_re.findall(text):
        target = raw.strip().strip("<>")
        if not target or target.startswith("#"):
            continue
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
            continue
        path_part = target.split("#", 1)[0]
        if not path_part:
            continue
        resolved = (doc.parent / unquote(path_part)).resolve()
        if repo not in resolved.parents and resolved != repo:
            failures.append(f"{doc}: link escapes repo: {target}")
        elif not resolved.exists():
            failures.append(f"{doc}: missing link target: {target}")

if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit(1)
print(f"D1 PASS: {len(docs)} docs checked")
PY

echo "== D1b staged docs never link outside the distribution =="
# A doc that ships into a consumer project may only reference paths that ship with
# it. pilothOS/runtime/codebase-intelligence.md pointed at docs/codebase-memory-plan.md,
# which is vendor-side: the link resolved here and was dead in every consumer.
python3 - <<'PY'
import importlib.util
import pathlib
import re
import sys
from urllib.parse import unquote

spec = importlib.util.spec_from_file_location("dist", "scripts/_distribution.py")
dist = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dist)

staged_roots = [pathlib.Path(src) for src, _ in dist.MAP]


def is_staged(path):
    return any(path == root or root in path.parents for root in staged_roots)


repo = pathlib.Path.cwd().resolve()
link_re = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
# Inline references like `docs/foo.md` are prose, not links, but a staged doc
# naming a vendor-only path is the same defect, so both are checked.
inline_re = re.compile(r"`([A-Za-z0-9._/-]+\.(?:md|json|py))`")
failures = []
checked = 0

for doc in sorted(pathlib.Path("pilothOS").rglob("*.md")):
    if not is_staged(doc):
        continue
    checked += 1
    text = doc.read_text(encoding="utf-8", errors="replace")
    targets = [t.strip().strip("<>") for t in link_re.findall(text)]
    for raw in targets:
        if not raw or raw.startswith("#") or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw):
            continue
        path_part = unquote(raw.split("#", 1)[0])
        if not path_part:
            continue
        resolved = (doc.parent / path_part).resolve()
        try:
            rel = resolved.relative_to(repo)
        except ValueError:
            failures.append(f"{doc}: link escapes repo: {raw}")
            continue
        if not resolved.exists():
            failures.append(f"{doc}: missing link target: {raw}")
        elif not is_staged(rel):
            failures.append(
                f"{doc}: links to {rel} which is NOT staged into a consumer "
                "(vendor-only path; state the content inline instead)"
            )
    # A staged doc MAY reference a vendor path when it says so on the same line —
    # self-hosting.md legitimately maps "in the Piloth source repo: scripts/stage.py".
    # Naming one silently is the defect, because a consumer reads it as their path.
    vendor_context = ("source repo", "vendor", "piloth repo", "repo cua piloth")
    for line in text.splitlines():
        if any(hint in line.lower() for hint in vendor_context):
            continue
        for raw in inline_re.findall(line):
            rel = pathlib.Path(raw)
            if rel.parts and rel.parts[0] in {"docs", "scripts", "src", "tests"} and not is_staged(rel):
                failures.append(
                    f"{doc}: names vendor-only path `{raw}` with no vendor context; "
                    "a consumer will not have it"
                )

if failures:
    print("\n".join(sorted(set(failures))), file=sys.stderr)
    raise SystemExit(1)
print(f"D1b PASS: {checked} staged docs checked against the distribution MAP")
PY
echo "D1b PASS"

echo "== D2 version bump smoke =="
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
python3 - "$REPO" "$TMP/repo" <<'PY'
import pathlib
import shutil
import sys

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
shutil.copytree(
    src,
    dst,
    ignore=shutil.ignore_patterns(".git", ".DS_Store", "__pycache__", "pilothOS/.backup"),
)
PY
# Exercises the no-op branch (new == current), so read the version instead of
# hardcoding it — a literal here breaks on every release bump, and also trips the
# bump audit that scans the tree for leftovers of the previous version.
CUR_VER=$(python3 -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['version'])")
(cd "$TMP/repo" && bash scripts/bump-version.sh "$CUR_VER" > "$TMP/bump.log")
grep -Fq "verified .claude-plugin/plugin.json" "$TMP/bump.log"
echo "D2 PASS"

echo "== D3 documented uninstall path =="
[ -f commands/uninstall.md ]
! grep -q "pilothOS/skills/workflow/pilothos-uninstall/SKILL.md" README.md
echo "D3 PASS"

echo "== D4 staged gitignore =="
grep -qx "pilothOS/" templates/gitignore
# Engine SSOT (PILOTHOS_GITIGNORE_LINES) phai khop template — chong drift giua
# nhanh greenfield-chua-co-gitignore (template) va normalize (engine append).
python3 - <<'PY'
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location("installer", "pilothOS/scripts/pilothos_installer.py")
inst = importlib.util.module_from_spec(spec); spec.loader.exec_module(inst)
tpl = [l for l in pathlib.Path("templates/gitignore").read_text(encoding="utf-8").splitlines() if l.strip()]
assert inst.PILOTHOS_GITIGNORE_LINES == tpl, (
    f"drift: PILOTHOS_GITIGNORE_LINES != templates/gitignore\n"
    f"engine={inst.PILOTHOS_GITIGNORE_LINES}\ntemplate={tpl}")
print("  engine SSOT khop templates/gitignore")
PY
echo "D4 PASS"

echo "== D5 structure docs match shipped roots =="
python3 - <<'PY'
import pathlib
import re
import sys

failures = []
structure = pathlib.Path("docs/structure.md").read_text(encoding="utf-8")
if not pathlib.Path(".github").exists():
    assert ".github/" not in structure

readme = pathlib.Path("README.md").read_text(encoding="utf-8")
match = re.search(r"└── pilothOS/.*?```", readme, re.S)
assert match, "README PilothOS tree not found"
assert "adapters/" not in match.group(0), "README still lists pilothOS/adapters/"

# Every directory a structure tree claims must exist. pilothOS/README.md advertised
# `pilothOS/adapters/` for several releases while the adapters live at the project
# root; a tree naming a directory nobody ships is exactly the drift these docs are
# supposed to prevent.
#
# A doc holds several trees with different roots (piloth/, adapters/, src/,
# pilothOS/ ...). An unindented `name/` line opens a new root, resolved against the
# repo root; indented `├── name/` lines resolve against the root currently open.
TREE_DOCS = ["docs/structure.md", "pilothOS/README.md"]
root_re = re.compile(r"^([A-Za-z0-9._/-]+)/\s*(?:#.*)?$")
child_re = re.compile(r"^[│├└─\s]+([A-Za-z0-9._-]+)/\s*(?:#.*)?$")


def resolve_root(name):
    """Where a tree's root label lives, or None when the tree describes something
    outside this repo (e.g. the `consumer-project/` example)."""
    if name == "piloth":
        return pathlib.Path(".")          # the repo's own name
    if pathlib.Path(name).is_dir():
        return pathlib.Path(name)
    inside_kernel = pathlib.Path("pilothOS") / name
    if inside_kernel.is_dir():
        return inside_kernel              # kernel subtrees are documented relative to pilothOS/
    return None


for doc in TREE_DOCS:
    for block in re.findall(r"```text\n(.*?)```", pathlib.Path(doc).read_text(encoding="utf-8"), re.S):
        root = pathlib.Path(".")
        for line in block.splitlines():
            top = root_re.match(line)
            if top:
                root = resolve_root(top.group(1))
                continue
            if root is None:
                continue                  # tree describes a consumer project, not this repo
            child = child_re.match(line)
            if not child:
                continue
            name = child.group(1)
            if not (root / name).is_dir():
                failures.append(
                    f"{doc}: tree names a directory that does not exist: {root / name}/"
                )

# Every top-level repo directory must be documented, so a new area cannot be added
# without saying what it is. `src/` — the actual source of the shipped guard — was
# missing from this tree entirely.
IGNORED_ROOTS = {".git", ".github", ".claude", ".claude-plugin", ".pytest_cache"}
for child in sorted(pathlib.Path(".").iterdir()):
    if not child.is_dir() or child.name in IGNORED_ROOTS:
        continue
    if f"{child.name}/" not in structure:
        failures.append(f"docs/structure.md: undocumented top-level directory: {child.name}/")

# Every suite in the release gate must be listed in the tests/ section.
suites = re.search(r'^SUITES="([^"]+)"', pathlib.Path("tests/run_all.sh").read_text(encoding="utf-8"), re.M)
assert suites, "run_all.sh SUITES not found"
for suite in suites.group(1).split():
    top = suite.split("/", 1)[0]
    if f"{top}/" not in structure:
        failures.append(f"docs/structure.md: release-gate suite not documented: tests/{top}/")

if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit(1)
PY
echo "D5 PASS"

echo "== D6 no stale enforcement claims =="
! grep -R "pre-edit.*post-edit.*no-op" docs pilothOS
! grep -R "re-init/upgrade chua ho tro" docs pilothOS
echo "D6 PASS"

echo "== D7 adapter bridge instructions stay thin =="
python3 - <<'PY'
import pathlib

checks = [
    pathlib.Path("templates/AGENTS.md"),
    pathlib.Path("adapters/cursor/rules/pilothos-core.mdc"),
    pathlib.Path("adapters/antigravity/rules/pilothos-core.md"),
    pathlib.Path("adapters/codex/config.toml"),
]

for path in checks:
    text = path.read_text(encoding="utf-8").lower()
    compact = " ".join(text.replace("#", " ").replace("`", " ").split())
    assert "os entry point" in compact, f"{path}: missing OS entry point"
    assert "contract-write" in compact, f"{path}: missing contract-write"
    assert "receipt-write" in compact, f"{path}: missing receipt-write"
    assert "do not bypass consumer skills" in compact, f"{path}: missing consumer skill bypass rule"
    assert "hooks" in compact and "tools" in compact and "design systems" in compact, f"{path}: missing consumer hooks/tools/DS"
    assert "do not fork" in compact and "policy" in compact, f"{path}: missing no-fork-policy rule"
print("D7 PASS")
PY

echo "== D8 runtime energy policy is shipped and indexed =="
python3 - <<'PY'
import json
import pathlib

runtime_index = pathlib.Path("pilothOS/runtime/index.md").read_text(encoding="utf-8")
energy = pathlib.Path("pilothOS/runtime/energy-token-policy.md")
assert energy.exists(), "missing energy-token-policy.md"
assert "energy-token-policy.md" in runtime_index, "runtime index missing energy-token-policy.md"
text = energy.read_text(encoding="utf-8")
for needle in ("Progressive loading", "tool-check", "large_delta_reason", "Build/Test"):
    assert needle in text, f"energy-token-policy.md missing {needle}"
manifest = json.loads(pathlib.Path("pilothOS/dist-manifest.json").read_text(encoding="utf-8"))
paths = {item["path"] for item in manifest["files"]}
forbidden_manifest = {
    "pilothOS/memory/state/receipt-seals.jsonl",
}
for forbidden in forbidden_manifest:
    assert forbidden not in paths, f"manifest must not ship local state: {forbidden}"
assert not any(path.startswith("pilothOS/memory/state/os-runs/") for path in paths), "manifest must not ship os-runs local state"
assert "pilothOS/runtime/energy-token-policy.md" in paths, "manifest missing energy policy"
print("D8 PASS")
PY

echo "== D9 consumer-aware OS docs are indexed and shipped =="
python3 - <<'PY'
import json
import pathlib

runtime_index = pathlib.Path("pilothOS/runtime/index.md").read_text(encoding="utf-8")
rules_index = pathlib.Path("pilothOS/rules/index.md").read_text(encoding="utf-8")
manifest = json.loads(pathlib.Path("pilothOS/dist-manifest.json").read_text(encoding="utf-8"))
paths = {item["path"] for item in manifest["files"]}

required_manifest = {
    "pilothOS/runtime/consumer-assets.md",
    "pilothOS/runtime/energy-token-policy.md",
    "pilothOS/runtime/os-control-plane.md",
    "pilothOS/runtime/self-hosting.md",
    "pilothOS/rules/ui-design-system.md",
}
missing = sorted(required_manifest - paths)
assert not missing, f"manifest missing consumer-aware files: {missing}"
assert "consumer-assets.md" in runtime_index, "runtime index missing consumer-assets.md"
assert "energy-token-policy.md" in runtime_index, "runtime index missing energy-token-policy.md"
assert "os-control-plane.md" in runtime_index, "runtime index missing os-control-plane.md"
assert "self-hosting.md" in runtime_index, "runtime index missing self-hosting.md"
assert "ui-design-system.md" in rules_index, "rules index missing ui-design-system.md"

consumer_assets = pathlib.Path("pilothOS/runtime/consumer-assets.md").read_text(encoding="utf-8")
for needle in (
    "PilothOS là control plane",
    "Asset | Type | Owner | Capability | Config/Path | Risk | Load When | Health Check | Notes",
    "Detected At",
    "detected_signals",
    "manifest_status",
    ".agents/",
    "tests/**/run-tests.sh",
    "asset-sync --source scan.json",
    "preserve",
    "route",
    "needs-judgment",
):
    assert needle in consumer_assets, f"consumer-assets.md missing {needle}"
self_hosting = pathlib.Path("pilothOS/runtime/self-hosting.md").read_text(encoding="utf-8")
for needle in ("Self-Hosting Contract", "contract-write", "receipt-write", "state-doctor", "scripts/build_manifest.py", "detected_signals", "receipt-seal", "receipt-verify", "allowed_entitlements", "project-local OS", "production-review", "artifact-janitor", "control-plane-check"):
    assert needle in self_hosting, f"self-hosting.md missing {needle}"

os_control = pathlib.Path("pilothOS/runtime/os-control-plane.md").read_text(encoding="utf-8")
for needle in ("consumer project", "project-local OS", "allowed_entitlements", "receipt-seal", "receipt-verify", "SHA-256", "not code signing", "artifact-janitor", "control-plane-check"):
    assert needle in os_control, f"os-control-plane.md missing {needle}"
print("D9 PASS")
PY

echo "== D10 generated doc blocks in sync with SSOT =="
python3 scripts/sync_docs.py --check
echo "D10 PASS"

echo "== D11 startup-contract copy still covers bootstrap's targets =="
# The baked copy (payloads/startup-contract-block.md, "for tools that don't read
# bootstrap") is a context-adapted paraphrase, not a byte copy — it uses full
# pilothOS/ paths and its own wording — so it cannot be generated verbatim. This
# guards the drift it warns about: every doc target bootstrap's Startup Contract
# names must still be referenced by the copy. Fuzzy on purpose (targets, not prose).
python3 - <<'PY'
import pathlib, re
boot = pathlib.Path("pilothOS/bootstrap.md").read_text(encoding="utf-8")
m = re.search(r"## Startup Contract\n(.*?)\n## ", boot, re.S)
assert m, "bootstrap.md: Startup Contract section not found"
targets = sorted(set(re.findall(r"`([^`]+\.md)`", m.group(1))))
assert targets, "bootstrap.md Startup Contract: no doc targets parsed"
copy = pathlib.Path("pilothOS/skills/workflow/pilothos-init/payloads/startup-contract-block.md").read_text(encoding="utf-8")
missing = [t for t in targets if t not in copy and f"pilothOS/{t}" not in copy]
assert not missing, (
    f"startup-contract-block.md missing bootstrap targets: {missing}\n"
    "  nguon chuan: pilothOS/bootstrap.md — cap nhat ban sao (bootstrap wins)")
print(f"  copy mirrors {len(targets)} bootstrap startup targets")
PY
echo "D11 PASS"

echo "DOCS SUITE: ALL PASS"
