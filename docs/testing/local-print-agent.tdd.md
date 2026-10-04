# Local receipt print agent — TDD evidence

Source: user journeys derived during this implementation.

## User journeys

1. As an admin, when I confirm a payment or refund, I want the receipt sent to my local thermal printer automatically.
2. As a developer, I want a local test receipt and permanent printer-size controls so I can calibrate each cashier computer.
3. As a Windows operator, I want downloadable installer files and a guide to start the print agent.

## Evidence

| Guarantee | Test | RED | GREEN |
|---|---|---|---|
| The local agent creates bounded ESC/POS jobs and rejects unsafe input | `python3 -m unittest tests/test_local_print_agent.py` | Failed because `diamond-print-agent.py` did not exist | 3 tests pass |
| Paper preferences validate and persist per local computer | `python3 -m unittest tests/test_local_print_agent.py` | Failed: missing `validate_settings` | 3 tests pass |
| Confirmed payment/refund tries the agent before browser fallback; Developer page has downloads, test print, settings | `python3 -m unittest tests/test_local_auto_printing.py` | Failed before helper/page existed | 3 tests pass |
| Receipt is Uzbek-only, compact, and has a small side inset | `python3 -m unittest tests/test_thermal_receipt_layout.py` | Failed against prior bilingual layout | 1 test passes |

Final command actually run:

```text
python3 -m unittest tests/test_local_print_agent.py tests/test_thermal_receipt_layout.py tests/test_local_auto_printing.py
.......
Ran 7 tests
OK
```

Type checking: `tsc --noEmit` completed with exit status 0. A local smoke server also returned `{"ok": true}` from `GET /health` on `127.0.0.1`.

Coverage note: these focused standard-library tests cover the agent validation/rendering/settings and source-level wiring. Physical printing cannot be automated without the XP-58IIL connected; the Developer page now provides the physical test print control.
