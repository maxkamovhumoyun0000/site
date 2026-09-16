from datetime import datetime, timedelta, timezone

import backend.main as main


def test_parent_access_token_is_opaque_and_not_login_id():
    token = main._new_parent_access_token()

    assert len(token) >= 32
    assert token.isalnum()
    assert "student" not in token.lower()


def test_study_room_code_has_exactly_six_digits():
    code = main._new_study_room_code()

    assert len(code) == 6
    assert code.isdigit()


def test_mistake_review_spacing_grows_after_correct_answers():
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)

    first = main._mistake_next_review_at(now, correct_streak=0)
    later = main._mistake_next_review_at(now, correct_streak=3)

    assert first == now + timedelta(days=1)
    assert later >= now + timedelta(days=14)
