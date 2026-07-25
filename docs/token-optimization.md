# Token Optimization

Tài liệu này giải thích cách Piloth giúp consumer **tiết kiệm token** khi coding
agent làm việc, và cách **tự đo** để biến "tiết kiệm token" từ một tuyên bố thành
một con số có bằng chứng.

## Nguyên tắc

Piloth coi token, context window, tool runtime và build/test là **tài nguyên hữu
hạn**. Agent chỉ nên tiêu chúng khi làm tăng Evidence của task. Chi tiết policy:
[`pilothOS/runtime/energy-token-policy.md`](../pilothOS/runtime/energy-token-policy.md).

Các đòn bẩy chính, từ tác động lớn tới nhỏ:

1. **Progressive context loading (routing)** — không nạp cả kernel vào context;
   chỉ nạp bootstrap set + đúng index/context layer cho `task_signal`.
2. **Operational preset** (`light` / `standard` / `strict`) — điều chỉnh lượng
   Evidence mà deliver receipt bắt buộc; `light` bỏ qua các gate nặng cho task nhỏ.
3. **OS adaptive mode** (`lean` / `standard` / `strict`) — chọn mode nhẹ nhất vẫn
   chứng minh được task; `lean` cho task UI/docs/test hẹp **và task code blast-radius
   nhỏ** (≤3 file cụ thể) — tự động, không cần khai. Ví dụ: helper + test (2 file)
   tự thành `lean` (7→3 gates, context ~6.668→~4.894 tok).
4. **Codebase intelligence có điều kiện** — graph route các câu hỏi cấu trúc tới
   candidate nhỏ, sau đó đọc live source. Không index nếu chi phí build lớn hơn
   giá trị của task.
5. **Digest thay vì blob** — mọi command in phần *hành động được* của quyết định
   router; chi tiết đầy đủ nằm trên đĩa (`contract.json`, OS state) và lấy qua
   `--verbose`. Đĩa miễn phí về token, context thì không.
6. **Adapter phải được nhận diện** — đây là đòn bẩy **capability**, không phải
   token: `adapter: unknown` cho 15 capability đều `unavailable`, nên `enforced`
   tự hạ thành `advisory` và specialist có `adapter_support` bị disqualify. Router
   tự detect qua env (chi tiết:
   [`evidence-router.md`](../pilothOS/runtime/evidence-router.md)); harness lạ khai
   bằng `PILOTHOS_ADAPTER`.

## Codebase retrieval proxy

Reference benchmark ở `tests/benchmark/codebase-memory/run-tests.sh` dùng corpus
call-chain có ground truth để đo index/query và số byte evidence được trả. Nó
giúp bắt regression trong retrieval contract, nhưng **không phải token
telemetry** và không chứng minh Piloth tiết kiệm token hay nhanh hơn end-to-end.

Các claim mục tiêu (median token/tool-call giảm 30%, end-to-end nhanh hơn 20%)
chỉ được mở khóa khi benchmark corpus có telemetry thật từ adapter. Freshness,
coverage và source fallback cũng phải pass để cost win không đổi lấy quality
regression.

## Đo footprint context (deterministic)

Command `context-budget` đo chính xác lượng kernel text mà một task sẽ nạp, so với
"trần" nạp toàn bộ kernel:

```bash
python3 pilothOS/scripts/pilothos_guard.py context-budget '{"task_signal":"bug fix"}'
```

Kết quả trả về `loaded_bytes`, `loaded_tokens_est`, `full_kernel_tokens_est` và
`savings_pct_vs_full_kernel`.

### Số đo tham chiếu

Hai denominator, **cùng báo cáo** để không tự khen:

- `full_kernel_*` — **77 file, ~74.7k token**: mọi `.md` dưới `pilothOS/`, tức
  trần "nạp tất cả" một cách ngây thơ.
- `routable_kernel_*` — **52 file, ~36.7k token**: bỏ `skills/**` (chỉ mở khi
  chính skill đó chạy, chiếm 45% trần) và `README`/`VALIDATION` (tài liệu cho
  người, không phải instruction cho task). **Đây là con số nên trích dẫn.**

