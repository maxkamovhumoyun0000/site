"""Authenticated LiveKit tokens and lobby state for Diamond Speaking video rooms.

This module deliberately keeps media traffic out of the web backend.  The
backend owns authentication, room membership and short-lived tokens; LiveKit
is the SFU that transports camera/microphone streams.  It is safe to deploy
before LiveKit itself: clients receive a clear 503 until the server variables
are configured, and no API secret is ever returned to a client.
"""
from __future__ import annotations

import os
import re
import secrets
import json
from urllib import error as urlerror
from urllib import request as urlrequest
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_conn


router = APIRouter()

# A room can contain up to 1,000 signed-in listeners.  The mobile client is a
# stage UI: it only renders/subscribes to the small visible set of cameras, so
# a room does not attempt to render one thousand video tiles on every device.
MAX_ROOM_PARTICIPANTS = 1000
TOKEN_LIFETIME_SECONDS = 10 * 60
PRESENCE_TTL_SECONDS = 90
ROOM_LIFETIME_HOURS = 8
_ROOM_ID_RE = re.compile(r"^spk-live-[a-z0-9]{10,40}$")


class LiveVideoRoomCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=90)
    subject: str = Field(default="english", min_length=2, max_length=20)


def _main_helpers():
    # Late import avoids an import cycle: main includes this router.
    from backend.main import _display_name, _require_role, _user_row_from_bearer
    return _display_name, _require_role, _user_row_from_bearer


def _require_user(authorization: str | None) -> dict[str, Any]:
    _, require_role, user_from_bearer = _main_helpers()
    user = user_from_bearer(authorization)
    require_role(user, {"student", "teacher", "support", "admin", "developer"})
    if int(user.get("blocked") or 0) == 1 or int(user.get("access_enabled", 1) or 0) != 1:
        raise HTTPException(status_code=403, detail="Live video is not available for this account")
    return user


def _require_staff(authorization: str | None) -> dict[str, Any]:
    _, require_role, user_from_bearer = _main_helpers()
    user = user_from_bearer(authorization)
    require_role(user, {"admin", "superadmin", "developer", "media", "media_admin", "speaking_admin"})
    return user


def _livekit_config() -> tuple[str, str, str]:
    url = str(os.getenv("LIVEKIT_URL") or "").strip().rstrip("/")
    api_key = str(os.getenv("LIVEKIT_API_KEY") or "").strip()
    api_secret = str(os.getenv("LIVEKIT_API_SECRET") or "").strip()
    if not (url.startswith(("wss://", "ws://")) and api_key and api_secret):
        raise HTTPException(status_code=503, detail="Live video is being prepared. Please try again shortly.")
    return url, api_key, api_secret


def _livekit_control_url(public_url: str) -> str:
    """Return the server-only LiveKit HTTP control endpoint.

    The public websocket endpoint is intentionally separate from the control
    endpoint.  In production this must normally be localhost, so an API key
    and secret never travel through the public reverse proxy.
    """
    configured = str(os.getenv("LIVEKIT_INTERNAL_URL") or "").strip().rstrip("/")
    if configured:
        if not configured.startswith(("http://", "https://")):
            raise HTTPException(status_code=503, detail="Live video is being prepared. Please try again shortly.")
        return configured
    if public_url.startswith("wss://"):
        return "https://" + public_url.removeprefix("wss://")
    if public_url.startswith("ws://"):
        return "http://" + public_url.removeprefix("ws://")
    raise HTTPException(status_code=503, detail="Live video is being prepared. Please try again shortly.")


def _livekit_control_token(api_key: str, api_secret: str) -> str:
    now = _now()
    return jwt.encode(
        {
            "iss": api_key,
            "nbf": int(now.timestamp()) - 5,
            "exp": int((now + timedelta(seconds=60)).timestamp()),
            "video": {"roomCreate": True, "roomList": True, "roomAdmin": True},
        },
        api_secret,
        algorithm="HS256",
    )


def _livekit_room_request(
    action: str,
    payload: dict[str, Any],
    *,
    ignore_exists: bool = False,
    ignore_not_found: bool = False,
) -> None:
    """Call the LiveKit RoomService without exposing its control credentials."""
    public_url, api_key, api_secret = _livekit_config()
    endpoint = f"{_livekit_control_url(public_url)}/twirp/livekit.RoomService/{action}"
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urlrequest.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_livekit_control_token(api_key, api_secret)}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=6):
            return
    except urlerror.HTTPError as exc:
        # CreateRoom is idempotent for this use: a room can already exist if
        # the backend restarted between its database write and the request.
        if ignore_exists and exc.code in {400, 409}:
            return
        # Deleting a room is also idempotent.  LiveKit can have already
        # removed an empty room or restarted after the application persisted
        # its lobby row; that must not prevent the host from ending the room.
        if ignore_not_found and exc.code == 404:
            return
    except (OSError, ValueError):
        pass
    raise HTTPException(status_code=503, detail="Live video is temporarily unavailable. Please try again shortly.")


