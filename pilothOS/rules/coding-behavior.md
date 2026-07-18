# Coding Behavior Rules

> Thiên về cẩn trọng hơn tốc độ. Với task trivial, dùng judgment nhưng không bỏ verification.

## 1. Think Before Coding

- Nêu giả định; không chắc thì nói rõ.
- Có nhiều cách hiểu thì trình bày, không tự chọn ngầm.
- Có cách đơn giản hơn thì đề xuất.
- Yêu cầu chưa rõ thì dừng và làm rõ trước khi code.

## 2. Simplicity First

- Không thêm feature ngoài yêu cầu.
- Không tạo abstraction chỉ dùng một lần.
- Không thêm configurability khi chưa cần.
- Nếu 50 dòng đủ, không viết 200 dòng.

## 3. Surgical Changes

- Chỉ sửa phần cần thiết.
- Không refactor hoặc format code không liên quan.
- Tuân theo style hiện có.
- Nếu thấy dead code hoặc vấn đề không liên quan, báo lại nhưng không tự xóa hoặc sửa.
- Chỉ dọn imports, variables hoặc functions trở nên unused do chính thay đổi hiện tại.

> Mọi dòng thay đổi phải truy vết được về yêu cầu.

## 4. Goal-Driven Execution

Chuyển task thành goal kiểm chứng được:

- Fix bug → tái hiện → sửa → verify.
- Add validation → viết case invalid → làm pass.
- Refactor → xác nhận behavior trước và sau không đổi.

## 5. Evidence Before Conclusion

- Phân biệt Fact, Assumption và Opinion.
- Không tuyên bố hoàn thành khi chưa chạy verification phù hợp.
- Báo rõ phần chưa kiểm chứng hoặc Evidence còn thiếu.

## 6. No Guessing / No Duplicate / Reuse First

- Search existing code before creating new code.
- Reuse helper, component, tool or pattern if sufficient.
- Do not invent API, config or state outside consumer scope.
- Do not add abstraction for one use.
- Do not build a component if the design system has one.
- If context is missing, ask or declare assumption before editing.

Receipt for code/UI/runtime/rules/adapter changes must include:

```json
{
  "reuse_discipline": {
    "existing_code_checked": "...",
    "existing_component_checked": "...",
    "existing_pattern_followed": "...",
    "new_code_reason": "...",
    "duplicate_risk": "...",
    "kiss_dry_rationale": "..."
  }
}
```

UI-specific receipt fields:

```json
{
  "design_system_checked": "...",
  "component_reuse_decision": "...",
  "token_reuse_decision": "..."
}
```

## 7. Test-First (khi task có test harness)

- Định nghĩa test phản ánh success criteria trước khi implement.
- Xác nhận test fail trước, rồi mới implement để test pass.
- Task không có test harness: nêu rõ cách verify thay thế trong plan.

## Tiêu chí hiệu quả

Các Rule này đang phát huy hiệu quả khi:

- Diff có ít thay đổi thừa và mọi dòng sửa đều truy vết được về yêu cầu.
- Ít phải viết lại do abstraction hoặc thiết kế quá phức tạp.
- Câu hỏi làm rõ xuất hiện trước implementation, không phải sau khi đã làm sai.
- Verification và Evidence được báo cáo trước khi tuyên bố hoàn thành.
