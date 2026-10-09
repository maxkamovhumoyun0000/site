"""
Diamond Speaking Questions — Backend & Media Admin API.
Handles dynamic topics, questions, vocabulary, Band 8-9 sample answers,
AI generation (via Diamondvoy / xAI / Gemini), and broadcast push notifications.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_conn
import push_notifications

logger = logging.getLogger(__name__)
router = APIRouter()

MEDIA_STAFF_ROLES = {"media", "media_admin", "admin", "superadmin", "developer"}


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
                status_badge TEXT DEFAULT '2026 PREDICTED',
                sort_order INTEGER DEFAULT 0,
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
        conn.commit()
        _seed_initial_topics(cur, conn)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("ensure_speaking_tables failed")
    finally:
        conn.close()


def _seed_initial_topics(cur, conn) -> None:
    cur.execute("SELECT COUNT(*) AS c FROM speaking_topics")
    row = cur.fetchone()
    count = row["c"] if hasattr(row, "__getitem__") and "c" in row else (row[0] if row else 0)
    if count > 0:
        return

    # Seed 1: Part 1 - Home
    cur.execute(
        "INSERT INTO speaking_topics (part, title, status_badge, sort_order) VALUES (?, ?, ?, ?) RETURNING id",
        (1, "Home", "HIGH FREQUENCY", 1),
    )
    topic_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO speaking_questions (topic_id, part, question_text, sample_answer, examiner_tip, vocabulary_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            topic_id,
            1,
            "What do you like most about the place where you live?",
            "My favourite thing about where I live is the close-knit sense of community. It is a tranquil neighbourhood, but residents are remarkably cordial and supportive. Furthermore, all basic amenities—such as grocery shops and a leafy park—are conveniently located within walking distance.",
            "Extend your response by stating a primary reason followed by concrete daily examples.",
            json.dumps([
                {"word": "Close-knit community", "definition": "A group of people bound together by strong social relationships.", "example": "Living in a close-knit community makes you feel supported and safe."},
                {"word": "Basic amenities", "definition": "Useful features or facilities such as shops, parks, and schools.", "example": "The apartment is situated near essential amenities and public transit."}
            ]),
        ),
    )

    # Seed 2: Part 2 - Travel (Journey)
    cur.execute(
        "INSERT INTO speaking_topics (part, title, status_badge, sort_order) VALUES (?, ?, ?, ?) RETURNING id",
        (2, "Travel", "2026 PREDICTED", 2),
    )
    p2_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO speaking_questions (topic_id, part, question_text, cue_card_bullet_points, sample_answer, examiner_tip, vocabulary_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            p2_id,
            2,
            "Describe a journey you will always remember.",
            json.dumps([
                "Where you went and how you travelled there",
                "Who accompanied you on the trip",
                "What unexpected events took place along the way",
                "And explain why this particular journey left an indelible impression on you."
            ]),
            "One journey that remains indelibly etched in my memory is a cross-country train voyage across Uzbekistan's historic Silk Road corridor. What made the expedition so mesmerizing was the sheer contrast between ancient mudbrick domes and endless desert plains.",
            "Structure your 2 minutes chronologically: context & departure -> key event -> lingering emotional reflection.",
            json.dumps([
                {"word": "Indelibly etched", "definition": "Impossible to forget or remove from memory.", "example": "The breathtaking sunrise remains indelibly etched in my recollection."},
                {"word": "Breathtaking panorama", "definition": "An extensive, spectacular unobstructed view.", "example": "From the carriage window we marvelled at breathtaking panoramas."}
            ]),
        ),
    )

    # Seed 3: Part 3 - Modern Transport
    cur.execute(
        "INSERT INTO speaking_topics (part, title, status_badge, sort_order) VALUES (?, ?, ?, ?) RETURNING id",
        (3, "Modern Transport", "2026 PREDICTED", 3),
    )
    p3_id = cur.fetchone()["id"]
    cur.execute(
        """
        INSERT INTO speaking_questions (topic_id, part, question_text, sample_answer, examiner_tip, vocabulary_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            p3_id,
            3,
            "How do you foresee the future of mass transit in metropolitan areas over the coming decade?",
            "I envision a profound paradigm shift towards fully automated, zero-emission mass transit systems. Municipal governments are already allocating substantial capital to high-speed rail networks and autonomous fleets to alleviate suffocating traffic gridlock.",
            "Speculate with nuanced hedging such as 'I envision...', 'It is highly plausible that...', and contrast present challenges with future solutions.",
            json.dumps([
                {"word": "Paradigm shift", "definition": "A fundamental change in approach or underlying assumptions.", "example": "Electrification marks a profound paradigm shift in urban mobility."},
                {"word": "Alleviate traffic gridlock", "definition": "Reduce severe vehicle congestion on streets.", "example": "Autonomous trains will significantly alleviate urban traffic gridlock."}
            ]),
        ),
    )
    conn.commit()


