import logging
import re
import html as html_module
import io
from urllib.parse import unquote, urlencode
import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import ErrorEvent
from aiogram.client.default import DefaultBotProperties
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message, WebAppInfo
from aiogram.types import ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError, TelegramServerError
import asyncio
import time
import traceback
from pathlib import Path
try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:
    cv2 = None  # type: ignore
    np = None  # type: ignore
import pytz
from uuid import uuid4
from datetime import date as date_cls, timedelta, time as dtime, datetime as dt, timezone
from aiogram.client.default import DefaultBotProperties


from config import (
    STUDENT_BOT_TOKEN,
    ADMIN_BOT_TOKEN,
    SUBJECTS,
    ADMIN_CHAT_IDS,
    LIMITED_ADMIN_CHAT_IDS,
    SUPPORT_BOT_TOKEN,
    ALL_ADMIN_IDS,
    STUDENT_WEBHOOK_PORT,
    TELEGRAM_MINI_APP_BASE_URL,
)
from bot_runtime import create_resilient_bot, log_telegram_delivery_failure, run_bot_dispatcher, spawn_guarded_task
from db import (
    get_user_by_telegram, get_tests_by_subject, save_test_result, update_user_level,
    enable_access, get_test_by_id, is_access_active, get_user_by_id, save_placement_session,
    get_placement_session, clear_placement_session, add_dcoins, get_dcoins,
    add_dpoints,
    get_conn,
    get_leaderboard_global, get_leaderboard_count,
    get_user_groups, get_user_subjects, update_user_subjects,
    check_user_group_access,
    get_dpoints, try_consume_dcoins,
    get_student_subjects, get_student_teachers, get_latest_test_result_for_subject,
    get_grammar_attempts, increment_grammar_attempt, add_test_history,
    set_user_login_type,
    set_user_language_by_telegram, remove_user_from_group,
    upsert_telegram_group_chat, set_telegram_group_chat_active,
    ensure_daily_test_attempt_and_items,
    get_group_level_for_subject,
    get_daily_test_attempt_items,
    mark_daily_test_question_answered,
    mark_daily_test_question_timed_out,
    finish_daily_test_attempt,
    get_daily_test_reminder_candidates,
    get_student_ai_daily_requests,
    increment_student_ai_daily_requests,
    consume_dcoins_allow_negative,
    get_arena_group_session,
    get_arena_group_session_questions,
    mark_arena_group_session_attempt,
    finish_arena_group_session_attempt,
    distribute_arena_group_rewards_if_ready,
    get_active_arena_group_session_by_group_id,
    ensure_support_lessons_schema,
    is_lesson_holiday,
    is_branch_date_closed_for_booking,
    get_branch_date_closed_reason,
    is_slot_blocked,
    is_slot_closed_effective,
    get_slot_block_reason,
    get_lesson_branch_weekdays,
    lesson_is_slot_free,
    create_lesson_booking_request,
    refresh_lesson_reminders_for_booking,
    generate_lesson_booking_id,
    student_has_active_upcoming_booking,
    get_next_lesson_booking_allowed_after_utc_iso,
    list_lesson_bookings_for_student,
    set_lesson_booking_status,
    list_lesson_extra_slots_for_date,
    list_recurring_open_times_for_date,
    add_lesson_waitlist,
    pop_lesson_waitlist_for_slot,
    ensure_duel_matchmaking_schema,
    create_duel_session,
    get_open_duel_session,
    list_open_duel_sessions_for_mode,
    log_diamondvoy_query,
    get_duel_session,
    join_duel_session,
    count_duel_participants,
    list_duel_participants,
    mark_duel_session_started,
    mark_duel_session_finished,
    cancel_expired_open_duel_sessions,
    mark_duel_participant_refunded,
    save_duel_participant_result,
    create_revenge_token,
    consume_valid_revenge_token,
    can_start_duel_today,
    increment_duel_daily_usage,
    get_lesson_user,
    get_last_ended_lesson_end_ts,
    get_or_create_scheduled_arena_run,
    get_scheduled_arena_run,
    mark_daily_test_notification_sent,
    update_scheduled_arena_run,
    register_arena_run_participant,
    count_arena_run_participants,
    delete_arena_run_questions,
    is_arena_run_participant,
    process_duel_win_streak_bonus,
    process_daily_activity_streak_award,
    was_season_notified,
    mark_season_notified,
    season_leaderboard_top_users,
    ensure_subject_dcoin_schema,
    ensure_dcoin_schema_migrations,
    validate_dcoin_runtime_ready,
    get_vocab_allowed_levels_for_user,
    get_vocab_cooldown_word_ids,
    record_vocab_word_result,
    insert_arena_group_session_answer,
    enqueue_arena_group_teacher_refresh,
    user_is_present_for_group_on_date,
)
from lesson_window import is_group_lesson_window_active
from auth import (
    verify_login,
    activate_user,
    compute_level,
    english_cefr_code_from_score,
    english_level_display_from_score,
    level_display_from_score,
    normalize_level_to_cefr,
    restore_sessions_on_startup,
    cleanup_inactive_accounts,
    process_login_message,
    get_login_state,
    set_login_state,
    clear_login_state,
    login_with_qr_token_for_bot,
    AuthMiddleware,
)
from utils import student_main_keyboard, student_vocab_keyboard, create_dual_choice_keyboard, create_leaderboard_pagination_keyboard, create_language_selection_keyboard_for_self
from i18n import t, detect_lang_from_user, level_ui_label
from vocabulary import search_words, get_words_by_subject_level, get_available_vocabulary_levels
from grammar_content import ALL_GRAMMAR_TOPICS, find_topic_by_id, get_topic, get_topics_by_level
from logging_config import get_logger
from bot_error_notify import notify_admins_unhandled_bot_error, notify_admins_handled_exception
from arena_runner import arena_run_poll_map, run_boss_arena_coordinator, run_daily_arena_coordinator
from diamondvoy_helpers import (
    is_diamondvoy_chat_trigger,
    extract_diamondvoy_query_anywhere,
    diamondvoy_is_subject_related,
    diamondvoy_gemini_answer,
    stream_diamondvoy_text_reply,
    try_diamondvoy_bot_info,
    default_subjects_for_diamondvoy,
    detect_query_language,
    resolve_query_subject,
)
from support_booking_time import SUPPORT_TZ, SUPPORT_LESSON_DURATION_MINUTES, support_make_end_ts, support_make_start_ts

# Setup logger
logger = get_logger(__name__)

VOCAB_GRAMMAR_POLL_SECONDS = 20
DAILY_TEST_POLL_SECONDS = 35
ARENA_GROUP_POLL_SECONDS = 40
DUEL_POLL_SECONDS = 40

bot: Bot | None = None
admin_bot: Bot | None = None
support_bot: Bot | None = None
NOTIFY_SEND_CONCURRENCY = 20
dp = Dispatcher()


async def _decode_qr_text_from_photo_message(message: types.Message) -> str:
    if not message.photo:
        return ""
    if cv2 is None or np is None:
        return ""
    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        if not file_info or not file_info.file_path:
            return ""
        binary = await bot.download_file(file_info.file_path)
        content = binary.getvalue() if hasattr(binary, "getvalue") else b""
        if not content:
            return ""
        frame = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return ""
        detector = cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(frame)
        text = str(data or "").strip()
        if text:
            return text
        ok, decoded_list, _, _ = detector.detectAndDecodeMulti(frame)
        if ok and decoded_list:
            return str(decoded_list[0] or "").strip()
    except Exception:
        return ""
    return ""


def _no_group_contact_payload(user: dict | None) -> dict:
    owner_admin_id = int((user or {}).get("owner_admin_id") or 0)
    owner_admin = get_user_by_id(owner_admin_id) if owner_admin_id > 0 else None
    admin_phone = str((owner_admin or {}).get("phone") or "").strip() or None
    admin_telegram_id = str((owner_admin or {}).get("telegram_id") or "").strip() or None
    admin_chat_url = None
    if admin_telegram_id:
        tg_clean = admin_telegram_id.strip()
        if tg_clean.startswith("@"):
            admin_chat_url = f"https://t.me/{tg_clean.lstrip('@')}"
        elif tg_clean.isdigit():
            admin_chat_url = f"tg://user?id={tg_clean}"
        else:
            admin_chat_url = f"https://t.me/{tg_clean}"
    request_form_path = "/?role=student&section=support"
    return {
        "message": "Siz hali guruhga biriktirilmagansiz",
        "admin_phone": admin_phone,
        "admin_telegram_id": admin_telegram_id,
        "admin_chat_url": admin_chat_url,
        "request_form_path": request_form_path,
    }


def _no_group_contact_keyboard(contact: dict) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    admin_chat_url = str(contact.get("admin_chat_url") or "").strip()
    admin_phone = str(contact.get("admin_phone") or "").strip()
    admin_telegram_id = str(contact.get("admin_telegram_id") or "").strip()
    request_form_path = str(contact.get("request_form_path") or "").strip()

    if admin_chat_url:
        buttons.append([InlineKeyboardButton(text="Admin Chat", url=admin_chat_url)])
    if admin_phone:
        phone_clean = admin_phone.replace(" ", "")
        buttons.append([InlineKeyboardButton(text=f"📞 {admin_phone}", url=f"tel:{phone_clean}")])
    if admin_telegram_id:
        if admin_telegram_id.startswith("@"):
            tg_url = f"https://t.me/{admin_telegram_id.lstrip('@')}"
        elif admin_telegram_id.isdigit():
            tg_url = f"tg://user?id={admin_telegram_id}"
        else:
            tg_url = f"https://t.me/{admin_telegram_id}"
        buttons.append([InlineKeyboardButton(text=f"Telegram: {admin_telegram_id}", url=tg_url)])
    if request_form_path:
        base = (TELEGRAM_MINI_APP_BASE_URL or "").strip()
        if base:
            sep = "&" if "?" in base else "?"
            url = f"{base.rstrip('/')}{sep}{urlencode({'role': 'student', 'section': 'support'})}"
            buttons.append([InlineKeyboardButton(text="Open Request Form", web_app=WebAppInfo(url=url))])
        else:
            buttons.append([InlineKeyboardButton(text="Open Request Form", callback_data="feedback_named")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _send_no_group_block_message(chat_id: int, lang: str, user: dict | None = None) -> None:
    contact = _no_group_contact_payload(user)
    text = contact.get("message") or "Siz hali guruhga biriktirilmagansiz"
    await bot.send_message(chat_id, str(text), reply_markup=_no_group_contact_keyboard(contact))

# Support lesson booking temporary per-chat state is stored in `student_state[chat_id]['data']['support_pending']`.
SUPPORT_DEFAULT_TIMES = ['14:00','14:30','15:00','15:30','16:00','16:30','17:00','17:30','18:00']
SUPPORT_BOOKING_COOLDOWN_HOURS = 6


def _support_allowed_dates(branch_key: str, days_ahead: int = 14) -> list[str]:
    allowed_wd = set(get_lesson_branch_weekdays(str(branch_key)))
    today = dt.now(SUPPORT_TZ).date()
    out: list[str] = []
    for i in range(0, max(1, int(days_ahead))):
        d = today + timedelta(days=i)
        if d.weekday() == 6:  # Sunday closed
            continue
        iso = d.isoformat()
        if is_lesson_holiday(iso):
            continue
        if is_branch_date_closed_for_booking(str(branch_key), iso):
            continue
        wd = d.weekday()
        if wd in allowed_wd:
            out.append(iso)
    return out


def _support_weekday_name(date_iso: str, lang: str) -> str:
    try:
        d = dt.strptime(date_iso, "%Y-%m-%d").date()
        idx = d.weekday()
        if lang == "ru":
            names = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]
        elif lang == "en":
            names = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        else:
            names = ["Dushanba","Seshanba","Chorshanba","Payshanba","Juma","Shanba","Yakshanba"]
        return names[idx]
    except Exception:
        return ""


def _support_fmt_dd_mm_yyyy(date_iso: str) -> str:
    try:
        d = dt.strptime(date_iso, "%Y-%m-%d").date()
        return d.strftime("%d-%m-%Y")
    except Exception:
        return date_iso


def _support_purpose_label(lang: str, purpose: str) -> str:
    key = {
        "speaking": "support_purpose_speaking",
        "grammar": "support_purpose_grammar",
        "writing": "support_purpose_writing",
        "reading": "support_purpose_reading",
        "listening": "support_purpose_listening",
        "all": "support_purpose_all",
    }.get((purpose or "").lower(), "support_purpose_all")
    return t(lang, key)


def _normalize_support_closed_reason(lang: str, reason: str | None) -> str | None:
    raw = (reason or "").strip()
    if not raw:
        return None
    norm = raw.lower().replace("-", "_").replace(" ", "_")
    if norm == "holiday_otmen":
        return t(lang, "support_reason_holiday_otmen")
    return raw


def _support_profile_link_html(user: dict, from_user) -> str:
    fn = html_module.escape((user.get("first_name") or "").strip())
    ln = html_module.escape((user.get("last_name") or "").strip())
    name = (fn + " " + ln).strip() or html_module.escape("Student")
    username = str(user.get("username") or "").strip().lstrip("@")
    if username:
        return f'<a href="https://t.me/{html_module.escape(username)}">{name}</a>'
    uid = int(getattr(from_user, "id", 0) or 0)
    if uid <= 0:
        try:
            uid = int(user.get("telegram_id") or 0)
        except Exception:
            uid = 0
    if uid > 0:
        return f'<a href="tg://user?id={uid}">{name}</a>'
    return name


def _support_booking_notify_admin_ids() -> list[int]:
    """Support lesson booking alerts: same IDs as support admin bot (ALL_ADMIN_IDS)."""
    return list(ALL_ADMIN_IDS) if ALL_ADMIN_IDS else []


async def _support_flow_render(
    text: str,
    reply_markup: InlineKeyboardMarkup,
    *,
    chat_id: int,
    callback_message: Message | None = None,
):
    """Single support booking UI message: edit in place or send fresh."""
    st = get_student_state(chat_id)
    st.setdefault("data", {})
    st["data"].setdefault("support_flow", {})
    flow = st["data"]["support_flow"]
    mid = flow.get("message_id")
    if callback_message is not None:
        mid = callback_message.message_id
    if mid:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=mid,
                text=text,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            flow["message_id"] = mid
            return mid
        except TelegramBadRequest:
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass
            flow["message_id"] = None
    m = await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
    flow["message_id"] = m.message_id
    return m.message_id


def _support_clear_flow_message_id(chat_id: int) -> None:
    st = get_student_state(chat_id)
    st.setdefault("data", {})
    st["data"].setdefault("support_flow", {})
    st["data"]["support_flow"]["message_id"] = None


def _support_end_ts_local_date_time(end_ts_iso: str) -> tuple[str, str]:
    """Tashkent (date str, time HH:MM) from UTC ISO end_ts."""
    try:
        s = (end_ts_iso or "").strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = dt.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        loc = d.astimezone(SUPPORT_TZ)
        return loc.strftime("%d-%m-%Y"), loc.strftime("%H:%M")
    except Exception:
        return end_ts_iso, ""


def _support_unlock_fmt(unlock_iso: str) -> str:
    try:
        s = (unlock_iso or "").strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = dt.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        loc = d.astimezone(SUPPORT_TZ)
        return loc.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return unlock_iso or ""


def _support_fmt_hhmm(time_raw: str | None, start_ts_iso: str | None = None) -> str:
    """Best-effort normalize to HH:MM for booking displays."""
    s = str(time_raw or "").strip()
    if s:
        if ":" in s:
            try:
                hh, mm = s.split(":", 1)
                return f"{int(hh):02d}:{int(mm):02d}"
            except Exception:
                pass
        if s.isdigit():
            try:
                return f"{int(s):02d}:00"
            except Exception:
                pass
    try:
        d = _support_dt_from_start_ts_iso(start_ts_iso)
        if d is not None:
            return d.astimezone(SUPPORT_TZ).strftime("%H:%M")
    except Exception:
        pass
    return s


def _support_fmt_long_date(date_iso: str, lang: str) -> str:
    try:
        d = dt.strptime(date_iso, "%Y-%m-%d").date()
        if lang == "ru":
            months = [
                "января", "февраля", "марта", "апреля", "мая", "июня",
                "июля", "августа", "сентября", "октября", "ноября", "декабря",
            ]
            return f"{d.day:02d} {months[d.month - 1]} {d.year}"
        if lang == "en":
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            ]
            return f"{months[d.month - 1]} {d.day:02d} {d.year}"
        months = [
            "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
            "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
        ]
        return f"{d.day:02d} {months[d.month - 1]} {d.year}"
    except Exception:
        return date_iso or ""


def _support_dt_from_start_ts_iso(start_ts_iso: str | None):
    if not start_ts_iso:
        return None
    try:
        s = start_ts_iso.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = dt.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None


def _support_encode_confirm_token(branch: str, date_iso: str, tm: str, purpose: str) -> str:
    # Keep callback_data below Telegram 64-byte limit.
    # Format: branch|date|time(with dots)|purpose
    b = str(branch or "").strip()
    d = str(date_iso or "").strip()
    t = str(tm or "").strip().replace(":", ".")
    p = str(purpose or "").strip()
    return f"{b}|{d}|{t}|{p}"


def _support_decode_confirm_token(token: str) -> tuple[str | None, str | None, str | None, str | None]:
    try:
        tkn = str(token or "").strip()
        if not tkn or "|" not in tkn:
            return None, None, None, None
        b, d, t, p = tkn.split("|", 3)
        t = t.replace(".", ":")
        return (b or None, d or None, t or None, p or None)
    except Exception:
        return None, None, None, None


@dp.errors()
async def global_error_handler(event: ErrorEvent):
    """Eski callback xatolarini yutish; qolganlarini adminlarga xabar qilish."""
    exc = event.exception
    if isinstance(exc, (TelegramNetworkError, TelegramServerError)):
        logger.warning("Suppressed transient Telegram API/network error: %s", exc)
        return True
    if isinstance(exc, TelegramBadRequest):
        msg = str(exc).lower()
        if "query is too old" in msg or "query id is invalid" in msg:
            logger.warning("Suppressed stale callback error: %s", exc)
            return True
    try:
        await notify_admins_unhandled_bot_error(
            bot_label="Student bot",
            event=event,
            admin_bot_instance=admin_bot,
        )
    except Exception:
        logger.exception("Adminlarga student bot xato xabari yuborilmadi")
    return False

@dp.my_chat_member()
async def handle_my_chat_member_status(update: types.ChatMemberUpdated):
    """Track when student bot is added to or removed from group chats."""
    try:
        chat = update.chat
        if chat.type in ("group", "supergroup") or chat.id < 0:
            new_status = update.new_chat_member.status
            if new_status in ("member", "administrator"):
                upsert_telegram_group_chat(chat.id, title=chat.title, chat_type=chat.type, is_active=1)
                logger.info(f"Student bot added to group chat {chat.id} ({chat.title})")
            elif new_status in ("left", "kicked", "banned"):
                set_telegram_group_chat_active(chat.id, is_active=0)
                logger.info(f"Student bot removed from group chat {chat.id} ({chat.title})")
    except Exception as e:
        logger.exception(f"Error handling my_chat_member: {e}")


# Setup authentication middleware
auth_middleware = AuthMiddleware(bot_type='student', expected_login_type=2)
dp.message.middleware(auth_middleware)
dp.callback_query.middleware(auth_middleware)

placement_state = {}
student_state = {}
vocab_state = {}
vocab_poll_map = {}  # poll_id -> metadata for vocab quiz
grammar_poll_map = {}  # poll_id -> metadata for grammar quiz
daily_poll_map = {}  # poll_id -> metadata for daily test quiz
arena_group_poll_map = {}  # poll_id -> metadata for group arena quiz

arena_runtime_started = False
arena_daily_last_slot: dict[tuple[str, str], str] = {}
arena_boss_last_slot: dict[tuple[str, str], str] = {}
_FLOW_ERROR_NOTIFY_CACHE: dict[str, float] = {}
_FLOW_ERROR_NOTIFY_COOLDOWN_SEC = 120


def _to_base36(n: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    if n <= 0:
        return "0"
    out = []
    x = int(n)
    while x:
        x, r = divmod(x, 36)
        out.append(chars[r])
    return "".join(reversed(out))


_GRAMMAR_TOPIC_TOKEN_BY_ID: dict[str, str] = {}
_GRAMMAR_TOPIC_ID_BY_TOKEN: dict[str, str] = {}
for _idx, _tp in enumerate(ALL_GRAMMAR_TOPICS):
    _tok = _to_base36(_idx)
    _GRAMMAR_TOPIC_TOKEN_BY_ID[_tp.topic_id] = _tok
    _GRAMMAR_TOPIC_ID_BY_TOKEN[_tok] = _tp.topic_id


def _grammar_topic_token(topic_id: str) -> str:
    return _GRAMMAR_TOPIC_TOKEN_BY_ID.get(str(topic_id or "").strip(), str(topic_id or "").strip())


def _grammar_topic_id_from_token(token_or_id: str) -> str:
    raw = str(token_or_id or "").strip()
    return _GRAMMAR_TOPIC_ID_BY_TOKEN.get(raw, raw)


def _today_tashkent() -> str:
    """Return today's date in Tashkent timezone as YYYY-MM-DD."""
    return dt.now(pytz.timezone("Asia/Tashkent")).date().isoformat()


def _flow_ctx(
    *,
    callback: CallbackQuery | None = None,
    user: dict | None = None,
    flow: str = "",
    extra: dict | None = None,
) -> dict:
    ctx = {
        "flow": flow,
        "chat_id": (callback.message.chat.id if callback and callback.message else None),
        "callback_data": (callback.data if callback else None),
        "telegram_id": (str(callback.from_user.id) if callback and callback.from_user else None),
        "username": (callback.from_user.username if callback and callback.from_user else None),
        "user_id": (user or {}).get("id"),
        "login_id": (user or {}).get("login_id"),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _flow_log(severity: str, message: str, **ctx):
    if severity == "warning":
        logger.warning("%s | ctx=%s", message, ctx)
    elif severity == "error":
        logger.error("%s | ctx=%s", message, ctx)
    else:
        logger.info("%s | ctx=%s", message, ctx)


async def _notify_flow_exception(
    *,
    flow: str,
    callback: CallbackQuery | None,
    user: dict | None,
    exc: Exception,
    context: dict | None = None,
):
    ctx = _flow_ctx(callback=callback, user=user, flow=flow, extra=context or {})
    key = f"{flow}:{ctx.get('chat_id')}:{type(exc).__name__}:{str(exc)[:120]}"
    now_ts = time.time()
    prev = _FLOW_ERROR_NOTIFY_CACHE.get(key, 0.0)
    if now_ts - prev < _FLOW_ERROR_NOTIFY_COOLDOWN_SEC:
        return
    _FLOW_ERROR_NOTIFY_CACHE[key] = now_ts
    try:
        await notify_admins_handled_exception(
            bot_label="Student bot",
            flow=flow,
            exception=exc,
            telegram_id=ctx.get("telegram_id"),
            username=ctx.get("username"),
            context=ctx,
            admin_bot_instance=admin_bot,
        )
    except Exception:
        logger.exception("Handled flow exception notify failed | flow=%s", flow)


def _get_student_subject(user: dict) -> str:
    """DB-first primary subject for D'coin and balances: user_subjects[0], else user.subject, default English."""
    subs = get_user_subjects(user["id"]) if user and user.get("id") is not None else []
    if subs:
        return str(subs[0]).strip().title()
    raw = (user or {}).get("subject") or "English"
    return str(raw).strip().title()


def _resolve_arena_subject_for_user(user: dict) -> str:
    """Arena fee/reward always uses arena subject; fallback is deterministic."""
    subjects = get_user_subjects(user["id"]) or []
    if subjects:
        return str(subjects[0]).strip().title()
    return ((_get_selected_subject_for_user(user) or "English")).strip().title()


def _now_tashkent() -> dt:
    return dt.now(SUPPORT_TZ)


def _notify_students_for_subject(subject: str, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Best-effort broadcast to active students for one subject (same text for all)."""
    _notify_students_for_subject_mapped(subject, lambda _u: text, lambda _u: reply_markup)


def _notify_students_for_subject_mapped(
    subject: str,
    text_for_user: "callable[[dict], str]",
    reply_markup_for_user: "callable[[dict], InlineKeyboardMarkup | None] | None" = None,
) -> None:
    """Broadcast; message text and keyboard can depend on each user's language."""
    if bot is None:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        join_query = """
            SELECT DISTINCT u.telegram_id, u.language, u.first_name
            FROM users u
            LEFT JOIN user_subject us ON us.user_id = u.id
            WHERE u.login_type IN (1,2) AND u.access_enabled=1
              AND u.telegram_id IS NOT NULL
              AND (
                LOWER(COALESCE(u.subject,'')) = LOWER(?)
                OR LOWER(COALESCE(us.subject,'')) = LOWER(?)
              )
            """
        params = (subject, subject)
        used_fallback = False
        try:
            cur.execute(join_query, params)
        except Exception as e:
            # If user_subject table doesn't exist yet, scheduled notifier should not crash.
            msg = str(e).lower()
            if "relation" in msg and "user_subject" in msg and "does not exist" in msg:
                logger.warning("user_subject table missing; creating it then retrying. err=%s", e)
                try:
                    from db import ensure_user_subject_schema

                    ensure_user_subject_schema()
                    cur.execute(join_query, params)
                except Exception as e2:
                    logger.exception(
                        "Retry after ensure_user_subject_schema failed; using fallback users.subject match. err=%s",
                        e2,
                    )
                    used_fallback = True
            else:
                raise

        if not used_fallback:
            rows = [dict(r) for r in cur.fetchall() if r.get("telegram_id")]
        else:
            fallback_query = """
                SELECT DISTINCT u.telegram_id, u.language, u.first_name
                FROM users u
                WHERE u.login_type IN (1,2) AND u.access_enabled=1
                  AND u.telegram_id IS NOT NULL
                  AND EXISTS (
                    SELECT 1
                    FROM unnest(string_to_array(COALESCE(u.subject,''), ',')) AS s
                    WHERE trim(s) <> '' AND LOWER(trim(s)) = LOWER(?)
                  )
                """
            cur.execute(fallback_query, (subject,))
            rows = [dict(r) for r in cur.fetchall() if r.get("telegram_id")]
    finally:
        conn.close()

    async def _run():
        sem = asyncio.Semaphore(NOTIFY_SEND_CONCURRENCY)

        async def _send_one(r: dict):
            try:
                async with sem:
                    tg = int(r["telegram_id"])
                    txt = text_for_user(r)
                    rm = None
                    if reply_markup_for_user:
                        rm = reply_markup_for_user(r)
                    await bot.send_message(tg, txt, reply_markup=rm)
            except Exception:
                pass
        await asyncio.gather(*[_send_one(r) for r in rows], return_exceptions=True)

    asyncio.create_task(_run())


def _is_simple_arena_join_callback(data: str) -> bool:
    if not data:
        return False
    if data.startswith("arena_enter_duel:"):
        return True
    if data.startswith("arena_enter_duel_"):
        return True
    if data in {
        "arena_join_group",
        "arena_join_daily",
        "arena_join_boss",
    }:
        return True
    return data.startswith("arena_join_daily:") or data.startswith("arena_join_boss:")


def _vocab_quiz_type_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'vocab_quiz_type_multiple_choice_btn'), callback_data="vocab_quiz_type_multiple_choice")],
        [InlineKeyboardButton(text=t(lang, 'vocab_quiz_type_gap_btn'), callback_data="vocab_quiz_type_gap_filling")],
        [InlineKeyboardButton(text=t(lang, 'vocab_quiz_type_definition_btn'), callback_data="vocab_quiz_type_definition")],
    ])


def _get_selected_subject_for_user(user: dict) -> str:
    """Get currently selected subject for this student session."""
    key = f"{user['id']}_current_subject"
    selected = placement_state.get(key)
    if selected:
        return selected
    subjects = get_user_subjects(user['id'])
    return (subjects[0] if subjects else (user.get('subject') or 'English'))


def _subject_button_text(lang: str, subject: str) -> str:
    subj = (subject or "").strip().title()
    if subj == "English":
        return f"🇬🇧 {t(lang, 'subject_english_btn')}"
    if subj == "Russian":
        return f"🇷🇺 {t(lang, 'subject_russian_btn')}"
    return f"📚 {subj}"


def get_student_state(chat_id: int):
    return student_state.setdefault(chat_id, {'step': None, 'data': {}})

def reset_student_state(chat_id: int):
    student_state.pop(chat_id, None)


def get_placement_state(user_id):
    key = str(user_id)
    return placement_state.setdefault(key, {'active': False, 'poll_map': {}})


def reset_placement_state(user_id):
    placement_state.pop(str(user_id), None)


