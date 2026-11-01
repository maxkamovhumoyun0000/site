import unittest

import gamified_tests


class GamifiedQuestionUniquenessTests(unittest.TestCase):
    def test_generated_vocab_is_not_reused_within_one_attempt(self):
        vocab = [
            {
                "word": f"word{index}",
                "tr": f"tarjima{index}",
                "ex": f"I can use word{index} today",
            }
            for index in range(24)
        ]
        readings = [
            {
                "passage": f"Fresh passage number {index} about learning.",
                "question": f"What is passage {index} about?",
                "options": [f"learning {index}", "sports", "music", "travel"],
                "answer_index": 0,
            }
            for index in range(3)
        ]
        questions = gamified_tests.build_questions(
            "English", level="B1", count=20, vocab=vocab, ai_readings=readings
        )

        source_words = []
        for question in questions:
            if question.get("type") == "word_match":
                source_words.extend((question.get("_answer") or {}).keys())
            elif question.get("_source_word"):
                source_words.append(question["_source_word"])

        self.assertEqual(sum(gamified_tests._score_units(q) for q in questions), 20)
        self.assertEqual(len(source_words), len(set(source_words)))

    def test_public_questions_hide_answer_and_internal_source(self):
        public = gamified_tests.public_question({
            "index": 0,
            "type": "mcq",
            "prompt": "Question?",
            "options": ["A", "B"],
            "_answer": 0,
            "_source_word": "private-source",
        })
        self.assertNotIn("_answer", public)
        self.assertNotIn("_source_word", public)


if __name__ == "__main__":
    unittest.main()
