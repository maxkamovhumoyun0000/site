from backend.speaking_learning import (
    QUESTION_TYPES,
    _answer_hash,
    _grade_submission,
    _is_correct,
    _public_data,
)


def test_speaking_path_accepts_rich_test_types_without_student_tables():
    assert {"matching", "word_order", "listening_gap", "speaking_response"} <= QUESTION_TYPES


def test_speaking_learning_grades_case_insensitive_and_compact_answers():
    assert _is_correct("short_answer", "Hello there", "  HELLO   THERE ", {})
    assert _is_correct("word_order", "I like speaking", "i  like speaking!", {})
    assert _is_correct("fill_blank", ["went", "home"], ["went", "home"], {})


def test_speaking_learning_grades_pair_matching_and_accepted_variants():
    expected = {"cat": "кот", "dog": "собака"}
    assert _is_correct("matching", expected, {"cat": "КОТ", "dog": "собака"}, {})
    assert _is_correct("short_answer", "color", "colour", {"accepted_answers": ["colour", "hue"]})


def test_speaking_learning_grades_question_sets_and_hides_embedded_answer_keys():
    assert _is_correct("reading_set", {"a": "yes", "b": "no"}, {"a": "yes", "b": "no"}, {})
    public = _public_data({"passage": "Text", "sub_questions": [{"prompt": "Q", "correct_answer": "hidden"}]})
    assert public == {"passage": "Text", "sub_questions": [{"prompt": "Q"}]}


def test_ai_checked_answer_is_only_counted_when_server_verified_same_payload():
    answer = {"audio_url": "/homework/voices/speaking_lp_voice_8_sample.m4a"}
    verified = (_answer_hash(answer), {"correct": True, "correct_count": 1, "total": 1})
    assert _grade_submission("speak_sentence", "Reference", answer, {}, verified) == (1, 1)
    assert _grade_submission("speak_sentence", "Reference", {"audio_url": "other"}, {}, verified) == (0, 1)


def test_answer_hash_is_stable_for_mapping_key_order():
    assert _answer_hash({"left": "one", "right": "two"}) == _answer_hash(
        {"right": "two", "left": "one"}
    )
