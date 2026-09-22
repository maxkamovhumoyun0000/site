"""Personal learning, study-room and parent-progress API.

This module deliberately owns only new, additive tables and routes.  It uses
the main application's authentication callback so existing role/session policy
remains the single source of truth.
"""

from __future__ import annotations

import re
import json
import secrets
import random
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse, unquote

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from db import get_conn, add_dcoins

logger = logging.getLogger(__name__)
router = APIRouter()
_runtime: dict[str, Callable[..., Any]] = {}
_schema_ready = False

STUDY_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "data" / "chat_uploads"
STUDY_ALT_UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"


def configure_runtime(**callbacks: Callable[..., Any]) -> None:
    _runtime.update(callbacks)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_parent_access_token() -> str:
    return secrets.token_urlsafe(32).replace("-", "").replace("_", "")


def new_study_room_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


# Study rooms are deliberately role-neutral.  A room is still private because
# every data, message and WebRTC operation verifies active membership; a role
# alone never reveals a room or its material.
STUDY_ROOM_ROLES = {"student", "teacher", "support", "admin"}
DEFAULT_TRACK_PASSING_SCORE = 70


def normalize_track_passing_score(value: Any) -> int:
    """One persistent threshold used by every module in a learning track."""
    if value is None or value == "":
        return DEFAULT_TRACK_PASSING_SCORE
    try:
        return min(100, max(1, int(float(value))))
    except (TypeError, ValueError):
        return DEFAULT_TRACK_PASSING_SCORE


def learning_score_passes(score: Any, passing_score: Any = None) -> bool:
    try:
        return float(score) >= normalize_track_passing_score(passing_score)
    except (TypeError, ValueError):
        return False


def next_track_unlocked(module_states: list[Any]) -> bool:
    return bool(module_states) and all(str(item).lower() == "passed" for item in module_states)


def track_certificate_eligible(track_status: Any, *, certificate_required: bool = True) -> bool:
    return bool(certificate_required) and str(track_status).lower() == "passed"


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
                notified INTEGER DEFAULT 0,
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
              subject TEXT DEFAULT 'English',
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
            """CREATE TABLE IF NOT EXISTS ai_generated_questions_bank (
              id BIGSERIAL PRIMARY KEY,
              subject TEXT NOT NULL,
              topic TEXT NOT NULL,
              difficulty TEXT DEFAULT 'medium',
              question_text TEXT NOT NULL,
              options_json TEXT NOT NULL,
              correct_answer TEXT NOT NULL,
              explanation TEXT,
              test_type TEXT DEFAULT 'multiple_choice',
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              use_count INTEGER DEFAULT 0
            )""",
            """CREATE TABLE IF NOT EXISTS personal_practice_attempts (
              id BIGSERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL,
              attempt_id TEXT NOT NULL,
              subject TEXT,
              total_questions INTEGER NOT NULL DEFAULT 0,
              completed_at TIMESTAMP,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, attempt_id)
            )""",
            """CREATE TABLE IF NOT EXISTS personal_practice_attempt_items (
              id BIGSERIAL PRIMARY KEY,
              user_id BIGINT NOT NULL,
              attempt_id TEXT NOT NULL,
              question_index INTEGER NOT NULL,
              subject TEXT,
              topic_key TEXT,
              prompt TEXT NOT NULL,
              options_json TEXT,
              selected_answer TEXT,
              correct_answer TEXT,
              explanation TEXT,
              is_correct INTEGER NOT NULL DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, attempt_id, question_index)
            )""",
            """CREATE TABLE IF NOT EXISTS learning_tracks (
              id BIGSERIAL PRIMARY KEY, owner_id BIGINT NOT NULL, subject TEXT NOT NULL,
              title TEXT NOT NULL, description TEXT, cover_key TEXT DEFAULT 'star',
              status TEXT NOT NULL DEFAULT 'draft', position INTEGER NOT NULL DEFAULT 0,
              passing_score INTEGER NOT NULL DEFAULT 70, certificate_required INTEGER NOT NULL DEFAULT 1,
              certificate_template_key TEXT DEFAULT 'english', certificate_layers_json TEXT DEFAULT '[]',
              version INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, published_at TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS learning_modules (
              id BIGSERIAL PRIMARY KEY, track_id BIGINT NOT NULL, title TEXT NOT NULL,
              description TEXT, cover_key TEXT DEFAULT 'star', position INTEGER NOT NULL DEFAULT 0,
              topic_keys_json TEXT NOT NULL DEFAULT '[]', passing_score INTEGER, reward_coins INTEGER NOT NULL DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS learning_module_lessons (
              id BIGSERIAL PRIMARY KEY, module_id BIGINT NOT NULL, title TEXT NOT NULL,
              source_kind TEXT NOT NULL DEFAULT 'manual', source_id TEXT, source_version TEXT,
              question_payload_json TEXT, duration_seconds INTEGER NOT NULL DEFAULT 0,
              position INTEGER NOT NULL DEFAULT 0, required INTEGER NOT NULL DEFAULT 1,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS learning_track_assignments (
              id BIGSERIAL PRIMARY KEY, track_id BIGINT NOT NULL, student_id BIGINT NOT NULL,
              assigned_by BIGINT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
              assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, due_at TIMESTAMP,
              UNIQUE(track_id, student_id)
            )""",
            """CREATE TABLE IF NOT EXISTS learning_lesson_attempts (
              id BIGSERIAL PRIMARY KEY, lesson_id BIGINT NOT NULL, student_id BIGINT NOT NULL,
              score REAL NOT NULL DEFAULT 0, passed INTEGER NOT NULL DEFAULT 0,
              answers_json TEXT, started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              completed_at TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS learning_module_progress (
              id BIGSERIAL PRIMARY KEY, module_id BIGINT NOT NULL, student_id BIGINT NOT NULL,
              status TEXT NOT NULL DEFAULT 'locked', best_score REAL NOT NULL DEFAULT 0,
              passed_at TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(module_id, student_id)
            )""",
            """CREATE TABLE IF NOT EXISTS learning_certificate_shares (
              id BIGSERIAL PRIMARY KEY, certificate_id TEXT NOT NULL UNIQUE, share_token TEXT NOT NULL UNIQUE,
              active INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              revoked_at TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS learning_track_final_progress (
              id BIGSERIAL PRIMARY KEY, track_id BIGINT NOT NULL, student_id BIGINT NOT NULL,
              status TEXT NOT NULL DEFAULT 'locked', best_score REAL NOT NULL DEFAULT 0,
              attempts_count INTEGER NOT NULL DEFAULT 0, passed_at TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(track_id, student_id)
            )""",
            """CREATE TABLE IF NOT EXISTS learning_track_final_attempts (
              id BIGSERIAL PRIMARY KEY, track_id BIGINT NOT NULL, student_id BIGINT NOT NULL,
              score REAL NOT NULL DEFAULT 0, passed INTEGER NOT NULL DEFAULT 0,
              answers_json TEXT, completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]
        for sql in statements:
            try:
                cur.execute(sql)
            except Exception:
                # Local SQLite fallback has no BIGSERIAL; existing db adapter's
                # production target is PostgreSQL, so retry using INTEGER PK.
                cur.execute(sql.replace("BIGSERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT").replace("BIGINT", "INTEGER"))
        # Older production databases predate the per-subject analysis column.
        # Add it before creating its index; PostgreSQL aborts the entire
        # transaction after an index references a missing column.
        try:
            cur.execute("ALTER TABLE weekly_ai_analyses ADD COLUMN IF NOT EXISTS subject TEXT DEFAULT 'English'")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE weekly_ai_analyses ADD COLUMN subject TEXT DEFAULT 'English'")
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

        for sql in (
            "CREATE INDEX IF NOT EXISTS idx_mistakes_user_review ON mistake_notebook_items(user_id, review_at)",
            "CREATE INDEX IF NOT EXISTS idx_bookmarks_user ON learning_bookmarks(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_study_room_members_room ON study_room_members(room_id, left_at)",
            "CREATE INDEX IF NOT EXISTS idx_study_room_messages_room ON study_room_messages(room_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_study_room_materials_room ON study_room_materials(room_id, id)",
            "CREATE INDEX IF NOT EXISTS idx_pomodoro_user ON pomodoro_sessions(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_user_sessions ON user_sessions(user_id, last_seen DESC)",
            "CREATE INDEX IF NOT EXISTS idx_weekly_analysis_user ON weekly_ai_analyses(user_id, week_start DESC)",
            "CREATE INDEX IF NOT EXISTS idx_weekly_analysis_user_subj ON weekly_ai_analyses(user_id, week_start, subject)",
            "CREATE INDEX IF NOT EXISTS idx_ai_qbank_topic ON ai_generated_questions_bank(subject, topic)",
            "CREATE INDEX IF NOT EXISTS idx_ai_qbank_count ON ai_generated_questions_bank(use_count)",
            "CREATE INDEX IF NOT EXISTS idx_personal_practice_attempts_user ON personal_practice_attempts(user_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_personal_practice_items_attempt ON personal_practice_attempt_items(user_id, attempt_id, question_index)",
            "CREATE INDEX IF NOT EXISTS idx_learning_tracks_owner ON learning_tracks(owner_id, subject, status, position)",
            "CREATE INDEX IF NOT EXISTS idx_learning_modules_track ON learning_modules(track_id, position)",
            "CREATE INDEX IF NOT EXISTS idx_learning_lessons_module ON learning_module_lessons(module_id, position)",
            "CREATE INDEX IF NOT EXISTS idx_learning_assignment_student ON learning_track_assignments(student_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_learning_progress_student ON learning_module_progress(student_id, module_id)",
            "CREATE INDEX IF NOT EXISTS idx_track_final_progress ON learning_track_final_progress(track_id, student_id)",
            "CREATE INDEX IF NOT EXISTS idx_track_final_attempts ON learning_track_final_attempts(track_id, student_id)",
        ):
            try:
                cur.execute(sql)
            except Exception:
                # A failed DDL command leaves a PostgreSQL transaction
                # aborted. Roll back before attempting the next optional
                # index so a legacy schema can still complete its upgrades.
                try:
                    conn.rollback()
                except Exception:
                    pass
        try:
            cur.execute("ALTER TABLE study_rooms ADD COLUMN IF NOT EXISTS voice_room_id BIGINT")
        except Exception:
            try:
                cur.execute("ALTER TABLE study_rooms ADD COLUMN voice_room_id INTEGER")
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE study_room_members ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMP")
        except Exception:
            try:
                cur.execute("ALTER TABLE study_room_members ADD COLUMN last_seen_at TIMESTAMP")
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE learning_modules ADD COLUMN IF NOT EXISTS reward_coins INTEGER NOT NULL DEFAULT 0")
        except Exception:
            try:
                cur.execute("ALTER TABLE learning_modules ADD COLUMN reward_coins INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
        try:
            cur.execute("UPDATE learning_module_progress SET status='passed' WHERE passed_at IS NOT NULL AND status != 'passed'")
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE learning_module_progress ADD COLUMN IF NOT EXISTS rewarded_at TIMESTAMP")
        except Exception:
            try:
                cur.execute("ALTER TABLE learning_module_progress ADD COLUMN rewarded_at TIMESTAMP")
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE learning_modules ADD COLUMN IF NOT EXISTS image_url TEXT")
        except Exception:
            try:
                cur.execute("ALTER TABLE learning_modules ADD COLUMN image_url TEXT")
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE student_badges ADD COLUMN IF NOT EXISTS notified INTEGER DEFAULT 0")
        except Exception:
            try:
                cur.execute("ALTER TABLE student_badges ADD COLUMN notified INTEGER DEFAULT 0")
            except Exception:
                pass
        try:
            cur.execute("ALTER TABLE weekly_ai_analyses ADD COLUMN IF NOT EXISTS subject TEXT DEFAULT 'English'")
        except Exception:
            try:
                cur.execute("ALTER TABLE weekly_ai_analyses ADD COLUMN subject TEXT DEFAULT 'English'")
            except Exception:
                pass
        official_badges = (
            ("flawless_test", "Xatosiz bilimdon", "Test ishlab, unda umuman xato qilmagan o‘quvchiga (100% natija)", "/badges/flawless_test.png", "flawless_test"),
            ("tests_500", "500+ Test giganti", "500 tadan ko‘p test ishlaganga", "/badges/tests_500.png", "tests_500"),
            ("books_10_tests", "10+ Kitob ustasi", "10 tadan ko‘p kitob sotib olib, ularning testlarini ishlab tugatgan o‘quvchiga", "/badges/books_10_tests.png", "books_10_tests"),
            ("daily_test_7", "7 kunlik odat", "7 kun davomida har kuni test ishlasa kunlik testni", "/badges/daily_test_7.png", "daily_test_7"),
            ("daily_test_30", "30 kunlik intizom", "30 kun davomida har kuni daily test ishlaganga", "/badges/daily_test_30.png", "daily_test_30"),
            ("arena_duel_streak_5", "Arena yengilmasi", "Arena va duellarda qatnashib, ketma-ket 5 marta yutgan o‘quvchiga", "/badges/arena_duel_streak_5.png", "arena_duel_streak_5"),
            ("learning_tracks_10", "10 Track zabt etuvchisi", "Learning path trackidan 10 tasini muvaffaqiyatli tugatgan o‘quvchiga", "/badges/learning_tracks_10.png", "learning_tracks_10"),
        )
        official_codes = [b[0] for b in official_badges]
        ph_off = ",".join("?" for _ in official_codes)
        try:
            cur.execute(f"UPDATE badge_definitions SET active=0 WHERE code NOT IN ({ph_off})", official_codes)
            cur.execute(f"DELETE FROM student_badges WHERE badge_code NOT IN ({ph_off})", official_codes)
        except Exception:
            pass

        for code, title, description, asset_url, rule_key in official_badges:
            try:
                cur.execute(
                    """
                    INSERT INTO badge_definitions(code,title,description,asset_url,rule_key,active)
                    VALUES(?,?,?,?,?,1)
                    ON CONFLICT(code) DO UPDATE SET
                        title=excluded.title,
                        description=excluded.description,
                        asset_url=excluded.asset_url,
                        rule_key=excluded.rule_key,
                        active=1
                    """,
                    (code, title, description, asset_url, rule_key),
                )
            except Exception:
                try:
                    cur.execute("DELETE FROM badge_definitions WHERE code=?", (code,))
                    cur.execute(
                        "INSERT INTO badge_definitions(code,title,description,asset_url,rule_key,active) VALUES(?,?,?,?,?,1)",
                        (code, title, description, asset_url, rule_key),
                    )
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


def _sanitize_row_value(val: Any) -> Any:
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def _dicts(rows: Any) -> list[dict[str, Any]]:
    return [{k: _sanitize_row_value(v) for k, v in dict(row).items()} for row in (rows or [])]


def _student_name(row: dict[str, Any]) -> str:
    return " ".join(part for part in (str(row.get("first_name") or "").strip(), str(row.get("last_name") or "").strip()) if part).strip() or str(row.get("login_id") or "Student")


def _award_badge(cur: Any, user_id: int, badge_code: str) -> None:
    try:
        cur.execute(
            "INSERT INTO student_badges(user_id,badge_code,notified) VALUES(?,?,0) ON CONFLICT(user_id,badge_code) DO NOTHING",
            (user_id, badge_code),
        )
    except Exception:
        try:
            cur.execute(
                "INSERT OR IGNORE INTO student_badges(user_id,badge_code,notified) VALUES(?,?,0)",
                (user_id, badge_code),
            )
        except Exception:
            pass


def _sync_student_badges(cur: Any, user_id: int) -> None:
    """Award badges based on student accomplishments for the 7 official visual badges."""
    # 1. flawless_test: Test with 100% correct answers (0 wrong, 0 skipped)
    try:
        cur.execute(
            """
            SELECT 1 FROM test_history
            WHERE user_id = ? AND correct_count > 0 AND COALESCE(wrong_count, 0) = 0 AND COALESCE(skipped_count, 0) = 0
            LIMIT 1
            """,
            (user_id,),
        )
        if cur.fetchone():
            _award_badge(cur, user_id, "flawless_test")
    except Exception:
        pass

    # 2. tests_500: 500+ tests taken or 500+ questions answered
    try:
        cur.execute(
            "SELECT COUNT(*) AS c, SUM(COALESCE(correct_count, 0) + COALESCE(wrong_count, 0)) AS q FROM test_history WHERE user_id = ?",
            (user_id,),
        )
        t_row = dict(cur.fetchone() or {})
        if int(t_row.get("c") or 0) >= 500 or int(t_row.get("q") or 0) >= 500:
            _award_badge(cur, user_id, "tests_500")
    except Exception:
        pass

    # 3. books_10_tests: 10+ books purchased and tested
    try:
        b_cnt = 0
        try:
            cur.execute(
                "SELECT COUNT(*) AS n FROM student_book_purchases WHERE user_id = ? AND status IN ('test_passed', 'completed', 'finished')",
                (user_id,),
            )
            b_cnt = int(dict(cur.fetchone() or {}).get("n") or 0)
        except Exception:
            pass
        if b_cnt < 10:
            try:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM test_history WHERE user_id = ? AND test_type IN ('book', 'content_book')",
                    (user_id,),
                )
                b_cnt = max(b_cnt, int(dict(cur.fetchone() or {}).get("n") or 0))
            except Exception:
                pass
        if b_cnt >= 10:
            _award_badge(cur, user_id, "books_10_tests")
    except Exception:
        pass

    # 4 & 5. daily_test_7 and daily_test_30: Daily test streaks of 7 and 30 days
    try:
        streak = 0
        daily_days = 0
        try:
            cur.execute("SELECT consecutive_qualifying_days FROM user_dcoin_streak WHERE user_id = ?", (user_id,))
            s_row = cur.fetchone()
            if s_row:
                streak = int(dict(s_row).get("consecutive_qualifying_days") or 0)
        except Exception:
            pass
        try:
            cur.execute(
                "SELECT COUNT(DISTINCT substr(created_at, 1, 10)) AS d FROM test_history WHERE user_id = ? AND test_type = 'daily'",
                (user_id,),
            )
            d_row = cur.fetchone()
            if d_row:
                daily_days = int(dict(d_row).get("d") or 0)
        except Exception:
            pass

        max_daily = max(streak, daily_days)
        if max_daily >= 7:
            _award_badge(cur, user_id, "daily_test_7")
        if max_daily >= 30:
            _award_badge(cur, user_id, "daily_test_30")
    except Exception:
        pass

    # 6. arena_duel_streak_5: 5 streak in arena or duels
    try:
        has_arena_streak = False
        try:
            cur.execute("SELECT win_streak FROM user_dcoin_streak WHERE user_id = ?", (user_id,))
            w_row = cur.fetchone()
            if w_row and int(dict(w_row).get("win_streak") or 0) >= 5:
                has_arena_streak = True
        except Exception:
            pass
        if not has_arena_streak:
            try:
                cur.execute("SELECT 1 FROM diamond_history WHERE user_id = ? AND change_type = 'streak_duel_5wins' LIMIT 1", (user_id,))
                if cur.fetchone():
                    has_arena_streak = True
            except Exception:
                pass
        if not has_arena_streak:
            try:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM diamond_history WHERE user_id = ? AND (change_type LIKE '%duel%' OR change_type LIKE '%arena%') AND dcoin_change > 0",
                    (user_id,),
                )
                a_row = cur.fetchone()
                if a_row and int(dict(a_row).get("n") or 0) >= 5:
                    has_arena_streak = True
            except Exception:
                pass
        if has_arena_streak:
            _award_badge(cur, user_id, "arena_duel_streak_5")
    except Exception:
        pass

    # 7. learning_tracks_10: 10 learning tracks or modules completed
    try:
        track_cnt = 0
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM learning_tracks t
                WHERE EXISTS (SELECT 1 FROM learning_modules m WHERE m.track_id = t.id)
                AND NOT EXISTS (
                    SELECT 1 FROM learning_modules m
                    LEFT JOIN learning_module_progress p ON p.module_id = m.id AND p.student_id = ?
                    WHERE m.track_id = t.id AND (p.status IS NULL OR p.status != 'completed')
                )
                """,
                (user_id,),
            )
            t_row = cur.fetchone()
            if t_row:
                track_cnt = int(dict(t_row).get("n") or 0)
        except Exception:
            pass
        if track_cnt < 10:
            try:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM learning_module_progress WHERE student_id = ? AND status = 'completed'",
                    (user_id,),
                )
                m_row = cur.fetchone()
                if m_row:
                    track_cnt = max(track_cnt, int(dict(m_row).get("n") or 0))
            except Exception:
                pass
        if track_cnt >= 10:
            _award_badge(cur, user_id, "learning_tracks_10")
    except Exception:
        pass

    # Auto-select the first unlocked badge if student doesn't have any selected badge
    try:
        cur.execute(
            """
            SELECT 1 FROM student_badges sb
            JOIN badge_definitions bd ON bd.code = sb.badge_code
            WHERE sb.user_id = ? AND sb.selected = 1 AND bd.active = 1
            LIMIT 1
            """,
            (user_id,),
        )
        if not cur.fetchone():
            cur.execute(
                """
                UPDATE student_badges SET selected = 1
                WHERE id = (
                    SELECT sb.id FROM student_badges sb
                    JOIN badge_definitions bd ON bd.code = sb.badge_code
                    WHERE sb.user_id = ? AND bd.active = 1
                    ORDER BY sb.id ASC
                    LIMIT 1
                )
                """,
                (user_id,),
            )
    except Exception:
        pass


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
            title = f"{subject or 'Fan'}: {topic or 'mavzu'} bo‘yicha mashq"
            cur.execute("INSERT INTO personalization_plan_tasks(plan_id, task_type, title, subject, topic_key, target_url, priority, metadata_json) VALUES(?,?,?,?,?,?,?,?)", (plan_id, "mistake_review", title, subject, topic, "/?role=student&section=learning-paths", 100-index, json.dumps({"mistakes": int(item.get("mistakes") or 0)})))
        cur.execute("SELECT COUNT(*) AS total FROM web_homeworks h LEFT JOIN web_homework_submissions s ON s.homework_id=h.id AND s.student_id=? WHERE h.student_id=? AND COALESCE(s.status,'') NOT IN ('done','accepted','reviewed','completed')", (student_id, student_id))
        pending = int(dict(cur.fetchone() or {}).get("total") or 0)
        if pending:
            cur.execute("INSERT INTO personalization_plan_tasks(plan_id, task_type, title, target_url, priority, metadata_json) VALUES(?,?,?,?,?,?)", (plan_id, "homework", f"{pending} ta uyga vazifani yakunlang", "/?role=student&section=homework", 90, json.dumps({"pending": pending})))
        # Learning paths are first-class learning evidence, not a separate
        # gamification island: unfinished assigned tracks belong in the daily
        # Diamondvoy plan and therefore weekly advice as well.
        cur.execute(
            "SELECT t.id,t.title,t.subject FROM learning_tracks t "
            "WHERE t.status != 'archived' "
            "ORDER BY t.position,t.id LIMIT 1"
        )
        learning = cur.fetchone()
        if learning:
            learning = dict(learning)
            cur.execute(
                "INSERT INTO personalization_plan_tasks(plan_id, task_type, title, subject, target_url, priority, metadata_json) VALUES(?,?,?,?,?,?,?)",
                (plan_id, "learning_path", f"{learning['title']} trackini davom ettiring", learning.get("subject"), "/?role=student&section=learning-paths", 85, json.dumps({"track_id": int(learning["id"])})),
            )
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


