"""Team identity must survive session persistence and reach both clients."""
import ast
import json
import unittest
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / 'backend' / 'main.py'


def load(names, extras):
    tree = ast.parse(SOURCE.read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = {'Any': Any, 'json': json, **extras}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'), ns)
    return ns


class TeamIdentityTest(unittest.TestCase):
    def test_team_two_survives_json_key_round_trip(self):
        recorded = []
        class Cursor:
            def execute(self, sql, params=()):
                if 'INSERT INTO web_competition_participants' in sql:
                    recorded.append(params)
        class Connection:
            def cursor(self): return Cursor()
            def commit(self): pass
            def close(self): pass
            def rollback(self): pass
        ns = load({'_competition_persist_session_db', '_competition_participant_team'}, {
            '_ensure_web_competition_runtime_schema': lambda: None,
            '_duel_normalize_session': lambda s: s,
            '_json_default': str,
            'get_conn': Connection,
            '_now_utc': lambda: None,
        })
        ns['_competition_persist_session_db']({
            'id': 'demo', 'mode': 'duel-3v3', 'created_at': '2026-01-01',
            'teams': {'1': 1, '2': 2},
            'participants': [{'user_id': 1}, {'user_id': 2}],
        })
        self.assertEqual({row[1]: row[3] for row in recorded}, {1: 1, 2: 2})

    def test_progress_labels_teammates_and_opponents(self):
        ns = load({'_competition_opponent_progress', '_competition_participant_team'}, {})
        session = {'questions': [{'id': 1}], 'teams': {'1': 1, '2': 1, '3': 2},
                   'participants': [{'user_id': 1}, {'user_id': 2}, {'user_id': 3}]}
        rows = ns['_competition_opponent_progress'](session, 1)
        self.assertEqual([(r['user_id'], r['team'], r['relationship']) for r in rows],
                         [(2, 1, 'teammate'), (3, 2, 'opponent')])


if __name__ == '__main__': unittest.main()
