# Token Optimization

Tài liệu này giải thích cách Piloth giúp consumer **tiết kiệm token** khi coding
agent làm việc, và cách **tự đo** để biến "tiết kiệm token" từ một tuyên bố thành
một con số có bằng chứng.

## Nguyên tắc

Piloth coi token, context window, tool runtime và build/test là **tài nguyên hữu
hạn**. Agent chỉ nên tiêu chúng khi làm tăng Evidence của task. Chi tiết policy:
[`pilothOS/runtime/energy-token-policy.md`](../pilothOS/runtime/energy-token-policy.md).

Ba đòn bẩy chính, từ tác động lớn tới nhỏ:

1. **Progressive context loading (routing)** — không nạp cả kernel vào context;
   chỉ nạp bootstrap set + đúng index/context layer cho `task_signal`.
2. **Operational preset** (`light` / `standard` / `strict`) — điều chỉnh lượng
   Evidence mà deliver receipt bắt buộc; `light` bỏ qua các gate nặng cho task nhỏ.
3. **OS adaptive mode** (`lean` / `standard` / `strict`) — chọn mode nhẹ nhất vẫn
   chứng minh được task; `lean` cho task UI/docs/test hẹp **và task code blast-radius
   nhỏ** (≤3 file cụ thể) — tự động, không cần khai. Ví dụ: helper + test (2 file)
   tự thành `lean` (7→3 gates, context ~5.845→~4.850 tok).

## Đo footprint context (deterministic)

Command `context-budget` đo chính xác lượng kernel text mà một task sẽ nạp, so với
"trần" nạp toàn bộ kernel:

```bash
python3 pilothOS/scripts/pilothos_guard.py context-budget '{"task_signal":"bug fix"}'
```

Kết quả trả về `loaded_bytes`, `loaded_tokens_est`, `full_kernel_tokens_est` và
`savings_pct_vs_full_kernel`.

### Số đo tham chiếu

Trần full-kernel: **68 file, ~57.9k token ước lượng**. Với routing:

| task_signal      | files | bytes  | est tokens | tiết kiệm vs full-kernel |
|------------------|:-----:|:------:|:----------:|:------------------------:|
| not_applicable   |   7   | 19,875 |    4,969   |          91.4%           |
| UI/component     |   8   | 21,600 |    5,400   |          90.7%           |
| API/backend      |   8   | 23,379 |    5,845   |          89.9%           |
| release/deploy   |   9   | 24,850 |    6,213   |          89.3%           |
| bug fix          |   9   | 27,862 |    6,966   |          88.0%           |

Nói cách khác: một task được route chỉ kéo **~9-12%** kernel vào context thay vì
100%. Đây là guardrail có unit test (`tests/unit/test_guard_context_budget.py`) —
nếu routing phình to trong tương lai, test sẽ fail.

### Mode-aware context (lean nạp ít hơn)

`context-budget` và `route-task` nhận `mode`. Ở `mode=lean`, Piloth **bỏ các doc
chỉ cần cho gate/asset** (`evaluation/quality-gates.md`, `runtime/consumer-assets.md`)
vì lean chạy ít gate hơn:

```bash
python3 pilothOS/scripts/pilothos_guard.py context-budget '{"task_signal":"bug fix","mode":"lean"}'
```

| task_signal | standard | lean (lazy rot) | micro |
|---|:---:|:---:|:---:|
| bug fix | ~6,966 | ~4,169 (−40%) | **~3,215 (−54%)** |
| API/backend | ~5,845 | ~4,271 (−27%) | ~3,317 (−43%) |
| UI/component | ~5,400 | ~3,826 (−29%) | ~2,872 (−47%) |

`lean`/`micro` còn dùng **lazy rot**: thay vì nạp cả bảng `rot/registry.md` (~579 tok),
gọi `rot-status` (chỉ scope quá hạn — thường "healthy", ~20 tok).

- `micro` = pass-through cho **script vứt đi / không tác động kiến trúc**: bỏ thêm
  Constitution (`PilothOS.md`) và `rot/registry.md` khỏi bootstrap, chỉ giữ orient
  tối thiểu. Chỉ dùng khi task thật sự không đụng kiến trúc.
- Default (không `mode`) = `standard` — không đổi hành vi cũ.

```bash
python3 pilothOS/scripts/pilothos_guard.py context-budget '{"task_signal":"bug fix","mode":"micro"}'
```

## Chọn profile nhẹ cho task nhỏ

Với task nhỏ (sửa 1 dòng, đổi text, fix nhỏ), dùng preset `light` để bỏ qua các
gate Evidence nặng:

```bash
# qua env cho một session
export PILOTHOS_OPERATIONAL_PRESET=light
```

hoặc khai `"operational_preset": "light"` trong task contract / receipt.

- `light` — receipt chỉ cần `changed_files`, `affected_layers`,
  `verification_command`, `result`; bỏ qua judgment/reuse/UI/warning checklist.
- `standard` (mặc định) — đầy đủ Evidence cho code/UI/runtime/rules/adapter.
- `strict` — dùng cho scope rộng, release/deploy, hoặc claim tuyệt đối; yêu cầu
  verification sạch, không chấp nhận skipped/failed.

## Bật `real_token_telemetry` (mở khóa cost claim)

