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
import threading
from typing import Any

logger = logging.getLogger(__name__)

# One Firebase Admin `App` instance per slot — see module docstring.
_firebase_apps: dict[str, Any] = {}
_firebase_lock = threading.Lock()
_init_attempted = False

_SLOTS = ("STUDENT_ANDROID", "STUDENT_IOS", "TEACHER_ANDROID", "TEACHER_IOS")


def _slot_for(app: str, platform: str) -> str | None:
    app_key = "STUDENT" if str(app or "").strip().lower() == "student" else "TEACHER" if str(app or "").strip().lower() == "teacher" else None
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
                messaging.send(message, app=app_instance)
            except Exception as exc:
                code = str(getattr(exc, "code", "") or "").lower()
                if "unregistered" in code or "not-registered" in code or "invalid-argument" in code:
                    dead_tokens.append(token)
                else:
                    logger.warning("push_notifications: send failed for a token (slot=%s): %s", slot, exc)
    except Exception:
        logger.exception("push_notifications: unexpected error while sending (slot=%s)", slot)
    if dead_tokens:
        _prune_tokens(dead_tokens)


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
