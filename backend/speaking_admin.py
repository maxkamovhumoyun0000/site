"""
Diamond Speaking Questions — Backend & Media Admin API.
Handles dynamic topics, questions, vocabulary, Band 8-9 sample answers,
AI generation (via Diamondvoy / xAI / Gemini), and broadcast push notifications.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from db import get_conn
import push_notifications
from speaking_contract import (
    MAX_BATCH_TOPIC_COUNT,
    MAX_QUESTION_GENERATION_COUNT,
    display_topic_status,
    individual_ai_topic_generation_count,
    minimum_questions_for_requested_limit,
    normalize_batch_topic_count,
    normalize_question_generation_count,
    normalize_topic_status,
    part_two_cue_card_fallback,
    public_sample_answer,
    question_insert_values_for_topic,
    variable_batch_question_targets,
)

logger = logging.getLogger(__name__)
router = APIRouter()

AI_PRIMARY_GENERATION_TIMEOUT_SECONDS = 90
AI_FALLBACK_GENERATION_TIMEOUT_SECONDS = 60
# A provider can be slow without being unavailable.  Jobs retry a timed-out
# provider once with this bounded extended window before moving to fallback.
AI_PRIMARY_RETRY_GENERATION_TIMEOUT_SECONDS = 150
AI_FALLBACK_RETRY_GENERATION_TIMEOUT_SECONDS = 120

MEDIA_STAFF_ROLES = {"media", "media_admin", "admin", "superadmin", "developer", "teacher", "support"}


def _auth_staff(authorization: str | None) -> dict[str, Any]:
    from backend.main import _require_role, _user_row_from_bearer
    user = _user_row_from_bearer(authorization)
    _require_role(user, MEDIA_STAFF_ROLES)
    return user


def ensure_speaking_tables() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_topics (
                id SERIAL PRIMARY KEY,
                part INTEGER NOT NULL,
                title TEXT NOT NULL,
                status_badge TEXT DEFAULT 'PREDICTED',
                sort_order INTEGER DEFAULT 0,
                subject TEXT DEFAULT 'english',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_questions (
                id SERIAL PRIMARY KEY,
                topic_id INTEGER NOT NULL REFERENCES speaking_topics(id) ON DELETE CASCADE,
                part INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                cue_card_bullet_points TEXT,
                sample_answer TEXT,
                examiner_tip TEXT,
                vocabulary_json TEXT,
                sort_order INTEGER DEFAULT 0,
                subject TEXT DEFAULT 'english',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_push_tokens (
                id SERIAL PRIMARY KEY,
                device_id TEXT NOT NULL UNIQUE,
                token TEXT NOT NULL,
                platform TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_notifications (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                target_part INTEGER,
                target_topic_id INTEGER,
                sent_by_user_id INTEGER,
                recipient_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'sent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS speaking_ai_generation_jobs (
                id BIGSERIAL PRIMARY KEY,
                created_by_user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress_percent INTEGER NOT NULL DEFAULT 0,
                stage TEXT NOT NULL DEFAULT 'Queued',
                request_json TEXT NOT NULL,
                result_json TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

        # Ensure subject column exists in existing tables
        for table in ("speaking_topics", "speaking_questions"):
            try:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN subject TEXT DEFAULT 'english'")
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("ensure_speaking_tables failed")
    finally:
        conn.close()


# --- Pydantic Request Models ---
class PushTokenRegisterRequest(BaseModel):
    device_id: str
    token: str
    platform: str = "android"
    app: str = "speaking"


class TopicCreateRequest(BaseModel):
    part: int = Field(default=1, ge=1, le=3)
    title: str = Field(..., min_length=1, max_length=180)
    status_badge: str = Field(default="PREDICTED", max_length=50)
    sort_order: int = 0
    subject: str = Field(default="english", max_length=32)


class TopicUpdateRequest(BaseModel):
    part: int | None = Field(default=None, ge=1, le=3)
    title: str | None = Field(default=None, min_length=1, max_length=180)
    status_badge: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None
    subject: str | None = None


class QuestionCreateRequest(BaseModel):
    part: int = Field(default=1, ge=1, le=3)
    question_text: str = Field(..., min_length=1, max_length=3000)
    cue_card_bullet_points: list[str] = Field(default_factory=list, max_length=6)
    sample_answer: str = Field(default="Sample answer to be reviewed.", max_length=15000)
    examiner_tip: str | None = None
    vocabulary: list[dict[str, Any]] = Field(default_factory=list)
    sort_order: int = 0
    subject: str = Field(default="english", max_length=32)


class QuestionUpdateRequest(BaseModel):
    question_text: str | None = None
    cue_card_bullet_points: list[str] | None = None
    sample_answer: str | None = None
    examiner_tip: str | None = None
    vocabulary: list[dict[str, Any]] | None = None
    sort_order: int | None = None
    subject: str | None = None


class AiGenerateRequest(BaseModel):
    theme: str | None = None
    part: int = Field(default=1, ge=1, le=3)
    question_count: int = Field(default=2, ge=1, le=MAX_QUESTION_GENERATION_COUNT)
    topic_count: int = Field(default=1, ge=1, le=MAX_BATCH_TOPIC_COUNT)
    custom_instruction: str | None = None
    question_text: str | None = None
    existing_topic_id: int | None = Field(default=None, ge=1)
    subject: str = Field(default="english", max_length=32)


class BatchQuestionCreateRequest(BaseModel):
    question_text: str = Field(..., min_length=1, max_length=3000)
    cue_card_bullet_points: list[str] = Field(default_factory=list, max_length=6)
    sample_answer: str = Field(default="", max_length=15000)
    examiner_tip: str | None = None
    vocabulary: list[dict[str, Any]] = Field(default_factory=list)
    sort_order: int = 0


class BatchTopicCreateItem(BaseModel):
    part: int = Field(default=1, ge=1, le=3)
    title: str = Field(..., min_length=1, max_length=180)
    status_badge: str = Field(default="PREDICTED", max_length=50)
    sort_order: int = 0
    questions: list[BatchQuestionCreateRequest] = Field(..., min_length=1, max_length=10)


class TopicBatchCreateRequest(BaseModel):
    subject: str = Field(default="english", max_length=32)
    topics: list[BatchTopicCreateItem] = Field(..., min_length=1, max_length=MAX_BATCH_TOPIC_COUNT)


class NotificationSendRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=180)
    body: str = Field(..., min_length=5, max_length=500)
    target_part: int | None = None
    target_topic_id: int | None = None


# --- PUBLIC API (FOR FLUTTER APP) ---
@router.get("/api/speaking/content")
@router.get("/speaking/content")
async def get_speaking_content(
    request: Request,
    subject: str | None = Query(default=None),
):
    """Returns all topics and questions for Diamond Speaking Questions app."""
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        where_subj = ""
        params_t = []
        params_q = []
        if subject:
            where_subj = "WHERE LOWER(COALESCE(subject, 'english')) = ?"
            params_t.append(subject.lower())
            params_q.append(subject.lower())

        cur.execute(
            f"""
            SELECT id, part, title, status_badge, sort_order, COALESCE(subject, 'english') AS subject
            FROM speaking_topics
            {where_subj}
            ORDER BY part ASC, sort_order ASC, id ASC
            """,
            tuple(params_t),
        )
        topics = [dict(row) for row in (cur.fetchall() or [])]

        q_where = f"WHERE LOWER(COALESCE(q.subject, COALESCE(t.subject, 'english'))) = ?" if subject else ""
        cur.execute(
            f"""
            SELECT q.id, q.topic_id, q.part, q.question_text, q.cue_card_bullet_points,
                   q.sample_answer, q.examiner_tip, q.vocabulary_json, q.sort_order,
                   COALESCE(q.subject, COALESCE(t.subject, 'english')) AS subject,
                   t.title AS topic_title, t.status_badge
            FROM speaking_questions q
            JOIN speaking_topics t ON q.topic_id = t.id
            {q_where}
            ORDER BY q.part ASC, t.sort_order ASC, q.sort_order ASC, q.id ASC
            """,
            tuple(params_q),
        )
        q_rows = cur.fetchall() or []
        questions = []
        for r in q_rows:
            d = dict(r)
            bullet_points = []
            if d.get("part") == 2 and d.get("cue_card_bullet_points"):
                try:
                    bullet_points = json.loads(d["cue_card_bullet_points"])
                except Exception:
                    bullet_points = [d["cue_card_bullet_points"]]

            vocab_items = []
            if d.get("vocabulary_json"):
                try:
                    vocab_items = json.loads(d["vocabulary_json"])
                except Exception:
                    vocab_items = []

            subject = (d.get("subject") or "english").lower()
            questions.append({
                "id": str(d["id"]),
                "topic_id": d["topic_id"],
                "category": d.get("topic_title") or "General",
                "part": d["part"],
                "subject": subject,
                "prompt": d["question_text"],
                "bestAnswer": public_sample_answer(d.get("sample_answer"), subject),
                "tag": display_topic_status(d.get("status_badge")),
                "prompts": bullet_points,
                "examinerTip": None,
                "vocabulary": vocab_items,
            })

        payload = {"topics": topics, "questions": questions}
        # The mobile app sends this value back on its next sync. An unchanged
        # content set gets a tiny 304 response instead of downloading every
        # English and Russian question again.
        content_bytes = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        etag = f'"{hashlib.sha256(content_bytes).hexdigest()}"'
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return JSONResponse(content=payload, headers=headers)
    finally:
        conn.close()


@router.post("/api/speaking/push-token")
@router.post("/speaking/push-token")
async def register_speaking_push_token(payload: PushTokenRegisterRequest):
    """Anonymous device registration for push notifications."""
    ensure_speaking_tables()
    push_notifications.register_speaking_token(
        device_id=payload.device_id,
        token=payload.token,
        platform=payload.platform,
    )
    return {"message": "Token registered successfully"}


# --- STAFF MEDIA ADMIN API ---
@router.get("/staff/speaking/topics")
async def list_staff_topics(authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT t.id, t.part, t.title, t.status_badge, t.sort_order, t.created_at,
                   COALESCE(t.subject, 'english') AS subject,
                   COUNT(q.id) AS question_count
            FROM speaking_topics t
            LEFT JOIN speaking_questions q ON t.id = q.topic_id
            GROUP BY t.id, t.part, t.title, t.status_badge, t.sort_order, t.created_at, t.subject
            ORDER BY t.part ASC, t.sort_order ASC, t.id DESC
            """
        )
        topics = [dict(row) for row in (cur.fetchall() or [])]

        cur.execute(
            """
            SELECT id, topic_id, part, question_text, cue_card_bullet_points,
                   sample_answer, examiner_tip, vocabulary_json, sort_order,
                   COALESCE(subject, 'english') AS subject
            FROM speaking_questions
            ORDER BY part ASC, sort_order ASC, id ASC
            """
        )
        questions = []
        for r in cur.fetchall() or []:
            d = dict(r)
            if d.get("part") == 2 and d.get("cue_card_bullet_points"):
                try:
                    d["cue_card_bullet_points"] = json.loads(d["cue_card_bullet_points"])
                except Exception:
                    pass
            else:
                d["cue_card_bullet_points"] = []

            d["examiner_tip"] = None
            if d.get("vocabulary_json"):
                try:
                    d["vocabulary"] = json.loads(d["vocabulary_json"])
                except Exception:
                    d["vocabulary"] = []
            questions.append(d)

        return {"topics": topics, "questions": questions}
    finally:
        conn.close()


