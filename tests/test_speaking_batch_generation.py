from __future__ import annotations

import unittest

from speaking_contract import individual_ai_topic_generation_count


class SpeakingBatchGenerationTests(unittest.TestCase):
    def test_splits_multi_topic_requests_into_individual_ai_generations(self) -> None:
        self.assertEqual(individual_ai_topic_generation_count(1), 0)
        self.assertEqual(individual_ai_topic_generation_count(2), 2)
        self.assertEqual(individual_ai_topic_generation_count(5), 5)
