"""Authenticated LiveKit tokens and lobby state for Diamond Speaking video rooms.

This module deliberately keeps media traffic out of the web backend.  The
backend owns authentication, room membership and short-lived tokens; LiveKit
is the SFU that transports camera/microphone streams.  It is safe to deploy
before LiveKit itself: clients receive a clear 503 until the server variables
are configured, and no API secret is ever returned to a client.
"""
from __future__ import annotations

import os
import asyncio
import logging
import re
import secrets
import json
import base64
from functools import lru_cache
from urllib import error as urlerror
from urllib import request as urlrequest
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import APIRouter, Body, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_conn


router = APIRouter()
logger = logging.getLogger(__name__)

# A room can contain up to 1,000 signed-in listeners.  The mobile client is a
# stage UI: it only renders/subscribes to the small visible set of cameras, so
# a room does not attempt to render one thousand video tiles on every device.
MAX_ROOM_PARTICIPANTS = 1000
TOKEN_LIFETIME_SECONDS = 10 * 60
PRESENCE_TTL_SECONDS = 90
ROOM_LIFETIME_HOURS = 8
_ROOM_ID_RE = re.compile(r"^spk-live-(?:[a-z0-9]{10,40}|lesson-[0-9]{1,18})$")


class LiveVideoRoomCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=90)
    subject: str = Field(default="english", min_length=2, max_length=20)


class LiveVideoRemoveParticipantRequest(BaseModel):
    identity: str = Field(min_length=1, max_length=128)


class LiveVideoMuteTrackRequest(BaseModel):
    identity: str = Field(min_length=1, max_length=128)
    track_sid: str = Field(min_length=1, max_length=128)
    muted: bool


class LiveVideoModeratorTokenRequest(BaseModel):
    session_id: str = Field(default="", max_length=40)
    device_name: str = Field(default="", max_length=40)


class LiveVideoMediaPermissionRequest(BaseModel):
    media_kind: str = Field(min_length=3, max_length=16)


class LiveVideoMediaPermissionDecision(BaseModel):
    user_id: int = Field(gt=0)
    media_kind: str = Field(min_length=3, max_length=16)
    approved: bool


class LiveVideoMessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class LiveVideoHandRequest(BaseModel):
    raised: bool


class LiveVideoDirectActionRequest(BaseModel):
    identity: str = Field(min_length=1, max_length=128)


class LiveVideoStatePatch(BaseModel):
    primary_identity: str | None = Field(default=None, max_length=128)
    primary_source: str | None = Field(default=None, max_length=20)
    announcement: str | None = Field(default=None, max_length=500)
    cue_card_title: str | None = Field(default=None, max_length=240)
    cue_card_prompts: list[str] | None = None
    cue_card_started_at: str | None = Field(default=None, max_length=50)
    cue_card_duration_seconds: int | None = Field(default=None, ge=0, le=600)
    cue_card_visible: bool | None = None
    board_text: str | None = Field(default=None, max_length=4000)
    board_visible: bool | None = None
    locked: bool | None = None


def _main_helpers():
    # Late import avoids an import cycle: main includes this router.
    from backend.main import _display_name, _require_role, _user_row_from_bearer
    return _display_name, _require_role, _user_row_from_bearer


def _require_user(authorization: str | None) -> dict[str, Any]:
    _, require_role, user_from_bearer = _main_helpers()
    user = user_from_bearer(authorization)
    # Staff identities may use participant endpoints too; moderator-only
    # controls are issued separately by staff-authenticated endpoints.
    require_role(user, {"speaking_user", "student", "teacher", "support", "admin", "superadmin", "developer", "media", "speaking_admin"})
    if int(user.get("blocked") or 0) == 1 or int(user.get("access_enabled", 1) or 0) != 1:
        raise HTTPException(status_code=403, detail="Live video is not available for this account")
    return user


def _require_staff(authorization: str | None) -> dict[str, Any]:
    _, require_role, user_from_bearer = _main_helpers()
    user = user_from_bearer(authorization)
    require_role(user, {"admin", "superadmin", "developer", "speaking_admin"})
    return user


