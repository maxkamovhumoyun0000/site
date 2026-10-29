"""Speaking app: 7 / 14 / 30-day Speaking Plan with AI-generated practice tests.

* The learner picks a goal (IELTS 5.5 / 6.0 / 6.5 / 7.0+, or 6-9 out of 10
  for Russian) and a duration.  Every day has one focus (Part 1 fluency, topic
  vocabulary, Part 2 structure, grammar, Part 3 discussion, pronunciation) or a
  mini / full mock exam.
* The plan adapts: future practice days are re-planned from the learner's AI
  speaking feedback (``speaking_answer_analyses`` criteria) and plan test
  scores.  A weak criterion (e.g. grammar below the goal) gets more days.
* Practice tests come from an AI-generated bank (``speaking_plan_tests``) that
  the Speaking admin manages on the website; a missing test is generated on
  demand.  Questions use the Learning Path question format, so the app solves
  them in the same runner as the Learning Path final exam and are graded with
  the same server-side grader.
* A learner can be served at most ``DAILY_QUESTION_LIMIT`` test questions per
  Tashkent day.
* Mock days are completed by a finished mock exam (``speaking_exams``).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()

TASHKENT = timezone(timedelta(hours=5))
DAILY_QUESTION_LIMIT = 50
QUESTIONS_PER_TEST = 10
PASSING_SCORE = 60
BANK_TARGET_PER_FOCUS = 6
STAFF_ROLES = {"speaking_admin", "admin", "superadmin", "developer"}
USER_ROLES = {"speaking_user", "student", "teacher", "support", "speaking_admin", "admin", "superadmin", "developer"}

GOALS: dict[str, list[str]] = {"english": ["5.5", "6.0", "6.5", "7.0"], "russian": ["6", "7", "8", "9"]}
DURATIONS = (7, 14, 30)
CRITERIA = ("fluency", "vocabulary", "grammar", "pronunciation")
VOCAB_TOPICS = ("work_study", "hometown", "technology", "environment", "health", "travel")
PRACTICE_FOCUSES = (
    "part1_fluency", "part2_structure", "part3_discussion", "grammar_accuracy", "grammar_range", "pronunciation",
    *(f"vocabulary_{topic}" for topic in VOCAB_TOPICS),
)
MOCK_FOCUSES = ("mini_mock", "full_mock")
MOCK_DAYS = {7: {7: "full_mock"}, 14: {7: "mini_mock", 14: "full_mock"}, 30: {7: "mini_mock", 14: "mini_mock", 21: "mini_mock", 30: "full_mock"}}

# Question kinds the AI may generate; all of them are rendered by the
# Learning Path runner and graded by ``_grade_learning_question``.
OBJECTIVE_KINDS = {"multiple_choice", "true_false", "gap_fill", "word_order", "matching"}
AI_KINDS = {"write_sentence", "paraphrase", "guided_writing", "speak_sentence", "read_aloud"}
PLAN_KINDS = OBJECTIVE_KINDS | AI_KINDS

FOCUS_KINDS = {
    "part1_fluency": ["multiple_choice", "word_order", "gap_fill", "speak_sentence", "paraphrase"],
    "part2_structure": ["multiple_choice", "word_order", "gap_fill", "guided_writing", "speak_sentence"],
    "part3_discussion": ["multiple_choice", "word_order", "true_false", "paraphrase", "speak_sentence"],
    "grammar_accuracy": ["multiple_choice", "gap_fill", "word_order", "true_false", "write_sentence"],
    "grammar_range": ["multiple_choice", "gap_fill", "word_order", "paraphrase", "write_sentence"],
    "pronunciation": ["multiple_choice", "true_false", "matching", "read_aloud"],
    "vocabulary": ["multiple_choice", "gap_fill", "matching", "write_sentence"],
}

TOPIC_NAMES = {
    "english": {
        "work_study": "Work & Study", "hometown": "Hometown & Places", "technology": "Technology & Media",
        "environment": "Environment & Nature", "health": "Health & Lifestyle", "travel": "Travel & Culture",
    },
    "russian": {
        "work_study": "Учёба и работа", "hometown": "Родной город", "technology": "Технологии и СМИ",
        "environment": "Природа и экология", "health": "Здоровье и образ жизни", "travel": "Путешествия и культура",
    },
}

FOCUS_BRIEFS = {
    "english": {
        "part1_fluency": "IELTS Speaking Part 1 fluency: natural short answers about familiar topics, extending an answer with a reason and an example, linking words and natural fillers.",
        "part2_structure": "IELTS Speaking Part 2 long turn: planning a cue card in one minute, strong opening sentences, sequencing and narrative linkers, past tenses for stories, rounding off.",
        "part3_discussion": "IELTS Speaking Part 3 discussion: giving and justifying opinions, comparing past and present, speculating about the future, hedging, abstract topic language.",
        "grammar_accuracy": "Grammatical accuracy in speech: tenses, articles, subject-verb agreement, prepositions, countable/uncountable nouns and typical errors of Uzbek learners.",
        "grammar_range": "Grammatical range in speech: conditionals, relative clauses, passive voice, modal verbs for speculation, complex sentences with linking.",
        "pronunciation": "Pronunciation awareness: word stress, silent letters, -ed and -s endings, sentence stress, minimal pairs and connected speech.",
        "vocabulary": "Topic vocabulary for '{topic}': collocations, band-appropriate idiomatic expressions, paraphrasing and less common words used in IELTS Speaking answers.",
    },
    "russian": {
        "part1_fluency": "Короткие ответы на вопросы о себе: естественные полные ответы, причина и пример, связки и разговорные выражения.",
        "part2_structure": "Монолог по теме: план, вступление, связки (во-первых, кроме того, в итоге), рассказ о прошлом, заключение.",
        "part3_discussion": "Дискуссия: выражение и обоснование мнения, сравнение, предположения о будущем.",
        "grammar_accuracy": "Грамматическая точность в речи: падежи, согласование, виды глагола, предлоги, типичные ошибки узбекоязычных учащихся.",
        "grammar_range": "Грамматическое разнообразие: сложные предложения, который, если бы, причастные и деепричастные обороты.",
        "pronunciation": "Произношение: ударение, редукция гласных, оглушение согласных, мягкий знак, интонация вопроса.",
        "vocabulary": "Лексика по теме «{topic}»: сочетаемость, устойчивые выражения, синонимы и перефразирование для устных ответов.",
    },
}

BAND_LEVELS = {
    "english": {"5.5": "B1+ (IELTS 5.5)", "6.0": "B2 (IELTS 6.0)", "6.5": "B2+ (IELTS 6.5)", "7.0": "C1 (IELTS 7.0+)"},
    "russian": {"6": "B1 (6/10)", "7": "B1+/B2 (7/10)", "8": "B2+ (8/10)", "9": "C1 (9/10)"},
}
CEFR_ESTIMATE = {
    "english": {"A1": 3.5, "A2": 4.5, "B1": 5.0, "B2": 6.0, "C1": 7.0, "C2": 8.0},
    "russian": {"A1": 4.0, "A2": 5.0, "B1": 6.0, "B2": 7.0, "C1": 8.0, "C2": 9.0},
}

_SCHEMA_READY = False
_GENERATION_LOCKS: dict[str, asyncio.Lock] = {}


# ---------------------------------------------------------------------------
# Auth, schema, small helpers
# ---------------------------------------------------------------------------

def _auth(authorization: str | None, roles: set[str]) -> tuple[dict[str, Any], str]:
    from backend.main import _require_role, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    role = _require_role(user, roles)
    return user, role


def ensure_tables() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_plans (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                subject TEXT NOT NULL DEFAULT 'english',
                goal TEXT NOT NULL,
                days INTEGER NOT NULL,
                started_on DATE NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_plans_user ON speaking_plans(user_id, subject, status)")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_plan_days (
                id BIGSERIAL PRIMARY KEY,
                plan_id BIGINT NOT NULL REFERENCES speaking_plans(id) ON DELETE CASCADE,
                day_index INTEGER NOT NULL,
                kind TEXT NOT NULL DEFAULT 'practice',
                base_focus TEXT NOT NULL,
                focus TEXT NOT NULL,
                adapted_reason TEXT NOT NULL DEFAULT '',
                best_score INTEGER,
                attempts INTEGER NOT NULL DEFAULT 0,
                exam_id BIGINT,
                completed_at TIMESTAMPTZ,
                UNIQUE (plan_id, day_index)
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_plan_tests (
                id BIGSERIAL PRIMARY KEY,
                subject TEXT NOT NULL DEFAULT 'english',
                focus TEXT NOT NULL,
                band TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                questions_json TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'draft',
                source TEXT NOT NULL DEFAULT 'ai',
                explanation_language TEXT NOT NULL DEFAULT 'uz',
                created_by BIGINT,
                uses INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_plan_tests_pick ON speaking_plan_tests(subject, focus, band, status)")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_plan_attempts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                plan_day_id BIGINT REFERENCES speaking_plan_days(id) ON DELETE SET NULL,
                test_id BIGINT REFERENCES speaking_plan_tests(id) ON DELETE SET NULL,
                subject TEXT NOT NULL DEFAULT 'english',
                focus TEXT NOT NULL DEFAULT '',
                band TEXT NOT NULL DEFAULT '',
                questions_json TEXT NOT NULL DEFAULT '[]',
                question_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'started',
                score INTEGER,
                correct INTEGER,
                total INTEGER,
                results_json TEXT NOT NULL DEFAULT '[]',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                finished_at TIMESTAMPTZ
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_plan_attempts_user ON speaking_plan_attempts(user_id, created_at DESC)")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_plan_answer_checks (
                attempt_id BIGINT NOT NULL REFERENCES speaking_plan_attempts(id) ON DELETE CASCADE,
                item_key TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                verdict TEXT NOT NULL,
                result_json TEXT NOT NULL DEFAULT '{}',
                checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (attempt_id, item_key)
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


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, TASHKENT)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _goal_value(goal: str) -> float:
    try:
        return float(goal)
    except (TypeError, ValueError):
        return 6.0


def _goal_label(subject: str, goal: str) -> str:
    if subject == "english":
        return "IELTS 7.0+" if goal == "7.0" else f"IELTS {goal}"
    return f"{goal}/10"


def _criterion_of(focus: str) -> str:
    if focus.startswith("vocabulary"):
        return "vocabulary"
    if focus.startswith("grammar"):
        return "grammar"
    if focus == "pronunciation":
        return "pronunciation"
    return "fluency"


def _focus_family(focus: str) -> str:
    return "vocabulary" if focus.startswith("vocabulary_") else focus


def _valid_focus(focus: str) -> bool:
    return focus in PRACTICE_FOCUSES


def _json_list(raw: Any) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def _json_dict(raw: Any) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


# ---------------------------------------------------------------------------
# Plan template and adaptation
# ---------------------------------------------------------------------------

def build_plan_template(days: int) -> list[dict[str, str]]:
    """Day list (1-based order) with kind and base focus."""
    mocks = MOCK_DAYS.get(days, {days: "full_mock"})
    result: list[dict[str, str]] = []
    practice_index = 0
    for day_index in range(1, days + 1):
        if day_index in mocks:
            result.append({"kind": mocks[day_index], "focus": mocks[day_index]})
            continue
        cycle, slot = divmod(practice_index, 6)
        focus = (
            "part1_fluency",
            f"vocabulary_{VOCAB_TOPICS[cycle % len(VOCAB_TOPICS)]}",
            "part2_structure",
            "grammar_accuracy" if cycle % 2 == 0 else "grammar_range",
            "part3_discussion",
            "pronunciation",
        )[slot]
        result.append({"kind": "practice", "focus": focus})
        practice_index += 1
    return result


def _weak_focus(criterion: str, turn: int) -> str:
    if criterion == "grammar":
        return ("grammar_accuracy", "grammar_range")[turn % 2]
    if criterion == "vocabulary":
        return f"vocabulary_{VOCAB_TOPICS[turn % len(VOCAB_TOPICS)]}"
    if criterion == "pronunciation":
        return "pronunciation"
    return ("part1_fluency", "part3_discussion", "part2_structure")[turn % 3]


def adapt_future_days(future: list[dict[str, Any]], weak: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """New focus/adapted_reason for future practice days (base focus kept).

    The weakest criterion takes every second future day when it is far below
    the goal (severity >= 2) and every third day otherwise; the second weakest
    takes every fourth day.  Days whose base focus already trains the weakest
    criterion are never replaced.
    """
    planned: list[dict[str, Any]] = []
    turns: dict[str, int] = {}
    first = weak[0]["criterion"] if weak else None
    step = 2 if weak and float(weak[0].get("severity") or 0) >= 2 else 3
    for position, day in enumerate(future):
        base = str(day["base_focus"])
        focus, reason = base, ""
        target: str | None = None
        if first and position % step == 0:
            target = first
        elif len(weak) > 1 and position % 4 == 3:
            target = weak[1]["criterion"]
        if target and _criterion_of(base) != target and _criterion_of(base) != first:
            turn = turns.get(target, 0)
            turns[target] = turn + 1
            focus, reason = _weak_focus(target, turn), target
        planned.append({**day, "focus": focus, "adapted_reason": reason})
    return planned


def weak_criteria(analysis_rows: list[dict[str, Any]], test_rows: list[dict[str, Any]], *, subject: str, goal: float) -> list[dict[str, Any]]:
    """Criteria below the goal, weakest first.

    ``analysis_rows`` carry ``criteria_json`` from AI speaking feedback;
    ``test_rows`` carry ``focus`` and ``score`` (0-100) of finished plan tests.
    """
    margin = 0.5 if subject == "english" else 1.0
    sums: dict[str, list[float]] = {key: [] for key in CRITERIA}
    for row in analysis_rows:
        criteria = _json_dict(row.get("criteria_json"))
        for key in CRITERIA:
            try:
                if criteria.get(key) is not None:
                    sums[key].append(float(criteria[key]))
            except (TypeError, ValueError):
                continue
    tests: dict[str, list[float]] = {key: [] for key in CRITERIA}
    for row in test_rows:
        try:
            tests[_criterion_of(str(row.get("focus") or ""))].append(float(row.get("score") or 0))
        except (TypeError, ValueError):
            continue
    result = []
    for key in CRITERIA:
        speaking_avg = round(sum(sums[key]) / len(sums[key]), 2) if len(sums[key]) >= 2 else None
        test_avg = round(sum(tests[key]) / len(tests[key]), 1) if tests[key] else None
        severity = 0.0
        if speaking_avg is not None:
            severity = max(severity, (goal - speaking_avg) / margin)
        if test_avg is not None:
            severity = max(severity, (70.0 - test_avg) / 10.0)
        if severity >= 1.0:
            result.append({
                "criterion": key, "severity": round(severity, 2),
                "speaking_average": speaking_avg, "test_average": test_avg, "goal": goal,
            })
    result.sort(key=lambda item: item["severity"], reverse=True)
    return result


def _load_weak(cur, user_id: int, subject: str, goal: float) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=14)
    analysis_rows: list[dict[str, Any]] = []
    try:
        cur.execute(
            """SELECT criteria_json FROM speaking_answer_analyses
               WHERE user_id=%s AND subject=%s AND created_at >= %s ORDER BY created_at DESC LIMIT 60""",
            (user_id, subject, since),
        )
        analysis_rows = [dict(r) for r in cur.fetchall() or []]
    except Exception:
        # The analyses table is created by speaking_answers; a fresh database
        # without it simply has no feedback yet.
        cur.connection.rollback()
    cur.execute(
        """SELECT focus, score FROM speaking_plan_attempts
           WHERE user_id=%s AND subject=%s AND status='finished' AND finished_at >= %s
           ORDER BY finished_at DESC LIMIT 40""",
        (user_id, subject, since),
    )
    test_rows = [dict(r) for r in cur.fetchall() or []]
    return weak_criteria(analysis_rows, test_rows, subject=subject, goal=goal)


# ---------------------------------------------------------------------------
# Learner profile (Speaking account or Student account)
# ---------------------------------------------------------------------------

def _estimate_from_level(subject: str, level: str) -> float | None:
    text = str(level or "").strip().upper()
    match = re.search(r"\b([ABC][12])\b", text)
    if match:
        return CEFR_ESTIMATE[subject].get(match.group(1))
    number = re.search(r"(\d+(?:\.\d)?)", text)
    if number and "IELTS" in text and subject == "english":
        return float(number.group(1))
    return None


def recommend_goal(subject: str, estimate: float | None) -> tuple[str, int]:
    goals = GOALS[subject]
    if estimate is None:
        return (goals[1], 14)
    step = 0.5 if subject == "english" else 1.0
    goal = next((g for g in goals if float(g) >= estimate + step), goals[-1])
    gap = float(goal) - estimate
    days = 7 if gap <= step else (14 if gap <= 2 * step else 30)
    return goal, days


def _profile(cur, user: dict[str, Any], role: str, subject: str) -> dict[str, Any]:
    from speaking_contract import is_speaking_app_account

    user_id = int(user.get("id") or 0)
    account_type = "speaking" if is_speaking_app_account(user.get("speaking_app_account")) else (
        "student" if role == "student" else role
    )
    level = str(user.get("level") or "").strip()
    user_subject = _subject_key(user.get("subject")) if str(user.get("subject") or "").strip() else None
    estimate: float | None = None
    source = "none"
    try:
        cur.execute(
            """SELECT score FROM speaking_answer_analyses WHERE user_id=%s AND subject=%s
               ORDER BY created_at DESC LIMIT 20""",
            (user_id, subject),
        )
        scores = [float(dict(r)["score"] or 0) for r in cur.fetchall() or []]
    except Exception:
        cur.connection.rollback()
        scores = []
    if len(scores) >= 3:
        from backend.speaking_answers import round_half

        avg = sum(scores) / len(scores)
        estimate = round_half(avg) if subject == "english" else round(avg)
        source = "analyses"
    elif level and (account_type == "student" or user_subject in (None, subject)):
        estimate = _estimate_from_level(subject, level)
        source = "level" if estimate is not None else "none"
    goal, days = recommend_goal(subject, estimate)
    return {
        "account_type": account_type,
        "name": str(user.get("first_name") or "").strip(),
        "level": level,
        "subject_hint": user_subject,
        "estimate": estimate,
        "estimate_source": source,
        "recommended_goal": goal,
        "recommended_days": days,
    }


def _band_for(subject: str, goal: str, estimate: float | None, day_index: int, days: int) -> str:
    """Test difficulty: the goal band, one step lower in the first half of a
    plan when the learner starts far below the goal."""
    goals = GOALS[subject]
    if estimate is None or goal not in goals:
        return goal if goal in goals else goals[1]
    step = 0.5 if subject == "english" else 1.0
    index = goals.index(goal)
    if float(goal) - estimate >= 3 * step and day_index <= days // 2 and index > 0:
        return goals[index - 1]
    return goal


# ---------------------------------------------------------------------------
# Question validation (Learning Path library format)
# ---------------------------------------------------------------------------

def _text(value: Any, limit: int = 600) -> str:
    return " ".join(str(value if value is not None else "").split())[:limit]


def clean_question(raw: Any, subject: str) -> dict[str, Any] | None:
    """A validated plan question or None when it cannot be graded reliably."""
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or raw.get("test_type") or raw.get("question_type") or "").strip().lower()
    if kind not in PLAN_KINDS:
        return None
    question = _text(raw.get("question") or raw.get("prompt"))
    explanation = _text(raw.get("explanation"), 800)
    instruction = _text(raw.get("instruction"), 300)
    item: dict[str, Any] = {"kind": kind, "question": question, "explanation": explanation}
    if instruction:
        item["instruction"] = instruction
    if kind == "multiple_choice":
        options = [_text(o, 200) for o in (raw.get("options") or []) if _text(o, 200)]
        correct = _text(raw.get("correct_answer") or raw.get("answer"), 200)
        if not question or len(options) < 3 or len(options) > 5 or len({o.casefold() for o in options}) != len(options):
            return None
        match = next((o for o in options if o.casefold() == correct.casefold()), None)
        if match is None:
            return None
        item.update(options=options, correct_answer=match)
    elif kind == "true_false":
        options = ["True", "False"] if subject == "english" else ["Верно", "Неверно"]
        value = raw.get("correct_answer", raw.get("answer"))
        truthy = {"true", "t", "yes", "верно", "да", "to'g'ri"}
        falsy = {"false", "f", "no", "неверно", "нет", "noto'g'ri"}
        if isinstance(value, bool):
            flag = value
        elif _text(value).casefold() in truthy:
            flag = True
        elif _text(value).casefold() in falsy:
            flag = False
        else:
            return None
        if not question:
            return None
        item.update(options=options, correct_answer=options[0 if flag else 1])
    elif kind == "gap_fill":
        correct = _text(raw.get("correct_answer") or raw.get("answer"), 120)
        if "___" not in question or question.count("___") != 1 or not correct:
            return None
        accepted = [_text(a, 120) for a in (raw.get("accepted_answers") or []) if _text(a, 120)]
        item.update(correct_answer=correct, accepted_answers=list(dict.fromkeys([correct, *accepted]))[:6])
        options = [_text(o, 120) for o in (raw.get("options") or []) if _text(o, 120)]
        if options:
            if len(options) < 3 or not any(o.casefold() == correct.casefold() for o in options):
                return None
            item["options"] = list(dict.fromkeys(options))[:5]
            item["accepted_answers"] = [correct]
    elif kind == "word_order":
        sentence = _text(raw.get("correct_answer") or raw.get("answer") or raw.get("target_sentence"), 240)
        words = sentence.split()
        if len(words) < 3 or len(words) > 16:
            return None
        tokens = list(words)
        rng = random.Random(hashlib.sha256(sentence.encode()).hexdigest())
        for _ in range(5):
            rng.shuffle(tokens)
            if tokens != words:
                break
        item.update(correct_answer=sentence, tokens=tokens, question=question or "Put the words in the correct order.")
    elif kind == "matching":
        pairs = []
        for pair in raw.get("pairs") or []:
            if isinstance(pair, dict) and _text(pair.get("left"), 120) and _text(pair.get("right"), 160):
                pairs.append({"left": _text(pair.get("left"), 120), "right": _text(pair.get("right"), 160)})
        lefts = {p["left"].casefold() for p in pairs}
        rights = {p["right"].casefold() for p in pairs}
        if len(pairs) < 3 or len(pairs) > 6 or len(lefts) != len(pairs) or len(rights) != len(pairs):
            return None
        item.update(pairs=pairs, question=question or "Match the pairs.")
    else:
        reference = _text(raw.get("reference_answer") or raw.get("sample_answer") or raw.get("target_sentence") or raw.get("correct_answer"), 600)
        if not question or not reference:
            return None
        item.update(reference_answer=reference, sample_answer=reference, check="ai")
        if kind == "read_aloud":
            item.update(target_sentence=reference, sentence=reference)
            if reference not in question:
                item["question"] = f"{question} \u201c{reference}\u201d"
        word = _text(raw.get("word"), 60)
        if word:
            item["word"] = word
    item["language"] = "en" if subject == "english" else "ru"
    return item


def clean_questions(raw_list: Any, subject: str) -> list[dict[str, Any]]:
    if not isinstance(raw_list, list):
        return []
    result = []
    for raw in raw_list[:30]:
        item = clean_question(raw, subject)
        if item:
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# AI generation
# ---------------------------------------------------------------------------

async def _ai_json(system: str, user: str, *, max_tokens: int = 7000) -> dict[str, Any]:
    import aiohttp
    from ai_generator import XAI_ENDPOINT, _get_xai_api_key, _xai_apply_payload_tuning, _xai_model_supports_reasoning_effort
    from backend.main import _homework_ai_model_candidates

    api_key = _get_xai_api_key()
    async with aiohttp.ClientSession() as session:
        for model in _homework_ai_model_candidates()[:2]:
            body: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "temperature": 0.7,
                "max_tokens": max_tokens,
            }
            _xai_apply_payload_tuning(body, model=model, stream=False)
            if _xai_model_supports_reasoning_effort(model):
                body["reasoning_effort"] = "low"
            try:
                async with session.post(
                    XAI_ENDPOINT,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    if resp.status != 200:
                        logger.warning("speaking plan generate status=%s model=%s", resp.status, model)
                        continue
                    data = await resp.json(content_type=None)
            except Exception as exc:
                logger.warning("speaking plan generate error=%s model=%s", type(exc).__name__, model)
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
    raise HTTPException(status_code=503, detail="AI test generation is temporarily unavailable. Please try again.")


EXPLANATION_LANGUAGES = {"uz": "Uzbek (Latin script)", "ru": "Russian", "en": "English"}


def generation_prompt(subject: str, focus: str, band: str, count: int, explanation_language: str, notes: str = "") -> tuple[str, str]:
    family = _focus_family(focus)
    topic_key = focus.split("_", 1)[1] if family == "vocabulary" else ""
    topic = TOPIC_NAMES[subject].get(topic_key, "")
    brief = FOCUS_BRIEFS[subject][family].replace("{topic}", topic)
    kinds = FOCUS_KINDS[family]
    ai_max = max(1, round(count * 0.3))
    target_language = "English" if subject == "english" else "Russian"
    level = BAND_LEVELS[subject].get(band, band)
    system = (
        f"You write practice tests for a {target_language} speaking preparation app used by Uzbek learners. "
        "Every task must train speaking skills, be unambiguous and have exactly one correct answer for objective kinds. "
        "Return ONLY JSON, no markdown."
    )
    user = f"""Create one practice test.
