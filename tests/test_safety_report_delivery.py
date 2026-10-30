"""Report delivery must be atomic and retry-safe, using an isolated database."""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from community_safety import SafetyStore


class SafetyDeliveryTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".sqlite")
        os.close(handle)
        conn = self.connect()
        conn.executescript("""
            CREATE TABLE feedback_threads (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE,
                status TEXT, created_at TEXT, updated_at TEXT);
            CREATE TABLE feedback_messages (id INTEGER PRIMARY KEY, thread_id INTEGER,
                sender_user_id INTEGER, sender_role TEXT, message_text TEXT,
                is_anonymous_choice INTEGER, created_at TEXT);
        """)
        conn.close()
        self.store = SafetyStore(self.connect)

    def tearDown(self):
        os.unlink(self.path)

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def test_report_is_delivered_once_and_duplicate_repairs_missing_inbox(self):
        args = (1, "user", "2", 2, "abuse", "details", "context")
        report_id, created = self.store.report(*args, sender_role="student")
        self.assertTrue(created)
        conn = self.connect()
        rows = conn.execute("SELECT message_text FROM feedback_messages").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertIn(report_id, rows[0]["message_text"])
        conn.execute("DELETE FROM feedback_messages")
        conn.commit()
        conn.close()
        self.assertEqual(self.store.report(*args, sender_role="student"), (report_id, False))
        self.store.report(*args, sender_role="student")
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT count(*) FROM feedback_messages").fetchone()[0], 1)
        conn.close()

    def test_inbox_failure_rolls_back_new_report(self):
        self.store.ensure_schema()
        conn = self.connect()
        conn.execute("DROP TABLE feedback_messages")
        conn.close()
        with self.assertRaises(sqlite3.OperationalError):
            self.store.report(1, "user", "2", 2, "abuse", "", "", sender_role="student")
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT count(*) FROM web_safety_reports").fetchone()[0], 0)
        conn.close()

    def test_new_report_reopens_closed_feedback_thread(self):
        conn = self.connect()
        conn.execute("INSERT INTO feedback_threads(user_id,status) VALUES (1,'Yopilgan')")
        conn.commit()
        conn.close()
        self.store.report(1, "user", "2", 2, "abuse", "", "", sender_role="student")
        conn = self.connect()
        self.assertEqual(conn.execute("SELECT status FROM feedback_threads WHERE user_id=1").fetchone()[0], "Yangi")
        conn.close()


if __name__ == "__main__":
    unittest.main()
