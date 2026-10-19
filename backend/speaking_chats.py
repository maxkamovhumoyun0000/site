"""Private student-to-student chat APIs for Diamond Speaking."""
from __future__ import annotations

import json
import threading
import asyncio
from typing import Any
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse

from backend.community_safety import validate_public_text
from db import get_conn
from speaking_contract import is_speaking_app_account

router = APIRouter()
_schema_ready = False
_schema_lock = threading.Lock()


class DirectChatCreateRequest(BaseModel):
    target_login_id: str = Field(min_length=3, max_length=64)


class DirectChatMessageRequest(BaseModel):
    message: str = Field(default="", max_length=3000)
    attachments: list[dict[str, str]] = Field(default_factory=list, max_length=5)


def _main_helpers():
    # Late import avoids a cycle: main imports this router at application setup.
    from backend.main import _display_name, _user_row_from_bearer

    return _display_name, _user_row_from_bearer


def _mutually_blocked_ids(user_id: int) -> set[int]:
    from backend.main import community_safety

    return community_safety.blocked_ids(int(user_id), either_direction=True)


def _ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        conn = get_conn()
        cur = conn.cursor()
        try:
            table_candidates = [
                """CREATE TABLE IF NOT EXISTS speaking_direct_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_low_id INTEGER NOT NULL,
                    user_high_id INTEGER NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_message_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_low_id, user_high_id)
                )""",
                """CREATE TABLE IF NOT EXISTS speaking_direct_chats (
                    id BIGSERIAL PRIMARY KEY,
                    user_low_id BIGINT NOT NULL,
                    user_high_id BIGINT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_message_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_low_id, user_high_id)
                )""",
            ]
            table_created = False
            for ddl in table_candidates:
                try:
                    cur.execute(ddl)
                    conn.commit()
                    table_created = True
                    break
                except Exception:
                    conn.rollback()
            if not table_created:
                raise RuntimeError("Could not create speaking_direct_chats table")
            message_candidates = [
                """CREATE TABLE IF NOT EXISTS speaking_direct_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    delivered_at TIMESTAMP,
                    read_at TIMESTAMP
                )""",
                """CREATE TABLE IF NOT EXISTS speaking_direct_messages (
                    id BIGSERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    sender_id BIGINT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    delivered_at TIMESTAMP,
                    read_at TIMESTAMP
                )""",
            ]
            messages_created = False
            for ddl in message_candidates:
                try:
                    cur.execute(ddl)
                    conn.commit()
                    messages_created = True
                    break
                except Exception:
                    conn.rollback()
            if not messages_created:
                raise RuntimeError("Could not create speaking_direct_messages table")
            try:
                cur.execute(
                    "ALTER TABLE speaking_direct_messages ADD COLUMN attachments_json TEXT NOT NULL DEFAULT '[]'"
                )
                conn.commit()
            except Exception:
                # Existing installations already have the migration applied.
                conn.rollback()
            for column in ("delivered_at", "read_at"):
                try:
                    cur.execute(f"ALTER TABLE speaking_direct_messages ADD COLUMN {column} TIMESTAMP")
                    conn.commit()
                except Exception:
                    conn.rollback()
            try:
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_speaking_direct_messages_chat ON speaking_direct_messages(chat_id, id)"
                )
                conn.commit()
            except Exception:
                conn.rollback()
            _schema_ready = True
        finally:
            conn.close()


def _require_speaking_user(authorization: str | None) -> dict[str, Any]:
    _, user_from_bearer = _main_helpers()
    user = user_from_bearer(authorization)
    if not is_speaking_app_account(user.get("speaking_app_account")):
        raise HTTPException(status_code=403, detail="Speaking app account required")
    if user.get("speaking_deleted_at"):
        raise HTTPException(status_code=403, detail="Speaking account is inactive")
    if int(user.get("blocked") or 0) == 1 or int(user.get("access_enabled", 1) or 0) != 1:
        raise HTTPException(status_code=403, detail="Speaking account is unavailable")
    return user


