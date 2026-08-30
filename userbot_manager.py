import asyncio
import logging
import re
import time
from typing import Any, Optional, Dict
from db import (
    get_userbot_settings,
    update_userbot_settings,
    get_cached_userbot_contact,
    cache_userbot_contact,
    log_userbot_message,
)

logger = logging.getLogger(__name__)

# Pyrogram import handling
try:
    from pyrogram import Client
    from pyrogram.errors import (
        FloodWait,
        PhoneCodeInvalid,
        PhoneCodeExpired,
        SessionPasswordNeeded,
        UserPrivacyRestricted,
        PeerIdInvalid,
        PhoneNumberInvalid,
        ApiIdInvalid,
    )
    from pyrogram.types import InputPhoneContact
    PYROGRAM_AVAILABLE = True
except ImportError:
    Client = None
    PYROGRAM_AVAILABLE = False
    logger.warning("Pyrogram library is not installed. Userbot feature disabled until installed.")

_userbot_client: Optional[Any] = None
_userbot_queue: asyncio.Queue = asyncio.Queue()
_worker_task: Optional[asyncio.Task] = None
_pending_login_clients: Dict[str, Dict[str, Any]] = {}


def format_phone(phone: str) -> str:
    """Clean phone number into E.164 format (+998901234567)."""
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return ""
    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 9:
        return "+998" + digits
    if raw.startswith("+"):
        return "+" + digits
    if digits.startswith("998"):
        return "+" + digits
    return "+" + digits


async def get_active_pyrogram_client() -> Optional[Any]:
    """Retrieves or initializes the active Pyrogram client from session_string stored in DB."""
    global _userbot_client
    if not PYROGRAM_AVAILABLE:
        return None

    settings = get_userbot_settings()
    session_str = str(settings.get("session_string") or "").strip()
    api_id = settings.get("api_id")
    api_hash = str(settings.get("api_hash") or "").strip()
    is_active = bool(settings.get("is_active") or 0)

    if not is_active or not session_str or not api_id or not api_hash:
        if _userbot_client and _userbot_client.is_connected:
            try:
                await _userbot_client.stop()
            except Exception:
                pass
            _userbot_client = None
        return None

    if _userbot_client is not None and _userbot_client.is_connected:
        return _userbot_client

    try:
        app = Client(
            "diamond_userbot_session",
            api_id=int(api_id),
            api_hash=api_hash,
            session_string=session_str,
            in_memory=True,
        )
        await app.start()
        _userbot_client = app
        logger.info("Userbot Pyrogram client started successfully")
        return _userbot_client
    except Exception as exc:
        logger.exception("Failed to start Userbot Pyrogram client: %s", exc)
        _userbot_client = None
        return None


async def send_userbot_otp_code(api_id: int, api_hash: str, phone_number: str) -> Dict[str, Any]:
    """Sends SMS OTP code via Pyrogram to initiate userbot login."""
    if not PYROGRAM_AVAILABLE:
        return {"ok": False, "error": "Pyrogram kutubxonasi serverda o'rnatilmagan"}

    phone = format_phone(phone_number)
    if not phone or len(re.sub(r"\D", "", phone)) < 9:
        return {"ok": False, "error": f"Telefon raqami formati noto'g'ri ({phone_number}). Misol: +998901234567"}

    try:
        temp_client = Client(
            f"userbot_auth_{int(time.time())}",
            api_id=int(api_id),
            api_hash=api_hash.strip(),
            in_memory=True,
        )
        await temp_client.connect()
        sent_code = await temp_client.send_code(phone)
        
        _pending_login_clients[phone] = {
            "client": temp_client,
            "phone_code_hash": sent_code.phone_code_hash,
            "api_id": int(api_id),
            "api_hash": api_hash.strip(),
            "created_at": time.time(),
        }
        return {
            "ok": True,
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "message": "SMS kod Telegram ilovasi/raqamiga yuborildi",
        }
    except PhoneNumberInvalid:
        return {"ok": False, "error": f"Telefon raqami Telegramda topilmadi yoki noto'g'ri ({phone}). Xalqaro formatda kiritib ko'ring: +998901234567"}
    except ApiIdInvalid:
        return {"ok": False, "error": "Telegram API ID yoki API Hash noto'g'ri."}
    except FloodWait as fw:
        return {"ok": False, "error": f"Telegram cheklovi (FloodWait): {fw.value} soniyadan keyin qayta urinib ko'ring."}
    except Exception as exc:
        err_msg = str(exc)
        if "PHONE_NUMBER_INVALID" in err_msg:
            return {"ok": False, "error": f"Telefon raqami Telegramda noto'g'ri ({phone}). Misol: +998901234567"}
        logger.exception("send_userbot_otp_code failed for %s", phone)
        return {"ok": False, "error": f"Kod yuborishda xatolik: {err_msg}"}