Focus: {brief}
Target level: {level}. Make the language and distractors exactly right for this level.
Number of questions: {count}.
Allowed kinds: {', '.join(kinds)}. Use at least 3 different kinds and at most {ai_max} questions of kinds {', '.join(k for k in kinds if k in AI_KINDS) or 'none'}.
Task text, options and answers are in {target_language}. "explanation" is a short teaching note in {EXPLANATION_LANGUAGES.get(explanation_language, 'Uzbek (Latin script)')}.
{('Extra instructions from the editor: ' + notes.strip()[:500]) if notes.strip() else ''}
JSON shape:
{{"title": "short test title in {target_language}",
 "questions": [
  {{"kind":"multiple_choice","question":"...","options":["a","b","c","d"],"correct_answer":"exactly one of the options","explanation":"..."}},
  {{"kind":"true_false","question":"a statement to judge","correct_answer":true,"explanation":"..."}},
  {{"kind":"gap_fill","question":"one sentence with exactly one ___ gap","correct_answer":"missing word(s)","accepted_answers":["other correct forms"],"explanation":"..."}},
  {{"kind":"word_order","question":"Put the words in the correct order.","correct_answer":"The full correct sentence.","explanation":"..."}},
  {{"kind":"matching","question":"Match ...","pairs":[{{"left":"...","right":"..."}},{{"left":"...","right":"..."}},{{"left":"...","right":"..."}},{{"left":"...","right":"..."}}],"explanation":"..."}},
  {{"kind":"write_sentence","question":"task, e.g. write one sentence using a word","word":"target word","reference_answer":"model answer","explanation":"..."}},
  {{"kind":"paraphrase","question":"Paraphrase: ...","reference_answer":"model paraphrase","explanation":"..."}},
  {{"kind":"guided_writing","question":"short planning or answer task","reference_answer":"model answer","explanation":"..."}},
  {{"kind":"speak_sentence","question":"a speaking question to answer aloud in 1-3 sentences","reference_answer":"model spoken answer","explanation":"..."}},
  {{"kind":"read_aloud","question":"Read the sentence aloud.","reference_answer":"the sentence to read","explanation":"what to pay attention to"}}
 ]}}
