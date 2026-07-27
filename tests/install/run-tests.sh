#!/usr/bin/env bash
# Install suite (C10 + layout FR-3 + two-channel + sync-templates + completeness reporting)
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
W=$(mktemp -d); trap "rm -rf $W" EXIT
ENG="pilothOS/scripts/pilothos_installer.py"
GRD="pilothOS/scripts/pilothos_guard.py"
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
grep -qx 'pilothOS/' .gitignore
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
  "adapters": ["claude"],
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
# Version lay tu payload cua release, khong hard-code: fixture nay tung ghim
# "2.0.2" nen moi lan bump version la merge_settings bao env_conflict va case
# chet o rc=4, che mat thu no thuc su kiem la thu tu hook. Xung dot env da co
# C10b3 lo.
PILOTHOS_VERSION=$(python3 -c "import json;print(json.load(open('$REPO/pilothOS/skills/workflow/pilothos-init/payloads/settings.json'))['env']['PILOTHOS_VERSION'])")
cat > .claude/settings.json <<JSON
{
  "env": {
    "PILOTHOS_VERSION": "$PILOTHOS_VERSION"
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
  "adapters": ["claude"],
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
printf '{"plan_version":1,"mode":"greenfield","fill":{"PERSONA":"P","GOALS":"G","OWNER":"O"},"adapters":["claude"],"steps":[{"op":"fill_placeholders","target":"CLAUDE.md"},{"op":"write_marker"}]}' > /tmp/c10d.json
python3 pilothOS/scripts/pilothos_installer.py apply /tmp/c10d.json > /tmp/c10d-receipt.json
grep -q '"AGENTS.md"' /tmp/c10d-receipt.json && echo "C10d PASS (engine receipt that, khong duplicate logic)"

echo "== C10e unattended install + upgrade/re-init =="
mkdir -p $W/unatt && bash "$REPO/scripts/stage.sh" "$W/unatt" > /dev/null && cd $W/unatt
python3 pilothOS/scripts/pilothos_installer.py unattended --mode greenfield --persona P --goals G --owner O --adapters claude > receipt.json
grep -q '"result": "applied"' receipt.json
# claude is the only adapter Piloth ships; nothing else may appear on disk
[ -f pilothOS/.initialized ] && [ -d .claude ] && [ ! -d .codex ] && [ ! -d .cursor ] && [ ! -d .antigravity ]
out=$(python3 pilothOS/scripts/pilothos_installer.py validate pilothOS/.pending-plan.json 2>&1 || true)
grep -q "re-init/upgrade" <<< "$out"
printf '{"plan_version":1,"mode":"upgrade","steps":[{"op":"write_marker"}]}' > upgrade-plan.json
out=$(python3 pilothOS/scripts/pilothos_installer.py dry-run upgrade-plan.json)
grep -q '"result": "plan_valid"' <<< "$out"
grep -A2 '"target": "pilothOS/.initialized"' <<< "$out" | grep -q '"kind": "modify"'
bash "$REPO/scripts/stage.sh" --upgrade "$W/unatt" > /dev/null
[ -f pilothOS/.initialized ] && [ -d .claude ] && [ ! -d .codex ] && [ ! -d .cursor ]
mkdir -p $W/stageflag
bash "$REPO/scripts/stage.sh" --unattended --dry-run "$W/stageflag" > /dev/null
[ -f $W/stageflag/pilothOS/.pending-plan.json ] && [ ! -f $W/stageflag/pilothOS/.initialized ]
out=$(python3 pilothOS/scripts/pilothos_installer.py unattended --mode upgrade --adapters codez --dry-run 2>&1 || true)
grep -q "unknown adapter" <<< "$out"
# an adapter Piloth stopped shipping must be rejected, not silently ignored:
# installing nothing while the plan says otherwise is how a consumer ends up
# believing a bridge exists when no file was written
out=$(python3 pilothOS/scripts/pilothos_installer.py unattended --mode upgrade --adapters claude,cursor --dry-run 2>&1 || true)
grep -q "unknown adapter" <<< "$out"
echo "C10e PASS"

echo "== C10g gitignore default: existing .gitignore ignores full pilothOS =="
mkdir -p $W/gi && cd $W/gi && printf 'node_modules/\n' > .gitignore
bash "$REPO/scripts/stage.sh" "$W/gi" > /dev/null   # staging bo qua .gitignore consumer-owned
! grep -q 'pilothOS' .gitignore   # staging mot minh khong them gi
python3 $ENG unattended --mode greenfield --persona P --goals G --owner O --adapters claude > receipt.json
grep -q '"result": "applied"' receipt.json
grep -qx 'pilothOS/' .gitignore
grep -qx 'node_modules/' .gitignore   # dong consumer giu nguyen
echo "C10g PASS: existing .gitignore ignores whole pilothOS/ by default"

echo "== C10h gitignore compatibility opt-in scope=runtime =="
mkdir -p $W/giruntime && cd $W/giruntime && printf 'node_modules/\n' > .gitignore
bash "$REPO/scripts/stage.sh" "$W/giruntime" > /dev/null
python3 $ENG unattended --mode greenfield --persona P --goals G --owner O --adapters claude --gitignore-scope runtime > receipt.json
grep -q '"result": "applied"' receipt.json
grep -qx 'pilothOS/.backup/' .gitignore
grep -qx 'pilothOS/memory/state/os-runs/' .gitignore
! grep -qx 'pilothOS/' .gitignore
echo "C10h PASS: explicit scope=runtime keeps kernel trackable"

echo "== C10i ship-empty ledgers carry no vendor history =="
mkdir -p $W/emptylogs && cd $W/emptylogs
bash "$REPO/scripts/stage.sh" "$W/emptylogs" > /dev/null
python3 - << EOP
import json, pathlib, sys
sys.path.insert(0, "$REPO/scripts")
from _distribution import SHIP_EMPTY_LOGS
manifest = json.load(open("$REPO/pilothOS/dist-manifest.json", encoding="utf-8"))
declared = {f["path"] for f in manifest["files"] if f.get("ship_empty")}
assert declared == SHIP_EMPTY_LOGS, f"manifest ship_empty {declared} != {SHIP_EMPTY_LOGS}"
for rel in sorted(SHIP_EMPTY_LOGS):
    staged = pathlib.Path("$W/emptylogs") / rel
    text = staged.read_text(encoding="utf-8")
    rows = [l for l in text.splitlines()
            if l.strip().startswith("|") and not set(l.strip()) <= set("|-: ")
            and not l.strip().startswith("| Date")]
    assert not rows, f"{rel} staged with vendor history: {rows[:2]}"
    assert "ship TR" in text, f"{rel} lost its header explaining why it is empty"
    # The repo's own copy must KEEP its history — the auto-log gate writes there.
    assert pathlib.Path("$REPO", rel).read_text(encoding="utf-8") != text, (
        f"{rel} was blanked in the Piloth repo, not just on stage")
print("C10i PASS: ledgers ship empty, repo keeps its history")
EOP

echo "== sync-templates guard =="
python3 - << EOP
import pathlib
tpl = pathlib.Path("$REPO/templates/CLAUDE.md").read_text(encoding="utf-8")
pay = pathlib.Path("$REPO/pilothOS/skills/workflow/pilothos-init/payloads/identity-block.md").read_text(encoding="utf-8")
assert pay.strip() in tpl, "templates/CLAUDE.md KHONG chua identity payload — drift!"
print("sync-templates PASS")
EOP
echo "== C11 upgrade khong de lai file mo coi hay hook tro toi chung =="
# v2.0.0 them prune_dead_hooks de go hook tro file da bi xoa, nhung op chi go
# entry tro path KHONG TON TAI, con staging thi khong prune — nen tren dung
# upgrade path file van con, hook khong "dead", va op khong bao gio chay
# (thangnd96/piloth#7). Test cu chi dung fixture khong co file do, tuc no dung
# san dieu kien op can — kiem logic ham, khong kiem duong ham phuc vu.
mkdir -p $W/orphan && cd $W/orphan
bash "$REPO/scripts/stage.sh" "$W/orphan" > /dev/null
python3 $ENG unattended --mode greenfield --persona P --goals G --owner O > /dev/null

# Gia lap install phien ban cu: file ma ban TRUOC tung ship (co trong manifest
# tren dia) nhung ban moi khong con — cong hook tro toi chung. Phai them vao
# manifest cu: tu v2.0.3 prune so manifest cu voi manifest moi, nen file chua
# bao gio duoc ship thi khong phai rac cua ban phan phoi (#12).
mkdir -p pilothOS/tools/review/hooks pilothOS/agent-teams
printf 'exit 0\n' > pilothOS/tools/review/hooks/review-hook.sh
printf '# team\n'  > pilothOS/agent-teams/index.md
python3 - << 'OLDMANIFEST'
import json, pathlib
m = pathlib.Path("pilothOS/dist-manifest.json")
data = json.loads(m.read_text())
for rel in ("pilothOS/tools/review/hooks/review-hook.sh",
            "pilothOS/agent-teams/index.md"):
    data["files"].append({"path": rel, "class": "verbatim"})
m.write_text(json.dumps(data, indent=2))
OLDMANIFEST
python3 - << 'SETUP'
import json, pathlib
p = pathlib.Path(".claude/settings.json"); d = json.loads(p.read_text())
h = d.setdefault("hooks", {})
for ev in ("PreToolUse", "PostToolUse"):
    h.setdefault(ev, []).append({"hooks": [{"type": "command",
        "command": "sh pilothOS/tools/review/hooks/review-hook.sh fire"}]})
h.setdefault("PreToolUse", []).append({"matcher": "Bash", "hooks": [
    {"type": "command", "command": "node .claude/consumer-own.cjs"}]})
p.write_text(json.dumps(d, indent=2))
SETUP
[ -f pilothOS/tools/review/hooks/review-hook.sh ]
[ "$(grep -c review-hook .claude/settings.json)" = "2" ]

# Dung chuoi thao tac SKILL.md mo ta: Re-stage roi Record.
# sleep 1: backup dir dat ten theo giay va do_apply dung exist_ok=False co chu
# dich (hai lan apply khong duoc chung backup), nen greenfield + upgrade trong
# cung mot giay se dung nhau. Khong lien quan den thu test nay kiem.
sleep 1
bash "$REPO/scripts/stage.sh" --upgrade "$W/orphan" > /dev/null
printf '{"plan_version":1,"mode":"upgrade","steps":[{"op":"write_marker"}]}' > up.json
python3 $ENG apply up.json > up-receipt.json
grep -q '"result": "applied"' up-receipt.json

python3 - << 'CHECK'
import json, pathlib, re
ship = {f["path"] for f in json.loads(
    pathlib.Path("pilothOS/dist-manifest.json").read_text())["files"]}
# Runtime state va manifest chinh no khong bao gio nam trong manifest.
PRESERVE = {"pilothOS/dist-manifest.json", "pilothOS/.initialized",
            "pilothOS/.pending-plan.json"}
orphans = sorted(
    p.as_posix() for p in pathlib.Path("pilothOS").rglob("*")
    if p.is_file() and ".backup" not in p.parts and "state" not in p.parts
    and p.as_posix() not in ship and p.as_posix() not in PRESERVE)
assert not orphans, f"file kernel ngoai manifest con lai sau upgrade: {orphans}"

# Hook kiem theo MANIFEST, khong theo exists() — exists() chinh la cho bug an.
settings = json.loads(pathlib.Path(".claude/settings.json").read_text())
dead = [f"{event}: {ref}"
        for event, groups in (settings.get("hooks") or {}).items()
        for g in groups for entry in g.get("hooks", [])
        for ref in re.findall(r"pilothOS/[^\s\"']+", str(entry.get("command", "")))
        if ref not in ship]
assert not dead, f"hook tro path ngoai manifest con lai: {dead}"

cmds = [h["command"] for gs in settings["hooks"].values() for g in gs for h in g["hooks"]]
assert any("consumer-own.cjs" in c for c in cmds), "hook consumer bi xoa nham"
assert any("pilothos_guard.py" in c for c in cmds), "hook Piloth con song bi xoa nham"
print("C11 PASS: upgrade don sach file mo coi va hook cua chung, giu hook consumer")
CHECK

echo "== C12 upgrade khong xoa noi dung do consumer hay kernel tao ra =="
# v2.0.2 prune coi "vang mat trong dist-manifest.json" la "rac cua ban cu". Sai:
# file consumer tu viet, file kernel sinh luc runtime (*-archive.md), va file ma
# kernel CHU DONG MOI consumer tao (knowledge/**) cung khong bao gio o trong
# manifest — nen ca ba nhom deu bi xoa, va rmdir con go luon thu muc rong
# (thangnd96/piloth#12, #13).
mkdir -p $W/keep && cd $W/keep
bash "$REPO/scripts/stage.sh" "$W/keep" > /dev/null
python3 $ENG unattended --mode greenfield --persona P --goals G --owner O > /dev/null

# Danh sach thu muc lay TU DOC, khong hard-code: neu doc doi thi test doi theo.
python3 - << 'SEED'
import pathlib, re
index = pathlib.Path("pilothOS/knowledge/index.md").read_text(encoding="utf-8")
invited = sorted({m for m in re.findall(r"`([a-z]+)/`", index)})
assert invited, "knowledge/index.md khong con moi consumer tao thu muc nao"
pathlib.Path("invited.txt").write_text("\n".join(invited))
for name in invited:
    d = pathlib.Path("pilothOS/knowledge") / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "consumer-fact.md").write_text(f"# fact cua consumer trong {name}\n")
# state-janitor sinh cac file nay khi log vuot nguong; khong co trong manifest
pathlib.Path("pilothOS/rot/review-log-archive.md").write_text("| 2026-01-01 | x |\n")
pathlib.Path("pilothOS/memory/lessons-learned-archive.md").write_text("| 2026-01-01 | y |\n")
# Registry cua consumer, ghi qua chinh `asset-sync` chu khong cay tay: no la
# producer that, va no ghi VAO GIUA cap marker — day la ranh gioi upgrade merge.
pathlib.Path("scan.json").write_text(
    '{"assets":[{"asset":"my-tool","type":"tool","owner":"consumer",'
    '"capability":"build","config_path":"scripts/x.sh","risk":"low",'
    '"load_when":"always","health_check":"ok","confidence":0.9}]}')
SEED
python3 $GRD asset-sync --source scan.json > /dev/null

sleep 1
bash "$REPO/scripts/stage.sh" --upgrade "$W/keep" > /dev/null

python3 - << 'VERIFY'
import pathlib
missing = []
for name in pathlib.Path("invited.txt").read_text().split():
    p = pathlib.Path("pilothOS/knowledge") / name / "consumer-fact.md"
    if not p.exists():
        missing.append(p.as_posix())
for rel in ("pilothOS/rot/review-log-archive.md",
            "pilothOS/memory/lessons-learned-archive.md"):
    if not pathlib.Path(rel).exists():
        missing.append(rel)
assert not missing, f"upgrade xoa noi dung khong phai cua ban phan phoi: {missing}"

registry = pathlib.Path("pilothOS/runtime/consumer-assets.md").read_text(encoding="utf-8")
assert "my-tool" in registry, (
    "consumer-assets.md bi ghi de: row do asset-sync ghi da mat. File nay la "
    "registry cua consumer, khong phai doc thuan cua kernel (#13)")
# Mat con lai cua cung mot seam. Giu nguyen ca file thay vi merge tung duoc thu
# va no dong bang tu vung cua ban cu, khien `self-check` fail va apply rollback —
# upgrade khong con chay duoc. Nen phan ngoai marker PHAI theo ban vendor.
print("C12 PASS: knowledge/**, *-archive.md va row registry deu song sot upgrade")
VERIFY

echo "== C13 prune van go dung thu tung duoc ship =="
# Doi trong voi C12: prune phai VAN lam viec cua no. File tung nam trong manifest
# cu ma khong con o manifest moi la rac that va phai bi go.
cd $W/keep
python3 - << 'SEED2'
import json, pathlib
# gia lap mot file ma ban truoc TUNG ship: co trong manifest tren dia, khong co
# trong ban phan phoi moi
m = pathlib.Path("pilothOS/dist-manifest.json")
data = json.loads(m.read_text())
data["files"].append({"path": "pilothOS/runtime/legacy-subsystem.md", "class": "verbatim"})
m.write_text(json.dumps(data, indent=2))
pathlib.Path("pilothOS/runtime/legacy-subsystem.md").write_text("# he con cua ban cu\n")
SEED2
sleep 1
bash "$REPO/scripts/stage.sh" --upgrade "$W/keep" > /dev/null
[ ! -f pilothOS/runtime/legacy-subsystem.md ]
[ -f pilothOS/rot/review-log-archive.md ]
echo "C13 PASS: go file tung duoc ship, giu file chua bao gio duoc ship"

echo "== C14 upgrade lam moi contract cua consumer-assets.md, giu vung marker =="
# Mat con lai cua seam o C12, va la ca da lam upgrade v1.11.0 -> v2.0.3 rollback:
# `self-check` doi file nay mang tu vung cua ban HIEN TAI, nen giu nguyen ca file
# se dong bang tu vung cu -> self-check FAIL -> apply rollback -> khong the nang
# cap. Phan ngoai marker phai theo vendor, phan trong marker phai theo consumer.
mkdir -p $W/seam && cd $W/seam
bash "$REPO/scripts/stage.sh" "$W/seam" > /dev/null
python3 $ENG unattended --mode greenfield --persona P --goals G --owner O > /dev/null
python3 - << 'AGED'
import pathlib
# mot ban "cu": thieu tu vung ma release nay yeu cau, co san vung marker cua consumer
pathlib.Path("pilothOS/runtime/consumer-assets.md").write_text(
    "# Consumer Asset Registry\n\nban cu, khong co tu vung moi\n\n"
    "<!-- PILOTHOS-GENERATED-ASSETS:START -->\n"
    "| `my-tool` | tool | consumer |\n"
    "<!-- PILOTHOS-GENERATED-ASSETS:END -->\n", encoding="utf-8")
AGED
sleep 1
bash "$REPO/scripts/stage.sh" --upgrade "$W/seam" > /dev/null
python3 - << 'SEAM'
import pathlib
text = pathlib.Path("pilothOS/runtime/consumer-assets.md").read_text(encoding="utf-8")
assert "specialist" in text, (
    "upgrade khong lam moi contract: tu vung cua release nay vang mat, "
    "`self-check` se fail va apply rollback")
assert "my-tool" in text, "upgrade lam mat vung marker cua consumer"
SEAM
# phep do quyet dinh: sau upgrade, self-check phai xanh
python3 $GRD self-check > /dev/null
echo "C14 PASS: contract theo vendor, vung marker theo consumer, self-check xanh"

echo "INSTALL SUITE: ALL PASS"
