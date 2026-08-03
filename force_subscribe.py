"""Optional forced Telegram channel subscription for the student bot."""
from __future__ import annotations

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import FORCE_SUBSCRIBE, FORCE_SUBSCRIBE_CHANNEL_ID, FORCE_SUBSCRIBE_CHANNEL_URL
from i18n import t


async def is_user_subscribed(bot: Bot, user_id: int) -> bool:
    """Return True if subscription is disabled or the user is a member of the channel."""
    if not FORCE_SUBSCRIBE or not FORCE_SUBSCRIBE_CHANNEL_ID:
        return True

    try:
        member = await bot.get_chat_member(FORCE_SUBSCRIBE_CHANNEL_ID, user_id)
        return member.status in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        )
    except Exception:
        return False


async def check_subscription_and_notify(
    bot: Bot,
    event: Message | CallbackQuery,
    lang: str = "uz",
) -> bool:
    """If not subscribed, send the channel prompt and return False."""
    user_id = event.from_user.id

    if await is_user_subscribed(bot, user_id):
        return True

    text = t(lang, "force_subscribe_text")
    url = FORCE_SUBSCRIBE_CHANNEL_URL or "https://t.me/diamond_education1"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "force_subscribe_btn"), url=url)]
        ]
    )

    if isinstance(event, Message):
        await event.answer(text, reply_markup=kb, disable_web_page_preview=True)
    else:
        await event.message.answer(text, reply_markup=kb, disable_web_page_preview=True)

    return False
