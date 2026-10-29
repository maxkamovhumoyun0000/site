"""Speaking app: level (placement) test.

A new Speaking account takes a short test after its account is confirmed:

* English: 4 spoken questions (3 Part 1 questions and 1 Part 2 cue card),
  scored by AI like any Speaking answer, plus 15 random multiple-choice
  questions from the Student app placement test bank (``tests`` table),
  graded on the server.
* Russian: 6-7 spoken questions from the Russian Speaking bank, no
  multiple-choice part.

The AI scores and the multiple-choice result are combined into a level
(CEFR, with an approximate IELTS band for English) that is saved per subject.
The learner can take the test again once every 30 days to update the level.

The test keeps its own tables: it does not touch the Student app placement
flow (which changes the account type) and placement answers are not counted
in Speaking progress.
"""
from __future__ import annotations

import json
import logging
import random
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()

RETAKE_DAYS = 30
MCQ_COUNT = 15
ENGLISH_PART1_COUNT = 3
OPEN_TEST_HOURS = 3
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MIN_AUDIO_BYTES = 2 * 1024
MIN_WORDS = 4
PART1_SECONDS = {"english": 45, "russian": 60}
CUE_PREP_SECONDS = 45
CUE_ANSWER_SECONDS = 90

ENGLISH_LEVELS = (
    # (band below which the level applies, code, CEFR, label); the usual
    # IELTS to CEFR mapping: 4.0-5.0 B1, 5.5-6.5 B2, 7.0-8.0 C1, 8.5+ C2.
    (3.0, "BEGINNER", "A1", "A1 (Beginner)"),
    (4.0, "ELEMENTARY", "A2", "A2 (Elementary)"),
    (5.5, "PRE-INTERMEDIATE", "B1", "B1 (Intermediate)"),
    (7.0, "INTERMEDIATE", "B2", "B2 (Upper Intermediate)"),
    (8.5, "UPPER-INTERMEDIATE", "C1", "C1 (Advanced)"),
    (99.0, "ADVANCED", "C2", "C2 (Proficiency)"),
)
RUSSIAN_LEVELS = (
    (2.5, "BEGINNER", "A1", "A1 (Элементарный)"),
    (4.5, "ELEMENTARY", "A2", "A2 (Базовый)"),
    (6.0, "PRE-INTERMEDIATE", "B1", "B1 (ТРКИ-1)"),
    (7.5, "INTERMEDIATE", "B2", "B2 (ТРКИ-2)"),
    (9.0, "UPPER-INTERMEDIATE", "C1", "C1 (ТРКИ-3)"),
    (99.0, "ADVANCED", "C2", "C2 (ТРКИ-4)"),
)

_schema_ready = False
_schema_lock = threading.Lock()


def ensure_tables() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS speaking_placement_flags (
                    user_id BIGINT PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS speaking_placement_tests (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    subject TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'started',
                    steps_json TEXT NOT NULL DEFAULT '[]',
                    mcq_json TEXT NOT NULL DEFAULT '[]',
                    result_json TEXT NOT NULL DEFAULT '{}',
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    finished_at TIMESTAMPTZ
                )"""
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_speaking_placement_tests_user "
                "ON speaking_placement_tests(user_id, subject, started_at DESC)"
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS speaking_placement_answers (
                    test_id BIGINT NOT NULL,
                    step_index INTEGER NOT NULL,
                    score DOUBLE PRECISION,
                    unclear INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (test_id, step_index)
                )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS speaking_placement_results (
                    user_id BIGINT NOT NULL,
                    subject TEXT NOT NULL,
                    level_code TEXT NOT NULL,
                    cefr TEXT NOT NULL,
                    level_label TEXT NOT NULL,
                    score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    scale TEXT NOT NULL DEFAULT 'ielts',
                    spoken_score DOUBLE PRECISION,
                    mcq_correct INTEGER NOT NULL DEFAULT 0,
                    mcq_total INTEGER NOT NULL DEFAULT 0,
                    summary TEXT NOT NULL DEFAULT '',
                    recommendations_json TEXT NOT NULL DEFAULT '[]',
                    test_id BIGINT,
                    tested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (user_id, subject)
                )"""
            )
            conn.commit()
            _schema_ready = True
        finally:
            cur.close()
            conn.close()


