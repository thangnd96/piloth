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
3. **OS mode** (`standard` / `strict`) — `strict` thêm gate cho scope rộng,
   release/deploy hoặc claim tuyệt đối; nó **không** đổi lượng context nạp.
4. **Digest thay vì blob** — mọi command in phần *hành động được* của quyết định
   router; chi tiết đầy đủ nằm trên đĩa (`contract.json`, OS state) và lấy qua
   `--verbose`. Đĩa miễn phí về token, context thì không.
5. **Adapter phải được nhận diện** — đây là đòn bẩy **capability**, không phải
   token: `adapter: unknown` cho 15 capability đều `unavailable`, nên `enforced`
   tự hạ thành `advisory` và specialist có `adapter_support` bị disqualify. Router
   tự detect qua env (chi tiết:
   [`evidence-router.md`](../pilothOS/runtime/evidence-router.md)); harness lạ khai
   bằng `PILOTHOS_ADAPTER`.

## Đo footprint context (deterministic)

`scripts/measure_budget.py` đo chính xác lượng kernel text mà một task sẽ nạp, so
với "trần" nạp toàn bộ kernel. Đây là **công cụ vendor**, không phải guard verb:
đo kernel là việc của người làm ra kernel, nên consumer không phải mang theo code
đo đạc mà họ không có lý do gì để chạy.

```bash
python3 scripts/measure_budget.py context '{"task_signal":"bug fix"}'
```

Kết quả trả về `loaded_bytes`, `loaded_tokens_est`, `full_kernel_tokens_est` và
`savings_pct_vs_full_kernel`.

### Số đo tham chiếu

Hai denominator, **cùng báo cáo** để không tự khen:

- `full_kernel_*` — **45 file, ~36.7k token**: mọi `.md` dưới `pilothOS/`, tức
  trần "nạp tất cả" một cách ngây thơ.
- `routable_kernel_*` — **33 file, ~26.4k token**: bỏ `skills/**` (chỉ mở khi
  chính skill đó chạy) và `README`/`VALIDATION` (tài liệu cho người, không phải
  instruction cho task). **Đây là con số nên trích dẫn.**
- Cả hai trần đều **loại** `rot/review-log.md` + `memory/lessons-learned.md`: kích
  thước của chúng phản ánh install chạy bao lâu (auto-log gate append mỗi session),
  không phản ánh kernel to bao nhiêu — và chúng **ship trống**, nên với consumer mới
  chúng gần như 0 byte. Tính vào sẽ làm trần thành mục tiêu di động đo trên sai install.

| task_signal      | files | bytes  | est tokens | vs full-kernel | vs routable |
|------------------|:-----:|:------:|:----------:|:--------------:|:-----------:|
| not_applicable   |   7   | 21,717 |    5,430   |     85.2%      |    79.5%    |
| UI/component     |   8   | 23,442 |    5,861   |     84.0%      |    77.8%    |
| API/backend      |   8   | 25,772 |    6,443   |     82.5%      |    75.6%    |
| release/deploy   |   9   | 27,654 |    6,914   |     81.2%      |    73.8%    |
| bug fix          |   9   | 29,704 |    7,426   |     79.8%      |    71.9%    |

Nói cách khác: một task được route kéo **~21-28%** routable kernel vào context
thay vì 100%.

### Vì sao tỷ lệ tiết kiệm GIẢM sau khi cắt kernel

Trước v2 bảng này ghi 89-93% (full) và 78-85% (routable). Giờ thấp hơn, và đó là
kết quả đúng chứ không phải hồi quy: **context thật sự nạp đã giảm** (bug fix
32.276 → 29.704 B), nhưng mẫu số giảm mạnh hơn nhiều (full kernel 296.863 →
146.931 B) vì phần lớn thứ bị xoá là doc chưa bao giờ được route.

Đây là bản chất của mọi phép đo "tiết kiệm so với nạp tất cả": nó thưởng cho việc
**có nhiều thứ để không nạp**. Một kernel phình to làm con số đẹp lên. Vì vậy tỷ
lệ này chỉ dùng để bắt regression trong routing, không dùng để khoe — con số đáng
quan tâm là **byte tuyệt đối** mà task nạp.

Guardrail: `CONTEXT_TOKEN_CEILINGS` trong `tests/unit/test_guard_context_budget.py`
đặt **ceiling theo token cho từng (task_signal, mode)** — chỉ được hạ, không được
nâng. Trước đó test chỉ chặn số **file** (`loaded_count <= 12`) nên bootstrap từng
phình +2.209 byte (+552 tok/task) mà không ai thấy: số file không đổi, còn
denominator cũng lớn lên nên tỷ lệ phần trăm thậm chí đẹp hơn.

## Đo footprint tool output

Phép đo context chỉ là **một nửa** hoá đơn: text kernel nạp vào context. Nửa còn
lại là **JSON mà guard in ra** — nó vào context y như một file được đọc. Từ khi
Evidence Router ra đời, nửa này lớn hơn nhiều mà không meter hay test nào thấy.

```bash
python3 scripts/measure_budget.py payload '{"task_signal":"bug fix"}'
```

Hai command mà một task được route thật sự in ra, đo trên đường `adapter: unknown`
(worst case — còn mang limitation tổng hợp):

| command | bytes | ghi chú |
|---|---:|---|
| `evidence-route` | **2.175 B** | digest là default, `--verbose` cho blob đầy đủ |
| `adapter-capabilities` | **1.498 B** | 15 key từng được phát ba lần (2.137 B); giờ một map + một dòng limitation tổng hợp |

