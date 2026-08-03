import asyncio
import hashlib
import html
import time
import traceback
from datetime import datetime, time as dtime_cls, timedelta, timezone
from uuid import uuid4

import pytz
from aiogram import Bot, Dispatcher, F
from aiogram.types import ErrorEvent
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from config import (
    SUPPORT_BOT_TOKEN,
    STUDENT_BOT_TOKEN,
    TEACHER_BOT_TOKEN,
    ALL_ADMIN_IDS,
    SUPPORT_WEBHOOK_PORT,
)
from bot_runtime import create_resilient_bot, run_bot_dispatcher, spawn_guarded_task
from i18n import t, detect_lang_from_user
from logging_config import get_logger
from bot_error_notify import notify_admins_unhandled_bot_error
from support_booking_time import support_make_end_ts, support_make_start_ts, normalize_time_hhmm
from auth import process_login_message, get_login_state, set_login_state, clear_login_state
from db import (
    ensure_support_lessons_schema,
    upsert_lesson_user,
    set_lesson_user_lang,
    list_lesson_upcoming_bookings,
    get_lesson_booking,
    set_lesson_booking_status,
    reschedule_lesson_booking,
    get_user_by_id,
    get_user_by_telegram,
    list_lesson_extra_slots_for_date,
    add_lesson_extra_slot,
    remove_lesson_extra_slot,
    add_blocked_slot,
    remove_blocked_slot,
    is_slot_blocked,
    is_slot_closed_effective,
    get_slot_block_reason,
    list_recurring_open_times_for_date,
    add_recurring_slot_rule,
    remove_recurring_slot_rule,
    lesson_is_slot_free,
    is_lesson_holiday,
    is_lesson_otmen_date_cancelled,
    is_branch_date_closed_for_booking,
    set_branch_date_closed,
    open_branch_date_for_booking,
    list_branch_dates_closed,
    get_branch_date_closed_reason,
    get_lesson_branch_weekdays,
    set_lesson_branch_weekdays,
    update_lesson_booking_branch,
    support_dashboard_metrics,
    list_student_telegram_ids_with_upcoming_bookings,
    list_student_telegram_ids_had_bookings,
    list_all_student_telegram_ids,
    claim_lesson_reminder_for_delivery,
    mark_lesson_reminder_sent,
    list_due_unsent_lesson_reminders,
    get_lesson_user as get_lesson_user_row,
    get_user_groups,
    get_user_subjects,
    get_student_teachers,
    get_student_subjects,
    get_dcoins,
    add_dpoints,
    set_support_booking_attendance,
    apply_support_attendance_penalty_if_needed,
    support_booking_bonus_allowed,
    apply_support_bonus_if_needed,
)

TZ = pytz.timezone("Asia/Tashkent")
logger = get_logger(__name__)
bot: Bot | None = None
student_notify_bot: Bot | None = None
teacher_notify_bot: Bot | None = None
dp = Dispatcher()
admin_state: dict[int, dict] = {}

SUPPORT_DEFAULT_TIMES = ["14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00", "17:30", "18:00"]

# Reply keyboard actions — must run even if a stale FSM mode is set from an unfinished inline flow.
SUPPORT_MAIN_MENU_ACTIONS = frozenset(
    {"dash", "bookings", "open_slot", "close_slot", "close_date", "broadcast", "weekdays", "language", "my_slots"}
)

# Ignore stray text while these modes expect inline/callback input (not reply menu).
_SUPPORT_WAITING_INLINE_MODES = frozenset(
    {
        "bc_collect",
        "bc_preview",
        "bc_fmt",
        "drm_close_confirm",
        "cs_confirm",
        "cs_perm",
        "os_perm",
        "os_confirm",
        "os_time",
        "os_date",
        "cs_date",
        "drm_close",
        "drm_open",
        "wd_branch",
    }
)


@dp.errors()
async def support_global_error_handler(event: ErrorEvent):
    exc = event.exception
    if isinstance(exc, TelegramBadRequest):
        msg = str(exc).lower()
        if "query is too old" in msg or "query id is invalid" in msg:
            logger.warning("Suppressed stale callback error: %s", exc)
            return True
    try:
        await notify_admins_unhandled_bot_error(
            bot_label="Support bot",
            event=event,
            admin_bot_instance=None,
        )
    except Exception:
        logger.exception("Adminlarga support bot xato xabari yuborilmadi")
    return False


def _admin_only(user_id: int) -> bool:
    user = get_user_by_telegram(str(user_id))
    if not user:
        return False
    return int(user.get("login_type") or 0) == 5 and int(user.get("logged_in") or 0) == 1


def _normalize_support_subject(value: object) -> str:
    return str(value or "").strip().casefold()


def _support_admin_user(user_id: int) -> dict | None:
    user = get_user_by_telegram(str(user_id))
    return user if user and int(user.get("login_type") or 0) == 5 and int(user.get("logged_in") or 0) == 1 else None


def _support_admin_subjects(user_id: int) -> set[str]:
    user = _support_admin_user(user_id)
    if not user:
        return set()
    subjects: set[str] = set()
    try:
        for item in get_user_subjects(int(user.get("id") or 0)) or []:
            subject = _normalize_support_subject(item)
            if subject:
                subjects.add(subject)
    except Exception:
        logger.exception("support admin subject lookup failed user_id=%s", user_id)
    for part in str(user.get("subject") or "").split(","):
        subject = _normalize_support_subject(part)
        if subject:
            subjects.add(subject)
    return subjects


def _support_admin_can_access_booking(user_id: int, booking: dict | None) -> bool:
    if not booking:
        return False
    user = _support_admin_user(user_id)
    if not user:
        return False
    assigned_teacher_id = int(booking.get("support_teacher_id") or 0)
    if assigned_teacher_id > 0:
        return assigned_teacher_id == int(user.get("id") or 0)
    booking_subject = _normalize_support_subject(booking.get("support_subject"))
    return bool(booking_subject and booking_subject in _support_admin_subjects(user_id))


async def _visible_booking_or_alert(callback: CallbackQuery, lang: str, bid: str) -> dict | None:
    b = get_lesson_booking(bid)
    if not b or not callback.from_user or not _support_admin_can_access_booking(callback.from_user.id, b):
        await callback.answer(t(lang, "support_admin_no_bookings"), show_alert=True)
        return None
    return b


def _admin_lang(admin_user) -> str:
    tg = str(admin_user.id)
    u = get_lesson_user_row(tg) or {}
    lang = (u.get("language") or "").strip()
    return lang if lang in ("uz", "ru", "en") else detect_lang_from_user(admin_user)


def _main_reply_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "support_rk_dashboard")),
                KeyboardButton(text=t(lang, "support_rk_bookings")),
            ],
            [
                KeyboardButton(text=t(lang, "support_rk_open_slot")),
                KeyboardButton(text=t(lang, "support_rk_close_slot")),
            ],
            [
                KeyboardButton(text=t(lang, "support_rk_my_slots")),
            ],
            [
                KeyboardButton(text=t(lang, "support_rk_close_date")),
                KeyboardButton(text=t(lang, "support_rk_broadcast")),
            ],
            [
                KeyboardButton(text=t(lang, "support_rk_weekdays")),
                KeyboardButton(text=t(lang, "support_rk_language")),
            ],
        ],
        resize_keyboard=True,
    )


def _menu_action_for_text(lang: str, txt: str | None) -> str | None:
    if not txt:
        return None
    mapping = [
        (t(lang, "support_rk_dashboard"), "dash"),
        (t(lang, "support_rk_bookings"), "bookings"),
        (t(lang, "support_rk_open_slot"), "open_slot"),
        (t(lang, "support_rk_close_slot"), "close_slot"),
        (t(lang, "support_rk_my_slots"), "my_slots"),
        (t(lang, "support_rk_close_date"), "close_date"),
        (t(lang, "support_rk_broadcast"), "broadcast"),
        (t(lang, "support_rk_weekdays"), "weekdays"),
        (t(lang, "support_rk_language"), "language"),
        (t(lang, "support_rk_cancel"), "cancel"),
    ]
    for label, act in mapping:
        if txt.strip() == label:
            return act
    return None


_ALLOWED_DATES_CACHE: dict[tuple[str, int, str], list[str]] = {}


def _invalidate_allowed_dates_cache(branch_key: str | None = None) -> None:
    if branch_key in (None, "all"):
        _ALLOWED_DATES_CACHE.clear()
        return
    b = str(branch_key)
    for k in list(_ALLOWED_DATES_CACHE.keys()):
        if k[0] == b:
            _ALLOWED_DATES_CACHE.pop(k, None)


def _allowed_dates(branch_key: str, days_ahead: int = 14) -> list[str]:
    today_key = datetime.now(TZ).date().isoformat()
    cache_key = (str(branch_key), int(days_ahead), today_key)
    cached = _ALLOWED_DATES_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)
    t0 = time.monotonic()
    allowed_wd = set(get_lesson_branch_weekdays(str(branch_key)))
    closed_rows = list_branch_dates_closed(str(branch_key))
    closed_dates = {
        str(x.get("date"))
        for x in (closed_rows or [])
        if str(x.get("branch")) in (str(branch_key), "all")
    }
    today = datetime.now(TZ).date()
    out: list[str] = []
    for i in range(0, max(1, int(days_ahead))):
        d = today + timedelta(days=i)
        if d.weekday() == 6:
            continue
        iso = d.isoformat()
        if is_lesson_holiday(iso):
            continue
        if iso in closed_dates:
            continue
        if d.weekday() in allowed_wd:
            out.append(iso)
    _ALLOWED_DATES_CACHE[cache_key] = list(out)
    _flow_log(
        "info",
        "allowed_dates computed",
        branch=branch_key,
        days_ahead=days_ahead,
        elapsed_ms=int((time.monotonic() - t0) * 1000),
    )
    return out


def _branch_dates_with_closed_status(branch_key: str, days_ahead: int = 14) -> list[tuple[str, bool]]:
    """Return (date_iso, is_closed) for branch-visible days, keeping closed days in the list."""
    allowed_wd = set(get_lesson_branch_weekdays(str(branch_key)))
    today = datetime.now(TZ).date()
    out: list[tuple[str, bool]] = []
    for i in range(0, max(1, int(days_ahead))):
        d = today + timedelta(days=i)
        if d.weekday() == 6:
            continue
        iso = d.isoformat()
        if is_lesson_holiday(iso):
            continue
        if d.weekday() not in allowed_wd:
            continue
        out.append((iso, is_branch_date_closed_for_booking(str(branch_key), iso)))
    return out