def _active_speaking_user(user_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, login_id, first_name, last_name, profile_image_url, role,
                      last_activity, last_login_at,
                      speaking_app_account, speaking_deleted_at, blocked, access_enabled
               FROM users WHERE id=? LIMIT 1""",
            (int(user_id),),
        )
        row = dict(cur.fetchone() or {})
        if (
            not row
            or not (
                is_speaking_app_account(row.get("speaking_app_account"))
                or str(row.get("role") or "").strip().lower() in {"student", "teacher", "admin", "superadmin", "developer", "speaking_admin"}
            )
            or row.get("speaking_deleted_at")
            or int(row.get("blocked") or 0) == 1
            or int(row.get("access_enabled", 1) or 0) != 1
        ):
            return None
        return row
    finally:
        conn.close()


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    display_name, _ = _main_helpers()
    role = str(row.get("role") or "speaking_user").strip().lower()
    if role in {"superadmin", "developer", "speaking_admin"}:
        public_role = "admin"
    elif role in {"student", "teacher", "admin"}:
        public_role = role
    else:
        public_role = "student" if is_speaking_app_account(row.get("speaking_app_account")) else role
    return {
        "id": int(row.get("id") or 0),
        "login_id": str(row.get("login_id") or ""),
        "full_name": display_name(row),
        "avatar_url": str(row.get("profile_image_url") or "").strip() or None,
        "last_active": row.get("last_activity") or row.get("last_login_at"),
        "role": public_role,
        "roles": [public_role],
    }


def _chat_for_user(chat_id: int, user_id: int) -> dict[str, Any]:
    _ensure_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT * FROM speaking_direct_chats
               WHERE id=? AND (user_low_id=? OR user_high_id=?) LIMIT 1""",
            (int(chat_id), int(user_id), int(user_id)),
        )
        row = dict(cur.fetchone() or {})
        if not row:
            raise HTTPException(status_code=404, detail="Speaking chat not found")
        other_id = int(row.get("user_high_id") if int(row.get("user_low_id") or 0) == user_id else row.get("user_low_id") or 0)
    finally:
        conn.close()
    if other_id in _mutually_blocked_ids(user_id):
        raise HTTPException(status_code=403, detail="This speaking chat is unavailable")
    other = _active_speaking_user(other_id)
    if not other:
        raise HTTPException(status_code=404, detail="Speaking user not found")
    return {**row, "other_user": _public_user(other)}


def _open_speaking_chat_with_user(target_user_id: int, user: dict[str, Any]) -> dict[str, Any]:
    """Find or atomically create a private conversation with an active user."""
    _ensure_schema()
    uid = int(user.get("id") or 0)
    target = _active_speaking_user(int(target_user_id))
    if not target or int(target.get("id") or 0) == uid:
        raise HTTPException(status_code=404, detail="Speaking user not found")
    if int(target_user_id) in _mutually_blocked_ids(uid):
        raise HTTPException(status_code=403, detail="This speaking chat is unavailable")
    low, high = sorted((uid, int(target_user_id)))
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO speaking_direct_chats(user_low_id,user_high_id) VALUES (?,?) ON CONFLICT(user_low_id,user_high_id) DO NOTHING",
            (low, high),
        )
        conn.commit()
        cur.execute("SELECT id FROM speaking_direct_chats WHERE user_low_id=? AND user_high_id=? LIMIT 1", (low, high))
        chat_id = int(dict(cur.fetchone() or {}).get("id") or 0)
        if chat_id <= 0:
            raise HTTPException(status_code=500, detail="Could not open speaking chat")
        return {"id": chat_id, "other_user": _public_user(target)}
    finally:
        conn.close()


