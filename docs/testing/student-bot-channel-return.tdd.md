# Student Bot channel return — TDD evidence

Source: user journey derived during this TDD run (no plan file supplied).

## User journey

As a Diamond Students user, after I link my account and prove channel
membership, I can reopen the Mini App from the same Student Bot message
without being sent through a second Telegram `/start` flow.

## Evidence

- RED: direct execution of
  `test_verified_channel_membership_reopens_the_miniapp_without_another_start`
  failed because `_channel_link_success_keyboard` did not exist.
- GREEN: direct execution of all three Telegram handoff contract checks passed.
- Static validation: `python3 -m py_compile student_bot.py` and
  `git diff --check` passed.

| Guarantee | Test | Result |
| --- | --- | --- |
| Link, channel join, and verification stay in one bot chat | `tests/test_telegram_handoff_contract.py` | PASS |
| Successful verification gives a native Mini App WebApp button, not a `/start` deep link | `tests/test_telegram_handoff_contract.py` | PASS |
| Existing terminal Telegram-auth UI behavior remains guarded | `tests/test_telegram_handoff_contract.py` | PASS |
