"""
Real OS-level push notifications (Firebase Cloud Messaging) for both
Flutter apps (Diamond Students + Diamond Teachers) — the piece that was
completely missing before: every notification the backend already creates
(`_payment_upsert_web_notification` rows, broadcasts, etc.) only ever
surfaced through the in-app "bell" list, which requires the app to be open
and polling. This module adds an actual FCM send alongside those existing
writes so a device gets a real system notification (like Telegram/
Instagram) even when the app is fully closed.

Multi-project design:
  Each of the 4 app+platform combinations (student/teacher x android/ios)
  was registered as its OWN separate Firebase project rather than one
  shared project — so there are 4 independent sets of credentials, not
  one. `init_firebase()` initializes up to 4 NAMED `firebase_admin` apps
  (one per slot: STUDENT_ANDROID, STUDENT_IOS, TEACHER_ANDROID,
  TEACHER_IOS), each from its own env-configured service-account. Any
  subset can be configured — an unconfigured slot is simply skipped (that
  slot's devices won't receive push, everything else keeps working).

  Every registered device token already carries `app`
  ("student"/"teacher") and `platform` ("android"/"ios"/"web") columns
  (see `register_device_token` / `POST /notifications/push-token`), so a
  send just looks up each token's own slot and uses that project's app
  instance. A `web` platform token has no matching Firebase project (there
  isn't one) and is skipped for real push — only the in-app notification
  row applies to it.

Design (unchanged from the original single-project version):
  - `init_firebase()` is called once at backend startup. It's a no-op (does
    NOT raise) when no service-account credentials are configured for ANY
    slot — the rest of the app (in-app notifications, everything else)
    keeps working exactly as before; only the OS-push side effect is
    skipped.
  - `send_push_to_user(user_id, title, body, data)` looks up every device
    token registered for that user (`push_device_tokens` table) and sends
    to all of them via each token's own project, pruning tokens FCM
    reports as unregistered/invalid so the table doesn't accumulate dead
    rows forever.
  - Sending is fire-and-forget from the caller's perspective: any failure
    is logged and swallowed, exactly like the existing `_safe_call`-wrapped
    Telegram sends elsewhere in this codebase — a push failure must never
    break the API request that triggered it.
"""
from __future__ import annotations

import json
import logging
import hmac
import threading
from typing import Any

logger = logging.getLogger(__name__)

from token_encryption import TokenCipher, TokenEncryptionConfigurationError

# One Firebase Admin `App` instance per slot — see module docstring.
_firebase_apps: dict[str, Any] = {}
_firebase_lock = threading.Lock()
_speaking_schema_lock = threading.Lock()
_speaking_routing_schema_ready = False
_init_attempted = False
# firebase-admin's HTTP session uses a small urllib3 connection pool. Several
# background notification jobs can run at once in each Uvicorn worker, so bound
# the process-wide number of synchronous sends below that pool's default size.
_FCM_SEND_SEMAPHORE = threading.BoundedSemaphore(8)

_SLOTS = ("STUDENT_ANDROID", "STUDENT_IOS", "TEACHER_ANDROID", "TEACHER_IOS", "SPEAKING_ANDROID", "SPEAKING_IOS")


def _slot_for(app: str, platform: str) -> str | None:
    app_lower = str(app or "").strip().lower()
    app_key = (
        "STUDENT"
        if app_lower == "student"
        else "TEACHER"
        if app_lower == "teacher"
        else "SPEAKING"
        if app_lower in ("speaking", "diamond_speaking", "diamondspeaking")
        else None
    )
    platform_key = "ANDROID" if str(platform or "").strip().lower() == "android" else "IOS" if str(platform or "").strip().lower() == "ios" else None
    if not app_key or not platform_key:
        return None
    return f"{app_key}_{platform_key}"