def _times_union(date_iso: str, branch: str) -> list[str]:
    extras = list_lesson_extra_slots_for_date(date_iso, branch) or []
    return sorted(set(SUPPORT_DEFAULT_TIMES + [x for x in extras if x]))


def _other_branch(branch: str) -> str:
    return "branch_2" if str(branch) == "branch_1" else "branch_1"


def _wd_keyboard_rows(lang: str, branch: str, selected: set[int]) -> list[list[InlineKeyboardButton]]:
    names = [("wd0", 0), ("wd1", 1), ("wd2", 2), ("wd3", 3), ("wd4", 4), ("wd5", 5), ("wd6", 6)]
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key, idx in names:
        mark = "✓" if idx in selected else "○"
        row.append(
            InlineKeyboardButton(
                text=f"{mark} {t(lang, 'support_wd_' + key)}",
                callback_data=f"s2:wd:t:{branch}:{idx}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            InlineKeyboardButton(text=t(lang, "support_branch_1"), callback_data="s2:wd:b:branch_1"),
            InlineKeyboardButton(text=t(lang, "support_branch_2"), callback_data="s2:wd:b:branch_2"),
        ]
    )
    return rows


def _half_hour_slots() -> list[str]:
    out: list[str] = []
    for h in range(8, 23):
        for mm in (0, 30):
            if h == 22 and mm > 0:
                break
            out.append(f"{h:02d}:{mm:02d}")
    return out


def _weekday_name(date_iso: str, lang: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
        idx = d.weekday()
        if lang == "ru":
            names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        elif lang == "en":
            names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        else:
            names = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        return names[idx]
    except Exception:
        return ""


def _weekday_short(date_iso: str, lang: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
        idx = d.weekday()
        if lang == "ru":
            names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        elif lang == "en":
            names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        else:
            names = ["Du", "Se", "Ch", "Pa", "Ju", "Sha", "Ya"]
        return names[idx]
    except Exception:
        return ""


def _date_short_mon_ddmm(date_iso: str, lang: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
        return f"{_weekday_short(date_iso, lang)} {d.day:02d}.{d.month:02d}"
    except Exception:
        return date_iso


def _long_date(date_iso: str, lang: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
        mkey = f"support_cal_m{d.month}"
        return t(lang, mkey, day=d.day, year=d.year)
    except Exception:
        return date_iso


def _branch_label(lang: str, br: str) -> str:
    return t(lang, "support_branch_1") if br == "branch_1" else t(lang, "support_branch_2")


def _student_name_link(b: dict, u: dict | None, lang: str) -> str:
    fn = (u or {}).get("first_name") or ""
    ln = (u or {}).get("last_name") or ""
    name = html.escape(f"{fn} {ln}".strip() or "—")
    tg = b.get("student_telegram_id")
    un = (u or {}).get("username")
    if un:
        uname = html.escape(str(un).lstrip("@"))
        if uname:
            return f'<a href="https://t.me/{uname}">{name}</a>'
    if tg:
        try:
            return f'<a href="tg://user?id={int(tg)}">{name}</a>'
        except Exception:
            return name
    return name


async def _notify_student(booking: dict, text: str):
    tg = booking.get("student_telegram_id")
    if not tg or not student_notify_bot:
        return
    try:
        await student_notify_bot.send_message(int(tg), text, parse_mode="HTML")
    except Exception:
        pass


def _clear_state(uid: int):
    admin_state.pop(uid, None)


def _flow_log(level: str, message: str, **ctx):
    payload = " ".join(f"{k}={ctx.get(k)!r}" for k in sorted(ctx.keys()) if ctx.get(k) is not None)
    text = f"{message}" + (f" | {payload}" if payload else "")
    if level == "error":
        logger.error(text)
    elif level == "warning":
        logger.warning(text)
    else:
        logger.info(text)


def _parse_cb_time(token: str | None) -> str | None:
    raw = (token or "").replace(".", ":")
    return normalize_time_hhmm(raw)


def _state_has_fields(st: dict, fields: list[str]) -> bool:
    return all(bool(st.get(k)) for k in fields)


async def _notify_traceback_admins(where: str, exc: Exception, *, user_id: int | None = None, payload: str | None = None):
    tb = traceback.format_exc()
    _flow_log("error", "Support flow exception", where=where, user_id=user_id, payload=payload, error=str(exc))
    if not bot:
        return
    body = (
        f"🚨 <b>Support bot traceback</b>\n"
        f"📍 <b>Where:</b> {html.escape(where)}\n"
        f"👤 <b>User ID:</b> {html.escape(str(user_id or '—'))}\n"
        f"🧩 <b>Payload:</b> {html.escape(payload or '—')}\n\n"
        f"<pre>{html.escape(tb[-3500:])}</pre>"
    )
    for aid in list(dict.fromkeys(ALL_ADMIN_IDS or [])):
        try:
            await bot.send_message(int(aid), body, parse_mode="HTML")
        except Exception:
            continue


@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not message.from_user:
        return
    if not _admin_only(message.from_user.id):
        tg = str(message.from_user.id)
        clear_login_state(tg)
        set_login_state(tg, {"step": "ask_login", "data": {}})
        lang = detect_lang_from_user(message.from_user)
        await message.answer("Support botga kirish uchun login ID kiriting.")
        await message.answer(t(lang, "ask_login_id"))
        return
    ensure_support_lessons_schema()
    upsert_lesson_user(
        telegram_id=str(message.from_user.id),
        lang=detect_lang_from_user(message.from_user),
        first_name=message.from_user.first_name,
        username=message.from_user.username,
    )
    _clear_state(message.from_user.id)
    lang = _admin_lang(message.from_user)
    await message.answer(t(lang, "support_admin_welcome"), reply_markup=_main_reply_kb(lang))


@dp.message(lambda m: bool(get_login_state(str(m.from_user.id)).get("step") in ("ask_login", "ask_password")))
async def support_login_flow(message: Message):
    if not message.from_user:
        return
    ok = await process_login_message(message, expected_login_type=5)
    if not ok:
        return
    ensure_support_lessons_schema()
    upsert_lesson_user(
        telegram_id=str(message.from_user.id),
        lang=detect_lang_from_user(message.from_user),
        first_name=message.from_user.first_name,
        username=message.from_user.username,
    )
    lang = _admin_lang(message.from_user)
    await message.answer(t(lang, "support_admin_welcome"), reply_markup=_main_reply_kb(lang))


@dp.message(Command("lang"))
async def cmd_lang(message: Message):
    if not message.from_user or not _admin_only(message.from_user.id):
        await message.answer(t(detect_lang_from_user(message.from_user), "admin_only"))
        return
    lang = _admin_lang(message.from_user)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "lang_btn_uz"), callback_data="s2:lang:uz")],
            [InlineKeyboardButton(text=t(lang, "lang_btn_ru"), callback_data="s2:lang:ru")],
            [InlineKeyboardButton(text=t(lang, "lang_btn_en"), callback_data="s2:lang:en")],
        ]
    )
    await message.answer(t(lang, "support_choose_language_prompt"), reply_markup=kb)


async def _send_dashboard(message: Message, lang: str):
    today = datetime.now(TZ).date().isoformat()
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()
    m = support_dashboard_metrics(today, now_utc)
    mom_c = m.get("mom_created_month_pct") or "—"
    mom_m = m.get("mom_mtd_pct") or "—"
    txt = t(
        lang,
        "support_dash_body",
        users=m.get("lesson_users", 0),
        active_upcoming=m.get("active_upcoming", 0),
        past_ended=m.get("past_ended", 0),
        today_bookings=m.get("today_bookings", 0),
        total_bookings=m.get("total_bookings", 0),
        created_month=m.get("bookings_created_this_month", 0),
        created_last=m.get("bookings_created_last_month", 0),
        mom_created=mom_c,
        mtd=m.get("mtd_bookings", 0),
        mtd_prev=m.get("mtd_prev_month_bookings", 0),
        mom_mtd=mom_m,
    )
    await message.answer(txt, parse_mode="HTML")


def _bookings_page_kb(lang: str, page: int, total_pages: int) -> list[list[InlineKeyboardButton]]:
    rows: list[list[InlineKeyboardButton]] = []
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="«", callback_data=f"s2:ub:p:{page - 1}"))
    for p in range(max(1, page - 2), min(total_pages, page + 2) + 1):
        nav.append(
            InlineKeyboardButton(
                text=str(p),
                callback_data=f"s2:ub:p:{p}",
            )
        )
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="»", callback_data=f"s2:ub:p:{page + 1}"))
    if nav:
        rows.append(nav)
    return rows


async def _send_bookings_list(message: Message, lang: str, page: int = 1, admin_tg_id: int | None = None):
    now_utc = datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()
    actor_id = int(admin_tg_id or (message.from_user.id if message.from_user else 0))
    all_items, _ = list_lesson_upcoming_bookings(page=1, per_page=200, now_iso_utc=now_utc)
    visible_items = [item for item in (all_items or []) if _support_admin_can_access_booking(actor_id, item)]
    total_pages = max(1, (len(visible_items) + 9) // 10)
    page = max(1, min(int(page or 1), total_pages))
    items = visible_items[(page - 1) * 10 : page * 10]
    if not items:
        await message.answer(t(lang, "support_admin_no_bookings"))
        return
    lines = [t(lang, "support_ub_title", page=page, total_pages=total_pages), ""]
    num_row: list[InlineKeyboardButton] = []
    for i, b in enumerate(items, start=1):
        u = get_user_by_id(int(b.get("student_user_id") or 0))
        bid = str(b.get("id"))
        lines.append(
            t(
                lang,
                "support_ub_line",
                n=i,
                booking_id=html.escape(bid),
                name=_student_name_link(b, u, lang),
                profile=_student_name_link(b, u, lang),
                purpose=html.escape(str(b.get("purpose") or "—")),
                weekday=_weekday_name(str(b.get("date") or ""), lang),
                date=_long_date(str(b.get("date") or ""), lang),
                time=html.escape(str(b.get("time") or "")),
                branch=_branch_label(lang, str(b.get("branch") or "")),
            )
        )
        num_row.append(InlineKeyboardButton(text=str(i), callback_data=f"s2:ub:d:{bid}"))
    rows = []
    for j in range(0, len(num_row), 5):
        rows.append(num_row[j : j + 5])
    rows.extend(_bookings_page_kb(lang, page, total_pages))
    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


async def _send_booking_detail(message: Message, lang: str, bid: str, admin_tg_id: int | None = None):
    b = get_lesson_booking(bid)
    actor_id = int(admin_tg_id or (message.from_user.id if message.from_user else 0))
    if not b or not _support_admin_can_access_booking(actor_id, b):
        await message.answer(t(lang, "support_admin_no_bookings"))
        return
    u = get_user_by_id(int(b.get("student_user_id") or 0))
    text = t(
        lang,
        "support_bd_body",
        booking_id=html.escape(str(b.get("id"))),
        name=_student_name_link(b, u, lang),
        profile=_student_name_link(b, u, lang),
        purpose=html.escape(str(b.get("purpose") or "—")),
        weekday=_weekday_name(str(b.get("date") or ""), lang),
        date=_long_date(str(b.get("date") or ""), lang),
        time=html.escape(str(b.get("time") or "")),
        branch=_branch_label(lang, str(b.get("branch") or "")),
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "support_bd_change_time"), callback_data=f"s2:bd:tm:{bid}")],
            [InlineKeyboardButton(text=t(lang, "support_bd_change_date"), callback_data=f"s2:bd:dt:{bid}")],
            [InlineKeyboardButton(text=t(lang, "support_bd_change_branch"), callback_data=f"s2:bd:br:{bid}")],
            [InlineKeyboardButton(text=t(lang, "support_bd_reject"), callback_data=f"s2:bd:rj:{bid}")],
            [InlineKeyboardButton(text=t(lang, "support_bd_write_student"), callback_data=f"s2:bd:wm:{bid}")],
        ]
    )
    await message.answer(text, parse_mode="HTML", reply_markup=kb)


