import backend.personalization as personalization


def test_track_passing_score_defaults_to_seventy_and_is_clamped():
    assert personalization.normalize_track_passing_score(None) == 70
    assert personalization.normalize_track_passing_score(70) == 70
    assert personalization.normalize_track_passing_score(101) == 100
    assert personalization.normalize_track_passing_score(0) == 1


def test_module_and_next_track_unlock_require_passing_score():
    assert personalization.learning_score_passes(69.99, 70) is False
    assert personalization.learning_score_passes(70, 70) is True
    assert personalization.next_track_unlocked(["passed", "passed"]) is True
    assert personalization.next_track_unlocked(["passed", "in_progress"]) is False


def test_certificate_is_eligible_only_after_track_completion():
    assert personalization.track_certificate_eligible("passed", certificate_required=True) is True
    assert personalization.track_certificate_eligible("in_progress", certificate_required=True) is False
    assert personalization.track_certificate_eligible("passed", certificate_required=False) is False


def test_library_question_keeps_rich_fields_and_accepted_answers():
    raw = {
        "kind": "spelling", "word": "colour", "answer": "colour",
        "accepted_answers": ["color"], "audio_url": "/audio/test.mp3",
        "image_url": "/image/test.png", "custom_metadata": {"source": "book"},
    }
    result = personalization._learning_library_question(raw)
    assert result["correct_answer"] == "colour"
    assert result["acceptable_answers"] == ["color"]
    for key in raw:
        assert result[key] == raw[key]


def test_deterministic_translation_checker_accepts_all_selected_synonyms():
    accepted = ["murabbiy", "тренер"]
    assert personalization._learning_answer_matches("Murabbiy", accepted)
    assert personalization._learning_answer_matches(
        "Murabbiy, тренер", accepted, allow_joined_translation=True
    )
    assert not personalization._learning_answer_matches(
        "Murabbiy, doctor", accepted, allow_joined_translation=True
    )


def test_false_answer_is_not_replaced_by_true():
    result = personalization._learning_library_question({"kind": "true_false", "answer": False})
    assert result["correct_answer"] == "Noto'g'ri"
    listening = personalization._learning_library_question({"kind": "listening_tf", "correct_index": 2})
    assert listening["correct_answer"] == "Not given"


def test_editing_library_choices_and_accepted_answers_replaces_old_values():
    result = personalization._learning_library_question({
        "kind": "listening", "options": ["old", "new"],
        "answer": "old", "correct_index": 1,
        "accepted_answers": [], "acceptable_answers": ["obsolete"],
    })
    assert result["correct_answer"] == "new"
    assert result["acceptable_answers"] == []


def test_learning_path_contract_canonicalizes_repeatable_legacy_values():
    result = personalization._learning_library_question({
        "kind": "listening",
        "prompt": "Choose",
        "options": "First | Second | Third",
        "correct_index": 0,
        "accepted_answers": "first answer, first option",
        "word_bank": "first\nsecond",
    })
    assert result["options"] == ["First", "Second", "Third"]
    assert result["correct_answer"] == "First"
    assert result["acceptable_answers"] == ["first answer", "first option"]
    assert result["word_bank"] == ["first", "second"]


def test_diamondvoy_learning_generator_uses_the_materials_library_contract():
    choice = personalization._learning_ai_question_payload({
        "test_type": "multiple_choice",
        "question": "Choose the verb.",
        "options": ["run", "blue", "quickly"],
        "correct_answer": "run",
    }, topic="Parts of speech", position=1)
    gap = personalization._learning_ai_question_payload({
        "test_type": "fill_blank",
        "question": "She ___ home.",
        "correct_answer": "goes",
        "accepted_answers": ["walks"],
    }, topic="Present simple", position=2)
    order = personalization._learning_ai_question_payload({
        "test_type": "word_order",
        "question": "Put the words in order.",
        "correct_answer": "We study English.",
    }, topic="Word order", position=3)

    assert choice["kind"] == choice["test_type"] == "multiple_choice"
    assert choice["correct_index"] == 0
    assert gap["kind"] == gap["test_type"] == "gap_fill"
    assert gap["accepted_answers"] == ["walks"]
    assert order["kind"] == order["test_type"] == "scrambled_sentence"
    assert order["tokens"] == ["We", "study", "English"]


def test_learning_path_cloze_keeps_each_alternative_as_a_separate_value():
    result = personalization._learning_library_question({
        "kind": "passage_cloze",
        "passage": "She ___ home.",
        "answers": [{"answer": "went", "accepted_answers": "has gone | had gone"}],
    })
    assert result["blanks"] == [{
        "answer": "went",
        "accepted_answers": ["has gone", "had gone"],
    }]
    assert result["answers"] == result["blanks"]


