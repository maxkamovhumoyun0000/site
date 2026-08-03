import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
import re
from urllib.parse import urlencode
import pytz

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from db import (
    get_conn,
    get_group,
    get_group_users,
    add_attendance,
    get_user_by_id,
    get_user_by_telegram,
    add_dpoints,
    get_attendance_effect,
    set_attendance_effect,
    get_temporary_teachers_for_group_on_date,
    is_lesson_otmen_date_cancelled,
)
from i18n import t, detect_lang_from_user
from logging_config import get_logger
from config import ADMIN_CHAT_IDS, LIMITED_ADMIN_CHAT_IDS, TELEGRAM_MINI_APP_BASE_URL

logger = get_logger(__name__)

# Set by admin_bot / teacher_bot startup so finalize_attendance_session can DM students via Student bot.
_attendance_student_notify_bot: Bot | None = None


def set_attendance_student_notify_bot(bot_instance: Bot | None) -> None:
    """Register the Student bot instance used for attendance DMs (not Admin/Teacher bot)."""
    global _attendance_student_notify_bot
    _attendance_student_notify_bot = bot_instance


def _resolve_student_notify_bot(explicit: Bot | None = None) -> Bot | None:
    if explicit is not None:
        return explicit
    if _attendance_student_notify_bot is not None:
        return _attendance_student_notify_bot
    try:
        import admin_bot as admin_bot_mod

        b = getattr(admin_bot_mod, "student_notify_bot", None)
        if b is not None:
            return b
    except Exception:
        pass
    try:
        import teacher_bot as teacher_bot_mod

        b = getattr(teacher_bot_mod, "student_notify_bot", None)
        if b is not None:
            return b
    except Exception:
        pass
    return None


def _normalized_group_subject(group: dict | None) -> str | None:
    if not group:
        return None
    raw = group.get("subject")
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    return s.title()


def _localized_group_name(group: dict | None, lang: str) -> str:
    """Display name for attendance messages; localized fallback when name is missing."""
    n = (group or {}).get("name")
    if n and str(n).strip():
        return str(n).strip()
    return t(lang, "attendance_fallback_group_name")


def _attendance_webapp_url(role: str, group_id: int, date_str: str, *, absolute: bool) -> str | None:
    query = urlencode(
        {
            "role": role,
            "section": "attendance",
            "attendance_group_id": int(group_id),
            "attendance_date": str(date_str),
            "attendance_open": "1",
        }
    )
    if not absolute:
        return f"/?{query}"
    base = (
        TELEGRAM_MINI_APP_BASE_URL
        or os.getenv("WEBAPP_URL")
        or os.getenv("WEBHOOK_BASE_URL")
        or ""
    ).strip()
    if not base:
        return None
    return f"{base.rstrip('/')}/?{query}"


