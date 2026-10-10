from __future__ import annotations

import unittest
from types import SimpleNamespace

from speaking_contract import question_insert_values_for_topic


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
