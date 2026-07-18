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
junk = [f['path'] for f in m['files'] if pathlib.PurePosixPath(f['path']).name in ('.DS_Store', 'Thumbs.db') or '__pycache__' in pathlib.PurePosixPath(f['path']).parts]
local_state = [
    f['path'] for f in m['files']
    if f['path'] in {
        'pilothOS/memory/state/scheduler-history.jsonl',
        'pilothOS/memory/state/receipt-seals.jsonl',
    }
    or f['path'].startswith('pilothOS/memory/state/team-runs/')
    or f['path'].startswith('pilothOS/memory/state/os-runs/')
]
assert not missing, missing
assert not junk, junk
assert not local_state, local_state
print(f"  manifest {len(m['files'])} muc — staging du 100%")
EOP
! find . \( -name .DS_Store -o -name Thumbs.db -o -name __pycache__ \) -print -quit | grep -q .
[ ! -f pilothOS/memory/state/scheduler-history.jsonl ]
[ ! -f pilothOS/memory/state/receipt-seals.jsonl ]
[ ! -d pilothOS/memory/state/team-runs ]
[ ! -d pilothOS/memory/state/os-runs ]
echo "C10a PASS"

echo "== C10b brownfield: khong de file consumer =="
mkdir -p $W/bf && cd $W/bf && printf 'my claude\n' > CLAUDE.md && printf 'my readme\n' > README.md && printf 'my lic\n' > LICENSE
bash "$REPO/scripts/stage.sh" "$W/bf" > /dev/null
grep -qx 'my claude' CLAUDE.md && grep -qx 'my readme' README.md && grep -qx 'my lic' LICENSE && [ -f pilothOS/LICENSE ] && echo "C10b PASS: consumer nguyen ven, OS van co license rieng"

echo "== C10b2 brownfield: consumer skills/tools/hooks preserved =="
mkdir -p $W/assets/.claude/skills/design-system $W/assets/.claude/commands $W/assets/scripts
cd $W/assets
printf 'consumer skill\n' > .claude/skills/design-system/SKILL.md
printf 'consumer command\n' > .claude/commands/my-command.md
printf '{"hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"echo consumer"}]}]}}\n' > .claude/settings.json
printf '{"mcpServers":{"figma":{"command":"figma-mcp"}}}\n' > .mcp.json
printf 'test script\n' > scripts/test.sh
printf '{"scripts":{"test":"vitest run"}}\n' > package.json
bash "$REPO/scripts/stage.sh" "$W/assets" > /dev/null
grep -qx 'consumer skill' .claude/skills/design-system/SKILL.md
grep -qx 'consumer command' .claude/commands/my-command.md
grep -q 'echo consumer' .claude/settings.json
grep -q 'figma-mcp' .mcp.json
grep -qx 'test script' scripts/test.sh
grep -q 'vitest run' package.json
echo "C10b2 PASS: consumer userland assets preserved"

echo "== C10b3 brownfield: settings conflicts need judgment =="
mkdir -p $W/conflict/.claude
cd $W/conflict
cat > .claude/settings.json <<'JSON'
{
  "env": {
    "PILOTHOS_VERSION": "consumer-version"
  },
  "statusLine": {
    "type": "command",
    "command": "echo consumer-status"
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {"type": "command", "command": "echo consumer-hook"}
        ]
      }
    ]
  }
}
JSON
before_hash=$(python3 - <<'PY'
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path(".claude/settings.json").read_bytes()).hexdigest())
PY
)
bash "$REPO/scripts/stage.sh" "$W/conflict" > /dev/null
cat > conflict-plan.json <<'JSON'
{
  "plan_version": 1,
  "mode": "brownfield",
  "steps": [
    {"op": "merge_settings", "payload": "settings.json", "target": ".claude/settings.json"},
    {"op": "write_marker"}
  ]
}
JSON
set +e
python3 pilothOS/scripts/pilothos_installer.py dry-run conflict-plan.json > conflict-receipt.json
rc=$?
set -e
[ "$rc" -eq 4 ]
grep -q '"result": "needs_judgment"' conflict-receipt.json
grep -q '"type": "env_conflict"' conflict-receipt.json
grep -q '"type": "statusline_conflict"' conflict-receipt.json
after_hash=$(python3 - <<'PY'
import hashlib, pathlib
print(hashlib.sha256(pathlib.Path(".claude/settings.json").read_bytes()).hexdigest())
PY
)
[ "$after_hash" = "$before_hash" ]
grep -q 'echo consumer-hook' .claude/settings.json
echo "C10b3 PASS: conflicts stop before settings overwrite"

