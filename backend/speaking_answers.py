"""Speaking app: instant AI scoring of recorded answers and the Progress page.

A learner records an answer to a Speaking question in the app. The app uploads
that recording once to ``POST /speaking/answers/analyze``; the server
transcribes it (xAI STT), scores it and returns the result in the same call.

* English answers get an approximate IELTS Speaking band (0-9, half bands)
  from the four public IELTS criteria.
* Russian answers get a 0-10 score from the same four criteria.

The audio is processed in memory and never written to disk: recordings stay
on the device, as the app promises. Only the transcript and the scores are
kept, so the Progress page can chart how the learner improves.
"""
from __future__ import annotations

import json
import logging
import math
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()

USER_ROLES = {"speaking_user", "student", "teacher", "support", "speaking_admin", "admin", "superadmin", "developer"}
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MIN_AUDIO_BYTES = 2 * 1024
MIN_WORDS = 4
# A full mock exam is up to 17 answers, so the limits allow a few per hour.
HOURLY_LIMIT = 60
DAILY_LIMIT = 200
TASHKENT = timezone(timedelta(hours=5))
CRITERIA = ("fluency", "vocabulary", "grammar", "pronunciation")

_SCHEMA_READY = False


def _user(authorization: str | None) -> dict[str, Any]:
    from backend.main import _require_role, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    _require_role(user, USER_ROLES)
    return user


def ensure_tables() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_answer_analyses (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                question_id BIGINT,
                question_ref TEXT NOT NULL DEFAULT '',
                client_recording_id TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT 'english',
                part INTEGER,
                topic_title TEXT NOT NULL DEFAULT '',
                prompt TEXT NOT NULL DEFAULT '',
                scale TEXT NOT NULL DEFAULT 'ielts',
                score DOUBLE PRECISION NOT NULL DEFAULT 0,
                criteria_json TEXT NOT NULL DEFAULT '{}',
                result_json TEXT NOT NULL DEFAULT '{}',
                transcript TEXT NOT NULL DEFAULT '',
                word_count INTEGER NOT NULL DEFAULT 0,
                duration_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        cur.execute("ALTER TABLE speaking_answer_analyses ADD COLUMN IF NOT EXISTS exam_id BIGINT")
        cur.execute("ALTER TABLE speaking_answer_analyses ADD COLUMN IF NOT EXISTS step_index INTEGER")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_answer_exam ON speaking_answer_analyses(exam_id, step_index) WHERE exam_id IS NOT NULL"
        )
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_speaking_answer_recording "
            "ON speaking_answer_analyses(user_id, client_recording_id) WHERE client_recording_id <> ''"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_answer_user_time "
            "ON speaking_answer_analyses(user_id, subject, created_at DESC)"
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_speaking_answer_user_question "
            "ON speaking_answer_analyses(user_id, question_ref, created_at DESC)"
        )
        conn.commit()
        _SCHEMA_READY = True
    finally:
        cur.close()
        conn.close()


def _subject_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return "russian" if raw.startswith(("rus", "ru", "рус")) else "english"


def round_half(value: float) -> float:
    """IELTS rounding: .25 goes up to .5 and .75 goes up to the next band."""
    return math.floor(float(value) * 2 + 0.5) / 2


