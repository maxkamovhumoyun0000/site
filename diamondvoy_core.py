"""
Admin Diamondvoy: stats (delegates to diamondvoy_helpers), student search, payments, password reset, Gemini.
"""
from __future__ import annotations

import html as html_module
import re
from typing import TYPE_CHECKING

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from admin_shared_menus import (
    send_admin_payments_root_menu,
    send_admin_student_control_message,
    send_admin_teacher_control_message,
)
from auth import generate_password
from config import ADMIN_CHAT_IDS, LIMITED_ADMIN_CHAT_IDS
from db import get_user_by_id, get_user_by_name_search, is_student_shared_with_admin, log_diamondvoy_query, reset_user_password, get_diamondvoy_chat_history, save_diamondvoy_chat_message
from diamondvoy_helpers import (
    default_subjects_for_diamondvoy,
    diamondvoy_gemini_answer,
    stream_diamondvoy_text_reply,
    try_diamondvoy_bot_info,
    try_diamondvoy_app_version_action,
)
from i18n import t
from logging_config import get_logger

if TYPE_CHECKING:
    from aiogram import Bot

logger = get_logger(__name__)


def _can_manage_user_diamondvoy(admin_id: int, user: dict | None) -> bool:
    """Mirror admin_bot._can_manage_user without importing admin_bot (circular import)."""
    if not user:
        return False
    if admin_id in ADMIN_CHAT_IDS or admin_id not in LIMITED_ADMIN_CHAT_IDS:
        return True
    if user.get("login_type") not in (1, 2):
        return True
    if user.get("owner_admin_id") == admin_id:
        return True
    uid = user.get("id")
    if uid is not None and is_student_shared_with_admin(int(uid), admin_id):
        return True
    return False


# Avoid treating short “stats” questions as name search (e.g. “nechta user”).
_ADMIN_STUDENT_SEARCH_EXCLUDE = re.compile(
    r"\b(nechta|qancha|necha|jami|stat|statistika|holat|studentlar|userlar|users\b|"
    r"foydalanuvchi|aktiv|daily|kunlik|test|zaxira|dcoin|reyting|leaderboard|online|umumiy|всего|сколько)\b",
    re.I,
)

_UZ_TOKEN_SUFFIXES_LONG = ("ningiz", "larga", "lari", "ning")
_UZ_TOKEN_SUFFIXES_SHORT = ("ning", "ni", "ga", "da", "dan")


def admin_diamondvoy_trigger(text: str | None) -> bool:
    if not text:
        return False
    low = text.strip().lower()
    return any(
        x in low
        for x in (
            "diamond voy",
            "daimondvoy",
            "diamonvoy",
            "dimondvoy",
            "diamondvoy",
            "dmnd",
        )
    )


def extract_admin_diamondvoy_query(text: str) -> str:
    raw = (text or "").strip()
    low = raw.lower()
    # Longer / spaced variants first so slicing matches the found substring length.
    for prefix in (
        "diamond voy",
        "daimondvoy",
        "diamonvoy",
        "dimondvoy",
        "diamondvoy",
        "dmnd",
    ):
        pl = prefix.lower()
        if low.startswith(pl):
            return raw[len(prefix) :].strip(" :.,!?-")
        idx = low.find(pl)
        if idx >= 0:
            return raw[idx + len(prefix) :].strip(" :.,!?-")
    return raw.strip()


def _strip_intent_noise(q: str) -> str:
    s = q
    for pat in (
        r"(?i)\bstudent\s+qidir\b",
        r"(?i)\bstudent\s+top\b",
        r"(?i)\bqidir\b",
        r"(?i)\bkim\s+bor\b",
        r"(?i)\boquvchi\b",
        r"(?i)\bo'quvchi\b",
        r"(?i)\boʻquvchi\b",
        r"(?i)\bpayment\b",
        r"(?i)\btolov\b",
        r"(?i)\bto['']lov\b",
        r"(?i)\bparol\w*",
        r"(?i)\bpassword\b",
        r"(?i)\breset\b",
        r"(?i)\byangilash\b",
        r"(?i)\bo'zgartir\b",
        r"(?i)\bozgartir\b",
        r"(?i)\bo'zgart\b",
        r"(?i)\bprofilini\b",
        r"(?i)\bprofil\b",
        r"(?i)\bko'rsat\b",
        r"(?i)\bko‘rsat\b",
        r"(?i)\bdiamondvoy\b",
        r"(?i)\bdmnd\b",
        r"(?i)\bmanga\b",
        r"(?i)\bqil\b",
        r"(?i)\btop\b",
        r"(?i)\bdatabasedan\b",
        r"(?i)\bdatabase\b",
        r"(?i)\bma'?lumotlar\s+bazasidan\b",
        r"(?i)\bber\b",
        r"(?i)\bko'?rsating\b",
        r"(?i)\bko‘rsating\b",
        r"(?i)\b(?:och|ochib|ochish|ochirish)\b",
        r"(?i)\bpayment\w*",
        r"(?i)\btolov\w*",
        r"(?i)\bto['']lov\w*",
        r"(?i)\bo'qituvchi\b",
        r"(?i)\boqituvchi\b",
        r"(?i)\boʻqituvchi\b",
        r"(?i)\bteacher\b",
        r"(?i)\bучитель\b",
        r"(?i)\bустоз\b",
    ):
        s = re.sub(pat, " ", s)
    return " ".join(s.split()).strip()


