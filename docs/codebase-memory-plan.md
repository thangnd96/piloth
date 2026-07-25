# Kế hoạch Codebase Intelligence cho Piloth

## Quyết định đã khóa

- Branch: `feat/codebase-memory`.
- Mục tiêu cuối: parity code-intelligence với upstream, không gồm UI/installer.
- Consumer runtime không có dependency package; Piloth được ship native asset đã
  build/vendor.
- Kiến trúc: Python control plane + static native engine do Piloth build.
- Upstream: maintained MIT fork/vendor, giữ attribution và patch ledger.
- State: SQLite local tại `pilothOS/memory/state/codebase-index/`, gitignored.
- CLI chung: `codebase-index`, `codebase-status`, `codebase-query`.
- Platform: macOS/Linux/Windows, arm64/amd64.
- Archive phân phối mục tiêu không quá khoảng 50 MB cho mỗi platform artifact.
- Invalidation: full rebuild khi commit/path structure đổi; content dirty dùng
  stale signal/overlay tạm, source fallback bắt buộc.
- Merge branch chỉ khi đạt full parity và SLA, không merge chỉ vì MVP chạy.

## SLA merge

| Trục | Gate |
|---|---|
| Tool contract | 100% contract matrix |
| Quality | không thấp hơn baseline quá 2 điểm phần trăm |
| p95 query/index | không chậm hơn baseline quá 10% |
| Coverage | equivalent declared language/edge coverage |
| Token/tool calls | median giảm ít nhất 30%, dùng telemetry thật |
| End-to-end | median nhanh hơn ít nhất 20% trên task corpus |
| Distribution | archive/platform khoảng <=50 MB; installed size báo riêng |
| Runtime dependency | không yêu cầu consumer cài package/tool |

Chỉ số giảm token không được suy từ byte proxy. Chúng cần
`real_token_telemetry=true` từ adapter. Nếu upstream không đạt một SLA trên corpus
chuẩn, parity không có nghĩa là sao chép failure; Piloth phải giữ source fallback
để đạt non-inferiority.

## Kiến trúc đích

```text
Agent adapter
    |
    v
Piloth guard CLI (stable JSON contract)
    |
    +-- policy: budget, freshness, coverage, confidence
    +-- provenance: source/generated/vendor/test
    +-- source fallback
    |
    v
Piloth native engine (vendored fork, static per OS/arch)
    |
    +-- Tree-sitter/LSP indexers
    +-- SQLite property graph
    +-- daemon/watcher/generation cursor
    |
    v
repo-local derived state
```

Python stdlib reference engine trên branch hiện tại khóa contract và failure
semantics. Nó không phải native engine cuối và không phải bằng chứng parity.

## Work breakdown

### M0 - Baseline và contract reference

Trạng thái: implemented trên branch, chưa merge-ready.

Deliverables:

- ba CLI JSON adapter-neutral;
- SQLite schema/reference indexer;
- Python AST deep adapter + universal shallow file/module adapter;
- search, trace, snippet, coverage, impact, overview;
- atomic build, containment, file budget, binary/oversize skip;
- generated-artifact canonicalization bằng body hash;
- freshness và source fallback signal;
- focused unit test và deterministic retrieval proxy.

Exit gate:

- bundle generated sạch;
- contract unit tests pass;
- benchmark công bố limitation, không claim token thật.

### M1 - Oracle và benchmark corpus

Deliverables:

- pin upstream cutoff bằng commit, tag, checksum và source archive;
- corpus đa ngôn ngữ gồm fixture nhỏ, OSS medium/large và consumer opt-in;
- ground truth cho symbol, calls, imports, inheritance, impact và coverage;
- task set cho agent outcome: locate, explain, change impact, bug trace;
- runner đo cold/warm index, process/MCP latency, RSS, archive/installed size;
- telemetry adapter cho token/tool call/end-to-end.

Exit gate:

- benchmark reproducible trên CI;
- không có metric dùng byte proxy để thay token telemetry;
- variance và machine profile được ghi.

### M2 - Maintained fork và reproducible native build

Deliverables:

- vendor/fork source MIT với `LICENSE`, `NOTICE`, upstream commit và patch ledger;
- khóa toolchain/grammar hashes;
- reproducible build cho 6 target family:
  macOS arm64/amd64, Linux arm64/amd64, Windows arm64/amd64;
- checksum, SBOM, sanitizer/fuzz và malware scan;
- loader chọn asset theo platform, không download lúc runtime.

Exit gate:

- provenance/SBOM đầy đủ;
- archive budget được đo từng platform;
- binary chạy từ clean consumer không cần dependency package.

### M3 - Index/schema parity

Deliverables:

- property graph schema, index passes và symbol identity tương đương upstream;
- provenance extension cho source/generated/vendor/test;
- manifest-aware canonicalization;
- parse error ranges, skip reason và coverage ledger;
- daemon coordination, crash recovery, atomic generation;
- team index artifact nếu feature nằm trong parity cutoff.

Exit gate:

- differential graph test trên corpus;
- no silent skip;
- RSS/timeout budget không regression quá SLA.

### M4 - Language và LSP parity

Deliverables:

- matrix tất cả grammar upstream tại cutoff;
- deep adapter test theo family: functions/classes/imports/calls/types;
- hybrid LSP cho Python, TS/JS, PHP, C#, Go, C/C++, Java/Kotlin, Rust, Perl
  hoặc đúng matrix của cutoff mới;
- fallback rõ cho dynamic dispatch, reflection, macros và generated code.

Exit gate:

- equivalent declared coverage, không chỉ grammar load;
- quality delta mỗi language family nằm trong 2pp;
- Windows Unicode/path và case-sensitivity corpus pass.

### M5 - Tool semantic parity

Matrix bắt buộc:

| Upstream capability | Piloth contract |
|---|---|
| index_repository | `codebase-index` |
| index_status, list/delete project | `codebase-status` + lifecycle actions |
| search_graph, query_graph, search_code | `codebase-query` discovery actions |
| trace_path | `codebase-query trace` |
| get_code_snippet | `codebase-query snippet` |
| get_graph_schema, get_architecture | `codebase-query schema/overview` |
| check_index_coverage | `codebase-query coverage` |
| detect_changes | `codebase-query impact/changes` |
| manage_adr | Knowledge/provenance action |
| ingest_traces | runtime-trace action, chỉ claim khi edge behavior thật sự có |

Exit gate:

- 100% request/response/error/pagination contract tests;
- generation-stamped cursor không đọc chéo generation;
- ambiguous symbol không bị tự chọn âm thầm.

### M6 - Adaptive routing và freshness overlay

Deliverables:

- không index ngầm cho task nhỏ;
- scheduler dùng index khi expected information gain vượt cost;
- full rebuild trên HEAD/path-set/schema/engine change;
- dirty-content overlay hoặc stale marker trong lúc chờ rebuild;
- confidence-aware hybrid: graph candidate -> live snippet/source;
- negative/exhaustive claim bắt buộc coverage check.

Exit gate:

- stale graph không được gắn `source_grounded`;
- source fallback được ghi vào receipt;
- repeated task benchmark chứng minh amortized win.

### M7 - Adapter integration

Deliverables:

- Claude Code, Codex, Cursor, Antigravity gọi cùng guard CLI;
- multilingual output theo locale/context của consumer;
- MCP adapter mỏng, không fork policy;
- install/uninstall/upgrade giữ consumer source và local state an toàn.

Exit gate:

- cùng JSON contract và fixture pass trên mọi adapter;
- adapter thiếu hook phải khai enforcement limitation.

### M8 - Hardening và soak

Deliverables:

- path containment, symlink/race, SQLite authorizer và input budget;
- crash/hang supervisor, concurrent client, corrupted DB recovery;
- large monorepo/OOM/timeout soak;
- dependency/license/security audit;
- rollback về source-only routing.

Exit gate:

- sanitizer/fuzz/soak pass;
- không ghi ra ngoài repo-local state;
- rollback drill pass.

### M9 - Final resync và merge decision

Deliverables:

- cập nhật cutoff tới upstream `main` mới nhất tại thời điểm release candidate;
- triage upstream delta theo contract/quality/security;
- chạy full platform/corpus/adapter/SLA matrix;
- ADR cuối, evidence receipt, known limitations và upgrade policy.

Merge gate:

- tất cả SLA đạt;
- không blocker/P0-P1;
- full parity claim có evidence cho contract lẫn behavior;
- archive và installed footprint đều được công bố;
- review độc lập chấp thuận.

## Rủi ro chính và đối sách

| Rủi ro | Đối sách |
|---|---|
| Upstream churn nhanh | cutoff từng milestone, patch ledger, final resync |
| Native asset vượt 50 MB | per-platform strip/compress; báo installed size; không giấu số |
| Graph trả false confidence | candidate-only mặc định, coverage/freshness/source fallback |
| OOM trên monorepo | budget, chunk/spill, supervisor, soak corpus |
| Parity kéo dài nhiều tháng | branch giữ độc lập; milestone usable nhưng không merge |
| 159 language chỉ là marketing | executable matrix và edge-quality corpus |
| Adapter fork semantics | một guard JSON contract, adapter chỉ transport |
| Token claim thiếu telemetry | gate từ chối claim, giữ metric proxy đúng tên |

## Rollback

Codebase index là derived state nên rollback không đụng source:

1. adapter ngừng route sang codebase CLI;
2. Piloth quay về index/doc/`rg`/source routing hiện tại;
3. xóa repo-local SQLite bằng lifecycle action có approval;
4. giữ receipt, benchmark và upstream provenance để điều tra;
5. không tự động download hoặc thay native binary trong consumer.

## Definition of done của branch

Branch chỉ được xem là hoàn thành khi M0-M9 đều đóng. Bản hiện tại mới đóng M0:
nó là vertical slice để chứng minh contract và insight riêng của Piloth, không
phải full parity, không production-ready và chưa đủ điều kiện merge.
