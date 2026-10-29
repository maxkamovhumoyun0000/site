"""Speaking app: personal Vocabulary Notebook.

Learners mark a word or a collocation in a question, a sample answer or the
AI feedback and save it.  Every item is enriched once by AI, separately for
each subject:

* English (IELTS): Uzbek and Russian translation, a simple English
  explanation, an IELTS Speaking example, IPA pronunciation, the collocation
  pattern and a "Band 7-9" flag for less common / idiomatic language.
* Russian: Uzbek translation, an explanation in simple Russian, a Russian
  example, the word with its stress mark, grammar (gender, aspect, case
  government) and a "high level" flag for C1-C2 vocabulary.

The learner adds an own example sentence (optionally checked by AI) and marks
the item saved / learned / difficult.  Search works by word, by translation,
by topic and by status.  AI search suggests academic, family-safe vocabulary
only: the 18+ filter runs before any database lookup or AI call, and the
model is told to refuse inappropriate requests.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()

USER_ROLES = {"speaking_user", "student", "teacher", "support", "speaking_admin", "admin", "superadmin", "developer"}
STATUSES = ("saved", "learned", "difficult")
SOURCES = ("question", "sample_answer", "vocabulary", "feedback", "search", "ai_search", "manual")
MAX_TERM_WORDS = 6
MAX_TERM_CHARS = 60
MAX_ITEMS = 2000
_SCHEMA_READY = False


def _user(authorization: str | None) -> dict[str, Any]:
    from backend.main import _require_role, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    _require_role(user, USER_ROLES)
    return user


def _subject_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return "russian" if raw.startswith(("rus", "ru", "рус")) else "english"


def ensure_tables() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_vocab_notebook (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                subject TEXT NOT NULL DEFAULT 'english',
                term TEXT NOT NULL,
                term_key TEXT NOT NULL,
                part_of_speech TEXT NOT NULL DEFAULT '',
                translation_uz TEXT NOT NULL DEFAULT '',
                translation_ru TEXT NOT NULL DEFAULT '',
                explanation TEXT NOT NULL DEFAULT '',
                example TEXT NOT NULL DEFAULT '',
                pronunciation TEXT NOT NULL DEFAULT '',
                grammar_note TEXT NOT NULL DEFAULT '',
                advanced BOOLEAN NOT NULL DEFAULT FALSE,
                level_label TEXT NOT NULL DEFAULT '',
                enriched BOOLEAN NOT NULL DEFAULT FALSE,
                user_example TEXT NOT NULL DEFAULT '',
                user_example_feedback TEXT NOT NULL DEFAULT '{}',
                topic_title TEXT NOT NULL DEFAULT '',
                topic_id BIGINT,
                question_id BIGINT,
                source TEXT NOT NULL DEFAULT 'manual',
                context TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'saved',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (user_id, subject, term_key)
            )"""
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_vocab_notebook_user ON speaking_vocab_notebook(user_id, subject, updated_at DESC)"
        )
        conn.commit()
        _SCHEMA_READY = True
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Text helpers and safety
# ---------------------------------------------------------------------------