async def verify_userbot_otp_code(phone_number: str, code: str, password: Optional[str] = None) -> Dict[str, Any]:
    """Verifies OTP code and optional 2FA password, stores session string in DB."""
    if not PYROGRAM_AVAILABLE:
        return {"ok": False, "error": "Pyrogram package not installed"}

    phone = format_phone(phone_number)
    pending = _pending_login_clients.get(phone)
    if not pending:
        return {"ok": False, "error": "Sessiya topilmadi yoki vaqti o'tdi. Qaytadan kod so'rang."}

    client: Client = pending["client"]
    phone_code_hash = pending["phone_code_hash"]

    try:
        try:
            await client.sign_in(phone, phone_code_hash, code.strip())
        except SessionPasswordNeeded:
            if not password:
                return {
                    "ok": False,
                    "requires_2fa": True,
                    "error": "Telegram hisobingizda Ikki bosqichli tasdiqlash (2FA parol) yoqilgan. Parolni kiriting.",
                }
            await client.check_password(password.strip())
        except (PhoneCodeInvalid, PhoneCodeExpired) as exc:
            return {"ok": False, "error": "Kiritilgan SMS kod noto'g'ri yoki vaqti o'tgan."}

        session_string = await client.export_session_string()
        me = await client.get_me()

        update_userbot_settings({
            "api_id": pending["api_id"],
            "api_hash": pending["api_hash"],
            "phone_number": phone,
            "session_string": session_string,
            "is_active": 1,
        })

        await client.disconnect()
        _pending_login_clients.pop(phone, None)

        # Force restart client
        global _userbot_client
        if _userbot_client and _userbot_client.is_connected:
            await _userbot_client.stop()
        _userbot_client = None
        await get_active_pyrogram_client()

        return {
            "ok": True,
            "user_id": me.id,
            "first_name": me.first_name,
            "username": me.username,
            "phone": me.phone_number,
            "message": "Userbot muvaffaqiyatli ulandi va faollashtirildi!",
        }
    except Exception as exc:
        logger.exception("verify_userbot_otp_code failed for %s", phone)
        return {"ok": False, "error": f"Tasdiqlashda xatolik: {str(exc)}"}


def extract_all_phones(raw_input: Any) -> list[str]:
    """Extracts clean E.164 formatted phone numbers (+998...) from raw input text."""
    if not raw_input:
        return []
    text = str(raw_input).strip()
    if not text:
        return []

    parts = re.split(r"[,;/|\n\t]+", text)
    cleaned_phones: list[str] = []
    for part in parts:
        part_str = part.strip()
        if not part_str:
            continue
        formatted = format_phone(part_str)
        if formatted and len(re.sub(r"\D", "", formatted)) >= 9 and formatted not in cleaned_phones:
            cleaned_phones.append(formatted)
    return cleaned_phones


