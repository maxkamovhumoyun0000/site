# Telegram channel handoff and Mini App authentication — TDD evidence

## Behaviour protected

1. The native Student app opens exactly one Student Bot hand-off.  Account
   linking, joining the official channel and checking membership all happen in
   that same bot chat; the post-link check is an inline callback, not another
   `/start` route.
2. The native membership screen does not duplicate a separate external channel
   button.  The account-deletion action on that blocking screen is replaced by
   a confirmed logout action.
3. Mini App authentication keeps the Telegram `initData` signature check on
   the server.  A terminal server decision (invalid/expired data, blocked or
   unregistered account) resolves the loading state instead of repeatedly
   showing “Telegram akkaunti tekshirilmoqda”.  Only transport failures retry.

## RED

- `tests/test_telegram_handoff_contract.py` initially failed its static
  contracts: the bot had no post-join verify callback, the Mini App had no
  terminal Telegram-auth classifier, and its Telegram loading branch ignored
  `authResolved`.
- `test/telegram_channel_gate_contract_test.dart` initially failed: the
  Student app exposed both a direct channel button and account deletion rather
  than logout.

## GREEN verification

Run without producing an Android/iOS build:

```bash
pytest -q tests/test_telegram_handoff_contract.py
python3 -m py_compile student_bot.py backend/main.py
cd "/home/xumoyun-maxkamov/Desktop/Diamond Students APP/diamond_students"
flutter test test/telegram_channel_gate_contract_test.dart
flutter analyze lib/features/channel_membership/telegram_channel_gate.dart
```

The production deploy smoke test must also confirm the Student Bot and backend
services are active. Telegram's platform-owned first-open **Start** affordance
cannot be removed; this change removes the accidental second Start-like
handoff after account linking.
