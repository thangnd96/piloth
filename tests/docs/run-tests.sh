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
(cd "$TMP/repo" && bash scripts/bump-version.sh 1.11.0 > "$TMP/bump.log")
grep -Fq "verified .claude-plugin/plugin.json" "$TMP/bump.log"
echo "D2 PASS"

echo "== D3 documented uninstall path =="
[ -f commands/uninstall.md ]
! grep -q "pilothOS/skills/workflow/pilothos-uninstall/SKILL.md" README.md
echo "D3 PASS"

echo "== D4 staged gitignore =="
grep -qx "pilothOS/.backup/" templates/gitignore
grep -qx "pilothOS/.pending-plan.json" templates/gitignore
grep -qx "pilothOS/memory/state/scheduler-history.jsonl" templates/gitignore
grep -qx "pilothOS/memory/state/receipt-seals.jsonl" templates/gitignore
grep -qx "pilothOS/memory/state/\*.jsonl" templates/gitignore
grep -qx "pilothOS/memory/state/team-runs/" templates/gitignore
grep -qx "pilothOS/memory/state/os-runs/" templates/gitignore
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

structure = pathlib.Path("docs/structure.md").read_text(encoding="utf-8")
if not pathlib.Path(".github").exists():
    assert ".github/" not in structure

readme = pathlib.Path("README.md").read_text(encoding="utf-8")
match = re.search(r"└── pilothOS/.*?```", readme, re.S)
assert match, "README PilothOS tree not found"
assert "adapters/" not in match.group(0), "README still lists pilothOS/adapters/"
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
    "pilothOS/memory/state/scheduler-history.jsonl",
    "pilothOS/memory/state/receipt-seals.jsonl",
}
for forbidden in forbidden_manifest:
    assert forbidden not in paths, f"manifest must not ship local state: {forbidden}"
assert not any(path.startswith("pilothOS/memory/state/team-runs/") for path in paths), "manifest must not ship team-runs local state"
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
for needle in ("Self-Hosting Contract", "contract-write", "receipt-write", "route-task", "scheduler-suggest", "scheduler-record", "state-doctor", "team-contract-write", "team-receipt-write", "scripts/build_manifest.py", "detected_signals", "repo-local entries", "edited_paths", "learning_suggestions", "duplicated_helper", "receipt-seal", "receipt-verify", "allowed_entitlements", "project-local OS", "production-review", "artifact-janitor", "control-plane-check"):
    assert needle in self_hosting, f"self-hosting.md missing {needle}"

os_control = pathlib.Path("pilothOS/runtime/os-control-plane.md").read_text(encoding="utf-8")
for needle in ("consumer project", "project-local OS", "allowed_entitlements", "receipt-seal", "receipt-verify", "SHA-256", "not code signing", "artifact-janitor", "control-plane-check"):
    assert needle in os_control, f"os-control-plane.md missing {needle}"

team_runtime = pathlib.Path("pilothOS/runtime/team-orchestration.md").read_text(encoding="utf-8")
for needle in ("role-<role>.md", "qa-verdict.md", "final-lead-decision.md", "edited_paths"):
    assert needle in team_runtime, f"team-orchestration.md missing {needle}"
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
