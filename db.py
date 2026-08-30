import threading
import logging
import math
import random
import string
import os
import queue
import re
import json
import pytz
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
from config import ADMIN_CHAT_IDS, ALL_ADMIN_IDS, DATABASE_URL
from logging_config import get_logger
from passwords import (
    generate_password as _generate_secure_password,
    hash_password,
    verify_password,
)
import psycopg
from psycopg.rows import dict_row
import time
try:
    from psycopg_pool import ConnectionPool
except Exception:  # pragma: no cover - optional runtime dependency
    ConnectionPool = None

logger = get_logger(__name__)
Path('data').mkdir(parents=True, exist_ok=True)
DB_WRITE_LOCK = threading.Lock()
_PG_CONNECT_MAX_ATTEMPTS = int(os.getenv("PG_CONNECT_MAX_ATTEMPTS", "4"))
_PG_CONNECT_BACKOFF_SEC = float(os.getenv("PG_CONNECT_BACKOFF_SEC", "0.5"))
_PG_POOL_ENABLED = os.getenv("PG_POOL_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on")
_PG_POOL_MIN_SIZE = max(0, int(os.getenv("PG_POOL_MIN_SIZE", "1")))
_PG_POOL_MAX_SIZE = max(1, int(os.getenv("PG_POOL_MAX_SIZE", "16")))
_PG_POOL_TIMEOUT = max(1.0, float(os.getenv("PG_POOL_TIMEOUT", "15")))
_PG_POOL_RECYCLE_ON_TIMEOUT = os.getenv("PG_POOL_RECYCLE_ON_TIMEOUT", "true").strip().lower() in ("1", "true", "yes", "on")
_PG_POOL: Any | None = None
_PG_POOL_LOCK = threading.Lock()
_SCHEMA_READY: set[str] = set()
_SCHEMA_READY_LOCK = threading.Lock()


def _schema_ready(name: str) -> bool:
    with _SCHEMA_READY_LOCK:
        return name in _SCHEMA_READY


def _mark_schema_ready(name: str) -> None:
    with _SCHEMA_READY_LOCK:
        _SCHEMA_READY.add(name)


def _safe_get(row, key, default=None):
    """Safely get a value from a database row or mapping-style object."""
    if row is None:
        return default
    if hasattr(row, 'get'):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def row_value(row, key, default=None):
    """Compatibility helper for dict and mapping-style rows."""
    return _safe_get(row, key, default)




def _to_postgres_sql(sql: str) -> str:
    """
    Minimal SQL compatibility for existing sqlite-style queries.
    - legacy placeholders `?` -> postgres `%s`
    """
    q = (sql or "").replace("?", "%s")
    return q


class _PgCursorCompat:
    def __init__(self, cur):
        self._cur = cur

    def execute(self, sql, params=None):
        q = _to_postgres_sql(sql)
        if params is None:
            return self._cur.execute(q)
        return self._cur.execute(q, params)

    def executemany(self, sql, seq_of_params):
        q = _to_postgres_sql(sql)
        return self._cur.executemany(q, seq_of_params)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    def __enter__(self):
        self._cur.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._cur.__exit__(exc_type, exc_val, exc_tb)

    def __getattr__(self, name):
        return getattr(self._cur, name)


class _PgConnCompat:
    def __init__(self, conn, release=None):
        self._conn = conn
        self._release = release
        self._closed = False

    def cursor(self):
        return _PgCursorCompat(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        if self._closed:
            return None
        self._closed = True
        if self._release is not None:
            # Return pooled connections cleanly even after read-only SELECTs or
            # handled statement errors. Callers explicitly commit writes first.
            try:
                self._conn.rollback()
            except Exception:
                pass
            return self._release()
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()
        return False

def _is_postgres_enabled() -> bool:
    return bool(DATABASE_URL and str(DATABASE_URL).strip().lower().startswith(('postgresql://', 'postgres://')))


def _pg_connect_kwargs() -> dict:
    return {
        "row_factory": dict_row,
        "connect_timeout": 8,
        "keepalives": 1,
        "keepalives_idle": 20,
        "keepalives_interval": 5,
        "keepalives_count": 3,
    }


class _SimplePgConnectionContext:
    def __init__(self, pool: "_SimplePgPool"):
        self._pool = pool
        self._conn = None

    def __enter__(self):
        self._conn = self._pool.acquire()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._pool.release(self._conn)
        self._conn = None
        return False


class _SimplePgPool:
    """Small per-worker psycopg pool used when psycopg_pool is unavailable."""

    def __init__(self, max_size: int):
        self.max_size = max(1, int(max_size))
        self._idle: queue.LifoQueue = queue.LifoQueue(maxsize=self.max_size)
        self._lock = threading.Lock()
        self._total = 0

    def _connect(self):
        return psycopg.connect(DATABASE_URL, **_pg_connect_kwargs())

    def acquire(self):
        while True:
            try:
                conn = self._idle.get_nowait()
                if not getattr(conn, "closed", False):
                    return conn
                with self._lock:
                    self._total = max(0, self._total - 1)
            except queue.Empty:
                break
        with self._lock:
            if self._total < self.max_size:
                self._total += 1
                create_new = True
            else:
                create_new = False
        if create_new:
            try:
                return self._connect()
            except Exception:
                with self._lock:
                    self._total = max(0, self._total - 1)
                raise
        try:
            conn = self._idle.get(timeout=_PG_POOL_TIMEOUT)
        except queue.Empty:
            # A leaked or broken checked-out connection can make a per-worker
            # fallback pool believe every slot is busy forever. Production
            # should degrade by recycling one stale slot instead of queuing
            # health/auth/navigation requests until they time out.
            if not _PG_POOL_RECYCLE_ON_TIMEOUT:
                raise
            logger.warning("postgres simple pool timeout; recycling one stale slot pid=%s max_size=%s", os.getpid(), self.max_size)
            with self._lock:
                self._total = max(0, self._total - 1)
                self._total += 1
            try:
                return self._connect()
            except Exception:
                with self._lock:
                    self._total = max(0, self._total - 1)
                raise
        if getattr(conn, "closed", False):
            with self._lock:
                self._total = max(0, self._total - 1)
            return self.acquire()
        return conn

    def release(self, conn) -> None:
        if conn is None:
            return
        if getattr(conn, "closed", False):
            with self._lock:
                self._total = max(0, self._total - 1)
            return
        try:
            self._idle.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            finally:
                with self._lock:
                    self._total = max(0, self._total - 1)

    def connection(self):
        return _SimplePgConnectionContext(self)


def _get_pg_pool():
    global _PG_POOL
    if not (_PG_POOL_ENABLED and _is_postgres_enabled()):
        return None
    if _PG_POOL is not None:
        return _PG_POOL
    with _PG_POOL_LOCK:
        if _PG_POOL is None:
            if ConnectionPool is not None:
                _PG_POOL = ConnectionPool(
                    conninfo=DATABASE_URL,
                    min_size=min(_PG_POOL_MIN_SIZE, _PG_POOL_MAX_SIZE),
                    max_size=_PG_POOL_MAX_SIZE,
                    timeout=_PG_POOL_TIMEOUT,
                    kwargs=_pg_connect_kwargs(),
                    open=True,
                    name=f"diamond-db-{os.getpid()}",
                )
            else:
                _PG_POOL = _SimplePgPool(max_size=_PG_POOL_MAX_SIZE)
        return _PG_POOL


def _execute_ddl_candidates(cur, statements: list[str] | tuple[str, ...]) -> None:
    if not statements:
        return
    items = [str(stmt or "").strip() for stmt in statements if str(stmt or "").strip()]
    if not items:
        return
    if _is_postgres_enabled():
        # The first candidate is the PostgreSQL DDL in all paired call sites.
        # Trying the SQLite fallback against Postgres masks the real error and
        # can fail startup with AUTOINCREMENT syntax after a transient DDL race.
        order = [0]
    elif len(items) > 1:
        order = list(range(1, len(items)))
    else:
        order = [0]
    last_error = None
    for idx in order:
        try:
            cur.execute(items[idx])
            return
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise last_error


def get_conn():
    if not _is_postgres_enabled():
        raise RuntimeError("PostgreSQL-only runtime: DATABASE_URL must be a postgresql:// URL")
    pool = _get_pg_pool()
    if pool is not None:
        ctx = pool.connection()
        conn = ctx.__enter__()

        def _release():
            return ctx.__exit__(None, None, None)

        return _PgConnCompat(conn, release=_release)
    last_error = None
    for attempt in range(1, max(1, _PG_CONNECT_MAX_ATTEMPTS) + 1):
        try:
            conn = psycopg.connect(DATABASE_URL, **_pg_connect_kwargs())
            return _PgConnCompat(conn)
        except Exception as e:
            last_error = e
            if attempt >= max(1, _PG_CONNECT_MAX_ATTEMPTS):
                break
            sleep_s = _PG_CONNECT_BACKOFF_SEC * (2 ** (attempt - 1))
            logger.warning(
                "Postgres connect failed attempt=%s/%s; retrying in %.2fs: %s",
                attempt,
                _PG_CONNECT_MAX_ATTEMPTS,
                sleep_s,
                e,
            )
            time.sleep(sleep_s)
    raise last_error


def _init_postgres_db():
    logger.info("Initializing PostgreSQL database...")
    conn = None
    try:
        conn = get_conn()
        logger.info("PostgreSQL connection established successfully")
        cur = conn.cursor()
        
        # Test the connection
        cur.execute("SELECT version()")
        version = cur.fetchone()
        logger.info(f"PostgreSQL version: {version}")
        
        # Check if bot_runtime_state table exists and its schema
        try:
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'bot_runtime_state'
                ORDER BY ordinal_position
            """)
            existing_schema = cur.fetchall()
            if existing_schema:
                logger.info(f"Existing bot_runtime_state schema: {existing_schema}")
            else:
                logger.info("bot_runtime_state table does not exist yet")
        except Exception as schema_e:
            logger.warning(f"Could not check existing schema: {schema_e}")
        
        # Create all tables
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS users (
                id BIGSERIAL PRIMARY KEY,
                telegram_id TEXT UNIQUE,
                login_id TEXT UNIQUE,
                password TEXT,
                password_used INTEGER DEFAULT 0,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                parent_phone TEXT,
                subject TEXT,
                login_type INTEGER DEFAULT 1,
                level TEXT,
                family_group_id BIGINT,
                access_enabled INTEGER DEFAULT 0,
                access_expires_at TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                failed_logins INTEGER DEFAULT 0,
                blocked INTEGER DEFAULT 0,
                test_in_progress INTEGER DEFAULT 0,
                test_subject TEXT,
                test_question_index INTEGER DEFAULT 0,
                test_score INTEGER DEFAULT 0,
                test_questions TEXT,
                pending_approval INTEGER DEFAULT 0,
                owner_admin_id BIGINT,
                group_id BIGINT,
                language TEXT DEFAULT 'uz',
                logged_in INTEGER DEFAULT 0,
                last_login_at TIMESTAMP,
                last_activity TEXT,
                session_started TEXT,
                logout_time TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id BIGSERIAL PRIMARY KEY,
                subject TEXT NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS family_groups (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                teacher_id BIGINT,
                level TEXT,
                subject TEXT,
                lesson_date TEXT,
                lesson_days TEXT,
                lesson_start TEXT,
                lesson_end TEXT,
                tz TEXT DEFAULT 'Asia/Tashkent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                owner_admin_id BIGINT,
                active INTEGER DEFAULT 1,
                course_id BIGINT,
                course_title TEXT,
                monthly_fee_text TEXT,
                telegram_group_url TEXT,
                pricing_type TEXT DEFAULT 'group',
                lang TEXT DEFAULT 'uz'
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                subject TEXT,
                score INTEGER,
                max_score INTEGER DEFAULT 100,
                level TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                group_id BIGINT NOT NULL,
                date TEXT NOT NULL,
                status TEXT DEFAULT 'Absent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_groups (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                group_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                left_date TIMESTAMP,
                UNIQUE(user_id, group_id)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS monthly_payments (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                ym TEXT NOT NULL,
                group_id BIGINT,
                subject TEXT,
                paid INTEGER DEFAULT 0,
                paid_at TEXT,
                notified_days TEXT,
                payment_dcoin_amount DOUBLE PRECISION,
                paid_by_admin_id BIGINT,
                paid_by_admin_name TEXT,
                payment_type TEXT,
                UNIQUE(user_id, ym, group_id)
            )
        """)
        
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_monthly_payments_user_ym_group ON monthly_payments(user_id, ym, group_id)')
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance_sessions (
                id BIGSERIAL PRIMARY KEY,
                group_id BIGINT NOT NULL,
                date TEXT NOT NULL,
                status TEXT DEFAULT 'open',
                closed_by TEXT,
                notified_admin INTEGER DEFAULT 0,
                notified_teacher INTEGER DEFAULT 0,
                notified_admin_pre INTEGER DEFAULT 0,
                notified_admin_post INTEGER DEFAULT 0,
                notified_teacher_pre INTEGER DEFAULT 0,
                notified_teacher_post INTEGER DEFAULT 0,
                admin_panel_chat_id BIGINT,
                admin_panel_message_id BIGINT,
                teacher_panel_chat_id BIGINT,
                teacher_panel_message_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, date)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS words (
                id BIGSERIAL PRIMARY KEY,
                word TEXT NOT NULL,
                subject TEXT NOT NULL,
                language TEXT NOT NULL,
                level TEXT,
                translation_uz TEXT,
                translation_ru TEXT,
                definition TEXT,
                example TEXT,
                added_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vocabulary_imports (
                id BIGSERIAL PRIMARY KEY,
                file_name TEXT NOT NULL,
                added_by BIGINT,
                subject TEXT NOT NULL,
                language TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vocab_seed_pool (
                id BIGSERIAL PRIMARY KEY,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                language TEXT NOT NULL,
                word TEXT NOT NULL,
                word_norm TEXT NOT NULL,
                translation_uz TEXT,
                translation_ru TEXT,
                definition TEXT,
                example TEXT,
                source TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subject, level, language, word_norm)
            )
            """
        )
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_preferences (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                preferred_translation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS vocab_word_mastery (
                user_id BIGINT NOT NULL,
                word_id BIGINT NOT NULL,
                question_type TEXT NOT NULL,
                consecutive_correct INTEGER NOT NULL DEFAULT 0,
                cooldown_until TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, word_id, question_type)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                name TEXT PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS diamond_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                dcoin_change DOUBLE PRECISION NOT NULL,
                dpoints_change DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subject TEXT,
                change_type TEXT
            )
        """)

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_dpoints (
                user_id BIGINT PRIMARY KEY,
                dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Critical D'coin source-of-truth table (must exist before bot startup).
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_subject_dcoins (
                user_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                balance DOUBLE PRECISION NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, subject)
            )
            """
        )
        # Compatibility: some old/manual schemas used `dcoin` column name.
        if _is_postgres_enabled():
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='user_subject_dcoins' AND column_name='dcoin'
                LIMIT 1
                """
            )
            if cur.fetchone():
                cur.execute("ALTER TABLE user_subject_dcoins RENAME COLUMN dcoin TO balance")
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_subject_dcoins_user_id
            ON user_subject_dcoins(user_id)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_subject_dcoins_subject
            ON user_subject_dcoins(subject)
            """
        )
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                feedback_text TEXT NOT NULL,
                is_anonymous INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                topic_id TEXT,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grammar_attempts (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                topic_id TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                last_attempt_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, topic_id)
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS overdue_penalty_log (
                user_id BIGINT NOT NULL,
                group_id BIGINT NOT NULL,
                ym TEXT NOT NULL,
                penalty_date TEXT NOT NULL,
                PRIMARY KEY (user_id, group_id, ym, penalty_date)
            )
        """)

        # Shared daily question set per calendar day (bootstrap; see also ensure_daily_tests_schema).
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daily_test_day_question_sets (
                id BIGSERIAL PRIMARY KEY,
                test_date DATE NOT NULL,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                total_questions INTEGER NOT NULL,
                bank_ids_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(test_date, subject, level)
            )
        """)
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_daily_test_day_sets_lookup
                ON daily_test_day_question_sets (test_date, subject, level)
                """
            )
        except Exception:
            pass
        try:
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_daily_test_day_sets_date
                ON daily_test_day_question_sets (test_date)
                """
            )
        except Exception:
            pass

        # Handle bot_runtime_state table with proper schema migration
        try:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'bot_runtime_state'
            """)
            runtime_cols = {r["column_name"] for r in cur.fetchall()}
            # Legacy schema detected (key/value/updated_at etc.) -> recreate clean table.
            if runtime_cols and "started_at" not in runtime_cols:
                logger.warning(
                    f"Legacy bot_runtime_state schema detected ({sorted(runtime_cols)}); recreating table"
                )
                cur.execute("DROP TABLE IF EXISTS bot_runtime_state")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bot_runtime_state (
                    id BIGSERIAL PRIMARY KEY,
                    started_at TIMESTAMP NOT NULL
                )
            """)
        except Exception as e:
            # Table might exist with different schema, try to drop and recreate
            logger.warning(f"bot_runtime_state table issue: {e}, attempting to recreate...")
            try:
                cur.execute("DROP TABLE IF EXISTS bot_runtime_state")
                cur.execute("""
                    CREATE TABLE bot_runtime_state (
                        id BIGSERIAL PRIMARY KEY,
                        started_at TIMESTAMP NOT NULL
                    )
                """)
            except Exception as drop_e:
                logger.error(f"Failed to recreate bot_runtime_state: {drop_e}")
                raise drop_e
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                author TEXT,
                category TEXT,
                level TEXT,
                thumbnail_url TEXT,
                video_url TEXT,
                duration INTEGER DEFAULT 0,
                is_published INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS video_progress (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                video_id BIGINT NOT NULL,
                watched_seconds INTEGER DEFAULT 0,
                last_position_seconds INTEGER DEFAULT 0,
                max_watched_seconds INTEGER DEFAULT 0,
                duration_seconds INTEGER DEFAULT 0,
                completed INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, video_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS video_views (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                video_id BIGINT NOT NULL,
                watched_seconds INTEGER DEFAULT 0,
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, video_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS diamondvoy_chat_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_diamondvoy_history_user ON diamondvoy_chat_history(user_id, created_at DESC)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                author TEXT,
                category TEXT,
                level TEXT,
                cover_url TEXT,
                pdf_url TEXT,
                price DOUBLE PRECISION DEFAULT 0,
                deadline_days INTEGER DEFAULT 0,
                is_published INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS book_questions (
                id BIGSERIAL PRIMARY KEY,
                book_id BIGINT NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                explanation TEXT,
                question_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS student_book_purchases (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                book_id BIGINT NOT NULL,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                UNIQUE(user_id, book_id)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS teacher_homework_settings (
                teacher_id BIGINT PRIMARY KEY,
                ai_auto_grade INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure row exists - let BIGSERIAL handle the ID automatically
        try:
            cur.execute('''
                INSERT INTO bot_runtime_state (started_at)
                VALUES (CURRENT_TIMESTAMP)
                ON CONFLICT DO NOTHING
            ''')
        except Exception as insert_e:
            # If INSERT fails due to schema issues, try a simpler approach
            logger.warning(f"INSERT failed: {insert_e}, trying alternative...")
            # psycopg keeps transaction aborted after failed query; rollback first.
            conn.rollback()
            try:
                cur.execute('''
                    INSERT INTO bot_runtime_state (id, started_at)
                    VALUES (1, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET started_at = CURRENT_TIMESTAMP
                ''')
            except Exception as final_e:
                logger.error(f"Failed to initialize bot_runtime_state: {final_e}")
                # If all else fails, just continue without this table
                logger.warning("Continuing without bot_runtime_state table")
        
        logger.info("PostgreSQL database initialization completed successfully")
        conn.commit()
        
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL database: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()


def _bootstrap_postgres_after_base_tables() -> None:
    """ensure_* migrations after _init_postgres_db (startup and after full schema wipe)."""
    print("[STARTUP][DB] ensure_overdue_penalty_log_table()")
    ensure_overdue_penalty_log_table()
    print("[STARTUP][DB] ensure_overdue_penalty_log_table() done")

    print("[STARTUP][DB] ensure_attendance_sessions_schema()")
    ensure_attendance_sessions_schema()
    print("[STARTUP][DB] ensure_attendance_sessions_schema() done")

    print("[STARTUP][DB] ensure_temporary_group_assignments_schema()")
    ensure_temporary_group_assignments_schema()
    print("[STARTUP][DB] ensure_temporary_group_assignments_schema() done")

    print("[STARTUP][DB] ensure_admin_student_shares_schema()")
    ensure_admin_student_shares_schema()
    print("[STARTUP][DB] ensure_admin_student_shares_schema() done")

    print("[STARTUP][DB] ensure_daily_tests_schema()")
    ensure_daily_tests_schema()
    print("[STARTUP][DB] ensure_daily_tests_schema() done")

    print("[STARTUP][DB] ensure_arena_questions_schema()")
    ensure_arena_questions_schema()
    print("[STARTUP][DB] ensure_arena_questions_schema() done")

    print("[STARTUP][DB] ensure_arena_group_schema()")
    ensure_arena_group_schema()
    print("[STARTUP][DB] ensure_arena_group_schema() done")

    print("[STARTUP][DB] ensure_video_teachers_schema()")
    ensure_video_teachers_schema()
    print("[STARTUP][DB] ensure_video_teachers_schema() done")

    print("[STARTUP][DB] ensure_arena_group_extended_schema()")
    ensure_arena_group_extended_schema()
    print("[STARTUP][DB] ensure_arena_group_extended_schema() done")

    print("[STARTUP][DB] ensure_arena_other_sessions_schema()")
    ensure_arena_other_sessions_schema()
    print("[STARTUP][DB] ensure_arena_other_sessions_schema() done")

    print("[STARTUP][DB] ensure_student_ai_chat_schema()")
    ensure_student_ai_chat_schema()
    print("[STARTUP][DB] ensure_student_ai_chat_schema() done")

    print("[STARTUP][DB] ensure_vocab_word_mastery_schema()")
    ensure_vocab_word_mastery_schema()
    print("[STARTUP][DB] ensure_vocab_word_mastery_schema() done")

    print("[STARTUP][DB] ensure_vocab_seed_pool_schema()")
    ensure_vocab_seed_pool_schema()
    print("[STARTUP][DB] ensure_vocab_seed_pool_schema() done")

    print("[STARTUP][DB] ensure_dpoints_schema()")
    ensure_dpoints_schema()
    print("[STARTUP][DB] ensure_dpoints_schema() done")

    print("[STARTUP][DB] ensure_subject_dcoin_schema()")
    ensure_subject_dcoin_schema()
    print("[STARTUP][DB] ensure_subject_dcoin_schema() done")

    print("[STARTUP][DB] ensure_user_subject_schema()")
    ensure_user_subject_schema()
    print("[STARTUP][DB] ensure_user_subject_schema() done")

    print("[STARTUP][DB] ensure_dcoin_schema_migrations()")
    ensure_dcoin_schema_migrations()
    print("[STARTUP][DB] ensure_dcoin_schema_migrations() done")

    print("[STARTUP][DB] ensure_teacher_kpi/materials/notes_schema()")
    ensure_teacher_kpi_schema()
    ensure_teacher_materials_schema()
    ensure_teacher_notes_schema()
    print("[STARTUP][DB] ensure_teacher_kpi/materials/notes_schema() done")


    print("[STARTUP][DB] ensure_duel_matchmaking_schema()")
    ensure_duel_matchmaking_schema()
    print("[STARTUP][DB] ensure_duel_matchmaking_schema() done")

    print("[STARTUP][DB] ensure_arena_extras_schema()")
    ensure_arena_extras_schema()
    print("[STARTUP][DB] ensure_arena_extras_schema() done")

    print("[STARTUP][DB] ensure_support_lessons_schema()")
    ensure_support_lessons_schema()
    print("[STARTUP][DB] ensure_support_lessons_schema() done")

    print("[STARTUP][DB] ensure_lesson_otmen_requests_schema()")
    ensure_lesson_otmen_requests_schema()
    print("[STARTUP][DB] ensure_lesson_otmen_requests_schema() done")

    print("[STARTUP][DB] ensure_diamondvoy_history_table()")
    ensure_diamondvoy_history_table()
    print("[STARTUP][DB] ensure_diamondvoy_history_table() done")

    print("[STARTUP][DB] ensure_diamondvoy_chat_schema()")
    ensure_diamondvoy_chat_schema()
    print("[STARTUP][DB] ensure_diamondvoy_chat_schema() done")

    print("[STARTUP][DB] ensure_universal_chat_schema()")
    ensure_universal_chat_schema()
    print("[STARTUP][DB] ensure_universal_chat_schema() done")

    print("[STARTUP][DB] ensure_media_assets_schema()")
    ensure_media_assets_schema()
    print("[STARTUP][DB] ensure_media_assets_schema() done")

    print("[STARTUP][DB] ensure_gifts_schema()")
    ensure_gifts_schema()
    print("[STARTUP][DB] ensure_gifts_schema() done")

    print("[STARTUP][DB] ensure_homework_schema()")
    ensure_homework_schema()
    print("[STARTUP][DB] ensure_homework_schema() done")

    print("[STARTUP][DB] ensure_video_book_stats_schema()")
    ensure_video_book_stats_schema()
    print("[STARTUP][DB] ensure_video_book_stats_schema() done")

    print("[STARTUP][DB] ensure_telegram_group_chats_schema()")
    ensure_telegram_group_chats_schema()
    print("[STARTUP][DB] ensure_telegram_group_chats_schema() done")

def ensure_video_book_stats_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    schema_lock_acquired = False
    try:
        if _is_postgres_enabled():
            cur.execute("SELECT pg_advisory_lock(?)", (92025052503,))
            schema_lock_acquired = True
    except Exception:
        logger.warning("video/book stats schema lock could not be acquired", exc_info=True)
    try:
        _ensure_table_columns(
            cur,
            "videos",
            [
                ("subject", "TEXT"),
                ("view_count", "INTEGER DEFAULT 0"),
                ("like_count", "INTEGER DEFAULT 0"),
                ("teacher_id", "BIGINT"),
            ],
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        _ensure_table_columns(
            cur,
            "video_progress",
            [
                ("has_counted_view", "INTEGER DEFAULT 0"),
                ("last_position_seconds", "INTEGER DEFAULT 0"),
                ("max_watched_seconds", "INTEGER DEFAULT 0"),
                ("duration_seconds", "INTEGER DEFAULT 0"),
            ],
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS video_views (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    video_id BIGINT NOT NULL,
                    watched_seconds INTEGER DEFAULT 0,
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, video_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS video_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    video_id INTEGER NOT NULL,
                    watched_seconds INTEGER DEFAULT 0,
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, video_id)
                )
                """,
            ],
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_video_views_video ON video_views(video_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_video_views_user_video ON video_views(user_id, video_id)")
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS video_view_events (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    video_id BIGINT NOT NULL,
                    watched_seconds INTEGER DEFAULT 0,
                    source TEXT DEFAULT 'play',
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS video_view_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    video_id INTEGER NOT NULL,
                    watched_seconds INTEGER DEFAULT 0,
                    source TEXT DEFAULT 'play',
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_video_view_events_video ON video_view_events(video_id, viewed_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_video_view_events_user_video ON video_view_events(user_id, video_id, viewed_at)")
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS video_likes (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    video_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, video_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS video_likes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    video_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, video_id)
                )
                """,
            ],
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_video_likes_video ON video_likes(video_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_video_likes_user_video ON video_likes(user_id, video_id)")
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        _ensure_table_columns(
            cur,
            "books",
            [
                ("subject", "TEXT"),
                ("purchase_count", "INTEGER DEFAULT 0"),
            ],
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        if schema_lock_acquired:
            try:
                cur.execute("SELECT pg_advisory_unlock(?)", (92025052503,))
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
        conn.close()

def wipe_postgresql_database_and_reinit() -> None:
    """
    DROP public schema and recreate all application tables. Irreversible.
    Caller must enforce admin + secret checks. Uses DB_WRITE_LOCK.
    """
    if not _is_postgres_enabled():
        raise RuntimeError("PostgreSQL only: DATABASE_URL required for wipe")
    with DB_WRITE_LOCK:
        raw = psycopg.connect(DATABASE_URL, autocommit=True)
        try:
            with raw.cursor() as cur:
                cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
                cur.execute("CREATE SCHEMA public")
                cur.execute("GRANT ALL ON SCHEMA public TO PUBLIC")
        finally:
            raw.close()
        logger.critical("PostgreSQL public schema dropped; reinitializing all tables")
        print("[WIPE][DB] _init_postgres_db() starting")
        _init_postgres_db()
        print("[WIPE][DB] _init_postgres_db() done")
        _bootstrap_postgres_after_base_tables()
        logger.info("PostgreSQL wipe + reinit completed")


def init_db():
    """Birinchi marta ishga tushganda tablelarni yaratadi."""
    if _is_postgres_enabled():
        print("[STARTUP][DB] _init_postgres_db() starting")
        _init_postgres_db()
        print("[STARTUP][DB] _init_postgres_db() done")
        logger.info("✅ PostgreSQL tables initialized")
        _bootstrap_postgres_after_base_tables()
        return
    raise RuntimeError("PostgreSQL-only runtime: SQLite/.db startup is disabled")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id TEXT UNIQUE,
        login_id TEXT UNIQUE,
        password TEXT,
        password_used INTEGER DEFAULT 0,
        first_name TEXT,
        last_name TEXT,
        phone TEXT,
        subject TEXT,
        login_type INTEGER DEFAULT 1,
        level TEXT,
        family_group_id INTEGER,
        access_enabled INTEGER DEFAULT 0,
        access_expires_at TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        failed_logins INTEGER DEFAULT 0,
        blocked INTEGER DEFAULT 0,
        test_in_progress INTEGER DEFAULT 0,
        test_subject TEXT,
        test_question_index INTEGER DEFAULT 0,
        test_score INTEGER DEFAULT 0,
        test_questions TEXT,
        pending_approval INTEGER DEFAULT 0,
        owner_admin_id INTEGER,
        group_id INTEGER,
        language TEXT DEFAULT 'uz',
        logged_in INTEGER DEFAULT 0,
        last_login_at TEXT,
        last_activity TEXT,
        session_started TEXT,
        logout_time TEXT,
        active INTEGER DEFAULT 1
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        question TEXT NOT NULL,
        option_a TEXT NOT NULL,
        option_b TEXT NOT NULL,
        option_c TEXT NOT NULL,
        option_d TEXT NOT NULL,
        correct_option TEXT NOT NULL
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS family_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS test_results (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT,
        subject TEXT,
        score INTEGER,
        max_score INTEGER DEFAULT 100,
        level TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    # Guruhlar jadvali
    cur.execute('''
    CREATE TABLE IF NOT EXISTS groups (
        id BIGSERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        teacher_id BIGINT,
        level TEXT,
        lesson_date TIMESTAMP,
        lesson_start TIMESTAMP,
        lesson_end TIMESTAMP,
        tz TEXT DEFAULT 'Asia/Tashkent',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(teacher_id) REFERENCES users(id)
    )
    ''')

    # Davomat jadvali
    cur.execute('''
    CREATE TABLE IF NOT EXISTS attendance (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        group_id BIGINT NOT NULL,
        date TIMESTAMP NOT NULL,
        status TEXT DEFAULT 'Absent',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(group_id) REFERENCES groups(id)
    )
    ''')

    # User-group join table for multi-group students
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_groups (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        group_id BIGINT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        left_date TIMESTAMP,
        UNIQUE(user_id, group_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(group_id) REFERENCES groups(id)
    )
    ''')

    # Monthly payments with optional group scope
    cur.execute('''
    CREATE TABLE IF NOT EXISTS monthly_payments (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        ym TEXT NOT NULL,
        group_id BIGINT,
        subject TEXT,
        paid INTEGER DEFAULT 0,
        paid_at TIMESTAMP,
        notified_days TEXT,
        payment_dcoin_amount DOUBLE PRECISION,
        paid_by_admin_id BIGINT,
        paid_by_admin_name TEXT,
        payment_type TEXT,
        UNIQUE(user_id, ym, group_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(group_id) REFERENCES groups(id)
    )
    ''')

    # Migratsiya jadvali
    cur.execute('''
    CREATE TABLE IF NOT EXISTS _migrations (
        name TEXT PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Vocabulary tables
    cur.execute('''
    CREATE TABLE IF NOT EXISTS words (
        id BIGSERIAL PRIMARY KEY,
        word TEXT NOT NULL,
        subject TEXT NOT NULL,
        language TEXT NOT NULL,
        level TEXT,
        translation_uz TEXT,
        translation_ru TEXT,
        definition TEXT,
        example TEXT,
        added_by BIGINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(added_by) REFERENCES users(id)
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS vocabulary_imports (
        id BIGSERIAL PRIMARY KEY,
        file_name TEXT NOT NULL,
        added_by BIGINT,
        subject TEXT NOT NULL,
        language TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(added_by) REFERENCES users(id)
    )
    ''')

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS vocab_seed_pool (
            id BIGSERIAL PRIMARY KEY,
            subject TEXT NOT NULL,
            level TEXT NOT NULL,
            language TEXT NOT NULL,
            word TEXT NOT NULL,
            word_norm TEXT NOT NULL,
            translation_uz TEXT,
            translation_ru TEXT,
            definition TEXT,
            example TEXT,
            source TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subject, level, language, word_norm)
        )
        '''
    )

    cur.execute('''
    CREATE TABLE IF NOT EXISTS student_preferences (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        preferred_translation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    cur.execute('''
    CREATE TABLE IF NOT EXISTS vocab_word_mastery (
        user_id BIGINT NOT NULL,
        word_id BIGINT NOT NULL,
        question_type TEXT NOT NULL,
        consecutive_correct INTEGER NOT NULL DEFAULT 0,
        cooldown_until TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (user_id, word_id, question_type),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(word_id) REFERENCES words(id)
    )
    ''')

    cur.execute(
        '''
        CREATE TABLE IF NOT EXISTS user_dpoints (
            user_id BIGINT PRIMARY KEY,
            dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        '''
    )

    cur.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            author TEXT,
            category TEXT,
            level TEXT,
            thumbnail_url TEXT,
            video_url TEXT,
            duration INTEGER DEFAULT 0,
            is_published INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS video_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            video_id BIGINT NOT NULL,
            watched_seconds INTEGER DEFAULT 0,
            last_position_seconds INTEGER DEFAULT 0,
            max_watched_seconds INTEGER DEFAULT 0,
            duration_seconds INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, video_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS video_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            video_id BIGINT NOT NULL,
            watched_seconds INTEGER DEFAULT 0,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, video_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            author TEXT,
            category TEXT,
            level TEXT,
            cover_url TEXT,
            pdf_url TEXT,
            price DOUBLE PRECISION DEFAULT 0,
            deadline_days INTEGER DEFAULT 0,
            is_published INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS book_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id BIGINT NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL,
            explanation TEXT,
            question_order INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS student_book_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id BIGINT NOT NULL,
            book_id BIGINT NOT NULL,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deadline_at TIMESTAMP,
            status TEXT DEFAULT 'active',
            UNIQUE(user_id, book_id)
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS teacher_homework_settings (
            teacher_id BIGINT PRIMARY KEY,
            ai_auto_grade INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("Legacy SQLite startup path is disabled")
    dedupe_tests()
    apply_migrations()
    ensure_monthly_payments_table()
    ensure_overdue_penalty_log_table()
    ensure_grammar_attempts_table()
    ensure_temporary_group_assignments_schema()
    ensure_admin_student_shares_schema()
    ensure_daily_tests_schema()
    ensure_student_ai_chat_schema()
    ensure_vocab_word_mastery_schema()
    ensure_vocab_seed_pool_schema()
    ensure_dpoints_schema()
    ensure_subject_dcoin_schema()
    ensure_dcoin_schema_migrations()
    ensure_duel_matchmaking_schema()
    ensure_arena_extras_schema()
    ensure_support_lessons_schema()
    ensure_lesson_otmen_requests_schema()
    ensure_diamondvoy_history_table()
    ensure_diamondvoy_chat_schema()
    ensure_universal_chat_schema()
    ensure_media_assets_schema()
    ensure_gifts_schema()
    ensure_homework_schema()


def set_pending_approval(user_id, pending=True):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET pending_approval=? WHERE id=?", (1 if pending else 0, user_id))
    conn.commit()
    conn.close()


def set_user_login_type(user_id: int, login_type: int) -> None:
    """
    Update user's login type.
    Used to convert temporary "new student" (placement-test) accounts into regular students.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET login_type=? WHERE id=?", (int(login_type), user_id))
    conn.commit()
    conn.close()


# =========================
# Support lessons (bookings)
# =========================

_SUPPORT_LESSONS_SCHEMA_READY = False

def is_lesson_holiday(date_iso: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM lesson_holidays WHERE date=? LIMIT 1", (date_iso,))
        return bool(cur.fetchone())
    except Exception:
        return False
    finally:
        conn.close()


def lesson_is_slot_free(start_ts: str) -> bool:
    """
    Slot is free if there is no booking in pending/approved state with same start_ts.
    """
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM lesson_bookings
            WHERE start_ts=? AND status IN ('pending','approved')
            LIMIT 1
            """,
            (start_ts,),
        )
        return not bool(cur.fetchone())
    except Exception:
        return True
    finally:
        conn.close()


def lesson_is_slot_free_for_subject(subject: str, date_iso: str, time_hhmm: str) -> bool:
    """
    Slot is free if the number of available teachers for this subject/weekday/time
    is strictly greater than the number of active bookings for this subject/date/time.

    Capacity logic:
    - Count teachers who have EXPLICITLY enabled this slot (active=1 in time_slots)
    - Count teachers who have NO explicit record for this slot (implicitly available = use default times)
    - Subtract teachers who have EXPLICITLY disabled this slot (active=0)
    - If final capacity <= 0, slot is blocked
    """
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        from datetime import datetime
        d = datetime.fromisoformat(date_iso)
        weekday = d.weekday()

        def _get_count(cursor) -> int:
            row = cursor.fetchone()
            if not row:
                return 0
            if isinstance(row, dict):
                return int(next(iter(row.values())) or 0)
            return int(row[0] or 0)

        # Count active bookings for this slot
        cur.execute(
            """
            SELECT COUNT(*) FROM lesson_bookings
            WHERE support_subject=? AND date=? AND time=? AND status IN ('pending','approved')
            """,
            (subject, date_iso, time_hhmm),
        )
        used = _get_count(cur)

        # Count teachers with explicit active=1 for this slot
        cur.execute(
            """
            SELECT COUNT(*) FROM support_teacher_time_slots
            WHERE subject=? AND weekday=? AND time=? AND active=1
            """,
            (subject, weekday, time_hhmm),
        )
        explicit_active = _get_count(cur)

        # Count teachers with explicit active=0 (they opted out of this slot)
        cur.execute(
            """
            SELECT COUNT(DISTINCT support_teacher_id) FROM support_teacher_time_slots
            WHERE subject=? AND weekday=? AND time=? AND active=0
            """,
            (subject, weekday, time_hhmm),
        )
        explicit_inactive = _get_count(cur)

        # Count ALL active support teachers for this subject
        cur.execute(
            """
            SELECT COUNT(DISTINCT u.id) FROM users u
            WHERE u.login_type=5
              AND COALESCE(u.access_enabled, 1)=1
              AND COALESCE(u.blocked, 0)=0
              AND COALESCE(u.active, 1)=1
              AND (
                LOWER(u.subject)=LOWER(?)
                OR LOWER(u.subject) LIKE ?
              )
            """,
            (subject, f"%{subject.lower()}%"),
        )
        total_teachers = _get_count(cur)

        # Teachers without explicit record = implicitly available (using default times)
        cur.execute(
            """
            SELECT COUNT(DISTINCT support_teacher_id) FROM support_teacher_time_slots
            WHERE subject=? AND weekday=? AND time=?
            """,
            (subject, weekday, time_hhmm),
        )
        teachers_with_explicit_record = _get_count(cur)

        implicit_teachers = max(0, total_teachers - teachers_with_explicit_record)

        # Total capacity = explicitly active + implicitly available
        capacity = explicit_active + implicit_teachers

        # Fallback: if no teachers found at all via user query, use time_slots count
        if capacity <= 0:
            capacity = max(1, explicit_active)

        # If all teachers explicitly opted out and none are implicitly available
        if explicit_inactive > 0 and explicit_active == 0 and implicit_teachers == 0:
            return False

        return used < capacity
    except Exception:
        return False
    finally:
        conn.close()


def generate_lesson_booking_id() -> str:
    """Unique alphanumeric booking id (uppercase letters + digits)."""
    import secrets
    import string

    alphabet = string.ascii_uppercase + string.digits
    ensure_support_lessons_schema()
    for _ in range(40):
        bid = "".join(secrets.choice(alphabet) for _ in range(9))
        if get_lesson_booking(bid) is None:
            return bid
    return bid + secrets.token_hex(2).upper()


def create_lesson_booking_request(
    booking_id: str,
    student_user_id: int,
    student_telegram_id: str | None,
    branch: str,
    date_iso: str,
    time_hhmm: str,
    start_ts: str | None,
    end_ts: str | None,
    purpose: str,
    subject: str | None = None,
    support_teacher_id: int | None = None,
) -> bool:
    ensure_support_lessons_schema()
    # DB-level guard: prevent duplicate active bookings and enforce 6h cooldown
    # even if callbacks are pressed back-to-back.
    from datetime import datetime, timezone

    if not start_ts:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    if student_has_active_upcoming_booking(int(student_user_id), now_iso, subject=subject):
        return False

    unlock_iso = get_next_lesson_booking_allowed_after_utc_iso(int(student_user_id), now_iso, subject=subject)
    if unlock_iso:
        return False

    # Slot/date-level guard (best-effort; UI already checks too).
    if is_lesson_date_effectively_closed(str(branch), str(date_iso)):
        return False
    if subject:
        if not lesson_is_slot_free_for_subject(subject, date_iso, time_hhmm):
            return False
    else:
        if not lesson_is_slot_free(start_ts):
            return False

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_bookings(
                id, student_user_id, student_telegram_id, branch, date, time,
                start_ts, end_ts, purpose, support_subject, support_teacher_id, status
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?, 'approved')
            """,
            (
                booking_id,
                int(student_user_id),
                student_telegram_id,
                branch,
                date_iso,
                time_hhmm,
                start_ts,
                end_ts,
                purpose,
                (subject or "").strip() or None,
                int(support_teacher_id) if support_teacher_id else None,
            ),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception(
            "create_lesson_booking_request failed booking_id=%s student_user_id=%s branch=%s date=%s time=%s",
            booking_id,
            student_user_id,
            branch,
            date_iso,
            time_hhmm,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def list_lesson_bookings_for_student(student_user_id: int, active_only: bool = True) -> list[dict]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if active_only:
            from datetime import datetime, timezone

            now_iso = datetime.now(timezone.utc).isoformat()
            cur.execute(
                """
                SELECT * FROM lesson_bookings
                WHERE student_user_id=? AND status IN ('pending','approved')
                  AND (end_ts IS NULL OR end_ts > ?)
                ORDER BY date ASC, time ASC
                """,
                (int(student_user_id), now_iso),
            )
        else:
            cur.execute(
                """
                SELECT * FROM lesson_bookings
                WHERE student_user_id=?
                ORDER BY created_at DESC
                """,
                (int(student_user_id),),
            )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_pending_lesson_bookings(page: int = 1, per_page: int = 10) -> tuple[list[dict], int]:
    ensure_support_lessons_schema()
    page = max(1, int(page or 1))
    per_page = max(1, min(50, int(per_page or 10)))
    offset = (page - 1) * per_page
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM lesson_bookings WHERE status='pending'")
        total = int((cur.fetchone() or {}).get("cnt") or 0)
        total_pages = max(1, (total + per_page - 1) // per_page)
        cur.execute(
            """
            SELECT * FROM lesson_bookings
            WHERE status='pending'
            ORDER BY created_at ASC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows], total_pages
    except Exception:
        return [], 1
    finally:
        conn.close()


def set_lesson_booking_status(booking_id: str, status: str, admin_id: int | None = None, admin_note: str | None = None) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT date, branch FROM lesson_bookings WHERE id=? LIMIT 1", (str(booking_id),))
        row = cur.fetchone()
        if not row:
            return False
        row_dict = dict(row)
        normalized_status = str(status or "").strip().lower()
        if normalized_status in {"pending", "approved"} and is_lesson_date_effectively_closed(
            str(row_dict.get("branch") or ""),
            str(row_dict.get("date") or ""),
        ):
            return False
        cur.execute(
            """
            UPDATE lesson_bookings
            SET status=?, handled_by_admin_id=?, admin_note=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (status, admin_id, admin_note, booking_id),
        )
        conn.commit()
        ok = cur.rowcount > 0
        if ok and str(status).lower() in ("canceled", "cancelled", "rejected"):
            delete_lesson_reminders_unsent_for_booking(str(booking_id))
        return ok
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def reschedule_lesson_booking(booking_id: str, date_iso: str, time_hhmm: str, start_ts: str | None, admin_id: int | None = None) -> bool:
    from support_booking_time import normalize_time_hhmm, support_make_end_ts, support_make_start_ts

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    if not tm:
        return False
    st = start_ts or support_make_start_ts(date_iso, tm)
    if not st:
        return False
    et = support_make_end_ts(st)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT branch FROM lesson_bookings WHERE id=? LIMIT 1", (str(booking_id),))
        row = cur.fetchone()
        if not row:
            return False
        branch = str((dict(row) or {}).get("branch") or "")
        if is_lesson_date_effectively_closed(branch, str(date_iso)):
            return False
        cur.execute(
            """
            UPDATE lesson_bookings
            SET date=?, time=?, start_ts=?, end_ts=?, status='approved', handled_by_admin_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (date_iso, tm, st, et, admin_id, booking_id),
        )
        conn.commit()
        ok = cur.rowcount > 0
        if ok:
            refresh_lesson_reminders_for_booking(str(booking_id))
        return ok
    except Exception:
        logger.exception(
            "reschedule_lesson_booking failed booking_id=%s date=%s time=%s admin_id=%s",
            booking_id,
            date_iso,
            tm,
            admin_id,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_lesson_booking(booking_id: str) -> dict | None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM lesson_bookings WHERE id=? LIMIT 1", (str(booking_id),))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def is_lesson_date_effectively_closed(branch: str, date_iso: str) -> bool:
    day = str(date_iso or "").strip()
    if not day:
        return False
    if is_lesson_otmen_date_cancelled(day):
        return True
    if is_lesson_holiday(day):
        return True
    branch_key = str(branch or "").strip()
    if branch_key and is_branch_date_closed_for_booking(branch_key, day):
        return True
    return False


def list_lesson_bookings(status: str | None = None, page: int = 1, per_page: int = 10) -> tuple[list[dict], int]:
    ensure_support_lessons_schema()
    page = max(1, int(page or 1))
    per_page = max(1, min(50, int(per_page or 10)))
    offset = (page - 1) * per_page
    conn = get_conn()
    cur = conn.cursor()
    try:
        if status:
            cur.execute("SELECT COUNT(*) as cnt FROM lesson_bookings WHERE status=?", (status,))
            total = int((cur.fetchone() or {}).get("cnt") or 0)
            total_pages = max(1, (total + per_page - 1) // per_page)
            cur.execute(
                """
                SELECT * FROM lesson_bookings
                WHERE status=?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (status, per_page, offset),
            )
        else:
            cur.execute("SELECT COUNT(*) as cnt FROM lesson_bookings")
            total = int((cur.fetchone() or {}).get("cnt") or 0)
            total_pages = max(1, (total + per_page - 1) // per_page)
            cur.execute(
                """
                SELECT * FROM lesson_bookings
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (per_page, offset),
            )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows], total_pages
    except Exception:
        return [], 1
    finally:
        conn.close()


def list_lesson_holidays() -> list[str]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT date FROM lesson_holidays ORDER BY date ASC")
        rows = cur.fetchall() or []
        return [str(r["date"]) if isinstance(r, dict) else str(r[0]) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def add_lesson_holiday(date_iso: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT OR IGNORE INTO lesson_holidays(date) VALUES (?)", (date_iso,))
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def remove_lesson_holiday(date_iso: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM lesson_holidays WHERE date=?", (date_iso,))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_pending_lesson_otmen_request_by_date(date_str: str) -> dict | None:
    ensure_lesson_otmen_requests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT *
            FROM lesson_otmen_requests
            WHERE date_str=? AND status='pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (date_str,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def get_latest_lesson_otmen_request_by_date(date_str: str, cancel_mode: str | None = None) -> dict | None:
    ensure_lesson_otmen_requests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if cancel_mode:
            cur.execute(
                """
                SELECT *
                FROM lesson_otmen_requests
                WHERE date_str=? AND cancel_mode=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(date_str), str(cancel_mode)),
            )
        else:
            cur.execute(
                """
                SELECT *
                FROM lesson_otmen_requests
                WHERE date_str=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (str(date_str),),
            )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def create_lesson_otmen_request(
    request_id: str,
    date_str: str,
    reason: str | None,
    expires_at_iso: str,
    cancel_mode: str = "manual",
) -> bool:
    ensure_lesson_otmen_requests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_otmen_requests(id, date_str, reason, status, expires_at, cancel_mode)
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (str(request_id), str(date_str), reason, expires_at_iso, str(cancel_mode or "manual")),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_lesson_otmen_request(request_id: str) -> dict | None:
    ensure_lesson_otmen_requests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM lesson_otmen_requests WHERE id=? LIMIT 1", (str(request_id),))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def list_cancelled_lesson_otmen_requests(limit: int = 20) -> list[dict]:
    ensure_lesson_otmen_requests_schema()
    tz = pytz.timezone("Asia/Tashkent")
    today_iso = datetime.now(tz).date().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT *
            FROM lesson_otmen_requests
            WHERE status='cancelled'
              AND date_str >= ?
            ORDER BY date_str DESC, cancelled_at DESC
            LIMIT ?
            """,
            (today_iso, int(limit)),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def mark_lesson_otmen_request_status(
    request_id: str,
    status: str,
    admin_id: int | None = None,
) -> bool:
    ensure_lesson_otmen_requests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE lesson_otmen_requests
            SET status=?,
                cancelled_by_admin_id=?,
                cancelled_at=CASE WHEN ?='cancelled' THEN CURRENT_TIMESTAMP ELSE cancelled_at END
            WHERE id=?
            """,
            (status, admin_id, status, str(request_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def list_lesson_bookings_by_date(date_str: str, statuses: tuple[str, ...] = ("pending", "approved")) -> list[dict]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["?"] * len(statuses))
        cur.execute(
            f"""
            SELECT *
            FROM lesson_bookings
            WHERE date=? AND status IN ({placeholders})
            ORDER BY time ASC, created_at ASC
            """,
            (date_str, *statuses),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def list_lesson_extra_slots_for_date(date_iso: str, branch: str | None = None) -> list[str]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if branch:
            cur.execute(
                """
                SELECT time FROM lesson_extra_slots
                WHERE date=? AND (branch IS NULL OR branch=?)
                ORDER BY time ASC
                """,
                (date_iso, branch),
            )
        else:
            cur.execute("SELECT time FROM lesson_extra_slots WHERE date=? ORDER BY time ASC", (date_iso,))
        rows = cur.fetchall() or []
        out: list[str] = []
        for r in rows:
            if isinstance(r, dict):
                out.append(str(r.get("time")))
            else:
                out.append(str(r[0]))
        return out
    except Exception:
        return []
    finally:
        conn.close()


def add_lesson_extra_slot(slot_id: str, date_iso: str, time_hhmm: str, branch: str | None = None) -> bool:
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    if not tm:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO lesson_extra_slots(id, date, time, branch) VALUES (?,?,?,?)",
            (slot_id, date_iso, tm, branch),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("add_lesson_extra_slot failed slot_id=%s date=%s time=%s branch=%s", slot_id, date_iso, tm, branch)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def remove_lesson_extra_slot(date_iso: str, time_hhmm: str, branch: str | None = None) -> bool:
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    if not tm:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        if branch:
            cur.execute(
                "DELETE FROM lesson_extra_slots WHERE date=? AND time=? AND (branch IS NULL OR branch=?)",
                (date_iso, tm, branch),
            )
        else:
            cur.execute("DELETE FROM lesson_extra_slots WHERE date=? AND time=?", (date_iso, tm))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_lesson_user(telegram_id: str) -> dict | None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM lesson_users WHERE telegram_id=? LIMIT 1", (str(telegram_id),))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None
    finally:
        conn.close()


def upsert_lesson_user(telegram_id: str, lang: str | None = None, first_name: str | None = None, username: str | None = None, full_name: str | None = None) -> None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_users(telegram_id, lang, first_name, full_name, username)
            VALUES (?,?,?,?,?)
            ON CONFLICT(telegram_id) DO UPDATE SET
              lang=COALESCE(excluded.lang, lesson_users.lang),
              first_name=COALESCE(excluded.first_name, lesson_users.first_name),
              full_name=COALESCE(excluded.full_name, lesson_users.full_name),
              username=COALESCE(excluded.username, lesson_users.username)
            """,
            (str(telegram_id), lang, first_name, full_name, username),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def set_lesson_user_lang(telegram_id: str, lang: str) -> None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE lesson_users SET lang=? WHERE telegram_id=?", (lang, str(telegram_id)))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def get_lesson_user_reminder_pref(telegram_id: str) -> str | None:
    u = get_lesson_user(str(telegram_id)) or {}
    pref = (u.get("reminder_pref") or "").strip()
    return pref or None


def set_lesson_user_reminder_pref(telegram_id: str, pref: str) -> None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE lesson_users SET reminder_pref=? WHERE telegram_id=?", (pref, str(telegram_id)))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def create_lesson_reminder(reminder_id: str, booking_id: str, telegram_id: str, reminder_target: str, reminder_type: str, scheduled_time: str, admin_id: int | None = None) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_reminders(id, booking_id, telegram_id, admin_id, reminder_target, reminder_type, scheduled_time, sent)
            VALUES (?,?,?,?,?,?,?,0)
            """,
            (reminder_id, str(booking_id), str(telegram_id), admin_id, reminder_target, reminder_type, scheduled_time),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def list_due_unsent_lesson_reminders(now_iso_utc: str, limit: int = 200) -> list[dict]:
    """
    Fetch due reminders. For SQLite TEXT timestamps we rely on ISO ordering.
    """
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT * FROM lesson_reminders
            WHERE sent=0 AND scheduled_time IS NOT NULL AND scheduled_time <= ?
            ORDER BY scheduled_time ASC
            LIMIT ?
            """,
            (now_iso_utc, int(limit)),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def mark_lesson_reminder_sent(reminder_id: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE lesson_reminders SET sent=1 WHERE id=?", (str(reminder_id),))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def claim_lesson_reminder_for_delivery(reminder_id: str) -> bool:
    """
    Atomically consume a due lesson reminder before Telegram delivery.
    This prevents duplicate sends when multiple bot processes/loops pick the same row.
    """
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE lesson_reminders SET sent=1 WHERE id=? AND COALESCE(sent, 0)=0",
            (str(reminder_id),),
        )
        claimed = (getattr(cur, "rowcount", 0) or 0) > 0
        conn.commit()
        return claimed
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def delete_lesson_reminders_unsent_for_booking(booking_id: str) -> None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM lesson_reminders WHERE booking_id=? AND sent=0", (str(booking_id),))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def list_teacher_telegram_ids_for_student(student_user_id: int) -> list[str]:
    """Distinct teacher telegram_ids linked to student via active group membership."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT t.telegram_id
            FROM user_groups ug
            JOIN groups g ON ug.group_id = g.id
            JOIN users t ON g.teacher_id = t.id
            WHERE ug.user_id = ?
              AND t.login_type = 3
              AND t.telegram_id IS NOT NULL
              AND CAST(t.telegram_id AS TEXT) != ''
            """,
            (int(student_user_id),),
        )
        out: list[str] = []
        for row in cur.fetchall() or []:
            tid = (dict(row) if isinstance(row, dict) else {"telegram_id": row[0]}).get("telegram_id")
            if tid is not None:
                out.append(str(tid))
        return sorted(set(out))
    except Exception:
        return []
    finally:
        conn.close()


def refresh_lesson_reminders_for_booking(booking_id: str) -> None:
    """Rebuild unsent reminders: student 1h + 10m, admin 10m + start + end flows."""
    from datetime import datetime, timedelta, timezone

    import uuid

    b = get_lesson_booking(str(booking_id))
    if not b:
        return
    if str(b.get("status") or "") not in ("pending", "approved"):
        return
    st_raw = b.get("start_ts")
    stu_tg = b.get("student_telegram_id")
    if not st_raw or not stu_tg:
        return
    dt = _parse_iso_utc(str(st_raw))
    if not dt:
        return
    tz_tashkent = pytz.timezone("Asia/Tashkent")
    start_tashkent = dt.astimezone(tz_tashkent)
    now_tashkent = datetime.now(tz_tashkent)
    now = now_tashkent.astimezone(timezone.utc)
    delete_lesson_reminders_unsent_for_booking(str(booking_id))

    rem_1h_tashkent = start_tashkent - timedelta(hours=1)
    rem_1h = rem_1h_tashkent.astimezone(timezone.utc)
    if rem_1h > now:
        create_lesson_reminder(
            uuid.uuid4().hex[:16],
            str(booking_id),
            str(stu_tg),
            "student",
            "1h_before",
            rem_1h.isoformat(),
            None,
        )

    rem_10m_tashkent = start_tashkent - timedelta(minutes=10)
    rem_10m = rem_10m_tashkent.astimezone(timezone.utc)
    if rem_10m > now:
        create_lesson_reminder(
            uuid.uuid4().hex[:16],
            str(booking_id),
            str(stu_tg),
            "student",
            "10m_before",
            rem_10m.isoformat(),
            None,
        )
        for aid in list(dict.fromkeys(ALL_ADMIN_IDS or [])):
            try:
                aid_int = int(aid)
                if aid_int <= 0:
                    continue
                atg = str(aid_int)
            except Exception:
                continue
            create_lesson_reminder(
                uuid.uuid4().hex[:16],
                str(booking_id),
                atg,
                "admin",
                "10m_before",
                rem_10m.isoformat(),
                aid_int,
            )

    # Admin: lesson start attendance prompt (at lesson start).
    if dt > now:
        for aid in list(dict.fromkeys(ALL_ADMIN_IDS or [])):
            try:
                aid_int = int(aid)
                if aid_int <= 0:
                    continue
                atg = str(aid_int)
            except Exception:
                continue
            create_lesson_reminder(
                uuid.uuid4().hex[:16],
                str(booking_id),
                atg,
                "admin",
                "lesson_start_attendance",
                dt.isoformat(),
                aid_int,
            )

    # Admin: lesson end bonus prompt (at lesson end).
    end_raw = b.get("end_ts")
    end_dt = _parse_iso_utc(str(end_raw)) if end_raw else None
    if end_dt and end_dt > now:
        for aid in list(dict.fromkeys(ALL_ADMIN_IDS or [])):
            try:
                aid_int = int(aid)
                if aid_int <= 0:
                    continue
                atg = str(aid_int)
            except Exception:
                continue
            create_lesson_reminder(
                uuid.uuid4().hex[:16],
                str(booking_id),
                atg,
                "admin",
                "lesson_end_bonus",
                end_dt.isoformat(),
                aid_int,
            )


def set_support_booking_attendance(booking_id: str, status: str) -> bool:
    """Set support attendance status for booking (present/excused/late/absent)."""
    st = (status or "").strip().lower()
    if st not in ("present", "excused", "late", "absent"):
        return False
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE lesson_bookings
            SET support_attendance_status=?,
                support_attendance_marked_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (st, str(booking_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def apply_support_attendance_penalty_if_needed(booking_id: str, amount: float) -> tuple[bool, int | None]:
    """
    Apply attendance penalty once per booking.
    Returns (applied_now, student_user_id).
    """
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT student_user_id, support_attendance_penalty_applied FROM lesson_bookings WHERE id=? LIMIT 1",
            (str(booking_id),),
        )
        row = cur.fetchone()
        if not row:
            return False, None
        uid = int((row or {}).get("student_user_id") or 0)
        already = int((row or {}).get("support_attendance_penalty_applied") or 0)
        if already == 1:
            return False, uid
        cur.execute(
            """
            UPDATE lesson_bookings
            SET support_attendance_penalty_applied=1, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (str(booking_id),),
        )
        conn.commit()
        return True, uid
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, None
    finally:
        conn.close()


def support_booking_bonus_allowed(booking_id: str) -> bool:
    ensure_support_lessons_schema()
    b = get_lesson_booking(str(booking_id))
    if not b:
        return False
    st = str(b.get("support_attendance_status") or "").lower()
    bonus_awarded = int(b.get("support_bonus_awarded") or 0)
    return st in ("present", "late") and bonus_awarded == 0


def apply_support_bonus_if_needed(booking_id: str, amount: float) -> tuple[bool, int | None]:
    """
    Apply support lesson bonus once per booking.
    Returns (applied_now, student_user_id).
    """
    amt = float(amount or 0)
    if amt <= 0:
        return False, None
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT student_user_id, support_attendance_status, support_bonus_awarded
            FROM lesson_bookings
            WHERE id=?
            LIMIT 1
            """,
            (str(booking_id),),
        )
        row = cur.fetchone()
        if not row:
            return False, None
        uid = int((row or {}).get("student_user_id") or 0)
        st = str((row or {}).get("support_attendance_status") or "").lower()
        awarded = int((row or {}).get("support_bonus_awarded") or 0)
        if st not in ("present", "late") or awarded == 1:
            return False, uid
        cur.execute(
            """
            UPDATE lesson_bookings
            SET support_bonus_awarded=1,
                support_bonus_amount=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (amt, str(booking_id)),
        )
        conn.commit()
        return True, uid
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False, None
    finally:
        conn.close()


def refresh_student_1h_reminder_for_booking(booking_id: str) -> None:
    """Backward-compatible alias."""
    refresh_lesson_reminders_for_booking(str(booking_id))


def add_lesson_waitlist(wait_id: str, date_iso: str, time_hhmm: str, branch: str, telegram_id: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_waitlist(id, date, time, branch, telegram_id)
            VALUES (?,?,?,?,?)
            """,
            (str(wait_id), date_iso, time_hhmm, branch, str(telegram_id)),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def pop_lesson_waitlist_for_slot(date_iso: str, time_hhmm: str, branch: str) -> dict | None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT * FROM lesson_waitlist
            WHERE date=? AND time=? AND branch=?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (date_iso, time_hhmm, branch),
        )
        row = cur.fetchone()
        if not row:
            return None
        entry = dict(row)
        cur.execute("DELETE FROM lesson_waitlist WHERE id=?", (str(entry.get("id")),))
        conn.commit()
        return entry
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def count_lesson_users() -> int:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM lesson_users")
        return int((cur.fetchone() or {}).get("cnt") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def count_lesson_today_bookings(date_iso: str) -> int:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) as cnt
            FROM lesson_bookings
            WHERE date=? AND status IN ('pending','approved')
            """,
            (date_iso,),
        )
        return int((cur.fetchone() or {}).get("cnt") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def count_lesson_completed_bookings(now_iso_utc: str) -> int:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) as cnt
            FROM lesson_bookings
            WHERE start_ts IS NOT NULL AND start_ts < ? AND status IN ('approved','done')
            """,
            (now_iso_utc,),
        )
        return int((cur.fetchone() or {}).get("cnt") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


_DEFAULT_BRANCH_WEEKDAYS = {"branch_1": [1, 3, 5], "branch_2": [0, 2, 4]}


def get_lesson_branch_weekdays(branch: str) -> list[int]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT weekdays FROM lesson_branch_weekdays WHERE branch=? LIMIT 1", (str(branch),))
        row = cur.fetchone()
        if not row:
            return list(_DEFAULT_BRANCH_WEEKDAYS.get(str(branch), [1, 3, 5]))
        raw = (dict(row) if isinstance(row, dict) else {"weekdays": row[0]}).get("weekdays") or ""
        parts = [int(x.strip()) for x in str(raw).split(",") if x.strip().isdigit()]
        return sorted(set(parts)) if parts else list(_DEFAULT_BRANCH_WEEKDAYS.get(str(branch), [1, 3, 5]))
    except Exception:
        return list(_DEFAULT_BRANCH_WEEKDAYS.get(str(branch), [1, 3, 5]))
    finally:
        conn.close()


def set_lesson_branch_weekdays(branch: str, weekdays: list[int]) -> bool:
    ensure_support_lessons_schema()
    wcsv = ",".join(str(int(d)) for d in sorted(set(weekdays)))
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_branch_weekdays(branch, weekdays)
            VALUES (?,?)
            ON CONFLICT(branch) DO UPDATE SET weekdays=excluded.weekdays
            """,
            (str(branch), wcsv),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("set_lesson_branch_weekdays failed branch=%s weekdays=%s", branch, wcsv)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def is_branch_date_closed_for_booking(branch: str, date_iso: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM lesson_branch_date_closed
            WHERE date=? AND (branch=? OR branch='all')
            LIMIT 1
            """,
            (date_iso, str(branch)),
        )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def set_branch_date_closed(branch: str, date_iso: str, reason: str | None) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_branch_date_closed(branch, date, reason)
            VALUES (?,?,?)
            ON CONFLICT(branch, date) DO UPDATE SET reason=excluded.reason
            """,
            (str(branch), date_iso, reason or ""),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception("set_branch_date_closed failed branch=%s date=%s", branch, date_iso)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def open_branch_date_for_booking(branch: str, date_iso: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM lesson_branch_date_closed WHERE branch=? AND date=?", (str(branch), date_iso))
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        logger.exception("open_branch_date_for_booking failed branch=%s date=%s", branch, date_iso)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def list_branch_dates_closed(branch: str | None = None) -> list[dict]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if branch:
            cur.execute(
                "SELECT * FROM lesson_branch_date_closed WHERE branch=? OR branch='all' ORDER BY date ASC",
                (str(branch),),
            )
        else:
            cur.execute("SELECT * FROM lesson_branch_date_closed ORDER BY branch ASC, date ASC")
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_branch_date_closed_reason(branch: str, date_iso: str) -> str | None:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT reason FROM lesson_branch_date_closed
            WHERE date=? AND (branch=? OR branch='all')
            ORDER BY CASE WHEN branch='all' THEN 1 ELSE 0 END ASC
            LIMIT 1
            """,
            (date_iso, str(branch)),
        )
        row = cur.fetchone()
        if not row:
            return None
        rs = (dict(row) if isinstance(row, dict) else {"reason": row[0]}).get("reason")
        return str(rs or "").strip() or None
    except Exception:
        return None
    finally:
        conn.close()


def is_slot_blocked(branch: str, date_iso: str, time_hhmm: str) -> bool:
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    if not tm:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM lesson_blocked_slots
            WHERE branch=? AND date=? AND time=?
            LIMIT 1
            """,
            (str(branch), date_iso, tm),
        )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def add_blocked_slot(
    slot_id: str, branch: str, date_iso: str, time_hhmm: str, reason: str | None, created_by: int | None
) -> bool:
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    if not tm:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM lesson_blocked_slots WHERE branch=? AND date=? AND time=?",
            (str(branch), date_iso, tm),
        )
        cur.execute(
            """
            INSERT INTO lesson_blocked_slots(id, branch, date, time, reason, created_by)
            VALUES (?,?,?,?,?,?)
            """,
            (str(slot_id), str(branch), date_iso, tm, reason or "", created_by),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception(
            "add_blocked_slot failed slot_id=%s branch=%s date=%s time=%s created_by=%s",
            slot_id,
            branch,
            date_iso,
            tm,
            created_by,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def remove_blocked_slot(branch: str, date_iso: str, time_hhmm: str) -> bool:
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    if not tm:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM lesson_blocked_slots WHERE branch=? AND date=? AND time=?",
            (str(branch), date_iso, tm),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        logger.exception("remove_blocked_slot failed branch=%s date=%s time=%s", branch, date_iso, tm)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def list_blocked_slots_for_date(branch: str, date_iso: str) -> list[dict]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM lesson_blocked_slots WHERE branch=? AND date=? ORDER BY time ASC",
            (str(branch), date_iso),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def add_recurring_slot_rule(
    rule_id: str,
    branch: str,
    weekday: int,
    time_hhmm: str,
    mode: str,
    reason: str | None,
    created_by: int | None,
    active: int = 1,
) -> bool:
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    md = (mode or "").strip().lower()
    if not tm or md not in ("open", "close"):
        return False
    if weekday < 0 or weekday > 6:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO lesson_recurring_slot_rules(id, branch, weekday, time, mode, reason, created_by, active)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(branch, weekday, time, mode)
            DO UPDATE SET reason=excluded.reason, created_by=excluded.created_by, active=excluded.active
            """,
            (str(rule_id), str(branch), int(weekday), tm, md, reason or "", created_by, int(active)),
        )
        conn.commit()
        return True
    except Exception:
        logger.exception(
            "add_recurring_slot_rule failed branch=%s weekday=%s time=%s mode=%s active=%s",
            branch,
            weekday,
            tm,
            md,
            active,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def remove_recurring_slot_rule(branch: str, weekday: int, time_hhmm: str, mode: str) -> bool:
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    md = (mode or "").strip().lower()
    if not tm or md not in ("open", "close"):
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM lesson_recurring_slot_rules WHERE branch=? AND weekday=? AND time=? AND mode=?",
            (str(branch), int(weekday), tm, md),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        logger.exception(
            "remove_recurring_slot_rule failed branch=%s weekday=%s time=%s mode=%s",
            branch,
            weekday,
            tm,
            md,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def list_recurring_slot_rules(branch: str | None = None, weekday: int | None = None, mode: str | None = None) -> list[dict]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        where = ["active=1"]
        vals: list = []
        if branch:
            where.append("branch=?")
            vals.append(str(branch))
        if weekday is not None:
            where.append("weekday=?")
            vals.append(int(weekday))
        if mode:
            where.append("mode=?")
            vals.append(str(mode).strip().lower())
        q = "SELECT * FROM lesson_recurring_slot_rules"
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY branch ASC, weekday ASC, time ASC"
        cur.execute(q, tuple(vals))
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()


def list_recurring_open_times_for_date(branch: str, date_iso: str) -> list[str]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        from datetime import datetime

        wd = datetime.strptime(date_iso, "%Y-%m-%d").date().weekday()
        cur.execute(
            """
            SELECT time FROM lesson_recurring_slot_rules
            WHERE active=1 AND branch=? AND weekday=? AND mode='open'
            ORDER BY time ASC
            """,
            (str(branch), int(wd)),
        )
        rows = cur.fetchall() or []
        out: list[str] = []
        for r in rows:
            out.append(str((dict(r) if isinstance(r, dict) else {"time": r[0]}).get("time") or ""))
        return [x for x in out if x]
    except Exception:
        return []
    finally:
        conn.close()


def get_slot_block_reason(branch: str, date_iso: str, time_hhmm: str) -> str | None:
    from datetime import datetime
    from support_booking_time import normalize_time_hhmm

    ensure_support_lessons_schema()
    tm = normalize_time_hhmm(time_hhmm)
    if not tm:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Highest priority: date closed
        cur.execute(
            """
            SELECT reason FROM lesson_branch_date_closed
            WHERE date=? AND (branch=? OR branch='all')
            ORDER BY CASE WHEN branch='all' THEN 1 ELSE 0 END ASC
            LIMIT 1
            """,
            (date_iso, str(branch)),
        )
        r0 = cur.fetchone()
        if r0:
            rs = (dict(r0) if isinstance(r0, dict) else {"reason": r0[0]}).get("reason")
            return str(rs or "").strip() or None

        wd = datetime.strptime(date_iso, "%Y-%m-%d").date().weekday()
        # Recurring close
        cur.execute(
            """
            SELECT reason FROM lesson_recurring_slot_rules
            WHERE active=1 AND branch=? AND weekday=? AND time=? AND mode='close'
            LIMIT 1
            """,
            (str(branch), int(wd), tm),
        )
        r1 = cur.fetchone()
        if r1:
            rs = (dict(r1) if isinstance(r1, dict) else {"reason": r1[0]}).get("reason")
            return str(rs or "").strip() or None

        # Date-specific close
        cur.execute(
            """
            SELECT reason FROM lesson_blocked_slots
            WHERE branch=? AND date=? AND time=?
            LIMIT 1
            """,
            (str(branch), date_iso, tm),
        )
        r2 = cur.fetchone()
        if r2:
            rs = (dict(r2) if isinstance(r2, dict) else {"reason": r2[0]}).get("reason")
            return str(rs or "").strip() or None
        return None
    except Exception:
        return None
    finally:
        conn.close()


def is_slot_closed_effective(branch: str, date_iso: str, time_hhmm: str) -> bool:
    return get_slot_block_reason(str(branch), str(date_iso), str(time_hhmm)) is not None


def update_lesson_booking_branch(booking_id: str, branch: str, admin_id: int | None = None) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE lesson_bookings
            SET branch=?, handled_by_admin_id=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (str(branch), admin_id, str(booking_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        logger.exception("update_lesson_booking_branch failed booking_id=%s branch=%s admin_id=%s", booking_id, branch, admin_id)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def is_lesson_otmen_date_cancelled(date_str: str) -> bool:
    """True when admin otmen request for date is already marked cancelled."""
    ensure_lesson_otmen_requests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
            FROM lesson_otmen_requests
            WHERE date_str=? AND status='cancelled'
            LIMIT 1
            """,
            (str(date_str),),
        )
        return cur.fetchone() is not None
    except Exception:
        logger.exception("is_lesson_otmen_date_cancelled failed date=%s", date_str)
        return False
    finally:
        conn.close()


def list_lesson_upcoming_bookings(page: int = 1, per_page: int = 10, now_iso_utc: str | None = None) -> tuple[list[dict], int]:
    from datetime import datetime, timezone

    ensure_support_lessons_schema()
    if now_iso_utc is None:
        now_iso_utc = datetime.now(timezone.utc).isoformat()
    page = max(1, int(page or 1))
    per_page = max(1, min(50, int(per_page or 10)))
    offset = (page - 1) * per_page
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM lesson_bookings
            WHERE status IN ('pending','approved')
              AND (
                (end_ts IS NOT NULL AND end_ts != '' AND end_ts > ?)
                OR ((end_ts IS NULL OR end_ts = '') AND start_ts IS NOT NULL AND start_ts != '' AND start_ts > ?)
              )
            """,
            (now_iso_utc, now_iso_utc),
        )
        total = int((cur.fetchone() or {}).get("cnt") or 0)
        total_pages = max(1, (total + per_page - 1) // per_page)
        cur.execute(
            """
            SELECT * FROM lesson_bookings
            WHERE status IN ('pending','approved')
              AND (
                (end_ts IS NOT NULL AND end_ts != '' AND end_ts > ?)
                OR ((end_ts IS NULL OR end_ts = '') AND start_ts IS NOT NULL AND start_ts != '' AND start_ts > ?)
              )
            ORDER BY COALESCE(start_ts, '9999-12-31T23:59:59+00:00') ASC
            LIMIT ? OFFSET ?
            """,
            (now_iso_utc, now_iso_utc, per_page, offset),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows], total_pages
    except Exception:
        return [], 1
    finally:
        conn.close()


def count_lesson_bookings_total() -> int:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM lesson_bookings")
        return int((cur.fetchone() or {}).get("cnt") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def count_lesson_active_upcoming(now_iso_utc: str) -> int:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM lesson_bookings
            WHERE status IN ('pending','approved')
              AND (
                (end_ts IS NOT NULL AND end_ts != '' AND end_ts > ?)
                OR ((end_ts IS NULL OR end_ts = '') AND start_ts IS NOT NULL AND start_ts != '' AND start_ts > ?)
              )
            """,
            (now_iso_utc, now_iso_utc),
        )
        return int((cur.fetchone() or {}).get("cnt") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def count_lesson_past_ended(now_iso_utc: str) -> int:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM lesson_bookings
            WHERE end_ts IS NOT NULL AND end_ts != '' AND end_ts <= ?
            """,
            (now_iso_utc,),
        )
        return int((cur.fetchone() or {}).get("cnt") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def _count_bookings_created_between(t0_iso: str, t1_iso: str) -> int:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) as cnt FROM lesson_bookings
            WHERE created_at >= ? AND created_at < ?
            """,
            (t0_iso, t1_iso),
        )
        return int((cur.fetchone() or {}).get("cnt") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def support_dashboard_metrics(today_date_iso: str, now_utc_iso: str) -> dict:
    """
    today_date_iso: YYYY-MM-DD in Asia/Tashkent.
    Returns counts and simple MoM % for bookings created in calendar month windows (SQLite created_at).
    """
    from calendar import monthrange
    from datetime import date, datetime, timedelta, timezone

    ensure_support_lessons_schema()
    today = datetime.strptime(today_date_iso, "%Y-%m-%d").date()
    y, m = today.year, today.month
    start_this = date(y, m, 1)
    if m == 1:
        start_prev = date(y - 1, 12, 1)
        end_prev = date(y, 1, 1)
    else:
        start_prev = date(y, m - 1, 1)
        end_prev = start_this
    _, last_day = monthrange(y, m)
    end_this_exclusive = start_this + timedelta(days=last_day)

    def d_iso(d: date) -> str:
        return d.isoformat() + " 00:00:00"

    c_this = _count_bookings_created_between(d_iso(start_this), d_iso(end_this_exclusive))
    c_prev = _count_bookings_created_between(d_iso(start_prev), d_iso(end_prev))

    def pct_change(cur: int, prev: int) -> str | None:
        if prev <= 0:
            return None if cur == 0 else "+100%"
        p = round((cur - prev) * 100.0 / prev, 1)
        return f"{p:+.1f}%"

    today_n = count_lesson_today_bookings(today_date_iso)
    # MoM for "today" vs same metric on same day-of-month last month is noisy; compare month-to-date totals instead.
    mtd_start = d_iso(start_this)
    mtd_now = today_date_iso + " 23:59:59"
    prev_month_same_span_end = min(today.replace(year=start_prev.year, month=start_prev.month, day=min(today.day, monthrange(start_prev.year, start_prev.month)[1])), end_prev - timedelta(days=1))
    mtd_prev_start = d_iso(start_prev)
    mtd_prev_end = prev_month_same_span_end.isoformat() + " 23:59:59"
    mtd_cur = _count_bookings_created_between(mtd_start, mtd_now)
    mtd_prev = _count_bookings_created_between(mtd_prev_start, mtd_prev_end)

    return {
        "lesson_users": count_lesson_users(),
        "active_upcoming": count_lesson_active_upcoming(now_utc_iso),
        "past_ended": count_lesson_past_ended(now_utc_iso),
        "today_bookings": today_n,
        "total_bookings": count_lesson_bookings_total(),
        "bookings_created_this_month": c_this,
        "bookings_created_last_month": c_prev,
        "mom_created_month_pct": pct_change(c_this, c_prev),
        "mtd_bookings": mtd_cur,
        "mtd_prev_month_bookings": mtd_prev,
        "mom_mtd_pct": pct_change(mtd_cur, mtd_prev),
    }


def list_student_telegram_ids_with_upcoming_bookings(now_iso_utc: str) -> list[str]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT student_telegram_id FROM lesson_bookings
            WHERE status IN ('pending','approved')
              AND student_telegram_id IS NOT NULL AND student_telegram_id != ''
              AND (
                (end_ts IS NOT NULL AND end_ts != '' AND end_ts > ?)
                OR ((end_ts IS NULL OR end_ts = '') AND start_ts IS NOT NULL AND start_ts != '' AND start_ts > ?)
              )
            """,
            (now_iso_utc, now_iso_utc),
        )
        out: list[str] = []
        for r in cur.fetchall() or []:
            tg = (dict(r) if isinstance(r, dict) else {"student_telegram_id": r[0]}).get("student_telegram_id")
            if tg:
                out.append(str(tg))
        return sorted(set(out))
    except Exception:
        return []
    finally:
        conn.close()


def list_student_telegram_ids_had_bookings() -> list[str]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT student_telegram_id FROM lesson_bookings
            WHERE student_telegram_id IS NOT NULL AND student_telegram_id != ''
            """
        )
        out: list[str] = []
        for r in cur.fetchall() or []:
            tg = (dict(r) if isinstance(r, dict) else {"student_telegram_id": r[0]}).get("student_telegram_id")
            if tg:
                out.append(str(tg))
        return sorted(set(out))
    except Exception:
        return []
    finally:
        conn.close()


def list_all_student_telegram_ids() -> list[str]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT telegram_id FROM users
            WHERE login_type IN (1, 2)
              AND telegram_id IS NOT NULL AND CAST(telegram_id AS TEXT) != ''
            """
        )
        out: list[str] = []
        for r in cur.fetchall() or []:
            tg = (dict(r) if isinstance(r, dict) else {"telegram_id": r[0]}).get("telegram_id")
            if tg is not None:
                out.append(str(tg))
        return sorted(set(out))
    except Exception:
        return []
    finally:
        conn.close()


def set_daily_test_upload_permission(teacher_id: int, allowed: bool):
    """Allow/restrict a teacher from uploading daily tests."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET can_upload_daily_tests=? WHERE id=?",
        (1 if allowed else 0, teacher_id),
    )
    conn.commit()
    conn.close()


def get_daily_test_upload_permission(teacher_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT can_upload_daily_tests FROM users WHERE id=?", (teacher_id,))
    row = cur.fetchone()
    conn.close()
    return bool(row["can_upload_daily_tests"]) if row else False


def set_teacher_ai_generation_permission(teacher_id: int, allowed: bool) -> None:
    """Allow/restrict a teacher from using AI generator for vocab/daily-tests."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET can_generate_ai=? WHERE id=?",
        (1 if allowed else 0, teacher_id),
    )
    conn.commit()
    conn.close()


def get_teacher_ai_generation_permission(teacher_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT login_type, can_generate_ai FROM users WHERE id=?", (teacher_id,))
        row = cur.fetchone()
        if not row:
            return False
        return bool(row["can_generate_ai"])
    except Exception:
        return False
    finally:
        conn.close()


def set_book_upload_permission(user_id: int, allowed: bool) -> None:
    """Allow/restrict a teacher/support teacher from uploading books."""
    ensure_teacher_content_permissions_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET can_upload_books=? WHERE id=?",
        (1 if allowed else 0, int(user_id)),
    )
    conn.commit()
    conn.close()


def get_book_upload_permission(user_id: int) -> bool:
    ensure_teacher_content_permissions_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT can_upload_books FROM users WHERE id=?", (int(user_id),))
        row = cur.fetchone()
        return bool(row["can_upload_books"]) if row else False
    except Exception:
        return False
    finally:
        conn.close()


def ensure_teacher_content_permissions_schema() -> None:
    if _schema_ready("teacher_content_permissions_v1"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _ensure_table_columns(
            cur,
            "users",
            [
                ("can_upload_books", "INTEGER DEFAULT 0"),
                ("can_upload_videos", "INTEGER DEFAULT 0"),
                ("can_manage_video_tests", "INTEGER DEFAULT 0"),
                ("can_manage_book_tests", "INTEGER DEFAULT 0"),
            ],
        )
        try:
            if not _migration_applied(cur, "teacher_content_permissions_backfill_v1"):
                cur.execute(
                    """
                    UPDATE users
                    SET can_upload_videos=COALESCE(can_upload_videos, can_upload_books, 0),
                        can_manage_video_tests=COALESCE(can_manage_video_tests, can_upload_books, 0),
                        can_manage_book_tests=COALESCE(can_manage_book_tests, can_upload_books, 0)
                    WHERE COALESCE(can_upload_books, 0)=1
                    """
                )
                _mark_migration_applied(cur, conn, "teacher_content_permissions_backfill_v1")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("teacher_content_permissions_v1")
    finally:
        conn.close()


def set_video_upload_permission(user_id: int, allowed: bool) -> None:
    ensure_teacher_content_permissions_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET can_upload_videos=? WHERE id=?", (1 if allowed else 0, int(user_id)))
    conn.commit()
    conn.close()


def get_video_upload_permission(user_id: int) -> bool:
    ensure_teacher_content_permissions_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT can_upload_videos FROM users WHERE id=?", (int(user_id),))
        row = cur.fetchone()
        return bool(row["can_upload_videos"]) if row else False
    except Exception:
        return False
    finally:
        conn.close()


def set_content_test_manage_permission(user_id: int, content_type: str, allowed: bool) -> None:
    ensure_teacher_content_permissions_schema()
    normalized = str(content_type or "").strip().lower()
    if normalized not in {"video", "book"}:
        return
    col = "can_manage_video_tests" if normalized == "video" else "can_manage_book_tests"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE users SET {col}=? WHERE id=?", (1 if allowed else 0, int(user_id)))
    conn.commit()
    conn.close()


def get_content_test_manage_permission(user_id: int, content_type: str) -> bool:
    ensure_teacher_content_permissions_schema()
    normalized = str(content_type or "").strip().lower()
    if normalized not in {"video", "book"}:
        return False
    col = "can_manage_video_tests" if normalized == "video" else "can_manage_book_tests"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT {col} FROM users WHERE id=?", (int(user_id),))
        row = cur.fetchone()
        return bool(row[col]) if row else False
    except Exception:
        return False
    finally:
        conn.close()


def ensure_student_ai_chat_schema() -> None:
    """Track daily student AI chat quota usage."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS student_ai_chat_usage (
                user_id BIGINT NOT NULL,
                usage_date DATE NOT NULL,
                requests_count INTEGER NOT NULL DEFAULT 0,
                last_prompt TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, usage_date),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            '''
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_vocab_word_mastery_schema() -> bool:
    """Per-user per-word per-question-type streak/cooldown tracking for vocab quiz."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS vocab_word_mastery (
                user_id BIGINT NOT NULL,
                word_id BIGINT NOT NULL,
                question_type TEXT NOT NULL,
                consecutive_correct INTEGER NOT NULL DEFAULT 0,
                cooldown_until TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, word_id, question_type),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(word_id) REFERENCES words(id)
            )
            '''
        )
        for idx_sql in (
            "CREATE INDEX IF NOT EXISTS idx_vocab_mastery_user_qtype_cooldown ON vocab_word_mastery(user_id, question_type, cooldown_until)",
            "CREATE INDEX IF NOT EXISTS idx_vocab_mastery_user_updated_word ON vocab_word_mastery(user_id, updated_at, word_id)",
            "CREATE INDEX IF NOT EXISTS idx_vocab_mastery_user_cooldown_updated ON vocab_word_mastery(user_id, cooldown_until, updated_at)",
        ):
            try:
                cur.execute(idx_sql)
            except Exception:
                pass
        conn.commit()
        return True
    except Exception:
        logger.exception("Failed to ensure vocab_word_mastery schema")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def _normalize_vocab_question_type(question_type: str | None) -> str:
    raw = str(question_type or "").strip().lower()
    if raw in ("multiple_choice", "gap_filling", "definition"):
        return raw
    return "multiple_choice"


def _coerce_level_code(user_level: str | None) -> str:
    raw = str(user_level or "").strip().upper()
    if raw in ("A1", "A2", "B1", "B2", "C1"):
        return raw
    
    mapping = {
        "BEGINNER": "A1",
        "ELEMENTARY": "A2",
        "PRE-INTERMEDIATE": "B1",
        "INTERMEDIATE": "B2",
        "UPPER-INTERMEDIATE": "C1",
        "ADVANCED": "C1"
    }
    if raw in mapping:
        return mapping[raw]
        
    m = re.search(r"(A1|A2|B1|B2|C1)", raw)
    if m:
        return m.group(1)
    return "A1"



def get_equivalent_levels(level: str | None) -> list[str]:
    raw = str(level or "").strip().upper()
    mapping = {
        "A1": ["A1", "BEGINNER"],
        "BEGINNER": ["A1", "BEGINNER"],
        "A2": ["A2", "ELEMENTARY"],
        "ELEMENTARY": ["A2", "ELEMENTARY"],
        "B1": ["B1", "PRE-INTERMEDIATE"],
        "PRE-INTERMEDIATE": ["B1", "PRE-INTERMEDIATE"],
        "B2": ["B2", "INTERMEDIATE"],
        "INTERMEDIATE": ["B2", "INTERMEDIATE"],
        "C1": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
        "UPPER-INTERMEDIATE": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
        "C2": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
        "ADVANCED": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
    }
    return mapping.get(raw, [raw])

def get_vocab_allowed_levels_for_user(user_level: str | None) -> list[str]:
    """
    Policy:
      - BEGINNER -> ["BEGINNER", "A1"]
      - ELEMENTARY -> ["ELEMENTARY", "A2"]
      - ... fallback to backward compatible sets for A1/A2 etc.
    """
    lvl = _coerce_level_code(user_level)
    
    mapping = {
        "BEGINNER": ["BEGINNER", "A1"],
        "ELEMENTARY": ["ELEMENTARY", "A2"],
        "PRE-INTERMEDIATE": ["PRE-INTERMEDIATE", "B1"],
        "INTERMEDIATE": ["INTERMEDIATE", "B2"],
        "UPPER-INTERMEDIATE": ["UPPER-INTERMEDIATE", "C1"],
        "ADVANCED": ["ADVANCED", "C1"],
    }
    raw = str(user_level or "").strip().upper()
    if raw in mapping:
        return mapping[raw]
        
    if lvl == "A1":
        return ["A1"]
    if lvl == "A2":
        return ["A2"]
    return ["A2", "B1", "B2", "C1"]


def _coerce_dt(value: datetime | str | None) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        if s:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(s[:19], fmt)
                except Exception:
                    continue
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass
    return datetime.utcnow()


def _db_ts(value: datetime | str | None) -> str:
    return _coerce_dt(value).strftime("%Y-%m-%d %H:%M:%S")


def get_vocab_cooldown_word_ids(
    user_id: int,
    question_type: str,
    now_ts: datetime | str | None = None,
) -> set[int]:
    ensure_vocab_word_mastery_schema()
    conn = get_conn()
    cur = conn.cursor()
    out: set[int] = set()
    try:
        qtype = _normalize_vocab_question_type(question_type)
        cur.execute(
            """
            SELECT word_id
            FROM vocab_word_mastery
            WHERE user_id=?
              AND question_type=?
              AND cooldown_until IS NOT NULL
              AND cooldown_until > ?
            """,
            (int(user_id), qtype, _db_ts(now_ts)),
        )
        for row in cur.fetchall() or []:
            try:
                out.add(int(row["word_id"]))
            except Exception:
                continue
        return out
    except Exception:
        logger.exception("Failed to load vocab cooldown word ids for user=%s", user_id)
        return set()
    finally:
        conn.close()


def record_vocab_word_result(
    user_id: int,
    word_id: int,
    question_type: str,
    is_correct: bool,
    answered_at: datetime | str | None = None,
) -> None:
    ensure_vocab_word_mastery_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        uid = int(user_id)
        wid = int(word_id)
        qtype = _normalize_vocab_question_type(question_type)
        now_dt = _coerce_dt(answered_at)
        now_ts = now_dt.strftime("%Y-%m-%d %H:%M:%S")

        # If still in active cooldown, keep row as-is.
        cur.execute(
            """
            SELECT 1
            FROM vocab_word_mastery
            WHERE user_id=? AND word_id=? AND question_type=?
              AND cooldown_until IS NOT NULL
              AND cooldown_until > ?
            LIMIT 1
            """,
            (uid, wid, qtype, now_ts),
        )
        if cur.fetchone():
            cur.execute(
                """
                UPDATE vocab_word_mastery
                SET updated_at=?
                WHERE user_id=? AND word_id=? AND question_type=?
                """,
                (now_ts, uid, wid, qtype),
            )
            conn.commit()
            return

        cur.execute(
            """
            SELECT consecutive_correct
            FROM vocab_word_mastery
            WHERE user_id=? AND word_id=? AND question_type=?
            LIMIT 1
            """,
            (uid, wid, qtype),
        )
        row = cur.fetchone()
        prev = int((row or {}).get("consecutive_correct") or 0)

        if is_correct:
            streak = prev + 1
            if streak >= 2:
                new_streak = 0
                cooldown_until = (now_dt + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
            else:
                new_streak = streak
                cooldown_until = None
        else:
            new_streak = 0
            cooldown_until = None

        if row:
            cur.execute(
                """
                UPDATE vocab_word_mastery
                SET consecutive_correct=?, cooldown_until=?, updated_at=?
                WHERE user_id=? AND word_id=? AND question_type=?
                """,
                (new_streak, cooldown_until, now_ts, uid, wid, qtype),
            )
        else:
            cur.execute(
                """
                INSERT INTO vocab_word_mastery
                    (user_id, word_id, question_type, consecutive_correct, cooldown_until, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (uid, wid, qtype, new_streak, cooldown_until, now_ts),
            )
        conn.commit()
    except Exception:
        logger.exception(
            "Failed to record vocab word result user=%s word=%s qtype=%s",
            user_id,
            word_id,
            question_type,
        )
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_dpoints_schema() -> bool:
    """Global wallet source-of-truth: D'points."""
    if _schema_ready("dpoints_schema_v2"):
        return True
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            # Multi-worker startup can otherwise run identical DDL in parallel.
            # A transaction-level advisory lock serializes this tiny migration
            # without broad ACCESS EXCLUSIVE table locks that caused deadlocks.
            cur.execute("SELECT pg_advisory_xact_lock(?)", (92025052501,))
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_dpoints (
                user_id BIGINT PRIMARY KEY,
                dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_dpoints_updated_at ON user_dpoints(updated_at)")
        except Exception:
            pass
        if _is_postgres_enabled():
            cur.execute("ALTER TABLE user_dpoints ADD COLUMN IF NOT EXISTS dcoin_floor DOUBLE PRECISION NOT NULL DEFAULT 0")
        else:
            try:
                cur.execute("ALTER TABLE user_dpoints ADD COLUMN dcoin_floor DOUBLE PRECISION NOT NULL DEFAULT 0")
            except Exception:
                pass
        if _is_postgres_enabled():
            cur.execute("ALTER TABLE user_dpoints ADD COLUMN IF NOT EXISTS dcoin_anchor_value DOUBLE PRECISION")
            cur.execute("ALTER TABLE user_dpoints ADD COLUMN IF NOT EXISTS dcoin_anchor_dpoints DOUBLE PRECISION")
        else:
            try:
                cur.execute("ALTER TABLE user_dpoints ADD COLUMN dcoin_anchor_value DOUBLE PRECISION")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE user_dpoints ADD COLUMN dcoin_anchor_dpoints DOUBLE PRECISION")
            except Exception:
                pass

        if _is_postgres_enabled():
            cur.execute("ALTER TABLE diamond_history ADD COLUMN IF NOT EXISTS dpoints_change DOUBLE PRECISION")
        else:
            try:
                cur.execute("ALTER TABLE diamond_history ADD COLUMN dpoints_change DOUBLE PRECISION")
            except Exception:
                pass
        conn.commit()
        _mark_schema_ready("dpoints_schema_v2")
        return True
    except Exception:
        logger.exception("Failed to ensure D'points schema")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def ensure_subject_dcoin_schema() -> bool:
    """Per-subject D'coin balances and subject-aware history."""
    if _schema_ready("subject_dcoin_schema_v2"):
        return True
    ensure_dpoints_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute("SELECT pg_advisory_xact_lock(?)", (92025052502,))
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_subject_dcoins (
                user_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                balance DOUBLE PRECISION NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, subject),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            '''
        )
        if _is_postgres_enabled():
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='user_subject_dcoins' AND column_name='dcoin'
                LIMIT 1
                """
            )
            if cur.fetchone():
                cur.execute("ALTER TABLE user_subject_dcoins RENAME COLUMN dcoin TO balance")
        else:
            try:
                cur.execute("ALTER TABLE user_subject_dcoins RENAME COLUMN dcoin TO balance")
            except Exception:
                pass
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_subject_dcoins_user_id ON user_subject_dcoins(user_id)"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_subject_dcoins_subject ON user_subject_dcoins(subject)"
            )
        except Exception:
            pass
        if _is_postgres_enabled():
            cur.execute("ALTER TABLE diamond_history ADD COLUMN IF NOT EXISTS subject TEXT")
            cur.execute("ALTER TABLE diamond_history ADD COLUMN IF NOT EXISTS change_type TEXT")
            cur.execute("ALTER TABLE diamond_history ADD COLUMN IF NOT EXISTS dpoints_change DOUBLE PRECISION")
        else:
            try:
                cur.execute("ALTER TABLE diamond_history ADD COLUMN subject TEXT")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE diamond_history ADD COLUMN change_type TEXT")
            except Exception:
                pass
            try:
                cur.execute("ALTER TABLE diamond_history ADD COLUMN dpoints_change DOUBLE PRECISION")
            except Exception:
                pass
        conn.commit()
        _mark_schema_ready("subject_dcoin_schema_v2")
        return True
    except Exception:
        logger.exception("Failed to ensure subject D'coin schema")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def _migration_applied(cur, name: str) -> bool:
    try:
        cur.execute("SELECT 1 FROM _migrations WHERE name=? LIMIT 1", (name,))
        return bool(cur.fetchone())
    except Exception:
        return False


def _mark_migration_applied(cur, conn, name: str) -> None:
    try:
        if _is_postgres_enabled():
            cur.execute(
                "INSERT INTO _migrations(name) VALUES (?) ON CONFLICT DO NOTHING",
                (name,),
            )
        else:
            cur.execute("INSERT OR IGNORE INTO _migrations(name) VALUES (?)", (name,))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def ensure_dcoin_schema_migrations() -> None:
    """
    One-time: diamond_history.diamonds_change -> dcoin_change; duel sessions table rename;
    legacy users.diamonds backfill then DROP; add change_type column.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS _migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        # 1) diamond_history column rename
        if not _migration_applied(cur, "dh_dcoin_change_rename"):
            if _is_postgres_enabled():
                try:
                    cur.execute(
                        """
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema='public' AND table_name='diamond_history'
                          AND column_name='diamonds_change'
                        """
                    )
                    if cur.fetchone():
                        cur.execute(
                            "ALTER TABLE diamond_history RENAME COLUMN diamonds_change TO dcoin_change"
                        )
                    cur.execute(
                        "ALTER TABLE diamond_history ADD COLUMN IF NOT EXISTS change_type TEXT"
                    )
                    cur.execute(
                        "ALTER TABLE diamond_history ADD COLUMN IF NOT EXISTS subject TEXT"
                    )
                    cur.execute(
                        "ALTER TABLE diamond_history ADD COLUMN IF NOT EXISTS dpoints_change DOUBLE PRECISION"
                    )
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    cur = conn.cursor()
            else:
                try:
                    cur.execute("PRAGMA table_info(diamond_history)")
                    cols = {str(r[1]) for r in cur.fetchall()}
                except Exception:
                    cols = set()
                if "dcoin_change" not in cols and "diamonds_change" in cols:
                    try:
                        cur.execute(
                            "ALTER TABLE diamond_history RENAME COLUMN diamonds_change TO dcoin_change"
                        )
                    except Exception:
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        cur = conn.cursor()
                try:
                    cur.execute("ALTER TABLE diamond_history ADD COLUMN change_type TEXT")
                except Exception:
                    pass
                try:
                    cur.execute("ALTER TABLE diamond_history ADD COLUMN subject TEXT")
                except Exception:
                    pass
                try:
                    cur.execute("ALTER TABLE diamond_history ADD COLUMN dpoints_change DOUBLE PRECISION")
                except Exception:
                    pass
            _mark_migration_applied(cur, conn, "dh_dcoin_change_rename")

        # 2) Rename legacy duel table arena_duel_match_sessions -> open_duel_sessions
        if not _migration_applied(cur, "duel_open_sessions_rename"):
            legacy_tbl = "arena_duel_match_sessions"
            new_tbl = "open_duel_sessions"
            if _is_postgres_enabled():
                try:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='public' AND table_name=?
                        """,
                        (legacy_tbl,),
                    )
                    old_exists = bool(cur.fetchone())
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='public' AND table_name=?
                        """,
                        (new_tbl,),
                    )
                    new_exists = bool(cur.fetchone())
                    if old_exists and not new_exists:
                        cur.execute(f"ALTER TABLE {legacy_tbl} RENAME TO {new_tbl}")
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    cur = conn.cursor()
            else:
                raise RuntimeError("PostgreSQL-only runtime: legacy SQLite migration path is disabled")
            _mark_migration_applied(cur, conn, "duel_open_sessions_rename")

        # 3) Legacy users.diamonds -> user_subject_dcoins then DROP
        if not _migration_applied(cur, "users_drop_legacy_diamonds"):
            has_diamonds = False
            if _is_postgres_enabled():
                try:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.columns
                        WHERE table_schema='public' AND table_name='users' AND column_name='diamonds'
                        """
                    )
                    has_diamonds = bool(cur.fetchone())
                except Exception:
                    has_diamonds = False
            else:
                try:
                    cur.execute("PRAGMA table_info(users)")
                    has_diamonds = any(str(r[1]) == "diamonds" for r in cur.fetchall())
                except Exception:
                    has_diamonds = False
            if has_diamonds:
                ensure_subject_dcoin_schema()
                try:
                    if _is_postgres_enabled():
                        cur.execute(
                            "SELECT id FROM users WHERE COALESCE(diamonds, 0) > 0"
                        )
                    else:
                        cur.execute(
                            "SELECT id FROM users WHERE COALESCE(diamonds, 0) > 0"
                        )
                    for row in cur.fetchall() or []:
                        _migrate_legacy_user_diamonds_to_subjects(int(row["id"]))
                except Exception:
                    logger.exception("Bulk legacy diamonds migration failed")
                try:
                    if _is_postgres_enabled():
                        cur.execute("ALTER TABLE users DROP COLUMN IF EXISTS diamonds")
                        cur.execute(
                            "ALTER TABLE users DROP COLUMN IF EXISTS last_diamond_update"
                        )
                    else:
                        try:
                            cur.execute("ALTER TABLE users DROP COLUMN diamonds")
                        except Exception:
                            pass
                        try:
                            cur.execute("ALTER TABLE users DROP COLUMN last_diamond_update")
                        except Exception:
                            pass
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
            _mark_migration_applied(cur, conn, "users_drop_legacy_diamonds")

        # 4) Global wallet source-of-truth: user_dpoints + one-time backfill from subject balances
        if not _migration_applied(cur, "wallet_dpoints_global_v1"):
            ensure_dpoints_schema()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_dpoints (
                    user_id BIGINT PRIMARY KEY,
                    dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            # Policy selected by product: D'points = current total D'coin (not multiplied by subject count)
            cur.execute(
                """
                INSERT INTO user_dpoints (user_id, dpoints, updated_at)
                SELECT
                    u.id,
                    COALESCE(SUM(sd.balance), 0) AS dpoints,
                    CURRENT_TIMESTAMP
                FROM users u
                LEFT JOIN user_subject_dcoins sd ON sd.user_id = u.id
                WHERE u.login_type IN (1, 2)
                GROUP BY u.id
                ON CONFLICT (user_id)
                DO UPDATE SET
                    dpoints = EXCLUDED.dpoints,
                    updated_at = EXCLUDED.updated_at
                """
            )
            _mark_migration_applied(cur, conn, "wallet_dpoints_global_v1")

        # 5) Case-insensitive dedupe lookup index for vocabulary imports/generation
        if not _migration_applied(cur, "words_dedupe_ci_index_v1"):
            try:
                if _is_postgres_enabled():
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_words_sub_lang_word_ci
                        ON words (LOWER(subject), LOWER(language), LOWER(BTRIM(word)))
                        """
                    )
                else:
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_words_sub_lang_word_ci
                        ON words (LOWER(TRIM(subject)), LOWER(TRIM(language)), LOWER(TRIM(word)))
                        """
                    )
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur = conn.cursor()
            _mark_migration_applied(cur, conn, "words_dedupe_ci_index_v1")

        # 6) Vocabulary runtime indexes for paged list + quiz generation.
        if not _migration_applied(cur, "words_runtime_indexes_v1"):
            try:
                if _is_postgres_enabled():
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_words_runtime_subject_language_id
                        ON words (LOWER(subject), LOWER(language), id)
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_words_runtime_subject_language_level_id
                        ON words (LOWER(subject), LOWER(language), level, id)
                        """
                    )
                else:
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_words_runtime_subject_language_id
                        ON words (LOWER(subject), LOWER(language), id)
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_words_runtime_subject_language_level_id
                        ON words (LOWER(subject), LOWER(language), level, id)
                        """
                    )
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur = conn.cursor()
            _mark_migration_applied(cur, conn, "words_runtime_indexes_v1")

        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_support_lessons_schema() -> None:
    """
    Support / Lesson booking schema aligned with Lesson Sessions bot.
    Cross-DB friendly (SQLite + Postgres) by using TEXT primary keys.
    """
    global _SUPPORT_LESSONS_SCHEMA_READY
    if _SUPPORT_LESSONS_SCHEMA_READY:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS _migrations (
                    name TEXT PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        except Exception:
            pass

        # Admin/user prefs for support bot (and optional student-side booking prefs)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_users (
                telegram_id TEXT PRIMARY KEY,
                lang TEXT,
                first_name TEXT,
                full_name TEXT,
                username TEXT,
                reminder_pref TEXT DEFAULT '1h',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_bookings (
                id TEXT PRIMARY KEY,
                student_user_id BIGINT NOT NULL,
                student_telegram_id TEXT,
                branch TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                start_ts TEXT,
                purpose TEXT,
                support_subject TEXT,
                status TEXT NOT NULL DEFAULT 'approved',
                handled_by_admin_id BIGINT,
                admin_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Reminders (4h/30m/pref1h/pref24h, plus optional teacher/admin reminders)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_reminders (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                telegram_id TEXT NOT NULL,
                admin_id BIGINT,
                reminder_target TEXT NOT NULL,
                reminder_type TEXT NOT NULL,
                scheduled_time TEXT,
                sent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Closed dates with reason (admin managed)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_closed_dates (
                date TEXT PRIMARY KEY,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_holidays (
                date TEXT PRIMARY KEY
            )
            """
        )
        # Waitlist
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_waitlist (
                id TEXT PRIMARY KEY,
                date TEXT,
                time TEXT,
                branch TEXT,
                telegram_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Extra slots (admin-managed additional 30-min slots)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_extra_slots (
                id TEXT PRIMARY KEY,
                date TEXT,
                time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_bookings_student_user_id ON lesson_bookings(student_user_id)")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_bookings_status ON lesson_bookings(status)")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_bookings_start_ts ON lesson_bookings(start_ts)")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_created_at ON lesson_bookings(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_status_created_at ON lesson_bookings(status, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_student_created_at ON lesson_bookings(student_user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_date_time ON lesson_bookings(date, time)",
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_branch_date_time ON lesson_bookings(branch, date, time)",
        ):
            try:
                cur.execute(index_sql)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_reminders_scheduled_time ON lesson_reminders(scheduled_time)")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_reminders_sent ON lesson_reminders(sent)")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_extra_slots_date ON lesson_extra_slots(date)")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_branch_weekdays (
                branch TEXT PRIMARY KEY,
                weekdays TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_blocked_slots (
                id TEXT PRIMARY KEY,
                branch TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                reason TEXT,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(branch, date, time)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_branch_date_closed (
                branch TEXT NOT NULL,
                date TEXT NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (branch, date)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_recurring_slot_rules (
                id TEXT PRIMARY KEY,
                branch TEXT NOT NULL,
                weekday INTEGER NOT NULL,
                time TEXT NOT NULL,
                mode TEXT NOT NULL,
                reason TEXT,
                created_by BIGINT,
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(branch, weekday, time, mode)
            )
            """
        )
        # Commit core support schema before optional/legacy steps.
        # This prevents optional-step rollbacks from undoing required table creation on Postgres.
        conn.commit()
        try:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='lesson_extra_slots' AND column_name='branch'
                """
            ) if _is_postgres_enabled() else cur.execute("PRAGMA table_info(lesson_extra_slots)")
            has_branch = bool(cur.fetchone()) if _is_postgres_enabled() else any(
                str((dict(r) if isinstance(r, dict) else {"name": r[1]}).get("name")) == "branch"
                for r in (cur.fetchall() or [])
            )
            if not has_branch:
                cur.execute("ALTER TABLE lesson_extra_slots ADD COLUMN branch TEXT")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute(
                """
                INSERT INTO lesson_branch_weekdays(branch, weekdays)
                VALUES (?, ?)
                ON CONFLICT(branch) DO NOTHING
                """,
                ("branch_1", "1,3,5"),
            )
            cur.execute(
                """
                INSERT INTO lesson_branch_weekdays(branch, weekdays)
                VALUES (?, ?)
                ON CONFLICT(branch) DO NOTHING
                """,
                ("branch_2", "0,2,4"),
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_blocked_slots_branch_date ON lesson_blocked_slots(branch, date)")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_lesson_recurring_slot_rules_lookup ON lesson_recurring_slot_rules(branch, weekday, time, mode, active)"
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='lesson_bookings' AND column_name='end_ts'
                """
            ) if _is_postgres_enabled() else cur.execute("PRAGMA table_info(lesson_bookings)")
            has_end_ts = bool(cur.fetchone()) if _is_postgres_enabled() else any(
                str((dict(r) if isinstance(r, dict) else {"name": r[1]}).get("name")) == "end_ts"
                for r in (cur.fetchall() or [])
            )
            if not has_end_ts:
                cur.execute("ALTER TABLE lesson_bookings ADD COLUMN end_ts TEXT")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        # Support lesson attendance/bonus state columns.
        for col_name, col_sql in (
            ("support_teacher_id", "BIGINT"),
            ("support_subject", "TEXT"),
            ("support_attendance_status", "TEXT"),
            ("support_attendance_marked_at", "TIMESTAMP"),
            ("support_attendance_penalty_applied", "INTEGER DEFAULT 0"),
            ("support_bonus_awarded", "INTEGER DEFAULT 0"),
            ("support_bonus_amount", "DOUBLE PRECISION DEFAULT 0"),
        ):
            try:
                if _is_postgres_enabled():
                    cur.execute(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name='lesson_bookings' AND column_name=?
                        """,
                        (col_name,),
                    )
                    has_col = bool(cur.fetchone())
                else:
                    cur.execute("PRAGMA table_info(lesson_bookings)")
                    has_col = any(
                        str((dict(r) if isinstance(r, dict) else {"name": r[1]}).get("name")) == col_name
                        for r in (cur.fetchall() or [])
                    )
                if not has_col:
                    cur.execute(f"ALTER TABLE lesson_bookings ADD COLUMN {col_name} {col_sql}")
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_student_status_end ON lesson_bookings(student_user_id, status, end_ts)",
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_subject_status ON lesson_bookings(support_subject, status)",
            "CREATE INDEX IF NOT EXISTS idx_lesson_bookings_teacher_subject_start ON lesson_bookings(support_teacher_id, support_subject, start_ts)",
        ):
            try:
                cur.execute(index_sql)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS support_teacher_weekday_settings (
                support_teacher_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                weekday INTEGER NOT NULL,
                active INTEGER DEFAULT 1,
                branch TEXT NOT NULL DEFAULT 'branch_1',
                updated_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (support_teacher_id, subject, weekday)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS support_teacher_date_overrides (
                support_teacher_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                date TEXT NOT NULL,
                is_closed INTEGER DEFAULT 1,
                reason TEXT,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (support_teacher_id, subject, date)
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS support_teacher_time_slots (
                id TEXT PRIMARY KEY,
                support_teacher_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                weekday INTEGER NOT NULL,
                time TEXT NOT NULL,
                active INTEGER DEFAULT 1,
                created_by BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(support_teacher_id, subject, weekday, time)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS support_booking_dpoint_actions (
                id TEXT PRIMARY KEY,
                booking_id TEXT NOT NULL,
                student_user_id BIGINT NOT NULL,
                support_teacher_id BIGINT,
                actor_user_id BIGINT NOT NULL,
                subject TEXT,
                action_type TEXT NOT NULL,
                amount DOUBLE PRECISION NOT NULL,
                reason TEXT NOT NULL,
                balance_before DOUBLE PRECISION,
                balance_after DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_support_weekday_subject_teacher ON support_teacher_weekday_settings(subject, support_teacher_id, weekday)",
            "CREATE INDEX IF NOT EXISTS idx_support_date_subject_teacher ON support_teacher_date_overrides(subject, support_teacher_id, date)",
            "CREATE INDEX IF NOT EXISTS idx_support_time_subject_teacher ON support_teacher_time_slots(subject, support_teacher_id, weekday, active)",
            "CREATE INDEX IF NOT EXISTS idx_support_dpoint_booking ON support_booking_dpoint_actions(booking_id)",
        ):
            try:
                cur.execute(index_sql)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass

        # One-time backfill: normalize time columns from '14' -> '14:00' etc.
        if not _migration_applied(cur, "support_lessons_time_backfill_hhmm"):
            from support_booking_time import normalize_time_hhmm

            def _backfill_table(table: str) -> None:
                try:
                    cur.execute(f"SELECT id, time FROM {table}")
                    rows = cur.fetchall() or []
                except Exception:
                    rows = []
                for r in rows:
                    try:
                        rid = (r.get("id") if isinstance(r, dict) else r[0])  # type: ignore[index]
                        rt = (r.get("time") if isinstance(r, dict) else r[1])  # type: ignore[index]
                        tm = normalize_time_hhmm(str(rt))
                        if tm and str(rt) != tm:
                            cur.execute(f"UPDATE {table} SET time=? WHERE id=?", (tm, str(rid)))
                    except Exception:
                        continue

            _backfill_table("lesson_bookings")
            _backfill_table("lesson_extra_slots")
            _backfill_table("lesson_blocked_slots")
            _mark_migration_applied(cur, conn, "support_lessons_time_backfill_hhmm")
        conn.commit()
        _SUPPORT_LESSONS_SCHEMA_READY = True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    _backfill_lesson_bookings_end_ts()

# =========================
# Support Teacher Slots Management
# =========================

def list_support_teacher_slots_by_weekday(teacher_id: int, subject: str, weekday: int) -> list[str]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT time FROM support_teacher_time_slots 
            WHERE support_teacher_id=? AND subject=? AND weekday=? AND active=1
            ORDER BY time ASC
            """,
            (int(teacher_id), str(subject), int(weekday)),
        )
        rows = cur.fetchall() or []
        return [str(r[0] if not isinstance(r, dict) else r["time"]) for r in rows]
    except Exception:
        return []
    finally:
        conn.close()

def toggle_support_teacher_slot(teacher_id: int, subject: str, weekday: int, time_str: str) -> bool:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT active FROM support_teacher_time_slots 
            WHERE support_teacher_id=? AND subject=? AND weekday=? AND time=?
            LIMIT 1
            """,
            (int(teacher_id), str(subject), int(weekday), str(time_str)),
        )
        row = cur.fetchone()
        if row:
            current = int(row[0] if not isinstance(row, dict) else row["active"])
            new_val = 0 if current == 1 else 1
            cur.execute(
                """
                UPDATE support_teacher_time_slots 
                SET active=? 
                WHERE support_teacher_id=? AND subject=? AND weekday=? AND time=?
                """,
                (new_val, int(teacher_id), str(subject), int(weekday), str(time_str)),
            )
        else:
            cur.execute(
                """
                INSERT INTO support_teacher_time_slots (support_teacher_id, subject, weekday, time, active) 
                VALUES (?, ?, ?, ?, 1)
                """,
                (int(teacher_id), str(subject), int(weekday), str(time_str)),
            )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()

def get_available_support_slots_for_subject(subject: str, date_iso: str) -> list[str]:
    ensure_support_lessons_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        from datetime import datetime
        d = datetime.fromisoformat(date_iso)
        weekday = d.weekday()
        
        # O'qituvchilar ochgan barcha yagona (unique) vaqtlar
        cur.execute(
            """
            SELECT DISTINCT time FROM support_teacher_time_slots 
            WHERE subject=? AND weekday=? AND active=1
            ORDER BY time ASC
            """,
            (str(subject), weekday),
        )
        rows = cur.fetchall() or []
        all_times = [str(r[0] if not isinstance(r, dict) else r["time"]) for r in rows]
        
        # Endi ularning bandligini tekshiramiz
        available = []
        for t in all_times:
            if lesson_is_slot_free_for_subject(subject, date_iso, t):
                available.append(t)
        return available
    except Exception:
        return []
    finally:
        conn.close()


def _parse_iso_utc(s: str | None):
    from datetime import datetime, timezone

    if not s:
        return None
    t = str(s).strip()
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(t)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _backfill_lesson_bookings_end_ts() -> None:
    """Set end_ts = start_ts + 60 minutes where missing (legacy rows)."""
    from datetime import timedelta, timezone

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, start_ts FROM lesson_bookings
            WHERE (end_ts IS NULL OR end_ts = '') AND start_ts IS NOT NULL AND start_ts != ''
            """
        )
        rows = cur.fetchall() or []
        for r in rows:
            rid = dict(r).get("id") if isinstance(r, dict) else r[0]
            st = dict(r).get("start_ts") if isinstance(r, dict) else r[1]
            dt = _parse_iso_utc(st)
            if not dt:
                continue
            end = (dt + timedelta(minutes=60)).isoformat()
            cur.execute("UPDATE lesson_bookings SET end_ts=? WHERE id=?", (end, str(rid)))
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def student_has_active_upcoming_booking(student_user_id: int, now_iso_utc: str | None = None, subject: str | None = None) -> bool:
    """True if student has pending/approved booking whose lesson end is still in the future."""
    from datetime import datetime, timezone

    ensure_support_lessons_schema()
    if now_iso_utc is None:
        now_iso_utc = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    cur = conn.cursor()
    try:
        vals: list = [int(student_user_id), now_iso_utc]
        subject_filter = ""
        if str(subject or "").strip():
            subject_filter = " AND COALESCE(support_subject, '') = ?"
            vals.append(str(subject).strip())
        cur.execute(
            f"""
            SELECT 1 FROM lesson_bookings
            WHERE student_user_id = ?
              AND status IN ('pending', 'approved')
              AND end_ts IS NOT NULL
              AND end_ts > ?
              {subject_filter}
            LIMIT 1
            """,
            tuple(vals),
        )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def get_last_ended_lesson_end_ts(student_user_id: int, now_iso_utc: str | None = None, subject: str | None = None) -> str | None:
    """Most recent lesson end_ts that is already in the past (for cooldown messaging)."""
    from datetime import datetime, timezone

    ensure_support_lessons_schema()
    if now_iso_utc is None:
        now_iso_utc = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    cur = conn.cursor()
    try:
        vals: list = [int(student_user_id), now_iso_utc]
        subject_filter = ""
        if str(subject or "").strip():
            subject_filter = " AND COALESCE(support_subject, '') = ?"
            vals.append(str(subject).strip())
        cur.execute(
            f"""
            SELECT end_ts FROM lesson_bookings
            WHERE student_user_id = ?
              AND status != 'cancelled'
              AND end_ts IS NOT NULL
              AND end_ts < ?
              {subject_filter}
            ORDER BY end_ts DESC
            LIMIT 1
            """,
            tuple(vals),
        )
        row = cur.fetchone()
        if not row:
            return None
        return (dict(row) if isinstance(row, dict) else {"end_ts": row[0]}).get("end_ts")
    except Exception:
        return None
    finally:
        conn.close()


def get_next_lesson_booking_allowed_after_utc_iso(student_user_id: int, now_iso_utc: str | None = None, subject: str | None = None) -> str | None:
    """
    If the student must wait (6 hours after last finished lesson), return UTC ISO when booking is allowed.
    Returns None if no cooldown applies (caller must still check active booking).
    """
    from datetime import datetime, timedelta, timezone

    ensure_support_lessons_schema()
    if now_iso_utc is None:
        now_iso_utc = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    cur = conn.cursor()
    try:
        vals: list = [int(student_user_id), now_iso_utc]
        subject_filter = ""
        if str(subject or "").strip():
            subject_filter = " AND COALESCE(support_subject, '') = ?"
            vals.append(str(subject).strip())
        cur.execute(
            f"""
            SELECT end_ts FROM lesson_bookings
            WHERE student_user_id = ?
              AND status != 'cancelled'
              AND end_ts IS NOT NULL
              AND end_ts < ?
              {subject_filter}
            ORDER BY end_ts DESC
            LIMIT 1
            """,
            tuple(vals),
        )
        row = cur.fetchone()
        if not row:
            return None
        end_s = (dict(row) if isinstance(row, dict) else {"end_ts": row[0]}).get("end_ts")
        last_end = _parse_iso_utc(end_s)
        now = _parse_iso_utc(now_iso_utc)
        if not last_end or not now:
            return None
        unlock = last_end + timedelta(hours=6)
        if unlock > now:
            return unlock.isoformat()
        return None
    except Exception:
        return None
    finally:
        conn.close()


def ensure_lesson_otmen_requests_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_otmen_requests (
                id TEXT PRIMARY KEY,
                date_str TEXT NOT NULL,
                reason TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT,
                cancelled_at TIMESTAMP,
                cancelled_by_admin_id BIGINT,
                cancel_mode TEXT NOT NULL DEFAULT 'manual'
            )
            """
        )
        # Backward-compat: old databases may not have cancel_mode yet.
        try:
            cur.execute("ALTER TABLE lesson_otmen_requests ADD COLUMN cancel_mode TEXT NOT NULL DEFAULT 'manual'")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_otmen_requests_date ON lesson_otmen_requests(date_str)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_lesson_otmen_requests_date_mode ON lesson_otmen_requests(date_str, cancel_mode)")
        except Exception:
            pass
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _migrate_legacy_user_diamonds_to_subjects(user_id: int, forced_subject: str | None = None) -> None:
    """
    Legacy compatibility:
    If `user_subject_dcoins` has no balance for a user yet, but `users.diamonds` has a value,
    initialize `user_subject_dcoins` by distributing legacy total equally across the user's subjects.

    After migration, `users.diamonds` is no longer used for balances (we only seed subject rows once).
    """
    ensure_subject_dcoin_schema()

    forced_subj = (forced_subject or "").strip().title()

    conn = get_conn()
    cur = conn.cursor()
    try:
        # If user already has any subject balance, do nothing.
        cur.execute("SELECT COALESCE(SUM(balance), 0) as total FROM user_subject_dcoins WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        total_subject_balance = float((row or {}).get("total") or 0)
        if total_subject_balance > 0:
            return

        try:
            cur.execute("SELECT COALESCE(diamonds, 0) as legacy_total FROM users WHERE id=?", (user_id,))
        except Exception:
            return
        lrow = cur.fetchone()
        legacy_total = float((lrow or {}).get("legacy_total") or 0)
        if legacy_total <= 0:
            return

        # Determine subjects for this user.
        subjects = get_user_subjects(user_id) or []
        if forced_subj:
            if forced_subj not in subjects:
                subjects = [forced_subj]
        if not subjects:
            # Fallback: use users.subject if present, else English
            cur.execute("SELECT subject FROM users WHERE id=?", (user_id,))
            urow = cur.fetchone()
            raw_subj = (urow or {}).get("subject") if urow else None
            sub = (raw_subj or "").strip().title() if raw_subj else "English"
            subjects = [sub]

        subjects = list(dict.fromkeys([s.strip().title() for s in subjects if s and s.strip()]))
        if not subjects:
            subjects = ["English"]

        share = legacy_total / float(len(subjects))

        for subj in subjects:
            cur.execute(
                '''
                INSERT INTO user_subject_dcoins(user_id, subject, balance, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, subject)
                DO UPDATE SET balance=excluded.balance, updated_at=excluded.updated_at
                ''',
                (int(user_id), subj, share),
            )

        conn.commit()
        # Migration for older DBs (table exists but column missing).
        try:
            _ensure_arena_run_answers_is_unanswered_column()
        except Exception:
            pass
    finally:
        conn.close()


def get_user_subject_dcoins(user_id: int) -> dict[str, float]:
    # Compatibility wrapper for legacy callers expecting a subject->balance map.
    try:
        return {"GLOBAL": float(get_dcoins(int(user_id)))}
    except Exception:
        logger.exception("get_user_subject_dcoins failed for user_id=%s", user_id)
        return {}


def get_student_ai_daily_requests(user_id: int, usage_date: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT requests_count FROM student_ai_chat_usage WHERE user_id=? AND usage_date=?",
            (user_id, usage_date),
        )
        row = cur.fetchone()
        return int((row or {}).get("requests_count") or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def increment_student_ai_daily_requests(user_id: int, usage_date: str, prompt: str = "") -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            INSERT INTO student_ai_chat_usage (user_id, usage_date, requests_count, last_prompt, updated_at)
            VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, usage_date)
            DO UPDATE SET
                requests_count = student_ai_chat_usage.requests_count + 1,
                last_prompt = excluded.last_prompt,
                updated_at = CURRENT_TIMESTAMP
            ''',
            (user_id, usage_date, (prompt or "")[:1000]),
        )
        conn.commit()
        return get_student_ai_daily_requests(user_id, usage_date)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return get_student_ai_daily_requests(user_id, usage_date)
    finally:
        conn.close()


def count_available_daily_tests(subject: str, level: str, created_by: int | None = None) -> int:
    """Count unused daily-test items (not reserved by any student yet)."""
    subj = (subject or "").strip().title()
    lvl = (level or "").strip().upper()
    conn = get_conn()
    cur = conn.cursor()
    if created_by is None:
        cur.execute(
            "SELECT COUNT(*) as c FROM daily_tests_bank WHERE active=1 AND first_used_at IS NULL AND subject=? AND level=?",
            (subj, lvl),
        )
    else:
        cur.execute(
            "SELECT COUNT(*) as c FROM daily_tests_bank WHERE active=1 AND first_used_at IS NULL AND subject=? AND level=? AND created_by=?",
            (subj, lvl, created_by),
        )
    row = cur.fetchone()
    conn.close()
    return int(row["c"]) if row and row["c"] is not None else 0


def get_daily_tests_unused_stock_by_subject_level() -> list[dict]:
    """Unused daily_tests_bank rows grouped by subject and level (admin stock report)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT subject, level, COUNT(*) AS c
        FROM daily_tests_bank
        WHERE active = 1 AND first_used_at IS NULL
        GROUP BY subject, level
        ORDER BY subject ASC, level ASC
        """
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def _normalize_seed_word_key(value: Any) -> str:
    return str(value or "").strip().lower()


def ensure_vocab_seed_pool_schema() -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS vocab_seed_pool (
                id BIGSERIAL PRIMARY KEY,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                language TEXT NOT NULL,
                word TEXT NOT NULL,
                word_norm TEXT NOT NULL,
                translation_uz TEXT,
                translation_ru TEXT,
                definition TEXT,
                example TEXT,
                source TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(subject, level, language, word_norm)
            )
            """
        )
        if _is_postgres_enabled():
            cur.execute("ALTER TABLE vocab_seed_pool ADD COLUMN IF NOT EXISTS word_norm TEXT")
            cur.execute("ALTER TABLE vocab_seed_pool ALTER COLUMN word_norm SET DEFAULT ''")
        else:
            try:
                cur.execute("ALTER TABLE vocab_seed_pool ADD COLUMN word_norm TEXT")
            except Exception:
                pass
        cur.execute(
            "UPDATE vocab_seed_pool SET word_norm=LOWER(TRIM(word)) "
            "WHERE word_norm IS NULL OR TRIM(word_norm)=''"
        )
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_vocab_seed_pool_lookup "
                "ON vocab_seed_pool(subject, level, language)"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_vocab_seed_pool_word_norm "
                "ON vocab_seed_pool(subject, language, word_norm)"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_vocab_seed_pool_scope_word "
                "ON vocab_seed_pool(subject, level, language, word_norm)"
            )
        except Exception:
            pass
        conn.commit()
        return True
    except Exception:
        logger.exception("Failed to ensure vocab_seed_pool schema")
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def upsert_vocab_seed_pool_items(items: list[dict[str, Any]]) -> dict[str, int]:
    """
    Upsert seed items into vocab_seed_pool by canonical key:
    (subject, level, language, lower(trim(word))).
    """
    ensure_vocab_seed_pool_schema()
    out = {"total": 0, "inserted": 0, "updated": 0, "skipped_invalid": 0}
    if not items:
        return out

    normalized_rows: list[tuple[str, str, str, str, str, str, str, str, str, str, str, str]] = []
    for it in items:
        subject = str(it.get("subject") or "").strip().title()
        level = str(it.get("level") or "").strip().upper()
        language = str(it.get("language") or "").strip().lower()
        word = str(it.get("word") or "").strip()
        word_norm = _normalize_seed_word_key(word)
        if not subject or not level or not language or not word_norm:
            out["skipped_invalid"] += 1
            continue
        translation_uz = str(it.get("translation_uz") or "").strip()
        translation_ru = str(it.get("translation_ru") or "").strip()
        definition = str(it.get("definition") or "").strip()
        example = str(it.get("example") or "").strip()
        source = str(it.get("source") or "").strip()
        fetched_at = str(it.get("fetched_at") or "").strip() or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        now_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        normalized_rows.append(
            (
                subject,
                level,
                language,
                word,
                word_norm,
                translation_uz,
                translation_ru,
                definition,
                example,
                source,
                fetched_at,
                now_ts,
            )
        )
    out["total"] = len(normalized_rows)
    if not normalized_rows:
        return out

    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            # Preload existing keys for rough inserted/updated stats.
            keys_to_check: set[tuple[str, str, str, str]] = {
                (row[0], row[1], row[2], row[4]) for row in normalized_rows
            }
            existing: set[tuple[str, str, str, str]] = set()
            keys_list = list(keys_to_check)
            for chunk_start in range(0, len(keys_list), 300):
                chunk = keys_list[chunk_start : chunk_start + 300]
                if not chunk:
                    continue
                conds = " OR ".join(["(subject=? AND level=? AND language=? AND word_norm=?)"] * len(chunk))
                params: list[Any] = []
                for c in chunk:
                    params.extend([c[0], c[1], c[2], c[3]])
                cur.execute(
                    f"SELECT subject, level, language, word_norm FROM vocab_seed_pool WHERE {conds}",
                    tuple(params),
                )
                for r in cur.fetchall() or []:
                    existing_key = (
                        str(r.get("subject") or ""),
                        str(r.get("level") or ""),
                        str(r.get("language") or ""),
                        str(r.get("word_norm") or ""),
                    )
                    existing.add(existing_key)

            present_before: set[tuple[str, str, str, str]] = set(existing)
            for row in normalized_rows:
                key = (row[0], row[1], row[2], row[4])
                if key in present_before:
                    out["updated"] += 1
                else:
                    out["inserted"] += 1
                    present_before.add(key)
                cur.execute(
                    """
                    INSERT INTO vocab_seed_pool
                        (subject, level, language, word, word_norm, translation_uz, translation_ru, definition, example, source, fetched_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(subject, level, language, word_norm)
                    DO UPDATE SET
                        word=excluded.word,
                        translation_uz=excluded.translation_uz,
                        translation_ru=excluded.translation_ru,
                        definition=excluded.definition,
                        example=excluded.example,
                        source=excluded.source,
                        fetched_at=excluded.fetched_at,
                        updated_at=excluded.updated_at
                    """,
                    row,
                )
            conn.commit()
        except Exception:
            logger.exception("Failed to upsert vocab seed items")
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()
    return out


def pull_seed_candidates(
    subject: str,
    level: str,
    need_count: int,
    exclude_keys: set[str] | None = None,
) -> list[dict]:
    ensure_vocab_seed_pool_schema()
    subj = str(subject or "").strip().title()
    lvl = str(level or "").strip().upper()
    if subj not in ("English", "Russian") or not lvl or int(need_count or 0) <= 0:
        return []
    lang = "ru" if subj == "Russian" else "en"
    limit = int(need_count)
    excluded = sorted({_normalize_seed_word_key(x) for x in (exclude_keys or set()) if _normalize_seed_word_key(x)})
    conn = get_conn()
    cur = conn.cursor()
    try:
        sql = (
            "SELECT word, level, translation_uz, translation_ru, definition, example, source "
            "FROM vocab_seed_pool "
            "WHERE LOWER(TRIM(subject))=LOWER(TRIM(?)) "
            "AND UPPER(TRIM(level))=UPPER(TRIM(?)) "
            "AND LOWER(TRIM(language))=LOWER(TRIM(?))"
        )
        params: list[Any] = [subj, lvl, lang]
        if excluded:
            placeholders = ",".join(["?"] * len(excluded))
            sql += f" AND word_norm NOT IN ({placeholders})"
            params.extend(excluded)
        sql += " ORDER BY id ASC LIMIT ?"
        params.append(limit)
        cur.execute(sql, tuple(params))
        return [dict(r) for r in (cur.fetchall() or [])]
    except Exception:
        logger.exception("Failed to pull seed candidates subject=%s level=%s", subj, lvl)
        return []
    finally:
        conn.close()


def get_vocabulary_stock_by_subject_level(subject: str) -> list[dict]:
    """Vocabulary rows grouped by level for a subject."""
    subj = (subject or "").strip().title()
    if subj not in ("English", "Russian"):
        return []
    lang = "ru" if subj == "Russian" else "en"

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT UPPER(COALESCE(NULLIF(TRIM(level), ''), 'UNSET')) AS level, COUNT(*) AS c
        FROM words
        WHERE LOWER(TRIM(subject)) = LOWER(TRIM(?))
          AND LOWER(TRIM(language)) = LOWER(TRIM(?))
        GROUP BY UPPER(COALESCE(NULLIF(TRIM(level), ''), 'UNSET'))
        ORDER BY
          CASE UPPER(COALESCE(NULLIF(TRIM(level), ''), 'UNSET'))
            WHEN 'A1' THEN 1
            WHEN 'A2' THEN 2
            WHEN 'B1' THEN 3
            WHEN 'B2' THEN 4
            WHEN 'C1' THEN 5
            ELSE 99
          END,
          level ASC
        """,
        (subj, lang),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def delete_vocabulary_stock(subject: str, level: str | None = None) -> int:
    """Delete vocabulary rows from words by subject (+ optional level). Returns deleted count."""
    subj = (subject or "").strip().title()
    if subj not in ("English", "Russian"):
        return 0
    lang = "ru" if subj == "Russian" else "en"
    lvl = (level or "").strip().upper()
    delete_all = lvl in ("", "ALL", "*")

    conn = get_conn()
    cur = conn.cursor()
    try:
        if delete_all:
            cur.execute(
                """
                DELETE FROM words
                WHERE LOWER(TRIM(subject)) = LOWER(TRIM(?))
                  AND LOWER(TRIM(language)) = LOWER(TRIM(?))
                """,
                (subj, lang),
            )
        else:
            cur.execute(
                """
                DELETE FROM words
                WHERE LOWER(TRIM(subject)) = LOWER(TRIM(?))
                  AND LOWER(TRIM(language)) = LOWER(TRIM(?))
                  AND UPPER(COALESCE(NULLIF(TRIM(level), ''), 'UNSET')) = UPPER(TRIM(?))
                """,
                (subj, lang, lvl),
            )
        deleted = int(getattr(cur, "rowcount", 0) or 0)
        conn.commit()
        return max(0, deleted)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("Failed to delete vocabulary stock subject=%s level=%s", subj, lvl or "ALL")
        return 0
    finally:
        conn.close()


def get_daily_tests_stock_by_teacher(teacher_id: int, subject: str) -> dict:
    """Return remaining daily tests count per level for a specific teacher (subject-scoped)."""
    subj = (subject or "").strip().title()
    levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'MIXED']
    stock = {lvl: 0 for lvl in levels}
    total = 0

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT level, COUNT(*) as c
        FROM daily_tests_bank
        WHERE active=1 AND first_used_at IS NULL AND subject=? AND created_by=?
        GROUP BY level
        ''',
        (subj, teacher_id),
    )
    rows = cur.fetchall()
    for r in rows:
        lvl = (r["level"] or "").upper()
        if lvl in stock:
            stock[lvl] = int(r["c"])
            total += stock[lvl]
        else:
            try:
                total += int(r["c"])
            except Exception:
                pass
    # Backward-compatibility: older rows might have created_by NULL,
    # so teacher stock would incorrectly show zeros. If so, fallback to global stock.
    if total == 0:
        try:
            cur.execute(
                '''
                SELECT level, COUNT(*) as c
                FROM daily_tests_bank
                WHERE active=1 AND first_used_at IS NULL AND subject=?
                GROUP BY level
                ''',
                (subj,),
            )
            rows2 = cur.fetchall()
            stock = {lvl: 0 for lvl in levels}
            total = 0
            for r in rows2:
                lvl = (r["level"] or "").upper()
                if lvl in stock:
                    stock[lvl] = int(r["c"])
                    total += stock[lvl]
                else:
                    try:
                        total += int(r["c"])
                    except Exception:
                        pass
        except Exception:
            pass
    conn.close()
    return {"subject": subj, "stock": stock, "total": total}


def get_daily_test_reminder_candidates(test_date: str, reminder_slot: int) -> list[dict]:
    """
    Return students who:
    - haven't completed a daily test for `test_date`
    - haven't received a reminder for `reminder_slot` yet
    - have access enabled (best-effort via `is_access_active` in Python)
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT *
        FROM users u
        WHERE u.login_type IN (1, 2)
          AND COALESCE(u.blocked, 0)=0
          AND NOT EXISTS (
              SELECT 1
              FROM daily_test_attempts a
              WHERE a.user_id=u.id AND a.test_date=? AND a.status='completed'
          )
          AND NOT EXISTS (
              SELECT 1
              FROM daily_test_notifications n
              WHERE n.user_id=u.id AND n.test_date=? AND n.reminder_slot=?
          )
        ''',
        (test_date, test_date, reminder_slot),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    # Filter by access expiration in Python (keeps SQL portable)
    return [r for r in rows if is_access_active(r)]


def mark_daily_test_notification_sent(user_id: int, test_date: str, reminder_slot: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            INSERT INTO daily_test_notifications (user_id, test_date, reminder_slot)
            VALUES (?, ?, ?)
            ON CONFLICT (user_id, test_date, reminder_slot) DO NOTHING
            ''',
            (user_id, test_date, reminder_slot),
        )
        inserted = (getattr(cur, "rowcount", 0) or 0) > 0
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def count_available_daily_tests_global() -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT COUNT(*) as c
        FROM daily_tests_bank
        WHERE active=1 AND first_used_at IS NULL
        '''
    )
    row = cur.fetchone()
    conn.close()
    return int(row["c"]) if row else 0


def get_teachers_with_daily_test_permission() -> list[dict]:
    """Teachers (login_type=3) allowed to upload daily tests."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT *
        FROM users
        WHERE login_type=3
          AND COALESCE(can_upload_daily_tests, 0)=1
          AND COALESCE(blocked, 0)=0
        '''
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def mark_daily_test_stock_alert(subject: str, level: str, threshold: int) -> bool:
    """Record that we notified `threshold` remaining tests (idempotent)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            INSERT INTO daily_test_stock_alerts (subject, level, threshold)
            VALUES (?, ?, ?)
            ON CONFLICT (subject, level, threshold) DO NOTHING
            ''',
            (subject, level, threshold),
        )
        inserted = (getattr(cur, "rowcount", 0) or 0) > 0
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def cleanup_expired_daily_tests(days: int = 1) -> int:
    """
    Delete used daily-test bank questions once they are no longer today's active set.
    Student attempt history stays intact because question details are stored in attempt_items.
    Works on both PostgreSQL and SQLite.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        days_int = max(1, int(days or 1))
        if days_int <= 1:
            cur.execute(
                '''
                DELETE FROM daily_tests_bank
                WHERE first_used_at IS NOT NULL
                  AND DATE(first_used_at) < CURRENT_DATE
                '''
            )
        else:
            # PostgreSQL supports INTERVAL; SQLite uses datetime offset arithmetic.
            if _is_postgres_enabled():
                cur.execute(
                    '''
                    DELETE FROM daily_tests_bank
                    WHERE first_used_at IS NOT NULL
                      AND first_used_at < (CURRENT_TIMESTAMP - (%s * INTERVAL '1 day'))
                    ''',
                    (days_int,),
                )
            else:
                cur.execute(
                    '''
                    DELETE FROM daily_tests_bank
                    WHERE first_used_at IS NOT NULL
                      AND first_used_at < datetime('now', ? || ' days')
                    ''',
                    (f"-{days_int}",),
                )
        deleted = getattr(cur, "rowcount", 0) or 0
        conn.commit()
        return int(deleted)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("cleanup_expired_daily_tests failed")
        return 0
    finally:
        conn.close()


_DAILY_BANK_LEVEL_ORDER = [
    "BEGINNER",
    "ELEMENTARY",
    "PRE-INTERMEDIATE",
    "INTERMEDIATE",
    "UPPER-INTERMEDIATE",
    "ADVANCED",
]

# Older imported daily-test rows use CEFR codes, while current placement and
# group records use descriptive tiers. They represent the same difficulty and
# must be considered together — especially BEGINNER/A1, otherwise a student
# can be told the bank is empty even when there are plenty of A1 questions.
_DAILY_BANK_LEVEL_ALIASES = {
    "BEGINNER": ("BEGINNER", "A1"),
    "ELEMENTARY": ("ELEMENTARY", "A2"),
    "PRE-INTERMEDIATE": ("PRE-INTERMEDIATE", "B1"),
    "INTERMEDIATE": ("INTERMEDIATE", "B2"),
    "UPPER-INTERMEDIATE": ("UPPER-INTERMEDIATE", "B2"),
    "ADVANCED": ("ADVANCED", "C1"),
}

_DAILY_BANK_CANONICAL_LEVELS = {
    "A1": "BEGINNER",
    "A2": "ELEMENTARY",
    "B1": "PRE-INTERMEDIATE",
    "B2": "UPPER-INTERMEDIATE",
    "C1": "ADVANCED",
}


def _daily_bank_level_candidates(level: str) -> list[str]:
    """Exact tier/CEFR alias first, then nearest tiers by rank distance.

    Example: BEGINNER checks BEGINNER then A1 before borrowing ELEMENTARY/A2.
    This protects level quality but prevents a thin bank from hard-blocking a
    daily test. Ties intentionally prefer the easier tier.
    """
    requested = (level or "").strip().upper()
    lvl = _DAILY_BANK_CANONICAL_LEVELS.get(requested, requested)
    if lvl not in _DAILY_BANK_LEVEL_ORDER:
        tier_candidates = [requested] + [t for t in _DAILY_BANK_LEVEL_ORDER if t != requested]
    else:
        idx = _DAILY_BANK_LEVEL_ORDER.index(lvl)
        tier_candidates = [lvl]
        for dist in range(1, len(_DAILY_BANK_LEVEL_ORDER)):
            for cand in (
                idx - dist >= 0 and _DAILY_BANK_LEVEL_ORDER[idx - dist],
                idx + dist < len(_DAILY_BANK_LEVEL_ORDER) and _DAILY_BANK_LEVEL_ORDER[idx + dist],
            ):
                if cand and cand not in tier_candidates:
                    tier_candidates.append(cand)

    candidates: list[str] = []
    for tier in tier_candidates:
        for candidate in _DAILY_BANK_LEVEL_ALIASES.get(tier, (tier,)):
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def _pick_unused_daily_test_bank_rows(
    cur,
    subject: str,
    level: str,
    test_date: str,
    total_questions: int,
) -> list:
    """
    Pick unused (first_used_at IS NULL) rows from daily_tests_bank using the daily type plan.
    Returns list of row mappings (same shape as before).
    """
    subj = (subject or "").strip().title()
    lvl = (level or "").strip().upper()
    plan = ensure_daily_test_type_plan(
        subject=subj, test_date=test_date, total_questions=total_questions
    )
    allowed_bank_types = {
        "grammar_rules",
        "grammar_sentence",
        "find_mistake",
        "error_spotting",
        "multiple_choice",
    }
    rich_types = [
        "grammar_rules",
        "grammar_sentence",
        "find_mistake",
        "error_spotting",
    ]
    base_counts = {
        "grammar_rules": int(plan.get("grammar_rules_count", 0)),
        "grammar_sentence": int(plan.get("grammar_sentence_count", 0)),
        "find_mistake": int(plan.get("find_mistake_count", 0)),
        "error_spotting": int(plan.get("error_spotting_count", 0)),
    }
    overflow = sum(base_counts.values()) - int(total_questions)
    trim_order = ["grammar_sentence", "grammar_rules", "find_mistake", "error_spotting"]
    ti = 0
    while overflow > 0 and trim_order:
        key = trim_order[ti % len(trim_order)]
        if base_counts.get(key, 0) > 1:
            base_counts[key] -= 1
            overflow -= 1
        ti += 1
        if ti > 100:
            break
    type_counts = [(qt, int(base_counts.get(qt, 0))) for qt in rich_types]

    bank_rows = []
    bank_ids: list[int] = []

    for qt, qt_need in type_counts:
        if qt_need <= 0:
            continue
        cur.execute(
            '''
            SELECT id, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json
            FROM daily_tests_bank
            WHERE active=1
              AND first_used_at IS NULL
              AND subject=? AND level=?
              AND question_type=?
            ORDER BY RANDOM()
            LIMIT ?
            ''',
            (subj, lvl, qt, qt_need),
        )
        rows = cur.fetchall()
        for r in rows:
            bid = int(r["id"])
            if bid in bank_ids:
                continue
            bank_rows.append(r)
            bank_ids.append(bid)
            if len(bank_rows) >= total_questions:
                break
        if len(bank_rows) >= total_questions:
            break

    missing = total_questions - len(bank_rows)
    if missing > 0:
        try:
            if bank_ids:
                placeholders = ",".join(["?"] * len(bank_ids))
                q_any = f'''
                    SELECT id, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json
                    FROM daily_tests_bank
                    WHERE active=1 AND first_used_at IS NULL
                      AND subject=? AND level=?
                      AND COALESCE(question_type, 'multiple_choice') IN ({",".join(["?"] * len(allowed_bank_types))})
                      AND id NOT IN ({placeholders})
                    ORDER BY RANDOM()
                    LIMIT ?
                '''
                cur.execute(q_any, tuple([subj, lvl] + sorted(allowed_bank_types) + bank_ids + [missing]))
            else:
                cur.execute(
                    '''
                    SELECT id, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json
                    FROM daily_tests_bank
                    WHERE active=1 AND first_used_at IS NULL
                      AND subject=? AND level=?
                      AND COALESCE(question_type, 'multiple_choice') IN (?, ?, ?, ?, ?)
                    ORDER BY RANDOM()
                    LIMIT ?
                    ''',
                    (subj, lvl, *sorted(allowed_bank_types), missing),
                )
            rows2 = cur.fetchall()
            for r in rows2:
                bid = int(r["id"])
                if bid in bank_ids:
                    continue
                bank_rows.append(r)
                bank_ids.append(bid)
                if len(bank_rows) >= total_questions:
                    break
        except Exception:
            try:
                cur.connection.rollback()
            except Exception:
                pass

    # Thin-bank fallback: fill any remainder from the nearest tiers of the
    # same subject so a sparse level (Russian PRE-INTERMEDIATE: 15 rows)
    # never blocks the daily test from starting.
    for fb_lvl in _daily_bank_level_candidates(lvl):
        if fb_lvl == lvl:
            continue
        missing = total_questions - len(bank_rows)
        if missing <= 0:
            break
        try:
            if bank_ids:
                placeholders = ",".join(["?"] * len(bank_ids))
                cur.execute(
                    f'''
                    SELECT id, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json
                    FROM daily_tests_bank
                    WHERE active=1 AND first_used_at IS NULL
                      AND subject=? AND level=?
                      AND COALESCE(question_type, 'multiple_choice') IN ({",".join(["?"] * len(allowed_bank_types))})
                      AND id NOT IN ({placeholders})
                    ORDER BY Random()
                    LIMIT ?
                    ''',
                    tuple([subj, fb_lvl] + sorted(allowed_bank_types) + bank_ids + [missing]),
                )
            else:
                cur.execute(
                    '''
                    SELECT id, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json
                    FROM daily_tests_bank
                    WHERE active=1 AND first_used_at IS NULL
                      AND subject=? AND level=?
                      AND COALESCE(question_type, 'multiple_choice') IN (?, ?, ?, ?, ?)
                    ORDER BY Random()
                    LIMIT ?
                    ''',
                    (subj, fb_lvl, *sorted(allowed_bank_types), missing),
                )
            for r in cur.fetchall():
                bid = int(r["id"])
                if bid in bank_ids:
                    continue
                bank_rows.append(r)
                bank_ids.append(bid)
                if len(bank_rows) >= total_questions:
                    break
        except Exception:
            try:
                cur.connection.rollback()
            except Exception:
                pass

    return bank_rows


def _ordered_daily_test_bank_rows(cur, bank_ids: list[int]) -> list:
    """Load bank rows in the same order as bank_ids; all must exist and be active."""
    if not bank_ids:
        return []
    allowed_bank_types = {
        "grammar_rules",
        "grammar_sentence",
        "find_mistake",
        "error_spotting",
        "multiple_choice",
    }
    placeholders = ",".join(["?"] * len(bank_ids))
    cur.execute(
        f'''
        SELECT id, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json
        FROM daily_tests_bank
        WHERE active=1
          AND COALESCE(question_type, 'multiple_choice') IN (?, ?, ?, ?, ?)
          AND id IN ({placeholders})
        ''',
        tuple(sorted(allowed_bank_types) + bank_ids),
    )
    by_id = {int(r["id"]): r for r in cur.fetchall()}
    out = []
    for bid in bank_ids:
        r = by_id.get(int(bid))
        if r is None:
            return []
        out.append(r)
    return out


def ensure_daily_test_attempt_and_items(
    user_id: int,
    subject: str,
    level: str,
    test_date: str,
    *,
    total_questions: int = 10,
) -> tuple[int, str]:
    """
    Ensure the daily test attempt for (user_id, test_date) exists,
    and the daily_test_attempt_items rows are created/reserved.

    On PostgreSQL, all students share the same question IDs for (test_date, subject, level).

    Returns: (attempt_id, status)
    """
    import json

    from auth import level_for_daily_tests_bank

    subj = (subject or "").strip().title()
    lvl = level_for_daily_tests_bank(subj, level)

    with DB_WRITE_LOCK:
        # Some DBs may miss `daily_test_day_question_sets` until the first daily flow runs.
        # Guard the schema here to prevent "relation ... does not exist" crashes.
        ensure_daily_tests_schema()
        conn = get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, status FROM daily_test_attempts WHERE user_id=? AND test_date=? AND subject=?",
            (user_id, test_date, subj),
        )
        row = cur.fetchone()
        if row:
            attempt_id = int(row["id"])
            status = row["status"]
        else:
            cur.execute(
                '''
                INSERT INTO daily_test_attempts (user_id, subject, level, test_date, total_questions)
                VALUES (?, ?, ?, ?, ?)
                RETURNING id
                ''',
                (user_id, subj, lvl, test_date, total_questions),
            )
            attempt_id = int(cur.fetchone()["id"])
            status = "in_progress"

        cur.execute(
            "SELECT COUNT(*) as c FROM daily_test_attempt_items WHERE attempt_id=?",
            (attempt_id,),
        )
        items_count = cur.fetchone()["c"] or 0
        if items_count >= total_questions:
            conn.close()
            return attempt_id, status

        bank_rows = []
        bank_ids: list[int] = []

        if _is_postgres_enabled():
            try:
                cur.execute(
                    """
                    SELECT bank_ids_json FROM daily_test_day_question_sets
                    WHERE test_date=? AND subject=? AND level=?
                    """,
                    (test_date, subj, lvl),
                )
                day_row = cur.fetchone()
            except Exception as e:
                # Extra safety: if shared day-set table is still missing or migration failed,
                # behave as if there is no precomputed row and let the allocation branch below
                # create both the table row and the question set instead of crashing.
                msg = str(e)
                if "daily_test_day_question_sets" in msg and "does not exist" in msg.lower():
                    # PostgreSQL transaction is aborted after failed statement.
                    # Reset tx state so later queries (pick/insert) can proceed.
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    cur = conn.cursor()
                    day_row = None
                else:
                    conn.close()
                    raise

            if day_row and day_row.get("bank_ids_json"):
                try:
                    bank_ids = [int(x) for x in json.loads(day_row["bank_ids_json"])]
                except Exception:
                    bank_ids = []
                if bank_ids:
                    bank_rows = _ordered_daily_test_bank_rows(cur, bank_ids)
                    if len(bank_rows) != len(bank_ids):
                        cur.execute(
                            """
                            DELETE FROM daily_test_day_question_sets
                            WHERE test_date=? AND subject=? AND level=?
                            """,
                            (test_date, subj, lvl),
                        )
                        bank_rows = []
                        bank_ids = []
                    bank_ids = [int(r["id"]) for r in bank_rows]
                    if len(bank_rows) > total_questions:
                        bank_rows = bank_rows[:total_questions]
                        bank_ids = [int(r["id"]) for r in bank_rows]

            if not bank_rows:
                for _attempt in range(4):
                    picked = _pick_unused_daily_test_bank_rows(
                        cur, subj, lvl, test_date, total_questions
                    )
                    if len(picked) < total_questions:
                        conn.close()
                        raise ValueError(
                            f"Not enough daily tests in bank. Need {total_questions}, have {len(picked)}."
                        )
                    bank_ids_new = [int(r["id"]) for r in picked]
                    payload = json.dumps(bank_ids_new, ensure_ascii=False)
                    try:
                        cur.execute(
                            """
                            INSERT INTO daily_test_day_question_sets
                                (test_date, subject, level, total_questions, bank_ids_json)
                            VALUES (?, ?, ?, ?, ?)
                            ON CONFLICT (test_date, subject, level) DO NOTHING
                            RETURNING id
                            """,
                            (test_date, subj, lvl, total_questions, payload),
                        )
                    except Exception as e:
                        msg = str(e).lower()
                        if "daily_test_day_question_sets" in msg and "does not exist" in msg:
                            try:
                                conn.rollback()
                            except Exception:
                                pass
                            # Recreate missing schema and retry once.
                            ensure_daily_tests_schema()
                            cur = conn.cursor()
                            cur.execute(
                                """
                                INSERT INTO daily_test_day_question_sets
                                    (test_date, subject, level, total_questions, bank_ids_json)
                                VALUES (?, ?, ?, ?, ?)
                                ON CONFLICT (test_date, subject, level) DO NOTHING
                                RETURNING id
                                """,
                                (test_date, subj, lvl, total_questions, payload),
                            )
                        else:
                            conn.close()
                            raise
                    ins = cur.fetchone()
                    if ins:
                        ph = ",".join(["?"] * len(bank_ids_new))
                        cur.execute(
                            f'''
                            UPDATE daily_tests_bank
                            SET first_used_at=CURRENT_TIMESTAMP
                            WHERE id IN ({ph})
                            ''',
                            tuple(bank_ids_new),
                        )
                        bank_rows = picked
                        bank_ids = bank_ids_new
                        break
                    cur.execute(
                        """
                        SELECT bank_ids_json FROM daily_test_day_question_sets
                        WHERE test_date=? AND subject=? AND level=?
                        """,
                        (test_date, subj, lvl),
                    )
                    dr = cur.fetchone()
                    if dr and dr.get("bank_ids_json"):
                        try:
                            bank_ids = [int(x) for x in json.loads(dr["bank_ids_json"])]
                        except Exception:
                            bank_ids = []
                        if bank_ids:
                            bank_rows = _ordered_daily_test_bank_rows(cur, bank_ids)
                            if len(bank_rows) == len(bank_ids):
                                if len(bank_rows) > total_questions:
                                    bank_rows = bank_rows[:total_questions]
                                    bank_ids = [int(r["id"]) for r in bank_rows]
                                break
                            cur.execute(
                                """
                                DELETE FROM daily_test_day_question_sets
                                WHERE test_date=? AND subject=? AND level=?
                                """,
                                (test_date, subj, lvl),
                            )
                            bank_rows = []
                            bank_ids = []
                else:
                    conn.close()
                    raise ValueError(
                        "Could not allocate shared daily test set (concurrency). Try again."
                    )
        else:
            bank_rows = _pick_unused_daily_test_bank_rows(
                cur, subj, lvl, test_date, total_questions
            )
            if len(bank_rows) < total_questions:
                conn.close()
                raise ValueError(
                    f"Not enough daily tests in bank. Need {total_questions}, have {len(bank_rows)}."
                )
            bank_ids = [int(r["id"]) for r in bank_rows]
            placeholders = ",".join(["?"] * len(bank_ids))
            cur.execute(
                f'''
                UPDATE daily_tests_bank
                SET first_used_at=CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                ''',
                tuple(bank_ids),
            )

        # Insert usage tracking per-user (no-repeat safety + audit)
        usage_rows = [(user_id, bid) for bid in bank_ids]
        try:
            cur.executemany(
                '''
                INSERT INTO daily_test_usage (user_id, bank_test_id)
                VALUES (?, ?)
                ON CONFLICT (user_id, bank_test_id) DO NOTHING
                ''',
                usage_rows,
            )
        except Exception:
            pass

        items = []
        for idx, r in enumerate(bank_rows, start=1):
            options = [r["option_a"], r["option_b"], r["option_c"], r["option_d"]]
            options_json = json.dumps(options, ensure_ascii=False)
            items.append(
                (
                    attempt_id,
                    int(r["id"]),
                    idx,
                    r["question"],
                    options_json,
                    r.get("payload_json"),
                )
            )

        cur.execute("DELETE FROM daily_test_attempt_items WHERE attempt_id=?", (attempt_id,))
        cur.executemany(
            '''
            INSERT INTO daily_test_attempt_items
            (attempt_id, bank_test_id, question_index, question, options_json, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            items,
        )

        cur.execute(
            "UPDATE daily_test_attempts SET status='in_progress' WHERE id=?",
            (attempt_id,),
        )

        conn.commit()
        conn.close()
        return attempt_id, "in_progress"


def get_daily_test_attempt_items(attempt_id: int) -> list[dict]:
    import json

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT
            iti.id as attempt_item_id,
            iti.question_index,
            iti.question,
            iti.options_json,
            COALESCE(iti.payload_json, dtb.payload_json) AS payload_json,
            iti.selected_option,
            iti.is_correct,
            iti.answered_at,
            iti.timed_out,
            iti.bank_test_id,
            dtb.subject,
            dtb.correct_option_index,
            dtb.question_type
        FROM daily_test_attempt_items iti
        JOIN daily_tests_bank dtb ON dtb.id = iti.bank_test_id
        WHERE iti.attempt_id=?
        ORDER BY iti.question_index
        ''',
        (attempt_id,),
    )
    rows = cur.fetchall()
    conn.close()
    # Keep options_json as-is; student bot will parse, but we normalize selected fields.
    return [dict(r) for r in rows]


def mark_daily_test_question_answered(
    attempt_id: int,
    question_index: int,
    selected_option: str,
    is_correct: bool,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        UPDATE daily_test_attempt_items
        SET selected_option=?, is_correct=?, answered_at=CURRENT_TIMESTAMP, timed_out=0
        WHERE attempt_id=? AND question_index=?
        ''',
        (selected_option, 1 if is_correct else 0, attempt_id, question_index),
    )
    conn.commit()
    conn.close()


def mark_daily_test_question_timed_out(attempt_id: int, question_index: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        UPDATE daily_test_attempt_items
        SET timed_out=1
        WHERE attempt_id=? AND question_index=? AND selected_option IS NULL
        ''',
        (attempt_id, question_index),
    )
    conn.commit()
    conn.close()


def finish_daily_test_attempt(
    attempt_id: int,
    correct: int,
    wrong: int,
    unanswered: int,
    net_dcoins: float,
    net_dpoints: float | None = None,
) -> None:
    points_value = float(net_dpoints) if net_dpoints is not None else float(net_dcoins)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        UPDATE daily_test_attempts
        SET
            finished_at=CURRENT_TIMESTAMP,
            status='completed',
            correct=?, wrong=?, unanswered=?,
            net_dcoins=?,
            net_dpoints=?,
            current_question_index=?
        WHERE id=?
        ''',
        (correct, wrong, unanswered, float(net_dcoins), points_value, correct + wrong + unanswered, attempt_id),
    )
    conn.commit()
    conn.close()


def mark_daily_test_attempt_failed(attempt_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE daily_test_attempts
            SET
                finished_at=COALESCE(finished_at, CURRENT_TIMESTAMP),
                status='failed'
            WHERE id=? AND COALESCE(status, 'in_progress') <> 'completed'
            """,
            (int(attempt_id),),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_daily_test_attempt_history(user_id: int, limit: int = 14) -> list[dict]:
    """Daily tests attempt history for a single student (most recent first)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT
            test_date,
            subject,
            level,
            started_at,
            finished_at,
            status,
            total_questions,
            correct,
            wrong,
            unanswered,
            net_dcoins,
            COALESCE(net_dpoints, net_dcoins) AS net_dpoints
        FROM daily_test_attempts
        WHERE user_id=?
        ORDER BY test_date DESC
        LIMIT ?
        ''',
        (user_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_test_history_global(days: int = 14) -> list[dict]:
    """Daily tests history aggregated globally (most recent days first)."""
    tz = pytz.timezone("Asia/Tashkent")
    from datetime import timedelta
    start_date = (datetime.now(tz).date() - timedelta(days=days)).isoformat()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT
            test_date,
            COUNT(*) as completed_attempts,
            COALESCE(SUM(correct),0) as correct_total,
            COALESCE(SUM(wrong),0) as wrong_total,
            COALESCE(SUM(unanswered),0) as unanswered_total,
            COALESCE(AVG(net_dcoins),0) as avg_net_dcoins,
            COALESCE(AVG(COALESCE(net_dpoints, net_dcoins)),0) as avg_net_dpoints
        FROM daily_test_attempts
        WHERE status='completed'
          AND test_date >= ?
        GROUP BY test_date
        ORDER BY test_date DESC
        LIMIT ?
        ''',
        (start_date, days),
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_daily_test_history_for_teacher(teacher_id: int, days: int = 14) -> list[dict]:
    """
    Daily tests history for a teacher's students, newest first.
    Teacher scope = all students from all groups created/owned by this teacher.
    """
    tz = pytz.timezone("Asia/Tashkent")
    from datetime import timedelta
    start_date = (datetime.now(tz).date() - timedelta(days=days)).isoformat()

    groups = get_groups_by_teacher(teacher_id) or []
    user_ids: set[int] = set()
    for g in groups:
        for u in get_group_users(g["id"]):
            if u.get("login_type") in (1, 2, 6):
                user_ids.add(u["id"])

    if not user_ids:
        return []

    placeholders = ",".join(["?"] * len(user_ids))
    row_limit = max(120, min(800, int(days) * max(8, len(user_ids))))
    params: list[Any] = [start_date, *list(user_ids), row_limit]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f'''
        SELECT
            a.id,
            a.user_id,
            a.subject,
            a.level,
            a.test_date,
            a.finished_at,
            1 as completed_attempts,
            COALESCE(a.correct,0) as correct_count,
            COALESCE(a.correct,0) as correct_total,
            COALESCE(a.wrong,0) as wrong_count,
            COALESCE(a.wrong,0) as wrong_total,
            COALESCE(a.unanswered,0) as unanswered_count,
            COALESCE(a.unanswered,0) as unanswered_total,
            COALESCE(a.net_dcoins,0) as net_dcoins,
            COALESCE(a.net_dcoins,0) as avg_net_dcoins,
            COALESCE(a.net_dpoints, a.net_dcoins, 0) as net_dpoints,
            COALESCE(a.net_dpoints, a.net_dcoins, 0) as avg_net_dpoints,
            u.first_name,
            u.last_name,
            u.login_id,
            u.phone
        FROM daily_test_attempts a
        LEFT JOIN users u ON u.id=a.user_id
        WHERE a.status='completed'
          AND a.test_date >= ?
          AND a.user_id IN ({placeholders})
        ORDER BY a.test_date DESC, a.finished_at DESC, a.id DESC
        LIMIT ?
        ''',
        tuple(params),
    )
    rows = cur.fetchall()
    conn.close()
    items: list[dict] = []
    for row in rows:
        item = _row_to_dict(row)
        full_name = " ".join(
            part
            for part in [str(item.get("first_name") or "").strip(), str(item.get("last_name") or "").strip()]
            if part
        ).strip()
        item["student_id"] = int(item.get("user_id") or 0)
        item["student_name"] = full_name or str(item.get("login_id") or item.get("phone") or f"Student #{item['student_id']}")
        items.append(item)
    return items


def apply_migrations():
    """Yangi ustunlarni qo'shish uchun migratsiyani ishga tushirish"""
    conn = get_conn()
    cur = conn.cursor()
    
    # pending_approval ustunini qo'shish
    try:
        cur.execute("ALTER TABLE users ADD COLUMN pending_approval INTEGER DEFAULT 0")
        logger.info("Migrasiya: pending_approval ustuni qo'shildi")
    except Exception:
        pass
    
    # group_id ustunini qo'shish
    try:
        cur.execute("ALTER TABLE users ADD COLUMN group_id INTEGER")
        logger.info("Migrasiya: group_id ustuni qo'shildi")
    except Exception:
        pass  # Agar ustun allaqachon bor bo'lsa, xato chiqmaydi
    
    # diamonds ustunini qo'shish
    try:
        cur.execute("ALTER TABLE users ADD COLUMN diamonds INTEGER DEFAULT 0")
        logger.info("Migrasiya: diamonds ustuni qo'shildi")
    except Exception:
        pass
    
    # last_diamond_update ustunini qo'shish
    try:
        cur.execute("ALTER TABLE users ADD COLUMN last_diamond_update TEXT")
        logger.info("Migrasiya: last_diamond_update ustuni qo'shildi")
    except Exception:
        pass

def ensure_video_teachers_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS teacher_id BIGINT")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    try:
        cur.execute("ALTER TABLE videos ADD COLUMN IF NOT EXISTS support_teacher_ids TEXT")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # language ustunini qo'shish (foydalanuvchi tilini saqlash uchun)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'uz'")
        logger.info("Migrasiya: language ustuni qo'shildi")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    # public_offer_agreed ustunini qo'shish
    try:
        cur.execute("ALTER TABLE users ADD COLUMN public_offer_agreed INTEGER DEFAULT 0")
        logger.info("Migrasiya: public_offer_agreed ustuni qo'shildi")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    
    # diamond_history table for tracking D'coin changes
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS diamond_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                dcoin_change DOUBLE PRECISION NOT NULL,
                dpoints_change DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                subject TEXT,
                change_type TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        logger.info("Migrasiya: diamond_history table created")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_dpoints (
                user_id BIGINT PRIMARY KEY,
                dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vocab_word_mastery (
                user_id BIGINT NOT NULL,
                word_id BIGINT NOT NULL,
                question_type TEXT NOT NULL,
                consecutive_correct INTEGER NOT NULL DEFAULT 0,
                cooldown_until TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, word_id, question_type),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (word_id) REFERENCES words (id)
            )
        """)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    
    # feedback table for anonymous student feedback
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                feedback_text TEXT NOT NULL,
                is_anonymous INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        logger.info("Migrasiya: feedback table created")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    
    # test_history table for tracking test statistics
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS test_history (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                topic_id TEXT,
                correct_count INTEGER DEFAULT 0,
                wrong_count INTEGER DEFAULT 0,
                skipped_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        logger.info("Migrasiya: test_history table created")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    # test_history schema alignment for old DBs
    for col, ddl in (
        ("topic_id", "ALTER TABLE test_history ADD COLUMN topic_id TEXT"),
        ("correct_count", "ALTER TABLE test_history ADD COLUMN correct_count INTEGER DEFAULT 0"),
        ("wrong_count", "ALTER TABLE test_history ADD COLUMN wrong_count INTEGER DEFAULT 0"),
        ("skipped_count", "ALTER TABLE test_history ADD COLUMN skipped_count INTEGER DEFAULT 0"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: test_history.{col} ustuni qo'shildi")
        except Exception:
            # psycopg: after an error, the connection becomes "aborted" until rollback.
            # Do rollback + refresh cursor so remaining ALTER TABLE statements can continue.
            try:
                conn.rollback()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
            try:
                cur = conn.cursor()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
            continue

    # Backfill from legacy column names if present and new values are empty.
    try:
        cur.execute(
            """
            UPDATE test_history
            SET correct_count = COALESCE(correct_count, 0) + COALESCE(correct_answers, 0)
            WHERE COALESCE(correct_answers, 0) <> 0
            """
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        cur.execute(
            """
            UPDATE test_history
            SET wrong_count = COALESCE(wrong_count, 0) + COALESCE(wrong_answers, 0)
            WHERE COALESCE(wrong_answers, 0) <> 0
            """
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        cur.execute(
            """
            UPDATE test_history
            SET skipped_count = COALESCE(skipped_count, 0) + COALESCE(skipped_answers, 0)
            WHERE COALESCE(skipped_answers, 0) <> 0
            """
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    
    # persistent login tracking
    for col, ddl in (
        ("parent_phone", "ALTER TABLE users ADD COLUMN parent_phone TEXT"),
        ("logged_in", "ALTER TABLE users ADD COLUMN logged_in INTEGER DEFAULT 0"),
        ("last_login_at", "ALTER TABLE users ADD COLUMN last_login_at TEXT"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: users.{col} ustuni qo'shildi")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # groups schedule columns
    for col, ddl in (
        ("subject", "ALTER TABLE groups ADD COLUMN subject TEXT"),
        ("lesson_date", "ALTER TABLE groups ADD COLUMN lesson_date TEXT"),
        ("lesson_start", "ALTER TABLE groups ADD COLUMN lesson_start TEXT"),
        ("lesson_end", "ALTER TABLE groups ADD COLUMN lesson_end TEXT"),
        ("tz", "ALTER TABLE groups ADD COLUMN tz TEXT DEFAULT 'Asia/Tashkent'"),
        # Guruh o'quv tili: 'uz' (default) yoki 'ru' (yevro/rus guruh — ruscha tarjima)
        ("lang", "ALTER TABLE groups ADD COLUMN lang TEXT DEFAULT 'uz'"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: groups.{col} ustuni qo'shildi")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # owner_admin_id columns (limited admins only see/manage their own students/groups)
    for col, ddl in (
        ("owner_admin_id", "ALTER TABLE users ADD COLUMN owner_admin_id INTEGER"),
        ("owner_admin_id", "ALTER TABLE groups ADD COLUMN owner_admin_id INTEGER"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: {ddl.split(' ')[2]}.{col} ustuni qo'shildi")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # monthly_payments table columns for per-group payment support
    for col, ddl in (
        ("group_id", "ALTER TABLE monthly_payments ADD COLUMN group_id INTEGER"),
        ("subject", "ALTER TABLE monthly_payments ADD COLUMN subject TEXT"),
        ("payment_dcoin_amount", "ALTER TABLE monthly_payments ADD COLUMN payment_dcoin_amount DOUBLE PRECISION"),
        ("paid_by_admin_id", "ALTER TABLE monthly_payments ADD COLUMN paid_by_admin_id BIGINT"),
        ("paid_by_admin_name", "ALTER TABLE monthly_payments ADD COLUMN paid_by_admin_name TEXT"),
        ("payment_type", "ALTER TABLE monthly_payments ADD COLUMN payment_type TEXT"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: monthly_payments.{col} ustuni qo'shildi")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    try:
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_monthly_payments_user_ym_group ON monthly_payments(user_id, ym, group_id)')
        logger.info("Migrasiya: ux_monthly_payments_user_ym_group indeksi qo'shildi")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    try:
        cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_monthly_payments_user_ym ON monthly_payments(user_id, ym)')
        logger.info("Migrasiya: ux_monthly_payments_user_ym indeksi qo'shildi")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    try:
        # attendance sessions table
        cur.execute('''
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id BIGSERIAL PRIMARY KEY,
            group_id BIGINT NOT NULL,
            date TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'open',
            opened_by TEXT,
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            notified_admin INTEGER DEFAULT 0,
            notified_teacher INTEGER DEFAULT 0,
            UNIQUE(group_id, date),
            FOREIGN KEY(group_id) REFERENCES groups(id)
        )
        ''')
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    # overdue_penalty_log schema alignment for old DBs
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS overdue_penalty_log (
            user_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL,
            ym TEXT NOT NULL,
            penalty_date TEXT NOT NULL
        )
        ''')
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    for col, ddl in (
        ("group_id", "ALTER TABLE overdue_penalty_log ADD COLUMN group_id BIGINT"),
        ("penalty_date", "ALTER TABLE overdue_penalty_log ADD COLUMN penalty_date TEXT"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: overdue_penalty_log.{col} ustuni qo'shildi")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    try:
        cur.execute(
            "UPDATE overdue_penalty_log SET penalty_date = COALESCE(penalty_date, CURRENT_DATE::text)"
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        cur.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_overdue_penalty_log_uniq ON overdue_penalty_log(user_id, group_id, ym, penalty_date)"
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    # attendance_sessions: add separate pre/post notification flags
    for col, ddl in (
        ("notified_admin_pre", "ALTER TABLE attendance_sessions ADD COLUMN notified_admin_pre INTEGER DEFAULT 0"),
        ("notified_admin_post", "ALTER TABLE attendance_sessions ADD COLUMN notified_admin_post INTEGER DEFAULT 0"),
        ("notified_teacher_pre", "ALTER TABLE attendance_sessions ADD COLUMN notified_teacher_pre INTEGER DEFAULT 0"),
        ("notified_teacher_post", "ALTER TABLE attendance_sessions ADD COLUMN notified_teacher_post INTEGER DEFAULT 0"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: attendance_sessions.{col} ustuni qo'shildi")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # Store last attendance panel message ids so admin/teacher bots can sync edits.
    for col, ddl in (
        ("admin_panel_chat_id", "ALTER TABLE attendance_sessions ADD COLUMN admin_panel_chat_id INTEGER"),
        ("admin_panel_message_id", "ALTER TABLE attendance_sessions ADD COLUMN admin_panel_message_id INTEGER"),
        ("teacher_panel_chat_id", "ALTER TABLE attendance_sessions ADD COLUMN teacher_panel_chat_id INTEGER"),
        ("teacher_panel_message_id", "ALTER TABLE attendance_sessions ADD COLUMN teacher_panel_message_id INTEGER"),
    ):
        try:
            cur.execute(ddl)
            logger.info(f"Migrasiya: attendance_sessions.{col} ustuni qo'shildi")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

    # Backfill new post flags from legacy notified_* so we don't re-notify old sessions
    try:
        cur.execute(
            "UPDATE attendance_sessions SET notified_admin_post=1 WHERE notified_admin=1 AND COALESCE(notified_admin_post,0)=0"
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    try:
        cur.execute(
            "UPDATE attendance_sessions SET notified_teacher_post=1 WHERE notified_teacher=1 AND COALESCE(notified_teacher_post,0)=0"
        )
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    # bot runtime start timestamp (used to limit month navigation/scheduling)
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS bot_runtime_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            started_at TEXT NOT NULL
        )
        ''')
        cur.execute('''
        INSERT INTO bot_runtime_state (id, started_at)
        VALUES (1, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO NOTHING
        ''')
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    
    conn.commit()
    conn.close()


def ensure_monthly_payments_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS monthly_payments (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        ym TEXT NOT NULL, -- YYYY-MM
        group_id BIGINT,
        subject TEXT,
        paid INTEGER DEFAULT 0,
        paid_at TIMESTAMP,
        notified_days TEXT, -- comma-separated days e.g. "1,5,15"
        payment_dcoin_amount DOUBLE PRECISION,
        paid_by_admin_id BIGINT,
        paid_by_admin_name TEXT,
        payment_type TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(group_id) REFERENCES groups(id)
    )
    ''')
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_monthly_payments_user_ym_group ON monthly_payments(user_id, ym, group_id)')
    try:
        cur.execute("ALTER TABLE monthly_payments ADD COLUMN payment_dcoin_amount DOUBLE PRECISION")
    except Exception:
        pass
    for alter_sql in (
        "ALTER TABLE monthly_payments ADD COLUMN paid_by_admin_id BIGINT",
        "ALTER TABLE monthly_payments ADD COLUMN paid_by_admin_name TEXT",
        "ALTER TABLE monthly_payments ADD COLUMN payment_type TEXT",
    ):
        try:
            cur.execute(alter_sql)
        except Exception:
            pass
    # IMPORTANT:
    # We need per-group payment tracking, so UNIQUE(user_id, ym) must NOT exist.
    # Older migrations may have created it, causing IntegrityError on pay_set.
    try:
        cur.execute('DROP INDEX IF EXISTS ux_monthly_payments_user_ym')
    except Exception:
        pass
    conn.commit()
    conn.close()


def set_bot_started_at_now():
    """Update bot started_at timestamp on every bot startup."""
    ensure_bot_runtime_state_table()
    import pytz
    tz = pytz.timezone("Asia/Tashkent")
    now = datetime.now(tz)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE bot_runtime_state SET started_at=%s WHERE id=1", (now,))
    conn.commit()
    conn.close()


def ensure_bot_runtime_state_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS bot_runtime_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            started_at TIMESTAMP NOT NULL
        )
    ''')
    cur.execute('''
        INSERT INTO bot_runtime_state (id, started_at)
        VALUES (1, CURRENT_TIMESTAMP)
        ON CONFLICT (id) DO NOTHING
    ''')
    conn.commit()
    conn.close()


def get_bot_started_at() -> str | None:
    ensure_bot_runtime_state_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT started_at FROM bot_runtime_state WHERE id=1")
    row = cur.fetchone()
    conn.close()
    return row["started_at"] if row else None


def get_bot_start_ym() -> str:
    """
    Return bot started month (YYYY-MM) to limit payment month navigation and penalties.
    """
    started_at = get_bot_started_at()
    if not started_at:
        # Fallback to current Uzbekistan month
        tz = pytz.timezone("Asia/Tashkent")
        return datetime.now(tz).strftime("%Y-%m")
    # started_at format: YYYY-MM-DD HH:MM:SS
    return str(started_at)[:7]


def ensure_overdue_penalty_log_table():
    """Track daily -2 D'coin penalty for overdue payments (one row per user,group,ym,date)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS overdue_penalty_log (
            user_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL,
            ym TEXT NOT NULL,
            penalty_date TIMESTAMP NOT NULL,
            penalty_amount INTEGER NOT NULL DEFAULT -2,
            PRIMARY KEY (user_id, group_id, ym, penalty_date),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(group_id) REFERENCES groups(id)
        )
        ''')

        # If table exists from an older schema, it may miss columns used by payment.py.
        # Make this idempotent by adding missing columns only.
        try:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='overdue_penalty_log' AND column_name='group_id'
                LIMIT 1
                """
            )
            has_group_id = cur.fetchone() is not None
            if not has_group_id:
                cur.execute("ALTER TABLE overdue_penalty_log ADD COLUMN group_id BIGINT")
        except Exception:
            conn.rollback()

        try:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='overdue_penalty_log' AND column_name='penalty_date'
                LIMIT 1
                """
            )
            has_penalty_date = cur.fetchone() is not None
            if not has_penalty_date:
                cur.execute("ALTER TABLE overdue_penalty_log ADD COLUMN penalty_date TIMESTAMP")
        except Exception:
            conn.rollback()

        # Ensure penalty_amount exists and has a safe default.
        try:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='overdue_penalty_log' AND column_name='penalty_amount'
                LIMIT 1
                """
            )
            has_penalty_amount = cur.fetchone() is not None
            if not has_penalty_amount:
                cur.execute("ALTER TABLE overdue_penalty_log ADD COLUMN penalty_amount INTEGER NOT NULL DEFAULT -2")
            else:
                cur.execute("UPDATE overdue_penalty_log SET penalty_amount=-2 WHERE penalty_amount IS NULL")
                cur.execute("ALTER TABLE overdue_penalty_log ALTER COLUMN penalty_amount SET DEFAULT -2")
        except Exception:
            conn.rollback()

        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_attendance_sessions_schema():
    """
    Ensure attendance_sessions has columns expected by attendance_manager.py.
    Particularly: closed_at.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='attendance_sessions' AND column_name='closed_at'
                LIMIT 1
                """
            )
            has_closed_at = cur.fetchone() is not None
            if not has_closed_at:
                cur.execute("ALTER TABLE attendance_sessions ADD COLUMN closed_at TIMESTAMP")
        except Exception:
            conn.rollback()
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_temporary_group_assignments_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS temporary_group_assignments (
                id BIGSERIAL PRIMARY KEY,
                group_id BIGINT NOT NULL,
                owner_teacher_id BIGINT NOT NULL,
                temp_teacher_id BIGINT NOT NULL,
                lesson_date TEXT NOT NULL,
                lesson_start TEXT,
                lesson_end TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cancelled_at TIMESTAMP
            )
            '''
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_admin_student_shares_schema() -> None:
    """Limited admins can share a student with another admin (full co-management until unshared)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS admin_student_shares (
                id BIGSERIAL PRIMARY KEY,
                student_id BIGINT NOT NULL,
                peer_admin_id BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_by_admin_id BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cancelled_at TIMESTAMP,
                UNIQUE(student_id, peer_admin_id)
            )
            '''
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def share_student_between_admins(
    student_id: int,
    peer_admin_id: int,
    created_by_admin_id: int,
) -> tuple[bool, str | None]:
    """
    Owner admin shares a student with peer_admin_id. Idempotent if already active.
    Returns (ok, error_key) where error_key is one of:
    not_found, not_student, peer_is_owner, only_owner_can_share
    """
    user = get_user_by_id(int(student_id))
    if not user:
        return False, "not_found"
    if user.get("login_type") not in (1, 2):
        return False, "not_student"
    owner = user.get("owner_admin_id")
    if owner is None:
        return False, "only_owner_can_share"
    if int(peer_admin_id) == int(owner):
        return False, "peer_is_owner"
    if int(created_by_admin_id) != int(owner) and int(created_by_admin_id) not in ADMIN_CHAT_IDS:
        return False, "only_owner_can_share"

    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                INSERT INTO admin_student_shares
                    (student_id, peer_admin_id, status, created_by_admin_id, created_at, cancelled_at)
                VALUES (%s, %s, 'active', %s, CURRENT_TIMESTAMP, NULL)
                ON CONFLICT (student_id, peer_admin_id) DO UPDATE SET
                    status = 'active',
                    created_by_admin_id = EXCLUDED.created_by_admin_id,
                    created_at = CURRENT_TIMESTAMP,
                    cancelled_at = NULL
                """,
                (int(student_id), int(peer_admin_id), int(created_by_admin_id)),
            )
        else:
            cur.execute(
                """
                INSERT INTO admin_student_shares
                    (student_id, peer_admin_id, status, created_by_admin_id, created_at, cancelled_at)
                VALUES (?, ?, 'active', ?, CURRENT_TIMESTAMP, NULL)
                ON CONFLICT(student_id, peer_admin_id) DO UPDATE SET
                    status = 'active',
                    created_by_admin_id = excluded.created_by_admin_id,
                    created_at = CURRENT_TIMESTAMP,
                    cancelled_at = NULL
                """,
                (int(student_id), int(peer_admin_id), int(created_by_admin_id)),
            )
        conn.commit()
        return True, None
    except Exception as e:
        logger.error("share_student_between_admins failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False, "db_error"
    finally:
        conn.close()


def unshare_student_between_admins(
    student_id: int,
    peer_admin_id: int,
    acting_admin_id: int,
) -> tuple[bool, str | None]:
    """
    Owner or peer cancels an active share.
    Returns (ok, error_key): not_found, not_student, not_authorized, not_shared, db_error
    """
    user = get_user_by_id(int(student_id))
    if not user:
        return False, "not_found"
    if user.get("login_type") not in (1, 2):
        return False, "not_student"
    owner = user.get("owner_admin_id")
    allowed_actors = {int(peer_admin_id)}
    if owner is not None:
        allowed_actors.add(int(owner))
    if int(acting_admin_id) not in ADMIN_CHAT_IDS and int(acting_admin_id) not in allowed_actors:
        return False, "not_authorized"

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM admin_student_shares
            WHERE student_id = ? AND peer_admin_id = ? AND status = 'active'
            LIMIT 1
            """,
            (int(student_id), int(peer_admin_id)),
        )
        if not cur.fetchone():
            return False, "not_shared"
        cur.execute(
            """
            UPDATE admin_student_shares
            SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
            WHERE student_id = ? AND peer_admin_id = ? AND status = 'active'
            """,
            (int(student_id), int(peer_admin_id)),
        )
        conn.commit()
        return True, None
    except Exception as e:
        logger.error("unshare_student_between_admins failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False, "db_error"
    finally:
        conn.close()


def is_student_shared_with_admin(student_id: int, admin_id: int) -> bool:
    """True if this admin is an active peer (not the owner) for the student."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1 FROM admin_student_shares
            WHERE student_id = ? AND peer_admin_id = ? AND status = 'active'
            LIMIT 1
            """,
            (int(student_id), int(admin_id)),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def get_shared_student_ids_for_admin(admin_id: int) -> set[int]:
    """Student IDs this admin can manage as a peer (shared owner access)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT student_id FROM admin_student_shares
            WHERE peer_admin_id = ? AND status = 'active'
            """,
            (int(admin_id),),
        )
        rows = cur.fetchall()
        out: set[int] = set()
        for r in rows:
            if isinstance(r, dict):
                sid = r.get("student_id")
            else:
                sid = r[0]
            if sid is not None:
                out.add(int(sid))
        return out
    finally:
        conn.close()


def get_peer_admins_for_student_share(student_id: int) -> list[int]:
    """Active peer admin telegram IDs for notifications / UI."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT peer_admin_id FROM admin_student_shares
            WHERE student_id = ? AND status = 'active'
            ORDER BY peer_admin_id
            """,
            (int(student_id),),
        )
        rows = cur.fetchall()
        peers: list[int] = []
        for r in rows:
            if isinstance(r, dict):
                pid = r.get("peer_admin_id")
            else:
                pid = r[0]
            if pid is not None:
                peers.append(int(pid))
        return peers
    finally:
        conn.close()


def ensure_grammar_attempts_table():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS grammar_attempts (
        id BIGSERIAL PRIMARY KEY,
        user_id BIGINT NOT NULL,
        topic_id TEXT NOT NULL,
        attempts INTEGER DEFAULT 0,
        last_attempt_at TIMESTAMP,
        UNIQUE(user_id, topic_id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')

    # Postgres-only: legacy DBs may store `last_attempt_at` as TEXT.
    if _is_postgres_enabled():
        try:
            cur.execute("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_name='grammar_attempts' AND column_name='last_attempt_at'
            """)
            row = cur.fetchone()
            data_type = (row or {}).get('data_type') if row else None
            if data_type and str(data_type).lower() in ('text', 'character varying', 'character', 'varchar', 'nvarchar'):
                logger.warning(
                    "Legacy schema detected: grammar_attempts.last_attempt_at is %s, converting to TIMESTAMP",
                    data_type,
                )
                cur.execute("""
                    ALTER TABLE grammar_attempts
                    ALTER COLUMN last_attempt_at TYPE TIMESTAMP
                    USING (
                        CASE
                          WHEN last_attempt_at IS NULL THEN NULL
                          WHEN last_attempt_at::text = '' THEN NULL
                          WHEN last_attempt_at::text ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}' THEN last_attempt_at::timestamp
                          ELSE NULL
                        END
                    )
                """)
        except Exception as e:
            # Don't crash the bot on schema migration errors;
            # we also handle TEXT in queries via defensive casting.
            conn.rollback()
            logger.error("Failed to migrate grammar_attempts.last_attempt_at type: %s", e)
    conn.commit()
    conn.close()


def ensure_daily_tests_schema():
    """
    Create schema needed for teacher-uploaded daily tests and student attempts.
    Runs on startup so it works for existing DBs too.
    """
    if not _is_postgres_enabled():
        # Daily tests feature is PostgreSQL-only in this implementation.
        return

    conn = get_conn()
    cur = conn.cursor()
    total_started = time.perf_counter()

    def _reset_tx() -> None:
        try:
            conn.rollback()
        except Exception:
            pass

    def _set_pg_timeouts() -> None:
        # Prevent startup hangs on schema locks.
        try:
            cur.execute("SET LOCAL lock_timeout = '3000ms'")
            cur.execute("SET LOCAL statement_timeout = '20000ms'")
        except Exception:
            _reset_tx()

    def _run_step(label: str, sql: str, params: tuple | None = None, *, fatal: bool = False) -> bool:
        started = time.perf_counter()
        try:
            _set_pg_timeouts()
            if params is None:
                cur.execute(sql)
            else:
                cur.execute(sql, params)
            conn.commit()
            logger.info(
                "ensure_daily_tests_schema step=%s status=ok ms=%.2f",
                str(label),
                (time.perf_counter() - started) * 1000.0,
            )
            return True
        except Exception as e:
            _reset_tx()
            logger.warning(
                "ensure_daily_tests_schema step=%s status=error ms=%.2f err=%s",
                str(label),
                (time.perf_counter() - started) * 1000.0,
                str(e),
            )
            if fatal:
                raise
            return False

    def _column_exists(table_name: str, column_name: str) -> bool:
        started = time.perf_counter()
        try:
            _set_pg_timeouts()
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name=%s AND column_name=%s
                LIMIT 1
                """,
                (str(table_name), str(column_name)),
            )
            exists = cur.fetchone() is not None
            conn.commit()
            logger.info(
                "ensure_daily_tests_schema step=column_exists.%s.%s status=ok ms=%.2f exists=%s",
                str(table_name),
                str(column_name),
                (time.perf_counter() - started) * 1000.0,
                bool(exists),
            )
            return bool(exists)
        except Exception as e:
            _reset_tx()
            logger.warning(
                "ensure_daily_tests_schema step=column_exists.%s.%s status=error ms=%.2f err=%s",
                str(table_name),
                str(column_name),
                (time.perf_counter() - started) * 1000.0,
                str(e),
            )
            return False

    # Teacher permission flags (idempotent, lock-safe).
    if not _column_exists("users", "can_upload_daily_tests"):
        _run_step(
            "users.add_can_upload_daily_tests",
            "ALTER TABLE users ADD COLUMN can_upload_daily_tests INTEGER DEFAULT 0",
        )
    if not _column_exists("users", "can_generate_ai"):
        _run_step(
            "users.add_can_generate_ai",
            "ALTER TABLE users ADD COLUMN can_generate_ai INTEGER DEFAULT 0",
        )
    if not _column_exists("users", "can_upload_books"):
        _run_step(
            "users.add_can_upload_books",
            "ALTER TABLE users ADD COLUMN can_upload_books INTEGER DEFAULT 0",
        )

    # Core daily tests schema (idempotent CREATE TABLE).
    _run_step(
        "daily_tests_bank.create",
        """
        CREATE TABLE IF NOT EXISTS daily_tests_bank (
            id BIGSERIAL PRIMARY KEY,
            created_by BIGINT,
            subject TEXT NOT NULL,
            level TEXT NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option_index INTEGER NOT NULL CHECK (correct_option_index BETWEEN 1 AND 4),
            question_type TEXT,
            active INTEGER DEFAULT 1,
            first_used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    )
    if not _column_exists("daily_tests_bank", "question_type"):
        _run_step("daily_tests_bank.add_question_type", "ALTER TABLE daily_tests_bank ADD COLUMN question_type TEXT")
    if not _column_exists("daily_tests_bank", "payload_json"):
        _run_step("daily_tests_bank.add_payload_json", "ALTER TABLE daily_tests_bank ADD COLUMN payload_json TEXT")
    _run_step(
        "daily_tests_bank.idx_subject_level_active",
        "CREATE INDEX IF NOT EXISTS idx_daily_tests_bank_subject_level_active ON daily_tests_bank(subject, level, active)",
    )

    _run_step(
        "daily_test_attempts.create",
        """
        CREATE TABLE IF NOT EXISTS daily_test_attempts (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            subject TEXT NOT NULL,
            level TEXT NOT NULL,
            test_date DATE NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMP,
            status TEXT NOT NULL DEFAULT 'in_progress',
            total_questions INTEGER NOT NULL DEFAULT 20,
            correct INTEGER NOT NULL DEFAULT 0,
            wrong INTEGER NOT NULL DEFAULT 0,
            unanswered INTEGER NOT NULL DEFAULT 0,
            net_dcoins DOUBLE PRECISION NOT NULL DEFAULT 0,
            net_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
            current_question_index INTEGER NOT NULL DEFAULT 0,
            UNIQUE(user_id, test_date, subject)
        )
        """,
    )
    if not _column_exists("daily_test_attempts", "net_dpoints"):
        _run_step(
            "daily_test_attempts.add_net_dpoints",
            "ALTER TABLE daily_test_attempts ADD COLUMN net_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0",
        )

    # Lightweight and lock-safe unique-constraint repair.
    try:
        _set_pg_timeouts()
        cur.execute(
            """
            SELECT conname, pg_get_constraintdef(c.oid) AS condef
            FROM pg_constraint c
            JOIN pg_class t ON t.oid=c.conrelid
            WHERE t.relname='daily_test_attempts' AND c.contype='u'
            """
        )
        uniq_rows = [dict(r) for r in (cur.fetchall() or [])]
        conn.commit()
        new_exists = any(
            "UNIQUE (user_id, test_date, subject)" in str(row.get("condef") or "")
            for row in uniq_rows
        )
        legacy_names = [
            str(row.get("conname") or "")
            for row in uniq_rows
            if "UNIQUE (user_id, test_date)" in str(row.get("condef") or "")
            and "subject" not in str(row.get("condef") or "")
        ]
        for legacy_name in legacy_names:
            _run_step(
                f"daily_test_attempts.drop_legacy_unique.{legacy_name}",
                f"ALTER TABLE daily_test_attempts DROP CONSTRAINT IF EXISTS {legacy_name}",
            )
        if not new_exists:
            _run_step(
                "daily_test_attempts.add_unique_user_date_subject",
                "ALTER TABLE daily_test_attempts ADD CONSTRAINT ux_daily_test_attempts_user_date_subject UNIQUE(user_id, test_date, subject)",
            )
    except Exception as e:
        _reset_tx()
        logger.warning("ensure_daily_tests_schema step=daily_test_attempts.unique_repair status=error err=%s", str(e))

    _run_step(
        "daily_test_attempts.idx_user_date_subject_status",
        "CREATE INDEX IF NOT EXISTS idx_daily_test_attempts_user_date_subject_status ON daily_test_attempts(user_id, test_date, subject, status)",
    )
    _run_step(
        "daily_test_attempts.idx_user_subject_date",
        "CREATE INDEX IF NOT EXISTS idx_daily_test_attempts_user_subject_date ON daily_test_attempts(user_id, subject, test_date)",
    )

    _run_step(
        "daily_test_attempt_items.create",
        """
        CREATE TABLE IF NOT EXISTS daily_test_attempt_items (
            id BIGSERIAL PRIMARY KEY,
            attempt_id BIGINT NOT NULL,
            bank_test_id BIGINT NOT NULL,
            question_index INTEGER NOT NULL,
            question TEXT NOT NULL,
            options_json TEXT,
            selected_option TEXT,
            is_correct INTEGER NOT NULL DEFAULT 0,
            answered_at TIMESTAMP,
            timed_out INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(attempt_id, question_index),
            FOREIGN KEY(attempt_id) REFERENCES daily_test_attempts(id) ON DELETE CASCADE
        )
        """,
    )
    if not _column_exists("daily_test_attempt_items", "payload_json"):
        _run_step("daily_test_attempt_items.add_payload_json", "ALTER TABLE daily_test_attempt_items ADD COLUMN payload_json TEXT")
    _run_step(
        "daily_test_notifications.create",
        """
        CREATE TABLE IF NOT EXISTS daily_test_notifications (
            user_id BIGINT NOT NULL,
            test_date DATE NOT NULL,
            reminder_slot INTEGER NOT NULL, -- 0=09:00 initial, 1=14:00, 2=19:00
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, test_date, reminder_slot)
        )
        """,
    )
    _run_step(
        "daily_test_usage.create",
        """
        CREATE TABLE IF NOT EXISTS daily_test_usage (
            user_id BIGINT NOT NULL,
            bank_test_id BIGINT NOT NULL,
            first_used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cleaned_at TIMESTAMP,
            UNIQUE(user_id, bank_test_id),
            FOREIGN KEY(bank_test_id) REFERENCES daily_tests_bank(id) ON DELETE CASCADE
        )
        """,
    )
    _run_step(
        "daily_test_stock_alerts.create",
        """
        CREATE TABLE IF NOT EXISTS daily_test_stock_alerts (
            id BIGSERIAL PRIMARY KEY,
            subject TEXT,
            level TEXT,
            threshold INTEGER NOT NULL,
            notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subject, level, threshold)
        )
        """,
    )
    _run_step(
        "daily_test_day_question_sets.create",
        """
        CREATE TABLE IF NOT EXISTS daily_test_day_question_sets (
            id BIGSERIAL PRIMARY KEY,
            test_date DATE NOT NULL,
            subject TEXT NOT NULL,
            level TEXT NOT NULL,
            total_questions INTEGER NOT NULL,
            bank_ids_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(test_date, subject, level)
        )
        """,
    )
    _run_step(
        "daily_test_day_question_sets.idx_lookup",
        """
        CREATE INDEX IF NOT EXISTS idx_daily_test_day_sets_lookup
        ON daily_test_day_question_sets (test_date, subject, level)
        """,
    )
    _run_step(
        "daily_test_day_question_sets.idx_date",
        """
        CREATE INDEX IF NOT EXISTS idx_daily_test_day_sets_date
        ON daily_test_day_question_sets (test_date)
        """,
    )
    _run_step(
        "daily_test_type_plans.create",
        """
        CREATE TABLE IF NOT EXISTS daily_test_type_plans (
            test_date DATE NOT NULL,
            subject TEXT NOT NULL,
            grammar_rules_count INTEGER NOT NULL,
            grammar_sentence_count INTEGER NOT NULL,
            find_mistake_count INTEGER NOT NULL,
            error_spotting_count INTEGER NOT NULL,
            total_questions INTEGER NOT NULL DEFAULT 20,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (test_date, subject)
        )
        """,
    )

    logger.info(
        "ensure_daily_tests_schema total_ms=%.2f",
        (time.perf_counter() - total_started) * 1000.0,
    )
    conn.close()


def ensure_arena_group_schema() -> None:
    """
    Group Arena (teacher-generated quiz) storage.
    Uses `daily_tests_bank` rows as the question source and stores selected bank ids per session.
    """
    if not _is_postgres_enabled():
        return

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS arena_group_sessions (
                id BIGSERIAL PRIMARY KEY,
                group_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                question_count INTEGER NOT NULL,
                bank_ids_json TEXT NOT NULL,
                created_by_teacher_id BIGINT,
                expected_players INTEGER NOT NULL DEFAULT 0,
                rewards_distributed INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'ready', -- ready | sent | completed
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
            '''
        )

        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS arena_group_session_attempts (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP,
                correct INTEGER NOT NULL DEFAULT 0,
                wrong INTEGER NOT NULL DEFAULT 0,
                unanswered INTEGER NOT NULL DEFAULT 0,
                net_dcoins DOUBLE PRECISION NOT NULL DEFAULT 0,
                net_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                UNIQUE(user_id, session_id)
            )
            '''
        )
        try:
            cur.execute("ALTER TABLE arena_group_session_attempts ADD COLUMN IF NOT EXISTS net_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0")
        except Exception:
            pass
        conn.commit()
        # Migration for older DBs: add `is_unanswered` if table existed without the column.
        try:
            _ensure_arena_run_answers_is_unanswered_column()
        except Exception:
            pass
    finally:
        conn.close()

    # Backward compatible: add columns if table exists without them.
    if _is_postgres_enabled():
        conn2 = get_conn()
        cur2 = conn2.cursor()
        try:
            cur2.execute("ALTER TABLE arena_group_sessions ADD COLUMN IF NOT EXISTS expected_players INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            cur2.execute("ALTER TABLE arena_group_sessions ADD COLUMN IF NOT EXISTS rewards_distributed INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            cur2.execute("ALTER TABLE arena_group_sessions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP")
        except Exception:
            pass
        try:
            cur2.execute("CREATE INDEX IF NOT EXISTS idx_arena_group_sessions_group_status ON arena_group_sessions(group_id, status)")
        except Exception:
            pass
        conn2.commit()
        conn2.close()


def ensure_arena_group_extended_schema() -> None:
    """Per-question answers, teacher live UI columns, promote-to-daily marker, refresh queue."""
    if not _is_postgres_enabled():
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS arena_group_session_answers (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                question_order INTEGER NOT NULL,
                bank_question_id BIGINT NOT NULL,
                selected_option_index INTEGER,
                is_correct INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, user_id, question_order)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS arena_group_teacher_refresh_queue (
                session_id BIGINT PRIMARY KEY,
                enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "ALTER TABLE arena_group_sessions ADD COLUMN IF NOT EXISTS teacher_chat_id BIGINT"
        )
        cur.execute(
            "ALTER TABLE arena_group_sessions ADD COLUMN IF NOT EXISTS teacher_status_message_id BIGINT"
        )
        cur.execute(
            "ALTER TABLE arena_questions_bank ADD COLUMN IF NOT EXISTS promoted_to_daily_at TIMESTAMP"
        )
        conn.commit()
    except Exception:
        logger.exception("ensure_arena_group_extended_schema failed")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def insert_arena_group_session_answer(
    *,
    session_id: int,
    user_id: int,
    question_order: int,
    bank_question_id: int,
    selected_option_index: int | None,
    is_correct: bool,
) -> None:
    if not _is_postgres_enabled():
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO arena_group_session_answers
                (session_id, user_id, question_order, bank_question_id, selected_option_index, is_correct)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (session_id, user_id, question_order)
            DO UPDATE SET
                bank_question_id = excluded.bank_question_id,
                selected_option_index = excluded.selected_option_index,
                is_correct = excluded.is_correct
            """,
            (
                int(session_id),
                int(user_id),
                int(question_order),
                int(bank_question_id),
                selected_option_index,
                1 if is_correct else 0,
            ),
        )
        conn.commit()
        # Migration for older DBs: add `is_unanswered` if table existed without the column.
        try:
            _ensure_arena_run_answers_is_unanswered_column()
        except Exception:
            pass
    finally:
        conn.close()


def enqueue_arena_group_teacher_refresh(session_id: int) -> None:
    if not _is_postgres_enabled():
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO arena_group_teacher_refresh_queue (session_id)
            VALUES (?)
            ON CONFLICT (session_id) DO UPDATE SET enqueued_at = CURRENT_TIMESTAMP
            """,
            (int(session_id),),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def pop_arena_group_teacher_refresh_session() -> int | None:
    if not _is_postgres_enabled():
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT session_id FROM arena_group_teacher_refresh_queue
            ORDER BY enqueued_at ASC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return None
        sid = int(row["session_id"])
        cur.execute(
            "DELETE FROM arena_group_teacher_refresh_queue WHERE session_id=?",
            (sid,),
        )
        conn.commit()
        return sid
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def set_arena_group_session_teacher_message(
    session_id: int, teacher_chat_id: int, message_id: int
) -> None:
    if not _is_postgres_enabled():
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE arena_group_sessions
            SET teacher_chat_id=?, teacher_status_message_id=?
            WHERE id=?
            """,
            (int(teacher_chat_id), int(message_id), int(session_id)),
        )
        conn.commit()
    finally:
        conn.close()


def user_is_present_for_group_on_date(user_id: int, group_id: int, date_str: str) -> bool:
    present = get_present_students_for_group_date(group_id, date_str)
    return any(int(u.get("id") or 0) == int(user_id) for u in present)


def get_group_arena_teacher_snapshot(session_id: int) -> dict | None:
    """Raw data for teacher live / export UI."""
    sess = get_arena_group_session(session_id)
    if not sess:
        return None
    gid = int(sess["group_id"])
    tz = pytz.timezone("Asia/Tashkent")
    today = datetime.now(tz).strftime("%Y-%m-%d")
    present = get_present_students_for_group_date(gid, today)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT * FROM arena_group_session_attempts
            WHERE session_id=?
            ORDER BY user_id
            """,
            (int(session_id),),
        )
        attempts = [dict(r) for r in cur.fetchall() or []]
    finally:
        conn.close()
    return {"session": sess, "present": present, "attempts": attempts, "date_str": today}


def list_arena_group_session_answers_for_export(session_id: int) -> list[dict]:
    if not _is_postgres_enabled():
        return []
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT a.*, u.first_name, u.last_name
            FROM arena_group_session_answers a
            JOIN users u ON u.id = a.user_id
            WHERE a.session_id=?
            ORDER BY a.user_id, a.question_order
            """,
            (int(session_id),),
        )
        return [dict(r) for r in cur.fetchall() or []]
    finally:
        conn.close()


def promote_expired_arena_questions_to_daily() -> int:
    """
    Promote Group Arena runtime tmp questions into `daily_tests_bank` after 3 hours retention.
    (Replaces the legacy 24h promotion from `arena_questions_bank`.)
    """
    if not _is_postgres_enabled():
        return 0
    ensure_arena_group_schema()
    ensure_arena_questions_tmp_schema()
    ensure_daily_tests_schema()
    conn = get_conn()
    cur = conn.cursor()
    promoted_rows = 0
    try:
        cur.execute(
            """
            SELECT DISTINCT t.session_id, s.completed_at
            FROM arena_group_questions_tmp t
            JOIN arena_group_sessions s ON s.id = t.session_id
            WHERE s.status='completed'
              AND s.completed_at <= (CURRENT_TIMESTAMP - INTERVAL '3 hours')
              AND t.promoted_at IS NULL
            ORDER BY s.completed_at ASC
            LIMIT 20
            """
        )
        session_ids = [int(r["session_id"]) for r in cur.fetchall() or []]

        import json

        for sid in session_ids:
            # Load session subject/level for daily_tests_bank insertion.
            cur.execute(
                """
                SELECT subject, level
                FROM arena_group_sessions
                WHERE id=?
                """,
                (int(sid),),
            )
            sess_row = cur.fetchone() or {}
            subject = str(sess_row.get("subject") or "English").strip().title()
            base_level = str(sess_row.get("level") or "B2").strip().upper() or "B2"

            cur.execute(
                """
                SELECT q_index, payload_json
                FROM arena_group_questions_tmp
                WHERE session_id=? AND promoted_at IS NULL
                ORDER BY q_index ASC
                """,
                (int(sid),),
            )
            qrows = cur.fetchall() or []
            if not qrows:
                continue

            for qr in qrows:
                try:
                    payload = json.loads(qr["payload_json"] or "{}")
                except Exception:
                    payload = {}

                created_by = int(payload.get("created_by") or 0)
                level = str(payload.get("level") or base_level).strip().upper() or base_level
                question = str(payload.get("question") or "").strip()

                option_a = str(payload.get("option_a") or "").strip()
                option_b = str(payload.get("option_b") or "").strip()
                option_c = str(payload.get("option_c") or "").strip()
                option_d = str(payload.get("option_d") or "").strip()

                correct_option_index = int(payload.get("correct_option_index") or 1)
                correct_option_index = int(max(1, min(4, correct_option_index)))

                question_type = payload.get("question_type")

                if not question:
                    continue

                cur.execute(
                    """
                    INSERT INTO daily_tests_bank
                        (created_by, subject, level, question,
                         option_a, option_b, option_c, option_d,
                         correct_option_index, question_type, payload_json, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        created_by,
                        subject,
                        level,
                        question,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        correct_option_index,
                        question_type,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )
                promoted_rows += 1

            # Cleanup tmp snapshot after successful promotion.
            cur.execute(
                """
                DELETE FROM arena_group_questions_tmp
                WHERE session_id=? AND promoted_at IS NULL
                """,
                (int(sid),),
            )
        conn.commit()
    except Exception:
        logger.exception("promote_expired_arena_questions_to_daily failed")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return promoted_rows


def promote_expired_daily_arena_questions_to_daily() -> int:
    """
    Copy Daily/Boss Arena runtime tmp questions into `daily_tests_bank` after 3 hours retention.

    For each eligible finished daily run:
      - read all questions from `arena_*_questions_tmp.payload_json`
      - insert into `daily_tests_bank`
      - mark `arena_scheduled_runs.questions_promoted=1`
      - cleanup tmp question rows for that run
    """
    import json

    if not _is_postgres_enabled():
        return 0
    ensure_arena_extras_schema()
    ensure_arena_questions_tmp_schema()
    ensure_daily_tests_schema()

    # If older DBs exist without the column, auto-migrate before SELECT.
    try:
        _ensure_arena_scheduled_runs_questions_promoted_column()
    except Exception:
        pass

    conn = get_conn()
    cur = conn.cursor()
    promoted_runs = 0
    try:
        # Limit how long the promotion scheduler can hold locks.
        try:
            cur.execute("SET LOCAL statement_timeout = '10s'")
        except Exception:
            pass

        select_sql = """
            SELECT id, subject, run_kind
            FROM arena_scheduled_runs
            WHERE run_kind IN ('daily','boss')
              AND status='finished'
              AND questions_promoted=0
              AND finished_at <= (CURRENT_TIMESTAMP - INTERVAL '3 hours')
            ORDER BY finished_at ASC
            LIMIT 20
        """
        try:
            cur.execute(select_sql)
        except psycopg.errors.UndefinedColumn:
            # Transaction might be aborted; rollback and auto-migrate then retry once.
            try:
                conn.rollback()
            except Exception:
                pass
            _ensure_arena_scheduled_runs_questions_promoted_column()
            cur = conn.cursor()
            try:
                cur.execute("SET LOCAL statement_timeout = '10s'")
            except Exception:
                pass
            cur.execute(select_sql)
        runs = [dict(r) for r in cur.fetchall() or []]
        for r in runs:
            run_id = int(r["id"])
            subject = str(r.get("subject") or "English").strip().title()
            run_kind = str(r.get("run_kind") or "").strip().lower()

            if run_kind == "daily":
                qtable = "arena_daily_questions_tmp"
            else:
                qtable = "arena_boss_questions_tmp"

            cur.execute(
                f"""
                SELECT stage, q_index, payload_json
                FROM {qtable}
                WHERE run_id=?
                ORDER BY stage ASC, q_index ASC
                """,
                (run_id,),
            )
            qrows = cur.fetchall() or []

            for qr in qrows:
                payload = {}
                try:
                    payload = json.loads(qr["payload_json"] or "{}")
                except Exception:
                    payload = {}

                created_by = int(payload.get("created_by") or 0)
                level = str(payload.get("level") or "B2").strip().upper() or "B2"
                question = str(payload.get("question") or "").strip()
                option_a = str(payload.get("option_a") or "").strip()
                option_b = str(payload.get("option_b") or "").strip()
                option_c = str(payload.get("option_c") or "").strip()
                option_d = str(payload.get("option_d") or "").strip()
                correct_option_index = int(payload.get("correct_option_index") or 1)
                question_type = payload.get("question_type")

                if not question:
                    continue

                cur.execute(
                    """
                    INSERT INTO daily_tests_bank
                        (created_by, subject, level, question,
                         option_a, option_b, option_c, option_d,
                         correct_option_index, question_type, payload_json, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        created_by,
                        subject,
                        level,
                        question,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        int(max(1, min(4, correct_option_index))),
                        question_type,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

            # Mark promoted + cleanup.
            cur.execute(
                "UPDATE arena_scheduled_runs SET questions_promoted=1 WHERE id=?",
                (run_id,),
            )
            # Cleanup tmp question pool.
            cur.execute(f"DELETE FROM {qtable} WHERE run_id=?", (run_id,))

            # Best-effort cleanup (may already be deleted by coordinators).
            cur.execute("DELETE FROM arena_run_answers WHERE run_id=?", (run_id,))
            cur.execute("DELETE FROM arena_run_questions WHERE run_id=?", (run_id,))
            promoted_runs += 1

        conn.commit()
    except Exception:
        logger.exception("promote_expired_daily_arena_questions_to_daily failed")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return promoted_runs


def promote_expired_duel_questions_tmp_to_daily() -> int:
    """
    Promote finished Duel (1v1/5v5) tmp questions into `daily_tests_bank` after 3 hours.
    """
    import json

    if not _is_postgres_enabled():
        return 0
    ensure_duel_matchmaking_schema()
    ensure_arena_questions_tmp_schema()
    ensure_daily_tests_schema()

    conn = get_conn()
    cur = conn.cursor()
    promoted_rows = 0
    try:
        cur.execute(
            """
            SELECT id, subject, level, mode
            FROM open_duel_sessions
            WHERE status='finished'
              AND finished_at <= (CURRENT_TIMESTAMP - INTERVAL '3 hours')
              AND mode IN ('1v1','5v5')
            ORDER BY finished_at ASC
            LIMIT 20
            """
        )
        sessions = [dict(r) for r in cur.fetchall() or []]

        for s in sessions:
            sess_id = int(s["id"])
            subject = str(s.get("subject") or "English").strip().title()
            base_level = str(s.get("level") or "A1").strip().upper() or "A1"

            mode = str(s.get("mode") or "").strip().lower()
            qtable = "duel_1v1_questions_tmp" if mode == "1v1" else "duel_5v5_questions_tmp"

            cur.execute(
                f"""
                SELECT q_index, payload_json
                FROM {qtable}
                WHERE session_id=? AND promoted_at IS NULL
                ORDER BY q_index ASC
                """,
                (sess_id,),
            )
            qrows = cur.fetchall() or []
            if not qrows:
                continue

            for qr in qrows:
                try:
                    payload = json.loads(qr["payload_json"] or "{}")
                except Exception:
                    payload = {}

                created_by = int(payload.get("created_by") or 0)
                level = str(payload.get("level") or base_level).strip().upper() or base_level
                question = str(payload.get("question") or "").strip()
                option_a = str(payload.get("option_a") or "").strip()
                option_b = str(payload.get("option_b") or "").strip()
                option_c = str(payload.get("option_c") or "").strip()
                option_d = str(payload.get("option_d") or "").strip()
                correct_option_index = int(payload.get("correct_option_index") or 1)
                correct_option_index = int(max(1, min(4, correct_option_index)))
                question_type = payload.get("question_type")

                if not question:
                    continue

                cur.execute(
                    """
                    INSERT INTO daily_tests_bank
                        (created_by, subject, level, question,
                         option_a, option_b, option_c, option_d,
                         correct_option_index, question_type, payload_json, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        created_by,
                        subject,
                        level,
                        question,
                        option_a,
                        option_b,
                        option_c,
                        option_d,
                        correct_option_index,
                        question_type,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )
                promoted_rows += 1

            # Cleanup tmp snapshot after successful promotion.
            cur.execute(f"DELETE FROM {qtable} WHERE session_id=? AND promoted_at IS NULL", (sess_id,))

        conn.commit()
    except Exception:
        logger.exception("promote_expired_duel_questions_tmp_to_daily failed")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return promoted_rows


def ensure_arena_questions_schema() -> None:
    """
    Separate bank for Arena questions.
    For now, Group Arena generator reuses `daily_tests_bank` content and copies rows into this table.
    """
    if not _is_postgres_enabled():
        return

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS arena_questions_bank (
                id BIGSERIAL PRIMARY KEY,
                created_by BIGINT,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                question TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option_index INTEGER NOT NULL CHECK (correct_option_index BETWEEN 1 AND 4),
                question_type TEXT,
                payload_json TEXT,
                active INTEGER DEFAULT 1,
                first_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
            )
        try:
            cur.execute(
                "ALTER TABLE arena_questions_bank ADD COLUMN IF NOT EXISTS promoted_to_daily_at TIMESTAMP"
            )
        except Exception:
            pass
        try:
            cur.execute(
                "ALTER TABLE arena_questions_bank ADD COLUMN IF NOT EXISTS payload_json TEXT"
            )
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_arena_questions_bank_subject_level_active ON arena_questions_bank(subject, level, active)")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def ensure_user_subject_schema() -> None:
    """
    Ensure `user_subject` exists and is seeded from `users.subject`.

    Some flows (scheduled arena notifier) rely on `user_subject` for subject-based fanout.
    In older DBs this table may be missing, so we create it + backfill.
    """
    if not _is_postgres_enabled():
        return

    conn = get_conn()
    cur = conn.cursor()
    started = time.perf_counter()
    try:
        try:
            cur.execute("SET LOCAL lock_timeout = '3000ms'")
            cur.execute("SET LOCAL statement_timeout = '15000ms'")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_subject (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                subject TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, subject)
            )
            '''
        )
        conn.commit()

        # Keep the fanout table aligned with users.subject. Older code only seeded
        # the table once, so users created later could be missing here.
        cur.execute(
            '''
            DELETE FROM user_subject us
            USING users u
            WHERE us.user_id = u.id
              AND NOT EXISTS (
                  SELECT 1
                  FROM unnest(string_to_array(COALESCE(u.subject, ''), ',')) AS s
                  WHERE trim(s) <> '' AND trim(s) = us.subject
              )
            '''
        )
        cur.execute(
            '''
            INSERT INTO user_subject (user_id, subject)
            SELECT
                u.id AS user_id,
                trim(s) AS subject
            FROM users u
            CROSS JOIN LATERAL unnest(string_to_array(u.subject, ',')) AS s
            WHERE u.subject IS NOT NULL
              AND trim(s) <> ''
            ON CONFLICT DO NOTHING
            '''
        )
        conn.commit()
        logger.info(
            "ensure_user_subject_schema sync=done total_ms=%.2f",
            (time.perf_counter() - started) * 1000.0,
        )
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning("ensure_user_subject_schema failed err=%s", str(e))
    finally:
        conn.close()


# When daily_tests_bank.question_type is empty, cycle these for group arena staging/export.
GROUP_ARENA_QUESTION_TYPE_CYCLE = (
    "reading",
    "grammar",
    "sentence_error",
    "true_false",
    "synonym",
    "antonym",
    "gap_fill",
    "vocab_definition",
)


def copy_daily_tests_bank_rows_to_arena_questions(
    *,
    bank_ids: list[int],
    created_by: int,
) -> list[int]:
    """
    Copy daily_tests_bank rows into arena_questions_bank.
    Returns new arena_questions_bank ids in the same order as `bank_ids`.
    """
    if not bank_ids:
        return []
    ensure_arena_questions_schema()

    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["?"] * len(bank_ids))
        cur.execute(
            f'''
            SELECT id, subject, level, question,
                   option_a, option_b, option_c, option_d,
                   correct_option_index, question_type, payload_json
            FROM daily_tests_bank
            WHERE id IN ({placeholders})
              AND active=1
            ''',
            tuple(int(x) for x in bank_ids),
        )
        rows = cur.fetchall()
        by_id = {int(r["id"]): r for r in rows}

        arena_ids: list[int] = []
        for i, bid in enumerate(bank_ids):
            r = by_id.get(int(bid))
            if not r:
                continue
            qt_raw = r.get("question_type")
            qt = (str(qt_raw).strip() if qt_raw is not None else "") or ""
            if not qt:
                qt = GROUP_ARENA_QUESTION_TYPE_CYCLE[i % len(GROUP_ARENA_QUESTION_TYPE_CYCLE)]
            # Insert single row to allow grabbing RETURNING id.
            cur.execute(
                '''
                INSERT INTO arena_questions_bank
                    (created_by, subject, level, question,
                     option_a, option_b, option_c, option_d,
                     correct_option_index, question_type, payload_json, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                RETURNING id
                ''',
                (
                    int(created_by),
                    str(r["subject"]),
                    str(r["level"]),
                    str(r["question"]),
                    str(r["option_a"]),
                    str(r["option_b"]),
                    str(r["option_c"]),
                    str(r["option_d"]),
                    int(r["correct_option_index"]),
                    qt,
                    r.get("payload_json"),
                ),
            )
            new_id_row = cur.fetchone()
            if new_id_row:
                # Postgres (psycopg dict_row): {"id": ...}
                # SQLite: may be tuple-like (0-based).
                new_id = None
                try:
                    if isinstance(new_id_row, dict):
                        new_id = new_id_row.get("id")
                    else:
                        new_id = new_id_row[0]
                except Exception:
                    try:
                        new_id = new_id_row["id"]
                    except Exception:
                        new_id = None
                if new_id is not None:
                    arena_ids.append(int(new_id))

        conn.commit()
        return arena_ids
    finally:
        conn.close()


def ensure_arena_other_sessions_schema() -> None:
    """Create placeholder schemas for other arena types (daily/boss/duel)."""
    if not _is_postgres_enabled():
        return

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS arena_daily_sessions (
                id BIGSERIAL PRIMARY KEY,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                question_count INTEGER NOT NULL,
                bank_ids_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                created_by_teacher_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS arena_daily_session_attempts (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                UNIQUE(user_id, session_id)
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS arena_boss_sessions (
                id BIGSERIAL PRIMARY KEY,
                subject TEXT NOT NULL,
                level TEXT NOT NULL,
                question_count INTEGER NOT NULL,
                bank_ids_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ready',
                created_by_teacher_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        cur.execute(
            '''
            CREATE TABLE IF NOT EXISTS arena_boss_session_attempts (
                id BIGSERIAL PRIMARY KEY,
                session_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                UNIQUE(user_id, session_id)
            )
            '''
        )
        conn.commit()
    finally:
        conn.close()


def create_arena_group_session(
    *,
    group_id: int,
    subject: str,
    level: str,
    question_count: int,
    bank_ids: list[int],
    created_by_teacher_id: int,
) -> int:
    import json

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            INSERT INTO arena_group_sessions
                (group_id, subject, level, question_count, bank_ids_json, created_by_teacher_id, status)
            VALUES (?, ?, ?, ?, ?, ?, 'ready')
            RETURNING id
            ''',
            (group_id, subject, level, int(question_count), json.dumps(bank_ids), created_by_teacher_id),
        )
        session_id = int(cur.fetchone()["id"])
        conn.commit()
        return session_id
    finally:
        conn.close()


def set_arena_group_session_status(session_id: int, status: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            'UPDATE arena_group_sessions SET status=? WHERE id=?',
            (status, int(session_id)),
        )
        conn.commit()
    finally:
        conn.close()


def cancel_group_arena_sessions_for_date(date_iso: str, group_ids: list[int], admin_note: str | None = None) -> int:
    """
    Cancel group arena sessions created on date for given groups.
    Returns affected session count.
    """
    if not group_ids:
        return 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholders = ",".join(["?"] * len(group_ids))
        # SQLite/Postgres compatibility in this codebase uses DATE(created_at)=?
        cur.execute(
            f"""
            UPDATE arena_group_sessions
            SET status='cancelled', completed_at=CURRENT_TIMESTAMP
            WHERE group_id IN ({placeholders})
              AND DATE(created_at)=?
              AND status IN ('ready','sent')
            """,
            (*[int(gid) for gid in group_ids], str(date_iso)),
        )
        cnt = int(cur.rowcount or 0)
        conn.commit()
        return cnt
    except Exception:
        logger.exception(
            "cancel_group_arena_sessions_for_date failed date=%s groups=%s note=%s",
            date_iso,
            group_ids,
            admin_note,
        )
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def set_arena_group_session_expected_players(session_id: int, expected_players: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            UPDATE arena_group_sessions
            SET expected_players=?, rewards_distributed=0, status='sent'
            WHERE id=?
            ''',
            (int(expected_players), int(session_id)),
        )
        conn.commit()
    finally:
        conn.close()


def _arena_attempt_duration_seconds(row: dict) -> float:
    """Shorter duration wins ties on same correct count."""
    from datetime import datetime

    try:
        sa = row.get("started_at")
        fa = row.get("finished_at")
        if sa is None or fa is None:
            return float("inf")
        if isinstance(sa, (int, float)) and isinstance(fa, (int, float)):
            return max(0.0, float(fa) - float(sa))
        s = str(sa).replace("Z", "").replace("+00:00", "")
        f = str(fa).replace("Z", "").replace("+00:00", "")
        d0 = datetime.fromisoformat(s[:26]) if len(s) > 19 else datetime.fromisoformat(s)
        d1 = datetime.fromisoformat(f[:26]) if len(f) > 19 else datetime.fromisoformat(f)
        return max(0.0, (d1 - d0).total_seconds())
    except Exception:
        return float("inf")


def distribute_arena_group_rewards_if_ready(session_id: int) -> dict:
    """
    Group Arena reward: every exact first-place tie receives 10 D'point.
    Once all expected players finished (finished_at set).
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            SELECT id, subject, expected_players, rewards_distributed
            FROM arena_group_sessions
            WHERE id=?
            ''',
            (int(session_id),),
        )
        sess = cur.fetchone()
        if not sess:
            return {"done": False, "max_correct": None, "winners": [], "winner_rewards": []}

        expected_players = int(sess["expected_players"] or 0)
        if expected_players <= 0:
            return {"done": False, "max_correct": None, "winners": [], "winner_rewards": []}
        if int(sess.get("rewards_distributed") or 0) == 1:
            return {"done": True, "max_correct": None, "winners": [], "winner_rewards": []}

        cur.execute(
            """
            SELECT COUNT(*) as c FROM arena_group_session_attempts
            WHERE session_id=? AND finished_at IS NOT NULL
            """,
            (int(session_id),),
        )
        attempts_count = int((cur.fetchone() or {}).get("c") or 0)
        if attempts_count < expected_players:
            return {"done": False, "max_correct": None, "winners": [], "winner_rewards": []}

        cur.execute(
            """
            SELECT user_id, correct, started_at, finished_at
            FROM arena_group_session_attempts
            WHERE session_id=? AND finished_at IS NOT NULL
            """,
            (int(session_id),),
        )
        rows = [dict(r) for r in cur.fetchall() or []]
        if not rows:
            return {"done": False, "max_correct": None, "winners": [], "winner_rewards": []}

        max_correct = max(int(r.get("correct") or 0) for r in rows)
        winner_rewards: list[tuple[int, float]] = []
        subject = (sess.get("subject") or "").strip().title() or None
        runtime_rules = _load_runtime_dpoint_rules_from_db()
        group_winner_reward = max(0.0, float(runtime_rules.get("group_arena_winner_reward") or 10.0))
        winners_rows = [row for row in rows if int(row.get("correct") or 0) == max_correct]
        for row in winners_rows:
            uid = int(row["user_id"])
            amt = group_winner_reward
            winner_rewards.append((uid, amt))
            try:
                add_dpoints(uid, amt, subject, change_type=f"group_arena_reward:{int(session_id)}")
            except Exception:
                logger.exception(
                    "Failed to add arena group reward uid=%s session_id=%s place=%s",
                    uid,
                    session_id,
                    "first_tie",
                )

        winners = [u for u, _ in winner_rewards]

        cur.execute(
            '''
            UPDATE arena_group_sessions
            SET rewards_distributed=1, status='completed', completed_at=CURRENT_TIMESTAMP
            WHERE id=?
            ''',
            (int(session_id),),
        )
        conn.commit()
        return {
            "done": True,
            "max_correct": max_correct,
            "winners": winners,
            "winner_rewards": winner_rewards,
        }
    finally:
        conn.close()


def get_arena_group_session(session_id: int) -> dict | None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            SELECT id, group_id, subject, level, question_count, bank_ids_json, created_by_teacher_id,
                   expected_players, rewards_distributed,
                   status, created_at
                   , teacher_chat_id, teacher_status_message_id
            FROM arena_group_sessions
            WHERE id=?
            ''',
            (int(session_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()


def list_ready_arena_group_sessions(group_id: int, limit: int = 20) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            SELECT id, group_id, subject, level, question_count, bank_ids_json, created_by_teacher_id,
                   expected_players, rewards_distributed, status, created_at,
                   teacher_chat_id, teacher_status_message_id
            FROM arena_group_sessions
            WHERE group_id=? AND status='ready'
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            ''',
            (int(group_id), int(max(1, min(100, limit)))),
        )
        return [dict(row) for row in (cur.fetchall() or [])]
    finally:
        conn.close()


def mark_arena_group_session_attempt(
    *,
    session_id: int,
    user_id: int,
) -> bool:
    """
    Returns True if inserted (first time for this user & session), else False.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            INSERT INTO arena_group_session_attempts(session_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(user_id, session_id) DO NOTHING
            ''',
            (int(session_id), int(user_id)),
        )
        inserted = cur.rowcount or 0
        conn.commit()
        return bool(inserted)
    finally:
        conn.close()


def finish_arena_group_session_attempt(
    *,
    session_id: int,
    user_id: int,
    correct: int,
    wrong: int,
    unanswered: int,
    net_dcoins: float,
    net_dpoints: float | None = None,
) -> None:
    points_value = float(net_dpoints) if net_dpoints is not None else float(net_dcoins)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            UPDATE arena_group_session_attempts
            SET finished_at=CURRENT_TIMESTAMP,
                correct=?,
                wrong=?,
                unanswered=?,
                net_dcoins=?,
                net_dpoints=?
            WHERE session_id=? AND user_id=?
            ''',
            (int(correct), int(wrong), int(unanswered), float(net_dcoins), points_value, int(session_id), int(user_id)),
        )
        conn.commit()
    finally:
        conn.close()


def update_arena_group_session_attempt_progress(
    *,
    session_id: int,
    user_id: int,
    correct: int,
    wrong: int,
    unanswered: int,
) -> None:
    """Update live Group Arena progress before final finish."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            UPDATE arena_group_session_attempts
            SET correct=?,
                wrong=?,
                unanswered=?
            WHERE session_id=? AND user_id=?
            ''',
            (int(correct), int(wrong), int(unanswered), int(session_id), int(user_id)),
        )
        conn.commit()
    finally:
        conn.close()


def populate_arena_group_questions_tmp(session_id: int) -> int:
    """
    Snapshot Group Arena session questions into `arena_group_questions_tmp`.
    Used for delayed promotion after the session is completed.
    """
    ensure_arena_group_schema()
    ensure_arena_questions_tmp_schema()

    import json

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT subject, level, question_count, bank_ids_json
            FROM arena_group_sessions
            WHERE id=?
            """,
            (int(session_id),),
        )
        sess = cur.fetchone()
        if not sess:
            return 0

        bank_ids = json.loads(sess["bank_ids_json"] or "[]")
        qcount = int(sess.get("question_count") or len(bank_ids) or 0)
        if not bank_ids or qcount <= 0:
            return 0

        # Reset tmp for this session.
        cur.execute("DELETE FROM arena_group_questions_tmp WHERE session_id=?", (int(session_id),))

        bank_ids_int = [int(x) for x in bank_ids]
        placeholders = ",".join(["?"] * len(bank_ids_int))

        def _fetch_rows(table: str) -> dict[int, dict]:
            cur.execute(
                f'''
                SELECT
                    id, created_by, level, question,
                    option_a, option_b, option_c, option_d,
                    correct_option_index, question_type, payload_json
                FROM {table}
                WHERE id IN ({placeholders})
                  AND active=1
                ''',
                tuple(bank_ids_int),
            )
            rows = cur.fetchall() or []
            return {int(r["id"]): dict(r) for r in rows}

        by_id: dict[int, dict] = {}
        try:
            by_id = _fetch_rows("arena_questions_bank")
        except Exception:
            by_id = {}

        if not by_id:
            by_id = _fetch_rows("daily_tests_bank")

        ordered_payloads: list[tuple[int, dict]] = []
        for bid in bank_ids_int:
            r = by_id.get(int(bid))
            if not r:
                continue
            payload = {
                "question": str(r.get("question") or "").strip(),
                "option_a": str(r.get("option_a") or "").strip(),
                "option_b": str(r.get("option_b") or "").strip(),
                "option_c": str(r.get("option_c") or "").strip(),
                "option_d": str(r.get("option_d") or "").strip(),
                "correct_option_index": int(r.get("correct_option_index") or 1),
                "question_type": r.get("question_type"),
                "level": str(r.get("level") or sess.get("level") or "").strip() or None,
                "created_by": int(r.get("created_by") or 0),
            }
            rich_payload = row_value(r, "payload_json")
            if rich_payload:
                try:
                    payload.update(json.loads(str(rich_payload)))
                except Exception:
                    payload["payload_json"] = rich_payload
            ordered_payloads.append((int(bid), payload))
            if len(ordered_payloads) >= qcount:
                break

        if not ordered_payloads:
            return 0

        rows_to_insert = []
        for qix, (bank_qid, payload) in enumerate(ordered_payloads, start=1):
            rows_to_insert.append(
                (
                    int(session_id),
                    int(qix),
                    int(bank_qid),
                    json.dumps(payload, ensure_ascii=False),
                )
            )

        cur.executemany(
            """
            INSERT INTO arena_group_questions_tmp(session_id, q_index, bank_question_id, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id, q_index) DO UPDATE SET
                bank_question_id=excluded.bank_question_id,
                payload_json=excluded.payload_json,
                promoted_at=NULL
            """,
            rows_to_insert,
        )
        conn.commit()
        return len(rows_to_insert)
    finally:
        conn.close()


def get_arena_group_session_questions(session_id: int) -> list[dict]:
    """
    Fetch selected rows and preserve teacher-selected order.
    New sessions use `arena_questions_bank`.
    Legacy sessions may still reference `daily_tests_bank` ids, so we fallback.
    """
    import json

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            SELECT bank_ids_json, question_count
            FROM arena_group_sessions
            WHERE id=?
            ''',
            (int(session_id),),
        )
        row = cur.fetchone()
        if not row:
            return []
        bank_ids = json.loads(row["bank_ids_json"] or "[]")
        qcount = int(row.get("question_count") or len(bank_ids))

        if not bank_ids:
            return []

        # Prefer runtime tmp snapshot if teacher already populated it.
        # If tmp isn't ready yet, fall back to the legacy sources.
        try:
            cur.execute(
                """
                SELECT q_index, bank_question_id, payload_json
                FROM arena_group_questions_tmp
                WHERE session_id=?
                ORDER BY q_index ASC
                """,
                (int(session_id),),
            )
            tmp_rows = cur.fetchall() or []
            if tmp_rows:
                ordered: list[dict] = []
                for tr in tmp_rows:
                    try:
                        payload = json.loads(tr["payload_json"] or "{}")
                    except Exception:
                        payload = {}
                    ordered.append(
                        {
                            "id": int(tr["bank_question_id"] or 0),
                            "question": payload.get("question"),
                            "option_a": payload.get("option_a"),
                            "option_b": payload.get("option_b"),
                            "option_c": payload.get("option_c"),
                            "option_d": payload.get("option_d"),
                            "correct_option_index": int(payload.get("correct_option_index") or 1),
                            "question_type": payload.get("question_type"),
                            "payload_json": tr["payload_json"],
                        }
                    )
                    if len(ordered) >= qcount:
                        break
                return ordered
        except Exception:
            pass

        placeholders = ",".join(["?"] * len(bank_ids))

        def _fetch_from(table: str) -> list[dict]:
            cur.execute(
                f'''
                SELECT id, question, option_a, option_b, option_c, option_d, correct_option_index, question_type, payload_json
                FROM {table}
                WHERE id IN ({placeholders})
                  AND active=1
                ''',
                tuple(int(x) for x in bank_ids),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]

        ordered: list[dict] = []
        arena_rows = []
        try:
            arena_rows = _fetch_from("arena_questions_bank")
        except Exception:
            arena_rows = []

        if arena_rows:
            by_id = {int(r["id"]): dict(r) for r in arena_rows}
            for bid in bank_ids:
                bdid = int(bid)
                if bdid in by_id:
                    ordered.append(by_id[bdid])
                if len(ordered) >= qcount:
                    break
            if ordered:
                return ordered

        # Legacy fallback: daily_tests_bank ids.
        legacy_rows = _fetch_from("daily_tests_bank")
        by_id = {int(r["id"]): dict(r) for r in legacy_rows}
        for bid in bank_ids:
            bdid = int(bid)
            if bdid in by_id:
                ordered.append(by_id[bdid])
            if len(ordered) >= qcount:
                break
        return ordered
    finally:
        conn.close()


def get_active_arena_group_session_by_group_id(group_id: int) -> dict | None:
    """
    Return the latest 'sent' arena session for a group.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            '''
            SELECT id, group_id, subject, level, question_count, bank_ids_json, created_by_teacher_id, status, created_at
            FROM arena_group_sessions
            WHERE group_id=? AND status IN ('ready', 'sent', 'running')
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            ''',
            (int(group_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def _scale_daily_test_type_counts(total_questions: int) -> dict[str, int]:
    """
    Integer counts proportional to the historical 20-question mix (5+10+3+2),
    summing exactly to total_questions.
    """
    n = max(1, int(total_questions))
    ratios = (5, 10, 3, 2)
    s = sum(ratios)
    raw = [r * n / s for r in ratios]
    floors = [int(x) for x in raw]
    deficit = n - sum(floors)
    order = sorted(range(4), key=lambda i: raw[i] - floors[i], reverse=True)
    for k in range(deficit):
        floors[order[k]] += 1
    return {
        "grammar_rules_count": floors[0],
        "grammar_sentence_count": floors[1],
        "find_mistake_count": floors[2],
        "error_spotting_count": floors[3],
    }


def ensure_daily_test_type_plan(subject: str, test_date: str, total_questions: int = 10) -> dict:
    """
    Ensure (test_date, subject) has a deterministic question-type mix.
    Counts scale from the 20-question reference mix (5+10+3+2) so the four
    counts always sum to total_questions (e.g. 10 → 3+5+1+1).
    """
    subject = (subject or "").strip().title()
    if subject not in ("English", "Russian"):
        subject = "English"

    conn = get_conn()
    cur = conn.cursor()
    scaled = _scale_daily_test_type_counts(total_questions)
    default = {
        **scaled,
        "total_questions": int(total_questions),
    }
    try:
        cur.execute(
            """
            SELECT grammar_rules_count, grammar_sentence_count, find_mistake_count, error_spotting_count, total_questions
            FROM daily_test_type_plans
            WHERE test_date=? AND subject=?
            """,
            (test_date, subject),
        )
        row = cur.fetchone()
        if row:
            return dict(row)

        cur.execute(
            """
            INSERT INTO daily_test_type_plans
            (test_date, subject, grammar_rules_count, grammar_sentence_count, find_mistake_count, error_spotting_count, total_questions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                test_date,
                subject,
                default["grammar_rules_count"],
                default["grammar_sentence_count"],
                default["find_mistake_count"],
                default["error_spotting_count"],
                default["total_questions"],
            ),
        )
        conn.commit()
        return default
    except Exception:
        # If insert fails due to races or schema mismatch, best-effort fallback.
        conn.rollback()
        return default
    finally:
        conn.close()


def get_daily_test_type_plan_for_subjects(test_date: str, subjects: list[str]) -> dict:
    """
    Return plan counts for the first subject (primarily to format a human message).
    """
    for s in subjects:
        plan = ensure_daily_test_type_plan(s, test_date)
        if plan:
            return plan
    return ensure_daily_test_type_plan("English", test_date)


def dedupe_tests():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        DELETE FROM tests
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM tests
            GROUP BY subject, question, option_a, option_b, option_c, option_d, correct_option
        )
    ''')
    conn.commit()
    conn.close()


def prepare_user_for_new_test(user_id, subject):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('''
            UPDATE users
            SET subject=?, login_type=1, access_enabled=0, password_used=0
            WHERE id=?
        ''', (subject, user_id))
        conn.commit()
        conn.close()


# ====================== ASOSIY FUNKSIYALAR ======================

# ---- Login brute-force throttle (shared by web /auth/login and bot logins) ----
# Persistent (DB) sliding-window counter per throttle key so limits survive
# restarts and apply across all processes that share the database.
LOGIN_THROTTLE_MAX_FAILURES = max(1, int(os.getenv("LOGIN_THROTTLE_MAX_FAILURES", "5") or 5))
LOGIN_THROTTLE_WINDOW_SEC = max(60, int(os.getenv("LOGIN_THROTTLE_WINDOW_SEC", "900") or 900))
_LOGIN_THROTTLE_SCHEMA_READY = False


def ensure_login_throttle_schema():
    global _LOGIN_THROTTLE_SCHEMA_READY
    if _LOGIN_THROTTLE_SCHEMA_READY:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS login_throttle (
                throttle_key TEXT PRIMARY KEY,
                failed_count INTEGER NOT NULL DEFAULT 0,
                window_started_at BIGINT NOT NULL DEFAULT 0,
                last_failed_at BIGINT NOT NULL DEFAULT 0
            )
        ''')
        conn.commit()
        _LOGIN_THROTTLE_SCHEMA_READY = True
    finally:
        conn.close()


def is_login_throttled(throttle_key: str, max_failures: int | None = None) -> bool:
    """True while the key has >= max_failures failures inside the window.

    Fails open (allows login) on unexpected DB errors so a throttle-table
    problem can never lock the whole platform out.
    """
    if not throttle_key:
        return False
    limit = max(1, int(max_failures or LOGIN_THROTTLE_MAX_FAILURES))
    try:
        ensure_login_throttle_schema()
        now = int(time.time())
        with DB_WRITE_LOCK:
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT failed_count, window_started_at FROM login_throttle WHERE throttle_key=?",
                    (throttle_key,),
                )
                row = cur.fetchone()
                if not row:
                    return False
                count = int(row["failed_count"] or 0)
                started = int(row["window_started_at"] or 0)
                if now - started >= LOGIN_THROTTLE_WINDOW_SEC:
                    cur.execute("DELETE FROM login_throttle WHERE throttle_key=?", (throttle_key,))
                    conn.commit()
                    return False
                return count >= limit
            finally:
                conn.close()
    except Exception:
        logger.exception("is_login_throttled failed (fail-open) key=%s", throttle_key)
        return False


def record_login_failure(throttle_key: str) -> None:
    if not throttle_key:
        return
    try:
        ensure_login_throttle_schema()
        now = int(time.time())
        with DB_WRITE_LOCK:
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute(
                    "SELECT failed_count, window_started_at FROM login_throttle WHERE throttle_key=?",
                    (throttle_key,),
                )
                row = cur.fetchone()
                if row and now - int(row["window_started_at"] or 0) >= LOGIN_THROTTLE_WINDOW_SEC:
                    row = None
                if row:
                    cur.execute(
                        "UPDATE login_throttle SET failed_count=?, last_failed_at=? WHERE throttle_key=?",
                        (int(row["failed_count"] or 0) + 1, now, throttle_key),
                    )
                else:
                    cur.execute(
                        "INSERT INTO login_throttle (throttle_key, failed_count, window_started_at, last_failed_at) VALUES (?,1,?,?)",
                        (throttle_key, now, now),
                    )
                conn.commit()
            finally:
                conn.close()
    except Exception:
        logger.exception("record_login_failure failed key=%s", throttle_key)


def clear_login_throttle(throttle_key: str) -> None:
    if not throttle_key:
        return
    try:
        with DB_WRITE_LOCK:
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM login_throttle WHERE throttle_key=?", (throttle_key,))
                conn.commit()
            finally:
                conn.close()
    except Exception:
        logger.exception("clear_login_throttle failed key=%s", throttle_key)


def increment_failed_logins(user_id: int) -> None:
    """Keep the legacy users.failed_logins column in sync for admin visibility."""
    try:
        with DB_WRITE_LOCK:
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute("UPDATE users SET failed_logins=failed_logins+1 WHERE id=?", (int(user_id),))
                conn.commit()
            finally:
                conn.close()
    except Exception:
        logger.exception("increment_failed_logins failed user_id=%s", user_id)


def clear_failed_logins(user_id: int) -> None:
    try:
        with DB_WRITE_LOCK:
            conn = get_conn()
            cur = conn.cursor()
            try:
                cur.execute("UPDATE users SET failed_logins=0 WHERE id=?", (int(user_id),))
                conn.commit()
            finally:
                conn.close()
    except Exception:
        logger.exception("clear_failed_logins failed user_id=%s", user_id)


def create_user(first_name, last_name, phone, subject, login_type, owner_admin_id: int | None = None, parent_phone: str | None = None):
    logger.info(f"db.create_user(login_type={login_type}, subject={subject}, first_name={first_name}, last_name={last_name})")
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Login ID va parol generatsiya (kriptografik tasodifiy)
        import secrets as _secrets, string as _string
        while True:
            login_id = 'ST' + ''.join(_secrets.choice(_string.ascii_uppercase + _string.digits) for _ in range(4))
            cur.execute("SELECT 1 FROM users WHERE login_id=?", (login_id,))
            if not cur.fetchone(): break

        password = _generate_secure_password(6)

        cur.execute('''
            INSERT INTO users (login_id, password, first_name, last_name, phone, parent_phone, subject, login_type, blocked, access_enabled, owner_admin_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        ''', (
            login_id,
            hash_password(password),
            first_name,
            last_name,
            phone,
            parent_phone,
            subject,
            login_type,
            1 if login_type == 2 else 0,
            1 if login_type == 3 else 0,
            owner_admin_id,
        ))
        row = cur.fetchone()
        conn.commit()
        return {'id': row["id"], 'login_id': login_id, 'password': password}
    finally:
        conn.close()

def verify_login(login_id, password):
    logger.info(f"db.verify_login(login_id={login_id})")
    conn = get_conn()
    cur = conn.cursor()
    login_id_clean = (login_id or "").strip().upper()
    password_clean = (password or "").strip()
    throttle_key = f"login:{login_id_clean}" if login_id_clean else ""
    if throttle_key and is_login_throttled(throttle_key):
        conn.close()
        return None, 'throttled'
    cur.execute("SELECT * FROM users WHERE UPPER(login_id)=?", (login_id_clean,))
    user = cur.fetchone()
    conn.close()

    if not user:
        record_login_failure(throttle_key)
        return None, 'not_found'
    if user['blocked']:
        return None, 'blocked'
    stored_password = (user['password'] or "").strip()
    if not verify_password(password_clean, stored_password):
        record_login_failure(throttle_key)
        increment_failed_logins(int(user['id'] or 0))
        return None, 'invalid'
    clear_login_throttle(throttle_key)
    clear_failed_logins(int(user['id'] or 0))
    return dict(user), 'ok'

def activate_user(user_id, telegram_id):
    logger.info(f"db.activate_user(user_id={user_id}, telegram_id={telegram_id})")
    with DB_WRITE_LOCK:
        conn = get_conn()
        try:
            cur = conn.cursor()
            # Remove telegram_id from any other user so UNIQUE is preserved
            cur.execute("UPDATE users SET telegram_id=NULL WHERE telegram_id=? AND id!=?", (telegram_id, user_id))
            cur.execute('''
                UPDATE users SET telegram_id=?, failed_logins=0, logged_in=1, last_login_at=CURRENT_TIMESTAMP, last_activity=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (telegram_id, user_id))
            conn.commit()
        finally:
            conn.close()


def block_user(user_id):
    """Block user by setting blocked=1"""
    logger.info(f"db.block_user(user_id={user_id})")
    with DB_WRITE_LOCK:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET blocked=1 WHERE id=?", (user_id,))
            conn.commit()
        finally:
            conn.close()


def unblock_user(user_id):
    """Unblock user by setting blocked=0"""
    logger.info(f"db.unblock_user(user_id={user_id})")
    with DB_WRITE_LOCK:
        conn = get_conn()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET blocked=0 WHERE id=?", (user_id,))
            conn.commit()
        finally:
            conn.close()


def hard_delete_user_profile(user_id: int) -> bool:
    """Hard-delete user and operational relations from DB."""
    logger.info("db.hard_delete_user_profile(user_id=%s)", user_id)
    ensure_support_lessons_schema()
    ensure_admin_student_shares_schema()
    ensure_temporary_group_assignments_schema()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            uid = int(user_id)
            cur.execute("SELECT telegram_id, login_type FROM users WHERE id=?", (uid,))
            urow = cur.fetchone()
            if not urow:
                return False

            ukeys = set(urow.keys()) if hasattr(urow, "keys") else set()
            telegram_id = urow["telegram_id"] if "telegram_id" in ukeys else None
            telegram_id_s = str(telegram_id) if telegram_id is not None else None
            login_type = int((urow["login_type"] if "login_type" in ukeys else 0) or 0)
            is_student = login_type in (1, 2)
            is_teacher = login_type == 3

            # Student relations.
            if is_student:
                cur.execute("UPDATE users SET group_id=NULL WHERE id=?", (uid,))
                cur.execute("DELETE FROM user_groups WHERE user_id=?", (uid,))
                cur.execute(
                    """
                    UPDATE admin_student_shares
                    SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP
                    WHERE student_id=? AND status='active'
                    """,
                    (uid,),
                )
                # Remove all share rows for this student (runtime relation cleanup).
                cur.execute("DELETE FROM admin_student_shares WHERE student_id=?", (uid,))

            # Teacher relations + delete teacher-owned groups.
            if is_teacher:
                cur.execute("SELECT id FROM groups WHERE teacher_id=?", (uid,))
                teacher_group_ids = [int((dict(r) if isinstance(r, dict) else {"id": r[0]}).get("id")) for r in (cur.fetchall() or [])]
                for gid in teacher_group_ids:
                    cur.execute("UPDATE users SET group_id=NULL WHERE group_id=?", (gid,))
                    cur.execute("DELETE FROM user_groups WHERE group_id=?", (gid,))
                    for tbl in ("attendance", "attendance_sessions", "monthly_payments", "overdue_penalty_log"):
                        try:
                            cur.execute(f"DELETE FROM {tbl} WHERE group_id=?", (gid,))
                        except Exception:
                            pass
                    try:
                        cur.execute("DELETE FROM temporary_group_assignments WHERE group_id=?", (gid,))
                    except Exception:
                        pass
                    try:
                        cur.execute("DELETE FROM arena_group_sessions WHERE group_id=?", (gid,))
                    except Exception:
                        pass
                    cur.execute("DELETE FROM groups WHERE id=?", (gid,))
                cur.execute("DELETE FROM user_groups WHERE user_id=?", (uid,))
                # If assigned as teacher elsewhere, unlink.
                cur.execute("UPDATE groups SET teacher_id=NULL WHERE teacher_id=?", (uid,))

            # Support/lesson cleanup (best-effort).
            try:
                if telegram_id_s is not None:
                    cur.execute(
                        """
                        DELETE FROM lesson_reminders
                        WHERE booking_id IN (
                            SELECT id FROM lesson_bookings
                            WHERE student_user_id=?
                        ) OR telegram_id=?
                        """,
                        (uid, telegram_id_s),
                    )
                    cur.execute("DELETE FROM lesson_waitlist WHERE telegram_id=?", (telegram_id_s,))
                    cur.execute("DELETE FROM lesson_users WHERE telegram_id=?", (telegram_id_s,))
                    cur.execute("DELETE FROM lesson_bookings WHERE student_user_id=? OR student_telegram_id=?", (uid, telegram_id_s))
                else:
                    cur.execute(
                        """
                        DELETE FROM lesson_reminders
                        WHERE booking_id IN (
                            SELECT id FROM lesson_bookings
                            WHERE student_user_id=?
                        )
                        """,
                        (uid,),
                    )
                    cur.execute("DELETE FROM lesson_bookings WHERE student_user_id=?", (uid,))
            except Exception:
                logger.exception("hard_delete_user_profile: support cleanup failed uid=%s", uid)
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur = conn.cursor()

            # Broad cleanup by common user-id columns to ensure profile disappears from runtime/rating areas.
            target_cols = (
                "user_id",
                "student_user_id",
                "teacher_id",
                "owner_teacher_id",
                "temp_teacher_id",
                "opponent_user_id",
                "last_opponent_user_id",
                "created_by_user_id",
                "added_by",
                "admin_id",
                "handled_by_admin_id",
            )
            try:
                if _is_postgres_enabled():
                    cur.execute(
                        """
                        SELECT table_name, column_name
                        FROM information_schema.columns
                        WHERE table_schema='public'
                          AND column_name = ANY(%s)
                        """,
                        (list(target_cols),),
                    )
                    rows = cur.fetchall() or []
                else:
                    rows = []
                for r in rows:
                    table_name = (dict(r) if isinstance(r, dict) else {"table_name": r[0]}).get("table_name")
                    column_name = (dict(r) if isinstance(r, dict) else {"column_name": r[1]}).get("column_name")
                    if not table_name or not column_name:
                        continue
                    if table_name in ("users", "groups", "web_student_reviews"):
                        continue
                    try:
                        cur.execute(f"DELETE FROM {table_name} WHERE {column_name}=?", (uid,))
                    except Exception:
                        continue
            except Exception:
                logger.exception("hard_delete_user_profile: broad cleanup scan failed uid=%s", uid)

            # Final hard delete user row.
            cur.execute("DELETE FROM users WHERE id=?", (uid,))
            changed = int(cur.rowcount or 0) > 0
            conn.commit()
            return changed
        except Exception:
            logger.exception("hard_delete_user_profile failed user_id=%s", user_id)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            conn.close()


def soft_delete_user_profile(user_id: int) -> bool:
    """Backward-compatible alias: now performs hard delete."""
    return hard_delete_user_profile(user_id)


def logout_user_by_telegram(telegram_id: str):
    """User-initiated logout: unlink telegram_id so they can login again."""
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        # Clear telegram link and allow re-login with the same login/password if needed
        cur.execute(
            "UPDATE users SET telegram_id=NULL, logged_in=0, password_used=0 WHERE telegram_id=?",
            (telegram_id,)
        )
        conn.commit()
        conn.close()


def update_user_telegram_id(user_id: int, telegram_id: str):
    """Update user's telegram_id"""
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE users SET telegram_id=? WHERE id=?", (telegram_id, user_id))
            conn.commit()
            logger.info(f"db.update_user_telegram_id: set telegram_id={telegram_id} for user_id={user_id}")
        except psycopg.IntegrityError:
            # This happens when telegram_id UNIQUE constraint is violated
            logger.warning(f"db.update_user_telegram_id: telegram_id {telegram_id} already used by another user")
            conn.rollback()
            raise
        except Exception:
            logger.exception("db.update_user_telegram_id: unexpected error")
            conn.rollback()
            raise
        finally:
            conn.close()


# ====================== MOBILE TELEGRAM APP LOGIN ======================

def ensure_mobile_telegram_login_schema() -> None:
    """Create the short-lived hand-off table used by the native student app.

    The app creates an opaque request token, the student bot approves it for
    the Telegram account currently signed in to the bot, and the API consumes
    it exactly once.  Keeping this state in Postgres lets the independently
    deployed API and bot processes coordinate without sharing a bot token or
    a JWT through a Telegram deep link.
    """
    schema_key = "mobile_telegram_login"
    if _schema_ready(schema_key):
        return
    with DB_WRITE_LOCK:
        if _schema_ready(schema_key):
            return
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_telegram_login_requests (
                    id BIGSERIAL PRIMARY KEY,
                    request_token TEXT UNIQUE NOT NULL,
                    device_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
                    telegram_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMPTZ NOT NULL,
                    approved_at TIMESTAMPTZ,
                    consumed_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_mobile_telegram_login_lookup
                ON mobile_telegram_login_requests (request_token, status, expires_at)
                """
            )
            conn.commit()
            _mark_schema_ready(schema_key)
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()


def create_mobile_telegram_login_request(
    request_token: str,
    device_id: str,
    expires_at: datetime,
) -> None:
    """Persist a pending native-app login request.

    ``request_token`` is generated by the API with cryptographic randomness;
    this function deliberately does not generate or expose credentials.
    """
    ensure_mobile_telegram_login_schema()
    token = str(request_token or "").strip()
    device = str(device_id or "").strip()
    if not token or not device:
        raise ValueError("request_token and device_id are required")
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            # Retain just enough history to diagnose an expired hand-off while
            # preventing this tiny coordination table from accumulating rows.
            cur.execute(
                """
                DELETE FROM mobile_telegram_login_requests
                WHERE expires_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
                   OR consumed_at < CURRENT_TIMESTAMP - INTERVAL '1 day'
                """
            )
            cur.execute(
                """
                INSERT INTO mobile_telegram_login_requests
                    (request_token, device_id, status, expires_at)
                VALUES (?, ?, 'pending', ?)
                """,
                (token, device, expires_at),
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()


def get_mobile_telegram_login_request(request_token: str) -> dict | None:
    """Return a hand-off request without exposing it to untrusted clients."""
    ensure_mobile_telegram_login_schema()
    token = str(request_token or "").strip()
    if not token:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM mobile_telegram_login_requests WHERE request_token=? LIMIT 1",
            (token,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def approve_mobile_telegram_login_request(
    request_token: str,
    *,
    user_id: int,
    telegram_id: str | int,
) -> bool:
    """Approve one pending request from the student bot.

    The bot supplies the authenticated Telegram sender and the account it has
    already resolved for that sender.  Approval is atomic and refuses expired,
    previously approved, or consumed requests.
    """
    ensure_mobile_telegram_login_schema()
    token = str(request_token or "").strip()
    uid = int(user_id or 0)
    tg = str(telegram_id or "").strip()
    if not token or uid <= 0 or not tg:
        return False
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE mobile_telegram_login_requests
                SET status='approved',
                    user_id=?,
                    telegram_id=?,
                    approved_at=CURRENT_TIMESTAMP
                WHERE request_token=?
                  AND status='pending'
                  AND user_id IS NULL
                  AND consumed_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                RETURNING id
                """,
                (uid, tg, token),
            )
            approved = cur.fetchone() is not None
            conn.commit()
            return approved
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()


def consume_mobile_telegram_login_request(
    request_token: str,
    *,
    device_id: str,
) -> dict | None:
    """Atomically exchange an approved request for its linked student ID."""
    ensure_mobile_telegram_login_schema()
    token = str(request_token or "").strip()
    device = str(device_id or "").strip()
    if not token or not device:
        return None
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE mobile_telegram_login_requests
                SET status='consumed', consumed_at=CURRENT_TIMESTAMP
                WHERE request_token=?
                  AND device_id=?
                  AND status='approved'
                  AND user_id IS NOT NULL
                  AND consumed_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                RETURNING user_id, telegram_id
                """,
                (token, device),
            )
            row = cur.fetchone()
            conn.commit()
            return dict(row) if row else None
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()

def enable_access(user_id, days=None):
    logger.info(f"db.enable_access(user_id={user_id}, days={days})")
    conn = get_conn()
    cur = conn.cursor()
    if days is None:
        cur.execute("UPDATE users SET access_enabled=1, access_expires_at=NULL, blocked=0 WHERE id=?", (user_id,))
    else:
        from datetime import datetime, timedelta
        expires = (datetime.utcnow() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        cur.execute("UPDATE users SET access_enabled=1, access_expires_at=?, blocked=0 WHERE id=?", (expires, user_id))
    conn.commit()
    conn.close()

def disable_access(user_id):
    logger.info(f"db.disable_access(user_id={user_id})")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET access_enabled=0, access_expires_at=NULL, blocked=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

def is_access_active(user):
    if not user or not user.get('access_enabled'):
        return False
    try:
        login_type = int(user.get("login_type") or 0)
    except Exception:
        login_type = 0
    # Part-1 policy: students without any active group must be blocked from bot usage.
    if login_type in (1, 2):
        user_id = int(user.get("id") or 0)
        if user_id <= 0:
            return False
        if not check_user_group_access(int(user_id)):
            return False
    expires = user.get('access_expires_at')
    if not expires:
        return True
    from datetime import datetime
    try:
        expires_dt = datetime.strptime(expires, '%Y-%m-%d %H:%M:%S')
        return datetime.utcnow() <= expires_dt
    except Exception:
        return False

def reset_user_password(user_id, password):
    logger.info(f"db.reset_user_password(user_id={user_id})")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password=?, password_used=0 WHERE id=?", (hash_password(password), user_id))
    conn.commit()
    conn.close()


def update_user_language(user_id, lang):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET language=? WHERE id=?", (lang, user_id))
    conn.commit()
    conn.close()


def update_user_subjects(user_id: int, subjects_list: list):
    """Update user's subjects as comma separated string"""
    clean_subjects = [str(s or "").strip() for s in (subjects_list or []) if str(s or "").strip()]
    subjects_str = ",".join(clean_subjects)
    with DB_WRITE_LOCK:
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        old_subject_count = _get_user_subject_count_tx(cur, int(user_id))
        _ensure_user_dpoints_row(cur, int(user_id))
        cur.execute("UPDATE users SET subject=? WHERE id=?", (subjects_str, user_id))
        if _is_postgres_enabled():
            cur.execute("DELETE FROM user_subject WHERE user_id=?", (int(user_id),))
            for subject in clean_subjects:
                cur.execute(
                    "INSERT INTO user_subject (user_id, subject) VALUES (?, ?) ON CONFLICT DO NOTHING",
                    (int(user_id), subject),
                )
        new_subject_count = _get_user_subject_count_tx(cur, int(user_id))
        _reanchor_dcoin_on_subject_count_change(cur, int(user_id), old_subject_count, new_subject_count)
        conn.commit()
        conn.close()


def _sync_user_subjects_from_active_groups_tx(cur, user_id: int) -> list[str]:
    """Keep student fanlari equal to currently active group fanlari."""
    uid = int(user_id)
    cur.execute("SELECT login_type, subject FROM users WHERE id=?", (uid,))
    user_row = cur.fetchone() or {}
    login_type = int(_safe_get(user_row, "login_type") or 0)
    cur.execute(
        """
        SELECT DISTINCT g.subject
        FROM groups g
        JOIN user_groups ug ON g.id = ug.group_id
        WHERE ug.user_id=?
          AND g.subject IS NOT NULL
          AND TRIM(g.subject) != ''
          AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT)) = '')
        ORDER BY g.subject
        """,
        (uid,),
    )
    subjects: list[str] = []
    for row in (cur.fetchall() or []):
        subject = str(_safe_get(row, "subject") or "").strip()
        if subject and subject not in subjects:
            subjects.append(subject)
    if not subjects and login_type not in (1, 2, 6):
        for part in str(_safe_get(user_row, "subject") or "").split(","):
            subject = part.strip()
            if subject and subject not in subjects:
                subjects.append(subject)
    next_subject_csv = ",".join(subjects)
    if str(_safe_get(user_row, "subject") or "") != next_subject_csv:
        cur.execute("UPDATE users SET subject=? WHERE id=?", (next_subject_csv, uid))
    if _is_postgres_enabled():
        cur.execute("DELETE FROM user_subject WHERE user_id=?", (uid,))
        for subject in subjects:
            cur.execute(
                "INSERT INTO user_subject (user_id, subject) VALUES (?, ?) ON CONFLICT DO NOTHING",
                (uid, subject),
            )
    return subjects


def update_user_subject(user_id: int, subject: str):
    """Update user's subject"""
    update_user_subjects(int(user_id), [str(subject or "").strip() or "English"])


def set_user_language(user_id: int, lang: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET language=? WHERE id=?", (lang, user_id))
    conn.commit()
    conn.close()


def update_user_level(user_id: int, level: str):
    """Update user's level"""
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET level=? WHERE id=?", (level, user_id))
        conn.commit()
        conn.close()

def update_user_social_links(user_id: int, instagram_url: str | None, telegram_url: str | None):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET instagram_url=?, telegram_url=? WHERE id=?", (instagram_url, telegram_url, user_id))
        conn.commit()
        conn.close()

def set_user_language_by_telegram(telegram_id, lang):
    conn = get_conn()
    cur = conn.cursor()
    # Try matching stored telegram_id as given
    cur.execute("SELECT id FROM users WHERE telegram_id=?", (telegram_id,))
    row = cur.fetchone()
    # If not found, try integer version (some records may store integers)
    if not row:
        try:
            maybe_int = int(telegram_id)
            cur.execute("SELECT id FROM users WHERE telegram_id=?", (maybe_int,))
            row = cur.fetchone()
        except Exception:
            row = None

    if not row:
        conn.close()
        return False
    uid = row['id']
    cur.execute("UPDATE users SET language=? WHERE id=?", (lang, uid))
    conn.commit()
    conn.close()
    return True

def get_user_by_telegram(telegram_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    row = cur.fetchone()
    # Fallback: maybe telegram_id stored as integer in some rows
    if not row:
        try:
            maybe_int = int(telegram_id)
            cur.execute("SELECT * FROM users WHERE telegram_id=?", (maybe_int,))
            row = cur.fetchone()
        except Exception:
            row = None
    conn.close()
    return dict(row) if row else None

def get_user_by_login(login_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE UPPER(login_id)=?", (login_id.strip().upper(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_login_id(login_id):
    return get_user_by_login(login_id)

def get_user_by_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_name_search(name: str, limit: int = 20) -> list[dict]:
    """Case-insensitive search by first name, last name, or full name (SQLite/Postgres)."""
    name = (name or "").strip()
    if len(name) < 1:
        return []
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{name.lower()}%"
    cur.execute(
        """
        SELECT * FROM users
        WHERE LOWER(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) LIKE ?
           OR LOWER(COALESCE(first_name, '')) LIKE ?
           OR LOWER(COALESCE(last_name, '')) LIKE ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (like, like, like, int(limit)),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def search_student_users_for_group_pick(query: str, limit: int = 500) -> list[dict]:
    """
    DB-backed search for students (login_type 1/2/6) when adding to a group.
    Matches first/last/full name, login_id, or telegram_id substring.
    Caller should apply admin scope via _scope_users_for_admin.
    """
    q = (query or "").strip()
    if len(q) < 1:
        return []
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{q.lower()}%"
    tg_like = f"%{q}%"
    lim = max(1, min(2000, int(limit)))
    cur.execute(
        """
        SELECT * FROM users
        WHERE login_type IN (1, 2, 6)
          AND (
            LOWER(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) LIKE ?
            OR LOWER(COALESCE(first_name, '')) LIKE ?
            OR LOWER(COALESCE(last_name, '')) LIKE ?
            OR LOWER(COALESCE(login_id, '')) LIKE ?
            OR CAST(telegram_id AS TEXT) LIKE ?
          )
        ORDER BY id DESC
        LIMIT ?
        """,
        (like, like, like, like, tg_like, lim),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_placement_session(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT test_in_progress, test_subject, test_question_index, test_score, test_questions FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    questions = []
    if row['test_questions']:
        try:
            import json
            questions = json.loads(row['test_questions'])
        except Exception:
            questions = []
    return {
        'active': bool(row['test_in_progress']),
        'subject': row['test_subject'],
        'question_index': row['test_question_index'] or 0,
        'score': row['test_score'] or 0,
        'questions': questions,
    }


def save_placement_session(user_id, session):
    conn = get_conn()
    cur = conn.cursor()
    import json
    questions_json = json.dumps(session.get('questions', []))
    cur.execute('''
        UPDATE users SET test_in_progress=?, test_subject=?, test_question_index=?, test_score=?, test_questions=?
        WHERE id=?
    ''', (
        1 if session.get('active') else 0,
        session.get('subject'),
        session.get('question_index', 0),
        session.get('score', 0),
        questions_json,
        user_id,
    ))
    conn.commit()
    conn.close()


def clear_placement_session(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        UPDATE users SET test_in_progress=0, test_subject=NULL, test_question_index=0, test_score=0, test_questions=NULL
        WHERE id=?
    ''', (user_id,))
    conn.commit()
    conn.close()


def get_tests_by_subject(subject):
    conn = get_conn()
    cur = conn.cursor()
    raw = str(subject or "").strip()
    low = raw.lower()
    aliases = {raw} if raw else set()
    if low in {"english", "eng", "ingliz", "en"}:
        aliases.update({"English", "english", "ENG", "Ingliz", "ingliz", "en"})
    elif low in {"russian", "rus", "ru", "русский", "russian language"}:
        aliases.update({"Russian", "russian", "RUS", "rus", "ru", "Русский", "русский"})

    rows = []
    if aliases:
        placeholders = ",".join(["?"] * len(aliases))
        query = f"SELECT * FROM tests WHERE LOWER(TRIM(subject)) IN ({placeholders})"
        cur.execute(query, tuple(str(item).strip().lower() for item in aliases))
        rows = [dict(row) for row in cur.fetchall()]
    if not rows and raw:
        # Backward-compatible fallback for legacy rows with inconsistent casing/spacing.
        cur.execute("SELECT * FROM tests WHERE subject=?", (raw,))
        rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows
def delete_all_tests():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM tests")
    conn.commit()
    conn.close()

def delete_tests_by_subject(subject: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM tests WHERE subject=?", (subject,))
    conn.commit()
    conn.close()
def get_test_by_id(test_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tests WHERE id=?", (test_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_test_by_subject_and_question(subject, question):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM tests WHERE LOWER(TRIM(subject))=LOWER(TRIM(?)) AND question=?",
        (subject, question),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def save_test_result(user_id, subject, score, level, max_score: int = 500):
    """Placement test uses score 0..500 (50 questions x 10)."""
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO test_results (user_id, subject, score, level, max_score)
            VALUES (?,?,?,?,?)
        ''', (user_id, subject, score, level, int(max_score)))
        conn.commit()
        conn.close()


def get_latest_test_result(user_id: int) -> dict | None:
    """Most recent test_results row for user (any subject)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM test_results
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (int(user_id),),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def extract_cefr_level_code(level_raw: str) -> str:
    """Normalize level strings (e.g. 'A2 (Elementary)') to CEFR code for group matching."""
    s = (level_raw or "").strip().upper()
    for code in ("MIXED", "C2", "C1", "B2", "B1", "A2", "A1"):
        if code in s:
            return code
    if len(s) >= 2 and s[0] in "ABC" and s[1].isdigit():
        return s[:2]
    parts = s.split()
    return parts[0] if parts else ""


def get_latest_test_result_for_subject(user_id: int, subject: str) -> dict | None:
    """Oxirgi placement/natija yozuvi (fan bo‘yicha)."""
    subj = (subject or "").strip()
    if not subj:
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT * FROM test_results
        WHERE user_id = ? AND LOWER(TRIM(subject)) = LOWER(?)
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (int(user_id), subj.strip()),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def insert_test(subject, question, option_a, option_b, option_c, option_d, correct_option):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO tests (subject, question, option_a, option_b, option_c, option_d, correct_option)
        VALUES (?,?,?,?,?,?,?)
    ''', (subject, question, option_a, option_b, option_c, option_d, correct_option))
    conn.commit()
    conn.close()

def has_tests():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM tests LIMIT 1")
    result = cur.fetchone()
    conn.close()
    return result is not None


def get_test_count():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as c FROM tests")
    row = cur.fetchone()
    conn.close()
    return row['c'] if row else 0


def get_all_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_all_teachers():
    """Get all users with login_type=3 (teachers)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE login_type=3 ORDER BY created_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_all_students():
    """Get all users with login_type=2 (students)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE login_type=2 ORDER BY created_at DESC")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

def get_recent_results(limit: int = 15):
    conn = get_conn()
    cur = conn.cursor()
    lim = max(1, min(100, int(limit or 15)))
    # Placement test results are stored in `test_results` with `max_score=500`.
    # For backward compatibility (older DBs), detect if `max_score` column exists.
    has_max_score = False
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name='test_results' AND column_name='max_score'
                LIMIT 1
                """
            )
            has_max_score = cur.fetchone() is not None
        else:
            cur.execute("PRAGMA table_info(test_results)")
            cols = {str(r["name"]) for r in cur.fetchall()}
            has_max_score = "max_score" in cols
    except Exception:
        has_max_score = False

    if has_max_score:
        cur.execute(
            "SELECT * FROM test_results WHERE max_score=? ORDER BY created_at DESC LIMIT ?",
            (500, lim),
        )
    else:
        cur.execute("SELECT * FROM test_results ORDER BY created_at DESC LIMIT ?", (lim,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows

def get_recent_users():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 50")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


# ====================== GURUHLAR BOSHQARUVI ======================

def create_group(
    name,
    teacher_id,
    level='All',
    subject=None,
    lesson_date=None,
    lesson_start=None,
    lesson_end=None,
    tz='Asia/Tashkent',
    owner_admin_id: int | None = None,
    extra_subjects: list[str] | None = None,
    course_id: int | None = None,
    course_title: str | None = None,
    monthly_fee_text: str | None = None,
    telegram_group_url: str | None = None,
    pricing_type: str | None = None,
    lang: str | None = None,
):
    """Yangi guruhi yaratish"""
    logger.info(
        f"create_group called with: name={name}, teacher_id={teacher_id}, level={level}, subject={subject}, "
        f"lesson_date={lesson_date}, lesson_start={lesson_start}, lesson_end={lesson_end}, tz={tz}, owner_admin_id={owner_admin_id}, "
        f"course_id={course_id}, course_title={course_title}, monthly_fee_text={monthly_fee_text}, telegram_group_url={telegram_group_url}"
    )
    ensure_group_extra_subjects_schema()

    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        group_id = 0
        effective_lang = str(lang or "uz").strip().lower()
        if effective_lang not in ("uz", "ru"):
            effective_lang = "uz"
        try:
            cur.execute(
                """
                INSERT INTO groups (
                    name, teacher_id, level, subject, lesson_date, lesson_start, lesson_end, tz, owner_admin_id,
                    course_id, course_title, monthly_fee_text, telegram_group_url, pricing_type, lang
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                """,
                (
                    name,
                    teacher_id,
                    level,
                    subject,
                    lesson_date,
                    lesson_start,
                    lesson_end,
                    tz,
                    owner_admin_id,
                    int(course_id) if course_id is not None and int(course_id) > 0 else None,
                    str(course_title or "").strip() or None,
                    str(monthly_fee_text or "").strip() or None,
                    str(telegram_group_url or "").strip() or None,
                    str(pricing_type or "group").strip() or "group",
                    effective_lang,
                ),
            )
            row = cur.fetchone()
            if row:
                group_id = int((row.get("id") if isinstance(row, dict) else row[0]) or 0)
        except Exception:
            cur.execute(
                """
                INSERT INTO groups (
                    name, teacher_id, level, subject, lesson_date, lesson_start, lesson_end, tz, owner_admin_id,
                    course_id, course_title, monthly_fee_text, telegram_group_url, pricing_type, lang
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    teacher_id,
                    level,
                    subject,
                    lesson_date,
                    lesson_start,
                    lesson_end,
                    tz,
                    owner_admin_id,
                    int(course_id) if course_id is not None and int(course_id) > 0 else None,
                    str(course_title or "").strip() or None,
                    str(monthly_fee_text or "").strip() or None,
                    str(telegram_group_url or "").strip() or None,
                    str(pricing_type or "group").strip() or "group",
                    effective_lang,
                ),
            )
            group_id = int(getattr(cur, "lastrowid", 0) or 0)
            if group_id <= 0 and _is_postgres_enabled():
                cur.execute("SELECT id FROM groups ORDER BY id DESC LIMIT 1")
                row = _row_to_dict(cur.fetchone())
                group_id = int(row.get("id") or 0)

        if group_id > 0:
            normalized_lang = str(lang or "uz").strip().lower()
            if normalized_lang not in {"uz", "ru"}:
                normalized_lang = "uz"
            try:
                cur.execute("UPDATE groups SET lang=? WHERE id=?", (normalized_lang, int(group_id)))
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
            cleaned: list[str] = []
            seen: set[str] = set()
            for item in (extra_subjects or []):
                value = str(item or "").strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                cleaned.append(value)
            cur.execute("DELETE FROM group_extra_subjects WHERE group_id=?", (int(group_id),))
            for idx, value in enumerate(cleaned):
                if _is_postgres_enabled():
                    cur.execute(
                        """
                        INSERT INTO group_extra_subjects(group_id, subject, sort_order)
                        VALUES (?, ?, ?)
                        ON CONFLICT(group_id, subject)
                        DO UPDATE SET sort_order=excluded.sort_order
                        """,
                        (int(group_id), value, idx),
                    )
                else:
                    cur.execute(
                        """
                        INSERT OR REPLACE INTO group_extra_subjects(group_id, subject, sort_order)
                        VALUES (?, ?, ?)
                        """,
                        (int(group_id), value, idx),
                    )
        conn.commit()
        conn.close()

        logger.info(f"Group created successfully with ID={group_id}")
        return group_id

def get_group(group_id):
    """Guruhni ID bo'yicha olish"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM groups WHERE id=?", (group_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_groups_by_teacher(teacher_id):
    """O'qituvchining barcha guruhlarini olish"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM groups WHERE teacher_id=? ORDER BY name", (teacher_id,))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


_TEMP_ASSIGNMENT_TZ = pytz.timezone("Asia/Tashkent")
_TEMP_ASSIGNMENT_ACCESS_BEFORE_MINUTES = 10
_TEMP_ASSIGNMENT_ACCESS_AFTER_HOURS = 12


def _temporary_assignment_hhmm(value: Any) -> tuple[int, int] | None:
    text = str(value or "").strip()
    if not re.match(r"^\d{2}:\d{2}$", text):
        return None
    try:
        hh, mm = [int(part) for part in text.split(":", 1)]
    except Exception:
        return None
    if 0 <= hh <= 23 and 0 <= mm <= 59:
        return hh, mm
    return None


def _temporary_assignment_access_bounds(row: dict, now_local: datetime | None = None) -> tuple[datetime, datetime] | None:
    lesson_date = str(row.get("temp_assignment_date") or row.get("lesson_date") or "").strip()
    if not lesson_date:
        return None
    try:
        day_value = datetime.strptime(lesson_date[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    start_pair = _temporary_assignment_hhmm(
        row.get("temp_assignment_start")
        or row.get("assignment_lesson_start")
        or row.get("lesson_start")
        or row.get("group_lesson_start")
    )
    end_pair = _temporary_assignment_hhmm(
        row.get("temp_assignment_end")
        or row.get("assignment_lesson_end")
        or row.get("lesson_end")
        or row.get("group_lesson_end")
    )
    # BUGFIX: groups can be created without lesson_start/lesson_end configured
    # (both columns are nullable, see create_group()). Previously this caused
    # _temporary_assignment_hhmm() to return None for one/both sides, making
    # this function return None unconditionally -> the substitute teacher
    # would NEVER pass _temporary_assignment_accessible_now(), even though
    # POST /teacher/groups/{id}/substitutions succeeded and returned a valid
    # assignment_id. The teacher app would then get silent 403s from every
    # attendance/homework/arena/dpoint endpoint for that group with no clear
    # explanation. Fall back to a full-day access window (00:00-23:59) for
    # the lesson_date whenever either time is missing/unparseable, instead
    # of refusing access outright.
    if not start_pair and not end_pair:
        start_local = _TEMP_ASSIGNMENT_TZ.localize(datetime.combine(day_value, datetime.min.time()))
        end_local = _TEMP_ASSIGNMENT_TZ.localize(datetime.combine(day_value, datetime.max.time().replace(microsecond=0)))
        return (
            start_local - timedelta(minutes=_TEMP_ASSIGNMENT_ACCESS_BEFORE_MINUTES),
            end_local + timedelta(hours=_TEMP_ASSIGNMENT_ACCESS_AFTER_HOURS),
        )
    if not start_pair:
        start_pair = (0, 0)
    if not end_pair:
        end_pair = (23, 59)
    start_local = _TEMP_ASSIGNMENT_TZ.localize(
        datetime.combine(
            day_value,
            datetime.min.time().replace(hour=start_pair[0], minute=start_pair[1]),
        )
    )
    end_local = _TEMP_ASSIGNMENT_TZ.localize(
        datetime.combine(
            day_value,
            datetime.min.time().replace(hour=end_pair[0], minute=end_pair[1]),
        )
    )
    if end_local < start_local:
        end_local = end_local + timedelta(days=1)
    return (
        start_local - timedelta(minutes=_TEMP_ASSIGNMENT_ACCESS_BEFORE_MINUTES),
        end_local + timedelta(hours=_TEMP_ASSIGNMENT_ACCESS_AFTER_HOURS),
    )


def _temporary_assignment_accessible_now(row: dict, now_local: datetime | None = None) -> bool:
    now_local = now_local or datetime.now(_TEMP_ASSIGNMENT_TZ)
    bounds = _temporary_assignment_access_bounds(row, now_local)
    if not bounds:
        return False
    window_start, window_end = bounds
    return window_start <= now_local <= window_end


def create_temporary_group_assignment(
    group_id: int,
    owner_teacher_id: int,
    temp_teacher_id: int,
    lesson_date: str,
    lesson_start: str | None = None,
    lesson_end: str | None = None,
) -> int:
    ensure_temporary_group_assignments_schema()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO temporary_group_assignments
            (group_id, owner_teacher_id, temp_teacher_id, lesson_date, lesson_start, lesson_end, status)
            VALUES (?, ?, ?, ?, ?, ?, 'active')
            """,
            (int(group_id), int(owner_teacher_id), int(temp_teacher_id), lesson_date, lesson_start, lesson_end),
        )
        assignment_id = int(getattr(cur, "lastrowid", 0) or 0)
        if _is_postgres_enabled():
            cur.execute("SELECT currval(pg_get_serial_sequence('temporary_group_assignments','id')) AS id")
            row = cur.fetchone()
            if row:
                assignment_id = int(row["id"])
        conn.commit()
        conn.close()
        return assignment_id


def get_active_temporary_assignments_by_owner(owner_teacher_id: int) -> list[dict]:
    ensure_temporary_group_assignments_schema()
    tz = pytz.timezone("Asia/Tashkent")
    today = datetime.now(tz).strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tga.*, g.name AS group_name, g.level AS group_level
        FROM temporary_group_assignments tga
        JOIN groups g ON g.id = tga.group_id
        WHERE tga.owner_teacher_id=? AND tga.status='active' AND tga.lesson_date >= ?
        ORDER BY tga.lesson_date ASC, COALESCE(tga.lesson_start, '') ASC
        """,
        (int(owner_teacher_id), today),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_active_temporary_assignments_for_pair(owner_teacher_id: int, group_id: int, temp_teacher_id: int) -> list[dict]:
    ensure_temporary_group_assignments_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM temporary_group_assignments
        WHERE owner_teacher_id=?
          AND group_id=?
          AND temp_teacher_id=?
          AND status='active'
        ORDER BY lesson_date ASC, COALESCE(lesson_start, '') ASC
        """,
        (int(owner_teacher_id), int(group_id), int(temp_teacher_id)),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_active_temporary_assignments_for_group_slots(group_id: int, lesson_dates: list[str]) -> list[dict]:
    """
    All active substitute assignments for [group_id] on any of [lesson_dates],
    regardless of which substitute teacher holds them. Used to prevent two
    different substitutes from being handed the same group+lesson slot at
    once (BUGFIX: previously only exact owner+group+substitute duplicates
    were checked, so a second, different substitute could be assigned to an
    already-covered slot with no warning, leading to two teachers being able
    to mark attendance/points/arena for the same lesson).
    """
    ensure_temporary_group_assignments_schema()
    clean_dates = sorted({str(d) for d in (lesson_dates or []) if str(d or "").strip()})
    if not clean_dates:
        return []
    placeholders = ",".join(["?"] * len(clean_dates))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT *
        FROM temporary_group_assignments
        WHERE group_id=?
          AND status='active'
          AND lesson_date IN ({placeholders})
        ORDER BY lesson_date ASC, COALESCE(lesson_start, '') ASC
        """,
        (int(group_id), *clean_dates),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_temporary_teachers_for_group_on_date(group_id: int, lesson_date: str) -> list[dict]:
    """
    Return temporary teacher user rows assigned to this group on exact lesson_date.
    """
    ensure_temporary_group_assignments_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DISTINCT u.*
        FROM temporary_group_assignments tga
        JOIN users u ON u.id = tga.temp_teacher_id
        WHERE tga.group_id=?
          AND tga.lesson_date=?
          AND tga.status='active'
        ORDER BY u.first_name, u.last_name, u.id
        """,
        (int(group_id), str(lesson_date)),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def get_groups_with_temporary_access_for_teacher(teacher_id: int) -> list[dict]:
    ensure_temporary_group_assignments_schema()
    now_local = datetime.now(_TEMP_ASSIGNMENT_TZ)
    cutoff_date = (now_local.date() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
               g.*,
               1 AS temporary_access,
               tga.id AS temp_assignment_id,
               tga.lesson_date AS temp_assignment_date,
               tga.lesson_date AS temp_assignment_next_date,
               COALESCE(NULLIF(TRIM(CAST(tga.lesson_start AS TEXT)), ''), g.lesson_start) AS temp_assignment_start,
               COALESCE(NULLIF(TRIM(CAST(tga.lesson_end AS TEXT)), ''), g.lesson_end) AS temp_assignment_end,
               tga.lesson_start AS assignment_lesson_start,
               tga.lesson_end AS assignment_lesson_end,
               g.lesson_start AS group_lesson_start,
               g.lesson_end AS group_lesson_end,
               tga.owner_teacher_id AS temp_owner_teacher_id
        FROM temporary_group_assignments tga
        JOIN groups g ON g.id = tga.group_id
        WHERE tga.temp_teacher_id=?
          AND tga.status='active'
          AND tga.lesson_date >= ?
        ORDER BY g.name, tga.lesson_date ASC, COALESCE(tga.lesson_start, '') ASC
        """,
        (int(teacher_id), cutoff_date),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return [row for row in rows if _temporary_assignment_accessible_now(row, now_local)]


def teacher_has_temporary_group_access(teacher_id: int, group_id: int) -> bool:
    ensure_temporary_group_assignments_schema()
    now_local = datetime.now(_TEMP_ASSIGNMENT_TZ)
    cutoff_date = (now_local.date() - timedelta(days=1)).strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tga.*,
               tga.lesson_date AS temp_assignment_date,
               COALESCE(NULLIF(TRIM(CAST(tga.lesson_start AS TEXT)), ''), g.lesson_start) AS temp_assignment_start,
               COALESCE(NULLIF(TRIM(CAST(tga.lesson_end AS TEXT)), ''), g.lesson_end) AS temp_assignment_end,
               tga.lesson_start AS assignment_lesson_start,
               tga.lesson_end AS assignment_lesson_end,
               g.lesson_start AS group_lesson_start,
               g.lesson_end AS group_lesson_end
        FROM temporary_group_assignments tga
        JOIN groups g ON g.id = tga.group_id
        WHERE tga.temp_teacher_id=?
          AND tga.group_id=?
          AND tga.status='active'
          AND tga.lesson_date >= ?
        ORDER BY tga.lesson_date ASC, COALESCE(tga.lesson_start, '') ASC
        """,
        (int(teacher_id), int(group_id), cutoff_date),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return any(_temporary_assignment_accessible_now(row, now_local) for row in rows)


def cancel_temporary_assignments_for_pair(owner_teacher_id: int, group_id: int, temp_teacher_id: int) -> int:
    ensure_temporary_group_assignments_schema()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE temporary_group_assignments
            SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP
            WHERE owner_teacher_id=?
              AND group_id=?
              AND temp_teacher_id=?
              AND status='active'
            """,
            (int(owner_teacher_id), int(group_id), int(temp_teacher_id)),
        )
        affected = int(cur.rowcount or 0)
        conn.commit()
        conn.close()
        return affected

def get_all_groups():
    """Barcha guruhlarni olish"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM groups ORDER BY name")
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def ensure_user_group_membership_log_schema() -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS user_group_membership_log (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    group_id BIGINT NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    left_at TIMESTAMP,
                    active INTEGER DEFAULT 1
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS user_group_membership_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    left_at TIMESTAMP,
                    active INTEGER DEFAULT 1
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_membership_log_user_group ON user_group_membership_log(user_id, group_id)")
        except Exception:
            pass
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("ensure_user_group_membership_log_schema failed")
        return False
    finally:
        conn.close()

def add_user_to_group(user_id, group_id, joined_at: str | None = None):
    """O'quvchini guruhga qo'shish (multi-group support)"""
    with DB_WRITE_LOCK:
        ensure_user_group_membership_log_schema()
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        old_subject_count = _get_user_subject_count_tx(cur, int(user_id))
        _ensure_user_dpoints_row(cur, int(user_id))
        effective_joined_at = str(joined_at or "").strip() or None
        
        # Add/reactivate membership. Historical students re-added to a group must
        # get a fresh billing start date instead of keeping the old left row.
        cur.execute(
            """
            INSERT INTO user_groups (user_id, group_id, joined_date, left_date)
            VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP), NULL)
            ON CONFLICT(user_id, group_id) DO UPDATE SET
                joined_date = CASE
                    WHEN user_groups.left_date IS NULL THEN user_groups.joined_date
                    ELSE EXCLUDED.joined_date
                END,
                left_date = NULL
            """,
            (int(user_id), int(group_id), effective_joined_at),
        )
        cur.execute(
            """
            UPDATE user_group_membership_log
            SET active=0, left_at=CURRENT_TIMESTAMP
            WHERE user_id=? AND group_id=? AND COALESCE(active, 1)=1
            """,
            (int(user_id), int(group_id)),
        )
        cur.execute(
            """
            INSERT INTO user_group_membership_log(user_id, group_id, joined_at, left_at, active)
            VALUES (?, ?, COALESCE(?, CURRENT_TIMESTAMP), NULL, 1)
            """,
            (int(user_id), int(group_id), effective_joined_at),
        )
        
        # Legacy support (old column)
        cur.execute("UPDATE users SET group_id=? WHERE id=?", (group_id, user_id))
        # When admin assigns a group, student should be able to access student bot.
        cur.execute("UPDATE users SET blocked=0, access_enabled=1 WHERE id=?", (user_id,))

        # Update user's level based on this group (keep highest level)
        cur.execute("SELECT level FROM groups WHERE id=?", (group_id,))
        gr = cur.fetchone()
        group_level = (gr["level"] if gr else None)
        
        if group_level:
            cur.execute("UPDATE users SET level=? WHERE id=?", (group_level, user_id))
        _sync_user_subjects_from_active_groups_tx(cur, int(user_id))
        new_subject_count = _get_user_subject_count_tx(cur, int(user_id))
        _reanchor_dcoin_on_subject_count_change(cur, int(user_id), old_subject_count, new_subject_count)
        conn.commit()
        conn.close()

    try:
        import userbot_manager
        userbot_manager.handle_userbot_group_join_event(int(user_id), int(group_id))
    except Exception:
        pass


def add_user_to_group_legacy(user_id, group_id):
    """Eski usul - faqat bitta guruh (backward compatibility)"""
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        # group determines student's current level
        cur.execute("SELECT level FROM groups WHERE id=?", (group_id,))
        gr = cur.fetchone()
        group_level = (gr["level"] if gr else None)
        if group_level:
            cur.execute("UPDATE users SET group_id=?, level=? WHERE id=?", (group_id, group_level, user_id))
        else:
            cur.execute("UPDATE users SET group_id=? WHERE id=?", (group_id, user_id))
        conn.commit()
        conn.close()


def update_group_days(group_id, days):
    """Update group lesson days (lesson_date is canonical for schedule UI; lesson_days kept in sync)."""
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE groups SET lesson_date=?, lesson_days=? WHERE id=?",
            (days, days, group_id),
        )
        conn.commit()
        conn.close()


RUSSIAN_GROUP_LEVELS = (
    'Начальный уровень (А1)',
    'Базовый уровень (А2)',
    'Средний (Б1)',
    'Продвинутый средний (Б2)',
)


def _russian_level_rank(level: str) -> int | None:
    raw = (level or '').strip()
    if raw in RUSSIAN_GROUP_LEVELS:
        return RUSSIAN_GROUP_LEVELS.index(raw)
    low = raw.lower().replace('ё', 'е')
    if 'началь' in low or 'а1' in low:
        return 0
    if 'базов' in low or 'элементар' in low or 'а2' in low:
        return 1
    if 'средн' in low or low == 'b1' or 'б1' in low:
        return 2
    if 'продвинут' in low or low == 'b2' or 'б2' in low:
        return 3
    return None


def normalize_russian_group_level(level: str | None) -> str | None:
    rank = _russian_level_rank(level or "")
    if rank is None:
        return None
    return RUSSIAN_GROUP_LEVELS[rank]


def is_higher_level(new_level, current_level):
    """Yangi level avvalgisidan yuqorimi"""
    nr = _russian_level_rank(new_level)
    cr = _russian_level_rank(current_level)
    if nr is not None and cr is not None:
        return nr > cr
    level_order = ['A1', 'A2', 'B1', 'B2', 'C1']
    try:
        new_idx = level_order.index(new_level)
        current_idx = level_order.index(current_level)
        return new_idx > current_idx
    except ValueError:
        return True


def get_user_groups(user_id):
    """Foydalanuvchining barcha guruhlarini olish"""
    conn = get_conn()
    cur = conn.cursor()
    groups: list[dict] = []
    sql_variants = (
        '''
        SELECT DISTINCT g.*
        FROM groups g
        JOIN user_groups ug ON g.id = ug.group_id
        WHERE ug.user_id = ?
          AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT)) = '')
        ''',
        '''
        SELECT DISTINCT g.*
        FROM groups g
        JOIN user_groups ug ON g.id = ug.group_id
        WHERE ug.user_id = ?
        ''',
    )
    for sql in sql_variants:
        try:
            cur.execute(sql, (user_id,))
            groups = [dict(row) for row in (cur.fetchall() or [])]
            break
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            continue
    if not groups:
        # Legacy fallback for records that still rely on users.group_id.
        cur.execute(
            '''
            SELECT g.*
            FROM users u
            JOIN groups g ON g.id = u.group_id
            WHERE u.id = ?
            LIMIT 1
            ''',
            (user_id,),
        )
        row = cur.fetchone()
        if row:
            groups = [dict(row)]
    conn.close()
    return groups


def check_user_group_access(user_id: int) -> bool:
    """Check if user is in any active group."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT COUNT(*) as count FROM user_groups ug
        JOIN groups g ON ug.group_id = g.id
        WHERE ug.user_id = ?
          AND COALESCE(g.active, 1) = 1
    ''', (user_id,))
    result = cur.fetchone()
    conn.close()
    return result['count'] > 0 if result else False


def auto_block_users_not_in_groups():
    """Automatically block users who are not in any active group"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Find users who are logged in but not in any active group
    cur.execute('''
        UPDATE users 
        SET blocked = 1, last_activity = CURRENT_TIMESTAMP
        WHERE login_type = 2 
        AND blocked = 0 
        AND logged_in = 1
        AND id NOT IN (
            SELECT DISTINCT ug.user_id 
            FROM user_groups ug 
            JOIN groups g ON ug.group_id = g.id 
            WHERE g.active = 1
        )
    ''')
    
    blocked_count = cur.rowcount
    conn.commit()
    conn.close()
    
    logger.info(f"Auto-blocked {blocked_count} users not in active groups")
    return blocked_count


def auto_unblock_users_in_groups():
    """Automatically unblock users who are in active groups (only if manually unblocked by admin first)"""
    conn = get_conn()
    cur = conn.cursor()
    
    # Only unblock users who were manually unblocked by admin (blocked = 0) and are in active groups
    cur.execute('''
        UPDATE users 
        SET last_activity = CURRENT_TIMESTAMP
        WHERE login_type = 2 
        AND blocked = 0 
        AND logged_in = 1
        AND id IN (
            SELECT DISTINCT ug.user_id 
            FROM user_groups ug 
            JOIN groups g ON ug.group_id = g.id 
            WHERE g.active = 1
        )
    ''')
    
    unblocked_count = cur.rowcount
    conn.commit()
    conn.close()
    
    logger.info(f"Auto-updated activity for {unblocked_count} users in active groups")
    return unblocked_count


def get_user_subjects(user_id):
    """Foydalanuvchining fanlari. Studentlarda aktiv guruh fanlari ustuvor."""
    conn = get_conn()
    cur = conn.cursor()
    subjects: list[str] = []
    cur.execute("SELECT login_type, subject FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    cur.execute("""
        SELECT DISTINCT g.subject FROM groups g
        JOIN user_groups ug ON g.id = ug.group_id
        WHERE ug.user_id = ?
          AND g.subject IS NOT NULL
          AND TRIM(g.subject) != ''
          AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT)) = '')
    """, (user_id,))
    group_rows = cur.fetchall()
    conn.close()
    group_subjects: list[str] = []
    for group_row in group_rows:
        s = str(group_row["subject"] or "").strip()
        if s and s not in group_subjects:
            group_subjects.append(s)
    if row and int(_safe_get(row, "login_type") or 0) in (1, 2, 6):
        # Student/accountless subjects are derived from current active groups only.
        # If a student leaves the last group for a subject, that subject must stop
        # granting access to support lessons, videos, books, and other filtered pages.
        return group_subjects
    if row and row["subject"]:
        for part in str(row["subject"]).split(","):
            s = part.strip()
            if s and s not in subjects:
                subjects.append(s)
    for s in group_subjects:
        if s and s not in subjects:
            subjects.append(s)
    return subjects


def remove_user_from_group(user_id: int, group_id: int, removed_at: str | None = None, is_mistake: bool = False):
    """Foydalanuvchini guruhdan olib tashlash (multi-group)"""
    with DB_WRITE_LOCK:
        ensure_user_group_membership_log_schema()
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        old_subject_count = _get_user_subject_count_tx(cur, int(user_id))
        _ensure_user_dpoints_row(cur, int(user_id))
        cur.execute("DELETE FROM user_groups WHERE user_id=? AND group_id=?", (user_id, group_id))
        
        if is_mistake:
            cur.execute("DELETE FROM user_group_membership_log WHERE user_id=? AND group_id=?", (int(user_id), int(group_id)))
            cur.execute("DELETE FROM monthly_payments WHERE user_id=? AND group_id=? AND paid=0", (int(user_id), int(group_id)))
            cur.execute("DELETE FROM payment_monthly_obligations WHERE user_id=? AND group_id=? AND paid_amount=0", (int(user_id), int(group_id)))
        else:
            effective_removed_at = str(removed_at or "").strip() or None
            cur.execute(
                """
                UPDATE user_group_membership_log
                SET active=0, left_at=COALESCE(?, CURRENT_TIMESTAMP)
                WHERE user_id=? AND group_id=? AND COALESCE(active, 1)=1
                """,
                (effective_removed_at, int(user_id), int(group_id)),
            )
        
        # Legacy support: clear old column if removing from this specific group
        cur.execute("UPDATE users SET group_id=NULL WHERE id=? AND group_id=?", (user_id, group_id))
        
        # If user has no more groups, recalculate level
        cur.execute("SELECT COUNT(*) as count FROM user_groups WHERE user_id=?", (user_id,))
        count = cur.fetchone()["count"]
        
        if count == 0:
            # Student without groups should lose active access (Part-1 policy).
            cur.execute("UPDATE users SET blocked=1, access_enabled=0, access_expires_at=NULL WHERE id=? AND login_type IN (1,2)", (user_id,))
        else:
            # Update to highest remaining group level
            cur.execute("""
                SELECT g.level FROM groups g
                JOIN user_groups ug ON g.id = ug.group_id
                WHERE ug.user_id = ?
                ORDER BY 
                    CASE g.level
                        WHEN 'A1' THEN 1
                        WHEN 'A2' THEN 2
                        WHEN 'B1' THEN 3
                        WHEN 'B2' THEN 4
                        WHEN 'C1' THEN 5
                    END DESC
                LIMIT 1
            """, (user_id,))
            result = cur.fetchone()
            if result:
                cur.execute("UPDATE users SET level=? WHERE id=?", (result["level"], user_id))
        _sync_user_subjects_from_active_groups_tx(cur, int(user_id))
        new_subject_count = _get_user_subject_count_tx(cur, int(user_id))
        _reanchor_dcoin_on_subject_count_change(cur, int(user_id), old_subject_count, new_subject_count)
        conn.commit()
        conn.close()


def list_user_group_membership_periods(user_id: int, group_id: int) -> list[dict]:
    ensure_user_group_membership_log_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id, group_id, joined_at, left_at, active
        FROM user_group_membership_log
        WHERE user_id=? AND group_id=?
        ORDER BY joined_at ASC
        """,
        (int(user_id), int(group_id)),
    )
    rows = [dict(row) for row in (cur.fetchall() or [])]
    conn.close()
    # Backward/forward compatible field aliases for payment engine expectations.
    for row in rows:
        if row.get("joined_date") is None:
            row["joined_date"] = row.get("joined_at")
        if row.get("left_date") is None:
            row["left_date"] = row.get("left_at")
    return rows


def update_group_name(group_id: int, name: str):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE groups SET name=? WHERE id=?", (name, group_id))
        conn.commit()
        conn.close()


def update_group_level(group_id: int, level: str, sync_students: bool = True):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE groups SET level=? WHERE id=?", (level, group_id))
        if sync_students:
            cur.execute("UPDATE users SET level=? WHERE group_id=?", (level, group_id))
        conn.commit()
        conn.close()


def update_group_teacher(group_id: int, teacher_id: int):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE groups SET teacher_id=? WHERE id=?", (teacher_id, group_id))
        conn.commit()
        conn.close()


def update_group_schedule(group_id: int, lesson_date: str | None, lesson_start: str | None, lesson_end: str | None, tz: str | None = None):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE groups SET lesson_date=?, lesson_start=?, lesson_end=?, tz=COALESCE(?, tz) WHERE id=?",
            (lesson_date, lesson_start, lesson_end, tz, group_id),
        )
        conn.commit()
        conn.close()


def update_group_subject(group_id: int, subject: str | None):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE groups SET subject=? WHERE id=?", (subject, group_id))
        conn.commit()
        conn.close()


def update_group_telegram_url(group_id: int, telegram_group_url: str | None):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE groups SET telegram_group_url=? WHERE id=?", (telegram_group_url, group_id))
        conn.commit()
        conn.close()


def update_group_lang(group_id: int, lang: str | None):
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        val = str(lang or "uz").strip().lower()
        if val not in ("uz", "ru"):
            val = "uz"
        cur.execute("UPDATE groups SET lang=? WHERE id=?", (val, group_id))
        conn.commit()
        conn.close()



def delete_group(group_id: int):
    with DB_WRITE_LOCK:
        ensure_user_group_membership_log_schema()
        conn = get_conn()
        cur = conn.cursor()
        gid = int(group_id)
        cur.execute("SELECT DISTINCT user_id FROM user_groups WHERE group_id=?", (gid,))
        affected_user_ids = [int((row or {}).get("user_id") or 0) for row in (cur.fetchall() or [])]
        # Unlink students first
        cur.execute("UPDATE users SET group_id=NULL WHERE group_id=?", (gid,))

        # Remove group memberships.
        cur.execute("DELETE FROM user_groups WHERE group_id=?", (gid,))
        cur.execute(
            """
            UPDATE user_group_membership_log
            SET active=0, left_at=CURRENT_TIMESTAMP
            WHERE group_id=? AND COALESCE(active, 1)=1
            """,
            (gid,),
        )
        if affected_user_ids:
            placeholders = ",".join(["?"] * len(affected_user_ids))
            cur.execute(
                f"""
                UPDATE users
                SET blocked=1, access_enabled=0, access_expires_at=NULL
                WHERE login_type IN (1,2)
                  AND id IN ({placeholders})
                  AND id NOT IN (SELECT DISTINCT user_id FROM user_groups)
                """,
                tuple(affected_user_ids),
            )

        # Cleanup group-scoped operational tables (best-effort).
        try:
            cur.execute("DELETE FROM attendance WHERE group_id=?", (gid,))
        except Exception:
            pass
        try:
            cur.execute("DELETE FROM attendance_sessions WHERE group_id=?", (gid,))
        except Exception:
            pass
        try:
            cur.execute("DELETE FROM overdue_penalty_log WHERE group_id=?", (gid,))
        except Exception:
            pass

        # Finally delete the group row.
        cur.execute("DELETE FROM groups WHERE id=?", (gid,))
        conn.commit()
        conn.close()


def _ym_now():
    from datetime import datetime
    import pytz
    return datetime.now(pytz.timezone("Asia/Tashkent")).strftime("%Y-%m")


def _cleanup_old_monthly_payments(retention_months: int = 6):
    # Disabled intentionally: historical monthly_payments records are preserved
    # for backward-compatible reads during payment automation migration.
    return


def set_month_paid(user_id: int, ym: str | None = None, group_id: int | None = None, subject: str | None = None, paid: bool = True):
    """Mark monthly payment status per user-group for a given month."""
    ym = ym or _ym_now()
    ensure_monthly_payments_table()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            if paid:
                cur.execute(
                    '''
                    INSERT INTO monthly_payments(user_id, ym, group_id, subject, paid, paid_at)
                    VALUES(?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, ym, group_id) DO UPDATE SET
                        paid=1,
                        paid_at=CURRENT_TIMESTAMP,
                        subject=COALESCE(excluded.subject, monthly_payments.subject)
                    ''',
                    (user_id, ym, group_id, subject),
                )
            else:
                cur.execute(
                    '''
                    INSERT INTO monthly_payments(user_id, ym, group_id, subject, paid, paid_at, payment_dcoin_amount)
                    VALUES(?, ?, ?, ?, 0, NULL, NULL)
                    ON CONFLICT(user_id, ym, group_id) DO UPDATE SET
                        paid=0,
                        paid_at=NULL,
                        payment_dcoin_amount=NULL,
                        subject=COALESCE(excluded.subject, monthly_payments.subject)
                    ''',
                    (user_id, ym, group_id, subject),
                )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()
    _cleanup_old_monthly_payments(retention_months=6)


def is_month_paid(user_id: int, ym: str | None = None, group_id: int | None = None) -> bool:
    ym = ym or _ym_now()
    ensure_monthly_payments_table()
    conn = get_conn()
    cur = conn.cursor()
    if group_id is None:
        cur.execute("SELECT paid FROM monthly_payments WHERE user_id=? AND ym=?", (user_id, ym))
    else:
        cur.execute("SELECT paid FROM monthly_payments WHERE user_id=? AND ym=? AND group_id=?", (user_id, ym, group_id))
    row = cur.fetchone()
    conn.close()
    return bool(row["paid"]) if row else False


def was_notified_on_day(user_id: int, day: int, ym: str | None = None) -> bool:
    ym = ym or _ym_now()
    ensure_monthly_payments_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT notified_days FROM monthly_payments WHERE user_id=? AND ym=?", (user_id, ym))
    row = cur.fetchone()
    conn.close()
    if not row or not row["notified_days"]:
        return False
    days = {d.strip() for d in str(row["notified_days"]).split(",") if d.strip()}
    return str(day) in days


def mark_notified_day(user_id: int, day: int, ym: str | None = None):
    ym = ym or _ym_now()
    ensure_monthly_payments_table()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT notified_days FROM monthly_payments WHERE user_id=? AND ym=?", (user_id, ym))
        row = cur.fetchone()
        cur_days = ""
        if row and row["notified_days"]:
            cur_days = str(row["notified_days"])
        days = {d.strip() for d in cur_days.split(",") if d.strip()}
        days.add(str(day))
        new_days = ",".join(sorted(days, key=lambda x: int(x)))
        # Portable for both SQLite and PostgreSQL regardless of unique indexes.
        cur.execute(
            "UPDATE monthly_payments SET notified_days=? WHERE user_id=? AND ym=?",
            (new_days, user_id, ym),
        )
        if cur.rowcount == 0:
            cur.execute(
                '''
                INSERT INTO monthly_payments(user_id, ym, group_id, subject, paid, paid_at, notified_days)
                VALUES(?, ?, NULL, NULL, 0, NULL, ?)
                ''',
                (user_id, ym, new_days),
            )
        conn.commit()
        conn.close()


def get_grammar_attempts(user_id: int, topic_id: str) -> int:
    ensure_grammar_attempts_table()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT attempts FROM grammar_attempts WHERE user_id=? AND topic_id=?", (user_id, topic_id))
    row = cur.fetchone()
    conn.close()
    return int(row["attempts"]) if row and row["attempts"] is not None else 0


def increment_grammar_attempt(user_id: int, topic_id: str) -> int:
    """Increments attempts and returns new value."""
    ensure_grammar_attempts_table()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            '''
            INSERT INTO grammar_attempts(user_id, topic_id, attempts, last_attempt_at)
            VALUES(?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, topic_id) DO UPDATE SET
              attempts=COALESCE(grammar_attempts.attempts,0)+1,
              last_attempt_at=CURRENT_TIMESTAMP
            ''',
            (user_id, topic_id),
        )
        conn.commit()
        cur.execute("SELECT attempts FROM grammar_attempts WHERE user_id=? AND topic_id=?", (user_id, topic_id))
        row = cur.fetchone()
        conn.close()
        return int(row["attempts"]) if row and row["attempts"] is not None else 0

def get_group_users(group_id):
    """Guruh a'zolarini olish (user_groups table orqali)"""
    conn = get_conn()
    cur = conn.cursor()
    rows: list[dict] = []
    sql_variants = (
        """
        SELECT u.*, ug.joined_date as joined_at
        FROM user_groups ug
        JOIN users u ON ug.user_id = u.id
        WHERE ug.group_id = ?
          AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT)) = '')
        ORDER BY u.first_name, u.last_name
        """,
        """
        SELECT u.*, ug.joined_date as joined_at
        FROM user_groups ug
        JOIN users u ON ug.user_id = u.id
        WHERE ug.group_id = ?
        ORDER BY u.first_name, u.last_name
        """,
    )
    for sql in sql_variants:
        try:
            cur.execute(sql, (group_id,))
            rows = [dict(row) for row in (cur.fetchall() or [])]
            break
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            continue
    conn.close()
    return rows

# ====================== DAVOMAT BOSHQARUVI ======================

def ensure_attendance_effects_schema() -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS attendance_effects (
                    user_id BIGINT NOT NULL,
                    group_id BIGINT NOT NULL,
                    date DATE NOT NULL,
                    status TEXT NOT NULL,
                    delta_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, group_id, date)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS attendance_effects (
                    user_id INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    delta_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(user_id, group_id, date)
                )
                """,
            ],
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("ensure_attendance_effects_schema failed")
        return False
    finally:
        conn.close()


def get_attendance_effect(user_id: int, group_id: int, date: str) -> dict | None:
    ensure_attendance_effects_schema()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT user_id, group_id, date, status, delta_dpoints, updated_at
        FROM attendance_effects
        WHERE user_id=? AND group_id=? AND date=?
        LIMIT 1
        """,
        (int(user_id), int(group_id), str(date)),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def set_attendance_effect(user_id: int, group_id: int, date: str, status: str, delta_dpoints: float) -> bool:
    ensure_attendance_effects_schema()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            if _is_postgres_enabled():
                cur.execute(
                    """
                    INSERT INTO attendance_effects(user_id, group_id, date, status, delta_dpoints, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, group_id, date)
                    DO UPDATE SET
                      status=excluded.status,
                      delta_dpoints=excluded.delta_dpoints,
                      updated_at=CURRENT_TIMESTAMP
                    """,
                    (int(user_id), int(group_id), str(date), str(status), float(delta_dpoints or 0)),
                )
            else:
                cur.execute(
                    """
                    INSERT OR REPLACE INTO attendance_effects(user_id, group_id, date, status, delta_dpoints, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (int(user_id), int(group_id), str(date), str(status), float(delta_dpoints or 0)),
                )
            conn.commit()
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("set_attendance_effect failed user_id=%s group_id=%s date=%s", user_id, group_id, date)
            return False
        finally:
            conn.close()

def add_attendance(user_id, group_id, date, status='Present'):
    """Davomatni qo'shish"""
    day = str(date or "").strip()
    if is_lesson_otmen_date_cancelled(day):
        return False
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        # Portable upsert: update first, insert if missing.
        cur.execute(
            "UPDATE attendance SET status=?, created_at=CURRENT_TIMESTAMP WHERE user_id=? AND group_id=? AND date=?",
            (status, user_id, group_id, day),
        )
        if cur.rowcount == 0:
            cur.execute(
                '''
                INSERT INTO attendance (user_id, group_id, date, status)
                VALUES (?, ?, ?, ?)
                ''',
                (user_id, group_id, day, status),
            )
        conn.commit()
        conn.close()

    try:
        import userbot_manager
        userbot_manager.handle_userbot_attendance_event(int(user_id), int(group_id), str(day), str(status))
    except Exception:
        pass

    return True

def get_attendance(user_id, group_id, date):
    """Konkret davomat yozuvini olish"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM attendance WHERE user_id=? AND group_id=? AND date=?
    ''', (user_id, group_id, date))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_attendance_by_group(group_id, date):
    """Guruhnning muayyan kuni davomatini olish"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        SELECT * FROM attendance WHERE group_id=? AND date=? ORDER BY user_id
    ''', (group_id, date))
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_present_students_for_group_date(group_id: int, date_str: str) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT u.*
        FROM attendance a
        JOIN users u ON u.id = a.user_id
        WHERE a.group_id=? AND a.date=? AND LOWER(COALESCE(a.status,''))='present'
          AND u.login_type IN (1,2)
        ''',
        (group_id, date_str),
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

# ====================== DIAMOND BOSHQARUVI ======================

def _is_missing_subject_dcoins_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "user_subject_dcoins" in msg
        and ("does not exist" in msg or "no such table" in msg)
    )


def _subject_dcoins_table_exists(cur) -> bool:
    try:
        if _is_postgres_enabled():
            cur.execute("SELECT to_regclass('user_subject_dcoins') AS reg")
            row = cur.fetchone() or {}
            if bool(row.get("reg")):
                return True
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_name='user_subject_dcoins'
                  AND table_schema = ANY (current_schemas(true))
                LIMIT 1
                """
            )
            return bool(cur.fetchone())
        return False
    except Exception:
        return False


def _ensure_subject_dcoins_ready(cur, *, context: str) -> bool:
    if _subject_dcoins_table_exists(cur):
        return True
    logger.error(
        "user_subject_dcoins table missing in %s",
        context,
    )
    return False


def _is_missing_user_dpoints_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "user_dpoints" in msg
        and ("does not exist" in msg or "no such table" in msg)
    )


def _user_dpoints_table_exists(cur) -> bool:
    try:
        if _is_postgres_enabled():
            cur.execute("SELECT to_regclass('user_dpoints') AS reg")
            row = cur.fetchone() or {}
            if bool(row.get("reg")):
                return True
            cur.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_name='user_dpoints'
                  AND table_schema = ANY (current_schemas(true))
                LIMIT 1
                """
            )
            return bool(cur.fetchone())
        return False
    except Exception:
        return False


def _ensure_user_dpoints_ready(cur, *, context: str) -> bool:
    if _user_dpoints_table_exists(cur):
        return True
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_dpoints (
                user_id INTEGER PRIMARY KEY,
                dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                dcoin_floor DOUBLE PRECISION NOT NULL DEFAULT 0,
                dcoin_anchor_value DOUBLE PRECISION,
                dcoin_anchor_dpoints DOUBLE PRECISION,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_dpoints_updated_at ON user_dpoints(updated_at)")
        except Exception:
            pass
        if _user_dpoints_table_exists(cur):
            logger.warning("user_dpoints table self-healed in %s", context)
            return True
    except Exception:
        logger.exception("user_dpoints table self-heal failed in %s", context)
    logger.error("user_dpoints table missing in %s", context)
    return False


def _legacy_total_dcoins(cur, user_id: int) -> float:
    try:
        cur.execute("SELECT COALESCE(SUM(balance), 0) as total FROM user_subject_dcoins WHERE user_id=?", (user_id,))
        row = cur.fetchone() or {}
        return float(row.get("total") or 0)
    except Exception:
        return 0.0


def _ensure_user_dpoints_row(cur, user_id: int) -> float:
    cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row is not None:
        return float(_safe_get(row, "dpoints", 0))
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    legacy_total = _legacy_total_dcoins(cur, int(user_id))
    cur.execute(
        """
        INSERT INTO user_dpoints (user_id, dpoints, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (int(user_id), float(legacy_total), now),
    )
    cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return float(_safe_get(row, "dpoints", 0))


def _normalize_subject_token(value: Any) -> str:
    raw = str(value or "").strip()
    return raw.title() if raw else ""


def _count_unique_subjects(values: list[Any]) -> int:
    cleaned: list[str] = []
    for item in values or []:
        token = _normalize_subject_token(item)
        if token and token not in cleaned:
            cleaned.append(token)
    return max(1, len(cleaned))


def _get_user_subject_count_tx(cur, user_id: int) -> int:
    subjects: list[str] = []
    cur.execute(
        """
        SELECT DISTINCT g.subject
        FROM groups g
        JOIN user_groups ug ON g.id = ug.group_id
        WHERE ug.user_id=? AND g.subject IS NOT NULL AND TRIM(g.subject) != ''
        """,
        (int(user_id),),
    )
    for row in (cur.fetchall() or []):
        subject = _safe_get(row, "subject")
        token = _normalize_subject_token(subject)
        if token and token not in subjects:
            subjects.append(token)
    cur.execute("SELECT subject FROM users WHERE id=?", (int(user_id),))
    row = cur.fetchone()
    subject = _safe_get(row, "subject")
    raw_csv = str(subject or "")
    if raw_csv.strip():
        for part in raw_csv.split(","):
            token = _normalize_subject_token(part)
            if token and token not in subjects:
                subjects.append(token)
    return max(1, len(subjects))


def get_user_subject_count(user_id: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        return _get_user_subject_count_tx(cur, int(user_id))
    except Exception:
        return 1
    finally:
        conn.close()


def _round_half_up(value: float, digits: int = 2) -> float:
    quant = Decimal("1").scaleb(-int(digits))
    return float(Decimal(str(float(value or 0.0))).quantize(quant, rounding=ROUND_HALF_UP))


def _get_user_wallet_state(cur, user_id: int) -> dict[str, float | None]:
    cur.execute(
        """
        SELECT
            COALESCE(dpoints, 0) AS dpoints,
            COALESCE(dcoin_floor, 0) AS dcoin_floor,
            dcoin_anchor_value,
            dcoin_anchor_dpoints
        FROM user_dpoints
        WHERE user_id=?
        """,
        (int(user_id),),
    )
    row = cur.fetchone() or {}
    anchor_value_raw = row.get("dcoin_anchor_value")
    anchor_dpoints_raw = row.get("dcoin_anchor_dpoints")
    return {
        "dpoints": float(row.get("dpoints") or 0.0),
        "dcoin_floor": float(row.get("dcoin_floor") or 0.0),
        "anchor_value": float(anchor_value_raw) if anchor_value_raw is not None else None,
        "anchor_dpoints": float(anchor_dpoints_raw) if anchor_dpoints_raw is not None else None,
    }


def _visible_dcoin_from_state(*, dpoints: float, subject_count: int, floor: float, anchor_value: float | None, anchor_dpoints: float | None) -> float:
    if anchor_value is not None and anchor_dpoints is not None:
        raw_visible = float(anchor_value) + (float(dpoints) - float(anchor_dpoints))
    else:
        raw_visible = float(dpoints)
    visible = float(raw_visible)
    visible = max(float(floor), visible)
    return _round_half_up(visible, 2)


def _visible_dcoin_balance_tx(cur, user_id: int, *, fallback_dpoints: float | None = None) -> float:
    cur.execute(
        """
        SELECT
            dpoints,
            COALESCE(dcoin_floor, 0) AS dcoin_floor,
            dcoin_anchor_value,
            dcoin_anchor_dpoints
        FROM user_dpoints
        WHERE user_id=?
        """,
        (int(user_id),),
    )
    row = cur.fetchone()
    if row is None:
        dpoints = float(fallback_dpoints) if fallback_dpoints is not None else float(_legacy_total_dcoins(cur, int(user_id)))
        floor = 0.0
        anchor_value = None
        anchor_dpoints = None
    else:
        dpoints = float(row.get("dpoints") or 0.0)
        if fallback_dpoints is not None and abs(dpoints) < 1e-9 and abs(float(fallback_dpoints)) > 1e-9:
            dpoints = float(fallback_dpoints)
        floor = float(row.get("dcoin_floor") or 0.0)
        anchor_value_raw = row.get("dcoin_anchor_value")
        anchor_dpoints_raw = row.get("dcoin_anchor_dpoints")
        anchor_value = float(anchor_value_raw) if anchor_value_raw is not None else None
        anchor_dpoints = float(anchor_dpoints_raw) if anchor_dpoints_raw is not None else None

    subject_count = _get_user_subject_count_tx(cur, int(user_id))
    return _visible_dcoin_from_state(
        dpoints=dpoints,
        subject_count=subject_count,
        floor=floor,
        anchor_value=anchor_value,
        anchor_dpoints=anchor_dpoints,
    )


def _spend_visible_dcoins_tx(cur, user_id: int, amount: float, now: str, *, allow_negative: bool = False) -> tuple[bool, float, float]:
    """Deduct visible D'coin without changing D'point balance."""
    amount_value = max(0.0, float(amount or 0.0))
    balance_before = float(_visible_dcoin_balance_tx(cur, int(user_id)))
    if amount_value <= 0:
        return True, balance_before, balance_before
    if not allow_negative and balance_before + 1e-9 < amount_value:
        return False, balance_before, balance_before
    state = _get_user_wallet_state(cur, int(user_id))
    current_dpoints = float(state.get("dpoints") or 0.0)
    balance_after = _round_half_up(balance_before - amount_value, 2)
    if not allow_negative:
        balance_after = max(0.0, balance_after)
    floor_after = max(0.0, balance_after)
    cur.execute(
        """
        UPDATE user_dpoints
        SET dcoin_floor=?,
            dcoin_anchor_value=?,
            dcoin_anchor_dpoints=?,
            updated_at=?
        WHERE user_id=?
        """,
        (float(floor_after), float(balance_after), float(current_dpoints), now, int(user_id)),
    )
    return True, balance_before, balance_after


def _add_visible_dcoins_only_tx(cur, user_id: int, amount: float, now: str) -> tuple[float, float]:
    """Increase visible D'coin without changing D'point balance."""
    amount_value = max(0.0, float(amount or 0.0))
    balance_before = float(_visible_dcoin_balance_tx(cur, int(user_id)))
    state = _get_user_wallet_state(cur, int(user_id))
    current_dpoints = float(state.get("dpoints") or 0.0)
    balance_after = _round_half_up(balance_before + amount_value, 2)
    cur.execute(
        """
        UPDATE user_dpoints
        SET dcoin_floor=?,
            dcoin_anchor_value=?,
            dcoin_anchor_dpoints=?,
            updated_at=?
        WHERE user_id=?
        """,
        (float(max(0.0, balance_after)), float(balance_after), float(current_dpoints), now, int(user_id)),
    )
    return balance_before, balance_after


def _reanchor_dcoin_on_subject_count_change(cur, user_id: int, old_subject_count: int, new_subject_count: int) -> bool:
    old_count = max(1, int(old_subject_count or 1))
    new_count = max(1, int(new_subject_count or 1))
    if new_count == old_count:
        return False
    state = _get_user_wallet_state(cur, int(user_id))
    old_visible = _visible_dcoin_from_state(
        dpoints=float(state.get("dpoints") or 0.0),
        subject_count=old_count,
        floor=float(state.get("dcoin_floor") or 0.0),
        anchor_value=state.get("anchor_value"),
        anchor_dpoints=state.get("anchor_dpoints"),
    )
    cur.execute(
        """
        UPDATE user_dpoints
        SET dcoin_anchor_value=?,
            dcoin_anchor_dpoints=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE user_id=?
        """,
        (float(old_visible), float(state.get("dpoints") or 0.0), int(user_id)),
    )
    return True


def _get_user_dcoin_floor(cur, user_id: int) -> float:
    try:
        cur.execute("SELECT COALESCE(dcoin_floor, 0) AS dcoin_floor FROM user_dpoints WHERE user_id=?", (int(user_id),))
        row = cur.fetchone() or {}
        return float(row.get("dcoin_floor") or 0)
    except Exception:
        return 0.0


def _is_accountless_user_tx(cur, user_id: int) -> bool:
    try:
        cur.execute("SELECT login_type FROM users WHERE id=? LIMIT 1", (int(user_id),))
        row = cur.fetchone() or {}
        return int(_safe_get(row, "login_type", 0) or 0) == 6
    except Exception:
        return False


def get_dpoints(user_id: int) -> float:
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_accountless_user_tx(cur, int(user_id)):
            return 0.0
        if not _ensure_user_dpoints_ready(cur, context="get_dpoints"):
            return 0.0
        val = _ensure_user_dpoints_row(cur, int(user_id))
        conn.commit()
        return float(val)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("get_dpoints failed for user_id=%s", user_id)
        return 0.0
    finally:
        conn.close()


def set_dpoints(user_id: int, dpoints: float) -> None:
    with DB_WRITE_LOCK:
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        try:
            if _is_accountless_user_tx(cur, int(user_id)):
                return
            if not _ensure_user_dpoints_ready(cur, context="set_dpoints"):
                return
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute(
                """
                INSERT INTO user_dpoints (user_id, dpoints, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT (user_id)
                DO UPDATE SET dpoints=excluded.dpoints, updated_at=excluded.updated_at
                """,
                (int(user_id), float(dpoints), now),
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("set_dpoints failed for user_id=%s", user_id)
        finally:
            conn.close()


def upsert_dpoints(user_id: int, dpoints: float) -> None:
    set_dpoints(user_id, dpoints)


def add_dpoints(user_id: int, amount: float, subject: str | None = None, *, change_type: str | None = None) -> None:
    """Apply wallet delta in D'points (authoritative test-economy unit)."""
    if subject and str(subject).strip().title() in ("Matematika", "Ona Tili", "Tarix", "Arab Tili", "Ona tili", "Arab tili"):
        return
    dpoints_delta = float(amount or 0)
    if dpoints_delta == 0:
        return
    with DB_WRITE_LOCK:
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        if _is_accountless_user_tx(cur, int(user_id)):
            conn.close()
            return
        if not _ensure_user_dpoints_ready(cur, context="add_dpoints"):
            conn.close()
            return
        try:
            _ensure_user_dpoints_row(cur, int(user_id))
            floor_before = _get_user_dcoin_floor(cur, int(user_id))
            dcoin_delta = dpoints_delta
            floor_after = floor_before
            if dcoin_delta < 0:
                floor_after = max(0.0, float(floor_before) + float(dcoin_delta))
            cur.execute(
                "UPDATE user_dpoints SET dpoints=dpoints+?, dcoin_floor=?, updated_at=? WHERE user_id=?",
                (dpoints_delta, float(floor_after), now, int(user_id)),
            )
            cur.execute(
                """
                INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    float(dcoin_delta),
                    float(dpoints_delta),
                    str(subject or "GLOBAL"),
                    now,
                    change_type,
                ),
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("add_dpoints failed for user_id=%s", user_id)
        finally:
            conn.close()


def add_dpoints_tx(cur, user_id: int, amount: float, subject: str | None = None, *, change_type: str | None = None) -> bool:
    """Apply a D'point delta using the caller's open DB transaction."""
    if subject and str(subject).strip().title() in ("Matematika", "Ona Tili", "Tarix", "Arab Tili", "Ona tili", "Arab tili"):
        return True
    dpoints_delta = float(amount or 0)
    if dpoints_delta == 0:
        return True
    if _is_accountless_user_tx(cur, int(user_id)):
        return False
    if not _ensure_user_dpoints_ready(cur, context="add_dpoints_tx"):
        return False
    _ensure_user_dpoints_row(cur, int(user_id))
    floor_before = _get_user_dcoin_floor(cur, int(user_id))
    dcoin_delta = dpoints_delta
    floor_after = floor_before
    if dcoin_delta < 0:
        floor_after = max(0.0, float(floor_before) + float(dcoin_delta))
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute(
        "UPDATE user_dpoints SET dpoints=dpoints+?, dcoin_floor=?, updated_at=? WHERE user_id=?",
        (dpoints_delta, float(floor_after), now, int(user_id)),
    )
    cur.execute(
        """
        INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            int(user_id),
            float(dcoin_delta),
            float(dpoints_delta),
            str(subject or "GLOBAL"),
            now,
            change_type,
        ),
    )
    return True


def validate_dcoin_runtime_ready(*, context: str = "startup") -> bool:
    """Validate wallet/runtime readiness for the running process."""
    try:
        ensure_dpoints_schema()
        ensure_subject_dcoin_schema()
        ensure_dcoin_schema_migrations()
    except Exception:
        logger.exception("D'coin schema ensure/migration failed during %s", context)
        return False

    conn = get_conn()
    cur = conn.cursor()
    try:
        if not _user_dpoints_table_exists(cur):
            logger.error("Wallet runtime not ready during %s: user_dpoints is missing", context)
            return False
        cur.execute("SELECT 1 FROM user_dpoints LIMIT 1")
        # Dry-run write-path probe: parse UPDATE without mutating rows.
        cur.execute("UPDATE user_dpoints SET updated_at=updated_at WHERE 1=0")
        conn.rollback()
        logger.info("Wallet runtime readiness OK during %s", context)
        return True
    except Exception:
        logger.exception("D'coin runtime readiness probe failed during %s", context)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()

def add_dcoins(user_id, amount, subject: str | None = None, *, change_type: str | None = None) -> None:
    """Global wallet update. Input `amount` is still interpreted as D'coin units."""
    if subject and str(subject).strip().title() in ("Matematika", "Ona Tili", "Tarix", "Arab Tili", "Ona tili", "Arab tili"):
        return
    amount = float(amount or 0)
    if amount == 0:
        return
    with DB_WRITE_LOCK:
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        if _is_accountless_user_tx(cur, int(user_id)):
            conn.close()
            return
        if not _ensure_user_dpoints_ready(cur, context="add_dcoins"):
            conn.close()
            return
        try:
            _ensure_user_dpoints_row(cur, int(user_id))
            if amount < 0:
                _spend_visible_dcoins_tx(cur, int(user_id), abs(amount), now, allow_negative=True)
            else:
                _add_visible_dcoins_only_tx(cur, int(user_id), amount, now)
            cur.execute(
                "UPDATE user_dpoints SET dpoints=dpoints+?, updated_at=? WHERE user_id=?",
                (amount, now, int(user_id)),
            )
            cur.execute(
                '''
                INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (int(user_id), amount, amount, "GLOBAL", now, change_type),
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("add_dcoins failed for user_id=%s", user_id)
        finally:
            conn.close()

def add_dcoins_only(user_id: int, amount: float, subject: str | None = None, *, change_type: str | None = None) -> bool:
    """Apply a visible D'coin delta without changing D'point balance."""
    amount_value = float(amount or 0)
    if amount_value == 0:
        return True
    with DB_WRITE_LOCK:
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        try:
            if _is_accountless_user_tx(cur, int(user_id)):
                return False
            if not _ensure_user_dpoints_ready(cur, context="add_dcoins_only"):
                return False
            _ensure_user_dpoints_row(cur, int(user_id))
            if amount_value > 0:
                _add_visible_dcoins_only_tx(cur, int(user_id), amount_value, now)
            else:
                ok, _before, _after = _spend_visible_dcoins_tx(cur, int(user_id), abs(amount_value), now)
                if not ok:
                    return False
            cur.execute(
                """
                INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    float(amount_value),
                    0.0,
                    str(subject or "GLOBAL"),
                    now,
                    change_type,
                ),
            )
            conn.commit()
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("add_dcoins_only failed for user_id=%s", user_id)
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass

def add_dcoins_tx(cur, user_id: int, amount: float, subject: str | None = None, *, change_type: str | None = None) -> bool:
    """Apply a visible D'coin delta using the caller's open DB transaction."""
    if subject and str(subject).strip().title() in ("Matematika", "Ona Tili", "Tarix", "Arab Tili", "Ona tili", "Arab tili"):
        return True
    amount = float(amount or 0)
    if amount == 0:
        return True
    if _is_accountless_user_tx(cur, int(user_id)):
        return False
    if not _ensure_user_dpoints_ready(cur, context="add_dcoins_tx"):
        return False
    _ensure_user_dpoints_row(cur, int(user_id))
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    if amount < 0:
        _spend_visible_dcoins_tx(cur, int(user_id), abs(amount), now, allow_negative=True)
    else:
        _add_visible_dcoins_only_tx(cur, int(user_id), amount, now)
    cur.execute(
        "UPDATE user_dpoints SET dpoints=dpoints+?, updated_at=? WHERE user_id=?",
        (amount, now, int(user_id)),
    )
    cur.execute(
        '''
        INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (int(user_id), amount, amount, str(subject or "GLOBAL"), now, change_type),
    )
    return True

def get_dcoins(user_id, subject: str | None = None) -> float:
    """Visible D'coin (derived, transition-safe). `subject` kept for compatibility."""
    _ = subject
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_accountless_user_tx(cur, int(user_id)):
            return 0.0
        if not _ensure_user_dpoints_ready(cur, context="get_dcoins"):
            return 0.0
        visible = _visible_dcoin_balance_tx(cur, int(user_id))
        return float(visible)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("get_dcoins failed for user_id=%s", int(user_id))
        return 0.0
    finally:
        conn.close()


def try_consume_dcoins(
    user_id: int,
    amount: float,
    subject: str,
    *,
    arena_type: str | None = None,
    change_type: str | None = None,
) -> bool:
    """Deduct amount in D'coin units from the global wallet if enough funds."""
    amount = float(amount)
    if amount <= 0:
        return True
    _ = subject
    with DB_WRITE_LOCK:
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        try:
            if _is_accountless_user_tx(cur, int(user_id)):
                return False
            if not _ensure_user_dpoints_ready(cur, context="try_consume_dcoins"):
                return False
            _ensure_user_dpoints_row(cur, int(user_id))
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            ok, _balance_before, _balance_after = _spend_visible_dcoins_tx(cur, int(user_id), amount, now)
            if not ok:
                return False
            ct = change_type or (f"arena_fee:{arena_type}" if arena_type else "consume")
            cur.execute(
                "INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type) VALUES (?, ?, ?, ?, ?, ?)",
                (int(user_id), -amount, 0.0, "GLOBAL", now, ct),
            )
            conn.commit()
            return True
        except Exception as e:
            if _is_missing_user_dpoints_error(e):
                logger.error("user_dpoints missing in try_consume_dcoins; rejecting consume request")
            else:
                logger.exception("try_consume_dcoins failed for user_id=%s", user_id)
            try:
                conn.rollback()
            except Exception:
                pass
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass


def consume_dcoins_allow_negative(
    user_id: int,
    amount: float,
    subject: str,
    *,
    change_type: str = "consume_allow_negative",
) -> float:
    """
    Deduct amount from subject balance even if it becomes negative.
    Returns new balance after deduction (best-effort).
    """
    amount = float(amount)
    if amount <= 0:
        return float(get_dcoins(user_id, subject))
    _ = subject

    with DB_WRITE_LOCK:
        ensure_dpoints_schema()
        conn = get_conn()
        cur = conn.cursor()
        try:
            if _is_accountless_user_tx(cur, int(user_id)):
                return 0.0
            if not _ensure_user_dpoints_ready(cur, context="consume_dcoins_allow_negative"):
                return float(get_dcoins(user_id))
            _ensure_user_dpoints_row(cur, int(user_id))
            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            _spend_visible_dcoins_tx(cur, int(user_id), amount, now, allow_negative=True)
            cur.execute(
                "INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type) VALUES (?, ?, ?, ?, ?, ?)",
                (int(user_id), -amount, 0.0, "GLOBAL", now, change_type),
            )
            conn.commit()
            return float(get_dcoins(user_id))
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception(
                "consume_dcoins_allow_negative failed for user_id=%s",
                user_id,
            )
            return float(get_dcoins(user_id))
        finally:
            try:
                conn.close()
            except Exception:
                pass

def get_leaderboard_global(limit=10, offset=0):
    """Global reyting (butun markaz boyicha)"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if not _ensure_user_dpoints_ready(cur, context="get_leaderboard_global"):
            return []
        cur.execute(
            """
            SELECT u.id, u.first_name, u.last_name, u.profile_image_url, COALESCE(ud.dpoints, 0) as dpoints
            FROM users u
            LEFT JOIN user_dpoints ud ON ud.user_id = u.id
            WHERE u.access_enabled=1 AND u.login_type IN (1,2)
            """
        )
        rows = []
        for r in cur.fetchall() or []:
            uid = int(r.get("id") or 0)
            dcoin_balance = float(_visible_dcoin_balance_tx(cur, uid, fallback_dpoints=float(r.get("dpoints") or 0.0)))
            if dcoin_balance <= 0:
                continue
            rows.append(
                {
                    "id": uid,
                    "first_name": r.get("first_name"),
                    "last_name": r.get("last_name"),
                    "profile_image_url": r.get("profile_image_url"),
                    "dcoin_balance": float(dcoin_balance),
                    "dpoint_balance": float(r.get("dpoints") or 0.0),
                }
            )
        rows.sort(key=lambda x: float(x.get("dcoin_balance") or 0), reverse=True)
        return rows[int(offset): int(offset) + int(limit)]
    except Exception as e:
        if _is_missing_user_dpoints_error(e):
            logger.exception("Leaderboard fallback: global wallet table missing")
            return []
        raise
    finally:
        conn.close()


def get_leaderboard_by_subject(subject: str, limit=10, offset=0):
    """Legacy alias: leaderboard is now global-only."""
    _ = subject
    return get_leaderboard_global(limit=limit, offset=offset)

def get_leaderboard_by_group(group_id, limit=10, offset=0):
    """GuruH bo'yicha reyting"""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if not _ensure_user_dpoints_ready(cur, context="get_leaderboard_by_group"):
            return []
        cur.execute(
            """
            SELECT u.id, u.first_name, u.last_name, u.profile_image_url, COALESCE(ud.dpoints, 0) as dpoints
            FROM users u
            LEFT JOIN user_dpoints ud ON ud.user_id = u.id
            WHERE u.group_id=? AND u.login_type IN (1,2)
            """,
            (group_id,),
        )
        rows = []
        for r in cur.fetchall() or []:
            uid = int(r.get("id") or 0)
            dcoin_balance = float(_visible_dcoin_balance_tx(cur, uid, fallback_dpoints=float(r.get("dpoints") or 0.0)))
            if dcoin_balance <= 0:
                continue
            rows.append(
                {
                    "id": uid,
                    "first_name": r.get("first_name"),
                    "last_name": r.get("last_name"),
                    "profile_image_url": r.get("profile_image_url"),
                    "dcoin_balance": float(dcoin_balance),
                    "dpoint_balance": float(r.get("dpoints") or 0.0),
                }
            )
        rows.sort(key=lambda x: float(x.get("dcoin_balance") or 0), reverse=True)
        return rows[int(offset): int(offset) + int(limit)]
    except Exception as e:
        if _is_missing_user_dpoints_error(e):
            logger.exception("Leaderboard fallback: group wallet table missing")
            return []
        raise
    finally:
        conn.close()

def get_leaderboard_count():
    """Global reytingdagi umumiy foydalanuvchi soni"""
    rows = get_leaderboard_global(limit=1000000, offset=0)
    return len(rows)


def get_leaderboard_count_by_subject(subject: str):
    _ = subject
    return get_leaderboard_count()


def get_staff_leaderboard_by_subject(subject: str, limit: int = 10, offset: int = 0) -> list[dict]:
    """Alias for admin/teacher bot D'coin leaderboard (per-subject)."""
    return get_leaderboard_by_subject(subject, limit=limit, offset=offset)


def get_staff_leaderboard_student_count(subject: str) -> int:
    """Total students on leaderboard (global wallet; subject arg kept for compatibility)."""
    return get_leaderboard_count_by_subject(subject)


def get_subject_dcoin_history_rows(subject: str, owner_admin_id: int | None = None) -> list[dict]:
    """Return global D'coin history rows (legacy `subject` arg is ignored)."""
    _ = subject
    ensure_dpoints_schema()

    conn = get_conn()
    cur = conn.cursor()
    try:
        if owner_admin_id is not None:
            cur.execute(
                """
                SELECT
                    u.first_name,
                    u.last_name,
                    u.login_id,
                    dh.created_at,
                    dh.dcoin_change,
                    COALESCE(dh.dpoints_change, 0) AS dpoints_change,
                    COALESCE(dh.change_type, '') AS change_type,
                    COALESCE(NULLIF(dh.subject, ''), 'GLOBAL') AS subject
                FROM diamond_history dh
                JOIN users u ON u.id = dh.user_id
                WHERE u.login_type IN (1, 2)
                  AND (
                    u.owner_admin_id = ?
                    OR u.id IN (
                        SELECT student_id
                        FROM admin_student_shares
                        WHERE peer_admin_id = ? AND status = 'active'
                    )
                  )
                ORDER BY dh.created_at DESC
                """,
                (owner_admin_id, owner_admin_id),
            )
        else:
            cur.execute(
                """
                SELECT
                    u.first_name,
                    u.last_name,
                    u.login_id,
                    dh.created_at,
                    dh.dcoin_change,
                    COALESCE(dh.dpoints_change, 0) AS dpoints_change,
                    COALESCE(dh.change_type, '') AS change_type,
                    COALESCE(NULLIF(dh.subject, ''), 'GLOBAL') AS subject
                FROM diamond_history dh
                JOIN users u ON u.id = dh.user_id
                WHERE u.login_type IN (1, 2)
                ORDER BY dh.created_at DESC
                """
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_teacher_groups_count(teacher_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as cnt FROM groups WHERE teacher_id = ?", (teacher_id,))
    row = cur.fetchone()
    conn.close()
    return row['cnt'] if row else 0


def get_teacher_students_count(teacher_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT u.id) as cnt 
        FROM users u
        JOIN groups g ON u.group_id = g.id
        WHERE g.teacher_id = ? AND u.login_type IN (1,2)
    """, (teacher_id,))
    row = cur.fetchone()
    conn.close()
    return row['cnt'] if row else 0


def get_teacher_total_students(teacher_id: int) -> int:
    """O'qituvchining barcha guruhlaridagi jami talabalar soni (multi-group tizimi uchun)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(DISTINCT ug.user_id) as total_students
        FROM user_groups ug
        JOIN groups g ON ug.group_id = g.id
        WHERE g.teacher_id = ? 
          AND g.active = 1
    """, (teacher_id,))
    row = cur.fetchone()
    conn.close()
    return row['total_students'] if row and row['total_students'] is not None else 0


def get_student_teachers(user_id: int):
    """Studentning barcha guruhlaridagi o'qituvchilarni qaytaradi (ism + guruh nomi bilan)"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT 
            t.id as teacher_id,
            t.first_name,
            t.last_name,
            g.name as group_name,
            g.subject
        FROM user_groups ug
        JOIN groups g ON ug.group_id = g.id
        JOIN users t ON g.teacher_id = t.id
        WHERE ug.user_id = ? 
          AND t.login_type = 3
        ORDER BY g.name
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_student_subjects(user_id: int) -> list:
    """Studentning aktiv guruhlaridagi UNIQUE fanlarni qaytaradi."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT g.subject 
        FROM user_groups ug
        JOIN groups g ON ug.group_id = g.id
        WHERE ug.user_id = ? 
          AND g.subject IS NOT NULL
          AND TRIM(g.subject) != ''
          AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT)) = '')
        ORDER BY g.subject
    """, (user_id,))
    rows = cur.fetchall()
    subjects = [row['subject'] for row in rows if row['subject']]
    if not subjects:
        cur.execute(
            """
            SELECT g.subject
            FROM users u
            JOIN groups g ON g.id = u.group_id
            WHERE u.id = ?
              AND g.subject IS NOT NULL
              AND TRIM(g.subject) != ''
            LIMIT 1
            """,
            (user_id,),
        )
        legacy = cur.fetchone()
        if legacy and legacy["subject"]:
            subjects = [legacy["subject"]]
    conn.close()
    return subjects


def get_group_level_for_subject(user_id: int, subject: str) -> str | None:
    """Lowest active group level for this student matching the subject.

    A student may study the same subject in multiple groups. Test placement for
    that subject should follow the lower active group level so the generated
    test does not jump ahead of the easier group.
    """
    want = (subject or "").strip().title()
    matches: list[str] = []
    for g in get_user_groups(user_id):
        if (g.get("subject") or "").strip().title() != want:
            continue
        lv = g.get("level")
        if lv is not None and str(lv).strip():
            matches.append(str(lv).strip())
    if not matches:
        return None

    def rank(level: str) -> tuple[int, str]:
        russian_rank = _russian_level_rank(level)
        if russian_rank is not None:
            return (russian_rank, level)
        code = extract_cefr_level_code(level)
        order = {"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5, "MIXED": 6}
        return (order.get(code, 99), level)

    return sorted(matches, key=rank)[0]


def get_user_groups_with_counts(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            g.id, g.name, g.level, 
            (SELECT COUNT(*) FROM users u2 
             WHERE u2.group_id = g.id AND u2.login_type IN (1,2)) as student_count
        FROM groups g
        JOIN users u ON u.group_id = g.id
        WHERE u.id = ?
        ORDER BY g.name
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_leaderboard_count_by_group(group_id):
    """Guruhdagi Diamond bilan foydalanuvchi soni"""
    rows = get_leaderboard_by_group(group_id, limit=1000000, offset=0)
    return len(rows)


def get_user_rating_info(user_id):
    """Foydalanuvchining reyting ma'lumotlarini olish"""
    global_rank = None
    group_rank = None

    all_global = get_leaderboard_global(limit=1000000, offset=0)
    for idx, row in enumerate(all_global, 1):
        if int(row.get("id") or 0) == int(user_id):
            global_rank = idx
            break

    gid = None
    user_row = get_user_by_id(int(user_id))
    if user_row:
        gid = user_row.get("group_id")
    if not gid:
        groups = get_user_groups(int(user_id))
        if groups:
            gid = groups[0].get("id")

    if gid:
        group_rows = get_leaderboard_by_group(gid, limit=1000000, offset=0)
        for idx, row in enumerate(group_rows, 1):
            if int(row.get("id") or 0) == int(user_id):
                group_rank = idx
                break

    return {
        'global_rank': global_rank,
        'group_rank': group_rank
    }


def get_rating_leaderboard(user_id, period, subject: str | None = None):
    """Global reyting jadvalini olish (daily, weekly, monthly). Legacy `subject` ignored."""
    conn = get_conn()
    cur = conn.cursor()
    _ = user_id
    _ = subject

    if period == 'daily':
        # Kunlik reyting - bugungi kun olgan D'coinlar
        cur.execute("""
            SELECT u.first_name, u.last_name, 
                   COALESCE(SUM(CASE 
                       WHEN DATE(dh.created_at) = CURRENT_DATE THEN dh.dcoin_change 
                       ELSE 0 END), 0) as score,
                   COALESCE(SUM(CASE 
                       WHEN DATE(dh.created_at) = CURRENT_DATE THEN dh.dcoin_change 
                       ELSE 0 END), 0) as dcoin
            FROM users u
            JOIN diamond_history dh ON u.id = dh.user_id
            WHERE DATE(dh.created_at) = CURRENT_DATE
            AND u.login_type IN (1, 2)
            GROUP BY u.id
            ORDER BY score DESC
            LIMIT 10
        """)
    elif period == 'weekly':
        # Haftalik reyting - oxirgi 7 kun
        cur.execute("""
            SELECT u.first_name, u.last_name, 
                   COALESCE(SUM(dh.dcoin_change), 0) as score,
                   COALESCE(SUM(dh.dcoin_change), 0) as dcoin
            FROM users u
            JOIN diamond_history dh ON u.id = dh.user_id
            WHERE dh.created_at >= (CURRENT_TIMESTAMP - INTERVAL '7 days')
            AND u.login_type IN (1, 2)
            GROUP BY u.id
            ORDER BY score DESC
            LIMIT 10
        """)
    elif period == 'monthly':
        # Oylik reyting - oxirgi 30 kun
        cur.execute("""
            SELECT u.first_name, u.last_name, 
                   COALESCE(SUM(dh.dcoin_change), 0) as score,
                   COALESCE(SUM(dh.dcoin_change), 0) as dcoin
            FROM users u
            JOIN diamond_history dh ON u.id = dh.user_id
            WHERE dh.created_at >= (CURRENT_TIMESTAMP - INTERVAL '30 days')
            AND u.login_type IN (1, 2)
            GROUP BY u.id
            ORDER BY score DESC
            LIMIT 10
        """)
    else:
        conn.close()
        return []
    
    rows = cur.fetchall()
    conn.close()
    
    leaderboard = []
    for row in rows:
        name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
        score = row['score'] or 0
        dcoin = row['dcoin'] or 0
        
        leaderboard.append({
            'name': name,
            'score': score,
            'dcoin': dcoin
        })
    
    return leaderboard


def add_feedback(user_id, feedback_text, is_anonymous=True):
    """Add student feedback to database"""
    conn = get_conn()
    cur = conn.cursor()
    from datetime import datetime
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    is_anon_bool = bool(is_anonymous)
    anon_int = 1 if is_anon_bool else 0
    anon_bool = is_anon_bool

    # Best-effort: detect column type in PostgreSQL to avoid psycopg type mismatch.
    # (Some deployments have feedback.is_anonymous as INTEGER, others as BOOLEAN.)
    inferred_use_bool = None
    try:
        cur.execute(
            "SELECT data_type FROM information_schema.columns WHERE table_name='feedback' AND column_name='is_anonymous'",
        )
        row = cur.fetchone()
        if row and row.get("data_type"):
            inferred_use_bool = str(row["data_type"]).lower() in ("boolean", "bool")
    except Exception:
        inferred_use_bool = None

    try:
        # Primary path: choose value type based on inferred column type.
        anon_param = anon_bool if inferred_use_bool else anon_int
        cur.execute('''
            INSERT INTO feedback (user_id, feedback_text, is_anonymous, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, feedback_text, anon_param, now))
    except Exception:
        # Fallback for BOOLEAN-backed schemas.
        conn.rollback()
        anon_param = anon_int if inferred_use_bool else anon_bool
        cur.execute('''
            INSERT INTO feedback (user_id, feedback_text, is_anonymous, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, feedback_text, anon_param, now))

    conn.commit()
    conn.close()


def get_student_monthly_stats(user_id):
    """Get student's monthly statistics"""
    # Make sure we have a compatible schema for existing databases.
    # Particularly: Postgres legacy DBs may store `grammar_attempts.last_attempt_at` as TEXT.
    ensure_grammar_attempts_table()
    conn = get_conn()
    cur = conn.cursor()
    
    # Get current month start
    cur.execute("SELECT DATE_TRUNC('month', CURRENT_TIMESTAMP) as month_start")
    month_start = cur.fetchone()['month_start']
    
    # === WORDS LEARNED — tuzatilgan versiya ===
    cur.execute('''
        SELECT COUNT(*) as words_learned
        FROM diamond_history 
        WHERE user_id = ? 
          AND dcoin_change > 0 
          AND created_at >= ?
    ''', (user_id, month_start))
    
    words_result = cur.fetchone()
    words_learned = words_result['words_learned'] if words_result else 0
    
    # Count grammar topics completed
    if _is_postgres_enabled():
        # Postgres: `last_attempt_at` might be TEXT in legacy DBs.
        # Cast only values that look like a datetime prefix to avoid runtime errors.
        cur.execute('''
            SELECT COUNT(DISTINCT topic_id) as topics_completed
            FROM grammar_attempts ga
            WHERE ga.user_id = ?
              AND (
                CASE
                  WHEN ga.last_attempt_at IS NULL THEN NULL
                  WHEN ga.last_attempt_at::text = '' THEN NULL
                  WHEN ga.last_attempt_at::text ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9]{2}:[0-9]{2}:[0-9]{2}' THEN ga.last_attempt_at::timestamptz
                  ELSE NULL
                END
              ) >= ?
        ''', (user_id, month_start))
    else:
        # SQLite: keep the original comparison.
        cur.execute('''
            SELECT COUNT(DISTINCT topic_id) as topics_completed
            FROM grammar_attempts ga
            WHERE ga.user_id = ?
              AND ga.last_attempt_at >= ?
        ''', (user_id, month_start))
    
    topics_result = cur.fetchone()
    topics_completed = topics_result['topics_completed'] if topics_result else 0
    
    # Count tests taken
    try:
        cur.execute('''
            SELECT COUNT(*) as tests_taken,
                   SUM(CASE WHEN correct_count > 0 THEN 1 ELSE 0 END) as tests_completed,
                   SUM(correct_count) as total_correct,
                   SUM(wrong_count) as total_wrong,
                   SUM(skipped_count) as total_skipped
            FROM test_history th
            WHERE th.user_id = ?
            AND th.created_at >= ?
        ''', (user_id, month_start))
        
        tests_result = cur.fetchone()
        if tests_result:
            tests_taken = tests_result['tests_taken'] or 0
            tests_completed = tests_result['tests_completed'] or 0
            total_correct = tests_result['total_correct'] or 0
            total_wrong = tests_result['total_wrong'] or 0
            total_skipped = tests_result['total_skipped'] or 0
        else:
            tests_taken = 0
            tests_completed = 0
            total_correct = 0
            total_wrong = 0
            total_skipped = 0
    except Exception:
        # If legacy schema misses columns, keep progress safe.
        tests_taken = 0
        tests_completed = 0
        total_correct = 0
        total_wrong = 0
        total_skipped = 0
    
    conn.close()
    
    return {
        'words_learned': words_learned,
        'topics_completed': topics_completed,
        'tests_taken': tests_taken,
        'tests_completed': tests_completed,
        'total_correct': total_correct,
        'total_wrong': total_wrong,
        'total_skipped': total_skipped
    }


def add_test_history(user_id, test_type, topic_id, correct_count, wrong_count, skipped_count):
    """Add test record to history"""
    conn = get_conn()
    cur = conn.cursor()
    from datetime import datetime
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

    # Defensive insert: some legacy DBs can miss some columns.
    # We build INSERT dynamically based on existing columns to avoid runtime crashes.
    existing_cols: set[str] = set()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='test_history'
                """
            )
            existing_cols = {str(r["column_name"]) for r in cur.fetchall()}
        else:
            cur.execute("PRAGMA table_info(test_history)")
            # sqlite rows: (cid, name, type, notnull, dflt_value, pk)
            existing_cols = {str(r["name"]) for r in cur.fetchall()}
    except Exception:
        # If introspection fails, assume full schema and let DB raise if it's truly incompatible.
        existing_cols = set()

    # Keep column/value order consistent with table schema.
    insert_cols: list[str] = ["user_id", "test_type"]
    values: list[Any] = [user_id, test_type]

    if "topic_id" in existing_cols:
        insert_cols.append("topic_id")
        values.append(topic_id)

    if "correct_count" in existing_cols:
        insert_cols.append("correct_count")
        values.append(correct_count)
    if "wrong_count" in existing_cols:
        insert_cols.append("wrong_count")
        values.append(wrong_count)
    if "skipped_count" in existing_cols:
        insert_cols.append("skipped_count")
        values.append(skipped_count)

    insert_cols.append("created_at")
    values.append(now)

    placeholders = ", ".join(["?"] * len(insert_cols))
    cols_sql = ", ".join(insert_cols)

    cur.execute(
        f"INSERT INTO test_history ({cols_sql}) VALUES ({placeholders})",
        tuple(values),
    )
    
    conn.commit()
    conn.close()


def ensure_duel_matchmaking_schema() -> None:
    """Create persistent duel queue/session tables for both SQLite and PostgreSQL."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS open_duel_sessions (
                    id BIGSERIAL PRIMARY KEY,
                    mode TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    level TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    required_players INTEGER NOT NULL,
                    created_by_user_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_duel_match_participants (
                    id BIGSERIAL PRIMARY KEY,
                    session_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    team_no INTEGER NOT NULL DEFAULT 1,
                    paid_fee INTEGER NOT NULL DEFAULT 1,
                    refunded_fee INTEGER NOT NULL DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    result_correct INTEGER NOT NULL DEFAULT 0,
                    result_wrong INTEGER NOT NULL DEFAULT 0,
                    result_unanswered INTEGER NOT NULL DEFAULT 0,
                    is_winner INTEGER NOT NULL DEFAULT 0,
                    last_opponent_user_id BIGINT,
                    UNIQUE(session_id, user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_duel_revenge_tokens (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    opponent_user_id BIGINT NOT NULL,
                    mode TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS open_duel_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    level TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    required_players INTEGER NOT NULL,
                    created_by_user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_duel_match_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    team_no INTEGER NOT NULL DEFAULT 1,
                    paid_fee INTEGER NOT NULL DEFAULT 1,
                    refunded_fee INTEGER NOT NULL DEFAULT 0,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    result_correct INTEGER NOT NULL DEFAULT 0,
                    result_wrong INTEGER NOT NULL DEFAULT 0,
                    result_unanswered INTEGER NOT NULL DEFAULT 0,
                    is_winner INTEGER NOT NULL DEFAULT 0,
                    last_opponent_user_id INTEGER,
                    UNIQUE(session_id, user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_duel_revenge_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    opponent_user_id INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_duel_sessions_open ON open_duel_sessions(mode, subject, level, status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_duel_participants_session ON arena_duel_match_participants(session_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_duel_revenge_user ON arena_duel_revenge_tokens(user_id, used, expires_at)")
        conn.commit()
    finally:
        conn.close()


def create_duel_session(mode: str, subject: str, level: str, created_by_user_id: int, required_players: int, expires_at: str) -> int:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO open_duel_sessions(mode, subject, level, status, required_players, created_by_user_id, expires_at)
            VALUES (?, ?, ?, 'open', ?, ?, ?)
            RETURNING id
            """,
            (mode, subject, level, int(required_players), int(created_by_user_id), expires_at),
        )
        sid = int(cur.fetchone()["id"])
        conn.commit()
        return sid
    finally:
        conn.close()


def get_open_duel_session(mode: str, subject: str, level: str) -> dict | None:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT *
            FROM open_duel_sessions
            WHERE mode=? AND subject=? AND level=? AND status='open'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """,
            (mode, subject, level),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_open_duel_sessions_for_mode(mode: str) -> list[dict]:
    """All open duel sessions for a mode (any subject/level), oldest first."""
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT *
            FROM open_duel_sessions
            WHERE mode=? AND status='open'
            ORDER BY created_at ASC, id ASC
            """,
            (mode,),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def cleanup_student_subject_side_effects(user_id: int, subject: str) -> None:
    """
    After removing a subject from a student, clear per-subject data that would be stale.
    Safe for SQLite/Postgres; ignores missing tables/columns.
    """
    uid = int(user_id)
    subj = (subject or "").strip()
    if not subj:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM user_subject_dcoins WHERE user_id=? AND LOWER(subject)=LOWER(?)", (uid, subj))
        cur.execute("DELETE FROM test_results WHERE user_id=? AND LOWER(subject)=LOWER(?)", (uid, subj))
        # Vocabulary bank is intentionally permanent; do not delete words on subject cleanup.
        cur.execute(
            "DELETE FROM diamond_history WHERE user_id=? AND LOWER(COALESCE(subject,''))=LOWER(?)",
            (uid, subj),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_diamondvoy_history_table() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS diamondvoy_history (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT,
                    query_text TEXT NOT NULL,
                    response_text TEXT,
                    subject TEXT,
                    bot_scope TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS diamondvoy_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    query_text TEXT NOT NULL,
                    response_text TEXT,
                    subject TEXT,
                    bot_scope TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_diamondvoy_chat_schema() -> None:
    if _schema_ready("diamondvoy_chat"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS diamondvoy_chats (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS diamondvoy_chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL REFERENCES diamondvoy_chats(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_diamondvoy_chats_user_updated ON diamondvoy_chats(user_id, updated_at DESC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_diamondvoy_chat_messages_chat_created ON diamondvoy_chat_messages(chat_id, created_at ASC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_diamondvoy_chat_messages_chat_id_desc ON diamondvoy_chat_messages(chat_id, id DESC)"
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS diamondvoy_chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS diamondvoy_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(chat_id) REFERENCES diamondvoy_chats(id)
                )
                """
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_diamondvoy_chats_user_updated ON diamondvoy_chats(user_id, updated_at DESC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_diamondvoy_chat_messages_chat_created ON diamondvoy_chat_messages(chat_id, created_at ASC)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_diamondvoy_chat_messages_chat_id_desc ON diamondvoy_chat_messages(chat_id, id DESC)"
            )
        conn.commit()
        _mark_schema_ready("diamondvoy_chat")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_universal_chat_schema() -> None:
    if _schema_ready("universal_chat"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS chat_threads (
                    id BIGSERIAL PRIMARY KEY,
                    thread_type TEXT NOT NULL DEFAULT 'direct',
                    direct_key TEXT,
                    group_id BIGINT,
                    title TEXT,
                    created_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS chat_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_type TEXT NOT NULL DEFAULT 'direct',
                    direct_key TEXT,
                    group_id INTEGER,
                    title TEXT,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "chat_threads",
            [
                ("thread_type", "TEXT NOT NULL DEFAULT 'direct'"),
                ("direct_key", "TEXT"),
                ("group_id", "BIGINT"),
                ("title", "TEXT"),
                ("created_by", "BIGINT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )

        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS chat_participants (
                    id BIGSERIAL PRIMARY KEY,
                    thread_id BIGINT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
                    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    role_snapshot TEXT,
                    last_read_message_id BIGINT,
                    last_read_at TIMESTAMP,
                    active INTEGER DEFAULT 1,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(thread_id, user_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS chat_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role_snapshot TEXT,
                    last_read_message_id INTEGER,
                    last_read_at TIMESTAMP,
                    active INTEGER DEFAULT 1,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(thread_id, user_id),
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id)
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "chat_participants",
            [
                ("role_snapshot", "TEXT"),
                ("last_read_message_id", "BIGINT"),
                ("last_read_at", "TIMESTAMP"),
                ("active", "INTEGER DEFAULT 1"),
                ("joined_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )

        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id BIGSERIAL PRIMARY KEY,
                    thread_id BIGINT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
                    sender_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    sender_role TEXT,
                    message_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id INTEGER NOT NULL,
                    sender_id INTEGER NOT NULL,
                    sender_role TEXT,
                    message_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(thread_id) REFERENCES chat_threads(id)
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "chat_messages",
            [
                ("sender_role", "TEXT"),
                ("message_text", "TEXT"),
                ("reply_to_message_id", "BIGINT"),
                ("client_message_id", "TEXT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )

        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_threads_direct_key ON chat_threads(direct_key)")
        except Exception:
            pass
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_threads_group_id ON chat_threads(group_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_participants_user_thread ON chat_participants(user_id, thread_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_created ON chat_messages(thread_id, id ASC)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_reply_to ON chat_messages(reply_to_message_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_client_msg ON chat_messages(thread_id, sender_id, client_message_id)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("universal_chat")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def ensure_media_assets_schema() -> None:
    if _schema_ready("media_assets"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Create and persist the core table first. Optional follow-up schema sync
        # must not roll this back, otherwise media registration can fail at runtime.
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS media_assets (
                    id BIGSERIAL PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    original_name TEXT,
                    content_type TEXT,
                    size_bytes BIGINT,
                    uploaded_by BIGINT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS media_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset_type TEXT NOT NULL,
                    storage_path TEXT NOT NULL,
                    original_name TEXT,
                    content_type TEXT,
                    size_bytes INTEGER,
                    uploaded_by INTEGER,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        conn.commit()
        _ensure_table_columns(
            cur,
            "media_assets",
            [
                ("asset_type", "TEXT NOT NULL"),
                ("storage_path", "TEXT NOT NULL"),
                ("original_name", "TEXT"),
                ("content_type", "TEXT"),
                ("size_bytes", "BIGINT"),
                ("uploaded_by", "BIGINT"),
                ("is_active", "INTEGER DEFAULT 1"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        conn.commit()
        try:
            _ensure_table_columns(
                cur,
                "videos",
                [
                    ("video_asset_id", "BIGINT"),
                ],
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            _ensure_table_columns(
                cur,
                "books",
                [
                    ("subject", "TEXT"),
                    ("description", "TEXT"),
                    ("cover_url", "TEXT"),
                    ("pdf_asset_id", "BIGINT"),
                    ("purchase_count", "INTEGER DEFAULT 0"),
                ],
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        try:
            cur.execute(
                """
                UPDATE books
                SET description = COALESCE(NULLIF(description, ''), NULLIF(short_description, ''), description)
                WHERE COALESCE(NULLIF(description, ''), '') = ''
                """
            )
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE books DROP COLUMN IF EXISTS short_description")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_media_assets_created ON media_assets(created_at DESC)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_videos_asset_id ON videos(video_asset_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_books_asset_id ON books(pdf_asset_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_videos_subject_published ON videos(subject, is_published)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_videos_published_rank ON videos(is_published, view_count DESC, like_count DESC, created_at DESC)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_books_subject_published ON books(subject, is_published)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_books_published_rank ON books(is_published, purchase_count DESC, created_at DESC)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("media_assets")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _chat_direct_key(user_a: int, user_b: int) -> str:
    a = int(user_a or 0)
    b = int(user_b or 0)
    if a <= 0 or b <= 0 or a == b:
        return ""
    lo = min(a, b)
    hi = max(a, b)
    return f"{lo}:{hi}"


def get_chat_thread(thread_id: int) -> dict | None:
    ensure_universal_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE id=?
            LIMIT 1
            """,
            (int(thread_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_chat_participants(thread_id: int) -> list[dict]:
    ensure_universal_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, thread_id, user_id, role_snapshot, last_read_message_id, last_read_at, active, joined_at
            FROM chat_participants
            WHERE thread_id=?
            ORDER BY id ASC
            """,
            (int(thread_id),),
        )
        return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def upsert_chat_participant(thread_id: int, user_id: int, role_snapshot: str | None = None) -> bool:
    ensure_universal_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                INSERT INTO chat_participants (thread_id, user_id, role_snapshot, active, joined_at)
                VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (thread_id, user_id)
                DO UPDATE SET
                    active=1,
                    role_snapshot=COALESCE(EXCLUDED.role_snapshot, chat_participants.role_snapshot)
                """,
                (int(thread_id), int(user_id), (str(role_snapshot or "").strip() or None)),
            )
        except Exception:
            cur.execute(
                """
                SELECT id
                FROM chat_participants
                WHERE thread_id=? AND user_id=?
                LIMIT 1
                """,
                (int(thread_id), int(user_id)),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    """
                    UPDATE chat_participants
                    SET active=1,
                        role_snapshot=COALESCE(?, role_snapshot)
                    WHERE thread_id=? AND user_id=?
                    """,
                    ((str(role_snapshot or "").strip() or None), int(thread_id), int(user_id)),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO chat_participants (thread_id, user_id, role_snapshot, active, joined_at)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                    """,
                    (int(thread_id), int(user_id), (str(role_snapshot or "").strip() or None)),
                )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_or_create_direct_chat_thread(
    user_a: int,
    user_b: int,
    *,
    role_a: str | None = None,
    role_b: str | None = None,
    created_by: int | None = None,
) -> dict | None:
    ensure_universal_chat_schema()
    direct_key = _chat_direct_key(int(user_a), int(user_b))
    if not direct_key:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE direct_key=?
            LIMIT 1
            """,
            (direct_key,),
        )
        existing = cur.fetchone()
        thread_id = int(existing.get("id") or 0) if existing else 0
        if thread_id <= 0:
            cur.execute(
                """
                INSERT INTO chat_threads (thread_type, direct_key, title, created_by, updated_at)
                VALUES ('direct', ?, NULL, ?, CURRENT_TIMESTAMP)
                """,
                (direct_key, int(created_by or user_a or 0) or None),
            )
            thread_id = int(getattr(cur, "lastrowid", 0) or 0)
            if not thread_id:
                cur.execute("SELECT currval(pg_get_serial_sequence('chat_threads', 'id')) as id")
                row = cur.fetchone()
                thread_id = int((row or {}).get("id") or 0)
        for uid, role in ((int(user_a), role_a), (int(user_b), role_b)):
            if uid <= 0:
                continue
            try:
                cur.execute(
                    """
                    INSERT INTO chat_participants (thread_id, user_id, role_snapshot, active, joined_at)
                    VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (thread_id, user_id)
                    DO UPDATE SET
                        active=1,
                        role_snapshot=COALESCE(EXCLUDED.role_snapshot, chat_participants.role_snapshot)
                    """,
                    (thread_id, uid, (str(role or "").strip() or None)),
                )
            except Exception:
                cur.execute(
                    """
                    SELECT id
                    FROM chat_participants
                    WHERE thread_id=? AND user_id=?
                    LIMIT 1
                    """,
                    (thread_id, uid),
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        """
                        UPDATE chat_participants
                        SET active=1,
                            role_snapshot=COALESCE(?, role_snapshot)
                        WHERE thread_id=? AND user_id=?
                        """,
                        ((str(role or "").strip() or None), thread_id, uid),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO chat_participants (thread_id, user_id, role_snapshot, active, joined_at)
                        VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
                        """,
                        (thread_id, uid, (str(role or "").strip() or None)),
                    )
        conn.commit()
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE id=?
            LIMIT 1
            """,
            (thread_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def get_or_create_group_chat_thread(
    group_id: int,
    *,
    title: str | None = None,
    created_by: int | None = None,
) -> dict | None:
    ensure_universal_chat_schema()
    gid = int(group_id or 0)
    if gid <= 0:
        return None
    safe_title = (str(title or "").strip()[:160] or None)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE group_id=?
            LIMIT 1
            """,
            (gid,),
        )
        row = cur.fetchone()
        thread_id = int(row.get("id") or 0) if row else 0
        if thread_id <= 0:
            cur.execute(
                """
                INSERT INTO chat_threads (thread_type, group_id, title, created_by, updated_at)
                VALUES ('group', ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (gid, safe_title, int(created_by or 0) or None),
            )
            thread_id = int(getattr(cur, "lastrowid", 0) or 0)
            if not thread_id:
                cur.execute("SELECT currval(pg_get_serial_sequence('chat_threads', 'id')) as id")
                created_row = cur.fetchone()
                thread_id = int((created_row or {}).get("id") or 0)
        elif safe_title:
            cur.execute(
                """
                UPDATE chat_threads
                SET title=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (safe_title, thread_id),
            )
        conn.commit()
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE id=?
            LIMIT 1
            """,
            (thread_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def get_or_create_admin_support_thread(user_id: int) -> dict | None:
    ensure_universal_chat_schema()
    uid = int(user_id or 0)
    if uid <= 0:
        return None
    direct_key = f"admin_support:{uid}"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE direct_key=? AND thread_type='admin_support'
            LIMIT 1
            """,
            (direct_key,)
        )
        existing = cur.fetchone()
        thread_id = int((existing or {}).get("id") or 0)
        
        if thread_id <= 0:
            cur.execute(
                """
                INSERT INTO chat_threads (thread_type, direct_key, title, created_by, updated_at)
                VALUES ('admin_support', ?, 'Admin Chat', ?, CURRENT_TIMESTAMP)
                """,
                (direct_key, uid)
            )
            thread_id = int(getattr(cur, "lastrowid", 0) or 0)
            if not thread_id:
                cur.execute("SELECT currval(pg_get_serial_sequence('chat_threads', 'id')) as id")
                thread_id = int((cur.fetchone() or {}).get("id") or 0)
                
            # Add user as participant
            cur.execute(
                """
                INSERT INTO chat_participants (thread_id, user_id, active, joined_at)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (thread_id, user_id) DO UPDATE SET active=1
                """,
                (thread_id, uid)
            )
            conn.commit()
            
            cur.execute(
                """
                SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
                FROM chat_threads
                WHERE id=?
                LIMIT 1
                """,
                (thread_id,)
            )
            existing = cur.fetchone()

        return dict(existing) if existing else None
    except Exception:
        try: conn.rollback()
        except: pass
        return None
    finally:
        conn.close()

def get_or_create_role_hub_thread(
    user_id: int,
    hub_role: str,
    *,
    participant_user_ids: list[int] | None = None,
    title: str | None = None,
    created_by: int | None = None,
) -> dict | None:
    ensure_universal_chat_schema()
    uid = int(user_id or 0)
    role_key = str(hub_role or "").strip().lower()
    if uid <= 0 or not role_key:
        return None
    direct_key = f"role_hub:{role_key}:{uid}"
    safe_title = (str(title or "").strip()[:160] or f"{role_key.title()} Chat")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE direct_key=? AND thread_type='role_hub'
            LIMIT 1
            """,
            (direct_key,),
        )
        existing = cur.fetchone()
        thread_id = int((existing or {}).get("id") or 0)

        if thread_id <= 0:
            cur.execute(
                """
                INSERT INTO chat_threads (thread_type, direct_key, title, created_by, updated_at)
                VALUES ('role_hub', ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (direct_key, safe_title, int(created_by or uid) or None),
            )
            thread_id = int(getattr(cur, "lastrowid", 0) or 0)
            if not thread_id:
                cur.execute("SELECT currval(pg_get_serial_sequence('chat_threads', 'id')) as id")
                thread_id = int((cur.fetchone() or {}).get("id") or 0)
        else:
            cur.execute(
                "UPDATE chat_threads SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (safe_title, thread_id),
            )

        participant_ids = {uid}
        for pid in (participant_user_ids or []):
            target = int(pid or 0)
            if target > 0:
                participant_ids.add(target)
        for pid in participant_ids:
            try:
                cur.execute(
                    """
                    INSERT INTO chat_participants (thread_id, user_id, active, joined_at)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (thread_id, user_id) DO UPDATE SET active=1
                    """,
                    (thread_id, int(pid)),
                )
            except Exception:
                cur.execute(
                    """
                    UPDATE chat_participants
                    SET active=1
                    WHERE thread_id=? AND user_id=?
                    """,
                    (thread_id, int(pid)),
                )
                if int(cur.rowcount or 0) <= 0:
                    cur.execute(
                        """
                        INSERT INTO chat_participants (thread_id, user_id, active, joined_at)
                        VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                        """,
                        (thread_id, int(pid)),
                    )
        conn.commit()
        cur.execute(
            """
            SELECT id, thread_type, direct_key, group_id, title, created_by, created_at, updated_at
            FROM chat_threads
            WHERE id=?
            LIMIT 1
            """,
            (thread_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def list_admin_support_threads(limit: int = 120) -> list[dict]:
    ensure_universal_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    lim = max(1, min(500, int(limit or 120)))
    try:
        cur.execute(
            """
            SELECT
                t.id,
                t.thread_type,
                t.direct_key,
                t.group_id,
                t.title,
                t.created_by as user_id,
                t.created_at,
                t.updated_at,
                (
                    SELECT m.message_text
                    FROM chat_messages m
                    WHERE m.thread_id=t.id
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_message,
                (
                    SELECT m.created_at
                    FROM chat_messages m
                    WHERE m.thread_id=t.id
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_message_at,
                (
                    SELECT COUNT(*)
                    FROM chat_messages um
                    WHERE um.thread_id=t.id
                      AND um.sender_role != 'admin'
                      AND NOT EXISTS (
                          SELECT 1 FROM chat_participants p 
                          WHERE p.thread_id=t.id
                            AND p.user_id=t.created_by
                            AND um.id <= COALESCE(p.last_read_message_id, 0)
                      )
                ) AS unread_count
            FROM chat_threads t
            WHERE t.thread_type='admin_support'
            ORDER BY
                COALESCE(
                    (
                        SELECT m.created_at
                        FROM chat_messages m
                        WHERE m.thread_id=t.id
                        ORDER BY m.id DESC
                        LIMIT 1
                    ),
                    t.updated_at
                ) DESC,
                t.id DESC
            LIMIT ?
            """,
            (lim,)
        )
        return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()

def list_chat_threads_for_user(user_id: int, limit: int = 120) -> list[dict]:
    ensure_universal_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    lim = max(1, min(500, int(limit or 120)))
    uid = int(user_id or 0)
    if uid <= 0:
        conn.close()
        return []
    try:
        cur.execute(
            """
            SELECT
                t.id,
                t.thread_type,
                t.direct_key,
                t.group_id,
                t.title,
                t.created_by,
                t.created_at,
                t.updated_at,
                p.last_read_message_id,
                (
                    SELECT m.message_text
                    FROM chat_messages m
                    WHERE m.thread_id=t.id
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_message,
                (
                    SELECT m.created_at
                    FROM chat_messages m
                    WHERE m.thread_id=t.id
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_message_at,
                (
                    SELECT COUNT(*)
                    FROM chat_messages um
                    WHERE um.thread_id=t.id
                      AND um.id > COALESCE(p.last_read_message_id, 0)
                      AND um.sender_id <> ?
                ) AS unread_count
            FROM chat_threads t
            JOIN chat_participants p ON p.thread_id=t.id
            WHERE p.user_id=?
              AND COALESCE(p.active, 1)=1
            ORDER BY
                COALESCE(
                    (
                        SELECT m.created_at
                        FROM chat_messages m
                        WHERE m.thread_id=t.id
                        ORDER BY m.id DESC
                        LIMIT 1
                    ),
                    t.updated_at
                ) DESC,
                t.id DESC
            LIMIT ?
            """,
            (uid, uid, lim),
        )
        return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def list_chat_messages(thread_id: int, after_id: int = 0, limit: int = 80) -> list[dict]:
    ensure_universal_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    lim = max(1, min(1000, int(limit or 80)))
    aft = max(0, int(after_id or 0))
    try:
        cur.execute(
            """
            SELECT
                m.id,
                m.thread_id,
                m.sender_id,
                m.sender_role,
                m.message_text,
                m.reply_to_message_id,
                m.client_message_id,
                m.created_at,
                rm.sender_id AS reply_sender_id,
                rm.sender_role AS reply_sender_role,
                rm.message_text AS reply_message_text,
                rm.created_at AS reply_created_at
            FROM chat_messages m
            LEFT JOIN chat_messages rm ON rm.id = m.reply_to_message_id
            WHERE m.thread_id=? AND m.id>?
            ORDER BY id ASC
            LIMIT ?
            """,
            (int(thread_id), aft, lim),
        )
        return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def add_chat_message(
    thread_id: int,
    sender_id: int,
    sender_role: str | None,
    message_text: str,
    *,
    reply_to_message_id: int | None = None,
    client_message_id: str | None = None,
) -> dict | None:
    ensure_universal_chat_schema()
    text = str(message_text or "").strip()
    if not text:
        return None
    text = text[:16000]
    reply_id = int(reply_to_message_id or 0)
    reply_id = reply_id if reply_id > 0 else None
    client_id = (str(client_message_id or "").strip()[:120] or None)
    conn = get_conn()
    cur = conn.cursor()
    try:
        if client_id:
            cur.execute(
                """
                SELECT id, thread_id, sender_id, sender_role, message_text, reply_to_message_id, client_message_id, created_at
                FROM chat_messages
                WHERE thread_id=? AND sender_id=? AND client_message_id=?
                LIMIT 1
                """,
                (int(thread_id), int(sender_id), client_id),
            )
            existing = cur.fetchone()
            if existing:
                return dict(existing)
        cur.execute(
            """
            INSERT INTO chat_messages (thread_id, sender_id, sender_role, message_text, reply_to_message_id, client_message_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                int(thread_id),
                int(sender_id),
                (str(sender_role or "").strip() or None),
                text,
                reply_id,
                client_id,
            ),
        )
        message_id = int(getattr(cur, "lastrowid", 0) or 0)
        if not message_id:
            cur.execute("SELECT currval(pg_get_serial_sequence('chat_messages', 'id')) as id")
            row = cur.fetchone()
            message_id = int((row or {}).get("id") or 0)

        cur.execute(
            """
            UPDATE chat_threads
            SET updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (int(thread_id),),
        )
        conn.commit()
        cur.execute(
            """
            SELECT id, thread_id, sender_id, sender_role, message_text, reply_to_message_id, client_message_id, created_at
            FROM chat_messages
            WHERE id=?
            LIMIT 1
            """,
            (message_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def mark_chat_read(thread_id: int, user_id: int, last_message_id: int | None = None) -> int:
    ensure_universal_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        target_id = int(last_message_id or 0)
        if target_id <= 0:
            cur.execute("SELECT id FROM chat_messages WHERE thread_id=? ORDER BY id DESC LIMIT 1", (int(thread_id),))
            row = cur.fetchone()
            target_id = int((dict(row) if row else {}).get("id") or 0)
        cur.execute(
            """
            SELECT last_read_message_id
            FROM chat_participants
            WHERE thread_id=? AND user_id=?
            LIMIT 1
            """,
            (int(thread_id), int(user_id)),
        )
        prev_row = cur.fetchone()
        prev_id = int((dict(prev_row) if prev_row else {}).get("last_read_message_id") or 0)
        effective = max(prev_id, target_id)
        cur.execute(
            """
            UPDATE chat_participants
            SET last_read_message_id=?, last_read_at=CURRENT_TIMESTAMP, active=1
            WHERE thread_id=? AND user_id=?
            """,
            (effective, int(thread_id), int(user_id)),
        )
        conn.commit()
        return effective
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def get_unread_chat_count(user_id: int) -> int:
    rows = list_chat_threads_for_user(int(user_id), limit=500)
    total = 0
    for row in rows:
        total += max(0, int(row.get("unread_count") or 0))
    return int(total)


def create_media_asset(
    *,
    asset_type: str,
    storage_path: str,
    original_name: str | None = None,
    content_type: str | None = None,
    size_bytes: int | None = None,
    uploaded_by: int | None = None,
) -> dict | None:
    ensure_media_assets_schema()
    safe_asset_type = (str(asset_type or "").strip().lower() or "file")[:40]
    safe_storage_path = str(storage_path or "").strip()
    if not safe_storage_path:
        return None
    safe_original_name = (str(original_name or "").strip() or None)
    safe_content_type = (str(content_type or "").strip().lower() or None)
    safe_size = int(size_bytes or 0)
    if safe_size < 0:
        safe_size = 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        upload_user_id = int(uploaded_by or 0) or None
        try:
            cur.execute(
                """
                INSERT INTO media_assets (asset_type, storage_path, original_name, content_type, size_bytes, uploaded_by, is_active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    safe_asset_type,
                    safe_storage_path,
                    safe_original_name,
                    safe_content_type,
                    safe_size or None,
                    upload_user_id,
                ),
            )
        except Exception as first_exc:
            # Fallback: if uploader FK/reference is invalid in mixed legacy states, preserve asset row without uploaded_by.
            if upload_user_id is not None:
                logger.warning("create_media_asset fallback without uploaded_by: %s", str(first_exc))
                cur.execute(
                    """
                    INSERT INTO media_assets (asset_type, storage_path, original_name, content_type, size_bytes, uploaded_by, is_active)
                    VALUES (?, ?, ?, ?, ?, NULL, 1)
                    """,
                    (
                        safe_asset_type,
                        safe_storage_path,
                        safe_original_name,
                        safe_content_type,
                        safe_size or None,
                    ),
                )
            else:
                raise

        asset_id = int(getattr(cur, "lastrowid", 0) or 0)
        if not asset_id:
            # Postgres cursor may not expose lastrowid. Resolve by latest matching row.
            cur.execute(
                """
                SELECT id
                FROM media_assets
                WHERE storage_path=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (safe_storage_path,),
            )
            row = cur.fetchone()
            if isinstance(row, dict):
                asset_id = int(row.get("id") or 0)
            elif row:
                try:
                    asset_id = int(row[0] or 0)
                except Exception:
                    asset_id = 0
        conn.commit()
        if asset_id <= 0:
            return None
        cur.execute(
            """
            SELECT id, asset_type, storage_path, original_name, content_type, size_bytes, uploaded_by, is_active, created_at
            FROM media_assets
            WHERE id=?
            LIMIT 1
            """,
            (asset_id,),
        )
        row = cur.fetchone()
        if isinstance(row, dict):
            return row
        if row:
            return _row_to_dict(row)
        return None
    except Exception as exc:
        logger.exception("create_media_asset failed: %s", str(exc))
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def get_media_asset(asset_id: int) -> dict | None:
    ensure_media_assets_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, asset_type, storage_path, original_name, content_type, size_bytes, uploaded_by, is_active, created_at
            FROM media_assets
            WHERE id=?
            LIMIT 1
            """,
            (int(asset_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_diamondvoy_chat(user_id: int, title: str | None = None) -> dict | None:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    safe_title = (title or "").strip()[:160] or None
    try:
        cur.execute(
            """
            INSERT INTO diamondvoy_chats (user_id, title, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (int(user_id), safe_title),
        )
        chat_id = int(getattr(cur, "lastrowid", 0) or 0)
        if not chat_id:
            # Postgres path
            cur.execute("SELECT currval(pg_get_serial_sequence('diamondvoy_chats', 'id')) as id")
            row = cur.fetchone()
            chat_id = int((row or {}).get("id") or 0)
        conn.commit()
        cur.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM diamondvoy_chats
            WHERE id=?
            """,
            (chat_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def get_diamondvoy_chat_for_user(user_id: int, chat_id: int) -> dict | None:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM diamondvoy_chats
            WHERE id=? AND user_id=?
            """,
            (int(chat_id), int(user_id)),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_diamondvoy_chat(chat_id: int) -> dict | None:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM diamondvoy_chats
            WHERE id=?
            """,
            (int(chat_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_diamondvoy_chats_for_user(user_id: int, limit: int = 30) -> list[dict]:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    lim = max(1, min(60, int(limit or 30)))
    try:
        cur.execute(
            """
            SELECT
                c.id,
                c.user_id,
                c.title,
                c.created_at,
                c.updated_at,
                (
                    SELECT m.content
                    FROM diamondvoy_chat_messages m
                    WHERE m.chat_id = c.id
                    ORDER BY m.id DESC
                    LIMIT 1
                ) AS last_message_preview
            FROM diamondvoy_chats c
            WHERE c.user_id=?
            ORDER BY c.updated_at DESC, c.id DESC
            LIMIT ?
            """,
            (int(user_id), lim),
        )
        return [dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def list_diamondvoy_chat_messages(chat_id: int, limit: int = 300) -> list[dict]:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    lim = max(1, min(1000, int(limit or 300)))
    try:
        cur.execute(
            """
            SELECT id, chat_id, role, content, created_at
            FROM diamondvoy_chat_messages
            WHERE chat_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(chat_id), lim),
        )
        rows = [dict(r) for r in (cur.fetchall() or [])]
        rows.reverse()
        return rows
    finally:
        conn.close()


def add_diamondvoy_chat_message(chat_id: int, role: str, content: str) -> dict | None:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    role_clean = str(role or "").strip().lower()
    if role_clean not in {"user", "assistant", "system"}:
        role_clean = "assistant"
    text = str(content or "").strip()
    if not text:
        return None
    text = text[:32000]
    try:
        cur.execute(
            """
            INSERT INTO diamondvoy_chat_messages (chat_id, role, content)
            VALUES (?, ?, ?)
            """,
            (int(chat_id), role_clean, text),
        )
        message_id = int(getattr(cur, "lastrowid", 0) or 0)
        if not message_id:
            cur.execute("SELECT currval(pg_get_serial_sequence('diamondvoy_chat_messages', 'id')) as id")
            row = cur.fetchone()
            message_id = int((row or {}).get("id") or 0)
        cur.execute(
            """
            UPDATE diamondvoy_chats
            SET updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (int(chat_id),),
        )
        conn.commit()
        cur.execute(
            """
            SELECT id, chat_id, role, content, created_at
            FROM diamondvoy_chat_messages
            WHERE id=?
            """,
            (message_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return None
    finally:
        conn.close()


def update_diamondvoy_chat_title(chat_id: int, title: str | None) -> None:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        safe_title = (title or "").strip()[:160] or None
        cur.execute(
            """
            UPDATE diamondvoy_chats
            SET title=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (safe_title, int(chat_id)),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def delete_diamondvoy_chat_for_user(user_id: int, chat_id: int) -> bool:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM diamondvoy_chat_messages WHERE chat_id IN (SELECT id FROM diamondvoy_chats WHERE id=? AND user_id=?)",
            (int(chat_id), int(user_id)),
        )
        cur.execute(
            "DELETE FROM diamondvoy_chats WHERE id=? AND user_id=?",
            (int(chat_id), int(user_id)),
        )
        changed = int(getattr(cur, "rowcount", 0) or 0) > 0
        conn.commit()
        return changed
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def delete_diamondvoy_chats_older_than_hours(hours: int = 168) -> int:
    ensure_diamondvoy_chat_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cutoff_student = datetime.utcnow() - timedelta(hours=max(1, int(hours or 72)))
        cutoff_teacher = datetime.utcnow() - timedelta(hours=504) # 3 weeks
        
        cur.execute(
            """
            DELETE FROM diamondvoy_chat_messages
            WHERE chat_id IN (
                SELECT c.id FROM diamondvoy_chats c
                JOIN users u ON u.id = c.user_id
                WHERE (u.login_type != 3 AND c.updated_at < ?)
                   OR (u.login_type = 3 AND c.updated_at < ?)
            )
            """,
            (cutoff_student, cutoff_teacher),
        )
        cur.execute(
            """
            DELETE FROM diamondvoy_chats
            WHERE id IN (
                SELECT c.id FROM diamondvoy_chats c
                JOIN users u ON u.id = c.user_id
                WHERE (u.login_type != 3 AND c.updated_at < ?)
                   OR (u.login_type = 3 AND c.updated_at < ?)
            )
            """, 
            (cutoff_student, cutoff_teacher)
        )
        deleted = int(getattr(cur, "rowcount", 0) or 0)
        conn.commit()
        return deleted
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def log_diamondvoy_query(
    user_id: int | None,
    query: str,
    response: str | None,
    *,
    subject: str | None = None,
    bot_scope: str | None = None,
) -> None:
    ensure_diamondvoy_history_table()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO diamondvoy_history (user_id, query_text, response_text, subject, bot_scope)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, (query or "")[:8000], (response or "")[:16000] if response else None, subject, bot_scope),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def delete_diamondvoy_history_older_than_days(days: int = 30) -> int:
    ensure_diamondvoy_history_table()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cutoff = datetime.utcnow() - timedelta(days=int(days))
        cur.execute("DELETE FROM diamondvoy_history WHERE created_at < ?", (cutoff,))
        n = int(getattr(cur, "rowcount", 0) or 0)
        conn.commit()
        return n
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def get_duel_session(session_id: int) -> dict | None:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM open_duel_sessions WHERE id=?", (int(session_id),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def join_duel_session(session_id: int, user_id: int, chat_id: int, team_no: int = 1) -> bool:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO arena_duel_match_participants(session_id, user_id, chat_id, team_no)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (session_id, user_id) DO NOTHING
            """,
            (int(session_id), int(user_id), int(chat_id), int(team_no)),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def count_duel_participants(session_id: int) -> int:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM arena_duel_match_participants WHERE session_id=?", (int(session_id),))
        row = cur.fetchone()
        return int((row or {}).get("cnt") or 0)
    finally:
        conn.close()


def list_duel_participants(session_id: int) -> list[dict]:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT *
            FROM arena_duel_match_participants
            WHERE session_id=?
            ORDER BY joined_at ASC, id ASC
            """,
            (int(session_id),),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def mark_duel_session_started(session_id: int) -> None:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE open_duel_sessions SET status='running', started_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(session_id),),
        )
        conn.commit()
    finally:
        conn.close()


def mark_duel_session_finished(session_id: int) -> None:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE open_duel_sessions SET status='finished', finished_at=CURRENT_TIMESTAMP WHERE id=?",
            (int(session_id),),
        )
        conn.commit()
    finally:
        conn.close()


def cancel_expired_open_duel_sessions(now_iso: str) -> list[dict]:
    """Cancel expired sessions and return participants who must be refunded."""
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM open_duel_sessions
            WHERE status='open' AND expires_at IS NOT NULL AND expires_at <= ?
            """,
            (now_iso,),
        )
        sids = [int(r["id"]) for r in cur.fetchall()]
        if not sids:
            return []
        refunds: list[dict] = []
        for sid in sids:
            cur.execute("UPDATE open_duel_sessions SET status='canceled', finished_at=CURRENT_TIMESTAMP WHERE id=?", (sid,))
            cur.execute(
                """
                SELECT session_id, user_id, chat_id
                FROM arena_duel_match_participants
                WHERE session_id=? AND refunded_fee=0
                """,
                (sid,),
            )
            refunds.extend([dict(r) for r in cur.fetchall()])
        conn.commit()
        return refunds
    finally:
        conn.close()


def mark_duel_participant_refunded(session_id: int, user_id: int) -> None:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE arena_duel_match_participants SET refunded_fee=1 WHERE session_id=? AND user_id=?",
            (int(session_id), int(user_id)),
        )
        conn.commit()
    finally:
        conn.close()


def save_duel_participant_result(
    session_id: int,
    user_id: int,
    *,
    correct: int,
    wrong: int,
    unanswered: int,
    is_winner: bool,
    last_opponent_user_id: int | None = None,
) -> None:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE arena_duel_match_participants
            SET result_correct=?, result_wrong=?, result_unanswered=?, is_winner=?, last_opponent_user_id=?
            WHERE session_id=? AND user_id=?
            """,
            (int(correct), int(wrong), int(unanswered), 1 if is_winner else 0, last_opponent_user_id, int(session_id), int(user_id)),
        )
        conn.commit()
    finally:
        conn.close()


def create_revenge_token(user_id: int, opponent_user_id: int, mode: str, subject: str, expires_at_iso: str) -> None:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO arena_duel_revenge_tokens(user_id, opponent_user_id, mode, subject, expires_at, used)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (int(user_id), int(opponent_user_id), mode, subject, expires_at_iso),
        )
        conn.commit()
    finally:
        conn.close()


def consume_valid_revenge_token(user_id: int, opponent_user_id: int, mode: str, subject: str, now_iso: str) -> bool:
    ensure_duel_matchmaking_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id
            FROM arena_duel_revenge_tokens
            WHERE user_id=? AND opponent_user_id=? AND mode=? AND subject=? AND used=0 AND expires_at > ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(user_id), int(opponent_user_id), mode, subject, now_iso),
        )
        row = cur.fetchone()
        if not row:
            return False
        cur.execute("UPDATE arena_duel_revenge_tokens SET used=1 WHERE id=?", (int(row["id"]),))
        conn.commit()
        return True
    finally:
        conn.close()


# --- Scheduled Daily/Boss arena, duel daily quota, streak (D'coin extras) ---

def ensure_arena_extras_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_scheduled_runs (
                    id BIGSERIAL PRIMARY KEY,
                    run_kind TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    start_hhmm TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    min_players INTEGER NOT NULL DEFAULT 4,
                    max_players INTEGER NOT NULL DEFAULT 15,
                    current_stage INTEGER NOT NULL DEFAULT 0,
                    questions_generated_at TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    questions_promoted INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_kind, subject, run_date, start_hhmm)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_run_participants (
                    id BIGSERIAL PRIMARY KEY,
                    run_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    chat_id BIGINT NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fee_charged INTEGER NOT NULL DEFAULT 0,
                    eliminated_after_stage INTEGER,
                    stage_scores_json TEXT,
                    UNIQUE(run_id, user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_run_questions (
                    id BIGSERIAL PRIMARY KEY,
                    run_id BIGINT NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_run_answers (
                    id BIGSERIAL PRIMARY KEY,
                    run_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    is_correct INTEGER NOT NULL DEFAULT 0,
                    is_unanswered INTEGER NOT NULL DEFAULT 0,
                    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_id, user_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS duel_daily_usage (
                    user_id BIGINT NOT NULL,
                    usage_date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    plays INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, usage_date, mode)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_dcoin_streak (
                    user_id BIGINT PRIMARY KEY,
                    consecutive_qualifying_days INTEGER NOT NULL DEFAULT 0,
                    last_qualify_date TEXT,
                    win_streak INTEGER NOT NULL DEFAULT 0,
                    last_win_date TEXT,
                    cycle_day_index INTEGER NOT NULL DEFAULT 0,
                    last_cycle_award_date TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_season_notify (
                    subject TEXT NOT NULL,
                    season_ym TEXT NOT NULL,
                    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(subject, season_ym)
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_scheduled_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_kind TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    start_hhmm TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    min_players INTEGER NOT NULL DEFAULT 4,
                    max_players INTEGER NOT NULL DEFAULT 15,
                    current_stage INTEGER NOT NULL DEFAULT 0,
                    questions_generated_at TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    questions_promoted INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_kind, subject, run_date, start_hhmm)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_run_participants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    chat_id INTEGER NOT NULL,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fee_charged INTEGER NOT NULL DEFAULT 0,
                    eliminated_after_stage INTEGER,
                    stage_scores_json TEXT,
                    UNIQUE(run_id, user_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_run_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_run_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    is_correct INTEGER NOT NULL DEFAULT 0,
                    is_unanswered INTEGER NOT NULL DEFAULT 0,
                    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(run_id, user_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS duel_daily_usage (
                    user_id INTEGER NOT NULL,
                    usage_date TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    plays INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, usage_date, mode)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS user_dcoin_streak (
                    user_id INTEGER PRIMARY KEY,
                    consecutive_qualifying_days INTEGER NOT NULL DEFAULT 0,
                    last_qualify_date TEXT,
                    win_streak INTEGER NOT NULL DEFAULT 0,
                    last_win_date TEXT,
                    cycle_day_index INTEGER NOT NULL DEFAULT 0,
                    last_cycle_award_date TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_season_notify (
                    subject TEXT NOT NULL,
                    season_ym TEXT NOT NULL,
                    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY(subject, season_ym)
                )
                """
            )
        conn.commit()
        # Migration for older DBs: add `is_unanswered` if it was missing.
        try:
            _ensure_arena_run_answers_is_unanswered_column()
        except Exception:
            pass
        # NOTE:
        # Do NOT auto-migrate `arena_scheduled_runs.questions_promoted` here.
        # It was causing startup hangs in some Postgres deployments.
        # We will handle it inside the promotion scheduler at runtime.
    finally:
        conn.close()


def _ensure_arena_run_answers_is_unanswered_column() -> None:
    """
    Best-effort migration: add `is_unanswered` column if it exists as an older schema.
    """
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            # Postgres supports IF NOT EXISTS; sqlite might not.
            cur.execute("ALTER TABLE arena_run_answers ADD COLUMN IF NOT EXISTS is_unanswered INTEGER NOT NULL DEFAULT 0")
        except Exception:
            try:
                cur.execute("ALTER TABLE arena_run_answers ADD COLUMN is_unanswered INTEGER NOT NULL DEFAULT 0")
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


def _ensure_arena_scheduled_runs_questions_promoted_column() -> None:
    """
    Best-effort migration: add `arena_scheduled_runs.questions_promoted` if missing.
    Uses information_schema check to avoid relying on CREATE TABLE IF NOT EXISTS
    for already-existing deployments.
    """
    if not _is_postgres_enabled():
        return

    conn = get_conn()
    cur = conn.cursor()
    try:
        # Keep ALTER fast; avoid scheduler deadlocks due to locks.
        try:
            cur.execute("SET LOCAL statement_timeout = '10s'")
        except Exception:
            pass

        # Check column existence in Postgres system catalog.
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name='arena_scheduled_runs'
              AND column_name='questions_promoted'
            LIMIT 1
            """
        )
        exists = cur.fetchone() is not None
        if exists:
            return

        # Add the column with default 0 so existing rows are safe.
        try:
            cur.execute(
                "ALTER TABLE arena_scheduled_runs ADD COLUMN IF NOT EXISTS questions_promoted INTEGER NOT NULL DEFAULT 0"
            )
        except Exception:
            cur.execute(
                "ALTER TABLE arena_scheduled_runs ADD COLUMN questions_promoted INTEGER NOT NULL DEFAULT 0"
            )
        conn.commit()
    finally:
        conn.close()


def get_or_create_scheduled_arena_run(
    *,
    run_kind: str,
    subject: str,
    run_date: str,
    start_hhmm: str,
    min_players: int = 4,
    max_players: int = 15,
) -> int:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM arena_scheduled_runs
            WHERE run_kind=? AND subject=? AND run_date=? AND start_hhmm=?
            """,
            (run_kind, subject, run_date, start_hhmm),
        )
        row = cur.fetchone()
        if row:
            return int(row["id"])
        cur.execute(
            """
            INSERT INTO arena_scheduled_runs(run_kind, subject, run_date, start_hhmm, min_players, max_players, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            RETURNING id
            """,
            (run_kind, subject, run_date, start_hhmm, int(min_players), int(max_players)),
        )
        rid = int(cur.fetchone()["id"])
        conn.commit()
        return rid
    finally:
        conn.close()


def get_scheduled_arena_run(run_id: int) -> dict | None:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM arena_scheduled_runs WHERE id=?", (int(run_id),))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_scheduled_arena_run(run_id: int, **kwargs: Any) -> None:
    ensure_arena_extras_schema()
    if not kwargs:
        return
    keys = [k for k in kwargs if kwargs[k] is not None]
    if not keys:
        return
    sets = ", ".join(f"{k}=?" for k in keys)
    vals = [kwargs[k] for k in keys] + [int(run_id)]
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE arena_scheduled_runs SET {sets} WHERE id=?",
            tuple(vals),
        )
        conn.commit()
    finally:
        conn.close()


def register_arena_run_participant(run_id: int, user_id: int, chat_id: int) -> bool:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO arena_run_participants(run_id, user_id, chat_id)
            VALUES (?, ?, ?)
            ON CONFLICT(run_id, user_id) DO NOTHING
            """,
            (int(run_id), int(user_id), int(chat_id)),
        )
        conn.commit()
        return (cur.rowcount or 0) > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def count_arena_run_participants(run_id: int) -> int:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) as c FROM arena_run_participants WHERE run_id=?",
            (int(run_id),),
        )
        return int((cur.fetchone() or {}).get("c") or 0)
    finally:
        conn.close()


def list_arena_run_participants(run_id: int) -> list[dict]:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM arena_run_participants WHERE run_id=? ORDER BY id ASC",
            (int(run_id),),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_arena_run_questions(run_id: int) -> None:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM arena_run_answers WHERE run_id=?", (int(run_id),))
        cur.execute("DELETE FROM arena_run_questions WHERE run_id=?", (int(run_id),))
        conn.commit()
    finally:
        conn.close()


def ensure_arena_run_questions_user_id_column() -> None:
    """Boss pool: per-user assignment; daily rows keep user_id NULL."""
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                "ALTER TABLE arena_run_questions ADD COLUMN IF NOT EXISTS user_id BIGINT"
            )
        else:
            try:
                cur.execute("ALTER TABLE arena_run_questions ADD COLUMN user_id INTEGER")
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


def ensure_arena_questions_tmp_schema() -> None:
    """
    Runtime temporary question pools for delayed promotion to `daily_tests_bank`.

    - Daily arena: `arena_daily_questions_tmp`
    - Boss arena: `arena_boss_questions_tmp`
    - Duel: `duel_1v1_questions_tmp`, `duel_5v5_questions_tmp`
    - Group arena: `arena_group_questions_tmp`
    """
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_daily_questions_tmp (
                    id BIGSERIAL PRIMARY KEY,
                    run_id BIGINT NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(run_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_boss_questions_tmp (
                    id BIGSERIAL PRIMARY KEY,
                    run_id BIGINT NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(run_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS duel_1v1_questions_tmp (
                    id BIGSERIAL PRIMARY KEY,
                    session_id BIGINT NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(session_id, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS duel_5v5_questions_tmp (
                    id BIGSERIAL PRIMARY KEY,
                    session_id BIGINT NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(session_id, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_group_questions_tmp (
                    id BIGSERIAL PRIMARY KEY,
                    session_id BIGINT NOT NULL,
                    q_index INTEGER NOT NULL,
                    bank_question_id BIGINT NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(session_id, q_index)
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_daily_questions_tmp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(run_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_boss_questions_tmp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    stage INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(run_id, stage, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS duel_1v1_questions_tmp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(session_id, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS duel_5v5_questions_tmp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(session_id, q_index)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS arena_group_questions_tmp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    q_index INTEGER NOT NULL,
                    bank_question_id INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    promoted_at TIMESTAMP,
                    UNIQUE(session_id, q_index)
                )
                """
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def insert_arena_run_question(
    run_id: int,
    stage: int,
    q_index: int,
    payload_json: str,
    user_id: Optional[int] = None,
) -> None:
    ensure_arena_run_questions_user_id_column()
    ensure_arena_extras_schema()
    ensure_arena_questions_tmp_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO arena_run_questions(run_id, stage, q_index, payload_json, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(run_id), int(stage), int(q_index), payload_json, user_id),
        )
        # Also write the same payload into type-specific tmp tables for delayed promotion.
        try:
            cache = getattr(insert_arena_run_question, "_run_kind_cache", None)
            if cache is None:
                cache = {}
                setattr(insert_arena_run_question, "_run_kind_cache", cache)

            run_kind = cache.get(int(run_id))
            if run_kind is None:
                cur.execute("SELECT run_kind FROM arena_scheduled_runs WHERE id=?", (int(run_id),))
                rr = cur.fetchone()
                run_kind = (rr or {}).get("run_kind") if rr else None
                cache[int(run_id)] = run_kind

            if run_kind == "daily":
                cur.execute(
                    """
                    INSERT INTO arena_daily_questions_tmp(run_id, stage, q_index, payload_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (run_id, stage, q_index) DO UPDATE SET
                        payload_json=excluded.payload_json,
                        promoted_at=NULL
                    """,
                    (int(run_id), int(stage), int(q_index), payload_json),
                )
            elif run_kind == "boss":
                cur.execute(
                    """
                    INSERT INTO arena_boss_questions_tmp(run_id, stage, q_index, payload_json)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (run_id, stage, q_index) DO UPDATE SET
                        payload_json=excluded.payload_json,
                        promoted_at=NULL
                    """,
                    (int(run_id), int(stage), int(q_index), payload_json),
                )
        except Exception:
            # Tmp promotion is best-effort; never break the running event.
            pass

        conn.commit()
    finally:
        conn.close()


def insert_duel_questions_tmp(
    mode: str,
    session_id: int,
    questions: list[dict],
    level: str,
) -> None:
    """
    Store duel questions in tmp table for delayed promotion to daily_tests_bank.
    """
    if not _is_postgres_enabled():
        return
    ensure_arena_questions_tmp_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        import json

        for idx, q in enumerate(questions, start=1):
            payload = {
                "question": str(q.get("question") or ""),
                "option_a": str(q.get("option_a") or ""),
                "option_b": str(q.get("option_b") or ""),
                "option_c": str(q.get("option_c") or ""),
                "option_d": str(q.get("option_d") or ""),
                "correct_option_index": int(q.get("correct_option_index") or 1),
                "question_type": str(q.get("question_type") or "mcq"),
            }
            cur.execute(
                """
                INSERT INTO duel_questions_tmp (mode, session_id, q_index, payload_json, level)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (session_id, q_index) DO NOTHING
                """,
                (mode, int(session_id), idx, json.dumps(payload, ensure_ascii=False), level),
            )
        conn.commit()
    except Exception:
        logger.exception("insert_duel_questions_tmp failed")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def fetch_duel_questions_for_session(session_id: int, mode: str = "1v1") -> list[dict]:
    """
    Fetch cached duel questions for a session to avoid regeneration.
    """
    if not _is_postgres_enabled():
        return []
    try:
        ensure_arena_questions_tmp_schema()
    except Exception:
        return []
    
    mode = (mode or "1v1").strip().lower()
    if mode == "1v1":
        table = "duel_1v1_questions_tmp"
    elif mode == "5v5":
        table = "duel_5v5_questions_tmp"
    else:
        return []
    
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT q_index, payload_json
            FROM {table}
            WHERE session_id=?
            ORDER BY q_index ASC
            """,
            (int(session_id),),
        )
        rows = cur.fetchall() or []
        questions = []
        import json
        for r in rows:
            try:
                payload = json.loads(r["payload_json"] or "{}")
                questions.append(payload)
            except Exception:
                logger.exception("Failed to parse duel question payload")
                continue
        return questions
    except Exception:
        logger.exception("fetch_duel_questions_for_session failed")
        return []
    finally:
        conn.close()


def insert_duel_questions_tmp_original(
    mode: str,
    session_id: int,
    questions: list[dict],
    *,
    level: str | None = None,
) -> None:
    """Insert duel runtime questions into the correct tmp pool table."""
    ensure_arena_questions_tmp_schema()
    if not questions:
        return

    import json

    mode = (mode or "").strip().lower()
    if mode == "1v1":
        table = "duel_1v1_questions_tmp"
    elif mode == "5v5":
        table = "duel_5v5_questions_tmp"
    else:
        return

    conn = get_conn()
    cur = conn.cursor()
    try:
        rows = []
        for i, q in enumerate(questions, start=1):
            payload = {
                "question": str(q.get("question") or "").strip(),
                "option_a": str(q.get("option_a") or "").strip(),
                "option_b": str(q.get("option_b") or "").strip(),
                "option_c": str(q.get("option_c") or "").strip(),
                "option_d": str(q.get("option_d") or "").strip(),
                "correct_option_index": int(q.get("correct_option_index") or 1),
                "level": str(level or "").strip() or None,
                "created_by": int(q.get("created_by") or 0),
                "question_type": q.get("question_type"),
            }
            rows.append((int(session_id), int(i), json.dumps(payload, ensure_ascii=False)))

        cur.executemany(
            f"""
            INSERT INTO {table}(session_id, q_index, payload_json)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id, q_index) DO UPDATE SET
                payload_json=excluded.payload_json,
                promoted_at=NULL
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def fetch_arena_run_questions(
    run_id: int,
    stage: int | None = None,
    user_id: Optional[int] = None,
) -> list[dict]:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if stage is not None and user_id is not None:
            cur.execute(
                """
                SELECT * FROM arena_run_questions
                WHERE run_id=? AND stage=? AND user_id=?
                ORDER BY q_index ASC
                """,
                (int(run_id), int(stage), int(user_id)),
            )
        elif stage is not None:
            cur.execute(
                """
                SELECT * FROM arena_run_questions
                WHERE run_id=? AND stage=? AND user_id IS NULL
                ORDER BY q_index ASC
                """,
                (int(run_id), int(stage)),
            )
        else:
            cur.execute(
                "SELECT * FROM arena_run_questions WHERE run_id=? ORDER BY stage ASC, q_index ASC",
                (int(run_id),),
            )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def record_arena_run_answer(
    run_id: int,
    user_id: int,
    stage: int,
    q_index: int,
    is_correct: int,
    is_unanswered: int = 0,
) -> None:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE FROM arena_run_answers
            WHERE run_id=? AND user_id=? AND stage=? AND q_index=?
            """,
            (int(run_id), int(user_id), int(stage), int(q_index)),
        )
        cur.execute(
            """
            INSERT INTO arena_run_answers(run_id, user_id, stage, q_index, is_correct, is_unanswered)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(run_id), int(user_id), int(stage), int(q_index), int(is_correct), int(is_unanswered)),
        )
        conn.commit()
    finally:
        conn.close()


def get_arena_run_user_stage_answer_stats(
    *,
    run_id: int,
    user_id: int,
    stage: int,
) -> dict[str, int]:
    """
    Returns {correct, wrong, unanswered} for a single (run_id, user_id, stage).
    """
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END), 0) AS correct,
                COALESCE(SUM(CASE WHEN is_unanswered=1 THEN 1 ELSE 0 END), 0) AS unanswered,
                COALESCE(SUM(CASE WHEN is_correct=0 AND is_unanswered=0 THEN 1 ELSE 0 END), 0) AS wrong
            FROM arena_run_answers
            WHERE run_id=? AND user_id=? AND stage=?
            """,
            (int(run_id), int(user_id), int(stage)),
        )
        row = cur.fetchone() or {}
        return {
            "correct": int(row.get("correct") or 0),
            "wrong": int(row.get("wrong") or 0),
            "unanswered": int(row.get("unanswered") or 0),
        }
    finally:
        conn.close()


def list_arena_run_users_stage_answer_stats(
    *,
    run_id: int,
    stage: int,
) -> list[dict]:
    """
    Returns rows with {user_id, correct, wrong, unanswered} for a given stage.
    """
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                user_id,
                COALESCE(SUM(CASE WHEN is_correct=1 THEN 1 ELSE 0 END), 0) AS correct,
                COALESCE(SUM(CASE WHEN is_unanswered=1 THEN 1 ELSE 0 END), 0) AS unanswered,
                COALESCE(SUM(CASE WHEN is_correct=0 AND is_unanswered=0 THEN 1 ELSE 0 END), 0) AS wrong
            FROM arena_run_answers
            WHERE run_id=? AND stage=?
            GROUP BY user_id
            ORDER BY user_id ASC
            """,
            (int(run_id), int(stage)),
        )
        rows = cur.fetchall() or []
        return [dict(r) for r in rows]
    finally:
        conn.close()


def leaderboard_users_through_stage(run_id: int, through_stage: int) -> list[tuple[int, int]]:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, COALESCE(SUM(is_correct), 0) AS s
            FROM arena_run_answers
            WHERE run_id=? AND stage <= ?
            GROUP BY user_id
            ORDER BY s DESC, user_id ASC
            """,
            (int(run_id), int(through_stage)),
        )
        return [(int(r["user_id"]), int(r["s"])) for r in cur.fetchall()]
    finally:
        conn.close()


def leaderboard_users_single_stage(run_id: int, stage: int) -> list[tuple[int, int]]:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT user_id, COALESCE(SUM(is_correct), 0) AS s
            FROM arena_run_answers
            WHERE run_id=? AND stage=?
            GROUP BY user_id
            ORDER BY s DESC, user_id ASC
            """,
            (int(run_id), int(stage)),
        )
        return [(int(r["user_id"]), int(r["s"])) for r in cur.fetchall()]
    finally:
        conn.close()


def mark_participant_eliminated(run_id: int, user_id: int, after_stage: int) -> None:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE arena_run_participants
            SET eliminated_after_stage=?
            WHERE run_id=? AND user_id=?
            """,
            (int(after_stage), int(run_id), int(user_id)),
        )
        conn.commit()
    finally:
        conn.close()


def list_non_eliminated_participants(run_id: int) -> list[dict]:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT * FROM arena_run_participants
            WHERE run_id=? AND eliminated_after_stage IS NULL
            ORDER BY id ASC
            """,
            (int(run_id),),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def boss_aggregate_stats(run_id: int) -> tuple[int, int]:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(*) AS c, COALESCE(SUM(is_correct), 0) AS s
            FROM arena_run_answers
            WHERE run_id=?
            """,
            (int(run_id),),
        )
        row = cur.fetchone() or {}
        return int(row.get("c") or 0), int(row.get("s") or 0)
    finally:
        conn.close()


def assign_boss_question_pool_to_user(run_id: int, user_id: int, count: int = 3) -> list[dict]:
    ensure_arena_run_questions_user_id_column()
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE arena_run_questions SET user_id=?
            WHERE rowid IN (
                SELECT rowid FROM arena_run_questions
                WHERE run_id=? AND user_id IS NULL AND stage=0
                ORDER BY q_index ASC
                LIMIT ?
            )
            """,
            (int(user_id), int(run_id), int(count)),
        )
        conn.commit()
        cur.execute(
            """
            SELECT * FROM arena_run_questions
            WHERE run_id=? AND user_id=? AND stage=0
            ORDER BY q_index ASC
            """,
            (int(run_id), int(user_id)),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def assign_boss_question_pool_to_user_pg(run_id: int, user_id: int, count: int = 3) -> list[dict]:
    ensure_arena_run_questions_user_id_column()
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE arena_run_questions AS q SET user_id=?
            FROM (
                SELECT id FROM arena_run_questions
                WHERE run_id=? AND user_id IS NULL AND stage=0
                ORDER BY q_index ASC
                LIMIT ?
            ) AS sub
            WHERE q.id = sub.id
            """,
            (int(user_id), int(run_id), int(count)),
        )
        conn.commit()
        cur.execute(
            """
            SELECT * FROM arena_run_questions
            WHERE run_id=? AND user_id=? AND stage=0
            ORDER BY q_index ASC
            """,
            (int(run_id), int(user_id)),
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def assign_boss_question_pool_to_user_auto(run_id: int, user_id: int, count: int = 3) -> list[dict]:
    if _is_postgres_enabled():
        return assign_boss_question_pool_to_user_pg(run_id, user_id, count)
    return assign_boss_question_pool_to_user(run_id, user_id, count)


def sum_user_boss_stage_answers(run_id: int, user_id: int) -> int:
    """Correct count for boss (stage=0)."""
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COALESCE(SUM(is_correct), 0) AS s
            FROM arena_run_answers
            WHERE run_id=? AND user_id=? AND stage=0
            """,
            (int(run_id), int(user_id)),
        )
        row = cur.fetchone() or {}
        return int(row.get("s") or 0)
    finally:
        conn.close()


def is_arena_run_participant(run_id: int, user_id: int) -> bool:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM arena_run_participants WHERE run_id=? AND user_id=? LIMIT 1",
            (int(run_id), int(user_id)),
        )
        return cur.fetchone() is not None
    finally:
        conn.close()


def duel_plays_today(user_id: int, mode: str, usage_date: str) -> int:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT plays FROM duel_daily_usage
            WHERE user_id=? AND usage_date=? AND mode=?
            """,
            (int(user_id), usage_date, mode),
        )
        row = cur.fetchone()
        return int((row or {}).get("plays") or 0)
    finally:
        conn.close()


def increment_duel_daily_usage(user_id: int, mode: str, usage_date: str) -> int:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        uid, d, m = int(user_id), usage_date, mode
        cur.execute(
            "SELECT plays FROM duel_daily_usage WHERE user_id=? AND usage_date=? AND mode=?",
            (uid, d, m),
        )
        row = cur.fetchone()
        if row:
            n = int(row["plays"] or 0) + 1
            cur.execute(
                "UPDATE duel_daily_usage SET plays=? WHERE user_id=? AND usage_date=? AND mode=?",
                (n, uid, d, m),
            )
        else:
            n = 1
            cur.execute(
                "INSERT INTO duel_daily_usage(user_id, usage_date, mode, plays) VALUES (?, ?, ?, 1)",
                (uid, d, m),
            )
        conn.commit()
        return n
    finally:
        conn.close()


def can_start_duel_today(user_id: int, mode: str, usage_date: str, limit_per_day: int = 50) -> bool:
    return duel_plays_today(user_id, mode, usage_date) < int(limit_per_day)


def _get_or_create_streak_row(conn, cur, user_id: int) -> dict:
    cur.execute("SELECT * FROM user_dcoin_streak WHERE user_id=?", (int(user_id),))
    row = cur.fetchone()
    if row:
        return dict(row)
    cur.execute(
        "INSERT INTO user_dcoin_streak(user_id) VALUES (?)",
        (int(user_id),),
    )
    conn.commit()
    cur.execute("SELECT * FROM user_dcoin_streak WHERE user_id=?", (int(user_id),))
    return dict(cur.fetchone() or {})


def process_duel_win_streak_bonus(user_id: int, subject: str, win_date: str) -> None:
    """Har 5 ketma-ket duel g'alaba: +10 D'point (bir marta)."""
    ensure_arena_extras_schema()
    subj = (subject or "English").strip().title() or "English"
    conn = get_conn()
    cur = conn.cursor()
    try:
        r = _get_or_create_streak_row(conn, cur, user_id)
        last = (r.get("last_win_date") or "").strip()
        ws = int(r.get("win_streak") or 0)
        if last == win_date:
            conn.close()
            return
        if last:
            from datetime import datetime, timedelta

            try:
                pd = datetime.strptime(last, "%Y-%m-%d").date()
                wd = datetime.strptime(win_date, "%Y-%m-%d").date()
                if (wd - pd).days != 1:
                    ws = 0
            except Exception:
                ws = 0
        ws += 1
        bonus = 0
        if ws >= 5:
            bonus = 10
            ws = 0
        cur.execute(
            """
            UPDATE user_dcoin_streak
            SET win_streak=?, last_win_date=?, updated_at=CURRENT_TIMESTAMP
            WHERE user_id=?
            """,
            (ws, win_date, int(user_id)),
        )
        conn.commit()
        conn.close()
        if bonus > 0:
            add_dpoints(int(user_id), float(bonus), subj, change_type="streak_duel_5wins")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


def process_daily_activity_streak_award(user_id: int, subject: str, qualify_date: str) -> None:
    """
    Kunlik 90%+ test yoki boshqa qualifying event: tsikl 1..30 kun, N-kunida +N D'point.
    Ketma-ket emas bo'lsa tsikl 1 dan.
    """
    ensure_arena_extras_schema()
    subj = (subject or "English").strip().title() or "English"
    conn = get_conn()
    cur = conn.cursor()
    try:
        r = _get_or_create_streak_row(conn, cur, user_id)
        last = (r.get("last_qualify_date") or "").strip()
        cycle = int(r.get("consecutive_qualifying_days") or 0)
        if last == qualify_date:
            conn.close()
            return
        from datetime import datetime

        if last:
            try:
                pd = datetime.strptime(last, "%Y-%m-%d").date()
                qd = datetime.strptime(qualify_date, "%Y-%m-%d").date()
                if (qd - pd).days == 1:
                    if cycle >= 30:
                        cycle = 1
                    else:
                        cycle = cycle + 1
                else:
                    cycle = 1
            except Exception:
                cycle = 1
        else:
            cycle = 1
        award = float(cycle)
        cur.execute(
            """
            UPDATE user_dcoin_streak
            SET consecutive_qualifying_days=?,
                last_qualify_date=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE user_id=?
            """,
            (cycle, qualify_date, int(user_id)),
        )
        conn.commit()
        conn.close()
        if award > 0:
            add_dpoints(int(user_id), award, subj, change_type=f"streak_daily_cycle_{cycle}")
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        conn.close()


def season_leaderboard_top_users(subject: str, limit: int = 10) -> list[dict]:
    ensure_subject_dcoin_schema()
    subj = (subject or "").strip().title()
    return get_leaderboard_by_subject(subj, limit=limit, offset=0)


def mark_season_notified(subject: str, season_ym: str) -> bool:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute(
                """
                INSERT INTO arena_season_notify(subject, season_ym)
                VALUES (?, ?)
                ON CONFLICT(subject, season_ym) DO NOTHING
                """,
                (subject, season_ym),
            )
        else:
            cur.execute(
                "INSERT OR IGNORE INTO arena_season_notify(subject, season_ym) VALUES (?, ?)",
                (subject, season_ym),
            )
        rc = cur.rowcount or 0
        conn.commit()
        return rc > 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def was_season_notified(subject: str, season_ym: str) -> bool:
    ensure_arena_extras_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM arena_season_notify WHERE subject=? AND season_ym=? LIMIT 1",
            (subject, season_ym),
        )
        return bool(cur.fetchone())
    finally:
        conn.close()


# Backward-compatible API surface for backend/main imports.
# These helpers keep service startup stable when older/newer modules diverge.
def _compat_stub(name: str) -> None:
    logger.warning("db compat stub called: %s", name)


def ensure_group_extra_subjects_schema() -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        _ensure_table_columns(
            cur,
            "groups",
            [
                ("course_id", "INTEGER"),
                ("course_title", "TEXT"),
                ("monthly_fee_text", "TEXT"),
                ("telegram_group_url", "TEXT"),
                ("pricing_type", "TEXT DEFAULT 'group'"),
                ("lang", "TEXT DEFAULT 'uz'"),
            ],
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS group_extra_subjects (
                    id BIGSERIAL PRIMARY KEY,
                    group_id BIGINT NOT NULL,
                    subject TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, subject)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS group_extra_subjects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, subject)
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_group_extra_subjects_group_id ON group_extra_subjects(group_id)")
        except Exception:
            pass
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("ensure_group_extra_subjects_schema failed")
        return False
    finally:
        conn.close()


def update_group_course_details(
    group_id: int,
    course_id: int | None = None,
    course_title: str | None = None,
    monthly_fee_text: str | None = None,
    telegram_group_url: str | None = None,
    pricing_type: str | None = None,
) -> bool:
    ensure_group_extra_subjects_schema()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE groups
                SET course_id=?,
                    course_title=?,
                    monthly_fee_text=?,
                    telegram_group_url=COALESCE(?, telegram_group_url),
                    pricing_type=COALESCE(?, pricing_type)
                WHERE id=?
                """,
                (
                    int(course_id) if course_id is not None and int(course_id) > 0 else None,
                    str(course_title or "").strip() or None,
                    str(monthly_fee_text or "").strip() or None,
                    str(telegram_group_url or "").strip() or None if telegram_group_url is not None else None,
                    str(pricing_type or "").strip() or None if pricing_type is not None else None,
                    int(group_id),
                ),
            )
            conn.commit()
            return bool(cur.rowcount > 0)
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("update_group_course_details failed group_id=%s", group_id)
            return False
        finally:
            conn.close()


def update_group_extra_subjects(group_id: int, subjects: list[str] | None = None) -> bool:
    ensure_group_extra_subjects_schema()
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in (subjects or []):
        value = str(item or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)

    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM groups WHERE id=? LIMIT 1", (int(group_id),))
            if not cur.fetchone():
                conn.commit()
                return False
            cur.execute("DELETE FROM group_extra_subjects WHERE group_id=?", (int(group_id),))
            for idx, subject in enumerate(cleaned):
                if _is_postgres_enabled():
                    cur.execute(
                        """
                        INSERT INTO group_extra_subjects(group_id, subject, sort_order)
                        VALUES (?, ?, ?)
                        ON CONFLICT(group_id, subject)
                        DO UPDATE SET sort_order=excluded.sort_order
                        """,
                        (int(group_id), subject, idx),
                    )
                else:
                    cur.execute(
                        """
                        INSERT OR REPLACE INTO group_extra_subjects(group_id, subject, sort_order)
                        VALUES (?, ?, ?)
                        """,
                        (int(group_id), subject, idx),
                    )
            conn.commit()
            return True
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("update_group_extra_subjects failed group_id=%s", group_id)
            return False
        finally:
            conn.close()


def get_group_extra_subjects(group_id: int) -> list[str]:
    ensure_group_extra_subjects_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT subject
            FROM group_extra_subjects
            WHERE group_id=?
            ORDER BY sort_order ASC, id ASC
            """,
            (int(group_id),),
        )
        rows = cur.fetchall() or []
        out: list[str] = []
        for row in rows:
            value = str((row.get("subject") if isinstance(row, dict) else row[0]) or "").strip()
            if value:
                out.append(value)
        return out
    except Exception:
        logger.exception("get_group_extra_subjects failed group_id=%s", group_id)
        return []
    finally:
        conn.close()


def set_standard_admin_account_credentials(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
    """
    Ensure configured web admin credentials exist in users table.
    Reads the following env pairs (in order):
      - ADMIN_LOGIN_ID / ADMIN_PASSWORD
      - ADMIN_LOGIN / ADMIN_PASSWORD
      - MAIN_ADMIN_WEB_LOGIN_1 / MAIN_ADMIN_WEB_PASSWORD_1
      - MAIN_ADMIN_WEB_LOGIN_2 / MAIN_ADMIN_WEB_PASSWORD_2
      - LIMITED_ADMIN_WEB_LOGIN_1 / LIMITED_ADMIN_WEB_PASSWORD_1
      - LIMITED_ADMIN_WEB_LOGIN_2 / LIMITED_ADMIN_WEB_PASSWORD_2
    Returns created/updated rows metadata.
    """
    pairs = [
        ("ADMIN_LOGIN_ID", "ADMIN_PASSWORD", "main_admin_1"),
        ("ADMIN_LOGIN", "ADMIN_PASSWORD", "main_admin_1"),
        ("MAIN_ADMIN_WEB_LOGIN_1", "MAIN_ADMIN_WEB_PASSWORD_1", "main_admin_1"),
        ("MAIN_ADMIN_WEB_LOGIN_2", "MAIN_ADMIN_WEB_PASSWORD_2", "main_admin_2"),
        ("LIMITED_ADMIN_WEB_LOGIN_1", "LIMITED_ADMIN_WEB_PASSWORD_1", "limited_admin_1"),
        ("LIMITED_ADMIN_WEB_LOGIN_2", "LIMITED_ADMIN_WEB_PASSWORD_2", "limited_admin_2"),
    ]
    credentials: list[tuple[str, str, str]] = []
    seen_login_ids: set[str] = set()
    for login_key, pass_key, label in pairs:
        login_id = str(os.getenv(login_key) or "").strip().upper()
        password = str(os.getenv(pass_key) or "").strip()
        if not login_id or not password:
            continue
        if login_id in seen_login_ids:
            continue
        seen_login_ids.add(login_id)
        credentials.append((login_id, password, label))

    if not credentials:
        raise RuntimeError("No admin web credentials configured in environment")

    conn = get_conn()
    cur = conn.cursor()
    items: list[dict[str, Any]] = []
    try:
        try:
            cur.execute("SET lock_timeout = '3000ms'")
            cur.execute("SET statement_timeout = '15000ms'")
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        for login_id, password, label in credentials:
            cur.execute("SELECT id FROM users WHERE UPPER(login_id)=? LIMIT 1", (login_id,))
            row = cur.fetchone()
            if row:
                user_id = int(row["id"]) if isinstance(row, dict) else int(row[0])
                cur.execute(
                    """
                    UPDATE users
                    SET password=?,
                        login_type=4,
                        blocked=0,
                        access_enabled=1,
                        password_used=0,
                        first_name=COALESCE(NULLIF(first_name, ''), ?),
                        last_name=COALESCE(NULLIF(last_name, ''), ?),
                        subject=COALESCE(NULLIF(subject, ''), 'English')
                    WHERE id=?
                    """,
                    (
                        hash_password(password),
                        "Main" if label.startswith("main_") else "Limited",
                        "Admin",
                        user_id,
                    ),
                )
                items.append({"id": user_id, "login_id": login_id, "updated": True, "created": False, "label": label})
            else:
                cur.execute(
                    """
                    INSERT INTO users
                    (login_id, password, first_name, last_name, phone, subject, login_type, blocked, access_enabled, password_used)
                    VALUES (?, ?, ?, ?, ?, ?, 4, 0, 1, 0)
                    RETURNING id
                    """,
                    (
                        login_id,
                        hash_password(password),
                        "Main" if label.startswith("main_") else "Limited",
                        "Admin",
                        "",
                        "English",
                    ),
                )
                created_row = cur.fetchone()
                created_id = int(created_row["id"]) if isinstance(created_row, dict) else int(created_row[0])
                items.append({"id": created_id, "login_id": login_id, "updated": False, "created": True, "label": label})
        conn.commit()
        return items
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _load_runtime_dpoint_rules_from_db() -> dict[str, float]:
    defaults = {
        "correct_answer_reward": 2.0,
        "wrong_answer_penalty": 3.0,
        "skipped_answer_penalty": 1.5,
        "daily_test_reward": 2.0,
        "daily_test_penalty": 3.0,
        "vocabulary_reward": 1.0,
        "vocabulary_penalty": 0.5,
        "group_arena_winner_reward": 10.0,
    }
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT value_json FROM web_runtime_settings WHERE key='dpoint_rules' LIMIT 1")
        row = cur.fetchone() or {}
        raw = str(row.get("value_json") or "").strip()
        if not raw:
            return defaults
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return defaults
        out = dict(defaults)
        for key, val in parsed.items():
            try:
                out[str(key)] = float(val)
            except Exception:
                continue
        return out
    except Exception:
        return defaults
    finally:
        conn.close()


def get_economy_rule_settings(mode: str | None = None) -> dict:
    """
    Runtime scoring rules used across web/bot quiz flows.
    Values are expressed in D'points (authoritative wallet unit).
    """
    runtime = _load_runtime_dpoint_rules_from_db()
    normalized = str(mode or "").strip().lower().replace("-", "_")
    generic_correct = float(runtime.get("correct_answer_reward") if runtime.get("correct_answer_reward") is not None else 2.0)
    generic_wrong = -abs(float(runtime.get("wrong_answer_penalty") if runtime.get("wrong_answer_penalty") is not None else 3.0))
    generic_skipped = -abs(float(runtime.get("skipped_answer_penalty") if runtime.get("skipped_answer_penalty") is not None else 1.5))

    daily_reward_val = runtime.get("daily_test_reward")
    if daily_reward_val is not None and float(daily_reward_val) != 2.0:
        daily_correct = float(daily_reward_val)
    else:
        daily_correct = generic_correct

    daily_pen_val = runtime.get("daily_test_penalty")
    if daily_pen_val is not None and float(daily_pen_val) != 3.0:
        daily_penalty = abs(float(daily_pen_val))
    else:
        daily_penalty = abs(generic_wrong)

    vocab_reward_val = runtime.get("vocabulary_reward")
    if vocab_reward_val is not None and float(vocab_reward_val) != 1.0:
        vocab_correct = float(vocab_reward_val)
    else:
        vocab_correct = generic_correct

    vocab_pen_val = runtime.get("vocabulary_penalty")
    if vocab_pen_val is not None and float(vocab_pen_val) != 0.5:
        vocab_penalty = abs(float(vocab_pen_val))
    else:
        vocab_penalty = abs(generic_wrong)

    if normalized in {"vocabulary", "vocab"}:
        return {
            "mode": "vocabulary",
            "correct": vocab_correct,
            "skipped": -vocab_penalty,
            "wrong": -vocab_penalty,
        }
    if normalized in {"daily", "daily_test", "grammar"}:
        return {
            "mode": "daily_grammar",
            "correct": daily_correct,
            "skipped": generic_skipped,
            "wrong": -daily_penalty,
        }
    return {
        "mode": "default",
        "correct": generic_correct,
        "skipped": generic_skipped,
        "wrong": generic_wrong,
    }


def get_dcoin_rule_settings(mode: str | None = None) -> dict:
    # Backward-compatible alias for legacy callers.
    return get_economy_rule_settings(mode=mode)


def calculate_economy_breakdown(*args: Any, **kwargs: Any) -> dict:
    correct_count = int(kwargs.get("correct_count", args[0] if len(args) > 0 else 0) or 0)
    skipped_count = int(kwargs.get("skipped_count", args[1] if len(args) > 1 else 0) or 0)
    wrong_count = int(kwargs.get("wrong_count", args[2] if len(args) > 2 else 0) or 0)
    subject_count = int(kwargs.get("subject_count", args[3] if len(args) > 3 else 1) or 1)
    mode = kwargs.get("mode") or kwargs.get("test_type") or kwargs.get("quiz_type")
    if subject_count <= 0:
        subject_count = 1
    rules = get_economy_rule_settings(str(mode or ""))
    correct_value = float(rules.get("correct", 2.0))
    skipped_value = float(rules.get("skipped", -1.5))
    wrong_value = float(rules.get("wrong", -3.0))
    correct_points = float(correct_count) * correct_value
    skipped_points = float(skipped_count) * skipped_value
    wrong_points = float(wrong_count) * wrong_value
    total_points = correct_points + skipped_points + wrong_points
    final_dcoins = total_points
    return {
        "correct_count": correct_count,
        "skipped_count": skipped_count,
        "wrong_count": wrong_count,
        "correct_points": float(correct_points),
        "skipped_points": float(skipped_points),
        "wrong_points": float(wrong_points),
        "total_points": float(total_points),
        "subject_count": int(subject_count),
        "final_dcoins": float(final_dcoins),
        "correct_value": float(correct_value),
        "skipped_value": float(skipped_value),
        "wrong_value": float(wrong_value),
    }


def calculate_dcoin_breakdown(*args: Any, **kwargs: Any) -> dict:
    # Backward-compatible alias for legacy callers.
    return calculate_economy_breakdown(*args, **kwargs)


def award_quiz_dpoints(*args: Any, **kwargs: Any) -> dict:
    user_id = int(kwargs.get("user_id", args[0] if len(args) > 0 else 0) or 0)
    subject = kwargs.get("subject", args[1] if len(args) > 1 else None)
    correct_count = int(kwargs.get("correct_count", args[2] if len(args) > 2 else 0) or 0)
    wrong_count = int(kwargs.get("wrong_count", args[3] if len(args) > 3 else 0) or 0)
    skipped_count = int(kwargs.get("skipped_count", args[4] if len(args) > 4 else 0) or 0)
    change_type = kwargs.get("change_type", args[5] if len(args) > 5 else "quiz_result")
    mode = kwargs.get("mode") or kwargs.get("test_type") or kwargs.get("quiz_type")
    if user_id <= 0:
        return {
            "correct_count": correct_count,
            "skipped_count": skipped_count,
            "wrong_count": wrong_count,
            "correct_points": 0.0,
            "skipped_points": 0.0,
            "wrong_points": 0.0,
            "total_points": 0.0,
            "subject_count": 1,
            "final_dcoins": 0.0,
            "correct_value": 2.0,
            "skipped_value": 0.5,
            "wrong_value": -1.0,
            "applied": False,
        }
    subject_count = max(1, int(get_user_subject_count(user_id)))
    breakdown = calculate_economy_breakdown(
        correct_count=correct_count,
        skipped_count=skipped_count,
        wrong_count=wrong_count,
        subject_count=subject_count,
        mode=mode,
    )
    delta_dpoints = float(breakdown.get("total_points") or 0.0)
    if abs(delta_dpoints) > 0:
        add_dpoints(user_id, delta_dpoints, subject=subject, change_type=str(change_type or "quiz_result"))
    breakdown["applied"] = True
    return breakdown


def award_quiz_dcoins(*args: Any, **kwargs: Any) -> dict:
    # Backward-compatible alias for legacy callers.
    return award_quiz_dpoints(*args, **kwargs)


def get_placement_results_for_user(user_id: int, limit: int = 20) -> list[dict]:
    uid = int(user_id or 0)
    if uid <= 0:
        return []
    lim = max(1, min(200, int(limit or 20)))
    conn = get_conn()
    cur = conn.cursor()
    try:
        has_max_score = False
        try:
            if _is_postgres_enabled():
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name='test_results' AND column_name='max_score'
                    LIMIT 1
                    """
                )
                has_max_score = cur.fetchone() is not None
            else:
                cur.execute("PRAGMA table_info(test_results)")
                cols = {str(r["name"]) for r in (cur.fetchall() or [])}
                has_max_score = "max_score" in cols
        except Exception:
            has_max_score = False

        if has_max_score:
            cur.execute(
                """
                SELECT *
                FROM test_results
                WHERE user_id = ? AND max_score = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (uid, 500, lim),
            )
        else:
            # Legacy DB fallback: placement rows may not have max_score yet.
            cur.execute(
                """
                SELECT *
                FROM test_results
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (uid, lim),
            )
        return [dict(r) for r in (cur.fetchall() or [])]
    except Exception:
        logger.exception("get_placement_results_for_user failed user_id=%s", uid)
        return []
    finally:
        conn.close()


def create_test_proctoring_session(*args: Any, **kwargs: Any) -> int | None:
    _compat_stub("create_test_proctoring_session")
    return None


def get_test_proctoring_session(*args: Any, **kwargs: Any) -> dict | None:
    _compat_stub("get_test_proctoring_session")
    return None


def get_active_test_proctoring_session(*args: Any, **kwargs: Any) -> dict | None:
    _compat_stub("get_active_test_proctoring_session")
    return None


def update_test_proctoring_session_status(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("update_test_proctoring_session_status")
    return False


def increment_test_proctoring_counter(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("increment_test_proctoring_counter")
    return False


def mark_test_proctoring_preview_visible(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("mark_test_proctoring_preview_visible")
    return False


def log_test_proctoring_event(*args: Any, **kwargs: Any) -> int | None:
    _compat_stub("log_test_proctoring_event")
    return None


def add_test_proctoring_snapshot(*args: Any, **kwargs: Any) -> int | None:
    _compat_stub("add_test_proctoring_snapshot")
    return None


def get_proctoring_session_timeline(*args: Any, **kwargs: Any) -> list[dict]:
    _compat_stub("get_proctoring_session_timeline")
    return []


def list_proctoring_sessions_for_admin(*args: Any, **kwargs: Any) -> list[dict]:
    _compat_stub("list_proctoring_sessions_for_admin")
    return []


def create_proctoring_grace_period(*args: Any, **kwargs: Any) -> int | None:
    _compat_stub("create_proctoring_grace_period")
    return None


def resolve_proctoring_grace_period(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("resolve_proctoring_grace_period")
    return False


def log_proctoring_screenshot_attempt(*args: Any, **kwargs: Any) -> int | None:
    _compat_stub("log_proctoring_screenshot_attempt")
    return None


def apply_proctoring_penalty(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("apply_proctoring_penalty")
    return False


def create_or_update_proctoring_device_session(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("create_or_update_proctoring_device_session")
    return False


def get_user_proctoring_status(*args: Any, **kwargs: Any) -> dict:
    _compat_stub("get_user_proctoring_status")
    return {"face_id_enrolled": False, "proctoring_required": True}


def create_face_enrollment_session(*args: Any, **kwargs: Any) -> int | None:
    _compat_stub("create_face_enrollment_session")
    return None


def get_face_enrollment_session(*args: Any, **kwargs: Any) -> dict | None:
    _compat_stub("get_face_enrollment_session")
    return None


def add_face_sample(*args: Any, **kwargs: Any) -> int | None:
    _compat_stub("add_face_sample")
    return None


def list_face_samples_for_enrollment(*args: Any, **kwargs: Any) -> list[dict]:
    _compat_stub("list_face_samples_for_enrollment")
    return []


def complete_face_enrollment(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("complete_face_enrollment")
    return False


def finalize_face_enrollment_session(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("finalize_face_enrollment_session")
    return False


def append_face_profile_audit(*args: Any, **kwargs: Any) -> bool:
    _compat_stub("append_face_profile_audit")
    return False


def get_active_face_profile(*args: Any, **kwargs: Any) -> dict | None:
    _compat_stub("get_active_face_profile")
    return None

# ====================== PROCTORING RUNTIME IMPLEMENTATION ======================

def _row_to_dict(row: Any) -> dict:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    try:
        return dict(row)
    except Exception:
        return {}


def _ensure_proctoring_schema_runtime() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        user_alters = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image_url TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_id_required INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_id_enrolled INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_id_status TEXT DEFAULT 'not_started'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_enrollment_required INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_profile_status TEXT DEFAULT 'pending'",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_profile_version INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_enrolled_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_last_verified_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_verification_method TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_match_threshold DOUBLE PRECISION DEFAULT 0.82",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_id_expires_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS proctoring_required INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS proctoring_block_reason TEXT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS proctoring_hold_until TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS proctoring_blocked_until TIMESTAMP",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS proctoring_risk_score DOUBLE PRECISION DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_total_violations INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS face_last_violation_at TIMESTAMP",
        ]
        for sql in user_alters:
            try:
                cur.execute(sql)
            except Exception:
                pass

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_face_profiles (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                status TEXT DEFAULT 'active',
                reference_image_url TEXT,
                primary_embedding TEXT,
                capture_device_info TEXT,
                verification_method TEXT,
                embedding_model TEXT,
                liveness_model TEXT,
                face_match_threshold DOUBLE PRECISION DEFAULT 0.82,
                face_id_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        profile_alters = [
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS reference_image_url TEXT",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS primary_embedding TEXT",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS capture_device_info TEXT",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS verification_method TEXT",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS embedding_model TEXT",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS liveness_model TEXT",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS face_match_threshold DOUBLE PRECISION DEFAULT 0.82",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS face_id_expires_at TIMESTAMP",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE user_face_profiles ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        ]
        for sql in profile_alters:
            try:
                cur.execute(sql)
            except Exception:
                pass
        cur.execute("CREATE INDEX IF NOT EXISTS idx_user_face_profiles_user_id ON user_face_profiles(user_id)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_face_profile_audit (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                profile_version INTEGER DEFAULT 0,
                action_type TEXT,
                result_status TEXT,
                details_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS face_enrollment_sessions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'started',
                attempt_number INTEGER DEFAULT 1,
                photo_url TEXT,
                video_url TEXT,
                liveness_passed INTEGER DEFAULT 0,
                liveness_score DOUBLE PRECISION,
                face_quality_score DOUBLE PRECISION,
                embedding_saved INTEGER DEFAULT 0,
                device_info TEXT,
                error_message TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                expires_at TIMESTAMP,
                profile_valid_until TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS face_samples (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                enrollment_session_id BIGINT NOT NULL,
                image_path TEXT,
                quality_score DOUBLE PRECISION DEFAULT 0,
                sample_label TEXT,
                embedding_vector TEXT,
                embedding_hash TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_face_samples_enroll ON face_samples(enrollment_session_id)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS test_proctoring_sessions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                test_type TEXT NOT NULL,
                test_attempt_ref TEXT,
                test_route TEXT,
                status TEXT DEFAULT 'active',
                failure_reason TEXT,
                penalty_applied INTEGER DEFAULT 0,
                selfie_preview_required INTEGER DEFAULT 1,
                selfie_preview_visible INTEGER DEFAULT 1,
                face_last_seen INTEGER DEFAULT 1,
                last_match_score DOUBLE PRECISION,
                face_missing_grace_until TIMESTAMP,
                app_blur_grace_until TIMESTAMP,
                face_missing_count INTEGER DEFAULT 0,
                face_different_person_count INTEGER DEFAULT 0,
                app_hidden_count INTEGER DEFAULT 0,
                screenshot_attempt_count INTEGER DEFAULT 0,
                final_verdict TEXT DEFAULT 'pending',
                verdict_reason TEXT,
                terminated_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_test_proctoring_sessions_user ON test_proctoring_sessions(user_id)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS test_proctoring_events (
                id BIGSERIAL PRIMARY KEY,
                proctoring_session_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                event_type TEXT NOT NULL,
                event_status TEXT,
                reason_code TEXT,
                score DOUBLE PRECISION,
                grace_started_at TIMESTAMP,
                grace_expires_at TIMESTAMP,
                resolved_at TIMESTAMP,
                client_ts TEXT,
                server_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details_json TEXT
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_test_proctoring_events_session ON test_proctoring_events(proctoring_session_id)")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS test_proctoring_snapshots (
                id BIGSERIAL PRIMARY KEY,
                proctoring_session_id BIGINT NOT NULL,
                face_count INTEGER DEFAULT 0,
                is_live INTEGER DEFAULT 0,
                match_score DOUBLE PRECISION,
                preview_visible INTEGER DEFAULT 1,
                app_visibility TEXT,
                snapshot_image_url TEXT,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS proctoring_grace_periods (
                id BIGSERIAL PRIMARY KEY,
                proctoring_session_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                grace_type TEXT NOT NULL,
                grace_timeout_sec INTEGER DEFAULT 5,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                resolved_at TIMESTAMP,
                resolution TEXT DEFAULT 'pending',
                duration_ms INTEGER,
                event_id BIGINT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS proctoring_screenshots_log (
                id BIGSERIAL PRIMARY KEY,
                proctoring_session_id BIGINT NOT NULL,
                user_id BIGINT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                detection_method TEXT,
                key_combination TEXT,
                blocked INTEGER DEFAULT 1,
                details_json TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS proctoring_penalties (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                proctoring_session_id BIGINT,
                test_type TEXT,
                penalty_rule TEXT,
                penalty_percent DOUBLE PRECISION,
                penalty_amount DOUBLE PRECISION,
                details_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS proctoring_device_sessions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                device_id TEXT,
                platform TEXT,
                browser TEXT,
                telegram_init_hash TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        device_alters = [
            "ALTER TABLE proctoring_device_sessions ADD COLUMN IF NOT EXISTS device_id TEXT",
            "ALTER TABLE proctoring_device_sessions ADD COLUMN IF NOT EXISTS platform TEXT",
            "ALTER TABLE proctoring_device_sessions ADD COLUMN IF NOT EXISTS browser TEXT",
            "ALTER TABLE proctoring_device_sessions ADD COLUMN IF NOT EXISTS telegram_init_hash TEXT",
            "ALTER TABLE proctoring_device_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "ALTER TABLE proctoring_device_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        ]
        for sql in device_alters:
            try:
                cur.execute(sql)
            except Exception:
                pass
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_proctoring_device_user_device ON proctoring_device_sessions(user_id, device_id)")

        session_alters = [
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS final_verdict TEXT DEFAULT 'pending'",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS verdict_reason TEXT",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS terminated_by TEXT",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS face_missing_count INTEGER DEFAULT 0",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS face_different_person_count INTEGER DEFAULT 0",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS app_hidden_count INTEGER DEFAULT 0",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS screenshot_attempt_count INTEGER DEFAULT 0",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS warning_count INTEGER DEFAULT 0",
            "ALTER TABLE test_proctoring_sessions ADD COLUMN IF NOT EXISTS warning_grace_until TIMESTAMP",
        ]
        for sql in session_alters:
            try:
                cur.execute(sql)
            except Exception:
                pass

        conn.commit()
    finally:
        conn.close()


def get_user_proctoring_status(user_id: int) -> dict:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                face_id_required, face_id_enrolled, face_id_status,
                face_enrollment_required, face_profile_status, face_profile_version,
                face_enrolled_at, face_last_verified_at, face_verification_method,
                face_match_threshold, proctoring_required, proctoring_block_reason,
                proctoring_hold_until, proctoring_blocked_until, proctoring_risk_score,
                face_id_expires_at, face_total_violations, face_last_violation_at
            FROM users
            WHERE id=?
            """,
            (int(user_id),),
        )
        user_row = _row_to_dict(cur.fetchone())
        if not user_row:
            return {}
        profile = {}
        try:
            cur.execute(
                """
                SELECT id, status, reference_image_url, primary_embedding, face_match_threshold,
                       face_id_expires_at, updated_at, created_at
                FROM user_face_profiles
                WHERE user_id=?
                ORDER BY (CASE WHEN status='active' THEN 0 ELSE 1 END), updated_at DESC, id DESC
                LIMIT 1
                """,
                (int(user_id),),
            )
            profile = _row_to_dict(cur.fetchone())
        except Exception:
            # Legacy schemas may not have all profile columns yet.
            cur.execute(
                """
                SELECT id, status, reference_image_url, primary_embedding
                FROM user_face_profiles
                WHERE user_id=?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(user_id),),
            )
            profile = _row_to_dict(cur.fetchone())
        out = dict(user_row)
        out["active_profile"] = profile or None
        return out
    finally:
        conn.close()


def create_or_update_proctoring_device_session(
    user_id: int,
    device_id: str | None = None,
    platform: str | None = None,
    browser: str | None = None,
    telegram_init_hash: str | None = None,
) -> int | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        device = (device_id or "").strip() or "unknown"
        if _is_postgres_enabled():
            cur.execute(
                """
                INSERT INTO proctoring_device_sessions(user_id, device_id, platform, browser, telegram_init_hash, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id, device_id)
                DO UPDATE SET platform=EXCLUDED.platform,
                              browser=EXCLUDED.browser,
                              telegram_init_hash=EXCLUDED.telegram_init_hash,
                              updated_at=CURRENT_TIMESTAMP
                RETURNING id
                """,
                (int(user_id), device, platform, browser, telegram_init_hash),
            )
            row = cur.fetchone()
            conn.commit()
            return int((row or {}).get("id") or 0) or None
        cur.execute(
            "SELECT id FROM proctoring_device_sessions WHERE user_id=? AND device_id=? LIMIT 1",
            (int(user_id), device),
        )
        row = _row_to_dict(cur.fetchone())
        if row:
            cur.execute(
                """
                UPDATE proctoring_device_sessions
                SET platform=?, browser=?, telegram_init_hash=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (platform, browser, telegram_init_hash, int(row.get("id") or 0)),
            )
            conn.commit()
            return int(row.get("id") or 0) or None
        cur.execute(
            """
            INSERT INTO proctoring_device_sessions(user_id, device_id, platform, browser, telegram_init_hash)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(user_id), device, platform, browser, telegram_init_hash),
        )
        cur.execute("SELECT id FROM proctoring_device_sessions WHERE user_id=? AND device_id=? ORDER BY id DESC LIMIT 1", (int(user_id), device))
        inserted = _row_to_dict(cur.fetchone())
        conn.commit()
        return int(inserted.get("id") or 0) or None
    finally:
        conn.close()


def create_face_enrollment_session(
    user_id: int,
    attempt_number: int = 1,
    device_info: str | None = None,
    expires_at: str | None = None,
) -> dict | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO face_enrollment_sessions(user_id, status, attempt_number, device_info, expires_at)
            VALUES (?, 'started', ?, ?, ?)
            RETURNING *
            """,
            (int(user_id), int(attempt_number or 1), device_info, expires_at),
        )
        row = _row_to_dict(cur.fetchone())
        conn.commit()
        return row
    finally:
        conn.close()


def get_face_enrollment_session(enrollment_session_id: int, user_id: int) -> dict | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM face_enrollment_sessions WHERE id=? AND user_id=? LIMIT 1",
            (int(enrollment_session_id), int(user_id)),
        )
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def add_face_sample(
    user_id: int,
    enrollment_session_id: int,
    image_path: str | None,
    quality_score: float | None = None,
    sample_label: str | None = None,
    embedding_vector: str | None = None,
    embedding_hash: str | None = None,
    metadata_json: str | None = None,
) -> dict | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO face_samples(
                user_id, enrollment_session_id, image_path, quality_score,
                sample_label, embedding_vector, embedding_hash, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                int(user_id),
                int(enrollment_session_id),
                image_path,
                float(quality_score or 0.0),
                sample_label,
                embedding_vector,
                embedding_hash,
                metadata_json,
            ),
        )
        row = _row_to_dict(cur.fetchone())
        cur.execute(
            "UPDATE face_enrollment_sessions SET status='photo_captured' WHERE id=? AND user_id=?",
            (int(enrollment_session_id), int(user_id)),
        )
        conn.commit()
        return row
    finally:
        conn.close()


def list_face_samples_for_enrollment(enrollment_session_id: int, user_id: int) -> list[dict]:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT *
            FROM face_samples
            WHERE enrollment_session_id=? AND user_id=?
            ORDER BY id ASC
            """,
            (int(enrollment_session_id), int(user_id)),
        )
        rows = cur.fetchall() or []
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def append_face_profile_audit(
    user_id: int,
    profile_version: int | None = None,
    action_type: str | None = None,
    result_status: str | None = None,
    details_json: str | None = None,
) -> bool:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO user_face_profile_audit(user_id, profile_version, action_type, result_status, details_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(user_id), int(profile_version or 0), action_type, result_status, details_json),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_active_face_profile(user_id: int) -> dict | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT * FROM user_face_profiles
            WHERE user_id=? AND status='active'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (int(user_id),),
        )
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def complete_face_enrollment(
    user_id: int,
    reference_image_url: str | None = None,
    capture_device_info: str | None = None,
    verification_method: str | None = None,
    embedding_model: str | None = None,
    liveness_model: str | None = None,
    primary_embedding: str | None = None,
    face_match_threshold: float | None = None,
    face_id_expires_at: str | None = None,
) -> dict:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE user_face_profiles SET status='expired', updated_at=CURRENT_TIMESTAMP WHERE user_id=? AND status='active'",
            (int(user_id),),
        )
        cur.execute(
            """
            INSERT INTO user_face_profiles(
                user_id, status, reference_image_url, primary_embedding,
                capture_device_info, verification_method, embedding_model,
                liveness_model, face_match_threshold, face_id_expires_at
            )
            VALUES (?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                int(user_id),
                reference_image_url,
                primary_embedding,
                capture_device_info,
                verification_method,
                embedding_model,
                liveness_model,
                float(face_match_threshold or 0.82),
                face_id_expires_at,
            ),
        )
        profile_row = _row_to_dict(cur.fetchone())

        cur.execute(
            """
            UPDATE users
            SET face_id_required=1,
                face_id_enrolled=1,
                face_id_status='active',
                face_enrollment_required=0,
                face_profile_status='active',
                face_profile_version=COALESCE(face_profile_version, 0) + 1,
                profile_image_url=COALESCE(NULLIF(?, ''), profile_image_url),
                face_enrolled_at=CURRENT_TIMESTAMP,
                face_last_verified_at=CURRENT_TIMESTAMP,
                face_verification_method=?,
                face_match_threshold=?,
                face_id_expires_at=?,
                proctoring_required=1,
                proctoring_block_reason=NULL,
                proctoring_hold_until=NULL,
                proctoring_blocked_until=NULL
            WHERE id=?
            """,
            (
                str(reference_image_url or "").strip(),
                verification_method,
                float(face_match_threshold or 0.82),
                face_id_expires_at,
                int(user_id),
            ),
        )
        conn.commit()

        append_face_profile_audit(
            int(user_id),
            action_type="enroll_completed",
            result_status="completed",
            details_json=_json_text_local({
                "profile_id": int(profile_row.get("id") or 0),
                "face_id_expires_at": face_id_expires_at,
                "embedding_model": embedding_model,
                "liveness_model": liveness_model,
            }),
        )
        return {"profile_id": int(profile_row.get("id") or 0), "face_id_expires_at": face_id_expires_at}
    finally:
        conn.close()


def finalize_face_enrollment_session(
    enrollment_session_id: int,
    user_id: int,
    status: str = "completed",
    photo_url: str | None = None,
    liveness_passed: bool | None = None,
    liveness_score: float | None = None,
    face_quality_score: float | None = None,
    embedding_saved: bool | None = None,
    profile_valid_until: str | None = None,
    error_message: str | None = None,
) -> bool:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE face_enrollment_sessions
            SET status=?,
                photo_url=COALESCE(?, photo_url),
                liveness_passed=COALESCE(?, liveness_passed),
                liveness_score=COALESCE(?, liveness_score),
                face_quality_score=COALESCE(?, face_quality_score),
                embedding_saved=COALESCE(?, embedding_saved),
                profile_valid_until=COALESCE(?, profile_valid_until),
                error_message=COALESCE(?, error_message),
                completed_at=CASE WHEN ? IN ('completed','failed','expired') THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE id=? AND user_id=?
            """,
            (
                status,
                photo_url,
                (1 if liveness_passed else 0) if liveness_passed is not None else None,
                liveness_score,
                face_quality_score,
                (1 if embedding_saved else 0) if embedding_saved is not None else None,
                profile_valid_until,
                error_message,
                status,
                int(enrollment_session_id),
                int(user_id),
            ),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def create_test_proctoring_session(
    user_id: int,
    test_type: str,
    test_attempt_ref: str | None = None,
    test_route: str | None = None,
    selfie_preview_required: bool = True,
) -> dict | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO test_proctoring_sessions(
                user_id, test_type, test_attempt_ref, test_route, status,
                selfie_preview_required, selfie_preview_visible, face_last_seen
            )
            VALUES (?, ?, ?, ?, 'active', ?, 0, 0)
            RETURNING *
            """,
            (
                int(user_id),
                str(test_type or "").strip(),
                str(test_attempt_ref or "").strip() or None,
                test_route,
                1 if selfie_preview_required else 0,
            ),
        )
        row = _row_to_dict(cur.fetchone())
        conn.commit()
        return row or None
    finally:
        conn.close()


def get_active_test_proctoring_session(user_id: int, test_type: str, test_attempt_ref: str | None = None) -> dict | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if str(test_attempt_ref or "").strip():
            cur.execute(
                """
                SELECT * FROM test_proctoring_sessions
                WHERE user_id=? AND test_type=? AND test_attempt_ref=? AND status='active'
                ORDER BY id DESC LIMIT 1
                """,
                (int(user_id), str(test_type or "").strip(), str(test_attempt_ref).strip()),
            )
        else:
            cur.execute(
                """
                SELECT * FROM test_proctoring_sessions
                WHERE user_id=? AND test_type=? AND status='active'
                ORDER BY id DESC LIMIT 1
                """,
                (int(user_id), str(test_type or "").strip()),
            )
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def get_test_proctoring_session(session_id: int) -> dict | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM test_proctoring_sessions WHERE id=? LIMIT 1", (int(session_id),))
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def update_test_proctoring_session_status(session_id: int, **kwargs: Any) -> dict | None:
    _ensure_proctoring_schema_runtime()
    allowed = {
        "status": "status",
        "failure_reason": "failure_reason",
        "selfie_preview_visible": "selfie_preview_visible",
        "face_last_seen": "face_last_seen",
        "last_match_score": "last_match_score",
        "face_missing_grace_until": "face_missing_grace_until",
        "app_blur_grace_until": "app_blur_grace_until",
        "warning_grace_until": "warning_grace_until",
        "penalty_applied": "penalty_applied",
        "final_verdict": "final_verdict",
        "verdict_reason": "verdict_reason",
        "terminated_by": "terminated_by",
    }
    updates: list[str] = []
    params: list[Any] = []

    for key, col in allowed.items():
        if key not in kwargs:
            continue
        val = kwargs.get(key)
        if key in {"selfie_preview_visible", "face_last_seen", "penalty_applied"} and val is not None:
            val = 1 if bool(val) else 0
        updates.append(f"{col}=?")
        params.append(val)

    if kwargs.get("clear_face_missing_grace"):
        updates.append("face_missing_grace_until=NULL")
    if kwargs.get("clear_app_blur_grace"):
        updates.append("app_blur_grace_until=NULL")
    if kwargs.get("clear_warning_grace"):
        updates.append("warning_grace_until=NULL")

    has_explicit_status = "status" in kwargs and kwargs.get("status") is not None and str(kwargs.get("status") or "").strip() != ""

    if "camera_started" in kwargs and bool(kwargs.get("camera_started")) and not has_explicit_status:
        updates.append("status=COALESCE(status,'active')")

    status_val = str(kwargs.get("status") or "").strip().lower()
    if status_val in {"failed", "passed", "aborted"}:
        updates.append("completed_at=COALESCE(completed_at, CURRENT_TIMESTAMP)")

    if not updates:
        return get_test_proctoring_session(int(session_id))

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE test_proctoring_sessions SET {', '.join(updates)} WHERE id=?",
            (*params, int(session_id)),
        )
        conn.commit()
    finally:
        conn.close()
    return get_test_proctoring_session(int(session_id))


def increment_test_proctoring_counter(session_id: int, counter_name: str, amount: int = 1) -> bool:
    _ensure_proctoring_schema_runtime()
    allowed = {
        "face_missing_count",
        "face_different_person_count",
        "app_hidden_count",
        "screenshot_attempt_count",
        "warning_count",
    }
    if counter_name not in allowed:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE test_proctoring_sessions SET {counter_name}=COALESCE({counter_name}, 0) + ? WHERE id=?",
            (int(amount or 1), int(session_id)),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def mark_test_proctoring_preview_visible(session_id: int, visible: bool) -> bool:
    row = update_test_proctoring_session_status(int(session_id), selfie_preview_visible=bool(visible))
    return bool(row)


def log_test_proctoring_event(
    proctoring_session_id: int,
    user_id: int,
    event_type: str,
    event_status: str | None = None,
    reason_code: str | None = None,
    score: float | None = None,
    grace_started_at: str | None = None,
    grace_expires_at: str | None = None,
    resolved_at: str | None = None,
    client_ts: str | None = None,
    details_json: str | None = None,
) -> int | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO test_proctoring_events(
                proctoring_session_id, user_id, event_type, event_status,
                reason_code, score, grace_started_at, grace_expires_at,
                resolved_at, client_ts, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                int(proctoring_session_id),
                int(user_id),
                event_type,
                event_status,
                reason_code,
                score,
                grace_started_at,
                grace_expires_at,
                resolved_at,
                client_ts,
                details_json,
            ),
        )
        row = _row_to_dict(cur.fetchone())
        conn.commit()
        return int(row.get("id") or 0) or None
    finally:
        conn.close()


def add_test_proctoring_snapshot(
    proctoring_session_id: int,
    face_count: int = 0,
    is_live: bool = False,
    match_score: float | None = None,
    preview_visible: bool = True,
    app_visibility: str | None = None,
    snapshot_image_url: str | None = None,
    metadata_json: str | None = None,
) -> int | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO test_proctoring_snapshots(
                proctoring_session_id, face_count, is_live, match_score,
                preview_visible, app_visibility, snapshot_image_url, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                int(proctoring_session_id),
                int(face_count or 0),
                1 if is_live else 0,
                match_score,
                1 if preview_visible else 0,
                app_visibility,
                snapshot_image_url,
                metadata_json,
            ),
        )
        row = _row_to_dict(cur.fetchone())
        conn.commit()
        return int(row.get("id") or 0) or None
    finally:
        conn.close()


def create_proctoring_grace_period(
    proctoring_session_id: int,
    user_id: int,
    grace_type: str,
    timeout_sec: int = 5,
    event_id: int | None = None,
) -> int | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO proctoring_grace_periods(
                proctoring_session_id, user_id, grace_type, grace_timeout_sec,
                started_at, expires_at, event_id
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP + (? || ' seconds')::interval, ?)
            RETURNING id
            """,
            (int(proctoring_session_id), int(user_id), grace_type, int(timeout_sec or 5), int(timeout_sec or 5), event_id),
        )
        row = _row_to_dict(cur.fetchone())
        conn.commit()
        return int(row.get("id") or 0) or None
    except Exception:
        # SQLite-compatible fallback without interval cast
        try:
            cur.execute(
                """
                INSERT INTO proctoring_grace_periods(
                    proctoring_session_id, user_id, grace_type, grace_timeout_sec,
                    started_at, expires_at, event_id
                )
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, datetime('now', ?), ?)
                """,
                (int(proctoring_session_id), int(user_id), grace_type, int(timeout_sec or 5), f"+{int(timeout_sec or 5)} seconds", event_id),
            )
            conn.commit()
            cur.execute("SELECT id FROM proctoring_grace_periods ORDER BY id DESC LIMIT 1")
            row = _row_to_dict(cur.fetchone())
            return int(row.get("id") or 0) or None
        finally:
            conn.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def resolve_proctoring_grace_period(
    grace_period_id: int | None = None,
    proctoring_session_id: int | None = None,
    grace_type: str | None = None,
    resolution: str = "recovered",
) -> bool:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if grace_period_id:
            cur.execute(
                """
                UPDATE proctoring_grace_periods
                SET resolution=?, resolved_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (resolution, int(grace_period_id)),
            )
        else:
            if grace_type is None:
                cur.execute(
                    """
                    UPDATE proctoring_grace_periods
                    SET resolution=?, resolved_at=CURRENT_TIMESTAMP
                    WHERE id=(
                        SELECT id FROM proctoring_grace_periods
                        WHERE proctoring_session_id=?
                          AND resolution='pending'
                        ORDER BY id DESC LIMIT 1
                    )
                    """,
                    (resolution, int(proctoring_session_id or 0)),
                )
            else:
                cur.execute(
                    """
                    UPDATE proctoring_grace_periods
                    SET resolution=?, resolved_at=CURRENT_TIMESTAMP
                    WHERE id=(
                        SELECT id FROM proctoring_grace_periods
                        WHERE proctoring_session_id=?
                          AND grace_type=?
                          AND resolution='pending'
                        ORDER BY id DESC LIMIT 1
                    )
                    """,
                    (resolution, int(proctoring_session_id or 0), grace_type),
                )
        conn.commit()
        return (cur.rowcount or 0) > 0
    finally:
        conn.close()


def log_proctoring_screenshot_attempt(
    proctoring_session_id: int,
    user_id: int,
    detection_method: str | None = None,
    key_combination: str | None = None,
    blocked: bool = True,
    details_json: str | None = None,
) -> int | None:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO proctoring_screenshots_log(
                proctoring_session_id, user_id, detection_method, key_combination, blocked, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                int(proctoring_session_id),
                int(user_id),
                detection_method,
                key_combination,
                1 if blocked else 0,
                details_json,
            ),
        )
        row = _row_to_dict(cur.fetchone())
        conn.commit()
        return int(row.get("id") or 0) or None
    finally:
        conn.close()


def apply_proctoring_penalty(
    user_id: int,
    proctoring_session_id: int,
    test_type: str | None = None,
    penalty_rule: str | None = None,
    penalty_percent: float = 0.0,
    penalty_amount: float = 0.0,
    details_json: str | None = None,
) -> bool:
    _ensure_proctoring_schema_runtime()
    ensure_dpoints_schema()
    percent = max(0.0, float(penalty_percent or 0))
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE test_proctoring_sessions
            SET penalty_applied=1
            WHERE id=? AND COALESCE(penalty_applied, 0)=0
            """,
            (int(proctoring_session_id),),
        )
        if (cur.rowcount or 0) <= 0:
            conn.rollback()
            return False

        accountless = _is_accountless_user_tx(cur, int(user_id))
        balance_before = 0.0
        balance_after = 0.0
        computed_amount = float(penalty_amount or 0)

        if not accountless:
            if not _ensure_user_dpoints_ready(cur, context="apply_proctoring_penalty"):
                conn.rollback()
                return False
            balance_before = float(_ensure_user_dpoints_row(cur, int(user_id)))
            if computed_amount <= 0 and percent > 0:
                computed_amount = round(balance_before * percent / 100.0, 6)
            computed_amount = max(0.0, float(computed_amount))
            balance_after = balance_before
            if computed_amount > 0:
                now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                dpoints_delta = -computed_amount
                dcoin_delta = dpoints_delta
                floor_before = _get_user_dcoin_floor(cur, int(user_id))
                floor_after = max(0.0, float(floor_before) + float(dcoin_delta))
                cur.execute(
                    "UPDATE user_dpoints SET dpoints=dpoints+?, dcoin_floor=?, updated_at=? WHERE user_id=?",
                    (dpoints_delta, float(floor_after), now, int(user_id)),
                )
                cur.execute(
                    """
                    INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(user_id),
                        float(dcoin_delta),
                        float(dpoints_delta),
                        "GLOBAL",
                        now,
                        "proctoring_max_penalty" if str(penalty_rule or "") != "screenshot_attempt" else "screenshot_penalty",
                    ),
                )
                balance_after = float(balance_before + dpoints_delta)
        else:
            computed_amount = 0.0

        details_payload: dict[str, Any] = {}
        if details_json:
            try:
                parsed = json.loads(str(details_json))
                if isinstance(parsed, dict):
                    details_payload.update(parsed)
                else:
                    details_payload["extra"] = parsed
            except Exception:
                details_payload["raw"] = str(details_json)
        details_payload.update(
            {
                "balance_before": round(balance_before, 6),
                "balance_after": round(balance_after, 6),
                "computed_penalty_amount": round(computed_amount, 6),
                "penalty_unit": "dpoint",
            }
        )

        cur.execute(
            """
            INSERT INTO proctoring_penalties(
                user_id, proctoring_session_id, test_type, penalty_rule,
                penalty_percent, penalty_amount, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                int(proctoring_session_id),
                test_type,
                penalty_rule,
                percent,
                computed_amount,
                json.dumps(details_payload, ensure_ascii=False),
            ),
        )
        cur.execute(
            """
            UPDATE users
            SET face_total_violations=COALESCE(face_total_violations, 0) + 1,
                face_last_violation_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (int(user_id),),
        )
        cur.execute(
            """
            UPDATE test_proctoring_sessions
            SET penalty_applied=1
            WHERE id=?
            """,
            (int(proctoring_session_id),),
        )
        conn.commit()
        return True
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        conn.close()


def get_proctoring_session_timeline(session_id: int, limit: int = 200) -> list[dict]:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, event_type, event_status, reason_code, score, grace_started_at,
                   grace_expires_at, resolved_at, client_ts, server_ts, details_json
            FROM test_proctoring_events
            WHERE proctoring_session_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(session_id), int(limit)),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def list_proctoring_sessions_for_admin(limit: int = 100, offset: int = 0) -> list[dict]:
    _ensure_proctoring_schema_runtime()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT s.*, u.login_id, u.first_name, u.last_name
            FROM test_proctoring_sessions s
            LEFT JOIN users u ON u.id=s.user_id
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?
            """,
            (int(limit), int(offset)),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def _json_text_local(value: Any) -> str | None:
    try:
        import json as _json

        return _json.dumps(value, ensure_ascii=False)
    except Exception:
        return None


def _ensure_table_columns(cur, table_name: str, columns: list[tuple[str, str]]) -> None:
    for col_name, col_sql in columns:
        try:
            if _is_postgres_enabled():
                cur.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name=? AND column_name=?
                    """,
                    (table_name, col_name),
                )
                has_col = bool(cur.fetchone())
            else:
                cur.execute(f"PRAGMA table_info({table_name})")
                has_col = any(
                    str((dict(r) if isinstance(r, dict) else {"name": r[1]}).get("name")) == col_name
                    for r in (cur.fetchall() or [])
                )
            if not has_col:
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_sql}")
        except Exception:
            # Legacy environments may not support all DDL variants.
            continue


def ensure_gifts_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_gifts (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    title_uz TEXT,
                    title_ru TEXT,
                    title_en TEXT,
                    description TEXT,
                    description_uz TEXT,
                    description_ru TEXT,
                    description_en TEXT,
                    image_url TEXT,
                    price_dcoin DOUBLE PRECISION DEFAULT 0,
                    required_tickets INTEGER DEFAULT 1,
                    probability_weight DOUBLE PRECISION DEFAULT 1,
                    active INTEGER DEFAULT 1,
                    created_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_gifts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    title_uz TEXT,
                    title_ru TEXT,
                    title_en TEXT,
                    description TEXT,
                    description_uz TEXT,
                    description_ru TEXT,
                    description_en TEXT,
                    image_url TEXT,
                    price_dcoin DOUBLE PRECISION DEFAULT 0,
                    required_tickets INTEGER DEFAULT 1,
                    probability_weight DOUBLE PRECISION DEFAULT 1,
                    active INTEGER DEFAULT 1,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_gifts",
            [
                ("title_uz", "TEXT"),
                ("title_ru", "TEXT"),
                ("title_en", "TEXT"),
                ("description", "TEXT"),
                ("description_uz", "TEXT"),
                ("description_ru", "TEXT"),
                ("description_en", "TEXT"),
                ("image_url", "TEXT"),
                ("price_dcoin", "DOUBLE PRECISION DEFAULT 0"),
                ("required_tickets", "INTEGER DEFAULT 1"),
                ("probability_weight", "DOUBLE PRECISION DEFAULT 1"),
                ("active", "INTEGER DEFAULT 1"),
                ("is_payment_discount", "INTEGER DEFAULT 0"),
                ("payment_discount_percent", "DOUBLE PRECISION DEFAULT 0"),
                ("created_by", "BIGINT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_gift_tickets (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    gift_id BIGINT NOT NULL,
                    ticket_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, gift_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_gift_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    gift_id INTEGER NOT NULL,
                    ticket_count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, gift_id)
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_gift_tickets",
            [
                ("ticket_count", "INTEGER DEFAULT 0"),
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_gift_chest_spins (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    winner_gift_id BIGINT,
                    cost_dcoin DOUBLE PRECISION DEFAULT 0,
                    awarded_tickets INTEGER DEFAULT 0,
                    roulette_payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_gift_chest_spins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    winner_gift_id INTEGER,
                    cost_dcoin DOUBLE PRECISION DEFAULT 0,
                    awarded_tickets INTEGER DEFAULT 0,
                    roulette_payload_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_gift_chest_spins",
            [
                ("winner_gift_id", "BIGINT"),
                ("cost_dcoin", "DOUBLE PRECISION DEFAULT 0"),
                ("awarded_tickets", "INTEGER DEFAULT 0"),
                ("roulette_payload_json", "TEXT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_gift_payment_discounts (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    gift_id BIGINT NOT NULL,
                    purchase_history_id BIGINT,
                    source_key TEXT UNIQUE,
                    ym TEXT NOT NULL,
                    discount_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    reason TEXT,
                    meta_json TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_gift_payment_discounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    gift_id INTEGER NOT NULL,
                    purchase_history_id INTEGER,
                    source_key TEXT UNIQUE,
                    ym TEXT NOT NULL,
                    discount_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active',
                    reason TEXT,
                    meta_json TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_gift_payment_discounts",
            [
                ("purchase_history_id", "BIGINT"),
                ("source_key", "TEXT"),
                ("discount_percent", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
                ("status", "TEXT NOT NULL DEFAULT 'active'"),
                ("reason", "TEXT"),
                ("meta_json", "TEXT"),
                ("applied_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_gifts_active ON web_gifts(active)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_gift_tickets_user ON web_gift_tickets(user_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_gift_spins_user ON web_gift_chest_spins(user_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_gift_payment_discount_user_ym ON web_gift_payment_discounts(user_id, ym, status)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_gift_payment_discount_purchase ON web_gift_payment_discounts(purchase_history_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_gift_payment_discount_source_key ON web_gift_payment_discounts(source_key)")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def ensure_purchase_history_schema() -> None:
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_purchase_history (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    item_id BIGINT,
                    item_type TEXT NOT NULL,
                    item_title TEXT,
                    amount_spent DOUBLE PRECISION NOT NULL DEFAULT 0,
                    balance_before DOUBLE PRECISION,
                    balance_after DOUBLE PRECISION,
                    source_page TEXT,
                    meta_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_purchase_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    item_id INTEGER,
                    item_type TEXT NOT NULL,
                    item_title TEXT,
                    amount_spent DOUBLE PRECISION NOT NULL DEFAULT 0,
                    balance_before DOUBLE PRECISION,
                    balance_after DOUBLE PRECISION,
                    source_page TEXT,
                    meta_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_purchase_history",
            [
                ("item_id", "BIGINT"),
                ("item_type", "TEXT NOT NULL"),
                ("item_title", "TEXT"),
                ("amount_spent", "DOUBLE PRECISION NOT NULL DEFAULT 0"),
                ("balance_before", "DOUBLE PRECISION"),
                ("balance_after", "DOUBLE PRECISION"),
                ("source_page", "TEXT"),
                ("meta_json", "TEXT"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_purchase_history_created ON web_purchase_history(created_at DESC)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_purchase_history_user_created ON web_purchase_history(user_id, created_at DESC)")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def log_purchase_history(
    *,
    user_id: int,
    item_id: int | None,
    item_type: str,
    item_title: str | None,
    amount_spent: float,
    balance_before: float | None,
    balance_after: float | None,
    source_page: str | None = None,
    meta: dict | None = None,
) -> int | None:
    ensure_purchase_history_schema()
    conn = get_conn()
    cur = conn.cursor()
    purchase_id = 0
    try:
        cur.execute(
            """
            INSERT INTO web_purchase_history (
                user_id, item_id, item_type, item_title,
                amount_spent, balance_before, balance_after,
                source_page, meta_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                int(item_id) if item_id else None,
                str(item_type or "").strip() or "other",
                str(item_title or "").strip() or None,
                float(amount_spent or 0.0),
                float(balance_before) if balance_before is not None else None,
                float(balance_after) if balance_after is not None else None,
                str(source_page or "").strip() or None,
                json.dumps(meta or {}, ensure_ascii=False) if meta is not None else None,
            ),
        )
        purchase_id = int(getattr(cur, "lastrowid", 0) or 0)
        if purchase_id <= 0 and _is_postgres_enabled():
            cur.execute("SELECT id FROM web_purchase_history ORDER BY id DESC LIMIT 1")
            row = _row_to_dict(cur.fetchone())
            purchase_id = int((row or {}).get("id") or 0)
        conn.commit()
    finally:
        conn.close()
    return purchase_id or None


def list_latest_purchase_history(limit: int = 500) -> list[dict]:
    ensure_purchase_history_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                p.*,
                g.title AS gift_title,
                g.title_uz AS gift_title_uz,
                g.title_ru AS gift_title_ru,
                g.title_en AS gift_title_en,
                g.description AS gift_description,
                g.description_uz AS gift_description_uz,
                g.description_ru AS gift_description_ru,
                g.description_en AS gift_description_en,
                g.image_url AS gift_image_url,
                g.price_dcoin AS gift_price_dcoin,
                g.required_tickets AS gift_required_tickets,
                g.is_payment_discount AS gift_is_payment_discount,
                g.payment_discount_percent AS gift_payment_discount_percent,
                u.first_name,
                u.last_name,
                u.login_id,
                u.phone,
                u.login_type,
                NULL AS role,
                u.owner_admin_id
            FROM web_purchase_history p
            LEFT JOIN web_gifts g
              ON g.id = p.item_id
             AND LOWER(COALESCE(p.item_type, '')) IN ('gift', 'chest')
            LEFT JOIN users u ON u.id = p.user_id
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT ?
            """,
            (max(1, min(1000, int(limit or 500))),),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def list_user_purchase_history(user_id: int, limit: int = 100, item_type: str | None = None) -> list[dict]:
    ensure_purchase_history_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        params: list[Any] = [int(user_id)]
        type_clause = ""
        if item_type:
            type_clause = " AND LOWER(p.item_type)=LOWER(?)"
            params.append(str(item_type).strip())
        params.append(max(1, min(300, int(limit or 100))))
        cur.execute(
            f"""
            SELECT
                p.*,
                g.title AS gift_title,
                g.title_uz AS gift_title_uz,
                g.title_ru AS gift_title_ru,
                g.title_en AS gift_title_en,
                g.description AS gift_description,
                g.description_uz AS gift_description_uz,
                g.description_ru AS gift_description_ru,
                g.description_en AS gift_description_en,
                g.image_url AS gift_image_url,
                g.price_dcoin AS gift_price_dcoin,
                g.required_tickets AS gift_required_tickets,
                g.is_payment_discount AS gift_is_payment_discount,
                g.payment_discount_percent AS gift_payment_discount_percent
            FROM web_purchase_history p
            LEFT JOIN web_gifts g
              ON g.id = p.item_id
             AND LOWER(COALESCE(p.item_type, '')) = 'gift'
            WHERE p.user_id=?
              {type_clause}
            ORDER BY p.created_at DESC, p.id DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()



def _normalize_content_type(content_type: str) -> str:
    raw = str(content_type or "").strip().lower()
    aliases = {
        "videos": "video",
        "video": "video",
        "books": "book",
        "book": "book",
        "homeworks": "homework",
        "homework": "homework",
    }
    return aliases.get(raw, raw)


def _normalize_content_test_questions_payload(questions: Any) -> list[dict]:
    if isinstance(questions, str):
        try:
            questions = json.loads(questions)
        except Exception:
            questions = []
    if not isinstance(questions, list):
        return []
    out: list[dict] = []
    letter_to_index = {"a": 0, "b": 1, "c": 2, "d": 3}
    for raw in questions:
        if not isinstance(raw, dict):
            continue
        question_text = str(raw.get("question") or raw.get("question_text") or "").strip()
        options_raw = raw.get("options")
        if isinstance(options_raw, dict):
            options = [str(options_raw.get(k) or "").strip() for k in ("A", "B", "C", "D")]
        elif isinstance(options_raw, list):
            options = [str(opt or "").strip() for opt in options_raw]
        else:
            options = [
                str(raw.get("option_a") or "").strip(),
                str(raw.get("option_b") or "").strip(),
                str(raw.get("option_c") or "").strip(),
                str(raw.get("option_d") or "").strip(),
            ]
        options = [opt for opt in options if opt]
        correct_index = raw.get("correct_option_index")
        if correct_index is None:
            correct_index = raw.get("correct_index")
        try:
            correct_idx = int(correct_index)
            if correct_idx >= 1 and correct_idx <= len(options):
                correct_idx -= 1
        except Exception:
            correct_idx = -1
        if correct_idx < 0:
            correct_raw = str(raw.get("correct") or raw.get("correct_option") or "").strip()
            lower = correct_raw.lower()
            if lower in letter_to_index:
                correct_idx = letter_to_index[lower]
            elif correct_raw in options:
                correct_idx = options.index(correct_raw)
        explanation = str(raw.get("explanation") or "").strip()
        raw_seconds = raw.get("time_limit_sec")
        if raw_seconds is None:
            raw_seconds = raw.get("time_limit_seconds")
        if raw_seconds is None:
            raw_seconds = raw.get("seconds")
        try:
            time_limit_sec = int(raw_seconds)
        except Exception:
            time_limit_sec = 30
        time_limit_sec = max(10, min(300, time_limit_sec or 30))
        if not question_text or len(options) < 2 or correct_idx < 0 or correct_idx >= len(options):
            continue
        out.append(
            {
                "question": question_text,
                "options": options,
                "correct_option_index": int(correct_idx),
                "correct": options[int(correct_idx)],
                "explanation": explanation,
                "time_limit_sec": int(time_limit_sec),
            }
        )
    return out


def _content_test_question_public(row: dict, include_answers: bool = True) -> dict:
    options: list[str] = []
    try:
        parsed = json.loads(str(row.get("options_json") or "[]"))
        if isinstance(parsed, list):
            options = [str(opt or "") for opt in parsed]
    except Exception:
        options = []
    correct_idx = int(row.get("correct_option_index") if row.get("correct_option_index") is not None else -1)
    payload = {
        "id": int(row.get("id") or 0),
        "question": str(row.get("question_text") or row.get("question") or "").strip(),
        "options": options,
        "order": int(row.get("order_index") or 0),
        "time_limit_sec": max(10, min(300, int(row.get("time_limit_sec") or 30))),
    }
    if include_answers:
        payload["correct_option_index"] = correct_idx
        payload["correct"] = options[correct_idx] if 0 <= correct_idx < len(options) else ""
        payload["explanation"] = str(row.get("explanation") or "").strip()
    return payload


def ensure_content_tests_schema() -> None:
    if _schema_ready("content_tests_v3"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_content_tests (
                    id BIGSERIAL PRIMARY KEY,
                    content_type TEXT NOT NULL,
                    content_id BIGINT NOT NULL,
                    title TEXT,
                    questions_json TEXT,
                    created_by BIGINT,
                    created_by_role TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(content_type, content_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_content_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_type TEXT NOT NULL,
                    content_id INTEGER NOT NULL,
                    title TEXT,
                    questions_json TEXT,
                    created_by INTEGER,
                    created_by_role TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(content_type, content_id)
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_content_test_questions",
            [
                ("time_limit_sec", "INTEGER DEFAULT 30"),
            ],
        )
        _ensure_table_columns(
            cur,
            "web_content_tests",
            [
                ("title", "TEXT"),
                ("questions_json", "TEXT"),
                ("created_by", "BIGINT"),
                ("created_by_role", "TEXT"),
                ("is_active", "INTEGER DEFAULT 1"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_content_test_questions (
                    id BIGSERIAL PRIMARY KEY,
                    test_id BIGINT NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    question_text TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    correct_option_index INTEGER NOT NULL,
                    explanation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_content_test_questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    question_text TEXT NOT NULL,
                    options_json TEXT NOT NULL,
                    correct_option_index INTEGER NOT NULL,
                    explanation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_content_test_attempts (
                    id BIGSERIAL PRIMARY KEY,
                    test_id BIGINT NOT NULL,
                    content_type TEXT NOT NULL,
                    content_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    wrong_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    total_questions INTEGER NOT NULL DEFAULT 0,
                    dpoints_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_content_test_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    content_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    correct_count INTEGER NOT NULL DEFAULT 0,
                    wrong_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    total_questions INTEGER NOT NULL DEFAULT 0,
                    dpoints_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
                    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_content_test_answers (
                    id BIGSERIAL PRIMARY KEY,
                    attempt_id BIGINT NOT NULL,
                    question_id BIGINT NOT NULL,
                    selected_option_index INTEGER,
                    is_correct INTEGER NOT NULL DEFAULT 0,
                    dpoints_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_content_test_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    selected_option_index INTEGER,
                    is_correct INTEGER NOT NULL DEFAULT 0,
                    dpoints_delta DOUBLE PRECISION NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_content_test_results (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    content_type TEXT NOT NULL,
                    content_id BIGINT NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL DEFAULT 0,
                    answers_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_content_test_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    content_type TEXT NOT NULL,
                    content_id INTEGER NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    total INTEGER NOT NULL DEFAULT 0,
                    answers_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        for stmt in (
            "CREATE INDEX IF NOT EXISTS idx_content_tests_content ON web_content_tests(content_type, content_id)",
            "CREATE INDEX IF NOT EXISTS idx_content_questions_test ON web_content_test_questions(test_id, order_index)",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_content_attempt_unique ON web_content_test_attempts(test_id, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_content_attempt_user_time ON web_content_test_attempts(user_id, submitted_at)",
            "CREATE INDEX IF NOT EXISTS idx_content_answers_attempt ON web_content_test_answers(attempt_id)",
            "CREATE INDEX IF NOT EXISTS idx_content_test_results_user ON web_content_test_results(user_id, content_type, content_id)",
        ):
            try:
                cur.execute(stmt)
            except Exception:
                pass
        conn.commit()
        _mark_schema_ready("content_tests_v3")
    finally:
        conn.close()


#: Yangi AI/avtomatik test turlari — bular MCQ jadvaliga emas, questions_json
#: dan xom holicha o'qiladi (kind/word/translation/pairs... saqlanishi uchun).
AI_CONTENT_TEST_KINDS = {
    "speak_sentence", "write_sentence", "guided_writing", "translation",
    "reading_open", "read_aloud", "paraphrase", "dialogue_completion",
    "picture_description", "listening", "dictation", "spelling",
    "matching", "scrambled_sentence", "gap_fill", "word_practice", "passage_cloze", "reading_set",
}


def _questions_have_ai_kinds(questions: Any) -> bool:
    if isinstance(questions, str):
        try:
            questions = json.loads(questions)
        except Exception:
            return False
    if not isinstance(questions, list):
        return False
    for q in questions:
        if isinstance(q, dict) and str(q.get("kind") or "").strip().lower() in AI_CONTENT_TEST_KINDS:
            return True
    return False


def _parse_questions_json(raw: Any) -> list[dict]:
    if isinstance(raw, list):
        return [q for q in raw if isinstance(q, dict)]
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
        return [q for q in parsed if isinstance(q, dict)] if isinstance(parsed, list) else []
    except Exception:
        return []


def _insert_content_test_questions_tx(cur, test_id: int, questions: list[dict]) -> None:
    cur.execute("DELETE FROM web_content_test_questions WHERE test_id=?", (int(test_id),))
    for index, question in enumerate(questions):
        options = [str(opt or "").strip() for opt in (question.get("options") or [])]
        cur.execute(
            """
            INSERT INTO web_content_test_questions(
                test_id, order_index, question_text, options_json, correct_option_index, explanation, time_limit_sec, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                int(test_id),
                int(index),
                str(question.get("question") or "").strip(),
                json.dumps(options, ensure_ascii=False),
                int(question.get("correct_option_index") or 0),
                str(question.get("explanation") or "").strip(),
                max(10, min(300, int(question.get("time_limit_sec") or 30))),
            ),
        )


def _fetch_content_test_questions_tx(cur, test_id: int, *, include_answers: bool = True) -> list[dict]:
    cur.execute(
        """
        SELECT *
        FROM web_content_test_questions
        WHERE test_id=?
        ORDER BY order_index ASC, id ASC
        """,
        (int(test_id),),
    )
    return [_content_test_question_public(_row_to_dict(row), include_answers=include_answers) for row in (cur.fetchall() or [])]


def _migrate_content_test_questions_if_needed_tx(cur, test_row: dict) -> None:
    test_id = int(test_row.get("id") or 0)
    if test_id <= 0:
        return
    cur.execute("SELECT COUNT(*) AS c FROM web_content_test_questions WHERE test_id=?", (test_id,))
    count_row = _row_to_dict(cur.fetchone())
    if int(count_row.get("c") or 0) > 0:
        return
    questions = _normalize_content_test_questions_payload(test_row.get("questions_json"))
    if questions:
        _insert_content_test_questions_tx(cur, test_id, questions)


def sync_book_questions_to_content_test(content_id: int, force: bool = False) -> None:
    ensure_content_tests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM book_questions WHERE book_id=? ORDER BY question_order ASC, id ASC", (int(content_id),))
        legacy_rows = [_row_to_dict(row) for row in (cur.fetchall() or [])]
        if not legacy_rows:
            return

        cur.execute("SELECT id FROM web_content_tests WHERE content_type='book' AND content_id=? LIMIT 1", (int(content_id),))
        test_row = _row_to_dict(cur.fetchone())
        
        if test_row and not force:
            test_id = int(test_row.get("id") or 0)
            cur.execute("SELECT COUNT(*) AS c FROM web_content_test_questions WHERE test_id=?", (test_id,))
            q_count_row = _row_to_dict(cur.fetchone())
            q_count = int((q_count_row or {}).get("c") or 0)
            if q_count >= len(legacy_rows):
                return

        questions: list[dict] = []
        for row in legacy_rows:
            options = [
                str(row.get("option_a") or "").strip(),
                str(row.get("option_b") or "").strip(),
                str(row.get("option_c") or "").strip(),
                str(row.get("option_d") or "").strip(),
            ]
            valid_options = [o for o in options if o]
            letter = str(row.get("correct_option") or "").strip().lower()
            correct_idx = {"a": 0, "b": 1, "c": 2, "d": 3}.get(letter, 0)
            if str(row.get("question") or "").strip() and len(valid_options) >= 2:
                questions.append(
                    {
                        "question": str(row.get("question") or "").strip(),
                        "options": valid_options,
                        "correct_option_index": min(correct_idx, max(0, len(valid_options) - 1)),
                        "explanation": str(row.get("explanation") or "").strip(),
                    }
                )
        if not questions:
            return

        payload = json.dumps(questions, ensure_ascii=False)
        try:
            cur.execute(
                """
                INSERT INTO web_content_tests(content_type, content_id, title, questions_json, created_by, created_by_role, is_active, updated_at)
                VALUES ('book', ?, 'Book test', ?, NULL, 'legacy', 1, CURRENT_TIMESTAMP)
                ON CONFLICT(content_type, content_id)
                DO UPDATE SET questions_json=EXCLUDED.questions_json, is_active=1, updated_at=CURRENT_TIMESTAMP
                """,
                (int(content_id), payload),
            )
        except Exception:
            cur.execute(
                """
                INSERT INTO web_content_tests(content_type, content_id, title, questions_json, created_by, created_by_role, is_active, updated_at)
                VALUES ('book', ?, 'Book test', ?, NULL, 'legacy', 1, CURRENT_TIMESTAMP)
                """,
                (int(content_id), payload),
            )
        cur.execute("SELECT id FROM web_content_tests WHERE content_type='book' AND content_id=? LIMIT 1", (int(content_id),))
        row = _row_to_dict(cur.fetchone())
        if row:
            _insert_content_test_questions_tx(cur, int(row.get("id") or 0), questions)
        conn.commit()
    finally:
        conn.close()


def _ensure_legacy_book_test_migrated(content_id: int) -> None:
    sync_book_questions_to_content_test(int(content_id), force=False)


def get_content_test(content_type: str, content_id: int, *, include_inactive: bool = False, include_answers: bool = True) -> dict | None:
    ensure_content_tests_schema()
    normalized_type = _normalize_content_type(content_type)
    if normalized_type == "book":
        sync_book_questions_to_content_test(int(content_id), force=False)
    conn = get_conn()
    cur = conn.cursor()
    try:
        active_clause = "" if include_inactive else " AND COALESCE(is_active, 1)=1"
        cur.execute(
            f"SELECT * FROM web_content_tests WHERE content_type=? AND content_id=? {active_clause} LIMIT 1",
            (normalized_type, int(content_id)),
        )
        row = _row_to_dict(cur.fetchone())
        if not row:
            return None
        # AI/yangi test turlari MCQ jadvaliga sig'maydi — ularni questions_json
        # dan xom holicha qaytaramiz (kind/word/translation/pairs saqlanadi).
        if _questions_have_ai_kinds(row.get("questions_json")):
            row["questions"] = _parse_questions_json(row.get("questions_json"))
            row["question_count"] = len(row["questions"])
            return row
        _migrate_content_test_questions_if_needed_tx(cur, row)
        conn.commit()
        row["questions"] = _fetch_content_test_questions_tx(cur, int(row.get("id") or 0), include_answers=include_answers)
        row["question_count"] = len(row["questions"])
        return row
    finally:
        conn.close()


def save_content_test(
    content_type: str,
    content_id: int,
    questions_json: str,
    created_by: int,
    *,
    title: str | None = None,
    created_by_role: str | None = None,
    is_active: bool = True,
    raw_questions: bool = False,
) -> dict | None:
    ensure_content_tests_schema()
    normalized_type = _normalize_content_type(content_type)
    if raw_questions:
        # AI/yangi test turlari (pairs, answer, kind, audio_url...) buzilmasligi uchun
        # MCQ normalizatsiyasini o'tkazib yuboramiz.
        if isinstance(questions_json, str):
            try:
                questions = json.loads(questions_json)
            except Exception:
                questions = []
        else:
            questions = questions_json
        if not isinstance(questions, list):
            questions = []
    else:
        # AI/yangi test turlari har qanday mijozdan kelsa ham buzilmasin:
        # `kind` maydoni bo'lsa xom holicha saqlaymiz (auto-detect).
        if _questions_have_ai_kinds(questions_json):
            if isinstance(questions_json, str):
                try:
                    questions = json.loads(questions_json)
                except Exception:
                    questions = []
            else:
                questions = questions_json
            if not isinstance(questions, list):
                questions = []
            raw_questions = True
        else:
            questions = _normalize_content_test_questions_payload(questions_json)
    conn = get_conn()
    cur = conn.cursor()
    try:
        payload = json.dumps(questions, ensure_ascii=False)
        test_id = 0
        try:
            cur.execute(
                """
                INSERT INTO web_content_tests(content_type, content_id, title, questions_json, created_by, created_by_role, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(content_type, content_id)
                DO UPDATE SET
                    title=COALESCE(EXCLUDED.title, web_content_tests.title),
                    questions_json=EXCLUDED.questions_json,
                    created_by=EXCLUDED.created_by,
                    created_by_role=EXCLUDED.created_by_role,
                    is_active=EXCLUDED.is_active,
                    updated_at=CURRENT_TIMESTAMP
                RETURNING id
                """,
                (
                    normalized_type,
                    int(content_id),
                    str(title or "").strip() or f"{normalized_type.title()} test",
                    payload,
                    int(created_by),
                    str(created_by_role or "").strip() or None,
                    1 if is_active else 0,
                ),
            )
            row = _row_to_dict(cur.fetchone())
            test_id = int(row.get("id") or 0)
        except Exception:
            cur.execute(
                """
                INSERT INTO web_content_tests(content_type, content_id, title, questions_json, created_by, created_by_role, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(content_type, content_id)
                DO UPDATE SET
                    title=COALESCE(EXCLUDED.title, web_content_tests.title),
                    questions_json=EXCLUDED.questions_json,
                    created_by=EXCLUDED.created_by,
                    created_by_role=EXCLUDED.created_by_role,
                    is_active=EXCLUDED.is_active,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    normalized_type,
                    int(content_id),
                    str(title or "").strip() or f"{normalized_type.title()} test",
                    payload,
                    int(created_by),
                    str(created_by_role or "").strip() or None,
                    1 if is_active else 0,
                ),
            )
            cur.execute("SELECT id FROM web_content_tests WHERE content_type=? AND content_id=? LIMIT 1", (normalized_type, int(content_id)))
            row = _row_to_dict(cur.fetchone())
            test_id = int(row.get("id") or 0)
        if test_id <= 0:
            conn.rollback()
            return None
        # AI/yangi test turlari uchun MCQ jadvalini to'ldirmaymiz (u ularni buzadi);
        # o'qishda questions_json dan xom holicha olinadi. Eski MCQ qatorlarini tozalaymiz.
        if raw_questions and _questions_have_ai_kinds(questions):
            try:
                cur.execute("DELETE FROM web_content_test_questions WHERE test_id=?", (int(test_id),))
            except Exception:
                pass
        else:
            _insert_content_test_questions_tx(cur, test_id, questions)
        conn.commit()
    finally:
        conn.close()
    return get_content_test(normalized_type, int(content_id), include_inactive=True, include_answers=True)


def deactivate_content_test(content_type: str, content_id: int) -> bool:
    ensure_content_tests_schema()
    normalized_type = _normalize_content_type(content_type)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE web_content_tests SET is_active=0, updated_at=CURRENT_TIMESTAMP WHERE content_type=? AND content_id=?",
            (normalized_type, int(content_id)),
        )
        changed = int(getattr(cur, "rowcount", 0) or 0)
        conn.commit()
        return changed > 0
    finally:
        conn.close()


def _serialize_content_attempt(row: dict | None, answers: list[dict] | None = None) -> dict | None:
    if not row:
        return None
    correct = int(row.get("correct_count") or row.get("score") or 0)
    total = int(row.get("total_questions") or row.get("total") or 0)
    wrong = int(row.get("wrong_count") or 0)
    skipped = int(row.get("skipped_count") or 0)
    delta = float(row.get("dpoints_delta") or 0.0)
    return {
        "id": int(row.get("id") or 0),
        "attempt_id": int(row.get("id") or 0),
        "test_id": int(row.get("test_id") or 0),
        "content_type": _normalize_content_type(str(row.get("content_type") or "")),
        "content_id": int(row.get("content_id") or 0),
        "user_id": int(row.get("user_id") or 0),
        "score": correct,
        "total": total,
        "correct": correct,
        "correct_count": correct,
        "wrong": wrong,
        "wrong_count": wrong,
        "skipped": skipped,
        "skipped_count": skipped,
        "unanswered": skipped,
        "total_questions": total,
        "dpoints_delta": delta,
        "score_percent": round((correct * 100.0) / max(1, total), 2),
        "passed": correct >= max(1, math.ceil(total * 0.7)) if total else False,
        "submitted_at": str(row.get("submitted_at") or row.get("created_at") or ""),
        "created_at": str(row.get("created_at") or ""),
        "answers": answers or [],
        "review": answers or [],
    }


def get_content_test_result(user_id: int, content_type: str, content_id: int) -> dict | None:
    ensure_content_tests_schema()
    normalized_type = _normalize_content_type(content_type)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT a.*
            FROM web_content_test_attempts a
            WHERE a.user_id=? AND a.content_type=? AND a.content_id=?
            ORDER BY a.id DESC
            LIMIT 1
            """,
            (int(user_id), normalized_type, int(content_id)),
        )
        attempt = _row_to_dict(cur.fetchone())
        if attempt:
            cur.execute(
                """
                SELECT ans.*, q.question_text, q.options_json, q.correct_option_index, q.explanation
                FROM web_content_test_answers ans
                LEFT JOIN web_content_test_questions q ON q.id=ans.question_id
                WHERE ans.attempt_id=?
                ORDER BY q.order_index ASC, ans.id ASC
                """,
                (int(attempt.get("id") or 0),),
            )
            answers: list[dict] = []
            for raw in (cur.fetchall() or []):
                row = _row_to_dict(raw)
                options: list[str] = []
                try:
                    parsed = json.loads(str(row.get("options_json") or "[]"))
                    if isinstance(parsed, list):
                        options = [str(opt or "") for opt in parsed]
                except Exception:
                    options = []
                selected_idx = row.get("selected_option_index")
                try:
                    selected_idx_int = int(selected_idx) if selected_idx is not None else None
                except Exception:
                    selected_idx_int = None
                correct_idx = int(row.get("correct_option_index") if row.get("correct_option_index") is not None else -1)
                answers.append(
                    {
                        "question_id": int(row.get("question_id") or 0),
                        "question": str(row.get("question_text") or "").strip(),
                        "selected_option_index": selected_idx_int,
                        "selected_option": options[selected_idx_int] if selected_idx_int is not None and 0 <= selected_idx_int < len(options) else None,
                        "correct_option_index": correct_idx,
                        "correct_option": options[correct_idx] if 0 <= correct_idx < len(options) else None,
                        "is_correct": bool(int(row.get("is_correct") or 0)),
                        "dpoints_delta": float(row.get("dpoints_delta") or 0.0),
                        "explanation": str(row.get("explanation") or "").strip() or None,
                    }
                )
            return _serialize_content_attempt(attempt, answers)
        cur.execute(
            "SELECT * FROM web_content_test_results WHERE user_id=? AND content_type=? AND content_id=? ORDER BY id DESC LIMIT 1",
            (int(user_id), normalized_type, int(content_id)),
        )
        legacy = _row_to_dict(cur.fetchone())
        if not legacy:
            return None
        answers = []
        if legacy.get("answers_json"):
            try:
                parsed = json.loads(str(legacy.get("answers_json") or "{}"))
                answers = parsed if isinstance(parsed, list) else []
            except Exception:
                answers = []
        legacy["correct_count"] = int(legacy.get("score") or 0)
        legacy["total_questions"] = int(legacy.get("total") or 0)
        return _serialize_content_attempt(legacy, answers)
    finally:
        conn.close()


def _resolve_selected_option_index(raw: Any, question: dict, fallback_index: int) -> int | None:
    options = [str(opt or "") for opt in (question.get("options") or [])]
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        idx = int(raw)
        if 0 <= idx < len(options):
            return idx
        if 1 <= idx <= len(options):
            return idx - 1
    value = str(raw).strip()
    if not value:
        return None
    if value in options:
        return options.index(value)
    lower = value.lower()
    if lower in {"a", "b", "c", "d"}:
        idx = {"a": 0, "b": 1, "c": 2, "d": 3}[lower]
        return idx if idx < len(options) else None
    if lower.isdigit():
        idx = int(lower)
        if 0 <= idx < len(options):
            return idx
        if 1 <= idx <= len(options):
            return idx - 1
    return None


def submit_content_test_attempt(
    user_id: int,
    content_type: str,
    content_id: int,
    answers: dict[str, Any],
    *,
    subject: str | None = None,
) -> dict | None:
    ensure_content_tests_schema()
    normalized_type = _normalize_content_type(content_type)
    test = get_content_test(normalized_type, int(content_id), include_inactive=False, include_answers=True)
    if not test or not test.get("questions"):
        return None
    existing = get_content_test_result(int(user_id), normalized_type, int(content_id))
    if existing:
        existing["already_submitted"] = True
        return existing
    questions = test.get("questions") or []
    correct = 0
    wrong = 0
    skipped = 0
    answer_rows: list[dict] = []
    for idx, question in enumerate(questions):
        qid = int(question.get("id") or 0)
        raw = None
        for key in (str(qid), str(idx), str(idx + 1)):
            if isinstance(answers, dict) and key in answers:
                raw = answers.get(key)
                break
        selected_idx = _resolve_selected_option_index(raw, question, idx)
        correct_idx = int(question.get("correct_option_index") if question.get("correct_option_index") is not None else -1)
        if selected_idx is None:
            skipped += 1
            delta = -3.0
            is_correct = False
        elif selected_idx == correct_idx:
            correct += 1
            delta = 2.0
            is_correct = True
        else:
            wrong += 1
            delta = -3.0
            is_correct = False
        if normalized_type == "homework":
            delta = 0.0
        answer_rows.append(
            {
                "question_id": qid,
                "selected_option_index": selected_idx,
                "is_correct": is_correct,
                "dpoints_delta": delta,
            }
        )
    total = len(questions)
    dpoints_delta = (correct * 2.0) - ((wrong + skipped) * 3.0)
    if normalized_type == "homework":
        dpoints_delta = 0.0
    conn = get_conn()
    cur = conn.cursor()
    attempt_id = 0
    try:
        cur.execute(
            """
            INSERT INTO web_content_test_attempts(
                test_id, content_type, content_id, user_id,
                correct_count, wrong_count, skipped_count, total_questions, dpoints_delta, submitted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                int(test.get("id") or 0),
                normalized_type,
                int(content_id),
                int(user_id),
                int(correct),
                int(wrong),
                int(skipped),
                int(total),
                float(dpoints_delta),
            ),
        )
        row = _row_to_dict(cur.fetchone())
        attempt_id = int(row.get("id") or 0)
        for item in answer_rows:
            cur.execute(
                """
                INSERT INTO web_content_test_answers(
                    attempt_id, question_id, selected_option_index, is_correct, dpoints_delta
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(attempt_id),
                    int(item["question_id"]),
                    item["selected_option_index"],
                    1 if item["is_correct"] else 0,
                    float(item["dpoints_delta"]),
                ),
            )
        if abs(float(dpoints_delta)) > 1e-9:
            add_dpoints_tx(
                cur,
                int(user_id),
                float(dpoints_delta),
                subject or "GLOBAL",
                change_type=f"{normalized_type}_test:{int(content_id)}:{int(test.get('id') or 0)}:{attempt_id}",
            )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        existing_after = get_content_test_result(int(user_id), normalized_type, int(content_id))
        if existing_after:
            existing_after["already_submitted"] = True
            return existing_after
        raise
    finally:
        conn.close()
    return get_content_test_result(int(user_id), normalized_type, int(content_id))


def save_content_test_result(user_id: int, content_type: str, content_id: int, score: int, total: int, answers_json: str) -> dict | None:
    ensure_content_tests_schema()
    normalized_type = _normalize_content_type(content_type)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO web_content_test_results(user_id, content_type, content_id, score, total, answers_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (int(user_id), normalized_type, int(content_id), int(score), int(total), str(answers_json))
        )
        conn.commit()
    finally:
        conn.close()
    return get_content_test_result(user_id, normalized_type, content_id)


def ensure_homework_schema() -> None:
    if _schema_ready("homework"):
        return
    conn = get_conn()
    cur = conn.cursor()
    schema_lock_acquired = False
    try:
        if _is_postgres_enabled():
            cur.execute("SELECT pg_advisory_lock(?)", (92025052801,))
            schema_lock_acquired = True
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_homeworks (
                    id BIGSERIAL PRIMARY KEY,
                    teacher_id BIGINT NOT NULL,
                    student_id BIGINT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_at TIMESTAMP,
                    image_url TEXT,
                    dcoin_effect DOUBLE PRECISION DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_homeworks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_at TEXT,
                    image_url TEXT,
                    dcoin_effect DOUBLE PRECISION DEFAULT 0,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_homeworks",
            [
                ("description", "TEXT"),
                ("group_id", "BIGINT"),
                ("target_type", "TEXT DEFAULT 'student'"),
                ("homework_kind", "TEXT DEFAULT 'both'"),
                ("due_at", "TIMESTAMP"),
                ("image_url", "TEXT"),
                ("dcoin_effect", "DOUBLE PRECISION DEFAULT 0"),
                ("status", "TEXT DEFAULT 'active'"),
                ("requires_voice_message", "BOOLEAN DEFAULT FALSE"),
                ("requires_file", "BOOLEAN DEFAULT FALSE"),
                ("is_voiceroom", "BOOLEAN DEFAULT FALSE"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_homework_submissions (
                    id BIGSERIAL PRIMARY KEY,
                    homework_id BIGINT NOT NULL,
                    student_id BIGINT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    note TEXT,
                    proof_image_url TEXT,
                    dcoin_delta DOUBLE PRECISION DEFAULT 0,
                    review_note TEXT,
                    reviewed_by BIGINT,
                    reviewed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(homework_id, student_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_homework_submissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    homework_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    status TEXT DEFAULT 'pending',
                    note TEXT,
                    proof_image_url TEXT,
                    dcoin_delta DOUBLE PRECISION DEFAULT 0,
                    review_note TEXT,
                    reviewed_by INTEGER,
                    reviewed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(homework_id, student_id)
                )
                """,
            ],
        )
        _ensure_table_columns(
            cur,
            "web_homework_submissions",
            [
                ("status", "TEXT DEFAULT 'pending'"),
                ("note", "TEXT"),
                ("proof_image_url", "TEXT"),
                ("proof_images_json", "TEXT"),
                ("dcoin_delta", "DOUBLE PRECISION DEFAULT 0"),
                ("dpoints_delta", "DOUBLE PRECISION DEFAULT 0"),
                ("review_note", "TEXT"),
                ("reviewed_by", "BIGINT"),
                ("reviewed_at", "TIMESTAMP"),
                ("voice_message_url", "TEXT"),
                ("ai_transcript", "TEXT"),
                ("ai_feedback", "TEXT"),
                ("ai_analyzed_at", "TIMESTAMP"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homeworks_teacher ON web_homeworks(teacher_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homeworks_student ON web_homeworks(student_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homeworks_group ON web_homeworks(group_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homework_submissions_homework ON web_homework_submissions(homework_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homeworks_teacher_created ON web_homeworks(teacher_id, created_at DESC)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homeworks_group_created ON web_homeworks(group_id, created_at DESC)")
        except Exception:
            pass
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_homework_deadline_penalties (
                    id BIGSERIAL PRIMARY KEY,
                    homework_id BIGINT NOT NULL,
                    student_id BIGINT NOT NULL,
                    penalty_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(homework_id, student_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_homework_deadline_penalties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    homework_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    penalty_dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(homework_id, student_id)
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homework_penalties_homework ON web_homework_deadline_penalties(homework_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_homework_penalties_student ON web_homework_deadline_penalties(student_id)")
        except Exception:
            pass
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS web_homework_voiceroom_groups (
                    id BIGSERIAL PRIMARY KEY,
                    homework_id BIGINT NOT NULL,
                    student1_id BIGINT NOT NULL,
                    student2_id BIGINT,
                    student3_id BIGINT,
                    room_id TEXT NOT NULL,
                    recorded_audio_url TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS web_homework_voiceroom_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    homework_id INTEGER NOT NULL,
                    student1_id INTEGER NOT NULL,
                    student2_id INTEGER,
                    student3_id INTEGER,
                    room_id TEXT NOT NULL,
                    recorded_audio_url TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_hw_vr_groups_hw ON web_homework_voiceroom_groups(homework_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_web_hw_vr_groups_room ON web_homework_voiceroom_groups(room_id)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("homework")
    finally:
        if schema_lock_acquired:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                cur.execute("SELECT pg_advisory_unlock(?)", (92025052801,))
                conn.commit()
            except Exception:
                pass
        conn.close()


def list_gifts(active_only: bool = True) -> list[dict]:
    ensure_gifts_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        if active_only:
            cur.execute("SELECT * FROM web_gifts WHERE COALESCE(active, 1)=1 ORDER BY id ASC")
        else:
            cur.execute("SELECT * FROM web_gifts ORDER BY id ASC")
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def get_gift(gift_id: int) -> dict | None:
    ensure_gifts_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM web_gifts WHERE id=? LIMIT 1", (int(gift_id),))
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def create_gift(
    title: str,
    description: str | None = None,
    title_uz: str | None = None,
    title_ru: str | None = None,
    title_en: str | None = None,
    description_uz: str | None = None,
    description_ru: str | None = None,
    description_en: str | None = None,
    image_url: str | None = None,
    price_dcoin: float = 0.0,
    required_tickets: int = 1,
    probability_weight: float = 1.0,
    active: bool = True,
    created_by: int | None = None,
    is_payment_discount: bool = False,
    payment_discount_percent: float = 0.0,
) -> dict | None:
    ensure_gifts_schema()
    conn = get_conn()
    cur = conn.cursor()
    gift_id = 0
    try:
        cur.execute(
            """
            INSERT INTO web_gifts(
                title, title_uz, title_ru, title_en,
                description, description_uz, description_ru, description_en,
                image_url, price_dcoin, required_tickets, probability_weight,
                active, created_by, is_payment_discount, payment_discount_percent
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(title or "").strip(),
                str(title_uz or "").strip() or None,
                str(title_ru or "").strip() or None,
                str(title_en or "").strip() or None,
                description,
                str(description_uz or "").strip() or None,
                str(description_ru or "").strip() or None,
                str(description_en or "").strip() or None,
                image_url,
                float(price_dcoin or 0),
                int(required_tickets or 1),
                float(probability_weight or 1),
                1 if active else 0,
                int(created_by or 0) if created_by else None,
                1 if is_payment_discount else 0,
                max(0.0, min(100.0, float(payment_discount_percent or 0.0))) if is_payment_discount else 0.0,
            ),
        )
        gift_id = int(getattr(cur, "lastrowid", 0) or 0)
        if gift_id <= 0 and _is_postgres_enabled():
            cur.execute("SELECT id FROM web_gifts ORDER BY id DESC LIMIT 1")
            row = _row_to_dict(cur.fetchone())
            gift_id = int(row.get("id") or 0)
        conn.commit()
    finally:
        conn.close()
    return get_gift(gift_id) if gift_id > 0 else None


def update_gift(
    gift_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    title_uz: str | None = None,
    title_ru: str | None = None,
    title_en: str | None = None,
    description_uz: str | None = None,
    description_ru: str | None = None,
    description_en: str | None = None,
    image_url: str | None = None,
    price_dcoin: float | None = None,
    required_tickets: int | None = None,
    probability_weight: float | None = None,
    active: bool | None = None,
    is_payment_discount: bool | None = None,
    payment_discount_percent: float | None = None,
) -> bool:
    ensure_gifts_schema()
    updates: list[str] = ["updated_at=CURRENT_TIMESTAMP"]
    params: list[Any] = []
    if title is not None:
        updates.append("title=?")
        params.append(str(title).strip())
    if title_uz is not None:
        updates.append("title_uz=?")
        params.append(str(title_uz).strip() or None)
    if title_ru is not None:
        updates.append("title_ru=?")
        params.append(str(title_ru).strip() or None)
    if title_en is not None:
        updates.append("title_en=?")
        params.append(str(title_en).strip() or None)
    if description is not None:
        updates.append("description=?")
        params.append(description)
    if description_uz is not None:
        updates.append("description_uz=?")
        params.append(str(description_uz).strip() or None)
    if description_ru is not None:
        updates.append("description_ru=?")
        params.append(str(description_ru).strip() or None)
    if description_en is not None:
        updates.append("description_en=?")
        params.append(str(description_en).strip() or None)
    if image_url is not None:
        updates.append("image_url=?")
        params.append(image_url)
    if price_dcoin is not None:
        updates.append("price_dcoin=?")
        params.append(float(price_dcoin))
    if required_tickets is not None:
        updates.append("required_tickets=?")
        params.append(max(1, int(required_tickets)))
    if probability_weight is not None:
        updates.append("probability_weight=?")
        params.append(max(0.0, float(probability_weight)))
    if active is not None:
        updates.append("active=?")
        params.append(1 if active else 0)
    if is_payment_discount is not None:
        updates.append("is_payment_discount=?")
        params.append(1 if is_payment_discount else 0)
        if not is_payment_discount and payment_discount_percent is None:
            updates.append("payment_discount_percent=?")
            params.append(0.0)
    if payment_discount_percent is not None:
        updates.append("payment_discount_percent=?")
        params.append(max(0.0, min(100.0, float(payment_discount_percent or 0.0))))
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE web_gifts SET {', '.join(updates)} WHERE id=?",
            (*params, int(gift_id)),
        )
        conn.commit()
        return bool(cur.rowcount > 0)
    finally:
        conn.close()


def get_user_gift_tickets(user_id: int) -> list[dict]:
    ensure_gifts_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT t.user_id, t.gift_id, t.ticket_count, t.updated_at,
                   g.title, g.image_url, g.required_tickets, g.active
            FROM web_gift_tickets t
            LEFT JOIN web_gifts g ON g.id=t.gift_id
            WHERE t.user_id=?
            ORDER BY t.gift_id ASC
            """,
            (int(user_id),),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def add_user_gift_ticket(user_id: int, gift_id: int, ticket_count: int = 1) -> dict | None:
    ensure_gifts_schema()
    delta = max(0, int(ticket_count or 0))
    if delta <= 0:
        rows = [row for row in get_user_gift_tickets(int(user_id)) if int(row.get("gift_id") or 0) == int(gift_id)]
        return rows[0] if rows else None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO web_gift_tickets(user_id, gift_id, ticket_count, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, gift_id)
            DO UPDATE SET ticket_count=COALESCE(web_gift_tickets.ticket_count, 0) + EXCLUDED.ticket_count,
                          updated_at=CURRENT_TIMESTAMP
            """,
            (int(user_id), int(gift_id), delta),
        )
        conn.commit()
    finally:
        conn.close()
    rows = [row for row in get_user_gift_tickets(int(user_id)) if int(row.get("gift_id") or 0) == int(gift_id)]
    return rows[0] if rows else None


def log_gift_chest_spin(
    user_id: int,
    winner_gift_id: int | None,
    cost_dcoin: float,
    awarded_tickets: int = 0,
    roulette_payload_json: str | None = None,
) -> int | None:
    ensure_gifts_schema()
    conn = get_conn()
    cur = conn.cursor()
    spin_id = None
    try:
        cur.execute(
            """
            INSERT INTO web_gift_chest_spins(
                user_id, winner_gift_id, cost_dcoin, awarded_tickets, roulette_payload_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(user_id),
                int(winner_gift_id) if winner_gift_id else None,
                float(cost_dcoin or 0),
                int(awarded_tickets or 0),
                roulette_payload_json,
            ),
        )
        spin_id = int(getattr(cur, "lastrowid", 0) or 0)
        if spin_id <= 0 and _is_postgres_enabled():
            cur.execute("SELECT id FROM web_gift_chest_spins ORDER BY id DESC LIMIT 1")
            row = _row_to_dict(cur.fetchone())
            spin_id = int(row.get("id") or 0)
        conn.commit()
        return spin_id or None
    finally:
        conn.close()


def record_gift_payment_discount(
    *,
    user_id: int,
    gift_id: int,
    purchase_history_id: int | None,
    ym: str,
    discount_percent: float,
    status: str = "applied",
    reason: str | None = None,
    meta: dict | None = None,
) -> dict | None:
    ensure_gifts_schema()
    uid = int(user_id or 0)
    gid = int(gift_id or 0)
    purchase_id = int(purchase_history_id or 0)
    source_key = f"gift_payment_discount:{purchase_id}" if purchase_id > 0 else f"gift_payment_discount:{uid}:{gid}:{ym}:{datetime.utcnow().timestamp()}"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO web_gift_payment_discounts(
                user_id, gift_id, purchase_history_id, source_key, ym,
                discount_percent, status, reason, meta_json, applied_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(source_key) DO NOTHING
            """,
            (
                uid,
                gid,
                purchase_id if purchase_id > 0 else None,
                source_key,
                str(ym or "").strip(),
                max(0.0, min(100.0, float(discount_percent or 0.0))),
                str(status or "applied").strip() or "applied",
                str(reason or "").strip() or None,
                json.dumps(meta or {}, ensure_ascii=False) if meta is not None else None,
            ),
        )
        conn.commit()
        cur.execute("SELECT * FROM web_gift_payment_discounts WHERE source_key=? LIMIT 1", (source_key,))
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def get_active_gift_payment_discount(user_id: int, ym: str) -> dict | None:
    ensure_gifts_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT d.*, g.title AS gift_title
            FROM web_gift_payment_discounts d
            LEFT JOIN web_gifts g ON g.id=d.gift_id
            WHERE d.user_id=?
              AND d.ym=?
              AND LOWER(COALESCE(d.status, 'applied')) IN ('active', 'applied')
              AND COALESCE(d.discount_percent, 0) > 0
            ORDER BY COALESCE(d.discount_percent, 0) DESC, d.applied_at DESC, d.id DESC
            LIMIT 1
            """,
            (int(user_id), str(ym or "").strip()),
        )
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def expire_other_gift_payment_discounts(user_id: int, ym: str, keep_id: int | None = None) -> int:
    ensure_gifts_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        params: list[Any] = [int(user_id), str(ym or "").strip()]
        extra = ""
        if int(keep_id or 0) > 0:
            extra = " AND id<>?"
            params.append(int(keep_id or 0))
        cur.execute(
            f"""
            UPDATE web_gift_payment_discounts
            SET status='expired_replaced',
                reason=COALESCE(reason, '') || CASE WHEN COALESCE(reason, '')='' THEN '' ELSE ' | ' END || 'expired because another bigger active discount was applied'
            WHERE user_id=?
              AND ym=?
              AND LOWER(COALESCE(status, 'applied')) IN ('active', 'applied')
              {extra}
            """,
            tuple(params),
        )
        changed = int(cur.rowcount or 0)
        conn.commit()
        return changed
    finally:
        conn.close()


def open_gift_chest_atomic(
    *,
    user_id: int,
    winner_gift_id: int,
    winner_title: str | None,
    cost_dcoin: float,
    awarded_tickets: int = 1,
    roulette_payload_json: str | None = None,
) -> dict[str, Any]:
    """Charge a gift chest spin and award its ticket in one transaction."""
    ensure_gifts_schema()
    ensure_purchase_history_schema()
    ensure_dpoints_schema()
    amount = max(0.0, float(cost_dcoin or 0.0))
    ticket_delta = max(1, int(awarded_tickets or 1))
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            if _is_accountless_user_tx(cur, int(user_id)):
                return {"ok": False, "reason": "accountless_user"}
            if not _ensure_user_dpoints_ready(cur, context="open_gift_chest_atomic"):
                return {"ok": False, "reason": "wallet_not_ready"}
            balance_before = float(_visible_dcoin_balance_tx(cur, int(user_id)))
            _ensure_user_dpoints_row(cur, int(user_id))

            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            if amount > 0:
                ok, balance_before, _balance_after = _spend_visible_dcoins_tx(cur, int(user_id), amount, now)
                if not ok:
                    return {"ok": False, "reason": "insufficient_balance", "balance_before": balance_before}
                cur.execute(
                    """
                    INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (int(user_id), -float(amount), 0.0, "GLOBAL", now, "gift_chest_open"),
                )

            cur.execute(
                """
                INSERT INTO web_gift_tickets(user_id, gift_id, ticket_count, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, gift_id)
                DO UPDATE SET ticket_count=COALESCE(web_gift_tickets.ticket_count, 0) + EXCLUDED.ticket_count,
                              updated_at=CURRENT_TIMESTAMP
                """,
                (int(user_id), int(winner_gift_id), int(ticket_delta)),
            )
            cur.execute(
                """
                INSERT INTO web_gift_chest_spins(
                    user_id, winner_gift_id, cost_dcoin, awarded_tickets, roulette_payload_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    int(winner_gift_id),
                    float(amount),
                    int(ticket_delta),
                    roulette_payload_json,
                ),
            )
            spin_id = int(getattr(cur, "lastrowid", 0) or 0)
            if spin_id <= 0:
                cur.execute("SELECT id FROM web_gift_chest_spins WHERE user_id=? ORDER BY id DESC LIMIT 1", (int(user_id),))
                spin_row = _row_to_dict(cur.fetchone())
                spin_id = int((spin_row or {}).get("id") or 0)

            balance_after = float(_visible_dcoin_balance_tx(cur, int(user_id)))
            # Chest ochilishi purchase history ga yozilmaydi (xarid emas)
            purchase_id = 0
            cur.execute(
                """
                SELECT t.user_id, t.gift_id, t.ticket_count, t.updated_at,
                       g.title, g.image_url, g.required_tickets, g.active
                FROM web_gift_tickets t
                LEFT JOIN web_gifts g ON g.id=t.gift_id
                WHERE t.user_id=? AND t.gift_id=?
                LIMIT 1
                """,
                (int(user_id), int(winner_gift_id)),
            )
            ticket_row = _row_to_dict(cur.fetchone())
            conn.commit()
            return {
                "ok": True,
                "spin_id": int(spin_id or 0),
                "purchase_id": int(purchase_id or 0),
                "ticket": ticket_row,
                "balance_before": float(balance_before),
                "balance_after": float(balance_after),
            }
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("open_gift_chest_atomic failed user_id=%s gift_id=%s", user_id, winner_gift_id)
            return {"ok": False, "reason": "transaction_failed", "error": str(exc)}
        finally:
            conn.close()


def purchase_gift_with_tickets_atomic(
    *,
    user_id: int,
    gift_id: int,
) -> dict[str, Any]:
    """Purchase a gift after the user has enough per-gift tickets and D'coin."""
    ensure_gifts_schema()
    ensure_purchase_history_schema()
    ensure_dpoints_schema()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            if _is_accountless_user_tx(cur, int(user_id)):
                return {"ok": False, "reason": "accountless_user"}
            cur.execute("SELECT * FROM web_gifts WHERE id=? LIMIT 1", (int(gift_id),))
            gift = _row_to_dict(cur.fetchone())
            if not gift or int(gift.get("active") or 0) != 1:
                return {"ok": False, "reason": "gift_not_found"}

            required_tickets = max(1, int(gift.get("required_tickets") or 1))
            price = max(0.0, float(gift.get("price_dcoin") or 0.0))
            cur.execute(
                "SELECT * FROM web_gift_tickets WHERE user_id=? AND gift_id=? LIMIT 1",
                (int(user_id), int(gift_id)),
            )
            ticket_row = _row_to_dict(cur.fetchone())
            current_tickets = max(0, int((ticket_row or {}).get("ticket_count") or 0))
            if current_tickets < required_tickets:
                return {
                    "ok": False,
                    "reason": "insufficient_tickets",
                    "ticket_count": int(current_tickets),
                    "required_tickets": int(required_tickets),
                }

            balance_before = float(_visible_dcoin_balance_tx(cur, int(user_id)))
            if price > 0:
                if not _ensure_user_dpoints_ready(cur, context="purchase_gift_with_tickets_atomic"):
                    return {"ok": False, "reason": "wallet_not_ready", "balance_before": balance_before}
                _ensure_user_dpoints_row(cur, int(user_id))
                now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                ok, balance_before, _balance_after = _spend_visible_dcoins_tx(cur, int(user_id), price, now)
                if not ok:
                    return {
                        "ok": False,
                        "reason": "insufficient_balance",
                        "balance_before": balance_before,
                        "price_dcoin": float(price),
                    }
                cur.execute(
                    """
                    INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (int(user_id), -float(price), 0.0, "GLOBAL", now, "gift_purchase"),
                )

            remaining_tickets = max(0, current_tickets - required_tickets)
            cur.execute(
                """
                UPDATE web_gift_tickets
                SET ticket_count=?, updated_at=CURRENT_TIMESTAMP
                WHERE user_id=? AND gift_id=?
                """,
                (int(remaining_tickets), int(user_id), int(gift_id)),
            )
            balance_after = float(_visible_dcoin_balance_tx(cur, int(user_id)))
            cur.execute(
                """
                INSERT INTO web_purchase_history (
                    user_id, item_id, item_type, item_title,
                    amount_spent, balance_before, balance_after,
                    source_page, meta_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(user_id),
                    int(gift_id),
                    "gift",
                    str(gift.get("title") or "").strip() or "Gift",
                    float(price),
                    float(balance_before),
                    float(balance_after),
                    "student_gifts",
                    json.dumps(
                        {
                            "required_tickets": int(required_tickets),
                            "tickets_before": int(current_tickets),
                            "tickets_after": int(remaining_tickets),
                            "is_payment_discount": bool(int(gift.get("is_payment_discount") or 0) == 1),
                            "payment_discount_percent": max(0.0, min(100.0, float(gift.get("payment_discount_percent") or 0.0))),
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            purchase_id = int(getattr(cur, "lastrowid", 0) or 0)
            if purchase_id <= 0:
                cur.execute("SELECT id FROM web_purchase_history WHERE user_id=? ORDER BY id DESC LIMIT 1", (int(user_id),))
                purchase_row = _row_to_dict(cur.fetchone())
                purchase_id = int((purchase_row or {}).get("id") or 0)
            cur.execute(
                """
                SELECT t.user_id, t.gift_id, t.ticket_count, t.updated_at,
                       g.title, g.image_url, g.required_tickets, g.active
                FROM web_gift_tickets t
                LEFT JOIN web_gifts g ON g.id=t.gift_id
                WHERE t.user_id=? AND t.gift_id=?
                LIMIT 1
                """,
                (int(user_id), int(gift_id)),
            )
            updated_ticket = _row_to_dict(cur.fetchone())
            conn.commit()
            return {
                "ok": True,
                "purchase_id": int(purchase_id or 0),
                "gift": gift,
                "ticket": updated_ticket,
                "balance_before": float(balance_before),
                "balance_after": float(balance_after),
            }
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("purchase_gift_with_tickets_atomic failed user_id=%s gift_id=%s", user_id, gift_id)
            return {"ok": False, "reason": "transaction_failed", "error": str(exc)}
        finally:
            conn.close()


def purchase_book_with_dcoins(
    *,
    user_id: int,
    book_id: int,
    price_dcoin: float,
    deadline_at: str | None,
    book_title: str | None = None,
    deadline_days: int | None = None,
) -> dict[str, Any]:
    """Create a book purchase and charge its D'coin price atomically."""
    ensure_dpoints_schema()
    ensure_purchase_history_schema()
    price = max(0.0, float(price_dcoin or 0.0))
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM student_book_purchases WHERE user_id=? AND book_id=? LIMIT 1",
                (int(user_id), int(book_id)),
            )
            existing = _row_to_dict(cur.fetchone())
            if existing:
                return {
                    "ok": True,
                    "already_purchased": True,
                    "purchase": existing,
                    "balance_after": float(_visible_dcoin_balance_tx(cur, int(user_id))),
                }

            balance_before = float(_visible_dcoin_balance_tx(cur, int(user_id)))
            if price > 0:
                if _is_accountless_user_tx(cur, int(user_id)):
                    return {"ok": False, "reason": "accountless_user", "balance_before": balance_before}
                if not _ensure_user_dpoints_ready(cur, context="purchase_book_with_dcoins"):
                    return {"ok": False, "reason": "wallet_not_ready", "balance_before": balance_before}
                _ensure_user_dpoints_row(cur, int(user_id))
                now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                ok, balance_before, _balance_after = _spend_visible_dcoins_tx(cur, int(user_id), price, now)
                if not ok:
                    return {"ok": False, "reason": "insufficient_balance", "balance_before": balance_before}
                cur.execute(
                    """
                    INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (int(user_id), -float(price), 0.0, "GLOBAL", now, "book_purchase"),
                )

            cur.execute(
                """
                INSERT INTO student_book_purchases (user_id, book_id, purchased_at, deadline_at, status)
                VALUES (?, ?, CURRENT_TIMESTAMP, ?, 'active')
                """,
                (int(user_id), int(book_id), deadline_at),
            )
            cur.execute("UPDATE books SET purchase_count = COALESCE(purchase_count, 0) + 1 WHERE id = ?", (int(book_id),))
            cur.execute(
                "SELECT * FROM student_book_purchases WHERE user_id=? AND book_id=? LIMIT 1",
                (int(user_id), int(book_id)),
            )
            purchase = _row_to_dict(cur.fetchone())
            balance_after = float(_visible_dcoin_balance_tx(cur, int(user_id)))
            purchase_history_id = 0
            if price > 0:
                cur.execute(
                    """
                    INSERT INTO web_purchase_history (
                        user_id, item_id, item_type, item_title,
                        amount_spent, balance_before, balance_after,
                        source_page, meta_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(user_id),
                        int(book_id),
                        "book",
                        str(book_title or "").strip() or "Book",
                        float(price),
                        float(balance_before),
                        float(balance_after),
                        "student_books",
                        json.dumps(
                            {
                                "deadline_days": int(deadline_days or 7),
                                "purchase_id": int((purchase or {}).get("id") or 0),
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                purchase_history_id = int(getattr(cur, "lastrowid", 0) or 0)
                if purchase_history_id <= 0:
                    cur.execute("SELECT id FROM web_purchase_history WHERE user_id=? ORDER BY id DESC LIMIT 1", (int(user_id),))
                    purchase_history_row = _row_to_dict(cur.fetchone())
                    purchase_history_id = int((purchase_history_row or {}).get("id") or 0)
            conn.commit()
            return {
                "ok": True,
                "already_purchased": False,
                "purchase": purchase,
                "purchase_history_id": int(purchase_history_id or 0),
                "balance_before": float(balance_before),
                "balance_after": float(balance_after),
            }
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("purchase_book_with_dcoins failed user_id=%s book_id=%s", user_id, book_id)
            return {"ok": False, "reason": "transaction_failed", "error": str(exc)}
        finally:
            conn.close()


def get_teacher_homework_settings(teacher_id: int) -> dict:
    """Returns homework settings for a teacher, defaulting ai_auto_grade to False."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM teacher_homework_settings WHERE teacher_id = ?", (int(teacher_id),))
        row = cur.fetchone()
        if not row:
            return {"teacher_id": int(teacher_id), "ai_auto_grade": False}
        res = _row_to_dict(row)
        return {
            "teacher_id": int(teacher_id),
            "ai_auto_grade": bool(res.get("ai_auto_grade")),
            "updated_at": str(res.get("updated_at") or ""),
        }
    except Exception:
        logger.exception("get_teacher_homework_settings failed teacher_id=%s", teacher_id)
        return {"teacher_id": int(teacher_id), "ai_auto_grade": False}
    finally:
        conn.close()


def upsert_teacher_homework_settings(teacher_id: int, ai_auto_grade: bool) -> dict:
    """Updates or inserts teacher homework settings."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        val = 1 if ai_auto_grade else 0
        if _is_postgres_enabled():
            cur.execute(
                """
                INSERT INTO teacher_homework_settings (teacher_id, ai_auto_grade, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (teacher_id)
                DO UPDATE SET ai_auto_grade = EXCLUDED.ai_auto_grade, updated_at = CURRENT_TIMESTAMP
                """,
                (int(teacher_id), val),
            )
        else:
            cur.execute(
                """
                INSERT INTO teacher_homework_settings (teacher_id, ai_auto_grade, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (teacher_id)
                DO UPDATE SET ai_auto_grade = excluded.ai_auto_grade, updated_at = CURRENT_TIMESTAMP
                """,
                (int(teacher_id), val),
            )
        conn.commit()
        return {"teacher_id": int(teacher_id), "ai_auto_grade": bool(ai_auto_grade)}
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.exception("upsert_teacher_homework_settings failed teacher_id=%s", teacher_id)
        raise exc
    finally:
        conn.close()


def transfer_dcoins_atomic(
    *,
    sender_id: int,
    recipient_id: int,
    amount: float,
    subject: str | None = None,
) -> dict[str, Any]:
    """Move visible D'coin between two real users without touching legacy balances."""
    ensure_dpoints_schema()
    amount_value = float(amount or 0.0)
    if amount_value <= 0:
        return {"ok": False, "reason": "invalid_amount"}
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, login_type FROM users WHERE id=? LIMIT 1", (int(sender_id),))
            sender = _row_to_dict(cur.fetchone())
            cur.execute("SELECT id, login_type FROM users WHERE id=? LIMIT 1", (int(recipient_id),))
            recipient = _row_to_dict(cur.fetchone())
            if not sender or not recipient:
                return {"ok": False, "reason": "user_not_found"}
            if _is_accountless_user_tx(cur, int(sender_id)) or _is_accountless_user_tx(cur, int(recipient_id)):
                return {"ok": False, "reason": "accountless_user"}
            if not _ensure_user_dpoints_ready(cur, context="transfer_dcoins_atomic"):
                return {"ok": False, "reason": "wallet_not_ready"}

            _ensure_user_dpoints_row(cur, int(sender_id))
            _ensure_user_dpoints_row(cur, int(recipient_id))
            sender_balance_before = float(_visible_dcoin_balance_tx(cur, int(sender_id)))
            if sender_balance_before + 1e-9 < amount_value:
                return {"ok": False, "reason": "insufficient_balance", "balance_before": float(_visible_dcoin_balance_tx(cur, int(sender_id)))}

            now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            _spend_visible_dcoins_tx(cur, int(sender_id), amount_value, now)
            _add_visible_dcoins_only_tx(cur, int(recipient_id), amount_value, now)
            subject_label = str(subject or "GLOBAL").strip() or "GLOBAL"
            cur.execute(
                "INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type) VALUES (?, ?, ?, ?, ?, ?)",
                (int(sender_id), -float(amount_value), 0.0, subject_label, now, "transfer_out"),
            )
            cur.execute(
                "INSERT INTO diamond_history (user_id, dcoin_change, dpoints_change, subject, created_at, change_type) VALUES (?, ?, ?, ?, ?, ?)",
                (int(recipient_id), float(amount_value), 0.0, subject_label, now, "transfer_in"),
            )
            sender_after = float(_visible_dcoin_balance_tx(cur, int(sender_id)))
            recipient_after = float(_visible_dcoin_balance_tx(cur, int(recipient_id)))
            conn.commit()
            return {
                "ok": True,
                "sender_balance_after": sender_after,
                "recipient_balance_after": recipient_after,
            }
        finally:
            conn.close()

def ensure_homework_schema():
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            _ensure_table_columns(
                cur,
                "web_homeworks",
                [
                    ("description", "TEXT"),
                    ("group_id", "INTEGER"),
                    ("target_type", "TEXT"),
                    ("homework_kind", "TEXT"),
                    ("due_at", "TIMESTAMP"),
                    ("image_url", "TEXT"),
                    ("dcoin_effect", "REAL DEFAULT 0"),
                    ("status", "TEXT DEFAULT 'active'"),
                    ("requires_voice_message", "BOOLEAN DEFAULT FALSE"),
                    ("requires_file", "BOOLEAN DEFAULT FALSE"),
                    ("requires_essay", "BOOLEAN DEFAULT FALSE"),
                    ("is_voiceroom", "BOOLEAN DEFAULT FALSE"),
                ],
            )
            conn.commit()
        finally:
            conn.close()


def create_homework(
    *,
    teacher_id: int,
    student_id: int | None = None,
    title: str,
    description: str | None = None,
    due_at: str | None = None,
    image_url: str | None = None,
    dcoin_effect: float = 0.0,
    group_id: int | None = None,
    homework_kind: str = "both",
    requires_voice_message: bool = False,
    requires_file: bool = False,
    requires_essay: bool = False,
    is_voiceroom: bool = False,
    voiceroom_groups: list[dict] | None = None,
) -> dict | None:
    ensure_homework_schema()
    normalized_kind = str(homework_kind or "both").strip().lower()
    if normalized_kind not in {"list", "test", "both"}:
        normalized_kind = "both"
    conn = get_conn()
    cur = conn.cursor()
    homework_id = 0
    try:
        cur.execute(
            """
            INSERT INTO web_homeworks(
                teacher_id, student_id, group_id, target_type, homework_kind, title, description, due_at, image_url, dcoin_effect, requires_voice_message, requires_file, requires_essay, is_voiceroom, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                int(teacher_id),
                int(student_id or 0),
                int(group_id) if group_id else None,
                "group" if group_id else "student",
                normalized_kind,
                str(title or "").strip(),
                description,
                due_at,
                image_url,
                float(dcoin_effect or 0),
                bool(requires_voice_message),
                bool(requires_file),
                bool(requires_essay),
                bool(is_voiceroom),
            ),
        )
        homework_id = int(getattr(cur, "lastrowid", 0) or 0)
        if homework_id <= 0 and _is_postgres_enabled():
            cur.execute("SELECT id FROM web_homeworks ORDER BY id DESC LIMIT 1")
            row = _row_to_dict(cur.fetchone())
            homework_id = int(row.get("id") or 0)
            
        if is_voiceroom and voiceroom_groups and homework_id > 0:
            import uuid
            for vg in voiceroom_groups:
                s1 = int(vg.get("student1_id") or 0)
                s2 = int(vg.get("student2_id") or 0) or None
                s3 = int(vg.get("student3_id") or 0) or None
                room_id = str(uuid.uuid4())
                if s1 > 0:
                    cur.execute(
                        """
                        INSERT INTO web_homework_voiceroom_groups(
                            homework_id, student1_id, student2_id, student3_id, room_id, status
                        ) VALUES (?, ?, ?, ?, ?, 'pending')
                        """,
                        (homework_id, s1, s2, s3, room_id)
                    )

        conn.commit()
    finally:
        conn.close()
    return get_homework(homework_id) if homework_id > 0 else None


def get_homework(homework_id: int) -> dict | None:
    ensure_homework_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM web_homeworks WHERE id=? LIMIT 1", (int(homework_id),))
        row = _row_to_dict(cur.fetchone())
        if row and int(row.get("is_voiceroom") or 0) == 1:
            cur.execute("""
                SELECT v.*,
                       u1.first_name AS student1_name,
                       u2.first_name AS student2_name,
                       u3.first_name AS student3_name
                FROM web_homework_voiceroom_groups v
                LEFT JOIN users u1 ON u1.id=v.student1_id
                LEFT JOIN users u2 ON u2.id=v.student2_id
                LEFT JOIN users u3 ON u3.id=v.student3_id
                WHERE v.homework_id=?
            """, (int(homework_id),))
            row["voiceroom_groups"] = [_row_to_dict(r) for r in cur.fetchall()]
        return row or None
    finally:
        conn.close()


def _homework_visible_window_sql(alias: str = "h") -> str:
    """Homework remains visible until 48 hours after its deadline."""
    prefix = f"{alias}." if alias else ""
    if _is_postgres_enabled():
        return (
            f"AND ({prefix}due_at IS NULL "
            f"OR TRIM(CAST({prefix}due_at AS TEXT))='' "
            f"OR {prefix}due_at >= (CURRENT_TIMESTAMP - INTERVAL '1 month'))"
        )
    return (
        f"AND ({prefix}due_at IS NULL "
        f"OR TRIM(CAST({prefix}due_at AS TEXT))='' "
        f"OR datetime(REPLACE(CAST({prefix}due_at AS TEXT),'T',' ')) >= datetime('now','-1 month'))"
    )


def update_homework(
    homework_id: int,
    *,
    title: str,
    description: str | None = None,
    due_at: str | None = None,
    image_url: str | None = None,
    dcoin_effect: float = 0.0,
    homework_kind: str = "both",
    requires_voice_message: bool = False,
    requires_file: bool = False,
) -> dict | None:
    ensure_homework_schema()
    normalized_kind = str(homework_kind or "both").strip().lower()
    if normalized_kind not in {"list", "test", "both"}:
        normalized_kind = "both"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE web_homeworks
            SET homework_kind=?,
                title=?,
                description=?,
                due_at=?,
                image_url=?,
                dcoin_effect=?,
                requires_voice_message=?,
                requires_file=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                normalized_kind,
                str(title or "").strip(),
                description,
                due_at,
                image_url,
                float(dcoin_effect or 0),
                bool(requires_voice_message),
                bool(requires_file),
                int(homework_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_homework(int(homework_id))


def list_homeworks_for_student(student_id: int) -> list[dict]:
    ensure_homework_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT h.*,
                   s.status AS submission_status,
                   s.note AS submission_note,
                   s.proof_image_url,
                   s.proof_images_json,
                   s.voice_message_url,
                   s.created_at AS submission_created_at,
                   s.updated_at AS submission_updated_at,
                   s.dcoin_delta,
                   COALESCE(s.dpoints_delta, s.dcoin_delta, 0) AS dpoints_delta,
                   s.review_note,
                   s.reviewed_by,
                   s.reviewed_at,
                   t.first_name AS teacher_first_name,
                   t.last_name AS teacher_last_name,
                   g.name AS group_name,
                   g.subject AS group_subject
            FROM web_homeworks h
            LEFT JOIN web_homework_submissions s ON s.homework_id=h.id AND s.student_id=?
            LEFT JOIN users t ON t.id=h.teacher_id
            LEFT JOIN groups g ON g.id=h.group_id
            WHERE COALESCE(h.status,'active')='active'
              {_homework_visible_window_sql('h')}
              AND (
                h.student_id=?
                OR (
                    h.group_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1
                        FROM user_groups ug
                        WHERE ug.user_id=? AND ug.group_id=h.group_id
                          -- Guruhga KEYIN qo'shilgan o'quvchi qo'shilishidan OLDIN
                          -- berilgan homeworklarni ko'rmaydi.
                          AND (
                            ug.joined_date IS NULL
                            OR h.created_at IS NULL
                            OR ug.joined_date <= h.created_at
                          )
                    )
                )
              )
            ORDER BY COALESCE(h.due_at, '9999-12-31T23:59:59') ASC, h.id DESC
            """,
            (int(student_id), int(student_id), int(student_id)),
        )
        rows = [_row_to_dict(r) for r in (cur.fetchall() or [])]
        for row in rows:
            if int(row.get("is_voiceroom") or 0) == 1:
                cur.execute(
                    """
                    SELECT v.*,
                           u1.first_name AS student1_name,
                           u2.first_name AS student2_name,
                           u3.first_name AS student3_name
                    FROM web_homework_voiceroom_groups v
                    LEFT JOIN users u1 ON u1.id=v.student1_id
                    LEFT JOIN users u2 ON u2.id=v.student2_id
                    LEFT JOIN users u3 ON u3.id=v.student3_id
                    WHERE v.homework_id=? AND (v.student1_id=? OR v.student2_id=? OR v.student3_id=?)
                    LIMIT 1
                    """,
                    (int(row["id"]), int(student_id), int(student_id), int(student_id))
                )
                vr_row = _row_to_dict(cur.fetchone())
                if vr_row:
                    row["voiceroom_group"] = vr_row
        return rows
    finally:
        conn.close()


def list_homeworks_for_teacher(teacher_id: int) -> list[dict]:
    ensure_homework_schema()
    temp_group_rows = get_groups_with_temporary_access_for_teacher(int(teacher_id))
    temp_group_ids = sorted({
        int(row.get("id") or row.get("group_id") or 0)
        for row in (temp_group_rows or [])
        if int(row.get("id") or row.get("group_id") or 0) > 0
    })
    access_sql = "h.teacher_id=?"
    params: list[Any] = [int(teacher_id)]
    if temp_group_ids:
        placeholders = ",".join("?" for _ in temp_group_ids)
        access_sql = f"({access_sql} OR h.group_id IN ({placeholders}))"
        params.extend(temp_group_ids)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            SELECT
                   h.id, h.teacher_id, h.group_id, h.target_type, h.homework_kind, h.title, h.description,
                   h.due_at, h.image_url, h.dcoin_effect, h.status, h.created_at, h.updated_at, h.is_voiceroom,
                   h.student_id AS homework_student_id,
                   COALESCE(NULLIF(h.student_id, 0), u.id) AS student_id,
                   s.student_id AS submission_student_id,
                   s.status AS submission_status,
                   s.note AS submission_note,
                   s.proof_image_url,
                   s.proof_images_json,
                   s.voice_message_url,
                   s.created_at AS submission_created_at,
                   s.updated_at AS submission_updated_at,
                   s.dcoin_delta,
                   COALESCE(s.dpoints_delta, s.dcoin_delta, 0) AS dpoints_delta,
                   s.review_note,
                   s.reviewed_by,
                   s.reviewed_at,
                   s.ai_transcript,
                   s.ai_feedback,
                   s.ai_analyzed_at,
                   COALESCE(u.first_name, direct_u.first_name) AS student_first_name,
                   COALESCE(u.last_name, direct_u.last_name) AS student_last_name,
                   COALESCE(u.profile_image_url, direct_u.profile_image_url) AS student_profile_image_url,
                   g.name AS group_name,
                   g.subject AS group_subject
            FROM web_homeworks h
            LEFT JOIN groups g ON g.id=h.group_id
            LEFT JOIN user_groups ug
              ON h.group_id IS NOT NULL
             AND ug.group_id=h.group_id
             AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT))='')
             -- Guruhga keyin qo'shilgan o'quvchi eski homeworklar uchun
             -- ko'rsatilmaydi (student tomonida ham ko'rinmaydi).
             AND (
                ug.joined_date IS NULL
                OR h.created_at IS NULL
                OR ug.joined_date <= h.created_at
             )
            LEFT JOIN users u
              ON u.id=ug.user_id
             AND COALESCE(u.login_type, 0) IN (1, 2, 6)
            LEFT JOIN users direct_u
              ON direct_u.id=NULLIF(h.student_id, 0)
            LEFT JOIN web_homework_submissions s
              ON s.homework_id=h.id
             AND s.student_id=COALESCE(NULLIF(h.student_id, 0), u.id)
            WHERE {access_sql}
              AND COALESCE(h.status,'active')='active'
              AND (
                NULLIF(h.student_id, 0) IS NOT NULL
                OR u.id IS NOT NULL
              )
            ORDER BY h.id DESC, COALESCE(s.updated_at, h.created_at) DESC, student_first_name ASC
            """,
            tuple(params),
        )
        rows = [_row_to_dict(r) for r in (cur.fetchall() or [])]
        for row in rows:
            if int(row.get("is_voiceroom") or 0) == 1:
                student_id = int(row.get("student_id") or 0)
                cur.execute(
                    """
                    SELECT v.*,
                           u1.first_name AS student1_name,
                           u2.first_name AS student2_name,
                           u3.first_name AS student3_name
                    FROM web_homework_voiceroom_groups v
                    LEFT JOIN users u1 ON u1.id=v.student1_id
                    LEFT JOIN users u2 ON u2.id=v.student2_id
                    LEFT JOIN users u3 ON u3.id=v.student3_id
                    WHERE v.homework_id=? AND (v.student1_id=? OR v.student2_id=? OR v.student3_id=?)
                    LIMIT 1
                    """,
                    (int(row["id"]), student_id, student_id, student_id)
                )
                vr_row = _row_to_dict(cur.fetchone())
                if vr_row:
                    row["voiceroom_group"] = vr_row
        return rows
    finally:
        conn.close()


def upsert_homework_submission(
    homework_id: int,
    student_id: int,
    status: str,
    note: str | None = None,
    proof_image_url: str | None = None,
    proof_images_json: str | None = None,
    voice_message_url: str | None = None,
) -> dict | None:
    ensure_homework_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM web_homework_submissions WHERE homework_id=? AND student_id=? LIMIT 1",
            (int(homework_id), int(student_id)),
        )
        existing = _row_to_dict(cur.fetchone())
        if existing:
            cur.execute(
                """
                UPDATE web_homework_submissions 
                SET status=?, note=?, proof_image_url=?, proof_images_json=?, voice_message_url=?, updated_at=CURRENT_TIMESTAMP
                WHERE homework_id=? AND student_id=?
                """,
                (
                    str(status or existing.get("status") or "pending").strip().lower(),
                    note if note is not None else existing.get("note"),
                    proof_image_url if proof_image_url is not None else existing.get("proof_image_url"),
                    proof_images_json if proof_images_json is not None else existing.get("proof_images_json"),
                    voice_message_url if voice_message_url is not None else existing.get("voice_message_url"),
                    int(homework_id),
                    int(student_id),
                )
            )
            conn.commit()
            return existing
        cur.execute(
            """
            INSERT INTO web_homework_submissions(
                homework_id, student_id, status, note, proof_image_url, proof_images_json, voice_message_url, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(homework_id, student_id) DO NOTHING
            """,
            (
                int(homework_id),
                int(student_id),
                str(status or "pending").strip().lower(),
                note,
                proof_image_url,
                proof_images_json,
                voice_message_url,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_homework_submission(int(homework_id), int(student_id))


def get_homework_submission(homework_id: int, student_id: int) -> dict | None:
    ensure_homework_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM web_homework_submissions WHERE homework_id=? AND student_id=? LIMIT 1",
            (int(homework_id), int(student_id)),
        )
        row = _row_to_dict(cur.fetchone())
        return row or None
    finally:
        conn.close()


def record_homework_deadline_penalty(homework_id: int, student_id: int, penalty_dpoints: float) -> dict | None:
    """Create a one-time not-submitted homework penalty marker and submission row.

    The penalty row is the idempotency guard; the actual D'point wallet delta is
    applied by the API layer only when this function returns a newly inserted row.
    """
    penalty = float(penalty_dpoints or 0)
    if penalty == 0:
        return None
    ensure_homework_schema()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT * FROM web_homework_deadline_penalties WHERE homework_id=? AND student_id=? LIMIT 1",
                (int(homework_id), int(student_id)),
            )
            existing_penalty = _row_to_dict(cur.fetchone())
            if existing_penalty:
                return None
            cur.execute(
                "SELECT * FROM web_homework_submissions WHERE homework_id=? AND student_id=? LIMIT 1",
                (int(homework_id), int(student_id)),
            )
            existing_submission = _row_to_dict(cur.fetchone())
            if existing_submission:
                return None
            cur.execute(
                """
                INSERT INTO web_homework_deadline_penalties(homework_id, student_id, penalty_dpoints, applied_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(homework_id, student_id) DO NOTHING
                """,
                (int(homework_id), int(student_id), penalty),
            )
            if int(getattr(cur, "rowcount", 0) or 0) <= 0:
                conn.rollback()
                return None
            cur.execute(
                "SELECT * FROM web_homework_deadline_penalties WHERE homework_id=? AND student_id=? LIMIT 1",
                (int(homework_id), int(student_id)),
            )
            inserted = _row_to_dict(cur.fetchone())
            if not inserted:
                conn.rollback()
                return None
            cur.execute(
                """
                INSERT INTO web_homework_submissions(
                    homework_id, student_id, status, note, dcoin_delta, dpoints_delta,
                    review_note, reviewed_by, reviewed_at, updated_at
                )
                VALUES (?, ?, 'not_done', NULL, ?, ?, 'Deadline missed', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(homework_id, student_id) DO NOTHING
                """,
                (int(homework_id), int(student_id), penalty, penalty),
            )
            conn.commit()
            return inserted
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()


def review_homework_submission(
    homework_id: int,
    student_id: int,
    reviewed_by: int = 0,
    status: str = "done",
    dcoin_delta: float = 0.0,
    review_note: str | None = None,
) -> dict | None:
    ensure_homework_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE web_homework_submissions
            SET status=?,
                dcoin_delta=?,
                dpoints_delta=?,
                review_note=?,
                reviewed_by=?,
                reviewed_at=CURRENT_TIMESTAMP,
                updated_at=CURRENT_TIMESTAMP
            WHERE homework_id=? AND student_id=?
            """,
            (
                "not_done" if str(status or "").strip().lower() == "not_done" else "done",
                float(dcoin_delta or 0),
                float(dcoin_delta or 0),
                review_note,
                int(reviewed_by),
                int(homework_id),
                int(student_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_homework_submission(int(homework_id), int(student_id))

def get_student_attendance_history(user_id: int, limit_months: int = 5) -> list[dict]:
    """Studentning oxirgi bir necha oydagi davomat tarixini olish."""
    conn = get_conn()
    cur = conn.cursor()
    
    from datetime import datetime, timedelta
    from dateutil.relativedelta import relativedelta
    
    # Bugungi sana
    today = datetime.now()
    
    # 5 oy oldingi sananing boshlanishi
    start_date = (today - relativedelta(months=limit_months)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    cur.execute('''
        SELECT a.id, a.user_id, a.group_id, a.date, a.status, a.created_at, g.name as group_name
        FROM attendance a
        LEFT JOIN groups g ON a.group_id = g.id
        WHERE a.user_id = ? AND a.date >= ?
        ORDER BY a.date DESC
    ''', (user_id, start_date.strftime('%Y-%m-%d %H:%M:%S')))
    
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def list_homeworks_for_admin(teacher_id: int | None = None, group_id: int | None = None) -> list[dict]:
    ensure_homework_schema()
    conn = get_conn()
    cur = conn.cursor()
    params = []
    where_clauses = ["COALESCE(h.status,'active')='active'"]
    
    if teacher_id and teacher_id > 0:
        where_clauses.append("h.teacher_id=?")
        params.append(teacher_id)
        
    if group_id and group_id > 0:
        where_clauses.append("h.group_id=?")
        params.append(group_id)
        
    where_sql = " AND ".join(where_clauses)
    if where_sql:
        where_sql = f"WHERE {where_sql}"
        
    try:
        cur.execute(
            f"""
            SELECT h.id, h.teacher_id, h.group_id, h.target_type, h.homework_kind, h.title, h.description,
                   h.due_at, h.image_url, h.dcoin_effect, h.status, h.created_at, h.updated_at, h.is_voiceroom,
                   h.student_id AS homework_student_id,
                   t.first_name AS teacher_first_name,
                   t.last_name AS teacher_last_name,
                   g.name AS group_name,
                   g.subject AS group_subject,
                   (SELECT COUNT(*) FROM web_homework_submissions s WHERE s.homework_id=h.id) AS submission_count,
                   (SELECT COUNT(*) FROM user_groups ug WHERE ug.group_id=h.group_id AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT))='')) AS group_member_count
            FROM web_homeworks h
            LEFT JOIN users t ON t.id=h.teacher_id
            LEFT JOIN groups g ON g.id=h.group_id
            {where_sql}
            ORDER BY h.created_at DESC
            LIMIT 300
            """,
            params,
        )
        rows = [_row_to_dict(row) for row in cur.fetchall()]
        return rows
    finally:
        conn.close()

def save_diamondvoy_chat_message(user_id: int, role: str, content: str) -> None:
    if not content or not str(content).strip():
        return
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO diamondvoy_chat_history (user_id, role, content)
            VALUES (?, ?, ?)
            """,
            (int(user_id), str(role).strip(), str(content).strip()),
        )
        conn.commit()
    except Exception as e:
        logger.exception(f"Error saving diamondvoy chat message: {e}")
    finally:
        conn.close()

def get_diamondvoy_chat_history(user_id: int, limit: int = 15) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT role, content, created_at
            FROM diamondvoy_chat_history
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (int(user_id), int(limit)),
        )
        rows = [_row_to_dict(row) for row in cur.fetchall()]
        return list(reversed(rows))
    except Exception as e:
        logger.exception(f"Error getting diamondvoy chat history: {e}")
        return []
    finally:
        conn.close()

def cleanup_diamondvoy_chat_history(days: int = 7) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM diamondvoy_chat_history
            WHERE created_at < CURRENT_TIMESTAMP - CAST(? AS INTERVAL)
            """,
            (f"{int(days)} days",),
        )
        deleted = cur.rowcount
        conn.commit()
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} old diamondvoy chat messages.")
    except Exception as e:
        logger.exception(f"Error cleaning up diamondvoy chat history: {e}")
    finally:
        conn.close()

def list_student_telegram_ids_by_subject(subject: str) -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT telegram_id, COALESCE(interface_lang, 'uz') as lang
            FROM users 
            WHERE login_type IN (1, 2) 
              AND telegram_id IS NOT NULL 
              AND CAST(telegram_id AS TEXT) != ''
              AND (subject = %s OR subject LIKE %s OR subject LIKE %s OR subject LIKE %s)
            """,
            (subject, f"%{subject},%", f"%,{subject}", f"%,{subject},%")
        )
        return [dict(r) for r in cur.fetchall() or []]
    except Exception:
        return []
    finally:
        conn.close()


def ensure_telegram_group_chats_schema() -> None:
    """Ensure telegram_group_chats table exists for tracking bot group memberships."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        if _is_postgres_enabled():
            cur.execute("""
                CREATE TABLE IF NOT EXISTS telegram_group_chats (
                    chat_id BIGINT PRIMARY KEY,
                    title TEXT,
                    chat_type TEXT DEFAULT 'group',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS telegram_group_chats (
                    chat_id INTEGER PRIMARY KEY,
                    title TEXT,
                    chat_type TEXT DEFAULT 'group',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    except Exception as e:
        logger.exception(f"Error creating telegram_group_chats table: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def upsert_telegram_group_chat(chat_id: int | str, title: str | None = None, chat_type: str | None = None, is_active: int = 1) -> None:
    """Insert or update a telegram group chat record."""
    ensure_telegram_group_chats_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cid = int(chat_id)
        c_title = str(title or "").strip() or None
        c_type = str(chat_type or "group").strip()
        if _is_postgres_enabled():
            cur.execute("""
                INSERT INTO telegram_group_chats (chat_id, title, chat_type, is_active, updated_at)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = COALESCE(EXCLUDED.title, telegram_group_chats.title),
                    chat_type = EXCLUDED.chat_type,
                    is_active = EXCLUDED.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (cid, c_title, c_type, int(is_active)))
        else:
            cur.execute("""
                INSERT INTO telegram_group_chats (chat_id, title, chat_type, is_active, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = COALESCE(excluded.title, telegram_group_chats.title),
                    chat_type = excluded.chat_type,
                    is_active = excluded.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (cid, c_title, c_type, int(is_active)))
        conn.commit()
    except Exception as e:
        logger.exception(f"Error in upsert_telegram_group_chat(chat_id={chat_id}): {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def set_telegram_group_chat_active(chat_id: int | str, is_active: int = 0) -> None:
    """Set active status of a telegram group chat."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cid = int(chat_id)
        if _is_postgres_enabled():
            cur.execute("UPDATE telegram_group_chats SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE chat_id = %s", (int(is_active), cid))
        else:
            cur.execute("UPDATE telegram_group_chats SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?", (int(is_active), cid))
        conn.commit()
    except Exception as e:
        logger.exception(f"Error in set_telegram_group_chat_active(chat_id={chat_id}): {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def get_active_telegram_group_chats() -> list[dict]:
    """Get all active telegram group chats formatted as recipient dicts for broadcasts."""
    ensure_telegram_group_chats_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT chat_id, title, chat_type FROM telegram_group_chats WHERE is_active = 1")
        rows = cur.fetchall() or []
        groups = []
        for r in rows:
            d = dict(r) if isinstance(r, dict) else {"chat_id": r[0], "title": r[1], "chat_type": r[2]}
            cid = str(d["chat_id"])
            groups.append({
                "id": -abs(int(cid)),
                "telegram_id": cid,
                "login_type": 1,  # Uses student bot
                "first_name": d.get("title") or f"Group {cid}",
                "last_name": "",
                "is_group": True
            })
        return groups
    except Exception as e:
        logger.exception(f"Error fetching active telegram group chats: {e}")
        return []
    finally:
        conn.close()


# ============================================================
# TEACHER NOTES SCHEMA + CRUD
# ============================================================

def ensure_teacher_notes_schema() -> None:
    """Create teacher_student_notes table if not exists."""
    if _schema_ready("teacher_notes"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS teacher_student_notes (
                    id          BIGSERIAL PRIMARY KEY,
                    teacher_id  BIGINT NOT NULL,
                    student_id  BIGINT NOT NULL,
                    note_text   TEXT NOT NULL,
                    is_visible  BOOLEAN DEFAULT TRUE,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS teacher_student_notes (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id  INTEGER NOT NULL,
                    student_id  INTEGER NOT NULL,
                    note_text   TEXT NOT NULL,
                    is_visible  INTEGER DEFAULT 1,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tsn_student ON teacher_student_notes(student_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tsn_teacher_student ON teacher_student_notes(teacher_id, student_id)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("teacher_notes")
    finally:
        conn.close()


def get_teacher_notes(teacher_id: int, student_id: int) -> list[dict]:
    ensure_teacher_notes_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM teacher_student_notes WHERE teacher_id=? AND student_id=? ORDER BY id DESC",
            (int(teacher_id), int(student_id)),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def get_student_visible_notes(student_id: int) -> list[dict]:
    """Notes visible to the student (from any teacher, is_visible=1)."""
    ensure_teacher_notes_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT n.*, u.first_name AS teacher_first_name, u.last_name AS teacher_last_name,
                   u.profile_image_url AS teacher_avatar
            FROM teacher_student_notes n
            LEFT JOIN users u ON u.id = n.teacher_id
            WHERE n.student_id=? AND n.is_visible=TRUE
            ORDER BY n.id DESC
            LIMIT 50
            """,
            (int(student_id),),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def create_teacher_note(teacher_id: int, student_id: int, note_text: str, is_visible: bool = True) -> dict | None:
    ensure_teacher_notes_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO teacher_student_notes(teacher_id, student_id, note_text, is_visible) VALUES (?, ?, ?, ?)",
            (int(teacher_id), int(student_id), str(note_text).strip(), bool(is_visible)),
        )
        note_id = int(getattr(cur, "lastrowid", 0) or 0)
        if note_id <= 0 and _is_postgres_enabled():
            cur.execute("SELECT id FROM teacher_student_notes ORDER BY id DESC LIMIT 1")
            row = _row_to_dict(cur.fetchone())
            note_id = int(row.get("id") or 0)
        conn.commit()
    finally:
        conn.close()
    if note_id <= 0:
        return None
    notes = get_teacher_notes(int(teacher_id), int(student_id))
    return next((n for n in notes if int(n.get("id") or 0) == note_id), None)


def update_teacher_note(note_id: int, teacher_id: int, *, note_text: str | None = None, is_visible: bool | None = None) -> bool:
    ensure_teacher_notes_schema()
    updates = ["updated_at=CURRENT_TIMESTAMP"]
    params: list = []
    if note_text is not None:
        updates.append("note_text=?")
        params.append(str(note_text).strip())
    if is_visible is not None:
        updates.append("is_visible=?")
        params.append(bool(is_visible))
    if not params:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE teacher_student_notes SET {', '.join(updates)} WHERE id=? AND teacher_id=?",
            (*params, int(note_id), int(teacher_id)),
        )
        conn.commit()
        return bool(getattr(cur, "rowcount", 0) > 0)
    finally:
        conn.close()


def delete_teacher_note(note_id: int, teacher_id: int) -> bool:
    ensure_teacher_notes_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM teacher_student_notes WHERE id=? AND teacher_id=?",
            (int(note_id), int(teacher_id)),
        )
        conn.commit()
        return bool(getattr(cur, "rowcount", 0) > 0)
    finally:
        conn.close()


# ============================================================
# TEACHER MATERIALS SCHEMA + CRUD
# ============================================================

def ensure_teacher_materials_schema() -> None:
    """Create teacher_materials table if not exists."""
    if _schema_ready("teacher_materials"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS teacher_materials (
                    id             BIGSERIAL PRIMARY KEY,
                    teacher_id     BIGINT NOT NULL,
                    title          TEXT NOT NULL,
                    description    TEXT,
                    file_url       TEXT NOT NULL,
                    file_type      TEXT DEFAULT 'other',
                    file_size      BIGINT DEFAULT 0,
                    subject        TEXT,
                    is_public      BOOLEAN DEFAULT FALSE,
                    download_count INTEGER DEFAULT 0,
                    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS teacher_materials (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id     INTEGER NOT NULL,
                    title          TEXT NOT NULL,
                    description    TEXT,
                    file_url       TEXT NOT NULL,
                    file_type      TEXT DEFAULT 'other',
                    file_size      INTEGER DEFAULT 0,
                    subject        TEXT,
                    is_public      INTEGER DEFAULT 0,
                    download_count INTEGER DEFAULT 0,
                    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tm_teacher ON teacher_materials(teacher_id)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tm_subject ON teacher_materials(subject)")
        except Exception:
            pass
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tm_public ON teacher_materials(is_public)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("teacher_materials")
    finally:
        conn.close()


def list_teacher_materials(
    teacher_id: int | None = None,
    *,
    subject: str | None = None,
    my_only: bool = False,
    limit: int = 80,
    offset: int = 0,
) -> list[dict]:
    ensure_teacher_materials_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        where = []
        params: list = []
        if my_only and teacher_id:
            where.append("m.teacher_id=?")
            params.append(int(teacher_id))
        else:
            # Show own + public
            if teacher_id:
                where.append("(m.is_public=TRUE OR m.teacher_id=?)")
                params.append(int(teacher_id))
            else:
                where.append("m.is_public=TRUE")
        if subject:
            where.append("LOWER(m.subject)=LOWER(?)")
            params.append(str(subject).strip())
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        cur.execute(
            f"""
            SELECT m.*,
                   u.first_name AS teacher_first_name, u.last_name AS teacher_last_name,
                   u.profile_image_url AS teacher_avatar
            FROM teacher_materials m
            LEFT JOIN users u ON u.id = m.teacher_id
            {where_sql}
            ORDER BY m.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, int(limit), int(offset)),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def get_teacher_material(material_id: int) -> dict | None:
    ensure_teacher_materials_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT m.*, u.first_name AS teacher_first_name, u.last_name AS teacher_last_name
            FROM teacher_materials m
            LEFT JOIN users u ON u.id = m.teacher_id
            WHERE m.id=? LIMIT 1
            """,
            (int(material_id),),
        )
        return _row_to_dict(cur.fetchone()) or None
    finally:
        conn.close()


def create_teacher_material(
    teacher_id: int,
    title: str,
    file_url: str,
    *,
    description: str | None = None,
    file_type: str = "other",
    file_size: int = 0,
    subject: str | None = None,
    is_public: bool = True,
) -> dict | None:
    ensure_teacher_materials_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO teacher_materials(teacher_id, title, description, file_url, file_type, file_size, subject, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(teacher_id),
                str(title).strip(),
                str(description or "").strip() or None,
                str(file_url).strip(),
                str(file_type or "other").strip(),
                int(file_size or 0),
                str(subject or "").strip() or None,
                True,
            ),
        )
        mat_id = int(getattr(cur, "lastrowid", 0) or 0)
        if mat_id <= 0 and _is_postgres_enabled():
            cur.execute("SELECT id FROM teacher_materials ORDER BY id DESC LIMIT 1")
            row = _row_to_dict(cur.fetchone())
            mat_id = int(row.get("id") or 0)
        conn.commit()
    finally:
        conn.close()
    return get_teacher_material(mat_id) if mat_id > 0 else None


def update_teacher_material(
    material_id: int,
    teacher_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    subject: str | None = None,
    is_public: bool | None = None,
) -> bool:
    ensure_teacher_materials_schema()
    updates = ["updated_at=CURRENT_TIMESTAMP"]
    params: list = []
    if title is not None:
        updates.append("title=?")
        params.append(str(title).strip())
    if description is not None:
        updates.append("description=?")
        params.append(str(description).strip() or None)
    if subject is not None:
        updates.append("subject=?")
        params.append(str(subject).strip() or None)
    if is_public is not None:
        updates.append("is_public=?")
        params.append(bool(is_public))
    if not params:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE teacher_materials SET {', '.join(updates)} WHERE id=? AND teacher_id=?",
            (*params, int(material_id), int(teacher_id)),
        )
        conn.commit()
        return bool(getattr(cur, "rowcount", 0) > 0)
    finally:
        conn.close()


def delete_teacher_material(material_id: int, teacher_id: int) -> bool:
    ensure_teacher_materials_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM teacher_materials WHERE id=? AND teacher_id=?",
            (int(material_id), int(teacher_id)),
        )
        conn.commit()
        return bool(getattr(cur, "rowcount", 0) > 0)
    finally:
        conn.close()


def increment_material_download(material_id: int) -> None:
    ensure_teacher_materials_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE teacher_materials SET download_count=COALESCE(download_count,0)+1 WHERE id=?",
            (int(material_id),),
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ============================================================
# TEACHER KPI SCHEMA + CRUD
# ============================================================

def ensure_teacher_kpi_schema() -> None:
    """Create teacher_kpi_cache table if not exists."""
    if _schema_ready("teacher_kpi"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS teacher_kpi_cache (
                    id                    BIGSERIAL PRIMARY KEY,
                    teacher_id            BIGINT NOT NULL UNIQUE,
                    attendance_rate       DOUBLE PRECISION DEFAULT 0,
                    homework_review_rate  DOUBLE PRECISION DEFAULT 0,
                    avg_student_score     DOUBLE PRECISION DEFAULT 0,
                    response_speed_score  DOUBLE PRECISION DEFAULT 0,
                    group_completion_rate DOUBLE PRECISION DEFAULT 0,
                    kpi_score             DOUBLE PRECISION DEFAULT 0,
                    total_students        INTEGER DEFAULT 0,
                    groups_count          INTEGER DEFAULT 0,
                    total_homeworks       INTEGER DEFAULT 0,
                    reviewed_homeworks    INTEGER DEFAULT 0,
                    computed_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS teacher_kpi_cache (
                    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_id            INTEGER NOT NULL UNIQUE,
                    attendance_rate       REAL DEFAULT 0,
                    homework_review_rate  REAL DEFAULT 0,
                    avg_student_score     REAL DEFAULT 0,
                    response_speed_score  REAL DEFAULT 0,
                    group_completion_rate REAL DEFAULT 0,
                    kpi_score             REAL DEFAULT 0,
                    total_students        INTEGER DEFAULT 0,
                    groups_count          INTEGER DEFAULT 0,
                    total_homeworks       INTEGER DEFAULT 0,
                    reviewed_homeworks    INTEGER DEFAULT 0,
                    computed_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tkpi_score ON teacher_kpi_cache(kpi_score DESC)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("teacher_kpi")
    finally:
        conn.close()


def upsert_teacher_kpi(
    teacher_id: int,
    *,
    attendance_rate: float = 0.0,
    homework_review_rate: float = 0.0,
    avg_student_score: float = 0.0,
    response_speed_score: float = 0.0,
    group_completion_rate: float = 0.0,
    kpi_score: float = 0.0,
    total_students: int = 0,
    groups_count: int = 0,
    total_homeworks: int = 0,
    reviewed_homeworks: int = 0,
) -> dict | None:
    ensure_teacher_kpi_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO teacher_kpi_cache(
                teacher_id, attendance_rate, homework_review_rate,
                avg_student_score, response_speed_score, group_completion_rate,
                kpi_score, total_students, groups_count, total_homeworks,
                reviewed_homeworks, computed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(teacher_id) DO UPDATE SET
                attendance_rate=EXCLUDED.attendance_rate,
                homework_review_rate=EXCLUDED.homework_review_rate,
                avg_student_score=EXCLUDED.avg_student_score,
                response_speed_score=EXCLUDED.response_speed_score,
                group_completion_rate=EXCLUDED.group_completion_rate,
                kpi_score=EXCLUDED.kpi_score,
                total_students=EXCLUDED.total_students,
                groups_count=EXCLUDED.groups_count,
                total_homeworks=EXCLUDED.total_homeworks,
                reviewed_homeworks=EXCLUDED.reviewed_homeworks,
                computed_at=CURRENT_TIMESTAMP
            """,
            (
                int(teacher_id),
                round(float(attendance_rate), 4),
                round(float(homework_review_rate), 4),
                round(float(avg_student_score), 4),
                round(float(response_speed_score), 4),
                round(float(group_completion_rate), 4),
                round(float(kpi_score), 2),
                int(total_students),
                int(groups_count),
                int(total_homeworks),
                int(reviewed_homeworks),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_teacher_kpi(int(teacher_id))


def get_teacher_kpi(teacher_id: int) -> dict | None:
    ensure_teacher_kpi_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM teacher_kpi_cache WHERE teacher_id=? LIMIT 1",
            (int(teacher_id),),
        )
        return _row_to_dict(cur.fetchone()) or None
    finally:
        conn.close()


def get_teacher_kpi_leaderboard(limit: int = 50) -> list[dict]:
    ensure_teacher_kpi_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT k.*, u.first_name, u.last_name, u.profile_image_url,
                   ROW_NUMBER() OVER (ORDER BY k.kpi_score DESC) AS rank_pos
            FROM teacher_kpi_cache k
            LEFT JOIN users u ON u.id = k.teacher_id
            ORDER BY k.kpi_score DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    except Exception:
        # Fallback without window function for older SQLite
        conn2 = get_conn()
        cur2 = conn2.cursor()
        try:
            cur2.execute(
                """
                SELECT k.*, u.first_name, u.last_name, u.profile_image_url
                FROM teacher_kpi_cache k
                LEFT JOIN users u ON u.id = k.teacher_id
                ORDER BY k.kpi_score DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = [_row_to_dict(r) for r in (cur2.fetchall() or [])]
            for i, row in enumerate(rows):
                row["rank_pos"] = i + 1
            return rows
        finally:
            conn2.close()
    finally:
        conn.close()


# ============================================================
# HOMEWORK SUBMISSIONS: AI fields helper
# ============================================================

def update_homework_submission_ai(
    homework_id: int,
    student_id: int,
    *,
    ai_transcript: str | None = None,
    ai_feedback: str | None = None,
    analysis_kind: str | None = None,
) -> bool:
    """Save an AI result without losing a previous speaking, image, or note result."""
    # Ensure columns exist (lazy migration)
    ensure_homework_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        # Add columns if they don't exist yet (safe ALTER)
        for col, col_type in [("ai_transcript", "TEXT"), ("ai_feedback", "TEXT"), ("ai_analyzed_at", "TIMESTAMP")]:
            try:
                cur.execute(f"ALTER TABLE web_homework_submissions ADD COLUMN {col} {col_type}")
            except Exception:
                pass
        feedback_to_save = str(ai_feedback or "").strip() or None
        kind = str(analysis_kind or "").strip().lower()
        if feedback_to_save and kind in {"speaking", "writing", "note"}:
            cur.execute(
                "SELECT ai_feedback FROM web_homework_submissions WHERE homework_id=? AND student_id=? LIMIT 1",
                (int(homework_id), int(student_id)),
            )
            existing = _row_to_dict(cur.fetchone()) or {}
            bundle: dict[str, Any] = {"version": 2}
            raw_existing = str(existing.get("ai_feedback") or "").strip()
            if raw_existing:
                try:
                    parsed = json.loads(raw_existing)
                    if isinstance(parsed, dict):
                        if "speaking" in parsed or "writing" in parsed or "note" in parsed:
                            bundle.update(parsed)
                        elif "transcript" in parsed:
                            bundle["speaking"] = parsed
                        else:
                            bundle["writing"] = parsed
                except Exception:
                    pass
            try:
                parsed_new = json.loads(feedback_to_save)
                bundle[kind] = parsed_new if isinstance(parsed_new, dict) else {"overall_feedback": feedback_to_save}
            except Exception:
                bundle[kind] = {"overall_feedback": feedback_to_save}
            feedback_to_save = json.dumps(bundle, ensure_ascii=False)

        cur.execute(
            """
            UPDATE web_homework_submissions
            SET ai_transcript=COALESCE(?, ai_transcript),
                ai_feedback=COALESCE(?, ai_feedback),
                ai_analyzed_at=CURRENT_TIMESTAMP
            WHERE homework_id=? AND student_id=?
            """,
            (
                str(ai_transcript or "").strip() or None,
                feedback_to_save,
                int(homework_id),
                int(student_id),
            ),
        )
        conn.commit()
        return bool(getattr(cur, "rowcount", 0) > 0)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# TEACHER LIBRARY — cheksiz chuqurlikdagi daraxt (papka -> papka -> fayl/test)
# va o'qituvchilararo sharing (view / edit / assign)
# ═══════════════════════════════════════════════════════════════════════════

LIBRARY_KINDS = {"folder", "file", "test"}
LIBRARY_SHARE_PERMISSIONS = {"view", "edit", "assign"}


def ensure_library_schema() -> None:
    if _schema_ready("library_nodes"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS library_nodes (
                    id           BIGSERIAL PRIMARY KEY,
                    parent_id    BIGINT,
                    owner_id     BIGINT NOT NULL,
                    kind         TEXT NOT NULL DEFAULT 'folder',
                    title        TEXT NOT NULL,
                    description  TEXT,
                    subject      TEXT,
                    level        TEXT,
                    file_url     TEXT,
                    payload_json TEXT,
                    is_public    BOOLEAN DEFAULT FALSE,
                    sort_order   INTEGER DEFAULT 0,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS library_nodes (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    parent_id    INTEGER,
                    owner_id     INTEGER NOT NULL,
                    kind         TEXT NOT NULL DEFAULT 'folder',
                    title        TEXT NOT NULL,
                    description  TEXT,
                    subject      TEXT,
                    level        TEXT,
                    file_url     TEXT,
                    payload_json TEXT,
                    is_public    INTEGER DEFAULT 0,
                    sort_order   INTEGER DEFAULT 0,
                    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        for ddl in (
            "CREATE INDEX IF NOT EXISTS idx_lnodes_owner ON library_nodes(owner_id)",
            "CREATE INDEX IF NOT EXISTS idx_lnodes_parent ON library_nodes(parent_id)",
            "CREATE INDEX IF NOT EXISTS idx_lnodes_public ON library_nodes(is_public)",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS library_shares (
                    id         BIGSERIAL PRIMARY KEY,
                    node_id    BIGINT NOT NULL,
                    teacher_id BIGINT NOT NULL,
                    permission TEXT NOT NULL DEFAULT 'view',
                    shared_by  BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(node_id, teacher_id)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS library_shares (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id    INTEGER NOT NULL,
                    teacher_id INTEGER NOT NULL,
                    permission TEXT NOT NULL DEFAULT 'view',
                    shared_by  INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(node_id, teacher_id)
                )
                """,
            ],
        )
        for ddl in (
            "CREATE INDEX IF NOT EXISTS idx_lshares_node ON library_shares(node_id)",
            "CREATE INDEX IF NOT EXISTS idx_lshares_teacher ON library_shares(teacher_id)",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
        conn.commit()
        _mark_schema_ready("library_nodes")
    finally:
        conn.close()


def _library_subtree_ids(cur, root_id: int) -> set[int]:
    """Berilgan tugun va uning barcha avlodlarini BFS bilan yig'adi."""
    ids: set[int] = set()
    frontier = [int(root_id)]
    while frontier:
        ids.update(frontier)
        placeholders = ",".join(["?"] * len(frontier))
        try:
            cur.execute(
                f"SELECT id FROM library_nodes WHERE parent_id IN ({placeholders})",
                tuple(frontier),
            )
        except Exception:
            break
        frontier = [int(r["id"]) for r in (cur.fetchall() or []) if r and r.get("id") is not None]
        frontier = [i for i in frontier if i not in ids]
    return ids


def _library_node_ancestor_ids(cur, node_id: int) -> list[int]:
    """Tugunning ota-onalar zanjirini (yuqoriga) qaytaradi, o'zini ichirmaydi."""
    chain: list[int] = []
    current = int(node_id)
    seen = {current}
    for _ in range(64):
        try:
            cur.execute("SELECT parent_id FROM library_nodes WHERE id=? LIMIT 1", (current,))
        except Exception:
            break
        row = cur.fetchone()
        parent = (row or {}).get("parent_id") if row else None
        if parent is None or parent == "":
            break
        parent = int(parent)
        if parent in seen:
            break
        chain.append(parent)
        seen.add(parent)
        current = parent
    return chain


def library_permission_for(cur_or_conn, teacher_id: int, node: dict) -> str | None:
    """'owner' | 'edit' | 'assign' | 'view' | None. Share parentdan meros olinadi."""
    if int(node.get("owner_id") or 0) == int(teacher_id):
        return "owner"
    own_cur = None
    conn = None
    try:
        if hasattr(cur_or_conn, "execute") and hasattr(cur_or_conn, "fetchone") and not hasattr(cur_or_conn, "cursor"):
            cur = cur_or_conn
        else:
            conn = (cur_or_conn or get_conn())
            own_cur = cur = conn.cursor()
        node_id = int(node.get("id") or 0)
        try:
            cur.execute(
                "SELECT permission FROM library_shares WHERE node_id=? AND teacher_id=? LIMIT 1",
                (node_id, int(teacher_id)),
            )
            row = cur.fetchone()
            if row and str((row or {}).get("permission") or "").strip().lower() in LIBRARY_SHARE_PERMISSIONS:
                return str((row or {}).get("permission")).strip().lower()
        except Exception:
            pass
        for ancestor_id in _library_node_ancestor_ids(cur, node_id):
            try:
                cur.execute(
                    "SELECT permission FROM library_shares WHERE node_id=? AND teacher_id=? LIMIT 1",
                    (ancestor_id, int(teacher_id)),
                )
                row = cur.fetchone()
            except Exception:
                continue
            if row and str((row or {}).get("permission") or "").strip().lower() in LIBRARY_SHARE_PERMISSIONS:
                return str((row or {}).get("permission")).strip().lower()
        return None
    finally:
        if own_cur is not None and conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def list_library_nodes(teacher_id: int) -> dict:
    """O'qituvchi ko'radigan barcha tugunlar: o'ziniki + public + shared (subtree bilan)."""
    ensure_library_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM library_nodes ORDER BY sort_order ASC, id ASC")
        all_nodes = [_row_to_dict(r) for r in (cur.fetchall() or [])]
        cur.execute(
            "SELECT node_id, permission FROM library_shares WHERE teacher_id=?",
            (int(teacher_id),),
        )
        direct_shares = {
            int((r or {}).get("node_id") or 0): str((r or {}).get("permission") or "view").strip().lower()
            for r in (cur.fetchall() or [])
        }
        by_id = {int(n.get("id") or 0): n for n in all_nodes}
        visible: dict[int, dict] = {}
        for node in all_nodes:
            nid = int(node.get("id") or 0)
            if int(node.get("owner_id") or 0) == int(teacher_id):
                visible[nid] = {**node, "visibility": "owner", "permission": "owner"}
        for node in all_nodes:
            nid = int(node.get("id") or 0)
            if nid in visible:
                continue
            if node.get("is_public"):
                perm = library_permission_for(cur, teacher_id, node)
                visible[nid] = {**node, "visibility": "public", "permission": perm or "view"}
                # Public papka bo'lsa — ichidagi hamma narsa ham ko'rinadi (subtree).
                if str(node.get("kind") or "") == "folder":
                    for sid in _library_subtree_ids(cur, nid):
                        child = by_id.get(sid)
                        if not child or sid in visible:
                            continue
                        if int(child.get("owner_id") or 0) == int(teacher_id):
                            continue
                        visible[sid] = {**child, "visibility": "public", "permission": "view"}
        for share_node_id, perm in direct_shares.items():
            if share_node_id in visible and visible[share_node_id].get("visibility") != "public":
                continue
            for sid in _library_subtree_ids(cur, share_node_id):
                node = by_id.get(sid)
                if not node or sid in visible:
                    continue
                if int(node.get("owner_id") or 0) == int(teacher_id):
                    continue
                visible[sid] = {**node, "visibility": "shared", "permission": perm}
        cur.execute(
            """
            SELECT s.node_id, s.teacher_id, s.permission, s.shared_by,
                   u.first_name AS teacher_first_name, u.last_name AS teacher_last_name
            FROM library_shares s
            LEFT JOIN users u ON u.id = s.teacher_id
            """
        )
        share_rows = [_row_to_dict(r) for r in (cur.fetchall() or [])]
        owner_share_ids = {int(n.get("id") or 0) for n in visible.values() if n.get("visibility") == "owner"}
        for row in share_rows:
            try:
                row["node_id"] = int(row.get("node_id") or 0)
                row["teacher_id"] = int(row.get("teacher_id") or 0)
            except Exception:
                continue
        result = sorted(visible.values(), key=lambda n: (int(n.get("sort_order") or 0), int(n.get("id") or 0)))
        return {"nodes": result, "shares": share_rows, "owner_node_ids": sorted(owner_share_ids)}
    finally:
        conn.close()


def get_library_node(node_id: int) -> dict | None:
    ensure_library_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM library_nodes WHERE id=? LIMIT 1", (int(node_id),))
        return _row_to_dict(cur.fetchone()) or None
    finally:
        conn.close()


def create_library_node(
    owner_id: int,
    title: str,
    kind: str = "folder",
    *,
    parent_id: int | None = None,
    description: str | None = None,
    subject: str | None = None,
    level: str | None = None,
    file_url: str | None = None,
    payload: dict | None = None,
    is_public: bool = True,
) -> dict:
    ensure_library_schema()
    kind = str(kind or "folder").strip().lower()
    if kind not in LIBRARY_KINDS:
        raise ValueError(f"Yaroqsiz tur: {kind}")
    conn = get_conn()
    cur = conn.cursor()
    try:
        parent = None
        if parent_id:
            cur.execute("SELECT * FROM library_nodes WHERE id=? LIMIT 1", (int(parent_id),))
            parent = _row_to_dict(cur.fetchone())
            if not parent:
                raise ValueError("Ota-papka topilmadi")
        cur.execute(
            """
            INSERT INTO library_nodes
                (parent_id, owner_id, kind, title, description, subject, level, file_url, payload_json, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                int(parent_id) if parent_id else None,
                int(owner_id),
                kind,
                str(title or "").strip() or "Nomsiz",
                description or None,
                subject or None,
                level or None,
                file_url or None,
                json.dumps(payload, ensure_ascii=False) if payload else None,
                True,
            ),
        )
        row = cur.fetchone()
        new_id = int((row or {}).get("id") or 0)
        conn.commit()
        node = get_library_node(new_id) or {"id": new_id}
        node["visibility"] = "owner"
        node["permission"] = "owner"
        return node
    finally:
        conn.close()


def update_library_node(node_id: int, *, title: str | None = None, description: str | None = None,
                        subject: str | None = None, level: str | None = None, file_url: str | None = None,
                        payload: dict | None = None, is_public: bool | None = None,
                        parent_id: int | None = None, sort_order: int | None = None) -> dict | None:
    ensure_library_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM library_nodes WHERE id=? LIMIT 1", (int(node_id),))
        existing = _row_to_dict(cur.fetchone())
        if not existing:
            return None
        sets: list[str] = []
        params: list = []
        if title is not None:
            sets.append("title=?")
            params.append(str(title).strip() or existing.get("title"))
        if description is not None:
            sets.append("description=?")
            params.append(description or None)
        if subject is not None:
            sets.append("subject=?")
            params.append(subject or None)
        if level is not None:
            sets.append("level=?")
            params.append(level or None)
        if file_url is not None:
            sets.append("file_url=?")
            params.append(file_url or None)
        if payload is not None:
            sets.append("payload_json=?")
            params.append(json.dumps(payload, ensure_ascii=False))
        if is_public is not None:
            sets.append("is_public=?")
            params.append(bool(is_public))
        if sort_order is not None:
            sets.append("sort_order=?")
            params.append(int(sort_order))
        if parent_id is not None:
            new_parent = int(parent_id) if int(parent_id or 0) > 0 else None
            if new_parent:
                if int(new_parent) == int(node_id):
                    raise ValueError("Tugunni o'zining ichiga ko'chirib bo'lmaydi")
                if int(node_id) in _library_subtree_ids(cur, new_parent):
                    raise ValueError("Tsikl hosil bo'ladi")
            sets.append("parent_id=?")
            params.append(new_parent)
        if not sets:
            return existing
        sets.append("updated_at=CURRENT_TIMESTAMP")
        params.append(int(node_id))
        cur.execute(f"UPDATE library_nodes SET {', '.join(sets)} WHERE id=?", tuple(params))
        conn.commit()
        return get_library_node(int(node_id))
    finally:
        conn.close()


def delete_library_node(node_id: int) -> bool:
    """Butun subtree bilan o'chiradi (sharelar ham tozalanadi)."""
    ensure_library_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        ids = _library_subtree_ids(cur, int(node_id))
        if not ids:
            return False
        placeholders = ",".join(["?"] * len(ids))
        cur.execute(f"DELETE FROM library_shares WHERE node_id IN ({placeholders})", tuple(ids))
        cur.execute(f"DELETE FROM library_nodes WHERE id IN ({placeholders})", tuple(ids))
        conn.commit()
        return True
    finally:
        conn.close()


def share_library_node(node_id: int, teacher_id: int, permission: str, shared_by: int | None = None) -> dict:
    ensure_library_schema()
    permission = str(permission or "view").strip().lower()
    if permission not in LIBRARY_SHARE_PERMISSIONS:
        raise ValueError(f"Yaroqsiz huquq: {permission}")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO library_shares (node_id, teacher_id, permission, shared_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (node_id, teacher_id) DO UPDATE SET permission=EXCLUDED.permission, shared_by=EXCLUDED.shared_by
            """,
            (int(node_id), int(teacher_id), permission, int(shared_by) if shared_by else None),
        )
        conn.commit()
        return {"node_id": int(node_id), "teacher_id": int(teacher_id), "permission": permission}
    finally:
        conn.close()


def unshare_library_node(node_id: int, teacher_id: int) -> bool:
    ensure_library_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM library_shares WHERE node_id=? AND teacher_id=?",
            (int(node_id), int(teacher_id)),
        )
        conn.commit()
        return bool(getattr(cur, "rowcount", 0) > 0)
    finally:
        conn.close()


def list_library_share_targets(node_id: int) -> list[dict]:
    """Bir tugun uchun mavjud sharelar + share qilinadigan o'qituvchilar ro'yxati."""
    ensure_library_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT s.teacher_id, s.permission,
                   u.first_name AS teacher_first_name, u.last_name AS teacher_last_name
            FROM library_shares s
            LEFT JOIN users u ON u.id = s.teacher_id
            WHERE s.node_id=?
            """,
            (int(node_id),),
        )
        shares = [_row_to_dict(r) for r in (cur.fetchall() or [])]
        cur.execute(
            """
            SELECT id, first_name, last_name, login_id FROM users
            WHERE login_type IN (3, 4) AND id <> (SELECT owner_id FROM library_nodes WHERE id=?)
            ORDER BY first_name, last_name LIMIT 300
            """,
            (int(node_id),),
        )
        teachers = [_row_to_dict(r) for r in (cur.fetchall() or [])]
        return {"shares": shares, "teachers": teachers}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# AI TESTLAR — speak/write sentence, guided writing va kitob mashqlari uchun
# urinish sessiyalari. Faqat bitta active attempt: yangi start -> eskisi
# abandoned (testdan chiqsa boshqatdan boshlash qoidasi).
# ═══════════════════════════════════════════════════════════════════════════

AI_TEST_QUESTION_KINDS = {
    # AI tekshiradigan
    "speak_sentence", "write_sentence", "guided_writing", "translation",
    "reading_open", "read_aloud", "paraphrase", "dialogue_completion", "picture_description",
    # Avtomatik tekshiriladigan
    "listening", "dictation", "spelling", "matching", "scrambled_sentence", "gap_fill",
}

AI_TEST_AUTO_KINDS = {
    "dictation", "spelling", "matching", "scrambled_sentence", "gap_fill", "listening",
}


def ensure_ai_tests_schema() -> None:
    if _schema_ready("ai_test_attempts"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS ai_test_attempts (
                    id            BIGSERIAL PRIMARY KEY,
                    user_id       BIGINT NOT NULL,
                    source_type   TEXT NOT NULL DEFAULT 'library_test',
                    source_id     BIGINT,
                    title         TEXT,
                    questions_json TEXT,
                    status        TEXT NOT NULL DEFAULT 'active',
                    correct_count INTEGER DEFAULT 0,
                    wrong_count   INTEGER DEFAULT 0,
                    skipped_count INTEGER DEFAULT 0,
                    retry_count   INTEGER DEFAULT 0,
                    dpoints_delta DOUBLE PRECISION DEFAULT 0,
                    started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at  TIMESTAMP,
                    abandoned_at  TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS ai_test_attempts (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    source_type   TEXT NOT NULL DEFAULT 'library_test',
                    source_id     INTEGER,
                    title         TEXT,
                    questions_json TEXT,
                    status        TEXT NOT NULL DEFAULT 'active',
                    correct_count INTEGER DEFAULT 0,
                    wrong_count   INTEGER DEFAULT 0,
                    skipped_count INTEGER DEFAULT 0,
                    retry_count   INTEGER DEFAULT 0,
                    dpoints_delta DOUBLE PRECISION DEFAULT 0,
                    started_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at  TIMESTAMP,
                    abandoned_at  TIMESTAMP
                )
                """,
            ],
        )
        for ddl in (
            "CREATE INDEX IF NOT EXISTS idx_ai_attempt_user ON ai_test_attempts(user_id, status)",
            "CREATE INDEX IF NOT EXISTS idx_ai_attempt_source ON ai_test_attempts(source_type, source_id)",
            "CREATE INDEX IF NOT EXISTS idx_ai_attempt_time ON ai_test_attempts(started_at)",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS ai_test_answers (
                    id              BIGSERIAL PRIMARY KEY,
                    attempt_id      BIGINT NOT NULL,
                    question_index  INTEGER NOT NULL,
                    kind            TEXT,
                    answer_text     TEXT,
                    audio_url       TEXT,
                    verdict         TEXT,
                    ai_feedback_json TEXT,
                    try_count       INTEGER DEFAULT 1,
                    answered_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS ai_test_answers (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    attempt_id      INTEGER NOT NULL,
                    question_index  INTEGER NOT NULL,
                    kind            TEXT,
                    answer_text     TEXT,
                    audio_url       TEXT,
                    verdict         TEXT,
                    ai_feedback_json TEXT,
                    try_count       INTEGER DEFAULT 1,
                    answered_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ai_answers_attempt ON ai_test_answers(attempt_id)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("ai_test_attempts")
    finally:
        conn.close()


def abandon_active_ai_test_attempts(user_id: int) -> int:
    """Foydalanuvchining barcha active attemptlarini tashlab yuboradi (restart qoidasi)."""
    ensure_ai_tests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE ai_test_attempts
            SET status='abandoned', abandoned_at=CURRENT_TIMESTAMP
            WHERE user_id=? AND status='active'
            """,
            (int(user_id),),
        )
        conn.commit()
        return int(getattr(cur, "rowcount", 0) or 0)
    finally:
        conn.close()


def start_ai_test_attempt(user_id: int, source_type: str, source_id: int | None,
                          questions: list[dict], title: str | None = None) -> dict:
    ensure_ai_tests_schema()
    if not questions:
        raise ValueError("Savollar ro'yxati bo'sh")
    abandon_active_ai_test_attempts(int(user_id))
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO ai_test_attempts (user_id, source_type, source_id, title, questions_json)
            VALUES (?, ?, ?, ?, ?) RETURNING id
            """,
            (
                int(user_id),
                str(source_type or "library_test"),
                int(source_id) if source_id else None,
                title or None,
                json.dumps(questions, ensure_ascii=False),
            ),
        )
        row = cur.fetchone()
        new_id = int((row or {}).get("id") or 0)
        conn.commit()
        return get_ai_test_attempt(new_id) or {"id": new_id}
    finally:
        conn.close()


def get_ai_test_attempt(attempt_id: int, user_id: int | None = None) -> dict | None:
    ensure_ai_tests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM ai_test_attempts WHERE id=? LIMIT 1", (int(attempt_id),))
        row = _row_to_dict(cur.fetchone())
        if not row:
            return None
        if user_id is not None and int(row.get("user_id") or 0) != int(user_id):
            return None
        row["questions"] = _safe_json_list(row.get("questions_json"))
        cur.execute(
            "SELECT * FROM ai_test_answers WHERE attempt_id=? ORDER BY question_index ASC, id ASC",
            (int(attempt_id),),
        )
        row["answers"] = [_row_to_dict(r) for r in (cur.fetchall() or [])]
        return row
    finally:
        conn.close()


def get_active_ai_test_attempt(user_id: int) -> dict | None:
    ensure_ai_tests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM ai_test_attempts WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
            (int(user_id),),
        )
        row = cur.fetchone()
        if not row:
            return None
        return get_ai_test_attempt(int((row or {}).get("id") or 0))
    finally:
        conn.close()


def save_ai_test_answer(
    attempt_id: int,
    question_index: int,
    *,
    kind: str | None = None,
    answer_text: str | None = None,
    audio_url: str | None = None,
    verdict: str = "wrong",
    ai_feedback: dict | None = None,
) -> dict:
    ensure_ai_tests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT try_count FROM ai_test_answers
            WHERE attempt_id=? AND question_index=? AND verdict='correct'
            LIMIT 1
            """,
            (int(attempt_id), int(question_index)),
        )
        if cur.fetchone():
            raise ValueError("Bu savolga allaqachon to'g'ri javob berilgan")
        cur.execute(
            """
            SELECT id, try_count FROM ai_test_answers
            WHERE attempt_id=? AND question_index=?
            ORDER BY id DESC LIMIT 1
            """,
            (int(attempt_id), int(question_index)),
        )
        prev = _row_to_dict(cur.fetchone())
        try_count = int((prev or {}).get("try_count") or 0) + 1
        cur.execute(
            """
            INSERT INTO ai_test_answers
                (attempt_id, question_index, kind, answer_text, audio_url, verdict, ai_feedback_json, try_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(attempt_id),
                int(question_index),
                kind or None,
                answer_text or None,
                audio_url or None,
                str(verdict or "wrong"),
                json.dumps(ai_feedback, ensure_ascii=False) if ai_feedback else None,
                try_count,
            ),
        )
        conn.commit()
        return {"try_count": try_count, "verdict": verdict}
    finally:
        conn.close()


def bump_ai_test_counters(attempt_id: int, *, correct: int = 0, wrong: int = 0,
                          skipped: int = 0, retries: int = 0, dpoints: float = 0.0,
                          complete: bool = False) -> None:
    ensure_ai_tests_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE ai_test_attempts
            SET correct_count = COALESCE(correct_count,0) + ?,
                wrong_count   = COALESCE(wrong_count,0) + ?,
                skipped_count = COALESCE(skipped_count,0) + ?,
                retry_count   = COALESCE(retry_count,0) + ?,
                dpoints_delta = COALESCE(dpoints_delta,0) + ?,
                status = CASE WHEN ?=1 THEN 'completed' ELSE status END,
                completed_at = CASE WHEN ?=1 THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE id=? AND status='active'
            """,
            (
                int(correct), int(wrong), int(skipped), int(retries),
                float(dpoints), 1 if complete else 0, 1 if complete else 0,
                int(attempt_id),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_user_week_attempts(user_id: int, date_from: str, date_to: str) -> list[dict]:
    """Haftalik review uchun: content testlar + AI testlar (hafta oralig'ida)."""
    ensure_ai_tests_schema()
    out: list[dict] = []
    conn = get_conn()
    cur = conn.cursor()
    try:
        try:
            cur.execute(
                """
                SELECT id, content_type, content_id, correct_count, wrong_count,
                       skipped_count, total_questions, submitted_at
                FROM web_content_test_attempts
                WHERE user_id=? AND submitted_at >= ? AND submitted_at <= ?
                ORDER BY submitted_at DESC LIMIT 200
                """,
                (int(user_id), str(date_from), str(date_to)),
            )
            for r in (cur.fetchall() or []):
                row = _row_to_dict(r)
                row["origin"] = "content_test"
                out.append(row)
        except Exception:
            logger.exception("list_user_week_attempts content part failed")
        try:
            cur.execute(
                """
                SELECT id, source_type, source_id, title, correct_count, wrong_count,
                       skipped_count, started_at
                FROM ai_test_attempts
                WHERE user_id=? AND status='completed' AND started_at >= ? AND started_at <= ?
                ORDER BY started_at DESC LIMIT 200
                """,
                (int(user_id), str(date_from), str(date_to)),
            )
            for r in (cur.fetchall() or []):
                row = _row_to_dict(r)
                row["origin"] = "ai_test"
                out.append(row)
        except Exception:
            logger.exception("list_user_week_attempts ai part failed")
        return out
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# HAFTALIK MAJBURIY TAKRORIY TEST (Weekly Review)
# ═══════════════════════════════════════════════════════════════════════════

def ensure_weekly_reviews_schema() -> None:
    if _schema_ready("weekly_reviews"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS weekly_reviews (
                    id            BIGSERIAL PRIMARY KEY,
                    user_id       BIGINT NOT NULL,
                    week_start    TEXT NOT NULL,
                    week_end      TEXT NOT NULL,
                    homework_id   BIGINT,
                    status        TEXT NOT NULL DEFAULT 'assigned',
                    attempt_count INTEGER DEFAULT 0,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at  TIMESTAMP,
                    UNIQUE(user_id, week_start)
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS weekly_reviews (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id       INTEGER NOT NULL,
                    week_start    TEXT NOT NULL,
                    week_end      TEXT NOT NULL,
                    homework_id   INTEGER,
                    status        TEXT NOT NULL DEFAULT 'assigned',
                    attempt_count INTEGER DEFAULT 0,
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at  TIMESTAMP,
                    UNIQUE(user_id, week_start)
                )
                """,
            ],
        )
        try:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_wreviews_user ON weekly_reviews(user_id, week_start)")
        except Exception:
            pass
        conn.commit()
        _mark_schema_ready("weekly_reviews")
    finally:
        conn.close()


def upsert_weekly_review(user_id: int, week_start: str, week_end: str,
                         homework_id: int | None, attempt_count: int = 0) -> dict:
    ensure_weekly_reviews_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO weekly_reviews (user_id, week_start, week_end, homework_id, attempt_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (user_id, week_start) DO UPDATE SET
                homework_id=COALESCE(EXCLUDED.homework_id, weekly_reviews.homework_id),
                attempt_count=EXCLUDED.attempt_count
            """,
            (int(user_id), str(week_start), str(week_end),
             int(homework_id) if homework_id else None, int(attempt_count)),
        )
        conn.commit()
        cur.execute(
            "SELECT * FROM weekly_reviews WHERE user_id=? AND week_start=? LIMIT 1",
            (int(user_id), str(week_start)),
        )
        return _row_to_dict(cur.fetchone()) or {}
    finally:
        conn.close()


def get_weekly_review(user_id: int, week_start: str) -> dict | None:
    ensure_weekly_reviews_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM weekly_reviews WHERE user_id=? AND week_start=? LIMIT 1",
            (int(user_id), str(week_start)),
        )
        return _row_to_dict(cur.fetchone()) or None
    finally:
        conn.close()


def complete_weekly_review(user_id: int, week_start: str) -> bool:
    ensure_weekly_reviews_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE weekly_reviews
            SET status='completed', completed_at=CURRENT_TIMESTAMP
            WHERE user_id=? AND week_start=? AND status='assigned'
            """,
            (int(user_id), str(week_start)),
        )
        conn.commit()
        return bool(getattr(cur, "rowcount", 0) > 0)
    finally:
        conn.close()


def _safe_json_list(raw: Any) -> list:
    if not raw:
        return []
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════
# TELEGRAM USERBOT SETTINGS, LOGS & CONTACT CACHE
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_USERBOT_TEMPLATES = {
    "tpl_attendance_absent": (
        "⚠️ **DARSGA KELMADI / OTСУТСТВИЕ НА УРОКЕ**\n\n"
        "Hurmatli ota-ona!\n"
        "Farzandingiz **{student_name}** bugun (**{date}**) **{group_name}** guruhidagi darsga kelmadi.\n\n"
        "Har bir dars farzandingiz kelajagi uchun muhim qadamdir. Muqaddas darsni qoldirish kichik e'tiborsizlik bo'lmasligini va farzandingiz ta'limiga birgalikda mas'uliyat bilan yondashishimizni so'raymiz. 📖✨\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители!\n"
        "Ваш ребёнок **{student_name}** сегодня (**{date}**) не пришёл(шла) на занятие в группе **{group_name}**.\n\n"
        "Каждый урок — это важный шаг к будущему вашего ребёнка. Пропуск занятия не должен оставаться без внимания, ведь образование наших детей — это наш общий главный приоритет. 📖✨"
    ),
    "tpl_attendance_late": (
        "⏰ **DARSGA KECHIKDI / ОПОЗДАНИЕ НА УРОК**\n\n"
        "Hurmatli ota-ona!\n"
        "Farzandingiz **{student_name}** **{group_name}** darsiga biroz kechikib keldi va hozirda darsda qatnashmoqda. 📚\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители!\n"
        "Ваш ребёнок **{student_name}** немного опоздал(а) на урок группы **{group_name}** и сейчас занимается на занятии. 📚"
    ),
    "tpl_homework_missing": (
        "📝 **UYGA VAZIFA OGOHLANTIRISHI / ДОМАШНЕЕ ЗАДАНИЕ**\n\n"
        "Hurmatli ota-ona!\n"
        "Farzandingiz **{student_name}** **{group_name}** bo'yicha berilgan navbatdagi uyga vazifani o'z vaqtida bajarmadi.\n"
        "Iltimos, farzandingizning darslarga tayyorgarligini nazorat qilib berishingizni so'raymiz. 📖💡\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители!\n"
        "Ваш ребёнок **{student_name}** не выполнил(а) вовремя домашнее задание по предмету **{group_name}**.\n"
        "Пожалуйста, проконтролируйте подготовку ребёнка к занятиям. 📖💡"
    ),
    "tpl_payment_reminder": (
        "💳 **TO'LOV ESLATMASI / НАПОМИНАНИЕ ОБ ОПЛАТЕ**\n\n"
        "Hurmatli ota-ona!\n"
        "Farzandingiz **{student_name}** uchun keyingi oy (**{date}**) to'lov muddati yaqinlashmoqda.\n"
        "Oylik to'lov summasi: **{fee_amount} so'm**.\n"
        "To'lovni o'z vaqtida amalga oshirishingizni so'raymiz. Rahmat! ✨\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители!\n"
        "Приближается срок оплаты за следующий месяц (**{date}**) для вашего ребёнка **{student_name}**.\n"
        "Сумма ежемесячной оплаты: **{fee_amount} сум**.\n"
        "Просим произвести оплату вовремя. Спасибо! ✨"
    ),
    "tpl_payment_overdue": (
        "🚨 **TO'LOV MUDDATI O'TDI / ЗАДОЛЖЕННОСТЬ ПО ОПЛАТЕ**\n\n"
        "Hurmatli ota-ona!\n"
        "Farzandingiz **{student_name}** (**{group_name}**) uchun oylik to'lov muddati o'tgan.\n"
        "Mavjud qarzdorlik summasi: **{fee_amount} so'm**.\n"
        "Iltimos, darslar to'xtatilib qolmasligi uchun to'lovni tez fursatda amalga oshirishingizni so'raymiz. 📲\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители!\n"
        "Истёк срок оплаты за обучение вашего ребёнка **{student_name}** в группе **{group_name}**.\n"
        "Сумма задолженности: **{fee_amount} сум**.\n"
        "Пожалуйста, произведите оплату в ближайшее время для продолжения обучения. 📲"
    ),
    "tpl_payment_receipt": (
        "✅ **TO'LOV QABUL QILINDI / ОПЛАТА ПОЛУЧЕНА**\n\n"
        "Hurmatli ota-ona!\n"
        "Farzandingiz **{student_name}** (**{group_name}**) uchun **{amount} so'm** miqdoridagi to'lov muvaffaqiyatli qabul qilindi.\n"
        "Ishonchingiz uchun tashakkur! 🌟\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители!\n"
        "Оплата в размере **{amount} сум** за обучение вашего ребёнка **{student_name}** в группе **{group_name}** успешно принята.\n"
        "Благодарим за доверие! 🌟"
    ),
    "tpl_welcome_group": (
        "🎓 **XUSH KELIBSIZ! / ДОБРО ПОЖАЛОВАТЬ!**\n\n"
        "Hurmatli ota-ona va o'quvchi!\n"
        "Farzandingiz **{student_name}** Diamond Education **{group_name}** guruhiga muvaffaqiyatli qo'shildi.\n\n"
        "📅 **Dars kunlari:** {schedule_days}\n"
        "⏰ **Dars vaqti:** {schedule_time}\n\n"
        "O'qishlarida ulkan zafarlar va yuksak marralar tilaymiz! 🚀\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители и ученик!\n"
        "Ваш ребёнок **{student_name}** успешно зачислен(а) в группу **{group_name}** в Diamond Education.\n\n"
        "📅 **Дни занятий:** {schedule_days}\n"
        "⏰ **Время занятий:** {schedule_time}\n\n"
        "Желаем успехов и высоких достижений в учёбе! 🚀"
    ),
    "tpl_holiday_cancellation": (
        "📢 **DARS QOLDIRILISHI E'LONI / ОТМЕНА ЗАНЯТИЙ**\n\n"
        "Hurmatli ota-ona!\n"
        "**{date}** kuni bayram/dam olish munosabati bilan **{group_name}** guruhida dars bo'lmaydi.\n"
        "Darslar belgilangan jadval bo'yicha keyingi kundan davom etadi. 🗓️\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Уважаемые родители!\n"
        "**{date}** в связи с праздником/выходным днём занятия в группе **{group_name}** проводиться не будут.\n"
        "Занятия возобновятся со следующего дня по расписанию. 🗓️"
    ),
    "tpl_achievement": (
        "🏆 **FARANDINGIZNING YUTUQI / ДОСТИЖЕНИЕ РЕБЁНКА**\n\n"
        "Ajoyib xushxabar! 🥳\n"
        "Farzandingiz **{student_name}** **{group_name}** guruhida ajoyib natija ko'rsatdi:\n"
        "👉 **{achievement_text}**\n\n"
        "Farzandingizning bilimi va mehnati bilan faxrlanamiz! 🎉👏\n\n"
        "— — — — — — — — — — — — — — —\n"
        "Отличные новости! 🥳\n"
        "Ваш ребёнок **{student_name}** показал(а) отличный результат в группе **{group_name}**:\n"
        "👉 **{achievement_text}**\n\n"
        "Мы гордимся успехами вашего ребёнка! 🎉👏"
    ),
}


def ensure_userbot_schema() -> None:
    if _schema_ready("userbot_settings"):
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS userbot_settings (
                    id                          BIGSERIAL PRIMARY KEY,
                    api_id                      INTEGER,
                    api_hash                    TEXT,
                    phone_number                TEXT,
                    session_string              TEXT,
                    is_active                   INTEGER DEFAULT 1,
                    notify_attendance_absent    INTEGER DEFAULT 1,
                    notify_attendance_late      INTEGER DEFAULT 1,
                    notify_homework_missing     INTEGER DEFAULT 1,
                    notify_payment_reminder     INTEGER DEFAULT 1,
                    notify_payment_receipt      INTEGER DEFAULT 1,
                    notify_welcome_group        INTEGER DEFAULT 1,
                    notify_holiday_cancellation INTEGER DEFAULT 1,
                    notify_achievements         INTEGER DEFAULT 1,
                    tpl_attendance_absent       TEXT,
                    tpl_attendance_late         TEXT,
                    tpl_homework_missing        TEXT,
                    tpl_payment_reminder        TEXT,
                    tpl_payment_overdue         TEXT,
                    tpl_payment_receipt         TEXT,
                    tpl_welcome_group           TEXT,
                    tpl_holiday_cancellation    TEXT,
                    tpl_achievement             TEXT,
                    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS userbot_settings (
                    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_id                      INTEGER,
                    api_hash                    TEXT,
                    phone_number                TEXT,
                    session_string              TEXT,
                    is_active                   INTEGER DEFAULT 1,
                    notify_attendance_absent    INTEGER DEFAULT 1,
                    notify_attendance_late      INTEGER DEFAULT 1,
                    notify_homework_missing     INTEGER DEFAULT 1,
                    notify_payment_reminder     INTEGER DEFAULT 1,
                    notify_payment_receipt      INTEGER DEFAULT 1,
                    notify_welcome_group        INTEGER DEFAULT 1,
                    notify_holiday_cancellation INTEGER DEFAULT 1,
                    notify_achievements         INTEGER DEFAULT 1,
                    tpl_attendance_absent       TEXT,
                    tpl_attendance_late         TEXT,
                    tpl_homework_missing        TEXT,
                    tpl_payment_reminder        TEXT,
                    tpl_payment_overdue         TEXT,
                    tpl_payment_receipt         TEXT,
                    tpl_welcome_group           TEXT,
                    tpl_holiday_cancellation    TEXT,
                    tpl_achievement             TEXT,
                    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS userbot_contacts (
                    phone_number                TEXT PRIMARY KEY,
                    telegram_user_id            BIGINT,
                    first_name                  TEXT,
                    last_name                   TEXT,
                    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS userbot_contacts (
                    phone_number                TEXT PRIMARY KEY,
                    telegram_user_id            INTEGER,
                    first_name                  TEXT,
                    last_name                   TEXT,
                    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS userbot_logs (
                    id              BIGSERIAL PRIMARY KEY,
                    target_phone    TEXT,
                    telegram_user_id BIGINT,
                    event_type      TEXT,
                    message_text    TEXT,
                    status          TEXT DEFAULT 'sent',
                    error_detail    TEXT,
                    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS userbot_logs (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_phone    TEXT,
                    telegram_user_id INTEGER,
                    event_type      TEXT,
                    message_text    TEXT,
                    status          TEXT DEFAULT 'sent',
                    error_detail    TEXT,
                    sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            ],
        )
        _execute_ddl_candidates(
            cur,
            [
                """
                CREATE TABLE IF NOT EXISTS userbot_attendance_tracker (
                    id                  BIGSERIAL PRIMARY KEY,
                    group_id            BIGINT NOT NULL,
                    user_id             BIGINT NOT NULL,
                    lesson_date         TEXT NOT NULL,
                    marked_absent_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    absent_notified     INTEGER DEFAULT 0,
                    late_notified       INTEGER DEFAULT 0
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS userbot_attendance_tracker (
                    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id            INTEGER NOT NULL,
                    user_id             INTEGER NOT NULL,
                    lesson_date         TEXT NOT NULL,
                    marked_absent_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    absent_notified     INTEGER DEFAULT 0,
                    late_notified       INTEGER DEFAULT 0
                )
                """,
            ],
        )
        for ddl in (
            "CREATE INDEX IF NOT EXISTS idx_ub_log_time ON userbot_logs(sent_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_ub_log_phone ON userbot_logs(target_phone)",
            "CREATE INDEX IF NOT EXISTS idx_ub_att_track ON userbot_attendance_tracker(group_id, user_id, lesson_date)",
        ):
            try:
                cur.execute(ddl)
            except Exception:
                pass
        conn.commit()
        _mark_schema_ready("userbot_settings")
    finally:
        conn.close()


def get_userbot_settings() -> dict:
    ensure_userbot_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM userbot_settings WHERE id=1 LIMIT 1")
        row = _row_to_dict(cur.fetchone())
        if not row:
            # First time default seed
            cur.execute(
                """
                INSERT INTO userbot_settings (
                    id, is_active, notify_attendance_absent, notify_attendance_late,
                    notify_homework_missing, notify_payment_reminder, notify_payment_receipt,
                    notify_welcome_group, notify_holiday_cancellation, notify_achievements,
                    tpl_attendance_absent, tpl_attendance_late, tpl_homework_missing,
                    tpl_payment_reminder, tpl_payment_overdue, tpl_payment_receipt,
                    tpl_welcome_group, tpl_holiday_cancellation, tpl_achievement
                ) VALUES (
                    1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    DEFAULT_USERBOT_TEMPLATES["tpl_attendance_absent"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_attendance_late"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_homework_missing"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_payment_reminder"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_payment_overdue"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_payment_receipt"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_welcome_group"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_holiday_cancellation"],
                    DEFAULT_USERBOT_TEMPLATES["tpl_achievement"],
                ),
            )
            conn.commit()
        if row:
            # Refresh defaults to bilingual Uzbek + Russian if templates are single-line/old or contain call requests
            updated_any = False
            for k, v in DEFAULT_USERBOT_TEMPLATES.items():
                val = str(row.get(k) or "").strip()
                if not val or "\n" not in val or (k == "tpl_attendance_absent" and ("bog'lanishingizni" in val or "сообщите причину" in val)):
                    cur.execute(f"UPDATE userbot_settings SET {k}=? WHERE id=1", (v,))
                    row[k] = v
                    updated_any = True
            if updated_any:
                conn.commit()
        return row
    finally:
        conn.close()


def update_userbot_settings(fields: dict) -> dict:
    ensure_userbot_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        get_userbot_settings() # Ensure ID 1 exists
        sets: list[str] = []
        params: list = []
        allowed = {
            "api_id", "api_hash", "phone_number", "session_string", "is_active",
            "notify_attendance_absent", "notify_attendance_late", "notify_homework_missing",
            "notify_payment_reminder", "notify_payment_receipt", "notify_welcome_group",
            "notify_holiday_cancellation", "notify_achievements",
            "tpl_attendance_absent", "tpl_attendance_late", "tpl_homework_missing",
            "tpl_payment_reminder", "tpl_payment_overdue", "tpl_payment_receipt",
            "tpl_welcome_group", "tpl_holiday_cancellation", "tpl_achievement",
        }
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?")
                params.append(v)
        if sets:
            sets.append("updated_at=CURRENT_TIMESTAMP")
            cur.execute(f"UPDATE userbot_settings SET {', '.join(sets)} WHERE id=1", tuple(params))
            conn.commit()
        return get_userbot_settings()
    finally:
        conn.close()


def cache_userbot_contact(phone: str, telegram_user_id: int, first_name: str | None = None, last_name: str | None = None) -> None:
    ensure_userbot_schema()
    clean_phone = "".join(c for c in str(phone or "") if c.isdigit() or c == "+")
    if not clean_phone:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO userbot_contacts (phone_number, telegram_user_id, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (phone_number) DO UPDATE SET
                telegram_user_id=EXCLUDED.telegram_user_id,
                first_name=COALESCE(EXCLUDED.first_name, userbot_contacts.first_name),
                last_name=COALESCE(EXCLUDED.last_name, userbot_contacts.last_name),
                updated_at=CURRENT_TIMESTAMP
            """,
            (clean_phone, int(telegram_user_id), first_name or None, last_name or None),
        )
        conn.commit()
    finally:
        conn.close()


def get_cached_userbot_contact(phone: str) -> dict | None:
    ensure_userbot_schema()
    clean_phone = "".join(c for c in str(phone or "") if c.isdigit() or c == "+")
    if not clean_phone:
        return None
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM userbot_contacts WHERE phone_number=? LIMIT 1", (clean_phone,))
        return _row_to_dict(cur.fetchone()) or None
    finally:
        conn.close()


def log_userbot_message(target_phone: str, telegram_user_id: int | None, event_type: str, message_text: str, status: str = "sent", error_detail: str | None = None) -> None:
    ensure_userbot_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO userbot_logs (target_phone, telegram_user_id, event_type, message_text, status, error_detail)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(target_phone or "").strip(),
                int(telegram_user_id) if telegram_user_id else None,
                str(event_type or "general"),
                str(message_text or ""),
                str(status or "sent"),
                str(error_detail or "") if error_detail else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_userbot_logs(limit: int = 100) -> list[dict]:
    ensure_userbot_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM userbot_logs ORDER BY id DESC LIMIT ?", (int(limit),))
        return [_row_to_dict(r) for r in (cur.fetchall() or [])]
    finally:
        conn.close()


def ensure_app_version_settings_schema():
    schema_key = "app_version_settings"
    if _schema_ready(schema_key):
        return
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            if _is_postgres_enabled():
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_version_settings (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        min_student_version TEXT DEFAULT '1.0.0',
                        min_student_build INTEGER DEFAULT 1,
                        student_play_store_url TEXT DEFAULT 'https://play.google.com/store/apps/details?id=com.diamond.students',
                        student_app_store_url TEXT DEFAULT 'https://apps.apple.com/app/id6742398571',
                        min_teacher_version TEXT DEFAULT '1.0.0',
                        min_teacher_build INTEGER DEFAULT 1,
                        teacher_play_store_url TEXT DEFAULT 'https://play.google.com/store/apps/details?id=com.diamond.teachers',
                        teacher_app_store_url TEXT DEFAULT 'https://apps.apple.com/app/id6742398571',
                        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            else:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS app_version_settings (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        min_student_version TEXT DEFAULT '1.0.0',
                        min_student_build INTEGER DEFAULT 1,
                        student_play_store_url TEXT DEFAULT 'https://play.google.com/store/apps/details?id=com.diamond.students',
                        student_app_store_url TEXT DEFAULT 'https://apps.apple.com/app/id6742398571',
                        min_teacher_version TEXT DEFAULT '1.0.0',
                        min_teacher_build INTEGER DEFAULT 1,
                        teacher_play_store_url TEXT DEFAULT 'https://play.google.com/store/apps/details?id=com.diamond.teachers',
                        teacher_app_store_url TEXT DEFAULT 'https://apps.apple.com/app/id6742398571',
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            conn.commit()
            _mark_schema_ready(schema_key)
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()


def get_app_version_settings() -> dict:
    ensure_app_version_settings_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM app_version_settings WHERE id=1 LIMIT 1")
        row = cur.fetchone()
        if not row:
            with DB_WRITE_LOCK:
                cur.execute(
                    """
                    INSERT INTO app_version_settings (id, min_student_version, min_student_build, min_teacher_version, min_teacher_build)
                    VALUES (1, '1.0.0', 1, '1.0.0', 1)
                    """
                )
                conn.commit()
                cur.execute("SELECT * FROM app_version_settings WHERE id=1 LIMIT 1")
                row = cur.fetchone()
        return _row_to_dict(row) if row else {
            "min_student_version": "1.0.0",
            "min_student_build": 1,
            "student_play_store_url": "https://play.google.com/store/apps/details?id=com.diamond.students",
            "student_app_store_url": "https://apps.apple.com/app/id6742398571",
            "min_teacher_version": "1.0.0",
            "min_teacher_build": 1,
            "teacher_play_store_url": "https://play.google.com/store/apps/details?id=com.diamond.teachers",
            "teacher_app_store_url": "https://apps.apple.com/app/id6742398571",
        }
    finally:
        conn.close()


def update_app_version_settings(fields: dict) -> dict:
    ensure_app_version_settings_schema()
    get_app_version_settings()
    allowed = {
        "min_student_version", "min_student_build", "student_play_store_url", "student_app_store_url",
        "min_teacher_version", "min_teacher_build", "teacher_play_store_url", "teacher_app_store_url"
    }
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_app_version_settings()

    sets = []
    params = []
    for k, v in updates.items():
        sets.append(f"{k}=?")
        params.append(v)

    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"UPDATE app_version_settings SET {', '.join(sets)} WHERE id=1", tuple(params))
            conn.commit()
        finally:
            conn.close()

    return get_app_version_settings()