def _student_miniapp_url(section: str = "home", extra: dict | None = None) -> str | None:
    base = (TELEGRAM_MINI_APP_BASE_URL or "").strip()
    if not base:
        base = "https://diamond-education.uz"
    if base and not base.lower().startswith(("http://", "https://")):
        base = f"https://{base.lstrip('/')}"
    if not base:
        return None
    params = {"role": "student", "section": section}
    if extra:
        params.update({k: v for k, v in extra.items() if v is not None})
    sep = "&" if "?" in base else "?"
    return f"{base.rstrip('/')}{sep}{urlencode(params)}"


def _arena_open_webapp_button(
    lang: str,
    section: str = "arena",
    *,
    extra: dict | None = None,
    text: str = "📱 Open Arena",
) -> InlineKeyboardButton | None:
    url = _student_miniapp_url(section, extra=extra)
    if not url:
        return None
    return InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))


def _miniapp_open_keyboard(label: str, section: str, *, extra: dict | None = None) -> InlineKeyboardMarkup | None:
    url = _student_miniapp_url(section, extra=extra)
    if not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))]]
    )


async def _send_test_redirect(
    chat_id: int,
    lang: str,
    *,
    section: str,
    title: str,
    label: str = "📱 Mini Appda ochish",
    extra: dict | None = None,
) -> bool:
    kb = _miniapp_open_keyboard(label, section, extra=extra)
    if not kb:
        await bot.send_message(chat_id, t(lang, "error_with_reason", error="MiniApp URL is not configured"))
        return False
    await bot.send_message(chat_id, title, reply_markup=kb)
    return True


def _placement_launch_keyboard(user: dict, lang: str) -> InlineKeyboardMarkup | None:
    placement_required = bool(int(user.get("placement_required") or 0)) or int(user.get("login_type") or 0) == 1
    label = "🎯 Daraja testini boshlash" if placement_required else "📱 MiniAppga kirish"
    url = _student_miniapp_url("home")
    if not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, web_app=WebAppInfo(url=url))]]
    )


def get_vocab_state(chat_id: int):
    return vocab_state.setdefault(chat_id, {'step': None, 'data': {}})


def _resolve_vocab_subject(user: dict, explicit_subject: str | None = None) -> str:
    if explicit_subject and explicit_subject.strip():
        return explicit_subject.strip().title()
    subjects = get_user_subjects(user['id']) if user else []
    if subjects:
        return subjects[0]
    raw = (user.get('subject') or '').strip() if user else ''
    if ',' in raw:
        return raw.split(',', 1)[0].strip().title()
    return raw.title() if raw else 'English'


def _format_vocab_result_line(idx: int, item: dict, subject: str) -> str:
    word = html_module.escape(str(item.get('word') or '-'))
    level = html_module.escape(str(item.get('level') or '').strip().upper())
    translation_uz = (item.get('translation_uz') or '').strip()
    translation_ru = (item.get('translation_ru') or '').strip()
    definition = (item.get('definition') or '').strip()
    example = (item.get('example') or '').strip()
    lang_field = (item.get('language') or '').strip().lower()
    subj = (subject or '').strip().lower()
    is_russian_word = lang_field == 'russian' or subj == 'russian'

    if len(example) > 180:
        example = example[:177].rstrip() + "..."

    title = f"<b>{idx}. {word}</b>"
    if level:
        title += f" <code>{level}</code>"
    lines = [title]
    if translation_uz:
        lines.append(f"🇺🇿 {html_module.escape(translation_uz)}")
    if translation_ru and not is_russian_word:
        lines.append(f"🇷🇺 {html_module.escape(translation_ru)}")
    if definition:
        lines.append(f"📖 {html_module.escape(definition)}")
    if example:
        lines.append(f"💬 {html_module.escape(example)}")
    return "\n".join(lines)


@dp.message(Command('vocab'))
async def cmd_vocab(message: types.Message):
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    if not user or not is_access_active(user):
        await message.answer(t(lang, 'please_send_start'))
        return
    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        message.chat.id,
        lang,
        section="vocabulary-process",
        title="Vocabulary testlarini Mini App orqali ishlang.",
        label="📱 Vocabulary Testni Ochish",
        extra=extra,
    )


@dp.message(Command('vocab_search'))
async def cmd_vocab_search(message: types.Message):
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    if not user or not is_access_active(user):
        await message.answer(t(lang, 'please_send_start'))
        return
    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        message.chat.id,
        lang,
        section="vocabulary-process",
        title="Vocabulary bo'limi Mini App ichida ochiladi.",
        label="📱 Vocabulary Testni Ochish",
        extra=extra,
    )


@dp.message(Command('vocab_pref'))
async def cmd_vocab_pref(message: types.Message):
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    if not user or not is_access_active(user):
        await message.answer(t(lang, 'please_send_start'))
        return
    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        message.chat.id,
        lang,
        section="vocabulary-process",
        title="Vocabulary sozlamalari va testlar Mini App ichida.",
        label="📱 Vocabulary Testni Ochish",
        extra=extra,
    )


@dp.message(Command('vocab_quiz'))
async def cmd_vocab_quiz(message: types.Message):
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    if not user or not is_access_active(user):
        await message.answer(t(lang, 'please_send_start'))
        return
    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        message.chat.id,
        lang,
        section="vocabulary-process",
        title="Vocabulary testlari Mini App ichida ishlaydi.",
        label="📱 Vocabulary Testni Ochish",
        extra=extra,
    )


@dp.callback_query(lambda c: c.data.startswith("vocab_pref_"))
async def handle_vocab_pref_inline(callback: CallbackQuery):
    code = callback.data.split("_")[-1]
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    if code not in ('uz', 'ru'):
        await callback.answer()
        return
    from vocabulary import save_student_preference
    save_student_preference(user['id'], code)
    await callback.answer(t(lang, 'saved'))
    vs = get_vocab_state(callback.message.chat.id)
    subj = (vs.get('data') or {}).get('subject_override') or (vs.get('data') or {}).get('quiz_subject')
    title_extra = t(lang, "vocab_quiz_subject_prefix", subject=html_module.escape(subj)) if subj else ""
    kb = _vocab_quiz_type_keyboard(lang)
    extra = t(lang, 'vocab_choose_type_explain')
    await callback.message.answer(title_extra + t(lang, 'vocab_choose_type') + "\n\n" + extra, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(lambda c: c.data.startswith("vocab_quiz_type_"))
async def handle_vocab_quiz_type(callback: CallbackQuery):
    qtype = callback.data.split("vocab_quiz_type_")[-1]
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    # Backward compatibility for older buttons
    if qtype == 'translation':
        qtype = 'multiple_choice'
    if qtype not in ('multiple_choice', 'gap_filling', 'definition'):
        await callback.answer()
        return
    state = get_vocab_state(callback.message.chat.id)
    prev = dict(state.get('data') or {})
    prev['qtype'] = qtype
    state['data'] = prev
    state['step'] = 'quiz_choose_count'
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="5", callback_data="vocab_quiz_cnt_5"),
         InlineKeyboardButton(text="10", callback_data="vocab_quiz_cnt_10"),
         InlineKeyboardButton(text="15", callback_data="vocab_quiz_cnt_15")],
        [InlineKeyboardButton(text="20", callback_data="vocab_quiz_cnt_20"),
         InlineKeyboardButton(text="25", callback_data="vocab_quiz_cnt_25"),
         InlineKeyboardButton(text="30", callback_data="vocab_quiz_cnt_30")],
    ])
    await callback.answer()
    await callback.message.answer(t(lang, 'vocab_choose_count'), reply_markup=kb)


async def _countdown_message(chat_id: int, base_text: str, seconds: int):
    # Backwards-compat helper: send + edit countdown
    lang = detect_lang_from_user(get_user_by_telegram(str(chat_id)) or {"language": "uz"})
    msg = await bot.send_message(chat_id, f"{base_text}\n{t(lang, 'student_quiz_countdown_suffix', seconds=seconds)}")
    start = time.monotonic()
    for s in [15, 10, 5, 4, 3, 2, 1]:
        target = seconds - s
        now = time.monotonic() - start
        if target > now:
            await asyncio.sleep(target - now)
        try:
            await bot.edit_message_text(
                f"{base_text}\n{t(lang, 'student_quiz_countdown_suffix', seconds=s)}",
                chat_id=chat_id,
                message_id=msg.message_id,
            )
        except Exception:
            pass
    return msg


async def _edit_countdown_steps(
    chat_id: int,
    message_id: int,
    base_text: str,
    total_seconds: int = 20,
    lang: str = "uz",
):
    """Edit countdown message at specific remaining seconds."""
    # Dynamic schedule for both 20s (vocab) and 30s (grammar)
    candidates = [total_seconds, 20, 15, 10, 5, 4, 3, 2, 1]
    schedule = []
    for s in candidates:
        if 1 <= s <= total_seconds and s not in schedule:
            schedule.append(s)
    start = time.monotonic()
    for s in schedule:
        target = total_seconds - s
        now = time.monotonic() - start
        if target > now:
            await asyncio.sleep(target - now)
        try:
            remaining = total_seconds - int((time.monotonic() - start))
            await bot.edit_message_text(
                f"{base_text}\n{t(lang, 'student_quiz_countdown_suffix', seconds=remaining)}",
                chat_id=chat_id,
                message_id=message_id,
            )
        except Exception:
            pass


def _poll_question_plain(prompt: str, idx: int, total: int) -> str:
    raw = f"{idx}/{total} — {prompt or ''}"
    plain = re.sub(r'<[^>]+>', '', raw)
    plain = plain.replace('\n', ' ').strip()
    if len(plain) > 280:
        return plain[:279] + '…'
    return plain


async def _run_vocab_quiz(chat_id: int, user: dict, qtype: str, cnt: int):
    from vocabulary import generate_quiz, get_student_preference
    pref = get_student_preference(user['id']) or 'uz'
    lang = detect_lang_from_user(user)
    vs = get_vocab_state(chat_id)
    subject_override = (vs.get('data') or {}).get('subject_override') or (vs.get('data') or {}).get('quiz_subject')
    quiz_subject = _resolve_vocab_subject(user, subject_override)
    
    # New policy:
    # - A1 -> only A1
    # - A2 -> only A2
    # - others -> A2/B1/B2/C1
    available_levels = get_vocab_allowed_levels_for_user(user.get('level'))
    initial_cooldown_ids = get_vocab_cooldown_word_ids(user['id'], qtype, now_ts=dt.utcnow())

    def build_questions():
        qs = []
        excluded_word_ids = set(initial_cooldown_ids)
        for lvl in available_levels:
            need = cnt - len(qs)
            if need <= 0:
                break
            level_questions = generate_quiz(
                user['id'],
                quiz_subject,
                lvl,
                need,
                qtype,
                pref,
                exclude_word_ids=excluded_word_ids,
            )
            qs.extend(level_questions)
            for q in level_questions:
                wid = int(q.get("word_id") or 0)
                if wid > 0:
                    excluded_word_ids.add(wid)
            if len(qs) >= cnt:
                break
        return qs[:cnt]

    questions = build_questions()

    if not questions:
        await bot.send_message(
            chat_id,
            t(lang, 'vocab_no_questions')
            + "\n\n"
            + t(lang, 'vocab_no_questions_with_subject', subject=html_module.escape(quiz_subject)),
        )
        return

    correct_count = 0
    wrong_count = 0
    skipped_count = 0
    sec = VOCAB_GRAMMAR_POLL_SECONDS

    await bot.send_message(
        chat_id,
        t(lang, 'vocab_quiz_intro', sec=sec),
        parse_mode="HTML",
    )
    
    for idx, q in enumerate(questions, start=1):
        opts = q.get('options') or []
        if len(opts) != 4:
            skipped_count += 1
            continue
        correct = q.get('correct')
        try:
            correct_idx = opts.index(correct)
        except Exception:
            correct_idx = 0
        question_text = _poll_question_plain(str(q.get('prompt') or ''), idx, len(questions))

        countdown_msg = await bot.send_message(
            chat_id,
            f"{question_text}\n{t(lang, 'student_quiz_countdown_suffix', seconds=sec)}",
        )

        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=question_text,
            options=[str(o)[:100] for o in opts],
            type='quiz',
            correct_option_id=correct_idx,
            is_anonymous=False,
            open_period=sec,
        )
        poll_id = poll_msg.poll.id
        ev = asyncio.Event()
        vocab_poll_map[poll_id] = {
            'event': ev,
            'chat_id': chat_id,
            'user_id': user['id'],
            'correct': correct_idx,
            'chosen': None,
            'poll_message_id': poll_msg.message_id,
            'countdown_message_id': countdown_msg.message_id,
            'word_id': int(q.get('word_id') or 0),
            'question_type': str(q.get('question_type') or qtype),
        }

        countdown_task = asyncio.create_task(_edit_countdown_steps(chat_id, countdown_msg.message_id, question_text, sec, lang=lang))

        try:
            await asyncio.wait_for(ev.wait(), timeout=sec + 1.0)
        except Exception:
            pass

        meta = vocab_poll_map.pop(poll_id, None)
        chosen = meta.get('chosen') if meta else None
        word_id = int((meta or {}).get('word_id') or 0)
        mastery_qtype = str((meta or {}).get('question_type') or qtype)
        is_correct = (chosen is not None and chosen == correct_idx)
        if chosen is None:
            skipped_count += 1
        elif chosen == correct_idx:
            correct_count += 1
        else:
            wrong_count += 1

        if word_id > 0:
            try:
                record_vocab_word_result(
                    user_id=int(user['id']),
                    word_id=word_id,
                    question_type=mastery_qtype,
                    is_correct=is_correct,
                    answered_at=dt.utcnow(),
                )
            except Exception:
                logger.exception(
                    "Failed to record vocab mastery user=%s word=%s qtype=%s",
                    user['id'],
                    word_id,
                    mastery_qtype,
                )

        try:
            countdown_task.cancel()
        except Exception:
            pass

        try:
            await bot.delete_message(chat_id, poll_msg.message_id)
        except Exception:
            pass
        try:
            await bot.delete_message(chat_id, countdown_msg.message_id)
        except Exception:
            pass

    total = correct_count + wrong_count + skipped_count
    
    dcoin_reward = correct_count * 1.0
    dcoin_penalty_skipped = skipped_count * 0.5
    dcoin_penalty_wrong = wrong_count * 0.5
    net_dcoin = dcoin_reward - dcoin_penalty_skipped - dcoin_penalty_wrong
    
    if net_dcoin != 0:
        add_dpoints(
            user['id'],
            net_dcoin,
            quiz_subject,
            change_type="vocab_test_reward" if net_dcoin > 0 else "vocab_test_penalty",
        )
    
    add_test_history(user['id'], 'vocabulary', None, correct_count, wrong_count, skipped_count)
    
    result_lines = [
        t(lang, 'vocab_quiz_results_title'),
        "",
        t(lang, 'quiz_total_questions', total=total),
        t(lang, 'quiz_correct_count', count=correct_count),
        t(lang, 'quiz_wrong_count', count=wrong_count),
        t(lang, 'quiz_skipped_count', count=skipped_count),
        "",
        t(lang, 'quiz_dcoin_title'),
        t(lang, "quiz_dcoin_reward_line", count=correct_count, mult="1", amount=f"{dcoin_reward:.1f}"),
    ]
    
    if skipped_count > 0:
        result_lines.append(
            t(
                lang,
                "quiz_dcoin_penalty_skipped_line",
                count=skipped_count,
                mult="0.5",
                amount=f"{dcoin_penalty_skipped:.1f}",
                label=t(lang, "daily_test_results_skipped_label"),
            )
        )
    
    if wrong_count > 0:
        result_lines.append(
            t(
                lang,
                "quiz_dcoin_penalty_wrong_line",
                count=wrong_count,
                mult="0.5",
                amount=f"{dcoin_penalty_wrong:.1f}",
                label=t(lang, "daily_test_results_wrong_label"),
            )
        )
    
    result_lines.append(t(lang, 'quiz_dcoin_total', total=f"{net_dcoin:+.1f}"))
    
    current_balance = get_dcoins(user['id'], quiz_subject)
    result_lines.append(t(lang, 'quiz_dcoin_balance', balance=f"{current_balance:.1f}"))
    
    vs = get_vocab_state(chat_id)
    if vs.get('data'):
        vs['data'].pop('subject_override', None)
        vs['data'].pop('quiz_subject', None)
    
    await bot.send_message(chat_id, "\n".join(result_lines), parse_mode="HTML")


async def show_grammar_levels(chat_id: int, user: dict):
    lang = detect_lang_from_user(user)
    selected_subject = (_get_selected_subject_for_user(user) or "").strip()
    if selected_subject.lower() not in ("english", "russian"):
        await bot.send_message(chat_id, t(lang, 'no_grammar_topics'))
        return
    subj_title = selected_subject.strip().title()
    if subj_title == "English":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=level_ui_label(lang, subject=subj_title, code="A1"),
                        callback_data="gr_lvl_A1",
                    ),
                    InlineKeyboardButton(
                        text=level_ui_label(lang, subject=subj_title, code="A2"),
                        callback_data="gr_lvl_A2",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=t(lang, "grammar_level_btn_b1_pre"),
                        callback_data="gr_lvl_B1",
                    ),
                    InlineKeyboardButton(
                        text=level_ui_label(lang, subject=subj_title, code="B2"),
                        callback_data="gr_lvl_B2",
                    ),
                    InlineKeyboardButton(
                        text=level_ui_label(lang, subject=subj_title, code="C1"),
                        callback_data="gr_lvl_C1",
                    ),
                ],
            ]
        )
    else:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "level_ru_tier_beginner"),
                        callback_data="gr_lvl_A1",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "level_ru_tier_elementary"),
                        callback_data="gr_lvl_A2",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=t(lang, "level_ru_tier_basic"),
                        callback_data="gr_lvl_B1",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "level_ru_tier_upper_mid"),
                        callback_data="gr_lvl_B2",
                    ),
                ],
            ]
        )
    await bot.send_message(
        chat_id,
        t(lang, 'grammar_choose_level_title'),
        reply_markup=kb,
        parse_mode="HTML",
    )


GRAMMAR_TOPICS_PER_PAGE = 10


async def _render_topics(chat_id: int, user: dict, level: str, page: int = 0):
    lang = detect_lang_from_user(user)
    selected_subject = _get_selected_subject_for_user(user)
    topics = get_topics_by_level(level, subject=selected_subject)
    if not topics:
        await bot.send_message(chat_id, t(lang, 'grammar_topics_not_available'))
        return

    per_page = GRAMMAR_TOPICS_PER_PAGE
    total_pages = max(1, (len(topics) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    chunk = topics[start : start + per_page]

    st = get_student_state(chat_id)
    st.setdefault('data', {})['grammar_pages'] = st.get('data', {}).get('grammar_pages') or {}
    st['data']['grammar_pages'][level.upper()] = page

    subj_title = (selected_subject or "English").strip().title()
    level_heading = level_ui_label(lang, subject=subj_title, code=level)
    lines = [
        t(lang, 'grammar_topics_header', level=level_heading),
        t(lang, 'grammar_topics_page_info', page=page + 1, total_pages=total_pages, total_topics=len(topics)),
        "",
    ]
    keyboard_rows = []
    num_row = []
    for i, tp in enumerate(chunk):
        global_idx = start + i + 1
        lines.append(f"<b>{global_idx}.</b> {tp.title}")
        topic_token = _grammar_topic_token(tp.topic_id)
        num_row.append(
            InlineKeyboardButton(
                text=str(global_idx),
                callback_data=f"gr_topic_pick:{level}:{topic_token}",
            )
        )
        if len(num_row) == 4:
            keyboard_rows.append(num_row)
            num_row = []
    if num_row:
        keyboard_rows.append(num_row)

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text=t(lang, 'btn_prev'), callback_data=f"gr_topic_page:{level}:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text=t(lang, 'btn_next_arrow'), callback_data=f"gr_topic_page:{level}:{page + 1}"))
    if nav_row:
        keyboard_rows.append(nav_row)

    keyboard_rows.append(
        [InlineKeyboardButton(text=t(lang, 'grammar_back_to_levels'), callback_data="menu_grammar")]
    )

    await bot.send_message(
        chat_id,
        "\n".join(lines) + "\n\n" + t(lang, 'grammar_topics_pick_hint'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows),
        parse_mode="HTML",
    )


async def _show_topic(chat_id: int, user: dict, level: str, topic_id: str):
    lang = detect_lang_from_user(user)
    selected_subject = _get_selected_subject_for_user(user)
    topic = get_topic(level, topic_id, subject=selected_subject)
    if not topic:
        await bot.send_message(chat_id, t(lang, 'grammar_topic_not_found'))
        return
    
    attempts = get_grammar_attempts(user['id'], topic.topic_id)
    left = max(0, 1 - attempts)
    
    # Create topic display
    lines = [t(lang, 'grammar_topic_title_html', title=html_module.escape(topic.title or '')), ""]
    lines.append(t(lang, 'grammar_rule_label'))
    lines.append(topic.rule)
    lines.append("")
    
    if left > 0:
        lines.append(t(lang, 'grammar_attempts_left_line', left=left))
    else:
        lines.append(t(lang, 'grammar_attempts_exhausted_line'))
    
    # Create keyboard
    st = get_student_state(chat_id)
    gpages = (st.get('data') or {}).get('grammar_pages') or {}
    back_page = int(gpages.get(level.upper(), 0))
    topic_token = _grammar_topic_token(topic.topic_id)

    if left > 0:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'grammar_start_test_with_left', left=left), callback_data=f"gr_start:{level}:{topic_token}")],
            [InlineKeyboardButton(text=t(lang, 'grammar_back_to_topics'), callback_data=f"gr_topic_page:{level}:{back_page}")],
        ])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'grammar_back_to_topics'), callback_data=f"gr_topic_page:{level}:{back_page}")],
        ])
    
    await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb, parse_mode="HTML")


async def _run_grammar_quiz(chat_id: int, user: dict, level: str, topic_id: str):
    lang = detect_lang_from_user(user)
    selected_subject = _get_selected_subject_for_user(user)
    topic = get_topic(level, topic_id, subject=selected_subject)
    if not topic:
        await bot.send_message(chat_id, t(lang, 'grammar_topic_not_found'))
        return
    
    attempts = get_grammar_attempts(user['id'], topic.topic_id)
    if attempts >= 1:
        await bot.send_message(chat_id, t(lang, 'grammar_attempts_max_reached'))
        return
    
    # Consume an attempt at start
    increment_grammar_attempt(user['id'], topic.topic_id)

    total_seconds = VOCAB_GRAMMAR_POLL_SECONDS
    correct_count = 0
    wrong_count = 0
    skipped_count = 0

    await bot.send_message(
        chat_id,
        t(lang, 'grammar_quiz_intro', title=topic.title, sec=total_seconds),
        parse_mode="HTML",
    )

    for idx, q in enumerate(topic.questions, start=1):
        q_plain = _poll_question_plain(q.prompt, idx, len(topic.questions))
        countdown_msg = await bot.send_message(
            chat_id,
            f"{q_plain}\n{t(lang, 'student_quiz_countdown_suffix', seconds=total_seconds)}",
        )
        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=q_plain,
            options=[str(o)[:100] for o in q.options],
            type='quiz',
            correct_option_id=q.correct_index,
            is_anonymous=False,
            open_period=total_seconds,
        )
        poll_id = poll_msg.poll.id
        ev = asyncio.Event()
        grammar_poll_map[poll_id] = {
            'event': ev,
            'correct': q.correct_index,
            'chosen': None,
            'countdown_message_id': countdown_msg.message_id,
            'poll_message_id': poll_msg.message_id,
        }
        countdown_task = asyncio.create_task(
            _edit_countdown_steps(chat_id, countdown_msg.message_id, q_plain, total_seconds, lang=lang)
        )
        try:
            await asyncio.wait_for(ev.wait(), timeout=total_seconds + 1.0)
        except Exception:
            pass
        meta = grammar_poll_map.pop(poll_id, None)
        chosen = meta.get('chosen') if meta else None
        if chosen is None:
            skipped_count += 1
        elif chosen == q.correct_index:
            correct_count += 1
        else:
            wrong_count += 1
        try:
            countdown_task.cancel()
        except Exception:
            pass
        try:
            await bot.delete_message(chat_id, poll_msg.message_id)
        except Exception:
            pass
        try:
            await bot.delete_message(chat_id, countdown_msg.message_id)
        except Exception:
            pass

    total = correct_count + wrong_count + skipped_count
    
    # Calculate percentage
    percentage = (correct_count / total * 100) if total > 0 else 0

    dcoin_reward = correct_count * 2.0
    dcoin_penalty_skipped = skipped_count * 1.5
    dcoin_penalty_wrong = wrong_count * 3.0
    net_dcoin = dcoin_reward - dcoin_penalty_skipped - dcoin_penalty_wrong

    gram_subject = _get_student_subject(user)
    if net_dcoin != 0:
        add_dpoints(
            user['id'],
            net_dcoin,
            gram_subject,
            change_type="grammar_test_reward" if net_dcoin > 0 else "grammar_test_penalty",
        )
    
    add_test_history(user['id'], 'grammar', topic.topic_id, correct_count, wrong_count, skipped_count)
    
    # Detailed results
    result_lines = [
        t(lang, "grammar_quiz_results_title", title=topic.title),
        "",
        t(lang, "daily_test_results_percentage", percentage=f"{percentage:.1f}"),
        "",
        t(lang, "quiz_total_questions", total=total),
        t(lang, "quiz_correct_count", count=correct_count),
        t(lang, "quiz_wrong_count", count=wrong_count),
        t(lang, "quiz_skipped_count", count=skipped_count),
        "",
        t(lang, "attempts_left_bold", left=f"{max(0, 1 - (attempts + 1))}/1"),
        "",
        t(lang, "quiz_dcoin_title"),
        t(lang, "quiz_dcoin_reward_line", count=correct_count, mult="2", amount=f"{dcoin_reward:.1f}"),
    ]
    if skipped_count > 0:
        result_lines.append(
            t(
                lang,
                "quiz_dcoin_penalty_skipped_line",
                count=skipped_count,
                mult="1.5",
                amount=f"{dcoin_penalty_skipped:.1f}",
                label=t(lang, "daily_test_results_skipped_label"),
            )
        )
    if wrong_count > 0:
        result_lines.append(
            t(
                lang,
                "quiz_dcoin_penalty_wrong_line",
                count=wrong_count,
                mult="3",
                amount=f"{dcoin_penalty_wrong:.1f}",
                label=t(lang, "daily_test_results_wrong_label"),
            )
        )
    result_lines.extend([
        t(lang, "quiz_dcoin_total", total=f"{net_dcoin:+.1f}"),
        t(lang, "balance_subject_bold", subject=gram_subject, balance=f"{get_dcoins(user['id'], gram_subject):.1f}"),
    ])
    
    # Add performance feedback
    if percentage >= 80:
        result_lines.append("\n" + t(lang, "performance_excellent"))
    elif percentage >= 60:
        result_lines.append("\n" + t(lang, "performance_good"))
    elif percentage >= 40:
        result_lines.append("\n" + t(lang, "performance_ok"))
    else:
        result_lines.append("\n" + t(lang, "performance_try_harder"))
    
    await bot.send_message(chat_id, "\n".join(result_lines), parse_mode="HTML")


@dp.callback_query(lambda c: c.data.startswith("vocab_quiz_cnt_"))
async def handle_vocab_quiz_count(callback: CallbackQuery):
    try:
        cnt = int(callback.data.split("_")[-1])
    except Exception:
        await callback.answer()
        return
    if cnt not in (5, 10, 15, 20, 25, 30):
        await callback.answer()
        return
    state = get_vocab_state(callback.message.chat.id)
    qtype = (state.get('data') or {}).get('qtype')
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user) or not qtype:
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    state['step'] = None
    await callback.answer(t(lang, 'started'))
    await _run_vocab_quiz(callback.message.chat.id, user, qtype, cnt)