def _attendance_link_keyboard(lang: str, role: str, group_id: int, date_str: str) -> InlineKeyboardMarkup | None:
    url = _attendance_webapp_url(role, group_id, date_str, absolute=True)
    if not url:
        return None
    text = t(lang, "attendance_open_link_btn")
    try:
        button = InlineKeyboardButton(text=text, web_app=WebAppInfo(url=url))
    except Exception:
        button = InlineKeyboardButton(text=text, url=url)
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def _store_attendance_web_notification(
    *,
    user_id: int,
    role: str,
    group: dict,
    date_str: str,
    start: str,
    end: str,
    phase: str,
    lang: str,
) -> None:
    if int(user_id or 0) <= 0:
        return
    group_id = int(group.get("id") or 0)
    if group_id <= 0:
        return
    url = _attendance_webapp_url(role, group_id, date_str, absolute=False)
    if not url:
        return
    group_name = _localized_group_name(group, lang)
    source_key = f"attendance:{phase}:{role}:{int(user_id)}:{group_id}:{date_str}"
    meta = {
        "source": "attendance_reminder",
        "role": role,
        "phase": phase,
        "group_id": group_id,
        "date": date_str,
        "start": start,
        "end": end,
    }
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM web_payment_notifications WHERE user_id=? AND source_key=? LIMIT 1",
            (int(user_id), source_key),
        )
        if cur.fetchone():
            return
        cur.execute(
            """
            INSERT INTO web_payment_notifications
                (user_id, notification_type, title, message, button_text, button_url, target_screen, source_key, meta_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                "attendance_reminder",
                t(lang, "attendance_web_notification_title"),
                t(lang, "attendance_web_notification_message", group=group_name, start=start, end=end),
                t(lang, "attendance_open_link_btn"),
                url,
                "attendance",
                source_key,
                json.dumps(meta, ensure_ascii=False),
            ),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("attendance web notification failed user_id=%s group_id=%s", user_id, group_id)
    finally:
        conn.close()

TZ = pytz.timezone("Asia/Tashkent")
PAGE_SIZE = 10


def _admin_should_receive_group_notification(admin_id: int, group: dict | None) -> bool:
    """
    General admins receive all attendance notifications.
    Limited admins receive only for their own groups.
    """
    try:
        aid = int(admin_id)
    except Exception:
        return False
    if aid in set(ADMIN_CHAT_IDS or []):
        return True
    if aid in set(LIMITED_ADMIN_CHAT_IDS or []):
        return bool(group) and group.get("owner_admin_id") == aid
    return False


def _teacher_recipients_for_attendance(group: dict, date_str: str) -> list[dict]:
    """
    Owner teacher + temporary teachers assigned exactly for this lesson date.
    """
    recipients: dict[int, dict] = {}
    owner = get_user_by_id(group.get("teacher_id")) if group.get("teacher_id") else None
    if owner and owner.get("telegram_id"):
        recipients[int(owner["id"])] = owner
    try:
        temps = get_temporary_teachers_for_group_on_date(int(group.get("id")), date_str) or []
        for t_user in temps:
            if t_user and t_user.get("telegram_id"):
                recipients[int(t_user["id"])] = t_user
    except Exception:
        logger.exception("Failed to load temporary attendance recipients for group=%s date=%s", group.get("id"), date_str)
    return list(recipients.values())

# Keep last sent attendance panel message IDs in-memory so different bots
# (admin/teacher) can edit the other's keyboard in realtime.
# {session_id: {"admin": (chat_id, message_id), "teacher": (chat_id, message_id)}}
PANEL_MESSAGES: dict[int, dict[str, tuple[int, int]]] = {}

# UI language per panel (admin vs teacher may differ).
PANEL_UI_LANG: dict[int, dict[str, str]] = {}


def set_panel_ui_lang(session_id: int, panel_owner: str, lang: str) -> None:
    PANEL_UI_LANG.setdefault(session_id, {})[panel_owner] = lang


def get_panel_ui_lang(session_id: int, panel_owner: str, fallback: str = "uz") -> str:
    return PANEL_UI_LANG.get(session_id, {}).get(panel_owner) or fallback


def _remember_panel(session_id: int, panel_owner: str, chat_id: int, message_id: int) -> None:
    """
    Persist panel message ids so separate admin/teacher bot processes can sync.
    Best-effort: if DB migration/columns missing, still keep in-memory cache.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        if panel_owner == "admin":
            cur.execute(
                """
                UPDATE attendance_sessions
                SET admin_panel_chat_id=?, admin_panel_message_id=?
                WHERE id=?
                """,
                (chat_id, message_id, session_id),
            )
        elif panel_owner == "teacher":
            cur.execute(
                """
                UPDATE attendance_sessions
                SET teacher_panel_chat_id=?, teacher_panel_message_id=?
                WHERE id=?
                """,
                (chat_id, message_id, session_id),
            )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Failed to persist panel message ids to DB")

    PANEL_MESSAGES.setdefault(session_id, {})[panel_owner] = (chat_id, message_id)


def _get_panel_message(session_id: int, panel_owner: str) -> tuple[int, int] | None:
    """
    Read panel message ids from DB (primary), fallback to in-memory cache.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT admin_panel_chat_id, admin_panel_message_id,
                   teacher_panel_chat_id, teacher_panel_message_id
            FROM attendance_sessions
            WHERE id=?
            """,
            (session_id,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            if panel_owner == "admin":
                cid = row["admin_panel_chat_id"]
                mid = row["admin_panel_message_id"]
                if cid and mid:
                    return int(cid), int(mid)
            elif panel_owner == "teacher":
                cid = row["teacher_panel_chat_id"]
                mid = row["teacher_panel_message_id"]
                if cid and mid:
                    return int(cid), int(mid)
    except Exception:
        logger.exception("Failed to read panel message ids from DB")

    return PANEL_MESSAGES.get(session_id, {}).get(panel_owner)


# Prevent duplicate reward/notifications when both auto-close and manual
# "finish" callbacks happen (or when schedulers loop multiple times).
FINALIZED_SESSION_IDS: set[int] = set()


async def finalize_attendance_session(
    bot,
    session_id: int,
    admin_chat_ids=None,
    *,
    student_notify_bot: Bot | None = None,
) -> None:
    """
    Close session rewards students with D'coin and notifies admin/teacher.
    Student DMs use the Student bot token (not admin/teacher bot).
    D'coin is applied only when the group has a non-empty subject (per-subject balance).
    Best-effort: never raise.
    """
    if session_id in FINALIZED_SESSION_IDS:
        return

    admin_chat_ids = admin_chat_ids or []

    session = get_session(session_id)
    if not session:
        return

    group_id = session["group_id"]
    date_str = session["date"]

    # Close already done by caller (or by scheduler), but keep best-effort idempotency.
    try:
        if session.get("status") != "closed":
            set_session_closed(session_id)
    except Exception:
        logger.exception("Failed to set_session_closed inside finalize_attendance_session")

    try:
        group = get_group(group_id)

        status_map = get_attendance_map(group_id, date_str)
        group_users = get_group_users(group_id)

        group_subject = _normalized_group_subject(group)
        if group_subject is None:
            gname = _localized_group_name(group, "uz")
            try:
                raise ValueError("attendance_subject_missing")
            except ValueError:
                logger.exception(
                    "event=attendance_subject_missing session_id=%s group_id=%s date=%s group_name=%s student_count=%s",
                    session_id,
                    group_id,
                    date_str,
                    gname,
                    len(group_users),
                )

        student_bot = _resolve_student_notify_bot(student_notify_bot)
        if student_bot is None:
            logger.warning(
                "Student notify bot not configured; attendance student messages skipped session_id=%s",
                session_id,
            )

        # Attendance D'point rule: Keldi +5, Sababsiz -10, Sababli/unmarked 0.
        for u in group_users:
            uid = u["id"]
            st = (status_map.get(uid) or "").lower()
            if st in {"present", "keldi", "late"}:
                normalized_status = "Keldi"
                reward = 5.0
            elif st in {"absent", "sababsiz"}:
                normalized_status = "Sababsiz"
                reward = -10.0
            elif st in {"excused", "sababli"}:
                normalized_status = "Sababli"
                reward = 0.0
            else:
                normalized_status = ""
                reward = 0.0
            present = normalized_status == "Keldi"

            if group_subject is not None:
                try:
                    prev = get_attendance_effect(int(uid), int(group_id), str(date_str)) or {}
                    prev_delta = float(prev.get("delta_dpoints") or 0)
                    prev_status = str(prev.get("status") or "")
                    if prev_status != normalized_status:
                        if prev_delta:
                            add_dpoints(uid, -prev_delta, group_subject, change_type="attendance_reverse")
                        if reward:
                            add_dpoints(uid, reward, group_subject, change_type="attendance_mark")
                        set_attendance_effect(uid, group_id, date_str, normalized_status, reward)
                except Exception:
                    logger.exception("Failed to apply attendance D'point uid=%s session_id=%s", uid, session_id)

            tg_id = u.get("telegram_id")
            if not tg_id or student_bot is None:
                continue

            try:
                u_lang = detect_lang_from_user(u)
                group_name = _localized_group_name(group, u_lang)
                if normalized_status not in {"Keldi", "Sababsiz"}:
                    continue
                if group_subject is not None:
                    msg_text = t(
                        u_lang,
                        "attendance_student_reward_present" if present else "attendance_student_reward_absent",
                        group=group_name,
                        date=date_str,
                    )
                else:
                    msg_text = t(
                        u_lang,
                        "attendance_student_present_no_subject"
                        if present
                        else "attendance_student_absent_no_subject",
                        group=group_name,
                        date=date_str,
                    )
                await student_bot.send_message(int(tg_id), msg_text)
            except TelegramForbiddenError:
                logger.warning("Student blocked bot uid=%s tg_id=%s", uid, tg_id)
            except TelegramBadRequest as e:
                # "chat not found" typically means the user hasn't started the bot
                # or telegram_id is no longer valid. We don't want this to break
                # the attendance finalization / other flows.
                msg = str(e).lower()
                if "chat not found" in msg or "user not found" in msg:
                    logger.warning("Cannot notify student (unavailable chat) uid=%s tg_id=%s: %s", uid, tg_id, e)
                else:
                    logger.exception("TelegramBadRequest notifying student uid=%s tg_id=%s", uid, tg_id)
            except Exception:
                logger.exception("Failed to notify student uid=%s", uid)

        # Notify admins in their stored language.
        for admin_id in admin_chat_ids:
            if not _admin_should_receive_group_notification(int(admin_id), group):
                continue
            try:
                admin_user = get_user_by_telegram(str(admin_id))
                admin_lang = detect_lang_from_user(admin_user or {})
                group_name = _localized_group_name(group, admin_lang)
                await bot.send_message(
                    int(admin_id),
                    t(admin_lang, "attendance_done_notify_teacher", group=group_name, date=date_str),
                )
            except Exception:
                logger.exception("Failed to notify admin_id=%s", admin_id)

        # Notify owner/temporary teachers for this lesson date.
        try:
            recipients = _teacher_recipients_for_attendance(group, date_str)
            for teacher in recipients:
                t_lang = detect_lang_from_user(teacher)
                group_name = _localized_group_name(group, t_lang)
                await bot.send_message(
                    int(teacher["telegram_id"]),
                    t(t_lang, "attendance_done_notify_teacher", group=group_name, date=date_str),
                )
        except Exception:
            logger.exception("Failed to notify teachers about attendance close")

        # Disable marking buttons on already-sent panels (best-effort).
        admin_kb = build_attendance_keyboard(
            session_id, group_id, date_str, 0, lang=get_panel_ui_lang(session_id, "admin", "uz")
        )
        teacher_kb = build_attendance_keyboard(
            session_id, group_id, date_str, 0, lang=get_panel_ui_lang(session_id, "teacher", "uz")
        )

        admin_panel = _get_panel_message(session_id, "admin")
        if admin_panel:
            admin_chat_id, admin_message_id = admin_panel
            try:
                import admin_bot as admin_bot_mod

                editor = getattr(admin_bot_mod, "bot", None)
                if editor:
                    await editor.edit_message_reply_markup(
                        chat_id=admin_chat_id,
                        message_id=admin_message_id,
                        reply_markup=admin_kb,
                    )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    logger.exception("Failed to edit admin panel on finalize")
            except Exception:
                logger.exception("Failed to edit admin panel on finalize")

        teacher_panel = _get_panel_message(session_id, "teacher")
        if teacher_panel:
            teacher_chat_id, teacher_message_id = teacher_panel
            try:
                import teacher_bot as teacher_bot_mod

                editor = getattr(teacher_bot_mod, "bot", None)
                if editor:
                    await editor.edit_message_reply_markup(
                        chat_id=teacher_chat_id,
                        message_id=teacher_message_id,
                        reply_markup=teacher_kb,
                    )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    logger.exception("Failed to edit teacher panel on finalize")
            except Exception:
                logger.exception("Failed to edit teacher panel on finalize")

    except Exception:
        logger.exception("finalize_attendance_session failed for session_id=%s", session_id)
        return

    FINALIZED_SESSION_IDS.add(session_id)


def now_tashkent():
    return datetime.now(TZ)


def _today_str():
    return now_tashkent().strftime("%Y-%m-%d")


def ensure_session(group_id: int, date_str: str):
    """Create attendance session if not exists, return session row dict."""
    if is_lesson_otmen_date_cancelled(str(date_str or "")):
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO attendance_sessions (group_id, date) VALUES (%s, %s) ON CONFLICT (group_id, date) DO NOTHING",
        (group_id, date_str),
    )
    conn.commit()
    cur.execute("SELECT * FROM attendance_sessions WHERE group_id=? AND date=?", (group_id, date_str))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def set_notified(session_id: int, field: str):
    if field not in (
        "notified_admin",
        "notified_teacher",
        "notified_admin_pre",
        "notified_admin_post",
        "notified_teacher_pre",
        "notified_teacher_post",
    ):
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE attendance_sessions SET {field}=1 WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


def claim_notified(session_id: int, field: str) -> bool:
    if field not in (
        "notified_admin",
        "notified_teacher",
        "notified_admin_pre",
        "notified_admin_post",
        "notified_teacher_pre",
        "notified_teacher_post",
    ):
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE attendance_sessions SET {field}=1 WHERE id=? AND COALESCE({field}, 0)=0",
            (session_id,),
        )
        claimed = (getattr(cur, "rowcount", 0) or 0) > 0
        conn.commit()
        return claimed
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("claim_notified failed session_id=%s field=%s", session_id, field)
        return False
    finally:
        conn.close()