def _require_active_staff(authorization: str | None) -> dict[str, Any]:
    user = _require_staff(authorization)
    if int(user.get("blocked") or 0) == 1 or int(user.get("access_enabled", 1) or 0) != 1:
        raise HTTPException(status_code=403, detail="Live video is not available for this account")
    return user


def _livekit_config() -> tuple[str, str, str]:
    url = str(os.getenv("LIVEKIT_URL") or "").strip().rstrip("/")
    api_key = str(os.getenv("LIVEKIT_API_KEY") or "").strip()
    api_secret = str(os.getenv("LIVEKIT_API_SECRET") or "").strip()
    if not (url.startswith(("wss://", "ws://")) and api_key and api_secret):
        # This is an expected configuration state, not an unexpected backend
        # crash. The UI maps this safe detail to a localized setup message.
        raise HTTPException(status_code=503, detail="Live video service is not configured yet.")
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


def _livekit_control_token(api_key: str, api_secret: str, room: str = "") -> str:
    now = _now()
    grants: dict[str, Any] = {"roomCreate": True, "roomList": True, "roomAdmin": True}
    # LiveKit requires roomAdmin grants to name the target room. A global
    # admin flag without `room` can create rooms but receives 401 for metadata,
    # participant and track operations.
    if room:
        grants["room"] = room
    return jwt.encode(
        {
            "iss": api_key,
            "nbf": int(now.timestamp()) - 5,
            "exp": int((now + timedelta(seconds=60)).timestamp()),
            "video": grants,
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
) -> dict[str, Any]:
    """Call the LiveKit RoomService without exposing its control credentials."""
    public_url, api_key, api_secret = _livekit_config()
    endpoint = f"{_livekit_control_url(public_url)}/twirp/livekit.RoomService/{action}"
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urlrequest.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_livekit_control_token(api_key, api_secret, str(payload.get('room') or ''))}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=6) as response:
            body = response.read()
            if not body:
                return {}
            try:
                payload = json.loads(body.decode("utf-8"))
                return payload if isinstance(payload, dict) else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
    except urlerror.HTTPError as exc:
        # CreateRoom is idempotent for this use: a room can already exist if
        # the backend restarted between its database write and the request.
        if ignore_exists and exc.code in {400, 409}:
            return {}
        # Deleting a room is also idempotent.  LiveKit can have already
        # removed an empty room or restarted after the application persisted
        # its lobby row; that must not prevent the host from ending the room.
        if ignore_not_found and exc.code == 404:
            return {}
    except (OSError, ValueError):
        pass
    raise HTTPException(status_code=503, detail="Live video is temporarily unavailable. Please try again shortly.")