| task_signal      | files | bytes  | est tokens | vs full-kernel | vs routable |
|------------------|:-----:|:------:|:----------:|:--------------:|:-----------:|
| not_applicable   |   7   | 22,084 |    5,521   |     92.6%      |    85.0%    |
| UI/component     |   8   | 23,809 |    5,953   |     92.0%      |    83.8%    |
| API/backend      |   8   | 26,669 |    6,668   |     91.1%      |    81.8%    |
| release/deploy   |   9   | 28,995 |    7,249   |     90.3%      |    80.3%    |
| bug fix          |   9   | 32,276 |    8,069   |     89.2%      |    78.0%    |

Nói cách khác: một task được route kéo **~15-22%** routable kernel vào context
thay vì 100%.

Guardrail: `CONTEXT_TOKEN_CEILINGS` trong `tests/unit/test_guard_context_budget.py`
đặt **ceiling theo token cho từng (task_signal, mode)** — chỉ được hạ, không được
nâng. Trước đó test chỉ chặn số **file** (`loaded_count <= 12`) nên bootstrap từng
phình +2.209 byte (+552 tok/task) mà không ai thấy: số file không đổi, còn
denominator cũng lớn lên nên tỷ lệ phần trăm thậm chí đẹp hơn.

### Mode-aware context (lean nạp ít hơn)

`context-budget` và `route-task` nhận `mode`. Ở `mode=lean`, Piloth **bỏ các doc
chỉ cần cho gate/asset** (`evaluation/quality-gates.md`, `runtime/consumer-assets.md`)
vì lean chạy ít gate hơn:

```bash
python3 pilothOS/scripts/pilothos_guard.py context-budget '{"task_signal":"bug fix","mode":"lean"}'
```

| task_signal | standard | lean (lazy rot) | micro |
|---|:---:|:---:|:---:|
| bug fix | ~8,069 | ~4,522 (−44%) | **~3,568 (−56%)** |
| API/backend | ~6,668 | ~4,894 (−27%) | ~3,940 (−41%) |
| UI/component | ~5,953 | ~4,179 (−30%) | ~3,225 (−46%) |

`lean`/`micro` còn dùng **lazy rot**: thay vì nạp cả bảng `rot/registry.md` (~579 tok),
gọi `rot-status` (chỉ scope quá hạn — thường "healthy", ~20 tok).

- `micro` = pass-through cho **script vứt đi / không tác động kiến trúc**: bỏ thêm
  Constitution (`PilothOS.md`) và `rot/registry.md` khỏi bootstrap, chỉ giữ orient
  tối thiểu. Chỉ dùng khi task thật sự không đụng kiến trúc.
- Default (không `mode`) = `standard` — không đổi hành vi cũ.

```bash
python3 pilothOS/scripts/pilothos_guard.py context-budget '{"task_signal":"bug fix","mode":"micro"}'
```

## Đo footprint tool output (`payload-budget`)

`context-budget` chỉ đo **một nửa** hoá đơn: text kernel nạp vào context. Nửa còn
lại là **JSON mà guard in ra** — nó vào context y như một file được đọc. Từ khi
Evidence Router ra đời, nửa này lớn hơn nhiều mà không meter hay test nào thấy.

```bash
python3 pilothOS/scripts/pilothos_guard.py payload-budget
python3 pilothOS/scripts/pilothos_guard.py payload-budget '{"task_signal":"UI/component"}'
```

Số đo cho một task `bug fix`, **đường adapter `claude` đã detect** (đúng cái một
consumer chạy Claude Code nhận được):

| command | trước | sau | ghi chú |
|---|---:|---:|---|
| `route-task` | 20.591 B | **11.860 B** | wrapper V1 từng nhúng cả decision 5.850 B; cộng thêm nén 4 view asset (dưới) |
| `scheduler-suggest` | 10.386 B | **4.732 B** | như trên |
| `evidence-route` | 7.342 B | **2.196 B** | digest là default, `--verbose` cho blob đầy đủ |
| `codebase-status` | 347 B | 347 B | đã gọn |
| `rot-status` | 108 B | 108 B | đã gọn |

