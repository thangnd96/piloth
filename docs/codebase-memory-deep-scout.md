# Deep Scout: codebase-memory-mcp

## Phạm vi và mốc nguồn

Khảo sát được chốt tại upstream commit
[`97ce23f`](https://github.com/DeusData/codebase-memory-mcp/commit/97ce23f9827177fff3858831156e9795c6832b18)
ngày 2026-07-23, tag gần nhất là
[`v0.9.0`](https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.9.0).
Mốc này phải được cập nhật ở từng milestone vì upstream thay đổi nhanh.

Phương pháp:

- đọc source C, schema/store, MCP dispatch, parser/LSP, security và test;
- build binary từ source và kiểm tra footprint;
- index chính Piloth để quan sát chất lượng graph và đường query;
- đối chiếu paper, README, release và issue đang mở;
- tách claim đã đo cục bộ khỏi claim do upstream công bố.

Nguồn chính:

- [repository](https://github.com/DeusData/codebase-memory-mcp);
- [paper v1](https://arxiv.org/html/2603.27277v1);
- [issue tracker](https://github.com/DeusData/codebase-memory-mcp/issues);
- [release v0.9.0](https://github.com/DeusData/codebase-memory-mcp/releases/tag/v0.9.0).

## Mô hình thực sự của upstream

Tên "memory" dễ gây hiểu nhầm. Lõi của project là một static code-intelligence
engine:

1. parser Tree-sitter và một số LSP tạo symbol/edge;
2. multi-pass indexer tạo property graph trong SQLite;
3. MCP query graph theo luồng search -> trace -> exact snippet;
4. daemon, watcher và generation cursor giữ query ổn định;
5. coverage/freshness cho biết graph có thể thiếu hoặc cũ;
6. source file vẫn là nguồn sự thật cuối cùng.

Mặt tool ở cutoff có 15 capability:
`index_repository`, `search_graph`, `query_graph`, `trace_path`,
`get_code_snippet`, `get_graph_schema`, `get_architecture`, `search_code`,
`list_projects`, `delete_project`, `index_status`, `check_index_coverage`,
`detect_changes`, `manage_adr`, `ingest_traces`.

Upstream khai báo hỗ trợ khoảng 158-159 ngôn ngữ qua grammar được vendor và có
đường hybrid LSP cho một nhóm ngôn ngữ chính. Con số phải được kiểm bằng matrix
test ở mỗi cutoff, không dùng README như bằng chứng parity.

## Điểm mạnh

### 1. Query cấu trúc thay cho đọc tuyến tính

Graph phù hợp với câu hỏi "ai gọi symbol này?", "thay file này ảnh hưởng gì?"
hoặc "module nào định nghĩa capability này?". Output dạng cây gọn làm giảm
context trung gian so với trả cả file.

### 2. Retrieval có trình tự

Contract search -> trace -> snippet buộc agent đi từ candidate rẻ đến source
chính xác. Đây là thiết kế tốt hơn việc nhét toàn repository vào prompt hoặc
coi semantic search là câu trả lời.

### 3. Negative evidence được xem là vấn đề riêng

`check_index_coverage`, trạng thái parse và generation cursor làm lộ vùng graph
không đủ dữ liệu. Đây là điểm tinh tế nhất của upstream: kết quả "không tìm thấy"
chỉ có giá trị khi scope đã được index đủ.

### 4. Tính thực dụng vận hành cao

SQLite local, binary self-contained, supervised indexing, skip file lỗi, daemon
coordination, checksum/signing và sanitizer/fuzz/soak cho thấy project quan tâm
đến failure mode thực tế chứ không chỉ parser demo.

### 5. Tối ưu cho agent protocol

Tool description dạy client dùng graph trước, source sau; pagination gắn với
generation; limit/depth có trần. Các chi tiết này kiểm soát cả token lẫn blast
radius của query.

## Điểm yếu và rủi ro

### 1. Graph là biểu diễn mất mát

Paper v0.5.5 báo điểm chất lượng trung bình của MCP là `0.83`, thấp hơn baseline
Explorer `0.92`, dù dùng khoảng 10 lần ít token hơn và 2.1 lần ít tool call hơn.
Explorer thắng ở source context và exhaustive grep; macro-heavy C là vùng yếu
rõ. Vì vậy không được chuyển "rẻ hơn" thành "tốt hơn" nếu thiếu fallback.

### 2. Bằng chứng benchmark chưa đủ rộng

Paper dùng một model, một repository/language, grading có first-author tham gia,
một cấu hình máy và static analysis. Dynamic dispatch, reflection, runtime
behavior và nhiều metaprogramming pattern vẫn là threat to validity.

### 3. Footprint có hai sự thật khác nhau

Build local macOS arm64 tạo executable khoảng 282 MB nhưng archive gzip khoảng
38 MB. Archive đạt budget phân phối 50 MB; installed footprint thì không. Kho
grammar vendor trong source checkout khoảng 1.2 GB. Piloth phải công bố cả
archive size, installed size và runtime memory, không chọn số đẹp nhất.

### 4. RAM và latency cần đo ở boundary thật

Indexer multi-pass ưu tiên RAM có thể nhanh nhưng issue tracker có báo cáo memory
runaway. Khi dogfood, graph query nội bộ báo dưới millisecond nhưng mỗi CLI
process vẫn mất khoảng 1.1-1.3 giây do startup/daemon boundary. MCP session dài
có thể amortize chi phí này; CLI ngắn thì không.

### 5. Correctness còn nhiều cạnh sắc

Issue mở cho thấy Windows path/Unicode, Python import-call, Go route, pagination,
false route và memory behavior vẫn đang chuyển động. Fast release cadence làm
chi phí pin, audit và backport tăng.

### 6. Bus factor và supply-chain

Lịch sử commit tập trung mạnh vào một maintainer. MIT cho phép fork/vendor,
nhưng Piloth phải giữ attribution, pin source, checksum, SBOM, patch ledger và
reproducible build thay vì kéo binary mới nhất lúc runtime.

### 7. Runtime trace chưa phải parity hoàn chỉnh

Ở cutoff, `ingest_traces` có mặt trong tool surface nhưng source còn thông báo
việc tạo runtime edge chưa được triển khai đầy đủ. "Tool contract parity" và
"semantic behavior parity" phải là hai cột test riêng.

## Kết quả dogfood trên Piloth

Build upstream được chạy trực tiếp trên Piloth:

| Chỉ số | Kết quả cục bộ |
|---|---:|
| Files indexed | 183 |
| Nodes | 2,640 |
| Edges | 8,907 |
| Full index wall time | 6.42 s |
| Skipped | 0 |
| Partial parse | 1 JavaScript file |
| Warm CLI process wall time/query | khoảng 1.13-1.28 s |

Các kết quả có ích:

- trace canonical source tìm đúng caller/callee;
- snippet trả exact live source;
- coverage chỉ đúng file JavaScript parse một phần.

Các kết quả sai hoặc nhiễu:

- package overview lẫn Python builtins;
- cùng symbol xuất hiện ở `src/guard/*.py` và generated bundle
  `pilothOS/scripts/pilothos_guard.py`;
- short-name trace trở nên ambiguous dù hai symbol là cùng logic.

Dogfood này dẫn tới cải tiến riêng của Piloth: dùng provenance, generated marker,
body hash và manifest để giữ một canonical symbol, thay vì buộc consumer tự loại
duplicate do build artifact.

## Điểm tinh tế nhất cần mang sang Piloth

Không phải "index càng nhiều càng tốt", mà là **calibrated ignorance**:

- provenance cho biết node đến từ source hay generated artifact;
- freshness cho biết graph còn đại diện cho source hiện tại không;
- coverage cho biết một kết luận âm có đáng tin không;
- confidence quyết định khi nào phải đọc source;
- exact snippet luôn đọc live source, không phát lại blob cũ từ index.

Graph vì thế là query planner và evidence cache, không phải Memory và không phải
source of truth.

## Góc nhìn top 0.1%

Người thiết kế hệ này ở mức cao nhất sẽ tối ưu **expected information gain trên
mỗi token và millisecond**, không tối ưu số node hay số ngôn ngữ trên README.
Họ sẽ:

- đo cả chi phí tạo index, startup, invalidation và source fallback;
- đặt non-inferiority gate trước cost/speed win;
- coi negative claim khó hơn positive match;
- tách parser coverage, edge correctness và agent task outcome;
- làm contract adapter-neutral trước khi chọn native engine;
- dùng corpus lỗi thật và differential oracle, không chỉ synthetic benchmark;
- giữ graph có thể xóa/rebuild vì nó là derived state.

## Cách đặt lại vấn đề

Thách thức không phải:

> Làm sao để Piloth nhớ toàn bộ codebase?

Mà là:

> Làm sao để Piloth biết phần nào cần biết ngay, phần nào có thể lấy rẻ từ graph,
> phần nào graph không đủ tin cậy, và bằng chứng nhỏ nhất nào phải đọc từ source
> trước khi hành động?

Theo cách đặt này, "nắm codebase" không phải trạng thái nhị phân. Đó là một
policy điều phối bằng provenance + freshness + coverage + confidence, có source
fallback bắt buộc.
