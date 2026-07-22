# ---------------------------------------------------------------- log append

def _sanitize(field):
    """Chống vỡ bảng markdown: thay | bằng ; và ép một dòng."""
    return field.replace("|", ";").replace("\n", " ").strip()


def log_append(argv):
    """Append MỘT dòng log đúng format — máy móc, hết lỗi typo/nuốt cột.

    Cách dùng:
      log-append review "<Scope>" "<Findings>" "<Action>" "<Evidence>" "<Reviewer>"
      log-append lesson "<Context>" "<Lesson>" "<PromotedTo>"

    - Date tự điền = hôm nay.
    - Nếu Evidence trông như đường dẫn trong repo mà KHÔNG tồn tại → FAIL,
      không append (chặn lớp lỗi Evidence-path sai từ lần adopt đầu tiên).
    """
    if not argv:
        print("FAIL log-append: thieu loai log (review|lesson)")
        return
    kind, fields = argv[0], [_sanitize(f) for f in argv[1:]]
    today = datetime.date.today().isoformat()
    if kind == "review":
        if len(fields) != 5:
            print("FAIL log-append review: can dung 5 truong "
                  "(Scope, Findings, Action, Evidence, Reviewer)")
            return
        evidence = fields[3]
        if "/" in evidence and " " not in evidence:
            if not (REPO_ROOT / evidence).exists():
                print(f"FAIL log-append: Evidence path khong ton tai: {evidence}")
                return
        row = f"| {today} | {fields[0]} | {fields[1]} | {fields[2]} | {fields[3]} | {fields[4]} |"
        target = REVIEW_LOG
    elif kind == "lesson":
        if len(fields) != 3:
            print("FAIL log-append lesson: can dung 3 truong "
                  "(Context, Lesson, PromotedTo)")
            return
        if not learning_promotion_target_valid(fields[2]):
            print(
                "FAIL log-append lesson: PromotedTo phai la target hop le "
                "hoac not_applicable"
            )
            return
        row = f"| {today} | {fields[0]} | {fields[1]} | {fields[2]} |"
        target = LESSONS
    else:
        print(f"FAIL log-append: loai khong ho tro: {kind}")
        return
    if not target.exists():
        print(f"FAIL log-append: khong tim thay {target}")
        return
    with open(target, "a", encoding="utf-8") as f:
        f.write(row + "\n")
    print(f"OK   da append vao {target.name}: {row}")


