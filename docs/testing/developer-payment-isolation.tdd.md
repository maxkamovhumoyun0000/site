# Developer role and refund receipt — TDD evidence

## User journeys

- As the dedicated Developer user, I only see the Developer workspace and can
  never enter an administrator workspace through a cached role or API payload.
- As an administrator, I can enter any positive payment amount once; the
  server calculates whether its resulting status is partial, paid, or
  overpaid from persisted obligation totals.
- As an administrator, I can issue, print, and download an immutable refund
  receipt with the same identifying fields shown vertically as a payment
  receipt.

## RED evidence

- `5fbdc8f test: reproduce developer admin role crossover`: production code
  classified `DEVELOPER-X-01` as `admin`.
- `efd0a85 test: reproduce refund receipt snapshot`: targeted production test
  failed with `AttributeError` because no refund receipt snapshot existed.
  Result: 1 failed, 5 passed.

## GREEN evidence

- Developer login now has a dedicated `developer` role, empty/minimal app
  state, a developer-only UI data source, and the existing allowlisted API
  guard. Normal login-type-4 users remain `admin`.
- Refund receipt data is derived solely from the persisted refund, source
  transaction, user, and group records. The receipt has a stable `REF-<id>-01`
  identifier; viewing, printing, and PDF creation are authorization-checked
  and written to the payment audit log.
- The payment confirmation API no longer accepts a client-provided
  `is_partial` switch. The persisted obligation calculation determines the
  resulting payment status. The web UI has one confirmation action and hides
  Group, Admin, and next-overpayment columns from the transaction table.
- Isolated production-equivalent test run: 15 passed
  (`test_payment_receipts.py`, `test_app_version_controls.py`).
- Static validation: `python3 -m py_compile backend/main.py` and
  `npx tsc --noEmit` passed.

## Coverage note

The repository has focused Python tests and no configured coverage command.
The targeted unit suite covers role classification, minimal developer app
state, receipt financial snapshots, refund receipt snapshot derivation, and
server-side PDF generation. Production smoke checks remain required after
deploy.
