import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Try to load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except Exception:
    pass

ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN')
TEACHER_BOT_TOKEN = os.getenv('TEACHER_BOT_TOKEN')
STUDENT_BOT_TOKEN = os.getenv('STUDENT_BOT_TOKEN')
SUPPORT_BOT_TOKEN = os.getenv('SUPPORT_BOT_TOKEN')
TELEGRAM_MINI_APP_BASE_URL = os.getenv('TELEGRAM_MINI_APP_BASE_URL', '').strip()


# Require PostgreSQL DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')
REQUIRE_POSTGRES = os.getenv("REQUIRE_POSTGRES", "true").strip().lower() in ("1", "true", "yes", "on")
if REQUIRE_POSTGRES and not (DATABASE_URL or "").strip().lower().startswith(("postgresql://", "postgres://")):
    raise RuntimeError("REQUIRE_POSTGRES=true but DATABASE_URL is not a PostgreSQL URL")




# For optional Redis caching in utils
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Allowed subjects
SUBJECTS = ['English', 'Russian']

# General admins: full visibility/control across all data and modules.
ADMIN_CHAT_IDS = [int(x) for x in os.getenv('ADMIN_CHAT_IDS', '').split(',') if x.strip().isdigit()]
TEACHER_CHAT_IDS = [int(x) for x in os.getenv('TEACHER_CHAT_IDS', '').split(',') if x.strip().isdigit()]

# Support lesson booking "NEW BOOKING" notifications: ALL_ADMIN_IDS (main + limited) via SUPPORT_BOT_TOKEN (student_bot).
# See student_bot._support_booking_notify_admin_ids()

# Limited admins (only manage their own students/groups).
# Set in .env as:
#   DiamondAdmin1=...
#   DiamondAdmin2=...
_limited_1 = (
    os.getenv('DiamondAdmin1')
    or os.getenv('DiamondAmind1')  # backward compatibility for common typo
    or os.getenv('DIAMOND_ADMIN_1')
)
_limited_2 = os.getenv('DiamondAdmin2') or os.getenv('DIAMOND_ADMIN_2')
LIMITED_ADMIN_CHAT_IDS = [int(x) for x in (_limited_1, _limited_2) if x and str(x).strip().isdigit()]

# All admins (main + limited) — can access admin bot; scoping applied per role
ALL_ADMIN_IDS = list(dict.fromkeys(ADMIN_CHAT_IDS + LIMITED_ADMIN_CHAT_IDS))


def limited_admin_label(admin_id: int) -> str:
    """
    Friendly label for limited admins in UI.
    Uses order in LIMITED_ADMIN_CHAT_IDS:
      [0] -> DiamondAdmin1
      [1] -> DiamondAdmin2
    Fallback: "Admin {id}"
    """
    try:
        aid = int(admin_id)
    except Exception:
        return f"Admin {admin_id}"
    if LIMITED_ADMIN_CHAT_IDS:
        if len(LIMITED_ADMIN_CHAT_IDS) >= 1 and aid == int(LIMITED_ADMIN_CHAT_IDS[0]):
            return "DiamondAdmin1"
        if len(LIMITED_ADMIN_CHAT_IDS) >= 2 and aid == int(LIMITED_ADMIN_CHAT_IDS[1]):
            return "DiamondAdmin2"
    return f"Admin {aid}"

# Diamondvoy: full DB wipe (PostgreSQL) after secret confirmation — set in .env only, never commit real values.
DIAMONDVOY_DB_RESET_SECRET = (os.getenv("DIAMONDVOY_DB_RESET_SECRET") or "").strip()

