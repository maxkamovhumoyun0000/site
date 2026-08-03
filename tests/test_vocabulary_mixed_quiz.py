from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

os.environ["REQUIRE_POSTGRES"] = "false"
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vocabulary
import db


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_words(path: Path) -> None:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE words (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL,
            subject TEXT NOT NULL,
            language TEXT NOT NULL,
            level TEXT NOT NULL,
            translation_uz TEXT,
            translation_ru TEXT,
            definition TEXT,
            example TEXT
        )
        """
    )
    for idx in range(1, 91):
        cur.execute(
            """
            INSERT INTO words (
                id, word, subject, language, level,
                translation_uz, translation_ru, definition, example
            )
            VALUES (?, ?, 'English', 'en', ?, ?, ?, ?, ?)
            """,
            (
                idx,
                f"word{idx}",
                ["A2", "B1", "B2"][idx % 3],
                f"uz{idx}",
                f"ru{idx}",
                f"definition {idx}",
                f"This is word{idx} in a sentence.",
            ),
        )
    conn.commit()
    conn.close()


def _seed_subject_schema(path: Path) -> None:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, subject TEXT)")
    cur.execute("CREATE TABLE groups (id INTEGER PRIMARY KEY, subject TEXT)")
    cur.execute("CREATE TABLE user_groups (user_id INTEGER, group_id INTEGER)")
    cur.execute("INSERT INTO users (id, subject) VALUES (1, 'English,Russian')")
    cur.execute("INSERT INTO groups (id, subject) VALUES (10, 'Russian')")
    cur.execute("INSERT INTO groups (id, subject) VALUES (11, 'English')")
    cur.execute("INSERT INTO user_groups (user_id, group_id) VALUES (1, 10)")
    cur.execute("INSERT INTO user_groups (user_id, group_id) VALUES (1, 11)")
    conn.commit()
    conn.close()


def test_generate_balanced_mixed_quiz_fixed_twenty_without_repeated_words(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "vocab.db"
    _seed_words(db_path)
    monkeypatch.setattr(vocabulary, "get_conn", lambda: _connect(db_path))

    questions = vocabulary.generate_balanced_mixed_quiz(
        user_id=1,
        subject="English",
        levels=["A2", "B1", "B2"],
        count=20,
        preferred_translation="uz",
        cooldown_word_ids_by_type={
            "multiple_choice": {1, 2, 3},
            "gap_filling": {1, 2, 3},
            "definition": {1, 2, 3},
        },
    )

    assert len(questions) == 20
    word_ids = [int(item["word_id"]) for item in questions]
    assert len(word_ids) == len(set(word_ids))
    assert not ({1, 2, 3} & set(word_ids))

    counts = {
        qtype: sum(1 for item in questions if item.get("question_type") == qtype)
        for qtype in vocabulary.VOCAB_QUIZ_TYPES
    }
    assert max(counts.values()) - min(counts.values()) <= 1


def test_get_user_subjects_prefers_user_subject_csv_order(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "subjects.db"
    _seed_subject_schema(db_path)
    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))

    assert db.get_user_subjects(1) == ["English", "Russian"]
