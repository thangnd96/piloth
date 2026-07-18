#!/usr/bin/env bash
# Bump version dong loat: sua files theo .version-bump.json -> regenerate manifest -> audit chuoi cu.
set -euo pipefail
cd "$(dirname "$0")/.."
NEW="${1:?Cach dung: bump-version.sh <version-moi>}"
OLD=$(python3 -c "import json;print(json.load(open('.claude-plugin/plugin.json'))['version'])")

if [ "$OLD" = "$NEW" ]; then
python3 - "$NEW" << 'PY'
import json, sys, pathlib
new = sys.argv[1]
cfg = json.load(open(".version-bump.json"))
for item in cfg["files"]:
    text = pathlib.Path(item["path"]).read_text(encoding="utf-8")
    assert new in text, f"THIEU version: {item['path']}"
    print(f"verified {item['path']}")
PY
exit 0
fi

python3 - "$NEW" "$OLD" << 'PY'
import json, sys, pathlib
new, old = sys.argv[1], sys.argv[2]
cfg = json.load(open(".version-bump.json"))
for item in cfg["files"]:
    p = pathlib.Path(item["path"])
    if "field" in item:
        data = json.load(open(p))
        node, keys = data, item["field"].split(".")
        for k in keys[:-1]:
            node = node[int(k)] if k.isdigit() else node[k]
        last = keys[-1]
        if last.isdigit():
            node[int(last)] = new
        else:
            node[last] = new
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        t = p.read_text(encoding="utf-8")
        before = item["pattern"].replace("{VER}", old)
        after = item["pattern"].replace("{VER}", new)
        if before not in t:
            raise AssertionError(f"THIEU pattern version cu trong {p}: {before}")
        t = t.replace(before, after)
        p.write_text(t, encoding="utf-8")
    print(f"bumped {p}")
PY
python3 scripts/build_manifest.py . > /dev/null && echo "manifest regenerated"
python3 - "$NEW" "$OLD" << 'PY'
import json, sys, pathlib
new, old = sys.argv[1], sys.argv[2]
if old == new: sys.exit(0)
ex = json.load(open(".version-bump.json"))["audit"]["exclude"]
hits = []
for f in pathlib.Path(".").rglob("*"):
    if not f.is_file() or any(e in str(f) for e in ex): continue
    try: t = f.read_text(encoding="utf-8")
    except Exception: continue
    if old in t: hits.append(str(f))
print("AUDIT " + ("PASS: khong con " + old if not hits else "FAIL con sot " + old + ": " + ", ".join(hits)))
sys.exit(1 if hits else 0)
PY
