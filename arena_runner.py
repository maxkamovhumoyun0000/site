"""
Scheduled Daily / Boss arena coordinators: shared arena_run_questions + arena_run_answers.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Any

from aiogram import Bot

from db import (
    add_dpoints,
    add_dcoins,
    boss_aggregate_stats,
    delete_arena_run_questions,
    fetch_arena_run_questions,
    get_conn,
    get_scheduled_arena_run,
    get_user_by_id,
    leaderboard_users_single_stage,
    leaderboard_users_through_stage,
    list_arena_run_participants,
    list_arena_run_users_stage_answer_stats,
    list_non_eliminated_participants,
    mark_participant_eliminated,
    record_arena_run_answer,
    update_scheduled_arena_run,
)
from i18n import detect_lang_from_user, t

logger = logging.getLogger(__name__)

arena_run_poll_map: dict[str, dict[str, Any]] = {}

ARENA_SCHEDULED_POLL_SECONDS = 30
BOSS_JOIN_WINDOW_SECONDS = 60
BOSS_GLOBAL_ACCURACY_GATE = 0.86
BOSS_POOL_SIZE = 15
BOSS_QUESTIONS_PER_USER = 5
DAILY_MIN_PLAYERS_WAIT_SECONDS = 300

_KEEP_AFTER_STAGE = {1: 12, 2: 9, 3: 6, 4: 4}


def _target_after_stage(stage_done: int, n: int) -> int:
    if n <= 4:
        return n
    cap = _KEEP_AFTER_STAGE.get(stage_done, 4)
    return min(cap, n)


def _payload_to_opts(payload: dict) -> tuple[list[str], int]:
    opts = [
        str(payload.get("option_a") or ""),
        str(payload.get("option_b") or ""),
        str(payload.get("option_c") or ""),
        str(payload.get("option_d") or ""),
    ]
    co = int(payload.get("correct_option_index") or 1)
    correct_idx0 = max(0, min(3, co - 1))
    return opts, correct_idx0


async def _play_mc_questions_for_user(
    bot: Bot,
    *,
    chat_id: int,
    user_id: int,
    run_id: int,
    stage: int,
    question_rows: list[dict],
) -> tuple[int, int, int]:
    correct = wrong = unanswered = 0
    for idx, qrow in enumerate(question_rows, start=1):
        try:
            payload = json.loads(qrow.get("payload_json") or "{}")
        except Exception:
            payload = {}
        qtext = str(payload.get("question") or "").strip()
        opts, correct_idx0 = _payload_to_opts(payload)
        if len(opts) != 4:
            unanswered += 1
            continue
        title = f"{idx}/{len(question_rows)}\n{qtext}"[:280]
        poll_msg = await bot.send_poll(
            chat_id=chat_id,
            question=title,
            options=opts[:4],
            type="quiz",
            correct_option_id=correct_idx0,
            is_anonymous=False,
            open_period=ARENA_SCHEDULED_POLL_SECONDS,
        )
        pid = poll_msg.poll.id
        ev = asyncio.Event()
        arena_run_poll_map[pid] = {
            "event": ev,
            "chosen": None,
            "run_id": run_id,
            "user_id": user_id,
            "stage": stage,
            "q_index": int(qrow.get("q_index") or idx),
        }
        try:
            await asyncio.wait_for(ev.wait(), timeout=ARENA_SCHEDULED_POLL_SECONDS + 1.0)
        except Exception:
            pass
        meta = arena_run_poll_map.pop(pid, None) or {}
        chosen = meta.get("chosen")
        qix = int(qrow.get("q_index") or idx)
        try:
            await bot.delete_message(chat_id, poll_msg.message_id)
        except Exception:
            pass

        if chosen is None:
            unanswered += 1
            record_arena_run_answer(run_id, user_id, stage, qix, 0, is_unanswered=1)
            continue
        sel = int(chosen)
        ok = 1 if sel == correct_idx0 else 0
        if ok:
            correct += 1
        else:
            wrong += 1
        record_arena_run_answer(run_id, user_id, stage, qix, ok, is_unanswered=0)

    return correct, wrong, unanswered


def _apply_elimination_after_stage(run_id: int, stage_done: int) -> None:
    active = list_non_eliminated_participants(run_id)
    n = len(active)
    if n <= 4:
        return
    ranked = leaderboard_users_through_stage(run_id, stage_done)
    active_ids = {int(p["user_id"]) for p in active}
    ranked = [(uid, sc) for uid, sc in ranked if uid in active_ids]
    ranked.sort(key=lambda x: (-x[1], x[0]))
    keep = _target_after_stage(stage_done, n)
    if keep >= n:
        return
    top_ids = {uid for uid, _ in ranked[:keep]}
    for uid, _ in ranked[keep:]:
        if uid not in top_ids:
            mark_participant_eliminated(run_id, uid, stage_done)


async def run_daily_arena_coordinator(bot: Bot, run_id: int) -> None:
    run = get_scheduled_arena_run(run_id)
    if not run:
        return
    subject = str(run.get("subject") or "English")
    min_p = int(run.get("min_players") or 10)
    parts = list_arena_run_participants(run_id)
    uid_to_chat = {int(p["user_id"]): int(p["chat_id"]) for p in parts}
    try:
        # Wait up to 5 minutes for minimum players.
        wait_deadline = asyncio.get_running_loop().time() + DAILY_MIN_PLAYERS_WAIT_SECONDS
        while True:
            parts = list_arena_run_participants(run_id)
            n = len(parts)
            if n >= min_p:
                break
            if asyncio.get_running_loop().time() >= wait_deadline:
                # Cancel daily run and refund all paid participants.
                for p in parts:
                    uid = int(p["user_id"])
                    chat_id = int(p["chat_id"])
                    add_dcoins(uid, 3.0, subject, change_type="daily_entry_refund")
                    try:
                        u = get_user_by_id(uid) or {}
                        lg = detect_lang_from_user(u)
                        await bot.send_message(chat_id, t(lg, "arena_daily_cancelled_low_players"))
                    except Exception:
                        pass
                delete_arena_run_questions(run_id)
                update_scheduled_arena_run(
                    run_id,
                    status="cancelled",
                    finished_at=datetime.utcnow().isoformat(),
                )
                return
            await asyncio.sleep(2)

        # Update mapping after wait.
        uid_to_chat = {int(p["user_id"]): int(p["chat_id"]) for p in parts}
        participant_ids = {int(p["user_id"]) for p in parts}

        # Countdown: 60 seconds after min players reached.
        await asyncio.sleep(60)

        # Notify non-joined students for this subject.
        try:
            start_hhmm = run.get("start_hhmm") or ""
            conn = get_conn()
            cur = conn.cursor()
            join_query = """
                SELECT DISTINCT u.id as user_id, u.telegram_id, u.language, u.first_name, u.last_name
                FROM users u
                LEFT JOIN user_subject us ON us.user_id = u.id
                WHERE u.login_type IN (1,2)
                  AND u.access_enabled=1
                  AND u.telegram_id IS NOT NULL
                  AND u.id IS NOT NULL
                  AND (
                    LOWER(COALESCE(u.subject,'')) = LOWER(?)
                    OR LOWER(COALESCE(us.subject,'')) = LOWER(?)
                  )
            """
            try:
                cur.execute(join_query, (subject, subject))
            except Exception as e:
                msg = str(e).lower()
                if "relation" in msg and "user_subject" in msg and "does not exist" in msg:
                    # Fallback when user_subject doesn't exist yet.
                    fallback_query = """
                        SELECT DISTINCT u.id as user_id, u.telegram_id, u.language, u.first_name, u.last_name
                        FROM users u
                        WHERE u.login_type IN (1,2)
                          AND u.access_enabled=1
                          AND u.telegram_id IS NOT NULL
                          AND EXISTS (
                            SELECT 1
                            FROM unnest(string_to_array(COALESCE(u.subject,''), ',')) AS s
                            WHERE trim(s) <> '' AND LOWER(trim(s)) = LOWER(?)
                          )
                    """
                    cur.execute(fallback_query, (subject,))
                else:
                    raise

            rows = [dict(r) for r in cur.fetchall() if r.get("telegram_id")]
            for ur in rows:
                uid = int(ur["user_id"])
                if uid in participant_ids:
                    continue
                tg = int(ur["telegram_id"])
                u = {"id": uid, **ur}
                lg = detect_lang_from_user(u)
                try:
                    await bot.send_message(
                        tg,
                        t(lg, "arena_daily_late_joiners_notification", subject=subject, time=start_hhmm),
                    )
                except Exception:
                    pass
        except Exception:
            logger.exception("Daily run %s: late joiner notification failed", run_id)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Start run.
        update_scheduled_arena_run(
            run_id,
            status="running",
            started_at=datetime.utcnow().isoformat(),
            current_stage=1,
        )

        def _difficulty_text(lg: str, s: int) -> str:
            # Short difficulty ramp shown to students.
            if lg == "ru":
                return {1: "Легко", 2: "Средне", 3: "Сложнее", 4: "Сложно", 5: "Максимально сложно"}.get(s, "")
            if lg == "en":
                return {1: "Easy", 2: "Medium", 3: "Medium-hard", 4: "Hard", 5: "Max-hard"}.get(s, "")
            return {1: "Oson", 2: "O‘rtacha", 3: "Qiyinroq", 4: "Qiyin", 5: "Juda qiyin"}.get(s, "")

        def _types_summary(lg: str, s: int) -> str:
            # Stage question-type mix summary (must match ai_generator conceptually).
            if lg == "ru":
                m = {
                    1: "Грамматика, ошибка в предложении, True/False, пропуск слова, определение слова, синонимы",
                    2: "Грамматика, ошибка в предложении, True/False, синонимы/антонимы, пропуск слова, определение слова",
                    3: "Ошибка в предложении, True/False, синонимы/антонимы, пропуск слова, определение слова",
                    4: "Грамматика, ошибка в предложении, True/False, синонимы/антонимы, пропуск слова, определение слова, Reading",
                    5: "Reading, ошибка в предложении, True/False, синонимы/антонимы, пропуск слова, определение слова",
                }
                return m.get(s, "")
            if lg == "en":
                m = {
                    1: "Grammar, sentence error, True/False, gap fill, vocab definition, synonyms",
                    2: "Grammar, sentence error, True/False, synonyms/antonyms, gap fill, vocab definition",
                    3: "Sentence error, True/False, synonyms/antonyms, gap fill, vocab definition",
                    4: "Grammar, sentence error, True/False, synonyms/antonyms, gap fill, vocab definition, Reading",
                    5: "Reading, sentence error, True/False, synonyms/antonyms, gap fill, vocab definition",
                }
                return m.get(s, "")
            m = {
                1: "Grammar, sentence error, True/False, gap filling, vocabulary definition, sinonim",
                2: "Grammar, sentence error, True/False, sinonim/antonim, gap filling, vocabulary definition",
                3: "sentence error, True/False, sinonim/antonim, gap filling, vocabulary definition",
                4: "Grammar, sentence error, True/False, sinonim/antonim, gap filling, vocabulary definition, Reading",
                5: "Reading, sentence error, True/False, sinonim/antonim, gap filling, vocabulary definition",
            }
            return m.get(s, "")

        # To avoid double notifications: once we announce preparation after a stage,
        # we skip the same announcement right at generation start.
        notified_prepare_next_stage: set[int] = set()

        for stage in range(1, 6):
            active = list_non_eliminated_participants(run_id)
            if not active:
                break
            qrows = fetch_arena_run_questions(run_id, stage, None)
            if len(qrows) < 10:
                from ai_generator import generate_daily_arena_stage_questions_and_insert

                # For stage > 1, send a short break/generation message (stage 1 has progress).
                if stage != 1 and stage not in notified_prepare_next_stage:
                    for p in active:
                        uid = int(p["user_id"])
                        chat_id = int(p["chat_id"])
                        u = get_user_by_id(uid) or {}
                        lg = detect_lang_from_user(u)
                        try:
                            diff_txt = _difficulty_text(lg, stage)
                            types_txt = _types_summary(lg, stage)
                            await bot.send_message(
                                chat_id,
                                "\n".join(
                                    [
                                        t(lg, "arena_ai_preparing", mode=f"Daily arena Stage {stage}"),
                                        f"🎯 {diff_txt}",
                                        f"📚 {types_txt}",
                                    ]
                                ),
                            )
                        except Exception:
                            pass

                # For stage 1, show generation progress to current participants.
                progress_cb = None
                if stage == 1:
                    uid_to_lang: dict[int, str] = {}
                    uid_to_chat_stage: dict[int, int] = {}
                    for p in active:
                        uid = int(p["user_id"])
                        uid_to_chat_stage[uid] = int(p["chat_id"])
                        u = get_user_by_id(uid) or {}
                        uid_to_lang[uid] = detect_lang_from_user(u)

                    async def _progress_cb(pct: int, current: int, total: int) -> None:
                        # Keep updates frequent but not too noisy (10% steps for 10 questions).
                        for uid, chat_id in uid_to_chat_stage.items():
                            lg = uid_to_lang.get(uid) or "uz"
                            try:
                                await bot.send_message(
                                    chat_id,
                                    t(
                                        lg,
                                            "arena_daily_stage1_generation_progress_pct_detail",
                                        pct=pct,
                                        current=current,
                                        total=total,
                                    ),
                                )
                            except Exception:
                                pass

                    progress_cb = _progress_cb

                    # Intro message once, right before generation starts.
                    for uid, chat_id in uid_to_chat_stage.items():
                        lg = uid_to_lang.get(uid) or "uz"
                        try:
                            diff_txt = _difficulty_text(lg, stage)
                            types_txt = _types_summary(lg, stage)
                            await bot.send_message(
                                chat_id,
                                "\n".join(
                                    [
                                        t(lg, "arena_ai_preparing", mode=f"Daily arena Stage 1"),
                                        f"🎯 {diff_txt}",
                                        f"📚 {types_txt}",
                                    ]
                                ),
                            )
                        except Exception:
                            pass

                await generate_daily_arena_stage_questions_and_insert(
                    run_id=run_id,
                    stage=stage,
                    subject=subject,
                    progress_cb=progress_cb,
                )
                qrows = fetch_arena_run_questions(run_id, stage, None)
                if len(qrows) < 10:
                    logger.warning("Daily run %s stage %s: generator produced less than 10", run_id, stage)
            tasks = [
                _play_mc_questions_for_user(
                    bot,
                    chat_id=int(p["chat_id"]),
                    user_id=int(p["user_id"]),
                    run_id=run_id,
                    stage=stage,
                    question_rows=qrows,
                )
                for p in active
            ]
            await asyncio.gather(*tasks)
            if stage < 5:
                _apply_elimination_after_stage(run_id, stage)

                # Explicit break: notify finalists about AI generating the next stage,
                # but only if next stage questions still need to be created.
                try:
                    qrows_next = fetch_arena_run_questions(run_id, stage + 1, None)
                    if len(qrows_next) < 10 and (stage + 1) not in notified_prepare_next_stage:
                        active_next = list_non_eliminated_participants(run_id)
                        for p in active_next:
                            uid = int(p["user_id"])
                            chat_id = int(p["chat_id"])
                            u = get_user_by_id(uid) or {}
                            lg = detect_lang_from_user(u)
                            diff_txt = _difficulty_text(lg, stage + 1)
                            types_txt = _types_summary(lg, stage + 1)
                            if lg == "ru":
                                msg = f"✅ Этап {stage} завершён!\nAI готовит вопросы для этапа {stage+1}...\n🎯 {diff_txt}\n📚 {types_txt}"
                            elif lg == "en":
                                msg = f"✅ Stage {stage} finished!\nAI is preparing questions for Stage {stage+1}...\n🎯 {diff_txt}\n📚 {types_txt}"
                            else:
                                msg = f"✅ {stage}-bosqich tugadi!\nAI {stage+1}-bosqich uchun savollar tayyorlayapti...\n🎯 {diff_txt}\n📚 {types_txt}"
                            try:
                                await bot.send_message(chat_id, msg)
                            except Exception:
                                pass
                        notified_prepare_next_stage.add(stage + 1)
                except Exception:
                    pass

        # Final stats and rewards
        participants = list_arena_run_participants(run_id)
        uid_to_chat = {int(p["user_id"]): int(p["chat_id"]) for p in participants}
        participants_by_uid = {int(p["user_id"]): p for p in participants}

        finalists = list_non_eliminated_participants(run_id)
        finalist_ids = {int(p["user_id"]) for p in finalists}

        # Total score through stage 5.
        totals = leaderboard_users_through_stage(run_id, 5)
        totals_filtered = [(int(uid), int(sc)) for uid, sc in totals if int(uid) in finalist_ids]
        totals_filtered.sort(key=lambda x: (-x[1], x[0]))

        rewards = [15.0, 10.0, 5.0]
        rank_map: dict[int, int] = {}
        for rk, (uid, _) in enumerate(totals_filtered, start=1):
            if rk <= 4:
                rank_map[uid] = rk

        top3 = totals_filtered[:3]
        for i, (uid, _) in enumerate(top3):
            add_dpoints(int(uid), rewards[i], subject, change_type="daily_arena_stage5_reward")
            u = get_user_by_id(int(uid)) or {}
            lg = detect_lang_from_user(u)
            chat = uid_to_chat.get(int(uid))
            if chat:
                try:
                    await bot.send_message(
                        chat,
                        t(lg, "arena_daily_podium", place=i + 1, reward=rewards[i]),
                    )
                except Exception:
                    pass

        # Stage-by-stage stats for all participants.
        stage_stats: dict[int, dict[int, dict[str, int]]] = {s: {} for s in range(1, 6)}
        for s in range(1, 6):
            rows = list_arena_run_users_stage_answer_stats(run_id=run_id, stage=s)
            for r in rows:
                uid = int(r["user_id"])
                stage_stats[s][uid] = {
                    "correct": int(r.get("correct") or 0),
                    "wrong": int(r.get("wrong") or 0),
                    "unanswered": int(r.get("unanswered") or 0),
                }

        async def _send_result_message(uid: int) -> None:
            p = participants_by_uid.get(uid) or {}
            u = get_user_by_id(uid) or {}
            lg = detect_lang_from_user(u)
            chat_id = uid_to_chat.get(uid)
            if not chat_id:
                return

            elim_after = p.get("eliminated_after_stage")
            eliminated_text = ""
            try:
                if elim_after is not None:
                    elim_after_int = int(elim_after)
                    if elim_after_int in (1, 2, 3, 4):
                        if lg == "ru":
                            eliminated_text = f"Убрали после этапа {elim_after_int}.\n"
                        elif lg == "en":
                            eliminated_text = f"Eliminated after Stage {elim_after_int}.\n"
                        else:
                            eliminated_text = f"{elim_after_int}-bosqichdan keyin saralashdan chiqqan.\n"
            except Exception:
                pass

            if lg == "ru":
                header = "📊 <b>Ежедневная арена: результаты</b>"
                stage_names = {1: "Этап 1", 2: "Этап 2", 3: "Этап 3", 4: "Этап 4", 5: "Этап 5"}
                total_label = "Итого"
                rank_label = "Место"
            elif lg == "en":
                header = "📊 <b>Daily Arena: results</b>"
                stage_names = {1: "Stage 1", 2: "Stage 2", 3: "Stage 3", 4: "Stage 4", 5: "Stage 5"}
                total_label = "Total"
                rank_label = "Place"
            else:
                header = "📊 <b>Kunlik arena: natijalar</b>"
                stage_names = {1: "1-bosqich", 2: "2-bosqich", 3: "3-bosqich", 4: "4-bosqich", 5: "5-bosqich"}
                total_label = "Jami"
                rank_label = "O‘rin"

            lines: list[str] = [header]
            total_correct = 0
            total_wrong = 0
            total_unanswered = 0
            for s in range(1, 6):
                st = stage_stats.get(s, {}).get(uid, {}) or {}
                c = int(st.get("correct") or 0)
                w = int(st.get("wrong") or 0)
                un = int(st.get("unanswered") or 0)
                total_correct += c
                total_wrong += w
                total_unanswered += un
                lines.append(f"• {stage_names[s]}: ✅{c} ❌{w} ⏭{un}")

            lines.append(
                f"\n<b>{total_label}:</b> ✅{total_correct}  ❌{total_wrong}  ⏭{total_unanswered}"
            )

            if uid in rank_map:
                rk = rank_map[uid]
                reward = rewards[rk - 1] if rk <= 3 else 0.0
                if reward > 0:
                    if lg == "ru":
                        lines.append(f"🏆 {rank_label}: <b>{rk}</b> (+{reward:.0f} D'point)")
                    elif lg == "en":
                        lines.append(f"🏆 {rank_label}: <b>{rk}</b> (+{reward:.0f} D'point)")
                    else:
                        lines.append(f"🏆 {rank_label}: <b>{rk}</b> (+{reward:.0f} D'point)")
                else:
                    if lg == "ru":
                        lines.append(f"🏆 {rank_label}: <b>{rk}</b>")
                    elif lg == "en":
                        lines.append(f"🏆 {rank_label}: <b>{rk}</b>")
                    else:
                        lines.append(f"🏆 {rank_label}: <b>{rk}</b>")
            elif eliminated_text:
                lines.append(eliminated_text.strip())

            msg = "\n".join(lines).strip()
            try:
                await bot.send_message(chat_id, msg, parse_mode="HTML")
            except Exception:
                pass

        # Send to everyone who joined.
        tasks = [_send_result_message(int(p["user_id"])) for p in participants]
        if tasks:
            await asyncio.gather(*tasks)

        update_scheduled_arena_run(
            run_id,
            status="finished",
            finished_at=datetime.utcnow().isoformat(),
            current_stage=5,
        )
    except Exception:
        logger.exception("run_daily_arena_coordinator failed run_id=%s", run_id)
        try:
            delete_arena_run_questions(run_id)
            update_scheduled_arena_run(run_id, status="finished", finished_at=datetime.utcnow().isoformat())
        except Exception:
            pass


async def run_boss_arena_coordinator(bot: Bot, run_id: int) -> None:
    run = get_scheduled_arena_run(run_id)
    if not run:
        return
    subject = str(run.get("subject") or "English")
    try:
        # Keep joins open for one minute after scheduled start.
        update_scheduled_arena_run(
            run_id,
            status="pending",
            started_at=datetime.utcnow().isoformat(),
        )
        await asyncio.sleep(BOSS_JOIN_WINDOW_SECONDS)

        update_scheduled_arena_run(
            run_id,
            status="running",
            started_at=datetime.utcnow().isoformat(),
        )
        parts = list_arena_run_participants(run_id)
        pool = fetch_arena_run_questions(run_id, 0, None)
        if len(pool) < BOSS_POOL_SIZE:
            for p in parts:
                add_dcoins(int(p["user_id"]), 3.0, subject, change_type="boss_entry_refund")
            delete_arena_run_questions(run_id)
            update_scheduled_arena_run(run_id, status="cancelled", finished_at=datetime.utcnow().isoformat())
            return

        tasks = []
        for p in parts:
            uid = int(p["user_id"])
            chat_id = int(p["chat_id"])
            qrows = random.sample(pool, BOSS_QUESTIONS_PER_USER)
            personalized = []
            for idx, q in enumerate(qrows, start=1):
                personalized.append(
                    {
                        "q_index": idx,
                        "payload_json": q.get("payload_json"),
                    }
                )
            if len(personalized) < BOSS_QUESTIONS_PER_USER:
                continue
            tasks.append(
                _play_mc_questions_for_user(
                    bot,
                    chat_id=chat_id,
                    user_id=uid,
                    run_id=run_id,
                    stage=0,
                    question_rows=personalized,
                )
            )
        if tasks:
            await asyncio.gather(*tasks)

        total, corr = boss_aggregate_stats(run_id)
        ratio = (corr / total) if total else 0.0
        gate_ok = ratio >= BOSS_GLOBAL_ACCURACY_GATE
        by_user = {
            int(r.get("user_id")): {
                "correct": int(r.get("correct") or 0),
                "wrong": int(r.get("wrong") or 0),
            }
            for r in list_arena_run_users_stage_answer_stats(run_id=run_id, stage=0)
        }

        for p in parts:
            uid = int(p["user_id"])
            u = get_user_by_id(uid) or {}
            lg = detect_lang_from_user(u)
            chat_id = int(p["chat_id"])
            st = by_user.get(uid, {"correct": 0, "wrong": 0})
            correct = int(st["correct"])
            wrong = int(st["wrong"])
            reward = float(correct)
            net = 0.0
            if gate_ok:
                if reward > 0:
                    add_dpoints(uid, reward, subject, change_type="boss_answer_correct_reward")
                net = reward
            else:
                add_dpoints(uid, -2.0, subject, change_type="boss_global_fail_penalty")
                net = -2.0
            try:
                await bot.send_message(
                    chat_id,
                    t(
                        lg,
                        "arena_boss_result",
                        ratio_pct=f"{ratio * 100:.1f}",
                        reward=f"{net:.1f}",
                        defeated="yes" if gate_ok else "no",
                    ),
                )
            except Exception:
                pass

        delete_arena_run_questions(run_id)
        update_scheduled_arena_run(
            run_id,
            status="finished",
            finished_at=datetime.utcnow().isoformat(),
        )
    except Exception:
        logger.exception("run_boss_arena_coordinator failed run_id=%s", run_id)
        try:
            delete_arena_run_questions(run_id)
            update_scheduled_arena_run(run_id, status="finished", finished_at=datetime.utcnow().isoformat())
        except Exception:
            pass