Only use the allowed kinds. Word order sentences have 4-12 words. Matching has 4 pairs."""
    return system, user


async def generate_test(subject: str, focus: str, band: str, *, count: int = QUESTIONS_PER_TEST,
                        explanation_language: str = "uz", notes: str = "") -> dict[str, Any]:
    system, user = generation_prompt(subject, focus, band, count, explanation_language, notes)
    raw = await _ai_json(system, user)
    questions = clean_questions(raw.get("questions"), subject)
    if len(questions) < max(3, count // 2):
        raise HTTPException(status_code=502, detail="AI returned too few valid questions. Please try again.")
    title = _text(raw.get("title"), 160) or f"{focus.replace('_', ' ').title()} · {band}"
    return {"title": title, "questions": questions[:count]}


def _insert_test(cur, *, subject: str, focus: str, band: str, title: str, questions: list[dict[str, Any]],
                 status: str, source: str, explanation_language: str, created_by: int | None) -> int:
    cur.execute(
        """INSERT INTO speaking_plan_tests (subject, focus, band, title, questions_json, status, source, explanation_language, created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (subject, focus, band, title, json.dumps(questions, ensure_ascii=False), status, source, explanation_language, created_by),
    )
    return int(dict(cur.fetchone())["id"])


# ---------------------------------------------------------------------------
# Plan loading
# ---------------------------------------------------------------------------