Bảng này ngắn hơn v1.12.0 vì ba trong năm probe cũ (`route-task`,
`scheduler-suggest`, `codebase-status`, `rot-status`) là verb đã bị gỡ. Riêng
`route-task` từng in 20.591 B rồi giảm còn 11.860 B sau khi nén — giờ là 0 B vì
routing chạy bên trong `os-start` và không in ra bản sao riêng nữa. Đó là dạng
tiết kiệm tốt nhất: không phải nén một output, mà là không sinh ra nó.

`os-start` và **mỗi lần** `os-status` cũng từng in lại nguyên decision; giờ in
digest, tiết kiệm ~5.3 KB (~1.3k tok) mỗi lần in. Blob đầy đủ luôn nằm trong
`contract.json` + OS state, nên không mất thông tin nào.

Guardrail: `PAYLOAD_BYTE_CEILINGS` trong `tests/unit/test_guard_payload_budget.py`
— cùng cơ chế ratchet như context, chỉ được hạ.

### Bốn view song song trên cùng tập asset khi routing

Routing từng in bốn mảng cho cùng một tập asset (~9,6 KB cho 16 asset). Chỉ
**hai** trong số đó là contract:

| mảng | trước | sau | vì sao |
|---|---:|---:|---|
| `detected_assets` | 2.971 B | **2.094 B** | pure output, không validator/doc → bỏ `health_reason` (lặp lại đường dẫn) và `handling` (gần như luôn là `index`); chi tiết lấy từ `asset-scan`/`asset-health` khi cần |
| `skipped_assets` | 2.148 B | **830 B** | "receipt guidance", không validator → chỉ giữ `asset`+`type`; lý do bỏ qua giống nhau mọi row nên nêu một lần ở `skipped_reason` |
| `consumer_asset_routing` | 2.219 B | **1.963 B** | **shape giữ nguyên** (validator bắt buộc cả 4 key non-empty); chỉ bỏ phần `reason` lặp lại `task_signal` — chính nó đã là field trên cùng row |
| `context_evidence` | 2.278 B | **2.054 B** | như trên: `source` đã có đường dẫn, routing entry đã có signal → `reason` chỉ còn nêu asset type |

Tổng payload routing: **20.591 → 11.860 B** (−42%), rồi về 0 khi verb bị gỡ
và routing chỉ còn chạy bên trong `os-start`.

Hai ratchet, mỗi cái cho một loại rò rỉ:
`test_route_task_asset_rows_stay_minimal` chặn **thêm field** vào 2 mảng pure-output;
`test_contract_view_reasons_do_not_restate_their_own_row` chặn `reason` **lặp lại lần
nữa** field đã có structural. Cả hai theo shape/nội dung, không theo byte — byte của
routing phụ thuộc số asset trong repo nên ceiling byte sẽ vỡ chỉ vì thêm một script.

### Vì sao không nén tiếp

Còn ~4 KB trong hai mảng contract, và nó **cố tình** ở đó:

- **Shape là hợp đồng.** `validate_object_list` bắt buộc `{task_signal, asset_type,
  decision, reason}` và `{source, reason, finding}` đều là string non-empty. Bỏ field
  nào cũng là breaking change với receipt mà consumer đang viết.
- **Nén input ở đây làm tăng output.** Hai mảng này là **deliverable của model** —
  `os-start` in ra để model copy vào contract/receipt. Cắt template đi thì model
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
  `os-runs/<task-id>/` (state + evidence + `artifacts/`), `receipt-seals.jsonl`. Chúng bị `.gitignore` và
  **không** được re-load vào context (mỗi task chỉ nạp một run active). Chúng làm
  phình đĩa và chậm I/O (glob quét mọi run), chứ không làm tốn token model.
- **Nhóm B — rác thật sự làm token tăng dần.** `memory/lessons-learned.md` và
  `rot/review-log.md` bị append mỗi session rồi **re-load vào context** ở task cần
  memory/rot. Đây mới là "càng ngày càng tốn token". (`rot/registry.md` là bảng cố
  định, update tại chỗ.)

`state-janitor` xử lý cả hai (chi tiết cờ và policy ở
`pilothOS/runtime/os-control-plane.md`):

```bash
python3 pilothOS/scripts/pilothos_guard.py state-janitor            # detect (Nhóm A)
python3 pilothOS/scripts/pilothos_guard.py state-janitor --fix      # dọn Nhóm A
python3 pilothOS/scripts/pilothos_guard.py state-janitor --fix --kernel-logs  # + rotate Nhóm B
```

- **Nhóm A** tự chạy (safe subset) sau khi `os-close` seal thành công — fail-soft,
  chỉ xoá `artifacts/` của run **đã seal** ngoài retention (giữ state/seal JSON).
  `receipt-seals.jsonl` (hash-chain) chỉ WARN.
- **Nhóm B** là opt-in (`--kernel-logs`), rotate **lossless** row cũ sang
  `*-archive.md` (không nằm trong context load set). Đây là đòn bẩy token thực sự
  cho install chạy lâu — chạy thủ công khi `state-doctor` báo `lessons_rows` /
  `review_log_rows` lớn.

Retention mặc định: giữ run active + 10 run gần nhất + mọi run trong 14 ngày
(`PILOTHOS_RETENTION_RUNS`, `PILOTHOS_RETENTION_DAYS`, `PILOTHOS_KERNEL_LOG_KEEP`).

## Review checklist (cho reviewer)

- Agent có nạp đúng context cần cho task không? (`scripts/measure_budget.py context`)
- Search có bắt đầu hẹp trước khi mở rộng không?
- Mỗi build/test/tool có gắn với expected evidence không?
- Full suite có được biện minh bởi blast radius không?
- Skipped/narrowed checks có được khai trong receipt không?
