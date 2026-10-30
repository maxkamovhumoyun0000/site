"""Fast selection does not reuse questions seen by either opponent."""
import ast
import unittest
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).resolve().parents[1] / "backend" / "main.py"


class FastQuestionSelectionTest(unittest.TestCase):
    def test_filters_seen_questions_and_wrong_levels(self):
        tree = ast.parse(SOURCE.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_competition_fast_bank_candidates"]
        self.assertEqual(len(functions), 1, "fast bank candidate selector must exist")
        namespace = {
            "Any": Any,
            "_competition_question_is_valid": lambda row: bool(row.get("question")),
            "_competition_question_key": lambda row: row["question"],
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), namespace)
        select = namespace["_competition_fast_bank_candidates"]
        rows = [
            {"question": "seen", "level": "B1"},
            {"question": "fresh", "level": "B1"},
            {"question": "fresh", "level": "B1"},
            {"question": "wrong level", "level": "C1"},
        ]
        self.assertEqual([r["question"] for r in select(rows, "B1", {"seen"})], ["fresh"])


if __name__ == "__main__":
    unittest.main()