@router.get("/speaking/chat/users")
@router.get("/api/speaking/chat/users")
@router.get("/api/speaking/chats/contacts")
async def search_speaking_chat_users(
    query: str = Query(min_length=3, max_length=64),
    authorization: str | None = Header(default=None),
):
    user = _require_speaking_user(authorization)
    normalized = query.strip().lstrip("@").lower()
    if len(normalized) < 3:
        raise HTTPException(status_code=422, detail="Enter at least three characters")
    blocked_ids = _mutually_blocked_ids(int(user.get("id") or 0))
    escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, login_id, first_name, last_name, profile_image_url, role, speaking_app_account, last_activity, last_login_at
               FROM users
               WHERE (COALESCE(speaking_app_account, 0)=1 OR LOWER(COALESCE(role,'')) IN ('student','teacher','admin','superadmin','developer','speaking_admin'))
                 AND COALESCE(CAST(speaking_deleted_at AS TEXT),'')=''
                 AND COALESCE(blocked, 0)=0
                 AND COALESCE(access_enabled, 1)=1
                 AND id<>?
                 AND (LOWER(COALESCE(login_id,'')) LIKE ? ESCAPE '\\'
                      OR LOWER(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) LIKE ? ESCAPE '\\')
               ORDER BY LOWER(COALESCE(first_name,'')), LOWER(COALESCE(last_name,'')), LOWER(COALESCE(login_id,'')) LIMIT 30""",
            (int(user.get("id") or 0), f"%{escaped}%", f"%{escaped}%"),
        )
        items = [
            _public_user(dict(row))
            for row in cur.fetchall() or []
            if int(dict(row).get("id") or 0) not in blocked_ids
        ]
        return {"items": items}
    finally:
        conn.close()


@router.get("/speaking/chats")
@router.get("/api/speaking/chats")
@router.get("/api/speaking/chats/direct")
async def list_speaking_direct_chats(authorization: str | None = Header(default=None)):
    user = _require_speaking_user(authorization)
    _ensure_schema()
    uid = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT * FROM speaking_direct_chats
               WHERE user_low_id=? OR user_high_id=?
               ORDER BY last_message_at DESC, id DESC LIMIT 100""",
            (uid, uid),
        )
        chats = [dict(row) for row in cur.fetchall() or []]
        items = []
        for chat in chats:
            other_id = int(chat.get("user_high_id") if int(chat.get("user_low_id") or 0) == uid else chat.get("user_low_id") or 0)
            other = _active_speaking_user(other_id)
            if not other:
                continue
            cur.execute(
            "SELECT message, created_at, attachments_json FROM speaking_direct_messages WHERE chat_id=? ORDER BY id DESC LIMIT 1",
                (int(chat.get("id") or 0),),
            )
            latest = dict(cur.fetchone() or {})
            items.append({
                "id": int(chat.get("id") or 0),
                "other_user": _public_user(other),
                "last_message": str(latest.get("message") or ("🎙️ Voice message" if latest.get("attachments_json") else "")),
                "last_time": latest.get("created_at") or chat.get("last_message_at"),
            })
        return {"items": items}
    finally:
        conn.close()


