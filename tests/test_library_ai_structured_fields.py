import backend.library_ai as library_ai
import asyncio


def test_string_list_accepts_structured_values_and_legacy_delimiters():
    assert library_ai._normalize_string_list([" goes ", "walks", "", "goes"]) == ["goes", "walks"]
    assert library_ai._normalize_string_list("goes, walks\n runs | jogs") == [
        "goes",
        "walks",
        "runs",
        "jogs",
    ]


def test_ai_import_canonicalizes_all_repeatable_fields_as_arrays():
    questions = library_ai._normalize_questions([
        {
            "kind": "passage_cloze",
            "passage": "She ___ home.",
            "answers": [{"answer": "went", "accepted_answers": "has gone, had gone"}],
            "word_bank": "went, goes | stayed",
        },
        {
            "kind": "scrambled_sentence",
            "prompt": "Put the words in order",
            "answer": "I go home",
            "tokens": "I | go | home",
            "distractors": "went, school",
        },
    ])

    assert questions[0]["blanks"][0]["accepted_answers"] == ["has gone", "had gone"]
    assert set(questions[0]["word_bank"]) == {"went", "goes", "stayed"}
    assert questions[1]["tokens"] == ["I", "go", "home"]
    assert questions[1]["distractors"] == ["went", "school"]


def test_ai_import_preserves_the_first_choice_when_correct_index_is_zero():
    question = library_ai._normalize_questions([
        {
            "kind": "listening",
            "prompt": "Choose the first option",
            "options": ["First", "Second"],
            "correct_index": 0,
            "correct_option_index": 1,
        }
    ])[0]

    assert question["correct_index"] == 0


def test_image_import_uses_audio_free_choice_types_for_printed_questions():
    questions = library_ai._normalize_questions([
        {
            "kind": "multiple_choice",
            "question": "Which word is a verb?",
            "options": ["run", "blue", "quickly"],
            "correct_answer": "run",
        },
        {
            "kind": "true_false",
            "question": "A sentence starts with a capital letter.",
            "correct_answer": "True",
        },
    ])

    assert [question["kind"] for question in questions] == ["multiple_choice", "true_false"]
    assert all(not question.get("needs_audio_upload") for question in questions)
    assert library_ai._question_for_student(questions[0])["input"] == "choice"
    assert library_ai._check_auto(
        questions[0], library_ai.AiTestAnswerRequest(question_index=0, choice_index=0)
    )[0] == "correct"


def test_homework_checker_uses_each_alternative_answer_as_a_complete_value():
    question = {
        "kind": "gap_fill",
        "answer": "goes",
        "accepted_answers": ["walks", "travels"],
    }

    verdict, _ = library_ai._check_auto(
        question,
        library_ai.AiTestAnswerRequest(question_index=0, answer_text="travels"),
    )

    assert verdict == "correct"


def test_nested_set_checker_respects_separate_choice_and_answer_fields():
    sub = {
        "type": "mcq",
        "options": ["Teacher", "Doctor", "Engineer"],
        "correct_index": 2,
    }
    correct, _ = library_ai._check_listening_set_sub_answer(sub, {"choice_index": 2})
    wrong, detail = library_ai._check_listening_set_sub_answer(sub, {"choice_index": 1})

    assert correct is True
    assert wrong is False
    assert detail["correct_answer"] == "Engineer"


def test_reading_choice_keeps_its_selected_option_for_homework_and_learning_paths():
    normalized = library_ai._normalize_questions([
        {
            "kind": "reading_set",
            "passage": "Sara is a doctor.",
            "questions": [{
                "type": "choice",
                "prompt": "What is Sara's job?",
                "options": "Teacher | Doctor | Engineer",
                "correct_index": 1,
            }],
        }
    ])[0]

    sub = normalized["sub_questions"][0]
    assert sub["options"] == ["Teacher", "Doctor", "Engineer"]
    assert sub["correct_index"] == 1
    assert sub["answer"] == "Doctor"
    verdict, _ = library_ai._check_auto(
        normalized,
        library_ai.AiTestAnswerRequest(
            question_index=0, sub_answers=[{"choice_index": 1}],
        ),
    )
    assert verdict == "correct"


def test_ai_grading_cache_key_includes_the_complete_rubric_and_result_language():
    base = {"kind": "write_sentence", "prompt": "Use travel.", "word": "travel"}
    same = dict(base)
    changed_reference = {**base, "reference_answer": "I travel by bus."}

    first = library_ai._ai_grading_cache_key(base, "I travel by bus.", "English", "Uzbek", False)
    assert first == library_ai._ai_grading_cache_key(same, "I travel by bus.", "English", "Uzbek", False)
    assert first != library_ai._ai_grading_cache_key(changed_reference, "I travel by bus.", "English", "Uzbek", False)
    assert first != library_ai._ai_grading_cache_key(base, "I travel by bus.", "English", "Russian", False)


def test_ai_grading_cache_has_no_default_time_expiry():
    library_ai._AI_CHECK_CACHE.clear()
    key = "cache-without-time-expiry"
    library_ai._ai_grading_cache_put(key, "correct", {"score": 10.0}, now=100.0)

    assert library_ai._AI_CHECK_CACHE_TTL_SECONDS == 0.0
    assert library_ai._ai_grading_cache_get(key, now=10_000_000.0) == (
        "correct",
        {"score": 10.0},
    )


def test_ai_grading_cache_expires_and_never_returns_an_old_rubric_result(monkeypatch):
    monkeypatch.setattr(library_ai, "_AI_CHECK_CACHE_TTL_SECONDS", 5)
    library_ai._AI_CHECK_CACHE.clear()
    key = "cache-test"
    library_ai._ai_grading_cache_put(key, "correct", {"score": 10.0}, now=100.0)
    assert library_ai._ai_grading_cache_get(key, now=104.9) == ("correct", {"score": 10.0})
    assert library_ai._ai_grading_cache_get(key, now=105.0) is None


def test_ai_grading_coalesces_duplicate_provider_requests(monkeypatch):
    library_ai._AI_CHECK_CACHE.clear()
    library_ai._AI_CHECK_INFLIGHT.clear()
    calls = 0

    async def fake_provider(_: str) -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return '{"is_correct":true,"grammar_ok":true,"level_ok":true,"score":10,"feedback":"Correct."}'

    monkeypatch.setattr(library_ai, "_fast_ai_grading_request", fake_provider)
    question = {"kind": "write_sentence", "prompt": "Use travel correctly.", "word": "travel"}
    payload = library_ai.AiTestAnswerRequest(question_index=0, answer_text="We travel by bus.")

    async def run():
        return await asyncio.gather(
            library_ai._check_with_ai(question, payload, "English", "uz"),
            library_ai._check_with_ai(question, payload, "English", "uz"),
        )

    results = asyncio.run(run())
    assert calls == 1
    assert results[0][0] == results[1][0] == "correct"
