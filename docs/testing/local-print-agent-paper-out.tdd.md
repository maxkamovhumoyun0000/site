# Local print agent paper-out warning — TDD evidence

## User journey

As a cashier, when the XP-58IIL has no paper, I see an Uzbek warning and hear a
short alarm instead of silently opening a browser-print fallback.

## RED

`python3 -m unittest tests/test_thermal_receipt_layout.py` failed before the
implementation because `paper_status_from_text` did not exist.

## GREEN

The same test now verifies that `media-empty-error` is classified as
`paper_out`, a normal idle CUPS status is `ready`, disabled queues are
`unavailable`, and the web client has both the paper state and alert hook.

The agent exposes `paper_status` and `paper_message` in `/health` and print
responses. CUPS media-empty signals prevent spooling; driver error text is
also classified. The web UI shows the error and uses Web Audio for three short
beeps during a user-triggered print or developer test.

## Validation

- `python3 -m unittest tests/test_thermal_receipt_layout.py` — 7 passed.
- `python3 -m py_compile public/downloads/diamond-print-agent.py …` — passed.
- `npm run lint` — passed.
- The installed Linux agent was restarted; `/health` reports `XP58IIL` and
  `paper_status: ready`.

The repository-wide Python discovery suite is not runnable in this checkout:
the local interpreter lacks project dependencies such as `fastapi`, `pytest`,
`psycopg`, and `openpyxl`. Existing legacy test expectations also target the
pre-server-generated receipt agent.
