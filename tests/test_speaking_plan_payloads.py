"""Exercise the production sanitizer without importing the application server."""
import ast
import hashlib
import random
import unittest
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / "backend/speaking_plans.py"
tree = ast.parse(SOURCE.read_text())
names = {"_text", "clean_question", "clean_questions"}
scope = {"Any": Any, "hashlib": hashlib, "random": random,
         "PLAN_KINDS": {"multiple_choice", "true_false", "gap_fill", "word_order", "matching",
                        "write_sentence", "paraphrase", "guided_writing", "speak_sentence", "read_aloud"}}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                             and n.name in names], type_ignores=[]), str(SOURCE), "exec"), scope)
clean = scope["clean_question"]


class PlanPayloadTests(unittest.TestCase):
    def test_required_word_is_never_invisible(self):
        self.assertIsNone(clean({"kind": "write_sentence", "question": "Use the given word.",
                                 "reference_answer": "I enjoy travelling."}, "english"))

    def test_target_word_alias_is_preserved(self):
        q = clean({"kind": "write_sentence", "question": "Use the given word.",
                   "target_word": "enjoy", "reference_answer": "I enjoy travelling."}, "english")
        self.assertEqual(q["word"], "enjoy")

    def test_paraphrase_keeps_source_not_model_answer(self):
        q = clean({"kind": "paraphrase", "question": "Перефразируйте предложение.",
                   "source_sentence": "Я люблю читать.", "reference_answer": "Мне нравится чтение."}, "russian")
        self.assertEqual(q["passage"], "Я люблю читать.")
        self.assertNotIn(q["reference_answer"], q["question"])

    def test_guided_writing_preserves_context_and_limit(self):
        q = clean({"kind": "guided_writing", "question": "Describe this situation.",
                   "context": "You missed the train.", "word_count": 40,
                   "reference_answer": "I asked for help."}, "english")
        self.assertEqual(q["passage"], "You missed the train.")
        self.assertEqual(q["word_count"], 40)

    def test_russian_fallback_instructions(self):
        q = clean({"kind": "word_order", "correct_answer": "Я люблю читать книги"}, "russian")
        self.assertEqual(q["question"], "Расставьте слова в правильном порядке.")

    def test_read_aloud_exposes_text_and_audio_input(self):
        q = clean({"kind": "read_aloud", "question": "Read aloud.",
                   "reference_answer": "The train leaves soon."}, "english")
        self.assertEqual(q["passage"], "The train leaves soon.")
        self.assertEqual(q["input"], "audio")

    def test_existing_objective_questions_remain_valid(self):
        cases = [
            {"kind": "multiple_choice", "question": "Choose.", "options": ["a", "b", "c"], "correct_answer": "b"},
            {"kind": "true_false", "question": "Это верно?", "correct_answer": False},
            {"kind": "gap_fill", "question": "Я ___ дома.", "correct_answer": "живу"},
            {"kind": "matching", "pairs": [{"left": "a", "right": "1"}, {"left": "b", "right": "2"}, {"left": "c", "right": "3"}]},
        ]
        for raw in cases:
            with self.subTest(kind=raw["kind"]):
                self.assertIsNotNone(clean(raw, "russian"))


if __name__ == "__main__":
    unittest.main()
