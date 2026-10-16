"""Regression guard for existing Diamondvoy usage rows."""

from pathlib import Path
import unittest


class DiamondvoyUsageContractTests(unittest.TestCase):
    def test_existing_usage_row_initializes_free_counter_before_limit_check(self) -> None:
        source = Path("backend/main.py").read_text(encoding="utf-8")
        start = source.index("def _diamondvoy_apply_usage(")
        end = source.index("\n\n_DIAMONDVOY_MEMORY_STOPWORDS", start)
        block = source[start:end]

        self.assertIn('free_used = max(0, int(row.get("free_count_used") or 0))', block)
        self.assertLess(
            block.index('free_used = max(0, int(row.get("free_count_used") or 0))'),
            block.index("if free_used >= current_limit:"),
        )
