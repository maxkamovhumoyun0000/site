"""Personal learning, study-room and parent-progress API.

This module deliberately owns only new, additive tables and routes.  It uses
the main application's authentication callback so existing role/session policy
remains the single source of truth.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from db import get_conn

router = APIRouter()
_runtime: dict[str, Callable[..., Any]] = {}


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


def ensure_schema() -> None:
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
        return {"items": items, "due_count": len(items), "total_count": total}
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
async def answer_mistake(item_id: int, correct: bool, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor(); cur.execute("SELECT correct_streak FROM mistake_notebook_items WHERE id=? AND user_id=?", (item_id, int(user["id"])))
        row = cur.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Mistake item not found")
        streak = int(dict(row).get("correct_streak") or 0) + 1 if correct else 0
        resolved = _now().isoformat() if streak >= 4 else None
        review = mistake_next_review_at(_now(), streak).isoformat()
        cur.execute("UPDATE mistake_notebook_items SET correct_streak=?, review_at=?, resolved_at=?, updated_at=? WHERE id=?", (streak, review, resolved, _now().isoformat(), item_id)); conn.commit()
        return {"correct_streak": streak, "review_at": review, "resolved": bool(resolved)}
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