def _time_grid_kb(bid: str, date_iso: str, branch: str, lang: str) -> InlineKeyboardMarkup:
    times = _times_union(date_iso, branch)
    now_tz = datetime.now(TZ)
    today_tz = now_tz.date()
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except Exception:
        d = today_tz
    row: list[InlineKeyboardButton] = []
    rows: list[list[InlineKeyboardButton]] = []
    for tm in times:
        start_ts = support_make_start_ts(date_iso, tm) or ""
        blocked = is_slot_blocked(branch, date_iso, tm)
        free = (lesson_is_slot_free(start_ts) if start_ts else True) and not blocked
        try:
            hh, mm = [int(x) for x in tm.split(":", 1)]
            local_dt = TZ.localize(datetime.combine(d, dtime_cls(hh, mm)))
            slot_passed = (d == today_tz) and (local_dt <= now_tz)
        except Exception:
            slot_passed = False
        tkn = tm.replace(":", ".")
        if slot_passed:
            row.append(InlineKeyboardButton(text="·", callback_data="s2:noop"))
        elif not free:
            row.append(InlineKeyboardButton(text="✗", callback_data="s2:noop"))
        else:
            row.append(InlineKeyboardButton(text=tm, callback_data=f"s2:bd:tt:{bid}:{tkn}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"s2:ub:d:{bid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _date_pick_kb(bid: str, branch: str, lang: str) -> InlineKeyboardMarkup:
    dates = _allowed_dates(branch, 14)
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for iso in dates[:14]:
        label = f"{iso[-5:]} {_weekday_name(iso, lang)[:3]}"
        row.append(InlineKeyboardButton(text=label, callback_data=f"s2:bd:dd:{bid}:{iso}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"s2:ub:d:{bid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(lambda c: (c.data or "").startswith("s2:"))
async def callbacks(callback: CallbackQuery):
    if not callback.from_user or not _admin_only(callback.from_user.id):
        await callback.answer(t(detect_lang_from_user(callback.from_user), "admin_only"), show_alert=True)
        return
    lang = _admin_lang(callback.from_user)
    data = callback.data or ""
    parts = data.split(":")
    _flow_log("info", "Support callback", user_id=callback.from_user.id, data=data)


    if parts[1] == "mys":
        if len(parts) >= 4 and parts[2] == "s":
            # Pick subject -> show weekdays
            subj = parts[3]
            rows = []
            for wd in range(7):
                rows.append([InlineKeyboardButton(text=_admin_weekday_label(wd, lang), callback_data=f"s2:mys:w:{subj}:{wd}")])
            await callback.message.edit_text(
                t(lang, "support_myslots_pick_weekday", subject=subj.capitalize()),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
            )
            return

        if len(parts) >= 5 and parts[2] == "w":
            # Pick weekday -> show time slots for this subject + weekday
            subj = parts[3]
            wd = int(parts[4])
            from db import list_support_teacher_slots_by_weekday
            from support_booking_time import normalize_time_hhmm
            
            # _weekly_slot_time_candidates() o'rniga oddiy ro'yxat yaratamiz
            all_times = []
            from datetime import datetime, timedelta
            start = datetime.strptime('08:00', '%H:%M')
            for i in range(29):
                all_times.append((start + timedelta(minutes=30 * i)).strftime('%H:%M'))
                
            active_times = set(list_support_teacher_slots_by_weekday(callback.from_user.id, subj, wd))
            
            rows = []
            row = []
            for tm in all_times:
                mark = "✅" if tm in active_times else "❌"
                tkn = tm.replace(":", ".")
                row.append(InlineKeyboardButton(f"{mark} {tm}", callback_data=f"s2:mys:t:{subj}:{wd}:{tkn}"))
                if len(row) == 3:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            rows.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data=f"s2:mys:s:{subj}")])
            
            await callback.message.edit_text(
                t(lang, "support_myslots_toggle", subject=subj.capitalize(), weekday=_admin_weekday_label(wd, lang)),
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
            )
            return

        if len(parts) >= 6 and parts[2] == "t":
            # Toggle time slot
            subj = parts[3]
            wd = int(parts[4])
            tkn = parts[5]
            time_str = tkn.replace(".", ":")
            
            from db import toggle_support_teacher_slot
            toggle_support_teacher_slot(callback.from_user.id, subj, wd, time_str)
            
            # Refresh slots
            from db import list_support_teacher_slots_by_weekday
            all_times = []
            from datetime import datetime, timedelta
            start = datetime.strptime('08:00', '%H:%M')
            for i in range(29):
                all_times.append((start + timedelta(minutes=30 * i)).strftime('%H:%M'))
                
            active_times = set(list_support_teacher_slots_by_weekday(callback.from_user.id, subj, wd))
            
            rows = []
            row = []
            for tm in all_times:
                mark = "✅" if tm in active_times else "❌"
                tkn2 = tm.replace(":", ".")
                row.append(InlineKeyboardButton(f"{mark} {tm}", callback_data=f"s2:mys:t:{subj}:{wd}:{tkn2}"))
                if len(row) == 3:
                    rows.append(row)
                    row = []
            if row:
                rows.append(row)
            rows.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data=f"s2:mys:s:{subj}")])
            
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
            return

    if data == "s2:drm:cf":
        try:
            st = admin_state.get(callback.from_user.id) or {}
            if not _state_has_fields(st, ["branch", "date"]):
                _flow_log("warning", "DRM confirm missing state", user_id=callback.from_user.id, state=st)
                _clear_state(callback.from_user.id)
                await callback.message.answer(t(lang, "support_state_expired_restart"))
                await callback.answer()
                return
            br = st.get("branch")
            d_iso = st.get("date")
            reason = st.get("reason") or ""
            if br == "all":
                ok1 = set_branch_date_closed("branch_1", str(d_iso), reason)
                ok2 = set_branch_date_closed("branch_2", str(d_iso), reason)
                ok = bool(ok1 and ok2)
                if ok:
                    _invalidate_allowed_dates_cache("all")
                _flow_log("info", "DRM close write all", user_id=callback.from_user.id, date=d_iso, ok1=ok1, ok2=ok2, reason=reason)
            else:
                ok = set_branch_date_closed(str(br), str(d_iso), reason)
                if ok:
                    _invalidate_allowed_dates_cache(str(br))
                _flow_log("info", "DRM close write single", user_id=callback.from_user.id, branch=br, date=d_iso, ok=ok, reason=reason)
            if ok:
                if str(br) == "all":
                    rb1 = is_branch_date_closed_for_booking("branch_1", str(d_iso))
                    rb2 = is_branch_date_closed_for_booking("branch_2", str(d_iso))
                    ok = rb1 and rb2
                    _flow_log("info", "DRM close readback all", user_id=callback.from_user.id, date=d_iso, rb1=rb1, rb2=rb2)
                else:
                    rb = is_branch_date_closed_for_booking(str(br), str(d_iso))
                    ok = rb
                    _flow_log("info", "DRM close readback single", user_id=callback.from_user.id, branch=br, date=d_iso, readback=rb)
            _clear_state(callback.from_user.id)
            if not ok and str(br) == "all":
                await callback.message.answer(t(lang, "support_drm_close_partial_failed"))
            else:
                await callback.message.answer(t(lang, "support_drm_closed_ok") if ok else t(lang, "support_drm_close_failed"))
            await callback.answer()
            return
        except Exception as e:
            await _notify_traceback_admins("callbacks:s2:drm:cf", e, user_id=callback.from_user.id, payload=data)
            await callback.answer(t(lang, "support_error_generic"), show_alert=True)
        return

    if data == "s2:drm:cn":
        _clear_state(callback.from_user.id)
        await callback.message.answer(t(lang, "support_state_cancelled"))
        await callback.answer()
        return

    if data == "s2:cs:cn":
        _clear_state(callback.from_user.id)
        await callback.message.answer(t(lang, "support_state_cancelled"))
        await callback.answer()
        return

    if data == "s2:noop":
        await callback.answer()
        return

    if parts[1] == "lang" and len(parts) >= 3:
        code = parts[2]
        if code not in ("uz", "ru", "en"):
            code = "en"
        set_lesson_user_lang(str(callback.from_user.id), code)
        await callback.message.answer(t(code, "support_admin_lang_set"), reply_markup=_main_reply_kb(code))
        await callback.answer()
        return

    if parts[1] == "att" and len(parts) >= 5:
        att_status = parts[2]
        booking_id = parts[3]
        try:
            expires_ts = int(parts[4])
        except Exception:
            await callback.answer(t(lang, "support_action_expired"), show_alert=True)
            return
        if int(time.time()) > expires_ts:
            await callback.answer(t(lang, "support_action_expired"), show_alert=True)
            return
        if att_status not in ("present", "late", "absent"):
            await callback.answer(t(lang, "invalid_action"), show_alert=True)
            return

        ok = set_support_booking_attendance(booking_id, att_status)
        if not ok:
            await callback.answer(t(lang, "support_error_generic"), show_alert=True)
            return

        if att_status == "late":
            applied, uid = apply_support_attendance_penalty_if_needed(booking_id, 5.0)
            if applied and uid:
                add_dpoints(int(uid), -5.0, "English", change_type="support_lesson_late")
        elif att_status == "absent":
            applied, uid = apply_support_attendance_penalty_if_needed(booking_id, 10.0)
            if applied and uid:
                add_dpoints(int(uid), -10.0, "English", change_type="support_lesson_absent")

        await callback.answer(t(lang, "support_attendance_marked_ok"))
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if parts[1] == "bonus" and len(parts) >= 5:
        try:
            amount = int(parts[2])
            booking_id = parts[3]
            expires_ts = int(parts[4])
        except Exception:
            await callback.answer(t(lang, "support_action_expired"), show_alert=True)
            return
        if int(time.time()) > expires_ts:
            await callback.answer(t(lang, "support_action_expired"), show_alert=True)
            return
        if amount < 1 or amount > 10:
            await callback.answer(t(lang, "invalid_action"), show_alert=True)
            return

        applied, uid = apply_support_bonus_if_needed(booking_id, float(amount))
        if not applied:
            await callback.answer(t(lang, "support_bonus_already_applied"), show_alert=True)
            return
        if uid:
            add_dpoints(int(uid), float(amount), "English", change_type="support_lesson_bonus")
        await callback.answer(t(lang, "support_bonus_saved", amount=amount))
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        return

    if parts[1] == "ub" and parts[2] == "p" and len(parts) >= 4:
        page = max(1, int(parts[3] or 1))
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.exception("Failed to clear reply markup for bookings page")
        await _send_bookings_list(callback.message, lang, page=page, admin_tg_id=callback.from_user.id)
        await callback.answer()
        return

    if parts[1] == "ub" and parts[2] == "d" and len(parts) >= 4:
        bid = parts[3]
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.exception("Failed to clear reply markup for booking detail")
        await _send_booking_detail(callback.message, lang, bid, admin_tg_id=callback.from_user.id)
        await callback.answer()
        return

    if parts[1] == "bd" and parts[2] == "tm" and len(parts) >= 4:
        bid = parts[3]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        await callback.message.answer(
            t(lang, "support_pick_new_time"),
            reply_markup=_time_grid_kb(bid, str(b.get("date")), str(b.get("branch")), lang),
        )
        await callback.answer()
        return

    if parts[1] == "bd" and parts[2] == "tt" and len(parts) >= 5:
        bid = parts[3]
        tm_raw = parts[4].replace(".", ":")
        tm = normalize_time_hhmm(tm_raw)
        if not tm:
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        date_iso = str(b.get("date"))
        if is_lesson_holiday(date_iso) or is_lesson_otmen_date_cancelled(date_iso):
            await callback.answer(t(lang, "lesson_canceled_for_date_alert", date=date_iso), show_alert=True)
            return
        br = str(b.get("branch"))
        st = support_make_start_ts(date_iso, tm) or ""
        if not st or not lesson_is_slot_free(st) or is_slot_blocked(br, date_iso, tm):
            await callback.answer(t(lang, "support_slot_unavailable"), show_alert=True)
            return
        ok = reschedule_lesson_booking(bid, date_iso, tm, None, int(callback.from_user.id))
        if ok:
            nb = get_lesson_booking(bid) or {}
            await _notify_student(nb, t(lang, "support_student_rescheduled", date=nb.get("date"), time=nb.get("time")))
        await callback.answer(t(lang, "support_admin_rescheduled_ok") if ok else t(lang, "support_error_generic"), show_alert=not ok)
        try:
            await callback.message.delete()
        except Exception:
            logger.exception("Failed to delete callback message after time reschedule")
        return

    if parts[1] == "bd" and parts[2] == "dt" and len(parts) >= 4:
        bid = parts[3]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        await callback.message.answer(
            t(lang, "support_pick_new_date"),
            reply_markup=_date_pick_kb(bid, str(b.get("branch")), lang),
        )
        await callback.answer()
        return

    if parts[1] == "bd" and parts[2] == "dd" and len(parts) >= 5:
        bid = parts[3]
        new_date = parts[4]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        tm = normalize_time_hhmm(str(b.get("time")))
        if not tm:
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        if is_lesson_holiday(new_date) or is_lesson_otmen_date_cancelled(new_date):
            await callback.answer(t(lang, "lesson_canceled_for_date_alert", date=new_date), show_alert=True)
            return
        br = str(b.get("branch"))
        st = support_make_start_ts(new_date, tm) or ""
        if not st or not lesson_is_slot_free(st) or is_slot_blocked(br, new_date, tm):
            await callback.answer(t(lang, "support_slot_unavailable"), show_alert=True)
            return
        ok = reschedule_lesson_booking(bid, new_date, tm, None, int(callback.from_user.id))
        if ok:
            nb = get_lesson_booking(bid) or {}
            await _notify_student(nb, t(lang, "support_student_rescheduled", date=nb.get("date"), time=nb.get("time")))
        await callback.answer(t(lang, "support_admin_rescheduled_ok") if ok else t(lang, "support_error_generic"), show_alert=not ok)
        try:
            await callback.message.delete()
        except Exception:
            logger.exception("Failed to delete callback message after date reschedule")
        return

    if parts[1] == "bd" and parts[2] == "br" and len(parts) >= 4:
        bid = parts[3]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_1"),
                        callback_data=f"s2:bd:bb:{bid}:branch_1",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_2"),
                        callback_data=f"s2:bd:bb:{bid}:branch_2",
                    ),
                ],
                [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data=f"s2:ub:d:{bid}")],
            ]
        )
        await callback.message.answer(t(lang, "support_pick_branch"), reply_markup=kb)
        await callback.answer()
        return

    if parts[1] == "bd" and parts[2] == "bb" and len(parts) >= 5:
        bid = parts[3]
        new_br = parts[4]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        ok = update_lesson_booking_branch(bid, new_br, int(callback.from_user.id))
        if ok:
            nb = get_lesson_booking(bid) or {}
            await _notify_student(
                nb,
                t(
                    lang,
                    "support_student_branch_changed",
                    branch=_branch_label(lang, new_br),
                ),
            )
        await callback.answer(t(lang, "support_branch_updated") if ok else t(lang, "support_error_generic"), show_alert=not ok)
        try:
            await callback.message.delete()
        except Exception:
            logger.exception("Failed to delete callback message after branch change")
        return

    if parts[1] == "bd" and parts[2] == "rj" and len(parts) >= 4:
        bid = parts[3]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_confirm_yes"),
                        callback_data=f"s2:bd:rx:{bid}",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "support_confirm_no"),
                        callback_data=f"s2:ub:d:{bid}",
                    ),
                ]
            ]
        )
        await callback.message.answer(t(lang, "support_reject_confirm"), reply_markup=kb)
        await callback.answer()
        return

    if parts[1] == "bd" and parts[2] == "rx" and len(parts) >= 4:
        bid = parts[3]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        ok = set_lesson_booking_status(bid, "canceled", admin_id=int(callback.from_user.id), admin_note="admin_rejected")
        if ok:
            b = get_lesson_booking(bid) or {}
            await _notify_student(b, t(lang, "support_student_canceled_by_admin"))
        await callback.answer(t(lang, "support_rejected_done") if ok else t(lang, "support_error_generic"), show_alert=not ok)
        try:
            await callback.message.delete()
        except Exception:
            logger.exception("Failed to delete callback message after reject")
        return

    if parts[1] == "bd" and parts[2] == "wm" and len(parts) >= 4:
        bid = parts[3]
        b = await _visible_booking_or_alert(callback, lang, bid)
        if not b:
            return
        admin_state[callback.from_user.id] = {"mode": "write_student", "booking_id": bid}
        await callback.message.answer(t(lang, "support_write_student_prompt"))
        await callback.answer()
        return

    if parts[1] == "drm" and len(parts) >= 3 and parts[2] in {"c", "o"}:
        sub = parts[2] if len(parts) > 2 else ""
        if sub == "c":
            admin_state[callback.from_user.id] = {"mode": "drm_close", "step": "branch"}
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=t(lang, "support_branch_1"),
                            callback_data="s2:drm:cb:branch_1",
                        ),
                        InlineKeyboardButton(
                            text=t(lang, "support_branch_2"),
                            callback_data="s2:drm:cb:branch_2",
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            text=t(lang, "support_drm_all_branches"),
                            callback_data="s2:drm:cb:all",
                        )
                    ],
                ]
            )
            await callback.message.answer(t(lang, "support_drm_pick_branch"), reply_markup=kb)
        elif sub == "o":
            admin_state[callback.from_user.id] = {"mode": "drm_open", "step": "branch"}
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=t(lang, "support_branch_1"),
                            callback_data="s2:drm:ob:branch_1",
                        ),
                        InlineKeyboardButton(
                            text=t(lang, "support_branch_2"),
                            callback_data="s2:drm:ob:branch_2",
                        ),
                    ],
                ]
            )
            await callback.message.answer(t(lang, "support_drm_open_pick_branch"), reply_markup=kb)
        await callback.answer()
        return

    if parts[1] == "drm" and parts[2] == "cb" and len(parts) >= 4:
        br = parts[3]
        admin_state[callback.from_user.id] = {"mode": "drm_close", "step": "date", "branch": br}
        if br == "all":
            today0 = datetime.now(TZ).date()
            dates = sorted(
                {(today0 + timedelta(days=i)).isoformat() for i in range(21) if (today0 + timedelta(days=i)).weekday() != 6}
            )
            closed_all = set()
            for x in list_branch_dates_closed(None):
                di = str(x.get("date") or "")
                if di:
                    closed_all.add(di)
        else:
            dates = [d for d, _ in _branch_dates_with_closed_status(br, 21)]
            closed_all = {d for d, is_closed in _branch_dates_with_closed_status(br, 21) if is_closed}
        rows: list[list[InlineKeyboardButton]] = []
        row: list[InlineKeyboardButton] = []
        for iso in dates[:16]:
            is_closed = iso in closed_all
            label = _date_short_mon_ddmm(iso, lang)
            if is_closed:
                label = f"🔒 {label}"
            row.append(InlineKeyboardButton(text=label, callback_data=f"s2:drm:cd:{br}:{iso}"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await callback.message.answer(
            t(lang, "support_drm_pick_date"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="—", callback_data="s2:noop")]]),
        )
        await callback.answer()
        return

    if parts[1] == "drm" and parts[2] == "cd" and len(parts) >= 5:
        br = parts[3]
        d_iso = parts[4]
        if br != "all" and is_branch_date_closed_for_booking(br, d_iso):
            rs = get_branch_date_closed_reason(br, d_iso)
            msg = t(lang, "support_day_closed_with_reason", reason=rs) if rs else t(lang, "support_day_closed_no_reason")
            await callback.answer(msg, show_alert=True)
            return
        admin_state[callback.from_user.id] = {
            "mode": "drm_close_reason",
            "branch": br,
            "date": d_iso,
        }
        await callback.message.answer(t(lang, "support_drm_enter_reason"))
        await callback.answer()
        return

    if parts[1] == "drm" and parts[2] == "ob" and len(parts) >= 4:
        br = parts[3]
        closed = [x for x in list_branch_dates_closed(br) if str(x.get("branch")) == br or str(x.get("branch")) == "all"]
        if not closed:
            await callback.answer(t(lang, "support_drm_nothing_closed"), show_alert=True)
            return
        rows: list[list[InlineKeyboardButton]] = []
        for rowd in closed[:12]:
            bbr = str(rowd.get("branch"))
            di = str(rowd.get("date"))
            rs = str(rowd.get("reason") or "").strip()
            lbl = f"{_branch_label(lang, bbr)} · {_date_short_mon_ddmm(di, lang)}"
            if rs:
                lbl += " 🔒"
            rows.append(
                [
                    InlineKeyboardButton(
                        text=lbl,
                        callback_data=f"s2:drm:ox:{bbr}:{di}",
                    )
                ]
            )
        await callback.message.answer(
            t(lang, "support_drm_pick_to_open"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    if parts[1] == "drm" and parts[2] == "ox" and len(parts) >= 5:
        bbr = parts[3]
        di = parts[4]
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_confirm_yes"),
                        callback_data=f"s2:drm:oy:{bbr}:{di}",
                    ),
                    InlineKeyboardButton(text=t(lang, "support_confirm_no"), callback_data="s2:noop"),
                ]
            ]
        )
        await callback.message.answer(t(lang, "support_drm_open_confirm", date=di), reply_markup=kb)
        await callback.answer()
        return

    if parts[1] == "drm" and parts[2] == "oy" and len(parts) >= 5:
        bbr = parts[3]
        di = parts[4]
        try:
            ok = open_branch_date_for_booking(bbr, di)
            if ok:
                _invalidate_allowed_dates_cache(bbr)
            rb = is_branch_date_closed_for_booking(bbr, di)
            _flow_log("info", "DRM open write/readback", user_id=callback.from_user.id, branch=bbr, date=di, db_write_ok=ok, readback_closed=rb)
            if ok and rb:
                ok = False
            await callback.answer(t(lang, "support_drm_opened_ok") if ok else t(lang, "support_drm_open_failed"), show_alert=not ok)
            return
        except Exception as e:
            await _notify_traceback_admins("callbacks:s2:drm:oy", e, user_id=callback.from_user.id, payload=data)
            await callback.answer(t(lang, "support_error_generic"), show_alert=True)
            return

    if parts[1] == "bc" and parts[2] == "aud" and len(parts) >= 4:
        aud = parts[3]
        if aud not in ("up", "had", "all"):
            await callback.answer()
            return
        admin_state[callback.from_user.id] = {"mode": "bc_fmt", "audience": aud}
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "support_bc_fmt_text"), callback_data="s2:bc:fmt:text")],
                [InlineKeyboardButton(text=t(lang, "support_bc_fmt_photo"), callback_data="s2:bc:fmt:photo")],
                [InlineKeyboardButton(text=t(lang, "support_bc_fmt_voice"), callback_data="s2:bc:fmt:voice")],
                [InlineKeyboardButton(text=t(lang, "support_bc_fmt_video_note"), callback_data="s2:bc:fmt:vnote")],
                [InlineKeyboardButton(text=t(lang, "support_bc_fmt_document"), callback_data="s2:bc:fmt:doc")],
                [InlineKeyboardButton(text=t(lang, "support_bc_fmt_video"), callback_data="s2:bc:fmt:video")],
                [InlineKeyboardButton(text=t(lang, "support_bc_fmt_audio"), callback_data="s2:bc:fmt:audio")],
            ]
        )
        await callback.message.answer(t(lang, "support_bc_pick_format"), reply_markup=kb)
        await callback.answer()
        return

    if parts[1] == "bc" and parts[2] == "fmt" and len(parts) >= 4:
        fmt = parts[3]
        st = admin_state.get(callback.from_user.id) or {}
        st["mode"] = "bc_collect"
        st["fmt"] = fmt
        admin_state[callback.from_user.id] = st
        await callback.message.answer(t(lang, "support_bc_send_content"))
        await callback.answer()
        return

    if parts[1] == "bc" and parts[2] == "ok":
        st = admin_state.get(callback.from_user.id) or {}
        payload = st.get("bc_payload") or {}
        aud = st.get("audience")
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc).isoformat()
        if aud == "up":
            recipients = list_student_telegram_ids_with_upcoming_bookings(now_utc)
        elif aud == "had":
            recipients = list_student_telegram_ids_had_bookings()
        else:
            recipients = list_all_student_telegram_ids()
        fmt = payload.get("fmt")
        ok_n = 0
        fail_n = 0
        if not student_notify_bot:
            await callback.answer(t(lang, "support_bc_no_student_bot"), show_alert=True)
            return
        for tid in recipients:
            try:
                if fmt == "text":
                    await student_notify_bot.send_message(
                        int(tid),
                        payload.get("text") or "",
                        parse_mode="HTML",
                    )
                elif fmt == "photo":
                    await student_notify_bot.send_photo(
                        int(tid),
                        payload.get("file_id"),
                        caption=payload.get("caption"),
                        parse_mode="HTML",
                    )
                elif fmt == "video":
                    await student_notify_bot.send_video(
                        int(tid),
                        payload.get("file_id"),
                        caption=payload.get("caption"),
                        parse_mode="HTML",
                    )
                elif fmt == "audio":
                    await student_notify_bot.send_audio(
                        int(tid),
                        payload.get("file_id"),
                        caption=payload.get("caption"),
                        parse_mode="HTML",
                    )
                elif fmt == "voice":
                    await student_notify_bot.send_voice(int(tid), payload.get("file_id"))
                elif fmt == "vnote":
                    await student_notify_bot.send_video_note(int(tid), payload.get("file_id"))
                elif fmt == "doc":
                    await student_notify_bot.send_document(
                        int(tid),
                        payload.get("file_id"),
                        caption=payload.get("caption"),
                        parse_mode="HTML",
                    )
                ok_n += 1
            except Exception:
                fail_n += 1
            await asyncio.sleep(0.04)
        _clear_state(callback.from_user.id)
        await callback.message.answer(t(lang, "support_bc_done", ok=ok_n, fail=fail_n))
        await callback.answer()
        return

    if parts[1] == "bc" and parts[2] == "no":
        _clear_state(callback.from_user.id)
        await callback.message.answer(t(lang, "support_bc_cancelled"))
        await callback.answer()
        return

    if parts[1] == "os" and parts[2] == "b" and len(parts) >= 4:
        br = parts[3]
        admin_state[callback.from_user.id] = {"mode": "os_date", "branch": br}
        dates = _branch_dates_with_closed_status(br, 14)
        rows: list[list[InlineKeyboardButton]] = []
        row: list[InlineKeyboardButton] = []
        for iso, is_closed in dates[:14]:
            label = _date_short_mon_ddmm(iso, lang)
            cb = f"s2:os:d:{br}:{iso}"
            if is_closed:
                label = f"🔒 {label}"
                cb = f"s2:os:dc:{br}:{iso}"
            row.append(InlineKeyboardButton(text=label, callback_data=cb))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await callback.message.answer(
            t(lang, "support_os_pick_date"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    if parts[1] == "os" and parts[2] == "dc" and len(parts) >= 5:
        br = parts[3]
        d_iso = parts[4]
        rs = get_branch_date_closed_reason(br, d_iso)
        msg = t(lang, "support_day_closed_with_reason", reason=rs) if rs else t(lang, "support_day_closed_no_reason")
        await callback.answer(msg, show_alert=True)
        return

    if parts[1] == "os" and parts[2] == "d" and len(parts) >= 5:
        br = parts[3]
        d_iso = parts[4]
        admin_state[callback.from_user.id] = {"mode": "os_time", "branch": br, "date": d_iso, "picked": None}
        row: list[InlineKeyboardButton] = []
        rows: list[list[InlineKeyboardButton]] = []
        for tm in _half_hour_slots():
            tkn = tm.replace(":", ".")
            row.append(InlineKeyboardButton(text=tm, callback_data=f"s2:os:t:{br}:{d_iso}:{tkn}"))
            if len(row) == 4:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await callback.message.answer(
            t(lang, "support_os_pick_time"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    if parts[1] == "os" and parts[2] == "t" and len(parts) >= 6:
        br = parts[3]
        d_iso = parts[4]
        tm = _parse_cb_time(parts[5])
        if not tm:
            _flow_log("warning", "OS pick time invalid", user_id=callback.from_user.id, branch=br, date=d_iso, raw=parts[5])
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        admin_state[callback.from_user.id] = {"mode": "os_perm", "branch": br, "date": d_iso, "time": tm}
        tkn = tm.replace(":", ".")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=t(lang, "support_confirm_yes"), callback_data=f"s2:os:p:1:{br}:{d_iso}:{tkn}"),
                    InlineKeyboardButton(text=t(lang, "support_confirm_no"), callback_data=f"s2:os:p:0:{br}:{d_iso}:{tkn}"),
                ]
            ]
        )
        await callback.message.answer(t(lang, "support_perm_weekday_question"), reply_markup=kb)
        return

    if parts[1] == "os" and parts[2] == "p" and len(parts) >= 7:
        perm = str(parts[3]) == "1"
        br = parts[4]
        d_iso = parts[5]
        tm = _parse_cb_time(parts[6])
        if not tm:
            _flow_log("warning", "OS perm invalid time", user_id=callback.from_user.id, branch=br, date=d_iso, raw=parts[6])
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        admin_state[callback.from_user.id] = {"mode": "os_confirm", "branch": br, "date": d_iso, "time": tm, "perm": perm}
        tkn = tm.replace(":", ".")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=t(lang, "support_confirm_yes"), callback_data=f"s2:os:cf:{int(perm)}:{br}:{d_iso}:{tkn}"),
                    InlineKeyboardButton(text=t(lang, "support_confirm_no"), callback_data="s2:cs:cn"),
                ]
            ]
        )
        await callback.message.answer(
            t(lang, "support_os_confirm_final", mode=t(lang, "support_perm_yes") if perm else t(lang, "support_perm_no")),
            reply_markup=kb,
        )
        await callback.answer()
        return

    if parts[1] == "os" and parts[2] == "cf" and len(parts) >= 7:
        perm = str(parts[3]) == "1"
        br = parts[4]
        d_iso = parts[5]
        tm = _parse_cb_time(parts[6])
        if not tm:
            _flow_log("warning", "OS confirm invalid time", user_id=callback.from_user.id, branch=br, date=d_iso, raw=parts[6])
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        st = admin_state.get(callback.from_user.id) or {}
        if not _state_has_fields(st, ["branch", "date", "time"]):
            _flow_log("warning", "OS confirm missing state", user_id=callback.from_user.id, state=st, branch=br, date=d_iso, time=tm)
            _clear_state(callback.from_user.id)
            await callback.answer(t(lang, "support_state_expired_restart"), show_alert=True)
            return
        try:
            ok = False
            if perm:
                try:
                    wd = datetime.strptime(d_iso, "%Y-%m-%d").date().weekday()
                except Exception:
                    wd = -1
                if wd >= 0:
                    remove_recurring_slot_rule(br, wd, tm, "close")
                    ok = add_recurring_slot_rule(uuid4().hex[:12], br, wd, tm, "open", "", int(callback.from_user.id))
                    _flow_log("info", "OS confirm recurring", user_id=callback.from_user.id, branch=br, date=d_iso, weekday=wd, time=tm, db_write_ok=ok)
            else:
                remove_blocked_slot(br, d_iso, tm)
                ok = add_lesson_extra_slot(uuid4().hex[:12], d_iso, tm, br)
                if ok:
                    extras = set(list_lesson_extra_slots_for_date(d_iso, br) or [])
                    ok = tm in extras
                    _flow_log("info", "OS confirm one-time", user_id=callback.from_user.id, branch=br, date=d_iso, time=tm, readback_ok=ok, extras_count=len(extras))
            await callback.answer(t(lang, "support_os_done") if ok else t(lang, "support_os_readback_failed"), show_alert=not ok)
            _clear_state(callback.from_user.id)
            return
        except Exception as e:
            _clear_state(callback.from_user.id)
            await _notify_traceback_admins("callbacks:s2:os:cf", e, user_id=callback.from_user.id, payload=data)
            await callback.answer(t(lang, "support_error_generic"), show_alert=True)
            return

    if parts[1] == "cs" and parts[2] == "b" and len(parts) >= 4:
        br = parts[3]
        admin_state[callback.from_user.id] = {"mode": "cs_date", "branch": br}
        dates = _branch_dates_with_closed_status(br, 14)
        rows: list[list[InlineKeyboardButton]] = []
        row: list[InlineKeyboardButton] = []
        for iso, is_closed in dates[:14]:
            label = _date_short_mon_ddmm(iso, lang)
            cb = f"s2:cs:d:{br}:{iso}"
            if is_closed:
                label = f"🔒 {label}"
                cb = f"s2:cs:dc:{br}:{iso}"
            row.append(InlineKeyboardButton(text=label, callback_data=cb))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await callback.message.answer(
            t(lang, "support_cs_pick_date"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    if parts[1] == "cs" and parts[2] == "dc" and len(parts) >= 5:
        br = parts[3]
        d_iso = parts[4]
        rs = get_branch_date_closed_reason(br, d_iso)
        msg = t(lang, "support_day_closed_with_reason", reason=rs) if rs else t(lang, "support_day_closed_no_reason")
        await callback.answer(msg, show_alert=True)
        return

    if parts[1] == "cs" and parts[2] == "d" and len(parts) >= 5:
        br = parts[3]
        d_iso = parts[4]
        now_tz = datetime.now(TZ)
        today_tz = now_tz.date()
        try:
            d = datetime.strptime(d_iso, "%Y-%m-%d").date()
        except Exception:
            d = today_tz
        row: list[InlineKeyboardButton] = []
        rows: list[list[InlineKeyboardButton]] = []
        recurring_open = list_recurring_open_times_for_date(br, d_iso) or []
        for tm in sorted(set(_times_union(d_iso, br) + recurring_open)):
            start_ts = support_make_start_ts(d_iso, tm) or ""
            blocked = is_slot_closed_effective(br, d_iso, tm)
            free = (lesson_is_slot_free(start_ts) if start_ts else True)
            try:
                hh, mm = [int(x) for x in tm.split(":", 1)]
                local_dt = TZ.localize(datetime.combine(d, dtime_cls(hh, mm)))
                slot_passed = (d == today_tz) and (local_dt <= now_tz)
            except Exception:
                slot_passed = False
            if blocked or not free or slot_passed:
                continue
            tkn = tm.replace(":", ".")
            row.append(InlineKeyboardButton(text=tm, callback_data=f"s2:cs:t:{br}:{d_iso}:{tkn}"))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        if not rows:
            await callback.answer(t(lang, "support_cs_no_slots"), show_alert=True)
            return
        await callback.message.answer(
            t(lang, "support_cs_pick_slot"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    if parts[1] == "cs" and parts[2] == "t" and len(parts) >= 6:
        br = parts[3]
        d_iso = parts[4]
        tm = _parse_cb_time(parts[5])
        if not tm:
            _flow_log("warning", "CS pick time invalid", user_id=callback.from_user.id, branch=br, date=d_iso, raw=parts[5])
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        admin_state[callback.from_user.id] = {
            "mode": "cs_reason",
            "branch": br,
            "date": d_iso,
            "time": tm,
        }
        await callback.message.answer(t(lang, "support_cs_reason"))
        await callback.answer()
        return

    if parts[1] == "cs" and parts[2] == "p" and len(parts) >= 7:
        perm = str(parts[3]) == "1"
        br = parts[4]
        d_iso = parts[5]
        tm = _parse_cb_time(parts[6])
        if not tm:
            _flow_log("warning", "CS perm invalid time", user_id=callback.from_user.id, branch=br, date=d_iso, raw=parts[6])
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        st = admin_state.get(callback.from_user.id) or {}
        admin_state[callback.from_user.id] = {**st, "mode": "cs_confirm", "branch": br, "date": d_iso, "time": tm, "perm": perm}
        tkn = tm.replace(":", ".")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_confirm_yes"),
                        callback_data=f"s2:cs:cf:{int(perm)}:{br}:{d_iso}:{tkn}",
                    ),
                    InlineKeyboardButton(text=t(lang, "support_confirm_no"), callback_data="s2:cs:cn"),
                ]
            ]
        )
        await callback.message.answer(
            t(lang, "support_cs_confirm_final", mode=t(lang, "support_perm_yes") if perm else t(lang, "support_perm_no")),
            reply_markup=kb,
        )
        await callback.answer()
        return

    if parts[1] == "cs" and parts[2] == "cf" and len(parts) >= 7:
        perm = str(parts[3]) == "1"
        br = parts[4]
        d_iso = parts[5]
        tm = _parse_cb_time(parts[6])
        if not tm:
            _flow_log("warning", "CS confirm invalid time", user_id=callback.from_user.id, branch=br, date=d_iso, raw=parts[6])
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        st = admin_state.get(callback.from_user.id) or {}
        if not _state_has_fields(st, ["branch", "date", "time"]):
            _flow_log("warning", "CS confirm missing state", user_id=callback.from_user.id, state=st, branch=br, date=d_iso, time=tm)
            _clear_state(callback.from_user.id)
            await callback.answer(t(lang, "support_state_expired_restart"), show_alert=True)
            return
        reason = st.get("cs_reason") or ""
        try:
            ok = False
            if perm:
                try:
                    wd = datetime.strptime(d_iso, "%Y-%m-%d").date().weekday()
                except Exception:
                    wd = -1
                if wd >= 0:
                    remove_recurring_slot_rule(br, wd, tm, "open")
                    ok = add_recurring_slot_rule(uuid4().hex[:12], br, wd, tm, "close", reason, int(callback.from_user.id))
                    if ok:
                        ok = is_slot_closed_effective(br, d_iso, tm)
                    _flow_log("info", "CS confirm recurring", user_id=callback.from_user.id, branch=br, date=d_iso, weekday=wd, time=tm, reason=reason, result_ok=ok)
            else:
                hid = hashlib.md5(f"{br}|{d_iso}|{tm}".encode()).hexdigest()[:16]
                ok = add_blocked_slot(hid, br, d_iso, tm, reason, int(callback.from_user.id))
                if ok and not is_slot_blocked(br, d_iso, tm):
                    ok = False
                _flow_log("info", "CS confirm one-time", user_id=callback.from_user.id, branch=br, date=d_iso, time=tm, reason=reason, result_ok=ok)
            await callback.answer(t(lang, "support_cs_done") if ok else t(lang, "support_slot_block_failed"), show_alert=not ok)
            _clear_state(callback.from_user.id)
            return
        except Exception as e:
            _clear_state(callback.from_user.id)
            await _notify_traceback_admins("callbacks:s2:cs:cf", e, user_id=callback.from_user.id, payload=data)
            await callback.answer(t(lang, "support_error_generic"), show_alert=True)
            return


    if parts[1] == "wd" and parts[2] == "b" and len(parts) >= 4:
        br = parts[3]
        admin_state[callback.from_user.id] = {"mode": "wd_branch", "branch": br}
        cur = set(get_lesson_branch_weekdays(br))
        rows = _wd_keyboard_rows(lang, br, cur)
        await callback.message.answer(
            t(lang, "support_wd_title", branch=_branch_label(lang, br)),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
        )
        await callback.answer()
        return

    if parts[1] == "wd" and parts[2] == "t" and len(parts) >= 5:
        br = parts[3]
        try:
            idx = int(parts[4])
        except Exception:
            _flow_log("warning", "WD toggle invalid idx", user_id=callback.from_user.id, branch=br, raw=parts[4] if len(parts) > 4 else None)
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        if idx < 0 or idx > 6:
            _flow_log("warning", "WD toggle out of range", user_id=callback.from_user.id, branch=br, idx=idx)
            await callback.answer(t(lang, "err_invalid_format"), show_alert=True)
            return
        cur = list(get_lesson_branch_weekdays(br))
        s = set(cur)
        was_on = idx in s
        if idx in s:
            s.remove(idx)
        else:
            s.add(idx)
        if not s:
            await callback.answer(t(lang, "support_wd_need_one"), show_alert=True)
            return
        other = _other_branch(br)
        other_set = set(get_lesson_branch_weekdays(other))
        # Cross-branch transfer rule:
        # when turning ON weekday in current branch, remove from opposite branch automatically.
        other_expected: set[int] | None = None
        if not was_on and idx in other_set:
            other_set.remove(idx)
            other_expected = set(other_set)
            set_lesson_branch_weekdays(other, sorted(other_set))
            _invalidate_allowed_dates_cache(other)

        ok = set_lesson_branch_weekdays(br, sorted(s))
        if ok:
            _invalidate_allowed_dates_cache(br)
        _flow_log("info", "WD save write", user_id=callback.from_user.id, branch=br, selected=sorted(s), db_write_ok=ok)
        if not ok:
            await callback.answer(t(lang, "support_wd_save_failed"), show_alert=True)
            return
        cur2 = set(get_lesson_branch_weekdays(br))
        if cur2 != set(sorted(s)):
            _flow_log("warning", "WD save readback mismatch", user_id=callback.from_user.id, branch=br, expected=sorted(s), got=sorted(cur2))
            await callback.answer(t(lang, "support_wd_save_failed"), show_alert=True)
            return
        if other_expected is not None:
            other_actual = set(get_lesson_branch_weekdays(other))
            if other_actual != other_expected:
                _flow_log("warning", "WD counterpart readback mismatch", user_id=callback.from_user.id, branch=other, expected=sorted(other_expected), got=sorted(other_actual))
                await callback.answer(t(lang, "support_wd_save_failed"), show_alert=True)
                return
        await callback.answer(t(lang, "support_wd_saved"))
        rows = _wd_keyboard_rows(lang, br, cur2)
        try:
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        except Exception:
            logger.exception("Failed to edit weekday toggle keyboard")
        return

    await callback.answer(t(lang, "invalid_action"), show_alert=True)