echo "== C10b4 brownfield: hook merge order and dedupe =="
mkdir -p $W/hookmerge/.claude
cd $W/hookmerge
cat > .claude/settings.json <<'JSON'
{
  "env": {
    "PILOTHOS_VERSION": "1.8.3"
  },
  "statusLine": {
    "type": "command",
    "command": "python3 pilothOS/scripts/pilothos_guard.py statusline"
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {"type": "command", "command": "echo consumer-pre"}
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {"type": "command", "command": "python3 pilothOS/scripts/pilothos_guard.py stop-check"}
        ]
      }
    ]
  }
}
JSON
bash "$REPO/scripts/stage.sh" "$W/hookmerge" > /dev/null
cat > hook-merge-plan.json <<'JSON'
{
  "plan_version": 1,
  "mode": "brownfield",
  "steps": [
    {"op": "merge_settings", "payload": "settings.json", "target": ".claude/settings.json"},
    {"op": "write_marker"}
  ]
}
JSON
python3 pilothOS/scripts/pilothos_installer.py apply hook-merge-plan.json > hook-merge-receipt.json
grep -q '"result": "applied"' hook-merge-receipt.json
python3 - <<'PY'
import json
from pathlib import Path

settings = json.loads(Path(".claude/settings.json").read_text(encoding="utf-8"))
pre = settings["hooks"]["PreToolUse"]
assert len(pre) == 2, pre
assert pre[0]["hooks"][0]["command"] == "echo consumer-pre", pre
assert pre[1]["hooks"][0]["command"] == "python3 pilothOS/scripts/pilothos_guard.py pre-edit", pre
stop = settings["hooks"]["Stop"]
assert len(stop) == 1, stop
assert stop[0]["hooks"][0]["command"] == "python3 pilothOS/scripts/pilothos_guard.py stop-check", stop
print("C10b4 PASS: consumer hooks first, Piloth hooks appended, duplicates deduped")
PY

echo "== C10c two-channel equivalence =="
mkdir -p $W/ch1 $W/ch2 && bash "$REPO/scripts/stage.sh" "$W/ch1" > /dev/null && (cd $W/ch2 && CLAUDE_PLUGIN_ROOT="$REPO" bash "$REPO/scripts/stage.sh" > /dev/null)
diff -r $W/ch1 $W/ch2 > /dev/null && echo "C10c PASS: plugin-env va clone-path ra cung ket qua"

echo "== C10d completeness bao dung khi thieu =="
cd $W/gf && rm AGENTS.md
printf '{"plan_version":1,"mode":"greenfield","fill":{"PERSONA":"P","GOALS":"G","OWNER":"O"},"steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},{"op":"write_marker"}]}' > /tmp/c10d.json
python3 pilothOS/scripts/pilothos_installer.py apply /tmp/c10d.json > /tmp/c10d-receipt.json
grep -q '"AGENTS.md"' /tmp/c10d-receipt.json && echo "C10d PASS (engine receipt that, khong duplicate logic)"

echo "== C10e unattended install + upgrade/re-init =="
mkdir -p $W/unatt && bash "$REPO/scripts/stage.sh" "$W/unatt" > /dev/null && cd $W/unatt
python3 pilothOS/scripts/pilothos_installer.py unattended --mode greenfield --persona P --goals G --owner O --adapters claude,codex > receipt.json
grep -q '"result": "applied"' receipt.json
[ -f pilothOS/.initialized ] && [ -d .codex ] && [ ! -d .cursor ] && [ ! -d .antigravity ]
out=$(python3 pilothOS/scripts/pilothos_installer.py validate pilothOS/.pending-plan.json 2>&1 || true)
grep -q "re-init/upgrade" <<< "$out"
printf '{"plan_version":1,"mode":"upgrade","steps":[{"op":"write_marker"}]}' > upgrade-plan.json
out=$(python3 pilothOS/scripts/pilothos_installer.py dry-run upgrade-plan.json)
grep -q '"result": "plan_valid"' <<< "$out"
grep -A2 '"target": "pilothOS/.initialized"' <<< "$out" | grep -q '"kind": "modify"'
bash "$REPO/scripts/stage.sh" --upgrade "$W/unatt" > /dev/null
[ -f pilothOS/.initialized ] && [ -d .codex ] && [ ! -d .cursor ] && [ ! -d .antigravity ]
mkdir -p $W/stageflag
bash "$REPO/scripts/stage.sh" --unattended --dry-run "$W/stageflag" > /dev/null
[ -f $W/stageflag/pilothOS/.pending-plan.json ] && [ ! -f $W/stageflag/pilothOS/.initialized ]
out=$(python3 pilothOS/scripts/pilothos_installer.py unattended --mode upgrade --adapters codez --dry-run 2>&1 || true)
grep -q "unknown adapter" <<< "$out"
echo "C10e PASS"

echo "== sync-templates guard =="
python3 - << EOP
import pathlib
tpl = pathlib.Path("$REPO/templates/CLAUDE.md").read_text(encoding="utf-8")
pay = pathlib.Path("$REPO/pilothOS/skills/workflow/pilothos-init/payloads/identity-block.md").read_text(encoding="utf-8")
assert pay.strip() in tpl, "templates/CLAUDE.md KHONG chua identity payload — drift!"
print("sync-templates PASS")
EOP
echo "INSTALL SUITE: ALL PASS"
