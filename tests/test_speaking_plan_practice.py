"""Exercise the practice-check route's ownership and AI-verdict contract."""
import ast
import asyncio
import hashlib
import json
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

source = Path(__file__).resolve().parents[1] / 'backend/speaking_plans.py'
tree = ast.parse(source.read_text())
selected = []
for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
        '_json_list', '_attempt', '_attempt_question', 'check_plan_practice_answer'
    }:
        node.decorator_list = []
        node.returns = None
        for arg in [*node.args.args, *node.args.kwonlyargs]:
            arg.annotation = None
        node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
        selected.append(node)


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        super().__init__(detail)


state = {}


class Cursor:
    def execute(self, sql, params):
        self.sql, self.params = sql, params

    def fetchone(self):
        if 'FROM speaking_plan_attempts' in self.sql:
            return state['attempt'] if self.params == (15, 7) else None
        if 'speaking_plan_answer_checks' in self.sql:
            return state.get('check')
        raise AssertionError(self.sql)

    def close(self):
        pass


class Connection:
    def cursor(self):
        return Cursor()

    def close(self):
        pass


def fingerprint(answer):
    return hashlib.sha256(str(answer).casefold().encode()).hexdigest()


personalization = types.ModuleType('backend.personalization')
personalization._learning_given_fingerprint = fingerprint
personalization._learning_question_needs_ai_check = lambda q: q['kind'] == 'write_sentence'
personalization._learning_owned_audio_path = lambda url, uid: None
personalization._grade_learning_question = lambda q, a, saved_ai_ok=False: (
    int(saved_ai_ok if q['kind'] == 'write_sentence' else a == q['correct_answer']), 1)

speaking_subscriptions = types.ModuleType('backend.speaking_subscriptions')
speaking_subscriptions.require_feature = lambda user, feature: {'allowed': True}
backend_package = types.ModuleType('backend')
backend_package.__path__ = []

scope = {'get_conn': Connection, 'HTTPException': HttpError, 're': re, 'json': json,
         '_auth': lambda authorization, roles: ({'id': state['user_id']}, 'speaking_user'),
         '_require_plan_subject': lambda user, subject: None,
         'ensure_tables': lambda: None, 'USER_ROLES': {'speaking_user'}, 'PASSING_SCORE': 60}
exec(compile(ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])), str(source), 'exec'), scope)


class PracticeCheckTests(unittest.TestCase):
    def setUp(self):
        state.clear()
        state.update(user_id=7, attempt={'id': 15, 'status': 'started', 'questions_json': json.dumps([
            {'kind': 'multiple_choice', 'correct_answer': 'Yes'},
            {'kind': 'write_sentence', 'word': 'enjoy'}])})

    def run_check(self, key, answer):
        with patch.dict(sys.modules, {
            'backend': backend_package,
            'backend.personalization': personalization,
            'backend.speaking_subscriptions': speaking_subscriptions,
        }):
            return asyncio.run(scope['check_plan_practice_answer'](15, types.SimpleNamespace(
                exam_key=key, answer=answer), 'Bearer test'))

    def test_choice_returns_server_verdict(self):
        self.assertTrue(self.run_check('15:0', 'Yes')['is_correct'])
        self.assertFalse(self.run_check('15:0', 'No')['is_correct'])

    def test_ai_requires_verdict_for_same_answer(self):
        state['check'] = {'fingerprint': fingerprint('I enjoy reading'), 'verdict': 'correct'}
        self.assertTrue(self.run_check('15:1', 'I enjoy reading')['is_correct'])
        with self.assertRaises(HttpError) as caught:
            self.run_check('15:1', 'different answer')
        self.assertEqual(caught.exception.status_code, 409)

    def test_other_user_and_forged_key_are_rejected(self):
        state['user_id'] = 8
        with self.assertRaises(HttpError) as caught:
            self.run_check('15:0', 'Yes')
        self.assertEqual(caught.exception.status_code, 404)
        state['user_id'] = 7
        with self.assertRaises(HttpError) as caught:
            self.run_check('16:0', 'Yes')
        self.assertEqual(caught.exception.status_code, 422)


if __name__ == '__main__':
    unittest.main()
