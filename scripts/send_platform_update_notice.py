#!/usr/bin/env python3
"""Send the trilingual "the platform is being updated" notice to every user.

Run on the server from the project root, with the same .env/DATABASE_URL as
the app:

    cd /root/diamond-site && .venv/bin/python scripts/send_platform_update_notice.py --dry-run
    cd /root/diamond-site && .venv/bin/python scripts/send_platform_update_notice.py --send

Without ``--send`` the script only reads (inside a READ ONLY transaction),
prints the recipient counts per channel and a sample, and sends nothing.

What ``--send`` writes
----------------------
1. ``web_payment_notifications``: one row per active, non-blocked user
   (students, teachers, support, admins incl. media, Speaking accounts) with
   ``notification_type='broadcast'``, ``source_key=SOURCE_KEY``, the title
   ``INBOX_TITLE`` and the UZ/RU/EN message. ``GET /notifications`` returns it
   as ``{"id": "payment_notification:<id>", "type": "broadcast", ...}``; that
   type opens the announcement popup on the website (student, teacher,
   support, admin and media roles) and in the Student and Teacher apps.
2. FCM push (``push_device_tokens``, Student/Teacher apps) to the devices of
   every user who got a new row in this run, in ``users.language`` (default
   uz), with the same data as an admin broadcast, so a tap opens the popup.
   Tokens FCM reports as unregistered are pruned, as push_notifications.py does.
3. Speaking app: one ``speaking_notifications`` row (the Speaking admin
   broadcast log) and an FCM push to every registered Speaking device
   (``speaking_push_tokens``; devices linked to a blocked or deleted account
   are skipped) with ``type='speaking_announcement'``. The app shows that push
   as its popup and reads the popup title/body from the data, so the popup is
   trilingual while the system notification uses the account language (uz
   for devices without an account).

``--send`` stops before writing anything when no Firebase project can be
initialised, so the inbox items are never created without their push.

Idempotency
-----------
Inbox rows are unique per (user_id, SOURCE_KEY); a re-run creates rows only
for users who still lack one and pushes only to those users. The Speaking
push runs once: the ``speaking_notifications`` row with this exact title and
body marks it as done (a row left as 'failed' with 0 recipients is retried).
A PostgreSQL advisory lock prevents two concurrent ``--send`` runs.

The script never sends Telegram messages and does not import backend/main.py
(importing it builds the whole FastAPI app and creates upload directories);
it uses db.get_conn and push_notifications directly.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("platform_update_notice")

SOURCE_KEY = "platform_update_notice_2026_10_28"
NOTIFICATION_TYPE = "broadcast"
LANGUAGES = ("uz", "ru", "en")
DEFAULT_LANGUAGE = "uz"

# Owner-approved texts. Do not edit without the owner.
PUSH_TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "title": "Muhim: platforma yangilanmoqda",
        "body": (
            "Hurmatli foydalanuvchi! Diamond Education platformasida xavfsizlikni kuchaytirish va yangi "
            "imkoniyatlarni qo'shish ishlari olib borilmoqda. Shu sababli Student, Speaking va Teacher "
            "ilovalarining ayrim bo'limlari ilovangiz yangilanmaguncha to'liq yoki to'g'ri ishlamasligi "
            "mumkin. Iltimos, ilovani App Store yoki Google Play orqali yangilang. Noqulaylik uchun uzr "
            "so'raymiz."
        ),
    },
    "ru": {
        "title": "Важно: платформа обновляется",
        "body": (
            "Уважаемый пользователь! На платформе Diamond Education проводятся работы по усилению "
            "безопасности и добавлению новых функций. Поэтому некоторые разделы приложений Student, "
            "Speaking и Teacher могут работать не полностью или некорректно, пока вы не обновите "
            "приложение. Пожалуйста, обновите приложение через App Store или Google Play. Приносим "
            "извинения за неудобства."
        ),
    },
    "en": {
        "title": "Important: the platform is being updated",
        "body": (
            "Dear user! We are strengthening security and adding new features on the Diamond Education "
            "platform. Because of this, some parts of the Student, Speaking and Teacher apps may not work "
            "fully or correctly until you update your app. Please update the app from the App Store or "
            "Google Play. We apologize for the inconvenience."
        ),
    },
}

# Popup and inbox text: one message, UZ then RU then EN, blank line between.
INBOX_TITLE = "Muhim · Важно · Important"
INBOX_MESSAGE = "\n\n".join(PUSH_TEXTS[language]["body"] for language in LANGUAGES)
# /notifications replaces an empty button/target with the payments page, so
# the row carries a neutral target: the apps show no extra button for "home"
# and the website button returns to the dashboard.
INBOX_BUTTON_TEXT = "OK"
INBOX_BUTTON_URL = "/?section=home"
INBOX_TARGET_SCREEN = "home"
INBOX_META = {"source_key": SOURCE_KEY, "script": "scripts/send_platform_update_notice.py"}

# Same data as an admin broadcast push (backend/main.py _run_broadcast_job).
APP_PUSH_DATA = {"target_screen": "notifications", "button_url": "", "notification_type": NOTIFICATION_TYPE}
SPEAKING_PUSH_TYPE = "speaking_announcement"

# Accounts that can sign in: 1/2 students, 3 teacher or support, 4 admin
# (incl. media), 5 support, 7 Speaking app. Type 6 is retired and blocked.
ACTIVE_LOGIN_TYPES = (1, 2, 3, 4, 5, 7)
INBOX_BATCH_SIZE = 500
TOKEN_QUERY_CHUNK = 1000
FCM_BATCH_SIZE = 500  # firebase_admin.messaging.send_each accepts up to 500 messages
PUSH_TITLE_LIMIT = 180  # same caps as push_notifications._send_to_tokens
PUSH_BODY_LIMIT = 500
SAMPLE_SIZE = 5
ERROR_SAMPLE_LIMIT = 5

ELIGIBLE_USERS_SQL = """
    SELECT id, login_id, login_type, language
    FROM users
    WHERE COALESCE(blocked, 0) = 0
      AND COALESCE(active, 1) = 1
      AND COALESCE(screenshot_demo, 0) = 0
      AND speaking_deleted_at IS NULL
      AND COALESCE(login_type, 1) IN (1, 2, 3, 4, 5, 7)
    ORDER BY id
