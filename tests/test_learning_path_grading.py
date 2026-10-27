"""Server-side Learning Path grading (stdlib only).

The pure grader in backend/personalization.py is executed in isolation via
``ast`` (the module itself needs FastAPI and a database).  Run with pytest or
``python3 tests/test_learning_path_grading.py``.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SOURCE_PATH = ROOT / "backend" / "personalization.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")

_PURE_PREFIXES = ("_learning_grade", "_LEARNING_GRADE")
_PURE_NAMES = {
    "_grade_learning_question", "_learning_question_needs_ai_check",
    "_normalize_learning_answer", "_learning_answer_matches", "_learning_token_key",
    "_learning_library_question", "_structured_string_list", "_normalize_learning_media_url",
    "_normalize_learning_media_payload", "_LEARNING_MEDIA_FIELDS", "_LEARNING_MEDIA_HOSTS",
    "_learning_exam_questions", "_learning_answer_fingerprint", "_learning_given_fingerprint",
    "_learning_lesson_submitted_answer", "_learning_exam_submitted_answers",
    "_parse_learning_exam_key", "_learning_exam_key", "_learning_track_exam_items",
    "lp_rewrite_sql", "_LP_TABLE_RE", "_LP_INDEX_RE", "LEARNING_PATH_TABLES",
    "SPEAKING_LP_TABLE_PREFIX", "_legacy_speaking_question_payload", "_LEGACY_SPEAKING_KIND_MAP",
}


class _HTTPException(Exception):
    def __init__(self, status_code: int = 500, detail: Any = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _wanted(name: str | None) -> bool:
    return bool(name) and (name in _PURE_NAMES or name.startswith(_PURE_PREFIXES))


def _load() -> dict[str, Any]:
    tree = ast.parse(SOURCE)
    selected: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _wanted(node.name):
            node.decorator_list = []
            selected.append(node)
        elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and _wanted(t.id) for t in node.targets):
            selected.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and _wanted(node.target.id):
            selected.append(node)
    names = {getattr(n, "name", None) or next((t.id for t in getattr(n, "targets", []) if isinstance(t, ast.Name)), None)
             or getattr(getattr(n, "target", None), "id", None) for n in selected}
    missing = {n for n in _PURE_NAMES if n not in names}
    assert not missing, f"personalization.py is missing {sorted(missing)}"
    namespace: dict[str, Any] = {
        "re": re, "json": json, "hashlib": hashlib, "Path": Path, "Any": Any,
        "urlparse": urlparse, "unquote": unquote, "HTTPException": _HTTPException,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE_PATH), "exec"), namespace)
    return namespace


NS = _load()
grade = NS["_grade_learning_question"]
library_question = NS["_learning_library_question"]
needs_ai = NS["_learning_question_needs_ai_check"]


def q(**raw: Any) -> dict[str, Any]:
    """A stored question exactly as the editor/AI pipelines save it."""
    question = library_question(raw)
    assert question, raw
    return question


def ok(question: dict[str, Any], given: Any, **kwargs: Any) -> bool:
    correct, total = grade(question, given, **kwargs)
    return total > 0 and correct == total


# --------------------------------------------------------------------------
# Choice kinds
# --------------------------------------------------------------------------

def test_multiple_choice():
    mc = q(kind="multiple_choice", prompt="2+2?", options=["3", "4", "5"], answer="4")
    assert ok(mc, "4") and ok(mc, {"text": "4"}) and ok(mc, 1)
    assert not ok(mc, "3") and not ok(mc, "") and not ok(mc, None)


def test_true_false_and_listening_tf():
    tf = q(kind="true_false", prompt="Sky is blue", answer=True)
    assert ok(tf, tf["options"][0]) and ok(tf, True) and ok(tf, "true")
    assert not ok(tf, tf["options"][1]) and not ok(tf, False)
    ltf = q(kind="listening_tf", prompt="Heard?", correct_index=2, audio_url="/homework/files/a.mp3")
    assert ok(ltf, "Not given") and not ok(ltf, "True") and not ok(ltf, False)


def test_listening_choice():
    listening = q(kind="listening", prompt="Which word?", options=["cat", "dog"], correct_index=1,
                  audio_url="/homework/files/a.mp3")
    assert ok(listening, "dog") and not ok(listening, "cat")


# --------------------------------------------------------------------------
# Free text kinds
# --------------------------------------------------------------------------

def test_gap_fill_and_fill_blank_accept_alternatives():
    gap = q(kind="gap_fill", prompt="___ your name?", answer="What's", accepted_answers=["What is"])
    assert ok(gap, "What is") and ok(gap, "what's") and ok(gap, ["What is"])
    assert not ok(gap, "Who is")
    blank = q(kind="fill_blank", prompt="I ___ a student.", answer="am")
    assert ok(blank, "am") and not ok(blank, "is")


def test_gap_fill_full_sentence_answer_and_multi_gap_sequence():
    gap = q(kind="gap_fill", prompt="She ___ to school.", answer="She goes to school.")
    assert ok(gap, "goes") and not ok(gap, "go")
    multi = q(kind="gap_fill", prompt="___ you ___ tea?", answer="Do ... like")
    assert ok(multi, ["Do", "like"]) and not ok(multi, ["Does", "like"])


def test_spelling_listening_gap_dictation():
    spelling = q(kind="spelling", word="beautiful (adj)")
    assert ok(spelling, "beautiful") and not ok(spelling, "beautifull")
    lgap = q(kind="listening_gap", prompt="I live in ___.", answer="London", audio_url="/homework/files/a.mp3")
    assert ok(lgap, "london") and not ok(lgap, "Paris")
    for kind in ("dictation", "listening_dictation"):
        item = q(kind=kind, prompt="Write what you hear", answer="I like apples.", audio_url="/homework/files/a.mp3")
        assert ok(item, "i like apples") and not ok(item, "I like oranges"), kind


def test_translation_is_deterministic_and_accepts_synonyms():
    tr = q(kind="translation", prompt="Translate: teacher", answer="o'qituvchi", accepted_answers=["muallim"])
    assert not needs_ai(tr)
    assert ok(tr, "muallim") and ok(tr, "O'qituvchi") and ok(tr, "o'qituvchi, muallim")
    assert not ok(tr, "teacher") and not ok(tr, "Translate: teacher")


# --------------------------------------------------------------------------
# Order / matching / cloze / sets
# --------------------------------------------------------------------------

def test_word_order_kinds():
    for kind in ("word_order", "scrambled_sentence", "listening_order"):
        item = q(kind=kind, answer="I am a student.", tokens=["student.", "am", "I", "a"])
        assert ok(item, "I am a student") and ok(item, ["I", "am", "a", "student."]), kind
        assert not ok(item, "am I a student"), kind


def test_matching_partial_credit_and_formats():
    matching = q(kind="matching", pairs=[{"left": "cat", "right": "mushuk"}, {"left": "dog", "right": "it"}])
    assert grade(matching, {"cat": "mushuk", "dog": "it"}) == (2, 2)
    assert grade(matching, {"cat": "it", "dog": "mushuk"}) == (0, 2)
    assert grade(matching, {"0::cat": "mushuk", "1::dog": "baliq"}) == (1, 2)
    assert grade(matching, [{"left": "cat", "right": "mushuk"}, {"left": "dog", "right": "it"}]) == (2, 2)
    assert grade(matching, "cat = mushuk | dog = it") == (2, 2)  # legacy string
    assert grade(matching, None) == (0, 2)


def test_passage_cloze():
    cloze = q(kind="passage_cloze", passage="I ___ tea and ___ coffee.",
              answers=[{"answer": "like", "accepted_answers": ["love"]}, "hate"])
    assert grade(cloze, ["love", "hate"]) == (2, 2)
    assert grade(cloze, ["like", "love"]) == (1, 2)
    assert grade(cloze, {"0": "like", "1": "hate"}) == (2, 2)
    assert grade(cloze, "1. like, 2. hate") == (2, 2)  # legacy web string
    assert grade(cloze, []) == (0, 2)


def test_reading_and_listening_sets():
    reading = q(kind="reading_set", passage="Tom has a red car.", questions=[
        {"type": "mcq", "prompt": "Colour?", "options": ["red", "blue"], "correct_index": 0},
        {"type": "short", "prompt": "Who?", "answer": "Tom"},
        {"type": "tf", "prompt": "Tom has a bike", "options": ["True", "False"], "answer": False},
    ])
    assert grade(reading, ["red", "tom", "False"]) == (3, 3)
    assert grade(reading, ["blue", "Tom", "True"]) == (1, 3)
    assert grade(reading, {"1": "red", "2": "Tom", "3": False}) == (3, 3)
    listening = q(kind="listening_set", audio_url="/homework/files/a.mp3",
                  sub_questions=[{"type": "gap", "prompt": "City?", "answer": "Paris"}])
    assert grade(listening, ["paris"]) == (1, 1) and grade(listening, ["Rome"]) == (0, 1)
    assert grade(listening, "1. Paris") == (1, 1)  # legacy "1. a | 2. b"


# --------------------------------------------------------------------------
# Vocabulary practice and AI-checked kinds
# --------------------------------------------------------------------------

def test_materialized_word_practice_variants():
    base = q(kind="word_practice", word="apple", translation_uz="olma")
    spelling = {**base, "kind": "spelling", "test_type": "spelling", "practice_mode": "spelling",
                "is_random_word_practice": True, "check": "auto", "answer": "apple",
                "correct_answer": "apple", "accepted_answers": ["apple"]}
    assert not needs_ai(spelling) and ok(spelling, "apple") and not ok(spelling, "aple")
    forward = {**base, "kind": "translation", "test_type": "translation", "practice_mode": "translation",
               "is_random_word_practice": True, "check": "auto", "answer": "olma",
               "correct_answer": "olma", "accepted_answers": ["olma"], "translation_uz": None}
    assert ok(forward, "olma") and not ok(forward, "apple")
    reverse = {**base, "kind": "translation", "test_type": "translation", "practice_mode": "translation",
               "is_random_word_practice": True, "check": "auto", "answer": "apple",
               "correct_answer": "apple", "accepted_answers": ["apple"], "translation": "olma"}
    # The reverse prompt shows the translation; copying it must not pass.
    assert ok(reverse, "apple") and not ok(reverse, "olma")
    sentence = {**base, "kind": "write_sentence", "practice_mode": "write_sentence", "check": "ai"}
    assert needs_ai(sentence) and not ok(sentence, "I eat an apple.")
    assert ok(sentence, "I eat an apple.", saved_ai_ok=True)
    # Unmaterialized vocabulary (final exam) is AI checked too.
    assert needs_ai(base)


def test_ai_checked_kinds_need_a_saved_verdict():
    for kind in ("speak_sentence", "write_sentence", "guided_writing", "reading_open", "read_aloud",
                 "paraphrase", "dialogue_completion", "picture_description", "listening_open", "open"):
        item = q(kind=kind, prompt="Task", reference_answer="Some answer")
        assert needs_ai(item), kind
        assert grade(item, {"text": "Some answer"}) == (0, 1), kind
        assert grade(item, {"text": "anything"}, saved_ai_ok=True) == (1, 1), kind


def test_question_without_any_key_is_ai_checked():
    keyless = {"kind": "gap_fill", "test_type": "gap_fill", "question": "Describe", "options": []}
    assert needs_ai(keyless) and grade(keyless, "x") == (0, 1)


def test_deterministic_kinds_never_need_ai():
    for item in (
        q(kind="multiple_choice", options=["a", "b"], answer="a"),
        q(kind="matching", pairs=[{"left": "a", "right": "b"}, {"left": "c", "right": "d"}]),
        q(kind="scrambled_sentence", answer="a b c"),
        q(kind="passage_cloze", passage="___", answers=["x"]),
        q(kind="reading_set", passage="p", questions=[{"type": "short", "answer": "x"}]),
    ):
        assert not needs_ai(item), item["test_type"]


# --------------------------------------------------------------------------
# Submit contracts
# --------------------------------------------------------------------------

def test_lesson_submit_contract_new_and_legacy():
    read = NS["_learning_lesson_submitted_answer"]
    assert read([{"answer": {"cat": "mushuk"}}]) == ({"cat": "mushuk"}, False)
    assert read([{"answer": {"text": "Hi", "audio_url": "/homework/voices/x.m4a"}}])[1] is False
    assert read([{"question": "Q", "selected": "4", "correct": True}]) == ("4", True)
    assert read(["4"]) == ("4", True)
    assert read([]) == (None, True)


def test_answer_fingerprint_matches_check_ai_inputs():
    fp = NS["_learning_answer_fingerprint"]
    given_fp = NS["_learning_given_fingerprint"]
    assert fp("I  like Tea", None) == given_fp({"text": "i like tea"})
    assert fp("", "/homework/voices/aitest_voice_5_1.m4a") == given_fp(
        {"audio_url": "https://diamond-education.uz/api/homework/voices/aitest_voice_5_1.m4a", "text": "whatever"})
    assert fp("a") != fp("b")
    assert given_fp({"text": " "}) is None and given_fp("") is None


def test_exam_keys_are_stable_and_legacy_submits_are_detected():
    parse = NS["_parse_learning_exam_key"]
    assert NS["_learning_exam_key"](12, 3) == "12:3" and parse("12:3") == (12, 3)
    assert parse("12") is None and parse("a:b") is None
    read = NS["_learning_exam_submitted_answers"]
    assert read({"1:0": "x", "bad": "y"}) == {"1:0": "x"}
    assert read([{"exam_key": "1:0", "answer": "x"}, {"exam_key": "2:1", "answer": ["a"]}]) == {"1:0": "x", "2:1": ["a"]}
    assert read([{"question": "Q", "selected": "x", "correct": True}]) is None
    assert read([]) == {}
    rows = [
        {"lesson_id": 7, "question_payload_json": json.dumps({"kind": "reading_set", "passage": "p",
            "questions": [{"type": "short", "answer": "a"}, {"type": "short", "answer": "b"}]})},
        {"lesson_id": 8, "question_payload_json": json.dumps({"kind": "multiple_choice", "options": ["x", "y"], "answer": "y"})},
    ]
    keys = [NS["_learning_exam_key"](row["lesson_id"], sub) for _, row, sub, _q in NS["_learning_track_exam_items"](rows)]
    assert keys == ["7:0", "7:1", "8:0"]


def test_score_is_never_read_from_the_client():
    submit = SOURCE.split("async def submit_learning_lesson(", 1)[1].split("\n@router.", 1)[0]
    assert "payload.score" not in submit
    assert "_grade_learning_question(question, given" in submit
    assert "_materialize_lesson_word_practice(" in submit
    final = SOURCE.split("async def submit_track_final_exam(", 1)[1].split("\n@router.", 1)[0]
    assert "float(payload.score" not in final
    assert "_grade_learning_question(question, given" in final
    assert "app_update_required" in final
    lesson_get = SOURCE.split("async def student_learning_lesson(", 1)[1].split("\n@router.", 1)[0]
    assert "_materialize_lesson_word_practice(" in lesson_get


def test_check_ai_uses_stored_payload_persists_and_has_no_fake_fallback():
    body = SOURCE.split("async def check_learning_lesson_ai(", 1)[1].split("\n@router.", 1)[0]
    assert "qp = {**qp, **payload.question_payload}" not in body
    assert "_learning_record_answer_check(" in body
    assert "_learning_owned_audio_path(" in body
    assert "status_code=503" in body
    assert "ans_norm in ref" not in body and "Javob qabul qilindi" not in body
    assert "learning_answer_checks" in SOURCE and "consumed_at" in SOURCE


# --------------------------------------------------------------------------
# Speaking namespace SQL rewrite and legacy migration payloads
# --------------------------------------------------------------------------

def test_speaking_namespace_rewrites_only_learning_path_tables():
    rewrite = NS["lp_rewrite_sql"]
    sql = ("SELECT * FROM learning_module_lessons l JOIN learning_modules m ON m.id=l.module_id "
           "JOIN learning_tracks t ON t.id=m.track_id JOIN users u ON u.id=t.owner_id "
           "LEFT JOIN certificates c ON c.user_id=u.id WHERE learning_module_progress.status='passed'")
    out = rewrite(sql)
    for table in ("learning_module_lessons", "learning_modules", "learning_tracks", "learning_module_progress"):
        assert f"speaking_lp_{table}" in out
    assert " users u" in out and " certificates c" in out and "speaking_lp_users" not in out
    assert "speaking_lp_speaking_lp_" not in out
    idx = rewrite("CREATE INDEX IF NOT EXISTS idx_learning_tracks_owner ON learning_tracks(owner_id)")
    assert idx == "CREATE INDEX IF NOT EXISTS idx_speaking_lp_learning_tracks_owner ON speaking_lp_learning_tracks(owner_id)"
    assert rewrite("idx_track_final_progress ON learning_track_final_progress") == (
        "idx_speaking_lp_track_final_progress ON speaking_lp_learning_track_final_progress")
    # Legacy speaking_learning_* tables and unrelated tables are untouched.
    assert rewrite("speaking_learning_tracks learning_bookmarks diamond_history") == (
        "speaking_learning_tracks learning_bookmarks diamond_history")
    for table in NS["LEARNING_PATH_TABLES"]:
        assert rewrite(f"FROM {table} x") == f"FROM speaking_lp_{table} x"


def test_legacy_speaking_questions_become_gradable_lessons():
    convert = NS["_legacy_speaking_question_payload"]

    def row(kind, prompt, options=None, answer=None, data=None):
        return {"question_type": kind, "prompt": prompt, "options_json": json.dumps(options or []),
                "answer_json": json.dumps(answer), "data_json": json.dumps(data or {}), "explanation": ""}

    mc = convert(row("multiple_choice", "2+2?", ["3", "4"], "4"))
    assert mc["test_type"] == "multiple_choice" and ok(mc, "4") and not ok(mc, "3")
    tf = convert(row("true_false", "Sky is blue", answer=True))
    assert ok(tf, True) and not ok(tf, False)
    match = convert(row("matching", "Match", answer={"cat": "mushuk"}, data={"pairs": [{"left": "cat", "right": "mushuk"}, {"left": "dog", "right": "it"}]}))
    assert grade(match, {"cat": "mushuk", "dog": "it"}) == (2, 2)
    cloze = convert(row("passage_cloze", "I ___ tea, ___ coffee", answer=["like", ["hate", "dislike"]]))
    assert cloze["test_type"] == "passage_cloze" and grade(cloze, ["like", "dislike"]) == (2, 2)
    reading = convert(row("reading_set", "Read", answer={"0": "Tom"}, data={"passage": "Tom ran.", "sub_questions": [{"type": "short", "prompt": "Who?"}]}))
    assert grade(reading, ["tom"]) == (1, 1)
    speak = convert(row("speaking_response", "Talk about your day", answer="I woke up early."))
    assert speak["test_type"] == "speak_sentence" and needs_ai(speak)
    short = convert(row("short_answer", "Capital of France?", answer="Paris", data={"accepted_answers": ["paris city"]}))
    assert short["test_type"] == "gap_fill" and ok(short, "paris city")


if __name__ == "__main__":
    import traceback

    failures = 0
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
        except Exception:  # noqa: BLE001 - report every failing case
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
        else:
            print(f"ok   {name}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
