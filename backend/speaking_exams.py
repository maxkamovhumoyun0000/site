"""Speaking app: IELTS-style Mock Exam, Daily Challenge, streaks and badges.

Questions come from the Speaking question bank (``speaking_questions``); no
AI is used to pick them.

English mock (standard order, or a single part):
* Part 1: 6-10 short questions from 2-3 Part 1 topics, 30 s each.
* Part 2: one cue card, 60 s preparation with notes, 120 s answer.
* Part 3: 5-6 discussion questions from the Part 3 topic closest to the cue
  card, 60 s each.

Russian mock: about 10 questions from different Russian topics, no parts,
up to 60 s each, scored out of 10 (mini mock 5, daily challenge 3).

Each answer is recorded separately and scored by
``POST /speaking/answers/analyze`` with ``exam_id``/``step_index``; finishing
the exam combines those scores into an overall result with strengths,
weaknesses and a next practice plan.

The Daily Challenge is a 3-step exam (one question per part) that is the
same for a user for the whole day. Completing it extends the streak.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()

TASHKENT = timezone(timedelta(hours=5))
_SCHEMA_READY = False

TIMINGS = {
    "english": {"part1": 30, "part2_prep": 60, "part2": 120, "part3": 60},
    # Russian exams have no parts: every question is answered in up to 60 s.
    "russian": {"part1": 60, "part2_prep": 60, "part2": 120, "part3": 60},
}
PART_WEIGHTS = {1: 0.3, 2: 0.35, 3: 0.35}
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "you", "your", "about", "describe",
    "with", "that", "this", "what", "how", "why", "when", "who", "time", "someone", "something",
    "и", "в", "на", "о", "об", "с", "по", "для", "как", "что", "это", "ваш", "вы",
}


def _user(authorization: str | None) -> dict[str, Any]:
    from backend.speaking_answers import _user as answers_user

    return answers_user(authorization)


def ensure_tables() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    from backend.speaking_answers import ensure_tables as ensure_answer_tables

    ensure_answer_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_exams (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                subject TEXT NOT NULL DEFAULT 'english',
                kind TEXT NOT NULL DEFAULT 'mock',
                mode TEXT NOT NULL DEFAULT 'exam',
                parts TEXT NOT NULL DEFAULT 'full',
                challenge_day DATE,
                steps_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'started',
                overall DOUBLE PRECISION,
                result_json TEXT NOT NULL DEFAULT '{}',
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMPTZ
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_exams_user ON speaking_exams(user_id, subject, started_at DESC)")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_daily_challenges (
                user_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                day DATE NOT NULL,
                exam_id BIGINT,
                completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, subject, day)
            )"""
        )
        conn.commit()
        _SCHEMA_READY = True
    finally:
        cur.close()
        conn.close()


def _subject_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    return "russian" if raw.startswith(("rus", "ru", "рус")) else "english"


def _today() -> date:
    return datetime.now(TASHKENT).date()


def _bullets(raw: Any) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return [str(raw)]
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()][:6]
    return [str(parsed)]


