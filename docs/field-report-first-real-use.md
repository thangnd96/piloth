# Field report — Piloth trên công việc thật

Vendor-only. Không ship. Đo ngày 2026-07-27 trên hai project VNG đã cài Piloth
v1.11.0, **trước** đợt cắt v2. Đây là lần đầu Piloth được quan sát ngoài chính
repo Piloth.

Nguồn dữ liệu: state repo-local của từng project (`pilothOS/memory/state/`,
`rot/review-log.md`, `memory/lessons-learned.md`, `.claude/settings.json`).
Không đọc source code của hai project.

## Cài đặt

| | vnggh-gio | vnggh-portal |
|---|---|---|
| Cài lần đầu | ~2026-07-19 | 2026-07-24 |
| `.initialized` | 07-23 (mode `upgrade`) | 07-24 (mode `brownfield`) |
| Version | 1.11.0 | 1.11.0 |
| Hook Piloth được wire | 6 event | 7 event |

Cả hai đều là brownfield thật: project đã có hook riêng, và sau khi cài mỗi
event có 2–6 hook trong đó Piloth là **một** — hook của consumer không bị ghi đè.
Hook-merge, thứ trước nay chỉ có test tổng hợp chứng minh, đã chạy đúng trên hai
repo thật.

## Cái gì được dùng

Đếm theo ngày, đã trừ 2 dòng vendor mà v1.11.0 ship kèm (bug đã vá sau đó).

| | vnggh-gio | vnggh-portal |
|---|---:|---:|
| Review-log entry | **65** (07-19 → 07-24) | **7** (07-24) |
| Lesson entry | **16** | **1** |
| `os-start` | 1 | 0 |
| `os-evidence` | 7 | 0 |
| `os-close` | **0** | **0** |
| Receipt seal | **0** | **0** |

81 entry ledger qua 5 ngày làm việc. Auto-log gate — hook `Stop` hỏi "phiên này
có thay đổi file, đã ghi log chưa" — chạy liên tục và **được tuân thủ**.

OS control plane — `os-start` → `os-close` → seal, tức hệ con lớn nhất trong
kernel — được gọi **một lần** và không hoàn tất lần nào.

## Run duy nhất, và nó dừng ở đâu

`task-21f4034a1686`, một task tích hợp API thật:

```
os-start      10:51   contract 15.861 B, 9 required gates
os-evidence   ×7      tsc sạch · eslint sạch · build ok · type-check ·
                      lint · check:classes · vitest 36/36 pass
                      (kéo dài tới 13:12 — 2h21m)
os-close      ——      chưa từng được gọi
```

Lifecycle đạt tới `intake → contract → route → tool/evidence`, dừng trước
`review → receipt → seal`. Sau 4 ngày run vẫn `status: open`.

Không có `close_attempts` trong state: **`os-close` không bị reject — nó không
được gọi.**

## Điều này nói lên cái gì

Công việc đã làm xong và đã verify: 7 bằng chứng, test 36/36 xanh. Người dùng
không bỏ giữa chừng vì task khó. Họ bỏ ở **bước viết receipt**.

Với task đó, `os-close` đòi 9 gate cộng khoảng 15 field có cấu trúc —
`scope_evidence`, `context_used[]`, `consumer_asset_routing[]`, `learning_review`
(4 field con), `reuse_discipline` (6 field con), `design_system_checked`,
`component_reuse_decision`, `token_reuse_decision`,
`design_system_candidate_review[]`, `judgment_checklist` (4 field con),
`claims[]` với `evidence_refs`. Khi tự dogfood đợt v2, tôi mất 6 vòng bị reject
mới viết đúng một receipt — và tôi có toàn bộ source code trước mặt.

Kết luận rút ra được từ dữ liệu này:

- **Thứ sống sót khi gặp công việc thật là gate nhẹ.** Auto-log gate hỏi một câu,
  chấp nhận một dòng, và được trả lời 81 lần.
- **Thứ không sống sót là lifecycle nặng.** 1 lần start, 0 lần close.
- Tỷ lệ đầu tư đang ngược: OS control plane là hệ con lớn nhất kernel.

## Điều này KHÔNG nói lên

- Không chứng minh Piloth làm agent tốt hơn hay tệ hơn. Vẫn chưa có benchmark
  had-piloth vs none-piloth, vẫn không có `real_token_telemetry` từ hai project.
- N = 1 người dùng, 2 project, 1 harness (Claude Code). Chưa ai khác cài.
- Đo trên v1.11.0, trước khi cắt. v2 chưa từng chạy ngoài repo Piloth.
- Không biết vì sao run bị bỏ: mệt, hết giờ, hay receipt quá nặng. Suy luận
  "dừng ở bước receipt" là từ vị trí dừng, không phải từ lời người dùng.

## Việc tiếp theo mà dữ liệu này gợi ý

1. Hỏi thẳng người đã dùng: lúc đó vì sao không close? Đó là dữ kiện duy nhất
   thay được suy luận ở trên bằng sự thật.
2. Nếu câu trả lời là "receipt quá nặng": đường V1 (`contract-write` →
   `receipt-write`) nhẹ hơn nhiều và vẫn ghi được evidence — nhưng không project
   nào dùng nó, và không doc nào nói cho họ biết nó tồn tại như một lựa chọn.
3. Cài v2 (đã cắt) lên chính hai project này và đo lại cùng các chỉ số. Đó là
   phép so sánh gần nhất với had-piloth vs none-piloth mà hiện có thể làm.
