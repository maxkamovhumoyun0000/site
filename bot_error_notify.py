"""
Ishlov berilmagan istisnolar uchun admin chatlarga HTML xabar (Student/Teacher/Admin/Support botlar).
"""
from __future__ import annotations

import html
import logging
import traceback
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ErrorEvent, Update, User

from config import ADMIN_BOT_TOKEN, ALL_ADMIN_IDS
from db import (
    get_user_by_telegram,
    get_student_subjects,
    get_user_groups,
    get_student_teachers,
    get_groups_by_teacher,
)

logger = logging.getLogger(__name__)

_MAX_TOTAL = 4000
_MAX_TB = 3200
_MAX_ACTION = 800


def _tg_user_from_update(update: Update) -> User | None:
    if update.message and update.message.from_user:
        return update.message.from_user
    if update.edited_message and update.edited_message.from_user:
        return update.edited_message.from_user
    if update.callback_query and update.callback_query.from_user:
        return update.callback_query.from_user
    if update.inline_query and update.inline_query.from_user:
        return update.inline_query.from_user
    if update.chosen_inline_result and update.chosen_inline_result.from_user:
        return update.chosen_inline_result.from_user
    if update.poll_answer and update.poll_answer.user:
        return update.poll_answer.user
    if update.my_chat_member and update.my_chat_member.from_user:
        return update.my_chat_member.from_user
    return None


def describe_user_action(update: Update | None) -> str:
    if not update:
        return "—"
    try:
        if update.message:
            m = update.message
            if m.text:
                return f"message.text: {m.text[:_MAX_ACTION]}"
            if m.caption:
                return f"message.caption: {m.caption[:_MAX_ACTION]}"
            for k in ("photo", "document", "voice", "video", "audio", "sticker", "location", "contact"):
                if getattr(m, k, None):
                    return f"message.{k}"
            return "message (other)"
        if update.callback_query:
            cq = update.callback_query
            parts = [f"callback_data: {cq.data}"]
            if cq.message:
                parts.append(f"chat_id: {cq.message.chat.id}")
            return " | ".join(parts)[:_MAX_ACTION]
        if update.edited_message:
            return f"edited_message: {(update.edited_message.text or update.edited_message.caption or '')[:_MAX_ACTION]}"
    except Exception:
        pass
    u = update.model_dump() if hasattr(update, "model_dump") else {}
    keys = [k for k in u if u.get(k)]
    return f"update keys: {', '.join(keys[:12])}" if keys else "—"