@router.post("/staff/speaking/topics")
async def create_staff_topic(payload: TopicCreateRequest, authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        subj = (payload.subject or "english").strip().lower()
        try:
            status_badge = normalize_topic_status(payload.status_badge)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        cur.execute(
            """
            INSERT INTO speaking_topics (part, title, status_badge, sort_order, subject)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id, part, title, status_badge, sort_order, subject
            """,
            (payload.part, payload.title.strip(), status_badge, payload.sort_order, subj),
        )
        row = cur.fetchone()
        conn.commit()
        return {"topic": dict(row)}
    finally:
        conn.close()


@router.post("/staff/speaking/topics/batch")
async def create_staff_topic_batch(payload: TopicBatchCreateRequest, authorization: str | None = Header(default=None)):
    """Create several topics and all of their questions atomically."""
    _auth_staff(authorization)
    ensure_speaking_tables()
    subject = (payload.subject or "english").strip().lower()
    conn = get_conn()
    cur = conn.cursor()
    try:
        created_topics = []
        for item in payload.topics:
            try:
                status_badge = normalize_topic_status(item.status_badge)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

            cur.execute(
                """
                INSERT INTO speaking_topics (part, title, status_badge, sort_order, subject)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id, part, title, status_badge, sort_order, subject
                """,
                (item.part, item.title.strip(), status_badge, item.sort_order, subject),
            )
            topic = dict(cur.fetchone())
            question_count = 0
            for question in item.questions:
                values = question_insert_values_for_topic(question, topic)
                cur.execute(
                    """
                    INSERT INTO speaking_questions (topic_id, part, question_text, cue_card_bullet_points, sample_answer, examiner_tip, vocabulary_json, sort_order, subject)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        topic["id"],
                        values["part"],
                        values["question_text"],
                        json.dumps(values["cue_card_bullet_points"]) if values["cue_card_bullet_points"] else None,
                        values["sample_answer"],
                        values["examiner_tip"],
                        json.dumps(values["vocabulary"]) if values["vocabulary"] else None,
                        values["sort_order"],
                        values["subject"],
                    ),
                )
                question_count += 1
            created_topics.append({**topic, "question_count": question_count})
        conn.commit()
        return {"topics": created_topics}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/staff/speaking/topics/{topic_id}")
async def update_staff_topic(topic_id: int, payload: TopicUpdateRequest, authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM speaking_topics WHERE id=?", (topic_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Topic not found")

        updates = []
        params = []
        if payload.part is not None:
            updates.append("part = ?")
            params.append(payload.part)
        if payload.title is not None:
            updates.append("title = ?")
            params.append(payload.title.strip())
        if payload.status_badge is not None:
            try:
                status_badge = normalize_topic_status(payload.status_badge)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            updates.append("status_badge = ?")
            params.append(status_badge)
        if payload.sort_order is not None:
            updates.append("sort_order = ?")
            params.append(payload.sort_order)
        if payload.subject is not None:
            updates.append("subject = ?")
            params.append(payload.subject.strip().lower())

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(topic_id)
            cur.execute(f"UPDATE speaking_topics SET {', '.join(updates)} WHERE id=?", tuple(params))
            conn.commit()

        cur.execute("SELECT id, part, title, status_badge, sort_order, COALESCE(subject, 'english') AS subject FROM speaking_topics WHERE id=?", (topic_id,))
        return {"topic": dict(cur.fetchone())}
    finally:
        conn.close()


@router.delete("/staff/speaking/topics/{topic_id}")
async def delete_staff_topic(topic_id: int, authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_questions WHERE topic_id=?", (topic_id,))
        cur.execute("DELETE FROM speaking_topics WHERE id=?", (topic_id,))
        conn.commit()
        return {"message": "Topic deleted successfully"}
    finally:
        conn.close()


@router.post("/staff/speaking/topics/{topic_id}/questions")
async def create_staff_question(topic_id: int, payload: QuestionCreateRequest, authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, part, COALESCE(subject, 'english') AS subject FROM speaking_topics WHERE id=?", (topic_id,))
        t_row = cur.fetchone()
        if not t_row:
            raise HTTPException(status_code=404, detail="Topic not found")

        values = question_insert_values_for_topic(payload, dict(t_row))
        bp_json = json.dumps(values["cue_card_bullet_points"]) if values["cue_card_bullet_points"] else None
        vocab_json = json.dumps(values["vocabulary"]) if values["vocabulary"] else None

        cur.execute(
            """
            INSERT INTO speaking_questions (topic_id, part, question_text, cue_card_bullet_points, sample_answer, examiner_tip, vocabulary_json, sort_order, subject)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id, topic_id, part, question_text, sample_answer, examiner_tip, subject
            """,
            (
                topic_id,
                values["part"],
                values["question_text"],
                bp_json,
                values["sample_answer"],
                values["examiner_tip"],
                vocab_json,
                values["sort_order"],
                values["subject"],
            ),
        )
        q_row = cur.fetchone()
        conn.commit()
        return {"question": dict(q_row)}
    finally:
        conn.close()


@router.patch("/staff/speaking/questions/{question_id}")
async def update_staff_question(question_id: int, payload: QuestionUpdateRequest, authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM speaking_questions WHERE id=?", (question_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Question not found")

        updates = []
        params = []
        if payload.question_text is not None:
            updates.append("question_text = ?")
            params.append(payload.question_text.strip())
        if payload.cue_card_bullet_points is not None:
            updates.append("cue_card_bullet_points = ?")
            params.append(json.dumps(payload.cue_card_bullet_points))
        if payload.sample_answer is not None:
            updates.append("sample_answer = ?")
            params.append(payload.sample_answer.strip())
        if payload.examiner_tip is not None:
            updates.append("examiner_tip = ?")
            params.append(payload.examiner_tip.strip())
        if payload.vocabulary is not None:
            updates.append("vocabulary_json = ?")
            params.append(json.dumps(payload.vocabulary))
        if payload.sort_order is not None:
            updates.append("sort_order = ?")
            params.append(payload.sort_order)
        if payload.subject is not None:
            updates.append("subject = ?")
            params.append(payload.subject.strip().lower())

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(question_id)
            cur.execute(f"UPDATE speaking_questions SET {', '.join(updates)} WHERE id=?", tuple(params))
            conn.commit()

        cur.execute("SELECT * FROM speaking_questions WHERE id=?", (question_id,))
        return {"question": dict(cur.fetchone())}
    finally:
        conn.close()


@router.delete("/staff/speaking/questions/{question_id}")
async def delete_staff_question(question_id: int, authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_questions WHERE id=?", (question_id,))
        conn.commit()
        return {"message": "Question deleted successfully"}
    finally:
        conn.close()


# --- AI TOPIC & QUESTIONS GENERATOR (DIAMONDVOY) ---
def _question_comparison_key(value: Any) -> str:
    """Normalize only harmless formatting differences for duplicate checks."""
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _load_existing_topic_questions(topic_id: int, subject: str) -> tuple[str, list[str]]:
    """Read the authoritative questions already stored in an admin-selected topic."""
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, title, COALESCE(subject, 'english') AS subject FROM speaking_topics WHERE id=?",
            (topic_id,),
        )
        topic = cur.fetchone()
        if not topic:
            raise HTTPException(status_code=404, detail="Selected speaking topic was not found")
        topic_subject = str(topic.get("subject") or "english").strip().lower()
        if topic_subject != subject:
            raise HTTPException(status_code=400, detail="Selected topic belongs to a different subject")
        cur.execute(
            "SELECT question_text FROM speaking_questions WHERE topic_id=? ORDER BY sort_order ASC, id ASC",
            (topic_id,),
        )
        return str(topic.get("title") or "").strip(), [
            str(row.get("question_text") or "").strip()
            for row in (cur.fetchall() or [])
            if str(row.get("question_text") or "").strip()
        ]
    finally:
        conn.close()


async def _generate_batch_topics_individually(
    payload: AiGenerateRequest,
    authorization: str | None,
    topic_count: int,
    report_progress: Any = None,
) -> dict[str, Any]:
    """Generate one topic per AI response and repair any truncated topic.

    Long Part 2 answers can make a provider return one question even when ten
    were requested.  We retain all valid initial questions, then request only
    the missing items as compact one-question calls.  The returned batch is
    therefore always has a useful minimum, without treating the selected
    question count as a mandatory exact total.
    """
    subject = (payload.subject or "english").strip().lower()
    generated_topics: list[dict[str, Any]] = []
    prior_titles: list[str] = []
    requested_questions = payload.question_count
    topic_question_targets = variable_batch_question_targets(
        requested_questions,
        topic_count,
        f"{payload.subject}|{payload.part}|{payload.theme}|{payload.custom_instruction}|{datetime.now().isoformat()}",
    )
    planned_total_questions = sum(topic_question_targets)
    replacement_semaphore = asyncio.Semaphore(3)

    async def notify(percent: int, stage: str) -> None:
        if report_progress:
            await report_progress(max(1, min(99, percent)), stage)

    for index in range(topic_count):
        target_questions = topic_question_targets[index]
        await notify(
            int(sum(topic_question_targets[:index]) * 95 / max(1, planned_total_questions)),
            f"{index + 1}/{topic_count}-mavzu tayyorlanmoqda",
        )
        prior_title_note = ", ".join(prior_titles[-4:]) or "none"
        batch_instruction = (
            f"This is topic {index + 1} of {topic_count} in one batch. Generate a distinctly different "
            f"topic; do not overlap with these already generated titles: {prior_title_note}. "
            f"Create {target_questions} complete, distinct questions for this topic."
        )
        custom_instruction = " ".join(
            part.strip()
            for part in (payload.custom_instruction or "", batch_instruction)
            if part.strip()
        )
        one_topic_payload = payload.model_copy(
            update={"topic_count": 1, "custom_instruction": custom_instruction}
        )
        generated = await _generate_speaking_ai_content(one_topic_payload, authorization)
        questions = generated.get("questions") if isinstance(generated, dict) else None
        if not isinstance(questions, list) or not questions:
            raise HTTPException(
                status_code=502,
                detail=f"AI did not return questions for batch topic {index + 1}",
            )
        title = str(generated.get("topic_title") or payload.theme or f"Speaking Topic {index + 1}").strip()
        prior_titles.append(title)
        normalized_questions = list(questions[:target_questions])

        # If the model was cut off, request the remaining questions separately.
        # They can run in parallel because each prompt is already anchored to
        # this topic title and explicitly asks for a different cue-card angle.
        missing_count = max(0, target_questions - len(normalized_questions))
        if missing_count > 0:
            existing_questions = "; ".join(
                str(item.get("question_text") or "").strip()
                for item in normalized_questions
                if isinstance(item, dict)
            ) or "none"

            completed_replacements = 0
            replacement_progress_lock = asyncio.Lock()

            async def generate_missing_question(question_number: int) -> dict[str, Any]:
                nonlocal completed_replacements
                missing_instruction = " ".join(
                    part.strip()
                    for part in (
                        payload.custom_instruction or "",
                        (
                            f"This is question {question_number} of {target_questions} required for batch topic "
                            f"'{title}'. Return exactly ONE complete, distinct question for this exact topic. "
                            f"Do not reuse or paraphrase these already generated questions: {existing_questions}."
                        ),
                    )
                    if part.strip()
                )
                one_question_payload = payload.model_copy(
                    update={
                        "topic_count": 1,
                        "question_count": 1,
                        "theme": title,
                        "custom_instruction": missing_instruction,
                    }
                )
                # Limit repair calls so a 5 × 10 batch stays reliable even if
                # the provider applies concurrent-request limits.
                async with replacement_semaphore:
                    repaired = await _generate_speaking_ai_content(one_question_payload, authorization)
                repaired_questions = repaired.get("questions") if isinstance(repaired, dict) else None
                if not isinstance(repaired_questions, list) or not repaired_questions:
                    raise HTTPException(
                        status_code=502,
                        detail=f"AI did not return replacement question {question_number} for batch topic {index + 1}",
                    )
                async with replacement_progress_lock:
                    completed_replacements += 1
                    await notify(
                        int(
                            (
                                sum(topic_question_targets[:index])
                                + len(normalized_questions)
                                + completed_replacements
                            )
                            * 95
                            / max(1, planned_total_questions)
                        ),
                        f"{index + 1}/{topic_count}-mavzu: {len(normalized_questions) + completed_replacements}/{target_questions} savol tayyor",
                    )
                return repaired_questions[0]

            repaired_questions = await asyncio.gather(
                *(generate_missing_question(len(normalized_questions) + offset + 1) for offset in range(missing_count))
            )
            normalized_questions.extend(repaired_questions)

        if len(normalized_questions) < target_questions:
            raise HTTPException(
                status_code=502,
                detail=f"AI returned only {len(normalized_questions)} of {target_questions} questions for batch topic {index + 1}",
            )
        await notify(
            int(sum(topic_question_targets[:index + 1]) * 95 / max(1, planned_total_questions)),
            f"{index + 1}/{topic_count}-mavzu tayyor",
        )
        try:
            status_badge = normalize_topic_status(generated.get("status_badge") or "PREDICTED")
        except ValueError:
            status_badge = "PREDICTED"
        generated_topics.append(
            {
                "topic_title": title,
                "status_badge": status_badge,
                "questions": normalized_questions,
            }
        )

    return {"topics": generated_topics, "subject": subject}


async def _generate_speaking_ai_content(
    payload: AiGenerateRequest,
    authorization: str | None,
    report_progress: Any = None,
):
    """Generates complete IELTS Speaking topics, questions, Band 8-9 answers, and vocabulary using Diamondvoy."""
    _auth_staff(authorization)

    subject_val = (payload.subject or "english").strip().lower()
    is_russian = subject_val == "russian"
    batch_topic_count = normalize_batch_topic_count(payload.topic_count)
    question_count = normalize_question_generation_count(payload.question_count)
    payload = payload.model_copy(update={"question_count": question_count})
    existing_question_texts: list[str] = []
    if payload.existing_topic_id:
        existing_title, existing_question_texts = _load_existing_topic_questions(
            payload.existing_topic_id, subject_val
        )
        # The database-selected title is authoritative for an existing topic.
        if existing_title:
            payload = payload.model_copy(update={"theme": existing_title})
    existing_question_note = ""
    if existing_question_texts:
        existing_question_note = (
            "\n- These questions are already stored in this topic. Do not repeat or paraphrase any of them: "
            + " | ".join(existing_question_texts[:30])
        )
    minimum_questions = minimum_questions_for_requested_limit(question_count)
    individual_generation_count = individual_ai_topic_generation_count(batch_topic_count)
    if individual_generation_count and not (payload.question_text and payload.question_text.strip()):
        return await _generate_batch_topics_individually(
            payload, authorization, individual_generation_count, report_progress
        )

    if is_russian:
        is_single_question = bool(payload.question_text and payload.question_text.strip())
        if is_single_question:
            q_text = payload.question_text.strip()
            prompt = (
                f"Вы — ведущий преподаватель разговорного русского языка в учебном центре Diamond Education.\n"
                f"Создайте учебный материал для разговорной практики по русскому языку:\n"
                f"Вопрос: \"{q_text}\"\n"
                f"Требования:\n"
                f"- cue_card_bullet_points: [] (строго пустой массив).\n"
                f"- Предоставьте 2-3 полезных русских слова, идиомы или устойчивых выражения ('vocabulary') с объяснением значения и живым примером.\n"
                f"- Не добавляйте examiner tips.\n"
                f"Дополнительные указания: {payload.custom_instruction or 'Живая литературная речь, богатая лексика'}\n\n"
                f"Выведите СТРОГО один валидный JSON-объект следующей структуры:\n"
                f"{{\n"
                f'  "question_text": "{q_text}",\n'
                f'  "cue_card_bullet_points": [],\n'
                f'  "vocabulary": [\n'
                f'    {{"word": "Полезное слово или идиома", "definition": "Краткое понятное объяснение значения", "example": "Живой пример употребления в речи"}}\n'
                f"  ]\n"
                f"}}\n"
                f"Только чистый JSON. Без markdown и текста вне JSON."
            )
        else:
            theme = (payload.theme or "Общая разговорная тема").strip()
            prompt = (
                f"Вы — ведущий преподаватель разговорного русского языка в учебном центре Diamond Education.\n"
                f"Создайте учебный блок для разговорной практики по теме:\n"
                f"Тема: {theme}\n"
                f"Количество вопросов: {payload.question_count}\n"
                f"Требования:\n"
                f"- КРИТИЧНО: верните от {minimum_questions} до {payload.question_count} полных, разных объектов в массиве questions; не останавливайтесь после одного.\n"
                f"- Все вопросы ('question_text') должны быть интересными, жизненными, побуждающими к подробному ответу на русском языке.\n"
                f"- Для каждого вопроса предоставьте 2-3 полезных русских слова, выражения или идиомы ('vocabulary') с толкованием и примером.\n"
                f"- cue_card_bullet_points: [] (строго пустой массив).\n"
                f"- Самостоятельно выберите один status_badge: PREDICTED, HIGH FREQUENCY или COMMON. PREDICTED используйте только для обоснованного прогноза, актуального до конца 2026 года; HIGH FREQUENCY — только для устойчиво часто встречающейся темы; иначе COMMON.\n"
                f"Дополнительные указания: {payload.custom_instruction or 'Разговорная практика, расширение словарного запаса'}{existing_question_note}\n\n"
                f"Выведите СТРОГО один валидный JSON-объект следующей структуры:\n"
                f"{{\n"
                f'  "topic_title": "{theme}",\n'
                f'  "status_badge": "PREDICTED | HIGH FREQUENCY | COMMON",\n'
                f'  "questions": [\n'
                f"    {{\n"
                f'      "question_text": "Вопрос для беседы на русском языке",\n'
                f'      "cue_card_bullet_points": [],\n'
                f'      "vocabulary": [\n'
                f'        {{"word": "Русское слово или выражение", "definition": "Объяснение значения", "example": "Пример употребления в предложении"}}\n'
                f"      ]\n"
                f"    }}\n"
                f"  ]\n"
                f"}}\n"
                f"Только чистый JSON. Без markdown и текста вне JSON."
            )
    else:
        if payload.part == 1:
            part_desc = "Part 1 (Introduction & Interview - everyday familiar topics)"
            answer_req = "Answer must be DIRECT and CONCISE (strictly 2 to 3 sentences). Candidate must answer directly right away without rambling or giving long stories, followed by a brief reason or everyday example."
            bullet_req = '"cue_card_bullet_points": [] (strictly empty array, NO bullet points in Part 1)'
            bullet_json_snippet = '"cue_card_bullet_points": []'
        elif payload.part == 2:
            part_desc = "Part 2 (Individual Long Turn / Cue Card)"
            answer_req = "Answer must be a COMPREHENSIVE, HIGH-SCORING MONOLOGUE (180 to 250 words, roughly 1.5 to 2 minutes of speech) addressing all 4 bullet points with chronological transitions and vivid descriptions."
            bullet_req = (
                '"cue_card_bullet_points": exactly 4 concise, specific prompts tailored to THIS exact cue card. '
                'Every question must have a different set of prompts: mention its real people, place, action, object or '
                'experience where relevant. Never reuse a generic template such as "Where/What it was".'
            )
            bullet_json_snippet = (
                '"cue_card_bullet_points": ["A specific detail from this cue card", '
                '"A person, place or time relevant to this card", "What happened or what you did", '
                '"And explain why this exact experience mattered"]'
            )
        else:
            part_desc = "Part 3 (Two-way Discussion - abstract, societal and analytical topics)"
            answer_req = "Answer must be an IN-DEPTH, ANALYTICAL answer (4 to 6 sentences) using sophisticated academic hedging (e.g. 'It could be argued that...', 'From a socioeconomic perspective...'), contrasting perspectives, and a logical conclusion."
            bullet_req = '"cue_card_bullet_points": [] (strictly empty array, NO bullet points in Part 3)'
            bullet_json_snippet = '"cue_card_bullet_points": []'

        is_single_question = bool(payload.question_text and payload.question_text.strip())

        if is_single_question:
            q_text = payload.question_text.strip()
            prompt = (
                f"You are a Senior British Council IELTS Examiner and Master Trainer for Diamond Education.\n"
                f"Create exam-standard content for IELTS Speaking {part_desc}:\n"
                f"Question: \"{q_text}\"\n"
                f"Requirements:\n"
                f"- {answer_req}\n"
                f"- {bullet_req}\n"
                f"- Provide 2-3 high-level C1/C2 collocations/vocabulary items with clear definitions and natural example sentences.\n"
                f"- Do NOT provide any examiner tips.\n"
                f"Optional instructions: {payload.custom_instruction or 'Natural Band 8.5-9.0 phrasing and C1/C2 lexical resource'}\n\n"
                f"Output strictly a single JSON object with the following schema:\n"
                f"{{\n"
                f'  "question_text": "{q_text}",\n'
                f'  {bullet_json_snippet},\n'
                f'  "sample_answer": "Model answer adhering strictly to the length and structure requirements above.",\n'
                f'  "vocabulary": [\n'
                f'    {{"word": "C1/C2 Collocation or Phrase", "definition": "Clear concise English definition", "example": "Natural usage sentence"}}\n'
                f"  ]\n"
                f"}}\n"
                f"Only valid JSON. No markdown backticks, no explanations outside JSON."
            )
        else:
            theme = (payload.theme or "General Topic").strip()
            prompt = (
                f"You are a Senior British Council IELTS Examiner and Master Trainer for Diamond Education.\n"
                f"Create complete IELTS Speaking content for:\n"
                f"Theme: {theme}\n"
                f"Speaking Section: {part_desc}\n"
                f"Question count: {payload.question_count}\n"
                f"Requirements:\n"
                f"- CRITICAL: Return between {minimum_questions} and {payload.question_count} complete, distinct objects inside the questions array. "
                f"Do not stop after one object.\n"
                f"- {answer_req}\n"
                f"- {bullet_req}\n"
                f"- If Part 2, the question_text MUST start with 'Describe a/an...'.\n"
                f"- For every question, provide 2-3 Band 9 collocations/vocabulary items with definitions and example sentences.\n"
                f"- Do NOT provide any examiner tips.\n"
                f"- Choose exactly one status_badge yourself: PREDICTED, HIGH FREQUENCY, or COMMON. Use PREDICTED only for a defensible exam prediction valid through the end of 2026; use HIGH FREQUENCY only for an established recurring topic; otherwise use COMMON.\n"
                f"Optional instruction: {payload.custom_instruction or 'Focus on predicted examination topics and Band 9 lexical resource'}{existing_question_note}\n\n"
                f"Output strictly a single JSON object with the following schema:\n"
                f"{{\n"
                f'  "topic_title": "Concise Category Name",\n'
                f'  "status_badge": "PREDICTED | HIGH FREQUENCY | COMMON",\n'
                f'  "questions": [\n'
                f"    {{\n"
                f'      "question_text": "Speaking question prompt",\n'
                f'      {bullet_json_snippet},\n'
                f'      "sample_answer": "Model answer adhering strictly to the length and structure requirements above.",\n'
                f'      "vocabulary": [\n'
                f'        {{"word": "C1/C2 Collocation or Phrase", "definition": "Clear concise English definition", "example": "Natural usage sentence"}}\n'
                f"      ]\n"
                f"    }}\n"
                f"  ]\n"
                f"}}\n"
                f"Only valid JSON. No markdown backticks, no explanations outside JSON."
            )

    if not is_single_question and batch_topic_count > 1:
        answer_field = "" if is_russian else ', "sample_answer": "Model answer"'
        prompt += (
            f"\nIMPORTANT: Create exactly {batch_topic_count} DISTINCT topics, each with {minimum_questions} to "
            f"{payload.question_count} questions. Return one JSON object using this schema only:\n"
            f'{{"topics": [{{"topic_title": "Distinct topic name", "status_badge": "PREDICTED | HIGH FREQUENCY | COMMON", '
            f'"questions": [{{"question_text": "Question"{answer_field}, "vocabulary": []}}]}}]}}\n'
            "Do not return a top-level 'questions' field in batch mode."
        )

    raw_text = ""
    # Try xAI / Grok generator
    try:
        import aiohttp
        from ai_generator import _xai_generate_text
        sys_prompt = "You are a master Russian language conversation teacher for Diamond Education. Return only valid JSON." if is_russian else "You are an elite IELTS Examiner for Diamond Education. Return only valid JSON."
        async with aiohttp.ClientSession() as session:
            for timeout_seconds in (
                AI_PRIMARY_GENERATION_TIMEOUT_SECONDS,
                AI_PRIMARY_RETRY_GENERATION_TIMEOUT_SECONDS,
            ):
                try:
                    raw_text = await asyncio.wait_for(
                        _xai_generate_text(
                            prompt,
                            session=session,
                            system_content=sys_prompt,
                            temperature=0.5,
                        ),
                        timeout=timeout_seconds,
                    )
                    if str(raw_text or "").strip():
                        break
                except asyncio.TimeoutError:
                    logger.warning(
                        "Speaking AI primary generation timed out after %ss subject=%s; retrying=%s",
                        timeout_seconds,
                        subject_val,
                        timeout_seconds != AI_PRIMARY_RETRY_GENERATION_TIMEOUT_SECONDS,
                    )
    except Exception as e:
        logger.warning("xAI generator failed for speaking AI: %s", e)
        raw_text = ""

    # Fallback to Diamondvoy Gemini answer
    if not raw_text.strip():
        try:
            from diamondvoy_helpers import diamondvoy_gemini_answer
            lang_code = "ru" if is_russian else "en"
            subjects_list = ["Russian"] if is_russian else ["English"]
            for timeout_seconds in (
                AI_FALLBACK_GENERATION_TIMEOUT_SECONDS,
                AI_FALLBACK_RETRY_GENERATION_TIMEOUT_SECONDS,
            ):
                try:
                    raw_text = await asyncio.wait_for(
                        diamondvoy_gemini_answer(prompt, subjects=subjects_list, lang=lang_code),
                        timeout=timeout_seconds,
                    )
                    if str(raw_text or "").strip():
                        break
                except asyncio.TimeoutError:
                    logger.warning(
                        "Speaking AI fallback timed out after %ss subject=%s; retrying=%s",
                        timeout_seconds,
                        subject_val,
                        timeout_seconds != AI_FALLBACK_RETRY_GENERATION_TIMEOUT_SECONDS,
                    )
        except Exception as e:
            logger.warning("Diamondvoy gemini fallback failed: %s", e)
            raw_text = ""

    if not raw_text.strip():
        raise HTTPException(status_code=503, detail="Diamondvoy AI generator is temporarily unavailable")

    try:
        from ai_generator import _balanced_json_object_slice, _sanitize_json_like_text
        cleaned = _sanitize_json_like_text(str(raw_text).strip())
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        parsed = None

        # Check if output is a JSON array: [ { ... } ]
        array_start = cleaned.find("[")
        obj_start = cleaned.find("{")
        if array_start >= 0 and (obj_start < 0 or array_start < obj_start):
            try:
                array_end = cleaned.rfind("]") + 1
                if array_end > array_start:
                    arr_parsed = json.loads(cleaned[array_start:array_end], strict=False)
                    if isinstance(arr_parsed, list):
                        parsed = {
                            "topic_title": payload.theme or ("Русский язык" if is_russian else f"Part {payload.part} Topic"),
                            "status_badge": "PREDICTED",
                            "questions": arr_parsed,
                        }
            except Exception:
                pass

        if parsed is None and obj_start >= 0:
            sliced = _balanced_json_object_slice(cleaned, obj_start)
            if sliced:
                try:
                    parsed = json.loads(sliced, strict=False)
                except Exception:
                    pass

        if parsed is None and obj_start >= 0:
            end = cleaned.rfind("}") + 1
            if end > obj_start:
                try:
                    parsed = json.loads(cleaned[obj_start:end], strict=False)
                except Exception:
                    pass

        if not isinstance(parsed, dict):
            raise ValueError("Parsed result is not a JSON object")

        # Flexible question list detection
        if "questions" not in parsed:
            for alt_key in ("items", "question_list", "data", "list", "results"):
                if alt_key in parsed and isinstance(parsed[alt_key], list):
                    parsed["questions"] = parsed[alt_key]
                    break

        def _normalize_item(q: dict[str, Any], is_ru: bool, target_part: int) -> dict[str, Any]:
            q.pop("examiner_tip", None)
            q["subject"] = "russian" if is_ru else "english"
            
            # Normalize question text
            if not q.get("question_text"):
                q["question_text"] = q.get("question") or q.get("prompt") or q.get("text") or "Speaking Question"
            q["question_text"] = str(q["question_text"]).strip()

            # Russian speaking questions intentionally do not use model answers.
            if is_ru:
                q["sample_answer"] = ""
            elif not q.get("sample_answer"):
                q["sample_answer"] = (
                    q.get("model_answer")
                    or q.get("answer")
                    or q.get("best_answer")
                    or q.get("bestAnswer")
                    or q.get("response")
                    or "Namuna javob"
                )
            q["sample_answer"] = str(q["sample_answer"]).strip()

            # Normalize cue card bullets
            if is_ru or target_part != 2:
                q["cue_card_bullet_points"] = []
            else:
                raw_bp = q.get("cue_card_bullet_points") or q.get("bullet_points") or q.get("bullets") or q.get("prompts")
                if isinstance(raw_bp, list):
                    clean_bullets = [str(x).strip() for x in raw_bp if str(x).strip()]
                    q["cue_card_bullet_points"] = clean_bullets[:4] if len(clean_bullets) >= 4 else part_two_cue_card_fallback(q["question_text"])
                else:
                    q["cue_card_bullet_points"] = part_two_cue_card_fallback(q["question_text"])

            # Normalize vocabulary list
            raw_v = q.get("vocabulary") or q.get("vocab") or q.get("words") or []
            norm_v = []
            if isinstance(raw_v, list):
                for item in raw_v:
                    if isinstance(item, dict):
                        norm_v.append({
                            "word": str(item.get("word") or item.get("term") or "").strip(),
                            "definition": str(item.get("definition") or item.get("meaning") or "").strip(),
                            "example": str(item.get("example") or item.get("sentence") or "").strip(),
                        })
                    elif isinstance(item, str) and item.strip():
                        norm_v.append({
                            "word": item.strip(),
                            "definition": "",
                            "example": "",
                        })
            q["vocabulary"] = [v for v in norm_v if v.get("word")]
            return q

        if not is_single_question and batch_topic_count > 1:
            raw_topics = parsed.get("topics")
            if not isinstance(raw_topics, list):
                raise ValueError("Batch response must contain a topics array")

            normalized_topics = []
            for index, raw_topic in enumerate(raw_topics[:batch_topic_count]):
                if not isinstance(raw_topic, dict):
                    continue
                raw_questions = raw_topic.get("questions")
                if not isinstance(raw_questions, list):
                    for alt_key in ("items", "question_list", "data", "list", "results"):
                        if isinstance(raw_topic.get(alt_key), list):
                            raw_questions = raw_topic[alt_key]
                            break
                normalized_questions = [
                    _normalize_item(question, is_russian, payload.part)
                    for question in (raw_questions or [])
                    if isinstance(question, dict)
                ][:payload.question_count]
                if len(normalized_questions) < minimum_questions:
                    raise ValueError(
                        f"Batch topic {index + 1} must contain at least {minimum_questions} questions"
                    )
                try:
                    status_badge = normalize_topic_status(raw_topic.get("status_badge") or "PREDICTED")
                except ValueError:
                    status_badge = "PREDICTED"
                title = str(raw_topic.get("topic_title") or raw_topic.get("title") or "").strip()
                if not title:
                    title = f"{(payload.theme or 'Speaking Topic').strip()} {index + 1}"
                normalized_topics.append({
                    "topic_title": title,
                    "status_badge": status_badge,
                    "questions": normalized_questions,
                })

            if len(normalized_topics) != batch_topic_count:
                raise ValueError(f"Batch response must contain exactly {batch_topic_count} topics")
            return {"topics": normalized_topics, "subject": subject_val}

        if is_single_question:
            if "questions" in parsed and isinstance(parsed["questions"], list) and len(parsed["questions"]) > 0:
                first_q = parsed["questions"][0]
                if isinstance(first_q, dict):
                    parsed = first_q
            parsed = _normalize_item(parsed, is_russian, payload.part)
            parsed["subject"] = subject_val
            return parsed

        if "questions" in parsed and isinstance(parsed["questions"], list) and len(parsed["questions"]) > 0:
            normalized_items = [
                _normalize_item(q, is_russian, payload.part)
                for q in parsed["questions"]
                if isinstance(q, dict)
            ]
            if existing_question_texts:
                existing_keys = {_question_comparison_key(text) for text in existing_question_texts}
                normalized_items = [
                    item
                    for item in normalized_items
                    if _question_comparison_key(item.get("question_text")) not in existing_keys
                ]
                if not normalized_items:
                    raise ValueError("AI only returned questions already stored in the selected topic")
            parsed["questions"] = normalized_items
            if not parsed.get("topic_title"):
                parsed["topic_title"] = payload.theme or ("Русский язык" if is_russian else f"Part {payload.part} Topic")
            if not parsed.get("status_badge"):
                parsed["status_badge"] = "PREDICTED"
            try:
                parsed["status_badge"] = normalize_topic_status(parsed["status_badge"])
            except ValueError:
                parsed["status_badge"] = "PREDICTED"
        else:
            single_norm = _normalize_item(parsed, is_russian, payload.part)
            parsed = {
                "topic_title": payload.theme or ("Русский язык" if is_russian else f"Part {payload.part} Topic"),
                "status_badge": "PREDICTED",
                "questions": [single_norm],
            }

        parsed["subject"] = subject_val
        return parsed
    except Exception as exc:
        logger.exception("Failed to parse AI generated speaking content")
        raise HTTPException(status_code=502, detail=f"Failed to parse Diamondvoy response: {exc}")


def _serialize_speaking_ai_job(row: Any) -> dict[str, Any]:
    job = dict(row)
    for key in ("request_json", "result_json"):
        raw = job.get(key)
        if isinstance(raw, str) and raw.strip():
            try:
                job[key] = json.loads(raw)
            except (TypeError, ValueError):
                job[key] = None
    job["progress_percent"] = max(0, min(100, int(job.get("progress_percent") or 0)))
    # The browser only needs progress/result; preserve the submitted prompt in
    # the database for diagnostics without reflecting it in API responses.
    job.pop("request_json", None)
    return job


def _read_speaking_ai_job(job_id: int) -> dict[str, Any]:
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_ai_generation_jobs WHERE id=?", (job_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Speaking AI generation job not found")
        return _serialize_speaking_ai_job(row)
    finally:
        conn.close()


def _update_speaking_ai_job(job_id: int, **updates: Any) -> None:
    allowed = {
        "status",
        "progress_percent",
        "stage",
        "result_json",
        "error_message",
    }
    values = {key: value for key, value in updates.items() if key in allowed}
    if not values:
        return
    columns = []
    params: list[Any] = []
    for key, value in values.items():
        columns.append(f"{key}=?")
        params.append(json.dumps(value, ensure_ascii=False) if key == "result_json" else value)
    columns.append("updated_at=CURRENT_TIMESTAMP")
    params.append(job_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE speaking_ai_generation_jobs SET {', '.join(columns)} WHERE id=?",
            tuple(params),
        )
        conn.commit()
    finally:
        conn.close()


async def _run_speaking_ai_generation_job(
    job_id: int,
    payload: AiGenerateRequest,
    authorization: str | None,
) -> None:
    async def report(percent: int, stage: str) -> None:
        _update_speaking_ai_job(job_id, progress_percent=percent, stage=stage)

    try:
        await report(1, "AI so'roviga tayyorgarlik")
        result = await _generate_speaking_ai_content(payload, authorization, report)
        _update_speaking_ai_job(
            job_id,
            status="completed",
            progress_percent=100,
            stage="Generatsiya tayyor",
            result_json=result,
        )
    except HTTPException as exc:
        _update_speaking_ai_job(
            job_id,
            status="failed",
            progress_percent=100,
            stage="Generatsiya to'xtadi",
            error_message=str(exc.detail),
        )
    except Exception:
        logger.exception("Speaking AI generation job failed job_id=%s", job_id)
        _update_speaking_ai_job(
            job_id,
            status="failed",
            progress_percent=100,
            stage="Generatsiya to'xtadi",
            error_message="AI generatsiyasida kutilmagan xatolik yuz berdi",
        )


@router.post("/staff/speaking/ai-generate")
async def generate_speaking_ai_content(
    payload: AiGenerateRequest,
    authorization: str | None = Header(default=None),
):
    """Immediate mode retained for single topic/question requests."""
    return await _generate_speaking_ai_content(payload, authorization)


@router.post("/staff/speaking/ai-generate/jobs")
async def start_speaking_ai_generation_job(
    payload: AiGenerateRequest,
    authorization: str | None = Header(default=None),
):
    """Start a durable, pollable batch job so the admin sees real progress."""
    user = _auth_staff(authorization)
    # Validate before creating a job, so invalid requests never remain queued.
    normalize_batch_topic_count(payload.topic_count)
    normalize_question_generation_count(payload.question_count)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO speaking_ai_generation_jobs
                (created_by_user_id, status, progress_percent, stage, request_json)
            VALUES (?, 'queued', 0, 'Navbatda', ?)
            RETURNING id
            """,
            (int(user.get("id") or 0), json.dumps(payload.model_dump(), ensure_ascii=False)),
        )
        row = cur.fetchone()
        conn.commit()
        job_id = int(row["id"] if isinstance(row, dict) else row[0])
    finally:
        conn.close()
    asyncio.create_task(_run_speaking_ai_generation_job(job_id, payload, authorization))
    return {"job": _read_speaking_ai_job(job_id)}


@router.get("/staff/speaking/ai-generate/jobs/{job_id}")
async def get_speaking_ai_generation_job(
    job_id: int,
    authorization: str | None = Header(default=None),
):
    user = _auth_staff(authorization)
    job = _read_speaking_ai_job(job_id)
    if int(job.get("created_by_user_id") or 0) != int(user.get("id") or 0):
        raise HTTPException(status_code=403, detail="Speaking AI generation job belongs to another user")
    return {"job": job}


# --- SPEAKING NOTIFICATIONS (BROADCAST PUSH) ---
@router.get("/staff/speaking/notifications")
async def list_staff_notifications(authorization: str | None = Header(default=None)):
    _auth_staff(authorization)
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, title, body, target_part, target_topic_id, recipient_count, status, created_at
            FROM speaking_notifications
            ORDER BY id DESC
            LIMIT 50
            """
        )
        return {"items": [dict(r) for r in (cur.fetchall() or [])]}
    finally:
        conn.close()


@router.post("/staff/speaking/notifications/send")
async def send_staff_speaking_notification(
    payload: NotificationSendRequest,
    authorization: str | None = Header(default=None),
):
    user = _auth_staff(authorization)
    ensure_speaking_tables()

    data_payload: dict[str, Any] = {
        "type": "speaking_announcement",
        "timestamp": datetime.now().isoformat(),
    }
    if payload.target_part:
        data_payload["target_part"] = str(payload.target_part)
    if payload.target_topic_id:
        data_payload["target_topic_id"] = str(payload.target_topic_id)

    recipient_count = push_notifications.send_push_to_speaking_devices(
        title=payload.title,
        body=payload.body,
        data=data_payload,
    )

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO speaking_notifications (title, body, target_part, target_topic_id, sent_by_user_id, recipient_count, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id, title, body, recipient_count, created_at
            """,
            (
                payload.title.strip(),
                payload.body.strip(),
                payload.target_part,
                payload.target_topic_id,
                int(user.get("id") or 0),
                recipient_count,
                "sent",
            ),
        )
        row = cur.fetchone()
        conn.commit()
        return {
            "success": True,
            "message": f"Bildirishnoma muvaffaqiyatli yuborildi ({recipient_count} ta qurilma)",
            "notification": dict(row) if row else None,
        }
    finally:
        conn.close()