# --- Pydantic Request Models ---
class PushTokenRegisterRequest(BaseModel):
    device_id: str
    token: str
    platform: str = "android"
    app: str = "speaking"


class TopicCreateRequest(BaseModel):
    part: int = Field(..., ge=1, le=3)
    title: str = Field(..., min_length=2, max_length=120)
    status_badge: str = Field(default="2026 PREDICTED", max_length=50)
    sort_order: int = 0


class TopicUpdateRequest(BaseModel):
    part: int | None = Field(default=None, ge=1, le=3)
    title: str | None = Field(default=None, min_length=2, max_length=120)
    status_badge: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None


class QuestionCreateRequest(BaseModel):
    part: int = Field(..., ge=1, le=3)
    question_text: str = Field(..., min_length=5)
    cue_card_bullet_points: list[str] = Field(default_factory=list)
    sample_answer: str = Field(..., min_length=10)
    examiner_tip: str | None = None
    vocabulary: list[dict[str, str]] = Field(default_factory=list)
    sort_order: int = 0


class QuestionUpdateRequest(BaseModel):
    question_text: str | None = None
    cue_card_bullet_points: list[str] | None = None
    sample_answer: str | None = None
    examiner_tip: str | None = None
    vocabulary: list[dict[str, str]] | None = None
    sort_order: int | None = None


class AiGenerateRequest(BaseModel):
    theme: str = Field(..., min_length=2)
    part: int = Field(default=1, ge=1, le=3)
    question_count: int = Field(default=2, ge=1, le=5)
    custom_instruction: str | None = None


class NotificationSendRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=180)
    body: str = Field(..., min_length=5, max_length=500)
    target_part: int | None = None
    target_topic_id: int | None = None