def _user_context_block(telegram_id: str | None) -> str:
    if not telegram_id:
        return "<i>Telegram ID aniqlanmadi</i>"
    user = get_user_by_telegram(str(telegram_id))
    if not user:
        try:
            if str(telegram_id).isdigit() and int(telegram_id) in {int(x) for x in (ALL_ADMIN_IDS or []) if x}:
                return "<i>Admin Telegram hisobi (DB user row talab qilinmaydi).</i>"
        except Exception:
            pass
        return "<i>Ma’lumotlar bazasida bu Telegram hisob topilmadi.</i>"

    lid = html.escape(str(user.get("login_id") or "-"))
    name = html.escape(
        f"{user.get('first_name') or ''} {user.get('last_name') or ''}".strip() or "-"
    )
    lt = user.get("login_type")

    if lt in (1, 2):
        subjects = get_student_subjects(user["id"]) or []
        subs = html.escape(", ".join(subjects) if subjects else (user.get("subject") or "-"))
        groups = get_user_groups(user["id"]) or []
        if groups:
            gtxt = ", ".join(
                [
                    f"{html.escape(str(g.get('name') or '-'))} ({html.escape(str(g.get('level') or '-'))})"
                    for g in groups
                ]
            )
        else:
            gtxt = "-"
        teachers = get_student_teachers(user["id"]) or []
        if teachers:
            ttxt = ", ".join(
                [
                    f"{html.escape(str(t.get('first_name') or '').strip())} "
                    f"{html.escape(str(t.get('last_name') or '').strip())} "
                    f"— {html.escape(str(t.get('group_name') or '-'))}"
                    for t in teachers
                ]
            )
        else:
            ttxt = "-"
        return (
            f"Login ID: <code>{lid}</code>\n"
            f"👤 Ism Familya: <b>{name}</b>\n"
            f"📚 Fanlar: {subs}\n"
            f"👨‍🏫 Teacherlar: {ttxt}\n"
            f"👥 Guruhlar haqida ma’lumot: {gtxt}\n"
        )

    if lt == 3:
        groups = get_groups_by_teacher(user["id"]) or []
        if groups:
            gtxt = ", ".join(
                [
                    f"{html.escape(str(g.get('name') or '-'))} "
                    f"[{html.escape(str(g.get('subject') or '-'))}]"
                    for g in groups
                ]
            )
        else:
            gtxt = "-"
        subj = html.escape(str(user.get("subject") or "-"))
        return (
            f"Login ID: <code>{lid}</code>\n"
            f"👤 Ism Familya: <b>{name}</b> <i>(o‘qituvchi)</i>\n"
            f"📚 Fan (akkaunt): {subj}\n"
            f"👥 Guruhlar: {gtxt}\n"
        )

    return (
        f"Login ID: <code>{lid}</code>\n"
        f"👤 Ism Familya: <b>{name}</b>\n"
        f"login_type: {html.escape(str(lt))}\n"
    )


def build_error_report_html(*, bot_label: str, event: ErrorEvent) -> str:
    update = event.update
    exc = event.exception
    tg_user = _tg_user_from_update(update)
    uname = (
        f"@{html.escape(tg_user.username)}"
        if tg_user and tg_user.username
        else html.escape(str(tg_user.id) if tg_user else "—")
    )
    tid = str(tg_user.id) if tg_user else None
    action = html.escape(describe_user_action(update))
    err_text = html.escape(str(exc)[:1200])
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    if len(tb) > _MAX_TB:
        tb = tb[:_MAX_TB] + "\n… (qisqartirildi)"
    tb_html = html.escape(tb)

    handler_hint = "—"
    try:
        stacks = traceback.extract_tb(exc.__traceback__)
        if stacks:
            last = stacks[-1]
            handler_hint = html.escape(f"{last.filename}:{last.lineno} in {last.name}")
    except Exception:
        pass

    ctx = _user_context_block(tid)

    base = (
        f"🚨 <b>BOT ERROR</b> ({html.escape(bot_label)}) · {uname}\n\n"
        f"{ctx}\n"
        f"🔧 <b>Handler / joy:</b> {handler_hint}\n"
        f"❌ <b>Error:</b> <code>{err_text}</code>\n"
        f"📝 <b>User Action:</b> <code>{action}</code>\n\n"
        f"<b>Traceback:</b>\n"
    )
    tail = "<i>…(xabar qisqartirildi)</i>"
    body = f"{base}<pre>{tb_html}</pre>"
    if len(body) <= _MAX_TOTAL:
        return body

    # Keep HTML entities and <pre> tags valid even when truncating.
    available = max(0, _MAX_TOTAL - len(base) - len("<pre></pre>\n") - len(tail))
    safe_tb_html = tb_html[:available]
    if safe_tb_html.endswith("&"):
        safe_tb_html = safe_tb_html[:-1]
    elif safe_tb_html.endswith("&lt") or safe_tb_html.endswith("&gt") or safe_tb_html.endswith("&amp"):
        safe_tb_html = safe_tb_html.rsplit("&", 1)[0]
    return f"{base}<pre>{safe_tb_html}</pre>\n{tail}"


