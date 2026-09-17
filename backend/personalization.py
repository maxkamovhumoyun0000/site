"""Personal learning, study-room and parent-progress API.

This module deliberately owns only new, additive tables and routes.  It uses
the main application's authentication callback so existing role/session policy
remains the single source of truth.
"""

from __future__ import annotations

import json
import secrets
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_conn

router = APIRouter()
_runtime: dict[str, Callable[..., Any]] = {}
_schema_ready = False


def configure_runtime(**callbacks: Callable[..., Any]) -> None:
    _runtime.update(callbacks)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_parent_access_token() -> str:
    return secrets.token_urlsafe(32).replace("-", "").replace("_", "")


def new_study_room_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def mistake_next_review_at(now: datetime, correct_streak: int) -> datetime:
    days = (1, 3, 7, 14, 30)[min(max(0, int(correct_streak)), 4)]
    return now + timedelta(days=days)


def record_test_mistake(
    *,
    user_id: int,
    source_type: str,
    source_id: str,
    subject: str | None,
    topic_key: str | None,
    prompt: str,
    options: list[Any] | None = None,
    selected_answer: Any = None,
    correct_answer: Any = None,
    explanation: str | None = None,
) -> int | None:
    """Persist one wrong/skipped question from a first-party test flow.

    This is deliberately server-side: a client cannot forge another user's
    notebook and repeated delivery of the same request does not create a new
    card.  Correct notebook reviews are handled by ``answer_mistake`` below.
    """
    text = str(prompt or "").strip()
    key = str(source_id or "").strip()
    if int(user_id or 0) <= 0 or not text or not key:
        return None
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM mistake_notebook_items WHERE user_id=? AND source_type=? AND source_id=? LIMIT 1",
            (int(user_id), str(source_type or "test"), key),
        )
        existing = cur.fetchone()
        now = _now()
        values = (
            str(subject or ""), str(topic_key or ""), text,
            json.dumps(options or [], ensure_ascii=False),
            None if selected_answer is None else str(selected_answer),
            None if correct_answer is None else str(correct_answer),
            str(explanation or ""), now.isoformat(), now.isoformat(),
        )
        if existing:
            item_id = int(dict(existing).get("id") or 0)
            cur.execute(
                "UPDATE mistake_notebook_items SET subject=?,topic_key=?,prompt=?,options_json=?,"
                "selected_answer=?,correct_answer=?,explanation=?,updated_at=? WHERE id=?",
                (*values[:-2], values[-1], item_id),
            )
        else:
            cur.execute(
                "INSERT INTO mistake_notebook_items(user_id,source_type,source_id,subject,topic_key,prompt,"
                "options_json,selected_answer,correct_answer,explanation,review_at,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    int(user_id), str(source_type or "test"), key,
                    *values[:-1],
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
            item_id = int(cur.lastrowid or 0)
        conn.commit()
        return item_id or None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        statements = [
            """CREATE TABLE IF NOT EXISTS personalization_plans (
                id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, plan_date TEXT NOT NULL,
                summary TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, plan_date))""",
            """CREATE TABLE IF NOT EXISTS personalization_plan_tasks (
                id BIGSERIAL PRIMARY KEY, plan_id BIGINT NOT NULL, task_type TEXT NOT NULL,
                title TEXT NOT NULL, subject TEXT, topic_key TEXT, target_url TEXT,
                priority INTEGER DEFAULT 0, completed_at TIMESTAMP, metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS mistake_notebook_items (
                id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, source_type TEXT NOT NULL,
                source_id TEXT, subject TEXT, topic_key TEXT, prompt TEXT NOT NULL,
                options_json TEXT, selected_answer TEXT, correct_answer TEXT, explanation TEXT,
                correct_streak INTEGER DEFAULT 0, review_at TIMESTAMP, resolved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS learning_bookmarks (
                id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, content_type TEXT NOT NULL,
                content_id TEXT NOT NULL, position_value TEXT, title TEXT, note TEXT, tag TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS reminder_preferences (
                user_id BIGINT PRIMARY KEY, enabled INTEGER DEFAULT 1, quiet_start TEXT,
                quiet_end TEXT, settings_json TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS reminder_delivery_log (
                id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, event_key TEXT NOT NULL,
                channel TEXT NOT NULL, delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_key, channel))""",
            """CREATE TABLE IF NOT EXISTS parent_access_links (
                id BIGSERIAL PRIMARY KEY, student_id BIGINT NOT NULL UNIQUE, access_token TEXT NOT NULL UNIQUE,
                active INTEGER DEFAULT 1, created_by BIGINT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                rotated_at TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS study_rooms (
                id BIGSERIAL PRIMARY KEY, room_code TEXT NOT NULL UNIQUE, owner_id BIGINT NOT NULL,
                title TEXT NOT NULL, status TEXT DEFAULT 'open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS study_room_members (
                id BIGSERIAL PRIMARY KEY, room_id BIGINT NOT NULL, user_id BIGINT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, left_at TIMESTAMP,
                UNIQUE(room_id, user_id))""",
            """CREATE TABLE IF NOT EXISTS study_room_messages (
                id BIGSERIAL PRIMARY KEY, room_id BIGINT NOT NULL, sender_id BIGINT NOT NULL,
                body TEXT NOT NULL, attachments_json TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS study_room_materials (
                id BIGSERIAL PRIMARY KEY, room_id BIGINT NOT NULL, uploaded_by BIGINT NOT NULL,
                title TEXT NOT NULL, file_url TEXT, mime_type TEXT, extracted_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS study_room_reports (
                id BIGSERIAL PRIMARY KEY, room_id BIGINT NOT NULL, reporter_id BIGINT NOT NULL,
                message_id BIGINT, reason TEXT NOT NULL, status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS pomodoro_sessions (
                id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, mode TEXT NOT NULL,
                planned_seconds INTEGER NOT NULL, completed_seconds INTEGER DEFAULT 0,
                completed_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS pomodoro_preferences (
                user_id BIGINT PRIMARY KEY, settings_json TEXT NOT NULL DEFAULT '{}',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
            """CREATE TABLE IF NOT EXISTS badge_definitions (
                code TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT, asset_url TEXT,
                rule_key TEXT NOT NULL, active INTEGER DEFAULT 1)""",
            """CREATE TABLE IF NOT EXISTS student_badges (
                id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, badge_code TEXT NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, selected INTEGER DEFAULT 0,
                UNIQUE(user_id, badge_code))""",
            """CREATE TABLE IF NOT EXISTS certificates (
                id BIGSERIAL PRIMARY KEY, certificate_id TEXT NOT NULL UNIQUE, user_id BIGINT NOT NULL,
                course_key TEXT NOT NULL, course_title TEXT NOT NULL, issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                pdf_path TEXT, metadata_json TEXT)""",
            """CREATE TABLE IF NOT EXISTS user_sessions (
              id BIGSERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL,
              token_hash TEXT NOT NULL UNIQUE,
              device_name TEXT,
              platform TEXT,
              ip_address TEXT,
              last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS weekly_ai_analyses (
              id BIGSERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL,
              week_start TEXT NOT NULL,
              week_end TEXT NOT NULL,
              analysis_text TEXT,
              weak_topics_json TEXT,
              recommendations_json TEXT,
              test_stats_json TEXT,
              homework_stats_json TEXT,
              practice_questions_json TEXT,
              status TEXT DEFAULT 'pending',
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, week_start)
            )""",
        ]
        for sql in statements:
            try:
                cur.execute(sql)
            except Exception:
                # Local SQLite fallback has no BIGSERIAL; existing db adapter's
                # production target is PostgreSQL, so retry using INTEGER PK.
                cur.execute(sql.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT").replace("BIGINT", "INTEGER"))
        for sql in (
            "CREATE INDEX IF NOT EXISTS idx_mistakes_user_review ON mistake_notebook_items(user_id, review_at)",
            "CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON learning_bookmarks(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_study_room_members_room ON study_room_members(room_id, left_at)",
            "CREATE INDEX IF NOT EXISTS idx_study_room_messages_room ON study_room_messages(room_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_study_room_materials_room ON study_room_materials(room_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_pomodoro_user ON pomodoro_sessions(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions ON user_sessions(user_id, last_seen DESC)",
            "CREATE INDEX IF NOT EXISTS idx_weekly_analysis_user ON weekly_ai_analyses(user_id, week_start DESC)",
        ):
            try:
                cur.execute(sql)
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE study_rooms ADD COLUMN IF NOT EXISTS voice_room_id BIGINT")
        except Exception:
            try:
                cur.execute("ALTER TABLE study_rooms ADD COLUMN voice_room_id INTEGER")
            except Exception:
                pass
        badge_defaults = (
            ("first_lesson", "Birinchi dars", "Birinchi darsga qatnashdingiz", "lesson_count"),
            ("lesson_streak_3", "3 kunlik dars seriyasi", "3 kun ketma-ket dars", "lesson_streak_3"),
            ("lesson_streak_7", "7 kunlik dars seriyasi", "7 kun ketma-ket dars", "lesson_streak_7"),
            ("lesson_streak_30", "30 kunlik dars seriyasi", "30 kun ketma-ket dars", "lesson_streak_30"),
            ("perfect_attendance_month", "Namunali davomat", "Bir oy dars qoldirmang", "perfect_attendance_month"),
            ("first_homework", "Birinchi vazifa", "Birinchi uy vazifangizni topshiring", "homework_count"),
            ("homework_streak_3", "Homework seriyasi", "3 vazifani ketma-ket topshiring", "homework_streak_3"),
            ("homework_streak_10", "Homework ustasi", "10 vazifani ketma-ket topshiring", "homework_streak_10"),
            ("all_homework_month", "Vazifalar oyining g‘olibi", "Bir oy barcha vazifalarni topshiring", "all_homework_month"),
            ("early_submitter", "Erta topshiruvchi", "Vazifani deadline dan oldin topshiring", "early_submitter"),
            ("first_test", "Birinchi test", "Birinchi testni tugating", "test_count"),
            ("test_streak_7", "Test seriyasi", "7 kun test ishlang", "test_streak_7"),
            ("perfect_test", "Mukammal test", "100% natija oling", "perfect_test"),
            ("mistake_notebook_master", "Xatolar ustasi", "20 xatoni qayta to‘g‘ri yoping", "mistakes_resolved"),
            ("daily_plan_streak_7", "Reja seriyasi", "7 kunlik reja vazifalarini yoping", "daily_plan_streak_7"),
            ("daily_plan_streak_30", "Reja marafoni", "30 kunlik reja vazifalarini yoping", "daily_plan_streak_30"),
            ("word_collector", "So‘z to‘plovchi", "Yangi so‘zlarni mashq qiling", "word_collector"),
            ("vocabulary_master", "Lug‘at ustasi", "Lug‘at mashqlarini tugating", "vocabulary_master"),
            ("grammar_master", "Grammatika ustasi", "Grammatika mavzularini yoping", "grammar_master"),
            ("bookworm", "Kitobxon", "Kutubxona materiallarini tugating", "book_complete"),
            ("video_finisher", "Video ustasi", "Video darslarni tugating", "video_complete"),
            ("first_arena", "Arena jangchisi", "Arenada qatnashing", "arena_count"),
            ("arena_winner", "Arena g‘olibi", "Arenada g‘olib bo‘ling", "arena_win"),
            ("arena_streak_3", "Arena seriyasi", "3 arena g‘alabasi", "arena_streak_3"),
            ("duel_winner", "Duel g‘olibi", "Duelda g‘olib bo‘ling", "duel_win"),
            ("duel_streak_3", "Duel seriyasi", "3 duel g‘alabasi", "duel_streak_3"),
            ("study_room_host", "Study-room host", "Study-room yarating", "study_room_host"),
            ("study_room_partner", "Study-room sherigi", "Study-roomga qo‘shiling", "study_room_partner"),
            ("helpful_learner", "Yordamchi o‘quvchi", "Study-roomda foydali yordam bering", "helpful_learner"),
            ("first_certificate", "Birinchi sertifikat", "Kurs/modulni yakunlang", "certificate_count"),
            ("course_graduate", "Kurs bitiruvchisi", "Kursni tugating", "course_complete"),
            ("skill_builder", "Ko‘nikma quruvchisi", "Kuchli ko‘nikma yarating", "skill_builder"),
        )
        for code, title, description, rule_key in badge_defaults:
            try:
                cur.execute("INSERT INTO badge_definitions(code,title,description,rule_key,active) VALUES(?,?,?,?,1) ON CONFLICT(code) DO NOTHING", (code, title, description, rule_key))
            except Exception:
                try:
                    cur.execute("INSERT OR IGNORE INTO badge_definitions(code,title,description,rule_key,active) VALUES(?,?,?,?,1)", (code, title, description, rule_key))
                except Exception:
                    pass
        conn.commit()
        _schema_ready = True
    finally:
        conn.close()


def _user(authorization: str | None) -> dict[str, Any]:
    return _runtime["user_from_bearer"](authorization)


def _role(user: dict[str, Any]) -> str:
    return str(_runtime["role_for_user"](user))


def _require(user: dict[str, Any], roles: set[str]) -> None:
    if _role(user) not in roles:
        raise HTTPException(status_code=403, detail="Permission denied")


def _staff_can_access_student(user: dict[str, Any], student_id: int) -> bool:
    callback = _runtime.get("staff_can_access_student")
    if not callback:
        return False
    try:
        return bool(callback(user, int(student_id)))
    except Exception:
        return False


def _dicts(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in (rows or [])]


def _student_name(row: dict[str, Any]) -> str:
    return " ".join(part for part in (str(row.get("first_name") or "").strip(), str(row.get("last_name") or "").strip()) if part).strip() or str(row.get("login_id") or "Student")


def _sync_student_badges(cur: Any, user_id: int) -> None:
    """Award only facts that are already persisted; future badge assets/rules stay additive."""
    checks = (
        ("first_test", "SELECT COUNT(*) AS n FROM test_history WHERE user_id=?", 1),
        ("first_homework", "SELECT COUNT(*) AS n FROM web_homeworks WHERE student_id=?", 1),
        ("study_room_host", "SELECT COUNT(*) AS n FROM study_rooms WHERE owner_id=?", 1),
        ("first_certificate", "SELECT COUNT(*) AS n FROM certificates WHERE user_id=?", 1),
        ("perfect_test", "SELECT COUNT(*) AS n FROM test_history WHERE user_id=? AND correct_count > 0 AND wrong_count = 0 AND skipped_count = 0", 1),
        ("mistake_notebook_master", "SELECT COUNT(*) AS n FROM mistake_notebook_items WHERE user_id=? AND resolved_at IS NOT NULL", 20),
    )
    for code, sql, threshold in checks:
        try:
            cur.execute(sql, (user_id,)); count=int(dict(cur.fetchone() or {}).get("n") or 0)
            if count >= threshold:
                try: cur.execute("INSERT INTO student_badges(user_id,badge_code) VALUES(?,?) ON CONFLICT(user_id,badge_code) DO NOTHING", (user_id,code))
                except Exception: cur.execute("INSERT OR IGNORE INTO student_badges(user_id,badge_code) VALUES(?,?)", (user_id,code))
        except Exception:
            continue


def _get_or_create_parent_token(student_id: int, created_by: int | None = None) -> str:
    ensure_schema()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT access_token FROM parent_access_links WHERE student_id=? AND active=1", (student_id,))
        row = cur.fetchone()
        if row:
            return str(dict(row).get("access_token"))
        token = new_parent_access_token()
        cur.execute("INSERT INTO parent_access_links(student_id, access_token, active, created_by) VALUES(?,?,1,?)", (student_id, token, created_by))
        conn.commit()
        return token
    finally:
        conn.close()


def _build_plan(student_id: int) -> dict[str, Any]:
    """Deterministic, data-backed daily plan; it works even before AI enrichment."""
    ensure_schema()
    date_key = _now().date().isoformat()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM personalization_plans WHERE user_id=? AND plan_date=?", (student_id, date_key))
        existing = cur.fetchone()
        if existing:
            plan = dict(existing)
            cur.execute("SELECT * FROM personalization_plan_tasks WHERE plan_id=? ORDER BY priority DESC, id", (plan["id"],))
            plan["tasks"] = _dicts(cur.fetchall())
            return _plan_payload(plan)
        cur.execute("SELECT subject, topic_key, COUNT(*) AS mistakes FROM mistake_notebook_items WHERE user_id=? AND resolved_at IS NULL GROUP BY subject, topic_key ORDER BY mistakes DESC LIMIT 3", (student_id,))
        weak = _dicts(cur.fetchall())
        summary = "Bugungi reja: zaif mavzularni takrorlang va berilgan vazifalarni yakunlang."
        cur.execute("INSERT INTO personalization_plans(user_id, plan_date, summary) VALUES(?,?,?)", (student_id, date_key, summary))
        plan_id = int(cur.lastrowid or 0)
        if not plan_id:
            cur.execute("SELECT id FROM personalization_plans WHERE user_id=? AND plan_date=?", (student_id, date_key)); plan_id = int(dict(cur.fetchone())["id"])
        tasks: list[dict[str, Any]] = []
        for index, item in enumerate(weak):
            subject = str(item.get("subject") or "")
            topic = str(item.get("topic_key") or "")
            title = f"{subject or 'Fan'}: {topic or 'xatolar'} bo‘yicha mashq"
            cur.execute("INSERT INTO personalization_plan_tasks(plan_id, task_type, title, subject, topic_key, target_url, priority, metadata_json) VALUES(?,?,?,?,?,?,?,?)", (plan_id, "mistake_review", title, subject, topic, "/?role=student&section=mistake-notebook", 100-index, json.dumps({"mistakes": int(item.get("mistakes") or 0)})))
        cur.execute("SELECT COUNT(*) AS total FROM web_homeworks h LEFT JOIN web_homework_submissions s ON s.homework_id=h.id AND s.student_id=? WHERE h.student_id=? AND COALESCE(s.status,'') NOT IN ('done','accepted','reviewed','completed')", (student_id, student_id))
        pending = int(dict(cur.fetchone() or {}).get("total") or 0)
        if pending:
            cur.execute("INSERT INTO personalization_plan_tasks(plan_id, task_type, title, target_url, priority, metadata_json) VALUES(?,?,?,?,?,?)", (plan_id, "homework", f"{pending} ta uyga vazifani yakunlang", "/?role=student&section=homework", 90, json.dumps({"pending": pending})))
        conn.commit()
        cur.execute("SELECT * FROM personalization_plans WHERE id=?", (plan_id,)); plan = dict(cur.fetchone())
        cur.execute("SELECT * FROM personalization_plan_tasks WHERE plan_id=? ORDER BY priority DESC, id", (plan_id,)); plan["tasks"] = _dicts(cur.fetchall())
        return _plan_payload(plan)
    finally:
        conn.close()


async def _notify_plan_once(user: dict[str, Any], plan: dict[str, Any]) -> None:
    callback = _runtime.get("notify_plan")
    if not callback:
        return
    ensure_schema()
    event_key = f"personal_plan:{int(user['id'])}:{str(plan.get('date') or _now().date().isoformat())}"
    conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT 1 FROM reminder_delivery_log WHERE user_id=? AND event_key=? LIMIT 1", (int(user["id"]),event_key))
        if cur.fetchone(): return
        await callback(user, plan)
        for channel in ("in_app", "push", "telegram"):
            try: cur.execute("INSERT INTO reminder_delivery_log(user_id,event_key,channel) VALUES(?,?,?)", (int(user["id"]),event_key,channel))
            except Exception: pass
        conn.commit()
    finally: conn.close()


class MistakeCreate(BaseModel):
    source_type: str = Field(min_length=2, max_length=64)
    source_id: str | None = Field(default=None, max_length=120)
    subject: str | None = Field(default=None, max_length=80)
    topic_key: str | None = Field(default=None, max_length=160)
    prompt: str = Field(min_length=1, max_length=6000)
    options: list[str] = Field(default_factory=list, max_length=8)
    selected_answer: str | None = Field(default=None, max_length=2000)
    correct_answer: str | None = Field(default=None, max_length=2000)
    explanation: str | None = Field(default=None, max_length=4000)


class ExplanationRequest(BaseModel):
    question: str = Field(min_length=1, max_length=6000)
    selected_answer: str | None = Field(default=None, max_length=2000)
    correct_answer: str | None = Field(default=None, max_length=2000)
    subject: str | None = Field(default=None, max_length=80)
    topic_key: str | None = Field(default=None, max_length=160)
    test_type: str = Field(default="test", max_length=80)


class BookmarkRequest(BaseModel):
    content_type: str = Field(pattern="^(video|book)$")
    content_id: str = Field(min_length=1, max_length=120)
    position_value: str | None = Field(default=None, max_length=120)
    title: str | None = Field(default=None, max_length=240)
    note: str | None = Field(default=None, max_length=3000)
    tag: str | None = Field(default=None, max_length=80)
    position_seconds: int | None = Field(default=None, ge=0)
    page: int | None = Field(default=None, ge=1)
    # Older mobile builds call this field page_number; accepting it keeps
    # bookmark deep-links backward compatible.
    page_number: int | None = Field(default=None, ge=1)


def _plan_payload(plan: dict[str, Any]) -> dict[str, Any]:
    tasks = []
    for task in plan.get("tasks") or []:
        row = dict(task)
        row["kind"] = str(row.get("task_type") or "practice")
        row["route"] = str(row.get("target_url") or "practice")
        row["topic"] = row.get("topic_key")
        row["completed"] = bool(row.get("completed_at"))
        tasks.append(row)
    return {**plan, "date": str(plan.get("plan_date") or ""), "diamondvoy_message": str(plan.get("summary") or ""), "tasks": tasks}


class ReminderPreferencesRequest(BaseModel):
    enabled: bool = True
    quiet_start: str | None = Field(default=None, max_length=5)
    quiet_end: str | None = Field(default=None, max_length=5)
    settings: dict[str, Any] = Field(default_factory=dict)


class PomodoroRequest(BaseModel):
    mode: str = Field(pattern="^(work|short_break|long_break)$")
    planned_seconds: int = Field(ge=60, le=14400)
    completed_seconds: int = Field(default=0, ge=0, le=14400)
    completed: bool = False


class PomodoroSettingsRequest(BaseModel):
    work_seconds: int = Field(default=1500, ge=60, le=14400)
    short_break_seconds: int = Field(default=300, ge=60, le=3600)
    long_break_seconds: int = Field(default=900, ge=60, le=7200)
    cycles_before_long_break: int = Field(default=4, ge=1, le=12)
    auto_start_next: bool = False
    sound_enabled: bool = True
    vibration_enabled: bool = True


class StudyRoomCreate(BaseModel):
    title: str = Field(default="Study-room", min_length=1, max_length=120)


class StudyRoomMessage(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    attachments: list[dict[str, Any]] = Field(default_factory=list, max_length=5)


class StudyRoomMaterial(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    file_url: str | None = Field(default=None, max_length=2000)
    mime_type: str | None = Field(default=None, max_length=120)
    extracted_text: str | None = Field(default=None, max_length=30000)


class StudyRoomReport(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)
    message_id: int | None = Field(default=None, ge=1)


class MistakeReviewAnswer(BaseModel):
    selected_answer: str | None = Field(default=None, max_length=4000)


@router.get("/student/personal-plan")
async def student_personal_plan(authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"})
    plan=_build_plan(int(user["id"])); await _notify_plan_once(user,plan); return plan


@router.post("/student/personal-plan/refresh")
async def refresh_personal_plan(authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"})
    plan=_build_plan(int(user["id"])); await _notify_plan_once(user,plan); return plan


@router.post("/student/personal-plan/tasks/{task_id}")
async def complete_personal_plan_task(task_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema(); conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE personalization_plan_tasks SET completed_at=? WHERE id=? AND plan_id IN (SELECT id FROM personalization_plans WHERE user_id=?)", (_now().isoformat(), task_id, int(user["id"])))
        conn.commit()
        if cur.rowcount == 0: raise HTTPException(status_code=404, detail="Plan task not found")
        return {"completed": True}
    finally: conn.close()


@router.get("/student/mistake-notebook")
async def mistake_notebook(authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor(); uid=int(user["id"])
        cur.execute("SELECT COUNT(*) AS total FROM mistake_notebook_items WHERE user_id=? AND resolved_at IS NULL", (uid,)); total=int(dict(cur.fetchone() or {}).get("total") or 0)
        cur.execute("SELECT * FROM mistake_notebook_items WHERE user_id=? AND resolved_at IS NULL AND (review_at IS NULL OR review_at<=?) ORDER BY review_at NULLS FIRST, id LIMIT 50", (uid, _now().isoformat()))
        items=[]
        for row in _dicts(cur.fetchall()):
            row["question"] = row.get("prompt")
            row["topic"] = row.get("topic_key") or row.get("subject")
            row["due_at"] = row.get("review_at")
            items.append(row)
        cur.execute("SELECT source_type,COUNT(*) AS count FROM mistake_notebook_items WHERE user_id=? AND resolved_at IS NULL GROUP BY source_type", (uid,))
        sources = {str(row.get("source_type") or "test"): int(row.get("count") or 0) for row in _dicts(cur.fetchall())}
        return {"items": items, "due_count": len(items), "total_count": total, "sources": sources}
    finally: conn.close()


@router.post("/student/mistake-notebook/start")
async def start_mistake_notebook(authorization: str | None = Header(default=None)):
    """Returns due questions in the common lightweight test contract."""
    payload = await mistake_notebook(authorization)
    questions=[]
    for item in payload["items"]:
        try: options=json.loads(str(item.get("options_json") or "[]"))
        except Exception: options=[]
        questions.append({"id": item.get("id"), "question": item.get("prompt"), "options": options, "topic": item.get("topic_key"), "subject": item.get("subject")})
    return {"title": "Xatolar daftari", "questions": questions, "total": len(questions)}


@router.post("/student/mistake-notebook")
async def add_mistake(payload: MistakeCreate, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor(); now = _now()
        cur.execute("INSERT INTO mistake_notebook_items(user_id, source_type, source_id, subject, topic_key, prompt, options_json, selected_answer, correct_answer, explanation, review_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (int(user["id"]), payload.source_type, payload.source_id, payload.subject, payload.topic_key, payload.prompt, json.dumps(payload.options), payload.selected_answer, payload.correct_answer, payload.explanation, mistake_next_review_at(now, 0).isoformat()))
        conn.commit(); return {"id": int(cur.lastrowid or 0), "review_at": mistake_next_review_at(now, 0).isoformat()}
    finally: conn.close()


@router.post("/student/mistake-notebook/{item_id}/answer")
async def answer_mistake(item_id: int, payload: MistakeReviewAnswer, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor(); cur.execute("SELECT correct_streak,correct_answer FROM mistake_notebook_items WHERE id=? AND user_id=?", (item_id, int(user["id"])))
        row = cur.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Mistake item not found")
        item = dict(row)
        selected = str(payload.selected_answer or "").strip()
        correct_answer = str(item.get("correct_answer") or "").strip()
        correct = bool(selected and correct_answer and selected == correct_answer)
        streak = int(item.get("correct_streak") or 0) + 1 if correct else 0
        resolved = _now().isoformat() if streak >= 4 else None
        review = mistake_next_review_at(_now(), streak).isoformat()
        cur.execute("UPDATE mistake_notebook_items SET correct_streak=?, review_at=?, resolved_at=?, updated_at=? WHERE id=?", (streak, review, resolved, _now().isoformat(), item_id)); conn.commit()
        return {"correct": correct, "correct_answer": correct_answer, "correct_streak": streak, "review_at": review, "resolved": bool(resolved)}
    finally: conn.close()


@router.post("/student/ai-explanations")
async def ai_explanation(payload: ExplanationRequest, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"})
    # Stored explanation is intentionally deterministic if the AI provider is
    # unavailable: no test flow is blocked by an external model outage.
    prompt = ("Diamondvoy sifatida qisqa, sodda izoh ber. Savol: " + payload.question +
              " Tanlangan javob: " + str(payload.selected_answer or "—") +
              " To‘g‘ri javob: " + str(payload.correct_answer or "—") +
              ". Fan: " + str(payload.subject or "umumiy"))
    explain = _runtime.get("explain")
    text = None
    if explain:
        try: text = await explain(prompt, user)
        except Exception: text = None
    text = str(text or "To‘g‘ri javobga qarang va shu mavzuni yana bir marta mashq qiling.").strip()
    return {"explanation": text, "test_type": payload.test_type}


def _bookmark_routes(prefix: str, roles: set[str]):
    @router.get(f"/{prefix}/bookmarks")
    async def list_bookmarks(authorization: str | None = Header(default=None)):
        user = _user(authorization); _require(user, roles); ensure_schema(); conn = get_conn()
        try:
            cur=conn.cursor(); cur.execute("SELECT * FROM learning_bookmarks WHERE user_id=? ORDER BY created_at DESC", (int(user["id"]),)); items=[]
            for row in _dicts(cur.fetchall()):
                position=str(row.get("position_value") or "")
                if position.startswith("seconds:"): row["position_seconds"]=int(position.split(":",1)[1] or 0)
                if position.startswith("page:"): row["page"]=int(position.split(":",1)[1] or 0)
                items.append(row)
            return {"items": items}
        finally: conn.close()
    @router.post(f"/{prefix}/bookmarks")
    async def create_bookmark(payload: BookmarkRequest, authorization: str | None = Header(default=None)):
        user = _user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            position = payload.position_value
            if payload.position_seconds is not None: position = f"seconds:{payload.position_seconds}"
            elif payload.page is not None or payload.page_number is not None: position = f"page:{payload.page if payload.page is not None else payload.page_number}"
            cur=conn.cursor(); cur.execute("INSERT INTO learning_bookmarks(user_id, content_type, content_id, position_value, title, note, tag) VALUES(?,?,?,?,?,?,?)", (int(user["id"]), payload.content_type, payload.content_id, position, payload.title, payload.note, payload.tag)); conn.commit(); return {"id": int(cur.lastrowid or 0)}
        finally: conn.close()
    @router.delete(f"/{prefix}/bookmarks/{{bookmark_id}}")
    async def delete_bookmark(bookmark_id: int, authorization: str | None = Header(default=None)):
        user = _user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor(); cur.execute("DELETE FROM learning_bookmarks WHERE id=? AND user_id=?", (bookmark_id, int(user["id"]))); conn.commit(); return {"deleted": cur.rowcount > 0}
        finally: conn.close()


def _reminder_routes(prefix: str, roles: set[str]):
    @router.get(f"/{prefix}/reminder-preferences")
    async def get_preferences(authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor(); cur.execute("SELECT * FROM reminder_preferences WHERE user_id=?", (int(user["id"]),)); row=cur.fetchone(); return dict(row) if row else {"enabled": True, "settings_json": "{}"}
        finally: conn.close()
    @router.put(f"/{prefix}/reminder-preferences")
    async def put_preferences(payload: ReminderPreferencesRequest, authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor(); cur.execute("DELETE FROM reminder_preferences WHERE user_id=?", (int(user["id"]),)); cur.execute("INSERT INTO reminder_preferences(user_id, enabled, quiet_start, quiet_end, settings_json, updated_at) VALUES(?,?,?,?,?,?)", (int(user["id"]), int(payload.enabled), payload.quiet_start, payload.quiet_end, json.dumps(payload.settings), _now().isoformat())); conn.commit(); return {"success": True}
        finally: conn.close()


def _pomodoro_routes(prefix: str, roles: set[str]):
    @router.get(f"/{prefix}/pomodoro/settings")
    async def get_pomodoro_settings(authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        defaults = PomodoroSettingsRequest().model_dump()
        try:
            cur=conn.cursor(); cur.execute("SELECT settings_json FROM pomodoro_preferences WHERE user_id=?", (int(user["id"]),)); row=cur.fetchone()
            if not row: return defaults
            try: saved=json.loads(str(dict(row).get("settings_json") or "{}"))
            except Exception: saved={}
            return {**defaults, **(saved if isinstance(saved, dict) else {})}
        finally: conn.close()

    @router.put(f"/{prefix}/pomodoro/settings")
    async def put_pomodoro_settings(payload: PomodoroSettingsRequest, authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor(); data=json.dumps(payload.model_dump())
            try:
                cur.execute("INSERT INTO pomodoro_preferences(user_id,settings_json,updated_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET settings_json=excluded.settings_json,updated_at=excluded.updated_at", (int(user["id"]),data,_now().isoformat()))
            except Exception:
                cur.execute("DELETE FROM pomodoro_preferences WHERE user_id=?", (int(user["id"]),)); cur.execute("INSERT INTO pomodoro_preferences(user_id,settings_json,updated_at) VALUES(?,?,?)", (int(user["id"]),data,_now().isoformat()))
            conn.commit(); return payload.model_dump()
        finally: conn.close()

    @router.get(f"/{prefix}/pomodoro/summary")
    async def pomodoro_summary(authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor(); cur.execute("SELECT COALESCE(SUM(completed_seconds),0) AS total, COUNT(*) AS sessions FROM pomodoro_sessions WHERE user_id=? AND created_at>=?", (int(user["id"]), (_now()-timedelta(days=7)).isoformat())); row=dict(cur.fetchone() or {}); return {"week_seconds": int(row.get("total") or 0), "sessions": int(row.get("sessions") or 0)}
        finally: conn.close()
    @router.post(f"/{prefix}/pomodoro/sessions")
    async def save_pomodoro(payload: PomodoroRequest, authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor(); cur.execute("INSERT INTO pomodoro_sessions(user_id, mode, planned_seconds, completed_seconds, completed_at) VALUES(?,?,?,?,?)", (int(user["id"]), payload.mode, payload.planned_seconds, payload.completed_seconds, _now().isoformat() if payload.completed else None)); conn.commit(); return {"id": int(cur.lastrowid or 0)}
        finally: conn.close()


_bookmark_routes("student", {"student"}); _bookmark_routes("staff", {"teacher", "support"})
_reminder_routes("student", {"student"}); _reminder_routes("staff", {"teacher", "support"})
_pomodoro_routes("student", {"student"}); _pomodoro_routes("staff", {"teacher", "support"})


@router.post("/student/study-rooms")
async def create_study_room(payload: StudyRoomCreate, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, {"student"}); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); code=new_study_room_code()
        for _ in range(8):
            cur.execute("SELECT 1 FROM study_rooms WHERE room_code=? AND status='open'", (code,))
            if not cur.fetchone(): break
            code=new_study_room_code()
        else: raise HTTPException(status_code=503, detail="Could not allocate room code")
        cur.execute("INSERT INTO study_rooms(room_code, owner_id, title) VALUES(?,?,?)", (code, int(user["id"]), payload.title)); room_id=int(cur.lastrowid or 0)
        if not room_id: cur.execute("SELECT id FROM study_rooms WHERE room_code=?", (code,)); room_id=int(dict(cur.fetchone())["id"])
        cur.execute("INSERT INTO study_room_members(room_id,user_id) VALUES(?,?)", (room_id,int(user["id"]))); conn.commit(); return {"id": room_id, "room_code": code, "title": payload.title, "max_members": 4}
    finally: conn.close()


@router.post("/student/study-rooms/join/{room_code}")
async def join_study_room(room_code: str, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, {"student"}); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT * FROM study_rooms WHERE room_code=? AND status='open'", (room_code,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Study-room not found")
        room=dict(row); cur.execute("SELECT COUNT(*) AS total FROM study_room_members WHERE room_id=? AND left_at IS NULL", (int(room["id"]),)); count=int(dict(cur.fetchone())["total"])
        cur.execute("SELECT 1 FROM study_room_members WHERE room_id=? AND user_id=? AND left_at IS NULL", (int(room["id"]),int(user["id"])))
        already=bool(cur.fetchone())
        if not already and count >= 4: raise HTTPException(status_code=409, detail="Study-room is full")
        if not already:
            # The unique room/user row is kept for audit; a former member can
            # safely rejoin with a currently valid code.
            cur.execute("UPDATE study_room_members SET left_at=NULL,joined_at=? WHERE room_id=? AND user_id=?", (_now().isoformat(), int(room["id"]), int(user["id"])))
            if cur.rowcount == 0:
                cur.execute("INSERT INTO study_room_members(room_id,user_id) VALUES(?,?)", (int(room["id"]),int(user["id"])))
            conn.commit()
        return {"room": room, "member_count": count if already else count+1, "max_members": 4}
    finally: conn.close()


def _room_for_member(room_id: int, user_id: int) -> dict[str, Any]:
    conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT r.* FROM study_rooms r JOIN study_room_members m ON m.room_id=r.id WHERE r.id=? AND m.user_id=? AND m.left_at IS NULL", (room_id,user_id)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=403, detail="Study-room membership required")
        return dict(row)
    finally: conn.close()


@router.get("/student/study-rooms/{room_id}/messages")
async def study_room_messages(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT m.*, u.first_name, u.last_name, u.login_id FROM study_room_messages m LEFT JOIN users u ON u.id=m.sender_id WHERE m.room_id=? ORDER BY m.id ASC LIMIT 250", (room_id,))
        items=[]
        for row in _dicts(cur.fetchall()):
            try: row["attachments"]=json.loads(str(row.get("attachments_json") or "[]"))
            except Exception: row["attachments"]=[]
            items.append(row)
        return {"items":items}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/messages")
async def post_study_room_message(room_id: int, payload: StudyRoomMessage, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("INSERT INTO study_room_messages(room_id,sender_id,body,attachments_json) VALUES(?,?,?,?)", (room_id,int(user["id"]),payload.body,json.dumps(payload.attachments))); conn.commit(); return {"id":int(cur.lastrowid or 0)}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/close")
async def close_study_room(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("UPDATE study_rooms SET status='closed',closed_at=? WHERE id=? AND owner_id=?", (_now().isoformat(),room_id,int(user["id"]))); conn.commit()
        if cur.rowcount==0: raise HTTPException(status_code=403, detail="Only room owner can close this room")
        return {"closed":True}
    finally: conn.close()


def _room_owner(room_id: int, user_id: int) -> dict[str, Any]:
    room = _room_for_member(room_id, user_id)
    if int(room.get("owner_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="Only room owner can manage this room")
    return room


@router.get("/student/study-rooms/{room_id}")
async def study_room_detail(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); room=_room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor()
        cur.execute("SELECT m.user_id,m.joined_at,u.first_name,u.last_name,u.login_id FROM study_room_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.left_at IS NULL ORDER BY m.joined_at", (room_id,))
        members=_dicts(cur.fetchall())
        cur.execute("SELECT * FROM study_room_materials WHERE room_id=? ORDER BY id DESC LIMIT 50", (room_id,))
        return {"room":room,"members":members,"materials":_dicts(cur.fetchall()),"max_members":4}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/regenerate-code")
async def regenerate_study_room_code(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); _room_owner(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); code=new_study_room_code()
        for _ in range(8):
            cur.execute("SELECT 1 FROM study_rooms WHERE room_code=? AND id<>?", (code,room_id))
            if not cur.fetchone(): break
            code=new_study_room_code()
        else: raise HTTPException(status_code=503, detail="Could not allocate room code")
        cur.execute("UPDATE study_rooms SET room_code=? WHERE id=? AND owner_id=?", (code,room_id,int(user["id"]))); conn.commit()
        return {"room_code":code}
    finally: conn.close()


@router.delete("/student/study-rooms/{room_id}/members/{member_id}")
async def remove_study_room_member(room_id: int, member_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); _room_owner(room_id,int(user["id"])); conn=get_conn()
    try:
        if int(member_id) == int(user["id"]):
            raise HTTPException(status_code=422, detail="Owner should close the room instead")
        cur=conn.cursor(); cur.execute("UPDATE study_room_members SET left_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL", (_now().isoformat(),room_id,member_id)); conn.commit()
        return {"removed":cur.rowcount > 0}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/materials")
async def add_study_room_material(room_id: int, payload: StudyRoomMaterial, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("INSERT INTO study_room_materials(room_id,uploaded_by,title,file_url,mime_type,extracted_text) VALUES(?,?,?,?,?,?)", (room_id,int(user["id"]),payload.title,payload.file_url,payload.mime_type,payload.extracted_text)); conn.commit()
        return {"id":int(cur.lastrowid or 0)}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/voice-room")
async def create_study_room_voice(room_id: int, authorization: str | None = Header(default=None)):
    """Create a private WebRTC room; the established websocket validates
    study-room membership before admitting a peer."""
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); room=_room_owner(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); existing=int(room.get("voice_room_id") or 0)
        if existing:
            return {"room_id":str(existing),"reused":True}
        title=f"Study-room · {str(room.get('title') or room_id)[:90]}"
        subject=f"_study_room_{room_id}"
        try:
            cur.execute("INSERT INTO web_voicerooms(name,subject,owner_id,tags) VALUES(?,?,?,?) RETURNING id", (title,subject,int(user["id"]),"study-room,private"))
            voice_id=int(dict(cur.fetchone()).get("id") or 0)
        except Exception:
            cur.execute("INSERT INTO web_voicerooms(name,subject,owner_id) VALUES(?,?,?)", (title,subject,int(user["id"])))
            voice_id=int(cur.lastrowid or 0)
        if not voice_id:
            raise HTTPException(status_code=500, detail="Voice room could not be created")
        cur.execute("UPDATE study_rooms SET voice_room_id=? WHERE id=?", (voice_id,room_id)); conn.commit()
        return {"room_id":str(voice_id),"reused":False}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/reports")
async def report_study_room(room_id: int, payload: StudyRoomReport, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor()
        if payload.message_id is not None:
            cur.execute("SELECT 1 FROM study_room_messages WHERE id=? AND room_id=?", (payload.message_id,room_id))
            if not cur.fetchone(): raise HTTPException(status_code=404, detail="Message not found in this room")
        cur.execute("INSERT INTO study_room_reports(room_id,reporter_id,message_id,reason) VALUES(?,?,?,?)", (room_id,int(user["id"]),payload.message_id,payload.reason)); conn.commit()
        return {"reported":True}
    finally: conn.close()


@router.get("/parent/progress/{access_token}")
async def parent_progress(access_token: str):
    ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT u.id,u.first_name,u.last_name,u.login_id,u.subject FROM parent_access_links p JOIN users u ON u.id=p.student_id WHERE p.access_token=? AND p.active=1",(access_token,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Parent progress link is invalid")
        student=dict(row); sid=int(student["id"])
        cur.execute("SELECT date,status,group_id FROM attendance WHERE user_id=? ORDER BY date DESC LIMIT 40",(sid,)); attendance=_dicts(cur.fetchall())
        cur.execute("SELECT h.id,h.title,h.status,h.due_at,s.review_note,COALESCE(s.updated_at,h.updated_at) AS updated_at,COALESCE(s.status,'pending') AS submission_status FROM web_homeworks h LEFT JOIN web_homework_submissions s ON s.homework_id=h.id AND s.student_id=? WHERE h.student_id=? ORDER BY COALESCE(s.updated_at,h.updated_at) DESC LIMIT 40",(sid,sid)); homework=_dicts(cur.fetchall())
        cur.execute("SELECT test_type,topic_id,correct_count,wrong_count,skipped_count,created_at FROM test_history WHERE user_id=? ORDER BY created_at DESC LIMIT 40",(sid,)); tests=_dicts(cur.fetchall())
        cur.execute("SELECT subject,topic_key,COUNT(*) AS mistakes FROM mistake_notebook_items WHERE user_id=? AND resolved_at IS NULL GROUP BY subject,topic_key ORDER BY mistakes DESC LIMIT 5",(sid,)); weak=_dicts(cur.fetchall())
        cur.execute("SELECT course_title,certificate_id,issued_at FROM certificates WHERE user_id=? ORDER BY issued_at DESC",(sid,)); certificates=_dicts(cur.fetchall())
        plan=_build_plan(sid)
        return {"student":{"name":_student_name(student),"login_id":student.get("login_id"),"subject":student.get("subject")},"attendance":attendance,"homework":homework,"tests":tests,"weak_topics":weak,"certificates":certificates,"plan":plan}
    finally: conn.close()


@router.post("/student/parent-access/regenerate")
async def regenerate_parent_access(authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); conn=get_conn()
    try:
        token=new_parent_access_token(); cur=conn.cursor(); cur.execute("UPDATE parent_access_links SET active=0,rotated_at=? WHERE student_id=? AND active=1",(_now().isoformat(),int(user["id"]))); cur.execute("INSERT INTO parent_access_links(student_id,access_token,active,created_by) VALUES(?,?,1,?)",(int(user["id"]),token,int(user["id"]))); conn.commit(); return {"access_token":token}
    finally: conn.close()


@router.get("/staff/students/{student_id}/parent-access")
async def staff_parent_access(student_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"teacher","support","admin"})
    if not _staff_can_access_student(user, student_id):
        raise HTTPException(status_code=403, detail="Student is outside your access scope")
    return {"access_token":_get_or_create_parent_token(student_id, int(user["id"]))}


@router.post("/staff/students/{student_id}/parent-access/regenerate")
async def staff_regenerate_parent_access(student_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"teacher","support","admin"}); ensure_schema()
    if not _staff_can_access_student(user, student_id):
        raise HTTPException(status_code=403, detail="Student is outside your access scope")
    conn=get_conn()
    try:
        token=new_parent_access_token(); cur=conn.cursor()
        cur.execute("UPDATE parent_access_links SET active=0,rotated_at=? WHERE student_id=? AND active=1",(_now().isoformat(),student_id))
        cur.execute("INSERT INTO parent_access_links(student_id,access_token,active,created_by) VALUES(?,?,1,?)",(student_id,token,int(user["id"]))); conn.commit()
        return {"access_token":token}
    finally: conn.close()


@router.get("/student/portfolio")
async def portfolio(authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); uid=int(user["id"]); _sync_student_badges(cur, uid); conn.commit(); cur.execute("SELECT *, course_title AS title, ('/certificates/' || certificate_id || '/pdf') AS pdf_url FROM certificates WHERE user_id=? ORDER BY issued_at DESC",(uid,)); certificates=_dicts(cur.fetchall()); cur.execute("SELECT d.code AS id,d.code,d.title,d.description,d.asset_url,CASE WHEN b.user_id IS NULL THEN 0 ELSE 1 END AS unlocked,COALESCE(b.selected,0) AS selected FROM badge_definitions d LEFT JOIN student_badges b ON b.badge_code=d.code AND b.user_id=? WHERE d.active=1 ORDER BY d.code",(uid,)); badges=_dicts(cur.fetchall()); selected=next((x for x in badges if int(x.get("selected") or 0)==1),None); return {"certificates":certificates,"badges":badges,"selected_badge":selected,"selected_badge_id":selected.get("id") if selected else None}
    finally: conn.close()


class BadgeSelectRequest(BaseModel):
    badge_id: str = Field(min_length=1, max_length=120)


@router.put("/student/portfolio/badge")
async def select_portfolio_badge(payload: BadgeSelectRequest, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); uid=int(user["id"]); cur.execute("SELECT 1 FROM student_badges WHERE user_id=? AND badge_code=?",(uid,payload.badge_id))
        if not cur.fetchone(): raise HTTPException(status_code=403, detail="Badge is not unlocked")
        cur.execute("UPDATE student_badges SET selected=0 WHERE user_id=?",(uid,)); cur.execute("UPDATE student_badges SET selected=1 WHERE user_id=? AND badge_code=?",(uid,payload.badge_id)); conn.commit(); return {"selected_badge_id":payload.badge_id}
    finally: conn.close()


@router.get("/teacher/student-insights")
async def teacher_student_insights(authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"teacher","support"}); ensure_schema(); conn=get_conn()
    try:
        visible = _runtime.get("staff_visible_student_ids", lambda _u: set())(user)
        ids = sorted({int(item) for item in (visible or set()) if int(item or 0) > 0})
        if not ids:
            return {"items":[]}
        placeholders=",".join("?" for _ in ids)
        cur=conn.cursor(); cur.execute(f"SELECT m.user_id,u.first_name,u.last_name,u.login_id,m.subject,m.topic_key,COUNT(*) AS mistakes FROM mistake_notebook_items m JOIN users u ON u.id=m.user_id WHERE m.resolved_at IS NULL AND m.user_id IN ({placeholders}) GROUP BY m.user_id,u.first_name,u.last_name,u.login_id,m.subject,m.topic_key ORDER BY mistakes DESC LIMIT 100", ids); rows=_dicts(cur.fetchall()); return {"items":rows}
    finally: conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# WEEKLY AI ANALYSIS — Personal Study Plan
# ═══════════════════════════════════════════════════════════════════════════════

def _current_week_range() -> tuple[str, str]:
    """Return (monday_iso, sunday_iso) for the current week."""
    today = _now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _collect_week_stats(cur: Any, user_id: int, week_start: str, week_end: str) -> dict[str, Any]:
    """Gather test + homework + mistake stats for the given week."""
    # Test stats
    cur.execute(
        "SELECT test_type, topic_id, correct_count, wrong_count, skipped_count, created_at "
        "FROM test_history WHERE user_id=? AND DATE(created_at) >= ? AND DATE(created_at) <= ? "
        "ORDER BY created_at DESC",
        (user_id, week_start, week_end),
    )
    tests = _dicts(cur.fetchall())
    total_correct = sum(int(t.get("correct_count") or 0) for t in tests)
    total_wrong = sum(int(t.get("wrong_count") or 0) for t in tests)
    total_skipped = sum(int(t.get("skipped_count") or 0) for t in tests)
    total_questions = total_correct + total_wrong + total_skipped
    accuracy = round((total_correct / total_questions * 100), 1) if total_questions > 0 else 0

    # Topic breakdown (which topics have most errors)
    topic_errors: dict[str, int] = {}
    for t in tests:
        topic = str(t.get("topic_id") or "general")
        wrong = int(t.get("wrong_count") or 0)
        if wrong > 0:
            topic_errors[topic] = topic_errors.get(topic, 0) + wrong
    weak_by_tests = sorted(topic_errors.items(), key=lambda x: x[1], reverse=True)[:5]

    # Mistake notebook stats (unresolved)
    cur.execute(
        "SELECT subject, topic_key, COUNT(*) AS cnt "
        "FROM mistake_notebook_items WHERE user_id=? AND resolved_at IS NULL "
        "GROUP BY subject, topic_key ORDER BY cnt DESC LIMIT 5",
        (user_id,),
    )
    weak_by_mistakes = _dicts(cur.fetchall())
    cur.execute(
        "SELECT source_type,COUNT(*) AS count FROM mistake_notebook_items "
        "WHERE user_id=? AND DATE(created_at)>=? AND DATE(created_at)<=? "
        "GROUP BY source_type ORDER BY count DESC",
        (user_id, week_start, week_end),
    )
    mistake_sources = _dicts(cur.fetchall())

    # Homework stats
    cur.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN COALESCE(s.status,'') IN ('done','accepted','reviewed','completed') THEN 1 ELSE 0 END) AS completed "
        "FROM web_homeworks h "
        "LEFT JOIN web_homework_submissions s ON s.homework_id=h.id AND s.student_id=? "
        "WHERE h.student_id=? AND DATE(COALESCE(h.created_at, h.due_at)) >= ? AND DATE(COALESCE(h.created_at, h.due_at)) <= ?",
        (user_id, user_id, week_start, week_end),
    )
    hw_row = dict(cur.fetchone() or {})
    hw_total = int(hw_row.get("total") or 0)
    hw_completed = int(hw_row.get("completed") or 0)

    return {
        "tests": tests[:20],
        "test_count": len(tests),
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_skipped": total_skipped,
        "accuracy_pct": accuracy,
        "weak_topics_by_tests": [{"topic": t, "errors": e} for t, e in weak_by_tests],
        "weak_topics_by_mistakes": weak_by_mistakes,
        "mistake_sources": mistake_sources,
        "homework_total": hw_total,
        "homework_completed": hw_completed,
        "homework_completion_pct": round(hw_completed / hw_total * 100, 1) if hw_total > 0 else 0,
    }


async def _generate_ai_analysis(stats: dict[str, Any], user_name: str) -> dict[str, Any]:
    """Call AI to produce weekly analysis, explanations, recommendations and practice questions."""
    import aiohttp

    weak_topics = []
    for item in stats.get("weak_topics_by_tests", []):
        weak_topics.append(f"- {item['topic']} ({item['errors']} ta xato)")
    for item in stats.get("weak_topics_by_mistakes", []):
        subj = str(item.get("subject") or "")
        topic = str(item.get("topic_key") or "")
        cnt = int(item.get("cnt") or 0)
        weak_topics.append(f"- {subj} / {topic} ({cnt} ta hal qilinmagan xato)")

    weak_str = "\n".join(weak_topics) if weak_topics else "Hozircha zaif mavzular aniqlanmadi."
    source_str = ", ".join(f"{item.get('source_type')}: {item.get('count')}" for item in stats.get("mistake_sources", [])) or "Hozircha xato qayd etilmagan."

    prompt = f"""Sen Diamond Education platformasida o'quvchilarga yordam beruvchi AI tutorsan (Diamondvoy).
O'quvchi: {user_name}

Bu haftadagi statistika:
- Testlar soni: {stats.get('test_count', 0)}
- To'g'ri: {stats.get('total_correct', 0)}, Noto'g'ri: {stats.get('total_wrong', 0)}, O'tkazilgan: {stats.get('total_skipped', 0)}
- Umumiy aniqlik: {stats.get('accuracy_pct', 0)}%
- Uy vazifalari: {stats.get('homework_completed', 0)}/{stats.get('homework_total', 0)} bajarildi ({stats.get('homework_completion_pct', 0)}%)

Zaif mavzular:
{weak_str}

Xatolar kelgan test turlari: {source_str}

Quyidagilarni JSON formatda yoz:
{{
  "analysis": "O'quvchining bu haftadagi holati haqida batafsil tahlil (3-5 jumlada, samimiy va rag'batlantiruvchi tonda, zaif tomonlarni ham aniq ko'rsat)",
  "weak_topics": [
    {{"topic": "mavzu nomi", "level": "weak/medium", "explanation": "bu mavzuda nega qiynalayotgani haqida tushuntirish", "rules": ["1-qoida yoki tushuntirish", "2-qoida yoki tushuntirish"]}}
  ],
  "recommendations": [
    "1-tavsiya: aniq va amaliy qadam",
    "2-tavsiya",
    "3-tavsiya"
  ],
  "practice_questions": [
    {{"question": "savol matni", "options": ["A) variant", "B) variant", "C) variant", "D) variant"], "correct": "A) variant", "topic": "mavzu", "difficulty": "easy", "explanation": "to'g'ri javob tushuntirmasi"}}
  ],
  "encouragement": "rag'batlantiruvchi xabar"
}}

practice_questions da eng kamida 5 ta savol bo'lsin, zaif mavzularga oid, OSON darajada.
Har bir zaif mavzu uchun kamida 1 ta savol bo'lsin.
Faqat JSON qaytar, boshqa hech narsa yozma."""

    try:
        from ai_generator import _xai_generate_text
        async with aiohttp.ClientSession() as session:
            raw = await _xai_generate_text(prompt, session=session, temperature=0.5)
        # Parse JSON from response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3]
        if not raw.startswith("{"):
            start, end = raw.find("{"), raw.rfind("}")
            raw = raw[start : end + 1] if start >= 0 and end > start else raw
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("AI response is not an object")
        result["weak_topics"] = result.get("weak_topics") if isinstance(result.get("weak_topics"), list) else []
        result["recommendations"] = result.get("recommendations") if isinstance(result.get("recommendations"), list) else []
        result["practice_questions"] = result.get("practice_questions") if isinstance(result.get("practice_questions"), list) else []
        return result
    except Exception:
        return {
            "analysis": "Bu haftadagi ma’lumotlar tayyor. Diamondvoy tahlili birozdan so‘ng yangilanadi.",
            "weak_topics": [{"topic": t.get("topic", ""), "level": "weak", "explanation": "", "rules": []} for t in stats.get("weak_topics_by_tests", [])],
            "recommendations": ["Zaif mavzulardagi testlarni qayta ishlang.", "Xatolar daftarini muntazam ko'rib chiqing.", "Uyga vazifalarni o'z vaqtida topshiring."],
            "practice_questions": [],
            "encouragement": "Davom eting, har qanday natija — bu rivojlanish!",
        }


async def _finish_weekly_analysis(
    *, user_id: int, user_name: str, week_start: str, stats: dict[str, Any]
) -> None:
    """Run the slow AI call outside the request and persist one immutable weekly result."""
    try:
        result = await _generate_ai_analysis(stats, user_name)
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE weekly_ai_analyses SET analysis_text=?, weak_topics_json=?, recommendations_json=?, "
                "practice_questions_json=?, status='done', updated_at=? WHERE user_id=? AND week_start=?",
                (
                    str(result.get("analysis", "")),
                    json.dumps(result.get("weak_topics", []), ensure_ascii=False),
                    json.dumps(result.get("recommendations", []), ensure_ascii=False),
                    json.dumps(result.get("practice_questions", []), ensure_ascii=False),
                    _now().isoformat(), user_id, week_start,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Never leave the learner in an endless "thinking" state.
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE weekly_ai_analyses SET status='failed', updated_at=? WHERE user_id=? AND week_start=?",
                (_now().isoformat(), user_id, week_start),
            )
            conn.commit()
        finally:
            conn.close()


def _weekly_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "exists": True,
        "week_start": row["week_start"],
        "week_end": row["week_end"],
        "status": row.get("status", "done"),
        "analysis": row.get("analysis_text", ""),
        "weak_topics": json.loads(row.get("weak_topics_json") or "[]"),
        "recommendations": json.loads(row.get("recommendations_json") or "[]"),
        "test_stats": json.loads(row.get("test_stats_json") or "{}"),
        "homework_stats": json.loads(row.get("homework_stats_json") or "{}"),
        "practice_questions": json.loads(row.get("practice_questions_json") or "[]"),
        "created_at": row.get("created_at"),
    }


@router.get("/student/personal-plan/weekly-analysis")
async def get_weekly_analysis(authorization: str | None = Header(default=None)):
    """Get the current week's AI analysis (or latest available)."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"]); week_start, week_end = _current_week_range()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM weekly_ai_analyses WHERE user_id=? AND week_start=?",
            (uid, week_start),
        )
        row = cur.fetchone()
        if row:
            return _weekly_payload(dict(row))
        # Collect live stats so the frontend can show partial data
        stats = _collect_week_stats(cur, uid, week_start, week_end)
        return {
            "exists": False,
            "week_start": week_start,
            "week_end": week_end,
            "status": "not_generated",
            "analysis": "",
            "weak_topics": [],
            "recommendations": [],
            "test_stats": stats,
            "homework_stats": {
                "total": stats["homework_total"],
                "completed": stats["homework_completed"],
                "completion_pct": stats["homework_completion_pct"],
            },
            "practice_questions": [],
            "created_at": None,
        }
    finally:
        conn.close()


@router.post("/student/personal-plan/weekly-analysis/generate")
async def generate_weekly_analysis(authorization: str | None = Header(default=None)):
    """Queue a weekly Diamondvoy analysis and return immediately for UI polling."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"]); week_start, week_end = _current_week_range()
    user_name = _student_name(user)
    conn = get_conn()
    try:
        cur = conn.cursor()
        stats = _collect_week_stats(cur, uid, week_start, week_end)
        cur.execute("SELECT status FROM weekly_ai_analyses WHERE user_id=? AND week_start=?", (uid, week_start))
        current = cur.fetchone()
        if current and str(dict(current).get("status") or "") == "processing":
            return {"accepted": True, "status": "processing", "week_start": week_start, "week_end": week_end}
        # Mark as processing
        try:
            cur.execute(
                "INSERT INTO weekly_ai_analyses(user_id, week_start, week_end, status, test_stats_json, homework_stats_json) "
                "VALUES(?,?,?,'processing',?,?) ON CONFLICT(user_id, week_start) DO UPDATE SET status='processing', updated_at=?",
                (uid, week_start, week_end, json.dumps(stats), json.dumps({
                    "total": stats["homework_total"], "completed": stats["homework_completed"],
                    "completion_pct": stats["homework_completion_pct"],
                }), _now().isoformat()),
            )
        except Exception:
            cur.execute("DELETE FROM weekly_ai_analyses WHERE user_id=? AND week_start=?", (uid, week_start))
            cur.execute(
                "INSERT INTO weekly_ai_analyses(user_id, week_start, week_end, status, test_stats_json, homework_stats_json) VALUES(?,?,?,'processing',?,?)",
                (uid, week_start, week_end, json.dumps(stats), json.dumps({
                    "total": stats["homework_total"], "completed": stats["homework_completed"],
                    "completion_pct": stats["homework_completion_pct"],
                })),
            )
        conn.commit()
    finally:
        conn.close()
    asyncio.create_task(_finish_weekly_analysis(user_id=uid, user_name=user_name, week_start=week_start, stats=stats))
    return {"accepted": True, "status": "processing", "week_start": week_start, "week_end": week_end}


@router.get("/student/personal-plan/analysis-history")
async def get_analysis_history(authorization: str | None = Header(default=None)):
    """Get all previous weekly analyses for the student."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, week_start, week_end, analysis_text, weak_topics_json, "
            "recommendations_json, test_stats_json, homework_stats_json, "
            "practice_questions_json, status, created_at "
            "FROM weekly_ai_analyses WHERE user_id=? AND status='done' "
            "ORDER BY week_start DESC LIMIT 12",
            (uid,),
        )
        items = []
        for row in cur.fetchall():
            r = dict(row)
            items.append({
                "id": r["id"],
                "week_start": r["week_start"],
                "week_end": r["week_end"],
                "analysis": r.get("analysis_text", ""),
                "weak_topics": json.loads(r.get("weak_topics_json") or "[]"),
                "recommendations": json.loads(r.get("recommendations_json") or "[]"),
                "test_stats": json.loads(r.get("test_stats_json") or "{}"),
                "homework_stats": json.loads(r.get("homework_stats_json") or "{}"),
                "practice_questions": json.loads(r.get("practice_questions_json") or "[]"),
                "created_at": r.get("created_at"),
            })
        return {"items": items}
    finally:
        conn.close()


class WeeklyAnalysisAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1200)


@router.post("/student/personal-plan/weekly-analysis/ask")
async def ask_weekly_analysis(payload: WeeklyAnalysisAskRequest, authorization: str | None = Header(default=None)):
    """Diamondvoy answers with the student's current-week learning context only."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    week_start, _ = _current_week_range()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT analysis_text,weak_topics_json,recommendations_json FROM weekly_ai_analyses "
            "WHERE user_id=? AND week_start=? AND status='done' LIMIT 1",
            (int(user["id"]), week_start),
        )
        row = cur.fetchone()
        context = dict(row) if row else {}
    finally:
        conn.close()
    weak_topics = context.get("weak_topics_json") or "[]"
    recommendations = context.get("recommendations_json") or "[]"
    try:
        import aiohttp
        from ai_generator import _xai_generate_text
        prompt = (
            "Sen Diamondvoysan. O‘quvchiga faqat oddiy, qisqa va foydali o‘quv izohini ber. "
            "Javobni 4-6 jumladan oshirma; uydirma fakt yoki yangi test javobini bermagin.\n\n"
            f"Haftalik tahlil: {str(context.get('analysis_text') or '')[:2500]}\n"
            f"Zaif mavzular: {str(weak_topics)[:2500]}\n"
            f"Tavsiyalar: {str(recommendations)[:1600]}\n\n"
            f"O‘quvchi savoli: {payload.question}"
        )
        async with aiohttp.ClientSession() as session:
            answer = await _xai_generate_text(prompt, session=session, temperature=0.35)
        return {"answer": str(answer).strip()}
    except Exception:
        return {"answer": "Bu mavzuni kichik qismlarga bo‘lib takrorlang: avval qoida, keyin bir misol, so‘ng yengil mashq. Xatolar daftaridagi shu mavzuni ham qayta ishlang."}


@router.get("/student/personal-plan/stats")
async def get_plan_stats(authorization: str | None = Header(default=None)):
    """Get current week stats without AI analysis."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"]); week_start, week_end = _current_week_range()
    conn = get_conn()
    try:
        cur = conn.cursor()
        stats = _collect_week_stats(cur, uid, week_start, week_end)
        return {"week_start": week_start, "week_end": week_end, **stats}
    finally:
        conn.close()


