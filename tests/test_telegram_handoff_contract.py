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


def test_verified_channel_membership_reopens_the_miniapp_without_another_start() -> None:
    source = (ROOT / "student_bot.py").read_text(encoding="utf-8")

    # A successful membership check returns the student to the Mini App via a
    # native WebApp button in this same bot chat. It must not send another
    # Telegram /start deep link or force the person through the bot entry flow.
    assert "def _channel_link_success_keyboard" in source
    assert 'text=_channel_link_copy(lang, "open_app")' in source
    assert "reply_markup=_channel_link_success_keyboard(lang)" in source
    assert "await callback.message.answer(_channel_link_copy(lang, \"approved\"), reply_markup=_channel_link_success_keyboard(lang))" in source


def test_mini_app_never_keeps_a_terminal_telegram_auth_failure_in_checking_state() -> None:
    source = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")

    assert "function isTerminalTelegramAuthError" in source
    assert "isTerminalTelegramAuthError(msg)" in source
    assert "!user && isTelegramClient && !authResolved" in source
