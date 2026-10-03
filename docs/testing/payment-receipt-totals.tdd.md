# Payment receipt totals and limits — TDD evidence

## Source and journeys

No plan file was supplied. The journeys were derived from the payment-screen request:

1. An administrator records a partial payment and receives a receipt showing the current payment, cumulative paid total, and remaining balance in Uzbek and Russian.
2. An administrator cannot record a payment above the persisted outstanding balance or a refund above the attendance-created credit.
3. An administrator sees the refundable amount only after selecting a student and only when `Sababli` attendance created that credit; an unrefunded credit is carried forward by the existing next-month carry-forward job.
4. Searching students and applying payment-page filters does not issue a server aggregate request for every keystroke.

## RED / GREEN checkpoints

| Stage | Commit / evidence | Result |
| --- | --- | --- |
| RED | `f97fb0a test: cover receipt totals and payment limits` | The pre-change implementation failed the new receipt-total and over-limit assertions on the isolated verification source. |
| RED | `test_attendance_credit_is_not_carried_into_a_future_month_early` | The implementation had no target-month guard (`AttributeError`), proving the timing rule was absent. |
| GREEN | Source validation below, after implementation | 10 receipt/payment tests passed; Python compilation passed. |

## Guarantees

| # | What is guaranteed | Test / validation | Type | Result |
| --- | --- | --- | --- | --- |
| 1 | A receipt snapshot keeps its current payment, running paid total, and remaining balance. | `tests/test_payment_receipts.py` | Unit | PASS |
| 2 | A total of zero after a refund remains zero and is not replaced with the original payment amount. | `test_refund_receipt_financial_snapshot_keeps_zero_total_paid` | Unit | PASS |
| 3 | Amounts above the persisted payment/refund limit are rejected. | `test_payment_amount_cannot_exceed_the_outstanding_or_refundable_limit` | Unit | PASS |
| 4 | The server-rendered PDF contains total-paid and Receipt ID fields, without Payment ID or an approval-status footer. | `test_receipt_pdf_is_rendered_from_server_snapshot` | Unit | PASS |
| 5 | The TypeScript payment screen, including auto-print and debounced search changes, type-checks. | `node_modules/.bin/tsc --noEmit` in a temporary verification copy | Static check | PASS |
| 6 | Attendance credit is not carried into a future calendar month early. | `test_attendance_credit_is_not_carried_into_a_future_month_early` | Unit | PASS |

## Commands and output

The backend was validated without changing the deployed application, using a temporary copy:

```text
PYTHONPATH=/tmp/diamond-receipt-verify:/root/diamond-site \
  .venv/bin/pytest -q /tmp/diamond-receipt-verify/tests/test_payment_receipts.py
.venv/bin/python -m py_compile /tmp/diamond-receipt-verify/backend/main.py
```

Output: `10 passed` (the environment emitted unrelated dependency deprecation warnings).

The frontend was copied to `/tmp/diamond-frontend-verify` and checked against the already-installed dependencies:

```text
node_modules/.bin/tsc --noEmit
```

Output: exit status 0.

## Coverage and known gaps

This repository has no configured coverage command for the Python payment suite, and the frontend has no component test harness for this screen. The payment rules and PDF output have direct unit coverage; the browser auto-print dialog and the debounced request cadence are type-checked but still require a manual browser confirmation after deployment.
