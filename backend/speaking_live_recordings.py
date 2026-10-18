"""Private server-side recordings for scheduled Diamond Speaking lessons.

The LiveKit Egress worker writes MP4s to the main server. Only a moderator's
post-lesson approval publishes an unguessable, 30-day replay link.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import secrets
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

import jwt
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()
_TOKEN_RE = re.compile(r"^[a-f0-9]{32}$")
_TERMINAL = {"EGRESS_COMPLETE", "COMPLETE", "3", 3}
_FAILED = {"EGRESS_FAILED", "FAILED", "EGRESS_ABORTED", "ABORTED", "EGRESS_LIMIT_REACHED", "LIMIT_REACHED", "4", "5", "6", 4, 5, 6}


class RecordingDecision(BaseModel):
    attach: bool


def _directory() -> Path:
    return Path(os.getenv("SPEAKING_RECORDINGS_DIR", "/srv/diamond-live-recordings")).resolve()


def _safe_file(path: str) -> Path:
    root = _directory()
    candidate = Path(path).resolve()
    if candidate.parent != root or not re.fullmatch(r"lesson-[0-9]+-[a-f0-9]{32}\.mp4", candidate.name):
        raise HTTPException(status_code=500, detail="Recording storage path is invalid")
    return candidate


def _egress_request(method: str, payload: dict, *, timeout: int = 15) -> dict:
    from backend.speaking_live_video import _livekit_config, _livekit_control_url

    public_url, api_key, api_secret = _livekit_config()
    now = datetime.now(timezone.utc)
    token = jwt.encode({
        "iss": api_key,
        "nbf": int(now.timestamp()) - 5,
        "exp": int((now + timedelta(seconds=90)).timestamp()),
        "video": {"roomRecord": True},
    }, api_secret, algorithm="HS256")
    req = urlrequest.Request(
        f"{_livekit_control_url(public_url)}/twirp/livekit.Egress/{method}",
        data=json.dumps(payload, separators=(",", ":")).encode(),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read() or b"{}")
    except (urlerror.HTTPError, urlerror.URLError, TimeoutError) as exc:
        logger.warning("LiveKit Egress %s failed: %s", method, exc)
        raise HTTPException(status_code=503, detail="Recording service is temporarily unavailable") from exc


def _lesson_for_room(room_id: str) -> dict | None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM speaking_live_lessons WHERE room_id=? AND status='live'", (room_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def start_recording_for_room(room_id: str) -> str:
    """Idempotent start when a moderator joins a scheduled live room."""
    from backend.speaking_live_lessons import ensure_live_lessons_schema

    ensure_live_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_live_lessons WHERE room_id=? AND status='live' FOR UPDATE", (room_id,))
        raw = cur.fetchone()
        if not raw:
            conn.commit()
            return "none"
        lesson = dict(raw)
        status = str(lesson.get("recording_status") or "none")
        if status in {"starting", "recording", "processing", "ready", "attached"}:
            conn.commit()
            return status
        lesson_id = int(lesson["id"])
        token = secrets.token_hex(16)
        file_path = _directory() / f"lesson-{lesson_id}-{token}.mp4"
        cur.execute(
            "UPDATE speaking_live_lessons SET recording_status='starting',recording_token=?,recording_file_path=?,recording_egress_id=NULL WHERE id=?",
            (token, str(file_path), lesson_id),
        )
        conn.commit()
    finally:
        conn.close()

    try:
        _directory().mkdir(mode=0o700, parents=True, exist_ok=True)
        if shutil.disk_usage(_directory()).free < 10 * 1024**3:
            raise HTTPException(status_code=507, detail="Recording storage has less than 10 GB free")
        # /recordings is the read/write mount of SPEAKING_RECORDINGS_DIR inside
        # the Egress container. Use a room layout so audio and all visible feeds
        # are captured without requiring the moderator browser to stay open.
        info = _egress_request("StartEgress", {
            "room_name": room_id,
            "template": {"layout": "grid"},
            "outputs": [{"file": {"file_type": "MP4", "filepath": f"/recordings/{file_path.name}"}}],
        }, timeout=30)
        egress_id = str(info.get("egress_id") or info.get("egressId") or "")
        if not egress_id:
            raise HTTPException(status_code=503, detail="Recording worker did not acknowledge the lesson")
    except Exception:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE speaking_live_lessons SET recording_status='failed' WHERE id=? AND recording_status='starting'", (lesson_id,))
            conn.commit()
        finally:
            conn.close()
        raise

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE speaking_live_lessons SET recording_status='recording',recording_egress_id=? WHERE id=? AND recording_status='starting'", (egress_id, lesson_id))
        conn.commit()
    finally:
        conn.close()
    return "recording"


def stop_recording_for_room(room_id: str) -> None:
    lesson = _lesson_for_room(room_id)
    if not lesson or lesson.get("recording_status") not in {"recording", "starting"}:
        return
    egress_id = str(lesson.get("recording_egress_id") or "")
    next_status = "processing"
    if egress_id:
        try:
            _egress_request("StopEgress", {"egress_id": egress_id}, timeout=12)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                result = _egress_request("ListEgress", {"egress_id": egress_id}, timeout=6)
                items = result.get("items") or result.get("egresses") or []
                remote_status = items[0].get("status") if items else None
                if remote_status in _TERMINAL:
                    path = _safe_file(str(lesson.get("recording_file_path") or ""))
                    next_status = "ready" if path.is_file() and path.stat().st_size > 1024 else "failed"
                    break
                if remote_status in _FAILED:
                    next_status = "failed"
                    break
                time.sleep(1)
        except HTTPException:
            # Deleting the room also stops Egress. Preserve the private file for
            # reconciliation instead of failing the lesson-end operation.
            logger.exception("Could not explicitly stop lesson recording %s", lesson["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE speaking_live_lessons SET recording_status=? WHERE id=? AND recording_status IN ('recording','starting')", (next_status, lesson["id"]))
        conn.commit()
    finally:
        conn.close()


def _refresh_status(lesson: dict) -> str:
    status = str(lesson.get("recording_status") or "none")
    if status not in {"recording", "processing", "starting"}:
        return status
    egress_id = str(lesson.get("recording_egress_id") or "")
    if not egress_id:
        if str(lesson.get("status")) == "completed":
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE speaking_live_lessons SET recording_status='failed' WHERE id=? AND recording_status IN ('starting','processing')", (lesson["id"],))
                conn.commit()
            finally:
                conn.close()
            return "failed"
        return status
    try:
        result = _egress_request("ListEgress", {"egress_id": egress_id}, timeout=6)
        items = result.get("items") or result.get("egresses") or []
        egress = items[0] if items else {}
        remote_status = egress.get("status")
        if remote_status in _TERMINAL:
            path = _safe_file(str(lesson.get("recording_file_path") or ""))
            status = "ready" if path.is_file() and path.stat().st_size > 1024 else "failed"
        elif remote_status in _FAILED:
            status = "failed"
        elif str(lesson.get("status")) == "completed":
            status = "processing"
        if status != lesson.get("recording_status"):
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute("UPDATE speaking_live_lessons SET recording_status=? WHERE id=?", (status, lesson["id"]))
                conn.commit()
            finally:
                conn.close()
    except HTTPException:
        logger.warning("Recording status unavailable for lesson %s", lesson["id"])
    return status


def _get_lesson(lesson_id: int) -> dict:
    from backend.speaking_live_lessons import _get_lesson as get_lesson

    return get_lesson(lesson_id)


@router.get("/staff/speaking/live-lessons/{lesson_id}/recording-status")
async def recording_status(lesson_id: int, authorization: str | None = Header(default=None)):
    from backend.speaking_live_lessons import _auth

    _auth(authorization, staff=True)
    lesson = _get_lesson(lesson_id)
    return {"status": await asyncio.to_thread(_refresh_status, lesson), "attached": bool(lesson.get("recording_url"))}


@router.post("/staff/speaking/live-lessons/{lesson_id}/recording-decision")
async def recording_decision(lesson_id: int, payload: RecordingDecision, authorization: str | None = Header(default=None)):
    from backend.speaking_live_lessons import _auth, _audit, _lesson

    user = _auth(authorization, staff=True)
    lesson = _get_lesson(lesson_id)
    if lesson.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Finish the lesson before deciding on the recording")
    status = await asyncio.to_thread(_refresh_status, lesson)
    if status not in {"ready", "attached", "discarded"}:
        raise HTTPException(status_code=409, detail="The recording is not ready yet")
    if payload.attach and status == "discarded":
        raise HTTPException(status_code=409, detail="This recording was already discarded")
    if not payload.attach and status == "attached":
        raise HTTPException(status_code=409, detail="This recording was already attached")
    if payload.attach:
        path = _safe_file(str(lesson.get("recording_file_path") or ""))
        if not path.is_file() or path.stat().st_size < 1024:
            raise HTTPException(status_code=409, detail="Recording file is missing")
        token = str(lesson.get("recording_token") or "")
        if not _TOKEN_RE.fullmatch(token):
            raise HTTPException(status_code=500, detail="Recording token is invalid")
        url = f"https://diamond-education.uz/api/speaking/live-lessons/{lesson_id}/recording/{token}"
        next_status = "attached"
    else:
        url = ""
        next_status = "discarded"
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE speaking_live_lessons SET recording_status=?,recording_url=?,recording_expires_at=COALESCE(ended_at,CURRENT_TIMESTAMP)+INTERVAL '30 days',updated_by=?,updated_at=CURRENT_TIMESTAMP WHERE id=? RETURNING *", (next_status, url, int(user.get("id") or 0), lesson_id))
        updated = dict(cur.fetchone())
        conn.commit()
    finally:
        conn.close()
    _audit(lesson_id, int(user.get("id") or 0), "recording_attached" if payload.attach else "recording_discarded")
    return {"lesson": _lesson(updated)}


@router.get("/api/speaking/live-lessons/{lesson_id}/recording/{token}")
async def stream_recording(lesson_id: int, token: str):
    # The secret in the URL is 128 bits of entropy and only returned after
    # moderator approval. Existing app video players can use it without a
    # custom Authorization header, while expiry is still checked on every hit.
    if not _TOKEN_RE.fullmatch(token):
        raise HTTPException(status_code=404, detail="Recording not found")
    lesson = _get_lesson(lesson_id)
    expiry = lesson.get("recording_expires_at")
    if isinstance(expiry, str):
        expiry = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
    expected = str(lesson.get("recording_token") or "")
    if not secrets.compare_digest(token, expected) or lesson.get("recording_status") != "attached" or not expiry or expiry <= datetime.now(timezone.utc):
        raise HTTPException(status_code=404, detail="Recording not found")
    path = _safe_file(str(lesson.get("recording_file_path") or ""))
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Recording not found")
    return FileResponse(path, media_type="video/mp4", filename=f"diamond-speaking-lesson-{lesson_id}.mp4", content_disposition_type="inline", headers={"Cache-Control": "private, no-store"})


def expire_recordings() -> int:
    """Purge private MP4s after the same 30-day window as replay access."""
    conn = get_conn()
    removed = 0
    try:
        cur = conn.cursor()
        cur.execute("SELECT id,recording_file_path FROM speaking_live_lessons WHERE recording_expires_at < CURRENT_TIMESTAMP AND recording_file_path IS NOT NULL")
        rows = [dict(row) for row in cur.fetchall() or []]
        for row in rows:
            try:
                _safe_file(str(row["recording_file_path"])).unlink(missing_ok=True)
            except (OSError, HTTPException):
                logger.exception("Could not remove expired lesson recording %s", row["id"])
                continue
            cur.execute("UPDATE speaking_live_lessons SET recording_file_path=NULL,recording_token=NULL,recording_egress_id=NULL,recording_url='',recording_status='expired' WHERE id=?", (row["id"],))
            removed += 1
        conn.commit()
    finally:
        conn.close()
    return removed