def _is_truthy(val: Any, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def get_target_phones_for_user(user: dict) -> list[str]:
    """
    Returns parent phone numbers for a user.
    Lookup hierarchy:
    1. Parent phone(s) listed in user['parent_phone'] or user['parent_phone_number']
    2. Parent accounts linked via family_group_id
    3. Fallback to student's own phone ONLY if no parent phone exists.
    """
    if not user:
        return []

    parent_phones: list[str] = []

    # 1. Parent phone column on student user
    raw_parent_phone = user.get("parent_phone") or user.get("parent_phone_number")
    if raw_parent_phone:
        for p in extract_all_phones(raw_parent_phone):
            if p not in parent_phones:
                parent_phones.append(p)

    # 2. Check linked parent users in same family_group_id if present
    family_group_id = user.get("family_group_id")
    if family_group_id and int(family_group_id) > 0:
        try:
            from db import get_conn, _row_to_dict
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                "SELECT phone, parent_phone FROM users WHERE family_group_id=? AND id!=?",
                (int(family_group_id), int(user.get("id") or 0))
            )
            rows = [_row_to_dict(r) for r in (cur.fetchall() or [])]
            conn.close()
            for r in rows:
                p_phone = r.get("phone")
                if p_phone:
                    for p in extract_all_phones(p_phone):
                        if p not in parent_phones:
                            parent_phones.append(p)
                p_parent_phone = r.get("parent_phone")
                if p_parent_phone:
                    for p in extract_all_phones(p_parent_phone):
                        if p not in parent_phones:
                            parent_phones.append(p)
        except Exception as exc:
            logger.exception("Failed to fetch family_group_id phones: %s", exc)

    # IF PARENT PHONES EXIST, RETURN ONLY PARENT PHONES!
    if parent_phones:
        return parent_phones

    # 3. Fallback ONLY if no parent phone exists: student's own phone
    user_phone = user.get("phone") or user.get("login_id")
    if user_phone:
        student_phones: list[str] = []
        for p in extract_all_phones(user_phone):
            if p not in student_phones:
                student_phones.append(p)
        return student_phones

    return []


async def send_direct_userbot_message(phone_number: str, message_text: str, event_type: str = "general") -> Dict[str, Any]:
    """Resolves phone number to Telegram contact and sends direct message."""
    client = await get_active_pyrogram_client()
    if not client:
        logger.warning("Userbot is not active or connected.")
        return {"ok": False, "error": "Userbot faol emas yoki ulangan emas."}

    phone = format_phone(phone_number)
    if not phone:
        return {"ok": False, "error": "Telefon raqami noto'g'ri."}

    tg_user_id = None
    cached = get_cached_userbot_contact(phone)
    if cached and cached.get("telegram_user_id"):
        tg_user_id = int(cached["telegram_user_id"])

    # Attempt sending to cached tg_user_id first
    if tg_user_id:
        try:
            await client.send_message(tg_user_id, message_text)
            log_userbot_message(phone, tg_user_id, event_type, message_text, "sent")
            return {"ok": True, "phone": phone, "telegram_user_id": tg_user_id}
        except Exception as exc:
            logger.info("Sending to cached tg_user_id %s failed for %s (%s). Re-resolving contact...", tg_user_id, phone, exc)
            tg_user_id = None

    # Resolve contact via Pyrogram import_contacts
    try:
        contacts = await client.import_contacts([InputPhoneContact(phone, "Parent", "Contact")])
        if contacts and getattr(contacts, "users", None):
            user = contacts.users[0]
            tg_user_id = user.id
            cache_userbot_contact(phone, user.id, getattr(user, "first_name", None), getattr(user, "last_name", None))
            await client.send_message(tg_user_id, message_text)
            log_userbot_message(phone, tg_user_id, event_type, message_text, "sent")
            return {"ok": True, "phone": phone, "telegram_user_id": tg_user_id}
        else:
            # Fallback direct send attempt to phone number string
            try:
                msg = await client.send_message(phone, message_text)
                if msg and getattr(msg, "chat", None):
                    cache_userbot_contact(phone, msg.chat.id, getattr(msg.chat, "first_name", None), getattr(msg.chat, "last_name", None))
                    log_userbot_message(phone, msg.chat.id, event_type, message_text, "sent")
                    return {"ok": True, "phone": phone, "telegram_user_id": msg.chat.id}
            except Exception:
                pass

            log_userbot_message(phone, None, event_type, message_text, "failed", "Telegram foydalanuvchisi topilmadi yoki maxfiylik sozlamalari yopiq")
            return {"ok": False, "error": "Foydalanuvchi Telegramdan topilmadi."}
    except FloodWait as exc:
        wait_seconds = exc.value
        logger.warning("Userbot FloodWait: waiting %s seconds", wait_seconds)
        log_userbot_message(phone, tg_user_id, event_type, message_text, "flood_wait", f"FloodWait: {wait_seconds}s")
        return {"ok": False, "error": f"Telegram cheklovi: {wait_seconds} soniya kuting."}
    except UserPrivacyRestricted:
        logger.info("UserPrivacyRestricted for phone %s", phone)
        log_userbot_message(phone, tg_user_id, event_type, message_text, "failed", "UserPrivacyRestricted")
        return {"ok": False, "error": "Ota-onada maxfiylik cheklovi bor."}
    except Exception as exc:
        logger.exception("send_direct_userbot_message failed for %s", phone)
        log_userbot_message(phone, tg_user_id, event_type, message_text, "failed", str(exc))
        return {"ok": False, "error": f"Xabar yuborishda xatolik: {str(exc)}"}