def _clean(value: Any, limit: int) -> str:
    text = unicodedata.normalize("NFKC", str(value if value is not None else ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return " ".join(text.split())[:limit]


def normalize_term(value: Any) -> str:
    """The marked word or phrase without surrounding quotes and punctuation."""
    # Russian stress marks belong to the pronunciation, not to the word.
    text = _clean(value, 200).replace("\u0301", "")
    text = text.strip(" \t\"'“”‘’«»()[]{}.,;:!?…-–—")
    return text


def term_key(term: str) -> str:
    return re.sub(r"\s+", " ", term.casefold().replace("ё", "е")).strip()


def is_safe(value: Any) -> bool:
    """The Speaking app's 18+ filter (applied to queries and AI output)."""
    from speaking_contract import is_safe_speaking_vocabulary_query

    text = _clean(value, 2000)
    if not text:
        return True
    if len(text) <= 80:
        return is_safe_speaking_vocabulary_query(text)
    # The filter accepts at most 80 characters; check long text in chunks.
    words = text.split()
    chunks, current = [], ""
    for word in words:
        if len(current) + len(word) + 1 > 70:
            chunks.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    chunks.append(current)
    return all(len(chunk) < 2 or is_safe_speaking_vocabulary_query(chunk) for chunk in chunks)


def validate_term(value: Any) -> str:
    term = normalize_term(value)
    if len(term) < 2:
        raise HTTPException(status_code=422, detail="Select a word or a short phrase.")
    if len(term.split()) > MAX_TERM_WORDS or len(term) > MAX_TERM_CHARS:
        raise HTTPException(status_code=422, detail="Select a word or a short phrase (up to 6 words).")
    if not is_safe(term):
        raise HTTPException(status_code=422, detail="This word cannot be saved. The notebook is for academic vocabulary.")
    return term


def _rate_limit(user_id: int, name: str, limit: int, window: int) -> None:
    from backend.main import _REDIS_CLIENT
    from backend.rate_limiting import consume_rate_limit

    allowed, retry_after = consume_rate_limit(_REDIS_CLIENT, f"speaking-notebook-{name}:{window}:{user_id}", limit=limit, window_seconds=window)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.", headers={"Retry-After": str(retry_after)})


# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

_SAFETY_RULE = (
    "This is a study app for teenagers and adults preparing for exams. Work only with academic, neutral, "
    "family-safe vocabulary. If the request or the term is sexual, vulgar, a swear word, a slur, hateful, "
    "about drugs, self-harm or violence instructions, or otherwise inappropriate for a school app, do not "
    "explain it: return exactly {\"safe\": false}."
)


def enrichment_prompt(subject: str, term: str, context: str, topic: str) -> tuple[str, str]:
    if subject == "english":
        system = (
            "You are a lexicographer writing a vocabulary notebook for IELTS Speaking learners whose first "
            f"language is Uzbek. {_SAFETY_RULE} Otherwise return ONLY compact JSON:\n"
            '{"safe":true,"term":"dictionary form of the word or collocation, as a learner would reuse it",'
            '"part_of_speech":"noun / verb / adjective / phrasal verb / idiom / collocation ...",'
            '"translation_uz":"natural Uzbek (Latin script) translation","translation_ru":"natural Russian translation",'
            '"explanation":"simple English explanation, max 25 words",'
            '"example":"one natural sentence a candidate could say in IELTS Speaking",'
            '"pronunciation":"British IPA between slashes",'
            '"grammar_note":"how it is used, e.g. the collocation pattern: be a double-edged sword",'
            '"band":"7-9 if it is less common, idiomatic or precise language typical of Band 7-9, otherwise 5-6"}'
        )
    else:
        system = (
            "Вы составитель словаря для учащихся, изучающих русский язык; их родной язык узбекский. "
            f"{_SAFETY_RULE} Otherwise return ONLY compact JSON, all explanations in simple Russian:\n"
            '{"safe":true,"term":"словарная форма слова или устойчивого сочетания",'
            '"part_of_speech":"существительное / глагол / прилагательное / устойчивое выражение ...",'
            '"translation_uz":"естественный перевод на узбекский (латиница)",'
            '"translation_ru":"",'
            '"explanation":"простое толкование на русском, до 25 слов",'
            '"example":"одно естественное предложение для устного ответа",'
            '"pronunciation":"слово с ударением, знак ударения над гласной (например: двусмы́сленный)",'
            '"grammar_note":"грамматика: род и склонение для существительного, вид и пара для глагола, управление (кого? чего? за что?)",'
            '"band":"advanced если это лексика уровня C1-C2, иначе intermediate или basic"}'
        )
    user = f"Term the learner marked: {term}\n"
    if context:
        user += f"Sentence where it was found: {context[:500]}\n"
    if topic:
        user += f"Topic: {topic[:120]}\n"
    return system, user


async def _ai_json(system: str, user: str, *, max_tokens: int = 1200) -> dict[str, Any]:
    from backend.speaking_plans import _ai_json as plans_ai_json

    return await plans_ai_json(system, user, max_tokens=max_tokens)


def clean_enrichment(raw: dict[str, Any], subject: str, fallback_term: str) -> dict[str, Any] | None:
    """Validated AI fields, or None when the model refused the term."""
    if not isinstance(raw, dict) or raw.get("safe") is False:
        return None
    term = normalize_term(raw.get("term")) or fallback_term
    if len(term.split()) > MAX_TERM_WORDS + 2 or len(term) > MAX_TERM_CHARS + 20:
        term = fallback_term
    band = _clean(raw.get("band"), 20).lower()
    advanced = band.startswith("7") or band.startswith("8") or band.startswith("9") or "advanced" in band
    fields = {
        "term": term,
        "part_of_speech": _clean(raw.get("part_of_speech"), 60),
        "translation_uz": _clean(raw.get("translation_uz"), 200),
        "translation_ru": _clean(raw.get("translation_ru"), 200) if subject == "english" else "",
        "explanation": _clean(raw.get("explanation"), 400),
        "example": _clean(raw.get("example"), 400),
        "pronunciation": _clean(raw.get("pronunciation"), 80),
        "grammar_note": _clean(raw.get("grammar_note"), 300),
        "advanced": advanced,
        "level_label": ("7-9" if advanced else "5-6") if subject == "english" else ("C1-C2" if advanced else "A2-B2"),
    }
    # Never store unsafe model output.
    for key in ("translation_uz", "translation_ru", "explanation", "example", "grammar_note"):
        if not is_safe(fields[key]):
            fields[key] = ""
    stressed = _clean(raw.get("term"), 120)
    if subject == "russian" and not fields["pronunciation"] and "\u0301" in stressed:
        fields["pronunciation"] = stressed
    if not is_safe(fields["term"]):
        return None
    return fields


async def enrich(subject: str, term: str, context: str, topic: str) -> dict[str, Any] | None:
    system, user = enrichment_prompt(subject, term, context, topic)
    raw = await _ai_json(system, user)
    return clean_enrichment(raw, subject, term)


def _bank_fields(subject: str, term: str) -> dict[str, Any]:
    """Translations from the shared vocabulary bank when AI is unavailable."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT translation_uz, translation_ru, definition, example FROM words
               WHERE LOWER(subject)=%s AND LOWER(word)=%s LIMIT 1""",
            (subject, term.casefold()),
        )
        row = cur.fetchone()
    except Exception:
        conn.rollback()
        row = None
    finally:
        cur.close()
        conn.close()
    if not row:
        return {}
    row = dict(row)
    return {
        "translation_uz": _clean(row.get("translation_uz"), 200),
        "translation_ru": _clean(row.get("translation_ru"), 200) if subject == "english" else "",
        "explanation": _clean(row.get("definition"), 400),
        "example": _clean(row.get("example"), 400),
    }


# ---------------------------------------------------------------------------
# Rows
# ---------------------------------------------------------------------------

def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _public(row: dict[str, Any]) -> dict[str, Any]:
    try:
        feedback = json.loads(row.get("user_example_feedback") or "{}")
    except ValueError:
        feedback = {}
    return {
        "id": int(row["id"]),
        "subject": row["subject"],
        "term": row["term"],
        "part_of_speech": row.get("part_of_speech") or "",
        "translation_uz": row.get("translation_uz") or "",
        "translation_ru": row.get("translation_ru") or "",
        "explanation": row.get("explanation") or "",
        "example": row.get("example") or "",
        "pronunciation": row.get("pronunciation") or "",
        "grammar_note": row.get("grammar_note") or "",
        "advanced": bool(row.get("advanced")),
        "level_label": row.get("level_label") or "",
        "enriched": bool(row.get("enriched")),
        "user_example": row.get("user_example") or "",
        "user_example_feedback": feedback if isinstance(feedback, dict) else {},
        "topic_title": row.get("topic_title") or "",
        "topic_id": row.get("topic_id"),
        "question_id": row.get("question_id"),
        "source": row.get("source") or "manual",
        "context": row.get("context") or "",
        "status": row.get("status") or "saved",
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }


def _question_topic(question_id: int | None) -> tuple[int | None, str]:
    if not question_id:
        return None, ""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT t.id, t.title FROM speaking_questions q JOIN speaking_topics t ON t.id=q.topic_id WHERE q.id=%s",
            (int(question_id),),
        )
        row = cur.fetchone()
    except Exception:
        conn.rollback()
        row = None
    finally:
        cur.close()
        conn.close()
    return (int(dict(row)["id"]), str(dict(row)["title"] or "")) if row else (None, "")


