#!/usr/bin/env bash
# Install suite (C10 + layout FR-3 + two-channel + sync-templates + completeness reporting)
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W=$(mktemp -d); trap "rm -rf $W" EXIT
ENG="pilothOS/scripts/pilothos_installer.py"
CMD_TIMEOUT="${CMD_TIMEOUT:-20s}"

echo "== C10a greenfield: layout FR-3 + completeness =="
mkdir -p $W/gf && bash "$REPO/scripts/stage.sh" "$W/gf" > /dev/null && cd $W/gf
[ ! -f README.md ] && [ ! -f CHANGELOG.md ] && [ ! -f LICENSE ] && echo "  root consumer sach (FR-3)"
[ -f pilothOS/README.md ] && [ -f pilothOS/CHANGELOG.md ] && [ -f pilothOS/LICENSE ] && echo "  docs+license theo pilothOS/"
python3 - << 'EOP'
import json
m = json.load(open('pilothOS/dist-manifest.json'))
import pathlib
missing = [f['path'] for f in m['files'] if f['class'] in ('verbatim','consumer-owned') and not pathlib.Path(f['path']).exists()]
assert not missing, missing
print(f"  manifest {len(m['files'])} muc — staging du 100%")
EOP
echo "C10a PASS"

echo "== C10b brownfield: khong de file consumer =="
mkdir -p $W/bf && cd $W/bf && printf 'my claude\n' > CLAUDE.md && printf 'my readme\n' > README.md && printf 'my lic\n' > LICENSE
bash "$REPO/scripts/stage.sh" "$W/bf" > /dev/null
grep -qx 'my claude' CLAUDE.md && grep -qx 'my readme' README.md && grep -qx 'my lic' LICENSE && [ -f pilothOS/LICENSE ] && echo "C10b PASS: consumer nguyen ven, OS van co license rieng"

echo "== C10c two-channel equivalence =="
mkdir -p $W/ch1 $W/ch2 && bash "$REPO/scripts/stage.sh" "$W/ch1" > /dev/null && (cd $W/ch2 && CLAUDE_PLUGIN_ROOT="$REPO" bash "$REPO/scripts/stage.sh" > /dev/null)
diff -r $W/ch1 $W/ch2 > /dev/null && echo "C10c PASS: plugin-env va clone-path ra cung ket qua"

echo "== C10d completeness bao dung khi thieu =="
cd $W/gf && rm AGENTS.md
printf '{"plan_version":1,"mode":"greenfield","fill":{"PERSONA":"P","GOALS":"G","OWNER":"O"},"steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},{"op":"write_marker"}]}' > /tmp/c10d.json
python3 pilothOS/scripts/pilothos_installer.py apply /tmp/c10d.json > /tmp/c10d-receipt.json
grep -q '"AGENTS.md"' /tmp/c10d-receipt.json && echo "C10d PASS (engine receipt that, khong duplicate logic)"

echo "== sync-templates guard =="
python3 - << EOP
import pathlib
tpl = pathlib.Path("$REPO/templates/CLAUDE.md").read_text(encoding="utf-8")
pay = pathlib.Path("$REPO/pilothOS/skills/workflow/pilothos-init/payloads/identity-block.md").read_text(encoding="utf-8")
assert pay.strip() in tpl, "templates/CLAUDE.md KHONG chua identity payload — drift!"
print("sync-templates PASS")
EOP
echo "INSTALL SUITE: ALL PASS"
