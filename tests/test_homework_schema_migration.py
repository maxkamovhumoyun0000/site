import sqlite3
import unittest
from unittest.mock import Mock, patch

import db


class HomeworkSchemaMigrationTests(unittest.TestCase):
    def test_adds_type_specific_prompt_columns_to_legacy_table(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute(
            "CREATE TABLE web_homeworks (id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL)"
        )
        connection_proxy = Mock(wraps=connection)
        connection_proxy.close = Mock()

        with patch.object(db, "get_conn", return_value=connection_proxy), patch.object(
            db, "_is_postgres_enabled", return_value=False
        ):
            db.ensure_homework_schema()

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(web_homeworks)").fetchall()
        }
        self.assertTrue(
            {"essay_prompt", "file_prompt", "voice_prompt"}.issubset(columns)
        )
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertTrue(
            {
                "web_homework_submissions",
                "web_homework_deadline_penalties",
                "web_homework_voiceroom_groups",
            }.issubset(tables)
        )
        connection.close()

    def test_all_homework_modalities_persist_on_fresh_schema(self):
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, first_name TEXT)"
        )
        connection.executemany(
            "INSERT INTO users(id, first_name) VALUES (?, ?)",
            [(1, "Student One"), (2, "Student Two")],
        )
        connection_proxy = Mock(wraps=connection)
        connection_proxy.close = Mock()
        db._SCHEMA_READY.clear()

        question = {
            "question": "Choose the correct answer",
            "options": ["Correct", "Incorrect"],
            "correct": "Correct",
        }
        assignments = [
            {
                "title": "Written response",
                "requires_essay": True,
                "essay_prompt": "Write about your daily routine.",
            },
            {
                "title": "File upload",
                "requires_file": True,
                "file_prompt": "Upload a photo of the worksheet.",
            },
            {
                "title": "Voice response",
                "requires_voice_message": True,
                "voice_prompt": "Describe your favorite book.",
            },
            {
                "title": "Interactive test",
                "homework_kind": "test",
                "test_questions": [question],
            },
            {
                "title": "Written response and test",
                "homework_kind": "both",
                "requires_essay": True,
                "essay_prompt": "Explain your answer.",
                "test_questions": [question],
            },
            {
                "title": "VoiceRoom pair task",
                "is_voiceroom": True,
                "voiceroom_groups": [
                    {"student1_id": 1, "student2_id": 2}
                ],
            },
        ]

        with patch.object(db, "get_conn", return_value=connection_proxy), patch.object(
            db, "_is_postgres_enabled", return_value=False
        ):
            for index, assignment in enumerate(assignments, start=1):
                homework = db.create_homework(
                    teacher_id=99,
                    subject="English",
                    idempotency_key=f"modality-{index}",
                    **assignment,
                )
                self.assertIsNotNone(homework, assignment["title"])
                self.assertEqual(homework["title"], assignment["title"])
            stored = connection.execute(
                "SELECT title, essay_prompt, file_prompt, voice_prompt "
                "FROM web_homeworks ORDER BY id"
            ).fetchall()

        self.assertEqual(len(stored), len(assignments))
        self.assertEqual(stored[0]["essay_prompt"], assignments[0]["essay_prompt"])
        self.assertEqual(stored[1]["file_prompt"], assignments[1]["file_prompt"])
        self.assertEqual(stored[2]["voice_prompt"], assignments[2]["voice_prompt"])
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM web_content_tests WHERE content_type='homework'"
            ).fetchone()[0],
            2,
        )
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM web_homework_voiceroom_groups"
            ).fetchone()[0],
            1,
        )
        connection.close()


if __name__ == "__main__":
    unittest.main()