def _soften_uz_name_tokens(name: str) -> str:
    """Strip common Uzbek clitics from tokens for broader LIKE match (search only)."""
    min_stem = 4
    out: list[str] = []
    for raw_t in (name or "").split():
        w, low = raw_t, raw_t.lower()
        if len(low) < min_stem + 2:
            out.append(w)
            continue
        for suf in _UZ_TOKEN_SUFFIXES_LONG:
            if low.endswith(suf) and len(low) > len(suf) + min_stem - 1:
                w = w[: -len(suf)]
                low = w.lower()
                break
        if len(low) >= min_stem + 2:
            for suf in _UZ_TOKEN_SUFFIXES_SHORT:
                if low.endswith(suf) and len(low) > len(suf) + min_stem - 1:
                    w = w[: -len(suf)]
                    break
        w = w.strip("-'")
        if w:
            out.append(w)
    return " ".join(out).strip()


def _normalize_admin_person_query(q: str) -> str:
    return _soften_uz_name_tokens(_strip_intent_noise(q))


def _search_users_for_admin(
    name: str,
    *,
    login_types: tuple[int, ...] | None = None,
    limit: int = 20,
) -> list[dict]:
    name = (name or "").strip()
    if not name:
        return []
    tokens = name.split()
    candidates: list[str] = []
    seen_lower: set[str] = set()

    def add(c: str) -> None:
        c = (c or "").strip()
        if not c:
            return
        k = c.lower()
        if k in seen_lower:
            return
        seen_lower.add(k)
        candidates.append(c)

    add(name)
    if len(tokens) >= 2:
        add(" ".join(tokens[:2]))
    if tokens:
        add(max(tokens, key=len))
        if len(tokens) >= 2:
            add(tokens[0])
    allowed = set(login_types) if login_types is not None else None
    for cand in candidates:
        rows = get_user_by_name_search(cand, limit=limit)
        if allowed is not None:
            rows = [r for r in rows if int(r.get("login_type") or 0) in allowed]
        if rows:
            return rows
    return []


def _intent_student_search(q: str) -> bool:
    ql = q.lower()
    if any(
        k in ql
        for k in (
            "student qidir",
            "student top",
            "qidir",
            "o'quvchi",
            "oquvchi",
            "oʻquvchi",
            "kim bor",
            "profil",
            "o'qituvchi",
            "oqituvchi",
            "oʻqituvchi",
            "teacher",
            "учитель",
            "ustoz",
            "устоз",
        )
    ):
        return True
    if re.search(r"\b(databasedan|database)\b", ql):
        if _ADMIN_STUDENT_SEARCH_EXCLUDE.search(q):
            return False
        if _intent_payment(q) or _intent_password(q):
            return False
        return True
    tokens = ql.split()
    if len(tokens) < 2 or _intent_payment(q) or _intent_password(q):
        return False
    if _ADMIN_STUDENT_SEARCH_EXCLUDE.search(q):
        return False
    return True


def _intent_payment(q: str) -> bool:
    ql = q.lower()
    return any(
        k in ql
        for k in (
            "payment",
            "to'lov",
            "tolov",
            "toʻlov",
        )
    )


def _intent_password(q: str) -> bool:
    ql = q.lower()
    return any(w in ql for w in ("parol", "password", "reset", "yangil", "o'zgart", "o‘zgart", "yangi"))