def mark_placement_required(user_id: int) -> None:
    """Called when a Speaking account is confirmed: the app then asks for the
    level test once (per subject) until a result exists."""
    if int(user_id or 0) <= 0:
        return
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO speaking_placement_flags (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING",
            (int(user_id),),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(authorization: str | None) -> dict[str, Any]:
    from backend.speaking_answers import _user as answers_user

    return answers_user(authorization)


def _subject_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return "russian" if raw.startswith(("rus", "ru", "рус")) else "english"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: Any) -> str | None:
    parsed = _aware(value)
    return parsed.isoformat() if parsed else None


def _json(raw: Any, fallback: Any) -> Any:
    try:
        value = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        return fallback
    return value if isinstance(value, type(fallback)) else fallback


def level_for(score: float, subject: str) -> tuple[str, str, str]:
    """(level code, CEFR, label) for a combined score (IELTS band or 0-10)."""
    table = RUSSIAN_LEVELS if subject == "russian" else ENGLISH_LEVELS
    for limit, code, cefr, label in table:
        if score < limit:
            return code, cefr, label
    _, code, cefr, label = table[-1]
    return code, cefr, label


def combine_scores(subject: str, spoken: list[float | None], mcq_correct: int, mcq_total: int) -> tuple[float, float | None]:
    """Combined score and spoken average.

    Unanswered spoken questions lower the spoken average a little (up to 15 %)
    rather than counting as zero, so one failed upload does not drop a level.
    English mixes 70 % speaking with 30 % multiple choice mapped to a band.
    """
    from backend.speaking_answers import round_half

    answered = [float(s) for s in spoken if s is not None]
    total = max(1, len(spoken))
    if answered:
        spoken_avg = sum(answered) / len(answered)
        spoken_value = spoken_avg * (0.85 + 0.15 * len(answered) / total)
    else:
        spoken_avg = None
        spoken_value = 1.0
    if subject == "english" and mcq_total > 0:
        mcq_band = 1.5 + 7.0 * (max(0, min(mcq_correct, mcq_total)) / mcq_total)
        combined = 0.7 * spoken_value + 0.3 * mcq_band
    else:
        combined = spoken_value
    top = 9.0 if subject == "english" else 10.0
    return round_half(max(0.0, min(top, combined))), (round_half(spoken_avg) if spoken_avg is not None else None)


def _serialize_result(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    tested = _aware(row.get("tested_at"))
    return {
        "subject": str(row.get("subject") or "english"),
        "level_code": str(row.get("level_code") or ""),
        "cefr": str(row.get("cefr") or ""),
        "level_label": str(row.get("level_label") or ""),
        "score": float(row.get("score") or 0),
        "scale": str(row.get("scale") or "ielts"),
        "max_score": 9.0 if str(row.get("scale") or "ielts") == "ielts" else 10.0,
        "spoken_score": float(row["spoken_score"]) if row.get("spoken_score") is not None else None,
        "mcq_correct": int(row.get("mcq_correct") or 0),
        "mcq_total": int(row.get("mcq_total") or 0),
        "summary": str(row.get("summary") or ""),
        "recommendations": _json(row.get("recommendations_json"), []),
        "tested_at": tested.isoformat() if tested else None,
        "next_available_at": (tested + timedelta(days=RETAKE_DAYS)).isoformat() if tested else None,
    }


def results_for(user_id: int) -> list[dict[str, Any]]:
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM speaking_placement_results WHERE user_id=%s ORDER BY subject",
            (int(user_id),),
        )
        return [r for r in (_serialize_result(dict(row)) for row in cur.fetchall() or []) if r]
    finally:
        cur.close()
        conn.close()


