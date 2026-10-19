"""Scheduling and 7-day replay access for Diamond Speaking live video lessons."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()
RECORDING_RETENTION_DAYS = 7
LESSON_HISTORY_DAYS = 30
REMINDER_MINUTES = (1440, 60, 15)
TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


class LessonPayload(BaseModel):
    title: str = Field(min_length=3, max_length=140)
    topic: str = Field(default="", max_length=240)
    subject: str = Field(default="english", max_length=20)
    moderator_name: str = Field(default="", max_length=100)
    audience_label: str = Field(default="Barcha Speaking foydalanuvchilari", max_length=160)
    starts_at: str = Field(min_length=10, max_length=64)
    # Optional compatibility input for older clients. Lesson duration is no
    # longer scheduled; the moderator controls when a live session ends.
    ends_at: str | None = Field(default=None, max_length=64)
    auto_open_video_room: bool = True
    reminder_minutes: list[int] = Field(default_factory=lambda: [1440, 60, 15])


class LessonRecordingPayload(BaseModel):
    recording_url: str = Field(min_length=8, max_length=2048)


def _auth(authorization: str | None, *, staff: bool = False) -> dict[str, Any]:
    from backend.main import _require_role, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    if staff:
        _require_role(user, {"speaking_admin", "admin", "superadmin", "developer"})
    else:
        _require_role(user, {"speaking_user", "student", "teacher", "support", "admin", "superadmin", "developer"})
        if int(user.get("blocked") or 0) == 1 or int(user.get("access_enabled", 1) or 0) != 1:
            raise HTTPException(status_code=403, detail="Speaking schedule is not available for this account")
    return user


def _iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Date and time must be valid ISO 8601")
    if parsed.tzinfo is None:
        raise HTTPException(status_code=422, detail="Date and time must include a timezone")
    return parsed.astimezone(timezone.utc)


def _display_time(value: Any) -> str:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return str(value or "")


def _normalise_payload(payload: LessonPayload) -> dict[str, Any]:
    title = " ".join(payload.title.split())
    topic = " ".join(payload.topic.split())
    subject = payload.subject.strip().lower()
    if subject in {"english", "eng", "ielts", "english / ielts", "english/ielts"}:
        subject = "english"
    elif subject in {"cefr", "english / cefr", "english/cefr"}:
        subject = "cefr"
    elif subject in {"ru", "russian", "rus tili"}:
        subject = "russian"
    else:
        raise HTTPException(status_code=422, detail="Subject must be english, russian or cefr")
    starts = _iso_datetime(payload.starts_at)
    reminders = sorted({int(item) for item in payload.reminder_minutes if int(item) in REMINDER_MINUTES}, reverse=True)
    return {
        "title": title,
        "topic": topic,
        "subject": subject,
        "moderator_name": " ".join(payload.moderator_name.split()),
        "audience_label": " ".join(payload.audience_label.split()) or "All Speaking learners",
        "starts_at": starts.isoformat(),
        "auto_open_video_room": bool(payload.auto_open_video_room),
        "reminder_minutes": json.dumps(reminders),
    }


@lru_cache(maxsize=1)
def ensure_live_lessons_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_live_lessons (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                topic TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT 'english',
                moderator_name TEXT NOT NULL DEFAULT '',
                audience_label TEXT NOT NULL DEFAULT 'All Speaking learners',
                starts_at TIMESTAMPTZ NOT NULL,
                ends_at TIMESTAMPTZ,
                auto_open_video_room BOOLEAN NOT NULL DEFAULT TRUE,
                status TEXT NOT NULL DEFAULT 'scheduled',
                cancellation_reason TEXT NOT NULL DEFAULT '',
                room_id TEXT,
                recording_url TEXT,
                recording_expires_at TIMESTAMPTZ,
                recording_egress_id TEXT,
                recording_status TEXT NOT NULL DEFAULT 'none',
                recording_file_path TEXT,
                recording_token TEXT,
                reminder_minutes TEXT NOT NULL DEFAULT '[1440,60,15]',
                created_by INTEGER NOT NULL DEFAULT 0,
                updated_by INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMPTZ
            )
            """
        )
        cur.execute("ALTER TABLE speaking_live_lessons ADD COLUMN IF NOT EXISTS auto_open_video_room BOOLEAN NOT NULL DEFAULT TRUE")
        # Keep old values for history, but do not require or use them for new schedules.
        cur.execute("ALTER TABLE speaking_live_lessons ALTER COLUMN ends_at DROP NOT NULL")
        cur.execute("ALTER TABLE speaking_live_lessons ADD COLUMN IF NOT EXISTS recording_egress_id TEXT")
        cur.execute("ALTER TABLE speaking_live_lessons ADD COLUMN IF NOT EXISTS recording_status TEXT NOT NULL DEFAULT 'none'")
        cur.execute("ALTER TABLE speaking_live_lessons ADD COLUMN IF NOT EXISTS recording_file_path TEXT")
        cur.execute("ALTER TABLE speaking_live_lessons ADD COLUMN IF NOT EXISTS recording_token TEXT")
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_live_lesson_notifications (
                id BIGSERIAL PRIMARY KEY,
                lesson_id INTEGER NOT NULL REFERENCES speaking_live_lessons(id) ON DELETE CASCADE,
                notification_key TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'sending',
                sent_count INTEGER NOT NULL DEFAULT 0,
                attempt_count INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMPTZ,
                UNIQUE (lesson_id, notification_key)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_live_lesson_audit (
                id BIGSERIAL PRIMARY KEY,
                lesson_id INTEGER NOT NULL REFERENCES speaking_live_lessons(id) ON DELETE CASCADE,
                actor_user_id INTEGER NOT NULL DEFAULT 0,
                action TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_live_lessons_start ON speaking_live_lessons(starts_at DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_live_lessons_status ON speaking_live_lessons(status, starts_at)")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _lesson(row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    item = dict(row)
    current = now or datetime.now(timezone.utc)
    expiry = item.get("recording_expires_at")
    if isinstance(expiry, str):
        try:
            expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
        except ValueError:
            expiry = None
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    expired = bool(expiry and expiry <= current)
    try:
        reminders = json.loads(str(item.get("reminder_minutes") or "[1440,60,15]"))
    except (TypeError, ValueError):
        reminders = [1440, 60, 15]
    return {
        "id": int(item.get("id") or 0),
        "title": str(item.get("title") or ""),
        "topic": str(item.get("topic") or ""),
        "subject": str(item.get("subject") or "english"),
        "moderator_name": str(item.get("moderator_name") or ""),
        "audience_label": str(item.get("audience_label") or ""),
        "starts_at": item.get("starts_at").isoformat() if isinstance(item.get("starts_at"), datetime) else str(item.get("starts_at") or ""),
        "status": str(item.get("status") or "scheduled"),
        "auto_open_video_room": bool(item.get("auto_open_video_room", True)),
        "cancellation_reason": str(item.get("cancellation_reason") or ""),
        "room_id": str(item.get("room_id") or ""),
        "can_join_live_video": str(item.get("status") or "") == "live" and bool(item.get("room_id")),
        "recording_url": "" if expired else str(item.get("recording_url") or ""),
        "recording_status": "expired" if expired else str(item.get("recording_status") or "none"),
        "recording_expired": expired,
        "recording_expires_at": "" if expired or not expiry else expiry.isoformat(),
        "recording_days_left": 0 if expired or not expiry else max(0, (expiry.date() - current.date()).days),
        "reminder_minutes": [int(value) for value in reminders if str(value).isdigit()],
        "created_at": item.get("created_at").isoformat() if isinstance(item.get("created_at"), datetime) else str(item.get("created_at") or ""),
        "updated_at": item.get("updated_at").isoformat() if isinstance(item.get("updated_at"), datetime) else str(item.get("updated_at") or ""),
        "ended_at": item.get("ended_at").isoformat() if isinstance(item.get("ended_at"), datetime) else str(item.get("ended_at") or ""),
    }


def _send_lesson_push(lesson_id: int, title: str, body: str, action: str) -> int:
    import push_notifications

    return int(push_notifications.send_push_to_speaking_devices(
        title=title,
        body=body,
        data={"type": "speaking_live_lesson", "lesson_id": str(lesson_id), "action": action},
    ) or 0)


async def _notify(lesson_id: int, title: str, body: str, key: str, action: str) -> int:
    ensure_live_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO speaking_live_lesson_notifications (lesson_id, notification_key, status) VALUES (?, ?, 'sending') ON CONFLICT (lesson_id, notification_key) DO UPDATE SET status='sending', attempt_count=speaking_live_lesson_notifications.attempt_count+1 WHERE speaking_live_lesson_notifications.status IN ('failed','no_devices') RETURNING id",
            (lesson_id, key),
        )
        claimed = cur.fetchone()
        conn.commit()
        if not claimed:
            return 0
    finally:
        conn.close()
    try:
        count = await asyncio.to_thread(_send_lesson_push, lesson_id, title, body, action)
        status = "sent" if count > 0 else "no_devices"
    except Exception:
        logger.exception("Speaking live lesson notification failed lesson_id=%s", lesson_id)
        count, status = 0, "failed"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_live_lesson_notifications SET status=?, sent_count=?, sent_at=CASE WHEN ?='sent' THEN CURRENT_TIMESTAMP ELSE sent_at END WHERE lesson_id=? AND notification_key=?", (status, count, status, lesson_id, key))
        conn.commit()
    finally:
        conn.close()
    return count


def _get_lesson(lesson_id: int) -> dict[str, Any]:
    ensure_live_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_live_lessons WHERE id=?", (lesson_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Live lesson was not found")
        return dict(row)
    finally:
        conn.close()


def _audit(lesson_id: int, actor_id: int, action: str, details: dict[str, Any] | None = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO speaking_live_lesson_audit (lesson_id,actor_user_id,action,details) VALUES (?,?,?,?)",
            (lesson_id, actor_id, action, json.dumps(details or {}, ensure_ascii=False, default=str)),
        )
        conn.commit()
    finally:
        conn.close()


@router.get("/speaking/live-lessons")
@router.get("/api/speaking/live-lessons")
async def list_my_live_lessons(authorization: str | None = Header(default=None)):
    _auth(authorization)
    ensure_live_lessons_schema()
    now = datetime.now(timezone.utc)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT * FROM speaking_live_lessons
               WHERE status='live'
                  OR starts_at >= ?
                  OR (starts_at >= ? AND status IN ('completed','cancelled'))
               ORDER BY CASE WHEN status='live' THEN 0 ELSE 1 END, starts_at ASC LIMIT 300""",
            (now.isoformat(), (now - timedelta(days=LESSON_HISTORY_DAYS)).isoformat()),
        )
        rows = [dict(row) for row in (cur.fetchall() or [])]
        return {"lessons": [_lesson(row, now=now) for row in rows], "recording_retention_days": RECORDING_RETENTION_DAYS}
    finally:
        conn.close()


@router.get("/staff/speaking/live-lessons")
async def list_staff_live_lessons(authorization: str | None = Header(default=None)):
    _auth(authorization, staff=True)
    ensure_live_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_live_lessons ORDER BY starts_at DESC LIMIT 500")
        rows = [dict(row) for row in (cur.fetchall() or [])]
        return {"lessons": [_lesson(row) for row in rows], "recording_retention_days": RECORDING_RETENTION_DAYS}
    finally:
        conn.close()


@router.post("/staff/speaking/live-lessons")
async def create_live_lesson(payload: LessonPayload, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    ensure_live_lessons_schema()
    values = _normalise_payload(payload)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_live_lessons
               (title,topic,subject,moderator_name,audience_label,starts_at,auto_open_video_room,reminder_minutes,created_by,updated_by)
               VALUES (?,?,?,?,?,?,?,?,?,?) RETURNING *""",
            (*[values[key] for key in ("title", "topic", "subject", "moderator_name", "audience_label", "starts_at", "auto_open_video_room", "reminder_minutes")], int(user.get("id") or 0), int(user.get("id") or 0)),
        )
        row = cur.fetchone()
        conn.commit()
        lesson = dict(row)
    finally:
        conn.close()
    _audit(int(lesson["id"]), int(user.get("id") or 0), "created", {"title": lesson["title"]})
    await _notify(int(lesson["id"]), "Yangi live dars rejalashtirildi", f"{lesson['title']} · {_display_time(lesson['starts_at'])} (Toshkent vaqti)", "created", "created")
    return {"lesson": _lesson(lesson)}


