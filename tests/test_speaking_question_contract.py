from __future__ import annotations

import unittest
from types import SimpleNamespace

from speaking_contract import (
    minimum_questions_for_requested_limit,
    part_two_cue_card_fallback,
    public_sample_answer,
    question_insert_values_for_topic,
)


class SpeakingQuestionContractTests(unittest.TestCase):
    def test_question_insert_uses_its_parent_topics_part_and_subject(self) -> None:
        payload = SimpleNamespace(
            part=3,
            subject="russian",
            question_text="What do you enjoy learning?",
            sample_answer="I enjoy learning languages.",
            cue_card_bullet_points=["Unexpected client value"],
            examiner_tip=None,
            vocabulary=[],
            sort_order=0,
        )

        values = question_insert_values_for_topic(
            payload,
            {"part": 1, "subject": "english"},
        )

        self.assertEqual(values["part"], 1)
        self.assertEqual(values["subject"], "english")
        self.assertEqual(values["cue_card_bullet_points"], [])

    def test_question_insert_normalizes_a_blank_optional_sample_answer(self) -> None:
        payload = SimpleNamespace(
            question_text="Tell me about your home.",
            sample_answer="   ",
            cue_card_bullet_points=[],
            examiner_tip=None,
            vocabulary=[],
            sort_order=0,
        )

        values = question_insert_values_for_topic(payload, {"part": 2, "subject": "english"})

        self.assertEqual(values["sample_answer"], "Sample answer to be reviewed.")

    def test_russian_question_keeps_sample_answer_empty(self) -> None:
        payload = SimpleNamespace(
            question_text="Расскажите о своём хобби.",
            sample_answer="",
            cue_card_bullet_points=[],
            examiner_tip=None,
            vocabulary=[],
            sort_order=0,
        )

        values = question_insert_values_for_topic(payload, {"part": 1, "subject": "russian"})

        self.assertEqual(values["sample_answer"], "")

    def test_public_russian_question_never_exposes_a_legacy_sample_answer(self) -> None:
        self.assertEqual(
            public_sample_answer("Legacy answer that must stay private", "russian"),
            "",
        )
        self.assertEqual(
            public_sample_answer("English model answer", "english"),
            "English model answer",
        )

    def test_part_two_fallback_bullets_are_question_specific_and_complete(self) -> None:
        travel = part_two_cue_card_fallback("Describe a memorable journey you took.")
        teacher = part_two_cue_card_fallback("Describe a teacher who influenced you.")

        self.assertEqual(len(travel), 4)
        self.assertEqual(len(teacher), 4)
        self.assertNotEqual(travel, teacher)
        self.assertIn("memorable journey you took", travel[0])
        self.assertIn("teacher who influenced you", teacher[0])

    def test_ten_is_a_generation_cap_with_four_questions_as_the_batch_minimum(self) -> None:
        self.assertEqual(minimum_questions_for_requested_limit(10), 4)
        self.assertEqual(minimum_questions_for_requested_limit(4), 4)
        self.assertEqual(minimum_questions_for_requested_limit(3), 3)