def _active_plan(cur, user_id: int, subject: str) -> dict[str, Any] | None:
    cur.execute(
        "SELECT * FROM speaking_plans WHERE user_id=%s AND subject=%s AND status IN ('active','completed') ORDER BY id DESC LIMIT 1",
        (user_id, subject),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _current_day(plan: dict[str, Any]) -> int:
    started = plan["started_on"] if isinstance(plan["started_on"], date) else date.fromisoformat(str(plan["started_on"]))
    return max(1, min(int(plan["days"]), (_today() - started).days + 1))


def _plan_days(cur, plan_id: int) -> list[dict[str, Any]]:
    cur.execute("SELECT * FROM speaking_plan_days WHERE plan_id=%s ORDER BY day_index", (plan_id,))
    return [dict(r) for r in cur.fetchall() or []]


def _link_mock_days(cur, plan: dict[str, Any], days: list[dict[str, Any]]) -> bool:
    """Complete unlocked mock days with a finished mock exam taken after the
    day opened."""
    current = _current_day(plan)
    used = {int(d["exam_id"]) for d in days if d.get("exam_id")}
    started = plan["started_on"] if isinstance(plan["started_on"], date) else date.fromisoformat(str(plan["started_on"]))
    changed = False
    for day in days:
        if day["kind"] not in MOCK_FOCUSES or day.get("completed_at") or int(day["day_index"]) > current:
            continue
        opened = _day_start(started + timedelta(days=int(day["day_index"]) - 1))
        parts_filter = "AND parts='full'" if day["kind"] == "full_mock" else "AND parts IN ('full','mini')"
        try:
            cur.execute(
                f"""SELECT id, overall FROM speaking_exams
                    WHERE user_id=%s AND subject=%s AND kind='mock' AND status='finished' {parts_filter}
                      AND finished_at >= %s AND COALESCE(overall, 0) > 0
                    ORDER BY finished_at ASC LIMIT 10""",
                (int(plan["user_id"]), plan["subject"], opened),
            )
            rows = [dict(r) for r in cur.fetchall() or []]
        except Exception:
            cur.connection.rollback()
            return changed
        exam = next((r for r in rows if int(r["id"]) not in used), None)
        if not exam:
            continue
        used.add(int(exam["id"]))
        max_score = 9.0 if plan["subject"] == "english" else 10.0
        score = round(float(exam["overall"] or 0) * 100 / max_score)
        cur.execute(
            "UPDATE speaking_plan_days SET exam_id=%s, best_score=%s, completed_at=NOW(), attempts=attempts+1 WHERE id=%s",
            (int(exam["id"]), score, int(day["id"])),
        )
        day.update(exam_id=int(exam["id"]), best_score=score, completed_at=datetime.now(timezone.utc))
        changed = True
    return changed


def _apply_adaptation(cur, plan: dict[str, Any], days: list[dict[str, Any]], weak: list[dict[str, Any]]) -> bool:
    current = _current_day(plan)
    future = [
        d for d in days
        if d["kind"] == "practice" and int(d["day_index"]) > current and not d.get("completed_at") and int(d.get("attempts") or 0) == 0
    ]
    changed = False
    for planned in adapt_future_days(future, weak):
        original = next(d for d in days if d["id"] == planned["id"])
        if original["focus"] != planned["focus"] or original["adapted_reason"] != planned["adapted_reason"]:
            cur.execute(
                "UPDATE speaking_plan_days SET focus=%s, adapted_reason=%s WHERE id=%s",
                (planned["focus"], planned["adapted_reason"], int(planned["id"])),
            )
            original.update(focus=planned["focus"], adapted_reason=planned["adapted_reason"])
            changed = True
    return changed


def _daily_usage(cur, user_id: int) -> dict[str, int]:
    cur.execute(
        "SELECT COALESCE(SUM(question_count), 0) AS n FROM speaking_plan_attempts WHERE user_id=%s AND created_at >= %s",
        (user_id, _day_start(_today())),
    )
    used = int(dict(cur.fetchone() or {}).get("n") or 0)
    return {"limit": DAILY_QUESTION_LIMIT, "used": used, "remaining": max(0, DAILY_QUESTION_LIMIT - used)}


def _public_plan(plan: dict[str, Any], days: list[dict[str, Any]], weak: list[dict[str, Any]]) -> dict[str, Any]:
    current = _current_day(plan)
    started = plan["started_on"] if isinstance(plan["started_on"], date) else date.fromisoformat(str(plan["started_on"]))
    done = sum(1 for d in days if d.get("completed_at"))
    items = []
    for d in days:
        index = int(d["day_index"])
        status = "done" if d.get("completed_at") else ("available" if index <= current else "locked")
        items.append({
            "id": int(d["id"]),
            "day_index": index,
            "date": (started + timedelta(days=index - 1)).isoformat(),
            "kind": d["kind"],
            "focus": d["focus"],
            "base_focus": d["base_focus"],
            "criterion": _criterion_of(d["focus"]) if d["kind"] == "practice" else None,
            "adapted_reason": d.get("adapted_reason") or "",
            "status": status,
            "is_today": index == current,
            "best_score": d.get("best_score"),
            "attempts": int(d.get("attempts") or 0),
            "exam_id": d.get("exam_id"),
            "mock_parts": "full" if d["kind"] == "full_mock" else ("mini" if d["kind"] == "mini_mock" else None),
        })
    return {
        "id": int(plan["id"]),
        "subject": plan["subject"],
        "goal": plan["goal"],
        "goal_label": _goal_label(plan["subject"], plan["goal"]),
        "days": int(plan["days"]),
        "started_on": started.isoformat(),
        "status": plan["status"],
        "current_day": current,
        "completed_days": done,
        "progress_percent": round(done * 100 / max(1, int(plan["days"]))),
        "scale": "ielts" if plan["subject"] == "english" else "ten",
        "passing_score": PASSING_SCORE,
        "items": items,
        "adaptation": {"weak": weak},
    }


def _refresh_plan(cur, plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    days = _plan_days(cur, int(plan["id"]))
    weak = _load_weak(cur, int(plan["user_id"]), plan["subject"], _goal_value(plan["goal"]))
    changed = False
    if plan["status"] == "active":
        changed |= _link_mock_days(cur, plan, days)
        changed |= _apply_adaptation(cur, plan, days, weak)
        if days and all(d.get("completed_at") for d in days):
            cur.execute("UPDATE speaking_plans SET status='completed', updated_at=NOW() WHERE id=%s", (int(plan["id"]),))
            plan["status"] = "completed"
            changed = True
    if changed:
        cur.connection.commit()
    return days, weak


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

class PlanCreate(BaseModel):
    subject: str = Field(default="english", max_length=32)
    goal: str = Field(min_length=1, max_length=8)
    days: int = Field(ge=7, le=30)


class FocusStart(BaseModel):
    subject: str = Field(default="english", max_length=32)
    focus: str = Field(min_length=3, max_length=40)


class CheckAnswer(BaseModel):
    exam_key: str = Field(min_length=3, max_length=40)
    answer_text: str | None = Field(default=None, max_length=4000)
    audio_url: str | None = Field(default=None, max_length=500)
    subject: str | None = Field(default=None, max_length=32)


class SubmitAnswers(BaseModel):
    answers: list[dict[str, Any]] = Field(default_factory=list, max_length=60)


def _goals_payload(subject: str) -> list[dict[str, str]]:
    return [{"value": goal, "label": _goal_label(subject, goal)} for goal in GOALS[subject]]


@router.get("/speaking/plans/current")
@router.get("/api/speaking/plans/current")
async def current_speaking_plan(subject: str = Query(default="english", max_length=32), authorization: str | None = Header(default=None)):
    user, role = _auth(authorization, USER_ROLES)
    ensure_tables()
    subject_key = _subject_key(subject)
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        profile = _profile(cur, user, role, subject_key)
        plan = _active_plan(cur, user_id, subject_key)
        payload_plan = None
        if plan:
            days, weak = _refresh_plan(cur, plan)
            payload_plan = _public_plan(plan, days, weak)
        return {
            "subject": subject_key,
            "profile": profile,
            "goals": _goals_payload(subject_key),
            "durations": list(DURATIONS),
            "plan": payload_plan,
            "daily": _daily_usage(cur, user_id),
        }
    finally:
        cur.close()
        conn.close()


@router.post("/speaking/plans")
@router.post("/api/speaking/plans")
async def create_speaking_plan(payload: PlanCreate, authorization: str | None = Header(default=None)):
    user, _ = _auth(authorization, USER_ROLES)
    ensure_tables()
    subject_key = _subject_key(payload.subject)
    if payload.goal not in GOALS[subject_key]:
        raise HTTPException(status_code=422, detail="Unknown goal")
    if payload.days not in DURATIONS:
        raise HTTPException(status_code=422, detail="A plan lasts 7, 14 or 30 days")
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE speaking_plans SET status='replaced', updated_at=NOW() WHERE user_id=%s AND subject=%s AND status IN ('active','completed')",
            (user_id, subject_key),
        )
        cur.execute(
            "INSERT INTO speaking_plans (user_id, subject, goal, days, started_on) VALUES (%s,%s,%s,%s,%s) RETURNING *",
            (user_id, subject_key, payload.goal, payload.days, _today()),
        )
        plan = dict(cur.fetchone())
        for index, day in enumerate(build_plan_template(payload.days), start=1):
            cur.execute(
                "INSERT INTO speaking_plan_days (plan_id, day_index, kind, base_focus, focus) VALUES (%s,%s,%s,%s,%s)",
                (int(plan["id"]), index, day["kind"], day["focus"], day["focus"]),
            )
        conn.commit()
        days, weak = _refresh_plan(cur, plan)
        return {"plan": _public_plan(plan, days, weak), "daily": _daily_usage(cur, user_id)}
    finally:
        cur.close()
        conn.close()


@router.delete("/speaking/plans/{plan_id}")
@router.delete("/api/speaking/plans/{plan_id}")
async def cancel_speaking_plan(plan_id: int, authorization: str | None = Header(default=None)):
    user, _ = _auth(authorization, USER_ROLES)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE speaking_plans SET status='cancelled', updated_at=NOW() WHERE id=%s AND user_id=%s RETURNING id",
            (int(plan_id), int(user.get("id") or 0)),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Plan not found")
        conn.commit()
        return {"ok": True}
    finally:
        cur.close()
        conn.close()


async def _pick_test(subject: str, focus: str, band: str, user_id: int) -> dict[str, Any]:
    """A published test for this focus and band the learner has done least,
    generating a new one while the bank is small."""
    def candidates() -> list[dict[str, Any]]:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT t.id, t.title, t.questions_json, t.band,
                          (SELECT COUNT(*) FROM speaking_plan_attempts a WHERE a.test_id=t.id AND a.user_id=%s) AS done
                   FROM speaking_plan_tests t
                   WHERE t.subject=%s AND t.focus=%s AND t.band=%s AND t.status='published'""",
                (user_id, subject, focus, band),
            )
            return [dict(r) for r in cur.fetchall() or []]
        finally:
            cur.close()
            conn.close()

    rows = candidates()
    fresh = [r for r in rows if int(r["done"] or 0) == 0]
    if not fresh and len(rows) < BANK_TARGET_PER_FOCUS:
        key = f"{subject}:{focus}:{band}"
        lock = _GENERATION_LOCKS.setdefault(key, asyncio.Lock())
        async with lock:
            rows = candidates()
            fresh = [r for r in rows if int(r["done"] or 0) == 0]
            if not fresh and len(rows) < BANK_TARGET_PER_FOCUS:
                try:
                    generated = await generate_test(subject, focus, band, explanation_language="uz" if subject == "english" else "ru")
                except HTTPException:
                    generated = None
                if generated:
                    conn = get_conn()
                    cur = conn.cursor()
                    try:
                        _insert_test(cur, subject=subject, focus=focus, band=band, title=generated["title"],
                                     questions=generated["questions"], status="published", source="auto",
                                     explanation_language="uz" if subject == "english" else "ru", created_by=None)
                        conn.commit()
                    finally:
                        cur.close()
                        conn.close()
                    rows = candidates()
    if not rows:
        # Fall back to the nearest band that has a published test.
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, title, questions_json, band, 0 AS done FROM speaking_plan_tests WHERE subject=%s AND focus=%s AND status='published'",
                (subject, focus),
            )
            others = [dict(r) for r in cur.fetchall() or []]
        finally:
            cur.close()
            conn.close()
        if not others:
            raise HTTPException(status_code=503, detail="Tests for this day are being prepared. Please try again in a minute.")
        target = _goal_value(band)
        others.sort(key=lambda r: abs(_goal_value(r["band"]) - target))
        rows = [r for r in others if r["band"] == others[0]["band"]]
    least = min(int(r["done"] or 0) for r in rows)
    return random.choice([r for r in rows if int(r["done"] or 0) == least])


def _bonus_questions(subject: str, focus: str, band: str, weak: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Two extra questions for the weakest criterion when today's focus trains
    something else."""
    if not weak or _criterion_of(focus) == weak[0]["criterion"]:
        return []
    criterion = weak[0]["criterion"]
    focuses = [f for f in PRACTICE_FOCUSES if _criterion_of(f) == criterion]
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT questions_json FROM speaking_plan_tests WHERE subject=%s AND band=%s AND status='published' AND focus = ANY(%s) ORDER BY random() LIMIT 1",
            (subject, band, focuses),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row:
        return []
    pool = [q for q in _json_list(dict(row)["questions_json"]) if isinstance(q, dict) and q.get("kind") in OBJECTIVE_KINDS]
    random.shuffle(pool)
    return [{**q, "bonus_for": criterion} for q in pool[:2]]


def _served_questions(attempt_id: int, raw_questions: list[dict[str, Any]], subject: str) -> list[dict[str, Any]]:
    from backend.personalization import _learning_exam_questions

    served = []
    for raw in raw_questions:
        for question in _learning_exam_questions(dict(raw)):
            if not question:
                continue
            index = len(served)
            served.append({
                **question,
                "id": index + 1,
                "exam_key": f"{attempt_id}:{index}",
                "subject_language": "english" if subject == "english" else "russian",
            })
    return served


async def _start_attempt(user: dict[str, Any], role: str, *, subject: str, focus: str, day: dict[str, Any] | None,
                         plan: dict[str, Any] | None) -> dict[str, Any]:
    user_id = int(user.get("id") or 0)
    conn = get_conn()
    cur = conn.cursor()
    try:
        daily = _daily_usage(cur, user_id)
        if daily["remaining"] <= 0:
            raise HTTPException(
                status_code=429,
                detail=f"You have solved the daily maximum of {DAILY_QUESTION_LIMIT} test questions. New tests open tomorrow.",
            )
        profile = _profile(cur, user, role, subject)
        goal = plan["goal"] if plan else profile["recommended_goal"]
        weak = _load_weak(cur, user_id, subject, _goal_value(goal))
    finally:
        cur.close()
        conn.close()
    day_index = int(day["day_index"]) if day else 1
    days_total = int(plan["days"]) if plan else 14
    band = _band_for(subject, goal, profile["estimate"], day_index, days_total)
    test = await _pick_test(subject, focus, band, user_id)
    questions = [q for q in _json_list(test["questions_json"]) if isinstance(q, dict)]
    random.shuffle(questions)
    bonus = _bonus_questions(subject, focus, band, weak)
    questions = questions[: QUESTIONS_PER_TEST - len(bonus)] + bonus
    questions = questions[: daily["remaining"]]
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_plan_attempts (user_id, plan_day_id, test_id, subject, focus, band)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (user_id, int(day["id"]) if day else None, int(test["id"]), subject, focus, band),
        )
        attempt_id = int(dict(cur.fetchone())["id"])
        served = _served_questions(attempt_id, questions, subject)
        cur.execute(
            "UPDATE speaking_plan_attempts SET questions_json=%s, question_count=%s WHERE id=%s",
            (json.dumps(served, ensure_ascii=False), len(served), attempt_id),
        )
        cur.execute("UPDATE speaking_plan_tests SET uses=uses+1 WHERE id=%s", (int(test["id"]),))
        if day:
            cur.execute("UPDATE speaking_plan_days SET attempts=attempts+1 WHERE id=%s", (int(day["id"]),))
        conn.commit()
        daily = _daily_usage(cur, user_id)
    finally:
        cur.close()
        conn.close()
    return {
        "attempt_id": attempt_id,
        "track_title": test.get("title") or "",
        "title": test.get("title") or "",
        "focus": focus,
        "band": band,
        "passing_score": PASSING_SCORE,
        "total_questions": len(served),
        "questions": served,
        "daily": daily,
    }


