from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_student_bot_channel_handoff_stays_inside_the_bot() -> None:
    source = (ROOT / "student_bot.py").read_text(encoding="utf-8")

    # Account linking and the subsequent membership check must use inline
    # callbacks in the already-open Student Bot, not a second `/start` route.
    assert '_CHANNEL_JOIN_VERIFY_CALLBACK_PREFIX = "channel_join_verify:"' in source
    assert 'callback_data=f"{_CHANNEL_JOIN_VERIFY_CALLBACK_PREFIX}{request_token}"' in source
    assert "async def verify_student_channel_membership" in source
    assert "check_subscription_and_notify(callback.message.bot, callback, lang=lang)" not in source


def test_mini_app_never_keeps_a_terminal_telegram_auth_failure_in_checking_state() -> None:
    source = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")

    assert "function isTerminalTelegramAuthError" in source
    assert "isTerminalTelegramAuthError(msg)" in source
    assert "!user && isTelegramClient && !authResolved" in source
