from __future__ import annotations

import unittest

from speaking_contract import (
    MAX_CATALOG_TOPIC_COUNT,
    normalize_catalog_question_target,
    normalize_catalog_topic_titles,
)


class SpeakingCustomCatalogContractTests(unittest.TestCase):
    def test_accepts_an_exact_question_target(self) -> None:
        self.assertEqual(
            normalize_catalog_question_target("exact", exact_count=12),
            (12, 12),
        )

    def test_accepts_a_minimum_to_maximum_question_target(self) -> None:
        self.assertEqual(
            normalize_catalog_question_target(
                "range", minimum_count=4, maximum_count=9
            ),
            (4, 9),
        )

    def test_rejects_invalid_question_target_ranges(self) -> None:
        with self.assertRaises(ValueError):
            normalize_catalog_question_target("range", minimum_count=10, maximum_count=4)
        with self.assertRaises(ValueError):
            normalize_catalog_question_target("exact", exact_count=0)

    def test_keeps_at_most_thirty_distinct_topic_titles(self) -> None:
        self.assertEqual(
            normalize_catalog_topic_titles(["Travel", " travel ", "Food"]),
            ("Travel", "Food"),
        )
        with self.assertRaises(ValueError):
            normalize_catalog_topic_titles(
                [f"Topic {index}" for index in range(MAX_CATALOG_TOPIC_COUNT + 1)]
            )