@router.post("/speaking/plans/days/{day_id}/start")
@router.post("/api/speaking/plans/days/{day_id}/start")
async def start_plan_day(day_id: int, authorization: str | None = Header(default=None)):
    user, role = _auth(authorization, USER_ROLES)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT d.*, p.user_id, p.subject, p.goal, p.days, p.started_on, p.status AS plan_status
               FROM speaking_plan_days d JOIN speaking_plans p ON p.id=d.plan_id WHERE d.id=%s""",
            (int(day_id),),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row or int(dict(row)["user_id"]) != int(user.get("id") or 0):
        raise HTTPException(status_code=404, detail="Plan day not found")
    day = dict(row)
    plan = {"id": day["plan_id"], "user_id": day["user_id"], "subject": day["subject"], "goal": day["goal"],
            "days": day["days"], "started_on": day["started_on"], "status": day["plan_status"]}
    if plan["status"] not in ("active", "completed"):
        raise HTTPException(status_code=409, detail="This plan is no longer active")
    if day["kind"] != "practice":
        raise HTTPException(status_code=409, detail="This day is a mock exam. Start it from the mock exam screen.")
    if int(day["day_index"]) > _current_day(plan):
        raise HTTPException(status_code=423, detail="This day opens later")
    return await _start_attempt(user, role, subject=plan["subject"], focus=day["focus"], day=day, plan=plan)


@router.post("/speaking/plans/practice/start")
@router.post("/api/speaking/plans/practice/start")
async def start_focus_practice(payload: FocusStart, authorization: str | None = Header(default=None)):
    """Extra practice for one focus outside the plan days (same daily limit)."""
    user, role = _auth(authorization, USER_ROLES)
    ensure_tables()
    if not _valid_focus(payload.focus):
        raise HTTPException(status_code=422, detail="Unknown focus")
    subject_key = _subject_key(payload.subject)
    conn = get_conn()
    cur = conn.cursor()
    try:
        plan = _active_plan(cur, int(user.get("id") or 0), subject_key)
    finally:
        cur.close()
        conn.close()
    return await _start_attempt(user, role, subject=subject_key, focus=payload.focus, day=None, plan=plan)


def _attempt(cur, attempt_id: int, user_id: int) -> dict[str, Any]:
    cur.execute("SELECT * FROM speaking_plan_attempts WHERE id=%s AND user_id=%s", (int(attempt_id), int(user_id)))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Test not found")
    return dict(row)


def _attempt_question(attempt: dict[str, Any], exam_key: str) -> dict[str, Any]:
    match = re.fullmatch(r"\s*(\d+):(\d+)\s*", str(exam_key or ""))
    if not match or int(match.group(1)) != int(attempt["id"]):
        raise HTTPException(status_code=422, detail="exam_key is invalid")
    questions = _json_list(attempt.get("questions_json"))
    index = int(match.group(2))
    if index >= len(questions):
        raise HTTPException(status_code=404, detail="Question not found")
    return questions[index]


@router.post("/speaking/plans/attempts/{attempt_id}/check-ai")
@router.post("/api/speaking/plans/attempts/{attempt_id}/check-ai")
async def check_plan_answer(
    attempt_id: int,
    payload: CheckAnswer,
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    from backend.main import _REDIS_CLIENT
    from backend.personalization import (
        _grade_learning_question, _learning_answer_fingerprint, _learning_owned_audio_path,
        _learning_question_needs_ai_check,
    )
    from backend.rate_limiting import consume_rate_limit

    user, _ = _auth(authorization, USER_ROLES)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    allowed, retry_after = consume_rate_limit(_REDIS_CLIENT, f"speaking-plan-check:{user_id}", limit=150, window_seconds=3600)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many checks. Please try again later.", headers={"Retry-After": str(retry_after)})
    conn = get_conn()
    cur = conn.cursor()
    try:
        attempt = _attempt(cur, attempt_id, user_id)
        if attempt["status"] == "finished":
            raise HTTPException(status_code=409, detail="This test is already finished")
        question = _attempt_question(attempt, payload.exam_key)
        subject = str(attempt["subject"] or "english")
        answer = str(payload.answer_text or "").strip()
        if answer == "[Audio answer]":
            answer = ""
        audio_url = (payload.audio_url or "").strip() or None
        if audio_url:
            _learning_owned_audio_path(audio_url, user_id)
        fingerprint = _learning_answer_fingerprint(answer, audio_url)

        def finish(result: dict[str, Any]) -> dict[str, Any]:
            cur.execute(
                """INSERT INTO speaking_plan_answer_checks (attempt_id, item_key, fingerprint, verdict, result_json, checked_at)
                   VALUES (%s,%s,%s,%s,%s,NOW())
                   ON CONFLICT (attempt_id, item_key) DO UPDATE SET fingerprint=EXCLUDED.fingerprint,
                     verdict=EXCLUDED.verdict, result_json=EXCLUDED.result_json, checked_at=NOW()""",
                (int(attempt_id), payload.exam_key.strip(), fingerprint, str(result.get("verdict") or "wrong"),
                 json.dumps(result, ensure_ascii=False, default=str)),
            )
            conn.commit()
            return result

        reference = str(question.get("reference_answer") or question.get("correct_answer") or "")
        if not answer and not audio_url:
            return {"is_correct": False, "verdict": "wrong", "feedback": "", "corrected": reference, "score": 0.0}
        if not _learning_question_needs_ai_check(question) and not audio_url:
            correct, total = _grade_learning_question(question, {"text": answer})
            ok = total > 0 and correct == total
            return finish({"is_correct": ok, "verdict": "correct" if ok else "wrong", "feedback": "",
                           "corrected": reference, "score": 100.0 if ok else 0.0})

        from backend.library_ai import AiTestAnswerRequest, _check_with_ai

        q_for_ai = {
            "kind": str(question.get("kind") or question.get("test_type") or "open"),
            "prompt": str(question.get("question") or ""),
            "instruction": str(question.get("instruction") or ""),
            "word": question.get("word"),
            "reference_answer": reference,
            "target_level": attempt.get("band"),
            "accepted_answers": [a for a in (question.get("accepted_answers") or []) if a],
        }
        language = "ru" if subject == "russian" else (x_language or "uz")
        try:
            verdict, feedback = await _check_with_ai(
                q_for_ai, AiTestAnswerRequest(question_index=0, answer_text=answer, audio_url=audio_url),
                "Russian" if subject == "russian" else "English", language,
            )
        except HTTPException as exc:
            if exc.status_code < 500:
                raise
            raise HTTPException(status_code=503, detail="AI checking is temporarily unavailable. Please try again.")
        except Exception as exc:
            logger.warning("speaking plan ai check unavailable: %s", exc)
            raise HTTPException(status_code=503, detail="AI checking is temporarily unavailable. Please try again.")
        ok = verdict == "correct"
        return finish({
            "is_correct": ok,
            "verdict": "correct" if ok else "wrong",
            "feedback": feedback.get("feedback") or "",
            "transcript": feedback.get("transcript") or "",
            "corrected": feedback.get("corrected") or reference,
            "grammar_errors": feedback.get("grammar_errors") or [],
            "pronunciation_errors": feedback.get("pronunciation_errors") or [],
            "was_spoken": bool(feedback.get("was_spoken") or audio_url),
            "score": feedback.get("score") or (100.0 if ok else 0.0),
        })
    finally:
        cur.close()
        conn.close()


@router.post("/speaking/plans/attempts/{attempt_id}/submit")
@router.post("/api/speaking/plans/attempts/{attempt_id}/submit")
async def submit_plan_attempt(attempt_id: int, payload: SubmitAnswers, authorization: str | None = Header(default=None)):
    from backend.personalization import (
        _grade_learning_question, _learning_given_fingerprint, _learning_owned_audio_path,
        _learning_question_needs_ai_check,
    )

    user, _ = _auth(authorization, USER_ROLES)
    ensure_tables()
    user_id = int(user.get("id") or 0)
    submitted: dict[str, Any] = {}
    for item in payload.answers:
        key = str(item.get("exam_key") or "").strip()
        if key:
            submitted[key] = item.get("answer", item.get("selected"))
    conn = get_conn()
    cur = conn.cursor()
    try:
        attempt = _attempt(cur, attempt_id, user_id)
        if attempt["status"] == "finished":
            return {
                "ok": True, "passed": int(attempt["score"] or 0) >= PASSING_SCORE, "score": int(attempt["score"] or 0),
                "correct": int(attempt["correct"] or 0), "total": int(attempt["total"] or 0),
                "results": _json_list(attempt.get("results_json")), "required_score": PASSING_SCORE,
                "reward_coins": 0, "message": "",
            }
        questions = _json_list(attempt.get("questions_json"))
        cur.execute("SELECT item_key, fingerprint, verdict FROM speaking_plan_answer_checks WHERE attempt_id=%s", (int(attempt_id),))
        checks = {str(dict(r)["item_key"]): dict(r) for r in cur.fetchall() or []}
        results = []
        correct_items = 0
        for index, question in enumerate(questions):
            key = f"{int(attempt_id)}:{index}"
            given = submitted.get(key)
            if isinstance(given, dict) and given.get("audio_url"):
                _learning_owned_audio_path(str(given["audio_url"]), user_id)
            ai_ok = False
            if given is not None and _learning_question_needs_ai_check(question):
                check = checks.get(key)
                ai_ok = bool(check and check["verdict"] == "correct" and check["fingerprint"] == _learning_given_fingerprint(given))
            item_correct, item_total = (0, 1) if given is None else _grade_learning_question(question, given, saved_ai_ok=ai_ok)
            fully = item_total > 0 and item_correct >= item_total
            correct_items += int(fully)
            results.append({"exam_key": key, "correct": fully, "correct_count": int(item_correct), "total": int(item_total)})
        total = len(questions)
        score = round(correct_items * 100 / total) if total else 0
        cur.execute(
            """UPDATE speaking_plan_attempts SET status='finished', score=%s, correct=%s, total=%s, results_json=%s, finished_at=NOW()
               WHERE id=%s AND status='started' RETURNING plan_day_id""",
            (score, correct_items, total, json.dumps(results), int(attempt_id)),
        )
        updated = cur.fetchone()
        day_id = dict(updated).get("plan_day_id") if updated else None
        if day_id:
            cur.execute(
                """UPDATE speaking_plan_days SET best_score=GREATEST(COALESCE(best_score, 0), %s),
                     completed_at=COALESCE(completed_at, NOW()) WHERE id=%s""",
                (score, int(day_id)),
            )
        conn.commit()
        passed = score >= PASSING_SCORE
        return {
            "ok": True, "passed": passed, "score": score, "correct": correct_items, "total": total,
            "results": results, "required_score": PASSING_SCORE, "reward_coins": 0,
            "daily": _daily_usage(cur, user_id),
            "message": "",
        }
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Staff endpoints (Speaking admin workspace on the website)
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    subject: str = Field(default="english", max_length=32)
    focus: str = Field(min_length=3, max_length=40)
    band: str = Field(min_length=1, max_length=8)
    tests: int = Field(default=1, ge=1, le=3)
    questions: int = Field(default=QUESTIONS_PER_TEST, ge=5, le=15)
    explanation_language: str = Field(default="uz", pattern="^(uz|ru|en)$")
    publish: bool = False
    notes: str = Field(default="", max_length=500)


class TestUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    status: str | None = Field(default=None, pattern="^(draft|published)$")
    band: str | None = Field(default=None, max_length=8)
    questions: list[dict[str, Any]] | None = Field(default=None, max_length=30)


def _staff_item(row: dict[str, Any], *, with_questions: bool = False) -> dict[str, Any]:
    questions = _json_list(row.get("questions_json"))
    item = {
        "id": int(row["id"]),
        "subject": row["subject"],
        "focus": row["focus"],
        "band": row["band"],
        "title": row.get("title") or "",
        "status": row["status"],
        "source": row["source"],
        "explanation_language": row.get("explanation_language") or "uz",
        "question_count": len(questions),
        "kinds": sorted({str(q.get("kind")) for q in questions if isinstance(q, dict)}),
        "uses": int(row.get("uses") or 0),
        "attempts": int(row.get("attempts") or 0),
        "average_score": int(row["average_score"]) if row.get("average_score") is not None else None,
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }
    if with_questions:
        item["questions"] = questions
    return item


def _staff_meta() -> dict[str, Any]:
    return {
        "subjects": ["english", "russian"],
        "focuses": list(PRACTICE_FOCUSES),
        "bands": GOALS,
        "kinds": sorted(PLAN_KINDS),
        "ai_kinds": sorted(AI_KINDS),
        "focus_kinds": {focus: FOCUS_KINDS[_focus_family(focus)] for focus in PRACTICE_FOCUSES},
        "daily_question_limit": DAILY_QUESTION_LIMIT,
        "questions_per_test": QUESTIONS_PER_TEST,
    }


@router.get("/staff/speaking/plan-tests")
async def staff_list_plan_tests(
    subject: str = Query(default="", max_length=32),
    focus: str = Query(default="", max_length=40),
    band: str = Query(default="", max_length=8),
    status: str = Query(default="", max_length=16),
    authorization: str | None = Header(default=None),
):
    _auth(authorization, STAFF_ROLES)
    ensure_tables()
    where, params = ["1=1"], []
    if subject:
        where.append("t.subject=%s")
        params.append(_subject_key(subject))
    if focus:
        where.append("t.focus=%s")
        params.append(focus)
    if band:
        where.append("t.band=%s")
        params.append(band)
    if status in ("draft", "published"):
        where.append("t.status=%s")
        params.append(status)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""SELECT t.*, (SELECT COUNT(*) FROM speaking_plan_attempts a WHERE a.test_id=t.id AND a.status='finished') AS attempts,
                       (SELECT ROUND(AVG(a.score)) FROM speaking_plan_attempts a WHERE a.test_id=t.id AND a.status='finished') AS average_score
                FROM speaking_plan_tests t WHERE {' AND '.join(where)} ORDER BY t.updated_at DESC LIMIT 500""",
            params,
        )
        items = [_staff_item(dict(r)) for r in cur.fetchall() or []]
        cur.execute(
            """SELECT COUNT(DISTINCT user_id) AS learners, COALESCE(SUM(question_count),0) AS questions, COUNT(*) AS tests
               FROM speaking_plan_attempts WHERE created_at >= %s""",
            (_day_start(_today()),),
        )
        today = dict(cur.fetchone() or {})
        cur.execute("SELECT COUNT(*) AS n FROM speaking_plans WHERE status='active'")
        active_plans = int(dict(cur.fetchone() or {}).get("n") or 0)
        return {
            "items": items,
            "meta": _staff_meta(),
            "stats": {
                "active_plans": active_plans,
                "learners_today": int(today.get("learners") or 0),
                "tests_today": int(today.get("tests") or 0),
                "questions_today": int(today.get("questions") or 0),
            },
        }
    finally:
        cur.close()
        conn.close()