def _item(cur, item_id: int, user_id: int) -> dict[str, Any]:
    cur.execute("SELECT * FROM speaking_vocab_notebook WHERE id=%s AND user_id=%s", (int(item_id), int(user_id)))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Notebook item not found")
    return dict(row)


def search_filter(scope: str, query: str) -> tuple[str, list[Any]]:
    """SQL condition and params for a notebook search."""
    needle = f"%{query.casefold()}%"
    columns = {
        "term": ["term"],
        "translation": ["translation_uz", "translation_ru"],
        "topic": ["topic_title"],
    }.get(scope, ["term", "translation_uz", "translation_ru", "explanation", "example", "topic_title", "user_example"])
    condition = "(" + " OR ".join(f"LOWER({column}) LIKE %s" for column in columns) + ")"
    return condition, [needle] * len(columns)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class Prefill(BaseModel):
    part_of_speech: str = Field(default="", max_length=60)
    translation_uz: str = Field(default="", max_length=200)
    translation_ru: str = Field(default="", max_length=200)
    explanation: str = Field(default="", max_length=400)
    example: str = Field(default="", max_length=400)
    pronunciation: str = Field(default="", max_length=80)
    grammar_note: str = Field(default="", max_length=300)
    advanced: bool = False


class SaveRequest(BaseModel):
    subject: str = Field(default="english", max_length=32)
    term: str = Field(min_length=1, max_length=200)
    context: str = Field(default="", max_length=1500)
    topic_title: str = Field(default="", max_length=200)
    question_id: str = Field(default="", max_length=32)
    source: str = Field(default="manual", max_length=24)
    # Fields of an AI search suggestion, so saving it needs no second AI call.
    prefill: Prefill | None = None