@dp.callback_query(lambda c: c.data.startswith("gr_lvl_"))
async def handle_grammar_level(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    level = callback.data.split("_")[-1].upper()
    await callback.answer()
    await _render_topics(callback.message.chat.id, user, level, 0)


@dp.callback_query(lambda c: c.data.startswith("gr_topic_page:"))
async def handle_grammar_topic_page(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    parts = callback.data.split(":")
    level = parts[1].upper()
    page = int(parts[2])
    await callback.answer()
    await _render_topics(callback.message.chat.id, user, level, page)


@dp.callback_query(lambda c: c.data.startswith("gr_topic_pick:"))
async def handle_grammar_topic_pick(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    _, level, topic_token = callback.data.split(":", 2)
    topic_id = _grammar_topic_id_from_token(topic_token)
    await callback.answer()
    await _show_topic(callback.message.chat.id, user, level.upper(), topic_id)


@dp.callback_query(lambda c: c.data.startswith("grammar_topic:"))
async def handle_grammar_topic_selection(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer(t(lang, 'user_not_found'))
        return
    
    topic_id = callback.data.split(":", 1)[1]
    topic = find_topic_by_id(topic_id)
    if not topic:
        await callback.answer(t(lang, 'grammar_topic_not_found'))
        return
    
    attempts = get_grammar_attempts(user['id'], topic.topic_id)
    left = max(0, 1 - attempts)
    rules = topic.rule
    attempts_line = t(lang, 'grammar_attempts_left', left=left)
    text = t(
        lang,
        'grammar_topic_plain_block',
        title=html_module.escape(topic.title or ''),
        rules=html_module.escape(rules or ''),
        attempts=attempts_line,
    )
    rows = []
    if left > 0:
        topic_token = _grammar_topic_token(topic.topic_id)
        rows.append([InlineKeyboardButton(text=t(lang, 'grammar_start_test'), callback_data=f"gr_start:{topic.level}:{topic_token}")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="menu_grammar")]])
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("gr_back_to_topics:"))
async def handle_back_to_topics(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer(t(lang, 'user_not_found'))
        return
    parts = callback.data.split(":")
    level = parts[1]
    page = int(parts[2]) if len(parts) > 2 else 0
    await callback.answer()
    await _render_topics(callback.message.chat.id, user, level, page)


async def handle_show_dcoin_balance(chat_id: int, user: dict = None):
    """D'coin balansini ko'rsatish"""
    if user is None:
        user = get_user_by_telegram(str(chat_id))
        if not user:
            return

    lang = detect_lang_from_user(user)
    dcoin_balance = float(get_dcoins(user['id']))
    dpoints_balance = float(get_dpoints(user['id']))
    subject_count = max(1, len(get_user_subjects(user["id"]) or []))
    lines = [
        t(lang, 'student_dcoin_single', amount=f'{dcoin_balance:.1f}'),
        t(lang, 'student_dpoints_single', amount=f'{dpoints_balance:.1f}'),
        t(lang, 'student_dcoin_formula_line', subjects=subject_count),
    ]
    text = "\n".join(lines)
    await bot.send_message(chat_id, text, parse_mode='HTML')


@dp.callback_query(lambda c: c.data == "exit_vocab_search")
async def handle_exit_vocab_search(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer(t(lang, 'user_not_found'))
        return
    
    lang = detect_lang_from_user(user)
    state = get_vocab_state(callback.message.chat.id)
    state['step'] = None  # Clear search state
    state['data'] = {}
    
    await callback.message.edit_text(t(lang, 'vocab_search_exited'), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "show_more_vocab_results")
async def handle_show_more_vocab_results(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer(t(lang, 'user_not_found'))
        return
    state = get_vocab_state(callback.message.chat.id)
    
    # Get search data from state
    search_data = state.get('data', {})
    subject = _resolve_vocab_subject(user, search_data.get('subject'))
    query = search_data.get('query', '')
    
    if not subject or not query:
        await callback.answer(t(lang, 'search_data_not_found'))
        return
    
    # Get more results
    from vocabulary import get_available_vocabulary_levels
    level_filter = get_available_vocabulary_levels(user.get('level', 'A1'))
    results = search_words(subject, query, levels=level_filter)
    if not results:
        await callback.answer(t(lang, 'no_more_results'))
        return
    
    # Show next 5 results
    start_idx = search_data.get('shown_count', 5)
    next_results = results[start_idx:start_idx + 5]
    
    if not next_results:
        await callback.answer(t(lang, 'no_more_results'))
        return
    
    # Update shown count
    search_data['shown_count'] = start_idx + len(next_results)
    state['data'] = search_data
    state['step'] = 'search_wait'
    
    lines = [t(lang, 'search_more_results_title', count=len(next_results))]
    
    for i, r in enumerate(next_results, start=start_idx + 1):
        lines.append(_format_vocab_result_line(i, r, subject))
    
    # Add navigation buttons
    nav_buttons = []
    if start_idx + len(next_results) < len(results):
        nav_buttons.append(InlineKeyboardButton(text=t(lang, 'show_more_results_btn'), callback_data="show_more_vocab_results"))
    
    nav_buttons.append(InlineKeyboardButton(text=t(lang, 'exit_btn'), callback_data="exit_vocab_search"))
    
    if nav_buttons:
        kb = InlineKeyboardMarkup(inline_keyboard=[nav_buttons])
        lines.append("")
        lines.append(t(lang, 'search_nav_hint'))
    else:
        kb = None
        lines.append(t(lang, 'search_all_results_shown'))
    
    await callback.message.answer("\n\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("rating_"))
async def handle_rating_period(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer(t(lang, 'user_not_found'))
        return

    period = callback.data.split("_")[1]  # daily, weekly, monthly

    from db import get_rating_leaderboard
    user_subjects = get_user_subjects(user['id']) or []
    subject = _get_selected_subject_for_user(user) if user_subjects else None
    leaderboard_data = get_rating_leaderboard(user['id'], period, subject=subject)

    if not leaderboard_data:
        await callback.answer(t(lang, "student_rating_period_not_available", period=period))
        return

    period_key = f"student_rating_period_{period}"
    period_label = t(lang, period_key)
    if period_label == period_key:
        period_label = period.replace("_", " ").title()
    title = t(lang, "student_rating_title", period_label=period_label)
    if subject:
        title += t(lang, "student_rating_subject_suffix", subject=html_module.escape(subject))
    lines = [title, "", t(lang, "student_rating_top10"), ""]

    for i, entry in enumerate(leaderboard_data[:10], start=1):
        name = html_module.escape(str(entry.get("name") or t(lang, "student_rating_unknown_name")))
        score = entry.get("score", 0)
        dcoin = entry.get("dcoin", 0)
        lines.append(t(lang, "student_rating_row", rank=i, name=name, score=f"{score:.1f}", dcoin=f"{dcoin:.1f}"))

    await callback.message.edit_text("\n".join(lines), parse_mode="HTML")
    await callback.answer()


async def show_student_progress(chat_id: int, user: dict, lang: str):
    """Show student's detailed progress"""
    from i18n import t
    from db import get_student_monthly_stats
    stats = get_student_monthly_stats(user['id'])

    if stats['tests_taken'] > 0:
        pct = f"{(stats['total_correct'] / (stats['tests_taken'] or 1) * 100):.1f}"
        pct_line = t(lang, 'student_progress_overall_percent', percent=pct)
    else:
        pct_line = t(lang, 'student_progress_overall_percent_na')

    lines = [
        t(lang, 'student_progress_month_title'),
        "",
        t(lang, 'student_progress_words_learned', count=stats['words_learned']),
        t(lang, 'student_progress_topics_completed', count=stats['topics_completed']),
        t(lang, 'student_progress_tests_taken', count=stats['tests_taken']),
        t(lang, 'student_progress_correct', count=stats['total_correct']),
        t(lang, 'student_progress_wrong', count=stats['total_wrong']),
        t(lang, 'student_progress_skipped', count=stats['total_skipped']),
        "",
        pct_line,
    ]
    
    # Add previous months navigation
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'daily_tests_history_btn'), callback_data="daily_tests_history_open")],
        [InlineKeyboardButton(text=t(lang, 'progress_previous_btn'), callback_data="progress_previous")],
        [InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="progress_back")]
    ])
    
    await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb, parse_mode="HTML")


async def show_feedback_menu(chat_id: int, user: dict, lang: str):
    """Show feedback menu with anonymous option"""
    from i18n import t
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'feedback_btn_student_anonymous'), callback_data="feedback_anonymous")],
        [InlineKeyboardButton(text=t(lang, 'feedback_btn_student_named'), callback_data="feedback_named")],
        [InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="feedback_back")]
    ])

    await bot.send_message(chat_id, t(lang, 'feedback_menu_text'), reply_markup=kb, parse_mode="HTML")


async def handle_progress_navigation(callback: CallbackQuery):
    """Handle progress navigation"""
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer(t(lang, 'user_not_found'))
        return
    
    action = callback.data.split("_")[-1]
    
    if action == "back":
        await callback.message.delete()
        return
    
    # Handle previous month logic here if needed
    await callback.answer()


@dp.callback_query(lambda c: c.data == 'daily_tests_history_open')
async def handle_daily_tests_history_open(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer()
        return
    lang = detect_lang_from_user(user)

    from db import get_daily_test_attempt_history
    attempts = get_daily_test_attempt_history(user['id'], limit=14)

    lines = [t(lang, 'daily_tests_history_title'), '']
    if not attempts:
        lines.append(t(lang, 'daily_tests_history_empty'))
    else:
        for idx, a in enumerate(attempts, start=1):
            status = a.get('status') or ''
            emoji = '✅' if status == 'completed' else '⏳'
            status_label = (
                t(lang, 'daily_test_history_status_completed')
                if status == 'completed'
                else t(lang, 'daily_test_history_status_other', status=html_module.escape(status))
            )
            correct = a.get('correct') or 0
            wrong = a.get('wrong') or 0
            unanswered = a.get('unanswered') or 0
            net = a.get('net_dcoins') or 0
            detail = t(
                lang,
                'daily_test_history_detail',
                c=correct,
                w=wrong,
                u=unanswered,
                net=f'{net:+.2f}',
            )
            lines.append(
                t(
                    lang,
                    'daily_test_history_line',
                    idx=idx,
                    date=a.get('test_date'),
                    emoji=emoji,
                    status=status_label,
                    detail=detail,
                )
            )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data='daily_tests_history_back')]
        ]
    )
    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == 'daily_tests_history_back')
async def handle_daily_tests_history_back(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer()
        return
    lang = detect_lang_from_user(user)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_student_progress(callback.message.chat.id, user, lang)
    await callback.answer()


async def handle_feedback_submission(callback: CallbackQuery):
    """Handle feedback submission (anonim / ism / orqaga)"""
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer(t(lang, 'user_not_found'))
        return

    action = callback.data.split("_")[-1]
    
    if action == "back":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()
        return
    
    # Start feedback collection
    is_anonymous = action == "anonymous"
    
    state = get_student_state(callback.message.chat.id)
    state['step'] = 'feedback_wait'
    state['data'] = {'anonymous': is_anonymous}
    
    if is_anonymous:
        prompt = t(lang, 'feedback_prompt_anonymous')
    else:
        nm = html_module.escape(
            f"{(user.get('first_name') or '').strip()} {(user.get('last_name') or '').strip()}".strip() or '—'
        )
        prompt = t(lang, 'feedback_prompt_named', name=nm)
    
    try:
        await callback.message.edit_text(prompt, parse_mode="HTML")
    except Exception:
        await callback.message.answer(prompt, parse_mode="HTML")
    await callback.answer()


async def _notify_admins_student_message(
    html_body: str, sender_tg_id: str | None = None, *, ui_lang: str = "uz"
):
    """O‘quvchi fikrini admin chatlarga yuborish."""
    global admin_bot
    from config import ADMIN_BOT_TOKEN, ADMIN_CHAT_IDS
    if not ADMIN_CHAT_IDS:
        return
    lg = ui_lang if ui_lang in ("uz", "ru", "en") else "uz"
    b = admin_bot
    if not b and ADMIN_BOT_TOKEN:
        b = Bot(token=ADMIN_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    if not b:
        return
    for aid in ADMIN_CHAT_IDS:
        try:
            reply_markup = None
            if sender_tg_id and str(sender_tg_id).strip().isdigit():
                reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(
                        text=t(lg, 'admin_reply_to_student_btn'),
                        url=f"tg://user?id={int(sender_tg_id)}",
                    )
                ]])
            await b.send_message(aid, html_body, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as e:
            logger.exception("Admin ga fikr yuborishda xato: %s", e)


def _student_feedback_admin_profile(user: dict, lang: str) -> str:
    subjects = get_student_subjects(user['id']) or []
    groups = get_user_groups(user['id']) or []
    teachers = get_student_teachers(user['id']) or []
    dcoin_total = float(get_dcoins(user['id']))
    dpoints_total = float(get_dpoints(user['id']))
    dcoin_by_subject = f"GLOBAL: {dcoin_total:.1f} | D'points: {dpoints_total:.1f}"

    subjects_text = ", ".join(subjects) if subjects else (user.get('subject') or '-')
    groups_text = ", ".join([(g.get('name') or '-') for g in groups]) if groups else '-'
    teachers_text = ", ".join([
        f"{(tr.get('first_name') or '').strip()} {(tr.get('last_name') or '').strip()} ({tr.get('group_name') or '-'})".strip()
        for tr in teachers
    ]) if teachers else '-'

    return t(
        lang,
        'feedback_admin_profile_block',
        fn=html_module.escape((user.get('first_name') or '-')),
        ln=html_module.escape((user.get('last_name') or '-')),
        phone=html_module.escape((user.get('phone') or '-')),
        subjects=html_module.escape(subjects_text),
        groups=html_module.escape(groups_text),
        teachers=html_module.escape(teachers_text),
        dcoin_total=f'{dcoin_total:.1f}',
        dcoin_by_subj=html_module.escape(dcoin_by_subject),
    )


async def handle_feedback_text(message: types.Message):
    """Fikr matni — avval qoralama, keyin tasdiqlash."""
    state = get_student_state(message.chat.id)
    
    if state.get('step') != 'feedback_wait':
        return
    
    user = get_user_by_telegram(str(message.from_user.id))
    if not user:
        return

    lang = detect_lang_from_user(user or message.from_user)
    
    feedback_text = (message.text or "").strip()
    is_anonymous = state.get('data', {}).get('anonymous', True)
    
    if not feedback_text:
        await message.answer(t(lang, 'feedback_empty_error'))
        return
    
    state['step'] = 'feedback_confirm'
    state['data']['draft'] = feedback_text
    state['data']['anonymous'] = is_anonymous

    safe = html_module.escape(feedback_text[:3800])
    preview = t(lang, 'feedback_confirm_prompt', draft=safe)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'feedback_btn_send_admin'), callback_data="fb_ok")],
        [InlineKeyboardButton(text=t(lang, 'feedback_btn_cancel'), callback_data="fb_cancel")],
    ])
    await message.answer(preview, reply_markup=kb, parse_mode="HTML")


@dp.callback_query(lambda c: c.data in ("fb_ok", "fb_cancel"))
async def handle_student_feedback_confirm(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        return
    state = get_student_state(callback.message.chat.id)
    if state.get('step') != 'feedback_confirm':
        await callback.answer(t(lang, 'feedback_action_expired'), show_alert=True)
        return

    if callback.data == "fb_cancel":
        state['step'] = None
        state['data'] = {}
        try:
            await callback.message.edit_text(t(lang, 'feedback_send_cancelled'))
        except Exception:
            await callback.message.answer(t(lang, 'feedback_send_cancelled'))
        await callback.answer()
        return

    draft = (state.get('data') or {}).get('draft', "")
    is_anonymous = (state.get('data') or {}).get('anonymous', True)
    from db import add_feedback
    add_feedback(user['id'], draft, is_anonymous)

    who = t(lang, 'feedback_admin_identity_anon' if is_anonymous else 'feedback_admin_identity_named')
    profile = _student_feedback_admin_profile(user, lang)
    admin_html = (
        t(lang, 'feedback_admin_report_title')
        + "\n"
        + who
        + "\n"
        + t(lang, 'feedback_admin_user_id', uid=user['id'])
        + "\n"
        + t(lang, 'feedback_admin_login_id', login=html_module.escape(user.get('login_id') or '-'))
        + "\n"
        + t(lang, 'feedback_admin_tg', tg=html_module.escape(str(user.get('telegram_id') or '—')))
        + "\n\n"
        + profile
        + "\n"
        + t(lang, 'feedback_admin_message_label')
        + "\n"
        + f"<pre>{html_module.escape(draft[:3500])}</pre>"
    )
    await _notify_admins_student_message(admin_html, user.get('telegram_id'), ui_lang=lang)

    state['step'] = None
    state['data'] = {}
    try:
        await callback.message.edit_text(t(lang, 'feedback_sent_success'), parse_mode="HTML")
    except Exception:
        await callback.message.answer(t(lang, 'feedback_sent_success'), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(lambda c: c.data == "profile_feedback_menu")
async def handle_profile_feedback_menu(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    await show_feedback_menu(callback.message.chat.id, user, lang)
    await callback.answer()


@dp.callback_query(lambda c: c.data == "profile_choose_lang")
async def handle_profile_choose_lang(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        return
    await callback.message.answer(t(lang, 'choose_lang'), reply_markup=create_language_selection_keyboard_for_self(lang))
    await callback.answer()


# Add callback handlers for feedback and progress
@dp.callback_query(lambda c: c.data in ("feedback_anonymous", "feedback_named", "feedback_back"))
async def handle_feedback_callbacks(callback: CallbackQuery):
    await handle_feedback_submission(callback)


@dp.callback_query(lambda c: c.data.startswith("progress_"))
async def handle_progress_callbacks(callback: CallbackQuery):
    await handle_progress_navigation(callback)


@dp.message(
    lambda m: is_diamondvoy_chat_trigger(m.text)
    and get_login_state(str(m.from_user.id)).get("step") not in ("ask_login", "ask_password")
)
async def handle_diamondvoy_message(message: types.Message):
    """Vocab/feedback dan oldin — Diamondvoy boshqa state lar bilan yutilib qolmasin."""
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    from db import get_diamondvoy_chat_history, save_diamondvoy_chat_message
    
    if not user or user.get("login_type") not in (1, 2):
        await message.answer(t(lang, "please_send_start"))
        return
    if not is_access_active(user):
        if not check_user_group_access(int(user.get("id") or 0)):
            await _send_no_group_block_message(message.chat.id, lang, user=user)
        else:
            await message.answer(t(lang, "blocked_contact_admin"))
        return
    query = extract_diamondvoy_query_anywhere(message.text or "")
    if not query:
        await message.answer(t(lang, "diamondvoy_subject_only_warning"))
        return

    status_msg = await message.answer(t(lang, "diamondvoy_status_thinking"))
    tg_id = message.from_user.id
    is_admin = tg_id in ALL_ADMIN_IDS
    scope = "admin_full" if is_admin else "student_limited"
    subjects = default_subjects_for_diamondvoy(user)
    query_lang = detect_query_language(query, fallback=lang)

    info_text = try_diamondvoy_bot_info(
        query,
        user=user,
        telegram_user_id=tg_id,
        lang=lang,
        scope=scope,
        student_state_map=student_state if is_admin else None,
    )
    if info_text is not None:
        try:
            await bot.edit_message_text(
                info_text,
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                parse_mode="HTML",
            )
        except Exception:
            await message.answer(info_text, parse_mode="HTML")
        log_diamondvoy_query(
            int(user["id"]),
            query,
            info_text,
            subject=subjects[0] if subjects else None,
            bot_scope=scope,
        )
        return

    today = _today_tashkent()
    is_paid_over_limit = False
    charged_subject = None
    charged_balance = None
    req_count_before = int(get_student_ai_daily_requests(user["id"], today) or 0) if not is_admin else 0

    if not await diamondvoy_is_subject_related(query, subjects):
        try:
            await bot.edit_message_text(
                t(lang, "diamondvoy_subject_only_warning"),
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
            )
        except Exception:
            await message.answer(t(lang, "diamondvoy_subject_only_warning"))
        return

    if not is_admin:
        if req_count_before >= 3:
            charged_subject = resolve_query_subject(query, subjects)
            charged_balance = consume_dcoins_allow_negative(
                int(user["id"]),
                5.0,
                charged_subject,
                change_type="diamondvoy_over_limit",
            )
            is_paid_over_limit = True
        increment_student_ai_daily_requests(user["id"], today, query)

    try:
        await bot.edit_message_text(
            t(lang, "diamondvoy_checking_question"),
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
        )
    except Exception:
        pass

    conversation = []
    if user and user.get("id"):
        conversation = get_diamondvoy_chat_history(user["id"], limit=12)

    answer = await diamondvoy_gemini_answer(query, subjects, lang=query_lang, is_admin_context=is_admin, conversation=conversation)
    
    if user and user.get("id"):
        save_diamondvoy_chat_message(user["id"], "user", query)
        save_diamondvoy_chat_message(user["id"], "assistant", answer)
        
    if is_paid_over_limit and charged_subject:
        bal_text = t(
            query_lang,
            "diamondvoy_over_limit_charge_notice",
            amount="5",
            subject=charged_subject,
            balance=f"{float(charged_balance or 0):.1f}",
        )
        answer = f"{bal_text}\n\n{answer}"
    await stream_diamondvoy_text_reply(bot, message.chat.id, answer, lang=query_lang, message_id=status_msg.message_id)
    log_diamondvoy_query(
        int(user["id"]),
        query,
        answer,
        subject=charged_subject or (subjects[0] if subjects else None),
        bot_scope=scope,
    )


# Add message handler for feedback text
@dp.message(lambda m: get_student_state(m.chat.id).get('step') == 'feedback_wait')
async def handle_feedback_message(message: types.Message):
    await handle_feedback_text(message)


@dp.callback_query(lambda c: c.data.startswith("gr_start:"))
async def handle_gr_start(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    async def _safe_answer(*args, **kwargs):
        try:
            await callback.answer(*args, **kwargs)
        except Exception:
            # query can be expired/invalid if user clicks very old button
            pass
    if not user:
        await _safe_answer(t(lang, 'not_registered'))
        return
    if not is_access_active(user):
        await _safe_answer(t(lang, 'access_denied'))
        return

    await _safe_answer()
    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        callback.message.chat.id,
        lang,
        section="grammar",
        title="Grammar testlari endi Mini App ichida ishlaydi.",
        label="📱 Grammarni Ochish",
        extra=extra,
    )


@dp.callback_query(lambda c: c.data.startswith("vocab_search_subject:"))
async def handle_vocab_search_subject(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        lang = detect_lang_from_user(callback.from_user)
        await callback.answer(t(lang, "err_user_not_found"))
        return
    
    subject = callback.data.split(":", 1)[1]
    lang = detect_lang_from_user(user)
    
    # Set search state with selected subject
    state = get_vocab_state(callback.message.chat.id)
    state['step'] = 'search_wait'
    state['data'] = {'subject': subject}
    
    await callback.message.edit_text(
        t(lang, "student_vocab_search_subject_input_prompt", subject=subject),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("grammar_rules:"))
async def handle_grammar_rules_callbacks(callback: CallbackQuery):
    """Grammar tugmalarini Mini App test sahifasiga yo'naltirish."""
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return

    parts = callback.data.split(":")
    subject = parts[1].strip() if len(parts) >= 2 and parts[1] else ""
    extra: dict[str, object] = {"auto_join": 1}
    if subject:
        extra["subject"] = subject
    else:
        subject_candidates = get_student_subjects(user["id"]) or []
        if len(subject_candidates) == 1:
            extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        callback.message.chat.id,
        lang,
        section="grammar",
        title="Grammar bo'limi Mini App ichida ochiladi.",
        label="📱 Grammarni Ochish",
        extra=extra,
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("vocab_quiz:"))
async def handle_vocab_quiz_subject_callbacks(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    rest = callback.data.split(":", 1)[1].strip() if ":" in callback.data else ""
    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if rest:
        extra["subject"] = rest
    elif len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        callback.message.chat.id,
        lang,
        section="vocabulary-process",
        title="Vocabulary testlari Mini App ichida ochiladi.",
        label="📱 Vocabulary Testni Ochish",
        extra=extra,
    )
    await callback.answer()


@dp.message(
    lambda m: bool(get_vocab_state(m.chat.id).get('step'))
    and not (m.text and m.text.startswith('/'))
    and not is_diamondvoy_chat_trigger(m.text)
)
async def handle_vocab_message(message: types.Message):
    state = get_vocab_state(message.chat.id)
    logger.info(f"💬 STUDENT VOCAB MESSAGE: {message.text} | User: {message.from_user.id}")
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    from vocabulary import search_words, save_student_preference, get_available_vocabulary_levels

    if state['step'] == 'search_wait':
        query = message.text.strip()
        
        # Handle exit command
        if query.lower() in ['exit', 'chiqish', 'quit', 'orqaga']:
            state['step'] = None
            state['data'] = {}
            await message.answer(t(lang, 'vocab_search_exited'), parse_mode="HTML")
            return
        
        # Resolve concrete subject (important for multi-subject csv values)
        subject = _resolve_vocab_subject(user, state.get('data', {}).get('subject'))
        
        if not subject:
            await message.answer(t(lang, 'subject_info_not_found_retry'))
            state['step'] = None
            return
        
        level_filter = get_available_vocabulary_levels(user.get('level', 'A1')) if user else None
        results = search_words(subject, query, levels=level_filter)
        if not results:
            # Add exit button
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, 'exit_btn'), callback_data="exit_vocab_search")]
            ])
            await message.answer(t(lang, 'search_no_words_found'), reply_markup=kb)
            state['data'] = {'subject': subject, 'query': query, 'shown_count': 0}
            state['step'] = 'search_wait'
            return
        
        # Store search data in state (qidiruv faol — chiqishgacha)
        state['data'] = {'subject': subject, 'query': query, 'shown_count': 5}
        state['step'] = 'search_wait'
        
        # Display first 5 results in one compact card message
        cards = [_format_vocab_result_line(i, r, subject) for i, r in enumerate(results[:5], 1)]
        await message.answer(
            t(lang, 'search_results_for_query', subject=subject, query=query, count=len(results)) + "\n\n" + "\n\n".join(cards),
            parse_mode="HTML",
        )
        
        # Add navigation buttons
        nav_buttons = [InlineKeyboardButton(text=t(lang, 'exit_btn'), callback_data="exit_vocab_search")]
        if len(results) > 5:
            nav_buttons.insert(0, InlineKeyboardButton(text=t(lang, 'show_more_results_btn'), callback_data="show_more_vocab_results"))
        
        kb = InlineKeyboardMarkup(inline_keyboard=[nav_buttons])
        await message.answer(t(lang, 'search_next_query_hint'), reply_markup=kb)
        state['step'] = 'search_wait'
        return

    if state['step'] == 'pref_wait':
        pref = message.text.strip().lower()
        if pref not in ('uz', 'ru'):
            await message.answer(t(lang, 'only_uz_or_ru'))
            return
        save_student_preference(user['id'], pref)
        await message.answer(t(lang, 'saved'))
        state['step'] = None
        return

    # Vocabulary tests must be Telegram quiz polls only (no text-mode quizzes)
    if state.get('step') in ('quiz_ask_type', 'quiz_ask_count'):
        state['step'] = None
        state['data'] = {}
        await message.answer(t(lang, 'vocab_quiz_only_polls'))
        return
@dp.message(Command('resync'))
async def cmd_resync(message: types.Message):
    """Handle /resync command to manually synchronize bot session and reset active states"""
    telegram_id = str(message.from_user.id)
    user = get_user_by_telegram(telegram_id)
    lang = detect_lang_from_user(user or message.from_user)

    if not user:
        msg = {
            'uz': "Siz hali tizimga kirmagansiz. Iltimos, /start buyrug'ini yuboring va login qiling.",
            'ru': "Вы еще не вошли в систему. Пожалуйста, отправьте команду /start и войдите.",
            'en': "You are not logged in yet. Please send /start command to login."
        }.get(lang, "You are not logged in yet. Please send /start command to login.")
        await message.answer(msg)
        return

    # Clear bot state/login session in case it was stuck
    clear_login_state(telegram_id)
    reset_placement_state(message.from_user.id)

    # Force database sync (update telegram_id, set logged_in=1, set activity timestamps)
    activate_user(user['id'], telegram_id)
    
    # Reload user info to get latest synced state
    user = get_user_by_telegram(telegram_id)

    # Check active group access
    if not is_access_active(user):
        if not bool(int(user.get("placement_required") or 0)):
            await _send_no_group_block_message(message.chat.id, lang, user=user)
            return
        kb = _placement_launch_keyboard(user or {}, lang)
        if kb:
            placement_required = bool(int((user or {}).get("placement_required") or 0)) or int((user or {}).get("login_type") or 0) == 1
            launch_text = {
                'uz': "Daraja testini boshlash uchun pastdagi tugmani bosing. Avval FaceID olinadi, keyin test ochiladi.",
                'ru': "Нажмите кнопку ниже, чтобы начать тест уровня. Сначала будет пройдено FaceID, затем откроется тест.",
                'en': "Click the button below to start the level test. FaceID will be taken first, then the test will open."
            }.get(lang, "Click the button below to start the level test. FaceID will be taken first, then the test will open.")
            await message.answer(launch_text, reply_markup=kb)
            return

    # Notify student that sync succeeded
    success_msg = {
        'uz': "Sessiyangiz muvaffaqiyatli yangilandi va sinxronizatsiya qilindi! Endi Mini Appdan foydalanishingiz mumkin.",
        'ru': "Ваша сессия успешно обновлена и синхронизирована! Теперь вы можете использовать Mini App.",
        'en': "Your session has been successfully refreshed and synchronized! You can now use the Mini App."
    }.get(lang, "Your session has been successfully refreshed and synchronized! You can now use the Mini App.")

    await message.answer(success_msg, reply_markup=student_main_keyboard(lang))

    # Offer direct launch link
    kb = _miniapp_open_keyboard(
        label="📱 Mini Appni ochish" if lang == 'uz' else ("📱 Открыть Mini App" if lang == 'ru' else "📱 Open Mini App"),
        section="home",
        extra={"auto_join": 1}
    )
    if kb:
        launch_text = {
            'uz': "Mini Appni to'g'ridan-to'g'ri ochish:",
            'ru': "Открыть Mini App напрямую:",
            'en': "Open Mini App directly:"
        }.get(lang, "Open Mini App directly:")
        await message.answer(launch_text, reply_markup=kb)