def init_firebase() -> bool:
    """
    Initializes one named Firebase Admin SDK app per configured slot
    (STUDENT_ANDROID / STUDENT_IOS / TEACHER_ANDROID / TEACHER_IOS), each
    from its own env-configured service-account credentials. Safe to call
    multiple times (idempotent) and safe to call with zero slots
    configured (returns False, logs one informational line per skipped
    slot). Returns True if at least one slot initialized successfully.
    """
    global _init_attempted
    with _firebase_lock:
        if _firebase_apps:
            return True
        if _init_attempted:
            return bool(_firebase_apps)
        _init_attempted = True
        try:
            import firebase_admin
            from firebase_admin import credentials
        except Exception:
            logger.info("push_notifications: firebase-admin not installed, push disabled")
            return False
        from config import FIREBASE_CREDENTIALS_BY_SLOT

        if not FIREBASE_CREDENTIALS_BY_SLOT:
            logger.info(
                "push_notifications: no FIREBASE_SERVICE_ACCOUNT_JSON_<SLOT>/PATH_<SLOT> configured for any slot (%s), push disabled",
                ", ".join(_SLOTS),
            )
            return False

        for slot in _SLOTS:
            slot_creds = FIREBASE_CREDENTIALS_BY_SLOT.get(slot)
            if not slot_creds:
                logger.info("push_notifications: slot=%s not configured, skipped", slot)
                continue
            cred = None
            try:
                if slot_creds.get("json"):
                    cred = credentials.Certificate(json.loads(slot_creds["json"]))
                elif slot_creds.get("path"):
                    cred = credentials.Certificate(slot_creds["path"])
            except Exception:
                logger.exception("push_notifications: failed to parse Firebase service account credentials for slot=%s", slot)
                continue
            if cred is None:
                continue
            try:
                # Each app instance needs a unique name — firebase_admin's
                # default `initialize_app()` (no name) can only be called
                # once per process, so every slot gets its own named app.
                _firebase_apps[slot] = firebase_admin.initialize_app(cred, name=f"diamond_{slot.lower()}")
                logger.info("push_notifications: Firebase Admin SDK initialized for slot=%s", slot)
            except Exception:
                logger.exception("push_notifications: Firebase Admin SDK initialization failed for slot=%s", slot)
        return bool(_firebase_apps)


def is_enabled() -> bool:
    return bool(_firebase_apps)


def _tokens_for_user(user_id: int) -> list[dict[str, str]]:
    from db import get_conn

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT token, app, platform FROM push_device_tokens WHERE user_id=?", (int(user_id),))
        return [
            {"token": str(row["token"]), "app": str(row.get("app") or ""), "platform": str(row.get("platform") or "")}
            for row in (cur.fetchall() or [])
            if row.get("token")
        ]
    finally:
        conn.close()


def _prune_tokens(tokens: list[str]) -> None:
    if not tokens:
        return
    from db import get_conn

    conn = get_conn()
    cur = conn.cursor()
    try:
        for token in tokens:
            cur.execute("DELETE FROM push_device_tokens WHERE token=?", (token,))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def send_push_to_user(
    user_id: int,
    title: str,
    body: str,
    *,
    data: dict[str, Any] | None = None,
) -> None:
    """
    Best-effort: sends an FCM notification to every device this user has
    registered, routing each device to its own Firebase project based on
    the `app`/`platform` recorded for that token. Never raises — any error
    (missing credentials, network failure, all tokens dead) is logged and
    swallowed so this can safely be called inline from any existing
    notification-creation code path.
    """
    if not is_enabled():
        return
    uid = int(user_id or 0)
    if uid <= 0:
        return
    try:
        rows = _tokens_for_user(uid)
    except Exception:
        logger.exception("push_notifications: failed to load device tokens for user_id=%s", uid)
        return
    if not rows:
        return
    _send_to_token_rows(rows, title, body, data or {})