"""
EXISTING_NOTICE_SQL = "SELECT DISTINCT user_id FROM web_payment_notifications WHERE source_key = ?"
EXISTING_NOTICE_FOR_USERS_SQL = (
    "SELECT user_id FROM web_payment_notifications WHERE source_key = ? AND user_id = ANY(?)"
)
INSERT_NOTICE_SQL = """
    INSERT INTO web_payment_notifications
        (user_id, notification_type, title, message, button_text, button_url,
         target_screen, source_key, meta_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    RETURNING id
"""
USER_TOKENS_SQL = "SELECT user_id, token, app, platform FROM push_device_tokens WHERE user_id = ANY(?)"
SPEAKING_DEVICES_SQL = """
    SELECT t.id AS device_row_id, t.token, t.platform, t.user_id,
           u.id AS account_id, u.language, u.blocked, u.active,
           u.screenshot_demo, u.speaking_deleted_at
    FROM speaking_push_tokens t
    LEFT JOIN users u ON u.id = t.user_id
    ORDER BY t.id
"""
SPEAKING_RECORD_SQL = """
    SELECT id, status, recipient_count
    FROM speaking_notifications
    WHERE title = ? AND body = ?
    ORDER BY id ASC
    LIMIT 1
"""
INSERT_SPEAKING_RECORD_SQL = """
    INSERT INTO speaking_notifications
        (title, body, target_part, target_topic_id, sent_by_user_id, recipient_count, status)
    VALUES (?, ?, NULL, NULL, NULL, 0, 'sending')
    RETURNING id
"""
UPDATE_SPEAKING_RECORD_SQL = "UPDATE speaking_notifications SET recipient_count = ?, status = ? WHERE id = ?"
LOCK_SQL = "SELECT pg_try_advisory_lock(hashtext(?)) AS locked"
UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtext(?)) AS unlocked"
READ_ONLY_SQL = "SET TRANSACTION READ ONLY"


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------

def normalize_language(value: Any) -> str:
    language = str(value or "").strip().lower()
    return language if language in LANGUAGES else DEFAULT_LANGUAGE


def role_label(login_type: Any, login_id: Any) -> str:
    """Workspace name used only for the printed counts."""
    lid = str(login_id or "").strip().upper()
    try:
        lt = int(login_type or 1)
    except (TypeError, ValueError):
        lt = 1
    if lid == str(os.getenv("DEVELOPER_WEB_LOGIN_ID") or "DEVELOPER-X-01").strip().upper():
        return "developer"
    if lid == str(os.getenv("SPEAKING_ADMIN_WEB_LOGIN_ID") or "DIAMOND-SP-1").strip().upper():
        return "speaking_admin"
    if lt == 4 and lid == "MEDIA-X-01":
        return "media"
    if lt == 4 and re.fullmatch(r"DIAMOND-LIM-\d+", lid):
        return "limited_admin"
    if lt in (1, 2):
        return "student"
    if lt == 3:
        return "support" if lid.startswith("SUP") else "teacher"
    if lt == 4:
        return "admin"
    if lt == 5:
        return "support"
    if lt == 7:
        return "speaking"
    return "other"


def chunks(items: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def speaking_device_language(row: dict[str, Any]) -> str | None:
    """Push language for a Speaking device, or None when its account is inactive."""
    if row.get("user_id") is None or row.get("account_id") is None:
        # Anonymous install, or the linked account no longer exists.
        return DEFAULT_LANGUAGE
    active = row.get("active")
    if (
        int(row.get("blocked") or 0) == 1
        or int(1 if active is None else active) != 1
        or int(row.get("screenshot_demo") or 0) == 1
        or row.get("speaking_deleted_at")
    ):
        return None
    return normalize_language(row.get("language"))


def speaking_push_data(record_id: int) -> dict[str, str]:
    """Data the Speaking app turns into its popup (title/body read from data first)."""
    return {
        "type": SPEAKING_PUSH_TYPE,
        "notification_id": str(int(record_id)),
        "title": INBOX_TITLE,
        "body": INBOX_MESSAGE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def speaking_record_is_retryable(record: dict[str, Any] | None) -> bool:
    return bool(record) and str(record.get("status") or "") == "failed" and int(record.get("recipient_count") or 0) == 0


# --------------------------------------------------------------------------
# Database reads (shared by --dry-run and --send)
# --------------------------------------------------------------------------

def load_eligible_users(cur) -> list[dict[str, Any]]:
    cur.execute(ELIGIBLE_USERS_SQL)
    users: list[dict[str, Any]] = []
    for row in cur.fetchall() or []:
        uid = int(row.get("id") or 0)
        if uid <= 0:
            continue
        users.append(
            {
                "id": uid,
                "role": role_label(row.get("login_type"), row.get("login_id")),
                "language": normalize_language(row.get("language")),
            }
        )
    return users


def load_existing_notice_user_ids(cur) -> set[int]:
    cur.execute(EXISTING_NOTICE_SQL, (SOURCE_KEY,))
    return {int(row.get("user_id") or 0) for row in (cur.fetchall() or []) if int(row.get("user_id") or 0) > 0}


def load_user_tokens(cur, user_ids: Sequence[int]) -> list[dict[str, Any]]:
    tokens: list[dict[str, Any]] = []
    for chunk in chunks(list(user_ids), TOKEN_QUERY_CHUNK):
        cur.execute(USER_TOKENS_SQL, (list(chunk),))
        for row in cur.fetchall() or []:
            token = str(row.get("token") or "").strip()
            if token:
                tokens.append(
                    {
                        "user_id": int(row.get("user_id") or 0),
                        "token": token,
                        "app": str(row.get("app") or ""),
                        "platform": str(row.get("platform") or ""),
                    }
                )
    return tokens


def load_speaking_record(cur) -> dict[str, Any] | None:
    cur.execute(SPEAKING_RECORD_SQL, (INBOX_TITLE, INBOX_MESSAGE))
    row = cur.fetchone()
    return dict(row) if row else None


def load_speaking_devices(cur) -> tuple[list[dict[str, Any]], Counter]:
    """Eligible Speaking device rows (token still encrypted) and exclusion counts."""
    cur.execute(SPEAKING_DEVICES_SQL)
    eligible: list[dict[str, Any]] = []
    counts: Counter = Counter()
    for raw in cur.fetchall() or []:
        row = dict(raw)
        counts["devices"] += 1
        language = speaking_device_language(row)
        if language is None:
            counts["excluded_inactive_account"] += 1
            continue
        counts["linked" if row.get("account_id") is not None else "anonymous"] += 1
        row["language"] = language
        eligible.append(row)
    return eligible, counts


def decrypt_speaking_tokens(rows: list[dict[str, Any]], counts: Counter) -> list[dict[str, Any]]:
    """Readable Speaking tokens; unreadable ones are counted and skipped."""
    from token_encryption import TokenCipher, TokenEncryptionConfigurationError

    try:
        cipher = TokenCipher.from_environment()
    except TokenEncryptionConfigurationError as exc:
        counts["unreadable_no_cipher"] += len(rows)
        logger.error("speaking token cipher is not configured: %s", exc)
        return []
    readable: list[dict[str, Any]] = []
    for row in rows:
        try:
            token = cipher.decrypt(str(row.get("token") or ""))
        except Exception:
            counts["unreadable_token"] += 1
            continue
        if not token:
            counts["unreadable_token"] += 1
            continue
        readable.append({"token": token, "platform": str(row.get("platform") or ""), "language": row["language"]})
    return readable


def classify_slots(rows: list[dict[str, Any]], slot_for, configured: set[str], *, app: str | None = None) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        slot = slot_for(app or row.get("app", ""), row.get("platform", ""))
        if not slot:
            counts["skipped_no_fcm_project"] += 1
        elif slot not in configured:
            counts[f"skipped_slot_not_configured:{slot}"] += 1
        else:
            counts[f"sendable:{slot}"] += 1
    return counts


# --------------------------------------------------------------------------
# FCM sending
# --------------------------------------------------------------------------

class PushSender:
    """Batched FCM sends through the Firebase apps that push_notifications initialised."""

    def __init__(self, messaging: Any, apps: dict[str, Any]) -> None:
        self.messaging = messaging
        self.apps = apps
        self.stats: Counter = Counter()
        self.errors: Counter = Counter()
        self.error_samples: list[str] = []

    def message(self, token: str, *, title: str, body: str, data: dict[str, Any]) -> Any:
        m = self.messaging
        return m.Message(
            notification=m.Notification(title=str(title)[:PUSH_TITLE_LIMIT], body=str(body)[:PUSH_BODY_LIMIT]),
            data={str(key): str(value) for key, value in data.items() if value is not None},
            token=token,
            android=m.AndroidConfig(priority="high"),
            apns=m.APNSConfig(payload=m.APNSPayload(aps=m.Aps(sound="default"))),
        )

    def _record_error(self, slot: str, exc: Any) -> None:
        key = f"{slot}:{type(exc).__name__}:{getattr(exc, 'code', '') or ''}"
        self.errors[key] += 1
        if len(self.error_samples) < ERROR_SAMPLE_LIMIT:
            self.error_samples.append(f"{key}: {str(exc)[:200]}")

    def _is_unregistered(self, exc: Any) -> bool:
        unregistered = getattr(self.messaging, "UnregisteredError", None)
        if isinstance(unregistered, type) and isinstance(exc, unregistered):
            return True
        code = str(getattr(exc, "code", "") or "").lower()
        # Never treat "invalid-argument" as a dead token here: a payload
        # problem would otherwise prune every device.
        return "unregistered" in code or "notregistered" in code

    def send(self, entries: list[tuple[str, str, Any]]) -> list[str]:
        """Send (slot, token, message) entries; return tokens FCM reports as unregistered."""
        by_slot: dict[str, list[tuple[str, Any]]] = {}
        for slot, token, message in entries:
            by_slot.setdefault(slot, []).append((token, message))
        dead: list[str] = []
        for slot, items in by_slot.items():
            app_instance = self.apps.get(slot)
            if app_instance is None:
                self.stats[f"skipped_slot_not_configured:{slot}"] += len(items)
                continue
            for chunk in chunks(items, FCM_BATCH_SIZE):
                try:
                    response = self.messaging.send_each([message for _, message in chunk], app=app_instance)
                except Exception as exc:  # network/auth failure for the whole batch
                    self.stats["failed"] += len(chunk)
                    self._record_error(slot, exc)
                    continue
                for (token, _message), result in zip(chunk, response.responses):
                    if result.success:
                        self.stats["sent"] += 1
                        continue
                    self.stats["failed"] += 1
                    self._record_error(slot, result.exception)
                    if self._is_unregistered(result.exception):
                        dead.append(token)
        return dead


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _counter_text(counter: Counter) -> str:
    return ", ".join(f"{key} {value}" for key, value in sorted(counter.items())) or "none"


def print_texts() -> None:
    print("\nTexts")
    print(f"  inbox/popup title: {INBOX_TITLE}")
    print(f"  inbox/popup message ({len(INBOX_MESSAGE)} chars):")
    for line in INBOX_MESSAGE.split("\n"):
        print(f"    | {line}")
    for language in LANGUAGES:
        text = PUSH_TEXTS[language]
        print(f"  push [{language}] {text['title']} / {text['body'][:70]}...")
    print(f"  app push data: {json.dumps(APP_PUSH_DATA, ensure_ascii=False)}")
    print(f"  speaking push data: type={SPEAKING_PUSH_TYPE}, notification_id=<record id>, title/body=popup text")


# --------------------------------------------------------------------------
# Modes
# --------------------------------------------------------------------------

def _read_only(conn, reader):
    """Run ``reader(cur)`` in its own READ ONLY transaction, then roll it back."""
    cur = conn.cursor()
    try:
        cur.execute(READ_ONLY_SQL)
        return reader(cur)
    finally:
        conn.rollback()


def run_dry_run(get_conn, push_notifications, config_module) -> int:
    print("Platform update notice: DRY RUN (nothing is written, nothing is sent)")
    print(f"source_key: {SOURCE_KEY}")
    token_error = ""
    speaking_error = ""
    speaking_record: dict[str, Any] | None = None
    speaking_rows: list[dict[str, Any]] = []
    speaking_counts: Counter = Counter()
    conn = get_conn()
    try:
        users = _read_only(conn, load_eligible_users)
        existing = _read_only(conn, load_existing_notice_user_ids)
        new_users = [user for user in users if user["id"] not in existing]
        new_ids = [user["id"] for user in new_users]
        try:
            tokens = _read_only(conn, lambda cur: load_user_tokens(cur, new_ids))
        except Exception as exc:
            tokens = []
            token_error = str(exc)
        try:
            speaking_record = _read_only(conn, load_speaking_record)
            speaking_rows, speaking_counts = _read_only(conn, load_speaking_devices)
        except Exception as exc:
            speaking_error = str(exc)
    finally:
        conn.close()

    configured = set(getattr(config_module, "FIREBASE_CREDENTIALS_BY_SLOT", {}) or {})
    slot_for = push_notifications._slot_for

    print("\n[inbox] web_payment_notifications, notification_type='broadcast'")
    print(f"  eligible users: {len(users)} ({_counter_text(Counter(user['role'] for user in users))})")
    print(f"  already have the notice: {len(existing)}")
    print(f"  would create: {len(new_users)}")
    sample = ", ".join(f"user {u['id']} {u['role']} {u['language']}" for u in new_users[:SAMPLE_SIZE])
    print(f"  sample: {sample or 'none'}")

    language_by_user = {user["id"]: user["language"] for user in new_users}
    platforms = Counter((row["app"] or "?") + "/" + (row["platform"] or "?") for row in tokens)
    languages = Counter(language_by_user.get(row["user_id"], DEFAULT_LANGUAGE) for row in tokens)
    print("\n[app push] push_device_tokens of the users above (Student/Teacher apps)")
    if token_error:
        print(f"  ERROR: push_device_tokens could not be read: {token_error}")
    print(f"  tokens: {len(tokens)} on {len({row['user_id'] for row in tokens})} users")
    print(f"  by app/platform: {_counter_text(platforms)}")
    print(f"  by language: {_counter_text(languages)}")
    print(f"  delivery: {_counter_text(classify_slots(tokens, slot_for, configured))}")

    print("\n[speaking] speaking_notifications + speaking_push_tokens (Speaking app)")
    if speaking_error:
        print(f"  ERROR: Speaking tables could not be read: {speaking_error}")
    else:
        if speaking_record and not speaking_record_is_retryable(speaking_record):
            print(
                f"  record exists: id {speaking_record.get('id')}, status {speaking_record.get('status')}, "
                f"recipients {speaking_record.get('recipient_count')} -> the Speaking push is skipped"
            )
        elif speaking_record:
            print(f"  record {speaking_record.get('id')} failed with 0 recipients -> would retry")
        else:
            print("  record: none yet -> would create one and push")
        print(f"  devices: {_counter_text(speaking_counts)}")
        print(f"  by language: {_counter_text(Counter(row['language'] for row in speaking_rows))}")
        try:
            readable = decrypt_speaking_tokens(speaking_rows, speaking_counts)
        except Exception as exc:  # token_encryption is unavailable in this environment
            print(f"  tokens could not be decrypted here: {exc}")
        else:
            unreadable = sum(value for key, value in speaking_counts.items() if key.startswith("unreadable"))
            print(f"  readable tokens: {len(readable)}, unreadable: {unreadable}")
            print(f"  delivery: {_counter_text(classify_slots(readable, slot_for, configured, app='speaking'))}")

    print(f"\nFCM credentials configured for: {', '.join(sorted(configured)) or 'none'}")
    print_texts()
    print("\nNothing was written. Run again with --send to deliver.")
    return 0


def run_send(get_conn, push_notifications) -> int:
    print("Platform update notice: SEND")
    print(f"source_key: {SOURCE_KEY}")
    conn = get_conn()
    cur = conn.cursor()
    locked = False
    try:
        cur.execute(LOCK_SQL, (SOURCE_KEY,))
        locked = bool((cur.fetchone() or {}).get("locked"))
        conn.commit()
        if not locked:
            print("ERROR: another --send run holds the lock; nothing was written.")
            return 3
        if not push_notifications.init_firebase():
            print("ERROR: no Firebase project could be initialised (FIREBASE_SERVICE_ACCOUNT_*); nothing was written.")
            return 2
        from firebase_admin import messaging

        apps = dict(push_notifications._firebase_apps)
        print(f"FCM projects ready: {', '.join(sorted(apps))}")

        inbox, app_sender = send_inbox_and_app_push(conn, cur, push_notifications, messaging, apps)
        speaking = send_speaking(conn, cur, push_notifications, messaging, apps)

        print("\nDone")
        print(f"  inbox: {_counter_text(inbox)}")
        print(f"  app push: {_counter_text(app_sender.stats)}")
        if app_sender.errors:
            print(f"  app push errors: {_counter_text(app_sender.errors)}")
            for sample in app_sender.error_samples:
                print(f"    e.g. {sample}")
        print(f"  speaking: {_counter_text(speaking)}")
        return 0
    finally:
        if locked:
            try:
                cur.execute(UNLOCK_SQL, (SOURCE_KEY,))
                conn.commit()
            except Exception:
                logger.warning("advisory unlock failed; it is released when the connection closes")
        conn.close()


def send_inbox_and_app_push(conn, cur, push_notifications, messaging, apps) -> tuple[Counter, PushSender]:
    users = load_eligible_users(cur)
    conn.commit()
    language_by_user = {user["id"]: user["language"] for user in users}
    user_ids = [user["id"] for user in users]
    inbox: Counter = Counter()
    sender = PushSender(messaging, apps)
    meta_json = json.dumps(INBOX_META, ensure_ascii=False)
    total_batches = max(1, -(-len(user_ids) // INBOX_BATCH_SIZE))
    print(f"\n[inbox + app push] {len(user_ids)} eligible users in {total_batches} batches")
    for number, batch in enumerate(chunks(user_ids, INBOX_BATCH_SIZE), start=1):
        missing: list[int] | None = None
        try:
            cur.execute(EXISTING_NOTICE_FOR_USERS_SQL, (SOURCE_KEY, list(batch)))
            existing = {int(row.get("user_id") or 0) for row in (cur.fetchall() or [])}
            missing = [uid for uid in batch if uid not in existing]
            for uid in missing:
                cur.execute(
                    INSERT_NOTICE_SQL,
                    (
                        uid,
                        NOTIFICATION_TYPE,
                        INBOX_TITLE,
                        INBOX_MESSAGE,
                        INBOX_BUTTON_TEXT,
                        INBOX_BUTTON_URL,
                        INBOX_TARGET_SCREEN,
                        SOURCE_KEY,
                        meta_json,
                    ),
                )
                cur.fetchone()
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if missing is None:
                inbox["failed"] += len(batch)
            else:
                inbox["failed"] += len(missing)
                inbox["already_had"] += len(batch) - len(missing)
            logger.error("inbox batch %s failed and was rolled back (%s); a re-run retries it", number, exc)
            continue
        created = missing
        inbox["already_had"] += len(batch) - len(created)
        inbox["created"] += len(created)

        before = Counter(sender.stats)
        if created:
            try:
                tokens = load_user_tokens(cur, created)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                tokens = []
                logger.error("device tokens for batch %s could not be read (%s)", number, exc)
            entries: list[tuple[str, str, Any]] = []
            for row in tokens:
                slot = push_notifications._slot_for(row["app"], row["platform"])
                if not slot:
                    sender.stats["skipped_no_fcm_project"] += 1
                    continue
                text = PUSH_TEXTS[language_by_user.get(row["user_id"], DEFAULT_LANGUAGE)]
                entries.append(
                    (slot, row["token"], sender.message(row["token"], title=text["title"], body=text["body"], data=APP_PUSH_DATA))
                )
            dead = sender.send(entries)
            if dead:
                push_notifications._prune_tokens(dead)
                sender.stats["pruned_unregistered"] += len(dead)
        delta = sender.stats - before
        print(
            f"  batch {number}/{total_batches}: created {len(created)}, "
            f"push sent {delta.get('sent', 0)}, failed {delta.get('failed', 0)}",
            flush=True,
        )
    return inbox, sender


def send_speaking(conn, cur, push_notifications, messaging, apps) -> Counter:
    counts: Counter = Counter()
    print("\n[speaking]")
    try:
        record = load_speaking_record(cur)
        rows, device_counts = load_speaking_devices(cur)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"  ERROR: Speaking tables could not be read ({exc}); the Speaking push was not sent.")
        counts["error"] += 1
        return counts
    counts.update(device_counts)
    if record and not speaking_record_is_retryable(record):
        print(f"  already sent (speaking_notifications id {record.get('id')}, status {record.get('status')}); skipped")
        counts["skipped_already_sent"] += 1
        return counts

    try:
        readable = decrypt_speaking_tokens(rows, counts)
    except Exception as exc:
        print(f"  ERROR: Speaking tokens could not be decrypted ({exc}); the Speaking push was not sent.")
        counts["error"] += 1
        return counts
    sender = PushSender(messaging, apps)
    targets: list[tuple[str, dict[str, Any]]] = []
    for row in readable:
        slot = push_notifications._slot_for("speaking", row["platform"])
        if not slot:
            counts["skipped_no_fcm_project"] += 1
        elif slot not in apps:
            counts[f"skipped_slot_not_configured:{slot}"] += 1
        else:
            targets.append((slot, row))
    if not targets:
        print("  no Speaking device can be reached; no record written, a later run can still send.")
        return counts

    if record:
        record_id = int(record["id"])
        cur.execute(UPDATE_SPEAKING_RECORD_SQL, (0, "sending", record_id))
    else:
        cur.execute(INSERT_SPEAKING_RECORD_SQL, (INBOX_TITLE, INBOX_MESSAGE))
        record_id = int((cur.fetchone() or {}).get("id") or 0)
    if record_id <= 0:
        conn.rollback()
        print("  ERROR: the speaking_notifications record could not be created; the Speaking push was not sent.")
        counts["error"] += 1
        return counts
    conn.commit()
    data = speaking_push_data(record_id)
    entries = [
        (
            slot,
            row["token"],
            sender.message(
                row["token"],
                title=PUSH_TEXTS[row["language"]]["title"],
                body=PUSH_TEXTS[row["language"]]["body"],
                data=data,
            ),
        )
        for slot, row in targets
    ]
    dead = sender.send(entries)
    # push_notifications never prunes Speaking tokens either; only count them.
    counts["unregistered"] += len(dead)
    counts.update(sender.stats)
    sent = int(sender.stats.get("sent", 0))
    cur.execute(UPDATE_SPEAKING_RECORD_SQL, (sent, "sent" if sent else "failed", record_id))
    conn.commit()
    if sender.errors:
        print(f"  errors: {_counter_text(sender.errors)}")
        for sample in sender.error_samples:
            print(f"    e.g. {sample}")
    print(f"  speaking_notifications id {record_id}: sent {sent}, failed {sender.stats.get('failed', 0)}")
    return counts


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print counts and a sample; write nothing (default)")
    mode.add_argument("--send", action="store_true", help="create the inbox items and send the pushes")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    # db -> config loads .env (DATABASE_URL, Firebase and encryption secrets).
    from db import get_conn
    import config
    import push_notifications

    if not args.send:
        return run_dry_run(get_conn, push_notifications, config)
    return run_send(get_conn, push_notifications)


if __name__ == "__main__":
    sys.exit(main())