async def notify_admins_unhandled_bot_error(
    *,
    bot_label: str,
    event: ErrorEvent,
    admin_bot_instance: Bot | None = None,
) -> None:
    recipients = [int(x) for x in (ALL_ADMIN_IDS or []) if x]
    if not recipients or not ADMIN_BOT_TOKEN:
        logger.warning("Adminga xato xabari: ALL_ADMIN_IDS yoki ADMIN_BOT_TOKEN bo‘sh")
        return

    text = build_error_report_html(bot_label=bot_label, event=event)
    bot = admin_bot_instance
    if not bot:
        bot = Bot(token=ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        own_session = True
    else:
        own_session = False

    try:
        for aid in recipients:
            try:
                await bot.send_message(aid, text, parse_mode="HTML")
            except Exception:
                logger.exception("Admin %s ga bot error xabari yuborilmadi", aid)
    finally:
        if own_session:
            try:
                await bot.session.close()
            except Exception:
                pass


def build_handled_error_report_html(
    *,
    bot_label: str,
    flow: str,
    exception: Exception,
    telegram_id: str | None = None,
    username: str | None = None,
    context: dict | None = None,
) -> str:
    uname = f"@{html.escape(username)}" if username else html.escape(str(telegram_id or "—"))
    err_text = html.escape(str(exception)[:1200])
    tb = "".join(traceback.format_exception(type(exception), exception, exception.__traceback__))
    if len(tb) > _MAX_TB:
        tb = tb[:_MAX_TB] + "\n… (qisqartirildi)"
    tb_html = html.escape(tb)
    ctx_block = _user_context_block(telegram_id)
    ctx_text = html.escape(str(context or {})[:1000])

    base = (
        f"🚨 <b>BOT ERROR</b> ({html.escape(bot_label)}) · {uname}\n\n"
        f"{ctx_block}\n"
        f"🔧 <b>Flow:</b> <code>{html.escape(flow)}</code>\n"
        f"❌ <b>Error:</b> <code>{err_text}</code>\n"
        f"📝 <b>Context:</b> <code>{ctx_text}</code>\n\n"
        f"<b>Traceback:</b>\n"
    )
    tail = "<i>…(xabar qisqartirildi)</i>"
    body = f"{base}<pre>{tb_html}</pre>"
    if len(body) <= _MAX_TOTAL:
        return body
    available = max(0, _MAX_TOTAL - len(base) - len("<pre></pre>\n") - len(tail))
    safe_tb_html = tb_html[:available]
    if safe_tb_html.endswith("&"):
        safe_tb_html = safe_tb_html[:-1]
    elif safe_tb_html.endswith("&lt") or safe_tb_html.endswith("&gt") or safe_tb_html.endswith("&amp"):
        safe_tb_html = safe_tb_html.rsplit("&", 1)[0]
    return f"{base}<pre>{safe_tb_html}</pre>\n{tail}"


async def notify_admins_handled_exception(
    *,
    bot_label: str,
    flow: str,
    exception: Exception,
    telegram_id: str | None = None,
    username: str | None = None,
    context: dict | None = None,
    admin_bot_instance: Bot | None = None,
) -> None:
    recipients = [int(x) for x in (ALL_ADMIN_IDS or []) if x]
    if not recipients or not ADMIN_BOT_TOKEN:
        logger.warning("Adminga handled xato xabari: ALL_ADMIN_IDS yoki ADMIN_BOT_TOKEN bo‘sh")
        return

    text = build_handled_error_report_html(
        bot_label=bot_label,
        flow=flow,
        exception=exception,
        telegram_id=telegram_id,
        username=username,
        context=context or {},
    )
    bot = admin_bot_instance
    if not bot:
        bot = Bot(token=ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        own_session = True
    else:
        own_session = False

    try:
        for aid in recipients:
            try:
                await bot.send_message(aid, text, parse_mode="HTML")
            except Exception:
                logger.exception("Admin %s ga handled bot error xabari yuborilmadi", aid)
    finally:
        if own_session:
            try:
                await bot.session.close()
            except Exception:
                pass
