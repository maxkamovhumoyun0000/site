from __future__ import annotations

import backend.main as api


def test_feedback_status_normalizes_waiting_for_user() -> None:
    assert api._normalize_feedback_status("awaiting_user") == "Javob kutilmoqda"


def test_admin_reply_moves_feedback_to_waiting_for_user() -> None:
    assert api._feedback_status_after_message("Ko‘rilmoqda", "admin") == "Javob kutilmoqda"


def test_user_follow_up_reopens_resolved_feedback() -> None:
    assert api._feedback_status_after_message("Hal qilindi", "student") == "Yangi"
