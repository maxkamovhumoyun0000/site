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


async def send_direct_userbot_message(phone_number: str, message_text: str, event_type: str = "general") -> Dict[str, Any]:
    """Resolves phone number to Telegram contact and sends direct message."""
    client = await get_active_pyrogram_client()
    if not client:
        return {"ok": False, "error": "Userbot faol emas yoki ulangan emas."}

    phone = format_phone(phone_number)
    if not phone:
        return {"ok": False, "error": "Telefon raqami noto'g'ri."}

    tg_user_id = None
    cached = get_cached_userbot_contact(phone)
    if cached and cached.get("telegram_user_id"):
        tg_user_id = int(cached["telegram_user_id"])

    try:
        if not tg_user_id:
            # Import contact to resolve user_id
            contacts = await client.import_contacts([InputPhoneContact(phone, "Parent")])
            if contacts and contacts.users:
                user = contacts.users[0]
                tg_user_id = user.id
                cache_userbot_contact(phone, user.id, user.first_name, user.last_name)
            else:
                log_userbot_message(phone, None, event_type, message_text, "failed", "Telegram foydalanuvchisi topilmadi yoki maxfiylik sozlamalari yopiq")
                return {"ok": False, "error": "Foydalanuvchi Telegramdan topilmadi."}

        await client.send_message(tg_user_id, message_text)
        log_userbot_message(phone, tg_user_id, event_type, message_text, "sent")
        return {"ok": True, "phone": phone, "telegram_user_id": tg_user_id}
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
                await asyncio.sleep(3.5) # Safe rate-limiting delay between DMs

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
            loop = asyncio.get_event_loop()
        _worker_task = loop.create_task(_userbot_queue_worker())


def queue_userbot_notification(phone: str, text: str, event_type: str = "general"):
    """Pushes a notification message to the Userbot dispatch queue."""
    clean_phone = format_phone(phone)
    if not clean_phone or not text:
        return
    _userbot_queue.put_nowait({
        "phone": clean_phone,
        "text": text,
        "event_type": event_type,
    })


def render_userbot_template(template_key: str, context: Dict[str, Any]) -> Optional[str]:
    """Helper to render message templates with dynamic context variables."""
    settings = get_userbot_settings()
    
    # Check if this notification toggle is enabled
    toggle_map = {
        "tpl_attendance_absent": "notify_attendance_absent",
        "tpl_attendance_late": "notify_attendance_late",
        "tpl_homework_missing": "notify_homework_missing",
        "tpl_payment_reminder": "notify_payment_reminder",
        "tpl_payment_overdue": "notify_payment_reminder",
        "tpl_payment_receipt": "notify_payment_receipt",
        "tpl_welcome_group": "notify_welcome_group",
        "tpl_holiday_cancellation": "notify_holiday_cancellation",
        "tpl_achievement": "notify_achievements",
    }
    
    toggle_key = toggle_map.get(template_key)
    if toggle_key and not bool(settings.get(toggle_key, 1)):
        return None # Disabled by admin

    raw_tpl = str(settings.get(template_key) or "").strip()
    if not raw_tpl:
        return None

    # Safe variable replacement
    res = raw_tpl
    for key, val in context.items():
        placeholder = "{" + str(key) + "}"
        res = res.replace(placeholder, str(val if val is not None else ""))
    return res