@dp.message(Command('otp'))
@dp.message(Command('code'))
async def cmd_otp(message: types.Message):
    """Generate One-Time Password (OTP) for the student to login on the website"""
    telegram_id = str(message.from_user.id)
    user = get_user_by_telegram(telegram_id)
    lang = detect_lang_from_user(user or message.from_user)
    if not user or not user.get('logged_in'):
        msg = {
            'uz': "Siz hali tizimga kirmagansiz. Iltimos, /start buyrug'ini yuboring va login qiling.",
            'ru': "Вы еще не вошли в систему. Пожалуйста, отправьте команду /start и войдите.",
            'en': "You are not logged in yet. Please send /start command to login."
        }.get(lang, "You are not logged in yet. Please send /start command to login.")
        await message.answer(msg)
        return

    import random
    import string
    from db import reset_user_password
    otp_code = "".join(random.choices(string.digits, k=6))
    reset_user_password(int(user["id"]), otp_code)

    message_text = {
        'uz': f"Sizning bir martalik kirish parolingiz (OTP):\n\n<code>{otp_code}</code>\n\nUshbu kodni saytga kirishda ishlating. Kirganingizdan so'ng parol o'zgaradi va uni qayta ishlatib bo'lmaydi.",
        'ru': f"Ваш одноразовый пароль (OTP):\n\n<code>{otp_code}</code>\n\nИспользуйте этот код для входа на сайт. После входа пароль изменится и его нельзя будет использовать повторно.",
        'en': f"Your One-Time Password (OTP):\n\n<code>{otp_code}</code>\n\nUse this code to log in to the site. The password will change after login and cannot be reused.",
    }.get(lang, f"Your One-Time Password (OTP):\n\n<code>{otp_code}</code>")

    await message.answer(message_text, parse_mode="HTML")


@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    """Handle /start command - check login status or show login instructions"""
    from force_subscribe import check_subscription_and_notify

    telegram_id = str(message.from_user.id)
    user = get_user_by_telegram(telegram_id)
    lang = detect_lang_from_user(user or message.from_user)
    if not await check_subscription_and_notify(message.bot, message, lang=lang):
        return

    # If user is already logged in, show main menu
    if user and user.get('logged_in'):
        lang = detect_lang_from_user(user)
        if not is_access_active(user):
            if not bool(int(user.get("placement_required") or 0)):
                await _send_no_group_block_message(message.chat.id, lang, user=user)
                return
            kb = _placement_launch_keyboard(user or {}, lang)
            if kb:
                await message.answer(
                    "Daraja testini boshlash uchun pastdagi tugmani bosing. Avval FaceID olinadi, keyin test ochiladi.",
                    reply_markup=kb,
                )
                return
        await message.answer(t(lang, 'welcome_back'), reply_markup=student_main_keyboard(lang))
        return
    
    # Clear any existing login state and start new login flow
    clear_login_state(telegram_id)
    reset_placement_state(message.from_user.id)
    
    # Start two-step login flow
    set_login_state(telegram_id, {'step': 'ask_login', 'data': {}})
    
    lang = detect_lang_from_user(message.from_user)
    
    await message.answer(t(lang, 'student_login_title'))
    await message.answer(t(lang, 'ask_login_id'))


@dp.message(lambda m: not (m.text or '').startswith('/'))
async def handle_login_and_messages(message: types.Message):
    """Ikki bosqichli login + eski formatni qo‘llab-quvvatlaydi"""
    telegram_id = str(message.from_user.id)
    login_state = get_login_state(telegram_id)
    lang = detect_lang_from_user(message.from_user)
    current_user = get_user_by_telegram(telegram_id)

    qr_login_allowed = login_state.get('step') in ('ask_login', 'ask_password') or not (current_user and current_user.get("logged_in"))
    if message.photo and qr_login_allowed:
        qr_raw = await _decode_qr_text_from_photo_message(message)
        if not qr_raw:
            # Do not block normal photo workflows for logged-in users.
            if login_state.get('step') in ('ask_login', 'ask_password'):
                await message.answer("QR code aniqlanmadi")
                return
        try:
            user = login_with_qr_token_for_bot(
                telegram_id=message.from_user.id,
                raw_qr_token=qr_raw,
                allowed_login_types=(1, 2),
            )
        except Exception as exc:
            if login_state.get('step') in ('ask_login', 'ask_password') or not (current_user and current_user.get("logged_in")):
                await message.answer(str(exc) or "QR code bilan kirib bo'lmadi")
                return
            # Authenticated user sending a random photo shouldn't be blocked here.
            user = None
        if not user:
            # Continue regular handler path.
            pass
        else:
            clear_login_state(telegram_id)
            reset_placement_state(message.from_user.id)
            lang = detect_lang_from_user(user or message.from_user)
            if not is_access_active(user):
                if not bool(int((user or {}).get("placement_required") or 0)):
                    await _send_no_group_block_message(message.chat.id, lang, user=user)
                    return
            await message.answer(t(lang, 'login_success'), reply_markup=student_main_keyboard(lang))
            kb = _placement_launch_keyboard(user or {}, lang)
            if kb:
                placement_required = bool(int((user or {}).get("placement_required") or 0)) or int((user or {}).get("login_type") or 0) == 1
                launch_text = (
                    "Daraja testini boshlash uchun pastdagi tugmani bosing. Avval FaceID olinadi, keyin test ochiladi."
                    if placement_required
                    else "MiniAppga kirish uchun pastdagi tugmani bosing. FaceID olinmagan bo'lsa avval FaceID ochiladi."
                )
                await message.answer(launch_text, reply_markup=kb)
            return

    # Login jarayonida bo‘lsa yoki eski formatda (:) bo‘lsa — process qil
    # Diamondvoy "salom diamondvoy: ..." matnlarida ':' bo‘lishi mumkin — ularni login ga yubormaslik.
    if login_state.get('step') in ('ask_login', 'ask_password') or (
        ':' in (message.text or '') and not is_diamondvoy_chat_trigger(message.text)
    ):
        success = await process_login_message(message, expected_login_type=2)
        if success:
            user = get_user_by_telegram(telegram_id)
            lang = detect_lang_from_user(user or message.from_user)
            if not is_access_active(user):
                if not bool(int((user or {}).get("placement_required") or 0)):
                    await _send_no_group_block_message(message.chat.id, lang, user=user)
                    return
            await message.answer(t(lang, 'login_success'), reply_markup=student_main_keyboard(lang))
            kb = _placement_launch_keyboard(user or {}, lang)
            if kb:
                placement_required = bool(int((user or {}).get("placement_required") or 0)) or int((user or {}).get("login_type") or 0) == 1
                launch_text = (
                    "Daraja testini boshlash uchun pastdagi tugmani bosing. Avval FaceID olinadi, keyin test ochiladi."
                    if placement_required
                    else "MiniAppga kirish uchun pastdagi tugmani bosing. FaceID olinmagan bo'lsa avval FaceID ochiladi."
                )
                await message.answer(launch_text, reply_markup=kb)
            else:
                await message.answer(t(lang, 'select_from_menu'), reply_markup=student_main_keyboard(lang))
        return  # Jarayon tugamaguncha boshqa hech narsa qilma

    # Agar login tugagan bo‘lsa — oddiy authenticated handler
    await handle_authenticated_message(message)


async def handle_authenticated_message(message: types.Message):
    """Handle messages from authenticated users"""
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    
    # Accept both legacy student login types (1 and 2)
    if not user or user.get('login_type') not in (1, 2):
        await message.answer(t(lang, 'please_send_start'))
        return
    if not check_user_group_access(int(user.get("id") or 0)):
        if not bool(int(user.get("placement_required") or 0)):
            await _send_no_group_block_message(message.chat.id, lang, user=user)
            return
        kb = _placement_launch_keyboard(user, lang)
        if kb:
            await message.answer(
                "Daraja testini boshlash uchun pastdagi tugmani bosing. Avval FaceID olinadi, keyin test ochiladi.",
                reply_markup=kb,
            )
        else:
            await message.answer(t(lang, 'please_send_start'))
        return

    state = get_student_state(message.chat.id)

    if state.get('step') == 'feedback_confirm':
        await message.answer(t(lang, 'feedback_confirm_use_buttons'))
        return
    
    # Handle grammar topic number selection
    if state.get('step') == 'grammar_topic_select':
        try:
            topic_num = int(message.text.strip())
            topics = state.get('data', {}).get('topics', [])
            level = state.get('data', {}).get('level')
            
            if 1 <= topic_num <= len(topics):
                selected_topic = topics[topic_num - 1]
                state['step'] = None  # Clear state
                state['data'] = {}
                await _show_topic(message.chat.id, user, level, selected_topic.topic_id)
            else:
                await message.answer(t(lang, 'wrong_topic_number_range', max_num=len(topics)))
        except ValueError:
            await message.answer(t(lang, 'only_number_input_example'))
        return
    
    # Note: Subject handling is now done via inline buttons, no text input needed
    
    # Localized button comparisons
    materials_btn = '📚 ' + t(lang, 'grammar_rules')
    progress_btn = '📊 ' + t(lang, 'progress')
    coins_btn = t(lang, 'student_dcoin_btn')
    leaderboard_btn = '💎 ' + t(lang, 'leaderboard')
    vocab_btn = '📖 ' + t(lang, 'vocab_menu')
    daily_test_btn = t(lang, 'daily_test_btn')
    daily_test_start_btn = t(lang, 'daily_test_start_btn')
    arena_btn = '⚔️ ' + t(lang, 'menu_arena')
    support_btn = '🆘 ' + t(lang, 'support_menu_btn')

    vocab_search_btn = '🔎 ' + t(lang, 'vocab_search_btn')
    vocab_quiz_btn = '🧠 ' + t(lang, 'vocab_quiz_btn')
    vocab_pref_btn = '⚙️ ' + t(lang, 'vocab_pref_btn')
    back_btn = '⬅️ ' + t(lang, 'back_btn')
    profile_btn = '👤 ' + t(lang, 'my_profile')

    if message.text == profile_btn:
        await show_my_profile(message.chat.id, user)
        return

    if message.text == materials_btn:
        subject_candidates = get_student_subjects(user["id"]) or []
        extra: dict[str, object] = {"auto_join": 1}
        if len(subject_candidates) == 1:
            extra["subject"] = subject_candidates[0]
        await _send_test_redirect(
            message.chat.id,
            lang,
            section="grammar",
            title="Grammar test va mavzulari Mini App ichida ochiladi.",
            label="📱 Grammarni Ochish",
            extra=extra,
        )
        return

    if message.text == progress_btn:
        await show_student_progress(message.chat.id, user, lang)
        return

    if message.text == coins_btn:
        await handle_show_dcoin_balance(message.chat.id, user)
        return

    if message.text == leaderboard_btn:
        await show_leaderboard(message.from_user.id, message.chat.id, 0, 'global')
        return

    # Vocabulary reply-menu (Mini App redirect)
    if message.text == vocab_btn:
        subject_candidates = get_student_subjects(user["id"]) or []
        extra: dict[str, object] = {"auto_join": 1}
        if len(subject_candidates) == 1:
            extra["subject"] = subject_candidates[0]
        await _send_test_redirect(
            message.chat.id,
            lang,
            section="vocabulary-process",
            title="Vocabulary testlari Mini App ichida ochiladi.",
            label="📱 Vocabulary Testni Ochish",
            extra=extra,
        )
        return

    if message.text == daily_test_btn:
        kb = _miniapp_open_keyboard(
            daily_test_start_btn,
            "daily-test-process",
            extra={"auto_join": 1},
        )
        if not kb:
            await message.answer(t(lang, "error_with_reason", error="MiniApp URL is not configured"))
            return
        await message.answer(
            t(lang, "daily_test_menu_title") + "\n\n" + t(lang, "daily_test_menu_start_hint"),
            reply_markup=kb,
        )
        return

    if message.text == support_btn:
        ensure_support_lessons_schema()
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "support_book_lesson_btn"), callback_data="support:book")],
                [InlineKeyboardButton(text=t(lang, "support_my_bookings_btn"), callback_data="support:my")],
            ]
        )
        await message.answer(t(lang, "support_menu_title"), reply_markup=kb)
        return

    diamondvoy_btn = '🤖 ' + t(lang, 'menu_diamondvoy_ai')
    if message.text == diamondvoy_btn:
        await message.answer(t(lang, "diamondvoy_prompt"))
        return

    if message.text == arena_btn:
        subject_candidates = get_student_subjects(user["id"]) or []
        extra: dict[str, object] = {"arena_mode": "arena", "auto_join": 1}
        if len(subject_candidates) == 1:
            extra["subject"] = subject_candidates[0]
        await _send_test_redirect(
            message.chat.id,
            lang,
            section="arena",
            title="Arena testlari Mini App ichida ochiladi.",
            label="📱 Arenani Ochish",
            extra=extra,
        )
        return
    if message.text == back_btn:
        await message.answer(t(lang, 'select_from_menu'), reply_markup=student_main_keyboard(lang))
        return
    if message.text == vocab_search_btn:
        subject_candidates = get_student_subjects(user["id"]) or []
        extra: dict[str, object] = {"auto_join": 1}
        if len(subject_candidates) == 1:
            extra["subject"] = subject_candidates[0]
        await _send_test_redirect(
            message.chat.id,
            lang,
            section="vocabulary-process",
            title="Vocabulary qidiruv va test bo'limi Mini App ichida.",
            label="📱 Vocabulary Testni Ochish",
            extra=extra,
        )
        return
    if message.text == vocab_pref_btn:
        subject_candidates = get_student_subjects(user["id"]) or []
        extra: dict[str, object] = {"auto_join": 1}
        if len(subject_candidates) == 1:
            extra["subject"] = subject_candidates[0]
        await _send_test_redirect(
            message.chat.id,
            lang,
            section="vocabulary-process",
            title="Vocabulary sozlamalari Mini App ichida.",
            label="📱 Vocabulary Testni Ochish",
            extra=extra,
        )
        return
    if message.text == vocab_quiz_btn:
        subject_candidates = get_student_subjects(user["id"]) or []
        extra: dict[str, object] = {"auto_join": 1}
        if len(subject_candidates) == 1:
            extra["subject"] = subject_candidates[0]
        await _send_test_redirect(
            message.chat.id,
            lang,
            section="vocabulary-process",
            title="Vocabulary testlari Mini App ichida ishlaydi.",
            label="📱 Vocabulary Testni Ochish",
            extra=extra,
        )
        return

    await message.answer(t(lang, 'unknown_command'))


async def show_my_profile(chat_id: int, user: dict):
    from i18n import t, detect_lang_from_user
    lang = detect_lang_from_user(user)

    subjects = get_student_subjects(user['id'])
    groups = get_user_groups(user['id'])
    teachers = get_student_teachers(user['id'])

    lines = []
    lines.append("👤 " + t(lang, 'my_profile'))
    lines.append("")
    lines.append(
        t(
            lang,
            'profile_full_name',
            first=html_module.escape(str(user.get('first_name') or '-')),
            last=html_module.escape(str(user.get('last_name') or '-')),
        )
    )
    lines.append(t(lang, 'profile_login_id', login=html_module.escape(str(user.get('login_id') or '-'))))

    if subjects:
        if len(subjects) == 1:
            lines.append(t(lang, 'profile_subject_one', subject=html_module.escape(subjects[0])))
        else:
            lines.append(
                t(
                    lang,
                    'profile_subjects_multi',
                    subjects=html_module.escape(', '.join(subjects)),
                    n=len(subjects),
                )
            )
        level_parts = []
        for sub in subjects:
            last = get_latest_test_result_for_subject(user['id'], sub)
            sc = last.get('score') if last else None
            try:
                sc_int = int(sc) if sc is not None else None
            except (TypeError, ValueError):
                sc_int = None
            lvl = level_display_from_score(sc_int, sub) if sc_int is not None else t(lang, 'student_lb_rank_dash')
            level_parts.append(f"{sub}: {lvl}")
        if level_parts:
            lines.append(f"📊 {t(lang, 'profile_subjects_levels_line')}: {', '.join(level_parts)}")
    else:
        lines.append(t(lang, 'profile_subject_one', subject=html_module.escape(str(user.get('subject') or '-'))))

    lines.append(t(lang, 'profile_groups_count', n=len(groups)))

    if teachers:
        lines.append(t(lang, 'profile_teachers_header', n=len(teachers)))
        for teacher in teachers:
            lines.append(
                t(
                    lang,
                    'profile_teacher_bullet',
                    first=html_module.escape(str(teacher.get('first_name') or '')),
                    last=html_module.escape(str(teacher.get('last_name') or '')),
                    group=html_module.escape(str(teacher.get('group_name') or '-')),
                )
            )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 OTP kod olish", callback_data='get_my_otp')],
        [InlineKeyboardButton(text=t(lang, 'survey'), callback_data='profile_feedback_menu')],
        [InlineKeyboardButton(text=t(lang, 'choose_lang'), callback_data='profile_choose_lang')],
        [InlineKeyboardButton(text=t(lang, 'logout'), callback_data='logout_me')],
    ])

    await bot.send_message(chat_id, "\n".join(lines), reply_markup=kb)


@dp.callback_query(lambda c: c.data.startswith("arena_mode_"))
async def handle_arena_modes(callback: CallbackQuery):
    mode = callback.data.split("arena_mode_", 1)[-1]
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    text_map = {
        "1v1": t(lang, "arena_desc_duel_1v1"),
        "5v5": t(lang, "arena_desc_duel_5v5"),
        "group": t(lang, "arena_desc_group"),
        "daily": t(lang, "arena_desc_daily"),
        "boss": t(lang, "arena_desc_boss"),
        "rules": t(lang, "arena_rules_question_types_html"),
        "rules_duel_1v1": t(lang, "arena_rules_duel_1v1_html"),
        "rules_duel_5v5": t(lang, "arena_rules_duel_5v5_html"),
        "rules_daily": t(lang, "arena_rules_daily_html"),
        "rules_boss": t(lang, "arena_rules_boss_html"),
        "rules_group": t(lang, "arena_rules_group_html"),
    }
    await callback.answer()
    if mode == "group":
        await callback.message.answer(t(lang, "arena_group_only_via_teacher"))
        return
    if mode == "rules":
        rules_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "arena_mode_duel_1v1"), callback_data="arena_mode_rules_duel_1v1")],
                [InlineKeyboardButton(text=t(lang, "arena_mode_duel_5v5"), callback_data="arena_mode_rules_duel_5v5")],
                [InlineKeyboardButton(text=t(lang, "arena_mode_daily"), callback_data="arena_mode_rules_daily")],
                [InlineKeyboardButton(text=t(lang, "arena_mode_boss"), callback_data="arena_mode_rules_boss")],
                [InlineKeyboardButton(text=t(lang, "arena_mode_group"), callback_data="arena_mode_rules_group")],
            ]
        )
        await callback.message.answer(text_map["rules"], reply_markup=rules_kb, parse_mode="HTML")
        return
    base = text_map.get(mode, t(lang, "arena_coming_soon"))
    if mode in {"1v1", "5v5", "daily", "boss"}:
        section_map = {
            "1v1": "duel-1v1",
            "5v5": "duel-5v5",
            "daily": "arena-daily",
            "boss": "arena-boss",
        }
        section = section_map.get(mode, "arena")
        url = _student_miniapp_url(section, extra={"arena_mode": section, "auto_join": 1})
        if not url:
            await callback.message.answer(t(lang, "error_with_reason", error="MiniApp URL is not configured"))
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "arena_join_paid_btn"), web_app=WebAppInfo(url=url))]
            ]
        )
        await callback.message.answer(base, reply_markup=kb, parse_mode="HTML")
    else:
        kb = _miniapp_open_keyboard("📱 Arenani Ochish", "arena", extra={"arena_mode": "arena", "auto_join": 1})
        if kb:
            await callback.message.answer("Arena bo'limi Mini App ichida ochiladi.", reply_markup=kb)
        else:
            await callback.message.answer(base, parse_mode="HTML")


@dp.callback_query(lambda c: (c.data or "").startswith("arena_duel_pick:"))
async def handle_arena_duel_pick_subject(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        return
    try:
        _, mode, subject = (callback.data or "").split(":", 2)
    except ValueError:
        await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
        return
    mode = mode.strip()
    subject = subject.strip().title()
    if mode not in {"1v1", "5v5"}:
        await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
        return
    allowed = {s.strip().title() for s in (get_user_subjects(user["id"]) or [])}
    if allowed and subject not in allowed:
        await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
        return
    section = "duel-1v1" if mode == "1v1" else "duel-5v5"
    url = _student_miniapp_url(section, extra={"arena_mode": section, "auto_join": 1, "subject": subject})
    if not url:
        await callback.message.answer(t(lang, "error_with_reason", error="MiniApp URL is not configured"))
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "duel_join_btn"), web_app=WebAppInfo(url=url))],
        ]
    )
    desc = {
        "1v1": t(lang, "arena_desc_duel_1v1"),
        "5v5": t(lang, "arena_desc_duel_5v5"),
    }.get(mode, "")
    await callback.answer()
    await callback.message.answer(f"{desc}\n\n{t(lang, 'arena_duel_chosen_subject', subject=subject)}", reply_markup=kb)


@dp.callback_query(lambda c: (c.data or "").startswith("arena_join_existing"))
async def handle_arena_join_existing_duel(callback: CallbackQuery):
    """Faqat ochiq duel sessiyasi bo‘lsa qo‘shiladi; aks holda ogohlantirish."""
    data = callback.data or ""
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer()
        return
    lang = detect_lang_from_user(user or callback.from_user)
    if data.startswith("arena_join_existing:"):
        try:
            _, mode, subj = data.split(":", 2)
        except ValueError:
            await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
            return
    else:
        mode = data.split("arena_join_existing_", 1)[-1].split(":", 1)[0]
        subj = _resolve_arena_subject_for_user(user)
    subj = subj.strip().title()
    sess_level = _normalize_arena_level(_resolve_user_level_for_subject(user, subj))
    ensure_duel_matchmaking_schema()
    if mode not in {"1v1", "5v5"}:
        await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
        return
    if not can_start_duel_today(user["id"], mode, _today_tashkent()):
        await callback.answer(t(lang, "duel_daily_limit_reached", mode=mode.upper()), show_alert=True)
        return
    open_session = _pick_open_duel_session_for_join(mode, user, subj)
    if not open_session:
        await callback.answer(t(lang, "duel_no_open_session", mode=mode.upper()), show_alert=True)
        return
    room_subj = str(open_session.get("subject") or subj).strip().title()
    room_lvl = _normalize_arena_level(open_session.get("level") or sess_level)
    fee = 3.0
    ok = try_consume_dcoins(user["id"], fee, room_subj, arena_type=mode)
    if not ok:
        await callback.answer(t(lang, "arena_insufficient_dcoin"), show_alert=True)
        return
    increment_duel_daily_usage(user["id"], mode, _today_tashkent())
    await callback.answer(t(lang, "arena_join_confirmed"))
    await _enqueue_duel_player_and_maybe_start(
        mode=mode,
        user=user,
        chat_id=callback.message.chat.id,
        subject=room_subj,
        level=room_lvl,
        session_id=int(open_session["id"]),
    )


@dp.callback_query(lambda c: _is_simple_arena_join_callback(c.data or ""))
async def handle_arena_join(callback: CallbackQuery):
    data = callback.data or ""
    if data.startswith("arena_enter_duel:"):
        try:
            _, mode, subj = data.split(":", 2)
        except ValueError:
            await callback.answer()
            return
        mode = mode.strip()
        subj = subj.strip().title()
        raw = mode
    elif data.startswith("arena_enter_duel_"):
        raw = data.split("arena_enter_duel_", 1)[-1]
    else:
        raw = data.split("arena_join_", 1)[-1]
    mode = raw.split(":", 1)[0]
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer()
        return
    lang = detect_lang_from_user(user or callback.from_user)
    if not data.startswith("arena_enter_duel:"):
        subj = _resolve_arena_subject_for_user(user)

    section_map = {
        "daily": "arena-daily",
        "boss": "arena-boss",
        "1v1": "duel-1v1",
        "5v5": "duel-5v5",
        "duel-1v1": "duel-1v1",
        "duel-5v5": "duel-5v5",
    }
    if mode in section_map:
        section = section_map[mode]
        subjects = get_user_subjects(user["id"]) or []
        extra: dict[str, object] = {"arena_mode": section, "auto_join": 1}
        if data.startswith("arena_enter_duel:") and subj:
            extra["subject"] = subj
        elif len(subjects) == 1:
            extra["subject"] = subjects[0]
        kb = _miniapp_open_keyboard(t(lang, "arena_join_paid_btn"), section, extra=extra)
        await callback.answer()
        if not kb:
            await callback.message.answer(t(lang, "error_with_reason", error="MiniApp URL is not configured"))
            return
        await callback.message.answer(t(lang, "arena_menu_title"), reply_markup=kb)
        return

    if mode in ("daily", "boss"):
        if ":" not in raw:
            await callback.answer()
            await callback.message.answer(t(lang, "arena_use_scheduled_link"))
            return
        try:
            rid = int(raw.split(":", 1)[1])
        except Exception:
            await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
            return
        run = get_scheduled_arena_run(rid)
        if not run:
            await callback.answer(t(lang, "arena_run_not_found"), show_alert=True)
            return
        st = (run.get("status") or "").strip()
        if st in ("running", "finished", "cancelled"):
            await callback.answer(t(lang, "arena_run_closed"), show_alert=True)
            return
        # Enforce max players only when a positive cap is configured.
        try:
            max_players = int(run.get("max_players") or 15)
        except Exception:
            max_players = 15
        try:
            cur_players = count_arena_run_participants(rid)
        except Exception:
            cur_players = 0
        if max_players > 0 and cur_players >= max_players:
            await callback.answer(t(lang, "arena_run_closed"), show_alert=True)
            return

        if is_arena_run_participant(rid, user["id"]):
            await callback.answer(t(lang, "arena_already_participated"), show_alert=True)
            return
        fee = 3.0
        ok = try_consume_dcoins(
            user["id"],
            fee,
            subj,
            arena_type=mode,
            change_type="boss_entry_fee" if mode == "boss" else None,
        )
        if not ok:
            await callback.answer(t(lang, "arena_insufficient_dcoin"), show_alert=True)
            return
        if not register_arena_run_participant(rid, int(user["id"]), int(callback.message.chat.id)):
            add_dcoins(
                user["id"],
                fee,
                subj,
                change_type="boss_entry_refund" if mode == "boss" else None,
            )
            await callback.answer(t(lang, "arena_already_participated"), show_alert=True)
            return
        await callback.answer()
        await callback.message.answer(t(lang, "arena_registered_for_run"))
        return

    if mode in {"1v1", "5v5"}:
        if not can_start_duel_today(user["id"], mode, _today_tashkent()):
            await callback.answer(t(lang, "duel_daily_limit_reached", mode=mode.upper()), show_alert=True)
            return
    fee = 0.0 if mode == "group" else 3.0
    if fee > 0:
        ok = try_consume_dcoins(user["id"], fee, subj, arena_type=mode)
        if not ok:
            await callback.answer(t(lang, "arena_insufficient_dcoin"), show_alert=True)
            return
    if mode in {"1v1", "5v5"} and fee > 0:
        increment_duel_daily_usage(user["id"], mode, _today_tashkent())
    if mode == "group":
        await callback.answer(t(lang, "arena_group_only_via_teacher"), show_alert=True)
        return

    await callback.answer(t(lang, "arena_join_confirmed"))
    level = _resolve_user_level_for_subject(user, subj)
    if mode in {"1v1", "5v5"}:
        await _enqueue_duel_player_and_maybe_start(
            mode=mode,
            user=user,
            chat_id=callback.message.chat.id,
            subject=subj,
            level=level,
        )


