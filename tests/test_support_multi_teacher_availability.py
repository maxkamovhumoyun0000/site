from __future__ import annotations

import backend.main as api


def test_only_individually_free_support_teachers_are_offered(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "_support_teacher_candidates_for_slot",
        lambda *_args: [{"id": 11}, {"id": 12}],
    )
    monkeypatch.setattr(
        api,
        "lesson_is_support_teacher_slot_free",
        lambda teacher_id, _date, _time: teacher_id == 12,
    )

    available = api._available_support_teacher_candidates_for_slot(
        "English", "branch_1", "2026-10-01", "14:00",
    )

    assert [teacher["id"] for teacher in available] == [12]
