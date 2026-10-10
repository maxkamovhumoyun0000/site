from __future__ import annotations

import unittest

from speaking_contract import normalize_topic_status


class SpeakingTopicStatusContractTests(unittest.TestCase):
    def test_normalizes_supported_topic_statuses(self) -> None:
        self.assertEqual(normalize_topic_status(" common "), "COMMON")
        self.assertEqual(normalize_topic_status("predicted"), "PREDICTED")
        self.assertEqual(normalize_topic_status("High Frequency"), "HIGH FREQUENCY")

    def test_rejects_unknown_topic_statuses(self) -> None:
        with self.assertRaises(ValueError):
            normalize_topic_status("CONVERSATIONAL")

