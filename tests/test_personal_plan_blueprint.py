"""Unit checks for the plan's untrusted AI output, without a live provider."""
import ast
import hashlib
import json
import unittest
import logging
from pathlib import Path
from typing import Any

path = Path(__file__).resolve().parents[1] / 'backend/speaking_plan_preparation.py'
tree = ast.parse(path.read_text())
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_validated_blueprint')
fingerprints = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_question_fingerprints')
scope = {'hashlib': hashlib, 'json': json}
exec(compile(ast.Module(body=[fn, fingerprints], type_ignores=[]), str(path), 'exec'), scope)
validate = scope['_validated_blueprint']
plan_path = path.with_name('speaking_plans.py')
plan_tree = ast.parse(plan_path.read_text())
functions = [n for n in plan_tree.body if isinstance(n, ast.FunctionDef) and n.name in {'_text', '_learner_activity'}]
collector = {'Any': Any, 'logging': logging, 'logger': logging.getLogger(__name__)}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(plan_path), 'exec'), collector)


class PersonalPlanBlueprintTest(unittest.TestCase):
    def test_repeated_questions_have_same_fingerprint(self):
        first = {'kind': 'gap_fill', 'question': 'I ___ home.', 'correct_answer': 'went'}
        second = {'kind': 'gap_fill', 'question': 'I ___ home.', 'correct_answer': 'went'}
        self.assertEqual(scope['_question_fingerprints']([first]), scope['_question_fingerprints']([second]))

    def test_every_activity_query_is_scoped_to_user_and_subject(self):
        class Cursor:
            calls = []
            def execute(self, sql, params=None):
                if params is not None:
                    self.calls.append((sql, params))
            def fetchall(self):
                return []
        cur = Cursor()
        collector['_learner_activity'](cur, 123, 'russian')
        self.assertEqual(len(cur.calls), 8)
        for sql, params in cur.calls:
            self.assertIn('user_id', sql.replace('student_id', 'user_id'))
            self.assertEqual(params, (123, 'russian'))

    def test_only_real_sources_are_exposed(self):
        days = [{'day_index': 1}]
        data = [{'day_index': 1, 'focus': 'grammar', 'activities': [
            {'type': 'notebook', 'instruction': 'Review your word'},
            {'type': 'saved_questions', 'instruction': 'Review a saved question'},
        ]}]
        result = validate(data, days, {'notebook': [{'term': 'test'}]}, ['grammar'])
        self.assertEqual([x['type'] for x in result[1]['activities']], ['notebook'])

    def test_missing_or_duplicate_days_are_rejected(self):
        entry = {'day_index': 1, 'focus': 'grammar', 'activities': [{'type': 'practice', 'instruction': 'Practise'}]}
        with self.assertRaises(ValueError):
            validate([entry, entry], [{'day_index': 1}, {'day_index': 2}], {}, ['grammar'])


if __name__ == '__main__':
    unittest.main()
