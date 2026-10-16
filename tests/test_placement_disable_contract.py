"""Regression guard for turning off a student's placement requirement."""

from pathlib import Path
import unittest


class PlacementDisableContractTests(unittest.TestCase):
    def test_disabling_placement_clears_the_attempt_and_auth_cache(self) -> None:
        source = Path("backend/main.py").read_text(encoding="utf-8")
        start = source.index("elif payload.placement_required is False:")
        end = source.index("\n    refreshed =", start)
        branch = source[start:end]

        self.assertIn("clear_placement_session(int(user_id))", branch)
        self.assertIn("_clear_auth_caches_for_user(int(user_id))", branch)
