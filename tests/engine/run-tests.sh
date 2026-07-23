#!/usr/bin/env bash
# Engine smoke suite: fast deterministic checks for installer contracts.
# Deep install/apply behavior is covered by tests/install/run-tests.sh.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

run_py() { python3 - "$@"; }

echo "== C1 schema-reject (6 cases, 0 writes) =="
snap=$(find . -type f | wc -l)
run_py <<'PY'
import importlib.util
spec=importlib.util.spec_from_file_location('installer','pilothOS/scripts/pilothos_installer.py')
installer=importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
plans=[
 {"plan_version":1,"mode":"greenfield","steps":[{"op":"evil"},{"op":"write_marker"}]},
 {"plan_version":1,"mode":"greenfield","steps":[{"op":"append_lines","target":"/etc/x","lines":["x"]},{"op":"write_marker"}]},
 {"plan_version":1,"mode":"greenfield","steps":[{"op":"append_lines","target":"../up.md","lines":["x"]},{"op":"write_marker"}]},
 {"plan_version":1,"mode":"greenfield","steps":[{"op":"append_lines","target":"pilothOS/bootstrap.md","lines":["x"]},{"op":"write_marker"}]},
 {"plan_version":1,"mode":"greenfield","steps":[{"op":"remove_path","target":"CLAUDE.md"},{"op":"write_marker"}]},
 {"plan_version":1,"mode":"greenfield","hack":1,"steps":[{"op":"write_marker"}]},
]
for plan in plans:
    try:
        installer.validate_and_simulate(plan)
    except (installer.PlanError, installer.NeedsJudgment):
        pass
    else:
        raise AssertionError(f"accepted invalid plan: {plan}")
print('C1 PASS')
PY
[ "$(find . -type f | wc -l)" = "$snap" ]

echo "== C2 merge semantics: conflict, chain, deny wins =="
run_py <<'PY'
import json, importlib.util
spec=importlib.util.spec_from_file_location('installer','pilothOS/scripts/pilothos_installer.py')
installer=importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
payload=json.load(open('pilothOS/skills/workflow/pilothos-init/payloads/settings.json'))
consumer={"permissions":{"allow":["Bash(pnpm:*)","Bash(rm -rf:*)"]},"env":{"PILOTHOS_VERSION":"khac"},"statusLine":{"type":"command","command":"echo consumer"},"hooks":{"Stop":[{"hooks":[{"type":"command","command":"echo c-stop"}]}]}}
try:
    installer.merge_settings_content(consumer, payload, {}, [])
except installer.NeedsJudgment as e:
    types={i['type'] for i in e.items}
    assert {'env_conflict','statusline_conflict'} <= types
else:
    raise AssertionError('expected needs judgment')
consumer['env']={}
notes=[]
merged=installer.merge_settings_content(consumer, payload, {'statusline':'chain'}, notes)
assert len(merged['hooks']['Stop'])==3 and 'c-stop' in json.dumps(merged['hooks']['Stop'][0])
assert 'echo consumer' in merged['statusLine']['command']
assert 'Bash(rm -rf:*)' not in merged['permissions']['allow']
assert any('deny-thang' in n for n in notes)
print('C2 PASS')
PY

echo "== C3 self-prune protected paths =="
run_py <<'PY'
import importlib.util
spec=importlib.util.spec_from_file_location('installer','pilothOS/scripts/pilothos_installer.py')
installer=importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
for tgt in ["pilothOS/skills/workflow/pilothos-init/payloads", "pilothOS/skills/workflow/pilothos-init/manifest-spec.md", "pilothOS/scripts/pilothos_installer.py", ".claude/commands/pilothos-uninstall.md"]:
    plan={"plan_version":1,"mode":"greenfield","steps":[{"op":"remove_path","target":tgt},{"op":"write_marker"}]}
    try:
        installer.validate_and_simulate(plan)
    except installer.PlanError:
        pass
    else:
        raise AssertionError(f"removal unexpectedly allowed: {tgt}")
print('C3 PASS')
PY

echo "ENGINE SUITE: ALL PASS"