def send_push_to_users(
    user_ids: list[int],
    title: str,
    body: str,
    *,
    data: dict[str, Any] | None = None,
) -> None:
    """Same as `send_push_to_user` but for a batch of recipients (broadcasts)."""
    if not is_enabled():
        return
    from db import get_conn

    ids = [int(u) for u in (user_ids or []) if int(u or 0) > 0]
    if not ids:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholders = ",".join("?" for _ in ids)
        cur.execute(f"SELECT token, app, platform FROM push_device_tokens WHERE user_id IN ({placeholders})", tuple(ids))
        rows = [
            {"token": str(row["token"]), "app": str(row.get("app") or ""), "platform": str(row.get("platform") or "")}
            for row in (cur.fetchall() or [])
            if row.get("token")
        ]
    except Exception:
        logger.exception("push_notifications: failed to load device tokens for batch send")
        return
    finally:
        conn.close()
    if not rows:
        return
    _send_to_token_rows(rows, title, body, data or {})


def _send_to_token_rows(rows: list[dict[str, str]], title: str, body: str, data: dict[str, Any]) -> None:
    """Groups tokens by their resolved Firebase slot (each slot = one
    project = one `firebase_admin` app instance) and sends per-slot, since
    the `firebase_admin.messaging` API sends against a specific app."""
    by_slot: dict[str, list[str]] = {}
    for row in rows:
        slot = _slot_for(row.get("app", ""), row.get("platform", ""))
        if not slot or slot not in _firebase_apps:
            continue  # unconfigured slot (or a "web" platform token, which has no FCM project) — skipped
        by_slot.setdefault(slot, []).append(row["token"])
    for slot, tokens in by_slot.items():
        _send_to_tokens(tokens, title, body, data, slot=slot)


def _is_dead_fcm_token_error(exc: Exception) -> bool:
    code = str(getattr(exc, "code", "") or "").strip().lower()
    message_text = str(exc).strip().lower()
    error_text = f"{code} {message_text}"
    if (
        "unregistered" in error_text
        or "notregistered" in error_text
        or "registration-token-not-registered" in error_text
    ):
        return True
    return (
        "invalid-argument" in error_text
        and "registration token" in error_text
        and ("not valid" in error_text or "invalid" in error_text)
    )


def _send_to_tokens(tokens: list[str], title: str, body: str, data: dict[str, Any], *, slot: str) -> None:
    try:
        from firebase_admin import messaging
    except Exception:
        return
    app_instance = _firebase_apps.get(slot)
    if app_instance is None:
        return
    # FCM's payload `data` values must all be strings.
    str_data = {str(k): str(v) for k, v in (data or {}).items() if v is not None}
    dead_tokens: list[str] = []
    failed_codes: dict[str, int] = {}
    try:
        for token in tokens:
            message = messaging.Message(
                notification=messaging.Notification(title=str(title or "")[:180], body=str(body or "")[:500]),
                data=str_data,
                token=token,
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))),
            )
            try:
                with _FCM_SEND_SEMAPHORE:
                    messaging.send(message, app=app_instance)
            except Exception as exc:
                code = str(getattr(exc, "code", "") or "").strip().lower()
                # Firebase's legacy adapter sometimes exposes NotRegistered in
                # the message but not in `exc.code`. Do not treat every
                # INVALID_ARGUMENT as a dead token: that can also mean a bad
                # payload and would otherwise prune valid devices.
                if _is_dead_fcm_token_error(exc):
                    dead_tokens.append(token)
                else:
                    safe_code = code.split("/")[-1] if code else type(exc).__name__
                    failed_codes[safe_code[:80]] = failed_codes.get(safe_code[:80], 0) + 1
    except Exception:
        logger.exception("push_notifications: unexpected error while sending (slot=%s)", slot)
    if dead_tokens:
        _prune_tokens(dead_tokens)
        logger.info(
            "push_notifications: pruned stale device tokens slot=%s count=%s",
            slot,
            len(dead_tokens),
        )
    if failed_codes:
        logger.warning(
            "push_notifications: batch send failures slot=%s count=%s codes=%s",
            slot,
            sum(failed_codes.values()),
            failed_codes,
        )


