# Changelog

## Unreleased

## v2.0.2 — 2026-07-27

Vá ba issue nữa từ cùng consumer, phát hiện khi nâng v1.11.0 → v2.0.1
([#7](https://github.com/thangnd96/piloth/issues/7),
[#8](https://github.com/thangnd96/piloth/issues/8),
[#9](https://github.com/thangnd96/piloth/issues/9)).

### Đổi hành vi: staging giờ GỠ file không còn được ship

`stage.sh --upgrade` trước nay chỉ thêm và ghi đè, không bao giờ xoá. Hệ quả:
mọi hệ con một release gỡ đi vẫn nằm lại trên đĩa consumer. Đo trên một upgrade
thật v1.11.0 → v2.0.1: **41 file kernel v1 còn lại, `dist-manifest.json` nói 57
file trong khi đĩa có 99** — manifest thôi là SSOT của completeness, và
`os-close`/rot/routing đọc được cả hai phiên bản của cùng một doc.

Giờ staging gỡ mọi file dưới `pilothOS/` vắng mặt trong manifest mới. **Backup
trước khi xoá** vào `.backup/stage-upgrade-<ts>` — hầu hết consumer gitignore
`pilothOS/` nên không có đường lùi bằng git. Giữ lại: `dist-manifest.json` (nó
không tự liệt kê mình), `.initialized`, `.pending-plan.json`, `.backup/**`,
`memory/state/**`.

### Sửa

- **`prune_dead_hooks` không bao giờ kích hoạt trên upgrade path** (#7). Op thêm
  ở v2.0.0 để gỡ hook trỏ file đã xoá chỉ nhận diện "đã xoá" bằng
  `os.path.exists()` — mà staging không prune, nên lúc Record file vẫn còn, hook
  không "dead", và op không chạy. **Op sinh ra để sửa lớp lỗi này không chạm
  được nó trên chính đường đó.** Giờ kiểm theo `dist-manifest.json`: một hook
  giữ sống hệ con mà bản này không ship là drift kể cả khi nó chạy được, và
  cách kiểm đó đúng không phụ thuộc thứ tự thao tác.
- **`--adapters` được doc nhưng staging không implement** (#8), và **`--gitignore-scope`
  vỡ y hệt** — flag hợp lệ, được doc, mà `--gitignore-scope runtime <target>`
  hard-fail `qua nhieu target`. Gốc chung: `INSTALLER_VALUE_OPTIONS` là bản chép
  tay của argparse installer và đã trôi, nên wrapper không biết flag nào nhận
  giá trị; token tiếp theo thành target thứ hai. Bảng đã đồng bộ và có test khoá.
- **Flag lạ không còn bị nuốt im lặng.** Nhánh catch-all `elif arg.startswith("--")`
  forward mọi thứ sang installer — đó là thứ biến một flag không tồn tại thành
  no-op, dạng tệ hơn hard-fail vì consumer tin mình vừa chọn xong. Giờ fail rõ
  ràng kèm danh sách flag hợp lệ.
- **`/piloth:adapter` trong `pilothos-update/SKILL.md`** (#9) — command và skill
  không còn ship từ v2.0.0.

### Gate

- **Upgrade end-to-end** (`tests/install`, C11): fixture một install có file
  ngoài manifest + hook trỏ tới chúng, chạy đúng chuỗi thao tác SKILL.md, assert
  không còn file mồ côi **và** không còn hook trỏ path ngoài manifest — **so với
  manifest, không dùng `exists()`**, vì `exists()` chính là chỗ bug ẩn. Đây là
  test lẽ ra phải có ở v2.0.0: fixture cũ chỉ kiểm logic của hàm và dựng sẵn
  điều kiện hàm cần, nên không bao giờ chạm tới đường mà hàm phục vụ.
- **Luật doc-reference mở hai chiều** — quét thêm `skills/**/SKILL.md`, và nhận
  thêm token `/piloth:<verb>`. Đúng hai chiều mà `/piloth:adapter` lọt qua.
- **Flag trong doc phải được tool xử lý tường minh**, và bảng option của staging
  phải khớp argparse của installer.

### Ghi chú

`ENGINE_LINE_BUDGETS[installer]` nâng 920 → 940. Hai lần nâng liên tiếp là tín
hiệu mà chính luật đó tồn tại để phát: lần phình tiếp theo phải tách phần settings
ra khỏi `00_header.py` chứ không nâng nữa.

`os-close` vẫn chưa sửa. Vẫn là bản vá hồi quy.

## v2.0.1 — 2026-07-27

Vá ba issue từ consumer đầu tiên nâng lên v2.0.0
([#4](https://github.com/thangnd96/piloth/issues/4),
[#5](https://github.com/thangnd96/piloth/issues/5),
[#6](https://github.com/thangnd96/piloth/issues/6)). Cả ba cùng một gốc: v2 xoá
file nhưng không có gì kiểm rằng mọi tham chiếu tới chúng đã biến mất.

### Sửa

- **`/piloth:update` chạy được đúng như doc viết** (#4). `pilothos-update/SKILL.md`
  ghi lệnh engine dạng inline JSON, nhưng installer chỉ nhận đường dẫn — mọi lần
  update làm đúng doc đều fail ở stage Record với exit 2, để lại kernel v2 mà
  marker còn version cũ. Installer giờ nhận cả hai dạng; plan inline được ghi ra
  `pilothOS/.pending-plan.json` trước khi normalize, nên tính chất "thứ approve =
  thứ thực thi" giữ nguyên: các step engine tự chèn (`prune_dead_hooks`,
  `.gitignore`) vẫn hiện trong một artifact đọc được.
- **Sáu tham chiếu trỏ file v2 không ship** (#5, #6). `agents/index.md` còn 3 row
  team-role; `runtime/index.md` còn `team-orchestration.md` **và**
  `codebase-intelligence.md`; `tools/index.md` còn trỏ
  `runtime/codebase-intelligence.md`; `evidence-routing.json` và
  `TASK_SIGNAL_ROUTES` cùng trỏ `knowledge/architecture/README.md`. Task
  `task_signal: architecture` giờ route tới `knowledge/index.md` — file có thật,
  và index chính là chỗ nói consumer đặt fact kiến trúc ở đâu.
- **`ui/component` đã lệch giữa hai nguồn context** và không ai thấy —
  `evidence-routing.json` nói `consumer-assets.md`, guard nói
  `context-loading.md`. Issue #5 ngờ rằng duplicate literal ở hai nơi là gốc của
  drift; nó đã sinh ra một drift thứ hai, độc lập. Sửa JSON theo guard (guard là
  thứ `route_task_payload` thực sự đọc, nên **không đổi hành vi routing**).

Ba trong sáu defect trên không issue nào bắt được — chúng lộ ra khi viết gate.

### Gate

Ba luật mới ở `tests/unit/test_doc_contracts.py`:

1. Mọi backtick `*.md` trong `**/index.md` phải resolve tới path có trong
   `dist-manifest.json` (sibling → kernel root → repo root). Miễn trừ tên trần
   `index.md`/`SKILL.md`/`README.md` — chúng chỉ một *loại* file, không phải vị trí.
2. Mọi context path trong `evidence-routing.json`, `TASK_SIGNAL_ROUTES` và
   `BOOTSTRAP_CONTEXT_FILES` phải có trong manifest.
3. Hai nguồn context phải khớp **theo giá trị**.

Gate đọc `dist-manifest.json` chứ không đọc đĩa, vì upgrade từ v1.x che đúng lớp
lỗi này: staging không prune nên file v1 còn nằm lại và path vẫn resolve. Chỉ
install mới mới thấy — và đó là lý do consumer phát hiện được còn CI thì không.

Thêm test parse chuỗi lệnh **trực tiếp từ** `pilothos-update/SKILL.md` và kiểm
engine nhận được shape đó. Loại lỗi #4 chỉ lộ khi có người làm theo doc nguyên văn.

### Ghi chú

`ENGINE_LINE_BUDGETS[installer]` nâng 900 → 920 cho `load_plan_arg`, có ghi lý do
tại chỗ: engine phải nhận được shape mà chính doc của nó bảo dùng, và đó là xử lý
đầu vào chứ không phải thứ tách fragment riêng sẽ rõ hơn.

`os-close` **chưa** được sửa. `docs/field-report-first-real-use.md` chỉ ra đó là
chỗ người dùng bỏ cuộc, nhưng trộn thiết kế lại vào một bản vá hồi quy làm cả hai
khó review.

## v2.0.0 — 2026-07-27

**Breaking.** Bản cắt bề mặt: 19 CLI verb, 4 hệ con và 3 adapter bị gỡ. Nâng cấp
từ v1.x cần đọc mục "Đã gỡ" bên dưới trước khi chạy `/piloth:update`.

### Vì sao

Repo 11 ngày tuổi, 0 user ngoài tác giả, và 32/32 dogfood run đều là Piloth làm
việc trên Piloth. Bốn hệ con lớn chưa từng được dùng một lần nào trong 32 run
đó, nên chúng bị gỡ thay vì tiếp tục ship và tiếp tục phải bảo trì. Số đo
trước/sau ở `docs/slim-baseline.md`.

### Đã gỡ

| Hệ con | Lần dùng thật trong 32 run | Ghi chú |
|---|---:|---|
| Governed Visual Review (`pilothOS/tools/review/`) | 0 | 23 run có `review-request.json`, không run nào có `review-feedback.jsonl` — round-trip chưa từng hoàn tất. 1.476 dòng JS/HTML không test. |
| Team orchestration | 0 | `team-runs/` chưa từng tồn tại. |
| Codebase Intelligence | 0 | 47 extension nhưng chỉ Python có parser; doc tự khai "does not meet the SLA". |
| Discovery / Prototype | 0 | Kể cả trong run mang tên nó. |

**19 verb bị gỡ:** `os-report`, `review-request`, `review-feedback`,
`review-verify`, `route-task`, `context-budget`, `payload-budget`,
`codebase-index`, `codebase-status`, `codebase-query`, `rot-status`,
`reuse-scan`, `ds-scan`, `scheduler-suggest`, `scheduler-record`,
`team-contract-write`, `team-receipt-write`, `registry-assets`, `audit-assets`.

**Thay bằng gì:**

| Đã gỡ | Dùng thay |
|---|---|
| `route-task` | routing chạy trong `os-start`, kết quả ở `asset_routing` của contract |
| `os-report` | `os-status` (mang cùng state) |
| `audit-assets`, `registry-assets` | `asset-scan --format md` (13 cột, superset của bảng cũ) |
| `context-budget`, `payload-budget` | `scripts/measure_budget.py` trong repo Piloth — công cụ vendor, consumer không cần |
| `codebase-*` | đọc source trực tiếp (`rg`, glob); kết luận âm vẫn phải nêu coverage |
| `scheduler-*` | bảng "chạy suite nào" nêu thẳng trong `runtime/self-hosting.md` |
| `evidence-add` | **giữ nguyên** — không bị thay thế, xem mục Sửa |

**Mode:** `lean` và `micro` bị gỡ (0/32 run từng chọn), `adaptive` resolver cũng
vậy. Còn `standard` (mặc định) và `strict`. `strict` chỉ thêm gate, không đổi
lượng context nạp.

**Adapter:** chỉ còn `claude`. `cursor`, `codex`, `antigravity` cộng lại 75 dòng
văn bản, không hook, không exec surface, 0 test. Harness khác vẫn đọc kernel qua
`AGENTS.md` và vẫn được Evidence Router lập hồ sơ trung thực. **Mất mát thật:**
`adapters/cursor/*.mdc` dùng `alwaysApply: true` — cơ chế nạp thật của Cursor;
sau v2 Cursor không còn tự nạp PilothOS, phải tự trỏ agent vào `AGENTS.md`.

**Team routing:** Evidence Router không còn chấm team score hay trả
`mode: team`. Security/release vẫn buộc reviewer độc lập
(`single_with_independent_review`, hoặc `single_with_external_review` kèm
limitation khi adapter không spawn được).

### Sửa

- **5 claim sai đang ship.** `VALIDATION.md` khai Team control plane "đã kiểm
  chứng qua vận hành" khi `TEAM_RUNS_DIR` chưa từng tồn tại. `quality-gates.md`
  ship bảng gate sai ở `mode=lean`. `context-loading.md` giấu hai `task_signal`
  hợp lệ (`architecture`, `security`) khỏi enum mà consumer copy. `README.md`
  quote % không khớp mẫu số nào. `templates/AGENTS.md` thiếu 3/4 target của
  Startup Contract.
- **`evidence-add` được khôi phục sau khi gỡ nhầm.** Nó không bị `os-evidence`
  thay thế: `os-evidence` đòi một OS run đang mở, còn `evidence-add` phục vụ
  đường V1 (`contract-write` → `receipt-write`) và là người ghi duy nhất của
  `evidence_commands`.
- **`production-review` không còn duyệt cây repo hai lần** cho một lần kiểm.
- **`prune_dead_hooks` (op mới, engine tự chèn ở `mode=upgrade`).** `settings.json`
  là consumer-owned nên upgrade giữ nguyên — nghĩa là mọi install v1.10+ vẫn trỏ
  tới `tools/review/hooks/review-hook.sh` sau khi v2 xoá nó, và hook đó exit 127
  mỗi lần có tool use khớp. Op này gỡ đúng các entry trỏ tới file `pilothOS/`
  không còn tồn tại; hook riêng của consumer không bị chạm.

### Gate

15 điều kiện doc tự khai giờ có test. Nặng nhất: quality floor trước chỉ so
**key**, nên đặt `route_confidence: 0.5` trong `evidence-routing.json` đổi mọi
quyết định routing mà vẫn qua toàn bộ suite. Chiều ngược của command-table được
bật lại — waiver cũ ("15 internal mode vắng mặt hợp lệ") chính là chỗ 9 verb mồ
côi ẩn mình. Mutation test: gieo 6 lỗi cố tình, cả 6 đều bị bắt.

`remove_path` — op phá huỷ duy nhất của engine — giờ chỉ chạm được self-prune
whitelist (trước còn xoá được `.cursor`/`.codex`/`.antigravity`).

### Số đo

| | v1.12.0 | v2.0.0 |
|---|---:|---:|
| CLI verb | 53 | 34 |
| Guard bundle (ship tới consumer) | 12.140 dòng | 9.108 dòng |
| Kernel markdown | 6.906 dòng | 3.269 dòng |
| File trong `dist-manifest` | 122 | 73 |
| Full kernel footprint | 296.863 B | 143.935 B |

Tỷ lệ "tiết kiệm context" **giảm** (89,1% → 79,5% cho task `bug fix`) dù byte
nạp thật cũng giảm: mẫu số giảm nhanh hơn. Mọi phép đo "so với nạp tất cả" đều
thưởng cho việc có nhiều thứ để không nạp, nên con số đáng theo dõi là byte
tuyệt đối.

### Chưa làm

Không có benchmark `had-piloth` vs `none-piloth`, nên v2 **không** claim làm
agent rẻ hơn hay nhanh hơn — chỉ claim bề mặt nhỏ hơn và test vẫn xanh.
`docs/field-report-first-real-use.md` ghi lần đầu đo Piloth trên hai project
thật: auto-log gate được dùng 81 lần qua 5 ngày, OS control plane được gọi 1 lần
và 0 lần hoàn tất. `os-close` chưa được sửa theo phát hiện đó.

## v1.12.0 — 2026-07-26

Cắt footprint tool-output + mở khóa cost evidence.

> **Breaking cho ai parse stdout của guard.** Sáu command giờ in **digest** thay vì
> quyết định đầy đủ: `evidence-route`, `os-start`, `os-status`, `os-report`,
> `route-task`, `scheduler-suggest`. Lấy lại blob cũ bằng `--verbose`
> (`evidence-route`, `os-status`) hoặc đọc `contract.json`/OS state — blob đầy đủ
> luôn còn trên đĩa. Shape **contract/receipt** (cái có validator, consumer viết)
> **không đổi**, và không adapter/hook/skill/template nào bị ảnh hưởng.

- **Vá hai lỗ quy trình lộ ra khi dogfood v1.12.0** (không đổi surface consumer):
  - Field consumer thấy nhưng chỉ được doc ở `docs/` — mà `docs/` **không nằm trong
    `dist-manifest`**, nên consumer không bao giờ đọc được. Đã doc
    `superseded_token_snapshots` + `total_tokens` vào `runtime/energy-token-policy.md`
    (doc shipped, sở hữu chủ đề token/cost), và thêm ratchet
    `test_cost_ledger_fields_are_documented_in_a_shipped_doc`: key được **derive
    runtime** từ `cost_ledger_summary()` + `budget_status()` nên field mới tự động bị
    soi, không có list nào để drift. Key có sẵn từ trước được grandfather trong
    `UNDOCUMENTED_LEDGER_KEYS` + test allowlist-chỉ-co — doc đủ 11 key sẽ thêm ~700 B
    vào một doc *routable*, đi ngược mục tiêu cắt context.
  - `bash tests/run_all.sh` — lệnh verify **bắt buộc** theo self-hosting contract — tự
    sinh `.pytest_cache`, mà `artifact-janitor` coi đó là artifact phải dọn tường minh.
    Nên thứ tự tự nhiên verify → `control-plane-check` **không bao giờ** xanh, phải chèn
    `artifact-janitor --fix` vào giữa. Đã redirect cache ra `/tmp` ở **cả hai** call site
    pytest (`tests/unit/`, `tests/benchmark/codebase-memory/` — vá một chỗ thì còn chỗ
    kia), theo đúng convention `PYTHONPYCACHEPREFIX` mà các suite khác đã dùng. Test
    `test_every_pytest_call_site_keeps_its_caches_out_of_the_repo` **quét** thay vì
    hardcode, nên call site pytest mới cũng bị soi.
- **Hai ledger append-only thôi ship kèm lịch sử của vendor**:
  `rot/review-log.md` và `memory/lessons-learned.md` tự khai trong header rằng chúng
  "ship **TRỐNG** có chủ đích", nhưng lại ship `verbatim` kèm dòng lịch sử vận hành
  của repo Piloth — nên consumer cài mới nhận review log của vendor làm state khởi
  tạo. Tệ hơn: auto-log gate **buộc** append vào chúng mỗi session có thay đổi file,
  nên payload consumer phình thêm sau mỗi lần dogfood, độc lập với version. Nay
  `stage.py` strip data row khi copy (`SHIP_EMPTY_LOGS` + `log_header_only` ở
  `scripts/_distribution.py`), repo vendor giữ nguyên lịch sử của nó; manifest khai
  `ship_empty: true` để transform là tường minh chứ không ẩn; gate `C10i` khẳng định
  bản staged không có dòng dữ liệu nào **và** bản trong repo không bị làm trống.
- **Mở khóa cost evidence: định giá `claude-opus-5` + cost khai được một phần**:
  `cost_usd` từng là all-or-nothing và **im lặng** — một turn có model không nằm
  trong `runtime/model-pricing.json` là mất số cost của **cả run**, không nói model
  nào. Transcript thật có 831 turn `claude-opus-5` (model default hiện tại) chưa
  được định giá, nên mọi run đều mất cost và `budget_status` luôn
  `advisory_unavailable`. Nay: thêm hàng giá Opus 5 ($5/$25, 1M context là default
  *và* maximum, không phụ phí long-context → cùng hàng với `claude-opus-4-8`);
  `<synthetic>` bị loại vì không phải model call; phần có giá vẫn được cộng kèm
  `cost_complete` + `unpriced_models` + `unpriced_tokens`, `budget_status` gắn nhãn
  `spent_usd` là **sàn** khi chưa đủ. Đo trên transcript thật: `cost_usd` từ `None`
  → **$106,32** với `cost_complete: true`. Price map có test self-consistency
  (`cache_write_5m = 1.25×input`, `cache_read = 0.1×input`) để typo tier cache —
  chiếm phần lớn hóa đơn session dài — fail chứ không âm thầm tính sai.
- **`docs/token-optimization.md` thôi nói ngược về token telemetry**: doc từng viết
  "adapter phải expose được prompt/completion token… chưa có nguồn số thật" trong
  khi command `token-telemetry` đã đọc transcript Claude Code và ghi
  `real_token_telemetry=true` (document ở `energy-token-policy.md`). Nay doc nêu
  đúng đường chính + ba giới hạn thật: cần benchmark `had-piloth` vs `none-piloth`
  cho claim so sánh, `subagent_scope=main_session_only`, và cost phụ thuộc price map
  (không phủ fast mode $10/$50 vì map chưa có chiều `speed`).
- **Env signal detect adapter chỉ gồm biến đã kiểm chứng**: `CURSOR_CLI` cố tình
  **không** dùng — integrated terminal set nó cả khi người thật gõ tay, nên nó nghĩa
  là "một terminal Cursor" chứ không phải "Cursor agent đang chạy", dùng nó sẽ claim
  sai capability profile. `CODEX_SANDBOX` có thật nhưng undocumented và chỉ xuất hiện
  khi sandbox bật, nên detect là best-effort và fail-closed về `unknown`. Thêm test:
  mọi signal phải map tới một adapter mà `adapter-capabilities.json` khai.
- **Nén cả bốn view asset trong `route-task`** (20.591→**11.860 B**, −42%):
  `detected_assets` 2.971→2.094 B (bỏ `health_reason` lặp lại đường dẫn, `handling`
  gần như luôn `index`), `skipped_assets` 2.148→830 B (lý do giống nhau mọi row → nêu
  một lần ở `skipped_reason`). Hai mảng contract **giữ nguyên shape** — validator bắt
  buộc mọi key là string non-empty — nhưng bỏ phần `reason` lặp lại field đã có
  structural trên cùng row: `consumer_asset_routing` 2.219→1.963 B,
  `context_evidence` 2.278→2.054 B. Đã kiểm chứng contract vẫn validate sạch ở **cả
  hai** nhánh (`contract_requires_context_evidence` true/false). Hai ratchet riêng:
  chặn thêm field vào mảng pure-output, và chặn `reason` lặp lại lần nữa. Không nén
  thêm là có chủ ý: shape là hợp đồng consumer đang viết, cắt template chỉ chuyển chi
  phí sang output token (đắt hơn ~5×), và lọc bớt asset là silent cap.
  `os-status` bỏ in trùng `allowed_paths` (luôn bằng `target_paths` do cùng biến ở
  `build_os_contract`): 4.885→4.043 B.
- **Digest-as-default cho output của router + ratchet token hai mặt**: Evidence
  Router in **digest** (phần hành động được + `decision_id`) ở `evidence-route`,
  `os-start`, `os-status`, `os-report`, `route-task`, `scheduler-suggest`; blob
  đầy đủ vẫn nằm trong `contract.json`/OS state và lấy qua `--verbose`. Đo được:
  `route-task` 20.591→14.937 B, `scheduler-suggest` 10.386→4.732 B,
  `evidence-route` 7.342→2.196 B; `os-start`/`os-status`/`os-report` tiết kiệm
  ~5.3 KB (~1.3k tok) mỗi lần in. `adapter_capabilities` thôi phát cùng 15 key ba
  lần (2.137 B → map + **một** dòng limitation tổng hợp + `sources` lọc
  `missing` + `sources_summary`).
- **Adapter auto-detect** (`resolve_adapter`): `adapter` trong request →
  `PILOTHOS_ADAPTER` → env harness (`CLAUDECODE`, `CLAUDE_PROJECT_DIR`,
  `CURSOR_AGENT`, `CODEX_SANDBOX`) → `unknown`, kèm `adapter_source` để
  auditable. Trước đó không caller nào truyền `adapter` nên mọi consumer chạy
  đường `unknown`: 15/15 capability `unavailable`, `enforced` tự hạ thành
  `advisory` và specialist có `adapter_support` bị disqualify. Đây là fix
  **capability**, không phải token.
- **`payload-budget` + ceiling test**: meter mới đo footprint output từng command
  một task gọi — mặt chi phí mà `context-budget` không thấy.
  `CONTEXT_TOKEN_CEILINGS` (per `task_signal`×`mode`) và `PAYLOAD_BYTE_CEILINGS`
  chặn bloat theo **token/byte**, không chỉ theo số file như trước (lỗ đó đã để
  bootstrap phình +2.209 B / +552 tok mỗi task mà không test nào fail).
  `context-budget` thêm denominator trung thực `routable_kernel_*` (bỏ
  `skills/**` + `README`/`VALIDATION` — 45% trần cũ). Line budget cho hai engine
  amalgamated được gate ở `tests/unit/test_repo_hygiene.py`.
  `docs/token-optimization.md` refresh bằng số đo thật và **bind vào test** nên
  drift làm fail CI.
- **Consumer `.gitignore` mặc định ignore toàn bộ `pilothOS/`**: init
  greenfield/brownfield và unattended install dùng scope `all` khi plan không
  khai báo lựa chọn. `--gitignore-scope runtime` /
  `options.gitignore_scope="runtime"` vẫn được giữ như compatibility opt-in
  cho team muốn commit kernel và chỉ ignore state phát sinh.

## v1.11.0 — 2026-07-23

Update path first-class + drift-warning (vá thiếu sót "update plugin rồi thì bản đã init nâng cấp thế nào").

- **`/piloth:update` (skill `pilothos-update`)**: command first-class nâng bản PilothOS
  đã init lên version plugin hiện tại — re-stage kernel/adapter (`stage.sh --upgrade`,
  có backup) rồi đóng dấu version qua engine (`mode=upgrade` + `write_marker`). GIỮ nguyên
  `CLAUDE.md`/`AGENTS.md`/`.gitignore`/`.claude/settings.json` + state (rot registry,
  review-log, lessons-learned). SSOT của upgrade flow — section "Re-init/Upgrade" của
  `pilothos-init` rút thành pointer. Bridge `/pilothos-update` cho project đã cài. Đổi
  adapter vẫn dùng `/piloth:adapter`.
- **Drift-warning ở session-start** (fail-soft, advisory): guard so `pilothos_version`
  trong `pilothOS/.initialized` với version plugin ở `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`;
  plugin mới hơn → nhắc chạy `/piloth:update` (không chặn task). Thiếu marker / thiếu
  `CLAUDE_PLUGIN_ROOT` / parse lỗi → im lặng. **Forward-looking**: chỉ kích hoạt cho
  consumer đã ở version CÓ nó (v1.11.0+) — lần nhảy từ v1.10.0 chưa thấy vì guard cũ chưa có.
- **Fix release tooling**: `bump-version.sh` audit thêm exclude `pilothOS/memory/state/`
  (runtime state gitignored) — trước đây os-run state của release trước (chứa version cũ)
  làm audit false-positive mỗi lần bump.
- Tests: `tests/unit/test_guard_version_drift.py` (advisory fail-soft: newer→warn,
  equal/older/missing→silent). Docs: README `## Updating`, structure, workflow, skills/index.

## v1.10.0 — 2026-07-23

Init ergonomics từ consumer feedback (adapter selection, add-adapter, plan-write, gitignore).

- **Adapter selection giờ được enforce (fix "chọn claude+codex vẫn cài đủ 4")**:
  plan interactive khai báo field `adapters` (list adapter giữ lại, gồm `claude`);
  engine `normalize_plan` tự sinh `remove_path` cho adapter KHÔNG chọn ở dry-run
  (không còn phụ thuộc Claude gõ tay). Greenfield/brownfield BẮT BUỘC khai báo
  `adapters` khi có optional adapter đã staging.
- **`/piloth:adapter` (skill `pilothos-adapter`)**: thêm/bớt adapter SAU init mà
  không cần re-init. ADD dùng `stage.sh --add-adapters <names>` (targeted — chỉ
  copy adapter thiếu, không đụng kernel); REMOVE qua engine `remove_path` (có backup).
- **Guard không còn chặn Claude ghi plan file khi harness không truyền
  `permission_mode`**: `pre-edit` cho ghi khi mọi target nằm trong `~/.claude/plans/`
  (hoặc `$CLAUDE_CONFIG_DIR/plans/`) — plan file là artifact harness, không phải
  code repo. Safety-net bổ trợ cho exemption plan-mode.
- **`.gitignore` runtime rules nhất quán + opt-in `all`**: SSOT `PILOTHOS_GITIGNORE_LINES`;
  `normalize_plan` chèn `append_lines` cho `.gitignore` (idempotent) ở MỌI nhánh —
  vá gap greenfield-có-sẵn-.gitignore và brownfield-append-thiếu-dòng. `pilothOS/`
  vẫn commit theo thiết kế; `options.gitignore_scope="all"` (elicit/`--gitignore-scope all`)
  cho consumer chọn ignore toàn bộ `pilothOS/`.
- Tests: `test_installer_safety.py` (adapter_set, normalize_plan, gitignore, adapters
  required); `test_guard_plan_mode.py` (harness plan-path allow); install C10f/C10g/C10h;
  lifecycle/install fixtures khai báo `adapters`.

Lifecycle ergonomics + taxonomy hardening (từ dogfood build landing page).

- **`os-close --dry-run`**: chạy TOÀN BỘ validator của os-close (quality gates,
  truth-in-seal, expected-evidence, footprint, janitor — không chỉ validator lõi)
  và trả `{would_pass, errors}` mà KHÔNG mutate state / seal / ghi `target-diff.json`.
  Lặp tới khi `would_pass:true` rồi close thật.
- **`receipt-template` gate-aware**: chỉ in field mà run này thực sự cần (docs-only
  bỏ field UI), enum điền sẵn giá trị hợp lệ (không còn `<placeholder>`); allowed
  values gom trong `_allowed_values`.
- **`os-start --explain`**: in schema request (field/required/default/allowed/alias)
  — SSOT dạng máy, mirror `installer explain`.
- **`energy_budget_reason` passthrough**: `build_os_contract` giờ nhận field này từ
  request (trước đây gate full-suite đòi nó nhưng os-start không có cách cấp) — cũng
  liệt kê trong `os-start --explain`.
- **`browser_smoke`** thêm vào `METRIC_TYPES` (loại evidence UI tự nhiên).
- **Gộp vocab decision**: `SEMANTIC_REVIEW_DECISIONS` alias `UI_DESIGN_SYSTEM_DECISIONS`
  (một nguồn, chống drift); `ASSET_ROUTING_DECISIONS` giữ riêng (khác ngữ nghĩa).
- **Error message rõ hơn**: `learning_review.promoted_to` liệt kê target hợp lệ +
  cú pháp `<target>, upstream`; `lesson_decision` derive từ constant.
- **Cross-project advisory** (không chặn): `os-close` phát `enforcement_advisory` khi
  diff-facts rỗng nhưng target-diff có thay đổi (target hook không fire khi drive từ
  session khác) — seal vẫn dựa trên git/manifest target-diff.
- Tests: `tests/unit/test_guard_taxonomy.py`; lc7 mở rộng (dry-run + gate-aware
  template). Docs: os-control-plane, task-lifecycle.

State retention / janitor — dọn rác vòng đời task (Nhóm A đĩa + Nhóm B token).

- **`state-janitor`** (detect mặc định, `--fix`): dọn `os-runs/<task>/artifacts/` của
  run đã seal ngoài retention (giữ state/seal JSON), tail-truncate scheduler-history;
  `receipt-seals.jsonl` (hash-chain) chỉ WARN. `--kernel-logs` rotate lossless
  `lessons-learned.md`/`review-log.md` sang `*-archive.md` (không load context).
  `os-close` tự chạy safe subset sau seal (fail-soft). `state-doctor` thêm advisory bloat.
- Tests: `tests/unit/test_guard_state_janitor.py`. Docs: token-optimization,
  energy-token-policy, os-control-plane, memory/state/README.

Governed Visual Review — human-in-the-loop review + agent loop + hook bridge.

- **Piloth Review** (`pilothOS/tools/review/`): companion tool tái hiện annotron 1:1
  (Node built-ins, zero runtime dependency) — point-and-click annotation trên artifact
  MD/HTML, agent loop poll/reply/finalized, live activity mirror (SSE), remote
  permission gate (fail-open). Chạy độc lập được, disk sạch (SDK inject lúc serve).
- **Gate `human_review`** trong guard: 3 mode `review-request`/`review-feedback`/
  `review-verify`; structured feedback (verdict + findings gắn gate/severity/
  disposition) thành evidence `kind=human_review`; `os-close` enforce — task cần human
  review không Seal khi thiếu artifact `approve`+`finalized` hoặc còn blocker/major chưa
  xử lý; blocker/major route về Repair. Receipt tự khai `PASS` mà thiếu artifact backing
  bị reject (chống honor-system).
- **Governance bridge** (opt-in, fail-soft): companion tool khi bind `--task`/`--govern`
  forward feedback → `review-feedback` và quyết định permission → `os-evidence`; không
  bind → core chạy 1:1 standalone.
- Tests: `tests/lifecycle/cases/lc10-human-review-roundtrip.sh` (full os-close
  enforcement) + `tests/unit/test_guard_human_review.py`.
- Docs: quality-gates, task-lifecycle, os-control-plane, operational-controls.
- **Review hooks default-on**: bản cài bật sẵn activity mirror + permission gate
  của review tool (fail-open); tắt bằng `PILOTH_REVIEW=off` trong `.claude/settings.json`.
- **Plan-mode exemption**: `pre-edit` bỏ qua enforcement khi `permission_mode=plan`
  (fix Piloth chặn Claude ghi plan trong plan mode); governance enforce lại khi thực thi.
  Test: `tests/unit/test_guard_plan_mode.py`.

Prototype phase + Discovery gate + pipeline stepper + recipe suggestions
(reimplement 1:1 DNA của aidlc, build native cho Piloth trên hạ tầng review).

- **Prototype phase** (skill `piloth-prototype` + persona `agents/team-roles/designer.md`):
  sinh ≥2 UI options (Claude Artifacts/Figma/design-system/shadcn/lo-fi), human chọn
  **tái dùng** `human_review` round-trip. `requires_prototype` tự bật
  `requires_human_review`; gate `prototype` (mỏng) kiểm invariant qua
  `os-evidence kind=prototype` (method hợp lệ, ≥2 options, `chosen` ∈ options);
  thiếu → route Repair; receipt tự khai `PASS` mà thiếu evidence bị reject.
- **Discovery gate** (skill `piloth-discovery`): hỏi-xác nhận câu hỏi mở đầu phase qua
  Governed Visual Review (`## Q<n>` + `[x] Decide for me` default), ghi
  `os-evidence kind=discovery` + fold vào contract `discovery_decisions` (Traceability
  trace tới). Là gate judgment, không hook tự trigger; `DISCOVERY.md` là working doc.
- **Pipeline stepper + option-picker** trong review chrome (Piloth-layer, fail-soft):
  route `/pipeline` đọc `os-status` qua `govern.js`; stepper hiện phase/gate + hint
  `phase_plan_suggestion`; option-picker cho `PROTOTYPE-option*.html`. Ungoverned →
  ẩn, core 1:1 annotron không đổi.
- **Recipe suggest-only + model-hints** (advisory): `suggest_phase_plan` khuyến nghị
  discovery/prototype theo signal/scope (**không auto-enable**); `model_hints` gợi ý
  model per-phase; cả hai surface ở `os-status`/`os-report`. Budget ceiling hoãn tới
  khi có `real_token_telemetry`.
- Tests: `tests/unit/test_guard_{prototype_gate,discovery,recipe}.py` +
  `tests/lifecycle/cases/lc11-prototype-roundtrip.sh`.
- Docs: quality-gates, task-lifecycle, os-control-plane, energy-token-policy, skills/index.

Real token telemetry (`token-telemetry`) + advisory budget — unlocks cost claims.

- **`token-telemetry` guard mode**: reads real per-turn `message.usage` from the
  Claude Code session transcript (`~/.claude/projects/<slug>/<session>.jsonl`),
  windowed to the OS run's `created_at`, prices it via `runtime/model-pricing.json`
  (input/output + cache-write ~1.25× / cache-read ~0.1×), and records
  `os-evidence kind=metric metric_type=llm_usage real_token_telemetry=true`
  (`cost_usd`, `model`, `window_start`, `subagent_scope=main_session_only`).
  Fail-soft: no transcript → `real_token_telemetry=false` + `unavailable_reason`.
  This is what unblocks `os-close` cost/token claims (superiority still needs a
  benchmark).
- **Price map** `pilothOS/runtime/model-pricing.json` (advisory, `as_of` dated;
  helpers `load_model_pricing`/`model_price`/`compute_token_cost_usd`).
- **Metric schema extended**: `cache_creation_input_tokens`,
  `cache_read_input_tokens`, `cost_usd`, `model` (+ `pricing_source`,
  `window_start`, `subagent_scope`) on `llm_usage`; `cost_ledger_summary` surfaces
  cache tokens + total `cost_usd`.
- **Advisory budget**: optional contract `budget.max_usd` → `budget_status`
  (`spent_usd`/`remaining_usd`/`over_budget`) in `os-status`/`os-report`; **never
  blocks `os-close`**.
- Tests: `tests/unit/test_guard_token_telemetry.py` (pricing/cost, cost ledger,
  metric schema, transcript parse/window) + `tests/unit/test_guard_budget.py`.

## 1.9.0

Reproducibility, safety net và token optimization.

- Release gate reproducible: `run_all.sh` thêm meta-guard abort to tiếng khi một
  suite khai báo thiếu `run-tests.sh` trên clean clone; track các suite
  `evaluation`/`docs`/`benchmark` + lifecycle case `lc6–lc9` vốn còn untracked.
- CI: GitHub Actions chạy full gate (Python 3.9/3.11/3.13) + `self-host-check`
  + `production-review` + `pytest` trên mỗi push/PR.
- Unit safety net: `tests/unit/` pytest cho các hàm quyết định của guard/installer
  (`validate_deliver_receipt`, routing, reuse, context-budget, `safe_rel`
  path-traversal, `check_target_writable_zone`, `merge_settings_content`,
  `choose_adaptive_mode`) — 59 unit test, lần đầu guard có coverage đơn vị.
- Dispatch table: `main()` thay ~45 nhánh `if/elif` bằng `COMMAND_TABLE`;
  `guard_registered_modes()` derive từ table thay vì regex-parse source (fix một
  class regression control-plane-check bắt được bởi benchmark).
- Giảm code: bỏ 4 hàm chết trong `pilothos_guard.py` (−28 dòng), hành vi giữ nguyên.
- **Token optimization**:
  - `context-budget` đo footprint context (bytes/token) routing nạp vs full kernel
    (~88–91% nhỏ hơn); nhãn `context_load`, không phải `llm_usage` telemetry.
  - Mode-aware context: `route-task`/`context-budget` nhận `mode`. `lean` bỏ
    gate/asset docs + lazy rot (`rot-status` thay cả bảng registry); `micro` bỏ
    thêm Constitution. standard→lean −27–40%, micro −43–54%.
  - Blast-radius-aware mode: `choose_adaptive_mode` tự chọn `lean` cho task ≤3 file
    cụ thể (không cần khai). Guide: `docs/token-optimization.md`.
- `real_token_telemetry` verified: os-evidence `llm_usage` (cần `metric_name` +
  `real_token_telemetry:true`) mở khóa cost claim ở os-close; thiếu → claim
  "rẻ hơn" bị từ chối.
- Init greenfield end-to-end verify `SELF-CHECK PASSED`.

Đã hoãn có chủ đích:
- Tách `pilothos_guard.py` thành package vật lý — rủi ro regression cao so với lợi
  ích; dispatch table đã lấy phần lớn lợi ích maintainability.
- Condense kernel docs (`agent-core` vs `extended`) — ROI thấp hơn, rủi ro cắt lố.
- Nguồn token telemetry thật phụ thuộc adapter harness expose prompt/completion.

## 1.8.3
- Harden staging for release: replace Bash process substitution with deterministic Python-backed staging and keep `stage.sh` as a thin stable wrapper.
- Add `pilothOS/dist-manifest.json` to the version-bump contract so the fifth version location is updated by process, not luck.
- Ship-clean audit: lifecycle tests must pass from a fresh unzip and the package must contain no cache, backup, init marker, pending plan, or stale generated artifacts.
- Harden test runners with process-group timeouts so timed-out cases cannot leave orphaned grandchildren holding deleted workspaces or pipes.

## 1.8.2
- Test: thêm lifecycle E2E suite (apply+receipt+marker, completeness từ engine thật, crash rollback, self-prune+uninstall round-trip, guard regression) — mỗi case một workspace riêng, output ra file, hard timeout; hang trở thành FAIL to tiếng.
- Test: C10d quay về assert bằng receipt thật của engine (`completeness_missing`), bỏ logic đọc manifest tĩnh trùng lặp.
- Guard (thay đổi engine-adjacent, gọi tên riêng): `read_hook_input` thêm `select` 0.5s — hook modes không còn block vô hạn khi stdin là pipe non-interactive không dữ liệu; docstring hết overclaim.
- Release tooling: `bump-version.sh` tự regenerate `pilothOS/dist-manifest.json` sau khi bump (vị trí version thứ 5 vào quy trình, hết phụ thuộc may mắn của audit).
- Runner tổng: per-suite timeout + timing.

## 1.8.1
- Sửa release-readiness findings: test runner báo cáo theo suite rõ ràng, engine/install suite có timeout cục bộ để tránh hang im lặng.
- Sửa wording README và VALIDATION.md để phân biệt enforcement cơ học với judgment-based contracts; không overclaim hook chặn những việc chưa thể máy móc hóa.
- `dist-manifest.json` thêm `schema_version`, `piloth_version`, `generated_at` để phục vụ upgrade/debug sau này.
- Giữ model plugin/runtime của 1.8.0, không thêm feature speculative.

## 1.8.0
- Tái cấu trúc repo production-shape: kernel `pilothOS/` và `adapters/<tool>/` visible ở root, không còn `dist/`; mỗi tài liệu một bản (diệt duplicate-SSOT — đã bắt được drift thật ở settings.json).
- `stage.sh` duy nhất cho cả hai kênh (plugin + clone); settings staged từ payload (SSOT).
- Docs + LICENSE của PilothOS đi theo `pilothOS/` trong project — root project của consumer không còn bị chiếm chỗ; LICENSE không còn vô tình áp lên code consumer.
- Test suite sống trong repo: `tests/run_all.sh` (engine C1–C9, install C10, sync-templates guard).
- Version automation: `.version-bump.json` + `scripts/bump-version.sh` (audit chuỗi version sót).
- Kênh feedback: issue templates khớp cột review-log, chảy thẳng vào quy trình upstream.

## 1.7.0
- Sửa bug hoàn chỉnh (feedback consumer): bản cài giờ ĐẦY ĐỦ như bản phân phối — install.sh v2 staging theo toàn bộ cây (adapters, bridges, AGENTS.md, docs), file của consumer không bao giờ bị đè.
- `dist-manifest.json`: SSOT của "bản cài hoàn chỉnh", sinh tự động lúc đóng gói; engine kiểm completeness sau apply và báo trong receipt.
- Op mới `fill_placeholders`: cá nhân hóa in-place (CLAUDE.md, registry — registry tự tính Next Due theo cadence, bỏ bước sửa tay khỏi First-Boot).

## 1.6.1
- Self-prune mặc định: sau khi cài, installer tự dọn mặt tiền install (command init, docs nhánh, skill bridge) bằng chính các step `remove_path` trong plan — có backup, `uninstall` phục hồi cả bộ install để cài lại được. Engine + `/pilothos-uninstall` + payloads không bao giờ bị dọn.

## 1.6.0
- Installer chuyển sang mô hình **plan/apply**: Claude soạn `install-plan.json`, engine deterministic (`pilothos_installer.py`) validate → backup → thực thi → receipt; auto-rollback khi lỗi giữa chừng.
- Bộ ops đóng (6 ops, xem `installer explain`) — SSOT merge semantics chuyển vào engine.
- Chọn tool adapters lúc init (Claude/Cursor/Codex/Antigravity); adapter không chọn được gỡ có backup, uninstall phục hồi.
- Bootstrapper `install.sh`: một lệnh terminal dàn dựng file vào project.
- Hỗ trợ unattended: gọi thẳng engine với plan tự viết.
- Prune: gỡ `pilothOS/adapters/` (trùng vai với adapter thật ở root; checklist dời vào review-guide) và `templates/review.md` (trùng per-layer checklists).
- Thêm `LICENSE` (MIT).

## 1.5.1
- Tài liệu phân phối viết lại hướng consumer; lịch sử phát triển tách khỏi bản ship.
- `CLAUDE.md` và `rot/registry.md` ship dạng placeholder — `/pilothos-init` điền.
- Quy ước `upstream` cho lessons-learned: lesson generalize được đánh dấu để gặt về bản phân phối.
- Sửa chuỗi version cũ còn sót trong `AGENTS.md`.

## 1.5.0
- Thêm `payloads/`: nội dung chuẩn cho installer (settings, identity, startup contract).
- Approve/confirm của installer chuyển sang câu hỏi có cấu trúc; điều chỉnh kèm approve được echo và xác nhận trước Apply.
- Guard mode `log-append`: ghi log máy móc, verify Evidence path.
- Token Budget Contract cho installer.

## 1.4.0
- Installer `/pilothos-init` (một lệnh cho cả greenfield lẫn brownfield, detect + confirm).
- Backup + manifest transactional; `/pilothos-uninstall` phục hồi nguyên trạng.
- Preflight, First-Boot Checklist, merge semantics cố định cho hooks/permissions/env/statusLine.

## 1.3.0
- Auto-log gate (Stop hook): phiên có thay đổi file phải append log hoặc tuyên bố không có finding.
- Cảnh báo Rot tối ưu token: một lần mỗi phiên cho cùng trạng thái.

## 1.2.0
- Enforcement baseline: hooks (SessionStart/UserPromptSubmit), statusline, self-check, pre-action gate trong Identity.

## 1.1.x
- Multi-tool adapters (Claude Code, Codex, Cursor, Antigravity); team `piloth-team`; skill `piloth-team-setup`.

## 1.0.0
- Kiến trúc lõi 7 layer + cross-cutting (Governance, Evaluation); Rot Management; templates.
