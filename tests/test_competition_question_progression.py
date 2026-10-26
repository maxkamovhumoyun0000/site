import backend.main as api


def test_answer_response_contains_the_next_question_without_waiting_for_opponent(monkeypatch):
    monkeypatch.setattr(api, "_duel_persist_session", lambda _session: None)
    session = {
        "id": "cmp-progress",
        "mode": "duel-1v1",
        "subject": "English",
        "status": "running",
        "questions": [
            {"question": "First?", "option_a": "A", "option_b": "B", "correct_option_index": 1},
            {"question": "Second?", "option_a": "C", "option_b": "D", "correct_option_index": 1},
        ],
        "progress": {7: {"index": 2, "correct": 1, "wrong": 0, "unanswered": 0}},
        "timers": {},
    }

    payload = api._competition_current_question_payload(session, 7)

    assert payload["question_index"] == 2
    assert payload["question"]["prompt"] == "Second?"
    assert payload["time_remaining_sec"] >= 30


def test_competition_question_validator_rejects_malformed_or_ambiguous_rows():
    valid = {
        "question": "Choose the correct answer.",
        "option_a": "Correct",
        "option_b": "Distractor",
        "correct_option_index": 1,
    }
    missing_prompt = {**valid, "question": "   "}
    duplicate_options = {**valid, "option_b": "correct"}
    invalid_correct_index = {**valid, "correct_option_index": 3}

    assert api._competition_question_is_valid(valid) is True
    assert api._competition_question_is_valid(missing_prompt) is False
    assert api._competition_question_is_valid(duplicate_options) is False
    assert api._competition_question_is_valid(invalid_correct_index) is False


def test_competition_question_deduplication_uses_the_question_not_distractors():
    first = {
        "question": "What is the capital of France?",
        "option_a": "Paris",
        "option_b": "Rome",
        "correct_option_index": 1,
    }
    rewritten = {
        **first,
        "option_b": "Berlin",
    }

    assert api._competition_valid_unique_rows([first, rewritten]) == [first]


def test_competition_timer_uses_the_database_question_limit_with_safe_bounds():
    question = {
        "question": "Choose the correct answer.",
        "option_a": "A",
        "option_b": "B",
        "correct_option_index": 1,
        "payload_json": '{"time_limit_sec": 47}',
    }

    assert api._competition_question_allowed_seconds(question, "duel-1v1") == 47


def test_stitch_competition_payloads_cover_all_random_vocabulary_inputs_without_visible_keys():
    variants = [
        ("spelling", "text", {"target_word": "acquire", "answer": "acquire"}),
        ("translation", "text", {"answer": "sotib olmoq", "direction": "EN→UZ"}),
        ("matching", "matching", {"pairs": [{"left": "acquire", "right": "sotib olmoq"}, {"left": "avoid", "right": "chetlab o'tmoq"}]}),
        ("speak_sentence", "audio", {"word": "acquire", "reference_answer": "I acquired new skills."}),
        ("read_aloud", "audio", {"word": "acquire", "reference_answer": "acquire"}),
        ("write_sentence", "text", {"word": "acquire", "reference_answer": "I acquired new skills."}),
    ]

    for question_type, input_type, extra in variants:
        payload = {
            "question_type": question_type,
            "input": input_type,
            "prompt": f"Prompt for {question_type}",
            "instruction": f"Instruction for {question_type}",
            **extra,
        }
        row = {
            "question": payload["prompt"],
            "question_type": question_type,
            "subject": "English",
            "payload_json": __import__("json").dumps(payload),
        }

        public = api._public_question_payload(row)

        assert public["question_type"] == question_type
        assert public["input_type"] == input_type
        assert "answer" not in public
        assert "correct_answer" not in public
        assert "accepted_answers" not in public
        if question_type == "spelling":
            assert public["pronunciation_text"] == "acquire"
            assert "word" not in public
        if question_type == "matching":
            assert len(public["matching_left"]) == len(public["matching_options"]) == 2


def test_result_review_has_sample_answers_and_explanations_for_rich_tests():
    question = api._mcq_question_from_row({
        "question": "Write a sentence using 'acquire'.",
        "question_type": "write_sentence",
        "payload_json": '{"question_type":"write_sentence","input":"text",'
        '"reference_answer":"I acquired new skills.",'
        '"explanation":"Use the past tense after the time marker."}',
    })

    assert api._competition_review_correct_answer(question) == "I acquired new skills."
    assert question["payload"]["explanation"] == "Use the past tense after the time marker."


def test_speaking_accounts_can_use_competitions_without_student_group_assignment(monkeypatch):
    monkeypatch.setattr(api, "is_access_active", lambda _user: True)

    def reject_student_group_gate(_user):
        raise AssertionError("Speaking accounts must not use the Student group gate")

    monkeypatch.setattr(api, "_require_student_learning_access", reject_student_group_gate)
    api._require_competition_learning_access({
        "id": 700,
        "login_type": 7,
        "speaking_app_account": 1,
        "access_enabled": 1,
        "blocked": 0,
    })


def test_speaking_competition_access_still_rejects_blocked_or_expired_accounts(monkeypatch):
    blocked_user = {
        "id": 701,
        "login_type": 7,
        "speaking_app_account": 1,
        "access_enabled": 1,
        "blocked": 1,
    }
    try:
        api._require_competition_learning_access(blocked_user)
    except api.HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Akkaunt bloklangan"
    else:
        raise AssertionError("Blocked Speaking accounts must be rejected")

    monkeypatch.setattr(api, "is_access_active", lambda _user: False)
    expired_user = {**blocked_user, "blocked": 0}
    try:
        api._require_competition_learning_access(expired_user)
    except api.HTTPException as exc:
        assert exc.status_code == 403
        assert "faol emas" in exc.detail
    else:
        raise AssertionError("Expired Speaking accounts must be rejected")
