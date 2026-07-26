# Quality Gates

Một task chỉ được Deliver khi các gate liên quan đạt:

| Gate | Câu hỏi |
|---|---|
| Scope | Output có giải quyết đúng yêu cầu, không mở rộng ngoài phạm vi? |
| Correctness | Có test, check hoặc Evidence xác nhận kết quả? |
| Architecture | Thành phần có nằm đúng layer và responsibility? |
| Simplicity | Có giải pháp đơn giản hơn mà vẫn đáp ứng? |
| Reuse / Non-Duplication | Agent đã check code/assets hiện có, reuse convention/DS/tools khi phù hợp, tránh duplicate helper/component, ở đúng consumer scope và justify abstraction mới chưa? |
| Regression | Thay đổi có phá behavior hiện có? |
| Traceability | Quyết định và thay đổi có truy vết được? |
| Disclosure | Limitation, assumption và phần chưa verify đã được nêu rõ? |
| UI Quality | Browser/visual evidence có bắt lỗi UI người dùng thấy được không? |

Kết quả gate phải là `PASS`, `FAIL` hoặc `NOT_APPLICABLE`, kèm Evidence.

## Required Gates By Work Type

`os-close` requires these receipt gates:

| Work type | Required gates |
|---|---|
| Any OS-closed task | `scope`, `correctness`, `traceability`, `disclosure` |
| Code/runtime/rules/adapter/tool changes | base gates + `architecture`, `reuse_non_duplication`, `regression` |
| UI/component changes | base gates + `design_system`, `ui_quality` |
| Design token generation | relevant gates + `design_token_coverage` |
| Release/deploy tasks | relevant gates + `operational_approval` |
| Consumer value / Piloth superiority claims | benchmark evidence proving no mandatory regression, real token telemetry and at least one consumer-visible win |

Direct `receipt-write` remains backward compatible with V1 receipts, but normal
delivery should close through `os-close` so the complete gate set is checked.

Evidence cho gate Reuse / Non-Duplication:

- `context_evidence`;
- `reuse_evidence`;
- diff facts;
- verification result.

Evidence cho gate `design_token_coverage`:

- `figma_node` evidence with `fileKey` and `nodeId`/`frameId`;
- `design_token_coverage` evidence with source refs and explicit
  `covered_groups`;
- generated surfaces (`ts`, `css_vars`, `tailwind_v3`, `tailwind_v4`) or a
  receipt limitation that qualifies the claim;
- build/typecheck/visual check evidence, or a limitation when the check was not
  run.

Evidence cho gate `ui_quality`:

- `ui_quality` metric recorded with viewport and browser/tool name;
- required text/semantic content result;
- console and page error counts;
- image failure count when images are used;
- overflow or layout overflow count;
- visual diff result and screenshot/artifact paths when available.

`os-close` rejects a successful UI receipt when `ui_quality` reports missing
required text, browser errors, failed images, overflow or failed visual diff.
Skipped pixel diff must be disclosed and cannot support `1:1` or
`pixel-perfect` claims.

Unqualified claims such as “full design tokens”, “all tokens”, “entire
library”, `1:1`, `pixel-perfect`, `production-ready`, “fully verified” or “no
issues” require matching evidence refs. Full design-token claims only pass when
coverage is declared as `full_declared_source` and source refs/surfaces support
that claim. Sampled frame coverage must be claimed as sampled/partial.

Claims that Piloth is cheaper, better, more accurate, superior, token-saving or
valuable to the consumer require benchmark evidence. The benchmark must compare
`none-piloth` and `had-piloth` on the same task. Piloth can only pass consumer
value when every mandatory metric is not worse, real token telemetry is present
and at least one consumer-visible metric wins. If Piloth only adds audit
overhead while output is the same, record `consumer_value_failed`.

Receipt shape for code/UI/runtime/rules/adapter changes:

```json
{
  "quality_gates": {
    "scope": {
      "result": "PASS|FAIL|NOT_APPLICABLE",
      "evidence": "scope evidence"
    },
    "correctness": {
      "result": "PASS|FAIL|NOT_APPLICABLE",
      "evidence": "test/check evidence"
    },
    "traceability": {
      "result": "PASS|FAIL|NOT_APPLICABLE",
      "evidence": "contract, diff facts, receipt/seal evidence"
    },
    "disclosure": {
      "result": "PASS|FAIL|NOT_APPLICABLE",
      "evidence": "limitations/skipped checks or none"
    },
    "reuse_non_duplication": {
      "result": "PASS|FAIL|NOT_APPLICABLE",
      "evidence": "context/reuse evidence, diff facts, verification result"
    },
    "ui_quality": {
      "result": "PASS|FAIL|NOT_APPLICABLE",
      "evidence": "ui_quality metric with browser/visual checks"
    },
    "design_token_coverage": {
      "result": "PASS|FAIL|NOT_APPLICABLE",
      "evidence": "Figma refs, covered groups, generated surfaces and verification/limitation"
    }
  }
}
```
