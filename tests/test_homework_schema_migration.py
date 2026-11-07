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
        connection.close()


if __name__ == "__main__":
    unittest.main()
