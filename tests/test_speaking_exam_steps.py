"""The exam, rather than submitted client text, owns generated questions."""
import ast
import json
import unittest
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'backend/speaking_answers.py'
tree = ast.parse(source.read_text())
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == '_exam_step_question')
node.returns = None


class Cursor:
    def execute(self, sql, params):
        self.params = params

    def fetchone(self):
        if self.params != (11, 7):
            return None
        return {'status': 'started', 'subject': 'russian', 'steps_json': json.dumps([
            {'index': 0, 'part': 1, 'prompt': 'Расскажите о себе.', 'topic': 'Знакомство',
             'question_id': None, 'bullets': []}])}

    def close(self):
        pass


class Connection:
    def cursor(self):
        return Cursor()

    def close(self):
        pass

    def rollback(self):
        pass


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        super().__init__(detail)


scope = {'get_conn': Connection, 'json': json, 'HTTPException': HttpError}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)


class GeneratedExamStepTests(unittest.TestCase):
    def test_generated_step_returns_server_question_and_subject(self):
        question, key, step, subject = scope['_exam_step_question'](7, 11, 0)
        self.assertEqual(question, '')
        self.assertEqual(key, 'exam-11-0')
        self.assertEqual(step['prompt'], 'Расскажите о себе.')
        self.assertEqual(subject, 'russian')

    def test_other_user_cannot_read_exam(self):
        with self.assertRaises(HttpError) as caught:
            scope['_exam_step_question'](8, 11, 0)
        self.assertEqual(caught.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main()