@router.post("/speaking/chats")
@router.post("/api/speaking/chats")
async def open_speaking_direct_chat(
    payload: DirectChatCreateRequest,
    authorization: str | None = Header(default=None),
):
    user = _require_speaking_user(authorization)
    _ensure_schema()
    login_id = payload.target_login_id.strip().lstrip("@").lower()
    uid = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, login_id, first_name, last_name, profile_image_url,
                      speaking_app_account, speaking_deleted_at, blocked, access_enabled
               FROM users WHERE LOWER(login_id)=? LIMIT 1""",
            (login_id,),
        )
        target = dict(cur.fetchone() or {})
        if not target or int(target.get("id") or 0) == uid:
            raise HTTPException(status_code=404, detail="Speaking user not found")
        target_id = int(target.get("id") or 0)
    finally:
        conn.close()
    return {"chat": _open_speaking_chat_with_user(target_id, user)}


@router.get("/api/speaking/chats/direct/{target_user_id}")
async def get_or_open_speaking_direct_chat_by_user_id(
    target_user_id: int,
    after_id: int | None = Query(default=None, ge=0),
    authorization: str | None = Header(default=None),
):
    user = _require_speaking_user(authorization)
    chat = _open_speaking_chat_with_user(target_user_id, user)
    result = await get_speaking_direct_messages(int(chat["id"]), after_id=after_id, authorization=authorization)
    result["chat"] = chat
    return result


@router.post("/api/speaking/chats/direct/{target_user_id}")
async def send_speaking_direct_chat_by_user_id(
    target_user_id: int,
    payload: DirectChatMessageRequest,
    authorization: str | None = Header(default=None),
):
    user = _require_speaking_user(authorization)
    chat = _open_speaking_chat_with_user(target_user_id, user)
    result = await send_speaking_direct_message(int(chat["id"]), payload, authorization=authorization)
    return {**result, "chat": chat}


class SpeakingCommunityMessageRequest(BaseModel):
    message: str = Field(default="", max_length=4000)
    reply_to_id: int | None = Field(default=None, ge=1)
    reply_to_message_id: int | None = Field(default=None, ge=1)
    client_message_id: str | None = Field(default=None, min_length=3, max_length=120)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=5)


@router.get("/api/speaking/chats/community")
async def get_speaking_community_chat(
    after_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=50),
    authorization: str | None = Header(default=None),
):
    from backend.main import community_chat_messages

    return await community_chat_messages(after_id=after_id, limit=limit, channel="speaking", authorization=authorization)


@router.post("/api/speaking/chats/community")
async def send_speaking_community_chat(
    payload: SpeakingCommunityMessageRequest,
    authorization: str | None = Header(default=None),
):
    from backend.main import CommunityChatAttachmentRequest, CommunityChatMessageRequest, community_chat_send_message

    request_payload = CommunityChatMessageRequest(
        message=payload.message,
        reply_to_message_id=payload.reply_to_message_id,
        reply_to_id=payload.reply_to_id,
        client_message_id=payload.client_message_id,
        attachments=[CommunityChatAttachmentRequest(url=str(item.get("url") or "")) for item in payload.attachments],
        channel="speaking",
    )
    return await community_chat_send_message(request_payload, authorization=authorization)


@router.get("/api/speaking/chats/community/events")
async def speaking_community_chat_events(
    request: Request,
    after_id: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
):
    from backend.main import community_chat_events

    return await community_chat_events(request=request, channel="speaking", after_id=after_id, authorization=authorization)


@router.get("/speaking/chats/{chat_id}/messages")
@router.get("/api/speaking/chats/{chat_id}/messages")
async def get_speaking_direct_messages(
    chat_id: int,
    after_id: int | None = Query(default=None, ge=0),
    authorization: str | None = Header(default=None),
):
    user = _require_speaking_user(authorization)
    chat = _chat_for_user(chat_id, int(user.get("id") or 0))
    conn = get_conn()
    cur = conn.cursor()
    try:
        if after_id is None:
            cur.execute(
                """SELECT m.id,m.message,m.attachments_json,m.sender_id,m.created_at,m.delivered_at,m.read_at,u.login_id,u.first_name,u.last_name,u.profile_image_url
                   FROM speaking_direct_messages m JOIN users u ON u.id=m.sender_id
                   WHERE m.chat_id=? ORDER BY m.id DESC LIMIT 150""",
                (int(chat_id),),
            )
            rows = [dict(row) for row in cur.fetchall() or []]
            rows.reverse()
        else:
            cur.execute(
                """SELECT m.id,m.message,m.attachments_json,m.sender_id,m.created_at,m.delivered_at,m.read_at,u.login_id,u.first_name,u.last_name,u.profile_image_url
                   FROM speaking_direct_messages m JOIN users u ON u.id=m.sender_id
                   WHERE m.chat_id=? AND m.id>? ORDER BY m.id ASC LIMIT 150""",
                (int(chat_id), int(after_id)),
            )
            rows = [dict(row) for row in cur.fetchall() or []]
        incoming_ids = [int(row.get("id") or 0) for row in rows if int(row.get("sender_id") or 0) != int(user.get("id") or 0)]
        if incoming_ids:
            newest_incoming = max(incoming_ids)
            cur.execute(
                "UPDATE speaking_direct_messages SET delivered_at=CURRENT_TIMESTAMP WHERE chat_id=? AND sender_id<>? AND id<=? AND delivered_at IS NULL",
                (int(chat_id), int(user.get("id") or 0), newest_incoming),
            )
            conn.commit()
            for row in rows:
                if int(row.get("id") or 0) in incoming_ids and not row.get("delivered_at"):
                    row["delivered_at"] = datetime.utcnow().isoformat()
        items = []
        for row in rows:
            author_row = {**row, "id": row.get("sender_id")}
            author = _public_user(author_row)
            try:
                attachments = json.loads(row.get("attachments_json") or "[]")
            except (TypeError, ValueError):
                attachments = []
            items.append({
                "id": int(row.get("id") or 0),
                "message": str(row.get("message") or ""),
                "sender_id": int(row.get("sender_id") or 0),
                "is_mine": int(row.get("sender_id") or 0) == int(user.get("id") or 0),
                "created_at": row.get("created_at"),
                "status": "seen" if int(row.get("sender_id") or 0) == int(user.get("id") or 0) and row.get("read_at") else ("delivered" if row.get("delivered_at") else "sent"),
                "author": author,
                "attachments": attachments if isinstance(attachments, list) else [],
            })
        return {"chat": chat, "items": items}
    finally:
        conn.close()


class DirectChatReadRequest(BaseModel):
    last_message_id: int | None = Field(default=None, ge=1)


@router.post("/speaking/chats/{chat_id}/read")
@router.post("/api/speaking/chats/{chat_id}/read")
async def mark_speaking_direct_messages_read(
    chat_id: int,
    payload: DirectChatReadRequest | None = None,
    authorization: str | None = Header(default=None),
):
    user = _require_speaking_user(authorization)
    _chat_for_user(chat_id, int(user.get("id") or 0))
    conn = get_conn()
    cur = conn.cursor()
    try:
        target_id = int(payload.last_message_id or 0) if payload else 0
        if target_id <= 0:
            cur.execute("SELECT id FROM speaking_direct_messages WHERE chat_id=? ORDER BY id DESC LIMIT 1", (int(chat_id),))
            target_id = int(dict(cur.fetchone() or {}).get("id") or 0)
        cur.execute(
            "UPDATE speaking_direct_messages SET read_at=CURRENT_TIMESTAMP, delivered_at=COALESCE(delivered_at,CURRENT_TIMESTAMP) WHERE chat_id=? AND sender_id<>? AND id<=? AND read_at IS NULL",
            (int(chat_id), int(user.get("id") or 0), target_id),
        )
        conn.commit()
        return {"ok": True, "last_read_message_id": target_id}
    except Exception:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Could not update read state")
    finally:
        conn.close()


def _speaking_chat_sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


@router.get("/speaking/chats/{chat_id}/events")
@router.get("/api/speaking/chats/{chat_id}/events")
async def speaking_direct_chat_events(
    chat_id: int,
    request: Request,
    after_id: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
):
    """SSE delivery for new messages and sent/delivered/seen receipts."""
    user = _require_speaking_user(authorization)
    uid = int(user.get("id") or 0)
    _chat_for_user(chat_id, uid)

    async def events():
        cursor = int(after_id)
        previous_statuses = ""
        yield ": connected\n\n"
        while not await request.is_disconnected():
            result = await get_speaking_direct_messages(
                chat_id, after_id=cursor, authorization=authorization,
            )
            items = result.get("items") or []
            for item in items:
                cursor = max(cursor, int(item.get("id") or 0))
                yield _speaking_chat_sse("message", item)

            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT id,delivered_at,read_at FROM speaking_direct_messages WHERE chat_id=? AND sender_id=? ORDER BY id DESC LIMIT 100",
                    (int(chat_id), uid),
                )
                statuses = [
                    {
                        "id": int(dict(row).get("id") or 0),
                        "status": "seen" if dict(row).get("read_at") else "delivered" if dict(row).get("delivered_at") else "sent",
                    }
                    for row in cur.fetchall() or []
                ]
            finally:
                conn.close()
            blob = json.dumps(statuses, separators=(",", ":"), sort_keys=True)
            if statuses and blob != previous_statuses:
                previous_statuses = blob
                yield _speaking_chat_sse("status", {"chat_id": int(chat_id), "items": statuses})
            if not items:
                yield ": keepalive\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "Connection": "keep-alive", "X-Accel-Buffering": "no",
    })


@router.post("/speaking/chats/{chat_id}/messages")
@router.post("/api/speaking/chats/{chat_id}/messages")
async def send_speaking_direct_message(
    chat_id: int,
    payload: DirectChatMessageRequest,
    authorization: str | None = Header(default=None),
):
    user = _require_speaking_user(authorization)
    uid = int(user.get("id") or 0)
    chat = _chat_for_user(chat_id, uid)
    try:
        message = validate_public_text(payload.message.strip())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Message could not be sent") from exc
    if len(payload.attachments) > 5:
        raise HTTPException(status_code=422, detail="At most 5 attachments can be sent")
    if not message and not payload.attachments:
        raise HTTPException(status_code=422, detail="Message or voice attachment is required")
    try:
        from backend.main import CommunityChatAttachmentRequest, _validate_community_chat_attachments

        attachments = _validate_community_chat_attachments([
            CommunityChatAttachmentRequest(url=item.get("url", ""))
            for item in payload.attachments
        ])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Attachment validation failed") from exc
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO speaking_direct_messages(chat_id,sender_id,message,attachments_json) VALUES (?,?,?,?) RETURNING id,created_at",
            (int(chat_id), uid, message, json.dumps(attachments, ensure_ascii=False)),
        )
        created = dict(cur.fetchone() or {})
        cur.execute(
            "UPDATE speaking_direct_chats SET last_message_at=? WHERE id=?",
            (created.get("created_at"), int(chat_id)),
        )
        conn.commit()
        other_user_id = int((chat.get("other_user") or {}).get("id") or 0)
        preview = message or ("🎙️ Voice message" if attachments else "📎 Attachment")
        if other_user_id > 0:
            title = f"{_public_user(user).get('full_name') or 'New message'} · Diamond Speaking"
            data = {
                "target_screen": "speaking_direct_chat",
                "notification_type": "speaking_direct_chat",
                "chat_id": str(int(chat_id)),
                "message_id": str(int(created.get("id") or 0)),
            }
            try:
                import push_notifications

                threading.Thread(
                    target=push_notifications.send_push_to_speaking_user,
                    args=(other_user_id, title, preview[:140]),
                    kwargs={"data": data},
                    daemon=True,
                ).start()
                threading.Thread(
                    target=push_notifications.send_push_to_user,
                    args=(other_user_id, title, preview[:140]),
                    kwargs={"data": data},
                    daemon=True,
                ).start()
            except Exception:
                # Chat delivery must succeed even when optional push is unavailable.
                pass
        return {"item": {"id": int(created.get("id") or 0), "message": message, "sender_id": uid, "is_mine": True, "created_at": created.get("created_at"), "author": _public_user(user), "attachments": attachments, "status": "sent"}}
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Message could not be saved") from exc
    finally:
        conn.close()
