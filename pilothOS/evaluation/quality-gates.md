# Quality Gates

Một task chỉ được Deliver khi các gate liên quan đạt:

| Gate | Câu hỏi |
|---|---|
| Scope | Output có giải quyết đúng yêu cầu, không mở rộng ngoài phạm vi? |
| Correctness | Có test, check hoặc Evidence xác nhận kết quả? |
| Architecture | Thành phần có nằm đúng layer và responsibility? |
| Simplicity | Có giải pháp đơn giản hơn mà vẫn đáp ứng? |
| Regression | Thay đổi có phá behavior hiện có? |
| Traceability | Quyết định và thay đổi có truy vết được? |
| Disclosure | Limitation, assumption và phần chưa verify đã được nêu rõ? |

Kết quả gate phải là `PASS`, `FAIL` hoặc `NOT_APPLICABLE`, kèm Evidence.
