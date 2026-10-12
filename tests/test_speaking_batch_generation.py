from __future__ import annotations

import unittest
from pathlib import Path

from speaking_contract import individual_ai_topic_generation_count


class SpeakingBatchGenerationTests(unittest.TestCase):
    def test_splits_multi_topic_requests_into_individual_ai_generations(self) -> None:
        self.assertEqual(individual_ai_topic_generation_count(1), 0)
        self.assertEqual(individual_ai_topic_generation_count(2), 2)
        self.assertEqual(individual_ai_topic_generation_count(5), 5)

    def test_russian_generation_prompt_explicitly_forbids_model_answers(self) -> None:
        source = (Path(__file__).parents[1] / "backend" / "speaking_admin.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("НЕ генерируйте sample_answer", source)
        self.assertIn("Не пишите образец ответа", source)
