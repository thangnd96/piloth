#!/usr/bin/env python3
"""Sinh pilothOS/dist-manifest.json — SSOT cua 'ban cai hoan chinh' (path theo PROJECT).
Mapping duplicate voi stage.sh co chu dich; linh gac = completeness check (C10)."""
import pathlib, json, sys, datetime
ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent)
MAP = [("pilothOS","pilothOS"),("adapters/claude",".claude"),("adapters/cursor",".cursor"),
       ("adapters/codex",".codex"),("adapters/antigravity",".antigravity"),
       ("templates/CLAUDE.md","CLAUDE.md"),("templates/AGENTS.md","AGENTS.md"),
       ("templates/gitignore",".gitignore"),
       ("pilothOS/skills/workflow/pilothos-init/payloads/settings.json",".claude/settings.json"),
       ("LICENSE","pilothOS/LICENSE"),("CHANGELOG.md","pilothOS/CHANGELOG.md")]
CONSUMER = {"CLAUDE.md","AGENTS.md",".gitignore",".claude/settings.json"}
FACADE = {".claude/commands/pilothos-init.md",".claude/skills/pilothos-init/SKILL.md",
          "pilothOS/skills/workflow/pilothos-init/SKILL.md",
          "pilothOS/skills/workflow/pilothos-init/greenfield.md",
          "pilothOS/skills/workflow/pilothos-init/brownfield.md"}
PERSONALIZE = {"CLAUDE.md","pilothOS/rot/registry.md"}
entries = {}
for src, dest in MAP:
    sp = ROOT / src
    if sp.is_file():
        entries[dest] = None
    elif sp.is_dir():
        for f in sorted(sp.rglob("*")):
            if f.is_file():
                rel = str(f.relative_to(sp))
                entries[f"{dest}/{rel}"] = None
entries.pop("pilothOS/dist-manifest.json", None)
files = []
for path in sorted(entries):
    cls = "installer-facade" if path in FACADE else "consumer-owned" if path in CONSUMER else "verbatim"
    e = {"path": path, "class": cls}
    if path in PERSONALIZE: e["personalize"] = True
    files.append(e)
out = ROOT / "pilothOS" / "dist-manifest.json"
version = json.load(open(ROOT / ".claude-plugin" / "plugin.json", encoding="utf-8"))["version"]
manifest = {
    "schema_version": 1,
    "piloth_version": version,
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "files": files,
}
out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"manifest: {len(files)} files -> {out}")
