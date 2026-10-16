from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SpeakingLinkSessionTransactionContractTests(unittest.TestCase):
    def test_student_link_session_replacement_uses_the_link_transaction(self) -> None:
        source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        approve_start = source.index("async def approve_speaking_student_link")
        approve_end = source.index('@app.post("/auth/speaking-link/complete"', approve_start)
        approve = source[approve_start:approve_end]
        complete_end = source.index('@app.post("/auth/speaking/add-subject")', approve_end)
        complete = source[approve_end:complete_end]

        # Replacing a selected old device, approving the link, and consuming
        # it must not require a second DB connection while this request holds
        # FOR UPDATE on the one-time code.
        expected = "requested_session_ids=payload.revoke_session_ids,\n            conn=conn,"
        self.assertIn(expected, approve)
        self.assertIn(expected, complete)
