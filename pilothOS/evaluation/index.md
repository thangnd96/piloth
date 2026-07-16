# Evaluation — Index

> Cross-cutting quality system; không phải layer thực thi.

## Purpose

Đánh giá output bằng acceptance criteria và Evidence trước khi Deliver.

## Responsibilities

- Quality gates.
- Acceptance criteria.
- Confidence và evidence coverage.
- Regression và safety checks.

## Non-Responsibilities

- Không sửa output; Runtime điều phối Repair.
- Không định nghĩa policy; Rules làm việc đó.
- Không thực thi tool; Agents và Tools làm việc đó.

## Contents

| File | Scope |
|---|---|
| `quality-gates.md` | Gate tối thiểu trước Deliver |

## Review Checklist

- Acceptance criteria có cụ thể, đo được và bám sát mục tiêu task không?
- Quality gate có Evidence đầy đủ và tránh false positive không?
- Regression, safety và confidence checks còn phù hợp không?
- Evaluation có đang sửa output thay vì chỉ phán định và trả kết quả cho Runtime không?

