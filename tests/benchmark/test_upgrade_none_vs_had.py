"""TB benchmark — none-piloth vs had-piloth for T6 upgrade self-heal.

Probe #7 for T6: upgrading Piloth preserves consumer customization. none-piloth
(a fork / blind re-copy) clobbers the consumer's edits on upgrade; had-piloth
(stage --upgrade) preserves them while still updating the kernel.
"""
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
STAGE = REPO / "scripts" / "stage.py"


def _stage(target, *args):
    subprocess.run([sys.executable, str(STAGE), str(target), *args],
                   check=True, capture_output=True, text=True)


def test_none_vs_had_upgrade_benchmark(tmp_path):
    # had-piloth: governed upgrade preserves the consumer's CLAUDE.md edit.
    had = tmp_path / "had"
    had.mkdir()
    _stage(had)
    hc = had / "CLAUDE.md"
    hc.write_text(hc.read_text(encoding="utf-8") + "\n# CUSTOM\n", encoding="utf-8")
    _stage(had, "--upgrade")
    had_preserved = "# CUSTOM" in hc.read_text(encoding="utf-8")

    # none-piloth: an ungoverned upgrade re-copies the shipped template over the
    # consumer file (a fork / blind copy) -> the customization is lost.
    none = tmp_path / "none"
    none.mkdir()
    _stage(none)
    nc = none / "CLAUDE.md"
    nc.write_text(nc.read_text(encoding="utf-8") + "\n# CUSTOM\n", encoding="utf-8")
    shutil.copy2(REPO / "templates" / "CLAUDE.md", nc)  # naive overwrite on upgrade
    none_preserved = "# CUSTOM" in nc.read_text(encoding="utf-8")

    assert had_preserved is True
    assert none_preserved is False

    consumer_value_passed = had_preserved and not none_preserved
    assert consumer_value_passed