@router.post("/student/personal-plan/practice-test/check")
async def check_practice_answer(payload: dict, authorization: str | None = Header(default=None)):
    """Check a practice question answer and get AI explanation."""
    user = _user(authorization); _require(user, {"student"})
    question = str(payload.get("question", ""))
    selected = str(payload.get("selected", ""))
    correct = str(payload.get("correct", ""))
    topic = str(payload.get("topic", ""))
    is_correct = selected.strip() == correct.strip()

    explanation = str(payload.get("explanation", ""))
    if not explanation and not is_correct:
        import aiohttp
        try:
            from ai_generator import _xai_generate_text
            prompt = (
                f"O'quvchi ingliz tili testida xato qildi.\n"
                f"Savol: {question}\nTanlangan: {selected}\nTo'g'ri javob: {correct}\nMavzu: {topic}\n\n"
                f"Nima uchun to'g'ri javob shu ekanini qisqa, sodda va tushunarli tilda tushuntir (2-3 jumla)."
            )
            async with aiohttp.ClientSession() as session:
                explanation = await _xai_generate_text(prompt, session=session, temperature=0.4)
        except Exception:
            explanation = f"To'g'ri javob: {correct}"

    # Save wrong answers to mistake notebook
    if not is_correct:
        ensure_schema(); conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO mistake_notebook_items(user_id, source_type, subject, topic_key, prompt, "
                "options_json, selected_answer, correct_answer, explanation, review_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (int(user["id"]), "weekly_practice", str(payload.get("subject") or ""), topic, question,
                 json.dumps(payload.get("options", []), ensure_ascii=False),
                 selected, correct, explanation,
                 mistake_next_review_at(_now(), 0).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    return {
        "correct": is_correct,
        "explanation": explanation,
        "correct_answer": correct,
    }


# ── Alias Routes (fix frontend/backend path mismatch) ────────────────────────
@router.get("/student/personalization/plan/today")
async def alias_plan_today(authorization: str | None = Header(default=None)):
    return await student_personal_plan(authorization)

@router.post("/student/personalization/plan/generate")
async def alias_plan_generate(authorization: str | None = Header(default=None)):
    return await refresh_personal_plan(authorization)

@router.put("/student/personalization/plan/tasks/{task_id}/complete")
async def alias_plan_complete(task_id: int, authorization: str | None = Header(default=None)):
    return await complete_personal_plan_task(task_id, authorization)
