"""Persistent, user-scoped safety controls shared by web and mobile clients.

No external services or app imports: the connection factory is injected so the
same queries can be exercised against an isolated database in regression tests.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os
import re
import threading
import unicodedata
from uuid import uuid4


def validate_public_text(text: str) -> str:
    text = str(text or "").strip()
    if not text or len(text) > 4000:
        raise ValueError("Matn 1–4000 belgidan iborat bo'lishi kerak.")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
    normalized = re.sub(r"\s+", " ", normalized)
    # Baseline text filtering, not a replacement for human moderation. The
    # operations team can extend phrases without shipping another mobile app.
    phrases = ["kill yourself", "i will kill you", "я тебя убью", "иди сдохни"]
    phrases += [p.strip().casefold() for p in os.getenv("COMMUNITY_BLOCKED_PHRASES", "").split("|") if p.strip()]
    if any(re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", normalized) for p in phrases):
        raise ValueError("Haqorat yoki tahdidli matnni yuborib bo'lmaydi.")
    if len(re.findall(r"https?://", normalized)) > 5:
        raise ValueError("Juda ko'p havola. Matnni qisqartiring.")
    return text


class SafetyStore:
    def __init__(self, connection_factory):
        self.connect = connection_factory
        self._ready = False
        self._lock = threading.Lock()

    def ensure_schema(self):
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            conn = self.connect()
            try:
                cur = conn.cursor()
                for sql in (
                    "CREATE TABLE IF NOT EXISTS web_user_blocks (user_id BIGINT NOT NULL, blocked_user_id BIGINT NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(user_id, blocked_user_id))",
                    "CREATE TABLE IF NOT EXISTS web_comment_authors (comment_id BIGINT PRIMARY KEY, author_user_id BIGINT NOT NULL)",
                    "CREATE TABLE IF NOT EXISTS web_hidden_content (target_type TEXT NOT NULL, target_id TEXT NOT NULL, PRIMARY KEY(target_type, target_id))",
                    """CREATE TABLE IF NOT EXISTS web_safety_reports (
                        id TEXT PRIMARY KEY, user_id BIGINT NOT NULL,
                        target_type TEXT NOT NULL, target_id TEXT NOT NULL,
                        target_user_id BIGINT, reason TEXT NOT NULL, details TEXT NOT NULL,
                        snapshot TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
                        created_at TEXT NOT NULL, resolved_at TEXT,
                        UNIQUE(user_id, target_type, target_id))""",
                    "CREATE INDEX IF NOT EXISTS idx_safety_reports_status ON web_safety_reports(status, created_at)",
                    "CREATE INDEX IF NOT EXISTS idx_user_blocks_reverse ON web_user_blocks(blocked_user_id, user_id)",
                ):
                    cur.execute(sql)
                conn.commit()
                self._ready = True
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    @contextmanager
    def transaction(self):
        self.ensure_schema()
        conn = self.connect()
        try:
            yield conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def blocked_ids(self, user_id, *, either_direction=True):
        if not user_id:
            return set()
        with self.transaction() as cur:
            cur.execute("SELECT blocked_user_id FROM web_user_blocks WHERE user_id=?", (int(user_id),))
            ids = {int(r["blocked_user_id"]) for r in cur.fetchall()}
            if either_direction:
                cur.execute("SELECT user_id FROM web_user_blocks WHERE blocked_user_id=?", (int(user_id),))
                ids.update(int(r["user_id"]) for r in cur.fetchall())
            return ids

    def block(self, user_id, target_id):
        if int(user_id) == int(target_id) or int(target_id) <= 0:
            raise ValueError("Bu foydalanuvchini bloklab bo'lmaydi.")
        with self.transaction() as cur:
            cur.execute("SELECT id FROM users WHERE id=?", (int(target_id),))
            if not cur.fetchone():
                raise LookupError("Foydalanuvchi topilmadi.")
            cur.execute("INSERT INTO web_user_blocks (user_id, blocked_user_id, created_at) VALUES (?, ?, ?) ON CONFLICT(user_id, blocked_user_id) DO NOTHING", (int(user_id), int(target_id), datetime.now(timezone.utc).isoformat()))

    def unblock(self, user_id, target_id):
        with self.transaction() as cur:
            cur.execute("DELETE FROM web_user_blocks WHERE user_id=? AND blocked_user_id=?", (int(user_id), int(target_id)))

    def list_blocks(self, user_id):
        with self.transaction() as cur:
            cur.execute("""SELECT b.blocked_user_id AS user_id, u.first_name, u.last_name
                FROM web_user_blocks b JOIN users u ON u.id=b.blocked_user_id
                WHERE b.user_id=? ORDER BY b.created_at DESC""", (int(user_id),))
            return [dict(r) for r in cur.fetchall()]

    def report(self, user_id, target_type, target_id, target_user_id, reason, details, snapshot):
        with self.transaction() as cur:
            cur.execute("SELECT id FROM web_safety_reports WHERE user_id=? AND target_type=? AND target_id=?", (user_id, target_type, str(target_id)))
            existing = cur.fetchone()
            if existing:
                return str(existing["id"]), False
            since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
            cur.execute("SELECT COUNT(*) AS n FROM web_safety_reports WHERE user_id=? AND created_at>?", (user_id, since))
            if int(cur.fetchone()["n"]) >= 10:
                raise ValueError("Shikoyatlar limiti. Birozdan keyin qayta urinib ko'ring.")
            report_id = str(uuid4())
            cur.execute("""INSERT INTO web_safety_reports
                (id,user_id,target_type,target_id,target_user_id,reason,details,snapshot,created_at)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,target_type,target_id) DO NOTHING""",
                (report_id, user_id, target_type, str(target_id), target_user_id, reason, details, snapshot[:4000], datetime.now(timezone.utc).isoformat()))
            created = cur.rowcount > 0
            cur.execute("SELECT id FROM web_safety_reports WHERE user_id=? AND target_type=? AND target_id=?", (user_id, target_type, str(target_id)))
            return str(cur.fetchone()["id"]), created

    def video_comments(self, video_id, viewer_id=0):
        blocked = self.blocked_ids(viewer_id)
        with self.transaction() as cur:
            cur.execute("""SELECT c.*, a.author_user_id FROM web_video_comments c
                LEFT JOIN web_comment_authors a ON a.comment_id=c.id
                WHERE c.video_id=? ORDER BY c.created_at DESC LIMIT 500""", (int(video_id),))
            rows = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT target_id FROM web_hidden_content WHERE target_type='video_comment'")
            hidden = {str(r["target_id"]) for r in cur.fetchall()}
            if viewer_id:
                cur.execute("SELECT target_id FROM web_safety_reports WHERE user_id=? AND target_type='video_comment'", (int(viewer_id),))
                hidden.update(str(r["target_id"]) for r in cur.fetchall())
            return [r for r in rows if str(r["id"]) not in hidden and int(r.get("author_user_id") or 0) not in blocked]

    def resolve(self, report_id, action):
        if action not in {"dismiss", "remove_content", "suspend_user"}:
            raise ValueError("Invalid moderation action")
        with self.transaction() as cur:
            cur.execute("SELECT * FROM web_safety_reports WHERE id=?", (report_id,))
            row = cur.fetchone()
            if not row:
                raise LookupError("Report not found")
            if action == "remove_content":
                if row["target_type"] != "video_comment":
                    raise ValueError("Use the source moderation screen for this content type")
                cur.execute("INSERT INTO web_hidden_content (target_type,target_id) VALUES (?,?) ON CONFLICT(target_type,target_id) DO NOTHING", (row["target_type"], row["target_id"]))
            if action == "suspend_user":
                if not row["target_user_id"]:
                    raise ValueError("No verified author for this report")
                cur.execute("UPDATE users SET blocked=1 WHERE id=?", (int(row["target_user_id"]),))
            cur.execute("UPDATE web_safety_reports SET status=?, resolved_at=? WHERE id=?", (action, datetime.now(timezone.utc).isoformat(), report_id))
            return dict(row)