Cơ chế đã sẵn: ghi evidence `llm_usage` với số token THẬT từ adapter, rồi cost
claim mới được os-close chấp nhận. Contract:

```bash
python3 pilothOS/scripts/pilothos_guard.py os-evidence '{
  "id": "llm-usage", "kind": "metric", "metric_type": "llm_usage",
  "metric_name": "adapter token telemetry", "phase": "verify",
  "real_token_telemetry": true,
  "input_tokens": 12000, "output_tokens": 3000, "total_tokens": 15000
}'
```

- `metric_name` bắt buộc (mọi metric evidence). `real_token_telemetry` phải là
  `true` **và** số token phải từ telemetry thật của harness (prompt/completion),
  không phải ước lượng byte/artifact.
- Đã kiểm chứng end-to-end: khi có evidence này, os-close **chấp nhận** cost claim
  (telemetry gate PASS → `os_closed`). Không có nó, claim "rẻ hơn" bị từ chối.
- `consumer_superiority` chỉ ra `consumer_value` (thay vì `consumer_value_failed`)
  khi thêm benchmark cho thấy consumer win trên metric bắt buộc.

**Điều kiện phụ thuộc harness:** adapter (vd Claude Code hook) phải expose được
prompt/completion token. Chừng nào chưa có nguồn số thật, Piloth cố tình để
`real_tokens: unavailable` và **từ chối** mọi claim "rẻ hơn" — đây là thiết kế,
không phải thiếu sót.

## Giới hạn trung thực (đọc kỹ)

`context-budget` đo **`context_load`** (footprint kernel text nạp vào context) —
đây **không phải** `llm_usage` telemetry (prompt/completion token thật của model).

- Con số `*_tokens_est` là **ước lượng ~4 bytes/token**, dùng để so sánh tương đối
  và bắt bloat, không phải hóa đơn token chính xác.
- Một tuyên bố kiểu "Piloth rẻ hơn / tiết kiệm token so với không dùng Piloth"
  **chỉ hợp lệ khi** run ghi lại `llm_usage` với `real_token_telemetry=true` từ
  adapter thật. Ước lượng byte/artifact không đủ để back claim đó — gate
  truth-in-seal sẽ từ chối (xem `pilothOS/VALIDATION.md`).

Nói ngắn gọn: Piloth cho bạn bằng chứng rằng nó **nạp ít context hơn**; để tuyên bố
**tổng token model thấp hơn**, cần telemetry thật từ harness.

## State retention & janitor (dọn rác)

Rác của Piloth có **hai nhóm khác hẳn nhau** — chỉ một nhóm thật sự tốn token:

- **Nhóm A — rác trên đĩa (KHÔNG trực tiếp tốn token LLM).**
  `os-runs/<task-id>/` (state + evidence + `artifacts/` HTML/PNG),
  `scheduler-history.jsonl`, `receipt-seals.jsonl`. Chúng bị `.gitignore` và
  **không** được re-load vào context (mỗi task chỉ nạp một run active). Chúng làm
  phình đĩa và chậm I/O (glob quét mọi run), chứ không làm tốn token model.
- **Nhóm B — rác thật sự làm token tăng dần.** `memory/lessons-learned.md` và
  `rot/review-log.md` bị append mỗi session rồi **re-load vào context** ở task cần
  memory/rot. Đây mới là "càng ngày càng tốn token". (`rot/registry.md` là bảng cố
  định, update tại chỗ, đã lazy-drop ở `lean`/`micro`.)

`state-janitor` xử lý cả hai (chi tiết cờ và policy ở
`pilothOS/runtime/os-control-plane.md`):

```bash
python3 pilothOS/scripts/pilothos_guard.py state-janitor            # detect (Nhóm A)
python3 pilothOS/scripts/pilothos_guard.py state-janitor --fix      # dọn Nhóm A
python3 pilothOS/scripts/pilothos_guard.py state-janitor --fix --kernel-logs  # + rotate Nhóm B
```

- **Nhóm A** tự chạy (safe subset) sau khi `os-close` seal thành công — fail-soft,
  chỉ xoá `artifacts/` của run **đã seal** ngoài retention (giữ state/seal JSON) và
  tail-truncate scheduler-history. `receipt-seals.jsonl` (hash-chain) chỉ WARN.
- **Nhóm B** là opt-in (`--kernel-logs`), rotate **lossless** row cũ sang
  `*-archive.md` (không nằm trong context load set). Đây là đòn bẩy token thực sự
  cho install chạy lâu — chạy thủ công khi `state-doctor` báo `lessons_rows` /
  `review_log_rows` lớn.

Retention mặc định: giữ run active + 10 run gần nhất + mọi run trong 14 ngày
(`PILOTHOS_RETENTION_RUNS`, `PILOTHOS_RETENTION_DAYS`, `PILOTHOS_SCHEDULER_KEEP`,
`PILOTHOS_KERNEL_LOG_KEEP`).

## Review checklist (cho reviewer)

- Agent có nạp đúng context cần cho task không? (`context-budget` để kiểm chứng)
- Search có bắt đầu hẹp trước khi mở rộng không?
- Mỗi build/test/tool có gắn với expected evidence không?
- Full suite có được biện minh bởi blast radius không?
- Skipped/narrowed checks có được khai trong receipt không?