def test_library_sets_and_cloze_have_native_runner_aliases():
    reading = personalization._learning_library_question({
        "kind": "reading_set", "passage": "A story.",
        "questions": [{"type": "mcq", "prompt": "Who?", "options": ["A", "B"], "correct_index": 1}],
    })
    assert reading["sub_questions"][0]["answer"] == "B"
    assert reading["questions"][0]["correct_index"] == 1
    cloze = personalization._learning_library_question({
        "kind": "passage_cloze", "passage": "I ___ home.",
        "answers": [{"answer": "go", "accepted_answers": ["went"]}],
    })
    assert cloze["blanks"] == cloze["answers"]


def test_final_exam_preserves_media_pairs_and_metadata():
    question = {"kind": "matching", "prompt": "Match", "pairs": [
        {"left": "one", "right": "bir"}, {"left": "two", "right": "ikki"},
    ], "audio_url": "/audio.mp3", "image_url": "/image.png"}
    result = personalization._learning_exam_questions(question)[0]
    assert result["pairs"] == question["pairs"]
    assert result["audio_url"] == question["audio_url"]
    assert result["image_url"] == question["image_url"]


def test_final_exam_expands_sets_and_numbers_cloze_without_answer_leaks():
    questions = personalization._learning_exam_questions({
        "kind": "listening_set", "audio_url": "/audio.mp3", "sub_questions": [
            {"type": "mcq", "prompt": "Who?", "options": ["A", "B"], "correct_index": 1},
            {"type": "open", "prompt": "Why?", "reference_answer": "Because."},
        ],
    })
    assert len(questions) == 2
    assert questions[0]["correct_answer"] == "B"
    assert questions[0]["test_type"] == "multiple_choice"
    assert questions[1]["test_type"] == "listening_open"
    assert all(q["audio_url"] == "/audio.mp3" for q in questions)
    cloze = personalization._learning_exam_questions({
        "kind": "passage_cloze", "passage": "I ___ to ___ .",
        "answers": [{"answer": "go"}, {"answer": "school"}],
    })
    assert len(cloze) == 2
    assert cloze[0]["passage"] == "I [1] to [2] ."
    assert cloze[1]["correct_answer"] == "school"


def test_batch_append_is_atomic_and_preserves_position_zero(monkeypatch):
    import asyncio
    import sqlite3
    import pytest
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE learning_modules(id INTEGER PRIMARY KEY, track_id INTEGER);
        INSERT INTO learning_modules VALUES(1, 7);
        CREATE TABLE learning_module_lessons(
            id INTEGER PRIMARY KEY, module_id INTEGER, title TEXT, source_kind TEXT,
            source_id TEXT, source_version TEXT, question_payload_json TEXT,
            duration_seconds INTEGER, position INTEGER, required INTEGER);
        INSERT INTO learning_module_lessons(module_id,title,position) VALUES(1,'Existing',0);
    """)
    class Connection:
        def cursor(self): return conn.cursor()
        def commit(self): conn.commit()
        def rollback(self): conn.rollback()
        def close(self): pass
    monkeypatch.setattr(personalization, "get_conn", lambda: Connection())
    monkeypatch.setattr(personalization, "ensure_schema", lambda: None)
    monkeypatch.setattr(personalization, "_user", lambda _: {"id": 1, "role": "teacher"})
    monkeypatch.setattr(personalization, "_require", lambda *args: None)
    monkeypatch.setattr(personalization, "_learning_track_for_manager", lambda *args: {})
    item = {"title": "New", "question_payload": {"kind": "spelling", "word": "hello"}}
    result = asyncio.run(personalization.add_learning_lessons_batch(1,
        personalization.LearningLessonBatchRequest(items=[item, item]), None))
    assert result["question_count"] == 2
    assert [r[0] for r in conn.execute("SELECT position FROM learning_module_lessons ORDER BY id")] == [0, 1, 2]
    conn.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON learning_module_lessons WHEN NEW.title='fail' BEGIN SELECT RAISE(ABORT,'test failure'); END;")
    with pytest.raises(sqlite3.IntegrityError):
        asyncio.run(personalization.add_learning_lessons_batch(1,
            personalization.LearningLessonBatchRequest(items=[item, {**item, "title": "fail"}]), None))
    assert conn.execute("SELECT COUNT(*) FROM learning_module_lessons").fetchone()[0] == 3
    conn.close()