Trong `adapter_capabilities` (block lớn nhất của decision), 15 key từng được phát
**ba lần**: map `capabilities`, 15 câu `limitations` boilerplate, và map `sources`
toàn `missing` — 2.137 B. Giờ chỉ còn map `capabilities` đầy đủ + **một** dòng
limitation tổng hợp + `sources` lọc bỏ `missing` kèm `sources_summary`.

`os-start`, `os-report` và **mỗi lần** `os-status` cũng từng in lại nguyên
decision; giờ in digest, tiết kiệm ~5.3 KB (~1.3k tok) mỗi lần in. Blob đầy đủ
luôn nằm trong `contract.json` + OS state, nên không mất thông tin nào.

Trên đường `adapter: unknown` (harness Piloth chưa nhận diện), digest là 2.405 B
— nhích lên vì còn 2 limitation thật: capability nào `unavailable`, và việc
`enforced` bị hạ thành `advisory`.

Guardrail: `PAYLOAD_BYTE_CEILINGS` trong `tests/unit/test_guard_payload_budget.py`
— cùng cơ chế ratchet như context, chỉ được hạ.

### Bốn view song song trên cùng tập asset trong `route-task`

`route-task` từng in bốn mảng cho cùng một tập asset (~9,6 KB cho 16 asset). Chỉ
**hai** trong số đó là contract:

| mảng | trước | sau | vì sao |
|---|---:|---:|---|
| `detected_assets` | 2.971 B | **2.094 B** | pure output, không validator/doc → bỏ `health_reason` (lặp lại đường dẫn) và `handling` (gần như luôn là `index`); chi tiết lấy từ `asset-scan`/`asset-health` khi cần |
| `skipped_assets` | 2.148 B | **830 B** | "receipt guidance", không validator → chỉ giữ `asset`+`type`; lý do bỏ qua giống nhau mọi row nên nêu một lần ở `skipped_reason` |
| `consumer_asset_routing` | 2.219 B | **1.963 B** | **shape giữ nguyên** (validator bắt buộc cả 4 key non-empty); chỉ bỏ phần `reason` lặp lại `task_signal` — chính nó đã là field trên cùng row |
| `context_evidence` | 2.278 B | **2.054 B** | như trên: `source` đã có đường dẫn, routing entry đã có signal → `reason` chỉ còn nêu asset type |

Tổng `route-task`: **20.591 → 11.860 B** (−42%).

Hai ratchet, mỗi cái cho một loại rò rỉ:
`test_route_task_asset_rows_stay_minimal` chặn **thêm field** vào 2 mảng pure-output;
`test_contract_view_reasons_do_not_restate_their_own_row` chặn `reason` **lặp lại lần
nữa** field đã có structural. Cả hai theo shape/nội dung, không theo byte — byte của
`route-task` phụ thuộc số asset trong repo nên ceiling byte sẽ vỡ chỉ vì thêm một script.

### Vì sao không nén tiếp

Còn ~4 KB trong hai mảng contract, và nó **cố tình** ở đó:

- **Shape là hợp đồng.** `validate_object_list` bắt buộc `{task_signal, asset_type,
  decision, reason}` và `{source, reason, finding}` đều là string non-empty. Bỏ field
  nào cũng là breaking change với receipt mà consumer đang viết.
- **Nén input ở đây làm tăng output.** Hai mảng này là **deliverable của model** —
  `route-task` in ra để model copy vào contract/receipt. Cắt template đi thì model
  phải tự dựng lại, tức chuyển chi phí từ input sang **output token (đắt hơn ~5×)**.
- **Không lọc bớt asset.** Có thể chỉ in asset "đáng chú ý" (risk cao / cần approval)
  và bỏ phần còn lại, nhưng đó là silent cap — đúng thứ chính tài liệu này cấm: nếu
  bỏ bớt coverage thì phải khai, và một asset bị ẩn là một asset model không cân nhắc.