@router.patch("/staff/speaking/live-lessons/{lesson_id}")
async def update_live_lesson(lesson_id: int, payload: LessonPayload, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    old = _get_lesson(lesson_id)
    if str(old.get("status")) not in {"scheduled", "live"}:
        raise HTTPException(status_code=409, detail="Only scheduled or live lessons can be edited")
    values = _normalise_payload(payload)
    time_changed = _iso_datetime(str(old.get("starts_at"))) != _iso_datetime(values["starts_at"])
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE speaking_live_lessons SET title=?,topic=?,subject=?,moderator_name=?,audience_label=?,starts_at=?,auto_open_video_room=?,reminder_minutes=?,updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING *""",
            (*[values[key] for key in ("title", "topic", "subject", "moderator_name", "audience_label", "starts_at", "auto_open_video_room", "reminder_minutes")], int(user.get("id") or 0), lesson_id),
        )
        row = cur.fetchone()
        conn.commit()
        updated = dict(row)
    finally:
        conn.close()
    _audit(lesson_id, int(user.get("id") or 0), "updated", {"schedule_changed": time_changed, "old_starts_at": old.get("starts_at"), "new_starts_at": updated.get("starts_at")})
    if time_changed:
        await _notify(lesson_id, "Live dars vaqti o‘zgardi", f"{updated['title']} · Yangi vaqt: {_display_time(updated['starts_at'])} (Toshkent vaqti)", f"rescheduled-{updated['updated_at']}", "rescheduled")
    return {"lesson": _lesson(updated), "schedule_changed": time_changed}


@router.post("/staff/speaking/live-lessons/{lesson_id}/cancel")
async def cancel_live_lesson(lesson_id: int, payload: dict[str, str] | None = None, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    lesson = _get_lesson(lesson_id)
    if str(lesson.get("status")) not in {"scheduled", "live"}:
        raise HTTPException(status_code=409, detail="This lesson can no longer be cancelled")
    reason = " ".join(str((payload or {}).get("reason") or "").split())[:300]
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_live_lessons SET status='cancelled', cancellation_reason=?, updated_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING *", (reason, int(user.get("id") or 0), lesson_id))
        updated = dict(cur.fetchone())
        conn.commit()
    finally:
        conn.close()
    _audit(lesson_id, int(user.get("id") or 0), "cancelled", {"reason": reason})
    await _notify(lesson_id, "Live dars bekor qilindi", f"{updated['title']} · {reason or 'Dars bekor qilindi'}", f"cancelled-{updated['updated_at']}", "cancelled")
    return {"lesson": _lesson(updated)}


@router.post("/staff/speaking/live-lessons/{lesson_id}/notify")
async def resend_live_lesson_notice(lesson_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    lesson = _get_lesson(lesson_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    sent = await _notify(lesson_id, "Diamond Speaking live darsi", f"{lesson['title']} · {_display_time(lesson['starts_at'])} (Toshkent vaqti)", f"manual-{stamp}", "reminder")
    _audit(lesson_id, int(user.get("id") or 0), "notification_resent", {"sent_count": sent})
    return {"sent_count": sent}


@router.get("/staff/speaking/live-lessons/{lesson_id}/history")
async def live_lesson_history(lesson_id: int, authorization: str | None = Header(default=None)):
    _auth(authorization, staff=True)
    _get_lesson(lesson_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id,actor_user_id,action,details,created_at FROM speaking_live_lesson_audit WHERE lesson_id=? ORDER BY created_at DESC,id DESC LIMIT 100", (lesson_id,))
        items = []
        for raw in cur.fetchall() or []:
            row = dict(raw)
            try:
                row["details"] = json.loads(str(row.get("details") or "{}"))
            except (TypeError, ValueError):
                row["details"] = {}
            if isinstance(row.get("created_at"), datetime):
                row["created_at"] = row["created_at"].isoformat()
            items.append(row)
        return {"items": items}
    finally:
        conn.close()


@router.post("/staff/speaking/live-lessons/{lesson_id}/start")
async def start_scheduled_live_lesson(lesson_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    updated, room_id, public_url, started = await asyncio.to_thread(
        _open_live_video_room, lesson_id, int(user.get("id") or 0)
    )
    if started:
        _audit(lesson_id, int(user.get("id") or 0), "started", {"room_id": room_id})
        await _notify(lesson_id, "Live dars boshlandi", f"{updated['title']} jonli efirda. Ilovani ochib qo‘shiling.", f"started-{updated['updated_at']}", "started")
    return {"lesson": _lesson(updated), "room_id": room_id, "livekit_url": public_url}


def _open_live_video_room(lesson_id: int, actor_id: int) -> tuple[dict[str, Any], str, str, bool]:
    lesson = _get_lesson(lesson_id)
    if lesson.get("status") == "live" and lesson.get("room_id"):
        from backend.speaking_live_video import _livekit_config

        public_url, _, _ = _livekit_config()
        return lesson, str(lesson["room_id"]), public_url, False
    if lesson.get("status") != "scheduled":
        raise HTTPException(status_code=409, detail="Only scheduled lessons can be started")
    if _iso_datetime(str(lesson["starts_at"])) > datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="Lesson cannot start before its scheduled time")
    from backend.speaking_live_video import (
        MAX_ROOM_PARTICIPANTS,
        _ensure_livekit_room,
        _iso,
        _livekit_config,
        ensure_live_video_schema,
    )
    public_url, _, _ = _livekit_config()
    ensure_live_video_schema()
    room_id = str(lesson.get("room_id") or f"spk-live-lesson-{lesson_id}")[:40]
    initial_state = json.dumps({"topic": str(lesson.get("topic") or "")}, ensure_ascii=False)
    _ensure_livekit_room(room_id, initial_state)
    now_iso = _iso()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO speaking_live_video_rooms (id,host_user_id,title,subject,max_participants,status,created_at,last_activity_at,room_state) VALUES (?,?,?,?,?,'active',?,?,?) ON CONFLICT (id) DO NOTHING", (room_id, int(actor_id or lesson.get("created_by") or 0), lesson["title"], lesson["subject"], MAX_ROOM_PARTICIPANTS, now_iso, now_iso, initial_state))
        cur.execute("UPDATE speaking_live_lessons SET room_id=?,status='live',updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='scheduled' RETURNING *", (room_id, int(actor_id or lesson.get("created_by") or 0), lesson_id))
        updated_row = cur.fetchone()
        if not updated_row:
            conn.rollback()
            latest = _get_lesson(lesson_id)
            if latest.get("status") == "live" and latest.get("room_id"):
                return latest, str(latest["room_id"]), public_url, False
            raise HTTPException(status_code=409, detail="This live lesson has already changed")
        updated = dict(updated_row)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return updated, room_id, public_url, True


@router.post("/staff/speaking/live-lessons/{lesson_id}/recording")
async def attach_live_lesson_recording(lesson_id: int, payload: LessonRecordingPayload, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    lesson = _get_lesson(lesson_id)
    parsed = urlparse(payload.recording_url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Recording link must be a secure HTTPS URL")
    if str(lesson.get("status")) not in {"completed", "live"}:
        raise HTTPException(status_code=409, detail="Recording can only be attached to a live or completed lesson")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_live_lessons SET recording_url=?, recording_expires_at=COALESCE(ended_at,CURRENT_TIMESTAMP) + INTERVAL '7 days', updated_by=?, updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING *", (payload.recording_url.strip(), int(user.get("id") or 0), lesson_id))
        updated = dict(cur.fetchone())
        conn.commit()
    finally:
        conn.close()
    _audit(lesson_id, int(user.get("id") or 0), "recording_attached", {"recording_expires_at": updated.get("recording_expires_at")})
    return {"lesson": _lesson(updated)}


@router.post("/staff/speaking/live-lessons/{lesson_id}/complete")
async def complete_live_lesson(lesson_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    lesson = _get_lesson(lesson_id)
    if lesson.get("status") not in {"live", "scheduled"}:
        raise HTTPException(status_code=409, detail="This lesson is already closed")
    if lesson.get("room_id"):
        from backend.speaking_live_video import end_live_video_room
        try:
            await end_live_video_room(str(lesson["room_id"]), authorization)
        except HTTPException as exc:
            if exc.status_code != 410:
                raise
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_live_lessons SET status='completed',ended_at=CURRENT_TIMESTAMP,recording_expires_at=CURRENT_TIMESTAMP + INTERVAL '7 days',updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING *", (int(user.get("id") or 0), lesson_id))
        updated = dict(cur.fetchone())
        conn.commit()
    finally:
        conn.close()
    _audit(lesson_id, int(user.get("id") or 0), "completed", {"room_id": lesson.get("room_id")})
    return {"lesson": _lesson(updated)}


@router.post("/staff/speaking/live-lessons/{lesson_id}/reopen")
async def reopen_live_lesson(lesson_id: int, authorization: str | None = Header(default=None)):
    user = _auth(authorization, staff=True)
    lesson = _get_lesson(lesson_id)
    if lesson.get("status") != "cancelled" or _iso_datetime(str(lesson.get("starts_at"))) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=409, detail="Only a cancelled future lesson can be reopened")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_live_lessons SET status='scheduled',cancellation_reason='',updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING *", (int(user.get("id") or 0), lesson_id))
        updated = dict(cur.fetchone())
        conn.commit()
    finally:
        conn.close()
    _audit(lesson_id, int(user.get("id") or 0), "reopened")
    await _notify(lesson_id, "Live dars qayta rejalashtirildi", f"{updated['title']} · {_display_time(updated['starts_at'])} (Toshkent vaqti)", f"reopened-{updated['updated_at']}", "reopened")
    return {"lesson": _lesson(updated)}


async def speaking_live_lesson_reminder_worker() -> None:
    await asyncio.sleep(10)
    last_recording_cleanup = datetime.min.replace(tzinfo=timezone.utc)
    while True:
        try:
            ensure_live_lessons_schema()
            now = datetime.now(timezone.utc)
            if now - last_recording_cleanup >= timedelta(hours=1):
                from backend.speaking_live_recordings import expire_recordings
                await asyncio.to_thread(expire_recordings)
                last_recording_cleanup = now
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute("SELECT * FROM speaking_live_lessons WHERE status='scheduled' AND starts_at>? AND starts_at<=? ORDER BY starts_at LIMIT 100", ((now - timedelta(minutes=6)).isoformat(), (now + timedelta(days=1, minutes=1)).isoformat()))
                rows = [dict(row) for row in (cur.fetchall() or [])]
            finally:
                conn.close()
            for row in rows:
                lesson_id = int(row.get("id") or 0)
                start = row.get("starts_at")
                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                minutes_left = int((start - now).total_seconds() // 60)
                auto_opened = False
                if bool(row.get("auto_open_video_room")) and start <= now and now - start <= timedelta(minutes=6):
                    try:
                        updated, room_id, _, opened = await asyncio.to_thread(
                            _open_live_video_room,
                            lesson_id,
                            int(row.get("created_by") or 0),
                        )
                        if opened:
                            _audit(lesson_id, int(row.get("created_by") or 0), "live_video_room_auto_opened", {"room_id": room_id})
                            await _notify(lesson_id, "Live dars boshlandi", f"{updated['title']} jonli efirda. Ilovani ochib qo‘shiling.", "auto-live-video-opened", "started")
                        auto_opened = True
                    except HTTPException as exc:
                        if exc.status_code != 409:
                            logger.exception("Could not auto-open live video room lesson_id=%s", lesson_id)
                    except Exception:
                        logger.exception("Could not auto-open live video room lesson_id=%s", lesson_id)
                if auto_opened:
                    continue
                try:
                    enabled = json.loads(str(row.get("reminder_minutes") or "[1440,60,15]"))
                except (TypeError, ValueError):
                    enabled = [1440, 60, 15]
                for minute in enabled:
                    minute = int(minute)
                    # Send once as the event enters the reminder window; the
                    # unique delivery key protects against multiple API workers.
                    if minute not in REMINDER_MINUTES or not (minute - 1 <= minutes_left <= minute):
                        continue
                    key = f"reminder-{minute}"
                    try:
                        await _notify(lesson_id, "Live dars yaqinlashmoqda", f"{row['title']} · {minute} daqiqadan so‘ng", key, "reminder")
                    except Exception:
                        logger.exception("Speaking live lesson reminder failed lesson_id=%s", lesson_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Speaking live lesson reminder worker failed")
        await asyncio.sleep(30)