async def _dispatch_support_main_menu(message: Message, lang: str, act: str) -> None:
    if act == "dash":
        await _send_dashboard(message, lang)
    elif act == "bookings":
        await _send_bookings_list(message, lang, page=1)
    elif act == "open_slot":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_1"),
                        callback_data="s2:os:b:branch_1",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_2"),
                        callback_data="s2:os:b:branch_2",
                    ),
                ],
            ]
        )
        await message.answer(t(lang, "support_os_pick_branch"), reply_markup=kb)
    elif act == "close_slot":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_1"),
                        callback_data="s2:cs:b:branch_1",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_2"),
                        callback_data="s2:cs:b:branch_2",
                    ),
                ],
            ]
        )
        await message.answer(t(lang, "support_cs_pick_branch"), reply_markup=kb)
    elif act == "close_date":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_drm_close_btn"),
                        callback_data="s2:drm:c",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "support_drm_open_btn"),
                        callback_data="s2:drm:o",
                    ),
                ],
            ]
        )
        await message.answer(t(lang, "support_drm_menu"), reply_markup=kb)
    elif act == "broadcast":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=t(lang, "support_bc_aud_up"), callback_data="s2:bc:aud:up")],
                [InlineKeyboardButton(text=t(lang, "support_bc_aud_had"), callback_data="s2:bc:aud:had")],
                [InlineKeyboardButton(text=t(lang, "support_bc_aud_all"), callback_data="s2:bc:aud:all")],
            ]
        )
        await message.answer(t(lang, "support_bc_audience"), reply_markup=kb)
    elif act == "weekdays":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_1"),
                        callback_data="s2:wd:b:branch_1",
                    ),
                    InlineKeyboardButton(
                        text=t(lang, "support_branch_2"),
                        callback_data="s2:wd:b:branch_2",
                    ),
                ],
            ]
        )
        await message.answer(t(lang, "support_wd_pick_branch"), reply_markup=kb)
    elif act == "language":
        await cmd_lang(message)
    elif act == "my_slots":
        subjects = list(_support_admin_subjects(message.from_user.id))
        if not subjects:
            await message.answer(t(lang, "support_no_subjects_assigned"))
            return
        rows = []
        for subj in subjects:
            rows.append([InlineKeyboardButton(text=subj.capitalize(), callback_data=f"s2:mys:s:{subj}")])
        await message.answer(t(lang, "support_myslots_pick_subject"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@dp.message(F.text)
async def admin_text_router(message: Message):
    try:
        if not message.from_user or not _admin_only(message.from_user.id):
            return
        lang = _admin_lang(message.from_user)
        uid = message.from_user.id
        st = admin_state.get(uid) or {}
        mode = st.get("mode")
        txt = (message.text or "").strip()
        _flow_log("info", "Support text router", user_id=uid, mode=mode, text=txt[:120])

        if mode == "bc_collect" and st.get("fmt") == "text" and message.text:
            payload = {
                "fmt": "text",
                "text": message.html_text if message.html_text else message.text,
            }
            admin_state[uid] = {**st, "mode": "bc_preview", "bc_payload": payload}
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text=t(lang, "support_bc_confirm_send"), callback_data="s2:bc:ok"),
                        InlineKeyboardButton(text=t(lang, "support_bc_confirm_cancel"), callback_data="s2:bc:no"),
                    ]
                ]
            )
            await message.answer(t(lang, "support_bc_preview_hint"), reply_markup=kb)
            await message.answer(payload["text"], parse_mode="HTML")
            return

        if mode == "write_student":
            bid = st.get("booking_id")
            b = get_lesson_booking(str(bid)) if bid else None
            if not b or not _support_admin_can_access_booking(uid, b):
                await message.answer(t(lang, "support_admin_no_bookings"))
                _clear_state(uid)
                return
            if b and student_notify_bot and b.get("student_telegram_id"):
                try:
                    await student_notify_bot.send_message(int(b.get("student_telegram_id")), txt)
                    await message.answer(t(lang, "support_write_student_sent"))
                except Exception:
                    await message.answer(t(lang, "support_error_generic"))
            else:
                await message.answer(t(lang, "support_error_generic"))
            _clear_state(uid)
            return

        if mode == "drm_close_reason":
            br = st.get("branch")
            d_iso = st.get("date")
            admin_state[uid] = {
                "mode": "drm_close_confirm",
                "branch": br,
                "date": d_iso,
                "reason": txt,
            }
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=t(lang, "support_confirm_yes"),
                            callback_data="s2:drm:cf",
                        ),
                        InlineKeyboardButton(text=t(lang, "support_confirm_no"), callback_data="s2:drm:cn"),
                    ]
                ]
            )
            await message.answer(t(lang, "support_drm_close_confirm"), reply_markup=kb)
            return

        if mode == "cs_reason":
            admin_state[uid] = {**st, "cs_reason": txt, "mode": "cs_perm"}
            br = st.get("branch")
            d_iso = st.get("date")
            tm = st.get("time")
            tkn = str(tm).replace(":", ".")
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=t(lang, "support_confirm_yes"),
                            callback_data=f"s2:cs:p:1:{br}:{d_iso}:{tkn}",
                        ),
                        InlineKeyboardButton(text=t(lang, "support_confirm_no"), callback_data=f"s2:cs:p:0:{br}:{d_iso}:{tkn}"),
                    ]
                ]
            )
            await message.answer(t(lang, "support_perm_weekday_question"), reply_markup=kb)
            return

        act = _menu_action_for_text(lang, txt)
        if act == "cancel":
            _clear_state(uid)
            await message.answer(t(lang, "support_state_cancelled"), reply_markup=_main_reply_kb(lang))
            return

        if act in SUPPORT_MAIN_MENU_ACTIONS:
            _clear_state(uid)
            await _dispatch_support_main_menu(message, lang, act)
            return

        if act is None and mode in _SUPPORT_WAITING_INLINE_MODES:
            return
    except Exception as e:
        uid = message.from_user.id if message.from_user else None
        await _notify_traceback_admins("admin_text_router", e, user_id=uid, payload=(message.text or ""))
        try:
            lg = _admin_lang(message.from_user) if message.from_user else "uz"
            await message.answer(t(lg, "support_error_generic"))
        except Exception:
            pass