class UpdateRequest(BaseModel):
    status: str | None = Field(default=None, pattern="^(saved|learned|difficult)$")
    user_example: str | None = Field(default=None, max_length=400)
    translation_uz: str | None = Field(default=None, max_length=200)
    translation_ru: str | None = Field(default=None, max_length=200)


class ExampleCheck(BaseModel):
    text: str = Field(min_length=2, max_length=400)


@router.get("/speaking/notebook")
@router.get("/api/speaking/notebook")
async def list_notebook(
    subject: str = Query(default="english", max_length=32),
    q: str = Query(default="", max_length=80),
    scope: str = Query(default="all", pattern="^(all|term|translation|topic)$"),
    status: str = Query(default="", max_length=16),
    topic: str = Query(default="", max_length=200),
    advanced: bool = Query(default=False),
    authorization: str | None = Header(default=None),
):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject_key = _subject_key(subject)
    query = _clean(q, 80)
    where = ["user_id=%s", "subject=%s"]
    params: list[Any] = [user_id, subject_key]
    blocked = False
    if query:
        if not is_safe(query):
            blocked = True
        else:
            condition, values = search_filter(scope, query)
            where.append(condition)
            params.extend(values)
    if status in STATUSES:
        where.append("status=%s")
        params.append(status)
    if topic:
        where.append("LOWER(topic_title)=%s")
        params.append(_clean(topic, 200).casefold())
    if advanced:
        where.append("advanced")
    conn = get_conn()
    cur = conn.cursor()
    try:
        items: list[dict[str, Any]] = []
        if not blocked:
            cur.execute(
                f"SELECT * FROM speaking_vocab_notebook WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT 500",
                params,
            )
            items = [_public(dict(r)) for r in cur.fetchall() or []]
        cur.execute(
            "SELECT status, COUNT(*) AS n FROM speaking_vocab_notebook WHERE user_id=%s AND subject=%s GROUP BY status",
            (user_id, subject_key),
        )
        counts = {s: 0 for s in STATUSES}
        for row in cur.fetchall() or []:
            row = dict(row)
            counts[str(row["status"])] = int(row["n"] or 0)
        cur.execute(
            """SELECT topic_title, COUNT(*) AS n FROM speaking_vocab_notebook
               WHERE user_id=%s AND subject=%s AND topic_title <> '' GROUP BY topic_title ORDER BY n DESC, topic_title LIMIT 60""",
            (user_id, subject_key),
        )
        topics = [{"title": dict(r)["topic_title"], "count": int(dict(r)["n"] or 0)} for r in cur.fetchall() or []]
        return {
            "subject": subject_key,
            "items": items,
            "blocked": blocked,
            "counts": {**counts, "total": sum(counts.values())},
            "topics": topics,
        }
    finally:
        cur.close()
        conn.close()