`asset-scan --format json` (17.9 KB) vẫn là command nặng nhất, nhưng nó **manual**,
không nằm trong đường per-task.

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

## `real_token_telemetry` — token thật, đo bằng một command

Trên Claude Code **không cần khai tay**: command `token-telemetry` đọc transcript
session (`~/.claude/projects/<slug>/<session>.jsonl`), lấy `message.usage` thật của
từng turn (`input`/`output`/`cache_creation`/`cache_read` + `model` + `timestamp`),
định giá qua `runtime/model-pricing.json`, rồi ghi evidence
`llm_usage real_token_telemetry=true` cho run đang mở:

```bash
python3 pilothOS/scripts/pilothos_guard.py token-telemetry [--task <id>] [--transcript <path>]
```

Chi tiết cơ chế: [`energy-token-policy.md`](../pilothOS/runtime/energy-token-policy.md).
Đây là số API thật, không phải ước lượng byte.

Harness khác (chưa expose per-turn usage) thì khai tay — `token-telemetry` fail-soft
sang `real_token_telemetry=false` + `unavailable_reason`:

```bash
python3 pilothOS/scripts/pilothos_guard.py os-evidence '{
  "id": "llm-usage", "kind": "metric", "metric_type": "llm_usage",
  "metric_name": "adapter token telemetry", "phase": "verify",
  "real_token_telemetry": true,
  "input_tokens": 12000, "output_tokens": 3000, "total_tokens": 15000
}'
```

- `metric_name` bắt buộc (mọi metric evidence). `real_token_telemetry` chỉ được
  `true` khi số token đến từ telemetry thật của harness, không phải ước lượng.
- Có evidence này thì os-close **chấp nhận** cost claim (telemetry gate PASS).

### Ba giới hạn phải đọc kèm

1. **Token thật ≠ chứng minh consumer tiết kiệm.** Claim "rẻ hơn khi không dùng
   Piloth" vẫn cần benchmark `had-piloth` vs `none-piloth`; real token chỉ mở khóa
   phần cost, không thay thế phép so sánh.
2. **Chỉ main session** (`subagent_scope=main_session_only`). Transcript của
   background subagent là file riêng, **không** được cộng vào — con số per-turn là
   thật, con số per-task là tổng trong cửa sổ run.
3. **Cost phụ thuộc price map.** Model không có trong `runtime/model-pricing.json`
   không làm mất số cost của cả run nữa — phần có giá vẫn được cộng, kèm
   `cost_complete: false` + `unpriced_models` + `unpriced_tokens`, và
   `budget_status` gắn nhãn `spent_usd` là **sàn**. `cost_usd: null` chỉ còn khi
   **không** turn nào định giá được. Price map cũng **không phủ fast mode**
   (Opus 5 fast là $10/$50, map chưa có chiều `speed`) → session fast bị tính thấp.

## Giới hạn trung thực (đọc kỹ)

`context-budget` đo **`context_load`** (footprint kernel text nạp vào context) —
đây **không phải** `llm_usage` telemetry (prompt/completion token thật của model).

- Con số `*_tokens_est` là **ước lượng ~4 bytes/token**, dùng để so sánh tương đối
  và bắt bloat, không phải hóa đơn token chính xác.
- Một tuyên bố kiểu "Piloth rẻ hơn / tiết kiệm token so với không dùng Piloth"
  **chỉ hợp lệ khi** run ghi lại `llm_usage` với `real_token_telemetry=true`.
  Ước lượng byte/artifact không đủ để back claim đó — gate truth-in-seal sẽ từ
  chối (xem `pilothOS/VALIDATION.md`).

Nói ngắn gọn: `context-budget` và `payload-budget` chứng minh Piloth **nạp và in ít
hơn**; `token-telemetry` cho **token/cost thật của session**. Mảnh còn thiếu để nói
"Piloth rẻ hơn" là **phép so sánh** — benchmark `had-piloth` vs `none-piloth` — chứ
không còn là chuyện harness có expose được token hay không.

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