def _load_bank(subject: str) -> dict[int, list[dict[str, Any]]]:
    """Questions of one subject grouped by topic id (with part and title)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT q.id, q.topic_id, COALESCE(q.part, t.part) AS part, q.question_text,
                      q.cue_card_bullet_points, q.sample_answer, q.vocabulary_json, q.sort_order,
                      t.title AS topic_title
               FROM speaking_questions q JOIN speaking_topics t ON t.id = q.topic_id
               WHERE LOWER(COALESCE(q.subject, t.subject, 'english')) = %s
                 AND COALESCE(q.question_text, '') <> ''
               ORDER BY t.id, q.sort_order, q.id""",
            (subject,),
        )
        topics: dict[int, list[dict[str, Any]]] = {}
        for row in cur.fetchall() or []:
            item = dict(row)
            topics.setdefault(int(item["topic_id"]), []).append(item)
        return topics
    finally:
        cur.close()
        conn.close()


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[\w']{3,}", str(text or "").lower()) if w not in _STOP_WORDS}


def _step(row: dict[str, Any], *, part: int, index: int, subject: str, practice: bool) -> dict[str, Any]:
    timing = TIMINGS[subject]
    step: dict[str, Any] = {
        "index": index,
        "part": part,
        "question_id": str(row.get("id")),
        "topic": str(row.get("topic_title") or ""),
        "prompt": str(row.get("question_text") or ""),
        "bullets": _bullets(row.get("cue_card_bullet_points")) if part == 2 else [],
        "prep_seconds": timing["part2_prep"] if part == 2 else 0,
        "answer_seconds": timing["part2"] if part == 2 else timing[f"part{part}"],
    }
    if practice:
        # Practice mode may show help; exam mode never receives it.
        from speaking_contract import public_sample_answer

        step["sample_answer"] = public_sample_answer(row.get("sample_answer"), subject) or ""
        try:
            vocab = json.loads(row.get("vocabulary_json") or "[]")
        except (TypeError, ValueError):
            vocab = []
        step["vocabulary"] = vocab if isinstance(vocab, list) else []
    return step


def _english_plan(bank: dict[int, list[dict[str, Any]]], parts: str, rng: random.Random, *, practice: bool,
                  part1_count: int, part3_count: int) -> list[dict[str, Any]]:
    by_part: dict[int, list[int]] = {1: [], 2: [], 3: []}
    for topic_id, rows in bank.items():
        part = int(rows[0].get("part") or 0)
        if part in by_part:
            by_part[part].append(topic_id)
    rows_out: list[tuple[int, dict[str, Any]]] = []
    cue: dict[str, Any] | None = None
    if parts in {"full", "part1"} and by_part[1]:
        topic_ids = rng.sample(by_part[1], k=min(3, len(by_part[1])))
        pool: list[dict[str, Any]] = []
        for topic_id in topic_ids:
            questions = list(bank[topic_id])
            rng.shuffle(questions)
            pool.extend(questions[:4])
        rows_out += [(1, row) for row in pool[:part1_count]]
    if parts in {"full", "part2", "part3"} and by_part[2]:
        cue = bank[rng.choice(by_part[2])][0]
        if parts in {"full", "part2"}:
            rows_out.append((2, cue))
    if parts in {"full", "part3"} and by_part[3]:
        topic_ids = list(by_part[3])
        if cue is not None:
            cue_words = _words(f"{cue.get('topic_title')} {cue.get('question_text')} {cue.get('cue_card_bullet_points') or ''}")

            def overlap(tid: int) -> int:
                text = " ".join([str(bank[tid][0].get("topic_title") or "")] + [str(r.get("question_text") or "") for r in bank[tid]])
                return len(cue_words & _words(text))

            rng.shuffle(topic_ids)
            topic_ids.sort(key=overlap, reverse=True)
        else:
            rng.shuffle(topic_ids)
        pool = []
        for topic_id in topic_ids:
            pool.extend(bank[topic_id])
            if len(pool) >= part3_count:
                break
        rows_out += [(3, row) for row in pool[:part3_count]]
    return [_step(row, part=part, index=i, subject="english", practice=practice) for i, (part, row) in enumerate(rows_out)]


def _russian_plan(bank: dict[int, list[dict[str, Any]]], rng: random.Random, *, practice: bool,
                  count: int) -> list[dict[str, Any]]:
    """Russian exam: about ``count`` questions from different topics, no parts
    (all steps are ``part`` 1, 60 s each), scored out of 10."""
    topic_ids = [tid for tid, rows in bank.items() if rows]
    if not topic_ids:
        return []
    rng.shuffle(topic_ids)
    picked: list[dict[str, Any]] = []
    per_topic = 1 if len(topic_ids) >= count else 2
    for topic_id in topic_ids:
        rows = list(bank[topic_id])
        rng.shuffle(rows)
        picked.extend(rows[:per_topic])
        if len(picked) >= count:
            break
    return [_step(row, part=1, index=i, subject="russian", practice=practice) for i, row in enumerate(picked[:count])]

def _related_part3(bank: dict[int, list[dict[str, Any]]], cue: dict[str, Any], count: int,
                   rng: random.Random) -> list[dict[str, Any]]:
    """Part 3 questions from the Part 3 topics closest to a cue card."""
    cue_words = _words(f"{cue.get('topic_title')} {cue.get('question_text')} {cue.get('cue_card_bullet_points') or ''}")
    topic_ids = [tid for tid, rows in bank.items() if int(rows[0].get("part") or 0) == 3]
    rng.shuffle(topic_ids)

    def overlap(tid: int) -> int:
        text = " ".join([str(bank[tid][0].get("topic_title") or "")] + [str(r.get("question_text") or "") for r in bank[tid]])
        return len(cue_words & _words(text))

    topic_ids.sort(key=overlap, reverse=True)
    pool: list[dict[str, Any]] = []
    for tid in topic_ids:
        pool.extend(bank[tid])
        if len(pool) >= count:
            break
    return pool[:count]


def topic_practice_rows(bank: dict[int, list[dict[str, Any]]], topic_id: int, subject: str,
                        rng: random.Random) -> list[tuple[int, dict[str, Any]]]:
    """About five minutes of speaking on one topic: (part, question) pairs.

    English Part 1: 7 questions x 30 s.  Part 2: the cue card (1 min + 2 min)
    and 2 related Part 3 questions.  Part 3: 5 questions x 60 s.  Russian:
    5 discussion questions x 60 s.
    """
    rows = list(bank.get(int(topic_id)) or [])
    if not rows:
        return []
    rng.shuffle(rows)
    if subject != "english":
        return [(1, row) for row in rows[:5]]
    part = int(rows[0].get("part") or 1)
    if part == 2:
        cue = rows[0]
        return [(2, cue)] + [(3, row) for row in _related_part3(bank, cue, 2, rng)]
    if part == 3:
        return [(3, row) for row in rows[:5]]
    return [(1, row) for row in rows[:7]]


def _challenge_seed(user_id: int, subject: str, day: date) -> int:
    digest = hashlib.sha256(f"{user_id}:{subject}:{day.isoformat()}".encode()).hexdigest()
    return int(digest[:12], 16)


def _build_plan(user_id: int, subject: str, kind: str, parts: str, practice: bool,
                topic_id: int | None = None) -> list[dict[str, Any]]:
    bank = _load_bank(subject)
    if kind == "topic":
        rows = topic_practice_rows(bank, int(topic_id or 0), subject, random.Random())
        plan = [_step(row, part=part, index=i, subject=subject, practice=practice) for i, (part, row) in enumerate(rows)]
    elif kind == "challenge":
        rng = random.Random(_challenge_seed(user_id, subject, _today()))
        if subject == "english":
            plan = _english_plan(bank, "full", rng, practice=practice, part1_count=1, part3_count=1)
        else:
            plan = _russian_plan(bank, rng, practice=practice, count=3)
    elif parts == "mini":
        # Speaking Plan mini mock: every part, fewer questions.
        rng = random.Random()
        if subject == "english":
            plan = _english_plan(bank, "full", rng, practice=practice, part1_count=4, part3_count=3)
        else:
            plan = _russian_plan(bank, rng, practice=practice, count=5)
    else:
        rng = random.Random()
        if subject == "english":
            plan = _english_plan(
                bank, parts, rng, practice=practice,
                part1_count=rng.randint(6, 10), part3_count=rng.randint(5, 6),
            )
        else:
            plan = _russian_plan(bank, rng, practice=practice, count=10)
    if not plan:
        raise HTTPException(status_code=404, detail="Not enough Speaking questions for this exam yet")
    return plan


class ExamStartRequest(BaseModel):
    subject: str = Field(default="english", max_length=32)
    kind: str = Field(default="mock", pattern="^(mock|challenge|topic)$")
    mode: str = Field(default="exam", pattern="^(exam|practice)$")
    parts: str = Field(default="full", pattern="^(full|part1|part2|part3|mini)$")
    # Required for kind "topic": the topic to practise again.
    topic_id: int | None = Field(default=None, ge=1)


class ExamStepResult(BaseModel):
    step_index: int = Field(ge=0, le=60)
    status: str = Field(default="answered", pattern="^(answered|skipped|unclear|failed)$")
    analysis_id: int | None = Field(default=None, ge=1)


class ExamFinishRequest(BaseModel):
    steps: list[ExamStepResult] = Field(default_factory=list, max_length=60)
    notes: str = Field(default="", max_length=3000)


def _scale(subject: str) -> tuple[str, float]:
    return ("ielts", 9.0) if subject == "english" else ("ten", 10.0)


@router.post("/speaking/exams/start")
@router.post("/api/speaking/exams/start")
async def start_speaking_exam(payload: ExamStartRequest, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject = _subject_key(payload.subject)
    if payload.kind != "mock":
        parts = "full"
    elif payload.parts == "mini" or subject == "english":
        parts = payload.parts
    else:
        parts = "full"
    if payload.kind == "topic" and not payload.topic_id:
        raise HTTPException(status_code=422, detail="topic_id is required for topic practice")
    steps = _build_plan(user_id, subject, payload.kind, parts, payload.mode == "practice", payload.topic_id)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_exams (user_id, subject, kind, mode, parts, challenge_day, steps_json)
               VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id, started_at""",
            (user_id, subject, payload.kind, payload.mode, parts,
             _today() if payload.kind == "challenge" else None, json.dumps(steps, ensure_ascii=False)),
        )
        row = dict(cur.fetchone())
        conn.commit()
    finally:
        cur.close()
        conn.close()
    scale, max_score = _scale(subject)
    return {"exam": {
        "id": int(row["id"]), "subject": subject, "kind": payload.kind, "mode": payload.mode, "parts": parts,
        "scale": scale, "max_score": max_score, "steps": steps,
        "started_at": row["started_at"].isoformat() if hasattr(row["started_at"], "isoformat") else str(row["started_at"]),
    }}


def _exam_row(cur, exam_id: int, user_id: int) -> dict[str, Any]:
    cur.execute("SELECT * FROM speaking_exams WHERE id=%s AND user_id=%s", (int(exam_id), int(user_id)))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Exam not found")
    return dict(row)


def _round_half(value: float) -> float:
    from backend.speaking_answers import round_half

    return round_half(value)


async def _exam_feedback(subject: str, step_rows: list[dict[str, Any]], part_scores: dict[int, float | None],
                         overall: float, scale: str, language: str) -> dict[str, Any]:
    """One AI call: strengths, weaknesses and a next practice plan."""
    from backend.speaking_answers import _clean_list, _score

    # The Russian exam is a flat list of questions without parts; older
    # Russian exams with three stages keep their part labels.
    part_less = subject == "russian" and len([k for k in part_scores if k]) <= 1
    lines = []
    for number, item in enumerate(step_rows, start=1):
        analysis = item.get("analysis") or {}
        label = f"Question {number}" if part_less else f"Part {item['part']}"
        lines.append(
            f"{label} | Q: {item['prompt'][:160]} | status: {item['status']} | "
            f"score: {analysis.get('score', '-')} | criteria: {json.dumps(analysis.get('criteria') or {})} | "
            f"answer: {str(analysis.get('transcript') or '')[:400]}"
        )
    exam_name = "IELTS Speaking mock exam" if scale == "ielts" else "Russian speaking exam"
    system = (
        f"You are an experienced examiner summarising a full {exam_name}. Base everything on the per-question data. "
        + ("The exam has no parts: never mention parts or stages. " if part_less else "")
        + f"Write every text in {language}. Return ONLY compact JSON: "
        '{"summary":"3-4 sentences","strengths":["..."],"weaknesses":["..."],'
        '"next_plan":["concrete practice step for the next days"]} '
        "with 3-4 strengths, 3-4 weaknesses and 5-6 plan steps."
    )
    part_line = "" if part_less else (
        f"Part scores: {json.dumps({f'part{k}': v for k, v in part_scores.items()})}."
    )
    user_turn = (
        f"Overall: {overall} ({'band' if scale == 'ielts' else 'out of 10'}). "
        f"{part_line}\n" + "\n".join(lines)
    )
    try:
        raw = await _score(system, user_turn[:12000])
    except HTTPException:
        raw = {}
    fallback_strengths: list[str] = []
    fallback_weak: list[str] = []
    for item in step_rows:
        analysis = item.get("analysis") or {}
        fallback_strengths += list(analysis.get("strengths") or [])
        fallback_weak += list(analysis.get("improvements") or [])
    return {
        "summary": str(raw.get("summary") or "").strip()[:900],
        "strengths": _clean_list(raw.get("strengths"), limit=5) or _clean_list(fallback_strengths, limit=4),
        "weaknesses": _clean_list(raw.get("weaknesses"), limit=5) or _clean_list(fallback_weak, limit=4),
        "next_plan": _clean_list(raw.get("next_plan"), limit=7),
    }


@router.post("/speaking/exams/{exam_id}/finish")
@router.post("/api/speaking/exams/{exam_id}/finish")
async def finish_speaking_exam(
    exam_id: int,
    payload: ExamFinishRequest,
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    from backend.speaking_answers import _serialize

    conn = get_conn()
    cur = conn.cursor()
    try:
        exam = _exam_row(cur, exam_id, user_id)
        if exam.get("status") == "finished":
            return {"exam": _public_exam(exam, cur)}
        steps = json.loads(exam.get("steps_json") or "[]")
        cur.execute(
            "SELECT * FROM speaking_answer_analyses WHERE user_id=%s AND exam_id=%s ORDER BY step_index, id",
            (user_id, int(exam_id)),
        )
        analyses = {int(dict(r).get("step_index") or 0): _serialize(dict(r)) for r in cur.fetchall() or []}
    finally:
        cur.close()
        conn.close()

    subject = str(exam.get("subject") or "english")
    scale, max_score = _scale(subject)
    reported = {item.step_index: item for item in payload.steps}
    step_rows: list[dict[str, Any]] = []
    per_part: dict[int, list[float]] = {}
    for step in steps:
        idx = int(step.get("index") or 0)
        analysis = analyses.get(idx)
        status = "answered" if analysis else (reported[idx].status if idx in reported else "skipped")
        if status == "answered" and not analysis:
            status = "failed"
        part = int(step.get("part") or 1)
        # An unanswered question counts as 0 in its part, like silence in a real exam.
        per_part.setdefault(part, []).append(float(analysis["score"]) if analysis else 0.0)
        step_rows.append({**step, "status": status, "analysis": analysis})

    part_scores = {part: _round_half(sum(values) / len(values)) for part, values in per_part.items() if values}
    weight_total = sum(PART_WEIGHTS.get(p, 0.3) for p in part_scores) or 1.0
    overall = _round_half(sum(score * PART_WEIGHTS.get(p, 0.3) for p, score in part_scores.items()) / weight_total) if part_scores else 0.0
    answered = [row["analysis"] for row in step_rows if row.get("analysis")]
    criteria: dict[str, float] = {}
    for key in ("fluency", "vocabulary", "grammar", "pronunciation"):
        values = [float((a.get("criteria") or {}).get(key)) for a in answered if (a.get("criteria") or {}).get(key) is not None]
        if values:
            criteria[key] = _round_half(sum(values) / len(values))

    from backend.main import _ai_result_language

    language = "Russian" if subject == "russian" else _ai_result_language(x_language)
    feedback = await _exam_feedback(subject, step_rows, part_scores, overall, scale, language) if answered else {
        "summary": "", "strengths": [], "weaknesses": [], "next_plan": [],
    }
    result = {
        "overall": overall,
        "max_score": max_score,
        "scale": scale,
        "part_scores": {str(k): v for k, v in sorted(part_scores.items())},
        "criteria": criteria,
        "answered": len(answered),
        "total": len(step_rows),
        **feedback,
    }
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE speaking_exams SET status='finished', overall=%s, result_json=%s, finished_at=NOW()
               WHERE id=%s AND user_id=%s RETURNING *""",
            (overall, json.dumps(result, ensure_ascii=False), int(exam_id), user_id),
        )
        finished = dict(cur.fetchone())
        if exam.get("kind") == "challenge" and answered:
            day = exam.get("challenge_day") or _today()
            cur.execute(
                """INSERT INTO speaking_daily_challenges (user_id, subject, day, exam_id)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (user_id, subject, day) DO NOTHING""",
                (user_id, subject, day, int(exam_id)),
            )
        conn.commit()
        return {"exam": _public_exam(finished, cur, step_rows=step_rows)}
    finally:
        cur.close()
        conn.close()


def _public_exam(exam: dict[str, Any], cur, *, step_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from backend.speaking_answers import _serialize

    if step_rows is None:
        steps = json.loads(exam.get("steps_json") or "[]")
        cur.execute(
            "SELECT * FROM speaking_answer_analyses WHERE user_id=%s AND exam_id=%s ORDER BY step_index, id",
            (int(exam["user_id"]), int(exam["id"])),
        )
        analyses = {int(dict(r).get("step_index") or 0): _serialize(dict(r)) for r in cur.fetchall() or []}
        step_rows = [
            {**step, "analysis": analyses.get(int(step.get("index") or 0)),
             "status": "answered" if analyses.get(int(step.get("index") or 0)) else "skipped"}
            for step in steps
        ]
    scale, max_score = _scale(str(exam.get("subject") or "english"))

    def iso(value: Any) -> str | None:
        return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)

    return {
        "id": int(exam["id"]),
        "subject": exam.get("subject"),
        "kind": exam.get("kind"),
        "mode": exam.get("mode"),
        "parts": exam.get("parts"),
        "status": exam.get("status"),
        "scale": scale,
        "max_score": max_score,
        "overall": exam.get("overall"),
        "started_at": iso(exam.get("started_at")),
        "finished_at": iso(exam.get("finished_at")),
        "result": json.loads(exam.get("result_json") or "{}"),
        "steps": step_rows,
    }


@router.get("/speaking/exams")
@router.get("/api/speaking/exams")
async def list_speaking_exams(
    subject: str = Query(default="english", max_length=32),
    limit: int = Query(default=20, ge=1, le=100),
    authorization: str | None = Header(default=None),
):
    user = _user(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT id, subject, kind, mode, parts, status, overall, started_at, finished_at, result_json
               FROM speaking_exams WHERE user_id=%s AND subject=%s AND status='finished'
               ORDER BY finished_at DESC LIMIT %s""",
            (int(user.get("id") or 0), _subject_key(subject), limit),
        )
        items = []
        for row in cur.fetchall() or []:
            item = dict(row)
            result = json.loads(item.pop("result_json") or "{}")
            items.append({
                **{k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in item.items()},
                "part_scores": result.get("part_scores") or {},
                "answered": result.get("answered"),
                "total": result.get("total"),
            })
        return {"items": items}
    finally:
        cur.close()
        conn.close()


@router.get("/speaking/exams/{exam_id}")
@router.get("/api/speaking/exams/{exam_id}")
async def get_speaking_exam(exam_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        return {"exam": _public_exam(_exam_row(cur, exam_id, int(user.get("id") or 0)), cur)}
    finally:
        cur.close()
        conn.close()


def streak_from_days(days: list[date], today: date) -> tuple[int, int]:
    """(current streak, best streak) from completed challenge days."""
    unique = sorted(set(days))
    best = run = 0
    previous: date | None = None
    for day in unique:
        run = run + 1 if previous and day - previous == timedelta(days=1) else 1
        best = max(best, run)
        previous = day
    current = 0
    cursor = today if today in unique else today - timedelta(days=1)
    day_set = set(unique)
    while cursor in day_set:
        current += 1
        cursor -= timedelta(days=1)
    return current, best


def build_badges(*, best_streak: int, recordings: int, mocks: int, part2_strong: int, subject: str) -> list[dict[str, Any]]:
    badges = [
        {"key": "streak_3", "progress": min(best_streak, 3), "target": 3},
        {"key": "streak_7", "progress": min(best_streak, 7), "target": 7},
        {"key": "audio_30", "progress": min(recordings, 30), "target": 30},
        {"key": "mock_10", "progress": min(mocks, 10), "target": 10},
    ]
    if subject == "english":
        badges.append({"key": "part2_master", "progress": min(part2_strong, 5), "target": 5})
    for badge in badges:
        badge["earned"] = badge["progress"] >= badge["target"]
    return badges


@router.get("/speaking/challenge/today")
@router.get("/api/speaking/challenge/today")
async def speaking_challenge_today(
    subject: str = Query(default="english", max_length=32),
    local_recordings: int = Query(default=0, ge=0, le=100000),
    authorization: str | None = Header(default=None),
):
    user = _user(authorization)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    subject_key = _subject_key(subject)
    today = _today()
    steps = _build_plan(user_id, subject_key, "challenge", "full", practice=False)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT day FROM speaking_daily_challenges WHERE user_id=%s AND subject=%s AND day >= %s ORDER BY day",
            (user_id, subject_key, today - timedelta(days=400)),
        )
        days = [d if isinstance(d, date) else date.fromisoformat(str(d)) for d in (dict(r)["day"] for r in cur.fetchall() or [])]
        cur.execute("SELECT COUNT(*) AS n FROM speaking_answer_analyses WHERE user_id=%s", (user_id,))
        analyses_count = int(dict(cur.fetchone() or {}).get("n") or 0)
        cur.execute(
            "SELECT COUNT(*) AS n FROM speaking_exams WHERE user_id=%s AND kind='mock' AND status='finished'",
            (user_id,),
        )
        mocks = int(dict(cur.fetchone() or {}).get("n") or 0)
        cur.execute(
            "SELECT COUNT(*) AS n FROM speaking_answer_analyses WHERE user_id=%s AND subject='english' AND part=2 AND score >= 6.5",
            (user_id,),
        )
        part2_strong = int(dict(cur.fetchone() or {}).get("n") or 0)
    finally:
        cur.close()
        conn.close()
    current, best = streak_from_days(days, today)
    return {
        "date": today.isoformat(),
        "subject": subject_key,
        "steps": steps,
        "completed": today in set(days),
        "streak": {"current": current, "best": best},
        "completed_days": [d.isoformat() for d in days if (today - d).days < 30],
        "badges": build_badges(
            best_streak=best, recordings=max(local_recordings, analyses_count), mocks=mocks,
            part2_strong=part2_strong, subject=subject_key,
        ),
    }
