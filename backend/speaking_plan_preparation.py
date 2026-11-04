"""Resumable, per-learner plan preparation; no database connection spans AI I/O.

The database lease excludes duplicate workers, while each completed day is
committed independently. After a worker restart POST /prepare resumes the
unfinished days once the old lease expires; it never resets real progress.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import contextmanager

from db import get_conn

logger = logging.getLogger(__name__)
_tasks: dict[int, asyncio.Task] = {}
_slots = asyncio.Semaphore(2)


@contextmanager
def _cursor():
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def queue_preparation(plan_id: int, user_id: int) -> None:
    if plan_id in _tasks:
        return
    task = asyncio.create_task(_prepare(plan_id, user_id))
    _tasks[plan_id] = task
    task.add_done_callback(lambda finished: _tasks.pop(plan_id, None))


async def _mock_steps(subject: str, kind: str, context: dict) -> list[dict]:
    from backend import speaking_plans as p
    from backend.speaking_exams import TIMINGS

    parts = ([1] * (5 if kind == "mini_mock" else 10) if subject == "russian" else
             [1] * (4 if kind == "mini_mock" else 6) + [2] + [3] * (3 if kind == "mini_mock" else 5))
    raw = await p._ai_json(
        "You are a speaking examiner. Return only JSON. No solutions or sample answers.",
        f"Prepare a personalised {subject} speaking mock exam. Learner: {json.dumps(context, ensure_ascii=False)}. "
        f"Return questions in this exact part order: {parts}. All text must be in {subject}. "
        'Shape: {"questions":[{"part":1,"prompt":"...","topic":"...","bullets":[]}]}. '
        "For part 2 provide a cue card with 4 specific bullets. Use varied, self-contained questions.",
    )
    questions = raw.get("questions") or []
    if not isinstance(questions, list) or len(questions) != len(parts):
        raise ValueError("Incomplete mock exam")
    steps = []
    for index, (question, part) in enumerate(zip(questions, parts)):
        if not isinstance(question, dict) or question.get("part") != part:
            raise ValueError("Invalid mock part")
        prompt = p._text(question.get("prompt"), 1000)
        bullets = [p._text(x, 300) for x in question.get("bullets", []) if isinstance(x, str) and x.strip()]
        if not prompt or (part == 2 and len(bullets) != 4):
            raise ValueError("Missing mock stimulus")
        steps.append({"index": index, "part": part, "question_id": None,
                      "prompt": prompt, "topic": p._text(question.get("topic"), 160),
                      "bullets": bullets if part == 2 else [],
                      "prep_seconds": TIMINGS[subject]["part2_prep"] if part == 2 else 0,
                      "answer_seconds": TIMINGS[subject][f"part{part}"]})
    return steps


async def _prepare(plan_id: int, user_id: int) -> None:
    from backend import speaking_plans as p

    token = uuid.uuid4().hex
    async with _slots:
        try:
            with _cursor() as cur:
                cur.execute(
                    """UPDATE speaking_plans SET preparation_status='preparing', preparation_token=%s,
                       preparation_lease_until=NOW()+INTERVAL '15 minutes', preparation_error=NULL
                       WHERE id=%s AND user_id=%s AND status='active'
                         AND preparation_status NOT IN ('legacy','ready')
                         AND (preparation_lease_until IS NULL OR preparation_lease_until<NOW()) RETURNING *""",
                    (token, plan_id, user_id),
                )
                row = cur.fetchone()
                if not row:
                    return
                plan = dict(row)
                days = p._plan_days(cur, plan_id)
            context = json.loads(plan.get("preparation_context") or "{}")
            if not context.get("analysed"):
                blueprint = await p._ai_json(
                    "You design individual speaking practice from verified learner performance. Return only JSON.",
                    f"Subject: {plan['subject']}; target: {plan['goal']}; learner: {json.dumps(context, ensure_ascii=False)}. "
                    f"Plan days: {len(days)}. Allowed practice focuses: {list(p.PRACTICE_FOCUSES)}. "
                    'Return {"days":[{"day_index":1,"focus":"..."}, ...]} for EVERY day. '
                    "Progress from current ability to the goal, prioritising weak criteria. Do not invent a learner history.",
                )
                raw_days = blueprint.get("days")
                if not isinstance(raw_days, list) or len(raw_days) != len(days):
                    raise ValueError("Invalid personalised plan blueprint")
                picks = {x.get("day_index"): x.get("focus") for x in raw_days if isinstance(x, dict)}
                if len(picks) != len(days) or any(picks.get(int(d["day_index"])) not in p.PRACTICE_FOCUSES for d in days):
                    raise ValueError("Invalid personalised plan blueprint")
                context["analysed"] = True
                with _cursor() as cur:
                    cur.execute("SELECT id FROM speaking_plans WHERE id=%s AND preparation_token=%s AND status='active' FOR UPDATE", (plan_id, token))
                    if not cur.fetchone():
                        return
                    for day in days:
                        if day["kind"] == "practice" and not p._json_list(day.get("prepared_json")):
                            day["focus"] = picks[int(day["day_index"])]
                            cur.execute("UPDATE speaking_plan_days SET focus=%s WHERE id=%s", (day["focus"], day["id"]))
                    cur.execute("UPDATE speaking_plans SET preparation_context=%s, preparation_lease_until=NOW()+INTERVAL '15 minutes' WHERE id=%s", (json.dumps(context), plan_id))
            for day in days:
                if p._json_list(day.get("prepared_json")):
                    continue
                with _cursor() as cur:
                    cur.execute("UPDATE speaking_plans SET preparation_lease_until=NOW()+INTERVAL '15 minutes' WHERE id=%s AND preparation_token=%s AND status='active' RETURNING id", (plan_id, token))
                    if not cur.fetchone():
                        return
                # One bounded retry for malformed AI output. Ready days never regenerate.
                questions = None
                for retry in range(2):
                    try:
                        if day["kind"] in p.MOCK_FOCUSES:
                            questions = await _mock_steps(plan["subject"], day["kind"], context)
                        else:
                            band = p._band_for(plan["subject"], plan["goal"], context.get("estimate"), int(day["day_index"]), int(plan["days"]))
                            generated = await p.generate_test(
                                plan["subject"], day["focus"], band,
                                explanation_language=context.get("explanation_language", "uz"),
                                notes=f"Day {day['day_index']} of {plan['days']}. Learner performance: {json.dumps(context, ensure_ascii=False)}",
                            )
                            questions = generated["questions"]
                        break
                    except Exception:
                        if retry:
                            raise
                with _cursor() as cur:
                    cur.execute("SELECT id FROM speaking_plans WHERE id=%s AND preparation_token=%s AND status='active' FOR UPDATE", (plan_id, token))
                    if not cur.fetchone():
                        return
                    cur.execute("UPDATE speaking_plan_days SET prepared_json=%s WHERE id=%s", (json.dumps(questions, ensure_ascii=False), day["id"]))
            with _cursor() as cur:
                cur.execute("UPDATE speaking_plans SET preparation_status='ready', preparation_token=NULL, preparation_lease_until=NULL, updated_at=NOW() WHERE id=%s AND preparation_token=%s AND status='active'", (plan_id, token))
        except asyncio.CancelledError:
            # Preserve the lease on process termination; another worker resumes
            # after expiry rather than overlapping an uncertain provider request.
            raise
        except Exception as exc:
            logger.warning("Speaking plan preparation failed plan=%s type=%s", plan_id, type(exc).__name__)
            with _cursor() as cur:
                cur.execute("UPDATE speaking_plans SET preparation_status='failed', preparation_error='generation_unavailable', preparation_token=NULL, preparation_lease_until=NULL WHERE id=%s AND preparation_token=%s", (plan_id, token))