# Queue worker for rate-limited async dispatching
async def _userbot_queue_worker():
    """Background task processing message dispatch queue with safety delays."""
    logger.info("Userbot queue worker started.")
    while True:
        try:
            item = await _userbot_queue.get()
            phone = item.get("phone")
            text = item.get("text")
            event_type = item.get("event_type", "general")

            if phone and text:
                res = await send_direct_userbot_message(phone, text, event_type)
                logger.info("Queued Userbot DM dispatch result: %s", res)
                await asyncio.sleep(3.5)

            _userbot_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.exception("Userbot queue worker error: %s", exc)
            await asyncio.sleep(2)


def start_userbot_queue_worker(loop: Optional[asyncio.AbstractEventLoop] = None):
    """Starts the background queue worker task."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        if loop is None:
            try:
                loop = asyncio.get_event_loop()
            except Exception:
                return
        _worker_task = loop.create_task(_userbot_queue_worker())


_main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def set_main_event_loop(loop: asyncio.AbstractEventLoop):
    """Sets main running event loop for threadsafe notification dispatching."""
    global _main_event_loop
    _main_event_loop = loop


def queue_userbot_notification(phone: str, text: str, event_type: str = "general"):
    """Pushes a notification message to the Userbot dispatch queue."""
    clean_phone = format_phone(phone)
    if not clean_phone or not text:
        return

    logger.info("Queueing/sending userbot notification to %s (type=%s)", clean_phone, event_type)

    try:
        loop = asyncio.get_running_loop()
        if loop and loop.is_running():
            asyncio.create_task(send_direct_userbot_message(clean_phone, text, event_type))
            return
    except RuntimeError:
        pass

    global _main_event_loop
    if _main_event_loop and _main_event_loop.is_running():
        try:
            asyncio.run_coroutine_threadsafe(send_direct_userbot_message(clean_phone, text, event_type), _main_event_loop)
            return
        except Exception:
            pass

    try:
        _userbot_queue.put_nowait({
            "phone": clean_phone,
            "text": text,
            "event_type": event_type,
        })
        start_userbot_queue_worker()
    except Exception as exc:
        logger.exception("Failed to queue userbot notification: %s", exc)


def render_userbot_template(template_key: str, context: Dict[str, Any]) -> Optional[str]:
    """Helper to render message templates with dynamic context variables."""
    settings = get_userbot_settings()

    is_active = _is_truthy(settings.get("is_active"), True)
    if not is_active:
        logger.info("Userbot is not active (is_active=0)")
        return None

    key_map = {
        "attendance_absent": ("tpl_attendance_absent", "notify_attendance_absent"),
        "tpl_attendance_absent": ("tpl_attendance_absent", "notify_attendance_absent"),

        "attendance_late": ("tpl_attendance_late", "notify_attendance_late"),
        "tpl_attendance_late": ("tpl_attendance_late", "notify_attendance_late"),

        "homework_missing": ("tpl_homework_missing", "notify_homework_missing"),
        "homework_alert": ("tpl_homework_missing", "notify_homework_missing"),
        "tpl_homework_missing": ("tpl_homework_missing", "notify_homework_missing"),

        "payment_reminder": ("tpl_payment_reminder", "notify_payment_reminder"),
        "tpl_payment_reminder": ("tpl_payment_reminder", "notify_payment_reminder"),

        "payment_overdue": ("tpl_payment_overdue", "notify_payment_reminder"),
        "overdue_alert": ("tpl_payment_overdue", "notify_payment_reminder"),
        "tpl_payment_overdue": ("tpl_payment_overdue", "notify_payment_reminder"),

        "payment_receipt": ("tpl_payment_receipt", "notify_payment_receipt"),
        "tpl_payment_receipt": ("tpl_payment_receipt", "notify_payment_receipt"),

        "welcome_group": ("tpl_welcome_group", "notify_welcome_group"),
        "welcome_message": ("tpl_welcome_group", "notify_welcome_group"),
        "tpl_welcome_group": ("tpl_welcome_group", "notify_welcome_group"),

        "holiday_cancellation": ("tpl_holiday_cancellation", "notify_holiday_cancellation"),
        "lesson_cancelled": ("tpl_holiday_cancellation", "notify_holiday_cancellation"),
        "tpl_holiday_cancellation": ("tpl_holiday_cancellation", "notify_holiday_cancellation"),

        "achievement": ("tpl_achievement", "notify_achievements"),
        "achievement_notice": ("tpl_achievement", "notify_achievements"),
        "tpl_achievement": ("tpl_achievement", "notify_achievements"),
    }

    if template_key not in key_map:
        return None

    tpl_col, notify_col = key_map[template_key]

    if notify_col and not _is_truthy(settings.get(notify_col), True):
        logger.info("Userbot notification %s is disabled by admin setting", notify_col)
        return None

    raw_tpl = str(settings.get(tpl_col) or "").strip()
    if not raw_tpl:
        from db import DEFAULT_USERBOT_TEMPLATES
        raw_tpl = str(DEFAULT_USERBOT_TEMPLATES.get(tpl_col) or "").strip()

    if not raw_tpl:
        return None

    res = raw_tpl
    for key, val in context.items():
        placeholder = "{" + str(key) + "}"
        res = res.replace(placeholder, str(val if val is not None else ""))
    return res


def handle_userbot_attendance_event(user_id: int, group_id: int, lesson_date: str, status: str):
    """Triggered when student attendance is marked absent or late."""
    try:
        from db import get_user_by_id, get_group
        user = get_user_by_id(int(user_id))
        if not user:
            return
        group = get_group(int(group_id)) or {}

        target_phones = get_target_phones_for_user(user)
        if not target_phones:
            logger.info("handle_userbot_attendance_event: no target phone for user %s", user_id)
            return

        student_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "O'quvchi"
        group_name = str(group.get("title") or group.get("name") or "Guruh").strip()
        course_title = str(group.get("course_title") or group.get("subject") or "Fan").strip()

        st = str(status or "").strip().lower()
        if st in ("absent", "sababsiz", "sababli", "qoldirdi", "bormadi", "-", "yo'q", "yoq", "unexcused", "excused"):
            tpl_key = "attendance_absent"
            ctx = {
                "student_name": student_name,
                "group_name": group_name,
                "course_title": course_title,
                "date": lesson_date,
            }
        elif st in ("late", "kechikdi", "kechikib"):
            tpl_key = "attendance_late"
            ctx = {
                "student_name": student_name,
                "group_name": group_name,
                "date": lesson_date,
            }
        else:
            return

        msg_text = render_userbot_template(tpl_key, ctx)
        if msg_text:
            for phone in target_phones:
                queue_userbot_notification(phone, msg_text, event_type=f"attendance_{st}")
    except Exception as exc:
        logger.exception("handle_userbot_attendance_event failed: %s", exc)


def handle_userbot_group_join_event(student_id: int, group_id: int):
    """Triggered when a student is added to a group."""
    try:
        from db import get_user_by_id, get_group
        user = get_user_by_id(int(student_id))
        if not user:
            return
        group = get_group(int(group_id)) or {}

        target_phones = get_target_phones_for_user(user)
        if not target_phones:
            logger.info("handle_userbot_group_join_event: no target phone for user %s", student_id)
            return

        student_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "O'quvchi"
        group_name = str(group.get("title") or group.get("name") or "Guruh").strip()

        raw_days = (
            group.get("lesson_date")
            or group.get("schedule_days")
            or group.get("days")
            or group.get("lesson_days")
        )
        schedule_days = str(raw_days).strip() if raw_days else "Belgilangan kunlar"

        start_t = str(group.get("lesson_start") or group.get("start_time") or "").strip()
        end_t = str(group.get("lesson_end") or group.get("end_time") or "").strip()

        if start_t and end_t:
            schedule_time = f"{start_t} - {end_t}"
        elif start_t:
            schedule_time = start_t
        else:
            raw_time = group.get("schedule_time") or group.get("time")
            schedule_time = str(raw_time).strip() if raw_time else "Belgilangan vaqt"

        ctx = {
            "student_name": student_name,
            "group_name": group_name,
            "schedule_days": schedule_days,
            "schedule_time": schedule_time,
            "schedule": f"{schedule_days} {schedule_time}".strip(),
            "start_time": start_t or schedule_time,
            "end_time": end_t,
        }
        msg_text = render_userbot_template("welcome_group", ctx)
        if msg_text:
            for phone in target_phones:
                queue_userbot_notification(phone, msg_text, event_type="welcome_group")
    except Exception as exc:
        logger.exception("handle_userbot_group_join_event failed: %s", exc)


def handle_userbot_payment_received_event(student_id: int, amount: float | int, group_id: int | None = None, ym: str | None = None, payment_method: str | None = None):
    """Triggered when payment is recorded for a student."""
    try:
        from db import get_user_by_id, get_group
        user = get_user_by_id(int(student_id))
        if not user:
            return
        group = get_group(int(group_id)) if group_id else {}

        target_phones = get_target_phones_for_user(user)
        if not target_phones:
            return

        student_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "O'quvchi"
        group_name = str((group or {}).get("title") or (group or {}).get("name") or "Diamond Education").strip()
        formatted_amount = f"{float(amount or 0):,.0f}".replace(",", " ")

        ctx = {
            "student_name": student_name,
            "group_name": group_name,
            "amount": formatted_amount,
            "fee_amount": formatted_amount,
            "receipt_no": f"REC-{int(time.time())}",
        }
        msg_text = render_userbot_template("payment_receipt", ctx)
        if msg_text:
            for phone in target_phones:
                queue_userbot_notification(phone, msg_text, event_type="payment_receipt")
    except Exception as exc:
        logger.exception("handle_userbot_payment_received_event failed: %s", exc)


def handle_userbot_holiday_event(group_ids: list[int] | None, date_str: str, reason: str):
    """Triggered when a holiday or lesson cancellation is announced."""
    try:
        from db import get_all_users, get_group_users, get_group
        students = []
        if group_ids:
            for gid in group_ids:
                group = get_group(int(gid)) or {}
                gname = str(group.get("title") or group.get("name") or "Guruh").strip()
                gstudents = get_group_users(int(gid)) or []
                for s in gstudents:
                    students.append((s, gname))
        else:
            all_u = get_all_users() or []
            for u in all_u:
                if int(u.get("login_type") or 0) in (1, 2):
                    students.append((u, "Diamond Education"))

        seen_phones = set()
        for user, gname in students:
            target_phones = get_target_phones_for_user(user)
            for target_phone in target_phones:
                if not target_phone or target_phone in seen_phones:
                    continue
                seen_phones.add(target_phone)
                student_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "O'quvchi"
                ctx = {
                    "student_name": student_name,
                    "group_name": gname,
                    "date": date_str,
                    "reason": reason or "Dam olish kuni",
                }
                msg_text = render_userbot_template("holiday_cancellation", ctx)
                if msg_text:
                    queue_userbot_notification(target_phone, msg_text, event_type="holiday_cancellation")
    except Exception as exc:
        logger.exception("handle_userbot_holiday_event failed: %s", exc)


def handle_userbot_homework_missing_event(student_id: int, group_id: int | None = None, reason: str = "", score: str = ""):
    """Triggered when homework is missed or unfulfilled."""
    try:
        from db import get_user_by_id, get_group
        user = get_user_by_id(int(student_id))
        if not user:
            return
        group = get_group(int(group_id)) if group_id else {}

        target_phones = get_target_phones_for_user(user)
        if not target_phones:
            return

        student_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "O'quvchi"
        group_name = str((group or {}).get("title") or (group or {}).get("name") or "Guruh").strip()

        ctx = {
            "student_name": student_name,
            "group_name": group_name,
            "reason": reason or "Vazifa topshirilmadi",
            "score": str(score or "-"),
        }
        msg_text = render_userbot_template("homework_missing", ctx)
        if msg_text:
            for phone in target_phones:
                queue_userbot_notification(phone, msg_text, event_type="homework_missing")
    except Exception as exc:
        logger.exception("handle_userbot_homework_missing_event failed: %s", exc)


def handle_userbot_payment_reminder_event(student_id: int, fee_amount: float | int, date_str: str, group_id: int | None = None, is_overdue: bool = False):
    """Triggered for upcoming payment reminder or overdue payment notification."""
    try:
        from db import get_user_by_id, get_group
        user = get_user_by_id(int(student_id))
        if not user:
            return
        group = get_group(int(group_id)) if group_id else {}

        target_phones = get_target_phones_for_user(user)
        if not target_phones:
            return

        student_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "O'quvchi"
        group_name = str((group or {}).get("title") or (group or {}).get("name") or "Diamond Education").strip()
        formatted_amount = f"{float(fee_amount or 0):,.0f}".replace(",", " ")

        tpl_key = "payment_overdue" if is_overdue else "payment_reminder"
        ctx = {
            "student_name": student_name,
            "group_name": group_name,
            "date": date_str,
            "fee_amount": formatted_amount,
            "amount": formatted_amount,
        }
        msg_text = render_userbot_template(tpl_key, ctx)
        if msg_text:
            for phone in target_phones:
                queue_userbot_notification(phone, msg_text, event_type=tpl_key)
    except Exception as exc:
        logger.exception("handle_userbot_payment_reminder_event failed: %s", exc)


def handle_userbot_achievement_event(student_id: int, title: str, description: str = "", reward_dpoints: int = 0, reward_dcoins: int = 0):
    """Triggered when a student unlocks an achievement or reward."""
    try:
        from db import get_user_by_id
        user = get_user_by_id(int(student_id))
        if not user:
            return

        target_phones = get_target_phones_for_user(user)
        if not target_phones:
            return

        student_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip() or "O'quvchi"

        ctx = {
            "student_name": student_name,
            "achievement_title": title or "Yangi Yutuq",
            "title": title or "Yangi Yutuq",
            "description": description or "",
            "dpoints": str(reward_dpoints),
            "dcoins": str(reward_dcoins),
        }
        msg_text = render_userbot_template("achievement", ctx)
        if msg_text:
            for phone in target_phones:
                queue_userbot_notification(phone, msg_text, event_type="achievement")
    except Exception as exc:
        logger.exception("handle_userbot_achievement_event failed: %s", exc)