class PomodoroRequest(BaseModel):
    mode: str = Field(default="work")
    phase: str | None = None
    planned_seconds: int = Field(default=1500, ge=1, le=86400)
    completed_seconds: int = Field(default=0, ge=0, le=86400)
    seconds: int | None = None
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
            cur=conn.cursor()
            today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            cur.execute("SELECT COALESCE(SUM(completed_seconds),0) AS today_sec, COUNT(*) AS today_sessions FROM pomodoro_sessions WHERE user_id=? AND (created_at>=? OR completed_at>=?)", (int(user["id"]), today_start, today_start))
            t_row = dict(cur.fetchone() or {})
            cur.execute("SELECT COALESCE(SUM(completed_seconds),0) AS total, COUNT(*) AS sessions FROM pomodoro_sessions WHERE user_id=? AND created_at>=?", (int(user["id"]), (_now()-timedelta(days=7)).isoformat()))
            row=dict(cur.fetchone() or {})
            return {
                "week_seconds": int(row.get("total") or 0),
                "week_focused_minutes": int((row.get("total") or 0) // 60),
                "sessions": int(row.get("sessions") or 0),
                "today_focused_minutes": int((t_row.get("today_sec") or 0) // 60),
                "completed_cycles": int(t_row.get("today_sessions") or 0),
            }
        finally: conn.close()

    @router.get(f"/{prefix}/pomodoro/sessions")
    async def get_pomodoro_sessions(authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor()
            cur.execute(
                "SELECT id, mode, planned_seconds, completed_seconds, completed_at, created_at FROM pomodoro_sessions WHERE user_id=? ORDER BY id DESC LIMIT 50",
                (int(user["id"]),)
            )
            rows = [dict(r) for r in cur.fetchall()]

            today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            cur.execute(
                "SELECT COALESCE(SUM(completed_seconds),0) AS today_seconds, COUNT(*) AS today_count FROM pomodoro_sessions WHERE user_id=? AND (created_at>=? OR completed_at>=?)",
                (int(user["id"]), today_start, today_start)
            )
            today_row = dict(cur.fetchone() or {})

            cur.execute(
                "SELECT COALESCE(SUM(completed_seconds),0) AS week_seconds, COUNT(*) AS week_sessions FROM pomodoro_sessions WHERE user_id=? AND created_at>=?",
                (int(user["id"]), (_now()-timedelta(days=7)).isoformat())
            )
            week_row = dict(cur.fetchone() or {})

            formatted = []
            for r in rows:
                c_sec = int(r.get("completed_seconds") or 0)
                p_sec = int(r.get("planned_seconds") or 0)
                formatted.append({
                    "id": int(r.get("id") or 0),
                    "mode": str(r.get("mode") or "work"),
                    "duration_minutes": max(1, (c_sec if c_sec > 0 else p_sec) // 60),
                    "planned_seconds": p_sec,
                    "completed_seconds": c_sec,
                    "completed_at": str(r.get("completed_at") or ""),
                    "created_at": str(r.get("created_at") or ""),
                    "completed": bool(r.get("completed_at") or c_sec > 0),
                })

            return {
                "sessions": formatted,
                "today_count": int(today_row.get("today_count") or 0),
                "today_minutes": int((today_row.get("today_seconds") or 0) // 60),
                "week_seconds": int(week_row.get("week_seconds") or 0),
                "week_sessions": int(week_row.get("week_sessions") or 0),
            }
        finally: conn.close()

    @router.post(f"/{prefix}/pomodoro/sessions")
    async def save_pomodoro(payload: PomodoroRequest, authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor()
            mode = payload.mode or payload.phase or "work"
            planned_sec = payload.planned_seconds if payload.planned_seconds else (payload.seconds or 1500)
            completed_sec = payload.completed_seconds if payload.completed_seconds else (payload.seconds or (planned_sec if payload.completed else 0))
            is_completed = payload.completed or completed_sec > 0
            comp_time = _now().isoformat() if is_completed else None
            try:
                cur.execute("INSERT INTO pomodoro_sessions(user_id, mode, planned_seconds, completed_seconds, completed_at) VALUES(?,?,?,?,?) RETURNING id", (int(user["id"]), mode, planned_sec, completed_sec, comp_time))
                row=cur.fetchone()
                sid=int(dict(row)["id"]) if row else 0
            except Exception:
                cur.execute("INSERT INTO pomodoro_sessions(user_id, mode, planned_seconds, completed_seconds, completed_at) VALUES(?,?,?,?,?)", (int(user["id"]), mode, planned_sec, completed_sec, comp_time))
                sid=int(getattr(cur, "lastrowid", 0) or 0)
            conn.commit(); return {"id": sid}
        finally: conn.close()

    @router.delete(f"/{prefix}/pomodoro/sessions/{{session_id}}")
    async def delete_pomodoro_session(session_id: int, authorization: str | None = Header(default=None)):
        user=_user(authorization); _require(user, roles); ensure_schema(); conn=get_conn()
        try:
            cur=conn.cursor()
            cur.execute("DELETE FROM pomodoro_sessions WHERE id=? AND user_id=?", (session_id, int(user["id"])))
            conn.commit()
            return {"deleted": True, "id": session_id}
        finally: conn.close()


_bookmark_routes("student", {"student"}); _bookmark_routes("staff", {"teacher", "support"})
_pomodoro_routes("student", {"student"}); _pomodoro_routes("staff", {"teacher", "support"}); _pomodoro_routes("teacher", {"teacher", "support"})


@router.post("/student/study-rooms")
async def create_study_room(payload: StudyRoomCreate, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, STUDY_ROOM_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); code=new_study_room_code()
        for _ in range(8):
            cur.execute("SELECT 1 FROM study_rooms WHERE room_code=? AND status='open'", (code,))
            if not cur.fetchone(): break
            code=new_study_room_code()
        else: raise HTTPException(status_code=503, detail="Could not allocate room code")
        room_id = 0
        try:
            cur.execute("INSERT INTO study_rooms(room_code, owner_id, title) VALUES(?,?,?) RETURNING id", (code, int(user["id"]), payload.title))
            row = cur.fetchone()
            if row:
                room_id = int(row.get("id") if hasattr(row, "get") else row[0])
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            cur.execute("INSERT INTO study_rooms(room_code, owner_id, title) VALUES(?,?,?)", (code, int(user["id"]), payload.title))
            cur.execute("SELECT id FROM study_rooms WHERE room_code=? ORDER BY id DESC LIMIT 1", (code,))
            row = cur.fetchone()
            if row:
                room_id = int(row.get("id") if hasattr(row, "get") else row[0])
        if not room_id:
            raise HTTPException(status_code=500, detail="Xona yaratishda xatolik yuz berdi")
        cur.execute("INSERT INTO study_room_members(room_id,user_id) VALUES(?,?)", (room_id,int(user["id"])))
        conn.commit()
        return {"id": room_id, "room_code": code, "title": payload.title, "max_members": 4}
    finally: conn.close()


@router.get("/student/study-rooms")
async def list_study_rooms(authorization: str | None = Header(default=None)):
    """Return only rooms in which the caller is currently a member.

    This is intentionally not a public directory: joining always requires the
    current six-digit code, and a room closed by its owner disappears here.
    """
    user=_user(authorization); _require(user, STUDY_ROOM_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor()
        _sweep_study_room_presence(cur)
        conn.commit()
        cur.execute(
            "SELECT r.*, COUNT(active.id) AS member_count FROM study_rooms r "
            "JOIN study_room_members mine ON mine.room_id=r.id AND mine.user_id=? AND mine.left_at IS NULL "
            "LEFT JOIN study_room_members active ON active.room_id=r.id AND active.left_at IS NULL "
            "WHERE r.status='open' GROUP BY r.id ORDER BY r.created_at DESC LIMIT 100",
            (int(user["id"]),),
        )
        return {"items": _dicts(cur.fetchall()), "max_members": 4}
    finally: conn.close()


def _cleanup_study_room_files(room_id: int, cur: Any) -> None:
    """Safely unlink all files from disk for materials and message attachments in this room."""
    try:
        cur.execute("SELECT file_url FROM study_room_materials WHERE room_id=?", (room_id,))
        urls = [str(r["file_url"] or "") for r in _dicts(cur.fetchall())]

        cur.execute("SELECT attachments_json FROM study_room_messages WHERE room_id=?", (room_id,))
        for msg in _dicts(cur.fetchall()):
            try:
                atts = json.loads(str(msg.get("attachments_json") or "[]"))
                for a in atts:
                    u = str(a.get("url") or a.get("file_url") or "")
                    if u:
                        urls.append(u)
            except Exception:
                pass

        for u in urls:
            if not u:
                continue
            try:
                parsed = urlparse(u)
                raw_filename = Path(unquote(parsed.path)).name
                if not raw_filename or raw_filename in {".", ".."}:
                    continue
                for upload_dir in (STUDY_UPLOAD_DIR, STUDY_ALT_UPLOAD_DIR):
                    target_file = (upload_dir / raw_filename).resolve()
                    if str(target_file).startswith(str(upload_dir.resolve())) and target_file.is_file():
                        target_file.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass


def _sweep_study_room_presence(cur: Any, room_id: int | None = None) -> list[int]:
    """Detect presence in all possible ways and auto-close empty study rooms.

    1. Any member whose last_seen_at was more than 30s ago (or null and joined > 30s ago)
       is marked left_at = now.
    2. Any study_room that is 'open' and has 0 active members (left_at IS NULL)
       is automatically closed, closed_at is set, and temporary files/messages are cleaned up.
    """
    now = _now()
    cutoff = (now - timedelta(seconds=10)).isoformat()
    now_iso = now.isoformat()

    # Step 1: Mark timed-out / disconnected members as left
    if room_id:
        cur.execute(
            "UPDATE study_room_members SET left_at=? WHERE room_id=? AND left_at IS NULL AND ((last_seen_at IS NOT NULL AND last_seen_at < ?) OR (last_seen_at IS NULL AND joined_at < ?))",
            (now_iso, room_id, cutoff, cutoff)
        )
    else:
        cur.execute(
            "UPDATE study_room_members SET left_at=? WHERE left_at IS NULL AND ((last_seen_at IS NOT NULL AND last_seen_at < ?) OR (last_seen_at IS NULL AND joined_at < ?))",
            (now_iso, cutoff, cutoff)
        )

    # Step 2: Find open rooms with 0 active members left
    if room_id:
        cur.execute("""
            SELECT r.id FROM study_rooms r
            WHERE r.id=? AND r.status='open'
            AND NOT EXISTS (
                SELECT 1 FROM study_room_members m
                WHERE m.room_id=r.id AND m.left_at IS NULL
            )
        """, (room_id,))
    else:
        cur.execute("""
            SELECT r.id FROM study_rooms r
            WHERE r.status='open'
            AND NOT EXISTS (
                SELECT 1 FROM study_room_members m
                WHERE m.room_id=r.id AND m.left_at IS NULL
            )
        """)

    empty_rooms = [int(dict(r)["id"]) for r in cur.fetchall()]
    for er_id in empty_rooms:
        try:
            _cleanup_study_room_files(er_id, cur)
            cur.execute("DELETE FROM study_room_materials WHERE room_id=?", (er_id,))
            cur.execute("DELETE FROM study_room_messages WHERE room_id=?", (er_id,))
            cur.execute(
                "UPDATE study_rooms SET status='closed', closed_at=? WHERE id=?",
                (now_iso, er_id)
            )
        except Exception:
            pass
    return empty_rooms


@router.post("/student/study-rooms/join/{room_code}")
async def join_study_room(room_code: str, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    _require(user, STUDY_ROOM_ROLES)
    ensure_schema()
    conn = get_conn()
    try:
        clean_code = str(room_code or "").strip()
        if len(clean_code) != 6 or not clean_code.isdigit():
            raise HTTPException(status_code=400, detail="Xona kodi 6 ta raqamdan iborat bo'lishi kerak")
        cur = conn.cursor()
        cur.execute("SELECT * FROM study_rooms WHERE room_code=? AND status='open'", (clean_code,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT status FROM study_rooms WHERE room_code=?", (clean_code,))
            closed_row = cur.fetchone()
            if closed_row:
                raise HTTPException(status_code=410, detail="Ushbu study room allaqachon yopilgan")
            raise HTTPException(status_code=404, detail="Bunday kodli study room topilmadi. Kodni tekshirib qaytadan kiriting.")
        room = dict(row)
        cur.execute("SELECT COUNT(*) AS total FROM study_room_members WHERE room_id=? AND left_at IS NULL", (int(room["id"]),))
        count = int(dict(cur.fetchone())["total"])
        cur.execute("SELECT 1 FROM study_room_members WHERE room_id=? AND user_id=? AND left_at IS NULL", (int(room["id"]), int(user["id"])))
        already = bool(cur.fetchone())
        if not already and count >= 4:
            raise HTTPException(status_code=409, detail="Study-room to'lgan (maksimum 4 kishi)")
        now_iso = _now().isoformat()
        if not already:
            cur.execute("UPDATE study_room_members SET left_at=NULL,joined_at=?,last_seen_at=? WHERE room_id=? AND user_id=?", (now_iso, now_iso, int(room["id"]), int(user["id"])))
            if cur.rowcount == 0:
                cur.execute("INSERT INTO study_room_members(room_id,user_id,joined_at,last_seen_at) VALUES(?,?,?,?)", (int(room["id"]), int(user["id"]), now_iso, now_iso))
            conn.commit()
        else:
            cur.execute("UPDATE study_room_members SET last_seen_at=? WHERE room_id=? AND user_id=?", (now_iso, int(room["id"]), int(user["id"])))
            conn.commit()
        return {"room": room, "member_count": count if already else count + 1, "max_members": 4}
    finally:
        conn.close()


def _room_for_member(room_id: int, user_id: int) -> dict[str, Any]:
    conn=get_conn()
    try:
        cur=conn.cursor()
        cur.execute("SELECT r.* FROM study_rooms r JOIN study_room_members m ON m.room_id=r.id WHERE r.id=? AND m.user_id=? AND m.left_at IS NULL", (room_id,user_id))
        row=cur.fetchone()
        if not row:
            raise HTTPException(status_code=403, detail="Study-room membership required")
        return dict(row)
    finally: conn.close()


@router.get("/student/study-rooms/{room_id}/messages")
async def study_room_messages(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); now_iso = _now().isoformat()
        cur.execute("UPDATE study_room_members SET last_seen_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL", (now_iso, room_id, int(user["id"])))
        cur.execute("SELECT m.*, u.first_name, u.last_name, u.login_id FROM study_room_messages m LEFT JOIN users u ON u.id=m.sender_id WHERE m.room_id=? ORDER BY m.id ASC LIMIT 250", (room_id,))
        items=[]
        for row in _dicts(cur.fetchall()):
            try: row["attachments"]=json.loads(str(row.get("attachments_json") or "[]"))
            except Exception: row["attachments"]=[]
            items.append(row)
        conn.commit()
        return {"items":items}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/messages")
async def post_study_room_message(room_id: int, payload: StudyRoomMessage, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); now_iso = _now().isoformat()
        cur.execute("UPDATE study_room_members SET last_seen_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL", (now_iso, room_id, int(user["id"])))
        cur.execute("INSERT INTO study_room_messages(room_id,sender_id,body,attachments_json) VALUES(?,?,?,?)", (room_id,int(user["id"]),payload.body,json.dumps(payload.attachments)))
        conn.commit(); return {"id":int(cur.lastrowid or 0)}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/ping")
async def ping_study_room(room_id: int, authorization: str | None = Header(default=None)):
    """Heartbeat presence ping from active client in study room."""
    user = _user(authorization); _require(user, STUDY_ROOM_ROLES); ensure_schema(); conn = get_conn()
    try:
        cur = conn.cursor(); now_iso = _now().isoformat()
        cur.execute(
            "UPDATE study_room_members SET last_seen_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL",
            (now_iso, room_id, int(user["id"]))
        )
        _sweep_study_room_presence(cur, room_id)
        conn.commit()
        cur.execute("SELECT status FROM study_rooms WHERE id=?", (room_id,))
        row = cur.fetchone()
        status = str(dict(row).get("status") or "closed") if row else "closed"
        cur.execute("SELECT COUNT(*) as c FROM study_room_members WHERE room_id=? AND left_at IS NULL", (room_id,))
        cnt_row = cur.fetchone()
        active_count = int(dict(cnt_row)["c"]) if cnt_row else 0
        return {"ok": True, "closed": status == "closed", "active_members": active_count}
    finally:
        conn.close()


@router.post("/student/study-rooms/{room_id}/close")
async def close_study_room(room_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    _require(user, STUDY_ROOM_ROLES)
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT owner_id FROM study_rooms WHERE id=?", (room_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Study room topilmadi")
        if int(dict(row).get("owner_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=403, detail="Faqat xona egasi xonani yopa oladi")

        # 1. Clean up uploaded files from disk
        _cleanup_study_room_files(room_id, cur)

        # 2. Clean up rows from DB
        cur.execute("DELETE FROM study_room_materials WHERE room_id=?", (room_id,))
        cur.execute("DELETE FROM study_room_messages WHERE room_id=?", (room_id,))

        # 3. Mark room closed
        cur.execute(
            "UPDATE study_rooms SET status='closed', closed_at=? WHERE id=?",
            (_now().isoformat(), room_id),
        )
        conn.commit()
        return {"closed": True, "files_cleaned": True}
    finally:
        conn.close()


def _room_owner(room_id: int, user_id: int) -> dict[str, Any]:
    room = _room_for_member(room_id, user_id)
    if int(room.get("owner_id") or 0) != int(user_id):
        raise HTTPException(status_code=403, detail="Only room owner can manage this room")
    return room


@router.get("/student/study-rooms/{room_id}")
async def study_room_detail(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); now_iso = _now().isoformat()
        cur.execute(
            "UPDATE study_room_members SET last_seen_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL",
            (now_iso, room_id, int(user["id"]))
        )
        _sweep_study_room_presence(cur, room_id)
        conn.commit()

        cur.execute("SELECT * FROM study_rooms WHERE id=?", (room_id,))
        room_row = cur.fetchone()
        if not room_row:
            raise HTTPException(status_code=404, detail="Study room topilmadi")
        room = dict(room_row)
        if str(room.get("status") or "").lower() == "closed":
            return {"room": room, "members": [], "materials": [], "closed": True, "notice": "Study roomda hech kim qolmaganligi sababli xona avtomatik yopildi", "max_members": 4}

        cur.execute("SELECT 1 FROM study_room_members WHERE room_id=? AND user_id=? AND left_at IS NULL", (room_id, int(user["id"])))
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="Study-room membership required")

        cur.execute("SELECT m.user_id,m.joined_at,m.last_seen_at,u.first_name,u.last_name,u.login_id FROM study_room_members m JOIN users u ON u.id=m.user_id WHERE m.room_id=? AND m.left_at IS NULL ORDER BY m.joined_at", (room_id,))
        members=_dicts(cur.fetchall())
        cur.execute("SELECT * FROM study_room_materials WHERE room_id=? ORDER BY id DESC LIMIT 50", (room_id,))
        return {"room": room, "members": members, "materials": _dicts(cur.fetchall()), "max_members": 4, "closed": False}
    finally:
        conn.close()


@router.post("/student/study-rooms/{room_id}/regenerate-code")
async def regenerate_study_room_code(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); _room_owner(room_id,int(user["id"])); conn=get_conn()
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
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); _room_owner(room_id,int(user["id"])); conn=get_conn()
    try:
        if int(member_id) == int(user["id"]):
            raise HTTPException(status_code=422, detail="Owner should close the room instead")
        cur=conn.cursor(); cur.execute("UPDATE study_room_members SET left_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL", (_now().isoformat(),room_id,member_id))
        _sweep_study_room_presence(cur, room_id)
        conn.commit()
        return {"removed":cur.rowcount > 0}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/leave")
async def leave_study_room(room_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema()
    conn=get_conn()
    try:
        cur=conn.cursor()
        now_iso = _now().isoformat()
        cur.execute("SELECT * FROM study_rooms WHERE id=?", (room_id,))
        room_row = cur.fetchone()
        if not room_row:
            return {"left": True, "closed": True}
        room = dict(room_row)
        user_id = int(user["id"])
        is_owner = int(room.get("owner_id") or 0) == user_id

        # Mark caller left
        cur.execute("UPDATE study_room_members SET left_at=? WHERE room_id=? AND user_id=? AND left_at IS NULL", (now_iso, room_id, user_id))

        # Check remaining active members (active in last 10s)
        cutoff = (_now() - timedelta(seconds=10)).isoformat()
        cur.execute(
            "SELECT user_id FROM study_room_members WHERE room_id=? AND left_at IS NULL AND ((last_seen_at IS NOT NULL AND last_seen_at >= ?) OR (last_seen_at IS NULL AND joined_at >= ?)) ORDER BY joined_at ASC",
            (room_id, cutoff, cutoff)
        )
        remaining = _dicts(cur.fetchall())

        if not remaining:
            # Nobody left -> auto close immediately!
            _cleanup_study_room_files(room_id, cur)
            cur.execute("DELETE FROM study_room_materials WHERE room_id=?", (room_id,))
            cur.execute("DELETE FROM study_room_messages WHERE room_id=?", (room_id,))
            cur.execute("UPDATE study_rooms SET status='closed', closed_at=? WHERE id=?", (now_iso, room_id))
            conn.commit()
            return {"left": True, "closed": True}
        else:
            if is_owner:
                new_owner_id = int(remaining[0]["user_id"])
                cur.execute("UPDATE study_rooms SET owner_id=? WHERE id=?", (new_owner_id, room_id))
            conn.commit()
            return {"left": True, "closed": False}
    finally:
        conn.close()


@router.post("/student/study-rooms/{room_id}/materials")
async def add_study_room_material(room_id: int, payload: StudyRoomMaterial, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("INSERT INTO study_room_materials(room_id,uploaded_by,title,file_url,mime_type,extracted_text) VALUES(?,?,?,?,?,?)", (room_id,int(user["id"]),payload.title,payload.file_url,payload.mime_type,payload.extracted_text)); conn.commit()
        return {"id":int(cur.lastrowid or 0)}
    finally: conn.close()


@router.post("/student/study-rooms/{room_id}/voice-room")
async def create_study_room_voice(room_id: int, authorization: str | None = Header(default=None)):
    """Create a private WebRTC room; the established websocket validates
    study-room membership before admitting a peer."""
    # Any active member may start the shared call. Membership is checked again
    # by the WebRTC websocket, therefore a room code alone never grants voice
    # access and an owner being offline does not block the group.
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); room=_room_for_member(room_id,int(user["id"])); conn=get_conn()
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
    user=_user(authorization); _require(user,STUDY_ROOM_ROLES); ensure_schema(); _room_for_member(room_id,int(user["id"])); conn=get_conn()
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


def get_users_selected_badges(user_ids: list[int]) -> dict[int, dict[str, Any]]:
    clean_ids = [int(u) for u in user_ids if int(u or 0) > 0]
    if not clean_ids:
        return {}
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        ph = ",".join("?" for _ in clean_ids)
        cur.execute(
            f"""
            SELECT sb.user_id, sb.badge_code, sb.selected, bd.title, bd.description, bd.asset_url
            FROM student_badges sb
            JOIN badge_definitions bd ON bd.code = sb.badge_code
            WHERE sb.user_id IN ({ph}) AND bd.active = 1
            ORDER BY sb.selected DESC, sb.unlocked_at DESC
            """,
            clean_ids,
        )
        res: dict[int, dict[str, Any]] = {}
        for r in cur.fetchall() or []:
            row = dict(r)
            uid = int(row.get("user_id") or 0)
            if uid not in res or int(row.get("selected") or 0) == 1:
                res[uid] = {
                    "code": str(row.get("badge_code") or ""),
                    "title": str(row.get("title") or ""),
                    "description": str(row.get("description") or ""),
                    "asset_url": str(row.get("asset_url") or ""),
                }
        return res
    finally:
        conn.close()


def get_user_badges_and_certificates(user_id: int) -> dict[str, Any]:
    uid = int(user_id)
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        _sync_student_badges(cur, uid)
        conn.commit()
        cur.execute(
            "SELECT *, course_title AS title, ('/certificates/' || certificate_id || '/pdf') AS pdf_url FROM certificates WHERE user_id=? ORDER BY issued_at DESC",
            (uid,),
        )
        certificates = _dicts(cur.fetchall())
        cur.execute(
            """
            SELECT d.code AS id, d.code, d.title, d.description, d.asset_url,
                   CASE WHEN b.user_id IS NULL THEN 0 ELSE 1 END AS unlocked,
                   COALESCE(b.selected, 0) AS selected
            FROM badge_definitions d
            LEFT JOIN student_badges b ON b.badge_code = d.code AND b.user_id = ?
            WHERE d.active = 1
            ORDER BY d.code
            """,
            (uid,),
        )
        badges = _dicts(cur.fetchall())
        selected = next((x for x in badges if int(x.get("selected") or 0) == 1), None)
        if not selected:
            unlocked = next((x for x in badges if int(x.get("unlocked") or 0) == 1), None)
            if unlocked:
                cur.execute("UPDATE student_badges SET selected = 1 WHERE user_id = ? AND badge_code = ?", (uid, unlocked["code"]))
                conn.commit()
                unlocked["selected"] = 1
                selected = unlocked
        return {
            "certificates": certificates,
            "badges": badges,
            "selected_badge": selected,
            "selected_badge_id": selected.get("id") if selected else None,
            "badge_asset_url": selected.get("asset_url") if selected else None,
            "badge_title": selected.get("title") if selected else None,
        }
    finally:
        conn.close()


@router.get("/student/portfolio")
async def portfolio(authorization: str | None = Header(default=None)):
    user = _user(authorization)
    _require(user, {"student"})
    return get_user_badges_and_certificates(int(user["id"]))


class BadgeSelectRequest(BaseModel):
    badge_id: str | None = Field(default=None, max_length=120)


@router.put("/student/portfolio/badge")
async def select_portfolio_badge(payload: BadgeSelectRequest, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    _require(user, {"student"})
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        uid = int(user["id"])
        target_code = (payload.badge_id or "").strip()
        cur.execute("UPDATE student_badges SET selected=0 WHERE user_id=?", (uid,))
        if target_code and target_code.lower() not in {"null", "none"}:
            cur.execute("SELECT 1 FROM student_badges WHERE user_id=? AND badge_code=?", (uid, target_code))
            if not cur.fetchone():
                raise HTTPException(status_code=403, detail="Badge is not unlocked")
            cur.execute("UPDATE student_badges SET selected=1 WHERE user_id=? AND badge_code=?", (uid, target_code))
            conn.commit()
            return {"selected_badge_id": target_code}
        conn.commit()
        return {"selected_badge_id": None}
    finally:
        conn.close()


@router.get("/student/badges/unseen")
async def get_unseen_badges(authorization: str | None = Header(default=None)):
    """Check and return badges the student has newly earned but hasn't seen celebration for yet."""
    user = _user(authorization)
    _require(user, {"student"})
    ensure_schema()
    uid = int(user["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        _sync_student_badges(cur, uid)
        conn.commit()
        cur.execute(
            """
            SELECT b.badge_code AS code, d.title, d.description, d.asset_url, b.earned_at
            FROM student_badges b
            JOIN badge_definitions d ON d.code = b.badge_code
            WHERE b.user_id = ? AND COALESCE(b.notified, 0) = 0
            ORDER BY b.earned_at DESC
            """,
            (uid,),
        )
        items = _dicts(cur.fetchall())
        return {"unseen_badges": items, "has_new": len(items) > 0}
    finally:
        conn.close()


class MarkBadgesSeenRequest(BaseModel):
    badge_codes: list[str] | None = None


@router.post("/student/badges/mark-seen")
async def mark_badges_seen(payload: MarkBadgesSeenRequest | None = None, authorization: str | None = Header(default=None)):
    """Mark newly unlocked badges as seen/notified."""
    user = _user(authorization)
    _require(user, {"student"})
    ensure_schema()
    uid = int(user["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        if payload and payload.badge_codes:
            ph = ",".join("?" for _ in payload.badge_codes)
            cur.execute(f"UPDATE student_badges SET notified=1 WHERE user_id=? AND badge_code IN ({ph})", [uid, *payload.badge_codes])
        else:
            cur.execute("UPDATE student_badges SET notified=1 WHERE user_id=?", (uid,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


BADGES_DIR = Path(__file__).resolve().parent.parent / "public" / "badges"


@router.get("/badges/{filename}")
@router.get("/api/badges/{filename}")
async def serve_badge_file(filename: str):
    clean_name = Path(filename).name
    file_path = BADGES_DIR / clean_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Badge asset not found")
    return FileResponse(file_path, media_type="image/png")


# ── Learning Paths / Duolingo-style tracks ──────────────────────────────────
LEARNING_MANAGER_ROLES = {"teacher", "support", "admin"}
LEARNING_COVERS = {"star", "chest", "dolphin", "jellyfish", "ship", "trophy"}


class LearningTrackRequest(BaseModel):
    # The server derives this from the teacher profile when omitted.
    subject: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    cover_key: str = Field(default="star", max_length=30)
    position: int = Field(default=0, ge=0, le=10000)
    # Created once as 70; subsequent edits are explicit teacher settings.
    passing_score: int | None = Field(default=None, ge=1, le=100)
    certificate_template_key: str | None = Field(default=None, pattern="^(english|russian)$")
    certificate_layers: list[dict[str, Any]] = Field(default_factory=list, max_length=24)


class LearningTrackUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    cover_key: str | None = Field(default=None, max_length=30)
    position: int | None = Field(default=None, ge=0, le=10000)
    passing_score: int | None = Field(default=None, ge=1, le=100)
    status: str | None = Field(default=None, pattern="^(draft|published|archived)$")
    certificate_template_key: str | None = Field(default=None, pattern="^(english|russian)$")
    certificate_layers: list[dict[str, Any]] | None = Field(default=None, max_length=24)


class LearningModuleRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    cover_key: str = Field(default="star", max_length=100)
    image_url: str | None = Field(default=None, max_length=2000)
    position: int = Field(default=0, ge=0, le=10000)
    topic_keys: list[str] = Field(default_factory=list, max_length=12)
    passing_score: int | None = Field(default=None, ge=1, le=100)
    reward_coins: int = Field(default=0, ge=0, le=10000)


class LearningModuleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    cover_key: str | None = Field(default=None, max_length=100)
    image_url: str | None = Field(default=None, max_length=2000)
    topic_keys: list[str] | None = Field(default=None, max_length=12)
    passing_score: int | None = Field(default=None, ge=1, le=100)
    reward_coins: int | None = Field(default=None, ge=0, le=10000)


class LearningLessonRequest(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    source_kind: str = Field(default="manual", pattern="^(manual|library|homework|ai)$")
    source_id: str | None = Field(default=None, max_length=120)
    source_version: str | None = Field(default=None, max_length=80)
    question_payload: dict[str, Any] | None = None
    test_type: str = Field(default="multiple_choice", max_length=40)
    question_count: int = Field(default=1, ge=1, le=50)
    duration_seconds: int = Field(default=0, ge=0, le=7200)
    position: int = Field(default=0, ge=0, le=10000)
    required: bool = True


class LearningAiLessonRequest(BaseModel):
    topic: str = Field(min_length=2, max_length=160)
    level: str | None = Field(default=None, max_length=80)
    instruction: str | None = Field(default=None, max_length=1000)
    question_count: int = Field(default=1, ge=1, le=30)
    test_types: list[str] = Field(
        default_factory=lambda: ["multiple_choice", "true_false", "fill_blank", "word_order", "matching"],
        max_length=12,
    )


class LearningLibraryTestAttachRequest(BaseModel):
    content_type: str = Field(pattern="^(video|book|homework|ai_generated|teacher_library|library_node|test)$")
    content_id: int = Field(gt=0)
    question_count: int | None = Field(default=None, ge=0, le=1000)


class LearningAssignRequest(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=1000)
    due_at: str | None = Field(default=None, max_length=64)


class LearningLessonSubmit(BaseModel):
    score: float = Field(ge=0, le=100)
    answers: list[Any] = Field(default_factory=list, max_length=200)


class LearningLessonAiCheckRequest(BaseModel):
    lesson_id: int | None = None
    question_payload: dict[str, Any] | None = None
    answer_text: str | None = None
    audio_url: str | None = None
    subject: str | None = None


def _learning_track_for_manager(track_id: int, user: dict[str, Any]) -> dict[str, Any]:
    conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT * FROM learning_tracks WHERE id=?", (track_id,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Learning track not found")
        track=dict(row)
        if _role(user) != "admin" and int(track.get("owner_id") or 0) != int(user["id"]):
            raise HTTPException(status_code=403, detail="Only the track owner can manage this track")
        return track
    finally: conn.close()


def _learning_track_subject(user: dict[str, Any], requested: str | None) -> str:
    """Use the manager's configured subject without making the UI ask again."""
    explicit = str(requested or "").strip()
    if explicit:
        return explicit[:80]
    for key in ("subject", "primary_subject", "teacher_subject"):
        value = str(user.get(key) or "").strip()
        if value:
            return value[:80]
    raw = user.get("subjects") or user.get("subjects_json") or []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = [raw]
    if isinstance(raw, (list, tuple)):
        for value in raw:
            text = str(value or "").strip()
            if text:
                return text[:80]
    # Admin users can be cross-subject; teachers are resolved from profile.
    return "General"


def _certificate_template_for_subject(subject: str, requested: str | None) -> str:
    if requested in {"english", "russian"}:
        return requested
    normalized = str(subject or "").lower()
    return "russian" if any(token in normalized for token in ("russian", "russ", "рус", "rus")) else "english"


def _learning_track_payload(cur: Any, track: dict[str, Any], student_id: int | None = None) -> dict[str, Any]:
    result=dict(track)
    try: result["certificate_layers"] = json.loads(str(track.get("certificate_layers_json") or "[]"))
    except Exception: result["certificate_layers"] = []
    cur.execute("SELECT * FROM learning_modules WHERE track_id=? ORDER BY position,id", (int(track["id"]),))
    modules=[]
    for module in _dicts(cur.fetchall()):
        try: raw_t_keys = json.loads(str(module.get("topic_keys_json") or "[]"))
        except Exception: raw_t_keys = []
        module["topic_keys"] = (raw_t_keys if isinstance(raw_t_keys, list) else [])
        cur.execute("SELECT id,title,source_kind,source_id,question_payload_json,duration_seconds,position,required FROM learning_module_lessons WHERE module_id=? ORDER BY position,id", (int(module["id"]),))
        lessons = []
        for l_row in _dicts(cur.fetchall()):
            try:
                l_row["question_payload"] = json.loads(str(l_row.pop("question_payload_json", None) or "{}"))
            except Exception:
                l_row["question_payload"] = {}
            l_row["passed"] = False
            l_row["best_score"] = 0.0
            lessons.append(l_row)
        module["lessons"] = lessons
        # Ensure image_url, icon_url and cover_key are always populated for Web & Mobile
        cover_k = str(module.get("cover_key") or "star")
        if cover_k not in LEARNING_COVERS:
            cover_k = "star"
        rel_url = f"/learning-paths/{cover_k}.png"
        full_url = f"https://diamond-education.uz/learning-paths/{cover_k}.png"
        module["cover_key"] = cover_k
        module["image_url"] = rel_url
        module["icon_url"] = full_url
        module["image_full_url"] = full_url
        if student_id:
            cur.execute("SELECT status,best_score,passed_at FROM learning_module_progress WHERE module_id=? AND student_id=?", (int(module["id"]), int(student_id)))
            progress = cur.fetchone()
            if progress:
                p_dict = dict(progress)
                if p_dict.get("passed_at") is not None:
                    p_dict["status"] = "passed"
                module["progress"] = p_dict
            else:
                module["progress"] = {"status": "locked", "best_score": 0}
            if lessons:
                lesson_ids = [l["id"] for l in lessons]
                ph = ",".join("?" for _ in lesson_ids)
                cur.execute(f"SELECT lesson_id, MAX(score) as best_score, MAX(CASE WHEN passed=1 THEN 1 ELSE 0 END) as passed FROM learning_lesson_attempts WHERE student_id=? AND lesson_id IN ({ph}) GROUP BY lesson_id", [student_id] + lesson_ids)
                attempts_by_lid = {int(r["lesson_id"]): dict(r) for r in _dicts(cur.fetchall())}
                for l in lessons:
                    att = attempts_by_lid.get(int(l["id"]), {})
                    l["passed"] = bool(att.get("passed"))
                    l["best_score"] = float(att.get("best_score") or 0)
        else:
            module["progress"] = {"status": "unlocked", "best_score": 0}

        # Determine total_topics and completed_topics for segmented circular ring
        # Topics are strictly defined by topic_keys (mavzular). Lessons are question/test tasks.
        mod_status = str((module.get("progress") or {}).get("status") or "locked").lower()
        topic_keys = [str(t).strip() for t in (module.get("topic_keys") or []) if str(t).strip()]
        total_topics = max(1, len(topic_keys)) if topic_keys else max(1, len(lessons))

        if mod_status == "passed":
            completed_topics = total_topics
        elif total_topics > 1 and len(lessons) > 0:
            passed_lessons = sum(1 for l in lessons if l.get("passed"))
            if len(lessons) == total_topics:
                completed_topics = min(total_topics, max(0, passed_lessons))
            else:
                completed_topics = min(total_topics - 1, int((passed_lessons / len(lessons)) * total_topics))
        else:
            completed_topics = 0

        module["total_topics"] = total_topics
        module["completed_topics"] = completed_topics
        module["current_topic_index"] = min(completed_topics, max(0, total_topics - 1))
        modules.append(module)
    result["modules"]=modules
    return result


@router.get("/staff/learning-tracks")
async def staff_learning_tracks(authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor()
        if _role(user) == "admin": cur.execute("SELECT * FROM learning_tracks ORDER BY subject,position,id")
        else: cur.execute("SELECT * FROM learning_tracks WHERE owner_id=? ORDER BY subject,position,id", (int(user["id"]),))
        return {"items":[_learning_track_payload(cur, row) for row in _dicts(cur.fetchall())], "default_passing_score":DEFAULT_TRACK_PASSING_SCORE, "covers":sorted(LEARNING_COVERS)}
    finally: conn.close()


@router.post("/staff/learning-tracks")
async def create_learning_track(payload: LearningTrackRequest, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); subject=_learning_track_subject(user, payload.subject)
        passing=normalize_track_passing_score(payload.passing_score)
        cover=payload.cover_key if payload.cover_key in LEARNING_COVERS else "star"
        cur.execute("INSERT INTO learning_tracks(owner_id,subject,title,description,cover_key,position,passing_score,certificate_template_key,certificate_layers_json,status,published_at) VALUES(?,?,?,?,?,?,?,?,?,'published',?)",
            (int(user["id"]), subject, payload.title, payload.description, cover, payload.position, passing, payload.certificate_template_key, json.dumps(payload.certificate_layers, ensure_ascii=False), _now().isoformat()))
        conn.commit(); return {"id":int(cur.lastrowid or 0)}
    finally: conn.close()


@router.patch("/staff/learning-tracks/{track_id}")
async def update_learning_track(track_id: int, payload: LearningTrackUpdate, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); _learning_track_for_manager(track_id, user); conn=get_conn()
    try:
        cur=conn.cursor(); values=payload.model_dump(exclude_unset=True)
        if not values: return {"id":track_id}
        sets=[]; params=[]
        for key,value in values.items():
            if key=="certificate_layers": key,value="certificate_layers_json",json.dumps(value,ensure_ascii=False)
            if key=="cover_key": value=value if value in LEARNING_COVERS else "star"
            if key=="passing_score": value=normalize_track_passing_score(value)
            sets.append(f"{key}=?"); params.append(value)
        sets.append("updated_at=?"); params.append(_now().isoformat())
        params.append(track_id)
        cur.execute(f"UPDATE learning_tracks SET {','.join(sets)} WHERE id=?", params); conn.commit()
        return {"id":track_id, "updated":True}
    finally: conn.close()


@router.delete("/staff/learning-tracks/{track_id}")
async def delete_learning_track(track_id: int, authorization: str | None = Header(default=None)):
    """Delete a track and all its modules, lessons, assignments and progress.

    Student test-history and mistake-notebook records are intentionally
    preserved so that academic history is never lost.
    """
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); _learning_track_for_manager(track_id, user); conn=get_conn()
    try:
        cur=conn.cursor()
        cur.execute("SELECT id FROM learning_modules WHERE track_id=? ORDER BY position, id", (track_id,))
        module_ids=[int(dict(r)["id"]) for r in cur.fetchall()]
        if module_ids:
            ph=",".join("?" for _ in module_ids)
            cur.execute(f"SELECT id FROM learning_module_lessons WHERE module_id IN ({ph})", module_ids)
            lesson_ids=[int(dict(r)["id"]) for r in cur.fetchall()]
            if lesson_ids:
                lph=",".join("?" for _ in lesson_ids)
                cur.execute(f"DELETE FROM learning_lesson_attempts WHERE lesson_id IN ({lph})", lesson_ids)
            cur.execute(f"DELETE FROM learning_module_progress WHERE module_id IN ({ph})", module_ids)
            cur.execute(f"DELETE FROM learning_module_lessons WHERE module_id IN ({ph})", module_ids)
        cur.execute("DELETE FROM learning_track_assignments WHERE track_id=?", (track_id,))
        cur.execute("DELETE FROM learning_modules WHERE track_id=?", (track_id,))
        cur.execute("DELETE FROM learning_tracks WHERE id=?", (track_id,))
        conn.commit()
        return {"deleted": True, "track_id": track_id}
    finally: conn.close()


@router.post("/staff/learning-tracks/{track_id}/modules")
async def add_learning_module(track_id: int, payload: LearningModuleRequest, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); _learning_track_for_manager(track_id,user); conn=get_conn()
    try:
        cur=conn.cursor(); cover=payload.cover_key if payload.cover_key in LEARNING_COVERS else "star"
        # Enforce consecutive uniqueness: cannot have the exact same cover as immediate previous module
        cur.execute("SELECT cover_key FROM learning_modules WHERE track_id=? ORDER BY position DESC, id DESC LIMIT 1", (track_id,))
        last_mod = cur.fetchone()
        if last_mod and str(dict(last_mod).get("cover_key") or "") == cover:
            available = [c for c in sorted(LEARNING_COVERS) if c != cover]
            if available: cover = available[0]
        passing=normalize_track_passing_score(payload.passing_score)
        clean_topics = (payload.topic_keys if isinstance(payload.topic_keys, list) else [])[:5]
        cur.execute("INSERT INTO learning_modules(track_id,title,description,cover_key,position,topic_keys_json,passing_score,reward_coins) VALUES(?,?,?,?,?,?,?,?)",(track_id,payload.title,payload.description,cover,payload.position,json.dumps(clean_topics,ensure_ascii=False),passing,payload.reward_coins)); conn.commit(); return {"id":int(cur.lastrowid or 0)}
    finally: conn.close()


@router.patch("/staff/learning-modules/{module_id}")
async def update_learning_module(module_id: int, payload: LearningModuleUpdate, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT track_id FROM learning_modules WHERE id=?", (module_id,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Learning module not found")
        track_id = int(dict(row)["track_id"])
        _learning_track_for_manager(track_id, user)
        values=payload.model_dump(exclude_unset=True)
        if not values: return {"id":module_id}
        if "cover_key" in values and values["cover_key"]:
            requested_cover = values["cover_key"] if values["cover_key"] in LEARNING_COVERS else "star"
            cur.execute("SELECT id, cover_key FROM learning_modules WHERE track_id=? ORDER BY position, id", (track_id,))
            all_mods = _dicts(cur.fetchall())
            mod_idx = next((i for i, m in enumerate(all_mods) if int(m["id"]) == module_id), -1)
            prev_cover = all_mods[mod_idx - 1]["cover_key"] if mod_idx > 0 else None
            next_cover = all_mods[mod_idx + 1]["cover_key"] if mod_idx >= 0 and mod_idx < len(all_mods) - 1 else None
            if requested_cover in (prev_cover, next_cover):
                available = [c for c in sorted(LEARNING_COVERS) if c != prev_cover and c != next_cover]
                if available: requested_cover = available[0]
            values["cover_key"] = requested_cover
        sets=[]; params=[]
        for key,value in values.items():
            if key == "topic_keys":
                clean_topics = (value if isinstance(value, list) else [])[:5]
                key,value="topic_keys_json",json.dumps(clean_topics,ensure_ascii=False)
            if key == "passing_score": value=normalize_track_passing_score(value)
            sets.append(f"{key}=?"); params.append(value)
        sets.append("updated_at=?"); params.append(_now().isoformat()); params.append(module_id)
        cur.execute(f"UPDATE learning_modules SET {','.join(sets)} WHERE id=?", params); conn.commit(); return {"id":module_id,"updated":True}
    finally: conn.close()


@router.delete("/staff/learning-modules/{module_id}")
async def delete_learning_module(module_id: int, authorization: str | None = Header(default=None)):
    """Delete one module and only its dependent learning-path records.

    This is intentionally owner-scoped.  Existing test-history and mistake
    notebook records are not removed, so a teacher changing a path cannot
    erase a student's broader academic history.
    """
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT track_id FROM learning_modules WHERE id=?", (module_id,)); row=cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Learning module not found")
        _learning_track_for_manager(int(dict(row)["track_id"]), user)
        cur.execute("SELECT id FROM learning_module_lessons WHERE module_id=?", (module_id,)); lesson_ids=[int(dict(item)["id"]) for item in cur.fetchall()]
        if lesson_ids:
            placeholders=",".join("?" for _ in lesson_ids)
            cur.execute(f"DELETE FROM learning_lesson_attempts WHERE lesson_id IN ({placeholders})", lesson_ids)
        cur.execute("DELETE FROM learning_module_progress WHERE module_id=?", (module_id,))
        cur.execute("DELETE FROM learning_module_lessons WHERE module_id=?", (module_id,))
        cur.execute("DELETE FROM learning_modules WHERE id=?", (module_id,))
        conn.commit()
        return {"deleted": True, "module_id": module_id}
    finally: conn.close()


@router.post("/staff/learning-modules/{module_id}/lessons")
async def add_learning_lesson(module_id: int, payload: LearningLessonRequest, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT track_id FROM learning_modules WHERE id=?",(module_id,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Learning module not found")
        _learning_track_for_manager(int(dict(row)["track_id"]),user)
        if payload.source_kind in {"manual","ai"} and not payload.question_payload: raise HTTPException(status_code=422,detail="Manual or AI lesson needs a question payload")
        cur.execute("INSERT INTO learning_module_lessons(module_id,title,source_kind,source_id,source_version,question_payload_json,duration_seconds,position,required) VALUES(?,?,?,?,?,?,?,?,?)",(module_id,payload.title,payload.source_kind,payload.source_id,payload.source_version,json.dumps(payload.question_payload,ensure_ascii=False) if payload.question_payload else None,payload.duration_seconds,payload.position,1 if payload.required else 0)); conn.commit(); return {"id":int(cur.lastrowid or 0)}
    finally: conn.close()


class LearningLessonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=180)
    question_payload: dict[str, Any] | None = None
    position: int | None = Field(default=None, ge=0, le=10000)
    required: bool | None = None


class LearningLessonBatchRequest(BaseModel):
    items: list[LearningLessonRequest] = Field(min_length=1, max_length=100)


@router.post("/staff/learning-modules/{module_id}/lessons/batch")
async def add_learning_lessons_batch(module_id: int, payload: LearningLessonBatchRequest, authorization: str | None = Header(default=None)):
    """Append a complete editor/AI draft atomically, preserving library fields."""
    user = _user(authorization)
    _require(user, LEARNING_MANAGER_ROLES)
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT track_id FROM learning_modules WHERE id=?", (module_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Learning module not found")
        _learning_track_for_manager(int(dict(row)["track_id"]), user)
        questions = []
        for item in payload.items:
            if not item.question_payload:
                raise HTTPException(status_code=422, detail="Question payload is required")
            questions.append(_learning_library_question(item.question_payload))
        cur.execute("SELECT MAX(position) AS value FROM learning_module_lessons WHERE module_id=?", (module_id,))
        last = dict(cur.fetchone() or {}).get("value")
        position = int(last) + 1 if last is not None else 0
        created = []
        for item, question in zip(payload.items, questions):
            cur.execute(
                "INSERT INTO learning_module_lessons(module_id,title,source_kind,source_id,source_version,question_payload_json,duration_seconds,position,required) VALUES(?,?,?,?,?,?,?,?,?)",
                (module_id, item.title, item.source_kind, item.source_id,
                 question["test_type"], json.dumps(question, ensure_ascii=False),
                 item.duration_seconds, position, 1 if item.required else 0),
            )
            created.append(int(cur.lastrowid or 0))
            position += 1
        conn.commit()
        return {"created_lesson_ids": created, "question_count": len(created)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/staff/learning-lessons/{lesson_id}")
async def update_learning_lesson(lesson_id: int, payload: LearningLessonUpdate, authorization: str | None = Header(default=None)):
    """Edit an existing lesson/test in a learning module."""
    user = _user(authorization)
    _require(user, LEARNING_MANAGER_ROLES)
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT l.id, l.module_id, m.track_id FROM learning_module_lessons l JOIN learning_modules m ON m.id=l.module_id WHERE l.id=?", (lesson_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dars topilmadi")
        track_id = int(dict(row)["track_id"])
        _learning_track_for_manager(track_id, user)

        updates = []
        params = []
        if payload.title is not None:
            updates.append("title=?")
            params.append(payload.title.strip())
        if payload.question_payload is not None:
            updates.append("question_payload_json=?")
            params.append(json.dumps(_learning_library_question(payload.question_payload), ensure_ascii=False))
        if payload.position is not None:
            updates.append("position=?")
            params.append(payload.position)
        if payload.required is not None:
            updates.append("required=?")
            params.append(1 if payload.required else 0)

        if updates:
            params.append(lesson_id)
            cur.execute(f"UPDATE learning_module_lessons SET {', '.join(updates)} WHERE id=?", params)
            conn.commit()

        return {"updated": True, "lesson_id": lesson_id}
    finally:
        conn.close()


@router.delete("/staff/learning-lessons/{lesson_id}")
async def delete_learning_lesson(lesson_id: int, authorization: str | None = Header(default=None)):
    """Delete a single lesson/test from a learning module."""
    user = _user(authorization)
    _require(user, LEARNING_MANAGER_ROLES)
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT l.id, l.module_id, m.track_id FROM learning_module_lessons l JOIN learning_modules m ON m.id=l.module_id WHERE l.id=?", (lesson_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Dars topilmadi")
        track_id = int(dict(row)["track_id"])
        _learning_track_for_manager(track_id, user)

        cur.execute("DELETE FROM learning_module_lessons WHERE id=?", (lesson_id,))
        conn.commit()
        return {"deleted": True, "lesson_id": lesson_id}
    finally:
        conn.close()


def _normalize_subject_label(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    low = raw.lower()
    if low in {"english", "eng", "ingliz", "en", "ielts", "cefr"}:
        return "English"
    if low in {"russian", "rus", "ru", "русский", "russian language"}:
        return "Russian"
    if low in {"matematika", "math", "mathematics"}:
        return "Matematika"
    if low in {"ona tili", "ona_tili", "uzbek", "o'zbek tili", "oʻzbek tili"}:
        return "Ona tili"
    if low in {"tarix", "history"}:
        return "Tarix"
    if low in {"arab tili", "arabic"}:
        return "Arab tili"
    if low in {"fizika", "physics"}:
        return "Fizika"
    if low in {"kimyo", "chemistry"}:
        return "Kimyo"
    if low in {"biologiya", "biology"}:
        return "Biologiya"
    if low in {"geografiya", "geography"}:
        return "Geografiya"
    if low in {"informatika", "computer science", "it"}:
        return "Informatika"
    return raw.strip().title()


def _detect_subject_language(subject: str | None) -> str:
    """Return 'ru', 'en', or 'uz' based on the subject."""
    s = str(subject or "").strip().lower()
    if any(k in s for k in ("rus", "рус")):
        return "ru"
    if any(k in s for k in ("eng", "ingliz", "ielts", "cefr")):
        return "en"
    return "uz"


def _extract_node_questions(payload_obj: Any) -> list[dict]:
    if isinstance(payload_obj, list):
        return [q for q in payload_obj if isinstance(q, dict)]
    if isinstance(payload_obj, dict):
        for key in ("questions", "items", "test_questions", "quiz"):
            val = payload_obj.get(key)
            if isinstance(val, list):
                return [q for q in val if isinstance(q, dict)]
    return []


def _teacher_allowed_subjects(user: dict[str, Any]) -> list[str]:
    uid = int(user.get("id") or 0)
    allowed: list[str] = []
    try:
        from main import _teacher_manageable_groups
        groups = _safe_call(lambda: _teacher_manageable_groups(uid), []) or []
        for g in groups:
            s = _normalize_subject_label(str(g.get("subject") or ""))
            if s and s not in allowed:
                allowed.append(s)
    except Exception:
        pass
    raw_s = str(user.get("subject") or "")
    for part in raw_s.split(","):
        s = _normalize_subject_label(part.strip())
        if s and s not in allowed:
            allowed.append(s)
    return allowed or ["English"]


def save_to_question_bank(
    subject: str,
    topic: str,
    questions: list[dict[str, Any]],
    difficulty: str = "medium",
) -> int:
    """Save generated questions into ai_generated_questions_bank to prevent duplicate generations."""
    if not questions:
        return 0
    clean_sub = _normalize_subject_label(subject) or "English"
    clean_top = str(topic or "").strip()
    if not clean_top:
        return 0
    ensure_schema()
    conn = get_conn()
    saved = 0
    try:
        cur = conn.cursor()
        for q in questions:
            if not isinstance(q, dict):
                continue
            q_text = str(q.get("question") or q.get("prompt") or "").strip()
            if not q_text:
                continue
            cur.execute(
                "SELECT id FROM ai_generated_questions_bank WHERE subject=? AND topic=? AND question_text=? LIMIT 1",
                (clean_sub, clean_top, q_text),
            )
            if cur.fetchone():
                continue
            opts = q.get("options") or []
            opts_json = json.dumps(opts, ensure_ascii=False) if isinstance(opts, list) else "[]"
            corr = str(q.get("correct_answer") or q.get("correct") or "")
            exp = str(q.get("explanation") or "")
            t_type = str(q.get("test_type") or "multiple_choice")
            cur.execute(
                """
                INSERT INTO ai_generated_questions_bank(
                    subject, topic, difficulty, question_text, options_json, correct_answer, explanation, test_type, use_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (clean_sub, clean_top, difficulty, q_text, opts_json, corr, exp, t_type),
            )
            saved += 1
        conn.commit()
    except Exception:
        logger.exception("Failed to save questions to bank")
    finally:
        conn.close()
    return saved


def get_questions_from_bank(
    subject: str,
    topic: str,
    count: int = 10,
    difficulty: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve least-used questions from the question bank."""
    clean_sub = _normalize_subject_label(subject) or "English"
    clean_top = str(topic or "").strip().lower()
    if not clean_top:
        return []
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, subject, topic, difficulty, question_text, options_json, correct_answer, explanation, test_type, use_count
            FROM ai_generated_questions_bank
            WHERE (LOWER(subject) = LOWER(?) OR subject = '')
              AND (LOWER(topic) LIKE ? OR ? LIKE '%' || LOWER(topic) || '%')
            ORDER BY use_count ASC, RANDOM()
            LIMIT ?
            """,
            (clean_sub, f"%{clean_top}%", clean_top, max(1, min(100, count))),
        )
        rows = _dicts(cur.fetchall())
        if not rows:
            return []
        ids = [int(r["id"]) for r in rows]
        if ids:
            ph = ",".join("?" for _ in ids)
            cur.execute(f"UPDATE ai_generated_questions_bank SET use_count = use_count + 1 WHERE id IN ({ph})", ids)
            conn.commit()
        result = []
        for r in rows:
            try:
                opts = json.loads(str(r.get("options_json") or "[]"))
            except Exception:
                opts = []
            result.append({
                "question": r.get("question_text") or "",
                "options": opts,
                "correct": r.get("correct_answer") or "",
                "correct_answer": r.get("correct_answer") or "",
                "explanation": r.get("explanation") or "",
                "topic": r.get("topic") or clean_top,
                "difficulty": r.get("difficulty") or "medium",
                "test_type": r.get("test_type") or "multiple_choice",
            })
        return result
    except Exception:
        logger.exception("Failed to get questions from bank")
        return []
    finally:
        conn.close()


def get_total_question_bank_count() -> int:
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS total FROM ai_generated_questions_bank")
        row = cur.fetchone()
        return int((dict(row) if row else {}).get("total") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def _learning_visible_library_ids(user: dict[str, Any]) -> set[int] | None:
    if _role(user) in {"admin", "superadmin"}:
        return None
    from db import list_library_nodes
    return {int(node["id"]) for node in list_library_nodes(int(user["id"])).get("nodes", [])}


@router.get("/staff/teacher-library-tree")
async def staff_teacher_library_tree(authorization: str | None = Header(default=None)):
    """Fetch teacher library folders and test nodes for attaching to learning modules, isolated strictly to the teacher's subject."""
    user = _user(authorization)
    _require(user, LEARNING_MANAGER_ROLES)
    ensure_schema()
    conn = get_conn()
    role = _role(user)
    allowed_subs = [s.lower() for s in _teacher_allowed_subjects(user)] if role == "teacher" else None
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, parent_id, owner_id, kind, title, description, subject, level, payload_json FROM library_nodes WHERE kind IN ('folder', 'test') ORDER BY sort_order ASC, id ASC")
        raw_rows = _dicts(cur.fetchall())
        visible_ids = _learning_visible_library_ids(user)
        if visible_ids is not None:
            raw_rows = [row for row in raw_rows if int(row["id"]) in visible_ids]
        all_nodes = []
        for r in raw_rows:
            try:
                p_obj = json.loads(str(r.pop("payload_json", None) or "{}"))
            except Exception:
                p_obj = {}
            qs = _extract_node_questions(p_obj)
            all_nodes.append({
                "id": int(r["id"]),
                "owner_id": int(r.get("owner_id") or 0),
                "parent_id": int(r["parent_id"]) if r.get("parent_id") is not None else None,
                "kind": str(r["kind"]),
                "title": str(r["title"] or ""),
                "description": r.get("description"),
                "subject": r.get("subject"),
                "level": r.get("level"),
                "question_count": len(qs) if isinstance(qs, list) else 0,
                "questions": qs if isinstance(qs, list) else [],
            })

        # Strict subject isolation for teachers
        if allowed_subs:
            matched_test_ids: set[int] = set()
            visible_parent_ids: set[int] = set()
            filtered_nodes = []

            for n in all_nodes:
                if n["kind"] == "test":
                    n_sub = (n.get("subject") or "").strip().lower()
                    if not n_sub and n.get("owner_id") == int(user["id"]):
                        match = True
                    elif n_sub:
                        match = any(sub in n_sub or n_sub in sub for sub in allowed_subs)
                    else:
                        # Fallback check on title
                        t_low = n["title"].lower()
                        if "rus" in allowed_subs and ("rus" in t_low or "рус" in t_low):
                            match = True
                        elif "english" in allowed_subs and ("eng" in t_low or "ielts" in t_low or "grammar" in t_low or "past" in t_low or "present" in t_low or "unit" in t_low or "vocabulary" in t_low):
                            match = True
                        elif not any(other in t_low for other in ("rus", "рус", "ona tili", "matematika")):
                            match = ("english" in allowed_subs)
                        else:
                            match = False

                    if match:
                        matched_test_ids.add(n["id"])
                        pid = n.get("parent_id")
                        while pid:
                            visible_parent_ids.add(pid)
                            parent_node = next((x for x in all_nodes if x["id"] == pid), None)
                            pid = parent_node.get("parent_id") if parent_node else None

            for n in all_nodes:
                if n["kind"] == "test" and n["id"] in matched_test_ids:
                    filtered_nodes.append(n)
                elif n["kind"] == "folder" and n["id"] in visible_parent_ids:
                    filtered_nodes.append(n)

            return {"nodes": filtered_nodes}

        return {"nodes": all_nodes}
    finally:
        conn.close()


@router.post("/staff/learning-modules/{module_id}/ai-question")
async def generate_learning_ai_question(module_id: int, payload: LearningAiLessonRequest, authorization: str | None = Header(default=None)):
    """Generate AI test questions using Diamondvoy (xAI / Gemini) with question bank reuse and auto-save."""
    import re
    user = _user(authorization)
    _require(user, LEARNING_MANAGER_ROLES)
    ensure_schema()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT track_id FROM learning_modules WHERE id=?", (module_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Learning module not found")
        track_row = _learning_track_for_manager(int(dict(row)["track_id"]), user)
        track_subject = str((track_row or {}).get("subject") or "English")
    finally:
        conn.close()

    DEFAULT_MIXED_TEST_TYPES = ["multiple_choice", "true_false", "fill_blank", "word_order", "matching"]
    raw_types = [str(t).strip() for t in (payload.test_types or []) if str(t).strip()]
    if not raw_types or any(k in raw_types for k in ("mixed", "all", "aralash", "barchasi")):
        types_list = DEFAULT_MIXED_TEST_TYPES
    else:
        types_list = raw_types
    types_str = ", ".join(types_list)

    needed_count = payload.question_count or 10

    # 1. Efficiency check: Retrieve from question bank if enough questions exist or bank has >= 2000 total questions
    bank_questions = get_questions_from_bank(
        subject=track_subject,
        topic=payload.topic,
        count=needed_count,
        difficulty=payload.level or "medium",
    )
    # The legacy bank has no columns for pairs, passages, media or nested items.
    # Reuse only self-contained questions of the types the teacher requested.
    bank_questions = [q for q in bank_questions if q.get("test_type") in types_list
                      and q.get("test_type") in {"multiple_choice", "true_false", "fill_blank", "word_order"}]
    if len(bank_questions) >= needed_count and set(types_list).issubset({q.get("test_type") for q in bank_questions}):
        chosen_bank = bank_questions[:needed_count]
        items = []
        for index, bq in enumerate(chosen_bank):
            items.append({
                "title": f"{payload.topic} · {index + 1}",
                "source_kind": "ai",
                "question_payload": bq,
            })
        return items[0] if needed_count == 1 else {"items": items, "question_count": len(items)}

    prompt = (
        f"Create exactly {needed_count} safe, high-quality test questions for students on the topic: '{payload.topic}'.\n"
        f"Subject: {track_subject}.\n"
        f"Difficulty Level: {payload.level or 'intermediate'}.\n"
        f"Required Exercise Types: {types_str}.\n"
        f"Distribute the questions evenly across these exercise types ({types_str}) to provide a varied and engaging mix.\n"
        f"Additional Instruction: {payload.instruction or 'none'}.\n\n"
        "Return ONLY a valid JSON array of objects. Do NOT use markdown code blocks or conversational text.\n"
        "Each question object MUST have:\n"
        "- 'question': clear question text or prompt\n"
        f"- 'test_type': one of ({types_str}); use only the requested types.\n"
        "- Keep type-specific fields: word and translations for word_practice/spelling; passage for reading/read_aloud; reference_answer for writing/speaking. Never invent audio or image URLs.\n"
        "- 'options': array of string choices strictly following these rules:\n"
        "   * 'multiple_choice': exactly 4 distinct complete choices where ONE is 'correct_answer' and 3 are plausible incorrect distractors. NEVER provide multiple correct choices!\n"
        "   * 'true_false': exactly ['To\\'g\\'ri', 'Noto\\'g\\'ri'].\n"
        "   * 'fill_blank': Either 4 full alternative phrases (1 correct and 3 distractors, e.g. ['will be traveling', 'will travel', 'are traveling', 'traveled']), OR an empty array [] so the student types the answer. NEVER split a single answer phrase into word fragments like ['will', 'be', 'traveling']!\n"
        "   * 'word_order': Array of shuffled words or empty array []. 'correct_answer' is the full sentence.\n"
        "   * 'matching': MUST provide 'pairs': [{'left': 'word1', 'right': 'meaning1'}, {'left': 'word2', 'right': 'meaning2'}, ...]. 'correct_answer': 'word1 = meaning1; word2 = meaning2'. 'options': []. NEVER output choices like '1-A, 2-B'!\n"
        "- 'correct_answer': the exact single correct answer string (must match one of the choices in 'options' for multiple_choice/true_false, or pairs for matching)\n"
        "- 'explanation': a short, clear explanation of why this is correct in the language of the topic/question\n"
    )

    raw_text: str = ""
    # 1. Try direct xAI generation with custom system prompt
    try:
        import aiohttp
        from ai_generator import _xai_generate_text
        sys_prompt = (
            "You are an expert curriculum and assessment designer. Output ONLY a valid JSON array of question objects. "
            "No markdown code blocks, no backticks, no introduction or greeting."
        )
        async with aiohttp.ClientSession() as session:
            raw_text = await _xai_generate_text(prompt, session=session, system_content=sys_prompt, temperature=0.6)
    except Exception:
        raw_text = ""

    # 2. Fallback to explain runtime callback
    if not raw_text.strip():
        callback = _runtime.get("explain")
        if callback:
            try:
                raw_text = str(await callback(prompt, user))
            except Exception:
                raw_text = ""

    if not raw_text.strip():
        raise HTTPException(status_code=503, detail="Diamondvoy test generator is currently unavailable")

    try:
        source = str(raw_text).strip()
        source = re.sub(r"^```(?:json)?\s*", "", source, flags=re.IGNORECASE)
        source = re.sub(r"\s*```$", "", source)
        start = source.find("[")
        end = source.rfind("]") + 1
        if start >= 0 and end > start:
            parsed = json.loads(source[start:end])
        else:
            obj_start = source.find("{")
            obj_end = source.rfind("}") + 1
            parsed = [json.loads(source[obj_start:obj_end])]

        if not isinstance(parsed, list) or not parsed:
            raise ValueError("empty questions parsed")

        items = []
        library_questions = []
        for index, result in enumerate(parsed[:needed_count]):
            if not isinstance(result, dict):
                continue
            q_text = str(result.get("question") or f"{payload.topic} savoli {index + 1}").strip()
            q_type = str(result.get("test_type") or types_list[index % len(types_list)] or "multiple_choice").strip().lower()
            raw_opts = result.get("options")
            options = [str(x).strip() for x in raw_opts] if isinstance(raw_opts, list) else []
            correct = str(result.get("correct_answer") or "").strip()

            if q_type == "true_false":
                if not options:
                    options = ["To'g'ri", "Noto'g'ri"]
                if correct not in options:
                    correct = "To'g'ri"
            elif q_type in ("fill_blank", "gap_fill"):
                norm_opts = [o.lower() for o in options]
                norm_correct = correct.lower()
                joined = " ".join(norm_opts)
                if joined == norm_correct or (norm_correct not in norm_opts and all(o in norm_correct for o in norm_opts if o)):
                    options = []
                elif norm_correct not in norm_opts and len(options) >= 2:
                    options.append(correct)
            elif q_type == "matching":
                pairs = result.get("pairs") or []
                if not pairs and options:
                    for opt in options:
                        if "=" in opt:
                            l, r = opt.split("=", 1)
                            pairs.append({"left": l.strip(), "right": r.strip()})
                        elif " - " in opt:
                            l, r = opt.split(" - ", 1)
                            pairs.append({"left": l.strip(), "right": r.strip()})
                if pairs:
                    options = [p.get("right") for p in pairs if isinstance(p, dict) and p.get("right")]
                    if not correct or "1-A" in correct:
                        correct = "; ".join(f"{p.get('left')} = {p.get('right')}" for p in pairs if isinstance(p, dict))
            elif q_type == "multiple_choice":
                if ";" in correct or "\n" in correct:
                    delim = ";" if ";" in correct else "\n"
                    parts = [p.strip() for p in correct.split(delim) if p.strip()]
                    if options and all(any(o.lower() in p.lower() or p.lower() in o.lower() for p in parts) for o in options):
                        correct = options[0]
                    elif parts:
                        for p in parts:
                            if any(p.lower() == o.lower() for o in options):
                                correct = p
                                break
                        else:
                            correct = parts[0]
                if len(options) < 2:
                    options = [correct or "A", "B", "C", "D"]
                if correct and not any(o.lower() == correct.lower() for o in options):
                    options.append(correct)
            elif not correct and options:
                correct = options[0]

            explanation = str(result.get("explanation") or "").strip()
            question_payload = {
                **result,
                "question": q_text,
                "options": options,
                "correct_answer": correct,
                "explanation": explanation,
                "test_type": q_type,
            }
            if q_type == "matching" and result.get("pairs"):
                pairs = result["pairs"]
                question_payload["pairs"] = pairs
                question_payload["left_items"] = [p.get("left") for p in pairs if isinstance(p, dict) and p.get("left")]
                question_payload["right_items"] = sorted([p.get("right") for p in pairs if isinstance(p, dict) and p.get("right")])
            items.append({
                "title": f"{payload.topic} · {index + 1}",
                "source_kind": "ai",
                "question_payload": question_payload,
            })
            library_questions.append({**question_payload, "kind": q_type})

        if not items:
            raise ValueError("No valid questions generated")

        # Save to question bank for efficient future reuse
        try:
            save_to_question_bank(
                subject=track_subject,
                topic=payload.topic,
                questions=library_questions,
                difficulty=payload.level or "medium",
            )
        except Exception:
            pass

        # Auto-save to materials library under content_type='ai_generated'
        save_cb = _runtime.get("save_library_test")
        if save_cb and library_questions:
            try:
                save_cb(
                    "ai_generated",
                    module_id,
                    json.dumps(library_questions, ensure_ascii=False),
                    int(user.get("id") or 0),
                    title=f"💎 AI: {payload.topic} (modul #{module_id})",
                    created_by_role=str(user.get("role") or "teacher"),
                    is_active=True,
                    raw_questions=True,
                )
            except Exception:
                pass

        return items[0] if needed_count == 1 else {"items": items, "question_count": len(items)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Diamondvoy returned an invalid test response: {exc}")


def _structured_string_list(raw: Any) -> list[str]:
    """Keep learning-path payloads compatible with old comma-delimited tests."""
    if isinstance(raw, str):
        source = raw.strip()
        if not source:
            return []
        try:
            decoded = json.loads(source)
        except Exception:
            decoded = None
        values = decoded if isinstance(decoded, list) else re.split(r"[,;|\n\r]+", source)
    elif isinstance(raw, (list, tuple, set)):
        values = raw
    else:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _learning_library_question(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a content-library test question to portable module format for all test types, preserving audio and extra metadata."""
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or raw.get("test_type") or "multiple_choice").strip().lower()
    question = str(raw.get("question") or raw.get("prompt") or raw.get("text") or raw.get("title") or raw.get("sentence") or raw.get("word") or "").strip()

    raw_opts = raw.get("options") if raw.get("options") is not None else raw.get("choices")
    options = _structured_string_list(raw_opts)

    correct = next((raw[key] for key in (
        "correct_answer", "correct", "answer", "reference_answer",
        "sample_answer", "target_sentence", "word",
    ) if raw.get(key) is not None and raw.get(key) != ""), None)
    index_raw = raw.get("correct_index", raw.get("correct_option_index"))
    try:
        index = int(index_raw) if index_raw is not None else None
    except (TypeError, ValueError):
        index = None
    if (correct is None or kind == "listening") and index is not None and 0 <= index < len(options):
        correct = options[index]

    explanation = str(raw.get("explanation") or raw.get("meaning") or "")
    audio_url = str(raw.get("audio_url") or "").strip()
    image_url = str(raw.get("image_url") or "").strip()
    instruction = str(raw.get("instruction") or "").strip()
    passage = str(raw.get("passage") or raw.get("passage_template") or "").strip()

    if kind in {"true_false", "boolean", "listening_tf"}:
        if not options:
            options = ["True", "False", "Not given"] if kind == "listening_tf" else ["To'g'ri", "Noto'g'ri"]
        if isinstance(correct, bool):
            correct = options[0 if correct else 1]
        if correct is None or (kind == "listening_tf" and isinstance(index, int)):
            correct = options[index] if isinstance(index, int) and 0 <= index < len(options) else options[0]
    elif kind in {"fill_blank", "gap_fill", "spelling", "word_practice", "listening_gap"}:
        raw_word = str(raw.get("word") or raw.get("prompt") or "").strip()
        clean_word = re.sub(r"\s*\([a-zA-Z\s\.,-]+\)\s*", "", raw_word).strip() or raw_word
        if not correct and raw_word:
            correct = clean_word
        if not correct and raw.get("answer"):
            correct = str(raw.get("answer"))
        if not question and raw.get("sentence"):
            question = str(raw.get("sentence"))
    elif kind in {"word_order", "scrambled_sentence", "listening_order"}:
        if not correct and raw.get("target_sentence"):
            correct = str(raw.get("target_sentence"))
        if not correct and raw.get("answer"):
            correct = str(raw.get("answer"))
        if not correct and raw.get("sentence"):
            correct = str(raw.get("sentence"))
    elif kind in {"listening", "dictation", "listening_dictation", "listening_open", "listening_set"}:
        if not correct and raw.get("answer"):
            correct = str(raw.get("answer"))

    if not question:
        if kind == "reading_set":
            question = instruction or "Matnni o'qing va savollarga javob bering:"
        elif kind == "listening_set":
            question = instruction or "Audioni tinglang va savollarga javob bering:"
        else:
            question = instruction or (str(raw.get("prompt") or "").strip() if str(raw.get("prompt") or "").strip() != passage else "")
            if not question:
                if passage:
                    question = "Matnni o'qing va topshiriqni bajaring:"
                elif raw.get("context"):
                    question = "Topshiriqni bajaring:"
                else:
                    question = "Savol"
    elif passage and question.strip() == passage.strip():
        if kind == "reading_set":
            question = instruction or "Matnni o'qing va savollarga javob bering:"
        else:
            question = instruction or "Matnni o'qing va topshiriqni bajaring:"

    accepted_answers = _structured_string_list(
        raw.get("accepted_answers") if raw.get("accepted_answers") is not None else raw.get("acceptable_answers")
    )
    res = {
        **raw,
        "question": question,
        "options": options,
        "correct_answer": str(correct if correct is not None else (options[0] if options else "")),
        "explanation": explanation,
        "audio_url": audio_url,
        "image_url": image_url,
        "instruction": instruction,
        "test_type": kind,
        "kind": kind,
        "accepted_answers": accepted_answers,
        "acceptable_answers": accepted_answers,
        "check": raw.get("check") or ("ai" if kind in {"speak_sentence", "write_sentence", "guided_writing", "translation", "reading_open", "read_aloud", "paraphrase", "dialogue_completion", "picture_description", "listening_open", "word_practice", "open"} else "auto"),
    }
    # Library editors and older app runners use different names for these lists.
    # Keep both representations so imports remain editable and runnable.
    if kind == "passage_cloze":
        blanks = raw.get("answers") or raw.get("blanks") or []
        normalized_blanks: list[dict[str, Any]] = []
        if isinstance(blanks, list):
            for blank in blanks:
                item = dict(blank) if isinstance(blank, dict) else {"answer": blank}
                if item.get("accepted_answers") is not None or item.get("acceptable_answers") is not None:
                    item["accepted_answers"] = _structured_string_list(
                        item.get("accepted_answers") if item.get("accepted_answers") is not None else item.get("acceptable_answers")
                    )
                normalized_blanks.append(item)
        res["answers"] = normalized_blanks
        res["blanks"] = normalized_blanks
    if kind in {"reading_set", "listening_set"}:
        subs = raw.get("questions") if kind == "reading_set" else raw.get("sub_questions")
        subs = subs or raw.get("sub_questions") or raw.get("questions") or []
        res["sub_questions"] = []
        for sub in subs:
            if not isinstance(sub, dict):
                continue
            sub = dict(sub)
            sub_options = _structured_string_list(sub.get("options"))
            sub["options"] = sub_options
            if sub.get("accepted_answers") is not None or sub.get("acceptable_answers") is not None:
                sub["accepted_answers"] = _structured_string_list(
                    sub.get("accepted_answers") if sub.get("accepted_answers") is not None else sub.get("acceptable_answers")
                )
            try:
                sub_index = int(sub.get("correct_index", sub.get("correct_option_index")))
            except (TypeError, ValueError):
                sub_index = None
            if not sub.get("answer") and sub_index is not None and 0 <= sub_index < len(sub_options):
                sub["answer"] = sub_options[sub_index]
            res["sub_questions"].append(sub)
    # Preserve rich polymorphic fields from materials library & homeworks
    for extra_key in (
        "passage", "context", "questions", "pairs", "matches",
        "cloze_text", "word_bank", "sentence", "target_sentence",
        "hints", "sample_answer", "tokens",
        "distractors", "left_items", "right_items",
        "passage_template", "blank_count", "answers",
        "hint", "word_count", "example_sentence", "direction",
        "word", "meaning", "reference_answer", "needs_audio_upload",
        "translation", "translation_uz", "translation_ru", "level",
        "pronunciation", "phonetic", "target_level",
    ):
        if extra_key in raw and raw[extra_key] is not None:
            if kind == "passage_cloze" and extra_key == "answers":
                continue
            res[extra_key] = (
                _structured_string_list(raw[extra_key])
                if extra_key in {"word_bank", "tokens", "distractors", "left_items", "right_items"}
                else raw[extra_key]
            )

    # Special handling for matching / pairs
    if kind == "matching":
        pairs = res.get("pairs") or raw.get("matches") or []
        if not pairs and options:
            parsed_pairs = []
            for opt in options:
                if "=" in opt:
                    p_left, p_right = opt.split("=", 1)
                    parsed_pairs.append({"left": p_left.strip(), "right": p_right.strip()})
                elif " - " in opt:
                    p_left, p_right = opt.split(" - ", 1)
                    parsed_pairs.append({"left": p_left.strip(), "right": p_right.strip()})
                elif ":" in opt and not opt.startswith("http"):
                    p_left, p_right = opt.split(":", 1)
                    parsed_pairs.append({"left": p_left.strip(), "right": p_right.strip()})
            if parsed_pairs:
                pairs = parsed_pairs

        # Universal fallback parser for AI or legacy questions with 1-A, 2-B format
        if not pairs:
            expl = str(res.get("explanation") or raw.get("explanation") or "")
            q_text = str(res.get("question") or raw.get("question") or "")
            left_matches = re.findall(r'(?:^|\s)(?:\d+[\.\)]\s*)([a-zA-Z\w\s\'-]+?)(?=(?:\s+\d+[\.\)]|$))', q_text)
            if left_matches:
                extracted_lefts = [w.strip() for w in left_matches if w.strip()]
                pairs_from_expl = []
                for left_word in extracted_lefts:
                    m = re.search(rf'\b{re.escape(left_word)}\b\s*(?:means|is|refer to|equals|tarjimasi|—|-|:)\s*([^,;.\n]+)', expl, re.IGNORECASE)
                    if m:
                        meaning = m.group(1).strip()
                        meaning = re.sub(r'\s*\([A-Za-z0-9]\)\s*', '', meaning).strip()
                        pairs_from_expl.append({"left": left_word, "right": meaning})
                if len(pairs_from_expl) >= 2:
                    pairs = pairs_from_expl

        if pairs:
            res["pairs"] = pairs
            res["left_items"] = [p.get("left") for p in pairs if isinstance(p, dict) and p.get("left")]
            res["right_items"] = sorted([p.get("right") for p in pairs if isinstance(p, dict) and p.get("right")])
            res["options"] = list(res["right_items"])
            if not res.get("correct_answer") or "1-A" in str(res.get("correct_answer")):
                res["correct_answer"] = "; ".join(f"{p.get('left')} = {p.get('right')}" for p in pairs if isinstance(p, dict))

    # Special handling for word_order / scrambled_sentence
    elif kind in {"word_order", "scrambled_sentence", "listening_order"}:
        if not res.get("tokens"):
            if options:
                res["tokens"] = list(options)
            elif res.get("correct_answer"):
                res["tokens"] = [w for w in str(res["correct_answer"]).split() if w]

    # Sanitize options and answers to avoid broken test UX
    if kind in {"fill_blank", "gap_fill"}:
        norm_opts = [o.strip().lower() for o in res["options"]]
        norm_correct = res["correct_answer"].strip().lower()
        joined = " ".join(norm_opts)
        if joined == norm_correct or (norm_correct not in norm_opts and all(o in norm_correct for o in norm_opts if o)):
            res["options"] = []
        elif norm_correct not in norm_opts and len(res["options"]) >= 2:
            res["options"].append(res["correct_answer"])
    elif kind in {"multiple_choice", "matching"}:
        if ";" in res["correct_answer"] or "\n" in res["correct_answer"]:
            delim = ";" if ";" in res["correct_answer"] else "\n"
            parts = [p.strip() for p in res["correct_answer"].split(delim) if p.strip()]
            if res["options"] and all(any(o.strip().lower() in p.lower() or p.lower() in o.strip().lower() for p in parts) for o in res["options"]):
                res["acceptable_answers"] = res["options"]
                res["correct_answer"] = res["options"][0]
            elif parts:
                for p in parts:
                    if any(p.strip().lower() == o.strip().lower() for o in res["options"]):
                        res["correct_answer"] = p.strip()
                        break
    # Sanitize word_bank in tense / verb form exercises or when sentences contain bracketed clues
    wb = res.get("word_bank")
    if isinstance(wb, list) and wb:
        inst_txt = str(res.get("instruction") or "").lower()
        q_txt = str(res.get("question") or "").lower()
        p_txt = str(res.get("passage") or res.get("passage_template") or "").lower()
        all_txt = f"{inst_txt} {q_txt} {p_txt}"
        is_tense_or_form = any(k in all_txt for k in ["form", "tense", "zamon", "shakl", "put the verb", "brackets", "qavs"])
        has_brackets = bool(re.search(r"\(\s*[a-zA-Z'\s-]+\s*\)", p_txt or q_txt))
        blanks = res.get("blanks") or res.get("answers") or []
        ans_set = {str(b.get("answer") if isinstance(b, dict) else b).strip().lower() for b in blanks if (b.get("answer") if isinstance(b, dict) else b)}
        wb_set = {str(w).strip().lower() for w in wb if w}
        if (is_tense_or_form and has_brackets) or (is_tense_or_form and ans_set and ans_set.issubset(wb_set)):
            res["word_bank"] = []

    if kind == "word_practice":
        raw_w = str(res.get("word") or res.get("question") or "").strip()
        clean_w = re.sub(r"\s*\([a-zA-Z\s\.,-]+\)\s*", "", raw_w).strip() or raw_w
        pos_m = re.search(r"\(([a-zA-Z\s\.,-]+)\)", raw_w)
        res["word"] = clean_w
        res["clean_word"] = clean_w
        res["raw_word"] = raw_w
        if pos_m:
            res["pos_tag"] = f"({pos_m.group(1).strip()})"
        res["test_type"] = "word_practice"
        res["kind"] = "word_practice"
        res["correct_answer"] = clean_w

    return res


def _learning_exam_questions(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose set questions individually to the web and native final-exam runners."""
    question = _learning_library_question(raw)
    if not question:
        return []
    kind = question["test_type"]
    if kind in {"reading_set", "listening_set"}:
        result = []
        aliases = {"mcq": "multiple_choice", "true_false_ng": "true_false",
                   "tf": "true_false", "gap": "gap_fill", "short": "gap_fill",
                   "order": "word_order", "open": "reading_open"}
        for sub in question.get("sub_questions") or []:
            sub_kind = str(sub.get("type") or sub.get("kind") or "gap_fill")
            if sub_kind == "open" and kind == "listening_set":
                sub_kind = "listening_open"
            item = _learning_library_question({
                "passage": question.get("passage") or question.get("context") or "",
                "audio_url": question.get("audio_url") or "",
                **sub, "kind": aliases.get(sub_kind, sub_kind),
            })
            if item:
                result.append(item)
        return result
    if kind == "passage_cloze":
        result = []
        passage = str(question.get("passage") or question.get("passage_template") or "")
        blank_number = iter(range(1, 1001))
        numbered_passage = re.sub(r"___|===|\[blank\]", lambda _: f"[{next(blank_number)}]", passage)
        for index, blank in enumerate(question.get("blanks") or []):
            blank = blank if isinstance(blank, dict) else {"answer": blank}
            result.append(_learning_library_question({
                **blank, "kind": "gap_fill",
                "prompt": f"{index + 1}-bo'sh joyni to'ldiring.",
                "passage": numbered_passage,
                "audio_url": question.get("audio_url") or "",
            }))
        return result
    return [question]


@router.post("/staff/learning-modules/{module_id}/library-test")
async def attach_learning_library_test(module_id: int, payload: LearningLibraryTestAttachRequest, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT track_id,position FROM learning_modules WHERE id=?", (module_id,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Learning module not found")
        _learning_track_for_manager(int(dict(row)["track_id"]),user)

        # Support real teacher library test nodes (from library_nodes table)
        if payload.content_type in {"teacher_library", "library_node", "test"}:
            visible_ids = _learning_visible_library_ids(user)
            if visible_ids is not None and payload.content_id not in visible_ids:
                raise HTTPException(status_code=403, detail="Bu testga ruxsatingiz yo'q")
            cur.execute("SELECT id, title, payload_json FROM library_nodes WHERE id=? AND kind='test'", (payload.content_id,))
            node_row = cur.fetchone()
            if not node_row:
                raise HTTPException(status_code=404, detail="Kutubxona testi topilmadi")
            n_dict = dict(node_row)
            try:
                p_obj = json.loads(str(n_dict.get("payload_json") or "{}"))
            except Exception:
                p_obj = {}
            raw_questions = _extract_node_questions(p_obj)
            test = {"title": n_dict.get("title") or "Kutubxona testi", "questions": raw_questions}
        else:
            test = None
            resolver=_runtime.get("content_test")
            if resolver:
                try: test=resolver(payload.content_type, payload.content_id)
                except Exception: test=None
            if not test:
                cur.execute("SELECT title, questions_json FROM web_content_tests WHERE content_type=? AND content_id=?", (payload.content_type, payload.content_id))
                wrow = cur.fetchone()
                if wrow:
                    try:
                        w_json = json.loads(str(dict(wrow).get("questions_json") or "[]"))
                        qs = _extract_node_questions(w_json)
                    except Exception:
                        qs = []
                    test = {"title": dict(wrow).get("title") or f"{payload.content_type} testi", "questions": qs}
            if not test: raise HTTPException(status_code=404,detail="Material test not found")

        questions=[item for item in (_learning_library_question(dict(raw)) for raw in (test.get("questions") or [])) if item]
        if not questions: raise HTTPException(status_code=422,detail="Bu testda qo'llab-quvvatlanadigan savollar topilmadi")
        cur.execute("SELECT COALESCE(MAX(position),-1) AS value FROM learning_module_lessons WHERE module_id=?", (module_id,)); position=int(dict(cur.fetchone() or {}).get("value", -1))+1
        created=[]
        target_questions = questions
        if payload.question_count is not None and payload.question_count > 0:
            target_questions = questions[:payload.question_count]
        for item in target_questions:
            cur.execute("INSERT INTO learning_module_lessons(module_id,title,source_kind,source_id,source_version,question_payload_json,duration_seconds,position,required) VALUES(?,?,?,?,?,?,?,?,?)",(module_id,str(test.get("title") or "Material testi"),"library",f"{payload.content_type}:{payload.content_id}",str(item.get("test_type") or "multiple_choice"),json.dumps(item,ensure_ascii=False),0,position,1)); created.append(int(cur.lastrowid or 0)); position+=1
        conn.commit(); return {"created_lesson_ids":created,"question_count":len(created)}
    finally: conn.close()


@router.post("/staff/learning-tracks/{track_id}/assign")
async def assign_learning_track(track_id: int, payload: LearningAssignRequest, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user, LEARNING_MANAGER_ROLES); ensure_schema(); _learning_track_for_manager(track_id,user); conn=get_conn()
    try:
        cur=conn.cursor(); assigned=[]
        for student_id in sorted(set(payload.student_ids)):
            if int(student_id)<=0 or (_role(user)!="admin" and not _staff_can_access_student(user,int(student_id))): continue
            try: cur.execute("INSERT INTO learning_track_assignments(track_id,student_id,assigned_by,due_at) VALUES(?,?,?,?) ON CONFLICT(track_id,student_id) DO UPDATE SET status='active',due_at=excluded.due_at",(track_id,int(student_id),int(user["id"]),payload.due_at))
            except Exception: cur.execute("INSERT OR REPLACE INTO learning_track_assignments(track_id,student_id,assigned_by,due_at,status) VALUES(?,?,?,?, 'active')",(track_id,int(student_id),int(user["id"]),payload.due_at))
            assigned.append(int(student_id))
        conn.commit(); return {"assigned_student_ids":assigned}
    finally: conn.close()


@router.get("/staff/materials-search")
async def staff_materials_search(q: str = "", content_type: str = "", authorization: str | None = Header(default=None)):
    """Search material library tests that can be attached to learning modules with strict teacher subject isolation."""
    user = _user(authorization)
    _require(user, LEARNING_MANAGER_ROLES)
    ensure_schema()
    conn = get_conn()
    role = _role(user)
    allowed_subs = [s.lower() for s in _teacher_allowed_subjects(user)] if role == "teacher" else None
    try:
        cur = conn.cursor()
        items = []
        visible_ids = _learning_visible_library_ids(user)
        all_types = {"book", "video", "homework", "ai_generated", "library_node"}
        search_types = [content_type] if content_type in all_types else ["library_node", "book", "video", "homework", "ai_generated"]
        for ct in search_types:
            try:
                if ct == "library_node":
                    if q.strip():
                        cur.execute("SELECT id, owner_id, title, subject, payload_json FROM library_nodes WHERE kind='test' AND title LIKE ? ORDER BY title LIMIT 40", (f"%{q.strip()}%",))
                    else:
                        cur.execute("SELECT id, owner_id, title, subject, payload_json FROM library_nodes WHERE kind='test' ORDER BY title LIMIT 40")
                    for row in _dicts(cur.fetchall()):
                        if visible_ids is not None and int(row["id"]) not in visible_ids:
                            continue
                        n_sub = (row.get("subject") or "").strip().lower()
                        if allowed_subs and not (not n_sub and int(row.get("owner_id") or 0) == int(user["id"])):
                            if n_sub:
                                if not any(sub in n_sub or n_sub in sub for sub in allowed_subs):
                                    continue
                            else:
                                t_low = str(row.get("title") or "").lower()
                                if "rus" in allowed_subs and ("rus" in t_low or "рус" in t_low):
                                    pass
                                elif "english" in allowed_subs and ("eng" in t_low or "ielts" in t_low or "grammar" in t_low or "past" in t_low or "present" in t_low or "unit" in t_low):
                                    pass
                                elif not any(other in t_low for other in ("rus", "рус", "ona tili", "matematika")):
                                    if "english" not in allowed_subs:
                                        continue
                                else:
                                    continue
                        try:
                            p_json = json.loads(str(row.get("payload_json") or "{}"))
                            qs = _extract_node_questions(p_json)
                        except Exception:
                            qs = []
                        items.append({"content_id": int(row["id"]), "title": str(row.get("title") or "Kutubxona testi"), "content_type": "library_node", "question_count": len(qs)})

                elif ct == "book":
                    if q.strip():
                        cur.execute("SELECT t.content_id, b.title, b.subject, t.questions_json FROM web_content_tests t JOIN web_books b ON b.id=t.content_id WHERE t.content_type='book' AND b.title LIKE ? ORDER BY b.title LIMIT 30", (f"%{q.strip()}%",))
                    else:
                        cur.execute("SELECT t.content_id, b.title, b.subject, t.questions_json FROM web_content_tests t JOIN web_books b ON b.id=t.content_id WHERE t.content_type='book' ORDER BY b.title LIMIT 30")
                    for row in _dicts(cur.fetchall()):
                        b_sub = (row.get("subject") or "").strip().lower()
                        if allowed_subs and b_sub and not any(sub in b_sub or b_sub in sub for sub in allowed_subs):
                            continue
                        try:
                            w_json = json.loads(str(row.get("questions_json") or "[]"))
                            qs = _extract_node_questions(w_json)
                        except Exception:
                            qs = []
                        items.append({"content_id": int(row["content_id"]), "title": str(row.get("title") or "Kitob"), "content_type": ct, "question_count": len(qs)})

                elif ct == "video":
                    if q.strip():
                        cur.execute("SELECT t.content_id, v.title, v.subject, t.questions_json FROM web_content_tests t JOIN web_videos v ON v.id=t.content_id WHERE t.content_type='video' AND v.title LIKE ? ORDER BY v.title LIMIT 30", (f"%{q.strip()}%",))
                    else:
                        cur.execute("SELECT t.content_id, v.title, v.subject, t.questions_json FROM web_content_tests t JOIN web_videos v ON v.id=t.content_id WHERE t.content_type='video' ORDER BY v.title LIMIT 30")
                    for row in _dicts(cur.fetchall()):
                        v_sub = (row.get("subject") or "").strip().lower()
                        if allowed_subs and v_sub and not any(sub in v_sub or v_sub in sub for sub in allowed_subs):
                            continue
                        try:
                            w_json = json.loads(str(row.get("questions_json") or "[]"))
                            qs = _extract_node_questions(w_json)
                        except Exception:
                            qs = []
                        items.append({"content_id": int(row["content_id"]), "title": str(row.get("title") or "Video"), "content_type": ct, "question_count": len(qs)})

                elif ct == "ai_generated":
                    if q.strip():
                        cur.execute("SELECT t.content_id, t.title, t.questions_json FROM web_content_tests t WHERE t.content_type='ai_generated' AND t.title LIKE ? AND t.is_active=1 ORDER BY t.updated_at DESC LIMIT 30", (f"%{q.strip()}%",))
                    else:
                        cur.execute("SELECT t.content_id, t.title, t.questions_json FROM web_content_tests t WHERE t.content_type='ai_generated' AND t.is_active=1 ORDER BY t.updated_at DESC LIMIT 30")
                    for row in _dicts(cur.fetchall()):
                        t_low = str(row.get("title") or "").lower()
                        if allowed_subs:
                            if "rus" in allowed_subs and ("rus" in t_low or "рус" in t_low):
                                pass
                            elif "english" in allowed_subs and not any(other in t_low for other in ("rus", "рус", "ona tili", "matematika")):
                                pass
                            else:
                                continue
                        try:
                            w_json = json.loads(str(row.get("questions_json") or "[]"))
                            qs = _extract_node_questions(w_json)
                        except Exception:
                            qs = []
                        items.append({"content_id": int(row["content_id"]), "title": str(row.get("title") or "AI Test"), "content_type": ct, "question_count": len(qs)})

                else:
                    if q.strip():
                        cur.execute("SELECT t.content_id, h.title, h.subject, t.questions_json FROM web_content_tests t JOIN web_homeworks h ON h.id=t.content_id WHERE t.content_type='homework' AND h.title LIKE ? ORDER BY h.title LIMIT 30", (f"%{q.strip()}%",))
                    else:
                        cur.execute("SELECT t.content_id, h.title, h.subject, t.questions_json FROM web_content_tests t JOIN web_homeworks h ON h.id=t.content_id WHERE t.content_type='homework' ORDER BY h.title LIMIT 30")
                    for row in _dicts(cur.fetchall()):
                        h_sub = (row.get("subject") or "").strip().lower()
                        if allowed_subs and h_sub and not any(sub in h_sub or h_sub in sub for sub in allowed_subs):
                            continue
                        try:
                            w_json = json.loads(str(row.get("questions_json") or "[]"))
                            qs = _extract_node_questions(w_json)
                        except Exception:
                            qs = []
                        items.append({"content_id": int(row["content_id"]), "title": str(row.get("title") or "Homework"), "content_type": ct, "question_count": len(qs)})
            except Exception:
                pass
        return {"items": items}
    finally: conn.close()


def _refresh_learning_module_progress(cur: Any, module_id: int, student_id: int, passing_score: int) -> dict[str, Any]:
    cur.execute("SELECT id,required FROM learning_module_lessons WHERE module_id=? ORDER BY position,id", (module_id,))
    lessons=_dicts(cur.fetchall())
    required=[int(row["id"]) for row in lessons if int(row.get("required") or 0)]
    if not required:
        required=[int(row["id"]) for row in lessons]
    if not required:
        return {"status":"unlocked","best_score":0,"passed":False}

    # Check if this module was ALREADY passed previously by this student
    cur.execute("SELECT status, best_score, passed_at, rewarded_at FROM learning_module_progress WHERE module_id=? AND student_id=?", (module_id, student_id))
    ex_row = cur.fetchone()
    already_passed = False
    existing_best = 0.0
    existing_passed_at = None
    existing_rewarded_at = None
    if ex_row is not None:
        ex_dict = dict(ex_row)
        already_passed = (str(ex_dict.get("status") or "") == "passed" or ex_dict.get("passed_at") is not None)
        existing_best = float(ex_dict.get("best_score") or 0.0)
        existing_passed_at = ex_dict.get("passed_at")
        existing_rewarded_at = ex_dict.get("rewarded_at")

    attempted_scores=[]
    for lesson_id in required:
        cur.execute("SELECT MAX(score) AS score FROM learning_lesson_attempts WHERE lesson_id=? AND student_id=?", (lesson_id, student_id))
        row=cur.fetchone()
        if row is not None and dict(row).get("score") is not None:
            attempted_scores.append(float(dict(row)["score"]))
    total_required=len(required)
    total_attempted=len(attempted_scores)
    if total_attempted==0:
        status="passed" if already_passed else "unlocked"
        best=existing_best
        complete=already_passed
    else:
        calc_best=round(sum(attempted_scores)/total_attempted, 2)
        best=max(existing_best, calc_best)
        if already_passed:
            status="passed"
            complete=True
        elif total_attempted<total_required:
            status="in_progress"
            complete=False
        else:
            if best>=passing_score or calc_best>=passing_score:
                status="passed"
                complete=True
            else:
                status="failed"
                complete=False

    passed_at = existing_passed_at or (_now().isoformat() if complete else None)
    now_iso = _now().isoformat()
    try:
        cur.execute(
            """
            INSERT INTO learning_module_progress(module_id, student_id, status, best_score, passed_at, rewarded_at, updated_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(module_id,student_id) DO UPDATE SET
                status=CASE WHEN learning_module_progress.status='passed' THEN 'passed' ELSE excluded.status END,
                best_score=CASE WHEN excluded.best_score > learning_module_progress.best_score THEN excluded.best_score ELSE learning_module_progress.best_score END,
                passed_at=COALESCE(learning_module_progress.passed_at, excluded.passed_at),
                rewarded_at=COALESCE(learning_module_progress.rewarded_at, excluded.rewarded_at),
                updated_at=excluded.updated_at
            """,
            (module_id, student_id, status, best, passed_at, existing_rewarded_at, now_iso)
        )
    except Exception:
        cur.execute(
            """
            UPDATE learning_module_progress
            SET status=CASE WHEN status='passed' THEN 'passed' ELSE ? END,
                best_score=CASE WHEN ? > best_score THEN ? ELSE best_score END,
                passed_at=COALESCE(passed_at, ?),
                rewarded_at=COALESCE(rewarded_at, ?),
                updated_at=?
            WHERE module_id=? AND student_id=?
            """,
            (status, best, best, passed_at, existing_rewarded_at, now_iso, module_id, student_id)
        )
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO learning_module_progress(module_id, student_id, status, best_score, passed_at, rewarded_at, updated_at)
                VALUES(?,?,?,?,?,?,?)
                """,
                (module_id, student_id, status, best, passed_at, existing_rewarded_at, now_iso)
            )
    return {"status": "passed" if (already_passed or complete) else status, "best_score": best, "passed": (already_passed or complete)}


def _ensure_track_certificate(cur: Any, track: dict[str, Any], student_id: int) -> dict[str, Any] | None:
    course_key=f"learning-track:{int(track['id'])}:v{int(track.get('version') or 1)}"
    cur.execute("SELECT * FROM certificates WHERE user_id=? AND course_key=?",(student_id,course_key)); existing=cur.fetchone()
    if existing:
        certificate=dict(existing)
        cur.execute("SELECT share_token FROM learning_certificate_shares WHERE certificate_id=? AND active=1", (certificate["certificate_id"],))
        share_row=cur.fetchone()
        if share_row: certificate["share_token"]=str(dict(share_row).get("share_token") or "")
        return certificate
    certificate_id=f"LP-{int(track['id'])}-{student_id}-{secrets.token_hex(5).upper()}"
    metadata={"source":"learning_path","track_id":int(track["id"]),"template":track.get("certificate_template_key"),"layers":json.loads(str(track.get("certificate_layers_json") or "[]"))}
    cur.execute("INSERT INTO certificates(certificate_id,user_id,course_key,course_title,metadata_json) VALUES(?,?,?,?,?)",(certificate_id,student_id,course_key,str(track.get("title") or "Learning Path"),json.dumps(metadata,ensure_ascii=False)))
    share=secrets.token_urlsafe(24).replace("-","").replace("_","")
    try: cur.execute("INSERT INTO learning_certificate_shares(certificate_id,share_token) VALUES(?,?)",(certificate_id,share))
    except Exception: pass
    cur.execute("SELECT * FROM certificates WHERE certificate_id=?",(certificate_id,)); certificate=dict(cur.fetchone()); certificate["share_token"]=share; return certificate


@router.get("/student/learning-tracks")
async def student_learning_tracks(subject: str | None = Query(default=None), authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); uid=int(user["id"]); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT * FROM learning_tracks WHERE status != 'archived' ORDER BY subject,position,id")
        raw_tracks=_dicts(cur.fetchall()); tracks=[]
        by_subject: dict[str, list[dict[str, Any]]] = {}
        for tr in raw_tracks:
            sub=str(tr.get("subject") or "general").strip()
            by_subject.setdefault(sub, []).append(tr)
        for sub, sub_tracks in by_subject.items():
            previous_complete=True
            for track in sub_tracks:
                item=_learning_track_payload(cur,track,uid)
                states=[str((module.get("progress") or {}).get("status") or "locked") for module in item["modules"]]
                for index,module in enumerate(item["modules"]):
                    progress=module.get("progress") or {}
                    if not previous_complete or (index>0 and states[index-1] != "passed"):
                        progress["status"]="locked"; module["progress"]=progress
                    elif progress.get("status") in ("locked", None):
                        progress["status"]="unlocked"; module["progress"]=progress

                all_modules_passed = bool(states) and all(s == "passed" for s in states)
                cur.execute("SELECT status, best_score, passed_at FROM learning_track_final_progress WHERE track_id=? AND student_id=?", (int(track["id"]), uid))
                fp_row = cur.fetchone()
                fp = dict(fp_row) if fp_row else {}
                final_status = str(fp.get("status") or "locked").lower()
                if not all_modules_passed:
                    final_status = "locked"
                elif final_status not in ("passed", "failed"):
                    final_status = "unlocked"

                final_passed = (final_status == "passed")
                completed = all_modules_passed and final_passed

                course_key = f"learning-track:{int(track['id'])}:v{int(track.get('version') or 1)}"
                cur.execute("SELECT certificate_id, issued_at FROM certificates WHERE user_id=? AND course_key=?", (uid, course_key))
                cert_row = cur.fetchone()
                cert_claimed = bool(cert_row)

                item["final_exam"] = {
                    "status": final_status,
                    "best_score": float(fp.get("best_score") or 0),
                    "passed": final_passed,
                    "passing_score": normalize_track_passing_score(track.get("passing_score")),
                    "unlocked": all_modules_passed,
                    "certificate_id": dict(cert_row).get("certificate_id") if cert_row else None,
                }
                item["progress_status"]="passed" if completed else ("unlocked" if previous_complete else "locked")
                item["locked"]=not previous_complete; item["certificate_eligible"]=completed
                item["certificate_claimed"] = cert_claimed
                tracks.append(item); previous_complete = previous_complete and completed

        # Collect distinct real subjects (strictly exclude any "all", "barchasi", etc.)
        distinct_subjects = []
        for tr in raw_tracks:
            s_val = str(tr.get("subject") or "").strip()
            if s_val and s_val.lower() not in ("all", "barchasi", "barcha fanlar", "все") and s_val not in distinct_subjects:
                distinct_subjects.append(s_val)

        # If subject query is provided, filter tracks
        if subject and subject.strip() and subject.strip().lower() not in ("all", "barchasi", "barcha fanlar", "все"):
            tracks = [t for t in tracks if str(t.get("subject") or "").strip().lower() == subject.strip().lower()]

        return {
            "items": tracks,
            "subjects": distinct_subjects,
            "default_subject": distinct_subjects[0] if distinct_subjects else "Ingliz tili",
            "passing_score": DEFAULT_TRACK_PASSING_SCORE,
        }
    finally: conn.close()


@router.get("/student/learning-lessons/{lesson_id}")
async def student_learning_lesson(lesson_id: int, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); uid=int(user["id"]); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT l.*,m.track_id,m.id AS module_id,m.passing_score AS module_passing,t.passing_score AS track_passing_score,t.status AS track_status FROM learning_module_lessons l JOIN learning_modules m ON m.id=l.module_id JOIN learning_tracks t ON t.id=m.track_id WHERE l.id=? AND t.status != 'archived'",(lesson_id,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Lesson not found")
        item=dict(row)
        cur.execute("SELECT id FROM learning_modules WHERE track_id=? ORDER BY position,id", (int(item["track_id"]),))
        module_ids=[int(dict(module)["id"]) for module in cur.fetchall()]
        module_index=module_ids.index(int(item["module_id"]))
        if module_index:
            cur.execute("SELECT status FROM learning_module_progress WHERE module_id=? AND student_id=?", (module_ids[module_index - 1], uid))
            previous=cur.fetchone()
            if not previous or str(dict(previous).get("status") or "") != "passed":
                raise HTTPException(status_code=423, detail="Oldingi modulni muvaffaqiyatli yakunlang")
        try:
            item["question_payload"] = _learning_library_question(json.loads(str(item.pop("question_payload_json", None) or "{}")))
        except Exception:
            item["question_payload"] = {}
        if isinstance(item.get("question_payload"), dict):
            qp = item["question_payload"]
            q_txt = str(qp.get("question") or "").strip()
            p_txt = str(qp.get("passage") or qp.get("passage_template") or "").strip()
            inst = str(qp.get("instruction") or "").strip()
            if p_txt and q_txt == p_txt:
                qp["question"] = inst or "Matnni o'qing va topshiriqni bajaring:"
            all_text = f"{inst} {q_txt} {p_txt}".lower()
            is_tense_or_form = any(k in all_text for k in ["form", "tense", "zamon", "shakl", "put the verb", "brackets", "qavs"])
            has_brackets = bool(re.search(r"\(\s*[a-zA-Z'\s-]+\s*\)", p_txt or q_txt))
            wb = qp.get("word_bank") or []
            blanks = qp.get("blanks") or qp.get("answers") or []
            if wb and blanks:
                ans_set = {str(b.get("answer") if isinstance(b, dict) else b).strip().lower() for b in blanks if (b.get("answer") if isinstance(b, dict) else b)}
                wb_set = {str(w).strip().lower() for w in wb if w}
                if (is_tense_or_form and has_brackets) or (is_tense_or_form and ans_set and ans_set.issubset(wb_set)):
                    qp["word_bank"] = []
            q_kind = str(qp.get("kind") or qp.get("test_type") or "")
            if q_kind in {"word_practice", "vocabulary", "vocab"} or qp.get("practice_mode") in {"word_practice", "random"}:
                import random as _rnd
                from backend.library_ai import _materialize_word_practice, _student_lang, _study_language_name
                # Deterministic single task per student & lesson (homework-like behavior)
                lesson_seed = int(item.get("id") or 0) * 10007 + uid
                r = _rnd.Random(lesson_seed)
                cand_variants = ["spelling", "translation", "write_sentence", "speak_sentence", "read_aloud"]
                tr_has = bool(qp.get("translation") or qp.get("translation_uz") or qp.get("translation_ru"))
                if not tr_has and "translation" in cand_variants:
                    cand_variants.remove("translation")
                chosen_v = str(qp.get("practice_mode") or "").strip()
                if chosen_v not in cand_variants:
                    chosen_v = r.choice(cand_variants)
                s_lang = _student_lang(user)
                st_lang = _study_language_name(str(item.get("track_subject") or "English"))
                mat = _materialize_word_practice(qp, lang=s_lang, study_lang=st_lang, chosen_kind=chosen_v)
                qp.update(mat)
        return item
    finally: conn.close()


@router.post("/student/learning-lessons/{lesson_id}/check-ai")
@router.post("/student/learning-lessons/check-ai")
async def check_learning_lesson_ai(
    lesson_id: int | None = None,
    payload: LearningLessonAiCheckRequest | None = None,
    authorization: str | None = Header(default=None),
    x_language: str | None = Header(default=None, alias="X-Language"),
):
    user = _user(authorization)
    _require(user, {"student", "teacher", "admin", "superadmin", "director", "mentor", "support", "staff"})
    conn = get_conn()
    try:
        cur = conn.cursor()
        eff_lesson_id = lesson_id or (payload.lesson_id if payload else None)
        qp: dict[str, Any] = {}
        track_subject = "English"
        if eff_lesson_id:
            cur.execute(
                "SELECT l.question_payload_json, t.subject FROM learning_module_lessons l "
                "JOIN learning_modules m ON m.id=l.module_id "
                "JOIN learning_tracks t ON t.id=m.track_id WHERE l.id=?",
                (int(eff_lesson_id),),
            )
            row = cur.fetchone()
            if row:
                r_dict = dict(row)
                track_subject = str(r_dict.get("subject") or "English")
                try:
                    qp = json.loads(str(r_dict.get("question_payload_json") or "{}"))
                except Exception:
                    qp = {}
        if payload and payload.question_payload and isinstance(payload.question_payload, dict):
            qp = {**qp, **payload.question_payload}

        if not qp:
            raise HTTPException(status_code=400, detail="Savol topilmadi")

        subject = (payload.subject if payload and payload.subject else None) or track_subject or "English"
        answer = str((payload.answer_text if payload else "") or "").strip()
        audio_url = (payload.audio_url if payload else None) or None
        if answer == "[Audio answer]":
            answer = ""

        if not answer and not audio_url:
            return {
                "is_correct": False,
                "verdict": "wrong",
                "feedback": "Javob bo'sh qoldirilgan.",
                "corrected": str(qp.get("reference_answer") or qp.get("sample_answer") or qp.get("correct_answer") or ""),
                "grammar_errors": [],
                "score": 0.0,
            }

        from backend.library_ai import _check_with_ai, _student_lang, AiTestAnswerRequest

        raw_w = str(qp.get("word") or qp.get("question") or qp.get("prompt") or "").strip()
        clean_w = re.sub(r"\s*\([a-zA-Z\s\.,-]+\)\s*", "", raw_w).strip() or raw_w
        acc_list = list(qp.get("acceptable_answers") or [])
        for candidate in [clean_w, raw_w, qp.get("translation"), qp.get("translation_uz"), qp.get("translation_ru"), qp.get("meaning")]:
            if candidate:
                for p in re.split(r"[,;\n/|]+", str(candidate)):
                    ps = p.strip()
                    if ps and ps not in acc_list:
                        acc_list.append(ps)

        q_for_ai = {
            "kind": str(qp.get("kind") or qp.get("test_type") or "open"),
            "prompt": str(qp.get("prompt") or qp.get("question") or qp.get("instruction") or ""),
            "instruction": str(qp.get("instruction") or ""),
            "word": clean_w or qp.get("word"),
            "clean_word": clean_w,
            "raw_word": raw_w,
            "passage": qp.get("passage") or qp.get("context"),
            "reference_answer": qp.get("reference_answer") or qp.get("sample_answer") or qp.get("example_sentence") or clean_w or qp.get("correct_answer"),
            "target_level": qp.get("target_level") or qp.get("level"),
            "translation": qp.get("translation"),
            "translation_uz": qp.get("translation_uz"),
            "translation_ru": qp.get("translation_ru"),
            "meaning": qp.get("meaning"),
            "accepted_answers": acc_list,
        }

        ai_req = AiTestAnswerRequest(
            question_index=0,
            answer_text=answer,
            audio_url=audio_url,
        )

        lang = x_language or _student_lang(user) or "uz"
        try:
            verdict, feedback = await _check_with_ai(q_for_ai, ai_req, subject, lang)
            is_correct = verdict == "correct"
            return {
                "is_correct": is_correct,
                "verdict": verdict,
                "feedback": feedback.get("feedback") or ("Ajoyib! Juda to'g'ri!" if is_correct else "Javobingizda xatolik mavjud."),
                "transcript": feedback.get("transcript") or (answer if feedback.get("was_spoken") else ""),
                "corrected": feedback.get("corrected"),
                "grammar_errors": feedback.get("grammar_errors") or [],
                "pronunciation_errors": feedback.get("pronunciation_errors") or [],
                "was_spoken": feedback.get("was_spoken") or bool(audio_url),
                "score": feedback.get("score") or (100.0 if is_correct else 0.0),
            }
        except Exception as exc:
            logger.warning("learning lesson ai check fallback on error: %s", exc)
            ref = str(q_for_ai.get("reference_answer") or "").strip().lower()
            ans_norm = answer.lower()
            if ref and (ans_norm == ref or ans_norm in ref or ref in ans_norm):
                return {
                    "is_correct": True,
                    "verdict": "correct",
                    "feedback": "Javob qabul qilindi.",
                    "corrected": q_for_ai.get("reference_answer"),
                    "grammar_errors": [],
                    "score": 100.0,
                }
            return {
                "is_correct": False,
                "verdict": "wrong",
                "feedback": "AI tekshirish xizmati javob bermadi. Iltimos qayta urinib ko'ring yoki javobingizni to'liqroq yozing.",
                "corrected": q_for_ai.get("reference_answer"),
                "grammar_errors": [],
                "score": 0.0,
            }
    finally:
        conn.close()


@router.post("/student/learning-lessons/{lesson_id}/submit")
async def submit_learning_lesson(lesson_id: int, payload: LearningLessonSubmit, authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"student"}); ensure_schema(); uid=int(user["id"]); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT l.*,m.track_id,m.id AS module_id,m.passing_score AS module_passing,m.reward_coins AS module_reward_coins,t.passing_score AS track_passing_score,t.certificate_required,t.certificate_template_key,t.certificate_layers_json,t.title AS track_title,t.version FROM learning_module_lessons l JOIN learning_modules m ON m.id=l.module_id JOIN learning_tracks t ON t.id=m.track_id WHERE l.id=? AND t.status != 'archived'",(lesson_id,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Lesson not found")
        lesson=dict(row); threshold=normalize_track_passing_score(lesson.get("module_passing") or lesson.get("track_passing_score")); passed=learning_score_passes(payload.score,threshold)
        cur.execute("SELECT id FROM learning_modules WHERE track_id=? ORDER BY position,id", (int(lesson["track_id"]),))
        module_ids=[int(dict(module)["id"]) for module in cur.fetchall()]
        module_index=module_ids.index(int(lesson["module_id"]))
        if module_index:
            cur.execute("SELECT status FROM learning_module_progress WHERE module_id=? AND student_id=?", (module_ids[module_index - 1], uid))
            previous=cur.fetchone()
            if not previous or str(dict(previous).get("status") or "") != "passed":
                raise HTTPException(status_code=423, detail="Oldingi modulni muvaffaqiyatli yakunlang")
        cur.execute("INSERT INTO learning_lesson_attempts(lesson_id,student_id,score,passed,answers_json,completed_at) VALUES(?,?,?,?,?,?)",(lesson_id,uid,payload.score,1 if passed else 0,json.dumps(payload.answers,ensure_ascii=False),_now().isoformat()))
        progress=_refresh_learning_module_progress(cur,int(lesson["module_id"]),uid,threshold)
        reward_coins=0
        if progress.get("passed") and int(lesson.get("module_reward_coins") or 0) > 0:
            mid = int(lesson["module_id"])
            cur.execute("SELECT rewarded_at FROM learning_module_progress WHERE module_id=? AND student_id=?", (mid, uid))
            p_row = cur.fetchone()
            was_rewarded = bool(p_row and dict(p_row).get("rewarded_at"))
            if not was_rewarded:
                cur.execute("SELECT id FROM diamond_history WHERE user_id=? AND change_type=? LIMIT 1", (uid, f"learning_module_reward:{mid}"))
                if cur.fetchone():
                    was_rewarded = True
            if not was_rewarded:
                cur.execute("UPDATE learning_module_progress SET rewarded_at=? WHERE module_id=? AND student_id=? AND rewarded_at IS NULL", (_now().isoformat(), mid, uid))
                if cur.rowcount:
                    reward_coins = int(lesson.get("module_reward_coins") or 0)
        cur.execute("SELECT COALESCE(p.status,'locked') AS status FROM learning_modules m LEFT JOIN learning_module_progress p ON p.module_id=m.id AND p.student_id=? WHERE m.track_id=? ORDER BY m.position,m.id",(uid,int(lesson["track_id"]))); states=[str(dict(r).get("status") or "locked") for r in cur.fetchall()]
        track_complete = False
        certificate = None
        conn.commit()
        if reward_coins:
            award=_runtime.get("award_coins")
            if award:
                try: award(uid,reward_coins,"GLOBAL",change_type=f"learning_module_reward:{int(lesson['module_id'])}")
                except Exception: pass
        return {"passed":passed,"required_score":threshold,"module_progress":progress,"track_completed":track_complete,"certificate":certificate,"reward_coins":reward_coins,"reward_points":reward_coins}
    finally: conn.close()


@router.get("/certificates/share/{share_token}")
async def shared_learning_certificate(share_token: str):
    ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT c.certificate_id,c.course_title,c.issued_at,u.first_name,u.last_name FROM learning_certificate_shares s JOIN certificates c ON c.certificate_id=s.certificate_id JOIN users u ON u.id=c.user_id WHERE s.share_token=? AND s.active=1",(share_token,)); row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Certificate link is invalid")
        certificate=dict(row); certificate["student_name"]=_student_name(certificate); certificate["download_url"]=f"/certificates/share/{share_token}/download"; return certificate
    finally: conn.close()


def _certificate_pdf(certificate: dict[str, Any]) -> bytes:
    """Render a centred, brand-colour certificate; share links never expose auth tokens."""
    try:
        from backend.certificate_generator import get_certificate_pdf
    except ImportError:
        try:
            from certificate_generator import get_certificate_pdf
        except ImportError:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from certificate_generator import get_certificate_pdf
    try:
        metadata=json.loads(str(certificate.get("metadata_json") or "{}"))
    except Exception:
        metadata={}
    return get_certificate_pdf(
        str(certificate["certificate_id"]),
        int(certificate.get("user_id") or 0),
        None,
        course_title=str(certificate.get("course_title") or "Diamond Education"),
        student_name=_student_name(certificate),
        issued_at=str(certificate.get("issued_at") or ""),
        template_key=str(metadata.get("template") or "english"),
        layers=metadata.get("layers") if isinstance(metadata.get("layers"),list) else [],
    )


@router.post("/student/learning-tracks/{track_id}/certificate")
async def claim_track_certificate(track_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM learning_tracks WHERE id=? AND status != 'archived'", (track_id,))
        track = cur.fetchone()
        if not track: raise HTTPException(status_code=404, detail="Track not found")
        track_dict = dict(track)
        
        # Check all modules in the track
        cur.execute("SELECT id, passing_score FROM learning_modules WHERE track_id=? ORDER BY position", (track_id,))
        modules = [dict(m) for m in cur.fetchall()]
        if not modules:
            raise HTTPException(status_code=400, detail="Track has no modules")
        
        module_ids = [m["id"] for m in modules]
        cur.execute(f"SELECT module_id, status FROM learning_module_progress WHERE student_id=? AND module_id IN ({','.join('?' for _ in module_ids)})", [uid] + module_ids)
        progresses = {dict(r)["module_id"]: dict(r)["status"] for r in cur.fetchall()}
        
        passed_count = sum(1 for m in modules if progresses.get(m["id"]) == "passed")
        all_passed = passed_count == len(modules)
        
        if not all_passed:
            return {
                "ok": False,
                "passed": False,
                "passed_count": passed_count,
                "total_count": len(modules),
                "message": f"Sandiq ochish uchun barcha {len(modules)} ta modulni muvaffaqiyatli topshirishingiz kerak (hozircha {passed_count}/{len(modules)})."
            }

        cur.execute("SELECT status FROM learning_track_final_progress WHERE track_id=? AND student_id=?", (track_id, uid))
        fp_row = cur.fetchone()
        final_passed = bool(fp_row and dict(fp_row).get("status") == "passed")
        if not final_passed:
            return {
                "ok": False,
                "passed": False,
                "message": "Sertifikat olish uchun avval Yakuniy Imtihonni muvaffaqiyatli topshirishingiz kerak."
            }
            
        cert = _ensure_track_certificate(cur, track_dict, uid)
        conn.commit()
        
        reward = 50.0
        history_key = f"track_complete_{track_id}"
        cur.execute("SELECT 1 FROM diamond_history WHERE user_id=? AND change_type=?", (uid, history_key))
        if not cur.fetchone():
            try:
                award = _runtime.get("award_coins") or add_dcoins
                award(uid, reward, str(track_dict.get("subject") or "GLOBAL"), change_type=history_key)
            except Exception as ex:
                logger.exception("Failed to award claim certificate coins: %s", ex)
            
        return {
            "ok": True,
            "passed": True,
            "certificate": cert,
            "reward_points": reward,
            "reward_coins": reward,
            "message": "Sertifikat va mukofot muvaffaqiyatli berildi!"
        }
    finally:
        conn.close()


@router.get("/student/learning-tracks/{track_id}/final-exam")
async def get_track_final_exam(track_id: int, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM learning_tracks WHERE id=? AND status != 'archived'", (track_id,))
        track = cur.fetchone()
        if not track:
            raise HTTPException(status_code=404, detail="Track topilmadi")
        track_dict = dict(track)
        threshold = normalize_track_passing_score(track_dict.get("passing_score"))

        cur.execute("SELECT id, title, passing_score FROM learning_modules WHERE track_id=? ORDER BY position, id", (track_id,))
        modules = [dict(m) for m in cur.fetchall()]
        if not modules:
            raise HTTPException(status_code=400, detail="Trackda modullar yo'q")

        module_ids = [m["id"] for m in modules]
        cur.execute(f"SELECT module_id, status FROM learning_module_progress WHERE student_id=? AND module_id IN ({','.join('?' for _ in module_ids)})", [uid] + module_ids)
        progresses = {dict(r)["module_id"]: dict(r)["status"] for r in cur.fetchall()}

        all_passed = all(progresses.get(mid) == "passed" for mid in module_ids)
        if not all_passed:
            passed_count = sum(1 for mid in module_ids if progresses.get(mid) == "passed")
            raise HTTPException(
                status_code=423,
                detail=f"Yakuniy imtihonni ochish uchun avval barcha {len(module_ids)} ta modulni muvaffaqiyatli yakunlang (hozircha {passed_count}/{len(module_ids)})."
            )

        cur.execute(f"""
            SELECT l.id as lesson_id, l.title, l.source_kind, l.source_id, l.question_payload_json, l.module_id, m.title as module_title
            FROM learning_module_lessons l
            JOIN learning_modules m ON m.id=l.module_id
            WHERE l.module_id IN ({','.join('?' for _ in module_ids)})
            ORDER BY l.module_id, l.position, l.id
        """, module_ids)
        lesson_rows = [dict(r) for r in cur.fetchall()]

        questions = []
        for idx, l in enumerate(lesson_rows):
            try:
                payload = json.loads(str(l.get("question_payload_json") or "{}"))
            except Exception:
                payload = {}
            if not payload:
                continue
            for question in _learning_exam_questions(payload):
                questions.append({
                    **question,
                    "id": len(questions) + 1,
                    "lesson_id": l["lesson_id"],
                    "module_id": l["module_id"],
                    "module_title": l.get("module_title") or "",
                    "title": l.get("title") or f"Savol {idx + 1}",
                })

        random.shuffle(questions)

        cur.execute("SELECT * FROM learning_track_final_progress WHERE track_id=? AND student_id=?", (track_id, uid))
        fp = cur.fetchone()
        fp_dict = dict(fp) if fp else {}

        return {
            "track_id": track_id,
            "track_title": track_dict.get("title"),
            "passing_score": threshold,
            "unlocked": True,
            "status": fp_dict.get("status") or "unlocked",
            "best_score": float(fp_dict.get("best_score") or 0),
            "total_questions": len(questions),
            "questions": questions,
        }
    finally:
        conn.close()


@router.post("/student/learning-tracks/{track_id}/final-exam/submit")
async def submit_track_final_exam(track_id: int, payload: LearningLessonSubmit, authorization: str | None = Header(default=None)):
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM learning_tracks WHERE id=? AND status != 'archived'", (track_id,))
        track = cur.fetchone()
        if not track:
            raise HTTPException(status_code=404, detail="Track topilmadi")
        track_dict = dict(track)
        threshold = normalize_track_passing_score(track_dict.get("passing_score"))

        cur.execute("SELECT id FROM learning_modules WHERE track_id=? ORDER BY position, id", (track_id,))
        module_ids = [dict(m)["id"] for m in cur.fetchall()]
        if not module_ids:
            raise HTTPException(status_code=400, detail="Trackda modullar yo'q")

        cur.execute(f"SELECT module_id, status FROM learning_module_progress WHERE student_id=? AND module_id IN ({','.join('?' for _ in module_ids)})", [uid] + module_ids)
        progresses = {dict(r)["module_id"]: dict(r)["status"] for r in cur.fetchall()}
        all_passed = all(progresses.get(mid) == "passed" for mid in module_ids)
        if not all_passed:
            raise HTTPException(status_code=423, detail="Oldingi barcha modullarni muvaffaqiyatli yakunlang")

        score = float(payload.score or 0)
        passed = score >= threshold
        now_iso = _now().isoformat()

        cur.execute(
            "INSERT INTO learning_track_final_attempts(track_id, student_id, score, passed, answers_json, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (track_id, uid, score, 1 if passed else 0, json.dumps(payload.answers, ensure_ascii=False), now_iso)
        )

        cur.execute("SELECT * FROM learning_track_final_progress WHERE track_id=? AND student_id=?", (track_id, uid))
        existing = cur.fetchone()
        if existing:
            ex_dict = dict(existing)
            new_best = max(float(ex_dict.get("best_score") or 0), score)
            new_status = "passed" if (passed or ex_dict.get("status") == "passed") else "failed"
            cur.execute("""
                UPDATE learning_track_final_progress
                SET status=?, best_score=?, attempts_count=attempts_count+1,
                    passed_at=CASE WHEN ?=1 THEN COALESCE(passed_at, ?) ELSE passed_at END,
                    updated_at=?
                WHERE track_id=? AND student_id=?
            """, (new_status, new_best, 1 if passed else 0, now_iso, now_iso, track_id, uid))
        else:
            new_status = "passed" if passed else "failed"
            cur.execute("""
                INSERT INTO learning_track_final_progress(track_id, student_id, status, best_score, attempts_count, passed_at, updated_at)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (track_id, uid, new_status, score, now_iso if passed else None, now_iso))

        certificate = None
        reward_awarded = False
        if passed:
            certificate = _ensure_track_certificate(cur, track_dict, uid)
            reward = 50.0
            history_key = f"track_complete_{track_id}"
            cur.execute("SELECT 1 FROM diamond_history WHERE user_id=? AND change_type=?", (uid, history_key))
            if not cur.fetchone():
                try:
                    award = _runtime.get("award_coins") or add_dcoins
                    award(uid, reward, str(track_dict.get("subject") or "GLOBAL"), change_type=history_key)
                    reward_awarded = True
                except Exception as ex:
                    logger.exception("Failed to award final exam coins: %s", ex)

        conn.commit()

        return {
            "ok": True,
            "passed": passed,
            "score": score,
            "required_score": threshold,
            "track_completed": passed,
            "certificate": certificate,
            "reward_awarded": reward_awarded,
            "reward_points": 50 if passed else 0,
            "reward_coins": 50 if passed else 0,
            "message": "Tabriklaymiz! Yakuniy imtihondan muvaffaqiyatli o'tdingiz!" if passed else f"O'tish bali: {threshold}%. Natijangiz: {score}%. Qayta topshirishingiz mumkin."
        }
    finally:
        conn.close()


@router.get("/student/certificates/{certificate_id}/pdf")
@router.get("/certificates/{certificate_id}/pdf")
@router.get("/api/student/certificates/{certificate_id}/pdf")
@router.get("/api/certificates/{certificate_id}/pdf")
async def download_student_certificate(certificate_id: str, authorization: str | None = Header(default=None)):
    ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT c.*,u.first_name,u.last_name FROM certificates c JOIN users u ON u.id=c.user_id WHERE c.certificate_id=?", (certificate_id,))
        row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Certificate not found")
        return Response(_certificate_pdf(dict(row)), media_type="application/pdf", headers={"Content-Disposition":f'inline; filename="{certificate_id}.pdf"'})
    finally: conn.close()


@router.get("/certificates/share/{share_token}/download")
async def download_shared_learning_certificate(share_token: str):
    ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor(); cur.execute("SELECT c.*,u.first_name,u.last_name FROM learning_certificate_shares s JOIN certificates c ON c.certificate_id=s.certificate_id JOIN users u ON u.id=c.user_id WHERE s.share_token=? AND s.active=1", (share_token,))
        row=cur.fetchone()
        if not row: raise HTTPException(status_code=404,detail="Certificate link is invalid")
        certificate=dict(row)
        return Response(_certificate_pdf(certificate), media_type="application/pdf", headers={"Content-Disposition":f'attachment; filename="{certificate["certificate_id"]}.pdf"'})
    finally: conn.close()


@router.get("/teacher/student-insights")
async def teacher_student_insights(authorization: str | None = Header(default=None)):
    user=_user(authorization); _require(user,{"teacher","support","admin"}); ensure_schema(); conn=get_conn()
    try:
        cur=conn.cursor()
        ids = set()
        if _role(user) == "admin":
            try:
                cur.execute("SELECT id FROM users WHERE (login_type IN (1, 2) OR login_type IS NULL) AND (blocked IS NULL OR blocked = 0) ORDER BY id DESC LIMIT 500")
                ids = {int(r["id"]) for r in _dicts(cur.fetchall())}
            except Exception:
                pass
        else:
            visible = _runtime.get("staff_visible_student_ids", lambda _u: set())(user)
            ids = {int(item) for item in (visible or set()) if int(item or 0) > 0}
            if not ids:
                try:
                    cur.execute("SELECT gs.student_id FROM group_students gs JOIN groups g ON g.id=gs.group_id WHERE g.teacher_id=? OR g.support_id=?", (int(user["id"]), int(user["id"])))
                    ids = {int(r["student_id"]) for r in _dicts(cur.fetchall())}
                except Exception:
                    pass
        if not ids:
            return {"items":[]}
        placeholders=",".join("?" for _ in sorted(ids))
        cur.execute(f"SELECT m.user_id,u.first_name,u.last_name,u.login_id,m.subject,m.topic_key,COUNT(*) AS mistakes FROM mistake_notebook_items m JOIN users u ON u.id=m.user_id WHERE m.resolved_at IS NULL AND m.user_id IN ({placeholders}) GROUP BY m.user_id,u.first_name,u.last_name,u.login_id,m.subject,m.topic_key ORDER BY mistakes DESC LIMIT 100", sorted(ids)); rows=_dicts(cur.fetchall()); return {"items":rows}
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


def _student_enrolled_subjects(cur: Any, user_id: int, user_row: dict[str, Any]) -> list[str]:
    subs: list[str] = []
    try:
        cur.execute(
            "SELECT DISTINCT g.subject FROM group_students gs JOIN groups g ON g.id=gs.group_id WHERE gs.student_id=?",
            (user_id,),
        )
        for r in cur.fetchall():
            s = _normalize_subject_label(str(dict(r).get("subject") or ""))
            if s and s not in subs:
                subs.append(s)
    except Exception:
        pass
    if not subs:
        raw_s = str(user_row.get("subject") or "")
        for part in raw_s.split(","):
            s = _normalize_subject_label(part.strip())
            if s and s not in subs:
                subs.append(s)
    return subs or ["English"]


def _collect_week_stats(cur: Any, user_id: int, week_start: str, week_end: str, subject: str | None = None) -> dict[str, Any]:
    """Gather test + homework + mistake stats for the given week, optionally filtered by subject."""
    clean_sub = _normalize_subject_label(subject)
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

    # Mistake notebook stats (unresolved, filtered by subject if specified)
    if clean_sub:
        cur.execute(
            "SELECT subject, topic_key, COUNT(*) AS cnt "
            "FROM mistake_notebook_items WHERE user_id=? AND (LOWER(subject)=LOWER(?) OR subject IS NULL) AND resolved_at IS NULL "
            "GROUP BY subject, topic_key ORDER BY cnt DESC LIMIT 5",
            (user_id, clean_sub),
        )
    else:
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
    cur.execute(
        "SELECT topic_key, question_text, explanation FROM mistake_notebook_items "
        "WHERE user_id=? AND DATE(created_at)>=? AND DATE(created_at)<=? "
        "ORDER BY id DESC LIMIT 3",
        (user_id, week_start, week_end),
    )
    sample_mistakes = _dicts(cur.fetchall())

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

    # Learning Path attempts filtered by track subject
    if clean_sub:
        cur.execute(
            "SELECT t.subject,t.title AS track_title,m.title AS module_title,l.source_kind,"
            "a.score,a.passed,a.completed_at "
            "FROM learning_lesson_attempts a "
            "JOIN learning_module_lessons l ON l.id=a.lesson_id "
            "JOIN learning_modules m ON m.id=l.module_id "
            "JOIN learning_tracks t ON t.id=m.track_id "
            "WHERE a.student_id=? AND DATE(a.completed_at)>=? AND DATE(a.completed_at)<=? "
            "AND (LOWER(t.subject)=LOWER(?) OR t.subject IS NULL) "
            "ORDER BY a.completed_at DESC",
            (user_id, week_start, week_end, clean_sub),
        )
    else:
        cur.execute(
            "SELECT t.subject,t.title AS track_title,m.title AS module_title,l.source_kind,"
            "a.score,a.passed,a.completed_at "
            "FROM learning_lesson_attempts a "
            "JOIN learning_module_lessons l ON l.id=a.lesson_id "
            "JOIN learning_modules m ON m.id=l.module_id "
            "JOIN learning_tracks t ON t.id=m.track_id "
            "WHERE a.student_id=? AND DATE(a.completed_at)>=? AND DATE(a.completed_at)<=? "
            "ORDER BY a.completed_at DESC",
            (user_id, week_start, week_end),
        )
    learning_path_attempts = _dicts(cur.fetchall())
    learning_path_total = len(learning_path_attempts)
    learning_path_passed = sum(1 for item in learning_path_attempts if int(item.get("passed") or 0) == 1)
    for item in learning_path_attempts:
        if int(item.get("passed") or 0) != 1:
            topic = str(item.get("module_title") or item.get("track_title") or "learning_path")
            topic_errors[topic] = topic_errors.get(topic, 0) + 1
    weak_by_tests = sorted(topic_errors.items(), key=lambda x: x[1], reverse=True)[:5]

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
        "sample_mistakes": sample_mistakes,
        "homework_total": hw_total,
        "homework_completed": hw_completed,
        "homework_completion_pct": round(hw_completed / hw_total * 100, 1) if hw_total > 0 else 0,
        "learning_path_attempts": learning_path_attempts[:30],
        "learning_path_count": learning_path_total,
        "learning_path_passed": learning_path_passed,
        "learning_path_accuracy_pct": round(learning_path_passed / learning_path_total * 100, 1) if learning_path_total else 0,
    }


def _build_smart_fallback_analysis(stats: dict[str, Any], user_name: str, subject: str = "English") -> dict[str, Any]:
    test_cnt = stats.get("test_count", 0)
    acc = stats.get("accuracy_pct", 0)
    hw_comp = stats.get("homework_completed", 0)
    hw_tot = stats.get("homework_total", 0)
    lang = _detect_subject_language(subject)

    raw_weaks = stats.get("weak_topics_by_tests", []) or []
    err_topic_names = [str(w.get("topic")) for w in raw_weaks[:3] if w.get("topic")]

    if lang == "ru":
        if test_cnt > 0:
            err_mention = f" Основные затруднения возникли в темах: {', '.join(err_topic_names)}." if err_topic_names else ""
            analysis = (
                f"Здравствуйте, {user_name}! На этой неделе вы выполнили {test_cnt} тестов с точностью {acc}%. "
                f"Сдано {hw_comp}/{hw_tot} домашних заданий.{err_mention} "
                f"Обратите внимание на эти ошибки и повторите правила для закрепления материала!"
            )
        else:
            analysis = (
                f"Здравствуйте, {user_name}! Начало недели — отличное время для освоения темы «{subject}». "
                f"Уделяйте 10-15 минут в день занятиям с Diamondvoy, чтобы не допускать типичных ошибок и повышать баллы!"
            )

        weak_topics = []
        for item in raw_weaks[:4]:
            t_name = str(item.get("topic") or "Грамматика и орфография")
            weak_topics.append({
                "topic": t_name,
                "level": "medium" if item.get("errors", 0) < 3 else "weak",
                "explanation": f"В теме «{t_name}» рекомендуется повторить правила, где чаще всего допускаются неточности.",
                "rules": [
                    f"Вспомните ключевые правила по теме «{t_name}».",
                    "Обращайте внимание на окончания, контекст и условия применения правил.",
                ],
            })

        if not weak_topics:
            weak_topics = [
                {
                    "topic": "Падежные окончания существительных",
                    "level": "medium",
                    "explanation": "Обращайте внимание на различие окончаний родительного, дательного и предложного падежей.",
                    "rules": [
                        "1-е склонение: в дательном и предложном падежах окончание -е (о книге, к реке).",
                        "Слова на -ия, -ий, -ие в предложном падеже имеют окончание -и (об армии, в здании).",
                    ],
                },
                {
                    "topic": "Правописание безударных гласных в корне",
                    "level": "weak",
                    "explanation": "Всегда проверяйте безударную гласную ударением или помните о чередующихся корнях.",
                    "rules": [
                        "Подбирайте однокоренное слово, где гласная под ударением: вода -> во́дный.",
                        "Корни с чередованием (лаг/лож, раст/рос) не проверяются ударением.",
                    ],
                },
            ]

        recs = [
            "Выполните 5 практических упражнений ниже для закрепления правил.",
            "Откройте Тетрадь Ошибок (Mistakes Notebook) и заново решите вопросы, где ошиблись.",
            "Регулярно проходите мини-тесты, чтобы закрепить слабые темы.",
        ]

        practice_qs = [
            {
                "question": "В каком слове на месте пропуска пишется буква И?",
                "options": ["пр..брежный", "пр..мудрый", "пр..красный", "пр..одолеть"],
                "correct": "пр..брежный",
                "topic": "Правописание приставок ПРЕ- и ПРИ-",
                "difficulty": "easy",
                "explanation": "Приставка ПРИ- пишется в значении приближения, присоединения, нахождения рядом: прибрежный.",
            },
            {
                "question": "Укажите предложение с ошибкой в согласовании:",
                "options": ["Быстрое метро довезло нас", "Вкусное кофе стояло на столе", "Новое пальто висело в шкафу", "Опытное жюри выставило оценки"],
                "correct": "Вкусное кофе стояло на столе",
                "topic": "Род несклоняемых существительных",
                "difficulty": "medium",
                "explanation": "Слово «кофе» мужского рода: «Вкусный кофе стоял на столе».",
            },
            {
                "question": "В каком слове пишется НН?",
                "options": ["стекля..ый", "кожа..ый", "песча..ый", "глиня..ый"],
                "correct": "стекля..ый",
                "topic": "Н и НН в суффиксах прилагательных",
                "difficulty": "easy",
                "explanation": "Стеклянный, оловянный, деревянный — слова-исключения, пишутся с двумя Н.",
            },
            {
                "question": "В каком корне пишется буква А?",
                "options": ["пол..жить", "предл..гать", "прик..снуться", "изл..жение"],
                "correct": "предл..гать",
                "topic": "Чередующиеся гласные в корне ЛАГ/ЛОЖ",
                "difficulty": "easy",
                "explanation": "Перед буквой Г в корне пишется А (предлагать), перед Ж пишется О (положить).",
            },
            {
                "question": "Выберите правильный вариант: Мы подошли к высокой ____.",
                "options": ["башне", "башни", "башню", "башней"],
                "correct": "башне",
                "topic": "Падежи существительных",
                "difficulty": "easy",
                "explanation": "Предлог «к» требует Дательного падежа: подошли к (чему?) башне.",
            },
        ]

        return {
            "analysis": analysis,
            "weak_topics": weak_topics,
            "recommendations": recs,
            "practice_questions": practice_qs,
            "encouragement": "Каждый пройденный шаг приближает вас к отличному знанию предмета. Продолжайте учиться! 🌟",
        }

    elif lang == "en":
        if test_cnt > 0:
            err_mention = f" Most mistakes occurred in: {', '.join(err_topic_names)}." if err_topic_names else ""
            analysis = (
                f"Hello, {user_name}! This week you completed {test_cnt} tests with an overall accuracy of {acc}%. "
                f"You finished {hw_comp}/{hw_tot} homework assignments.{err_mention} "
                f"Focusing on these specific mistakes will rapidly improve your test scores!"
            )
        else:
            analysis = (
                f"Hello, {user_name}! The start of the week is the perfect time to build your English skills. "
                f"Spend 10-15 minutes each day with Diamondvoy to master core rules and eliminate recurring errors!"
            )

        weak_topics = []
        for item in raw_weaks[:4]:
            t_name = str(item.get("topic") or "General Grammar")
            weak_topics.append({
                "topic": t_name,
                "level": "medium" if item.get("errors", 0) < 3 else "weak",
                "explanation": f"Reviewing core patterns and common traps for '{t_name}' will prevent careless mistakes.",
                "rules": [
                    f"Remember the core formula and typical use cases for '{t_name}'.",
                    "Pay close attention to key time indicators and sentence structure.",
                ],
            })

        if not weak_topics:
            weak_topics = [
                {
                    "topic": "Present Simple vs Present Continuous",
                    "level": "medium",
                    "explanation": "Notice the difference between repeated routines (Simple) and actions happening right now (Continuous).",
                    "rules": [
                        "For daily habits and general facts: Present Simple (always, usually, every day).",
                        "For ongoing actions happening right now: Present Continuous (now, at the moment).",
                    ],
                },
                {
                    "topic": "Past Simple Irregular Verbs",
                    "level": "weak",
                    "explanation": "Memorize common V2 irregular forms and remember that negatives use 'did not + V1'.",
                    "rules": [
                        "Go -> Went, See -> Saw, Buy -> Bought, Make -> Made.",
                        "In questions and negatives, the main verb stays in base form: Did you see? (NOT Did you saw).",
                    ],
                },
            ]

        recs = [
            "Complete the 5 practice questions below to reinforce these rules.",
            "Open your Mistakes Notebook to re-attempt questions you missed previously.",
            "Make it a daily habit to review weak areas and take mini-tests.",
        ]

        practice_qs = [
            {
                "question": "She _____ to English classes every Tuesday and Thursday.",
                "options": ["go", "goes", "is going", "went"],
                "correct": "goes",
                "topic": "Present Simple",
                "difficulty": "easy",
                "explanation": "Third-person singular subjects (he, she, it) take the -s/-es verb ending in Present Simple.",
            },
            {
                "question": "Look at the window! It _____ heavily right now.",
                "options": ["rains", "is raining", "rained", "has rained"],
                "correct": "is raining",
                "topic": "Present Continuous",
                "difficulty": "easy",
                "explanation": "'Look!' and 'right now' indicate an action happening at this exact moment (is + V-ing).",
            },
            {
                "question": "Yesterday they _____ a great time at the amusement park.",
                "options": ["have", "had", "having", "has"],
                "correct": "had",
                "topic": "Past Simple",
                "difficulty": "easy",
                "explanation": "'Yesterday' signals the Past Simple tense, and the past form of 'have' is 'had'.",
            },
            {
                "question": "He hasn't finished reading the book _____.",
                "options": ["already", "yet", "just", "since"],
                "correct": "yet",
                "topic": "Present Perfect",
                "difficulty": "medium",
                "explanation": "Negative Present Perfect sentences typically end with 'yet'.",
            },
            {
                "question": "If you study consistently, you _____ the exam easily.",
                "options": ["pass", "will pass", "passed", "would pass"],
                "correct": "will pass",
                "topic": "First Conditional",
                "difficulty": "medium",
                "explanation": "In First Conditional: If + Present Simple (study), main clause uses will + V1 (will pass).",
            },
        ]

        return {
            "analysis": analysis,
            "weak_topics": weak_topics,
            "recommendations": recs,
            "practice_questions": practice_qs,
            "encouragement": "Every step you take brings you closer to mastery. Keep practicing! 🌟",
        }

    else:
        # Default: UZBEK
        if test_cnt > 0:
            err_mention = f" Asosan «{', '.join(err_topic_names)}» mavzularida xatoliklar ko'proq uchradi." if err_topic_names else ""
            analysis = (
                f"Salom, {user_name}! Bu hafta siz {test_cnt} ta test ishlab, {acc}% aniqlik ko'rsatdingiz. "
                f"Uy vazifalaridan {hw_comp}/{hw_tot} tasi topshirildi.{err_mention} "
                f"Ushbu asosiy xatolar ustida ishlab, bilimlaringizni yanada mustahkamlang!"
            )
        else:
            analysis = (
                f"Salom, {user_name}! Hafta boshlanishi — {subject} fanidan yangi bilimlarni o'zlashtirish uchun qulay fursat. "
                f"Har kuni Diamondvoy bilan 10-15 daqiqa mashq qiling, asosiy xatolarni bartaraf etib, yuqori natijalarga erishing!"
            )

        weak_topics = []
        for item in raw_weaks[:4]:
            t_name = str(item.get("topic") or f"{subject} asosiy qoidalari")
            weak_topics.append({
                "topic": t_name,
                "level": "medium" if item.get("errors", 0) < 3 else "weak",
                "explanation": f"«{t_name}» mavzusida testlarda xatolarga yo'l qo'yilgan. Qoidalarni takrorlash tavsiya etiladi.",
                "rules": [
                    f"«{t_name}» bo'yicha asosiy qoidalar va formulalarni qayta ko'rib chiqing.",
                    "Savol shartini diqqat bilan o'qing va shoshmasdan tahlil qiling.",
                ],
            })

        if not weak_topics:
            weak_topics = [
                {
                    "topic": f"{subject} asosiy tushunchalari",
                    "level": "medium",
                    "explanation": "Mavzu bo'yicha tayanch atamalar va qoidalarni mustahkamlash zarur.",
                    "rules": [
                        "Har bir qoidaga mos kamida ikkitadan misol keltiring.",
                        "Xato daftarchangizga tushgan savollarni qayta ishlab chiqing.",
                    ],
                },
            ]

        recs = [
            "Quyida keltirilgan 5 ta amaliy mashqni bajarib, bilimlaringizni sinab ko'ring.",
            "«Xatolar daftari» bo'limiga kirib, oldin noto'g'ri ishlangan savollarni qaytadan yeching.",
            "Har kuni kamida bitta test yoki kundalik viktorina ishlashni odat qiling.",
        ]

        practice_qs = [
            {
                "question": f"{subject} fani bo'yicha mustahkamlash savoli: Qaysi javob to'g'ri berilgan?",
                "options": ["A varianti (To'g'ri qoida)", "B varianti (Noto'g'ri)", "C varianti (Chalg'ituvchi)", "D varianti (Xato)"],
                "correct": "A varianti (To'g'ri qoida)",
                "topic": f"{subject} asoslari",
                "difficulty": "easy",
                "explanation": "Qoidaga to'liq mos keluvchi variant to'g'ri deb qabul qilinadi.",
            },
            {
                "question": "Qoidalarni qo'llashda eng muhim omil nima?",
                "options": ["Savol sharti va mantiqiy bog'liqlikni tushunish", "Faqat yodlash", "Shoshilib belgilash", "Tasodifiy tanlash"],
                "correct": "Savol sharti va mantiqiy bog'liqlikni tushunish",
                "topic": "Tahlil qilish",
                "difficulty": "easy",
                "explanation": "Savolni to'g'ri o'qib, tahlil qilish xatolardan xalos qiladi.",
            },
            {
                "question": "Mavzuni to'liq o'zlashtirish uchun nima qilish kerak?",
                "options": ["Qoidani o'rganib, amaliy mashqlar bilan mustahkamlash", "Faqat bir marta o'qish", "Mashqlarni bajarmaslik", "Testlarni o'tkazib yuborish"],
                "correct": "Qoidani o'rganib, amaliy mashqlar bilan mustahkamlash",
                "topic": "O'quv metodikasi",
                "difficulty": "easy",
                "explanation": "Nazariya va amaliyot uyg'unligi yuqori natija beradi.",
            },
            {
                "question": "Xatolarni bartaraf etishning eng samarali yo'li nima?",
                "options": ["Xato qilingan savol sababini tushunib, qayta ishlash", "Xatoga e'tibor bermaslik", "Faqat to'g'ri javoblarni yodlash", "Test ishlashni to'xtatish"],
                "correct": "Xato qilingan savol sababini tushunib, qayta ishlash",
                "topic": "Xatolar ustida ishlash",
                "difficulty": "easy",
                "explanation": "O'z xatosi sababini tahlil qilgan o'quvchi keyingi safar adashmaydi.",
            },
            {
                "question": "Haftalik o'quv rejasiga qat'iy rioya qilish nimani ta'minlaydi?",
                "options": ["Muntazam o'sish va bilimlarning mustahkamligini", "Vaqt yo'qotishni", "Faqat baholarni", "Hech narsani o'zgartirmaydi"],
                "correct": "Muntazam o'sish va bilimlarning mustahkamligini",
                "topic": "Rejalashtirish",
                "difficulty": "easy",
                "explanation": "Muntazamlik va intizom har qanday fanda muvaffaqiyat garovidir.",
            },
        ]

        return {
            "analysis": analysis,
            "weak_topics": weak_topics,
            "recommendations": recs,
            "practice_questions": practice_qs,
            "encouragement": "Har bir harakat sizni yuksak marralarga yaqinlashtiradi. O'rganishdan to'xtamang! 🌟",
        }


async def _generate_ai_analysis(stats: dict[str, Any], user_name: str, subject: str = "English") -> dict[str, Any]:
    """Call AI to produce weekly analysis in the student's target subject language."""
    import aiohttp
    lang = _detect_subject_language(subject)

    weak_topics = []
    for item in stats.get("weak_topics_by_tests", []):
        err_w = "ошибок" if lang == "ru" else ("errors" if lang == "en" else "ta xato")
        weak_topics.append(f"- {item['topic']} ({item['errors']} {err_w})")
    for item in stats.get("weak_topics_by_mistakes", []):
        sub = str(item.get("subject") or "")
        topic = str(item.get("topic_key") or "")
        cnt = int(item.get("cnt") or 0)
        unr_w = "нерешенных ошибок" if lang == "ru" else ("unresolved mistakes" if lang == "en" else "ta tuzatilmagan xato")
        weak_topics.append(f"- {sub} / {topic} ({cnt} {unr_w})")

    mistakes_list = [
        f"- {m.get('topic_key') or 'Savol'}: {str(m.get('question_text') or '')[:120]}"
        for m in (stats.get("sample_mistakes") or [])
        if m.get("question_text") or m.get("topic_key")
    ]
    sample_mistakes_str = "\n".join(mistakes_list) if mistakes_list else ("None recorded." if lang == "en" else ("Ошибок не зафиксировано." if lang == "ru" else "Xatolar qayd etilmagan."))

    if lang == "ru":
        weak_str = "\n".join(weak_topics) if weak_topics else "Слабые темы пока не выявлены."
        source_str = ", ".join(f"{item.get('source_type')}: {item.get('count')}" for item in stats.get("mistake_sources", [])) or "Ошибок пока не зафиксировано."
        prompt = f"""Ты — персональный AI-тьютор Diamondvoy на платформе Diamond Education.
Ученик: {user_name}
Предмет: {subject}

Статистика за неделю:
- Количество тестов: {stats.get('test_count', 0)}
- Верно: {stats.get('total_correct', 0)}, Неверно: {stats.get('total_wrong', 0)}, Пропущено: {stats.get('total_skipped', 0)}
- Точность: {stats.get('accuracy_pct', 0)}%
- Домашние задания: {stats.get('homework_completed', 0)}/{stats.get('homework_total', 0)} выполнено ({stats.get('homework_completion_pct', 0)}%)

Слабые темы:
{weak_str}

Конкретные недавние ошибки ученика:
{sample_mistakes_str}

Источники ошибок: {source_str}

Требования к еженедельному анализу:
1. Текст анализа ('analysis') должен быть кратким и четким (2-4 предложения), не слишком перегруженным или сложным, но ОБЯЗАТЕЛЬНО назвать главные ошибки ученика за эту неделю и темы, где они допущены.
2. ВСЕ ТЕКСТЫ, ОБЪЯСНЕНИЯ, ВОПРОСЫ И ПРАВИЛА ДОЛЖНЫ БЫТЬ СТРОГО НА РУССКОМ ЯЗЫКЕ!

Верни строго JSON объект следующей структуры:
{{
  "analysis": "Краткий понятный анализ недели (2-4 предложения) с обязательным указанием главных ошибок ученика",
  "weak_topics": [
    {{"topic": "название темы", "level": "weak/medium", "explanation": "почему здесь возникают трудности", "rules": ["1-е правило", "2-е правило"]}}
  ],
  "recommendations": [
    "1-я рекомендация",
    "2-я рекомендация",
    "3-я рекомендация"
  ],
  "practice_questions": [
    {{"question": "текст вопроса", "options": ["Вариант A", "Вариант B", "Вариант C", "Вариант D"], "correct": "Вариант A", "topic": "тема", "difficulty": "easy", "explanation": "объяснение ответа"}}
  ],
  "encouragement": "ободряющее сообщение"
}}

В practice_questions должно быть не менее 5 легких практических вопросов по слабым темам. Только валидный JSON."""

    elif lang == "en":
        weak_str = "\n".join(weak_topics) if weak_topics else "No weak topics detected yet."
        source_str = ", ".join(f"{item.get('source_type')}: {item.get('count')}" for item in stats.get("mistake_sources", [])) or "No mistakes recorded yet."
        prompt = f"""You are Diamondvoy, the personal AI tutor at Diamond Education.
Student: {user_name}
Target Subject: {subject}

This week's statistics:
- Test count: {stats.get('test_count', 0)}
- Correct: {stats.get('total_correct', 0)}, Wrong: {stats.get('total_wrong', 0)}, Skipped: {stats.get('total_skipped', 0)}
- Overall accuracy: {stats.get('accuracy_pct', 0)}%
- Homework: {stats.get('homework_completed', 0)}/{stats.get('homework_total', 0)} completed ({stats.get('homework_completion_pct', 0)}%)

Weak topics:
{weak_str}

Recent student errors:
{sample_mistakes_str}

Mistake sources: {source_str}

Analysis requirements:
1. The analysis text ('analysis') should be concise and clear (2-4 sentences), not overly dense or deep, but it MUST explicitly state the student's key mistakes and weak topics from this week.
2. ALL TEXTS, EXPLANATIONS, AND QUESTIONS MUST BE STRICTLY IN ENGLISH!

Return ONLY a valid JSON object with the following structure:
{{
  "analysis": "Concise weekly analysis (2-4 sentences) highlighting the student's key mistakes and areas for improvement",
  "weak_topics": [
    {{"topic": "topic name", "level": "weak/medium", "explanation": "why student struggled here", "rules": ["rule 1", "rule 2"]}}
  ],
  "recommendations": [
    "1st recommendation",
    "2nd recommendation",
    "3rd recommendation"
  ],
  "practice_questions": [
    {{"question": "question text", "options": ["Choice A", "Choice B", "Choice C", "Choice D"], "correct": "Choice A", "topic": "topic", "difficulty": "easy", "explanation": "clear explanation"}}
  ],
  "encouragement": "warm encouraging closing statement"
}}

practice_questions must include at least 5 easy practice questions covering the weak topics. Return ONLY JSON."""

    else:
        # Default: UZBEK for all other subjects (Matematika, Ona tili, Tarix, Fizika, Kimyo, Biologiya, etc.)
        weak_str = "\n".join(weak_topics) if weak_topics else "Zaif mavzular aniqlanmadi."
        source_str = ", ".join(f"{item.get('source_type')}: {item.get('count')}" for item in stats.get("mistake_sources", [])) or "Xatolar qayd etilmagan."
        prompt = f"""Siz Diamond Education platformasidagi shaxsiy AI repetitor — Diamondvoysiz.
O'quvchi: {user_name}
Fan: {subject}

Ushbu haftadagi statistika:
- Ishlangan testlar: {stats.get('test_count', 0)} ta
- To'g'ri: {stats.get('total_correct', 0)}, Xato: {stats.get('total_wrong', 0)}, O'tkazilgan: {stats.get('total_skipped', 0)}
- Test aniqligi: {stats.get('accuracy_pct', 0)}%
- Uy vazifalari: {stats.get('homework_completed', 0)}/{stats.get('homework_total', 0)} ta bajarildi ({stats.get('homework_completion_pct', 0)}%)

Zaif mavzular:
{weak_str}

O'quvchi yo'l qo'ygan aniq xatolar:
{sample_mistakes_str}

Xatolar manbai: {source_str}

Tahlil talablari:
1. Tahlil matni ('analysis') juda uzun yoki haddan tashqari chuqur bo'lishi shart emas (2-4 ta tushunarli jumla), ammo o'quvchining bu hafta yo'l qo'ygan ASOSIY XATOLARINI va zaif mavzularini aniq aytib o'tishi SHART.
2. BARCHA MATNLAR, TAHLIL, ZAIF MAVZULAR, TAVSIYALAR, SAVOLLAR VA QOIDALAR TO'LIQ VA QAT'IY O'ZBEK TILIDA (LOTIN ALIFBOSIDA) BO'LSIN!

Faqat quyidagi JSON obyektni qaytaring:
{{
  "analysis": "Haftalik qisqa va tushunarli tahlil (2-4 jumla), o'quvchining asosiy xatolarini albatta ko'rsatgan holda",
  "weak_topics": [
    {{"topic": "mavzu nomi", "level": "weak/medium", "explanation": "nima uchun qiyinchilik tug'ilgani", "rules": ["1-qoida", "2-qoida"]}}
  ],
  "recommendations": [
    "1-tavsiya",
    "2-tavsiya",
    "3-tavsiya"
  ],
  "practice_questions": [
    {{"question": "savol matni", "options": ["Variant A", "Variant B", "Variant C", "Variant D"], "correct": "Variant A", "topic": "mavzu", "difficulty": "easy", "explanation": "javob tushuntirishi"}}
  ],
  "encouragement": "rag'batlantiruvchi gap"
}}

practice_questions da zaif mavzular bo'yicha kamida 5 ta yengil amaliy savol bo'lsin. Faqat to'g'ri JSON qaytaring."""

    try:
        from ai_generator import _xai_generate_text
        async with aiohttp.ClientSession() as session:
            raw = await _xai_generate_text(prompt, session=session, temperature=0.3)
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
        result["weak_topics"] = result.get("weak_topics") if isinstance(result.get("weak_topics"), list) and result.get("weak_topics") else []
        result["recommendations"] = result.get("recommendations") if isinstance(result.get("recommendations"), list) and result.get("recommendations") else []
        result["practice_questions"] = result.get("practice_questions") if isinstance(result.get("practice_questions"), list) and len(result.get("practice_questions")) >= 3 else []
        if not result.get("practice_questions"):
            fallback = _build_smart_fallback_analysis(stats, user_name, subject=subject)
            result["practice_questions"] = fallback["practice_questions"]
            if not result.get("weak_topics"):
                result["weak_topics"] = fallback["weak_topics"]
            if not result.get("recommendations"):
                result["recommendations"] = fallback["recommendations"]
        return result
    except Exception:
        return _build_smart_fallback_analysis(stats, user_name, subject=subject)


async def _finish_weekly_analysis(
    *, user_id: int, user_name: str, week_start: str, stats: dict[str, Any], subject: str = "English"
) -> None:
    """Run the slow AI call outside the request and persist one immutable weekly result for the subject."""
    clean_sub = _normalize_subject_label(subject) or "English"
    try:
        result = await _generate_ai_analysis(stats, user_name, subject=clean_sub)
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE weekly_ai_analyses SET analysis_text=?, weak_topics_json=?, recommendations_json=?, "
                "practice_questions_json=?, status='done', updated_at=? WHERE user_id=? AND week_start=? AND (subject=? OR (subject IS NULL AND ?='English'))",
                (
                    str(result.get("analysis", "")),
                    json.dumps(result.get("weak_topics", []), ensure_ascii=False),
                    json.dumps(result.get("recommendations", []), ensure_ascii=False),
                    json.dumps(result.get("practice_questions", []), ensure_ascii=False),
                    _now().isoformat(), user_id, week_start, clean_sub, clean_sub,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        try:
            fallback = _build_smart_fallback_analysis(stats, user_name, subject=clean_sub)
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    "UPDATE weekly_ai_analyses SET analysis_text=?, weak_topics_json=?, recommendations_json=?, "
                    "practice_questions_json=?, status='done', updated_at=? WHERE user_id=? AND week_start=? AND (subject=? OR (subject IS NULL AND ?='English'))",
                    (
                        str(fallback.get("analysis", "")),
                        json.dumps(fallback.get("weak_topics", []), ensure_ascii=False),
                        json.dumps(fallback.get("recommendations", []), ensure_ascii=False),
                        json.dumps(fallback.get("practice_questions", []), ensure_ascii=False),
                        _now().isoformat(), user_id, week_start, clean_sub, clean_sub,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass


async def generate_weekly_analysis_for_all_students() -> dict[str, Any]:
    """Batch generator for all active students.
    Runs every Sunday 12:00 PM - 1:00 PM Tashkent time."""
    ensure_schema()
    week_start, week_end = _current_week_range()
    conn = get_conn()
    students: list[dict[str, Any]] = []
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, login_id, first_name, last_name, login_type, subject FROM users WHERE (login_type IN (1, 2) OR login_type IS NULL) AND (blocked IS NULL OR blocked = 0)")
        students = _dicts(cur.fetchall())
    finally:
        conn.close()

    total = len(students)
    processed = 0
    skipped = 0
    errors = 0

    for s in students:
        uid = int(s["id"])
        user_name = _student_name(s)
        try:
            conn = get_conn()
            try:
                cur = conn.cursor()
                enrolled_subs = _student_enrolled_subjects(cur, uid, s)
                target_sub = enrolled_subs[0] if enrolled_subs else "English"
                cur.execute("SELECT status FROM weekly_ai_analyses WHERE user_id=? AND week_start=? AND (subject=? OR (subject IS NULL AND ?='English'))", (uid, week_start, target_sub, target_sub))
                row = cur.fetchone()
                if row and dict(row).get("status") == "done":
                    skipped += 1
                    continue
                stats = _collect_week_stats(cur, uid, week_start, week_end, subject=target_sub)
                has_activity = (
                    int(stats.get("test_count") or 0) > 0
                    or int(stats.get("homework_total") or 0) > 0
                    or len(stats.get("weak_topics_by_tests") or []) > 0
                    or len(stats.get("weak_topics_by_mistakes") or []) > 0
                    or int(stats.get("learning_path_count") or 0) > 0
                )
            finally:
                conn.close()

            if has_activity:
                result = await _generate_ai_analysis(stats, user_name, subject=target_sub)
            else:
                result = _build_smart_fallback_analysis(stats, user_name, subject=target_sub)
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO weekly_ai_analyses(
                        user_id, week_start, week_end, subject, analysis_text, weak_topics_json,
                        recommendations_json, test_stats_json, homework_stats_json,
                        practice_questions_json, status, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,'done',?)
                    ON CONFLICT(user_id, week_start) DO UPDATE SET
                        subject=excluded.subject,
                        analysis_text=excluded.analysis_text,
                        weak_topics_json=excluded.weak_topics_json,
                        recommendations_json=excluded.recommendations_json,
                        test_stats_json=excluded.test_stats_json,
                        homework_stats_json=excluded.homework_stats_json,
                        practice_questions_json=excluded.practice_questions_json,
                        status='done',
                        updated_at=excluded.updated_at
                    """,
                    (
                        uid, week_start, week_end, target_sub,
                        str(result.get("analysis", "")),
                        json.dumps(result.get("weak_topics", []), ensure_ascii=False),
                        json.dumps(result.get("recommendations", []), ensure_ascii=False),
                        json.dumps(stats, ensure_ascii=False),
                        json.dumps({
                            "total": stats.get("homework_total", 0),
                            "completed": stats.get("homework_completed", 0),
                            "completion_pct": stats.get("homework_completion_pct", 0),
                        }, ensure_ascii=False),
                        json.dumps(result.get("practice_questions", []), ensure_ascii=False),
                        _now().isoformat(),
                    ),
                )
                conn.commit()
                processed += 1
            finally:
                conn.close()
        except Exception:
            logger.exception("Error generating weekly analysis for student %s", uid)
            errors += 1

    return {"total": total, "processed": processed, "skipped": skipped, "errors": errors}


def _weekly_payload(row: dict[str, Any], available_subjects: list[str] | None = None, selected_subject: str | None = None) -> dict[str, Any]:
    created_at = row.get("created_at")
    if hasattr(created_at, "isoformat"):
        created_at = created_at.isoformat()
    elif created_at is not None:
        created_at = str(created_at)
    return {
        "exists": True,
        "week_start": str(row["week_start"]),
        "week_end": str(row["week_end"]),
        "subject": str(row.get("subject") or selected_subject or "English"),
        "available_subjects": available_subjects or ["English"],
        "selected_subject": selected_subject or str(row.get("subject") or "English"),
        "status": str(row.get("status") or "done"),
        "analysis": row.get("analysis_text", ""),
        "weak_topics": json.loads(row.get("weak_topics_json") or "[]"),
        "recommendations": json.loads(row.get("recommendations_json") or "[]"),
        "test_stats": json.loads(row.get("test_stats_json") or "{}"),
        "homework_stats": json.loads(row.get("homework_stats_json") or "{}"),
        "practice_questions": json.loads(row.get("practice_questions_json") or "[]"),
        "created_at": created_at,
    }


@router.get("/student/personal-plan/weekly-analysis")
async def get_weekly_analysis(subject: str | None = Query(default=None), authorization: str | None = Header(default=None)):
    """Get the current week's AI analysis in the student's enrolled subject and language."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"]); week_start, week_end = _current_week_range()
    conn = get_conn()
    try:
        cur = conn.cursor()
        enrolled_subs = _student_enrolled_subjects(cur, uid, user)
        clean_sub = _normalize_subject_label(subject)
        active_sub = clean_sub if clean_sub and clean_sub in enrolled_subs else enrolled_subs[0]

        cur.execute(
            "SELECT * FROM weekly_ai_analyses WHERE user_id=? AND week_start=? AND (subject=? OR (subject IS NULL AND ?='English'))",
            (uid, week_start, active_sub, active_sub),
        )
        row = cur.fetchone()
        if row:
            row_dict = dict(row)
            # Agar processing holatida uzoq qolib ketgan bo'lsa (masalan server restart bo'lganida), qayta ishga tushiramiz
            if str(row_dict.get("status") or "") == "processing":
                upd = row_dict.get("updated_at") or row_dict.get("created_at")
                is_stale = False
                if upd:
                    try:
                        upd_str = str(upd).replace("Z", "+00:00")
                        upd_dt = datetime.fromisoformat(upd_str)
                        if (_now() - upd_dt).total_seconds() > 60:
                            is_stale = True
                    except Exception:
                        is_stale = True
                if is_stale:
                    stats = _collect_week_stats(cur, uid, week_start, week_end, subject=active_sub)
                    user_name = _student_name(user)
                    asyncio.create_task(_finish_weekly_analysis(user_id=uid, user_name=user_name, week_start=week_start, stats=stats, subject=active_sub))
            return _weekly_payload(row_dict, available_subjects=enrolled_subs, selected_subject=active_sub)

        # Collect live stats and auto-trigger generation if not yet generated
        stats = _collect_week_stats(cur, uid, week_start, week_end, subject=active_sub)
        user_name = _student_name(user)
        try:
            cur.execute(
                "INSERT INTO weekly_ai_analyses(user_id, week_start, week_end, subject, status, test_stats_json, homework_stats_json) "
                "VALUES(?,?,?,?,'processing',?,?) ON CONFLICT(user_id, week_start) DO UPDATE SET subject=excluded.subject, status='processing', updated_at=?",
                (uid, week_start, week_end, active_sub, json.dumps(stats), json.dumps({
                    "total": stats["homework_total"], "completed": stats["homework_completed"],
                    "completion_pct": stats["homework_completion_pct"],
                }), _now().isoformat()),
            )
            conn.commit()
            asyncio.create_task(_finish_weekly_analysis(user_id=uid, user_name=user_name, week_start=week_start, stats=stats, subject=active_sub))
        except Exception:
            pass

        lang = _detect_subject_language(active_sub)
        if lang == "ru":
            thinking_msg = "Diamondvoy готовит ваш еженедельный анализ..."
        elif lang == "en":
            thinking_msg = "Diamondvoy is preparing your weekly analysis..."
        else:
            thinking_msg = "Diamondvoy sizning haftalik tahlilingizni tayyorlamoqda..."
        return {
            "exists": True,
            "week_start": week_start,
            "week_end": week_end,
            "subject": active_sub,
            "available_subjects": enrolled_subs,
            "selected_subject": active_sub,
            "status": "processing",
            "analysis": thinking_msg,
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
async def generate_weekly_analysis(subject: str | None = Query(default=None), authorization: str | None = Header(default=None)):
    """Queue a weekly Diamondvoy analysis for the specified subject and return immediately for UI polling."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"]); week_start, week_end = _current_week_range()
    user_name = _student_name(user)
    conn = get_conn()
    try:
        cur = conn.cursor()
        enrolled_subs = _student_enrolled_subjects(cur, uid, user)
        clean_sub = _normalize_subject_label(subject)
        active_sub = clean_sub if clean_sub and clean_sub in enrolled_subs else enrolled_subs[0]

        stats = _collect_week_stats(cur, uid, week_start, week_end, subject=active_sub)
        cur.execute("SELECT status FROM weekly_ai_analyses WHERE user_id=? AND week_start=? AND (subject=? OR (subject IS NULL AND ?='English'))", (uid, week_start, active_sub, active_sub))
        current = cur.fetchone()
        if current and str(dict(current).get("status") or "") == "processing":
            return {"accepted": True, "success": True, "status": "processing", "week_start": week_start, "week_end": week_end, "subject": active_sub}

        # Mark as processing
        try:
            cur.execute(
                "INSERT INTO weekly_ai_analyses(user_id, week_start, week_end, subject, status, test_stats_json, homework_stats_json) "
                "VALUES(?,?,?,?,'processing',?,?) ON CONFLICT(user_id, week_start) DO UPDATE SET subject=excluded.subject, status='processing', updated_at=?",
                (uid, week_start, week_end, active_sub, json.dumps(stats), json.dumps({
                    "total": stats["homework_total"], "completed": stats["homework_completed"],
                    "completion_pct": stats["homework_completion_pct"],
                }), _now().isoformat()),
            )
        except Exception:
            cur.execute("DELETE FROM weekly_ai_analyses WHERE user_id=? AND week_start=?", (uid, week_start))
            cur.execute(
                "INSERT INTO weekly_ai_analyses(user_id, week_start, week_end, subject, status, test_stats_json, homework_stats_json) VALUES(?,?,?,?,'processing',?,?)",
                (uid, week_start, week_end, active_sub, json.dumps(stats), json.dumps({
                    "total": stats["homework_total"], "completed": stats["homework_completed"],
                    "completion_pct": stats["homework_completion_pct"],
                })),
            )
        conn.commit()
    finally:
        conn.close()
    asyncio.create_task(_finish_weekly_analysis(user_id=uid, user_name=user_name, week_start=week_start, stats=stats, subject=active_sub))
    return {"accepted": True, "success": True, "status": "processing", "week_start": week_start, "week_end": week_end, "subject": active_sub}


@router.get("/student/personal-plan/analysis-history")
async def get_analysis_history(subject: str | None = Query(default=None), authorization: str | None = Header(default=None)):
    """Get all previous weekly analyses for the student, optionally filtered by subject."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"])
    clean_sub = _normalize_subject_label(subject)
    conn = get_conn()
    try:
        cur = conn.cursor()
        if clean_sub:
            cur.execute(
                "SELECT id, week_start, week_end, subject, analysis_text, weak_topics_json, "
                "recommendations_json, test_stats_json, homework_stats_json, "
                "practice_questions_json, status, created_at "
                "FROM weekly_ai_analyses WHERE user_id=? AND (subject=? OR (subject IS NULL AND ?='English')) AND status='done' "
                "ORDER BY week_start DESC LIMIT 12",
                (uid, clean_sub, clean_sub),
            )
        else:
            cur.execute(
                "SELECT id, week_start, week_end, subject, analysis_text, weak_topics_json, "
                "recommendations_json, test_stats_json, homework_stats_json, "
                "practice_questions_json, status, created_at "
                "FROM weekly_ai_analyses WHERE user_id=? AND status='done' "
                "ORDER BY week_start DESC LIMIT 12",
                (uid,),
            )
        items = []
        for row in cur.fetchall():
            r = dict(row)
            created_at = r.get("created_at")
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            elif created_at is not None:
                created_at = str(created_at)
            items.append({
                "id": r["id"],
                "week_start": str(r["week_start"]),
                "week_end": str(r["week_end"]),
                "subject": str(r.get("subject") or "English"),
                "analysis": r.get("analysis_text", ""),
                "weak_topics": json.loads(r.get("weak_topics_json") or "[]"),
                "recommendations": json.loads(r.get("recommendations_json") or "[]"),
                "test_stats": json.loads(r.get("test_stats_json") or "{}"),
                "homework_stats": json.loads(r.get("homework_stats_json") or "{}"),
                "practice_questions": json.loads(r.get("practice_questions_json") or "[]"),
                "created_at": created_at,
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
        return {"answer": "Bu mavzuni kichik qismlarga bo‘lib takrorlang: avval qoida, keyin bir misol, so‘ng yengil mashq. Shu mavzudagi testlarni ham qayta ishlang."}


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

    # Keep every answer, not only mistakes, so a full practice attempt can be
    # reopened later. Wrong answers continue to feed the mistake notebook.
    ensure_schema()
    attempt_id = str(payload.get("attempt_id") or secrets.token_urlsafe(16)).strip()[:96]
    try:
        question_index = max(1, int(payload.get("question_index") or 1))
    except (TypeError, ValueError):
        question_index = 1
    try:
        total_questions = max(question_index, int(payload.get("total_questions") or question_index))
    except (TypeError, ValueError):
        total_questions = question_index
    subject = str(payload.get("subject") or "")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO personal_practice_attempts(user_id,attempt_id,subject,total_questions) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id,attempt_id) DO UPDATE SET subject=excluded.subject,total_questions=excluded.total_questions",
            (int(user["id"]), attempt_id, subject, total_questions),
        )
        cur.execute(
            "INSERT INTO personal_practice_attempt_items(user_id,attempt_id,question_index,subject,topic_key,prompt,options_json,selected_answer,correct_answer,explanation,is_correct) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(user_id,attempt_id,question_index) DO UPDATE SET selected_answer=excluded.selected_answer,correct_answer=excluded.correct_answer,explanation=excluded.explanation,is_correct=excluded.is_correct,options_json=excluded.options_json",
            (int(user["id"]), attempt_id, question_index, subject, topic, question,
             json.dumps(payload.get("options", []), ensure_ascii=False), selected, correct,
             explanation, 1 if is_correct else 0),
        )
        if not is_correct:
            cur.execute(
                "INSERT INTO mistake_notebook_items(user_id, source_type, source_id, subject, topic_key, prompt, "
                "options_json, selected_answer, correct_answer, explanation, review_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (int(user["id"]), "weekly_practice", f"{attempt_id}:{question_index}", subject, topic, question,
                 json.dumps(payload.get("options", []), ensure_ascii=False), selected, correct, explanation,
                 mistake_next_review_at(_now(), 0).isoformat()),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "correct": is_correct,
        "explanation": explanation,
        "correct_answer": correct,
        "attempt_id": attempt_id,
    }


@router.post("/student/personal-plan/practice-test/{attempt_id}/complete")
async def complete_practice_attempt(attempt_id: str, authorization: str | None = Header(default=None)):
    """Finalize a personal practice once and write its aggregate to test history."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"]); key = str(attempt_id or "").strip()[:96]
    if not key:
        raise HTTPException(status_code=400, detail="Missing practice attempt")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT subject,total_questions,completed_at FROM personal_practice_attempts WHERE user_id=? AND attempt_id=? LIMIT 1", (uid, key))
        attempt = dict(cur.fetchone() or {})
        if not attempt:
            raise HTTPException(status_code=404, detail="Practice attempt not found")
        cur.execute("SELECT is_correct FROM personal_practice_attempt_items WHERE user_id=? AND attempt_id=?", (uid, key))
        rows = _dicts(cur.fetchall())
        correct = sum(1 for row in rows if bool(int(row.get("is_correct") or 0)))
        wrong = max(0, len(rows) - correct)
        skipped = max(0, int(attempt.get("total_questions") or len(rows)) - len(rows))
        first_completion = not attempt.get("completed_at")
        if first_completion:
            cur.execute("UPDATE personal_practice_attempts SET completed_at=? WHERE user_id=? AND attempt_id=?", (_now().isoformat(), uid, key))
        conn.commit()
    finally:
        conn.close()
    if first_completion:
        callback = _runtime.get("add_test_history")
        if callback:
            try:
                callback(uid, "weekly_practice", str(attempt.get("subject") or ""), correct, wrong, skipped)
            except Exception:
                pass
    return {"attempt_id": key, "correct": correct, "wrong": wrong, "skipped": skipped, "total": max(0, int(attempt.get("total_questions") or len(rows))), "completed": True}


@router.get("/student/personal-plan/practice-test/history")
async def personal_practice_history(limit: int = 20, authorization: str | None = Header(default=None)):
    """Student-owned practice history, including every question and answer."""
    user = _user(authorization); _require(user, {"student"}); ensure_schema()
    uid = int(user["id"])
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM personal_practice_attempts WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (uid, max(1, min(50, int(limit or 20)))))
        attempts = _dicts(cur.fetchall())
        for attempt in attempts:
            key = str(attempt.get("attempt_id") or "")
            cur.execute("SELECT * FROM personal_practice_attempt_items WHERE user_id=? AND attempt_id=? ORDER BY question_index ASC", (uid, key))
            items = _dicts(cur.fetchall())
            for item in items:
                try:
                    item["options"] = json.loads(str(item.pop("options_json", "[]") or "[]"))
                except Exception:
                    item["options"] = []
            attempt["items"] = items
            attempt["correct"] = sum(1 for item in items if bool(int(item.get("is_correct") or 0)))
            attempt["wrong"] = max(0, len(items) - int(attempt["correct"]))
            attempt["skipped"] = max(0, int(attempt.get("total_questions") or len(items)) - len(items))
        return {"items": attempts}
    finally:
        conn.close()


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