def register_device_token(user_id: int, token: str, *, platform: str = "", app: str = "teacher") -> None:
    """
    Upserts one device's FCM token for `user_id`. A single physical device
    can only ever point at one user at a time — logging out and a
    different teacher logging in on the same phone must not leave the
    previous account still receiving that device's pushes — so any other
    user_id currently holding this exact token is cleared first.
    """
    from db import get_conn

    tok = str(token or "").strip()
    if not tok or int(user_id or 0) <= 0:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM push_device_tokens WHERE token=? AND user_id<>?", (tok, int(user_id)))
        cur.execute(
            """
            INSERT INTO push_device_tokens (user_id, token, platform, app, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(token) DO UPDATE SET
                user_id=excluded.user_id,
                platform=excluded.platform,
                app=excluded.app,
                updated_at=CURRENT_TIMESTAMP
            """,
            (int(user_id), tok, str(platform or "")[:20], str(app or "teacher")[:30]),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("push_notifications: failed to register device token for user_id=%s", user_id)
    finally:
        conn.close()


def unregister_device_token(token: str) -> None:
    """Called on logout so a signed-out device stops receiving pushes for
    that account immediately, rather than waiting for FCM to report it as
    unregistered (which only happens after a failed send)."""
    from db import get_conn

    tok = str(token or "").strip()
    if not tok:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM push_device_tokens WHERE token=?", (tok,))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _speaking_token_update_allowed(existing_user: int | None, incoming_user: int | None, existing_token: str, incoming_token: str) -> bool:
    """A bound device may rotate for its owner, or transfer only with token proof."""
    if existing_user is None:
        return True
    if incoming_user is not None and int(existing_user) == int(incoming_user):
        return True
    return bool(existing_token) and hmac.compare_digest(existing_token, incoming_token)


def speaking_push_route_product(user_id: int | None, signed_product: str, claimed_product: str) -> str | None:
    """Choose a routing label; authenticated sessions override client claims."""
    value = signed_product if user_id else claimed_product
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"english", "russian"} else None


def _ensure_speaking_routing_schema(cur: Any, conn: Any) -> None:
    global _speaking_routing_schema_ready
    if _speaking_routing_schema_ready:
        return
    with _speaking_schema_lock:
        if _speaking_routing_schema_ready:
            return
        cur.execute("ALTER TABLE speaking_push_tokens ADD COLUMN IF NOT EXISTS product_code TEXT")
        conn.commit()
        _speaking_routing_schema_ready = True


def register_speaking_token(device_id: str, token: str, *, platform: str = "android", user_id: int | None = None, product_code: str | None = None) -> None:
    """Registers an anonymous device token for Diamond Speaking Questions."""
    from db import get_conn

    dev_id = str(device_id or "").strip()[:80]
    tok = str(token or "").strip()
    plat = str(platform or "android").strip()[:20]
    if not tok:
        return
    try:
        cipher = TokenCipher.from_environment()
    except TokenEncryptionConfigurationError:
        logger.error("push_notifications: speaking token encryption is not configured")
        raise
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_push_tokens (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL UNIQUE,
                token TEXT NOT NULL,
                platform TEXT,
                user_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "ALTER TABLE speaking_push_tokens ADD COLUMN IF NOT EXISTS user_id BIGINT"
        )
        _ensure_speaking_routing_schema(cur, conn)
        _encrypt_legacy_speaking_tokens(cur, conn, cipher)
        dev_id = dev_id or f"dev_{hash(tok)}"
        uid = int(user_id) if user_id else None
        product = product_code if product_code in {"english", "russian"} else None
        encrypted = cipher.encrypt(tok)
        # Serialize claims for an existing installation. The insert handles
        # concurrent first registrations; the loser locks and checks ownership.
        cur.execute(
            """INSERT INTO speaking_push_tokens (device_id, token, platform, user_id, product_code, updated_at)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(device_id) DO NOTHING RETURNING id""",
            (dev_id, encrypted, plat, uid, product),
        )
        if not cur.fetchone():
            cur.execute("SELECT token, user_id FROM speaking_push_tokens WHERE device_id=? FOR UPDATE", (dev_id,))
            existing = cur.fetchone()
            if existing:
                try:
                    previous_token = cipher.decrypt(str(existing.get("token") or ""))
                except Exception:
                    previous_token = ""
                if _speaking_token_update_allowed(existing.get("user_id"), uid, previous_token, tok):
                    cur.execute(
                        "UPDATE speaking_push_tokens SET token=?, platform=?, user_id=?, product_code=COALESCE(?, product_code), updated_at=CURRENT_TIMESTAMP WHERE device_id=?",
                        (encrypted, plat, uid, product, dev_id),
                    )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("push_notifications: failed to register speaking token")
    finally:
        conn.close()


