from __future__ import annotations

import unittest

from speaking_contract import normalize_batch_topic_count


class SpeakingBatchContractTests(unittest.TestCase):
    def test_allows_a_safe_batch_of_topics(self) -> None:
        self.assertEqual(normalize_batch_topic_count(1), 1)
        self.assertEqual(normalize_batch_topic_count("5"), 5)

    def test_rejects_out_of_range_or_invalid_topic_counts(self) -> None:
        for count in (0, 6, "many", True):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    normalize_batch_topic_count(count)