def _intent_database_reset(q: str) -> bool:
    """Full PostgreSQL wipe request (Diamondvoy); must not overlap payment / generic search."""
    ql = (q or "").strip().lower()
    if not ql:
        return False
    if _intent_payment(q):
        return False
    wipe_signals = (
        "tozalab yubor",
        "tozalash",
        "bazani tozala",
        "databaseni tozala",
        "database tozala",
        "ma'lumotlar bazasini",
        "malumotlar bazasini",
        "to'liq tozala",
        "tolik tozala",
        "to‘liq tozala",
        "базу полностью",
        "очистить базу",
        "полностью очистить",
        "wipe database",
        "drop schema",
        "reset database",
        "clear database",
    )
    if not any(s in ql for s in wipe_signals):
        return False
    if _intent_password(q) and not any(
        x in ql for x in ("baz", "database", "schema", "databas", "очист", "tozala", "wipe", "drop", "clear")
    ):
        return False
    return True


class DiamondVoyAdmin:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def process(self, message: Message, lang: str) -> None:
        raw_text = (message.text or "").strip()
        q = extract_admin_diamondvoy_query(raw_text)

        if _intent_database_reset(q):
            from config import ALL_ADMIN_IDS, DIAMONDVOY_DB_RESET_SECRET

            uid = int(message.from_user.id)
            if uid not in ALL_ADMIN_IDS:
                await message.answer(t(lang, "diamondvoy_db_reset_forbidden_limited"))
                return
            if not DIAMONDVOY_DB_RESET_SECRET:
                await message.answer(
                    t(lang, "diamondvoy_db_reset_secret_not_configured"),
                    parse_mode="HTML",
                )
                return
            import admin_bot as admin_bot_mod

            st = admin_bot_mod.get_admin_state(message.chat.id)
            st["step"] = "dv_db_reset_await_code"
            await message.answer(t(lang, "diamondvoy_db_reset_confirm_prompt"), parse_mode="HTML")
            return

        if not q:
            await message.answer(t(lang, "diamondvoy_admin_empty_help"))
            return

        status_msg = await message.answer(t(lang, "diamondvoy_admin_status_searching"))
        admin_row = None
        try:
            from db import get_user_by_telegram

            admin_row = get_user_by_telegram(str(message.from_user.id))
        except Exception:
            logger.exception("get_user_by_telegram admin")

        subjects_for_log = default_subjects_for_diamondvoy(admin_row)
        uid_log = int(admin_row["id"]) if admin_row and admin_row.get("id") is not None else None
        subj_hint = subjects_for_log[0] if subjects_for_log else None

        name_part = _normalize_admin_person_query(q)

        if _intent_password(q) and name_part:
            await self._flow_password(message, status_msg, name_part, lang)
            return
        if _intent_student_search(q) and name_part:
            await self._flow_student_search(message, status_msg, name_part, lang)
            return
        ver_text = try_diamondvoy_app_version_action(q, is_admin=True, lang=lang)
        if ver_text is not None:
            try:
                await self.bot.edit_message_text(
                    ver_text,
                    chat_id=message.chat.id,
                    message_id=status_msg.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                await message.answer(ver_text, parse_mode="HTML")
            log_diamondvoy_query(uid_log, q, ver_text, subject=subj_hint, bot_scope="admin_full")
            return

        info_text = try_diamondvoy_bot_info(
            q,
            user=admin_row,
            telegram_user_id=message.from_user.id,
            lang=lang,
            scope="admin_full",
            student_state_map=None,
        )
        if info_text is not None:
            try:
                await self.bot.edit_message_text(
                    info_text,
                    chat_id=message.chat.id,
                    message_id=status_msg.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                await message.answer(info_text, parse_mode="HTML")
            log_diamondvoy_query(uid_log, q, info_text, subject=subj_hint, bot_scope="admin_full")
            return

        gemini_subjects = ["English", "Russian", "General", "Student", "Payment", "System", "Database"]
        
        conversation = []
        if uid_log:
            conversation = get_diamondvoy_chat_history(uid_log, limit=12)
            
        answer = await diamondvoy_gemini_answer(q, gemini_subjects, lang=lang, is_admin_context=True, conversation=conversation)
        await stream_diamondvoy_text_reply(
            self.bot, message.chat.id, answer, lang=lang, message_id=status_msg.message_id
        )
        log_diamondvoy_query(uid_log, q, answer, subject=subj_hint, bot_scope="admin_full")
        
        if uid_log:
            save_diamondvoy_chat_message(uid_log, "user", q)
            save_diamondvoy_chat_message(uid_log, "assistant", answer)

    async def _flow_student_search(
        self, message: Message, status_msg: Message, name: str, lang: str
    ) -> None:
        users = _search_users_for_admin(name, login_types=(1, 2, 3))
        try:
            await self.bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass
        if not users:
            await message.answer(t(lang, "diamondvoy_admin_no_users"))
            return
        if len(users) == 1:
            u = users[0]
            if int(u.get("login_type") or 0) == 3:
                await send_admin_teacher_control_message(self.bot, message.chat.id, u, lang)
            else:
                if not _can_manage_user_diamondvoy(message.from_user.id, u):
                    await message.answer(t(lang, "admin_share_forbidden"))
                    return
                await send_admin_student_control_message(
                    self.bot, message.chat.id, u, lang, viewer_admin_id=message.from_user.id
                )
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=(
                            ("👨‍🏫 " if int(u.get("login_type") or 0) == 3 else "")
                            + (
                                f"{(u.get('first_name') or '')[:18]} {(u.get('last_name') or '')[:18]}".strip()
                                or str(u.get("login_id"))
                            )
                        ),
                        callback_data=f"dv:stu:{int(u['id'])}",
                    )
                ]
                for u in users[:8]
            ]
        )
        await message.answer(
            t(lang, "diamondvoy_admin_pick_user", n=len(users)),
            reply_markup=kb,
        )

    async def _flow_payment(self, message: Message, status_msg: Message, name: str, lang: str) -> None:
        try:
            await self.bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass
        await send_admin_payments_root_menu(self.bot, message.chat.id, lang)

    async def _flow_password(self, message: Message, status_msg: Message, name: str, lang: str) -> None:
        users = _search_users_for_admin(name, login_types=(1, 2, 3))
        try:
            await self.bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass
        if not users:
            await message.answer(t(lang, "diamondvoy_admin_no_users"))
            return
        if len(users) == 1:
            await self._do_password_reset(message, users[0], lang)
            return
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"{(u.get('first_name') or '')[:18]} {(u.get('last_name') or '')[:18]}".strip()
                        or str(u.get("login_id")),
                        callback_data=f"dv:pw:{int(u['id'])}",
                    )
                ]
                for u in users[:8]
            ]
        )
        await message.answer(t(lang, "diamondvoy_admin_pick_reset"), reply_markup=kb)

    async def _do_password_reset(self, message: Message, user: dict, lang: str) -> None:
        new_pw = generate_password(8)
        reset_user_password(int(user["id"]), new_pw)
        lid = html_module.escape(str(user.get("login_id") or ""))
        fn = html_module.escape(str(user.get("first_name") or ""))
        ln = html_module.escape(str(user.get("last_name") or ""))
        pw = html_module.escape(new_pw)
        lt = int(user.get("login_type") or 0)
        role = "Student" if lt in (1, 2) else "Teacher" if lt == 3 else "User"
        await message.answer(
            t(
                lang,
                "diamondvoy_admin_reset_done",
                role=role,
                first=fn,
                last=ln,
                login_id=lid,
                password=pw,
                combo=f"{lid}:{pw}",
            ),
            parse_mode="HTML",
        )


async def handle_diamondvoy_admin_callback(bot: Bot, callback: CallbackQuery, lang: str) -> None:
    data = callback.data or ""
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "dv":
        await callback.answer()
        return
    _, action, uid_s = parts
    try:
        uid = int(uid_s)
    except ValueError:
        await callback.answer()
        return
    user = get_user_by_id(uid)
    if not user:
        await callback.answer(t(lang, "diamondvoy_admin_no_users"), show_alert=True)
        return

    dv = DiamondVoyAdmin(bot)
    if action == "stu":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        if int(user.get("login_type") or 0) == 3:
            await send_admin_teacher_control_message(bot, callback.message.chat.id, user, lang)
        else:
            if not _can_manage_user_diamondvoy(callback.from_user.id, user):
                await callback.answer(t(lang, "admin_share_forbidden"), show_alert=True)
                return
            await send_admin_student_control_message(
                bot, callback.message.chat.id, user, lang, viewer_admin_id=callback.from_user.id
            )
    elif action == "pw":
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
        await dv._do_password_reset(callback.message, user, lang)
    elif action == "pay":
        await send_admin_payments_root_menu(bot, callback.message.chat.id, lang)
    await callback.answer()