def _ensure_livekit_room(room_id: str) -> None:
    _livekit_room_request(
        "CreateRoom",
        {
            "name": room_id,
            "empty_timeout": ROOM_LIFETIME_HOURS * 60 * 60,
            "departure_timeout": 120,
            "max_participants": MAX_ROOM_PARTICIPANTS,
        },
        ignore_exists=True,
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _safe_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _subject(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"english", "ielts", "eng"}:
        return "english"
    if normalized in {"russian", "russian-speaking", "rus", "ru"}:
        return "russian"
    raise HTTPException(status_code=422, detail="Subject must be english or russian")


def _room_id(value: str) -> str:
    room_id = str(value or "").strip().lower()
    if not _ROOM_ID_RE.fullmatch(room_id):
        raise HTTPException(status_code=404, detail="Live video room was not found")
    return room_id


def ensure_live_video_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_live_video_rooms (
                id TEXT PRIMARY KEY,
                host_user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                subject TEXT NOT NULL DEFAULT 'english',
                max_participants INTEGER NOT NULL DEFAULT 1000,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_live_video_presences (
                room_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                identity TEXT NOT NULL,
                display_name TEXT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                left_at TIMESTAMP,
                PRIMARY KEY (room_id, user_id)
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_live_video_rooms_active ON speaking_live_video_rooms(status, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_live_video_presences_active ON speaking_live_video_presences(room_id, last_seen_at)"
        )
        # Upgrade older pilot rows.  The product policy is now 1,000 signed-in
        # listeners per room; this is a capacity limit, not a promise that a
        # single device will render a thousand video streams.
        cur.execute(
            "UPDATE speaking_live_video_rooms SET max_participants=? WHERE max_participants<?",
            (MAX_ROOM_PARTICIPANTS, MAX_ROOM_PARTICIPANTS),
        )
        conn.commit()
    except Exception:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()


def _active_presence_count(cur: Any, room_id: str, now: datetime) -> int:
    cutoff = _iso(now - timedelta(seconds=PRESENCE_TTL_SECONDS))
    cur.execute(
        """
        SELECT COUNT(*) AS total FROM speaking_live_video_presences
        WHERE room_id=? AND left_at IS NULL AND last_seen_at>=?
        """,
        (room_id, cutoff),
    )
    row = cur.fetchone() or {}
    return int(dict(row).get("total") or 0)


def _serialize_room(row: dict[str, Any], participants: int) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "title": str(row.get("title") or "Live speaking room"),
        "subject": str(row.get("subject") or "english"),
        "host_user_id": int(row.get("host_user_id") or 0),
        "max_participants": min(MAX_ROOM_PARTICIPANTS, max(1, int(row.get("max_participants") or MAX_ROOM_PARTICIPANTS))),
        "participant_count": max(0, int(participants)),
        "created_at": row.get("created_at"),
    }


def _active_room_or_error(cur: Any, room_id: str) -> dict[str, Any]:
    cur.execute("SELECT * FROM speaking_live_video_rooms WHERE id=?", (room_id,))
    raw = cur.fetchone()
    if not raw:
        raise HTTPException(status_code=404, detail="Live video room was not found")
    room = dict(raw)
    if str(room.get("status") or "").lower() != "active":
        raise HTTPException(status_code=410, detail="This live video room has ended")
    created = _safe_datetime(room.get("created_at"))
    if created and created < _now() - timedelta(hours=ROOM_LIFETIME_HOURS):
        cur.execute("UPDATE speaking_live_video_rooms SET status='ended', ended_at=?, last_activity_at=? WHERE id=?", (_iso(), _iso(), room_id))
        raise HTTPException(status_code=410, detail="This live video room has ended")
    return room


@router.get("/api/speaking/live-video/rooms")
async def list_live_video_rooms(authorization: str | None = Header(default=None)):
    _require_user(authorization)
    ensure_live_video_schema()
    now = _now()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE speaking_live_video_rooms
            SET status='ended', ended_at=?, last_activity_at=?
            WHERE status='active' AND created_at<?
            """,
            (_iso(now), _iso(now), _iso(now - timedelta(hours=ROOM_LIFETIME_HOURS))),
        )
        cur.execute(
            """
            SELECT * FROM speaking_live_video_rooms
            WHERE status='active'
            ORDER BY created_at DESC
            LIMIT 200
            """
        )
        rows = [dict(row) for row in (cur.fetchall() or [])]
        rooms = [_serialize_room(row, _active_presence_count(cur, str(row["id"]), now)) for row in rows]
        conn.commit()
        return {"rooms": rooms, "max_participants_per_room": MAX_ROOM_PARTICIPANTS}
    finally:
        conn.close()


@router.post("/api/speaking/live-video/rooms")
async def create_live_video_room(
    payload: LiveVideoRoomCreateRequest,
    authorization: str | None = Header(default=None),
):
    user = _require_user(authorization)
    ensure_live_video_schema()
    title = " ".join(payload.title.split())
    if len(title) < 3:
        raise HTTPException(status_code=422, detail="Room title is required")
    subject = _subject(payload.subject)
    room_id = f"spk-live-{secrets.token_urlsafe(12).lower().replace('_', 'a').replace('-', 'b')}"
    room_id = room_id[:40]
    # Fail before persisting lobby state if the SFU is not configured.  This
    # prevents a ghost "active" room which mobile clients could never join.
    _ensure_livekit_room(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM speaking_live_video_rooms
            WHERE host_user_id=? AND status='active' AND created_at>=?
            LIMIT 1
            """,
            (int(user.get("id") or 0), _iso(_now() - timedelta(hours=ROOM_LIFETIME_HOURS))),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Finish your current live video room before creating a new one")
        cur.execute(
            """
            INSERT INTO speaking_live_video_rooms
            (id, host_user_id, title, subject, max_participants, status, created_at, last_activity_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (room_id, int(user.get("id") or 0), title, subject, MAX_ROOM_PARTICIPANTS, _iso(), _iso()),
        )
        conn.commit()
    finally:
        conn.close()
    return {
        "room": {
            "id": room_id,
            "title": title,
            "subject": subject,
            "host_user_id": int(user.get("id") or 0),
            "max_participants": MAX_ROOM_PARTICIPANTS,
            "participant_count": 0,
        }
    }


@router.post("/api/speaking/live-video/rooms/{room_id}/token")
async def live_video_room_token(room_id: str, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ensure_live_video_schema()
    url, api_key, api_secret = _livekit_config()
    room_id = _room_id(room_id)
    user_id = int(user.get("id") or 0)
    identity = f"speaking-{user_id}"
    display_name, _, _ = _main_helpers()
    name = " ".join(str(display_name(user)).split())[:80] or "Diamond learner"
    now = _now()
    conn = get_conn()
    cur = conn.cursor()
    try:
        # The room row is locked while a new presence is reserved.  This makes
        # the 1,000-seat limit authoritative even when several join requests hit
        # at exactly the same moment.
        try:
            cur.execute("SELECT * FROM speaking_live_video_rooms WHERE id=? FOR UPDATE", (room_id,))
            locked = cur.fetchone()
            if not locked:
                raise HTTPException(status_code=404, detail="Live video room was not found")
            room = dict(locked)
            if str(room.get("status") or "").lower() != "active":
                raise HTTPException(status_code=410, detail="This live video room has ended")
        except HTTPException:
            raise
        except Exception:
            with suppress(Exception):
                conn.rollback()
            cur = conn.cursor()
            room = _active_room_or_error(cur, room_id)

        if _safe_datetime(room.get("created_at")) and _safe_datetime(room.get("created_at")) < now - timedelta(hours=ROOM_LIFETIME_HOURS):
            cur.execute("UPDATE speaking_live_video_rooms SET status='ended', ended_at=?, last_activity_at=? WHERE id=?", (_iso(now), _iso(now), room_id))
            raise HTTPException(status_code=410, detail="This live video room has ended")

        # Rooms made by an earlier application deployment are upgraded lazily
        # before the signed participant token is issued.
        _ensure_livekit_room(room_id)

        cur.execute("SELECT user_id FROM speaking_live_video_presences WHERE room_id=? AND user_id=?", (room_id, user_id))
        own = cur.fetchone()
        if not own:
            max_participants = min(MAX_ROOM_PARTICIPANTS, max(1, int(room.get("max_participants") or MAX_ROOM_PARTICIPANTS)))
            if _active_presence_count(cur, room_id, now) >= max_participants:
                raise HTTPException(status_code=409, detail=f"This live video room is full ({max_participants} participants)")
            cur.execute(
                """
                INSERT INTO speaking_live_video_presences(room_id,user_id,identity,display_name,joined_at,last_seen_at,left_at)
                VALUES (?,?,?,?,?,?,NULL)
                """,
                (room_id, user_id, identity, name, _iso(now), _iso(now)),
            )
        else:
            cur.execute("UPDATE speaking_live_video_presences SET identity=?, display_name=?, last_seen_at=?, left_at=NULL WHERE room_id=? AND user_id=?", (identity, name, _iso(now), room_id, user_id))
        cur.execute("UPDATE speaking_live_video_rooms SET last_activity_at=? WHERE id=?", (_iso(now), room_id))
        conn.commit()
        room_count = _active_presence_count(cur, room_id, now)
    except HTTPException:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()

    is_host = int(room.get("host_user_id") or 0) == user_id
    claims = {
        "iss": api_key,
        "sub": identity,
        "name": name,
        "nbf": int(now.timestamp()) - 5,
        "exp": int((now + timedelta(seconds=TOKEN_LIFETIME_SECONDS)).timestamp()),
        "video": {
            "roomJoin": True,
            "room": room_id,
            "canPublish": True,
            "canSubscribe": True,
            "canPublishData": True,
            "roomAdmin": is_host,
        },
    }
    token = jwt.encode(claims, api_secret, algorithm="HS256")
    return {
        "url": url,
        "token": token,
        "room": _serialize_room(room, room_count),
        "is_host": is_host,
        "expires_in_seconds": TOKEN_LIFETIME_SECONDS,
    }


@router.post("/api/speaking/live-video/rooms/{room_id}/heartbeat")
async def live_video_room_heartbeat(room_id: str, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        room = _active_room_or_error(cur, room_id)
        user_id = int(user.get("id") or 0)
        cur.execute("UPDATE speaking_live_video_presences SET last_seen_at=?, left_at=NULL WHERE room_id=? AND user_id=?", (_iso(), room_id, user_id))
        if int(cur.rowcount or 0) != 1:
            raise HTTPException(status_code=403, detail="Join the live video room first")
        cur.execute("UPDATE speaking_live_video_rooms SET last_activity_at=? WHERE id=?", (_iso(), room_id))
        count = _active_presence_count(cur, room_id, _now())
        conn.commit()
        return {"room": _serialize_room(room, count)}
    except HTTPException:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/api/speaking/live-video/rooms/{room_id}/leave")
async def leave_live_video_room(room_id: str, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_live_video_presences SET left_at=?, last_seen_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL", (_iso(), _iso(), room_id, int(user.get("id") or 0)))
        conn.commit()
    finally:
        conn.close()
    # Leaving is per participant.  Deleting the SFU room here would disconnect
    # every other learner whenever one person presses the normal leave button.
    # Only the host-only end endpoint below may close a room for everybody.
    return {"ok": True}


@router.post("/api/speaking/live-video/rooms/{room_id}/end")
async def end_live_video_room(room_id: str, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        room = _active_room_or_error(cur, room_id)
        if int(room.get("host_user_id") or 0) != int(user.get("id") or 0):
            raise HTTPException(status_code=403, detail="Only the host can end this live video room")
        # Block new application joins before the SFU is closed.  This avoids a
        # token request recreating the room in the small interval around
        # DeleteRoom, while still allowing us to roll back cleanly if the SFU
        # cannot be reached.
        cur.execute(
            "UPDATE speaking_live_video_rooms SET status='ending', last_activity_at=? WHERE id=?",
            (_iso(), room_id),
        )
        conn.commit()
    except HTTPException:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()
    try:
        _livekit_room_request(
            "DeleteRoom",
            {"room": room_id},
            ignore_not_found=True,
        )
    except HTTPException:
        # A failed delete remains retryable: restore the active lobby instead
        # of reporting a false successful end or orphaning the room forever.
        restore_conn = get_conn()
        restore_cur = restore_conn.cursor()
        try:
            restore_cur.execute(
                "UPDATE speaking_live_video_rooms SET status='active', last_activity_at=? WHERE id=? AND status='ending'",
                (_iso(), room_id),
            )
            restore_conn.commit()
        finally:
            restore_conn.close()
        raise

    finish_conn = get_conn()
    finish_cur = finish_conn.cursor()
    try:
        finish_cur.execute(
            "UPDATE speaking_live_video_rooms SET status='ended', ended_at=?, last_activity_at=? WHERE id=? AND status='ending'",
            (_iso(), _iso(), room_id),
        )
        finish_cur.execute(
            "UPDATE speaking_live_video_presences SET left_at=?, last_seen_at=? WHERE room_id=? AND left_at IS NULL",
            (_iso(), _iso(), room_id),
        )
        finish_conn.commit()
    finally:
        finish_conn.close()
    return {"ok": True}


@router.get("/staff/speaking/live-video/rooms")
async def staff_list_live_video_rooms(authorization: str | None = Header(default=None)):
    _require_staff(authorization)
    ensure_live_video_schema()
    now = _now()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_live_video_rooms ORDER BY created_at DESC LIMIT 200")
        rows = [dict(row) for row in (cur.fetchall() or [])]
        return {"rooms": [_serialize_room(row, _active_presence_count(cur, str(row["id"]), now)) for row in rows]}
    finally:
        conn.close()