def _result(cur, user_id: int, subject: str) -> dict[str, Any] | None:
    cur.execute(
        "SELECT * FROM speaking_placement_results WHERE user_id=%s AND subject=%s",
        (int(user_id), subject),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _open_test(cur, user_id: int, subject: str) -> dict[str, Any] | None:
    cur.execute(
        """SELECT * FROM speaking_placement_tests
           WHERE user_id=%s AND subject=%s AND status='started' AND started_at > %s
           ORDER BY id DESC LIMIT 1""",
        (int(user_id), subject, _now() - timedelta(hours=OPEN_TEST_HOURS)),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _next_available(result: dict[str, Any] | None) -> datetime | None:
    tested = _aware((result or {}).get("tested_at"))
    if not tested:
        return None
    available = tested + timedelta(days=RETAKE_DAYS)
    return available if available > _now() else None


def _user_subjects(user: dict[str, Any]) -> set[str]:
    raw = str(user.get("subject") or "")
    subjects = {_subject_key(part) for part in raw.split(",") if part.strip()}
    return subjects or {"english", "russian"}


def _spoken_steps(subject: str, rng: random.Random) -> list[dict[str, Any]]:
    from backend.speaking_exams import _load_bank, _russian_plan, _step

    bank = _load_bank(subject)
    if subject == "english":
        # One Part 1 question from each of three different topics, then one
        # Part 2 cue card: a quick look at short and long answers.
        part1_topics = [tid for tid, rows in bank.items() if rows and int(rows[0].get("part") or 0) == 1]
        part2_topics = [tid for tid, rows in bank.items() if rows and int(rows[0].get("part") or 0) == 2]
        rng.shuffle(part1_topics)
        picked: list[tuple[int, dict[str, Any]]] = []
        for topic_id in part1_topics[:ENGLISH_PART1_COUNT]:
            picked.append((1, rng.choice(bank[topic_id])))
        if len(picked) < ENGLISH_PART1_COUNT and part1_topics:
            pool = [row for tid in part1_topics for row in bank[tid] if all(row is not p for _, p in picked)]
            rng.shuffle(pool)
            picked += [(1, row) for row in pool[: ENGLISH_PART1_COUNT - len(picked)]]
        if part2_topics:
            picked.append((2, bank[rng.choice(part2_topics)][0]))
        steps = [_step(row, part=part, index=i, subject="english", practice=False) for i, (part, row) in enumerate(picked)]
    else:
        steps = _russian_plan(bank, rng, practice=False, count=rng.choice((6, 7)))
    for index, step in enumerate(steps):
        step["index"] = index
        if int(step.get("part") or 0) == 2:
            step["prep_seconds"] = CUE_PREP_SECONDS
            step["answer_seconds"] = CUE_ANSWER_SECONDS
        else:
            step["answer_seconds"] = PART1_SECONDS[subject]
    return steps


def _mcq_ids(subject: str, rng: random.Random) -> list[int]:
    if subject != "english":
        return []
    from db import get_tests_by_subject

    rows = [r for r in (get_tests_by_subject("English") or []) if str(r.get("question") or "").strip()]
    usable = [
        int(r["id"]) for r in rows
        if str(r.get("correct_option") or "").strip().upper() in {"A", "B", "C", "D"}
    ]
    return rng.sample(usable, k=min(MCQ_COUNT, len(usable)))


def _mcq_payload(ids: list[int]) -> list[dict[str, Any]]:
    from db import get_test_by_id

    out = []
    for position, test_id in enumerate(ids):
        row = get_test_by_id(int(test_id)) or {}
        if not row:
            continue
        out.append({
            "question_id": int(test_id),
            "index": position,
            "question": str(row.get("question") or ""),
            "options": {
                "A": str(row.get("option_a") or ""),
                "B": str(row.get("option_b") or ""),
                "C": str(row.get("option_c") or ""),
                "D": str(row.get("option_d") or ""),
            },
        })
    return out


def _answered_steps(cur, test_id: int) -> dict[int, dict[str, Any]]:
    cur.execute("SELECT * FROM speaking_placement_answers WHERE test_id=%s", (int(test_id),))
    return {int(dict(r)["step_index"]): dict(r) for r in cur.fetchall() or []}


def _test_payload(test: dict[str, Any], answered: dict[int, dict[str, Any]]) -> dict[str, Any]:
    subject = str(test.get("subject") or "english")
    steps = _json(test.get("steps_json"), [])
    return {
        "id": int(test["id"]),
        "subject": subject,
        "scale": "ielts" if subject == "english" else "ten",
        "steps": steps,
        "answered_steps": sorted(answered.keys()),
        "mcq": _mcq_payload(_json(test.get("mcq_json"), [])),
        "started_at": _iso(test.get("started_at")),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/speaking/placement/status")
@router.get("/api/speaking/placement/status")
async def speaking_placement_status(
    subject: str = Query(default="english", max_length=32),
    authorization: str | None = Header(default=None),
):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject_key = _subject_key(subject)
    conn = get_conn()
    cur = conn.cursor()
    try:
        result = _result(cur, user_id, subject_key)
        cur.execute("SELECT 1 AS x FROM speaking_placement_flags WHERE user_id=%s", (user_id,))
        flagged = cur.fetchone() is not None
        open_test = _open_test(cur, user_id, subject_key)
    finally:
        cur.close()
        conn.close()
    next_available = _next_available(result)
    return {
        "subject": subject_key,
        "required": bool(flagged and result is None and subject_key in _user_subjects(user)),
        "result": _serialize_result(result),
        "can_take": next_available is None,
        "next_available_at": next_available.isoformat() if next_available else None,
        "retake_days": RETAKE_DAYS,
        "open_test_id": int(open_test["id"]) if open_test else None,
        "plan": {
            "spoken": ENGLISH_PART1_COUNT + 1 if subject_key == "english" else 7,
            "mcq": MCQ_COUNT if subject_key == "english" else 0,
        },
    }


class PlacementStartRequest(BaseModel):
    subject: str = Field(default="english", max_length=32)


@router.post("/speaking/placement/start")
@router.post("/api/speaking/placement/start")
async def start_speaking_placement(payload: PlacementStartRequest, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject = _subject_key(payload.subject)
    conn = get_conn()
    cur = conn.cursor()
    try:
        result = _result(cur, user_id, subject)
        next_available = _next_available(result)
        if next_available is not None:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": f"You can take the level test again after {RETAKE_DAYS} days.",
                    "next_available_at": next_available.isoformat(),
                },
            )
        test = _open_test(cur, user_id, subject)
        if test is None:
            rng = random.Random()
            steps = _spoken_steps(subject, rng)
            if not steps:
                raise HTTPException(status_code=404, detail="Not enough Speaking questions for the level test yet")
            mcq = _mcq_ids(subject, rng)
            cur.execute(
                """INSERT INTO speaking_placement_tests (user_id, subject, steps_json, mcq_json)
                   VALUES (%s,%s,%s,%s) RETURNING *""",
                (user_id, subject, json.dumps(steps, ensure_ascii=False), json.dumps(mcq)),
            )
            test = dict(cur.fetchone())
            conn.commit()
        answered = _answered_steps(cur, int(test["id"]))
    finally:
        cur.close()
        conn.close()
    return {"test": _test_payload(test, answered)}


def _owned_open_test(cur, test_id: int, user_id: int) -> dict[str, Any]:
    cur.execute("SELECT * FROM speaking_placement_tests WHERE id=%s AND user_id=%s", (int(test_id), int(user_id)))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Level test not found")
    test = dict(row)
    if test.get("status") != "started":
        raise HTTPException(status_code=409, detail="This level test is already finished")
    started = _aware(test.get("started_at"))
    if started and started < _now() - timedelta(hours=OPEN_TEST_HOURS):
        raise HTTPException(status_code=410, detail="This level test has expired. Please start again.")
    return test


@router.post("/speaking/placement/{test_id}/answer")
@router.post("/api/speaking/placement/{test_id}/answer")
async def answer_speaking_placement(
    test_id: int,
    file: UploadFile = File(...),
    step_index: int = Form(..., ge=0, le=20),
    duration_seconds: float = Form(default=0.0, ge=0, le=600),
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    from backend.main import _ai_result_language
    from backend.speaking_answers import (
        _enforce_limits,
        _score,
        _scoring_prompt,
        _transcribe_bytes,
        normalize_ai_result,
    )

    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        test = _owned_open_test(cur, test_id, user_id)
        answered = _answered_steps(cur, int(test_id))
    finally:
        cur.close()
        conn.close()
    if int(step_index) in answered:
        row = answered[int(step_index)]
        return {"step_index": int(step_index), "unclear": bool(row.get("unclear")), "cached": True}
    steps = _json(test.get("steps_json"), [])
    step = next((s for s in steps if int(s.get("index") or 0) == int(step_index)), None)
    if not step:
        raise HTTPException(status_code=422, detail="Unknown level test question")

    raw = await file.read(MAX_AUDIO_BYTES + 1)
    if len(raw) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="The recording is too long (max 10 MB).")
    subject = str(test.get("subject") or "english")
    score: float | None = None
    unclear = True
    result: dict[str, Any] = {}
    if len(raw) >= MIN_AUDIO_BYTES:
        if raw[4:8] != b"ftyp":
            raise HTTPException(status_code=422, detail="Unsupported audio format. Please record again in the app.")
        _enforce_limits(user_id)
        transcript = await _transcribe_bytes(raw, "answer.m4a", "en" if subject == "english" else "ru")
        word_count = len(re.findall(r"[\w'-]+", transcript, re.UNICODE))
        if word_count >= MIN_WORDS:
            scale = "ielts" if subject == "english" else "ten"
            system, user_turn = _scoring_prompt(
                scale=scale, part=int(step.get("part") or 1) if subject == "english" else None,
                topic=str(step.get("topic") or ""), prompt=str(step.get("prompt") or ""),
                bullets="; ".join(step.get("bullets") or []), transcript=transcript[:6000],
                duration=float(duration_seconds or 0), word_count=word_count,
                result_language="Russian" if subject == "russian" else _ai_result_language(x_language),
            )
            scored = normalize_ai_result(await _score(system, user_turn), scale=scale)
            score = float(scored["score"])
            unclear = False
            result = {
                "score": score,
                "criteria": scored["criteria"],
                "summary": scored["summary"],
                "word_count": word_count,
                "transcript": transcript[:1500],
            }
    # A silent or unclear answer is kept as "not answered" so the test can go on.
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_placement_answers (test_id, step_index, score, unclear, result_json)
               VALUES (%s,%s,%s,%s,%s) ON CONFLICT (test_id, step_index) DO NOTHING""",
            (int(test_id), int(step_index), score, 1 if unclear else 0, json.dumps(result, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return {"step_index": int(step_index), "unclear": unclear, "cached": False}


class PlacementMcqAnswer(BaseModel):
    question_id: int = Field(ge=1)
    answer: str = Field(default="", max_length=1)


class PlacementFinishRequest(BaseModel):
    answers: list[PlacementMcqAnswer] = Field(default_factory=list, max_length=40)


async def _summary(subject: str, level_label: str, score: float, answers: list[dict[str, Any]],
                   mcq_correct: int, mcq_total: int, language: str) -> tuple[str, list[str]]:
    from backend.speaking_answers import _clean_list, _score

    lines = [
        f"Q{index + 1}: score {a.get('score')} | {str(a.get('summary') or '')[:300]} | "
        f"answer: {str(a.get('transcript') or '')[:300]}"
        for index, a in enumerate(answers)
    ]
    exam = "English (IELTS-style)" if subject == "english" else "Russian"
    system = (
        f"You are an examiner who just finished a short {exam} speaking level test. "
        f"Write in {language}. Return ONLY compact JSON: "
        '{"summary":"2-3 sentences about the level and what holds the learner back",'
        '"recommendations":["concrete next step"]} with 3 recommendations.'
    )
    user_turn = (
        f"Detected level: {level_label}, score {score}. "
        + (f"Grammar and vocabulary test: {mcq_correct}/{mcq_total} correct.\n" if mcq_total else "\n")
        + "\n".join(lines)
    )
    try:
        raw = await _score(system, user_turn[:8000])
    except Exception:
        # The summary is optional; the level is already saved.
        logger.warning("speaking placement summary unavailable", exc_info=True)
        return "", []
    return str(raw.get("summary") or "").strip()[:700], _clean_list(raw.get("recommendations"), limit=4)


@router.post("/speaking/placement/{test_id}/finish")
@router.post("/api/speaking/placement/{test_id}/finish")
async def finish_speaking_placement(
    test_id: int,
    payload: PlacementFinishRequest,
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    from backend.main import _ai_result_language
    from db import get_test_by_id

    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        test = _owned_open_test(cur, test_id, user_id)
        answered = _answered_steps(cur, int(test_id))
    finally:
        cur.close()
        conn.close()
    subject = str(test.get("subject") or "english")
    steps = _json(test.get("steps_json"), [])
    spoken: list[float | None] = []
    answer_results: list[dict[str, Any]] = []
    for step in steps:
        row = answered.get(int(step.get("index") or 0))
        if row and not int(row.get("unclear") or 0) and row.get("score") is not None:
            spoken.append(float(row["score"]))
            answer_results.append(_json(row.get("result_json"), {}))
        else:
            spoken.append(None)

    # Only the questions of this test count, each once, graded on the server.
    mcq_ids = [int(i) for i in _json(test.get("mcq_json"), [])]
    given = {int(a.question_id): a.answer.strip().upper() for a in payload.answers}
    mcq_correct = 0
    for question_id in mcq_ids:
        row = get_test_by_id(question_id) or {}
        correct = str(row.get("correct_option") or "").strip().upper()
        if correct and given.get(question_id) == correct:
            mcq_correct += 1
    mcq_total = len(mcq_ids)

    score, spoken_avg = combine_scores(subject, spoken, mcq_correct, mcq_total)
    level_code, cefr, level_label = level_for(score, subject)
    language = "Russian" if subject == "russian" else _ai_result_language(x_language)
    # The level is saved first; the AI summary is added afterwards, so a slow
    # model can never lose a finished test.
    summary, recommendations = "", []
    scale = "ielts" if subject == "english" else "ten"
    now = _now()
    result_payload = {
        "level_code": level_code, "cefr": cefr, "level_label": level_label, "score": score,
        "spoken_score": spoken_avg, "mcq_correct": mcq_correct, "mcq_total": mcq_total,
        "spoken_answered": sum(1 for s in spoken if s is not None), "spoken_total": len(spoken),
    }
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE speaking_placement_tests SET status='finished', finished_at=%s, result_json=%s
               WHERE id=%s AND user_id=%s AND status='started'""",
            (now, json.dumps(result_payload, ensure_ascii=False), int(test_id), user_id),
        )
        if int(cur.rowcount or 0) != 1:
            conn.rollback()
            raise HTTPException(status_code=409, detail="This level test is already finished")
        cur.execute(
            """INSERT INTO speaking_placement_results
                   (user_id, subject, level_code, cefr, level_label, score, scale, spoken_score,
                    mcq_correct, mcq_total, summary, recommendations_json, test_id, tested_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (user_id, subject) DO UPDATE SET
                   level_code=EXCLUDED.level_code, cefr=EXCLUDED.cefr, level_label=EXCLUDED.level_label,
                   score=EXCLUDED.score, scale=EXCLUDED.scale, spoken_score=EXCLUDED.spoken_score,
                   mcq_correct=EXCLUDED.mcq_correct, mcq_total=EXCLUDED.mcq_total, summary=EXCLUDED.summary,
                   recommendations_json=EXCLUDED.recommendations_json, test_id=EXCLUDED.test_id,
                   tested_at=EXCLUDED.tested_at""",
            (user_id, subject, level_code, cefr, level_label, score, scale, spoken_avg, mcq_correct,
             mcq_total, summary, json.dumps(recommendations, ensure_ascii=False), int(test_id), now),
        )
        # The single users.level column belongs to the Student app for school
        # accounts; only Speaking-only accounts get their English level there.
        from speaking_contract import is_speaking_app_account

        if subject == "english" and is_speaking_app_account(user.get("speaking_app_account")):
            cur.execute("UPDATE users SET level=%s WHERE id=%s", (level_code, user_id))
        cur.execute(
            "SELECT * FROM speaking_placement_results WHERE user_id=%s AND subject=%s",
            (user_id, subject),
        )
        saved = dict(cur.fetchone() or {})
        conn.commit()
    finally:
        cur.close()
        conn.close()
    summary, recommendations = await _summary(
        subject, level_label, score, answer_results, mcq_correct, mcq_total, language,
    )
    if summary or recommendations:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """UPDATE speaking_placement_results SET summary=%s, recommendations_json=%s
                   WHERE user_id=%s AND subject=%s AND test_id=%s""",
                (summary, json.dumps(recommendations, ensure_ascii=False), user_id, subject, int(test_id)),
            )
            conn.commit()
        finally:
            cur.close()
            conn.close()
        saved = {**saved, "summary": summary, "recommendations_json": json.dumps(recommendations, ensure_ascii=False)}
    return {
        "result": _serialize_result(saved),
        "details": result_payload,
    }