def _encrypt_legacy_speaking_tokens(cur: Any, conn: Any, cipher: TokenCipher) -> None:
    """Migrates old clear-text FCM rows before any new token is persisted."""
    cur.execute("SELECT id, token FROM speaking_push_tokens")
    legacy_rows = [
        row for row in (cur.fetchall() or [])
        if str(row.get("token") or "") and not str(row.get("token") or "").startswith("enc:v1:")
    ]
    for row in legacy_rows:
        cur.execute(
            "UPDATE speaking_push_tokens SET token=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (cipher.encrypt(str(row["token"])), int(row["id"])),
        )
    if legacy_rows:
        conn.commit()
        logger.info("push_notifications: migrated %s legacy speaking push token(s) to encrypted storage", len(legacy_rows))


def _speaking_product_matches(stored: str | None, requested: str | None) -> bool:
    """Shared notifications reach all; targeted ones require a known match."""
    return requested is None or stored == requested


def _speaking_competition_product(data: dict[str, Any] | None) -> str | None:
    """Competition events with a known subject target that product only."""
    values = data or {}
    kind = str(values.get("notification_type") or "").lower()
    subject = str(values.get("subject") or "").strip().lower()
    if kind.startswith(("competition_", "duel_")) and subject in {"english", "russian"}:
        return subject
    return None


def send_push_to_speaking_devices(
    title: str,
    body: str,
    *,
    data: dict[str, Any] | None = None,
    product_code: str | None = None,
) -> int:
    """Send to registered devices, using the public topic only as a fallback.

    Sending to both destinations duplicates every broadcast for registered app
    installs because those devices subscribe to ``speaking_all`` as well.
    """
    from db import get_conn

    init_firebase()
    try:
        cipher = TokenCipher.from_environment()
    except TokenEncryptionConfigurationError:
        logger.error("push_notifications: speaking token encryption is not configured")
        return 0
    conn = get_conn()
    cur = conn.cursor()
    token_rows: list[dict[str, str]] = []
    try:
        _encrypt_legacy_speaking_tokens(cur, conn, cipher)
        _ensure_speaking_routing_schema(cur, conn)
        cur.execute("SELECT token, platform, product_code FROM speaking_push_tokens")
        for row in (cur.fetchall() or []):
            if not _speaking_product_matches(row.get("product_code"), product_code):
                continue
            encrypted_token = str(row.get("token") or "")
            if not encrypted_token:
                continue
            try:
                token = cipher.decrypt(encrypted_token)
            except Exception:
                logger.warning("push_notifications: skipped an unreadable encrypted speaking token")
                continue
            if token:
                token_rows.append({"token": token, "platform": str(row.get("platform") or "android"), "app": "speaking"})
    except Exception:
        logger.info("push_notifications: speaking_push_tokens table not yet present or query error")
    finally:
        conn.close()

    if token_rows:
        _send_to_token_rows(token_rows, title, body, data or {})
        return len(token_rows)

    speaking_app = _firebase_apps.get("SPEAKING_ANDROID") or _firebase_apps.get("SPEAKING_IOS")
    if not speaking_app and _firebase_apps:
        speaking_app = next(iter(_firebase_apps.values()))

    if speaking_app:
        try:
            from firebase_admin import messaging
            str_data = {str(k): str(v) for k, v in (data or {}).items() if v is not None}
            msg = messaging.Message(
                notification=messaging.Notification(title=str(title or "")[:180], body=str(body or "")[:500]),
                data=str_data,
                topic=f"speaking_{product_code}" if product_code in {"english", "russian"} else "speaking_all",
                android=messaging.AndroidConfig(priority="high"),
                apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))),
            )
            messaging.send(msg, app=speaking_app)
            logger.info("push_notifications: topic 'speaking_all' message broadcasted successfully")
        except Exception as e:
            logger.warning("push_notifications: topic broadcast failed: %s", e)

        return 1
    return 0