@router.post("/speaking/notebook")
@router.post("/api/speaking/notebook")
async def save_to_notebook(payload: SaveRequest, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject_key = _subject_key(payload.subject)
    term = validate_term(payload.term)
    key = term_key(term)
    context = _clean(payload.context, 600)
    source = payload.source if payload.source in SOURCES else "manual"
    question_id = int(payload.question_id) if payload.question_id.isdigit() else None
    topic_id, topic_title = _question_topic(question_id)
    topic_title = topic_title or _clean(payload.topic_title, 200)

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM speaking_vocab_notebook WHERE user_id=%s AND subject=%s AND term_key=%s",
            (user_id, subject_key, key),
        )
        existing = cur.fetchone()
        if existing:
            return {"item": _public(dict(existing)), "created": False}
        cur.execute("SELECT COUNT(*) AS n FROM speaking_vocab_notebook WHERE user_id=%s", (user_id,))
        if int(dict(cur.fetchone() or {}).get("n") or 0) >= MAX_ITEMS:
            raise HTTPException(status_code=409, detail=f"The notebook is full ({MAX_ITEMS} items). Delete learned items first.")
    finally:
        cur.close()
        conn.close()

    fields: dict[str, Any] | None
    enriched = False
    if payload.prefill is not None:
        fields = clean_enrichment({"safe": True, "term": term, **payload.prefill.model_dump(),
                                   "band": "7-9" if payload.prefill.advanced else "5-6"}, subject_key, term)
        if fields is None:
            raise HTTPException(status_code=422, detail="This word cannot be saved. The notebook is for academic vocabulary.")
        enriched = True
    else:
        _rate_limit(user_id, "save", 60, 3600)
        _rate_limit(user_id, "save", 300, 86400)
        try:
            fields = await enrich(subject_key, term, context, topic_title)
            if fields is None:
                raise HTTPException(status_code=422, detail="This word cannot be saved. The notebook is for academic vocabulary.")
            enriched = True
        except HTTPException as exc:
            if exc.status_code < 500:
                raise
            # AI is busy: keep the word with what the shared bank knows; the
            # learner can fill the rest later with "Refresh with AI".
            fields = {"term": term, **_bank_fields(subject_key, term)}
    fields.setdefault("term", term)
    key = term_key(fields["term"]) or key

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_vocab_notebook
                 (user_id, subject, term, term_key, part_of_speech, translation_uz, translation_ru, explanation, example,
                  pronunciation, grammar_note, advanced, level_label, enriched, topic_title, topic_id, question_id, source, context)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id, subject, term_key) DO NOTHING RETURNING *""",
            (
                user_id, subject_key, fields["term"], key, fields.get("part_of_speech", ""),
                fields.get("translation_uz", ""), fields.get("translation_ru", ""), fields.get("explanation", ""),
                fields.get("example", ""), fields.get("pronunciation", ""), fields.get("grammar_note", ""),
                bool(fields.get("advanced")), fields.get("level_label", ""), enriched, topic_title, topic_id,
                question_id, source, context,
            ),
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                "SELECT * FROM speaking_vocab_notebook WHERE user_id=%s AND subject=%s AND term_key=%s",
                (user_id, subject_key, key),
            )
            conn.commit()
            return {"item": _public(dict(cur.fetchone())), "created": False}
        conn.commit()
        return {"item": _public(dict(row)), "created": True}
    finally:
        cur.close()
        conn.close()


@router.patch("/speaking/notebook/{item_id}")
@router.patch("/api/speaking/notebook/{item_id}")
async def update_notebook_item(item_id: int, payload: UpdateRequest, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    ensure_tables()
    sets, params = ["updated_at=NOW()"], []
    if payload.status is not None:
        sets.append("status=%s")
        params.append(payload.status)
    if payload.user_example is not None:
        text = _clean(payload.user_example, 400)
        if not is_safe(text):
            raise HTTPException(status_code=422, detail="Please write an appropriate example sentence.")
        sets.append("user_example=%s")
        params.append(text)
        sets.append("user_example_feedback='{}'")
    for key in ("translation_uz", "translation_ru"):
        value = getattr(payload, key)
        if value is not None:
            text = _clean(value, 200)
            if not is_safe(text):
                raise HTTPException(status_code=422, detail="Please write an appropriate translation.")
            sets.append(f"{key}=%s")
            params.append(text)
    conn = get_conn()
    cur = conn.cursor()
    try:
        _item(cur, item_id, int(user.get("id") or 0))
        cur.execute(
            f"UPDATE speaking_vocab_notebook SET {', '.join(sets)} WHERE id=%s AND user_id=%s RETURNING *",
            [*params, int(item_id), int(user.get("id") or 0)],
        )
        row = dict(cur.fetchone())
        conn.commit()
        return {"item": _public(row)}
    finally:
        cur.close()
        conn.close()


@router.delete("/speaking/notebook/{item_id}")
@router.delete("/api/speaking/notebook/{item_id}")
async def delete_notebook_item(item_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM speaking_vocab_notebook WHERE id=%s AND user_id=%s RETURNING id",
            (int(item_id), int(user.get("id") or 0)),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Notebook item not found")
        conn.commit()
        return {"ok": True}
    finally:
        cur.close()
        conn.close()


@router.post("/speaking/notebook/{item_id}/enrich")
@router.post("/api/speaking/notebook/{item_id}/enrich")
async def refresh_notebook_item(item_id: int, authorization: str | None = Header(default=None)):
    """Fill or refresh the AI fields of a saved item."""
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        item = _item(cur, item_id, user_id)
    finally:
        cur.close()
        conn.close()
    _rate_limit(user_id, "save", 60, 3600)
    fields = await enrich(item["subject"], item["term"], item.get("context") or "", item.get("topic_title") or "")
    if fields is None:
        raise HTTPException(status_code=422, detail="This word cannot be explained here.")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE speaking_vocab_notebook SET part_of_speech=%s, translation_uz=%s, translation_ru=%s, explanation=%s,
                 example=%s, pronunciation=%s, grammar_note=%s, advanced=%s, level_label=%s, enriched=TRUE, updated_at=NOW()
               WHERE id=%s AND user_id=%s RETURNING *""",
            (fields["part_of_speech"], fields["translation_uz"], fields["translation_ru"], fields["explanation"],
             fields["example"], fields["pronunciation"], fields["grammar_note"], fields["advanced"], fields["level_label"],
             int(item_id), user_id),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return {"item": _public(row)}
    finally:
        cur.close()
        conn.close()