# --- PUBLIC API (FOR FLUTTER APP) ---
@router.get("/api/speaking/content")
@router.get("/speaking/content")
async def get_speaking_content():
    """Returns all topics and questions for Diamond Speaking Questions app."""
    ensure_speaking_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, part, title, status_badge, sort_order
            FROM speaking_topics
            ORDER BY part ASC, sort_order ASC, id ASC
            """
        )
        topics = [dict(row) for row in (cur.fetchall() or [])]

        cur.execute(
            """
            SELECT q.id, q.topic_id, q.part, q.question_text, q.cue_card_bullet_points,
                   q.sample_answer, q.examiner_tip, q.vocabulary_json, q.sort_order,
                   t.title AS topic_title, t.status_badge
            FROM speaking_questions q
            JOIN speaking_topics t ON q.topic_id = t.id
            ORDER BY q.part ASC, t.sort_order ASC, q.sort_order ASC, q.id ASC
            """
        )
        q_rows = cur.fetchall() or []
        questions = []
        for r in q_rows:
            d = dict(r)
            bullet_points = []
            if d.get("cue_card_bullet_points"):
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

            questions.append({
                "id": str(d["id"]),
                "topic_id": d["topic_id"],
                "category": d.get("topic_title") or "General",
                "part": d["part"],
                "prompt": d["question_text"],
                "bestAnswer": d.get("sample_answer") or "",
                "tag": d.get("status_badge") or "2026 PREDICTED",
                "prompts": bullet_points,
                "examinerTip": d.get("examiner_tip"),
                "vocabulary": vocab_items,
            })

        return {"topics": topics, "questions": questions}
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
                   COUNT(q.id) AS question_count
            FROM speaking_topics t
            LEFT JOIN speaking_questions q ON t.id = q.topic_id
            GROUP BY t.id, t.part, t.title, t.status_badge, t.sort_order, t.created_at
            ORDER BY t.part ASC, t.sort_order ASC, t.id DESC
            """
        )
        topics = [dict(row) for row in (cur.fetchall() or [])]

        cur.execute(
            """
            SELECT id, topic_id, part, question_text, cue_card_bullet_points,
                   sample_answer, examiner_tip, vocabulary_json, sort_order
            FROM speaking_questions
            ORDER BY part ASC, sort_order ASC, id ASC
            """
        )
        questions = []
        for r in cur.fetchall() or []:
            d = dict(r)
            if d.get("cue_card_bullet_points"):
                try:
                    d["cue_card_bullet_points"] = json.loads(d["cue_card_bullet_points"])
                except Exception:
                    pass
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
        cur.execute(
            """
            INSERT INTO speaking_topics (part, title, status_badge, sort_order)
            VALUES (?, ?, ?, ?)
            RETURNING id, part, title, status_badge, sort_order
            """,
            (payload.part, payload.title.strip(), payload.status_badge.strip(), payload.sort_order),
        )
        row = cur.fetchone()
        conn.commit()
        return {"topic": dict(row)}
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
            updates.append("status_badge = ?")
            params.append(payload.status_badge.strip())
        if payload.sort_order is not None:
            updates.append("sort_order = ?")
            params.append(payload.sort_order)

        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(topic_id)
            cur.execute(f"UPDATE speaking_topics SET {', '.join(updates)} WHERE id=?", tuple(params))
            conn.commit()

        cur.execute("SELECT id, part, title, status_badge, sort_order FROM speaking_topics WHERE id=?", (topic_id,))
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
        cur.execute("SELECT id, part FROM speaking_topics WHERE id=?", (topic_id,))
        t_row = cur.fetchone()
        if not t_row:
            raise HTTPException(status_code=404, detail="Topic not found")

        bp_json = json.dumps(payload.cue_card_bullet_points) if payload.cue_card_bullet_points else None
        vocab_json = json.dumps(payload.vocabulary) if payload.vocabulary else None

        cur.execute(
            """
            INSERT INTO speaking_questions (topic_id, part, question_text, cue_card_bullet_points, sample_answer, examiner_tip, vocabulary_json, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id, topic_id, part, question_text, sample_answer, examiner_tip
            """,
            (
                topic_id,
                payload.part or dict(t_row)["part"],
                payload.question_text.strip(),
                bp_json,
                payload.sample_answer.strip(),
                payload.examiner_tip.strip() if payload.examiner_tip else None,
                vocab_json,
                payload.sort_order,
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
@router.post("/staff/speaking/ai-generate")
async def generate_speaking_ai_content(payload: AiGenerateRequest, authorization: str | None = Header(default=None)):
    """Generates complete IELTS Speaking topics, questions, Band 8-9 answers, and vocabulary using Diamondvoy."""
    _auth_staff(authorization)

    part_desc = (
        "Part 1 (Introduction & Interview - everyday topics, concise 3-4 sentence answers)"
        if payload.part == 1
        else "Part 2 (Individual Long Turn - 1 cue card with 4 bullet points, 1-2 min model speech)"
        if payload.part == 2
        else "Part 3 (Two-way Discussion - deep analytical questions, Band 9 nuanced answers)"
    )

    prompt = (
        f"You are a Senior British Council IELTS Examiner and Master Trainer for Diamond Education.\n"
        f"Create high-scoring IELTS 2026 exam content for:\n"
        f"Theme: {payload.theme}\n"
        f"Speaking Part: {part_desc}\n"
        f"Question count: {payload.question_count}\n"
        f"Optional instruction: {payload.custom_instruction or 'Focus on predicted high-frequency 2026 examination trends'}\n\n"
        f"Output strictly a single JSON object with the following schema:\n"
        f"{{\n"
        f'  "topic_title": "Concise Category Name (e.g. Artificial Intelligence, Eco-Tourism)",\n'
        f'  "status_badge": "2026 PREDICTED",\n'
        f'  "questions": [\n'
        f"    {{\n"
        f'      "question_text": "The exact speaking prompt",\n'
        f'      "cue_card_bullet_points": ["bullet 1", "bullet 2", "bullet 3", "bullet 4"],\n'
        f'      "sample_answer": "Band 8.5-9.0 natural model answer with advanced lexical resource and cohesive discourse markers.",\n'
        f'      "examiner_tip": "Practical examiner guidance on how to secure Band 8+ on this specific question.",\n'
        f'      "vocabulary": [\n'
        f'        {{"word": "C1/C2 Collocation or Phrase", "definition": "Clear concise English definition", "example": "Natural usage sentence"}}\n'
        f"      ]\n"
        f"    }}\n"
        f"  ]\n"
        f"}}\n"
        f"Only valid JSON. No markdown backticks, no explanatory preamble."
    )

    raw_text = ""
    # Try xAI / Grok generator
    try:
        import aiohttp
        from ai_generator import _xai_generate_text
        sys_prompt = "You are an elite IELTS Examiner for Diamond Education. Return only valid JSON."
        async with aiohttp.ClientSession() as session:
            raw_text = await _xai_generate_text(prompt, session=session, system_content=sys_prompt, temperature=0.7)
    except Exception as e:
        logger.warning("xAI generator failed for speaking AI: %s", e)
        raw_text = ""

    # Fallback to Diamondvoy Gemini answer
    if not raw_text.strip():
        try:
            from diamondvoy_helpers import diamondvoy_gemini_answer
            raw_text = await diamondvoy_gemini_answer(prompt, subjects=["English"], lang="en")
        except Exception as e:
            logger.warning("Diamondvoy gemini fallback failed: %s", e)
            raw_text = ""

    if not raw_text.strip():
        raise HTTPException(status_code=503, detail="Diamondvoy AI generator is temporarily unavailable")

    try:
        source = str(raw_text).strip()
        source = re.sub(r"^```(?:json)?\s*", "", source, flags=re.IGNORECASE)
        source = re.sub(r"\s*```$", "", source)
        start = source.find("{")
        end = source.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(source[start:end])
            return parsed
        else:
            raise ValueError("No JSON object brackets found in response")
    except Exception as exc:
        logger.exception("Failed to parse AI generated speaking content")
        raise HTTPException(status_code=502, detail=f"Failed to parse Diamondvoy response: {exc}")


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
