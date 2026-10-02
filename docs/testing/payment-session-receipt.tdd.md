# Payment receipt and session persistence — TDD evidence

## User journeys

1. As an admin, I can confirm an entered partial payment so the exact paid
   amount and remaining debt are shown on the receipt.
2. As a signed-in web user, I stay signed in beyond one day unless I log out,
   change my password, am blocked, or a session policy revokes access.
3. As an admin, I can build after clearing `.next` without requiring an
   external Google Fonts cache.

## RED → GREEN

The focused test file was run against the server virtual environment because
the local system Python does not include the project test dependencies.

| Stage | Command | Result |
|---|---|---|
| RED | `.venv/bin/python -m pytest -q /tmp/diamond-payment-receipts-red-test.py` | 2 expected failures: missing receipt financial snapshot helper; web TTL was `24`, not `720`. |
| GREEN | `.venv/bin/python -m pytest -q tests/test_payment_receipts.py` | `5 passed` |
| Type/compile | `python3 -m py_compile backend/main.py && npx --no-install tsc --noEmit` | Passed |
| Clean production build | server `npm run build` after `.next` cleanup | Exit `0` |

## Guarantees

| # | Guarantee | Test | Result |
|---|---|---|---|
| 1 | A partial transaction stores its payment amount, remaining balance, overpayment and status for the receipt. | `test_receipt_financial_snapshot_preserves_partial_payment_and_remaining_balance` | PASS |
| 2 | Browser sessions are issued for 30 days, matching mobile session duration. | `test_web_sessions_default_to_thirty_days_to_prevent_daily_logout` | PASS |
| 3 | Receipt payload remains restricted to immutable receipt data. | `test_receipt_public_payload_only_returns_immutable_snapshot` | PASS |
| 4 | Receipt PDF renders server-side from its snapshot. | `test_receipt_pdf_is_rendered_from_server_snapshot` | PASS |

## Notes

- Existing browser tokens that had already passed the previous 24-hour expiry
  cannot safely be revived; users affected by that old policy must sign in once.
- Existing receipts missing balance fields are backfilled only from their
  original transaction's persisted `*_after` values and the action is audited.
