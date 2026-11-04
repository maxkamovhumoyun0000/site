"""Exercise the production sanitizer without importing the application server."""
import ast
import asyncio
import hashlib
import json
import random
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / "backend/speaking_plans.py"
tree = ast.parse(SOURCE.read_text())
names = {"_text", "_json_list", "clean_question", "clean_questions", "_preparation_summary", "generate_test"}
scope = {"Any": Any, "hashlib": hashlib, "random": random, "json": json,
         "datetime": datetime, "timezone": timezone,
         "PLAN_KINDS": {"multiple_choice", "true_false", "gap_fill", "word_order", "matching",
                        "write_sentence", "paraphrase", "guided_writing", "speak_sentence", "read_aloud"}}
scope.update(QUESTIONS_PER_TEST=10)
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                             and n.name in names], type_ignores=[]), str(SOURCE), "exec"), scope)
clean = scope["clean_question"]


class PlanPayloadTests(unittest.TestCase):
    def test_progress_counts_persisted_ready_days_only(self):
        summarize = scope['_preparation_summary']
        days = [{'prepared_json': '[{}]'}, {'prepared_json': '[]'}, {'prepared_json': None}]
        self.assertEqual(summarize({'preparation_status': 'preparing'}, days)['percent'], 33)
        self.assertEqual(summarize({'preparation_status': 'failed'}, days)['ready_days'], 1)
        self.assertEqual(summarize({'preparation_status': 'ready'}, days)['percent'], 33)
        resumed = summarize({'preparation_status': 'preparing', 'preparation_lease_until':
                             datetime.now(timezone.utc) - timedelta(seconds=1)}, days)
        self.assertEqual(resumed['status'], 'pending')
        self.assertTrue(resumed['resume_needed'])

    def test_short_generated_test_is_rejected(self):
        class HttpError(Exception):
            def __init__(self, **kwargs):
                super().__init__(kwargs['detail'])
        async def short_output(*args, **kwargs):
            return {'questions': [{'kind': 'gap_fill', 'question': f'I ___ item {i}.',
                                    'correct_answer': 'like'} for i in range(5)]}
        scope.update(HTTPException=HttpError, _ai_json=short_output,
                     generation_prompt=lambda *a: ('system', 'user'))
        with self.assertRaises(HttpError):
            asyncio.run(scope['generate_test']('english', 'grammar_accuracy', '6.0'))

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
