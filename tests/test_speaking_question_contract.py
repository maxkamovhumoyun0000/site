from __future__ import annotations

import unittest
from types import SimpleNamespace

from speaking_contract import (
    cue_card_bullets_are_open_ended,
    minimum_questions_for_requested_limit,
    variable_batch_question_targets,
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

    def test_part_two_cue_cards_reject_pre_written_answer_details(self) -> None:
        generic = [
            "The key details you would include in your description",
            "When and where it happened, or how you know about it",
            "The people, events or features that are relevant to you",
            "And explain why it was important or memorable to you",
        ]
        pre_written = [
            "Talk about your friend Alex in London",
            "Explain why he bought the red bicycle in 2024",
            "Describe what happened at the party",
            "Say why the experience mattered",
        ]

        self.assertTrue(cue_card_bullets_are_open_ended(generic))
        self.assertFalse(cue_card_bullets_are_open_ended(pre_written))

    def test_ten_is_a_generation_cap_with_four_questions_as_the_batch_minimum(self) -> None:
        self.assertEqual(minimum_questions_for_requested_limit(10), 4)
        self.assertEqual(minimum_questions_for_requested_limit(4), 4)
        self.assertEqual(minimum_questions_for_requested_limit(3), 3)

    def test_batch_targets_vary_without_exceeding_the_requested_cap(self) -> None:
        targets = variable_batch_question_targets(10, 5, "English|2|Travel")

        self.assertEqual(len(targets), 5)
        self.assertTrue(all(4 <= count <= 10 for count in targets))
        self.assertGreater(len(set(targets)), 1)