def _clamp(value: Any, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return low
    if math.isnan(number):
        return low
    return max(low, min(high, number))


def _clean_list(value: Any, *, limit: int, keys: tuple[str, ...] | None = None) -> list:
    if not isinstance(value, list):
        return []
    out: list = []
    for item in value:
        if keys:
            if not isinstance(item, dict):
                continue
            cleaned = {key: str(item.get(key) or "").strip()[:400] for key in keys}
            if any(cleaned.values()):
                out.append(cleaned)
        else:
            text = str(item or "").strip()
            if text:
                out.append(text[:400])
        if len(out) >= limit:
            break
    return out


def normalize_ai_result(raw: dict[str, Any], *, scale: str) -> dict[str, Any]:
    """Validate the model's JSON and compute the overall score ourselves."""
    top = 9.0 if scale == "ielts" else 10.0
    criteria_raw = raw.get("criteria") if isinstance(raw.get("criteria"), dict) else {}
    criteria = {}
    for key in CRITERIA:
        value = criteria_raw.get(key, raw.get(f"{key}_score"))
        criteria[key] = round_half(_clamp(value, 0.0, top))
    overall = round_half(sum(criteria.values()) / len(criteria))
    return {
        "score": overall,
        "max_score": top,
        "criteria": criteria,
        "on_topic": raw.get("on_topic") is not False,
        "summary": str(raw.get("summary") or "").strip()[:700],
        "strengths": _clean_list(raw.get("strengths"), limit=4),
        "improvements": _clean_list(raw.get("improvements"), limit=5),
        "grammar_errors": _clean_list(raw.get("grammar_errors"), limit=6, keys=("original", "correction", "explanation")),
        "vocabulary_suggestions": _clean_list(raw.get("vocabulary_suggestions"), limit=6, keys=("original", "better", "note")),
        "pronunciation_notes": _clean_list(raw.get("pronunciation_notes"), limit=4, keys=("word", "note")),
        "improved_answer": str(raw.get("improved_answer") or "").strip()[:2500],
    }


def _scoring_prompt(*, scale: str, part: int | None, topic: str, prompt: str, bullets: str,
                    transcript: str, duration: float, word_count: int, result_language: str) -> tuple[str, str]:
    if scale == "ielts":
        rubric = (
            "You are a certified IELTS Speaking examiner. Score this ONE answer with the public IELTS Speaking band "
            "descriptors. Give each criterion a band from 0 to 9 in steps of 0.5:\n"
            "- fluency = Fluency and Coherence (length, pace, hesitation, linking, logical development)\n"
            "- vocabulary = Lexical Resource (range, precision, collocation, idiomatic use, paraphrase)\n"
            "- grammar = Grammatical Range and Accuracy (variety of structures, error frequency)\n"
            "- pronunciation = Pronunciation, judged from the speech-to-text transcript: words recognised as other "
            "words, missing endings and broken words suggest pronunciation problems. Be cautious here.\n"
            "Be realistic, like a real examiner: most learners are 5.0-6.5; 7.5+ needs genuinely natural, flexible, "
            "accurate speech. A very short answer cannot score above 5.0 for fluency. An off-topic answer is "
            "penalised in fluency (coherence)."
        )
        part_note = {
            1: "This is IELTS Part 1: a natural answer is 2-4 sentences (about 20-40 seconds).",
            2: "This is IELTS Part 2 (long turn): the candidate should speak for 1-2 minutes and cover the cue card.",
            3: "This is IELTS Part 3: expect an extended, reasoned answer with examples (about 40-90 seconds).",
        }.get(int(part or 0), "")
        improved = "a natural Band 8 version of the student's own answer, keeping their ideas"
    else:
        rubric = (
            "You are an experienced examiner of spoken Russian (ТРКИ style). Score this ONE answer from 0 to 10 in "
            "steps of 0.5 for each criterion:\n"
            "- fluency = fluency and coherence (length, pace, hesitation, logical connection)\n"
            "- vocabulary = range and accuracy of vocabulary\n"
            "- grammar = grammar accuracy: cases, verb aspect, agreement, word order\n"
            "- pronunciation = pronunciation judged from the speech-to-text transcript (be cautious)\n"
            "Be realistic: 9-10 means near-native, 5-6 means understandable with frequent errors. "
            "A very short or off-topic answer is penalised in fluency."
        )
        part_note = ""
        improved = "an improved, natural version of the student's own answer in Russian, keeping their ideas"
    system = (
        f"{rubric}\n{part_note}\n"
        f"Write summary, strengths, improvements and every explanation/note field in {result_language}. "
        "Keep the student's quoted words and corrections in the language they spoke. "
        "Return ONLY compact valid JSON, no markdown, with exactly these keys:\n"
        '{"criteria":{"fluency":6.0,"vocabulary":6.0,"grammar":5.5,"pronunciation":6.0},'
        '"on_topic":true,"summary":"2-3 sentences",'
        '"strengths":["..."],"improvements":["concrete, actionable tip"],'
        '"grammar_errors":[{"original":"...","correction":"...","explanation":"..."}],'
        '"vocabulary_suggestions":[{"original":"...","better":"...","note":"..."}],'
        '"pronunciation_notes":[{"word":"...","note":"..."}],'
        f'"improved_answer":"{improved}"}}\n'
        "At most 4 grammar errors, 4 vocabulary suggestions, 3 pronunciation notes."
    )
    user = (
        f"Topic: {topic or '-'}\nQuestion: {prompt or '-'}\n"
        + (f"Cue card points: {bullets}\n" if bullets else "")
        + f"Recording length: {round(duration)} seconds, {word_count} words.\n"
        f"Transcript of the student's spoken answer:\n{transcript}"
    )
    return system, user


async def _transcribe_bytes(raw: bytes, filename: str, language: str) -> str:
    import aiohttp
    from ai_generator import _get_xai_api_key

    try:
        api_key = _get_xai_api_key()
    except Exception:
        raise HTTPException(status_code=503, detail="AI service is not configured")
    form = aiohttp.FormData()
    form.add_field("language", language)
    form.add_field("format", "true")
    # xAI STT requires the file to be the last multipart field.
    form.add_field("file", raw, filename=filename, content_type="audio/mp4")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.x.ai/v1/stt",
                headers={"Authorization": f"Bearer {api_key}"},
                data=form,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    logger.warning("speaking answer stt status=%s", resp.status)
                    raise HTTPException(status_code=503, detail="Speech recognition failed. Please try again.")
                data = await resp.json(content_type=None)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("speaking answer stt error=%s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Speech recognition failed. Please try again.")
    return str((data or {}).get("text") or "").strip()


async def _score(system: str, user: str) -> dict[str, Any]:
    import aiohttp
    from ai_generator import XAI_ENDPOINT, _get_xai_api_key, _xai_apply_payload_tuning, _xai_model_supports_reasoning_effort
    from backend.main import _homework_ai_model_candidates

    api_key = _get_xai_api_key()
    async with aiohttp.ClientSession() as session:
        for model in _homework_ai_model_candidates()[:2]:
            body: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.2,
                "max_tokens": 1500,
            }
            _xai_apply_payload_tuning(body, model=model, stream=False)
            if _xai_model_supports_reasoning_effort(model):
                body["reasoning_effort"] = "low"
            try:
                async with session.post(
                    XAI_ENDPOINT,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as resp:
                    if resp.status != 200:
                        logger.warning("speaking answer score status=%s model=%s", resp.status, model)
                        continue
                    data = await resp.json(content_type=None)
            except Exception as exc:
                logger.warning("speaking answer score error=%s model=%s", type(exc).__name__, model)
                continue
            text = str(((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                continue
            try:
                parsed = json.loads(match.group(0))
            except ValueError:
                continue
            if isinstance(parsed, dict):
                return parsed
    raise HTTPException(status_code=503, detail="AI scoring is temporarily unavailable. Please try again.")


def _question_row(question_id: int | None) -> dict[str, Any] | None:
    if not question_id:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT q.id, q.part, q.question_text, q.cue_card_bullet_points,
                      COALESCE(q.subject, t.subject, 'english') AS subject, t.title AS topic_title
               FROM speaking_questions q JOIN speaking_topics t ON t.id = q.topic_id
               WHERE q.id = %s LIMIT 1""",
            (int(question_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    try:
        result = json.loads(row.get("result_json") or "{}")
    except ValueError:
        result = {}
    created = row.get("created_at")
    duration = float(row.get("duration_seconds") or 0)
    words = int(row.get("word_count") or 0)
    return {
        **result,
        "id": int(row.get("id") or 0),
        "question_id": str(row.get("question_ref") or row.get("question_id") or ""),
        "client_recording_id": str(row.get("client_recording_id") or ""),
        # Mock exam answers: which exam and step (their audio is kept on the
        # device under that exam), so attempts of one question can be compared.
        "exam_id": int(row["exam_id"]) if row.get("exam_id") is not None else None,
        "step_index": int(row["step_index"]) if row.get("step_index") is not None else None,
        "subject": str(row.get("subject") or "english"),
        "part": row.get("part"),
        "scale": str(row.get("scale") or "ielts"),
        "score": float(row.get("score") or 0),
        "transcript": str(row.get("transcript") or ""),
        "word_count": words,
        "duration_seconds": round(duration, 1),
        "words_per_minute": round(words * 60 / duration) if duration >= 5 else None,
        "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created or ""),
    }


def _existing(user_id: int, client_recording_id: str) -> dict[str, Any] | None:
    if not client_recording_id:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM speaking_answer_analyses WHERE user_id=%s AND client_recording_id=%s LIMIT 1",
            (user_id, client_recording_id),
        )
        row = cur.fetchone()
        return _serialize(dict(row)) if row else None
    finally:
        cur.close()
        conn.close()


def _exam_step_question(user_id: int, exam_id: int, step_index: int) -> tuple[str, str]:
    """Question id and idempotency key of one step of the user's open exam."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status, steps_json FROM speaking_exams WHERE id=%s AND user_id=%s", (exam_id, user_id))
        row = cur.fetchone()
    except Exception:
        conn.rollback()
        row = None
    finally:
        cur.close()
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Exam not found")
    row = dict(row)
    if row.get("status") != "started":
        raise HTTPException(status_code=409, detail="This exam is already finished")
    steps = json.loads(row.get("steps_json") or "[]")
    step = next((s for s in steps if int(s.get("index") or 0) == step_index), None)
    if not step:
        raise HTTPException(status_code=422, detail="Unknown exam question")
    return str(step.get("question_id") or ""), f"exam-{exam_id}-{step_index}"


def _enforce_limits(user_id: int) -> None:
    from backend.main import _REDIS_CLIENT
    from backend.rate_limiting import consume_rate_limit

    for window, limit in ((3600, HOURLY_LIMIT), (86400, DAILY_LIMIT)):
        allowed, retry_after = consume_rate_limit(
            _REDIS_CLIENT, f"speaking-answer-analyze:{window}:{user_id}", limit=limit, window_seconds=window
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="You have reached the answer analysis limit for now. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


@router.post("/speaking/answers/analyze")
@router.post("/api/speaking/answers/analyze")
async def analyze_speaking_answer(
    file: UploadFile = File(...),
    question_id: str = Form(default="", max_length=64),
    client_recording_id: str = Form(default="", max_length=120),
    duration_seconds: float = Form(default=0.0, ge=0, le=900),
    subject: str = Form(default="", max_length=32),
    part: int | None = Form(default=None, ge=1, le=3),
    topic_title: str = Form(default="", max_length=300),
    prompt: str = Form(default="", max_length=1200),
    exam_id: int | None = Form(default=None, ge=1),
    step_index: int | None = Form(default=None, ge=0, le=60),
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    recording_ref = re.sub(r"[^A-Za-z0-9_.:-]", "", client_recording_id)[:120]
    cached = _existing(user_id, recording_ref)
    if cached:
        return {"analysis": cached, "cached": True}

    raw = await file.read(MAX_AUDIO_BYTES + 1)
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The recording is too long (max 10 MB).")
    if len(raw) < MIN_AUDIO_BYTES:
        raise HTTPException(status_code=422, detail="The recording is too short. Please answer for a few seconds.")
    if raw[4:8] != b"ftyp":
        raise HTTPException(status_code=422, detail="Unsupported audio format. Please record again in the app.")

    if exam_id is not None:
        # Exam answers: the exam (not the client) decides which question this is.
        question_id, recording_ref = _exam_step_question(user_id, int(exam_id), int(step_index or 0))
        cached = _existing(user_id, recording_ref)
        if cached:
            return {"analysis": cached, "cached": True}
    question_ref = re.sub(r"[^A-Za-z0-9_.-]", "", question_id)[:64]
    numeric_id = int(question_ref) if question_ref.isdigit() else None
    row = _question_row(numeric_id)
    if row:
        subject_key = _subject_key(row.get("subject"))
        part_value = int(row.get("part") or 0) or None
        topic = str(row.get("topic_title") or "")
        question_text = str(row.get("question_text") or "")
        bullets = str(row.get("cue_card_bullet_points") or "")
    else:
        numeric_id = None
        subject_key = _subject_key(subject)
        part_value = part
        topic = topic_title.strip()
        question_text = prompt.strip()
        bullets = ""
    scale = "ielts" if subject_key == "english" else "ten"

    _enforce_limits(user_id)
    from backend.main import _ai_result_language

    started = time.monotonic()
    transcript = await _transcribe_bytes(raw, "answer.m4a", "en" if subject_key == "english" else "ru")
    word_count = len(re.findall(r"[\w'-]+", transcript, re.UNICODE))
    if word_count < MIN_WORDS:
        raise HTTPException(
            status_code=422,
            detail="We could not hear a clear answer. Please speak a little longer and closer to the microphone.",
        )
    duration = float(duration_seconds or 0)
    system, user_turn = _scoring_prompt(
        scale=scale, part=part_value, topic=topic, prompt=question_text, bullets=bullets,
        transcript=transcript[:6000], duration=duration, word_count=word_count,
        # Russian answers are analysed entirely in Russian; English answers
        # get feedback in the app's interface language.
        result_language="Russian" if subject_key == "russian" else _ai_result_language(x_language),
    )
    result = normalize_ai_result(await _score(system, user_turn), scale=scale)
    logger.info("speaking answer analyzed user=%s scale=%s ms=%s", user_id, scale, int((time.monotonic() - started) * 1000))

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_answer_analyses
                   (user_id, question_id, question_ref, client_recording_id, subject, part, topic_title, prompt,
                    scale, score, criteria_json, result_json, transcript, word_count, duration_seconds,
                    exam_id, step_index)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id, client_recording_id) WHERE client_recording_id <> '' DO NOTHING
               RETURNING *""",
            (
                user_id, numeric_id, question_ref, recording_ref, subject_key, part_value, topic[:300],
                question_text[:1200], scale, result["score"], json.dumps(result["criteria"]),
                json.dumps(result, ensure_ascii=False), transcript[:8000], word_count, duration,
                exam_id, step_index if exam_id is not None else None,
            ),
        )
        saved = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        conn.close()
    if not saved:
        # A parallel request for the same recording finished first.
        existing = _existing(user_id, recording_ref)
        if existing:
            return {"analysis": existing, "cached": True}
        raise HTTPException(status_code=409, detail="This recording was already analysed")
    return {"analysis": _serialize(dict(saved)), "cached": False}


@router.get("/speaking/answers/analyses")
@router.get("/api/speaking/answers/analyses")
async def list_speaking_answer_analyses(
    question_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Header(default=None),
):
    user = _user(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if question_id:
            cur.execute(
                "SELECT * FROM speaking_answer_analyses WHERE user_id=%s AND question_ref=%s ORDER BY created_at DESC LIMIT %s",
                (int(user.get("id") or 0), re.sub(r"[^A-Za-z0-9_.-]", "", question_id)[:64], limit),
            )
        else:
            cur.execute(
                "SELECT * FROM speaking_answer_analyses WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
                (int(user.get("id") or 0), limit),
            )
        return {"items": [_serialize(dict(row)) for row in cur.fetchall() or []]}
    finally:
        cur.close()
        conn.close()


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def build_progress(rows: list[dict[str, Any]], learning_rows: list[dict[str, Any]], *, weeks: int, now: datetime) -> dict[str, Any]:
    """Aggregate analyses (oldest first) into the Progress page payload."""
    local_now = now.astimezone(TASHKENT)
    this_monday = (local_now - timedelta(days=local_now.weekday())).date()
    week_starts = [this_monday - timedelta(weeks=offset) for offset in range(weeks - 1, -1, -1)]
    weekly = {start: {"answers": 0, "scores": [], "seconds": 0.0, "lp_attempts": 0, "lp_scores": []} for start in week_starts}
    daily_starts = [local_now.date() - timedelta(days=offset) for offset in range(13, -1, -1)]
    daily = {day: {"answers": 0, "scores": []} for day in daily_starts}
    criteria_recent: dict[str, list[float]] = {key: [] for key in CRITERIA}
    criteria_previous: dict[str, list[float]] = {key: [] for key in CRITERIA}
    by_part: dict[int, list[float]] = {1: [], 2: [], 3: []}
    questions: dict[str, dict[str, Any]] = {}
    active_days: set = set()
    scores = [float(row.get("score") or 0) for row in rows]

    for row in rows:
        created = _as_utc(row.get("created_at"))
        if not created:
            continue
        local = created.astimezone(TASHKENT)
        day = local.date()
        active_days.add(day)
        score = float(row.get("score") or 0)
        week = day - timedelta(days=day.weekday())
        if week in weekly:
            weekly[week]["answers"] += 1
            weekly[week]["scores"].append(score)
            weekly[week]["seconds"] += float(row.get("duration_seconds") or 0)
        if day in daily:
            daily[day]["answers"] += 1
            daily[day]["scores"].append(score)
        age_days = (local_now - local).days
        try:
            crit = json.loads(row.get("criteria_json") or "{}")
        except ValueError:
            crit = {}
        for key in CRITERIA:
            if key in crit and age_days < 30:
                criteria_recent[key].append(float(crit[key]))
            elif key in crit and age_days < 60:
                criteria_previous[key].append(float(crit[key]))
        part = int(row.get("part") or 0)
        if part in by_part:
            by_part[part].append(score)
        ref = str(row.get("question_ref") or "")
        if ref:
            entry = questions.setdefault(ref, {
                "question_id": ref, "prompt": str(row.get("prompt") or ""), "topic": str(row.get("topic_title") or ""),
                "part": row.get("part"), "scores": [],
            })
            entry["scores"].append(score)

    for row in learning_rows:
        created = _as_utc(row.get("created_at"))
        if not created:
            continue
        day = created.astimezone(TASHKENT).date()
        active_days.add(day)
        week = day - timedelta(days=day.weekday())
        if week in weekly:
            weekly[week]["lp_attempts"] += 1
            weekly[week]["lp_scores"].append(float(row.get("score") or 0))

    streak = 0
    cursor = local_now.date()
    if cursor not in active_days:
        cursor -= timedelta(days=1)
    while cursor in active_days:
        streak += 1
        cursor -= timedelta(days=1)

    # Compare the earliest and the latest answers without overlap: up to 5
    # each, and half of the answers each while there are fewer than 10.
    window = max(1, min(5, len(scores) // 2))
    first = scores[:window]
    last = scores[-window:]
    recent_week = [float(r.get("score") or 0) for r in rows if (_as_utc(r.get("created_at")) or now) >= now - timedelta(days=7)]
    previous_week = [
        float(r.get("score") or 0) for r in rows
        if now - timedelta(days=14) <= (_as_utc(r.get("created_at")) or now) < now - timedelta(days=7)
    ]
    question_changes = []
    for entry in questions.values():
        if len(entry["scores"]) < 2:
            continue
        question_changes.append({
            "question_id": entry["question_id"], "prompt": entry["prompt"][:240], "topic": entry["topic"][:120],
            "part": entry["part"], "attempts": len(entry["scores"]), "first_score": entry["scores"][0],
            "best_score": max(entry["scores"]), "last_score": entry["scores"][-1],
            "change": round(entry["scores"][-1] - entry["scores"][0], 2),
        })
    question_changes.sort(key=lambda item: abs(item["change"]), reverse=True)

    def part_entry(part: int, values: list[float]) -> dict[str, Any]:
        size = max(1, min(5, len(values) // 2))
        first_avg = _avg(values[:size]) if len(values) >= 2 else None
        recent_avg = _avg(values[-size:]) if len(values) >= 2 else None
        return {
            "part": part, "answers": len(values), "average_score": _avg(values),
            "first_average": first_avg, "recent_average": recent_avg,
            "change": round(recent_avg - first_avg, 2) if first_avg is not None and recent_avg is not None else None,
        }

    return {
        "summary": {
            "total_answers": len(rows),
            "total_minutes": round(sum(float(r.get("duration_seconds") or 0) for r in rows) / 60, 1),
            "average_score": _avg(scores),
            "best_score": max(scores) if scores else None,
            "latest_score": scores[-1] if scores else None,
            "first_average": _avg(first),
            "recent_average": _avg(last),
            "improvement": round(_avg(last) - _avg(first), 2) if len(scores) >= 2 else None,
            "this_week_average": _avg(recent_week),
            "previous_week_average": _avg(previous_week),
            "week_change": round(_avg(recent_week) - _avg(previous_week), 2) if recent_week and previous_week else None,
            "streak_days": streak,
            "active_days_30": len([d for d in active_days if (local_now.date() - d).days < 30]),
            "practice_days": len(active_days),
            "learning_attempts": len(learning_rows),
        },
        "weekly": [
            {
                "week_start": start.isoformat(),
                "answers": weekly[start]["answers"],
                "average_score": _avg(weekly[start]["scores"]),
                "minutes": round(weekly[start]["seconds"] / 60, 1),
                "learning_attempts": weekly[start]["lp_attempts"],
                "learning_average": _avg(weekly[start]["lp_scores"]),
            }
            for start in week_starts
        ],
        "daily": [
            {"date": day.isoformat(), "answers": daily[day]["answers"], "average_score": _avg(daily[day]["scores"])}
            for day in daily_starts
        ],
        "score_trend": [
            {
                "score": float(row.get("score") or 0),
                "part": row.get("part"),
                "question_id": str(row.get("question_ref") or ""),
                "created_at": (_as_utc(row.get("created_at")) or now).isoformat(),
            }
            for row in rows[-40:]
        ],
        "criteria": [
            {"key": key, "average": _avg(criteria_recent[key]), "previous_average": _avg(criteria_previous[key])}
            for key in CRITERIA
        ],
        "by_part": [part_entry(part, values) for part, values in by_part.items()],
        "band_estimate": band_estimate_series(rows),
        "question_changes": question_changes[:20],
    }


def band_estimate_series(rows: list[dict[str, Any]], *, window: int = 5, limit: int = 30) -> list[dict[str, Any]]:
    """Estimated band at the end of every practice day: the rounded average of
    the last ``window`` answers up to that day (rows oldest first)."""
    by_day: dict[Any, int] = {}
    ordered = [row for row in rows if _as_utc(row.get("created_at"))]
    for index, row in enumerate(ordered):
        by_day[_as_utc(row["created_at"]).astimezone(TASHKENT).date()] = index
    series = []
    for day, last_index in sorted(by_day.items()):
        recent = [float(r.get("score") or 0) for r in ordered[max(0, last_index - window + 1): last_index + 1]]
        series.append({
            "date": day.isoformat(),
            "estimate": round_half(sum(recent) / len(recent)),
            "answers": last_index + 1,
        })
    return series[-limit:]


def _topic_key(row: dict[str, Any], titles: dict[str, int]) -> tuple[str, int | None, str]:
    title = str(row.get("topic_title") or "").strip()
    topic_id = row.get("topic_id")
    if topic_id is None and title:
        topic_id = titles.get(title.casefold())
    if topic_id is not None:
        return f"id:{int(topic_id)}", int(topic_id), title
    return f"title:{title.casefold()}", None, title


def build_topic_insights(rows: list[dict[str, Any]], bank_topics: list[dict[str, Any]], *, subject: str,
                         now: datetime, user_id: int = 0) -> dict[str, Any]:
    """Most practised, weakest and weak topics with reasons, plus one
    re-practice recommendation.

    Weak topic signals: a low AI band, slow answers with many pauses (low
    words per minute or a low fluency score), many grammar errors and topics
    the learner has practised little or not at all.
    """
    scale_low = 5.0
    slow_wpm = 90.0 if subject == "english" else 70.0
    bank_by_id = {int(t["id"]): t for t in bank_topics if t.get("id") is not None}
    titles = {str(t.get("title") or "").strip().casefold(): int(t["id"]) for t in bank_topics if t.get("title")}
    topics: dict[str, dict[str, Any]] = {}
    all_scores: list[float] = []
    all_criteria: dict[str, list[float]] = {key: [] for key in CRITERIA}
    for row in rows:
        key, topic_id, title = _topic_key(row, titles)
        if not title and topic_id in bank_by_id:
            title = str(bank_by_id[topic_id].get("title") or "")
        if not title:
            continue
        entry = topics.setdefault(key, {
            "topic_id": topic_id, "title": title,
            "part": row.get("part") or (bank_by_id.get(topic_id) or {}).get("part"),
            "scores": [], "criteria": {k: [] for k in CRITERIA}, "wpm": [], "grammar_errors": [],
            "seconds": 0.0, "last": None,
        })
        score = float(row.get("score") or 0)
        entry["scores"].append(score)
        all_scores.append(score)
        try:
            crit = json.loads(row.get("criteria_json") or "{}")
        except ValueError:
            crit = {}
        for k in CRITERIA:
            if crit.get(k) is not None:
                entry["criteria"][k].append(float(crit[k]))
                all_criteria[k].append(float(crit[k]))
        duration = float(row.get("duration_seconds") or 0)
        entry["seconds"] += duration
        if duration >= 10:
            entry["wpm"].append(int(row.get("word_count") or 0) * 60 / duration)
        if row.get("grammar_errors") is not None:
            entry["grammar_errors"].append(int(row.get("grammar_errors") or 0))
        created = _as_utc(row.get("created_at"))
        if created and (entry["last"] is None or created > entry["last"]):
            entry["last"] = created

    overall = _avg(all_scores)
    overall_crit = {k: _avg(v) for k, v in all_criteria.items()}
    items = []
    for entry in topics.values():
        avg = _avg(entry["scores"])
        crit = {k: _avg(v) for k, v in entry["criteria"].items()}
        wpm = round(sum(entry["wpm"]) / len(entry["wpm"])) if entry["wpm"] else None
        errors = round(sum(entry["grammar_errors"]) / len(entry["grammar_errors"]), 1) if entry["grammar_errors"] else None
        reasons: list[str] = []
        severity = 0.0
        if avg is not None and ((overall is not None and len(all_scores) >= 5 and avg <= overall - 0.5) or avg < scale_low):
            reasons.append("low_band")
            severity += max(0.5, (overall or avg) - avg + (scale_low - avg if avg < scale_low else 0))
        fluency = crit.get("fluency")
        if (wpm is not None and wpm < slow_wpm) or (
            fluency is not None and overall_crit.get("fluency") is not None and fluency <= overall_crit["fluency"] - 0.5
        ):
            reasons.append("pauses")
            severity += 0.75
        grammar = crit.get("grammar")
        if (errors is not None and errors >= 2.0) or (
            grammar is not None and overall_crit.get("grammar") is not None and grammar <= overall_crit["grammar"] - 0.5
        ):
            reasons.append("grammar")
            severity += 0.75
        last = entry["last"]
        if len(entry["scores"]) == 1 and last is not None and (now - last).days >= 14:
            reasons.append("low_practice")
            severity += 0.25
        weakest = min((k for k in CRITERIA if crit.get(k) is not None), key=lambda k: crit[k], default=None)
        items.append({
            "topic_id": entry["topic_id"], "title": entry["title"][:160], "part": entry["part"],
            "answers": len(entry["scores"]), "average_score": avg, "best_score": max(entry["scores"]),
            "minutes": round(entry["seconds"] / 60, 1), "words_per_minute": wpm,
            "grammar_errors_per_answer": errors, "criteria": crit, "weakest_criterion": weakest,
            "last_practiced": last.isoformat() if last else None,
            "reasons": reasons, "severity": round(severity, 2),
        })

    most = sorted(items, key=lambda i: (-i["answers"], -(i["average_score"] or 0)))[:6]
    weakest_topics = sorted(
        [i for i in items if i["average_score"] is not None],
        key=lambda i: (i["average_score"], -i["answers"]),
    )[:6]
    weak = sorted([i for i in items if i["reasons"]], key=lambda i: -i["severity"])[:6]

    # Topics in the bank the learner has not practised yet (stable per day).
    practised_ids = {i["topic_id"] for i in items if i["topic_id"] is not None}
    unpractised = [t for t in bank_topics if t.get("id") is not None and int(t["id"]) not in practised_ids]
    rng = random.Random(f"{user_id}:{subject}:{now.astimezone(TASHKENT).date().isoformat()}")
    rng.shuffle(unpractised)
    for topic in unpractised[: max(0, min(3, 8 - len(weak)))]:
        weak.append({
            "topic_id": int(topic["id"]), "title": str(topic.get("title") or "")[:160], "part": topic.get("part"),
            "answers": 0, "average_score": None, "best_score": None, "minutes": 0.0, "words_per_minute": None,
            "grammar_errors_per_answer": None, "criteria": {}, "weakest_criterion": None, "last_practiced": None,
            "reasons": ["low_practice"], "severity": 0.1,
        })

    recommendation = None
    for item in weak:
        if item["topic_id"] is None:
            continue
        reason = item["reasons"][0]
        criterion = item["weakest_criterion"]
        if reason == "pauses":
            criterion = "fluency"
        elif reason == "grammar":
            criterion = "grammar"
        recommendation = {
            "topic_id": item["topic_id"], "title": item["title"], "part": item["part"],
            "reason": reason, "criterion": criterion, "minutes": 5,
            "average_score": item["average_score"],
        }
        break
    return {"most_practiced": most, "weakest": weakest_topics, "weak": weak, "recommendation": recommendation}


def _exam_progress(user_id: int, subject_key: str) -> dict[str, Any]:
    """Recent finished mock exams and the Daily Challenge streak."""
    try:
        from backend.speaking_exams import ensure_tables as ensure_exam_tables, streak_from_days, _today

        ensure_exam_tables()
    except Exception:
        return {"mock_exams": [], "challenge_streak": {"current": 0, "best": 0}}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, kind, mode, parts, overall, finished_at, result_json FROM speaking_exams
               WHERE user_id=%s AND subject=%s AND status='finished' AND kind='mock'
               ORDER BY finished_at DESC LIMIT 12""",
            (user_id, subject_key),
        )
        exams = []
        for row in cur.fetchall() or []:
            item = dict(row)
            result = json.loads(item.get("result_json") or "{}")
            finished = item.get("finished_at")
            exams.append({
                "id": int(item["id"]), "mode": item.get("mode"), "parts": item.get("parts"),
                "overall": item.get("overall"), "part_scores": result.get("part_scores") or {},
                "finished_at": finished.isoformat() if hasattr(finished, "isoformat") else str(finished or ""),
            })
        exams.reverse()
        cur.execute("SELECT day FROM speaking_daily_challenges WHERE user_id=%s AND subject=%s", (user_id, subject_key))
        days = [dict(r)["day"] for r in cur.fetchall() or []]
    except Exception:
        conn.rollback()
        return {"mock_exams": [], "challenge_streak": {"current": 0, "best": 0}}
    finally:
        cur.close()
        conn.close()
    current, best = streak_from_days(days, _today())
    return {"mock_exams": exams, "challenge_streak": {"current": current, "best": best}}


@router.get("/speaking/progress")
@router.get("/api/speaking/progress")
async def speaking_progress(
    subject: str = Query(default="english", max_length=32),
    weeks: int = Query(default=12, ge=4, le=26),
    authorization: str | None = Header(default=None),
):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject_key = _subject_key(subject)
    now = datetime.now(timezone.utc)
    conn = get_conn()
    cur = conn.cursor()
    try:
        base_columns = (
            "a.score, a.part, a.question_ref, a.prompt, a.topic_title, a.criteria_json, a.duration_seconds, "
            "a.word_count, a.created_at, q.topic_id"
        )
        grammar_column = (
            "CASE WHEN jsonb_typeof(a.result_json::jsonb -> 'grammar_errors') = 'array' "
            "THEN jsonb_array_length(a.result_json::jsonb -> 'grammar_errors') END AS grammar_errors"
        )
        query = (
            "SELECT {columns} FROM speaking_answer_analyses a "
            "LEFT JOIN speaking_questions q ON q.id = a.question_id "
            "WHERE a.user_id=%s AND a.subject=%s ORDER BY a.created_at DESC LIMIT 3000"
        )
        try:
            cur.execute(query.format(columns=f"{base_columns}, {grammar_column}"), (user_id, subject_key))
        except Exception:
            # A malformed stored result must not hide the whole Progress page.
            conn.rollback()
            cur.execute(query.format(columns=base_columns), (user_id, subject_key))
        rows = [dict(row) for row in cur.fetchall() or []]
        rows.reverse()
        bank_topics: list[dict[str, Any]] = []
        try:
            cur.execute(
                """SELECT t.id, t.title, t.part FROM speaking_topics t
                   WHERE LOWER(COALESCE(t.subject, 'english'))=%s
                     AND EXISTS (SELECT 1 FROM speaking_questions q WHERE q.topic_id=t.id AND COALESCE(q.question_text,'') <> '')""",
                (subject_key,),
            )
            bank_topics = [dict(row) for row in cur.fetchall() or []]
        except Exception:
            conn.rollback()
        learning_rows: list[dict[str, Any]] = []
        try:
            cur.execute(
                """SELECT a.score, a.created_at
                   FROM speaking_learning_attempts a
                   JOIN speaking_learning_modules m ON m.id = a.module_id
                   JOIN speaking_learning_tracks t ON t.id = m.track_id
                   WHERE a.user_id=%s AND LOWER(t.subject)=%s AND a.created_at >= %s
                   ORDER BY a.created_at""",
                (user_id, subject_key, (now - timedelta(weeks=weeks + 1)).replace(tzinfo=None)),
            )
            learning_rows = [dict(row) for row in cur.fetchall() or []]
        except Exception:
            conn.rollback()
    finally:
        cur.close()
        conn.close()
    payload = build_progress(rows, learning_rows, weeks=weeks, now=now)
    payload["topics"] = build_topic_insights(rows, bank_topics, subject=subject_key, now=now, user_id=user_id)
    payload.update(_exam_progress(user_id, subject_key))
    payload["subject"] = subject_key
    payload["scale"] = "ielts" if subject_key == "english" else "ten"
    payload["max_score"] = 9.0 if subject_key == "english" else 10.0
    return payload
