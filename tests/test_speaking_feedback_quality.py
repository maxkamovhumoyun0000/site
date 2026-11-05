"""Check scoring normalization and prompt requirements without AI calls."""
import ast
import math
import re
import unittest
from pathlib import Path
from typing import Any

path = Path(__file__).resolve().parents[1] / 'backend/speaking_answers.py'
tree = ast.parse(path.read_text())
names = {'round_half', '_clamp', '_clean_list', 'normalize_ai_result', '_scoring_prompt', '_normalize_silence_transcript'}
scope = {'Any': Any, 'math': math, 're': re, 'CRITERIA': ('fluency', 'vocabulary', 'grammar', 'pronunciation')}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[]), str(path), 'exec'), scope)


class SpeakingFeedbackQualityTest(unittest.TestCase):
    def test_silence_marker_does_not_treat_real_speech_as_empty(self):
        self.assertEqual(scope['_normalize_silence_transcript']('[BLANK_AUDIO]'), '')
        self.assertEqual(scope['_normalize_silence_transcript']('(silence)'), '')
        self.assertEqual(scope['_normalize_silence_transcript']('I enjoy silence.'), 'I enjoy silence.')

    def test_all_feedback_is_preserved_and_no_rewrite_is_returned(self):
        errors = [{'original': str(i), 'correction': 'fixed'} for i in range(12)]
        result = scope['normalize_ai_result']({'grammar_errors': errors, 'vocabulary_suggestions': errors,
                                                'improved_answer': 'unwanted'}, scale='ielts')
        self.assertEqual(len(result['grammar_errors']), 12)
        self.assertEqual(len(result['vocabulary_suggestions']), 12)
        self.assertNotIn('improved_answer', result)
        self.assertEqual(result['score'], 0)

    def test_prompt_forbids_rewrite_and_does_not_limit_to_two(self):
        system, _ = scope['_scoring_prompt'](scale='ielts', part=1, topic='', prompt='', bullets='',
                                             transcript='hello', duration=10, word_count=1, result_language='English')
        self.assertIn('all meaningful distinct grammar errors', system)
        self.assertIn('Do not rewrite the full answer', system)
        self.assertNotIn('At most 4 grammar errors', system)


if __name__ == '__main__':
    unittest.main()