def set_session_opened(session_id: int, opened_by: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE attendance_sessions SET opened_by=?, opened_at=CURRENT_TIMESTAMP, status='open' WHERE id=?",
        (opened_by, session_id),
    )
    conn.commit()
    conn.close()


def set_session_closed(session_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE attendance_sessions SET status='closed', closed_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))
    conn.commit()
    conn.close()


def get_session(session_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM attendance_sessions WHERE id=?", (session_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_group_sessions(group_id: int):
    """Get all attendance sessions for a group, ordered by date descending"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM attendance_sessions 
        WHERE group_id=? 
        ORDER BY date DESC
    """, (group_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_attendance(session_id: int, user_id: int, status: str):
    """Persist one student's status for the session's group/date (Present / Absent)."""
    session = get_session(session_id)
    if not session:
        return False
    if is_lesson_otmen_date_cancelled(str(session.get("date") or "")):
        return False
    st = (status or "Present").strip()
    if st.lower() == "present":
        st = "Present"
    elif st.lower() == "absent":
        st = "Absent"
    return bool(add_attendance(user_id, session["group_id"], session["date"], st))


def get_attendance_map(group_id: int, date_str: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT user_id, status FROM attendance WHERE group_id=? AND date=?", (group_id, date_str))
    rows = cur.fetchall()
    conn.close()
    return {r["user_id"]: r["status"] for r in rows}


def build_attendance_keyboard(session_id: int, group_id: int, date_str: str, page: int, lang: str = "uz"):
    session = get_session(session_id)
    is_closed = bool(session and session.get("status") == "closed")

    users = get_group_users(group_id)
    total = len(users)
    start = page * PAGE_SIZE
    end = min(total, start + PAGE_SIZE)
    slice_users = users[start:end]

    status_map = get_attendance_map(group_id, date_str)

    lbl_present = t(lang, "attendance_kb_mark_present")
    lbl_absent = t(lang, "attendance_kb_mark_absent")

    rows = []
    for u in slice_users:
        uid = u["id"]
        st = (status_map.get(uid) or "").lower()
        prefix = "✅ " if st == "present" else ("❌ " if st == "absent" else "⚪ ")
        name_btn = InlineKeyboardButton(text=prefix + f"{u.get('first_name','')} {u.get('last_name','')}", callback_data="att_noop")
        # When session is closed, disable mark buttons to avoid confusing UI.
        present_cb = "att_noop" if is_closed else f"att_mark_{session_id}_{uid}_Present_{page}"
        absent_cb = "att_noop" if is_closed else f"att_mark_{session_id}_{uid}_Absent_{page}"
        present_btn = InlineKeyboardButton(text=lbl_present, callback_data=present_cb)
        absent_btn = InlineKeyboardButton(text=lbl_absent, callback_data=absent_cb)
        rows.append([name_btn, present_btn, absent_btn])

    nav = []
    if start > 0:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_prev"), callback_data=f"att_page_{session_id}_{page-1}"))
    if end < total:
        nav.append(InlineKeyboardButton(text=t(lang, "btn_next_arrow"), callback_data=f"att_page_{session_id}_{page+1}"))
    if nav:
        rows.append(nav)

    finish_cb = "att_noop" if is_closed else f"att_finish_{session_id}"
    rows.append([InlineKeyboardButton(text=t(lang, "attendance_finish_btn"), callback_data=finish_cb)])

    return InlineKeyboardMarkup(inline_keyboard=rows)


async def send_attendance_panel(
    bot,
    chat_id: int,
    session_id: int,
    group_id: int,
    date_str: str,
    page: int = 0,
    panel_owner: str = "admin",
):
    group = get_group(group_id)
    # Try to detect language from recipient if they exist in users table
    u = get_user_by_telegram(str(chat_id))
    lang = detect_lang_from_user(u or {})
    title = t(lang, 'attendance_title', group=_localized_group_name(group, lang), date=date_str)
    set_panel_ui_lang(session_id, panel_owner, lang)
    kb = build_attendance_keyboard(session_id, group_id, date_str, page, lang=lang)
    msg = await bot.send_message(chat_id, title, reply_markup=kb)
    _remember_panel(session_id, panel_owner, chat_id, msg.message_id)
    return msg.message_id


def can_teacher_manage_group(teacher_user: dict, group: dict) -> bool:
    return teacher_user and teacher_user.get("login_type") == 3 and group and group.get("teacher_id") == teacher_user.get("id")


async def attendance_scheduler(bot, role: str, admin_chat_ids=None):
    """
    role: 'admin' or 'teacher'
    - admin: notify ADMIN_CHAT_IDS
    - teacher: notify each group's teacher telegram_id
    """
    admin_chat_ids = admin_chat_ids or []
    while True:
        try:
            now = now_tashkent()
            today = now.strftime("%Y-%m-%d")
            cur_time = now.strftime("%H:%M")
            weekday = now.weekday()  # 0=Mon ... 6=Sun

            conn = get_conn()
            cur = conn.cursor()
            # Fetch all groups that have a schedule; we will decide per-group if today is a lesson day
            cur.execute("SELECT * FROM groups WHERE lesson_start IS NOT NULL AND lesson_end IS NOT NULL")
            groups = [dict(r) for r in cur.fetchall()]
            conn.close()

            for g in groups:
                # Decide if this group has lesson today
                lesson_date = (g.get("lesson_date") or "").strip()
                has_today = False
                if lesson_date:
                    # Explicit calendar date
                    if re.match(r"^\d{4}-\d{2}-\d{2}$", lesson_date):
                        has_today = (lesson_date == today)
                    else:
                        code = lesson_date.upper()
                        if code in ("ODD", "MWF", "MON/WED/FRI", "MON,WED,FRI"):
                            # Mon/Wed/Fri
                            has_today = weekday in (0, 2, 4)
                        elif code in ("EVEN", "TTS", "TUE/THU/SAT", "TUE,THU,SAT"):
                            # Tue/Thu/Sat
                            has_today = weekday in (1, 3, 5)
                if not has_today:
                    continue

                start = (g.get("lesson_start") or "")[:5]
                end = (g.get("lesson_end") or "")[:5]
                if not start or not end:
                    continue

                # Build timezone-aware datetimes for comparisons
                try:
                    start_naive = datetime.strptime(f"{today} {start}", "%Y-%m-%d %H:%M")
                    end_naive = datetime.strptime(f"{today} {end}", "%Y-%m-%d %H:%M")
                    start_dt = TZ.localize(start_naive)
                    end_dt = TZ.localize(end_naive)
                except Exception:
                    continue
                pre_dt = start_dt - timedelta(minutes=10)

                # Operate from (start - 10 min) until end; for now > end_dt we only close.
                if now < pre_dt:
                    continue

                # If admin otmen already cancelled this date, do not create/reopen
                # attendance sessions and do not send notifications.
                if is_lesson_otmen_date_cancelled(today):
                    continue

                session = ensure_session(g["id"], today)
                if not session or session.get("status") == "closed":
                    continue

                # Pre-notify removed as requested: only notify at the exact start time.

                # Post-notify: at/after start until end (so if bot restarts, it still notifies)
                if start_dt <= now <= end_dt:
                    if role == "admin":
                        if not session.get("notified_admin_post") and not session.get("notified_admin") and claim_notified(session["id"], "notified_admin_post"):
                            for admin_id in admin_chat_ids:
                                if not _admin_should_receive_group_notification(int(admin_id), g):
                                    continue
                                try:
                                    admin_user = get_user_by_telegram(str(admin_id))
                                    admin_lang = detect_lang_from_user(admin_user or {})
                                    if admin_user:
                                        _store_attendance_web_notification(
                                            user_id=int(admin_user.get("id") or 0),
                                            role="admin",
                                            group=g,
                                            date_str=today,
                                            start=start,
                                            end=end,
                                            phase="post",
                                            lang=admin_lang,
                                        )
                                    await bot.send_message(
                                        admin_id,
                                        t(admin_lang, 'attendance_post_notify', group=g.get('name'), start=start, end=end),
                                        reply_markup=_attendance_link_keyboard(admin_lang, "admin", g["id"], today),
                                    )
                                except Exception:
                                    logger.exception("Admin attendance post-notify failed")
                            # legacy flag for backward compatibility with old DBs/logic
                            set_notified(session["id"], "notified_admin")

                    if role == "teacher":
                        if not session.get("notified_teacher_post") and not session.get("notified_teacher") and claim_notified(session["id"], "notified_teacher_post"):
                            recipients = _teacher_recipients_for_attendance(g, today)
                            for teacher in recipients:
                                try:
                                    tid = int(teacher["telegram_id"])
                                    t_lang = detect_lang_from_user(teacher)
                                    _store_attendance_web_notification(
                                        user_id=int(teacher.get("id") or 0),
                                        role="teacher",
                                        group=g,
                                        date_str=today,
                                        start=start,
                                        end=end,
                                        phase="post",
                                        lang=t_lang,
                                    )
                                    await bot.send_message(
                                        tid,
                                        t(t_lang, 'attendance_post_notify', group=g.get('name'), start=start, end=end),
                                        reply_markup=_attendance_link_keyboard(t_lang, "teacher", g["id"], today),
                                    )
                                except Exception:
                                    logger.exception("Teacher attendance post-notify failed")
                            set_notified(session["id"], "notified_teacher")

        except Exception:
            logger.exception("attendance_scheduler loop error")

        await asyncio.sleep(30)
