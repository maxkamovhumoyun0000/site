"""Speaking app: Teacher Feedback.

A Speaking app learner picks one of their recorded answers and sends it to a
teacher.  Reviewers see the student's name, the question and topic, the audio,
the transcript, the AI evaluation, the student's previous answers and their
progress, and reply with written feedback, an audio comment, a band
recommendation, corrections and a "do it again" task.  The learner keeps a
feedback history and marks each reply "resolved" or "practice again".

Who reviews:
* the Speaking admin (always);
* teachers and support teachers the Speaking admin assigned as reviewers.

Security:
* every reviewer endpoint re-checks the role and the assignment;
* learners only ever see their own requests;
* audio lives in a private directory outside every public upload folder and is
  served only through short-lived HMAC-signed URLs bound to the viewer and
  the file; uploads are size-limited and checked by their magic bytes;
* reviewers see the student's name and Speaking results only, never contact
  details or credentials.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()

AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "speaking_feedback_audio"
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MIN_AUDIO_BYTES = 2 * 1024
AUDIO_URL_TTL = 2 * 3600
DAILY_REQUEST_LIMIT = 20
MAX_OPEN_REQUESTS = 10
STUDENT_ROLES = {"speaking_user", "student"}
REVIEWER_ROLES = {"speaking_admin", "teacher", "support"}
REQUEST_STATUSES = ("pending", "in_review", "answered")
STUDENT_STATUSES = ("new", "resolved", "practice_again")
_FILE_RE = re.compile(r"^(req|rep)_\d+_[0-9a-f]{24}\.m4a$")
_SCHEMA_READY = False


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def ensure_tables() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_feedback_reviewers (
                user_id BIGINT PRIMARY KEY,
                assigned_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_feedback_requests (
                id BIGSERIAL PRIMARY KEY,
                student_id BIGINT NOT NULL,
                subject TEXT NOT NULL DEFAULT 'english',
                client_recording_id TEXT NOT NULL DEFAULT '',
                analysis_id BIGINT,
                question_id BIGINT,
                question_text TEXT NOT NULL DEFAULT '',
                topic_title TEXT NOT NULL DEFAULT '',
                part INTEGER,
                audio_file TEXT NOT NULL DEFAULT '',
                duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                transcript TEXT NOT NULL DEFAULT '',
                ai_score DOUBLE PRECISION,
                ai_result_json TEXT NOT NULL DEFAULT '{}',
                student_note TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                reviewer_id BIGINT,
                claimed_at TIMESTAMPTZ,
                student_status TEXT NOT NULL DEFAULT 'new',
                student_seen_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                answered_at TIMESTAMPTZ
            )"""
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_feedback_student ON speaking_feedback_requests(student_id, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_feedback_status ON speaking_feedback_requests(status, created_at)"
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_feedback_replies (
                request_id BIGINT PRIMARY KEY REFERENCES speaking_feedback_requests(id) ON DELETE CASCADE,
                reviewer_id BIGINT NOT NULL,
                reviewer_name TEXT NOT NULL DEFAULT '',
                reviewer_role TEXT NOT NULL DEFAULT '',
                feedback_text TEXT NOT NULL DEFAULT '',
                audio_file TEXT NOT NULL DEFAULT '',
                band DOUBLE PRECISION,
                criteria_json TEXT NOT NULL DEFAULT '{}',
                corrections_json TEXT NOT NULL DEFAULT '[]',
                retry_task TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        conn.commit()
        _SCHEMA_READY = True
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _user(authorization: str | None) -> tuple[dict[str, Any], str]:
    from backend.main import _role_from_login_type, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    role = _role_from_login_type(int(user.get("login_type") or 1), str(user.get("login_id") or ""))
    return user, role


def _is_assigned_reviewer(user_id: int) -> bool:
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM speaking_feedback_reviewers WHERE user_id=%s", (int(user_id),))
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def has_reviewer_access(user: dict[str, Any], role: str) -> bool:
    if role == "speaking_admin":
        return True
    if role in {"teacher", "support"}:
        if int(user.get("blocked") or 0) == 1:
            return False
        return _is_assigned_reviewer(int(user.get("id") or 0))
    return False


def _reviewer(authorization: str | None) -> tuple[dict[str, Any], str]:
    user, role = _user(authorization)
    if role not in REVIEWER_ROLES or not has_reviewer_access(user, role):
        raise HTTPException(status_code=403, detail="Speaking feedback access is not enabled for this account")
    return user, role


def _speaking_admin(authorization: str | None) -> dict[str, Any]:
    user, role = _user(authorization)
    if role != "speaking_admin":
        raise HTTPException(status_code=403, detail="Only the Speaking admin can manage reviewers")
    return user


def _student(authorization: str | None) -> dict[str, Any]:
    user, role = _user(authorization)
    if role not in STUDENT_ROLES:
        raise HTTPException(status_code=403, detail="Only Speaking app learners can send answers to a teacher")
    return user


def sections_for(user: dict[str, Any], role: str, sections: dict[str, list[str]]) -> dict[str, list[str]]:
    """``SECTIONS_BY_ROLE`` with "speaking-feedback" added for an assigned
    teacher or support reviewer (used by ``/app/state``)."""
    if role not in {"teacher", "support"}:
        return sections
    try:
        allowed = has_reviewer_access(user, role)
    except Exception:
        logger.debug("speaking feedback access lookup failed", exc_info=True)
        return sections
    if not allowed:
        return sections
    current = list(sections.get(role) or [])
    if "speaking-feedback" not in current:
        insert_at = current.index("profile") if "profile" in current else len(current)
        current.insert(insert_at, "speaking-feedback")
    return {**sections, role: current}


def _rate_limit(key: str, limit: int, window: int) -> None:
    from backend.main import _REDIS_CLIENT
    from backend.rate_limiting import consume_rate_limit

    allowed, retry_after = consume_rate_limit(_REDIS_CLIENT, f"speaking-feedback:{key}:{window}", limit=limit, window_seconds=window)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.", headers={"Retry-After": str(retry_after)})


# ---------------------------------------------------------------------------
# Audio files
# ---------------------------------------------------------------------------

def _secret() -> bytes:
    from backend.main import MEDIA_STREAM_TOKEN_SECRET

    return str(MEDIA_STREAM_TOKEN_SECRET).encode("utf-8")


def _signature(filename: str, viewer_id: int, exp_ts: int) -> str:
    payload = f"speaking-feedback:{filename}:{int(viewer_id)}:{int(exp_ts)}"
    return hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def audio_url(filename: str, viewer_id: int) -> str | None:
    """Short-lived signed URL (backend path) for one private audio file."""
    if not filename or not _FILE_RE.match(filename):
        return None
    exp_ts = ((int(time.time()) + AUDIO_URL_TTL) // 600 + 1) * 600
    token = f"{exp_ts}.{int(viewer_id)}.{_signature(filename, viewer_id, exp_ts)}"
    return f"/speaking/feedback/audio/{filename}?t={token}"


def verify_audio_token(filename: str, token: str) -> bool:
    parts = str(token or "").split(".", 2)
    if len(parts) != 3 or not _FILE_RE.match(filename or ""):
        return False
    try:
        exp_ts, viewer_id = int(parts[0]), int(parts[1])
    except ValueError:
        return False
    if exp_ts < int(time.time()):
        return False
    return hmac.compare_digest(_signature(filename, viewer_id, exp_ts), parts[2].strip().lower())


def _is_mp4(raw: bytes) -> bool:
    return len(raw) > 12 and raw[4:8] == b"ftyp"


def _is_webm_or_ogg(raw: bytes) -> bool:
    return raw[:4] == b"\x1a\x45\xdf\xa3" or raw[:4] == b"OggS"


def _new_filename(kind: str, request_id: int) -> str:
    return f"{kind}_{int(request_id)}_{secrets.token_hex(12)}.m4a"


def _path_for(filename: str) -> Path:
    if not _FILE_RE.match(filename or ""):
        raise HTTPException(status_code=404, detail="Audio not found")
    root = AUDIO_DIR.resolve()
    target = (root / filename).resolve()
    if target.parent != root:
        raise HTTPException(status_code=404, detail="Audio not found")
    return target


async def _read_upload(file: UploadFile) -> bytes:
    raw = await file.read(MAX_AUDIO_BYTES + 1)
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The recording is too long (max 10 MB).")
    if len(raw) < MIN_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="The recording is too short.")
    return raw


def _transcode_to_m4a(source: Path, target: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise HTTPException(status_code=503, detail="Audio conversion is not available on the server.")
    tmp = target.with_suffix(".tmp.m4a")
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-vn",
             "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(tmp)],
            check=True, capture_output=True, timeout=90,
        )
        tmp.replace(target)
    except subprocess.CalledProcessError as exc:
        logger.warning("speaking feedback transcode failed: %s", (exc.stderr or b"")[:300])
        raise HTTPException(status_code=422, detail="The recording could not be read. Please record again.")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=422, detail="The recording is too long.")
    finally:
        tmp.unlink(missing_ok=True)


async def _store_audio(raw: bytes, kind: str, request_id: int) -> str:
    """Saves an m4a (AAC) recording; browser WebM/Ogg is converted to m4a so
    every player (iOS included) can play it."""
    filename = _new_filename(kind, request_id)
    target = _path_for(filename)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    if _is_mp4(raw):
        tmp = target.with_suffix(".part")
        tmp.write_bytes(raw)
        tmp.replace(target)
        return filename
    if _is_webm_or_ogg(raw):
        source = target.with_suffix(".src")
        source.write_bytes(raw)
        try:
            await asyncio.to_thread(_transcode_to_m4a, source, target)
        finally:
            source.unlink(missing_ok=True)
        return filename
    raise HTTPException(status_code=422, detail="Unsupported audio format. Please record again in the app.")


def _delete_audio(filename: str) -> None:
    if not filename:
        return
    try:
        _path_for(filename).unlink(missing_ok=True)
    except HTTPException:
        pass


@router.get("/speaking/feedback/audio/{filename}")
@router.get("/api/speaking/feedback/audio/{filename}")
async def feedback_audio(filename: str, t: str = Query(default="", max_length=200)):
    if not verify_audio_token(filename, t):
        raise HTTPException(status_code=403, detail="This audio link has expired")
    path = _path_for(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(
        str(path),
        media_type="audio/mp4",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _json(raw: Any, fallback: Any) -> Any:
    try:
        value = json.loads(raw or "")
    except (TypeError, ValueError):
        return fallback
    return value if isinstance(value, type(fallback)) else fallback


def _name(row: dict[str, Any] | None) -> str:
    if not row:
        return ""
    return f"{str(row.get('first_name') or '').strip()} {str(row.get('last_name') or '').strip()}".strip()


def _public_ai(raw: Any) -> dict[str, Any]:
    result = _json(raw, {})
    keep = ("score", "max_score", "criteria", "summary", "strengths", "improvements", "grammar_errors",
            "vocabulary_suggestions", "pronunciation_notes", "improved_answer", "scale")
    return {key: result[key] for key in keep if key in result}


def _reply_payload(reply: dict[str, Any] | None, viewer_id: int) -> dict[str, Any] | None:
    if not reply:
        return None
    return {
        "reviewer_name": reply.get("reviewer_name") or "",
        "reviewer_role": reply.get("reviewer_role") or "",
        "feedback_text": reply.get("feedback_text") or "",
        "audio_url": audio_url(str(reply.get("audio_file") or ""), viewer_id),
        "band": reply.get("band"),
        "criteria": _json(reply.get("criteria_json"), {}),
        "corrections": _json(reply.get("corrections_json"), []),
        "retry_task": reply.get("retry_task") or "",
        "created_at": _iso(reply.get("created_at")),
        "updated_at": _iso(reply.get("updated_at")),
    }


def _request_payload(row: dict[str, Any], viewer_id: int, *, reply: dict[str, Any] | None = None,
                     student_name: str = "", reviewer_name: str = "", full: bool = True) -> dict[str, Any]:
    scale = "ielts" if row.get("subject") == "english" else "ten"
    item: dict[str, Any] = {
        "id": int(row["id"]),
        "subject": row.get("subject") or "english",
        "scale": scale,
        "max_score": 9.0 if scale == "ielts" else 10.0,
        "question_id": row.get("question_id"),
        "question_text": row.get("question_text") or "",
        "topic_title": row.get("topic_title") or "",
        "part": row.get("part"),
        "duration_seconds": float(row.get("duration_seconds") or 0),
        "ai_score": row.get("ai_score"),
        "student_note": row.get("student_note") or "",
        "status": row.get("status") or "pending",
        "student_status": row.get("student_status") or "new",
        "student_name": student_name,
        "reviewer_name": reviewer_name,
        "created_at": _iso(row.get("created_at")),
        "answered_at": _iso(row.get("answered_at")),
        "seen": row.get("student_seen_at") is not None,
    }
    if full:
        item.update(
            audio_url=audio_url(str(row.get("audio_file") or ""), viewer_id),
            transcript=row.get("transcript") or "",
            ai=_public_ai(row.get("ai_result_json")),
            reply=_reply_payload(reply, viewer_id),
        )
    return item


def _replies_for(cur, ids: list[int]) -> dict[int, dict[str, Any]]:
    if not ids:
        return {}
    cur.execute("SELECT * FROM speaking_feedback_replies WHERE request_id = ANY(%s)", (ids,))
    return {int(dict(r)["request_id"]): dict(r) for r in cur.fetchall() or []}


def _names_for(cur, ids: set[int]) -> dict[int, str]:
    clean = sorted({int(i) for i in ids if i})
    if not clean:
        return {}
    cur.execute("SELECT id, first_name, last_name FROM users WHERE id = ANY(%s)", (clean,))
    return {int(dict(r)["id"]): _name(dict(r)) or f"#{int(dict(r)['id'])}" for r in cur.fetchall() or []}


# ---------------------------------------------------------------------------
# Student endpoints (Speaking app)
# ---------------------------------------------------------------------------

def _analysis_for(cur, student_id: int, client_recording_id: str) -> dict[str, Any] | None:
    if not client_recording_id:
        return None
    try:
        cur.execute(
            "SELECT * FROM speaking_answer_analyses WHERE user_id=%s AND client_recording_id=%s LIMIT 1",
            (student_id, client_recording_id),
        )
        row = cur.fetchone()
    except Exception:
        cur.connection.rollback()
        return None
    return dict(row) if row else None


def _question_info(cur, question_id: int | None) -> dict[str, Any]:
    if not question_id:
        return {}
    try:
        cur.execute(
            """SELECT q.id, q.question_text, COALESCE(q.part, t.part) AS part, t.title AS topic_title,
                      LOWER(COALESCE(q.subject, t.subject, 'english')) AS subject
               FROM speaking_questions q JOIN speaking_topics t ON t.id=q.topic_id WHERE q.id=%s""",
            (int(question_id),),
        )
        row = cur.fetchone()
    except Exception:
        cur.connection.rollback()
        return {}
    return dict(row) if row else {}


def _notify_reviewers_async(request_id: int, topic: str) -> None:
    """Website / Teachers app notification for assigned reviewers. Optional:
    failures never break a send."""
    def run() -> None:
        try:
            from backend.main import _role_from_login_type, _store_browser_notification_for_user

            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    """SELECT u.id, u.login_type, u.login_id FROM speaking_feedback_reviewers r
                       JOIN users u ON u.id=r.user_id WHERE COALESCE(u.blocked, 0)=0"""
                )
                reviewers = [dict(r) for r in cur.fetchall() or []]
            finally:
                cur.close()
                conn.close()
            for reviewer in reviewers[:200]:
                role = _role_from_login_type(int(reviewer.get("login_type") or 1), str(reviewer.get("login_id") or ""))
                if role not in {"teacher", "support"}:
                    continue
                _store_browser_notification_for_user(
                    int(reviewer["id"]),
                    notification_type="speaking_feedback",
                    title="Speaking feedback",
                    message=f"Yangi javob tekshiruvni kutmoqda: {topic[:80]}",
                    button_text="Ochish",
                    button_url=f"/?role={role}&section=speaking-feedback",
                    target_screen="speaking_feedback",
                    source_key=f"speaking_feedback_{int(request_id)}_{int(reviewer['id'])}",
                    meta={"request_id": int(request_id)},
                )
        except Exception:
            logger.debug("speaking feedback reviewer notification failed", exc_info=True)

    threading.Thread(target=run, daemon=True).start()


@router.post("/speaking/feedback/requests")
@router.post("/api/speaking/feedback/requests")
async def send_to_teacher(
    file: UploadFile = File(...),
    client_recording_id: str = Form(default="", max_length=120),
    question_id: str = Form(default="", max_length=32),
    question_text: str = Form(default="", max_length=1200),
    topic_title: str = Form(default="", max_length=300),
    subject: str = Form(default="english", max_length=32),
    part: int | None = Form(default=None, ge=1, le=3),
    duration_seconds: float = Form(default=0.0, ge=0, le=900),
    note: str = Form(default="", max_length=600),
    authorization: str | None = Header(default=None),
):
    user = _student(authorization)
    ensure_tables()
    student_id = int(user.get("id") or 0)
    recording_ref = re.sub(r"[^A-Za-z0-9_.:-]", "", client_recording_id)[:120]
    raw = await _read_upload(file)
    if not _is_mp4(raw):
        raise HTTPException(status_code=422, detail="Unsupported audio format. Please record again in the app.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        if recording_ref:
            cur.execute(
                """SELECT * FROM speaking_feedback_requests WHERE student_id=%s AND client_recording_id=%s
                   AND status <> 'answered' ORDER BY id DESC LIMIT 1""",
                (student_id, recording_ref),
            )
            existing = cur.fetchone()
            if existing:
                return {"request": _request_payload(dict(existing), student_id), "created": False}
        cur.execute(
            "SELECT COUNT(*) AS n FROM speaking_feedback_requests WHERE student_id=%s AND status <> 'answered'",
            (student_id,),
        )
        if int(dict(cur.fetchone() or {}).get("n") or 0) >= MAX_OPEN_REQUESTS:
            raise HTTPException(status_code=409, detail=f"You already have {MAX_OPEN_REQUESTS} answers waiting for a teacher.")
    finally:
        cur.close()
        conn.close()
    _rate_limit(f"send:{student_id}", DAILY_REQUEST_LIMIT, 86400)

    conn = get_conn()
    cur = conn.cursor()
    try:
        qid = int(question_id) if question_id.isdigit() else None
        info = _question_info(cur, qid)
        analysis = _analysis_for(cur, student_id, recording_ref)
        subject_key = "russian" if str(info.get("subject") or subject).lower().startswith(("rus", "ru")) else "english"
        cur.execute(
            """INSERT INTO speaking_feedback_requests
                 (student_id, subject, client_recording_id, analysis_id, question_id, question_text, topic_title, part,
                  duration_seconds, transcript, ai_score, ai_result_json, student_note)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                student_id, subject_key, recording_ref, int(analysis["id"]) if analysis else None,
                int(info["id"]) if info.get("id") else None,
                str(info.get("question_text") or question_text or "")[:1200],
                str(info.get("topic_title") or topic_title or "")[:300],
                info.get("part") or part, float(duration_seconds or 0),
                str((analysis or {}).get("transcript") or "")[:8000],
                (analysis or {}).get("score"),
                str((analysis or {}).get("result_json") or "{}"),
                " ".join(note.split())[:600],
            ),
        )
        row = dict(cur.fetchone())
        conn.commit()
    finally:
        cur.close()
        conn.close()
    try:
        filename = await _store_audio(raw, "req", int(row["id"]))
    except Exception:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM speaking_feedback_requests WHERE id=%s", (int(row["id"]),))
            conn.commit()
        finally:
            cur.close()
            conn.close()
        raise
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE speaking_feedback_requests SET audio_file=%s WHERE id=%s RETURNING *", (filename, int(row["id"])))
        row = dict(cur.fetchone())
        conn.commit()
    finally:
        cur.close()
        conn.close()
    _notify_reviewers_async(int(row["id"]), row.get("topic_title") or row.get("question_text") or "")
    return {"request": _request_payload(row, student_id), "created": True}


@router.get("/speaking/feedback/requests")
@router.get("/api/speaking/feedback/requests")
async def my_feedback_history(
    subject: str = Query(default="", max_length=32),
    authorization: str | None = Header(default=None),
):
    user = _student(authorization)
    ensure_tables()
    student_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        if subject:
            subject_key = "russian" if subject.lower().startswith(("rus", "ru")) else "english"
            cur.execute(
                "SELECT * FROM speaking_feedback_requests WHERE student_id=%s AND subject=%s ORDER BY created_at DESC LIMIT 200",
                (student_id, subject_key),
            )
        else:
            cur.execute(
                "SELECT * FROM speaking_feedback_requests WHERE student_id=%s ORDER BY created_at DESC LIMIT 200",
                (student_id,),
            )
        rows = [dict(r) for r in cur.fetchall() or []]
        replies = _replies_for(cur, [int(r["id"]) for r in rows])
        items = [_request_payload(r, student_id, reply=replies.get(int(r["id"]))) for r in rows]
        return {
            "items": items,
            "counts": {
                "waiting": sum(1 for r in rows if r["status"] != "answered"),
                "answered": sum(1 for r in rows if r["status"] == "answered"),
                "unseen": sum(1 for r in rows if r["status"] == "answered" and r.get("student_seen_at") is None),
            },
        }
    finally:
        cur.close()
        conn.close()


class StudentStatusInput(BaseModel):
    student_status: str = Field(pattern="^(resolved|practice_again)$")


def _own_request(cur, request_id: int, student_id: int) -> dict[str, Any]:
    cur.execute("SELECT * FROM speaking_feedback_requests WHERE id=%s AND student_id=%s", (int(request_id), int(student_id)))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Feedback request not found")
    return dict(row)


@router.post("/speaking/feedback/requests/{request_id}/seen")
@router.post("/api/speaking/feedback/requests/{request_id}/seen")
async def mark_seen(request_id: int, authorization: str | None = Header(default=None)):
    user = _student(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        row = _own_request(cur, request_id, int(user.get("id") or 0))
        if row["status"] == "answered" and row.get("student_seen_at") is None:
            cur.execute("UPDATE speaking_feedback_requests SET student_seen_at=NOW() WHERE id=%s", (int(request_id),))
            conn.commit()
        return {"ok": True}
    finally:
        cur.close()
        conn.close()


@router.post("/speaking/feedback/requests/{request_id}/status")
@router.post("/api/speaking/feedback/requests/{request_id}/status")
async def set_student_status(request_id: int, payload: StudentStatusInput, authorization: str | None = Header(default=None)):
    user = _student(authorization)
    ensure_tables()
    student_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        row = _own_request(cur, request_id, student_id)
        if row["status"] != "answered":
            raise HTTPException(status_code=409, detail="The teacher has not answered yet")
        cur.execute(
            """UPDATE speaking_feedback_requests SET student_status=%s, student_seen_at=COALESCE(student_seen_at, NOW()),
                 updated_at=NOW() WHERE id=%s RETURNING *""",
            (payload.student_status, int(request_id)),
        )
        updated = dict(cur.fetchone())
        replies = _replies_for(cur, [int(request_id)])
        conn.commit()
        return {"request": _request_payload(updated, student_id, reply=replies.get(int(request_id)))}
    finally:
        cur.close()
        conn.close()


@router.delete("/speaking/feedback/requests/{request_id}")
@router.delete("/api/speaking/feedback/requests/{request_id}")
async def cancel_request(request_id: int, authorization: str | None = Header(default=None)):
    user = _student(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        row = _own_request(cur, request_id, int(user.get("id") or 0))
        if row["status"] == "answered":
            raise HTTPException(status_code=409, detail="An answered request stays in your history")
        cur.execute("DELETE FROM speaking_feedback_requests WHERE id=%s", (int(request_id),))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    _delete_audio(str(row.get("audio_file") or ""))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Reviewer endpoints (website: Speaking admin / teacher / support; Teachers app)
# ---------------------------------------------------------------------------

@router.get("/staff/speaking/feedback/access")
async def reviewer_access(authorization: str | None = Header(default=None)):
    user, role = _user(authorization)
    allowed = role in REVIEWER_ROLES and has_reviewer_access(user, role)
    return {"allowed": allowed, "role": role, "can_manage_reviewers": role == "speaking_admin"}


def _list_filter(status: str, subject: str, q: str, reviewer_id: int, mine: bool) -> tuple[str, list[Any]]:
    where, params = ["1=1"], []
    if status == "open":
        where.append("r.status <> 'answered'")
    elif status in REQUEST_STATUSES:
        where.append("r.status=%s")
        params.append(status)
    if subject in {"english", "russian"}:
        where.append("r.subject=%s")
        params.append(subject)
    if mine:
        where.append("r.reviewer_id=%s")
        params.append(reviewer_id)
    if q:
        needle = f"%{q.casefold()}%"
        where.append(
            "(LOWER(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) LIKE %s "
            "OR LOWER(r.topic_title) LIKE %s OR LOWER(r.question_text) LIKE %s)"
        )
        params.extend([needle, needle, needle])
    return " AND ".join(where), params


@router.get("/staff/speaking/feedback/requests")
async def reviewer_list(
    status: str = Query(default="open", max_length=16),
    subject: str = Query(default="", max_length=16),
    q: str = Query(default="", max_length=80),
    mine: bool = Query(default=False),
    authorization: str | None = Header(default=None),
):
    user, _ = _reviewer(authorization)
    ensure_tables()
    reviewer_id = int(user.get("id") or 0)
    where, params = _list_filter(status, subject, " ".join(q.split()), reviewer_id, mine)
    # Oldest open answers first so nobody waits long; answered newest first.
    order = "r.answered_at DESC" if status == "answered" else "r.created_at ASC"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""SELECT r.id, r.student_id, r.subject, r.question_id, r.question_text, r.topic_title, r.part,
                       r.duration_seconds, r.ai_score, r.student_note, r.status, r.student_status, r.reviewer_id,
                       r.created_at, r.answered_at, r.student_seen_at, u.first_name, u.last_name
                FROM speaking_feedback_requests r LEFT JOIN users u ON u.id = r.student_id
                WHERE {where} ORDER BY {order}, r.id LIMIT 300""",
            params,
        )
        rows = [dict(r) for r in cur.fetchall() or []]
        reviewers = _names_for(cur, {int(r["reviewer_id"]) for r in rows if r.get("reviewer_id")})
        cur.execute("SELECT status, COUNT(*) AS n FROM speaking_feedback_requests GROUP BY status")
        counts = {s: 0 for s in REQUEST_STATUSES}
        for row in cur.fetchall() or []:
            counts[str(dict(row)["status"])] = int(dict(row)["n"] or 0)
        items = [
            _request_payload(r, reviewer_id, student_name=_name(r) or f"#{r['student_id']}",
                             reviewer_name=reviewers.get(int(r["reviewer_id"] or 0), ""), full=False)
            for r in rows
        ]
        return {"items": items, "counts": {**counts, "open": counts["pending"] + counts["in_review"]}}
    finally:
        cur.close()
        conn.close()


def _student_progress(cur, student_id: int, subject: str, exclude_analysis: int | None) -> dict[str, Any]:
    """Previous answers and a compact progress summary of one student."""
    try:
        cur.execute(
            """SELECT id, score, criteria_json, prompt, topic_title, part, transcript, duration_seconds, created_at
               FROM speaking_answer_analyses WHERE user_id=%s AND subject=%s ORDER BY created_at DESC LIMIT 60""",
            (student_id, subject),
        )
        rows = [dict(r) for r in cur.fetchall() or []]
    except Exception:
        cur.connection.rollback()
        rows = []
    previous = [
        {
            "id": int(r["id"]), "score": r.get("score"), "prompt": str(r.get("prompt") or "")[:300],
            "topic_title": r.get("topic_title") or "", "part": r.get("part"),
            "transcript": str(r.get("transcript") or "")[:1200],
            "duration_seconds": float(r.get("duration_seconds") or 0), "created_at": _iso(r.get("created_at")),
        }
        for r in rows if int(r["id"]) != int(exclude_analysis or 0)
    ][:10]
    scores = [float(r.get("score") or 0) for r in rows]
    criteria: dict[str, list[float]] = {}
    for r in rows:
        for key, value in _json(r.get("criteria_json"), {}).items():
            try:
                criteria.setdefault(str(key), []).append(float(value))
            except (TypeError, ValueError):
                continue
    trend = [{"score": float(r.get("score") or 0), "created_at": _iso(r.get("created_at"))} for r in reversed(rows[:20])]
    half = max(1, min(5, len(scores) // 2))
    change = round(sum(scores[:half]) / half - sum(scores[-half:]) / half, 2) if len(scores) >= 2 else None
    try:
        cur.execute(
            """SELECT r.id, r.question_text, r.topic_title, r.created_at, r.student_status, p.band
               FROM speaking_feedback_requests r LEFT JOIN speaking_feedback_replies p ON p.request_id=r.id
               WHERE r.student_id=%s AND r.status='answered' ORDER BY r.answered_at DESC LIMIT 5""",
            (student_id,),
        )
        past_feedback = [
            {"id": int(dict(r)["id"]), "question_text": str(dict(r)["question_text"] or "")[:200],
             "topic_title": dict(r)["topic_title"] or "", "band": dict(r)["band"],
             "student_status": dict(r)["student_status"], "created_at": _iso(dict(r)["created_at"])}
            for r in cur.fetchall() or []
        ]
    except Exception:
        cur.connection.rollback()
        past_feedback = []
    return {
        "previous_answers": previous,
        "past_feedback": past_feedback,
        "progress": {
            "answers": len(rows),
            "average_score": round(sum(scores) / len(scores), 2) if scores else None,
            "best_score": max(scores) if scores else None,
            # Newest minus oldest window: positive = improving.
            "change": change,
            "criteria": {k: round(sum(v) / len(v), 2) for k, v in criteria.items() if v},
            "trend": trend,
        },
    }


@router.get("/staff/speaking/feedback/requests/{request_id}")
async def reviewer_detail(
    request_id: int,
    status: str = Query(default="open", max_length=16),
    subject: str = Query(default="", max_length=16),
    q: str = Query(default="", max_length=80),
    mine: bool = Query(default=False),
    authorization: str | None = Header(default=None),
):
    user, _ = _reviewer(authorization)
    ensure_tables()
    reviewer_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT r.*, u.first_name, u.last_name FROM speaking_feedback_requests r
               LEFT JOIN users u ON u.id=r.student_id WHERE r.id=%s""",
            (int(request_id),),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Feedback request not found")
        row = dict(row)
        replies = _replies_for(cur, [int(request_id)])
        reviewer_names = _names_for(cur, {int(row["reviewer_id"])} if row.get("reviewer_id") else set())
        extra = _student_progress(cur, int(row["student_id"]), row["subject"], row.get("analysis_id"))
        # Neighbours in the same filtered list, for prev/next and swiping.
        where, params = _list_filter(status, subject, " ".join(q.split()), reviewer_id, mine)
        order = "r.answered_at DESC" if status == "answered" else "r.created_at ASC"
        cur.execute(
            f"""SELECT r.id FROM speaking_feedback_requests r LEFT JOIN users u ON u.id = r.student_id
                WHERE {where} ORDER BY {order}, r.id LIMIT 300""",
            params,
        )
        ids = [int(dict(r)["id"]) for r in cur.fetchall() or []]
    finally:
        cur.close()
        conn.close()
    position = ids.index(int(request_id)) if int(request_id) in ids else -1
    payload = _request_payload(
        row, reviewer_id, reply=replies.get(int(request_id)), student_name=_name(row) or f"#{row['student_id']}",
        reviewer_name=reviewer_names.get(int(row.get("reviewer_id") or 0), ""),
    )
    payload.update(extra)
    payload["navigation"] = {
        "position": position + 1 if position >= 0 else None,
        "total": len(ids),
        "previous_id": ids[position - 1] if position > 0 else None,
        "next_id": ids[position + 1] if 0 <= position < len(ids) - 1 else None,
    }
    return {"request": payload}


@router.post("/staff/speaking/feedback/requests/{request_id}/claim")
async def reviewer_claim(request_id: int, authorization: str | None = Header(default=None)):
    """Marks an answer "in review" by this reviewer so others skip it."""
    user, _ = _reviewer(authorization)
    ensure_tables()
    reviewer_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE speaking_feedback_requests SET status='in_review', reviewer_id=%s, claimed_at=NOW(), updated_at=NOW()
               WHERE id=%s AND (status='pending' OR (status='in_review' AND (reviewer_id=%s OR claimed_at < NOW() - INTERVAL '2 hours')))
               RETURNING id""",
            (reviewer_id, int(request_id), reviewer_id),
        )
        claimed = cur.fetchone() is not None
        conn.commit()
        return {"ok": claimed}
    finally:
        cur.close()
        conn.close()


def _clean_text(value: Any, limit: int) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    return "\n".join(" ".join(line.split()) for line in text.split("\n"))[:limit]


def clean_corrections(raw: Any) -> list[dict[str, str]]:
    items = raw if isinstance(raw, list) else []
    result = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        original = _clean_text(item.get("original"), 300)
        correction = _clean_text(item.get("correction"), 300)
        note = _clean_text(item.get("note"), 400)
        if original or correction:
            result.append({"original": original, "correction": correction, "note": note})
    return result


def clean_criteria(raw: Any, max_score: float) -> dict[str, float]:
    result: dict[str, float] = {}
    if not isinstance(raw, dict):
        return result
    for key in ("fluency", "vocabulary", "grammar", "pronunciation"):
        try:
            value = float(raw.get(key))
        except (TypeError, ValueError):
            continue
        if 0 <= value <= max_score:
            result[key] = round(value * 2) / 2
    return result


@router.post("/staff/speaking/feedback/requests/{request_id}/reply")
async def reviewer_reply(
    request_id: int,
    feedback_text: str = Form(default="", max_length=6000),
    band: str = Form(default="", max_length=8),
    criteria: str = Form(default="{}", max_length=2000),
    corrections: str = Form(default="[]", max_length=20000),
    retry_task: str = Form(default="", max_length=2000),
    remove_audio: bool = Form(default=False),
    audio: UploadFile | None = File(default=None),
    authorization: str | None = Header(default=None),
):
    user, role = _reviewer(authorization)
    ensure_tables()
    reviewer_id = int(user.get("id") or 0)
    _rate_limit(f"reply:{reviewer_id}", 300, 3600)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_feedback_requests WHERE id=%s", (int(request_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Feedback request not found")
        row = dict(row)
        cur.execute("SELECT * FROM speaking_feedback_replies WHERE request_id=%s", (int(request_id),))
        existing = cur.fetchone()
        existing = dict(existing) if existing else None
    finally:
        cur.close()
        conn.close()
    if existing and int(existing["reviewer_id"]) != reviewer_id and role != "speaking_admin":
        raise HTTPException(status_code=409, detail="Another reviewer already answered this request")

    max_score = 9.0 if row["subject"] == "english" else 10.0
    band_value: float | None = None
    if band.strip():
        try:
            band_value = round(float(band) * 2) / 2
        except ValueError:
            raise HTTPException(status_code=422, detail="Band must be a number")
        if not 0 <= band_value <= max_score:
            raise HTTPException(status_code=422, detail=f"Band must be between 0 and {max_score:g}")
    text = _clean_text(feedback_text, 6000)
    task = _clean_text(retry_task, 2000)
    try:
        corrections_list = clean_corrections(json.loads(corrections or "[]"))
        criteria_map = clean_criteria(json.loads(criteria or "{}"), max_score)
    except ValueError:
        raise HTTPException(status_code=422, detail="Corrections or criteria are not valid JSON")

    audio_file = str((existing or {}).get("audio_file") or "")
    new_audio = ""
    if audio is not None and (audio.filename or audio.size):
        raw = await _read_upload(audio)
        new_audio = await _store_audio(raw, "rep", int(request_id))
    if not (text or new_audio or (audio_file and not remove_audio) or band_value is not None or corrections_list or task):
        _delete_audio(new_audio)
        raise HTTPException(status_code=422, detail="Write feedback or record an audio comment first")
    old_audio = ""
    if new_audio:
        old_audio, audio_file = audio_file, new_audio
    elif remove_audio:
        old_audio, audio_file = audio_file, ""

    reviewer_name = _name(user) or ("Speaking admin" if role == "speaking_admin" else "Teacher")
    first_answer = existing is None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_feedback_replies
                 (request_id, reviewer_id, reviewer_name, reviewer_role, feedback_text, audio_file, band, criteria_json,
                  corrections_json, retry_task)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (request_id) DO UPDATE SET reviewer_id=EXCLUDED.reviewer_id, reviewer_name=EXCLUDED.reviewer_name,
                 reviewer_role=EXCLUDED.reviewer_role, feedback_text=EXCLUDED.feedback_text, audio_file=EXCLUDED.audio_file,
                 band=EXCLUDED.band, criteria_json=EXCLUDED.criteria_json, corrections_json=EXCLUDED.corrections_json,
                 retry_task=EXCLUDED.retry_task, updated_at=NOW()
               RETURNING *""",
            (int(request_id), reviewer_id, reviewer_name, role, text, audio_file, band_value,
             json.dumps(criteria_map), json.dumps(corrections_list, ensure_ascii=False), task),
        )
        reply = dict(cur.fetchone())
        cur.execute(
            """UPDATE speaking_feedback_requests SET status='answered', reviewer_id=%s, answered_at=COALESCE(answered_at, NOW()),
                 student_status=CASE WHEN %s THEN 'new' ELSE student_status END,
                 student_seen_at=CASE WHEN %s THEN NULL ELSE student_seen_at END, updated_at=NOW()
               WHERE id=%s RETURNING *""",
            (reviewer_id, first_answer, first_answer, int(request_id)),
        )
        updated = dict(cur.fetchone())
        conn.commit()
    except Exception:
        conn.rollback()
        _delete_audio(new_audio)
        raise
    finally:
        cur.close()
        conn.close()
    if old_audio and old_audio != audio_file:
        _delete_audio(old_audio)
    _push_student(int(row["student_id"]), int(request_id), row.get("topic_title") or "", updated["subject"], first_answer)
    return {"request": _request_payload(updated, reviewer_id, reply=reply)}


def _push_student(student_id: int, request_id: int, topic: str, subject: str, first: bool) -> None:
    russian = subject == "russian"
    title = ("Преподаватель ответил" if russian else "Teacher feedback") if first else (
        "Отзыв обновлён" if russian else "Feedback updated")
    body = (f"Отзыв на ваш ответ: {topic}" if russian else f"Your teacher reviewed your answer: {topic}")[:140]
    data = {"target_screen": "speaking_teacher_feedback", "notification_type": "speaking_teacher_feedback",
            "request_id": str(request_id)}

    def run() -> None:
        try:
            import push_notifications

            push_notifications.send_push_to_speaking_user(student_id, title, body, data=data)
        except Exception:
            logger.debug("speaking feedback push failed", exc_info=True)

    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------------------
# Reviewer management (Speaking admin)
# ---------------------------------------------------------------------------

class ReviewerInput(BaseModel):
    user_id: int = Field(ge=1)


def _staff_rows(cur, ids: list[int] | None = None, q: str = "", limit: int = 60) -> list[dict[str, Any]]:
    from backend.main import _role_from_login_type

    params: list[Any] = []
    where = ["login_type IN (3, 5)", "COALESCE(blocked, 0)=0", "COALESCE(screenshot_demo, 0)=0"]
    if ids is not None:
        if not ids:
            return []
        where.append("id = ANY(%s)")
        params.append(ids)
    if q:
        needle = f"%{q.casefold()}%"
        where.append("(LOWER(COALESCE(first_name,'') || ' ' || COALESCE(last_name,'')) LIKE %s OR LOWER(COALESCE(subject,'')) LIKE %s)")
        params.extend([needle, needle])
    cur.execute(
        f"""SELECT id, first_name, last_name, login_id, login_type, subject FROM users
            WHERE {' AND '.join(where)} ORDER BY first_name, last_name, id LIMIT %s""",
        [*params, limit],
    )
    result = []
    for row in cur.fetchall() or []:
        row = dict(row)
        role = _role_from_login_type(int(row.get("login_type") or 1), str(row.get("login_id") or ""))
        if role not in {"teacher", "support"}:
            continue
        result.append({"id": int(row["id"]), "name": _name(row) or f"#{row['id']}", "role": role,
                       "subject": str(row.get("subject") or "")})
    return result


@router.get("/staff/speaking/feedback/reviewers")
async def list_reviewers(q: str = Query(default="", max_length=80), authorization: str | None = Header(default=None)):
    _speaking_admin(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT user_id, created_at FROM speaking_feedback_reviewers ORDER BY created_at")
        assigned_rows = {int(dict(r)["user_id"]): dict(r) for r in cur.fetchall() or []}
        assigned = _staff_rows(cur, list(assigned_rows))
        cur.execute(
            """SELECT reviewer_id, COUNT(*) AS n FROM speaking_feedback_requests
               WHERE status='answered' AND reviewer_id IS NOT NULL GROUP BY reviewer_id"""
        )
        answered = {int(dict(r)["reviewer_id"]): int(dict(r)["n"] or 0) for r in cur.fetchall() or []}
        for item in assigned:
            item["assigned_at"] = _iso(assigned_rows[item["id"]].get("created_at"))
            item["answered"] = answered.get(item["id"], 0)
        candidates = [c for c in _staff_rows(cur, None, " ".join(q.split())) if c["id"] not in assigned_rows]
        return {"assigned": assigned, "candidates": candidates[:40]}
    finally:
        cur.close()
        conn.close()


@router.post("/staff/speaking/feedback/reviewers")
async def add_reviewer(payload: ReviewerInput, authorization: str | None = Header(default=None)):
    admin = _speaking_admin(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if not _staff_rows(cur, [int(payload.user_id)]):
            raise HTTPException(status_code=422, detail="Only an active teacher or support teacher can be assigned")
        cur.execute(
            "INSERT INTO speaking_feedback_reviewers (user_id, assigned_by) VALUES (%s,%s) ON CONFLICT (user_id) DO NOTHING",
            (int(payload.user_id), int(admin.get("id") or 0)),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    _clear_app_state_cache()
    return {"ok": True}


@router.delete("/staff/speaking/feedback/reviewers/{user_id}")
async def remove_reviewer(user_id: int, authorization: str | None = Header(default=None)):
    _speaking_admin(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_feedback_reviewers WHERE user_id=%s", (int(user_id),))
        # Answers this reviewer had claimed go back to the queue.
        cur.execute(
            "UPDATE speaking_feedback_requests SET status='pending', reviewer_id=NULL, claimed_at=NULL WHERE reviewer_id=%s AND status='in_review'",
            (int(user_id),),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    _clear_app_state_cache()
    return {"ok": True}


def _clear_app_state_cache() -> None:
    try:
        from backend.main import _APP_STATE_BOOT_CACHE

        _APP_STATE_BOOT_CACHE.clear()
    except Exception:
        pass