@router.post("/speaking/notebook/{item_id}/check-example")
@router.post("/api/speaking/notebook/{item_id}/check-example")
async def check_user_example(
    item_id: int,
    payload: ExampleCheck,
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    """Save the learner's own example sentence and let AI check it."""
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    text = _clean(payload.text, 400)
    if not is_safe(text):
        raise HTTPException(status_code=422, detail="Please write an appropriate example sentence.")
    conn = get_conn()
    cur = conn.cursor()
    try:
        item = _item(cur, item_id, user_id)
    finally:
        cur.close()
        conn.close()
    _rate_limit(user_id, "check", 60, 3600)
    from backend.main import _ai_result_language

    subject = item["subject"]
    language = "Russian" if subject == "russian" else _ai_result_language(x_language)
    target = "English" if subject == "english" else "Russian"
    system = (
        f"You are a friendly {target} teacher. The learner wrote their own example sentence with a vocabulary item. "
        "Judge whether the item is used correctly and naturally and whether the sentence is grammatical. "
        f"Write the feedback in {language}. Return ONLY JSON: "
        '{"ok":true,"feedback":"1-2 short sentences","corrected":"corrected natural sentence, same idea"}'
    )
    user_turn = f"Vocabulary item: {item['term']}\nMeaning: {item.get('explanation') or item.get('translation_uz') or ''}\nLearner's sentence: {text}"
    try:
        raw = await _ai_json(system, user_turn, max_tokens=500)
    except HTTPException:
        raw = {}
    feedback = {
        "ok": raw.get("ok") is True,
        "feedback": _clean(raw.get("feedback"), 400),
        "corrected": _clean(raw.get("corrected"), 400),
        "checked": bool(raw),
    }
    if not is_safe(feedback["feedback"]) or not is_safe(feedback["corrected"]):
        feedback.update(feedback="", corrected="")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE speaking_vocab_notebook SET user_example=%s, user_example_feedback=%s, updated_at=NOW()
               WHERE id=%s AND user_id=%s RETURNING *""",
            (text, json.dumps(feedback, ensure_ascii=False), int(item_id), user_id),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return {"item": _public(row)}
    finally:
        cur.close()
        conn.close()


def ai_search_prompt(subject: str, query: str) -> tuple[str, str]:
    if subject == "english":
        shape = (
            '{"blocked":false,"items":[{"term":"...","part_of_speech":"...","translation_uz":"...","translation_ru":"...",'
            '"explanation":"simple English, max 20 words","example":"IELTS Speaking sentence","pronunciation":"/IPA/",'
            '"grammar_note":"collocation pattern","band":"7-9 or 5-6"}]}'
        )
        role = "an IELTS Speaking vocabulary coach for Uzbek learners"
    else:
        shape = (
            '{"blocked":false,"items":[{"term":"словарная форма","part_of_speech":"...","translation_uz":"...","translation_ru":"",'
            '"explanation":"толкование на простом русском","example":"предложение на русском","pronunciation":"слово с ударением",'
            '"grammar_note":"род / вид / управление","band":"advanced, intermediate или basic"}]}'
        )
        role = "a Russian speaking-exam vocabulary coach for Uzbek learners"
    system = (
        f"You are {role}. The learner searches for useful vocabulary. The query may be a word, a meaning in Uzbek or "
        "Russian, or a topic (for example 'environment'). Suggest up to 6 academic, family-safe words or collocations "
        "that match it and are useful in speaking exams. If the query asks for sexual, vulgar, offensive, hateful or "
        "other content inappropriate for a school app, return exactly {\"blocked\":true,\"items\":[]}. "
        f"Return ONLY JSON: {shape}"
    )
    return system, f"Query: {query}"


@router.get("/speaking/notebook/ai-search")
@router.get("/api/speaking/notebook/ai-search")
async def notebook_ai_search(
    subject: str = Query(default="english", max_length=32),
    q: str = Query(default="", max_length=80),
    authorization: str | None = Header(default=None),
):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject_key = _subject_key(subject)
    query = _clean(q, 80)
    if len(query) < 2:
        return {"items": [], "blocked": False}
    if not is_safe(query):
        return {"items": [], "blocked": True}
    _rate_limit(user_id, "ai-search", 30, 3600)
    system, user_turn = ai_search_prompt(subject_key, query)
    try:
        raw = await _ai_json(system, user_turn, max_tokens=2000)
    except HTTPException as exc:
        raise HTTPException(status_code=503, detail="AI search is temporarily unavailable. Please try again.") from exc
    if raw.get("blocked") is True:
        return {"items": [], "blocked": True}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT term_key FROM speaking_vocab_notebook WHERE user_id=%s AND subject=%s", (user_id, subject_key))
        saved = {str(dict(r)["term_key"]) for r in cur.fetchall() or []}
    finally:
        cur.close()
        conn.close()
    items = []
    for candidate in (raw.get("items") or [])[:8]:
        if not isinstance(candidate, dict):
            continue
        term = normalize_term(candidate.get("term"))
        if len(term) < 2 or len(term.split()) > MAX_TERM_WORDS or not is_safe(term):
            continue
        fields = clean_enrichment({**candidate, "safe": True}, subject_key, term)
        if not fields:
            continue
        items.append({**fields, "saved": term_key(fields["term"]) in saved})
    return {"items": items, "blocked": False}