def _lesson_weekday_label(date_iso: str, lang: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
        idx = d.weekday()
        if lang == "ru":
            names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        elif lang == "en":
            names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        else:
            names = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        return names[idx]
    except Exception:
        return ""


def _norm_ui_lang(raw: str | None) -> str:
    x = (raw or "uz").strip().lower()
    return x if x in ("uz", "ru", "en") else "uz"


def _parse_iso_utc_rem(s: str | None):
    if not s:
        return None
    ts = str(s).strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        dtx = datetime.fromisoformat(ts)
    except Exception:
        return None
    if dtx.tzinfo is None:
        dtx = dtx.replace(tzinfo=timezone.utc)
    return dtx.astimezone(timezone.utc)


def _lesson_date_long_line(date_iso: str, lang: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
    except Exception:
        return html.escape(date_iso)
    wd = _lesson_weekday_label(date_iso, lang)
    if lang == "en":
        en_m = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        en_d = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        return html.escape(f"{en_d[d.weekday()]}, {d.day:02d} {en_m[d.month - 1]} {d.year}")
    mkey = f"support_cal_m{d.month}"
    cal_part = t(lang, mkey, day=d.day, year=d.year)
    return f"{html.escape(wd)}, {cal_part}"


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


def _student_display_name(u: dict | None) -> str:
    if not u:
        return "—"
    fn = (u.get("first_name") or "").strip()
    ln = (u.get("last_name") or "").strip()
    return (fn + " " + ln).strip() or "—"


def _student_phone(u: dict | None) -> str:
    if not u:
        return "—"
    return str(u.get("phone") or u.get("phone_number") or u.get("telegram_phone") or "—")


def _support_attendance_kb(booking_id: str, expires_ts: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅", callback_data=f"s2:att:present:{booking_id}:{expires_ts}"),
            InlineKeyboardButton(text="❌", callback_data=f"s2:att:late:{booking_id}:{expires_ts}"),
            InlineKeyboardButton(text="⛔️", callback_data=f"s2:att:absent:{booking_id}:{expires_ts}"),
        ]]
    )