@dp.callback_query(lambda c: c.data.startswith("arena_join_direct:"))
async def handle_arena_join_direct(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer()
        return
    lang = detect_lang_from_user(user or callback.from_user)
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
        return

    _, mode, third = parts

    # Teacher-generated Group Arena session.
    if mode == "group":
        try:
            session_id = int(third)
        except Exception:
            await callback.answer(t(lang, "arena_session_invalid"), show_alert=True)
            return

        session = get_arena_group_session(session_id)
        if not session or (session.get("status") != "sent"):
            await callback.answer(t(lang, "arena_questions_not_ready"), show_alert=True)
            return

        gid = int(session["group_id"])
        today = _today_tashkent()
        if not user_is_present_for_group_on_date(user["id"], gid, today):
            await callback.answer(t(lang, "arena_group_not_present"), show_alert=True)
            return
        if not is_group_lesson_window_active(gid):
            await callback.answer(t(lang, "arena_group_not_lesson_time"), show_alert=True)
            return

        try:
            await callback.answer()
        except Exception:
            pass

        ok = mark_arena_group_session_attempt(session_id=session_id, user_id=user["id"])
        if not ok:
            await callback.message.answer(t(lang, "arena_already_participated"))
            return

        try:
            enqueue_arena_group_teacher_refresh(session_id)
        except Exception:
            pass

        await _run_arena_group_quiz(
            chat_id=callback.message.chat.id,
            user=user,
            session_id=session_id,
            session=session,
        )
        return

    subject = third
    if mode in ("daily", "boss"):
        try:
            rid = int(subject)
        except Exception:
            await callback.answer(t(lang, "arena_wrong_callback"), show_alert=True)
            return
        subj = _resolve_arena_subject_for_user(user)
        run = get_scheduled_arena_run(rid)
        if not run:
            await callback.answer(t(lang, "arena_run_not_found"), show_alert=True)
            return
        st = (run.get("status") or "").strip()
        if st in ("running", "finished", "cancelled"):
            await callback.answer(t(lang, "arena_run_closed"), show_alert=True)
            return
        if is_arena_run_participant(rid, user["id"]):
            await callback.answer(t(lang, "arena_already_participated"), show_alert=True)
            return
        fee = 3.0
        ok = try_consume_dcoins(
            user["id"],
            fee,
            subj,
            arena_type=mode,
            change_type="boss_entry_fee" if mode == "boss" else None,
        )
        if not ok:
            await callback.answer(t(lang, "arena_insufficient_dcoin"), show_alert=True)
            return
        if not register_arena_run_participant(rid, int(user["id"]), int(callback.message.chat.id)):
            add_dcoins(
                user["id"],
                fee,
                subj,
                change_type="boss_entry_refund" if mode == "boss" else None,
            )
            await callback.answer(t(lang, "arena_already_participated"), show_alert=True)
            return
        await callback.answer()
        await callback.message.answer(t(lang, "arena_registered_for_run"))
        return

    if mode in {"1v1", "5v5"}:
        if not can_start_duel_today(user["id"], mode, _today_tashkent()):
            await callback.answer(t(lang, "duel_daily_limit_reached", mode=mode.upper()), show_alert=True)
            return
    fee = 0.0 if mode == "group" else 3.0
    if fee > 0:
        ok = try_consume_dcoins(user["id"], fee, subject, arena_type=mode)
        if not ok:
            await callback.answer(t(lang, "arena_insufficient_dcoin"), show_alert=True)
            return
    if mode in {"1v1", "5v5"} and fee > 0:
        increment_duel_daily_usage(user["id"], mode, _today_tashkent())
    await callback.answer(t(lang, "arena_join_confirmed"))

    level = _resolve_user_level_for_subject(user, subject)
    if mode in {"1v1", "5v5"}:
        await _enqueue_duel_player_and_maybe_start(
            mode=mode,
            user=user,
            chat_id=callback.message.chat.id,
            subject=subject,
            level=level,
        )
    return


@dp.callback_query(lambda c: (c.data or "").startswith("arena_join_duel_session:"))
async def handle_arena_join_duel_session(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer()
        return
    lang = detect_lang_from_user(user or callback.from_user)
    try:
        sid = int((callback.data or "").split(":", 1)[1])
    except Exception:
        await callback.answer(t(lang, "invalid_action"), show_alert=True)
        return
    sess = get_duel_session(sid)
    if not sess or sess.get("status") != "open":
        await callback.answer(t(lang, "duel_session_expired"), show_alert=True)
        return
    subject = str(sess.get("subject") or "English")
    mode = str(sess.get("mode") or "1v1")
    if not can_start_duel_today(user["id"], mode, _today_tashkent()):
        await callback.answer(t(lang, "duel_daily_limit_reached", mode=mode.upper()), show_alert=True)
        return
    if not try_consume_dcoins(user["id"], 3.0, subject, arena_type=mode):
        await callback.answer(t(lang, "arena_insufficient_dcoin"), show_alert=True)
        return
    increment_duel_daily_usage(user["id"], mode, _today_tashkent())
    await callback.answer()
    await _enqueue_duel_player_and_maybe_start(
        mode=mode,
        user=user,
        chat_id=callback.message.chat.id,
        subject=subject,
        level=str(sess.get("level") or "A1"),
        session_id=sid,
    )


@dp.callback_query(lambda c: (c.data or "").startswith("arena_revenge:"))
async def handle_arena_revenge(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer()
        return
    lang = detect_lang_from_user(user or callback.from_user)
    try:
        _, mode, subject, opp = (callback.data or "").split(":", 3)
        opponent_id = int(opp)
    except Exception:
        await callback.answer(t(lang, "invalid_action"), show_alert=True)
        return
    now_iso = _now_tashkent().strftime("%Y-%m-%d %H:%M:%S")
    if not consume_valid_revenge_token(int(user["id"]), opponent_id, mode, subject, now_iso):
        await callback.answer(t(lang, "duel_revenge_expired"), show_alert=True)
        return
    if not can_start_duel_today(user["id"], mode, _today_tashkent()):
        await callback.answer(t(lang, "duel_daily_limit_reached", mode=mode.upper()), show_alert=True)
        return
    if not try_consume_dcoins(user["id"], 3.0, subject, arena_type=mode):
        await callback.answer(t(lang, "arena_insufficient_dcoin"), show_alert=True)
        return
    increment_duel_daily_usage(user["id"], mode, _today_tashkent())
    await callback.answer()
    await _enqueue_duel_player_and_maybe_start(
        mode=mode,
        user=user,
        chat_id=callback.message.chat.id,
        subject=subject,
        level=_resolve_user_level_for_subject(user, subject),
    )


async def _run_arena_group_quiz(chat_id: int, user: dict, session_id: int, session: dict):
    questions = get_arena_group_session_questions(session_id)
    if not questions:
        lang = detect_lang_from_user(user)
        await bot.send_message(chat_id, t(lang, "arena_questions_not_found"))
        return

    total = len(questions)
    correct_count = 0
    wrong_count = 0
    unanswered_count = 0

    subject = session.get("subject") or _get_selected_subject_for_user(user) or "English"

    lang = detect_lang_from_user(user)
    await bot.send_message(
        chat_id,
        t(lang, "arena_group_quiz_intro", total=total, sec=ARENA_GROUP_POLL_SECONDS),
        parse_mode="HTML",
    )

    for idx, q in enumerate(questions, start=1):
        question_text = str(q.get("question") or "").strip()
        options = [
            str(q.get("option_a") or ""),
            str(q.get("option_b") or ""),
            str(q.get("option_c") or ""),
            str(q.get("option_d") or ""),
        ]
        correct_option_index_1 = int(q.get("correct_option_index") or 1)
        correct_idx0 = max(0, min(3, correct_option_index_1 - 1))

        poll_question = f"{idx}/{total} — {question_text}"
        countdown_msg = await bot.send_message(
            chat_id,
            t(lang, "arena_poll_answer_instruction_abcd", sec=ARENA_GROUP_POLL_SECONDS),
        )

        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=poll_question,
            options=[o[:100] for o in options],
            type="quiz",
            correct_option_id=correct_idx0,
            is_anonymous=False,
            open_period=ARENA_GROUP_POLL_SECONDS,
        )

        ev = asyncio.Event()
        arena_group_poll_map[poll_msg.poll.id] = {
            "event": ev,
            "chosen": None,
        }

        try:
            await asyncio.wait_for(ev.wait(), timeout=ARENA_GROUP_POLL_SECONDS + 1.0)
        except Exception:
            pass

        meta = arena_group_poll_map.pop(poll_msg.poll.id, None) or {}
        chosen = meta.get("chosen")

        try:
            await bot.delete_message(chat_id, poll_msg.message_id)
        except Exception:
            pass
        try:
            await bot.delete_message(chat_id, countdown_msg.message_id)
        except Exception:
            pass

        if chosen is None:
            unanswered_count += 1
            try:
                insert_arena_group_session_answer(
                    session_id=session_id,
                    user_id=user["id"],
                    question_order=idx,
                    bank_question_id=int(q.get("id") or 0),
                    selected_option_index=None,
                    is_correct=False,
                )
                enqueue_arena_group_teacher_refresh(session_id)
            except Exception:
                pass
            continue

        selected_idx0 = int(chosen)
        if selected_idx0 == correct_idx0:
            correct_count += 1
        else:
            wrong_count += 1
        try:
            insert_arena_group_session_answer(
                session_id=session_id,
                user_id=user["id"],
                question_order=idx,
                bank_question_id=int(q.get("id") or 0),
                selected_option_index=selected_idx0,
                is_correct=selected_idx0 == correct_idx0,
            )
            enqueue_arena_group_teacher_refresh(session_id)
        except Exception:
            pass

    finish_arena_group_session_attempt(
        session_id=session_id,
        user_id=user["id"],
        correct=correct_count,
        wrong=wrong_count,
        unanswered=unanswered_count,
        net_dcoins=0.0,
    )

    # Finalize Group Arena reward distribution when all expected players finished.
    rewards = {"done": False, "max_correct": None, "winners": [], "winner_rewards": []}
    try:
        rewards = distribute_arena_group_rewards_if_ready(session_id)
    except Exception:
        pass

    try:
        enqueue_arena_group_teacher_refresh(session_id)
    except Exception:
        pass

    lang = detect_lang_from_user(user)
    await bot.send_message(
        chat_id,
        t(
            lang,
            "arena_group_result_summary",
            total=total,
            correct=correct_count,
            wrong=wrong_count,
            unanswered=unanswered_count,
        ),
    )

    # Top-3 D'coin rewards notification
    try:
        if rewards.get("done"):
            for uid, amt in rewards.get("winner_rewards") or []:
                if int(uid) == int(user["id"]):
                    lang = detect_lang_from_user(user)
                    await bot.send_message(
                        chat_id,
                        t(lang, "arena_group_place_reward", amount=float(amt)),
                    )
    except Exception:
        pass


def _normalize_arena_level(level: str | None) -> str:
    lv = normalize_level_to_cefr(level)
    return lv if lv in {"A1", "A2", "B1", "B2", "C1", "MIXED"} else "A1"


def _resolve_user_level_for_subject(user: dict, subject: str) -> str:
    subj = (subject or "").strip().title()
    groups = get_user_groups(user["id"]) or []
    for g in groups:
        gs = (g.get("subject") or "").strip().title()
        if gs and gs == subj:
            return _normalize_arena_level(g.get("level"))
    if groups:
        return _normalize_arena_level(groups[0].get("level"))
    return _normalize_arena_level(user.get("level"))


def _pick_open_duel_session_for_join(mode: str, user: dict, arena_subject: str) -> dict | None:
    """Exact match first; then any open session for this mode with the same subject (room level may differ)."""
    subj = (arena_subject or "").strip().title()
    lvl = _normalize_arena_level(_resolve_user_level_for_subject(user, subj))
    hit = get_open_duel_session(mode, subj, lvl)
    if hit:
        return hit
    for row in list_open_duel_sessions_for_mode(mode):
        if str(row.get("subject") or "").strip().title() == subj:
            return dict(row)
    return None


async def _generate_arena_questions_via_daily_generator(
    *,
    user_id: int,
    subject: str,
    level: str,
    count: int,
) -> list[dict]:
    """
    Best-effort Arena question source:
    - reuse existing Gemini daily generator (`daily_tests_bank`)
    - then fetch the freshly generated rows to run a quiz
    """
    from ai_generator import generate_daily_tests_and_insert

    subj = (subject or "").strip().title()
    lvl = _normalize_arena_level(level)

    await generate_daily_tests_and_insert(
        subject=subj,
        level=lvl,
        count=int(count),
        created_by=user_id,
    )

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            SELECT question, option_a, option_b, option_c, option_d, correct_option_index
            FROM daily_tests_bank
            WHERE created_by=? AND subject=? AND level=?
              AND active=1
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            ''',
            (int(user_id), subj, lvl, int(count)),
        )
        rows = cur.fetchall()
        # `rows` are newest -> oldest; reverse to keep stable question numbering.
        rows = list(rows)
        rows.reverse()
        return [dict(r) for r in rows]
    finally:
        conn.close()


async def _run_arena_simple_quiz(
    *,
    chat_id: int,
    user: dict,
    mode: str,
    subject: str,
    level: str,
    question_count: int,
    reward_fn,
) -> None:
    questions = await _generate_arena_questions_via_daily_generator(
        user_id=user["id"],
        subject=subject,
        level=level,
        count=question_count,
    )
    if not questions:
        lang = detect_lang_from_user(user)
        await bot.send_message(chat_id, t(lang, "arena_questions_not_found"))
        return

    correct_count = 0
    wrong_count = 0
    unanswered_count = 0

    total = len(questions)
    for idx, q in enumerate(questions, start=1):
        lang = detect_lang_from_user(user)
        question_text = f"{t(lang, 'arena_question_title', num=idx)}\n{str(q.get('question') or '').strip()}"
        opts = [
            str(q.get("option_a") or ""),
            str(q.get("option_b") or ""),
            str(q.get("option_c") or ""),
            str(q.get("option_d") or ""),
        ]
        correct_option_index_1 = int(q.get("correct_option_index") or 1)
        correct_idx0 = max(0, min(3, correct_option_index_1 - 1))

        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=question_text,
            options=opts[:4],
            type="quiz",
            correct_option_id=correct_idx0,
            is_anonymous=False,
            open_period=ARENA_GROUP_POLL_SECONDS,
        )

        ev = asyncio.Event()
        arena_group_poll_map[poll_msg.poll.id] = {"event": ev, "chosen": None}

        try:
            await asyncio.wait_for(ev.wait(), timeout=ARENA_GROUP_POLL_SECONDS + 1.0)
        except Exception:
            pass

        meta = arena_group_poll_map.pop(poll_msg.poll.id, None) or {}
        chosen = meta.get("chosen")

        try:
            await bot.delete_message(chat_id, poll_msg.message_id)
        except Exception:
            pass

        if chosen is None:
            unanswered_count += 1
            continue

        selected_idx0 = int(chosen)
        if selected_idx0 == correct_idx0:
            correct_count += 1
        else:
            wrong_count += 1

    ratio = (correct_count / total) if total else 0.0
    reward = float(
        reward_fn(
            correct_count=correct_count,
            wrong_count=wrong_count,
            unanswered_count=unanswered_count,
            ratio=ratio,
        )
    )

    if reward > 0:
        add_dpoints(user["id"], reward, subject, change_type=f"arena_{mode}_reward")

    await bot.send_message(
        chat_id,
        t(
            detect_lang_from_user(user),
            "arena_result_summary",
            mode=mode.upper(),
            total=total,
            correct=correct_count,
            wrong=wrong_count,
            unanswered=unanswered_count,
            reward=f"{reward:.1f}",
        ),
    )


async def _run_arena_quiz_with_questions(
    *,
    chat_id: int,
    user: dict,
    subject: str,
    mode: str,
    questions: list[dict],
) -> dict:
    """Run the poll-based quiz on provided questions, without applying any reward."""
    lang = detect_lang_from_user(user)
    correct_count = 0
    wrong_count = 0
    unanswered_count = 0

    total = len(questions)
    for idx, q in enumerate(questions, start=1):
        question_text = f"{t(lang, 'arena_question_title', num=idx)}\n{str(q.get('question') or '').strip()}"
        opts = [
            str(q.get("option_a") or ""),
            str(q.get("option_b") or ""),
            str(q.get("option_c") or ""),
            str(q.get("option_d") or ""),
        ]
        correct_option_index_1 = int(q.get("correct_option_index") or 1)
        correct_idx0 = max(0, min(3, correct_option_index_1 - 1))

        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=question_text,
            options=opts[:4],
            type="quiz",
            correct_option_id=correct_idx0,
            is_anonymous=False,
            open_period=DUEL_POLL_SECONDS,
        )

        ev = asyncio.Event()
        arena_group_poll_map[poll_msg.poll.id] = {"event": ev, "chosen": None}

        try:
            await asyncio.wait_for(ev.wait(), timeout=DUEL_POLL_SECONDS + 1.0)
        except Exception:
            pass

        meta = arena_group_poll_map.pop(poll_msg.poll.id, None) or {}
        chosen = meta.get("chosen")

        try:
            await bot.delete_message(chat_id, poll_msg.message_id)
        except Exception:
            pass

        if chosen is None:
            unanswered_count += 1
            continue

        selected_idx0 = int(chosen)
        if selected_idx0 == correct_idx0:
            correct_count += 1
        else:
            wrong_count += 1

    await bot.send_message(
        chat_id,
        t(
            lang,
            "duel_result_summary",
            mode=mode.upper(),
            total=total,
            correct=correct_count,
            wrong=wrong_count,
            unanswered=unanswered_count,
        ),
    )

    return {
        "correct": correct_count,
        "wrong": wrong_count,
        "unanswered": unanswered_count,
    }


async def _start_duel_match(
    *,
    mode: str,
    players: list[dict],  # {user: dict, chat_id: int}
    subject: str,
    level: str,
    question_count: int,
) -> None:
    if not players:
        return
    
    session_id = int(players[0].get("session_id") or 0)
    
    # Validate session is in correct state
    if session_id:
        sess = get_duel_session(session_id)
        if not sess or str(sess.get("status") or "").strip().lower() != "running":
            logger.warning(f"Duel session {session_id} not in running state, aborting match start")
            return
    
    for p in players:
        try:
            plang = detect_lang_from_user(p.get("user") or {})
            await bot.send_message(
                p["chat_id"],
                t(plang, "duel_started_sending_questions"),
            )
        except Exception:
            pass
    
    # Check if questions already exist for this session (avoid regeneration)
    existing_questions = None
    if session_id:
        try:
            from db import fetch_duel_questions_for_session
            existing_questions = fetch_duel_questions_for_session(session_id, mode=mode)
        except Exception:
            logger.exception("Failed to fetch existing duel questions")
    
    if existing_questions and len(existing_questions) >= question_count:
        questions = existing_questions[:question_count]
    else:
        # Lightweight progress updates while AI pipeline runs.
        for pct in (10, 35, 65):
            for p in players:
                try:
                    plang = detect_lang_from_user(p.get("user") or {})
                    await bot.send_message(
                        p["chat_id"],
                        t(plang, "duel_preparing_progress", mode=mode.upper(), percent=pct),
                    )
                except Exception:
                    pass
        # Generate ONE shared set of questions for the duel.
        generator_user_id = players[0]["user"]["id"]
        questions = await _generate_arena_questions_via_daily_generator(
            user_id=generator_user_id,
            subject=subject,
            level=level,
            count=question_count,
        )
    if not questions:
        for p in players:
            try:
                plang = detect_lang_from_user(p.get("user") or {})
                await bot.send_message(p["chat_id"], t(plang, "duel_questions_not_found"))
            except Exception:
                pass
        return

    # Snapshot duel questions into tmp pool for delayed promotion.
    try:
        from db import insert_duel_questions_tmp

        session_id = int(players[0].get("session_id") or 0)
        insert_duel_questions_tmp(mode=mode, session_id=session_id, questions=questions, level=level)
    except Exception:
        logger.exception("insert_duel_questions_tmp failed session_id=%s", players[0].get("session_id"))

    for p in players:
        try:
            plang = detect_lang_from_user(p.get("user") or {})
            await bot.send_message(
                p["chat_id"],
                t(plang, "duel_preparing_progress", mode=mode.upper(), percent=100),
            )
        except Exception:
            pass

    # Run quizzes concurrently for all players.
    tasks = [
        _run_arena_quiz_with_questions(
            chat_id=p["chat_id"],
            user=p["user"],
            subject=subject,
            mode=mode,
            questions=questions,
        )
        for p in players
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    scored: list[tuple[dict, int, int]] = []  # (player_item, correct, wrong)
    for p, r in zip(players, results):
        if isinstance(r, Exception):
            continue
        scored.append((p, int(r.get("correct") or 0), int(r.get("wrong") or 0)))

    if not scored:
        return

    winner_ids: list[int] = []
    participant_rows = list_duel_participants(int(players[0].get("session_id") or 0)) if players[0].get("session_id") else []
    team_map = {int(r["user_id"]): int(r.get("team_no") or 1) for r in participant_rows}
    if mode == "5v5":
        # True 5v5: pick winner team by total correct; tie-break by total wrong.
        teams: dict[int, dict[str, int]] = {}
        for p, c, w in scored:
            uid = int(p["user"]["id"])
            tno = int(team_map.get(uid, 1))
            teams.setdefault(tno, {"correct": 0, "wrong": 0})
            teams[tno]["correct"] += c
            teams[tno]["wrong"] += w
        if teams:
            best_team = sorted(teams.items(), key=lambda x: (-x[1]["correct"], x[1]["wrong"]))[0][0]
            winner_ids = [int(p["user"]["id"]) for p, _, _ in scored if int(team_map.get(int(p["user"]["id"]), 1)) == int(best_team)]
    else:
        # 1v1 winner by: max correct, then min wrong.
        max_correct = max(c for _, c, _ in scored)
        best = [t for t in scored if t[1] == max_correct]
        min_wrong = min(w for _, _, w in best)
        winners = [t for t in best if t[2] == min_wrong]
        winner_ids = [t[0]["user"]["id"] for t in winners]

    # Apply rewards (1v1 winners +10, 5v5 winning team members +5).
    for p in players:
        uid = p["user"]["id"]
        plang = detect_lang_from_user(p.get("user") or {})
        stats = next((x for x in scored if int(x[0]["user"]["id"]) == int(uid)), None)
        corr = int(stats[1]) if stats else 0
        wrg = int(stats[2]) if stats else 0
        unans = 10 - corr - wrg
        opponent_uid = None
        if mode == "1v1" and len(players) == 2:
            opponent_uid = int(players[0]["user"]["id"] if int(players[1]["user"]["id"]) == int(uid) else players[1]["user"]["id"])
        save_duel_participant_result(
            int(p.get("session_id") or 0),
            int(uid),
            correct=corr,
            wrong=wrg,
            unanswered=max(0, unans),
            is_winner=uid in winner_ids,
            last_opponent_user_id=opponent_uid,
        )
        if uid in winner_ids:
            duel_reward = 5.0
            add_dpoints(uid, duel_reward, subject, change_type="duel_win")
            try:
                process_duel_win_streak_bonus(int(uid), subject, _today_tashkent())
            except Exception:
                pass
            try:
                await bot.send_message(p["chat_id"], t(plang, "duel_win_reward", reward=int(duel_reward)))
            except Exception:
                pass
        else:
            try:
                await bot.send_message(p["chat_id"], t(plang, "duel_finished_try_again"))
            except Exception:
                pass
        if mode == "1v1" and opponent_uid:
            exp = (_now_tashkent() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
            create_revenge_token(int(uid), int(opponent_uid), mode, subject, exp)
            revenge_url = _student_miniapp_url(
                "duel-1v1",
                extra={"arena_mode": "duel-1v1", "auto_join": 1, "subject": subject},
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=t(plang, "duel_revenge_btn"), web_app=WebAppInfo(url=revenge_url))]
                ]
            ) if revenge_url else None
            try:
                await bot.send_message(p["chat_id"], t(plang, "duel_revenge_hint"), reply_markup=kb)
            except Exception:
                pass
    if players[0].get("session_id"):
        mark_duel_session_finished(int(players[0]["session_id"]))


async def _enqueue_duel_player_and_maybe_start(
    *,
    mode: str,
    user: dict,
    chat_id: int,
    subject: str,
    level: str,
    session_id: int | None = None,
) -> None:
    ensure_duel_matchmaking_schema()
    required = 2 if mode == "1v1" else 10
    refund_subj = (subject or "English").strip().title()

    if session_id is not None:
        sess_row = get_duel_session(int(session_id))
        if not sess_row:
            add_dcoins(int(user["id"]), 3.0, refund_subj, change_type="duel_refund")
            lang = detect_lang_from_user(user)
            await bot.send_message(chat_id, t(lang, "duel_session_not_found"))
            return
        # Check if session is already running or finished
        sess_status = str(sess_row.get("status") or "").strip().lower()
        if sess_status in ("running", "finished", "canceled"):
            add_dcoins(int(user["id"]), 3.0, refund_subj, change_type="duel_refund")
            lang = detect_lang_from_user(user)
            await bot.send_message(chat_id, t(lang, "duel_already_started"))
            return
        if sess_status != "open":
            add_dcoins(int(user["id"]), 3.0, refund_subj, change_type="duel_refund")
            return
        mode = str(sess_row.get("mode") or mode).strip()
        subj = str(sess_row.get("subject") or subject or "").strip().title()
        lvl = _normalize_arena_level(sess_row.get("level") or level)
        open_session = dict(sess_row)
    else:
        subj = (subject or "").strip().title()
        lvl = _normalize_arena_level(level)
        # Match existing pending session by mode+subject first (level can differ).
        open_session = _pick_open_duel_session_for_join(mode, user, subj)
        if not open_session:
            expires_at = (_now_tashkent() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
            sid = create_duel_session(mode, subj, lvl, int(user["id"]), required, expires_at)
            join_duel_session(sid, int(user["id"]), int(chat_id), team_no=1)
            lang = detect_lang_from_user(user)
            remaining = max(0, required - 1)
            open_text = t(
                lang,
                "duel_arena_opened",
                mode=mode.upper(),
                joined=1,
                need=required,
                remaining=remaining,
            )
            await bot.send_message(chat_id, open_text)

            def _open_txt(r: dict) -> str:
                lg = (r.get("language") or "uz").strip()[:5] or "uz"
                return t(
                    lg,
                    "duel_arena_opened",
                    mode=mode.upper(),
                    joined=1,
                    need=required,
                    remaining=remaining,
                )

            def _open_kb(r: dict) -> InlineKeyboardMarkup:
                lg = (r.get("language") or "uz").strip()[:5] or "uz"
                section = "duel-1v1" if mode == "1v1" else "duel-5v5"
                join_url = _student_miniapp_url(
                    section,
                    extra={"arena_mode": section, "auto_join": 1, "subject": subj},
                )
                return InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=t(lg, "duel_join_btn"),
                                web_app=WebAppInfo(url=join_url),
                            )
                        ]
                    ]
                ) if join_url else None

            _notify_students_for_subject_mapped(subj, _open_txt, _open_kb)
            return

    sid = int(open_session["id"])
    current_count = count_duel_participants(sid)
    if current_count >= required:
        add_dcoins(int(user["id"]), 3.0, subj, change_type="duel_refund")
        ulang = detect_lang_from_user(user)
        section = "duel-1v1" if mode == "1v1" else "duel-5v5"
        full_url = _student_miniapp_url(
            section,
            extra={"arena_mode": section, "auto_join": 1, "subject": subj},
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(ulang, "duel_room_full_try_new_btn"),
                        web_app=WebAppInfo(url=full_url),
                    )
                ]
            ]
        ) if full_url else None
        await bot.send_message(
            chat_id,
            t(ulang, "duel_room_full_create_new", mode=mode.upper()),
            reply_markup=kb,
        )
        return
    team_no = 1
    if mode == "5v5":
        team_no = 1 if current_count < 5 else 2
    before_join = count_duel_participants(sid)
    join_duel_session(sid, int(user["id"]), int(chat_id), team_no=team_no)
    joined = count_duel_participants(sid)
    joined_new = joined > before_join
    created_by = int(open_session.get("created_by_user_id") or 0)
    if joined_new and created_by and int(user["id"]) != created_by:
        creator = get_user_by_id(created_by)
        if creator and creator.get("telegram_id"):
            cl = detect_lang_from_user(creator)
            jn = " ".join(
                filter(
                    None,
                    [
                        (user.get("first_name") or "").strip(),
                        (user.get("last_name") or "").strip(),
                    ],
                )
            ).strip() or str(user.get("login_id") or "?")
            try:
                await bot.send_message(
                    int(creator["telegram_id"]),
                    t(
                        cl,
                        "duel_creator_opponent_joined",
                        joiner_name=jn,
                        mode=mode.upper(),
                        subject=subj,
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
    lang = detect_lang_from_user(user)
    remaining = max(0, required - joined)
    prog = t(
        lang,
        "duel_waiting_progress",
        mode=mode.upper(),
        joined=joined,
        need=required,
        remaining=remaining,
    )
    await bot.send_message(chat_id, prog)

    def _prog_txt(r: dict) -> str:
        lg = (r.get("language") or "uz").strip()[:5] or "uz"
        return t(
            lg,
            "duel_waiting_progress",
            mode=mode.upper(),
            joined=joined,
            need=required,
            remaining=remaining,
        )

    def _prog_kb(r: dict) -> InlineKeyboardMarkup:
        lg = (r.get("language") or "uz").strip()[:5] or "uz"
        section = "duel-1v1" if mode == "1v1" else "duel-5v5"
        join_url = _student_miniapp_url(
            section,
            extra={"arena_mode": section, "auto_join": 1, "subject": subj},
        )
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lg, "duel_join_btn"),
                        web_app=WebAppInfo(url=join_url),
                    )
                ]
            ]
        ) if join_url else None

    _notify_students_for_subject_mapped(subj, _prog_txt, _prog_kb)
    if joined >= required:
        # Double-check session status to prevent race condition
        sess_check = get_duel_session(sid)
        if sess_check and str(sess_check.get("status") or "").strip().lower() != "open":
            # Session already started by another thread
            return
        
        mark_duel_session_started(sid)
        parts = list_duel_participants(sid)
        
        # Validate we actually have enough participants
        if len(parts) < required:
            logger.warning(f"Duel session {sid} started with insufficient participants: {len(parts)} < {required}")
            return
        
        players = []
        for p in parts[:required]:
            u = get_user_by_id(int(p["user_id"]))
            if not u:
                continue
            players.append({"user": u, "chat_id": int(p["chat_id"]), "session_id": sid, "team_no": int(p.get("team_no") or 1)})
        
        # Validate we have enough valid players
        if len(players) < required:
            logger.warning(f"Duel session {sid}: Not enough valid players {len(players)} < {required}")
            return
            
        asyncio.create_task(
            _start_duel_match(
                mode=mode,
                players=players,
                subject=subj,
                level=lvl,
                question_count=10,
            )
        )


@dp.callback_query(lambda c: c.data.startswith("arena_join_subject:"))
async def handle_arena_join_subject(callback: CallbackQuery):
    # Backward compatibility for old inline buttons.
    try:
        _, mode, _ = callback.data.split(":", 2)
    except Exception:
        await callback.answer()
        return
    callback.data = f"arena_enter_duel_{mode}"
    await handle_arena_join(callback)


@dp.callback_query(lambda c: c.data == 'student_subject_settings')
async def handle_student_subject_settings(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    user_subjects = get_user_subjects(user['id'])
    subj_line = ', '.join(user_subjects) if user_subjects else '-'
    await callback.message.answer(
        t(lang, "student_current_subjects_ask_prompt", subjects=subj_line),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'subject_add_btn'), callback_data='student_add_subject')],
            [InlineKeyboardButton(text=t(lang, 'subject_delete_btn'), callback_data='student_delete_subject')],
            [InlineKeyboardButton(text=t(lang, 'btn_back_inline'), callback_data='student_subject_settings_back')],
        ])
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == 'student_add_subject')
async def handle_student_add_subject(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        return
    
    # Show inline buttons for subject selection
    await callback.message.answer(
        t(lang, 'which_subject_add'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'subject_english_btn'), callback_data='student_add_subject_English')],
            [InlineKeyboardButton(text=t(lang, 'subject_russian_btn'), callback_data='student_add_subject_Russian')],
            [InlineKeyboardButton(text=t(lang, 'back_btn_inline'), callback_data='student_subject_settings')],
        ])
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == 'student_delete_subject')
async def handle_student_delete_subject(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        return
    
    user_subjects = get_user_subjects(user['id'])
    if not user_subjects:
        await callback.message.answer(t(lang, 'no_subjects_assigned'))
        await callback.answer()
        return
    
    # Create inline buttons for each subject
    keyboard_rows = []
    for subject in user_subjects:
        keyboard_rows.append([InlineKeyboardButton(text=f'➖ {subject}', callback_data=f'student_delete_subject_{subject}')])
    keyboard_rows.append([InlineKeyboardButton(text=t(lang, 'back_btn_inline'), callback_data='student_subject_settings')])
    
    await callback.message.answer(
        t(lang, 'which_subject_delete'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_rows)
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data == 'student_subject_settings_back')
async def handle_student_subject_settings_back(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    await callback.message.answer(t(lang, 'select_from_menu'), reply_markup=student_main_keyboard(lang))
    reset_student_state(callback.message.chat.id)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith('student_add_subject_'))
async def handle_student_add_subject_specific(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        return
    
    subject = callback.data.split('_', 3)[-1]  # Get the subject name
    user_subjects = get_user_subjects(user['id'])
    
    if subject in user_subjects:
        await callback.message.answer(t(lang, 'subject_already_exists'))
    elif len(user_subjects) >= 12:
        await callback.message.answer(t(lang, 'max_subjects_reached'))
    else:
        user_subjects.append(subject)
        update_user_subjects(user['id'], user_subjects)
        await callback.message.answer(t(lang, 'subject_added_success', subject=subject))
    
    # Go back to subject settings
    await handle_student_subject_settings(callback)
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith('student_delete_subject_'))
async def handle_student_delete_subject_specific(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer()
        return
    
    subject = callback.data.split('_', 3)[-1]  # Get the subject name
    user_subjects = get_user_subjects(user['id'])

    # If subject exists only because the user belongs to groups with that subject,
    # deleting only users.subject will not remove it from profile.
    # Remove user from all groups having this subject, then update users.subject CSV.
    if subject not in user_subjects:
        await callback.message.answer(t(lang, 'subject_not_assigned_to_user'))
    else:
        groups = get_user_groups(user['id'])
        to_remove = [g['id'] for g in groups if (g.get('subject') or '').strip() == subject]
        for gid in to_remove:
            try:
                remove_user_from_group(user['id'], gid)
            except Exception:
                logger.exception("Failed removing user from group during subject delete user_id=%s group_id=%s", user['id'], gid)

        # Recalculate after group removals and persist CSV without the subject.
        updated_subjects = get_user_subjects(user['id'])
        updated_subjects = [s for s in updated_subjects if (s or '').strip() != subject]
        update_user_subjects(user['id'], updated_subjects)

        await callback.message.answer(t(lang, 'subject_deleted_success', subject=subject))
    
    # Go back to subject settings
    await handle_student_subject_settings(callback)
    await callback.answer()




async def show_subject_selection_for_search(chat_id: int, user: dict, user_subjects: list):
    """Show subject selection specifically for vocabulary search"""
    lang = detect_lang_from_user(user)
    
    keyboard = []
    for subject in user_subjects:
        keyboard.append([InlineKeyboardButton(
            text=_subject_button_text(lang, subject),
            callback_data=f"vocab_search_subject:{subject}"
        )])
    
    await bot.send_message(
        chat_id, 
        t(lang, 'search_choose_subject_title'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


async def show_subject_selection(chat_id: int, user: dict, callback_data_prefix: str):
    """Show subject selection for students with multiple subjects"""
    lang = detect_lang_from_user(user)
    user_subjects = get_user_subjects(user['id'])
    
    if len(user_subjects) <= 1:
        # If only one subject, proceed directly
        subject = user_subjects[0] if user_subjects else 'English'
        await handle_subject_selection(chat_id, user, subject, callback_data_prefix)
        return
    
    # Create keyboard for subject selection
    keyboard = []
    for subject in user_subjects:
        keyboard.append([InlineKeyboardButton(
            text=_subject_button_text(lang, subject),
            callback_data=f"{callback_data_prefix}:{subject}"
        )])
    
    await bot.send_message(
        chat_id, 
        t(lang, 'choose_subject_continue_title'),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


async def handle_subject_selection(chat_id: int, user: dict, subject: str, callback_data_prefix: str):
    """Handle subject selection and proceed with the original action"""
    # Store selected subject in user state for this session
    user_subject_state = f"{user['id']}_current_subject"
    placement_state[user_subject_state] = subject
    
    # Proceed based on the callback data prefix
    if callback_data_prefix == "grammar_rules":
        # For Russian grammar go directly to topics list (default level A1),
        # for other subjects keep existing level-selection flow.
        if (subject or "").strip().lower() == "russian":
            await _render_topics(chat_id, user, "A1")
        else:
            await show_grammar_levels(chat_id, user)
    elif callback_data_prefix == "vocab_quiz":
        await cmd_vocab_quiz_with_subject(chat_id, user, subject)
    # Add more cases as needed


@dp.callback_query(lambda c: c.data == "menu_grammar")
async def menu_grammar(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return

    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    await _send_test_redirect(
        callback.message.chat.id,
        lang,
        section="grammar",
        title="Grammar bo'limi Mini App ichida ochiladi.",
        label="📱 Grammarni Ochish",
        extra=extra,
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("grammar_level_"))
async def handle_grammar_level_legacy(callback: CallbackQuery):
    """Eski inline menyudan — grammar_content bo'yicha sahifalangan mavzular (gr_topic_*)."""
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    level = callback.data.split("_")[-1].upper()
    await callback.message.edit_text(
        t(lang, 'grammar_legacy_topics_pick', level=level),
        reply_markup=get_paginated_topics_keyboard(level, page=0, lang=lang),
    )
    await callback.answer()


@dp.callback_query(lambda c: c.data.startswith("grammar_topic_"))
async def handle_grammar_topic_legacy(callback: CallbackQuery):
    """Eski grammar_topic_<level>_... — qisman gr_topic_page va gr_topic_pick ga yo'naltiriladi."""
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return

    parts = callback.data.split("_")
    # grammar_topic_page_{level}_{page}
    if len(parts) >= 5 and parts[2] == "page":
        level = parts[3].upper()
        page = int(parts[4])
        await callback.message.edit_text(
            t(lang, 'grammar_legacy_topics_pick_page', level=level, page=page + 1),
            reply_markup=get_paginated_topics_keyboard(level, page=page, lang=lang),
        )
        await callback.answer()
        return

    # grammar_topic_{level}_{global_index}
    if len(parts) < 4:
        await callback.answer(t(lang, 'invalid_button'), show_alert=True)
        return
    level = parts[2].upper()
    topic_index = int(parts[3])
    topics = get_topics_by_level(level)
    if topic_index >= len(topics):
        await callback.answer(t(lang, 'grammar_topic_not_found_alert'), show_alert=True)
        return
    topic = topics[topic_index]
    await _show_topic(callback.message.chat.id, user, level, topic.topic_id)
    await callback.answer()


async def cmd_vocab_quiz_with_subject(chat_id: int, user: dict, subject: str):
    """Tanlangan fan bo'yicha vocab quiz boshlash (cmd_vocab_quiz bilan bir xil oq)."""
    from vocabulary import get_student_preference

    lang = detect_lang_from_user(user)
    subjects = get_student_subjects(user['id'])
    selected_subject = (subject or "").strip() or (subjects[0] if subjects else 'English')

    state = get_vocab_state(chat_id)
    state['data'] = dict(state.get('data') or {})
    state['data']['subject_override'] = selected_subject
    state['data']['quiz_subject'] = selected_subject

    pref = get_student_preference(user['id'])
    if pref not in ('uz', 'ru'):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'vocab_pref_btn_uz'), callback_data="vocab_pref_uz")],
            [InlineKeyboardButton(text=t(lang, 'vocab_pref_btn_ru'), callback_data="vocab_pref_ru")],
        ])
        await bot.send_message(chat_id, t(lang, 'vocab_choose_language'), reply_markup=kb)
        return
    kb = _vocab_quiz_type_keyboard(lang)
    subj_h = html_module.escape(selected_subject)
    await bot.send_message(
        chat_id,
        t(lang, "vocab_quiz_subject_prefix", subject=subj_h)
        + t(lang, 'vocab_choose_type')
        + "\n\n"
        + t(lang, 'vocab_choose_type_explain'),
        reply_markup=kb,
        parse_mode="HTML",
    )


@dp.callback_query(lambda c: c.data == 'logout_me')
async def handle_logout_me(callback: CallbackQuery):
    from db import logout_user_by_telegram
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    logout_user_by_telegram(str(callback.from_user.id))
    # Force Mini App/web sessions to expire when user logs out from bot.
    conn = None
    try:
        uid = int((user or {}).get("id") or 0)
        if uid > 0:
            conn = get_conn()
            cur = conn.cursor()
            now_iso = dt.utcnow().isoformat()
            cur.execute(
                "UPDATE users SET session_version=COALESCE(session_version, 1)+1 WHERE id=?",
                (uid,),
            )
            cur.execute(
                """
                UPDATE web_user_sessions
                SET revoked_at=?,
                    revoked_reason=?
                WHERE user_id=?
                  AND revoked_at IS NULL
                """,
                (now_iso, "bot_logout", uid),
            )
            conn.commit()
    except Exception:
        logger.exception("Failed to revoke web sessions on bot logout user_id=%s", (user or {}).get("id"))
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    clear_login_state(callback.message.chat.id)
    reset_placement_state(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(t(lang, 'logged_out'), reply_markup=ReplyKeyboardRemove())


@dp.callback_query(lambda c: c.data == 'get_my_otp')
async def handle_get_my_otp(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True)
        return

    lang = detect_lang_from_user(user)

    import random
    import string
    from db import reset_user_password
    otp_code = "".join(random.choices(string.digits, k=6))
    reset_user_password(int(user["id"]), otp_code)

    message_text = {
        'uz': f"Sizning bir martalik kirish parolingiz (OTP):\n\n<code>{otp_code}</code>\n\nUshbu kodni saytga kirishda ishlating. Kirganingizdan so'ng parol o'zgaradi va uni qayta ishlatib bo'lmaydi.",
        'ru': f"Ваш одноразовый пароль (OTP):\n\n<code>{otp_code}</code>\n\nИспользуйте этот код для входа на сайт. После входа пароль изменится и его нельзя будет использовать повторно.",
        'en': f"Your One-Time Password (OTP):\n\n<code>{otp_code}</code>\n\nUse this code to log in to the site. The password will change after login and cannot be reused.",
    }.get(lang, f"Your One-Time Password (OTP):\n\n<code>{otp_code}</code>")

    await callback.message.answer(message_text, parse_mode="HTML")
    await callback.answer()


async def start_placement_test(chat_id: int, override_subject: str = None):
    """Start placement test for the specified subject"""
    user = get_user_by_telegram(str(chat_id))
    if not user:
        return
    
    logger.debug('start_placement_test called user=%s chat_id=%s override_subject=%s', user, chat_id, override_subject)
    lang = detect_lang_from_user(user)
    
    # Use the provided subject or user's subject
    subject = (override_subject or user.get('subject') or '').strip().title()
    
    # Validate subject
    if subject not in ['English', 'Russian']:
        await bot.send_message(chat_id, t(lang, 'subject_not_set'))
        return
    
    if not subject:
        logger.warning('start_placement_test: user has no subject user=%s', user['id'])
        await bot.send_message(chat_id, t(lang, 'subject_not_set'))
        return

    ps = get_placement_state(chat_id)
    logger.debug('placement_state before init: %s', ps)
    if ps.get('active'):
        logger.info('Test already active for user %s', chat_id)
        await bot.send_message(chat_id, t(lang, 'test_already_active'))
        return

    questions = get_tests_by_subject(subject)
    logger.debug('Loaded %s questions for subject %s', len(questions), subject)
    if not questions:
        await bot.send_message(chat_id, t(lang, 'no_questions_for_subject', subject=subject))
        return

    ps.update({
        'active': True,
        'user_id': user['id'],
        'subject': subject,
        'question_index': 0,
        'score': 0,
        'questions': [q['id'] for q in questions],
        'poll_map': {},
    })
    save_placement_session(user['id'], {
        'active': True,
        'subject': subject,
        'question_index': 0,
        'score': 0,
        'questions': [q['id'] for q in questions],
    })
    await bot.send_message(
        chat_id,
        t(
            lang,
            "placement_test_progress",
            subject=subject,
            title=t(lang, "placement_test_starting").rstrip("."),
            current=1,
            total=len(ps["questions"]),
        ),
    )
    try:
        await send_next_question(chat_id)
    except Exception:
        logger.exception('Test savol yuborishda xatolik yuz berdi')
        await bot.send_message(chat_id, t(lang, 'test_send_error'))


async def send_next_question(chat_id):
    key = str(chat_id)
    ps = get_placement_state(key)
    logger.debug('send_next_question called chat_id=%s key=%s ps=%s', chat_id, key, ps)
    user_for_lang = get_user_by_telegram(str(chat_id))
    lang = detect_lang_from_user(user_for_lang or {})
    if not ps.get('active'):
        user = get_user_by_telegram(str(chat_id))
        if user:
            session = get_placement_session(user['id'])
            if session and session.get('active'):
                ps.update({
                    'active': True,
                    'subject': session['subject'],
                    'question_index': session['question_index'],
                    'score': session['score'],
                    'questions': session['questions'],
                    'poll_map': {},
                })
                logger.info('Resumed placement session from DB for chat %s', chat_id)
            else:
                logger.info('send_next_question: placement not active for chat %s', chat_id)
                return
        else:
            logger.info('send_next_question: placement not active for chat %s', chat_id)
            return

    idx = ps.get('question_index', 0)
    if idx >= len(ps.get('questions', [])):
        logger.info('send_next_question: question_index out of range %s >= %s', idx, len(ps.get('questions', [])))
        return

    q_id = ps['questions'][idx]
    question = get_test_by_id(q_id)
    if not question:
        logger.error('send_next_question: test question not found id=%s', q_id)
        await bot.send_message(chat_id, t(lang, 'question_not_found'))
        return

    options = [question['option_a'], question['option_b'], question['option_c'], question['option_d']]
    if len(options) != 4 or any(opt is None or opt == '' for opt in options):
        logger.error('send_next_question: invalid options for question id=%s options=%s', q_id, options)
        await bot.send_message(chat_id, t(lang, 'question_options_incomplete'))
        return

    correct_option = question.get('correct_option', '').strip().upper()
    if correct_option not in 'ABCD':
        logger.error('send_next_question: noto‘g‘ri correct_option for question id=%s: %s', q_id, correct_option)
        await bot.send_message(chat_id, t(lang, 'question_correct_option_error'))
        return

    correct_index = 'ABCD'.index(correct_option)
    poll_question = f"{idx + 1}/{len(ps['questions'])} - {question['question']}\n\nVariantlar:"
    
    # Send timer message first
    timer_msg = await bot.send_message(chat_id, t(lang, "student_quiz_30s_instruction"))
    
    msg = None
    for attempt in range(2):
        try:
            msg = await bot.send_poll(
                chat_id=chat_id,
                question=poll_question,
                options=options,
                type='quiz',
                correct_option_id=correct_index,
                is_anonymous=False,
                open_period=30,  # 30-second timer
            )
            break
        except Exception:
            if attempt == 0:
                await asyncio.sleep(0.4)
                continue
            logger.exception('send_next_question: bot.send_poll failed for chat=%s q_id=%s', chat_id, q_id)
            try:
                await bot.delete_message(chat_id, timer_msg.message_id)
            except Exception:
                pass
            user = get_user_by_telegram(str(chat_id))
            if user:
                clear_placement_session(user['id'])
            reset_placement_state(chat_id)
            await bot.send_message(chat_id, t(lang, 'placement_poll_send_failed'))
            return

    if msg is None:
        return

    poll_id = msg.poll.id
    ps['poll_map'][poll_id] = {
        'question_id': q_id,
        'correct_option': correct_index,
    }
    asyncio.create_task(auto_advance_question_if_no_answer(chat_id, poll_id, 31))

    try:
        await bot.delete_message(chat_id, timer_msg.message_id)
    except Exception:
        pass


async def auto_advance_question_if_no_answer(chat_id: int, poll_id: int, delay: int):
    """Agar foydalanuvchi vaqt ichida javob bermasa, keyingi savolga o'tadi"""
    await asyncio.sleep(delay)

    ps = get_placement_state(str(chat_id))
    if not ps.get('active'):
        return
    if poll_id not in ps.get('poll_map', {}):
        return

    ps['poll_map'].pop(poll_id, None)
    user = get_user_by_telegram(str(chat_id))
    if not user:
        return
    lang = detect_lang_from_user(user)
    await bot.send_message(chat_id, t(lang, "student_quiz_time_up_next"))

    ps['question_index'] += 1
    save_placement_session(user['id'], {
        'active': True,
        'subject': ps['subject'],
        'question_index': ps['question_index'],
        'score': ps['score'],
        'questions': ps['questions'],
    })

    if ps['question_index'] >= len(ps['questions']):
        await finish_placement_test(user, chat_id)
    else:
        await send_next_question(chat_id)


@dp.callback_query(lambda c: c.data == 'start_test')
async def handle_start_test(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user:
        lang = detect_lang_from_user(callback.from_user)
        await callback.answer(t(lang, 'not_registered'))
        return
    lang = detect_lang_from_user(user)
    kb = _placement_launch_keyboard(user, lang)
    if kb:
        await callback.answer()
        await callback.message.answer(
            "Daraja testini boshlash uchun pastdagi tugmani bosing. FaceID olinmagan bo'lsa avval FaceID ochiladi.",
            reply_markup=kb,
        )
        return
    await callback.answer(t(lang, 'test_starting'))


@dp.callback_query(lambda c: c.data.startswith('start_test_'))
async def handle_start_test_subject(callback: CallbackQuery):
    """
    Handle dual-subject placement test start (e.g. start_test_English).
    This is used when a student has 2 subjects and we ask which language to start.
    """
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user:
        await callback.answer(t(lang, 'not_registered'))
        return

    subject = callback.data.split('start_test_', 1)[-1].strip().title()
    if subject not in ('English', 'Russian'):
        await callback.answer()
        return

    kb = _placement_launch_keyboard(user, lang)
    if kb:
        await callback.answer()
        await callback.message.answer(
            f"{subject} bo'yicha daraja testini boshlash uchun pastdagi tugmani bosing.",
            reply_markup=kb,
        )
        return
    await callback.answer(t(lang, 'test_starting'))


@dp.callback_query(lambda c: c.data == 'daily_test_start')
async def handle_daily_test_start(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return
    await callback.answer()
    subject_candidates = get_student_subjects(user["id"]) or []
    extra: dict[str, object] = {"auto_join": 1}
    if len(subject_candidates) == 1:
        extra["subject"] = subject_candidates[0]
    kb = _miniapp_open_keyboard(t(lang, "daily_test_start_btn"), "daily-test-process", extra=extra)
    if not kb:
        await callback.message.answer(t(lang, "error_with_reason", error="MiniApp URL is not configured"))
        return
    await callback.message.answer(
        t(lang, "daily_test_menu_title") + "\n\n" + t(lang, "daily_test_menu_start_hint"),
        reply_markup=kb,
    )


@dp.callback_query(lambda c: c.data.startswith("daily_test:"))
async def handle_daily_test_subject_callbacks(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return

    subject = callback.data.split(":", 1)[1].strip().title()
    if subject not in ("English", "Russian"):
        await callback.answer()
        return
    await callback.answer()
    kb = _miniapp_open_keyboard(
        t(lang, "daily_test_start_btn"),
        "daily-test-process",
        extra={"auto_join": 1, "subject": subject},
    )
    if not kb:
        await callback.message.answer(t(lang, "error_with_reason", error="MiniApp URL is not configured"))
        return
    await callback.message.answer(
        t(lang, "daily_test_menu_title") + "\n\n" + t(lang, "daily_test_menu_start_hint"),
        reply_markup=kb,
    )


@dp.callback_query(lambda c: c.data == 'student_daily_test_back_to_main')
async def handle_student_daily_test_back_to_main(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, 'please_send_start'))
        return

    await callback.answer()
    await callback.message.answer(t(lang, 'select_from_menu'), reply_markup=student_main_keyboard(lang))


async def _run_daily_test_attempt(chat_id: int, user: dict, attempt_id: int):
    import json
    from datetime import datetime as dt

    lang = detect_lang_from_user(user)

    items = get_daily_test_attempt_items(attempt_id)
    if not items:
        await bot.send_message(chat_id, t(lang, 'daily_test_not_ready'))
        return

    total = len(items)
    # Find first unanswered question (selected_option is NULL and timed_out=0).
    start_q = None
    for it in items:
        if it.get('selected_option') is None and not it.get('timed_out'):
            start_q = int(it['question_index'])
            break
    if start_q is None:
        await bot.send_message(chat_id, t(lang, 'daily_test_already_done'))
        return

    correct_count = 0
    wrong_count = 0
    unanswered_count = 0

    await bot.send_message(
        chat_id,
        t(lang, 'daily_test_intro', total=total, sec=DAILY_TEST_POLL_SECONDS),
        parse_mode="HTML",
    )

    for it in items:
        q_idx = int(it['question_index'])
        if q_idx < start_q:
            continue

        options_json = it.get('options_json') or '[]'
        try:
            options = json.loads(options_json) if isinstance(options_json, str) else options_json
        except Exception:
            options = []

        if len(options) != 4:
            # If bank row is malformed, skip and do not reward/penalize.
            unanswered_count += 1
            mark_daily_test_question_timed_out(attempt_id, q_idx)
            continue

        correct_option_index_1 = int(it.get('correct_option_index') or 1)
        correct_idx0 = max(0, min(3, correct_option_index_1 - 1))
        question_text = str(it.get('question') or '').strip()

        poll_question = f"{q_idx}/{total} — {question_text}"

        countdown_msg = await bot.send_message(
            chat_id,
            t(lang, 'daily_test_countdown_suffix', seconds=DAILY_TEST_POLL_SECONDS),
        )

        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=poll_question,
            options=[str(o)[:100] for o in options],
            type='quiz',
            correct_option_id=correct_idx0,
            is_anonymous=False,
            open_period=DAILY_TEST_POLL_SECONDS,
        )

        poll_id = poll_msg.poll.id
        ev = asyncio.Event()
        daily_poll_map[poll_id] = {
            'event': ev,
            'chosen': None,
            'attempt_id': attempt_id,
            'question_index': q_idx,
            'correct_idx0': correct_idx0,
        }

        try:
            await asyncio.wait_for(ev.wait(), timeout=DAILY_TEST_POLL_SECONDS + 1.0)
        except Exception:
            pass

        meta = daily_poll_map.pop(poll_id, None)
        chosen = meta.get('chosen') if meta else None

        if chosen is None:
            unanswered_count += 1
            mark_daily_test_question_timed_out(attempt_id, q_idx)
        else:
            selected_option = options[chosen] if 0 <= chosen < 4 else None
            is_correct = chosen == correct_idx0
            if is_correct:
                correct_count += 1
            else:
                wrong_count += 1
            mark_daily_test_question_answered(attempt_id, q_idx, selected_option, is_correct=is_correct)

        try:
            await bot.delete_message(chat_id, poll_msg.message_id)
        except Exception:
            pass
        try:
            await bot.delete_message(chat_id, countdown_msg.message_id)
        except Exception:
            pass

    # Scoring: +2 correct, -3 wrong, -1.5 skipped (unanswered/timed out)
    dpoint_reward_correct = correct_count * 2.0
    dpoint_penalty_wrong = wrong_count * -3.0
    dpoint_penalty_unanswered = unanswered_count * -1.5
    net_dpoints = dpoint_reward_correct + dpoint_penalty_wrong + dpoint_penalty_unanswered

    daily_subject = (items[0].get("subject") if items else None) or _get_selected_subject_for_user(user)
    if correct_count:
        add_dpoints(
            user['id'],
            dpoint_reward_correct,
            daily_subject,
            change_type="daily_test_correct",
        )
    if unanswered_count:
        add_dpoints(
            user['id'],
            dpoint_penalty_unanswered,
            daily_subject,
            change_type="daily_test_skipped",
        )
    if wrong_count:
        add_dpoints(
            user['id'],
            dpoint_penalty_wrong,
            daily_subject,
            change_type="daily_test_wrong",
        )
    subject_count = max(1, len(get_student_subjects(int(user["id"])) or []))
    net_dcoins = float(net_dpoints) / float(subject_count)

    finish_daily_test_attempt(
        attempt_id=attempt_id,
        correct=correct_count,
        wrong=wrong_count,
        unanswered=unanswered_count,
        net_dcoins=net_dcoins,
        net_dpoints=net_dpoints,
    )

    if total and (correct_count / total) >= 0.9:
        try:
            process_daily_activity_streak_award(
                int(user["id"]),
                daily_subject or "English",
                _today_tashkent(),
            )
        except Exception:
            pass

    # Build final detailed message (always show the same block).
    raw_first_question = str((items[0].get("question") if items else "") or "").strip()
    first_line = raw_first_question.split("\n", 1)[0].strip() if raw_first_question else ""
    test_title = first_line if first_line else t(lang, "daily_test_default_title")

    percentage = (correct_count / total * 100.0) if total else 0.0
    remaining_attempts = "0/1"  # only 1 attempt per subject/day

    current_balance = get_dcoins(user['id'], daily_subject)

    if percentage >= 80:
        compliment = t(lang, "daily_test_compliment_excellent")
    elif percentage >= 60:
        compliment = t(lang, "daily_test_compliment_good")
    elif percentage >= 40:
        compliment = t(lang, "daily_test_compliment_average")
    else:
        compliment = t(lang, "daily_test_compliment_practice")

    lines = [
        t(lang, "daily_test_results_title", title=test_title),
        "",
        t(lang, "daily_test_results_percentage", percentage=f"{percentage:.1f}"),
        t(lang, "daily_test_results_total_questions", total=total),
        t(lang, "daily_test_results_correct", count=correct_count),
        t(lang, "daily_test_results_wrong", count=wrong_count),
        t(lang, "daily_test_results_skipped", count=unanswered_count),
        t(lang, "daily_test_results_attempts_left", left=remaining_attempts),
        "",
        "💠 D'Point:",
        f"🪙 +{correct_count} × 2 = {dpoint_reward_correct:+.1f}",
        (
            f"➖ {wrong_count} × 3 = {dpoint_penalty_wrong:.1f} ({t(lang, 'daily_test_results_wrong_label')})"
            if wrong_count
            else f"➖ 0 × 3 = {0.0:.1f} ({t(lang, 'daily_test_results_wrong_label')})"
        ),
    ]
    if unanswered_count:
        lines.append(f"➖ {unanswered_count} × 1.5 = {dpoint_penalty_unanswered:.1f} ({t(lang, 'daily_test_results_skipped_label')})")
    lines.extend(
        [
            f"💎 Jami D'Point: {net_dpoints:+.1f}",
            t(lang, "daily_test_results_balance", amount=f"{current_balance:.1f}"),
            "",
            compliment,
        ]
    )

    await bot.send_message(chat_id, "\n".join(lines))


@dp.poll_answer()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    chat_id = poll_answer.user.id
    logger.debug('handle_poll_answer: chat_id=%s poll_id=%s option_ids=%s', chat_id, poll_answer.poll_id, poll_answer.option_ids)
    # First handle vocabulary quiz polls
    if poll_answer.poll_id in vocab_poll_map:
        meta = vocab_poll_map.get(poll_answer.poll_id)
        if meta:
            chosen = poll_answer.option_ids[0] if poll_answer.option_ids else None
            meta['chosen'] = chosen
            ev = meta.get('event')
            if ev:
                ev.set()
        return

    # Grammar quiz polls
    if poll_answer.poll_id in grammar_poll_map:
        meta = grammar_poll_map.get(poll_answer.poll_id)
        if meta:
            chosen = poll_answer.option_ids[0] if poll_answer.option_ids else None
            meta['chosen'] = chosen
            ev = meta.get('event')
            if ev:
                ev.set()
        return

    # Daily test polls
    if poll_answer.poll_id in daily_poll_map:
        meta = daily_poll_map.get(poll_answer.poll_id)
        if meta:
            chosen = poll_answer.option_ids[0] if poll_answer.option_ids else None
            meta['chosen'] = chosen
            ev = meta.get('event')
            if ev:
                ev.set()
        return

    # Scheduled Daily/Boss arena (arena_runner)
    if poll_answer.poll_id in arena_run_poll_map:
        meta = arena_run_poll_map.get(poll_answer.poll_id)
        if meta:
            chosen = poll_answer.option_ids[0] if poll_answer.option_ids else None
            meta["chosen"] = chosen
            ev = meta.get("event")
            if ev:
                ev.set()
        return

    # Group Arena polls
    if poll_answer.poll_id in arena_group_poll_map:
        meta = arena_group_poll_map.get(poll_answer.poll_id)
        if meta:
            chosen = poll_answer.option_ids[0] if poll_answer.option_ids else None
            meta['chosen'] = chosen
            ev = meta.get('event')
            if ev:
                ev.set()
        return

    ps = get_placement_state(chat_id)
    if not ps.get('active'):
        logger.warning('handle_poll_answer: no active placement for chat_id=%s', chat_id)
        return

    poll_id = poll_answer.poll_id
    if poll_id not in ps['poll_map']:
        return

    chosen = poll_answer.option_ids[0] if poll_answer.option_ids else None
    meta = ps['poll_map'].pop(poll_id, None)
    if meta is None:
        return

    if chosen == meta['correct_option']:
        ps['score'] += 10

    user = get_user_by_telegram(str(chat_id))
    if not user:
        logger.warning('handle_poll_answer: user not found for chat_id=%s', chat_id)
        reset_placement_state(chat_id)
        return

    ps['question_index'] += 1
    save_placement_session(user['id'], {
        'active': True,
        'subject': ps['subject'],
        'question_index': ps['question_index'],
        'score': ps['score'],
        'questions': ps['questions'],
    })

    if ps['question_index'] >= len(ps['questions']):
        await finish_placement_test(user, chat_id)
        return

    lang = detect_lang_from_user(user)
    await bot.send_message(chat_id, t(lang, 'next_question'))
    await send_next_question(chat_id)


async def send_test_completion_to_admin(
    user: dict,
    subject: str,
    percentage: int,
    correct_count: int,
    level: str,
    *,
    level_code: str | None = None,
):
    """Send detailed test completion notification to admin with group recommendations"""
    from admin_bot import bot as admin_bot
    from config import ADMIN_CHAT_IDS, LIMITED_ADMIN_CHAT_IDS
    from db import extract_cefr_level_code, get_all_groups, get_group_users, get_peer_admins_for_student_share, get_user_by_id as get_user_by_id_db
    lang = detect_lang_from_user(user)

    if not admin_bot:
        return

    code = (level_code or extract_cefr_level_code(level) or "").strip().upper()

    owner_admin_id = user.get("owner_admin_id")

    all_groups = get_all_groups()
    owner_scoped_groups = all_groups
    if owner_admin_id is not None:
        # Limited admin: only groups created by this owner admin.
        owner_scoped_groups = [g for g in all_groups if g.get("owner_admin_id") == owner_admin_id]

    def build_payload(groups_base):
        suitable_groups = []
        for group in groups_base:
            if group.get('subject', '').lower() != subject.lower():
                continue
            glev = extract_cefr_level_code(group.get('level', ''))
            if code and glev == code:
                suitable_groups.append(group)

        if not suitable_groups and code:
            level_mapping = {
                'A1': ['A1', 'A2'],
                'A2': ['A1', 'A2', 'B1'],
                'B1': ['A2', 'B1', 'B2'],
                'B2': ['B1', 'B2'],
            }
            acceptable_levels = level_mapping.get(code, [code])
            for group in groups_base:
                if group.get('subject', '').lower() != subject.lower():
                    continue
                glev = extract_cefr_level_code(group.get('level', ''))
                if glev in acceptable_levels:
                    suitable_groups.append(group)

        admin_msg = t(
            lang,
            'admin_test_completion_title',
            first_name=user['first_name'],
            last_name=user['last_name'],
            login_id=user['login_id'],
            phone=user.get('phone', '—'),
            subject=subject,
            correct_count=correct_count,
            percentage=percentage,
            level=level,
        )

        if suitable_groups:
            admin_msg += t(
                lang,
                'admin_test_completion_recommended_groups_header',
                count=len(suitable_groups),
            )
            for i, group in enumerate(suitable_groups[:10], 1):
                teacher = get_user_by_id_db(group.get('teacher_id')) if group.get('teacher_id') else None
                teacher_name = f"{teacher['first_name']} {teacher['last_name']}" if teacher else "—"
                student_count = len(get_group_users(group['id']))
                admin_msg += t(
                    lang,
                    'admin_test_completion_group_item',
                    i=i,
                    group_name=group['name'],
                    group_level=group.get('level', '—'),
                    teacher_name=teacher_name,
                    student_count=student_count,
                    start=(group.get('lesson_start', '—') or '—')[:5],
                    end=(group.get('lesson_end', '—') or '—')[:5],
                )

            keyboard_buttons = []
            for i, group in enumerate(suitable_groups[:5], 1):
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"{i}. {group['name']} ({group.get('level', '—')})",
                        callback_data=f"assign_test_user_{user['id']}_{group['id']}"
                    )
                ])
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        else:
            admin_msg += t(lang, 'admin_test_completion_no_suitable_groups')
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=t(lang, 'recommendation_groups_btn'),
                    callback_data=f"rec_groups:{user['id']}:page:0"
                )]
            ])

        # Add general action buttons.
        action_buttons = [
            [InlineKeyboardButton(text=t(lang, 'admin_test_completion_user_info_btn'), callback_data=f"user_detail_{user['id']}")],
            [InlineKeyboardButton(text=t(lang, 'admin_test_completion_back_btn'), callback_data="back_to_menu")],
        ]
        if keyboard.inline_keyboard:
            keyboard.inline_keyboard.extend(action_buttons)
        else:
            keyboard = InlineKeyboardMarkup(inline_keyboard=action_buttons)

        return admin_msg, keyboard

    # Send message to:
    # - limited admins: only the owner admin (diamondadmin1/2 split)
    # - "general" admins in ADMIN_CHAT_IDS: everyone in ADMIN_CHAT_IDS can see
    recipients = set(ADMIN_CHAT_IDS) if ADMIN_CHAT_IDS else set()
    if owner_admin_id is not None:
        # Remove other limited admins
        for limited_admin_id in LIMITED_ADMIN_CHAT_IDS:
            if limited_admin_id != owner_admin_id:
                recipients.discard(limited_admin_id)
        # Ensure the owner limited admin always gets it
        recipients.add(owner_admin_id)
        for pid in get_peer_admins_for_student_share(int(user["id"])):
            recipients.add(pid)

    for admin_chat in recipients:
        try:
            groups_base = owner_scoped_groups if admin_chat in LIMITED_ADMIN_CHAT_IDS else all_groups
            admin_msg, keyboard = build_payload(groups_base)
            await admin_bot.send_message(
                admin_chat,
                admin_msg,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Admin notification failed: {e}")


async def finish_placement_test(user: dict, chat_id: int):
    ps = get_placement_state(chat_id)
    lang = detect_lang_from_user(user)
    score = ps['score']
    correct_count = score // 10
    subj_pl = (ps.get('subject') or '').lower()
    if subj_pl in ('русский', 'russian', 'ru'):
        level_code = compute_level(score, ps['subject'])
        level_display = level_code
    else:
        level_code = english_cefr_code_from_score(score)
        level_display = english_level_display_from_score(score)

    update_user_level(user['id'], level_display)
    save_test_result(user['id'], ps['subject'], score, level_code)
    # Convert temporary "new student" account into a regular student account
    # so placement test won't be requested again on subsequent logins.
    set_user_login_type(user['id'], 2)
    # Enable access after placement completion so multi-subject students
    # can use grammar/vocab/daily test flows immediately.
    enable_access(user['id'])
    # Set pending approval flag
    from db import set_pending_approval
    set_pending_approval(user['id'], True)
    clear_placement_session(user['id'])

    subject = ps.get('subject', 'unknown').title()
    total_questions = len(ps.get('questions', []))
    actual_max_score = total_questions * 10 if total_questions > 0 else 500
    percentage = min(100, int((score / actual_max_score) * 100)) if actual_max_score > 0 else 0
    result_msg = t(lang, 'placement_test_result_msg', percentage=percentage, correct_count=correct_count, level=level_display)

    await bot.send_message(chat_id, result_msg, parse_mode="HTML")

    await send_test_completion_to_admin(
        user, subject, percentage, correct_count, level_display, level_code=level_code
    )

    user = get_user_by_telegram(str(chat_id))
    if is_access_active(user):
        await bot.send_message(chat_id, t(lang, 'select_from_menu'), reply_markup=student_main_keyboard(lang))

    reset_placement_state(chat_id)
    if not is_access_active(user):
        clear_login_state(chat_id)


async def show_leaderboard(user_id, chat_id, page, filter_type='global'):
    """Reytingni sahifa bilan ko'rsatish"""
    user = get_user_by_telegram(str(user_id))
    if not user:
        lang = 'uz'  # default
        await bot.send_message(chat_id, t(lang, 'not_registered'))
        return
    
    # ← BU QATORNI QO'SHING (agar hali yo'q bo'lsa)
    lang = detect_lang_from_user(user)
    
    limit = 10
    offset = page * limit
    
    if filter_type != 'global':
        filter_type = 'global'
    leaderboard = get_leaderboard_global(limit=limit, offset=offset)
    total_count = get_leaderboard_count()
    title = t(lang, 'leaderboard_global_title')
    current_diamonds = get_dcoins(user['id'])
    
    # User's rank aniqlash
    all_users = get_leaderboard_global(limit=10000)  # Barcha foydalanuvchilarni olish rankini aniqlash uchun
    
    user_rank = None
    for idx, lb_user in enumerate(all_users, 1):
        if lb_user['id'] == user['id']:
            user_rank = idx
            break
    
    total_pages = (total_count - 1) // limit + 1 if total_count else 1
    
    rank_disp = str(user_rank) if user_rank is not None else t(lang, 'student_lb_rank_dash')
    header = f"{title}\n"
    header += (
        "<b>"
        + t(lang, 'your_rank_header', rank=rank_disp, dcoin=f'{current_diamonds:.1f}')
        + "</b>\n"
    )
    header += t(lang, 'student_lb_page', current=page + 1, total=total_pages) + "\n\n"

    text = header
    if leaderboard:
        for idx, lb_user in enumerate(leaderboard, start=offset + 1):
            medal = '🥇' if idx == 1 else '🥈' if idx == 2 else '🥉' if idx == 3 else f'{idx}.'
            bal = lb_user.get("dcoin_balance", lb_user.get("diamonds"))
            fn = html_module.escape(str(lb_user.get('first_name') or ''))
            ln = html_module.escape(str(lb_user.get('last_name') or ''))
            text += t(lang, 'student_lb_row', medal=medal, first=fn, last=ln, balance=bal) + "\n"
    else:
        text += t(lang, 'no_results')

    reply_markup = None
    if total_pages > 1:
        reply_markup = create_leaderboard_pagination_keyboard(page, total_pages, filter_type, lang=lang)
    await bot.send_message(
        chat_id,
        text,
        parse_mode='HTML',
        reply_markup=reply_markup,
    )


@dp.callback_query(lambda c: c.data.startswith('leaderboard_'))
async def handle_leaderboard_callback(callback: CallbackQuery):
    logger.info(f"🔘 CALLBACK: {callback.data} | User: {callback.from_user.id}")
    """Reyting paginatsiya va filter callbacklari"""
    data = callback.data
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    if data.startswith('lbprv|'):
        try:
            _, page_s, enc = data.split('|', 2)
            cur = int(page_s)
            filter_type = unquote(enc)
        except (ValueError, IndexError):
            await callback.answer()
            return
        await show_leaderboard(user_id, chat_id, max(0, cur - 1), filter_type)
        await callback.answer()
        return

    if data.startswith('lbnext|'):
        try:
            _, page_s, enc = data.split('|', 2)
            cur = int(page_s)
            filter_type = unquote(enc)
        except (ValueError, IndexError):
            await callback.answer()
            return
        await show_leaderboard(user_id, chat_id, cur + 1, filter_type)
        await callback.answer()
        return
    
    if data.startswith('leaderboard_filter_'):
        await show_leaderboard(user_id, chat_id, 0, 'global')
        await callback.answer()
        return


def _support_get_pending(chat_id: int) -> dict:
    st = get_student_state(chat_id)
    st.setdefault("data", {})
    st["data"].setdefault("support_pending", {})
    return st["data"]["support_pending"]


async def _support_check_booking_limits(chat_id: int, user: dict, lang: str) -> bool:
    """
    If the student cannot start a new booking (active upcoming lesson or 6h cooldown),
    send the same messages as before and return False. Otherwise return True.
    """
    now_iso = dt.now(timezone.utc).isoformat()
    if student_has_active_upcoming_booking(int(user["id"]), now_iso):
        b0 = (list_lesson_bookings_for_student(user["id"], active_only=True) or [None])[0]
        date_s = (b0 or {}).get("date") or ""
        tm_s = _support_fmt_hhmm((b0 or {}).get("time"), (b0 or {}).get("start_ts"))
        br_s = (b0 or {}).get("branch") or ""
        branch_label = t(lang, "support_branch_1") if br_s == "branch_1" else t(lang, "support_branch_2")
        purpose_label = _support_purpose_label(lang, str((b0 or {}).get("purpose") or "all"))
        await bot.send_message(
            chat_id,
            t(
                lang,
                "support_booking_active_blocked",
                date=_support_fmt_long_date(date_s, lang),
                time=tm_s,
                branch=branch_label,
                purpose=purpose_label,
            ),
            parse_mode="HTML",
        )
        return False
    unlock_iso = get_next_lesson_booking_allowed_after_utc_iso(int(user["id"]), now_iso)
    if unlock_iso:
        last_end = get_last_ended_lesson_end_ts(int(user["id"]), now_iso)
        ld, lt = _support_end_ts_local_date_time(last_end or "")
        await bot.send_message(
            chat_id,
            t(
                lang,
                "support_booking_cooldown_wait",
                last_date=ld,
                last_time=lt,
                unlock_time=_support_unlock_fmt(unlock_iso),
                hours=SUPPORT_BOOKING_COOLDOWN_HOURS,
            ),
            parse_mode="HTML",
        )
        return False
    return True


async def _support_show_menu(chat_id: int, user: dict, *, callback_message: Message | None = None):
    lang = detect_lang_from_user(user)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "support_book_lesson_btn"), callback_data="support:book")],
            [InlineKeyboardButton(text=t(lang, "support_my_bookings_btn"), callback_data="support:my")],
        ]
    )
    await _support_flow_render(
        t(lang, "support_menu_title"),
        kb,
        chat_id=chat_id,
        callback_message=callback_message,
    )


async def _support_show_subjects(chat_id: int, user: dict, *, callback_message: Message | None = None):
    lang = detect_lang_from_user(user)
    subjects = get_student_subjects(int(user["id"])) or []
    subject_set = {str(s).strip().lower() for s in subjects if s is not None}
    
    # Avval faqat English edi, endi student qaysi fanni o'qisa shunga ko'ra chiqariladi.
    # Agar hech qanday fan bo'lmasa, xabar beramiz
    if not subject_set:
        await bot.send_message(chat_id, t(lang, "student_no_active_groups"), parse_mode="HTML")
        return
        
    rows = []
    for subj in sorted(subject_set):
        rows.append([InlineKeyboardButton(text=subj.capitalize(), callback_data=f"support:subj:{subj}")])
    
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="support:back:menu")])
    await _support_flow_render(
        t(lang, "choose_subject") if "choose_subject" in t(lang, "choose_subject") else "Iltimos, fanni tanlang: / Please choose a subject:",
        InlineKeyboardMarkup(inline_keyboard=rows),
        chat_id=chat_id,
        callback_message=callback_message,
    )

async def _support_show_branches(chat_id: int, user: dict, *, callback_message: Message | None = None):
    lang = detect_lang_from_user(user)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "support_branch_1"), callback_data="support:branch:branch_1")],
            [InlineKeyboardButton(text=t(lang, "support_branch_2"), callback_data="support:branch:branch_2")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="support:back:subjects")],
        ]
    )
    await _support_flow_render(
        t(lang, "support_choose_branch"),
        kb,
        chat_id=chat_id,
        callback_message=callback_message,
    )


async def _support_show_dates(chat_id: int, user: dict, branch_key: str, *, callback_message: Message | None = None):
    lang = detect_lang_from_user(user)
    allowed_wd = set(get_lesson_branch_weekdays(str(branch_key)))
    today = dt.now(SUPPORT_TZ).date()
    dates: list[tuple[str, bool]] = []
    for i in range(0, 14):
        d = today + timedelta(days=i)
        if d.weekday() == 6:
            continue
        if d.weekday() not in allowed_wd:
            continue
        iso = d.isoformat()
        if is_lesson_holiday(iso):
            continue
        is_closed = is_branch_date_closed_for_booking(str(branch_key), iso)
        dates.append((iso, is_closed))
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for d_iso, is_closed in dates[:14]:
        wd = _support_weekday_name(d_iso, lang)
        date_line = _support_fmt_long_date(d_iso, lang)
        label = (
            t(lang, "support_date_pick_with_weekday", date=date_line, weekday=wd)
            if wd
            else t(lang, "support_date_pick_no_weekday", date=date_line)
        )
        if is_closed:
            row.append(InlineKeyboardButton(text=f"🔒 {label}", callback_data=f"support:date_closed:{branch_key}:{d_iso}"))
        else:
            row.append(InlineKeyboardButton(text=label, callback_data=f"support:date:{branch_key}:{d_iso}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="support:back:branch")])
    await _support_flow_render(
        t(lang, "support_choose_date"),
        InlineKeyboardMarkup(inline_keyboard=rows),
        chat_id=chat_id,
        callback_message=callback_message,
    )


async def _support_show_times(
    chat_id: int, user: dict, subject: str, branch_key: str, date_iso: str, *, callback_message: Message | None = None
):
    lang = detect_lang_from_user(user)
    from db import get_available_support_slots_for_subject, lesson_is_slot_free_for_subject
    
    times = get_available_support_slots_for_subject(subject, date_iso)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    now_tz = dt.now(SUPPORT_TZ)
    today_tz = now_tz.date()
    try:
        d = dt.strptime(date_iso, "%Y-%m-%d").date()
    except Exception:
        d = dt.now(SUPPORT_TZ).date()
    for tm in times:
        start_ts = support_make_start_ts(date_iso, tm) or ""
        blocked = is_slot_closed_effective(branch_key, date_iso, tm)
        free = lesson_is_slot_free_for_subject(subject, date_iso, tm) and not blocked
        try:
            hh, mm = [int(x) for x in tm.split(":", 1)]
            local_dt = SUPPORT_TZ.localize(dt.combine(d, dtime(hh, mm)))
            slot_passed = (d == today_tz) and (local_dt <= now_tz)
        except Exception:
            slot_passed = False

        if slot_passed:
            label = "⏰"
            cb = "support:slot_passed"
        elif blocked:
            label = f"🔒 {tm}"
            cb = f"support:slot_blocked:{date_iso}|{tm}|{branch_key}"
        elif free:
            label = f"🕒 {tm}"
            cb = f"support:time:{branch_key}:{date_iso}:{tm.replace(':', '.')}"
        else:
            label = f"❌ {tm}"
            cb = f"support:slot_taken:{date_iso}|{tm}|{branch_key}"
        row.append(InlineKeyboardButton(text=label, callback_data=cb))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if not times:
        rows.append([InlineKeyboardButton(text="Barcha slotlar band / No slots", callback_data="support:noop")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"support:back:dates:{branch_key}")])
    await _support_flow_render(
        t(lang, "support_choose_time"),
        InlineKeyboardMarkup(inline_keyboard=rows),
        chat_id=chat_id,
        callback_message=callback_message,
    )


async def _support_show_purposes(chat_id: int, user: dict, *, callback_message: Message | None = None):
    lang = detect_lang_from_user(user)
    pairs = [
        ("support_purpose_speaking", "speaking"),
        ("support_purpose_grammar", "grammar"),
        ("support_purpose_writing", "writing"),
        ("support_purpose_reading", "reading"),
        ("support_purpose_listening", "listening"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    # Two-column UI; if purpose count is odd, last one becomes a single-button row.
    for i in range(0, len(pairs), 2):
        a = pairs[i]
        row = [
            InlineKeyboardButton(text=t(lang, a[0]), callback_data=f"support:purpose:{a[1]}"),
        ]
        if i + 1 < len(pairs):
            b = pairs[i + 1]
            row.append(
                InlineKeyboardButton(text=t(lang, b[0]), callback_data=f"support:purpose:{b[1]}"),
            )
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text=t(lang, "support_purpose_all"), callback_data="support:purpose:all")]
    )
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="support:back:times")])
    await _support_flow_render(
        t(lang, "support_choose_purpose"),
        InlineKeyboardMarkup(inline_keyboard=rows),
        chat_id=chat_id,
        callback_message=callback_message,
    )


async def _support_show_confirm(chat_id: int, user: dict, *, callback_message: Message | None = None):
    lang = detect_lang_from_user(user)
    pending = _support_get_pending(chat_id)
    branch = pending.get("branch")
    date_iso = pending.get("date")
    tm = pending.get("time")
    purpose = pending.get("purpose")
    if not (branch and date_iso and tm and purpose):
        await bot.send_message(chat_id, t(lang, "support_booking_incomplete"))
        return
    wd = _support_weekday_name(date_iso, lang)
    branch_label = t(lang, "support_branch_1") if branch == "branch_1" else t(lang, "support_branch_2")
    purpose_label = _support_purpose_label(lang, purpose)
    date_dd = _support_fmt_dd_mm_yyyy(date_iso)
    tm_disp = _support_fmt_hhmm(tm, None)
    text = t(
        lang,
        "support_booking_summary_confirm",
        date_line=date_dd,
        weekday=wd or "",
        time=tm_disp,
        branch=branch_label,
        purpose=purpose_label,
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(lang, "support_confirm_btn"),
                    callback_data=f"support:confirm:{_support_encode_confirm_token(branch, date_iso, tm, purpose)}",
                )
            ],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="support:back:purpose")],
        ]
    )
    await _support_flow_render(text, kb, chat_id=chat_id, callback_message=callback_message)


async def _support_show_my_bookings(chat_id: int, user: dict, from_user):
    lang = detect_lang_from_user(user)
    items = list_lesson_bookings_for_student(user["id"], active_only=True)
    if not items:
        await bot.send_message(chat_id, t(lang, "support_no_bookings"))
        return
    b = items[0]
    bid = b.get("id")
    date_iso = b.get("date") or ""
    wd = _support_weekday_name(date_iso, lang)
    branch_label = t(lang, "support_branch_1") if b.get("branch") == "branch_1" else t(lang, "support_branch_2")
    purpose_label = _support_purpose_label(lang, str(b.get("purpose") or "all"))
    fn = html_module.escape(f"{(user.get('first_name') or '').strip()} {(user.get('last_name') or '').strip()}".strip() or "—")
    date_long = _support_fmt_long_date(date_iso, lang)
    tm_disp = _support_fmt_hhmm(b.get("time"), b.get("start_ts"))
    text = t(
        lang,
        "support_my_booking_current",
        login_id=html_module.escape(str(user.get("login_id") or "—")),
        name=fn,
        profile=_support_profile_link_html(user, from_user),
        date_long=html_module.escape(date_long),
        weekday=wd or "",
        time=tm_disp,
        branch=branch_label,
        purpose=purpose_label,
        booking_id=html_module.escape(str(bid)),
    )
    rows = [
        [InlineKeyboardButton(text=t(lang, "support_cancel_booking_btn"), callback_data=f"support:cancel:{bid}")],
        [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="support:back:menu")],
    ]
    await bot.send_message(
        chat_id,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        parse_mode="HTML",
    )


@dp.callback_query(lambda c: c.data.startswith("support:"))
async def support_callbacks(callback: CallbackQuery):
    user = get_user_by_telegram(str(callback.from_user.id))
    if not user and callback.message and callback.message.chat:
        # Fallback for cases where callback user/chat ids mismatch persisted telegram_id mapping.
        user = get_user_by_telegram(str(callback.message.chat.id))
    lang = detect_lang_from_user(user or callback.from_user)
    if not user or not is_access_active(user):
        await callback.answer()
        await callback.message.answer(t(lang, "please_send_start"))
        return

    ensure_support_lessons_schema()
    data = callback.data
    parts = data.split(":")
    action = parts[1] if len(parts) > 1 else ""
    chat_id = callback.message.chat.id

    if action == "noop":
        await callback.answer()
        return

    pending = _support_get_pending(chat_id)

    if action == "slot_passed":
        await callback.answer(t(lang, "slot_passed"), show_alert=True)
        return

    if action == "slot_blocked" and len(parts) >= 3:
        payload = parts[2]
        try:
            date_iso, tm, br = payload.split("|", 2)
        except Exception:
            date_iso, tm, br = "", "", ""
        reason = get_slot_block_reason(br, date_iso, tm) if (date_iso and tm and br) else None
        msg = t(lang, "support_slot_locked_with_reason", reason=reason) if reason else t(lang, "support_slot_locked_no_reason")
        await callback.answer(msg, show_alert=True)
        return

    if action == "slot_taken" and len(parts) >= 3:
        payload = parts[2]
        try:
            date_iso, tm, br = payload.split("|", 2)
        except Exception:
            date_iso, tm, br = "", "", ""
        await callback.answer(t(lang, "slot_taken"), show_alert=True)
        if date_iso and tm and br:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=t(lang, "join_waitlist"), callback_data=f"support:join_waitlist:{date_iso}|{tm}|{br}")],
                    [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"support:back:dates:{br}")],
                ]
            )
            await callback.message.answer(t(lang, "waitlist_prompt"), reply_markup=kb, parse_mode="HTML")
        return

    if action == "join_waitlist" and len(parts) >= 3:
        payload = parts[2]
        try:
            date_iso, tm, br = payload.split("|", 2)
        except Exception:
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        ok = add_lesson_waitlist(uuid4().hex[:12], date_iso, tm, br, str(callback.from_user.id))
        if ok:
            await callback.message.answer(t(lang, "waitlist_joined"), parse_mode="HTML")
        else:
            await callback.message.answer(t(lang, "support_error_generic"), parse_mode="HTML")
        await callback.answer()
        return

    if action == "back":
        where = parts[2] if len(parts) > 2 else "menu"
        if where == "menu":
            await _support_show_menu(chat_id, user, callback_message=callback.message)
        elif where == "subjects":
            await _support_show_subjects(chat_id, user, callback_message=callback.message)
        elif where == "branch":
            await _support_show_branches(chat_id, user, callback_message=callback.message)
        elif where == "dates":
            branch_key = parts[3] if len(parts) > 3 else pending.get("branch") or "branch_1"
            await _support_show_dates(chat_id, user, branch_key, callback_message=callback.message)
        elif where == "times":
            branch_key = pending.get("branch") or "branch_1"
            date_iso = pending.get("date") or ""
            subj = pending.get("subject") or "english"
            if branch_key and date_iso:
                await _support_show_times(
                    chat_id, user, subj, branch_key, date_iso, callback_message=callback.message
                )
            else:
                await _support_show_dates(chat_id, user, branch_key, callback_message=callback.message)
        elif where == "purpose":
            await _support_show_purposes(chat_id, user, callback_message=callback.message)
        await callback.answer()
        return

    if action == "book":
        pending.clear()
        if not await _support_check_booking_limits(chat_id, user, lang):
            _flow_log(
                "warning",
                "Support booking blocked at book entry (active or cooldown)",
                **_flow_ctx(callback=callback, user=user, flow="support_booking_book", extra={}),
            )
            await callback.answer()
            return
        await _support_show_subjects(chat_id, user, callback_message=callback.message)
        await callback.answer()
        return
        
    if action == "subj" and len(parts) >= 3:
        subj = parts[2]
        pending["subject"] = subj
        await _support_show_branches(chat_id, user, callback_message=callback.message)
        await callback.answer()
        return

    if action == "my":
        await _support_show_my_bookings(chat_id, user, callback.from_user)
        await callback.answer()
        return

    if action == "branch" and len(parts) >= 3:
        branch_key = parts[2]
        pending["branch"] = branch_key
        await _support_show_dates(chat_id, user, branch_key, callback_message=callback.message)
        await callback.answer()
        return

    if action == "date" and len(parts) >= 4:
        branch_key = parts[2]
        date_iso = parts[3]
        subj = pending.get("subject") or "english"
        pending["branch"] = branch_key
        pending["date"] = date_iso
        await _support_show_times(chat_id, user, subj, branch_key, date_iso, callback_message=callback.message)
        await callback.answer()
        return

    if action == "date_closed" and len(parts) >= 4:
        branch_key = parts[2]
        date_iso = parts[3]
        rs_raw = get_branch_date_closed_reason(branch_key, date_iso)
        rs = _normalize_support_closed_reason(lang, rs_raw)
        msg = t(lang, "support_day_closed_with_reason", reason=rs) if rs else t(lang, "support_day_closed_no_reason")
        await callback.answer(msg, show_alert=True)
        return

    if action == "time" and len(parts) >= 5:
        branch_key = parts[2]
        date_iso = parts[3]
        tm = parts[4].replace(".", ":")
        pending["branch"] = branch_key
        pending["date"] = date_iso
        pending["time"] = tm
        await _support_show_purposes(chat_id, user, callback_message=callback.message)
        await callback.answer()
        return

    if action == "purpose" and len(parts) >= 3:
        purpose = parts[2]
        pending["purpose"] = purpose
        await _support_show_confirm(chat_id, user, callback_message=callback.message)
        await callback.answer()
        return

    if action == "confirm":
        # Prefer compact encoded callback payload, fallback to legacy/state.
        branch_key = date_iso = tm = purpose = None
        if len(parts) >= 3:
            branch_key, date_iso, tm, purpose = _support_decode_confirm_token(parts[2])
        if not (branch_key and date_iso and tm and purpose):
            # Legacy payload support: support:confirm:<branch>:<date>:<time>:<purpose>
            branch_key = parts[2] if len(parts) >= 6 else pending.get("branch")
            date_iso = parts[3] if len(parts) >= 6 else pending.get("date")
            tm = parts[4] if len(parts) >= 6 else pending.get("time")
            purpose = parts[5] if len(parts) >= 6 else pending.get("purpose")
        base_ctx = _flow_ctx(
            callback=callback,
            user=user,
            flow="support_booking_confirm",
            extra={
                "branch": branch_key,
                "date_iso": date_iso,
                "time": tm,
                "purpose": purpose,
            },
        )
        _flow_log("info", "Support booking confirm clicked", **base_ctx)
        if not (branch_key and date_iso and tm and purpose):
            _flow_log("warning", "Support booking confirm missing payload", **base_ctx)
            await callback.answer(t(lang, "support_booking_incomplete"), show_alert=True)
            return

        try:
            start_ts = support_make_start_ts(date_iso, tm)
            if not start_ts:
                _flow_log("warning", "Support booking invalid start_ts", **base_ctx)
                await callback.answer(t(lang, "support_booking_incomplete"), show_alert=True)
                return
            if is_slot_closed_effective(branch_key, date_iso, tm):
                _flow_log("warning", "Support booking slot blocked by admin", **base_ctx)
                rs = get_slot_block_reason(branch_key, date_iso, tm)
                msg = t(lang, "support_slot_locked_with_reason", reason=rs) if rs else t(lang, "support_slot_locked_no_reason")
                await callback.answer(msg, show_alert=True)
                return
                
            subj = pending.get("subject") or "english"
            
            from db import lesson_is_slot_free_for_subject
            if not lesson_is_slot_free_for_subject(subj, date_iso, tm):
                _flow_log("warning", "Support booking slot already taken", **base_ctx)
                await callback.answer(t(lang, "support_slot_taken"), show_alert=True)
                return

            end_ts = support_make_end_ts(start_ts)
            booking_id = generate_lesson_booking_id()
            _flow_log("info", "Creating support booking request", **_flow_ctx(callback=callback, user=user, flow="support_booking_confirm", extra={"booking_id": booking_id, "start_ts": start_ts}))
            ok = create_lesson_booking_request(
                booking_id=booking_id,
                student_user_id=user["id"],
                student_telegram_id=str(callback.from_user.id),
                branch=branch_key,
                date_iso=date_iso,
                time_hhmm=tm,
                start_ts=start_ts,
                end_ts=end_ts,
                purpose=purpose,
                subject=subj,
            )
            _flow_log("info", "Support booking create result", **_flow_ctx(callback=callback, user=user, flow="support_booking_confirm", extra={"booking_id": booking_id, "ok": bool(ok)}))
        except Exception as e:
            logger.exception("Support booking confirm failed")
            await _notify_flow_exception(
                flow="support_booking_confirm",
                callback=callback,
                user=user,
                exc=e,
                context={
                    "branch": branch_key,
                    "date_iso": date_iso,
                    "time": tm,
                    "purpose": purpose,
                },
            )
            await callback.answer(t(lang, "support_error_generic"), show_alert=True)
            return
        if not ok:
            now_iso_retry = dt.now(timezone.utc).isoformat()
            has_active = student_has_active_upcoming_booking(int(user["id"]), now_iso_retry)
            unlock_iso2 = get_next_lesson_booking_allowed_after_utc_iso(int(user["id"]), now_iso_retry)
            slot_free_retry = lesson_is_slot_free(start_ts)
            # DB-level guard may have rejected the booking even after our UI checks.
            # Re-check the most common reasons and show a precise message instead of generic error.
            if has_active:
                b0 = (list_lesson_bookings_for_student(user["id"], active_only=True) or [None])[0]
                date_s = (b0 or {}).get("date") or ""
                tm_s = _support_fmt_hhmm((b0 or {}).get("time"), (b0 or {}).get("start_ts"))
                br_s = (b0 or {}).get("branch") or ""
                branch_label = t(lang, "support_branch_1") if br_s == "branch_1" else t(lang, "support_branch_2")
                purpose_label = _support_purpose_label(lang, str((b0 or {}).get("purpose") or "all"))
                await bot.send_message(
                    chat_id,
                    t(
                        lang,
                        "support_booking_active_blocked",
                        date=_support_fmt_long_date(date_s, lang),
                        time=tm_s,
                        branch=branch_label,
                        purpose=purpose_label,
                    ),
                    parse_mode="HTML",
                )
                await callback.answer()
                return

            if unlock_iso2:
                last_end2 = get_last_ended_lesson_end_ts(int(user["id"]), now_iso_retry)
                ld2, lt2 = _support_end_ts_local_date_time(last_end2 or "")
                await bot.send_message(
                    chat_id,
                    t(
                        lang,
                        "support_booking_cooldown_wait",
                        last_date=ld2,
                        last_time=lt2,
                        unlock_time=_support_unlock_fmt(unlock_iso2),
                        hours=SUPPORT_BOOKING_COOLDOWN_HOURS,
                    ),
                    parse_mode="HTML",
                )
                await callback.answer()
                return

            if not slot_free_retry:
                await callback.answer(t(lang, "support_slot_taken"), show_alert=True)
                return

            await callback.answer(t(lang, "support_error_generic"), show_alert=True)
            return

        refresh_lesson_reminders_for_booking(str(booking_id))

        pending.clear()
        _support_clear_flow_message_id(chat_id)
        branch_label = t(lang, "support_branch_1") if branch_key == "branch_1" else t(lang, "support_branch_2")
        purpose_label = _support_purpose_label(lang, purpose)
        wd = _support_weekday_name(date_iso, lang)
        full_name = f"{(user.get('first_name') or '').strip()} {(user.get('last_name') or '').strip()}".strip()
        student_txt = t(
            lang,
            "support_booking_confirmed_student",
            login_id=html_module.escape(str(user.get("login_id") or "")),
            name=html_module.escape(full_name or "—"),
            profile=_support_profile_link_html(user, callback.from_user),
            date_dd_mm_yyyy=_support_fmt_dd_mm_yyyy(date_iso),
            weekday=wd or "",
            time=_support_fmt_hhmm(tm, start_ts),
            branch=branch_label,
            purpose=purpose_label,
            booking_id=html_module.escape(booking_id),
        )
        await bot.send_message(chat_id, student_txt, parse_mode="HTML")

        support_admin_ids = _support_booking_notify_admin_ids()
        if support_bot and support_admin_ids:
            for aid in support_admin_ids:
                tlu = get_lesson_user(str(aid)) or {}
                tlang = (tlu.get("language") or "en").lower()
                if tlang not in ("uz", "ru", "en"):
                    tlang = "en"
                note_t = t(
                    tlang,
                    "support_booking_new_teacher",
                    login_id=html_module.escape(str(user.get("login_id") or "")),
                    name=html_module.escape(full_name or "—"),
                    profile=_support_profile_link_html(user, callback.from_user),
                    date_long=_support_fmt_long_date(date_iso, tlang),
                    weekday=wd or "",
                    time=_support_fmt_hhmm(tm, start_ts),
                    branch=branch_label,
                    purpose=purpose_label,
                    booking_id=html_module.escape(booking_id),
                )
                try:
                    await support_bot.send_message(int(aid), note_t, parse_mode="HTML")
                except Exception:
                    pass

        await callback.answer()
        return

    if action == "cancel" and len(parts) >= 3:
        bid = parts[2]
        ok = set_lesson_booking_status(str(bid), "canceled", admin_id=None, admin_note="student_canceled")
        if ok:
            await callback.message.answer(t(lang, "support_booking_canceled"))
            # notify waitlist if any
            try:
                b = None
                # best-effort: fetch from student list
                for it in list_lesson_bookings_for_student(user["id"], active_only=False):
                    if str(it.get("id")) == str(bid):
                        b = it
                        break
                if b:
                    entry = pop_lesson_waitlist_for_slot(b.get("date"), b.get("time"), b.get("branch"))
                    if entry and entry.get("telegram_id"):
                        try:
                            await bot.send_message(
                                int(entry["telegram_id"]),
                                t(
                                    lang,
                                    "waitlist_slot_available",
                                    date=b.get("date"),
                                    time=_support_fmt_hhmm(b.get("time"), b.get("start_ts")),
                                ),
                                parse_mode="HTML",
                            )
                        except Exception:
                            pass
            except Exception:
                pass
        else:
            await callback.message.answer(t(lang, "support_error_generic"))
        await callback.answer()
        return

    await callback.answer(t(lang, "invalid_action"), show_alert=True)


async def run_student_bot():
    global bot, admin_bot, support_bot
    print("[STARTUP] student_bot run_student_bot() starting")
    if not STUDENT_BOT_TOKEN:
        raise RuntimeError("STUDENT_BOT_TOKEN is not set. Put it in .env (STUDENT_BOT_TOKEN=...) and retry.")
    bot = create_resilient_bot(STUDENT_BOT_TOKEN)

    def _preflight() -> int:
        try:
            ensure_subject_dcoin_schema()
            ensure_dcoin_schema_migrations()
        except Exception:
            logger.exception("Student bot startup: D'coin schema ensure failed")
        if not validate_dcoin_runtime_ready(context="student_bot startup"):
            raise RuntimeError("Student bot startup aborted: D'coin runtime schema is not ready")
        return restore_sessions_on_startup(run_cleanup=False)

    restored_count = await asyncio.to_thread(_preflight)

    print("[STARTUP] student_bot validate_dcoin_runtime_ready() ok")
    
    # Initialize admin bot for sending notifications
    from config import ADMIN_BOT_TOKEN
    if ADMIN_BOT_TOKEN:
        admin_bot = create_resilient_bot(ADMIN_BOT_TOKEN)
    else:
        logger.warning("ADMIN_BOT_TOKEN not set, admin notifications will not work")

    # Initialize support bot for booking notifications (SUPPORT_BOT_TOKEN)
    if SUPPORT_BOT_TOKEN:
        support_bot = create_resilient_bot(SUPPORT_BOT_TOKEN)
    else:
        support_bot = None
    
    logger.info(f"🔄 Restored {restored_count} user sessions on startup")
    
    # Start cleanup scheduler for inactive accounts (runs once per day)
    async def cleanup_scheduler():
        while True:
            try:
                await asyncio.sleep(86400)  # Sleep for 24 hours
                deleted_count = await asyncio.to_thread(cleanup_inactive_accounts)
                logger.info(f"🧹 Cleanup completed: {deleted_count} inactive accounts deleted (60+ days)")
            except Exception as e:
                logger.error(f"Cleanup scheduler error: {e}")
    
    async def duel_timeout_scheduler():
        while True:
            try:
                now_iso = _now_tashkent().strftime("%Y-%m-%d %H:%M:%S")
                refunds = cancel_expired_open_duel_sessions(now_iso)
                for row in refunds:
                    uid = int(row["user_id"])
                    sess_id = int(row["session_id"])
                    chat = int(row["chat_id"])
                    sess = get_duel_session(sess_id) or {}
                    subject = str(sess.get("subject") or "English")
                    add_dcoins(uid, 3.0, subject, change_type="duel_refund")
                    mark_duel_participant_refunded(sess_id, uid)
                    try:
                        u = get_user_by_id(uid) or {}
                        ulang = detect_lang_from_user(u)
                        await bot.send_message(chat, t(ulang, "duel_timeout_refund"))
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Duel timeout scheduler error: {e}")
            await asyncio.sleep(20)

    async def _pregen_scheduled_run_questions(rid: int, kind: str, subject: str):
        from datetime import datetime
        from ai_generator import populate_boss_arena_run_questions, populate_daily_arena_run_questions

        try:
            # Daily arena questions are generated on-demand per stage in arena_runner.
            if kind == "boss":
                await populate_boss_arena_run_questions(run_id=rid, subject=subject, pool_size=15)
                update_scheduled_arena_run(rid, questions_generated_at=datetime.utcnow().isoformat())
        except Exception:
            logger.exception("pregen arena run_id=%s kind=%s", rid, kind)

    async def scheduled_arena_announcer():
        """
        Tashkent: Daily EN 19:00 / RU 20:00 — T-10 da join xabari + tugma, T-1 eslatma, startda coordinator boshlanadi.
        Boss Arena no longer has a fixed-time reminder; real session notifications are handled by the web runtime.
        """
        while True:
            try:
                now = _now_tashkent()
                hhmm = now.strftime("%H:%M")
                day = now.date().isoformat()
                schedules = [
                    {"subject": "English", "start": "19:00", "kind": "daily", "pregen_min": 10, "warn": (10, 1)},
                    {"subject": "Russian", "start": "20:00", "kind": "daily", "pregen_min": 10, "warn": (10, 1)},
                ]
                for spec in schedules:
                    subject = spec["subject"]
                    start_hhmm = spec["start"]
                    kind = spec["kind"]
                    h, m = [int(x) for x in start_hhmm.split(":")]
                    start_dt = SUPPORT_TZ.localize(dt.combine(now.date(), dtime(h, m)))

                    # Pregen / create run (T-N minutes before start)
                    pg = int(spec.get("pregen_min") or 30)
                    pregen_dt = start_dt - timedelta(minutes=pg)
                    k_pregen = (day, kind, subject, start_hhmm, "pregen")
                    if pregen_dt.strftime("%H:%M") == hhmm and arena_daily_last_slot.get(k_pregen) != "1":
                        arena_daily_last_slot[k_pregen] = "1"
                        try:
                            rid = get_or_create_scheduled_arena_run(
                                run_kind=kind,
                                subject=subject,
                                run_date=day,
                                start_hhmm=start_hhmm,
                            )
                            update_scheduled_arena_run(
                                rid,
                                status="pending",
                                questions_generated_at=None,
                            )
                            asyncio.create_task(_pregen_scheduled_run_questions(rid, kind, subject))
                        except Exception:
                            logger.exception("scheduled arena pregen/create")

                    for w in spec.get("warn") or ():
                        pre = start_dt - timedelta(minutes=int(w))
                        k = (day, kind, subject, start_hhmm, f"warn{w}")
                        if pre.strftime("%H:%M") == hhmm and arena_daily_last_slot.get(k) != "1":
                            arena_daily_last_slot[k] = "1"

                            # Freeze loop vars for async fan-out (avoid late-binding to last iteration).
                            def _txt(
                                urow,
                                _subject=subject,
                                _kind=kind,
                                _w=int(w),
                                _start=start_hhmm,
                            ):
                                lg = (urow.get("language") or "uz").strip()[:5] or "uz"
                                if _kind == "daily" and _w == 10:
                                    return t(
                                        lg,
                                        "arena_daily_join_soon_t10",
                                        subject=_subject,
                                        time=_start,
                                        minutes=_w,
                                    )
                                return t(
                                    lg,
                                    "arena_scheduled_soon",
                                    mode=_kind.upper(),
                                    subject=_subject,
                                    time=_start,
                                    minutes=_w,
                                )
                            try:
                                rid = get_or_create_scheduled_arena_run(
                                    run_kind=kind,
                                    subject=subject,
                                    run_date=day,
                                    start_hhmm=start_hhmm,
                                    min_players=10,
                                    max_players=0 if kind == "boss" else 15,
                                )
                            except Exception:
                                rid = 0

                            if rid > 0:
                                def _kb(
                                    urow,
                                    _kind=kind,
                                    _rid=rid,
                                    _subject=subject,
                                ):
                                    lg = (urow.get("language") or "uz").strip()[:5] or "uz"
                                    section = "arena-daily" if _kind == "daily" else "arena-boss"
                                    url = _student_miniapp_url(
                                        section,
                                        extra={"arena_mode": section, "auto_join": 1, "subject": _subject},
                                    )
                                    if not url:
                                        return None
                                    return InlineKeyboardMarkup(
                                        inline_keyboard=[[InlineKeyboardButton(text=t(lg, "arena_join_paid_btn"), web_app=WebAppInfo(url=url))]]
                                    )
                                _notify_students_for_subject_mapped(subject, _txt, _kb)
                            else:
                                _notify_students_for_subject_mapped(subject, _txt, None)

                    k_start = (day, kind, subject, start_hhmm, "start")
                    if start_hhmm == hhmm and arena_boss_last_slot.get(k_start) != "1":
                        arena_boss_last_slot[k_start] = "1"
                        try:
                            rid = get_or_create_scheduled_arena_run(
                                run_kind=kind,
                                subject=subject,
                                run_date=day,
                                start_hhmm=start_hhmm,
                                min_players=10,
                                max_players=15,
                            )
                            # Daily and boss coordinators will open/lock joins themselves.
                            if kind == "daily":
                                asyncio.create_task(run_daily_arena_coordinator(bot, rid))
                            else:
                                asyncio.create_task(run_boss_arena_coordinator(bot, rid))
                        except Exception:
                            logger.exception("scheduled arena start")
                            rid = 0
                        mode_cb = "daily" if kind == "daily" else "boss"
                        suffix = f":{rid}" if rid else ""

                        def _txt2(
                            urow,
                            _kind=kind,
                            _subject=subject,
                            _start=start_hhmm,
                        ):
                            lg = (urow.get("language") or "uz").strip()[:5] or "uz"
                            return t(
                                lg,
                                "arena_scheduled_started",
                                mode=_kind.upper(),
                                subject=_subject,
                                time=_start,
                            )

                        def _kb_start(
                            urow,
                            _mode_cb=mode_cb,
                            _suffix=suffix,
                            _subject=subject,
                        ):
                            lg = (urow.get("language") or "uz").strip()[:5] or "uz"
                            section = "arena-daily" if _mode_cb == "daily" else "arena-boss"
                            url = _student_miniapp_url(
                                section,
                                extra={"arena_mode": section, "auto_join": 1, "subject": _subject},
                            )
                            if not url:
                                return None
                            return InlineKeyboardMarkup(
                                inline_keyboard=[[InlineKeyboardButton(text=t(lg, "arena_join_paid_btn"), web_app=WebAppInfo(url=url))]]
                            )
                        if rid > 0:
                            _notify_students_for_subject_mapped(subject, _txt2, _kb_start)
                        else:
                            _notify_students_for_subject_mapped(subject, _txt2, None)
            except Exception as e:
                logger.error(f"Scheduled arena notifier error: {e}")
            await asyncio.sleep(25)

    async def daily_test_reminder_scheduler():
        """
        Daily test reminders:
        - slot 0: 09:00
        - slot 1: 14:00
        - slot 2: 19:00
        """
        sent_slots: set[tuple[str, int]] = set()
        slot_hhmm = {0: "09:00", 1: "14:00", 2: "19:00"}
        while True:
            try:
                now = _now_tashkent()
                day = now.date().isoformat()
                hhmm = now.strftime("%H:%M")
                for slot, target_time in slot_hhmm.items():
                    key = (day, slot)
                    if hhmm != target_time:
                        continue
                    if key in sent_slots:
                        continue
                    sent_slots.add(key)
                    candidates = get_daily_test_reminder_candidates(day, slot) or []
                    for row in candidates:
                        uid = int(row.get("id") or 0)
                        tg = str(row.get("telegram_id") or "").strip()
                        if uid <= 0 or not tg:
                            continue
                        if not mark_daily_test_notification_sent(uid, day, slot):
                            continue
                        subjects = get_user_subjects(uid) or []
                        subject = (subjects[0] if subjects else "English").strip().title()
                        if subject not in ("English", "Russian"):
                            continue
                        lang = detect_lang_from_user(row)
                        text = (
                            f"{t(lang, 'daily_test_reminder_text')}\n\n"
                            f"📘 Subject: {subject}\n"
                            f"🕒 Time: {target_time}"
                        )
                        daily_url = _student_miniapp_url("daily-test-process", extra={"auto_join": 1, "subject": subject})
                        kb = (
                            InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [
                                        InlineKeyboardButton(
                                            text=t(lang, "daily_test_start_btn"),
                                            web_app=WebAppInfo(url=daily_url),
                                        )
                                    ]
                                ]
                            )
                            if daily_url
                            else None
                        )
                        try:
                            await bot.send_message(int(tg), text, reply_markup=kb)
                        except Exception as exc:
                            log_telegram_delivery_failure(
                                logger,
                                "daily_test_reminder send failed user_id=%s slot=%s",
                                uid,
                                slot,
                                exc=exc,
                            )
            except Exception:
                logger.exception("daily_test_reminder_scheduler error")
            await asyncio.sleep(25)

    async def season_end_scheduler():
        # User requested to completely disable end of month season leaderboard broadcasts.
        pass

    # Run scheduler in background
    spawn_guarded_task(cleanup_scheduler(), name="student_cleanup_scheduler")
    spawn_guarded_task(duel_timeout_scheduler(), name="student_duel_timeout_scheduler")
    spawn_guarded_task(scheduled_arena_announcer(), name="student_scheduled_arena_announcer")
    spawn_guarded_task(daily_test_reminder_scheduler(), name="student_daily_test_reminder_scheduler")
    # spawn_guarded_task(season_end_scheduler(), name="student_season_end_scheduler")  # Disabled per user request
    logger.info("🧹 Inactive account cleanup scheduler started (runs every 24 hours)")
    
    logger.info("Student bot started successfully")
    await run_bot_dispatcher(dp=dp, bot=bot, bot_name="student", webhook_port=STUDENT_WEBHOOK_PORT)


# ==================== GRAMMAR LEVEL + PAGINATION ====================

def get_grammar_level_keyboard(lang: str, subject: str = "English"):
    """gr_lvl_* callbacks; English 5 choices (single B1), Russian 4 tier labels."""
    subj = (subject or "English").strip().title()
    if subj == "Russian":
        keyboard = [
            [
                InlineKeyboardButton(text=t(lang, "level_ru_tier_beginner"), callback_data="gr_lvl_A1"),
                InlineKeyboardButton(text=t(lang, "level_ru_tier_elementary"), callback_data="gr_lvl_A2"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "level_ru_tier_basic"), callback_data="gr_lvl_B1"),
                InlineKeyboardButton(text=t(lang, "level_ru_tier_upper_mid"), callback_data="gr_lvl_B2"),
            ],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton(text=level_ui_label(lang, subject=subj, code="A1"), callback_data="gr_lvl_A1"),
                InlineKeyboardButton(text=level_ui_label(lang, subject=subj, code="A2"), callback_data="gr_lvl_A2"),
            ],
            [
                InlineKeyboardButton(text=t(lang, "grammar_level_btn_b1_pre"), callback_data="gr_lvl_B1"),
                InlineKeyboardButton(text=level_ui_label(lang, subject=subj, code="B2"), callback_data="gr_lvl_B2"),
                InlineKeyboardButton(text=level_ui_label(lang, subject=subj, code="C1"), callback_data="gr_lvl_C1"),
            ],
        ]
    keyboard.append([InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_paginated_topics_keyboard(level: str, page: int = 0, per_page: int = 10, lang: str = 'uz'):
    """Mavzular grammar_content.get_topics_by_level dan; tanlash gr_topic_pick / gr_topic_page."""
    topics = get_topics_by_level(level)
    if not topics:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, 'btn_back'), callback_data="menu_grammar")],
        ])
    total = len(topics)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    chunk = topics[start:start + per_page]

    keyboard = []
    for tp in chunk:
        label = (tp.title[:58] + "…") if len(tp.title) > 59 else tp.title
        topic_token = _grammar_topic_token(tp.topic_id)
        keyboard.append([
            InlineKeyboardButton(
                text=label,
                callback_data=f"gr_topic_pick:{level}:{topic_token}",
            ),
        ])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text=t(lang, 'btn_prev'), callback_data=f"gr_topic_page:{level}:{page - 1}"))
    if start + per_page < total:
        nav_row.append(InlineKeyboardButton(text=t(lang, 'btn_next_arrow'), callback_data=f"gr_topic_page:{level}:{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text=t(lang, 'grammar_back_to_levels_legacy'), callback_data="menu_grammar")])
    keyboard.append([InlineKeyboardButton(text=t(lang, 'main_menu_legacy_btn'), callback_data="menu_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


@dp.error()
async def error_handler(event: types.ErrorEvent):
    exc = event.exception
    if isinstance(exc, (TelegramNetworkError, TelegramServerError)):
        logger.warning("Suppressed transient Telegram API/network error (legacy handler): %s", exc)
        return True
    logger.error(f"Error in student bot: {exc}", exc_info=True)

    # 1) Write to log.txt
    try:
        log_file = Path(__file__).resolve().parent / "log.txt"
        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(f"Student bot error: {repr(exc)}\n")
            f.write(stack)
            f.write("\n")
    except Exception:
        logger.exception("Failed to write student bot error to log.txt")

    # 2) Notify admins (best-effort)
    try:
        if bot:
            update_info = getattr(event, "update", None)
            update_id = getattr(update_info, "update_id", None)
            short = f"Student bot xatolik: {repr(exc)}"
            if update_id is not None:
                short += f" (update_id={update_id})"
            for aid in ADMIN_CHAT_IDS:
                await bot.send_message(int(aid), short)
    except Exception:
        logger.exception("Failed to notify admins about student bot error")


@dp.callback_query(lambda c: c.data.startswith('set_lang_me_'))
async def handle_set_lang_me(callback: CallbackQuery):
    code = callback.data.split('_')[-1]
    ok = set_user_language_by_telegram(str(callback.from_user.id), code)
    if ok:
        await callback.answer()
        await callback.message.answer(t(code, 'lang_set'))
        # Send updated main menu in new language
        await callback.message.answer(t(code, 'select_from_menu'), reply_markup=student_main_keyboard(code))
    else:
        await callback.answer()
        await callback.message.answer(t(code, 'please_send_start'))
