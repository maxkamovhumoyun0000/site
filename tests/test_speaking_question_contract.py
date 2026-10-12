from __future__ import annotations

import unittest
from types import SimpleNamespace

from speaking_contract import (
    cue_card_bullets_are_open_ended,
    is_safe_speaking_vocabulary_query,
    is_speaking_app_account,
    minimum_questions_for_requested_limit,
    normalize_speaking_link_code,
    normalize_speaking_email,
    speaking_account_state_label,
    normalize_speaking_voice_guest_name,
    speaking_voice_guest_identity,
    session_replacements_for_login,
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

    def test_vocabulary_lookup_rejects_18_plus_queries_before_ai_can_receive_them(self) -> None:
        self.assertTrue(is_safe_speaking_vocabulary_query("resilient"))
        self.assertFalse(is_safe_speaking_vocabulary_query("pornography"))
        self.assertFalse(is_safe_speaking_vocabulary_query("секс"))

    def test_voice_room_guest_identity_is_stable_without_exposing_device_id(self) -> None:
        raw_device_id = "speaking-device-1234567890"

        identity = speaking_voice_guest_identity(raw_device_id)

        self.assertTrue(identity.startswith("guest-"))
        self.assertNotIn(raw_device_id, identity)
        self.assertEqual(identity, speaking_voice_guest_identity(raw_device_id))
        self.assertIsNone(speaking_voice_guest_identity("short"))

    def test_voice_room_guest_name_removes_controls_and_uses_a_fallback(self) -> None:
        self.assertEqual(
            normalize_speaking_voice_guest_name("  Dilnoza\n\t "),
            "Dilnoza",
        )
        self.assertEqual(normalize_speaking_voice_guest_name("\x00 \t"), "Speaking learner")

    def test_speaking_accounts_are_explicitly_marked_for_admin_list_isolation(self) -> None:
        self.assertTrue(is_speaking_app_account(1))
        self.assertTrue(is_speaking_app_account("true"))
        self.assertFalse(is_speaking_app_account(0))

    def test_ten_is_a_generation_cap_with_four_questions_as_the_batch_minimum(self) -> None:
        self.assertEqual(minimum_questions_for_requested_limit(10), 4)
        self.assertEqual(minimum_questions_for_requested_limit(4), 4)
        self.assertEqual(minimum_questions_for_requested_limit(3), 3)

    def test_batch_targets_vary_without_exceeding_the_requested_cap(self) -> None:
        targets = variable_batch_question_targets(10, 5, "English|2|Travel")

        self.assertEqual(len(targets), 5)
        self.assertTrue(all(4 <= count <= 10 for count in targets))
        self.assertGreater(len(set(targets)), 1)

    def test_session_limit_requires_the_learner_to_select_a_real_old_device(self) -> None:
        active = [
            {"session_id": "student-phone", "device_id": "phone-a"},
            {"session_id": "student-tablet", "device_id": "tablet-b"},
            {"session_id": "speaking-phone", "device_id": "phone-c"},
        ]

        self.assertEqual(
            session_replacements_for_login(
                active,
                limit=3,
                device_id="new-phone",
                requested_session_ids=["student-tablet"],
            ),
            ("student-tablet",),
        )
        with self.assertRaises(ValueError):
            session_replacements_for_login(
                active,
                limit=3,
                device_id="new-phone",
                requested_session_ids=["not-this-users-session"],
            )

    def test_session_limit_reuses_the_same_device_without_prompting_for_another(self) -> None:
        active = [
            {"session_id": "old-speaking", "device_id": "same-device"},
            {"session_id": "student-phone", "device_id": "phone-a"},
            {"session_id": "student-tablet", "device_id": "tablet-b"},
        ]

        self.assertEqual(
            session_replacements_for_login(
                active,
                limit=3,
                device_id="same-device",
                requested_session_ids=[],
            ),
            ("old-speaking",),
        )

    def test_student_app_link_code_is_canonical_and_rejects_unsafe_input(self) -> None:
        self.assertEqual(normalize_speaking_link_code(' speak-ab12cd34 '), 'SPEAK-AB12CD34')
        with self.assertRaises(ValueError):
            normalize_speaking_link_code('SPEAK-<script>')

    def test_speaking_email_is_normalized_and_deleted_accounts_are_labeled_inactive(self) -> None:
        self.assertEqual(normalize_speaking_email(' Learner@Example.COM '), 'learner@example.com')
        self.assertEqual(speaking_account_state_label('2026-10-12T00:00:00Z'), 'inactive')
        self.assertEqual(speaking_account_state_label(None), 'active')