def _support_bonus_kb(booking_id: str, expires_ts: int) -> InlineKeyboardMarkup:
    row1 = [InlineKeyboardButton(text=str(i), callback_data=f"s2:bonus:{i}:{booking_id}:{expires_ts}") for i in range(1, 6)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=f"s2:bonus:{i}:{booking_id}:{expires_ts}") for i in range(6, 11)]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])


def _student_profile_anchor(u: dict | None, student_telegram_id: str | None) -> str:
    name = html.escape(_student_display_name(u))
    if not student_telegram_id:
        return name
    try:
        tid = int(student_telegram_id)
    except Exception:
        return name
    un = (u or {}).get("username")
    if un:
        uu = html.escape(str(un).lstrip("@"))
        return f'<a href="https://t.me/{uu}">{name}</a>'
    return f'<a href="tg://user?id={tid}">{name}</a>'


@dp.message()
async def admin_media_router(message: Message):
    try:
        if not message.from_user or not _admin_only(message.from_user.id):
            return
        uid = message.from_user.id
        st = admin_state.get(uid) or {}
        if st.get("mode") != "bc_collect":
            return
        lang = _admin_lang(message.from_user)
        fmt = st.get("fmt")
        payload: dict = {"fmt": fmt}
        if fmt == "text" and message.text:
            payload["text"] = message.html_text if message.html_text else message.text
        elif fmt == "photo" and message.photo:
            payload["file_id"] = message.photo[-1].file_id
            payload["caption"] = message.caption or ""
        elif fmt == "video" and message.video:
            payload["file_id"] = message.video.file_id
            payload["caption"] = message.caption or ""
        elif fmt == "audio" and message.audio:
            payload["file_id"] = message.audio.file_id
            payload["caption"] = message.caption or ""
        elif fmt == "voice" and message.voice:
            payload["file_id"] = message.voice.file_id
        elif fmt == "vnote" and message.video_note:
            payload["file_id"] = message.video_note.file_id
        elif fmt == "doc" and message.document:
            payload["file_id"] = message.document.file_id
            payload["caption"] = message.caption or ""
        else:
            await message.answer(t(lang, "support_bc_bad_content"))
            return
        admin_state[uid] = {**st, "mode": "bc_preview", "bc_payload": payload}
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=t(lang, "support_bc_confirm_send"), callback_data="s2:bc:ok"),
                    InlineKeyboardButton(text=t(lang, "support_bc_confirm_cancel"), callback_data="s2:bc:no"),
                ]
            ]
        )
        await message.answer(t(lang, "support_bc_preview_hint"), reply_markup=kb)
        if fmt == "text":
            await message.answer(payload.get("text") or "", parse_mode="HTML")
        elif fmt == "photo" and message.photo:
            await message.answer_photo(payload["file_id"], caption=payload.get("caption"), parse_mode="HTML")
        elif fmt == "video" and message.video:
            await message.answer_video(payload["file_id"], caption=payload.get("caption"), parse_mode="HTML")
        elif fmt == "audio" and message.audio:
            await message.answer_audio(payload["file_id"], caption=payload.get("caption"), parse_mode="HTML")
        elif fmt == "voice" and message.voice:
            await message.answer_voice(payload["file_id"])
        elif fmt == "vnote" and message.video_note:
            await message.answer_video_note(payload["file_id"])
        elif fmt == "doc" and message.document:
            await message.answer_document(payload["file_id"], caption=payload.get("caption"), parse_mode="HTML")
    except Exception as e:
        uid = message.from_user.id if message.from_user else None
        await _notify_traceback_admins("admin_media_router", e, user_id=uid, payload=f"fmt={((admin_state.get(uid) or {}).get('fmt') if uid else '')}")


