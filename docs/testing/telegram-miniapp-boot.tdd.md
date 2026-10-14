# Telegram Mini App boot — TDD evidence

Source: user journey derived during this TDD run (no plan file was supplied).

## User journeys

- As a Telegram Mini App user, I am authenticated from Telegram's signed
  launch data (including `tgWebAppData` in the URL hash), so I never see the
  public hero page by mistake while the SDK object is late.
- As a deployer, I release an exact pushed commit with its directory layout,
  so an IDE's uncommitted changes cannot overwrite or remove a prior fix.

## RED / GREEN record

- RED: `python3 -c "...test_telegram_miniapp_boot_contract..."` failed with
  `AssertionError` for the missing `isTelegramRuntime` guard.
- GREEN: the same direct contract test command passed after the implementation.
- Added: the launch-hash contract passed; it proves that the UI derives the
  Telegram ID and signed init-data from `tgWebAppData` and sends that pair to
  the normal Telegram login-status request.
- Regression: direct execution of
  `tests/test_telegram_handoff_contract.py` passed for the existing Telegram
  channel handoff and terminal-auth-state guarantees.
- Static checks: `git diff --check` passed.

## Guarantees

| Guarantee | Test | Type | Result |
| --- | --- | --- | --- |
| Delayed Telegram `initData` stays in loading and retries | `tests/test_telegram_miniapp_boot_contract.py` | source contract | PASS |
| Telegram hash launch data is used for ID-based login | `tests/test_telegram_miniapp_boot_contract.py` | source contract | PASS |
| Deployment uses a committed snapshot and preserves relative paths | `tests/test_telegram_miniapp_boot_contract.py` | runbook contract | PASS |
| Existing channel-handoff and terminal Telegram auth guarantees remain | `tests/test_telegram_handoff_contract.py` | source contract | PASS |

## Coverage / known gaps

This repository does not have the Python `pytest` package installed and the
local frontend dependency tree currently lacks `eslint` (`npm run lint` exits
with `eslint: not found`). The targeted executable source-contract tests above
are the available verification for this change; production `npm run build` is
still required by `deploy.md` before release.
