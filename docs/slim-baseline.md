# Slim baseline — đo trước khi cắt

Vendor-only. Không nằm trong `dist-manifest.json`, không ship tới consumer.

Chốt tại `pre-slim-v1.12.0` (commit `e8814e6`, nhánh `slim/v2.0.0`), 2026-07-26.
Mọi con số dưới đây đo bằng chính công cụ của repo, không ước lượng.

## Bề mặt

| Chỉ số | Giá trị | Cách đo |
|---|---:|---|
| CLI verb đã đăng ký | **53** | `GUARD_MODES` trong `src/guard/00_header.py` |
| Dòng source viết tay | **12.966** | `wc -l src/guard/*.py src/installer/*.py` |
| Dòng kernel markdown | **6.906** | `find pilothOS -name '*.md' \| xargs wc -l` |
| File trong `dist-manifest.json` | **122** | `len(manifest["files"])` |

`pilothOS/scripts/*.py` (12.966 dòng) là bản amalgamation sinh ra từ `src/`, không đếm hai lần.

## Context footprint

`python3 pilothOS/scripts/pilothos_guard.py context-budget '{"task_signal":"bug fix"}'`

| Chỉ số | Files | Bytes |
|---|---:|---:|
| Full kernel | 75 | **296.863** |
| Routable kernel | 50 | **144.895** |
| Task `bug fix` (standard) nạp | 9 | **32.276** |

Chín file được nạp: `bootstrap.md` 3.011 · `PilothOS.md` 3.816 · `rules/index.md` 1.659 · `runtime/index.md` 2.528 · `rot/registry.md` 2.316 · `runtime/consumer-assets.md` 4.777 · `runtime/context-loading.md` 3.977 · `rules/coding-behavior.md` 3.097 · `evaluation/quality-gates.md` 7.095.

Chênh lệch giữa full (296.863 B) và routable (144.895 B) là **151.968 B** — hơn một nửa kernel markdown không bao giờ được route. Phần lớn là `skills/` (138.477 B, bị loại khỏi mẫu số bằng một dòng hardcode ở `src/guard/07_context_budget.py:71`) và `tools/review/` (78.708 B).

## Test suite

`bash tests/run_all.sh` — **ALL SUITES PASSED**

| Suite | Thời gian |
|---|---:|
| engine | 0s |
| install | 5s |
| lifecycle | 18s |
| evaluation | 26s |
| docs | 2s |
| benchmark/figma-ui | 1s |
| benchmark/codebase-memory | 4s |
| benchmark/evidence-router | 0s |
| unit | 19s |

Đây là mốc so sánh: sau mỗi phase cắt, cả 9 suite phải xanh trở lại (trừ những suite bị xoá cùng hệ con của nó, và việc xoá đó phải được ghi rõ).

## Bằng chứng sử dụng thật (32 dogfood run)

Đo trên `pilothOS/memory/state/os-runs/` — thư mục này gitignored, nên số liệu chỉ đúng với máy local tại thời điểm chốt.

| Hệ con | Số lần dùng thật |
|---|---:|
| Evidence Router | 32/32 (nhưng **task_signal = None** ở cả 32 → chỉ dòng `not_applicable` từng chạy) |
| Visual Review (`human_review` evidence) | **0** |
| Team orchestration (`team-runs/`) | **0** — thư mục không tồn tại |
| Codebase Intelligence (`codebase-query`) | **0** |
| Discovery / Prototype | **0** |
| Context mode | 25 `standard` · 7 `strict` · **0 `lean`** · **0 `micro`** |

Loại evidence từng được ghi: `command` ×109, `metric` ×33. Không có loại nào khác.

## Kết quả sau Phase 1–2

Đo lại bằng cùng công cụ, cùng lệnh.

| Chỉ số | Trước | Sau | Δ |
|---|---:|---:|---:|
| CLI verb | 53 | **34** | −36% |
| Dòng source viết tay | 12.966 | **10.014** | −23% |
| Guard bundle (ship tới consumer) | 12.140 | **9.188** | −24% |
| Dòng kernel markdown | 6.906 | **3.332** | −52% |
| File trong `dist-manifest.json` | 122 | **85** | −30% |
| Full kernel bytes | 296.863 | **147.507** | −50% |
| Routable kernel bytes | 144.895 | **106.134** | −27% |
| Task `bug fix` nạp | 32.276 B / 8.069 tok | **29.594 B / 7.399 tok** | −8% |
| Dòng test | 8.921 | **7.448** | −17% |
| Hệ con 0-lần-dùng | 4 | **0** | — |

Cả 8 suite còn lại xanh (`benchmark/codebase-memory` bị xoá cùng hệ con của nó).

Hai điều đáng ghi lại vì chúng đi ngược trực giác:

**Tỷ lệ "tiết kiệm context" giảm dù context thật sự nạp cũng giảm.** Trước: 89,1%
so với full kernel cho task `bug fix`. Sau: 79,9%. Byte nạp giảm (32.276 →
29.594) nhưng mẫu số giảm mạnh hơn (296.863 → 147.507) vì phần lớn thứ bị xoá là
doc chưa bao giờ được route. Mọi phép đo dạng "tiết kiệm so với nạp tất cả" đều
thưởng cho việc có nhiều thứ để không nạp — nên con số đáng theo dõi là **byte
tuyệt đối**, không phải phần trăm.

**Một mục trong plan sai và đã được sửa khi thực thi.** Plan xếp `evidence-add`
vào nhóm "bị `os-evidence` thay thế". Sai: `os-evidence` **đòi** một OS run đang
mở, còn `evidence-add` phục vụ đường V1 (`contract-write` → `receipt-write`) mà
`self-hosting.md` vẫn công nhận là kernel primitive cho adapter mỏng. Nó là
người ghi duy nhất của `evidence_commands` — chính field mà receipt gate đọc
trước khi cảnh báo "code changed without test/evidence". Verb đã được khôi phục.
Dead-code analysis đồng ý nó chết chỉ vì tôi đã gỡ nó khỏi registry trước — một
vòng lặp tự khẳng định, đúng dạng lỗi mà `lessons-learned.md:72` cảnh báo.

## Điểm cứu hộ

```bash
git tag pre-slim-v1.12.0    # đã tạo local
git checkout pre-slim-v1.12.0   # quay lại toàn bộ trạng thái trước khi cắt
```

Tag chưa push lên origin. Đẩy lên khi muốn có bản sao ngoài máy:

```bash
git push origin pre-slim-v1.12.0
```
