# --------------------------------------------------------------- team v5

def preflight():
    """Preflight cua /pilothos-init: kiem tra moi truong, fail som va ro rang."""
    import os
    ok = True

    def check(cond, msg_ok, msg_fail):
        nonlocal ok
        if cond:
            print(f"OK   {msg_ok}")
        else:
            ok = False
            print(f"FAIL {msg_fail}")

    check(os.access(REPO_ROOT, os.W_OK),
          f"repo root ghi duoc: {REPO_ROOT}",
          f"repo root KHONG ghi duoc: {REPO_ROOT}")
    claude_dir = REPO_ROOT / ".claude"
    check(claude_dir.exists() and os.access(claude_dir, os.W_OK)
          or (not claude_dir.exists() and os.access(REPO_ROOT, os.W_OK)),
          ".claude/ ghi duoc hoac tao duoc",
          ".claude/ KHONG ghi duoc")
    if SETTINGS.exists():
        try:
            json.load(open(SETTINGS, encoding="utf-8"))
            print(f"OK   settings.json hien co hop le")
        except json.JSONDecodeError as e:
            ok = False
            print(f"FAIL settings.json hien co KHONG hop le: {e} — sua truoc khi init")
    else:
        print("OK   chua co settings.json (se duoc tao/merge o Apply)")
    missing = [f.name for f in CORE_FILES if not f.exists()]
    check(not missing,
          "cay pilothOS/ day du core files",
          f"cay pilothOS/ THIEU: {', '.join(missing)} — ban phan phoi loi hoac dirty install")
    print("PREFLIGHT " + ("PASSED" if ok else "FAILED"))


def detect():
    """Stage 0 cua /pilothos-init: verdict + evidence. KHONG tu re nhanh —
    agent phai trinh bay ket qua va CHO CONSUMER CONFIRM."""
    evidence = []
    if INIT_MARKER.exists():
        print("VERDICT: re-init")
        print(f"EVIDENCE: {INIT_MARKER} ton tai — "
              f"noi dung: {INIT_MARKER.read_text(encoding='utf-8').strip()}")
        print("NOTE: co the upgrade bang staging --upgrade va installer mode=upgrade; "
              "khong chay lai greenfield/brownfield plan tren project da init.")
        return
    missing = [f.name for f in CORE_FILES if not f.exists()]
    if missing:
        print("VERDICT: dirty")
        print(f"EVIDENCE: pilothOS/ ton tai nhung thieu core files: {', '.join(missing)}")
        print("NOTE: co the la lan init/copy truoc bi do dang. De xuat: xoa pilothOS/ "
              "va copy lai ban phan phoi, hoac phuc hoi tu .backup/manifest neu co.")
        return
    root_claude = REPO_ROOT / "CLAUDE.md"
    if root_claude.exists():
        content = root_claude.read_text(encoding="utf-8", errors="replace")
        if "@pilothOS/bootstrap.md" in content:
            evidence.append("CLAUDE.md o root da import bootstrap cua PilothOS (ban phan phoi full-copy)")
        else:
            evidence.append("CLAUDE.md o root la cua consumer (KHONG import bootstrap PilothOS)")
    for name in ("AGENTS.md",):
        f = REPO_ROOT / name
        if f.exists() and "PilothOS" not in f.read_text(encoding="utf-8", errors="replace"):
            evidence.append(f"{name} cua consumer ton tai")
    for hint in CONSUMER_ASSET_HINTS:
        if (REPO_ROOT / hint).exists():
            evidence.append(f"tai san consumer: {hint}")
    for adir in ADAPTER_DIRS:
        d = REPO_ROOT / adir
        if d.exists():
            extra = _non_pilothos_content(d)
            if extra:
                evidence.append(
                    f"tai san consumer trong {adir}/: {', '.join(extra[:5])}"
                    + (" ..." if len(extra) > 5 else ""))
    consumer_signals = [e for e in evidence if "consumer" in e or "tai san" in e]
    if consumer_signals:
        print("VERDICT: brownfield")
    else:
        print("VERDICT: greenfield")
    for e in evidence or ["repo chi chua ban phan phoi PilothOS, khong co tai san khac"]:
        print(f"EVIDENCE: {e}")
    print("NOTE: verdict chi la de xuat — agent PHAI trinh bay va cho consumer confirm truoc khi sang Stage 1.")


