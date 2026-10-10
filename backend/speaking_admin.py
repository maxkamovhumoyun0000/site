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
    question_text: str = Field(..., min_length=1)
    cue_card_bullet_points: list[str] = Field(default_factory=list)
    sample_answer: str = Field(default="Sample answer to be reviewed.", min_length=1)
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
    question_count: int = Field(default=2, ge=1, le=5)
    custom_instruction: str | None = None
    question_text: str | None = None
    subject: str = Field(default="english", max_length=32)


class NotificationSendRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=180)
    body: str = Field(..., min_length=5, max_length=500)
    target_part: int | None = None
    target_topic_id: int | None = None


# --- PUBLIC API (FOR FLUTTER APP) ---
@router.get("/api/speaking/content")
@router.get("/speaking/content")
async def get_speaking_content(subject: str | None = Query(default=None)):
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

            questions.append({
                "id": str(d["id"]),
                "topic_id": d["topic_id"],
                "category": d.get("topic_title") or "General",
                "part": d["part"],
                "subject": (d.get("subject") or "english").lower(),
                "prompt": d["question_text"],
                "bestAnswer": d.get("sample_answer") or "",
                "tag": (d.get("status_badge") or "PREDICTED").replace("2026", "").strip(),
                "prompts": bullet_points,
                "examinerTip": None,
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
        cur.execute(
            """
            INSERT INTO speaking_topics (part, title, status_badge, sort_order, subject)
            VALUES (?, ?, ?, ?, ?)
            RETURNING id, part, title, status_badge, sort_order, subject
            """,
            (payload.part, payload.title.strip(), payload.status_badge.strip(), payload.sort_order, subj),
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

        t_dict = dict(t_row)
        subj = (payload.subject or t_dict.get("subject") or "english").strip().lower()
        bp_json = json.dumps(payload.cue_card_bullet_points) if payload.cue_card_bullet_points else None
        vocab_json = json.dumps(payload.vocabulary) if payload.vocabulary else None

        cur.execute(
            """
            INSERT INTO speaking_questions (topic_id, part, question_text, cue_card_bullet_points, sample_answer, examiner_tip, vocabulary_json, sort_order, subject)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id, topic_id, part, question_text, sample_answer, examiner_tip, subject
            """,
            (
                topic_id,
                payload.part or t_dict["part"],
                payload.question_text.strip(),
                bp_json,
                payload.sample_answer.strip(),
                payload.examiner_tip.strip() if payload.examiner_tip else None,
                vocab_json,
                payload.sort_order,
                subj,
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
@router.post("/staff/speaking/ai-generate")
async def generate_speaking_ai_content(payload: AiGenerateRequest, authorization: str | None = Header(default=None)):
    """Generates complete IELTS Speaking topics, questions, Band 8-9 answers, and vocabulary using Diamondvoy."""
    _auth_staff(authorization)

    subject_val = (payload.subject or "english").strip().lower()
    is_russian = subject_val == "russian"

    if is_russian:
        is_single_question = bool(payload.question_text and payload.question_text.strip())
        if is_single_question:
            q_text = payload.question_text.strip()
            prompt = (
                f"Вы — ведущий преподаватель разговорного русского языка в учебном центре Diamond Education.\n"
                f"Создайте учебный материал для разговорной практики по русскому языку:\n"
                f"Вопрос: \"{q_text}\"\n"
                f"Требования:\n"
                f"- Образец ответа ('sample_answer') должен быть естественным, грамотным, развёрнутым (3-5 предложений уровня B2-C1).\n"
                f"- cue_card_bullet_points: [] (строго пустой массив).\n"
                f"- Предоставьте 2-3 полезных русских слова, идиомы или устойчивых выражения ('vocabulary') с объяснением значения и живым примером.\n"
                f"- Не добавляйте examiner tips.\n"
                f"Дополнительные указания: {payload.custom_instruction or 'Живая литературная речь, богатая лексика'}\n\n"
                f"Выведите СТРОГО один валидный JSON-объект следующей структуры:\n"
                f"{{\n"
                f'  "question_text": "{q_text}",\n'
                f'  "cue_card_bullet_points": [],\n'
                f'  "sample_answer": "Естественный, богатый лексикой развёрнутый ответ на русском языке.",\n'
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
                f"- Все вопросы ('question_text') должны быть интересными, жизненными, побуждающими к подробному ответу на русском языке.\n"
                f"- Для каждого вопроса составьте естественный, развёрнутый образец ответа ('sample_answer', 3-5 предложений уровня B2-C1).\n"
                f"- Для каждого вопроса предоставьте 2-3 полезных русских слова, выражения или идиомы ('vocabulary') с толкованием и примером.\n"
                f"- cue_card_bullet_points: [] (строго пустой массив).\n"
                f"Дополнительные указания: {payload.custom_instruction or 'Разговорная практика, расширение словарного запаса'}\n\n"
                f"Выведите СТРОГО один валидный JSON-объект следующей структуры:\n"
                f"{{\n"
                f'  "topic_title": "{theme}",\n'
                f'  "status_badge": "РАЗГОВОРНЫЙ",\n'
                f'  "questions": [\n'
                f"    {{\n"
                f'      "question_text": "Вопрос для беседы на русском языке",\n'
                f'      "cue_card_bullet_points": [],\n'
                f'      "sample_answer": "Грамотный, живой и развёрнутый ответ на русском языке.",\n'
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
        elif payload.part == 2:
            part_desc = "Part 2 (Individual Long Turn / Cue Card)"
            answer_req = "Answer must be a COMPREHENSIVE, HIGH-SCORING MONOLOGUE (180 to 250 words, roughly 1.5 to 2 minutes of speech) addressing all 4 bullet points with chronological transitions and vivid descriptions."
            bullet_req = '"cue_card_bullet_points": ["Where/What it was", "Who was involved", "What happened", "And explain why..."] (strictly 4 bullet points)'
        else:
            part_desc = "Part 3 (Two-way Discussion - abstract, societal and analytical topics)"
            answer_req = "Answer must be an IN-DEPTH, ANALYTICAL answer (4 to 6 sentences) using sophisticated academic hedging (e.g. 'It could be argued that...', 'From a socioeconomic perspective...'), contrasting perspectives, and a logical conclusion."
            bullet_req = '"cue_card_bullet_points": [] (strictly empty array, NO bullet points in Part 3)'

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
                f'  {"cue_card_bullet_points": [] if payload.part != 2 else \'"cue_card_bullet_points": ["point 1", "point 2", "point 3", "point 4"]\'},\n'
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
                f"- {answer_req}\n"
                f"- {bullet_req}\n"
                f"- If Part 2, the question_text MUST start with 'Describe a/an...'.\n"
                f"- For every question, provide 2-3 Band 9 collocations/vocabulary items with definitions and example sentences.\n"
                f"- Do NOT provide any examiner tips.\n"
                f"Optional instruction: {payload.custom_instruction or 'Focus on predicted examination topics and Band 9 lexical resource'}\n\n"
                f"Output strictly a single JSON object with the following schema:\n"
                f"{{\n"
                f'  "topic_title": "Concise Category Name",\n'
                f'  "status_badge": "PREDICTED",\n'
                f'  "questions": [\n'
                f"    {{\n"
                f'      "question_text": "Speaking question prompt",\n'
                f'      {"cue_card_bullet_points": [] if payload.part != 2 else \'"cue_card_bullet_points": ["point 1", "point 2", "point 3", "point 4"]\'},\n'
                f'      "sample_answer": "Model answer adhering strictly to the length and structure requirements above.",\n'
                f'      "vocabulary": [\n'
                f'        {{"word": "C1/C2 Collocation or Phrase", "definition": "Clear concise English definition", "example": "Natural usage sentence"}}\n'
                f"      ]\n"
                f"    }}\n"
                f"  ]\n"
                f"}}\n"
                f"Only valid JSON. No markdown backticks, no explanations outside JSON."
            )

    raw_text = ""
    # Try xAI / Grok generator
    try:
        import aiohttp
        from ai_generator import _xai_generate_text
        sys_prompt = "You are a master Russian language conversation teacher for Diamond Education. Return only valid JSON." if is_russian else "You are an elite IELTS Examiner for Diamond Education. Return only valid JSON."
        async with aiohttp.ClientSession() as session:
            raw_text = await _xai_generate_text(prompt, session=session, system_content=sys_prompt, temperature=0.5)
    except Exception as e:
        logger.warning("xAI generator failed for speaking AI: %s", e)
        raw_text = ""

    # Fallback to Diamondvoy Gemini answer
    if not raw_text.strip():
        try:
            from diamondvoy_helpers import diamondvoy_gemini_answer
            lang_code = "ru" if is_russian else "en"
            subjects_list = ["Russian"] if is_russian else ["English"]
            raw_text = await diamondvoy_gemini_answer(prompt, subjects=subjects_list, lang=lang_code)
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
        start = cleaned.find("{")
        if start >= 0:
            sliced = _balanced_json_object_slice(cleaned, start)
            if sliced:
                parsed = json.loads(sliced, strict=False)

        if parsed is None:
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(cleaned[start:end], strict=False)

        if not isinstance(parsed, dict):
            raise ValueError("Parsed result is not a JSON object")

        def _normalize_item(q: dict[str, Any], is_ru: bool, target_part: int) -> dict[str, Any]:
            q.pop("examiner_tip", None)
            q["subject"] = "russian" if is_ru else "english"
            
            # Normalize question text
            if not q.get("question_text"):
                q["question_text"] = q.get("question") or q.get("prompt") or q.get("text") or "Speaking Question"
            q["question_text"] = str(q["question_text"]).strip()

            # Normalize sample answer
            if not q.get("sample_answer"):
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
                if isinstance(raw_bp, list) and len(raw_bp) > 0:
                    q["cue_card_bullet_points"] = [str(x).strip() for x in raw_bp if x]
                else:
                    q["cue_card_bullet_points"] = [
                        "What or who it is",
                        "When and where it took place",
                        "What occurred in detail",
                        "And explain how you felt about it"
                    ]

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

        if "questions" in parsed and isinstance(parsed["questions"], list) and len(parsed["questions"]) > 0:
            parsed["questions"] = [_normalize_item(q, is_russian, payload.part) for q in parsed["questions"] if isinstance(q, dict)]
            if not parsed.get("topic_title"):
                parsed["topic_title"] = payload.theme or ("Русский язык" if is_russian else f"Part {payload.part} Topic")
            if not parsed.get("status_badge"):
                parsed["status_badge"] = "PREDICTED"
        else:
            # Single question format normalized
            parsed = _normalize_item(parsed, is_russian, payload.part)

        parsed["subject"] = subject_val
        return parsed
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
