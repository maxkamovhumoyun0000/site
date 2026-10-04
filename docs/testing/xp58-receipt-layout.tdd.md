# XP-58IIL receipt layout — TDD evidence

## User journey

As a cashier, I print a receipt on the XPrinter XP-58IIL and it uses the full
thermal print width without an oversized blank tail or clipped 80 mm layout.

## RED / GREEN evidence

| Stage | Command | Result |
|---|---|---|
| RED | `python3 tests/test_thermal_receipt_layout.py` | Failed because the receipt declared 80 mm paper, a 66 mm content width, duplicate IDs, and a confirmation footer. |
| GREEN | `python3 tests/test_thermal_receipt_layout.py` | Passed after the receipt was constrained to the full 48 mm XP-58 printable area with zero margins. |

## Guarantees

| Guarantee | Test |
|---|---|
| Browser print CSS uses a 48 mm page and full 48 mm content width. | `test_thermal_receipt_layout.py` |
| Duplicate Payment ID and confirmation footer are absent; Chek ID remains. | `test_thermal_receipt_layout.py` |

The XP-58IIL uses 58 mm rolls. Its official CUPS XP-58 profile exposes a
48 mm raster width; the receipt has no application-added side margins.