def _ensure_livekit_room(room_id: str, metadata: str = "{}") -> None:
    _livekit_room_request(
        "CreateRoom",
        {
            "name": room_id,
            "emptyTimeout": ROOM_LIFETIME_HOURS * 60 * 60,
            "departureTimeout": 120,
            "maxParticipants": MAX_ROOM_PARTICIPANTS,
            "metadata": metadata,
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
    if normalized in {"english", "ielts", "eng", "english / ielts", "english/ielts"}:
        return "english"
    if normalized in {"cefr", "english / cefr", "english/cefr"}:
        return "cefr"
    if normalized in {"russian", "russian-speaking", "rus", "ru"}:
        return "russian"
    raise HTTPException(status_code=422, detail="Subject must be english, russian or cefr")


def _room_id(value: str) -> str:
    room_id = str(value or "").strip().lower()
    if not _ROOM_ID_RE.fullmatch(room_id):
        raise HTTPException(status_code=404, detail="Live video room was not found")
    return room_id


@lru_cache(maxsize=1)
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
                last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                room_state TEXT NOT NULL DEFAULT '{}',
                locked BOOLEAN NOT NULL DEFAULT FALSE
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
            """
            CREATE TABLE IF NOT EXISTS speaking_live_video_media_permissions (
                room_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                media_kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                decided_at TIMESTAMP,
                decided_by INTEGER,
                PRIMARY KEY (room_id, user_id, media_kind)
            )
            """
        )
        cur.execute("ALTER TABLE speaking_live_video_rooms ADD COLUMN IF NOT EXISTS room_state TEXT NOT NULL DEFAULT '{}'")
        cur.execute("ALTER TABLE speaking_live_video_rooms ADD COLUMN IF NOT EXISTS locked BOOLEAN NOT NULL DEFAULT FALSE")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_live_video_messages (
                id BIGSERIAL PRIMARY KEY,
                room_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                is_moderator BOOLEAN NOT NULL DEFAULT FALSE,
                text TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_live_video_hands (
                room_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                display_name TEXT NOT NULL,
                raised BOOLEAN NOT NULL DEFAULT FALSE,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_live_video_media_permissions_pending ON speaking_live_video_media_permissions(room_id, status, requested_at)"
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_live_video_messages_room ON speaking_live_video_messages(room_id, id DESC)")
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
        "status": str(row.get("status") or ""),
        "max_participants": min(MAX_ROOM_PARTICIPANTS, max(1, int(row.get("max_participants") or MAX_ROOM_PARTICIPANTS))),
        "participant_count": max(0, int(participants)),
        "created_at": row.get("created_at"),
        "locked": bool(row.get("locked")),
    }


def _room_state(row: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(str(row.get("room_state") or "{}"))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _broadcast_room_event(room_id: str, event: dict[str, Any], destination: list[str] | None = None) -> None:
    encoded = base64.b64encode(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).decode("ascii")
    _livekit_room_request(
        "SendData",
        {
            "room": room_id,
            "data": encoded,
            "kind": "RELIABLE",
            "destinationIdentities": destination or [],
            "topic": "diamond.speaking.live",
        },
    )


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


def _media_kind(value: str) -> str:
    kind = str(value or "").strip().lower()
    if kind not in {"camera", "microphone"}:
        raise HTTPException(status_code=422, detail="Media kind must be camera or microphone")
    return kind


def _participant_publish_sources(cur: Any, room_id: str, user_id: int) -> list[str]:
    cur.execute(
        "SELECT media_kind FROM speaking_live_video_media_permissions WHERE room_id=? AND user_id=? AND status='approved'",
        (room_id, user_id),
    )
    values = {str(dict(row).get("media_kind") or "").lower() for row in (cur.fetchall() or [])}
    # Screen share has its own explicit OS confirmation and remains available
    # to learners. Camera and microphone require moderator approval.
    return ["SCREEN_SHARE", *[source for source in ("MICROPHONE", "CAMERA") if source.lower() in values]]


def _sync_livekit_publish_permissions(room_id: str, identity: str, sources: list[str]) -> None:
    """Apply per-source approval to an already-connected LiveKit participant."""
    participants = _livekit_room_request("ListParticipants", {"room": room_id}).get("participants", [])
    if not any(str(row.get("identity") or "") == identity for row in participants if isinstance(row, dict)):
        # A grant is persisted even if the learner is temporarily disconnected;
        # the next join token will contain the approved source list.
        return
    _livekit_room_request(
        "UpdateParticipant",
        {
            "room": room_id,
            "identity": identity,
            "permission": {
                "canSubscribe": True,
                "canPublish": bool(sources),
                "canPublishData": True,
                "canPublishSources": sources,
            },
        },
    )


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
    # Room creation is a web staff action. The Speaking app is a participant
    # client and must only join an already-created room.
    user = _require_staff(authorization)
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
    publish_sources: list[str] = []
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
        if bool(room.get("locked")):
            cur.execute(
                "SELECT 1 FROM speaking_live_video_presences WHERE room_id=? AND user_id=? AND left_at IS NULL AND last_seen_at>=?",
                (room_id, user_id, _iso(now - timedelta(seconds=PRESENCE_TTL_SECONDS))),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=423, detail="This live video room is locked by the moderator")
        _ensure_livekit_room(room_id, str(room.get("room_state") or "{}"))

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
        publish_sources = _participant_publish_sources(cur, room_id, user_id)
        conn.commit()
        room_count = _active_presence_count(cur, room_id, now)
    except HTTPException:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()

    claims = {
        "iss": api_key,
        "sub": identity,
        "name": name,
        "nbf": int(now.timestamp()) - 5,
        "exp": int((now + timedelta(seconds=TOKEN_LIFETIME_SECONDS)).timestamp()),
        "video": {
            "roomJoin": True,
            "room": room_id,
            # Learners join as listeners. Each source remains server-denied
            # until a moderator approves its separate request.
            "canPublish": bool(publish_sources),
            "canPublishSources": publish_sources,
            "canSubscribe": True,
            "canPublishData": True,
            "roomAdmin": False,
        },
    }
    token = jwt.encode(claims, api_secret, algorithm="HS256")
    return {
        "url": url,
        "token": token,
        "room": _serialize_room(room, room_count),
        "room_state": _room_state(room),
        # Mobile participants never receive LiveKit room-admin privileges.
        "is_host": False,
        "expires_in_seconds": TOKEN_LIFETIME_SECONDS,
    }


@router.post("/staff/speaking/live-video/rooms/{room_id}/moderator-token")
async def staff_live_video_moderator_token(
    room_id: str,
    payload: LiveVideoModeratorTokenRequest | None = Body(default=None),
    authorization: str | None = Header(default=None),
):
    user = _require_active_staff(authorization)
    ensure_live_video_schema()
    url, api_key, api_secret = _livekit_config()
    room_id = _room_id(room_id)
    user_id = int(user.get("id") or 0)
    session_id = str(payload.session_id if payload else "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", session_id):
        session_id = secrets.token_hex(8)
    identity = f"speaking-admin-{user_id}-{session_id}"
    display_name, _, _ = _main_helpers()
    name = " ".join(str(display_name(user)).split())[:80] or "Speaking moderator"
    device_name = " ".join(str(payload.device_name if payload else "").split())[:40]
    if device_name:
        name = f"{name} · {device_name}"[:120]
    now = _now()
    conn = get_conn()
    cur = conn.cursor()
    try:
        room = _active_room_or_error(cur, room_id)
        cur.execute("SELECT user_id FROM speaking_live_video_presences WHERE room_id=? AND user_id=?", (room_id, user_id))
        if cur.fetchone():
            cur.execute(
                "UPDATE speaking_live_video_presences SET identity=?, display_name=?, last_seen_at=?, left_at=NULL WHERE room_id=? AND user_id=?",
                (identity, name, _iso(now), room_id, user_id),
            )
        else:
            cur.execute(
                "INSERT INTO speaking_live_video_presences(room_id,user_id,identity,display_name,joined_at,last_seen_at,left_at) VALUES (?,?,?,?,?,?,NULL)",
                (room_id, user_id, identity, name, _iso(now), _iso(now)),
            )
        cur.execute("UPDATE speaking_live_video_rooms SET last_activity_at=? WHERE id=?", (_iso(now), room_id))
        conn.commit()
        room_count = _active_presence_count(cur, room_id, now)
    except HTTPException:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()

    recording_status = "none"
    try:
        from backend.speaking_live_recordings import start_recording_for_room
        recording_status = await asyncio.to_thread(start_recording_for_room, room_id)
    except Exception:
        # A recording outage must be visible to the moderator, but must not
        # prevent the class from meeting or strand participants in the lobby.
        recording_status = "failed"
        logger.exception("Could not start recording for scheduled room %s", room_id)

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
            "roomAdmin": True,
        },
    }
    return {
        "url": url,
        "token": jwt.encode(claims, api_secret, algorithm="HS256"),
        "room": _serialize_room(room, room_count),
        "room_state": _room_state(room),
        "is_host": True,
        "is_moderator": True,
        "recording_status": recording_status,
        "expires_in_seconds": TOKEN_LIFETIME_SECONDS,
    }


@router.get("/api/speaking/live-video/rooms/{room_id}/session-state")
async def live_video_session_state(room_id: str, authorization: str | None = Header(default=None)):
    _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        room = _active_room_or_error(cur, room_id)
        return {"state": _room_state(room), "locked": bool(room.get("locked"))}
    finally:
        conn.close()


@router.patch("/staff/speaking/live-video/rooms/{room_id}/session-state")
async def staff_update_live_video_session_state(
    room_id: str,
    payload: LiveVideoStatePatch,
    authorization: str | None = Header(default=None),
):
    _require_active_staff(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No live room changes were provided")
    if "primary_identity" in changes and changes["primary_identity"] is not None:
        identity = str(changes["primary_identity"])
        if not re.fullmatch(r"(?:speaking-[0-9]+|speaking-admin-[0-9]+-[A-Za-z0-9_-]{8,40})", identity):
            raise HTTPException(status_code=422, detail="Invalid primary participant")
    if "primary_source" in changes and changes["primary_source"] not in {None, "camera", "screen", "board", "auto"}:
        raise HTTPException(status_code=422, detail="Invalid primary source")
    if "cue_card_prompts" in changes:
        prompts = changes["cue_card_prompts"]
        if prompts is not None and (len(prompts) > 5 or any(not isinstance(item, str) or len(item) > 240 for item in prompts)):
            raise HTTPException(status_code=422, detail="Cue card has too many or overly long prompts")
    if changes.get("cue_card_started_at") and not _safe_datetime(changes["cue_card_started_at"]):
        raise HTTPException(status_code=422, detail="Invalid cue card start time")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_live_video_rooms WHERE id=? FOR UPDATE", (room_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Live video room was not found")
        room = dict(row)
        if str(room.get("status")) != "active":
            raise HTTPException(status_code=410, detail="This live video room has ended")
        state = _room_state(room)
        state.update({key: value for key, value in changes.items() if key != "locked"})
        metadata = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        if len(metadata.encode("utf-8")) > 32_000:
            raise HTTPException(status_code=422, detail="Live room state is too large")
        # LiveKit publishes the updated metadata to every connected learner.
        _livekit_room_request("UpdateRoomMetadata", {"room": room_id, "metadata": metadata})
        locked = bool(changes.get("locked", room.get("locked")))
        cur.execute("UPDATE speaking_live_video_rooms SET room_state=?,locked=?,last_activity_at=? WHERE id=?", (metadata, locked, _iso(), room_id))
        conn.commit()
        return {"state": state, "locked": locked}
    except Exception:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/api/speaking/live-video/rooms/{room_id}/messages")
async def list_live_video_messages(room_id: str, authorization: str | None = Header(default=None)):
    _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute("SELECT id,display_name,is_moderator,text,created_at FROM speaking_live_video_messages WHERE room_id=? ORDER BY id DESC LIMIT 100", (room_id,))
        rows = [dict(row) for row in (cur.fetchall() or [])]
        return {"messages": [dict(row, created_at=_iso(row["created_at"]) if isinstance(row.get("created_at"), datetime) else str(row.get("created_at") or "")) for row in reversed(rows)]}
    finally:
        conn.close()


@router.post("/api/speaking/live-video/rooms/{room_id}/messages")
async def send_live_video_message(room_id: str, payload: LiveVideoMessageRequest, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    user_id = int(user.get("id") or 0)
    text = " ".join(payload.text.split())
    if not text:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    display_name, _, _ = _main_helpers()
    name = " ".join(str(display_name(user)).split())[:80] or "Participant"
    moderator = str(user.get("role") or "").lower() in {"speaking_admin", "admin", "superadmin", "developer"}
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute("SELECT 1 FROM speaking_live_video_presences WHERE room_id=? AND user_id=? AND left_at IS NULL AND last_seen_at>=?", (room_id, user_id, _iso(_now() - timedelta(seconds=PRESENCE_TTL_SECONDS))))
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="Join the live room before chatting")
        cur.execute("INSERT INTO speaking_live_video_messages(room_id,user_id,display_name,is_moderator,text) VALUES (?,?,?,?,?) RETURNING id,created_at", (room_id, user_id, name, moderator, text))
        row = dict(cur.fetchone())
        conn.commit()
    finally:
        conn.close()
    event = {"type": "chat", "id": int(row["id"]), "display_name": name, "is_moderator": moderator, "text": text, "created_at": _iso(row["created_at"]) if isinstance(row.get("created_at"), datetime) else str(row.get("created_at") or "")}
    try:
        _broadcast_room_event(room_id, event)
        delivered = True
    except HTTPException:
        # History remains available even when a transient data packet fails.
        delivered = False
    return {"message": event, "delivered_live": delivered}


@router.get("/staff/speaking/live-video/rooms/{room_id}/hands")
async def staff_live_video_hands(room_id: str, authorization: str | None = Header(default=None)):
    _require_active_staff(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute("SELECT h.user_id,h.display_name,h.updated_at FROM speaking_live_video_hands h JOIN speaking_live_video_presences p ON p.room_id=h.room_id AND p.user_id=h.user_id WHERE h.room_id=? AND h.raised=TRUE AND p.left_at IS NULL AND p.last_seen_at>=? ORDER BY h.updated_at ASC", (room_id, _iso(_now() - timedelta(seconds=PRESENCE_TTL_SECONDS))))
        return {"hands": [dict(row) for row in (cur.fetchall() or [])]}
    finally:
        conn.close()


@router.post("/api/speaking/live-video/rooms/{room_id}/hand")
async def set_live_video_hand(room_id: str, payload: LiveVideoHandRequest, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    user_id = int(user.get("id") or 0)
    display_name, _, _ = _main_helpers()
    name = " ".join(str(display_name(user)).split())[:80] or "Participant"
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute("SELECT 1 FROM speaking_live_video_presences WHERE room_id=? AND user_id=? AND left_at IS NULL", (room_id, user_id))
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="Join the live room before raising a hand")
        cur.execute("INSERT INTO speaking_live_video_hands(room_id,user_id,display_name,raised,updated_at) VALUES (?,?,?,?,?) ON CONFLICT (room_id,user_id) DO UPDATE SET raised=EXCLUDED.raised,display_name=EXCLUDED.display_name,updated_at=EXCLUDED.updated_at", (room_id, user_id, name, payload.raised, _iso()))
        conn.commit()
    finally:
        conn.close()
    event = {"type": "hand", "user_id": user_id, "display_name": name, "raised": payload.raised}
    with suppress(HTTPException):
        _broadcast_room_event(room_id, event)
    return {"ok": True, "raised": payload.raised}


@router.post("/staff/speaking/live-video/rooms/{room_id}/{action}")
async def staff_live_video_direct_action(room_id: str, action: str, payload: LiveVideoDirectActionRequest, authorization: str | None = Header(default=None)):
    _require_active_staff(authorization)
    if action not in {"invite-to-speak", "ask-to-unmute"}:
        raise HTTPException(status_code=404, detail="Unknown live room action")
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    identity = payload.identity.strip()
    if not re.fullmatch(r"speaking-[0-9]+", identity):
        raise HTTPException(status_code=422, detail="Invalid learner identity")
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
    finally:
        conn.close()
    participants = _livekit_room_request("ListParticipants", {"room": room_id}).get("participants", [])
    if not any(isinstance(row, dict) and str(row.get("identity") or "") == identity for row in participants):
        raise HTTPException(status_code=404, detail="Learner is no longer in this live room")
    _broadcast_room_event(room_id, {"type": action.replace("-", "_"), "identity": identity}, [identity])
    if action == "invite-to-speak":
        learner_id = int(identity.removeprefix("speaking-"))
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE speaking_live_video_hands SET raised=FALSE,updated_at=? WHERE room_id=? AND user_id=?", (_iso(), room_id, learner_id))
            conn.commit()
        finally:
            conn.close()
        with suppress(HTTPException):
            _broadcast_room_event(room_id, {"type": "hand", "user_id": learner_id, "raised": False})
    return {"ok": True}


@router.get("/api/speaking/live-video/rooms/{room_id}/media-permissions")
async def live_video_media_permissions(room_id: str, authorization: str | None = Header(default=None)):
    user = _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute(
            "SELECT media_kind,status,requested_at,decided_at FROM speaking_live_video_media_permissions WHERE room_id=? AND user_id=?",
            (room_id, int(user.get("id") or 0)),
        )
        states = {str(dict(row).get("media_kind")): dict(row) for row in (cur.fetchall() or [])}
        return {
            "permissions": {
                kind: {
                    "status": str(states.get(kind, {}).get("status") or "not_requested"),
                    "requested_at": states.get(kind, {}).get("requested_at"),
                    "decided_at": states.get(kind, {}).get("decided_at"),
                }
                for kind in ("camera", "microphone")
            }
        }
    finally:
        conn.close()


@router.post("/api/speaking/live-video/rooms/{room_id}/media-permissions/request")
async def request_live_video_media_permission(
    room_id: str,
    payload: LiveVideoMediaPermissionRequest,
    authorization: str | None = Header(default=None),
):
    user = _require_user(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    kind = _media_kind(payload.media_kind)
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute(
            "SELECT 1 FROM speaking_live_video_presences WHERE room_id=? AND user_id=? AND left_at IS NULL AND last_seen_at>=?",
            (room_id, user_id, _iso(_now() - timedelta(seconds=PRESENCE_TTL_SECONDS))),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=409, detail="Join the live room before requesting media access")
        cur.execute(
            "SELECT status,requested_at FROM speaking_live_video_media_permissions WHERE room_id=? AND user_id=? AND media_kind=?",
            (room_id, user_id, kind),
        )
        existing = cur.fetchone()
        if existing:
            existing = dict(existing)
            status = str(existing.get("status") or "")
            if status in {"pending", "approved"}:
                return {"media_kind": kind, "status": status}
            last_request = _safe_datetime(existing.get("requested_at"))
            if last_request and _now() - last_request < timedelta(seconds=15):
                raise HTTPException(status_code=429, detail="Please wait before requesting this permission again")
            cur.execute(
                "UPDATE speaking_live_video_media_permissions SET status='pending',requested_at=?,decided_at=NULL,decided_by=NULL WHERE room_id=? AND user_id=? AND media_kind=?",
                (_iso(), room_id, user_id, kind),
            )
        else:
            cur.execute(
                "INSERT INTO speaking_live_video_media_permissions(room_id,user_id,media_kind,status,requested_at) VALUES (?,?,?,'pending',?)",
                (room_id, user_id, kind, _iso()),
            )
        conn.commit()
        return {"media_kind": kind, "status": "pending"}
    except HTTPException:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/staff/speaking/live-video/rooms/{room_id}/media-permissions")
async def staff_live_video_media_permission_queue(room_id: str, authorization: str | None = Header(default=None)):
    _require_active_staff(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute(
            """
            SELECT p.user_id,p.media_kind,p.status,p.requested_at,x.display_name,x.identity
            FROM speaking_live_video_media_permissions p
            JOIN speaking_live_video_presences x ON x.room_id=p.room_id AND x.user_id=p.user_id
            WHERE p.room_id=? AND p.status='pending'
              AND x.left_at IS NULL AND x.last_seen_at>=?
            ORDER BY p.requested_at ASC
            LIMIT 200
            """,
            (room_id, _iso(_now() - timedelta(seconds=PRESENCE_TTL_SECONDS))),
        )
        return {"requests": [dict(row) for row in (cur.fetchall() or [])]}
    finally:
        conn.close()


@router.post("/staff/speaking/live-video/rooms/{room_id}/media-permissions/decide")
async def decide_live_video_media_permission(
    room_id: str,
    payload: LiveVideoMediaPermissionDecision,
    authorization: str | None = Header(default=None),
):
    moderator = _require_active_staff(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    kind = _media_kind(payload.media_kind)
    identity = f"speaking-{payload.user_id}"
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
        cur.execute(
            "SELECT status FROM speaking_live_video_media_permissions WHERE room_id=? AND user_id=? AND media_kind=?",
            (room_id, payload.user_id, kind),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Permission request was not found")
        next_status = "approved" if payload.approved else "denied"
        cur.execute(
            "UPDATE speaking_live_video_media_permissions SET status=?,decided_at=?,decided_by=? WHERE room_id=? AND user_id=? AND media_kind=?",
            (next_status, _iso(), int(moderator.get("id") or 0), room_id, payload.user_id, kind),
        )
        cur.execute("SELECT media_kind FROM speaking_live_video_media_permissions WHERE room_id=? AND user_id=? AND status='approved'", (room_id, payload.user_id))
        sources = ["SCREEN_SHARE", *[str(dict(row).get("media_kind") or "").upper() for row in (cur.fetchall() or [])]]
        _sync_livekit_publish_permissions(room_id, identity, sources)
        conn.commit()
        return {"user_id": payload.user_id, "media_kind": kind, "status": next_status}
    except HTTPException:
        with suppress(Exception):
            conn.rollback()
        raise
    finally:
        conn.close()


@router.post("/staff/speaking/live-video/rooms/{room_id}/participants/remove")
async def staff_remove_live_video_participant(
    room_id: str,
    payload: LiveVideoRemoveParticipantRequest,
    authorization: str | None = Header(default=None),
):
    _require_active_staff(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    identity = payload.identity.strip()
    if not re.fullmatch(r"speaking-[0-9]+", identity):
        raise HTTPException(status_code=422, detail="Moderators cannot remove another moderator")
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
    finally:
        conn.close()
    response = _livekit_room_request("RemoveParticipant", {"room": room_id, "identity": identity})
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_live_video_presences SET left_at=?, last_seen_at=? WHERE room_id=? AND identity=? AND left_at IS NULL", (_iso(), _iso(), room_id, identity))
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "participant": response}


@router.post("/staff/speaking/live-video/rooms/{room_id}/tracks/mute")
async def staff_mute_live_video_track(
    room_id: str,
    payload: LiveVideoMuteTrackRequest,
    authorization: str | None = Header(default=None),
):
    _require_active_staff(authorization)
    ensure_live_video_schema()
    room_id = _room_id(room_id)
    identity = payload.identity.strip()
    track_sid = payload.track_sid.strip()
    if not re.fullmatch(r"speaking-[0-9]+", identity) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", track_sid):
        raise HTTPException(status_code=422, detail="Invalid participant track")
    conn = get_conn()
    cur = conn.cursor()
    try:
        _active_room_or_error(cur, room_id)
    finally:
        conn.close()
    response = _livekit_room_request(
        "MutePublishedTrack",
        {"room": room_id, "identity": identity, "trackSid": track_sid, "muted": payload.muted},
    )
    return {"ok": True, "track": response}


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
    user_id = int(user.get("id") or 0)
    remaining_moderator: dict[str, str] | None = None
    if str(user.get("role") or "").lower() in {"speaking_admin", "admin", "superadmin", "developer"}:
        # The presence table is user-scoped but LiveKit moderator identities
        # are device-scoped. Leaving one browser must not mark another active
        # moderator device as gone.
        with suppress(HTTPException):
            participants = _livekit_room_request("ListParticipants", {"room": room_id}).get("participants", [])
            remaining_moderator = next(
                (
                    {"identity": str(item.get("identity") or ""), "name": str(item.get("name") or "")}
                    for item in participants
                    if isinstance(item, dict)
                    and str(item.get("identity") or "").startswith(f"speaking-admin-{user_id}-")
                ),
                None,
            )
    conn = get_conn()
    cur = conn.cursor()
    try:
        if remaining_moderator:
            cur.execute(
                "UPDATE speaking_live_video_presences SET identity=?,display_name=?,last_seen_at=?,left_at=NULL WHERE room_id=? AND user_id=?",
                (remaining_moderator["identity"], remaining_moderator["name"], _iso(), room_id, user_id),
            )
        else:
            cur.execute("UPDATE speaking_live_video_presences SET left_at=?, last_seen_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL", (_iso(), _iso(), room_id, user_id))
            cur.execute("UPDATE speaking_live_video_hands SET raised=FALSE,updated_at=? WHERE room_id=? AND user_id=?", (_iso(), room_id, user_id))
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
    # Prepare the schedule table before changing the room state. Running DDL
    # through a second connection inside the finalization transaction could
    # block that transaction after the SFU room has already been deleted.
    from backend.speaking_live_lessons import ensure_live_lessons_schema
    ensure_live_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        room = _active_room_or_error(cur, room_id)
        if int(room.get("host_user_id") or 0) != int(user.get("id") or 0):
            _require_active_staff(authorization)
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
        try:
            from backend.speaking_live_recordings import stop_recording_for_room
            await asyncio.to_thread(stop_recording_for_room, room_id)
        except Exception:
            logger.exception("Could not finalize recording before closing room %s", room_id)
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
        finish_cur.execute(
            "UPDATE speaking_live_lessons SET status='completed',ended_at=CURRENT_TIMESTAMP,recording_expires_at=CURRENT_TIMESTAMP + INTERVAL '30 days',updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE room_id=? AND status='live'",
            (int(user.get("id") or 0), room_id),
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