# Firebase Cloud Messaging (real OS-level push notifications for both
# Flutter apps, Android + iOS). Each app+platform combo
# (student/teacher x android/ios) was registered as its OWN separate
# Firebase project (rather than one shared project per app, or one for
# everything), so there are 4 independent service-account credentials —
# one per project — instead of a single global one. For each of the 4,
# set ONE of:
#   FIREBASE_SERVICE_ACCOUNT_JSON_<SLOT> — the full service-account JSON
#     as a single-line string (convenient for most hosting panels' env-var
#     UIs).
#   FIREBASE_SERVICE_ACCOUNT_PATH_<SLOT> — absolute path to the
#     service-account .json file on disk (convenient for local/VM
#     deployments).
# <SLOT> is one of STUDENT_ANDROID / STUDENT_IOS / TEACHER_ANDROID /
# TEACHER_IOS, matching the `app`+`platform` columns already stored per
# device token in `push_device_tokens` (see
# `POST /notifications/push-token`), so `push_notifications.py` can pick
# the right project's credentials per-token when sending.
# Never commit the actual key material — all are read from the
# environment only. When a given slot's credentials aren't set,
# push_notifications.py silently skips ONLY that slot (in-app
# notifications still work as before; other configured slots are
# unaffected).
FIREBASE_SERVICE_ACCOUNT_JSON = (os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
FIREBASE_SERVICE_ACCOUNT_PATH = (os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or "").strip()

FIREBASE_CREDENTIALS_BY_SLOT: dict[str, dict[str, str]] = {}
for _slot in ("STUDENT_ANDROID", "STUDENT_IOS", "TEACHER_ANDROID", "TEACHER_IOS"):
    _json_val = (os.getenv(f"FIREBASE_SERVICE_ACCOUNT_JSON_{_slot}") or "").strip()
    _path_val = (os.getenv(f"FIREBASE_SERVICE_ACCOUNT_PATH_{_slot}") or "").strip()
    if _json_val or _path_val:
        FIREBASE_CREDENTIALS_BY_SLOT[_slot] = {"json": _json_val, "path": _path_val}

# ================== DATABASE ==================
# Runtime storage is PostgreSQL-only.  Keep the name available for old imports,
# but never default to or create a local .db file.
DB_PATH = ""

# For one-time password generation
OTP_LENGTH = 6

# Basic login limits
MAX_LOGIN_ATTEMPTS = 3
# Student bot: optional forced channel subscription (see force_subscribe.py)
def _env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name, "") or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


FORCE_SUBSCRIBE = _env_bool("FORCE_SUBSCRIBE", "false")
_force_ch = os.getenv("FORCE_SUBSCRIBE_CHANNEL_ID", "").strip()
try:
    FORCE_SUBSCRIBE_CHANNEL_ID: int | None = int(_force_ch) if _force_ch else None
except ValueError:
    FORCE_SUBSCRIBE_CHANNEL_ID = None
FORCE_SUBSCRIBE_CHANNEL_URL = os.getenv(
    "FORCE_SUBSCRIBE_CHANNEL_URL",
    "https://t.me/diamond_education1",
).strip()

# Runtime transport mode
USE_WEBHOOK = _env_bool("USE_WEBHOOK", "false")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
WEBHOOK_PATH_PREFIX = os.getenv("WEBHOOK_PATH_PREFIX", "tg").strip() or "tg"
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "0.0.0.0").strip() or "0.0.0.0"
WEBHOOK_STALE_UPDATE_MAX_AGE_SEC = max(1, _env_int("WEBHOOK_STALE_UPDATE_MAX_AGE_SEC", 120))
WEBHOOK_STALE_FILTER_WINDOW_SEC = max(1, _env_int("WEBHOOK_STALE_FILTER_WINDOW_SEC", 300))

# Per-bot webhook ports (safe defaults when bots run as separate services)
ADMIN_WEBHOOK_PORT = int(os.getenv("ADMIN_WEBHOOK_PORT", "8081"))
TEACHER_WEBHOOK_PORT = int(os.getenv("TEACHER_WEBHOOK_PORT", "8082"))
STUDENT_WEBHOOK_PORT = int(os.getenv("STUDENT_WEBHOOK_PORT", "8083"))
SUPPORT_WEBHOOK_PORT = int(os.getenv("SUPPORT_WEBHOOK_PORT", "8084"))

# Runtime resilience / keep-warm knobs
BOT_HEARTBEAT_INTERVAL_SEC = max(10, _env_int("BOT_HEARTBEAT_INTERVAL_SEC", 45))
BOT_SUPERVISOR_MIN_RESTART_SEC = max(1, _env_int("BOT_SUPERVISOR_MIN_RESTART_SEC", 2))
BOT_SUPERVISOR_MAX_RESTART_SEC = max(
    BOT_SUPERVISOR_MIN_RESTART_SEC,
    _env_int("BOT_SUPERVISOR_MAX_RESTART_SEC", 60),
)