def send_push_to_speaking_user(
    user_id: int,
    title: str,
    body: str,
    *,
    data: dict[str, Any] | None = None,
    product_code: str | None = None,
) -> int:
    """Send a private speaking-chat push only to the recipient's linked devices."""
    from db import get_conn

    uid = int(user_id or 0)
    if uid <= 0:
        return 0
    product_code = product_code or _speaking_competition_product(data)
    init_firebase()
    if not is_enabled():
        return 0
    try:
        cipher = TokenCipher.from_environment()
    except TokenEncryptionConfigurationError:
        logger.error("push_notifications: speaking token encryption is not configured")
        return 0
    conn = get_conn()
    cur = conn.cursor()
    token_rows: list[dict[str, str]] = []
    try:
        _ensure_speaking_routing_schema(cur, conn)
        cur.execute("SELECT token, platform, product_code FROM speaking_push_tokens WHERE user_id=?", (uid,))
        for row in cur.fetchall() or []:
            if not _speaking_product_matches(row.get("product_code"), product_code):
                continue
            encrypted_token = str(row.get("token") or "")
            if not encrypted_token:
                continue
            try:
                token = cipher.decrypt(encrypted_token)
            except Exception:
                logger.warning("push_notifications: skipped an unreadable encrypted speaking token")
                continue
            if token:
                token_rows.append({"token": token, "platform": str(row.get("platform") or "android"), "app": "speaking"})
    except Exception:
        logger.exception("push_notifications: failed to load speaking devices for user_id=%s", uid)
    finally:
        conn.close()
    if token_rows:
        _send_to_token_rows(token_rows, title, body, data or {})
    return len(token_rows)


def send_push_to_speaking_users(
    user_ids: list[int],
    title: str,
    body: str,
    *,
    data: dict[str, Any] | None = None,
    product_code: str | None = None,
) -> int:
    """Send chat pushes to selected Speaking accounts without broadcasting to a topic."""
    from db import get_conn

    ids = list(dict.fromkeys(int(uid) for uid in (user_ids or []) if int(uid or 0) > 0))
    if not ids:
        return 0
    product_code = product_code or _speaking_competition_product(data)
    init_firebase()
    if not is_enabled():
        return 0
    try:
        cipher = TokenCipher.from_environment()
    except TokenEncryptionConfigurationError:
        logger.error("push_notifications: speaking token encryption is not configured")
        return 0
    conn = get_conn()
    cur = conn.cursor()
    token_rows: list[dict[str, str]] = []
    try:
        placeholders = ",".join("?" for _ in ids)
        _ensure_speaking_routing_schema(cur, conn)
        cur.execute(f"SELECT token, platform, product_code FROM speaking_push_tokens WHERE user_id IN ({placeholders})", tuple(ids))
        for row in cur.fetchall() or []:
            if not _speaking_product_matches(row.get("product_code"), product_code):
                continue
            try:
                token = cipher.decrypt(str(row.get("token") or ""))
            except Exception:
                logger.warning("push_notifications: skipped an unreadable encrypted speaking token")
                continue
            if token:
                token_rows.append({"token": token, "platform": str(row.get("platform") or "android"), "app": "speaking"})
    except Exception:
        logger.exception("push_notifications: failed to load speaking devices for batch push")
    finally:
        conn.close()
    if token_rows:
        _send_to_token_rows(token_rows, title, body, data or {})
    return len(token_rows)