async def _reminders_loop():
    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            now_iso = now_utc.isoformat()
            due = list_due_unsent_lesson_reminders(now_iso_utc=now_iso, limit=200)
            for r in due:
                rid = str(r.get("id"))
                tgt_raw = str(r.get("telegram_id") or "").strip()
                target = str(r.get("reminder_target") or "student").lower()
                rtype = str(r.get("reminder_type") or "").lower()
                bid = r.get("booking_id")
                b = get_lesson_booking(str(bid)) if bid else None

                if not b or str(b.get("status") or "") not in ("pending", "approved"):
                    mark_lesson_reminder_sent(rid)
                    continue

                end = _parse_iso_utc_rem(str(b.get("end_ts") or ""))
                start = _parse_iso_utc_rem(str(b.get("start_ts") or ""))
                if rtype not in ("lesson_end_bonus",) and end and now_utc >= end:
                    mark_lesson_reminder_sent(rid)
                    continue
                if rtype not in ("lesson_start_attendance", "lesson_end_bonus") and start and now_utc >= start:
                    # Reminder is stale (lesson already started) - consume it.
                    mark_lesson_reminder_sent(rid)
                    continue

                stu_tg = b.get("student_telegram_id")
                su = get_user_by_id(int(b.get("student_user_id") or 0)) if b.get("student_user_id") else None

                if not tgt_raw:
                    mark_lesson_reminder_sent(rid)
                    continue

                try:
                    if not claim_lesson_reminder_for_delivery(rid):
                        continue
                    date_iso = str(b.get("date") or "")
                    tm = normalize_time_hhmm(str(b.get("time") or "")) or str(b.get("time") or "")
                    if target == "teacher":
                        # Support reminders must come only from support admin bot.
                        mark_lesson_reminder_sent(rid)
                        continue
                    elif target == "admin":
                        if rtype not in ("10m_before", "lesson_start_attendance", "lesson_end_bonus"):
                            mark_lesson_reminder_sent(rid)
                            continue
                        if not bot:
                            mark_lesson_reminder_sent(rid)
                            continue
                        au = get_user_by_telegram(tgt_raw) or {}
                        alang = _norm_ui_lang((au or {}).get("language"))
                        if rtype == "10m_before":
                            wd = _weekday_name(date_iso, alang)
                            br = b.get("branch") or ""
                            branch_label = t(alang, "support_branch_1") if br == "branch_1" else t(alang, "support_branch_2")
                            date_long = _lesson_date_long_line(date_iso, alang)
                            purpose = html.escape(_support_purpose_label(alang, str(b.get("purpose") or "")))
                            profile = _student_profile_anchor(su, str(stu_tg) if stu_tg else None)
                            txt = t(
                                alang,
                                "support_lesson_admin_rem_10m",
                                booking_id=html.escape(str(b.get("id") or "")),
                                profile=profile,
                                date_long=date_long,
                                weekday=html.escape(wd),
                                time=html.escape(tm),
                                branch=branch_label,
                                purpose=purpose,
                            )
                            await bot.send_message(int(tgt_raw), txt, parse_mode="HTML")
                        elif rtype == "lesson_start_attendance":
                            uid = int(b.get("student_user_id") or 0)
                            profile = _student_profile_anchor(su, str(stu_tg) if stu_tg else None)
                            subjects = ", ".join(get_student_subjects(uid) or get_user_subjects(uid) or []) or "—"
                            groups = ", ".join([str(g.get("name") or "-") for g in (get_user_groups(uid) or [])]) or "—"
                            teachers = ", ".join(
                                [f"{str(tu.get('first_name') or '').strip()} {str(tu.get('last_name') or '').strip()}".strip() for tu in (get_student_teachers(uid) or [])]
                            ) or "—"
                            global_dcoin = float(get_dcoins(uid))
                            txt = t(
                                alang,
                                "support_attendance_prompt_card",
                                booking_id=html.escape(str(b.get("id") or "")),
                                profile=profile,
                                subjects=html.escape(subjects),
                                groups=html.escape(groups),
                                teachers=html.escape(teachers),
                                phone=html.escape(_student_phone(su)),
                                dcoin_en=f"{global_dcoin:.1f}",
                            )
                            exp = int(time.time()) + (15 * 60)
                            await bot.send_message(
                                int(tgt_raw),
                                txt,
                                parse_mode="HTML",
                                reply_markup=_support_attendance_kb(str(b.get("id") or ""), exp),
                            )
                        elif rtype == "lesson_end_bonus":
                            bid_s = str(b.get("id") or "")
                            if not support_booking_bonus_allowed(bid_s):
                                mark_lesson_reminder_sent(rid)
                                continue
                            txt = t(alang, "support_bonus_prompt_card", booking_id=html.escape(bid_s))
                            exp = int(time.time()) + (10 * 60)
                            await bot.send_message(
                                int(tgt_raw),
                                txt,
                                parse_mode="HTML",
                                reply_markup=_support_bonus_kb(bid_s, exp),
                            )
                    else:
                        if not student_notify_bot:
                            mark_lesson_reminder_sent(rid)
                            continue
                        sl = _norm_ui_lang((su or {}).get("language"))
                        wd = _lesson_weekday_label(date_iso, sl)
                        br = b.get("branch") or ""
                        branch_label = t(sl, "support_branch_1") if br == "branch_1" else t(sl, "support_branch_2")
                        date_long = _lesson_date_long_line(date_iso, sl)
                        fn = html.escape(_student_display_name(su))
                        purpose = html.escape(_support_purpose_label(sl, str(b.get("purpose") or "")))
                        booking_id_h = html.escape(str(b.get("id")))
                        tm_h = html.escape(tm)
                        tmpl = "support_lesson_stu_rem_10m" if rtype == "10m_before" else "support_lesson_stu_rem_1h"
                        txt = t(
                            sl,
                            tmpl,
                            booking_id=booking_id_h,
                            time=tm_h,
                            date_long=date_long,
                            weekday=html.escape(wd),
                            branch=branch_label,
                            full_name=fn,
                            purpose=purpose,
                        )
                        await student_notify_bot.send_message(int(tgt_raw), txt, parse_mode="HTML")
                except TelegramBadRequest as e:
                    msg = str(e).lower()
                    if "chat not found" in msg or "user not found" in msg:
                        logger.warning(
                            "lesson reminder terminal error; marking sent booking_id=%s reminder_id=%s target=%s telegram_id=%s err=%s",
                            bid,
                            rid,
                            target,
                            tgt_raw,
                            e,
                        )
                        mark_lesson_reminder_sent(rid)
                    else:
                        logger.exception("lesson reminder telegram error booking_id=%s reminder_id=%s", bid, rid)
                except Exception:
                    logger.exception("lesson reminder failed booking_id=%s reminder_id=%s", bid, rid)
        except Exception:
            logger.exception("reminders loop error")
        await asyncio.sleep(30)


async def run_support_bot():
    global bot, student_notify_bot, teacher_notify_bot
    print("[STARTUP] support_bot run_support_bot() starting")
    if not SUPPORT_BOT_TOKEN:
        raise RuntimeError("SUPPORT_BOT_TOKEN is not set. Put it in .env (SUPPORT_BOT_TOKEN=...) and retry.")
    bot = create_resilient_bot(SUPPORT_BOT_TOKEN)
    student_notify_bot = create_resilient_bot(STUDENT_BOT_TOKEN) if STUDENT_BOT_TOKEN else None
    teacher_notify_bot = create_resilient_bot(TEACHER_BOT_TOKEN) if TEACHER_BOT_TOKEN else None
    await asyncio.to_thread(ensure_support_lessons_schema)
    spawn_guarded_task(_reminders_loop(), name="support_reminders_loop")
    await run_bot_dispatcher(dp=dp, bot=bot, bot_name="support", webhook_port=SUPPORT_WEBHOOK_PORT)
