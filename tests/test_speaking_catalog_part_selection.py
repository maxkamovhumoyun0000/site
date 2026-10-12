from __future__ import annotations

import ast
import unittest
from pathlib import Path


class SpeakingCatalogPartSelectionTests(unittest.TestCase):
    def test_english_catalog_has_ten_topics_for_each_ielts_part(self) -> None:
        source = Path(__file__).parents[1] / "backend" / "speaking_admin.py"
        module = ast.parse(source.read_text(encoding="utf-8"))
        value = next(
            node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "ENGLISH_CATALOG_TOPICS" for target in node.targets)
        )
        topics = ast.literal_eval(value)

        self.assertEqual(len(topics), 30)
        self.assertEqual(sum(part == 1 for part, _ in topics), 10)
        self.assertEqual(sum(part == 2 for part, _ in topics), 10)
        self.assertEqual(sum(part == 3 for part, _ in topics), 10)

    def test_catalog_helper_returns_only_the_selected_part(self) -> None:
        source = Path(__file__).parents[1] / "backend" / "speaking_admin.py"
        contents = source.read_text(encoding="utf-8")

        self.assertIn("def english_catalog_topics_for_part(part: int)", contents)
        self.assertIn("spec[0] == selected_part", contents)
        self.assertIn("part: int = Query(default=1, ge=1, le=3)", contents)