@router.get("/staff/speaking/plan-tests/{test_id}")
async def staff_get_plan_test(test_id: int, authorization: str | None = Header(default=None)):
    _auth(authorization, STAFF_ROLES)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_plan_tests WHERE id=%s", (int(test_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Test not found")
        return {"item": _staff_item(dict(row), with_questions=True)}
    finally:
        cur.close()
        conn.close()


@router.post("/staff/speaking/plan-tests/generate")
async def staff_generate_plan_tests(payload: GenerateRequest, authorization: str | None = Header(default=None)):
    user, _ = _auth(authorization, STAFF_ROLES)
    ensure_tables()
    subject_key = _subject_key(payload.subject)
    if not _valid_focus(payload.focus):
        raise HTTPException(status_code=422, detail="Unknown focus")
    if payload.band not in GOALS[subject_key]:
        raise HTTPException(status_code=422, detail="Unknown band for this subject")
    from backend.main import _REDIS_CLIENT
    from backend.rate_limiting import consume_rate_limit

    allowed, retry_after = consume_rate_limit(
        _REDIS_CLIENT, f"speaking-plan-generate:{int(user.get('id') or 0)}", limit=60, window_seconds=3600
    )
    if not allowed:
        raise HTTPException(status_code=429, detail="Generation limit reached. Please try again later.", headers={"Retry-After": str(retry_after)})
    created: list[dict[str, Any]] = []
    errors: list[str] = []
    for _ in range(payload.tests):
        try:
            generated = await generate_test(
                subject_key, payload.focus, payload.band, count=payload.questions,
                explanation_language=payload.explanation_language, notes=payload.notes,
            )
        except HTTPException as exc:
            errors.append(str(exc.detail))
            continue
        conn = get_conn()
        cur = conn.cursor()
        try:
            test_id = _insert_test(
                cur, subject=subject_key, focus=payload.focus, band=payload.band, title=generated["title"],
                questions=generated["questions"], status="published" if payload.publish else "draft", source="ai",
                explanation_language=payload.explanation_language, created_by=int(user.get("id") or 0) or None,
            )
            conn.commit()
            cur.execute("SELECT * FROM speaking_plan_tests WHERE id=%s", (test_id,))
            created.append(_staff_item(dict(cur.fetchone()), with_questions=True))
        finally:
            cur.close()
            conn.close()
    if not created:
        raise HTTPException(status_code=503, detail=errors[0] if errors else "AI test generation failed")
    return {"items": created, "errors": errors}


