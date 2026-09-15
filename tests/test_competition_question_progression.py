import backend.main as api


def test_answer_response_contains_the_next_question_without_waiting_for_opponent(monkeypatch):
    monkeypatch.setattr(api, "_duel_persist_session", lambda _session: None)
    session = {
        "id": "cmp-progress",
        "mode": "duel-1v1",
        "subject": "English",
        "status": "running",
        "questions": [
            {"question": "First?", "option_a": "A", "option_b": "B", "correct_option_index": 1},
            {"question": "Second?", "option_a": "C", "option_b": "D", "correct_option_index": 1},
        ],
        "progress": {7: {"index": 2, "correct": 1, "wrong": 0, "unanswered": 0}},
        "timers": {},
    }

    payload = api._competition_current_question_payload(session, 7)

    assert payload["question_index"] == 2
    assert payload["question"]["prompt"] == "Second?"
    assert payload["time_remaining_sec"] >= 30
