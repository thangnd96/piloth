# ------------------------------------------------------------ placeholders

CADENCE_RE = re.compile(r"(\d+)\s*[–-]\s*(\d+)?\s*(tuần|tháng)")


def fill_text(text, fill, is_registry):
    today = datetime.date.today()
    text = _fill_persona_goals(text, fill)
    if fill.get("OWNER"):
        text = text.replace("<owner>", fill["OWNER"])
    if is_registry:
        out = []
        for line in text.splitlines():
            if "| <init> | <init> |" in line:
                m = CADENCE_RE.search(line)
                if m:
                    lo = int(m.group(1))
                    hi = int(m.group(2)) if m.group(2) else lo
                    unit = 7 if m.group(3) == "tuần" else 30
                    days = int((lo + hi) / 2 * unit)
                else:
                    days = 30
                nxt = (today + datetime.timedelta(days=days)).isoformat()
                line = line.replace("| <init> | <init> |",
                                    f"| {today.isoformat()} | {nxt} |")
            line = line.replace("<init>", today.isoformat())
            out.append(line)
        text = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    else:
        text = text.replace("<init>", today.isoformat())
    return text