@router.put("/staff/speaking/plan-tests/{test_id}")
async def staff_update_plan_test(test_id: int, payload: TestUpdate, authorization: str | None = Header(default=None)):
    _auth(authorization, STAFF_ROLES)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_plan_tests WHERE id=%s", (int(test_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Test not found")
        current = dict(row)
        sets, params = ["updated_at=NOW()"], []
        if payload.title is not None:
            sets.append("title=%s")
            params.append(_text(payload.title, 160))
        if payload.status is not None:
            sets.append("status=%s")
            params.append(payload.status)
        if payload.band is not None:
            if payload.band not in GOALS[str(current["subject"])]:
                raise HTTPException(status_code=422, detail="Unknown band for this subject")
            sets.append("band=%s")
            params.append(payload.band)
        if payload.questions is not None:
            cleaned = clean_questions(payload.questions, str(current["subject"]))
            if len(cleaned) != len(payload.questions):
                raise HTTPException(
                    status_code=422,
                    detail=f"{len(payload.questions) - len(cleaned)} question(s) are incomplete: check the answer key, options and gaps.",
                )
            if len(cleaned) < 3:
                raise HTTPException(status_code=422, detail="A test needs at least 3 questions")
            sets.append("questions_json=%s")
            params.append(json.dumps(cleaned, ensure_ascii=False))
        cur.execute(f"UPDATE speaking_plan_tests SET {', '.join(sets)} WHERE id=%s RETURNING *", [*params, int(test_id)])
        updated = dict(cur.fetchone())
        conn.commit()
        return {"item": _staff_item(updated, with_questions=True)}
    finally:
        cur.close()
        conn.close()


@router.delete("/staff/speaking/plan-tests/{test_id}")
async def staff_delete_plan_test(test_id: int, authorization: str | None = Header(default=None)):
    _auth(authorization, STAFF_ROLES)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_plan_tests WHERE id=%s RETURNING id", (int(test_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Test not found")
        conn.commit()
        return {"ok": True}
    finally:
        cur.close()
        conn.close()
