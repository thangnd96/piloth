#!/usr/bin/env python3
"""Sinh pilothOS/dist-manifest.json — SSOT cua 'ban cai hoan chinh' (path theo PROJECT).
Distribution model (MAP + ignore rules) dung chung voi stage.py qua _distribution;
linh gac = completeness check (C10).

Provenance (T4): moi entry co sha256 (hash cua noi dung SOURCE se ship);
manifest_digest = sha256 over sorted 'path:sha256' (content-addressed, tamper-
evident, reproducible); source_commit = git HEAD (fail-soft). Day la analog
BLAKE3-manifest cua AOS — chua phai code signing/Sigstore (xem supply-chain.md)."""
import pathlib, json, sys, datetime, hashlib, subprocess

from _distribution import CONSUMER_OWNED, MAP, ignored_distribution_artifact

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parent.parent)
FACADE = {".claude/commands/pilothos-init.md",".claude/skills/pilothos-init/SKILL.md",
          "pilothOS/skills/workflow/pilothos-init/SKILL.md",
          "pilothOS/skills/workflow/pilothos-init/greenfield.md",
          "pilothOS/skills/workflow/pilothos-init/brownfield.md"}
PERSONALIZE = {"CLAUDE.md","pilothOS/rot/registry.md"}


def _sha256(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _source_commit(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


entries = {}  # dest path -> source Path (de hash noi dung se ship)
for src, dest in MAP:
    sp = ROOT / src
    if sp.is_file():
        if not ignored_distribution_artifact(pathlib.PurePosixPath(sp.name)):
            entries[dest] = sp
    elif sp.is_dir():
        for f in sorted(sp.rglob("*")):
            if f.is_file():
                if ignored_distribution_artifact(f.relative_to(sp)):
                    continue
                rel = str(f.relative_to(sp))
                entries[f"{dest}/{rel}"] = f
entries.pop("pilothOS/dist-manifest.json", None)

files = []
digest_lines = []
for path in sorted(entries):
    src_path = entries[path]
    cls = "installer-facade" if path in FACADE else "consumer-owned" if path in CONSUMER_OWNED else "verbatim"
    sha = _sha256(src_path)
    e = {"path": path, "class": cls, "sha256": sha}
    if path in PERSONALIZE: e["personalize"] = True
    files.append(e)
    digest_lines.append(f"{path}:{sha}")
manifest_digest = hashlib.sha256("\n".join(sorted(digest_lines)).encode("utf-8")).hexdigest()

out = ROOT / "pilothOS" / "dist-manifest.json"
version = json.load(open(ROOT / ".claude-plugin" / "plugin.json", encoding="utf-8"))["version"]
manifest = {
    "schema_version": 1,
    "piloth_version": version,
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "source_commit": _source_commit(ROOT),
    "manifest_digest": manifest_digest,
    "files": files,
}
out.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"manifest: {len(files)} files, digest {manifest_digest[:12]} -> {out}")
