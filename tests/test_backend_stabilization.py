from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import backend.main as api
import gamified_tests


def _student_user(user_id: int = 11) -> dict:
    return {"id": user_id, "login_type": 1, "login_id": f"STU{user_id}"}


def _teacher_user(user_id: int = 22) -> dict:
    return {"id": user_id, "login_type": 3, "login_id": f"TCH{user_id}"}


def _support_user(user_id: int = 33) -> dict:
    return {"id": user_id, "login_type": 5, "login_id": f"SUP{user_id}"}


def _admin_user(user_id: int = 44) -> dict:
    return {"id": user_id, "login_type": 4, "login_id": f"ADM{user_id}"}


def test_require_role_support_only_policy() -> None:
    assert api._require_role(_support_user(), {"support"}) == "support"

    with pytest.raises(HTTPException) as teacher_exc:
        api._require_role(_teacher_user(), {"support"})
    assert teacher_exc.value.status_code == 403

    with pytest.raises(HTTPException) as admin_exc:
        api._require_role(_admin_user(), {"support"})
    assert admin_exc.value.status_code == 403


def test_homework_window_policy_assignment_and_submission_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    homework = {"created_at": "2026-01-01T00:00:00+00:00"}

    monkeypatch.setattr(api, "_now_utc", lambda: datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc))
    assert api._homework_window_open(homework, None) is True

    monkeypatch.setattr(api, "_now_utc", lambda: datetime(2026, 1, 9, 0, 0, tzinfo=timezone.utc))
    assert api._homework_window_open(homework, None) is False

    submission = {"created_at": "2026-01-20T00:00:00+00:00"}
    monkeypatch.setattr(api, "_now_utc", lambda: datetime(2026, 1, 26, 0, 0, tzinfo=timezone.utc))
    assert api._homework_window_open(homework, submission) is True

    monkeypatch.setattr(api, "_now_utc", lambda: datetime(2026, 1, 28, 12, 0, tzinfo=timezone.utc))
    assert api._homework_window_open(homework, submission) is False


def test_filter_homeworks_with_open_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_now_utc", lambda: datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc))
    rows = [
        {"id": 1, "created_at": "2026-02-08T00:00:00+00:00", "submission_created_at": None},
        {"id": 2, "created_at": "2026-02-01T00:00:00+00:00", "submission_created_at": None},
        {"id": 3, "created_at": "2026-01-01T00:00:00+00:00", "submission_created_at": "2026-02-09T00:00:00+00:00"},
    ]

    kept = api._filter_homeworks_with_open_window(rows)
    kept_ids = {int(item.get("id") or 0) for item in kept}

    assert kept_ids == {1, 3}


def test_proctoring_payload_degrades_when_face_enrollment_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    user = {
        "id": 11,
        "login_type": 1,
        "proctoring_required": 1,
        "face_enrollment_required": 1,
        "face_profile_status": "pending",
    }
    monkeypatch.setattr(api, "get_active_face_profile", lambda _user_id: None)

    def _unexpected_create(*_args, **_kwargs):
        raise AssertionError("proctoring session should not be created without a ready face profile")

    monkeypatch.setattr(api, "create_test_proctoring_session", _unexpected_create)

    payload = api._attach_proctoring_payload(
        user,
        {"session_id": "test_1"},
        test_type="vocabulary",
        test_attempt_ref="test_1",
    )

    assert payload["session_id"] == "test_1"
    assert payload["proctoring_required"] is False
    assert payload["face_enrollment_required"] is True
    assert payload["proctoring_degraded"] is True


def test_proctoring_session_access_does_not_block_answers_when_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    user = {
        "id": 11,
        "login_type": 1,
        "proctoring_required": 1,
        "face_enrollment_required": 1,
        "face_profile_status": "pending",
    }
    monkeypatch.setattr(api, "get_active_face_profile", lambda _user_id: None)

    def _unexpected_lookup(*_args, **_kwargs):
        raise AssertionError("proctoring session lookup should be skipped in degraded mode")

    monkeypatch.setattr(api, "get_test_proctoring_session", _unexpected_lookup)

    assert api._ensure_proctoring_session_access(
        user,
        None,
        expected_test_type="vocabulary",
        expected_attempt_ref="test_1",
    ) is None


def _pending_boss_session(now: datetime, participants: int, *, deadline_offset_seconds: int = -1) -> dict:
    first_joined = now - timedelta(minutes=5, seconds=1)
    deadline = now + timedelta(seconds=deadline_offset_seconds)
    return {
        "id": f"cmp_boss_{participants}",
        "mode": "boss",
        "subject": "English",
        "level": "B1",
        "status": "pending",
        "required_players": 5,
        "max_players": 200,
        "queue_key": "boss|English|B1",
        "participants": [
            {
                "user_id": uid,
                "name": f"Student {uid}",
                "status": "active",
                "joined_at": first_joined.isoformat(),
            }
            for uid in range(1, participants + 1)
        ],
        "charged_user_ids": list(range(1, participants + 1)),
        "refunded_user_ids": [],
        "first_joined_at": first_joined.isoformat(),
        "last_joined_at": first_joined.isoformat(),
        "wait_deadline_at": deadline.isoformat(),
        "generation_started": False,
        "generation_percent": 0,
        "stage_generation_percent": 0,
        "stage": 0,
        "total_stages": 1,
        "result": {"winners": [], "by_user": {}},
    }


def test_boss_lobby_expires_and_refunds_when_required_players_do_not_join(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    session = _pending_boss_session(now, 1)
    refunded: list[tuple[int, str]] = []

    monkeypatch.setattr(api, "_duel_persist_session", lambda _session: None)
    monkeypatch.setattr(api, "_competition_save_history", lambda _session: None)
    monkeypatch.setattr(api, "_competition_schedule_timeout_notification", lambda _session: None)

    def fake_refund(row: dict, uid: int, reason: str) -> bool:
        refunded.append((uid, reason))
        row.setdefault("refunded_user_ids", []).append(uid)
        return True

    monkeypatch.setattr(api, "_competition_refund_user_entry_fee", fake_refund)

    assert api._competition_expire_waiting_session_if_needed(session, now) is True
    assert session["status"] == "expired"
    assert session["finalized"] is True
    assert session["cancel_reason"] == "session_timeout"
    assert session["result"]["refunded"] is True
    assert session["result"]["by_user"][1]["result_status"] == "cancelled"
    assert refunded == [(1, "session_timeout")]


def test_boss_lobby_starts_generation_when_required_players_join_by_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    session = _pending_boss_session(now, 5)
    started: list[object] = []

    monkeypatch.setattr(api, "_duel_persist_session", lambda _session: None)

    def fake_create_task(coro):
        started.append(coro)
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return object()

    monkeypatch.setattr(api.asyncio, "create_task", fake_create_task)

    assert api._competition_expire_waiting_session_if_needed(session, now) is False
    assert session["status"] == "generating"
    assert session["generation_started"] is True
    assert session["generation_percent"] >= 5
    assert started


def test_competition_generation_prepare_requires_joined_players(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    session = {
        **_pending_boss_session(now, 1),
        "mode": "duel-1v1",
        "required_players": 2,
        "max_players": 2,
        "queue_key": "duel-1v1|English",
    }

    monkeypatch.setattr(api, "_duel_persist_session", lambda _session: None)

    assert api._competition_prepare_generation(session, target_stage=1) is None
    assert session["status"] == "pending"
    assert not session.get("generation_token")

    session["participants"].append(
        {
            "user_id": 2,
            "name": "Student 2",
            "status": "active",
            "joined_at": now.isoformat(),
        }
    )
    token = api._competition_prepare_generation(session, target_stage=1)

    assert token
    assert session["status"] == "generating"
    assert session["generation_token"] == token
    assert session["generation_task_stage"] == 1


@pytest.mark.asyncio
async def test_competition_generation_rechecks_players_before_start(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc)
    before = {
        **_pending_boss_session(now, 2),
        "id": "cmp_duel_drop",
        "mode": "duel-1v1",
        "status": "generating",
        "required_players": 2,
        "max_players": 2,
        "queue_key": "duel-1v1|English",
        "generation_token": "tok",
        "generation_task_stage": 1,
        "question_count": 5,
    }
    after = {
        **before,
        "participants": [
            {
                "user_id": 1,
                "name": "Student 1",
                "status": "active",
                "joined_at": now.isoformat(),
            },
            {
                "user_id": 2,
                "name": "Student 2",
                "status": "left",
                "joined_at": now.isoformat(),
                "left_reason": "left_queue",
            },
        ],
    }
    loads = [before, after]
    persisted: list[dict] = []

    monkeypatch.setattr(api, "_competition_session_advisory_lock", lambda _sid: nullcontext())
    monkeypatch.setattr(api, "_competition_load_session_from_db", lambda _sid: loads.pop(0) if loads else after)
    monkeypatch.setattr(api, "_duel_persist_session", lambda session: persisted.append(dict(session)))

    async def fake_generate_questions(**_kwargs):
        return [
            {
                "question": f"Question {idx}",
                "option_a": "A",
                "option_b": "B",
                "option_c": "C",
                "option_d": "D",
                "correct_option_index": 1,
            }
            for idx in range(5)
        ]

    notified: list[dict] = []
    async def fake_notify_started(session):
        notified.append(session)

    monkeypatch.setattr(api, "_runtime_generate_questions", fake_generate_questions)
    monkeypatch.setattr(api, "_competition_notify_started", fake_notify_started)

    await api._competition_start_generation("cmp_duel_drop", stage=1, generation_token="tok")

    assert after["status"] == "pending"
    assert after["generation_started"] is False
    assert after.get("questions") in (None, [])
    assert not after.get("generation_token")
    assert not notified
    assert persisted


@pytest.mark.asyncio
async def test_finished_competition_session_is_readable_by_participant(monkeypatch: pytest.MonkeyPatch) -> None:
    finished = {
        "id": "cmp_done",
        "mode": "duel-1v1",
        "subject": "English",
        "status": "finished",
        "finalized": True,
        "participants": [{"user_id": 11, "name": "Student 11", "status": "finished"}],
        "result": {"winners": [11], "by_user": {11: {"correct": 5, "wrong": 0}}},
    }

    monkeypatch.setattr(api, "_competition_load_session_from_db", lambda _sid: finished)

    assert await api._competition_ensure_session_for_user("cmp_done", _student_user()) is finished


def test_gamified_matching_public_payload_and_score_count_pairs() -> None:
    question = {
        "index": 0,
        "type": "word_match",
        "prompt": "Match",
        "left": ["a", "b", "c", "d"],
        "right": ["1", "2", "3", "4"],
        "_answer": {"a": "1", "b": "2", "c": "3", "d": "4"},
    }

    public = gamified_tests.public_question(question)
    result = gamified_tests.score_session([question], {0: {"a": "1", "b": "wrong", "c": "3"}})

    assert public["score_units"] == 4
    assert result["correct"] == 2
    assert result["wrong"] == 1
    assert result["skipped"] == 1
    assert result["total"] == 4


@pytest.mark.asyncio
async def test_support_booking_status_denied_for_teacher(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _teacher_user())

    with pytest.raises(HTTPException) as exc:
        await api.change_booking_status(
            "booking_1",
            api.BookingStatusRequest(status="approved"),
            authorization="Bearer test",
        )

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_support_booking_status_allowed_for_support(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _support_user())
    monkeypatch.setattr(api, "set_lesson_booking_status", lambda *args, **kwargs: True)

    result = await api.change_booking_status(
        "booking_2",
        api.BookingStatusRequest(status="approved"),
        authorization="Bearer test",
    )

    assert result["status"] == "approved"
    assert result["booking_id"] == "booking_2"


@pytest.mark.asyncio
async def test_teacher_support_requests_support_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _teacher_user())
    with pytest.raises(HTTPException) as denied:
        await api.teacher_support_requests(authorization="Bearer test")
    assert denied.value.status_code == 403

    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _support_user())
    monkeypatch.setattr(
        api,
        "list_lesson_bookings",
        lambda status=None, page=1, per_page=300: ([{"id": "b1", "created_at": "2026-04-24T10:00:00+00:00"}], 1),
    )
    monkeypatch.setattr(api, "_serialize_booking_row", lambda row: {"id": row.get("id"), "created_at": row.get("created_at")})

    result = await api.teacher_support_requests(authorization="Bearer test")
    assert isinstance(result.get("items"), list)
    assert result["items"][0]["id"] == "b1"


@pytest.mark.asyncio
async def test_support_booking_attendance_support_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _admin_user())
    with pytest.raises(HTTPException) as denied:
        await api.mark_booking_attendance(
            "booking_9",
            api.BookingAttendanceRequest(status="present", bonus_amount=0, penalty_amount=0),
            authorization="Bearer test",
        )
    assert denied.value.status_code == 403

    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _support_user())
    monkeypatch.setattr(api, "set_support_booking_attendance", lambda _booking_id, _status: True)

    result = await api.mark_booking_attendance(
        "booking_9",
        api.BookingAttendanceRequest(status="present", bonus_amount=0, penalty_amount=0),
        authorization="Bearer test",
    )
    assert result["status"] == "present"
    assert result["booking_id"] == "booking_9"


@pytest.mark.asyncio
async def test_teacher_support_request_status_support_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _teacher_user())

    with pytest.raises(HTTPException) as denied:
        await api.teacher_support_request_status(
            "b900",
            api.TeacherBookingDecisionRequest(status="approved", note="ok"),
            authorization="Bearer test",
        )
    assert denied.value.status_code == 403

    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _support_user())
    monkeypatch.setattr(api, "list_lesson_bookings", lambda status=None, page=1, per_page=300: ([{"id": "b900"}], 1))
    monkeypatch.setattr(api, "set_lesson_booking_status", lambda *args, **kwargs: True)

    result = await api.teacher_support_request_status(
        "b900",
        api.TeacherBookingDecisionRequest(status="approved", note="ok"),
        authorization="Bearer test",
    )
    assert result["status"] == "approved"
    assert result["booking_id"] == "b900"


@pytest.mark.asyncio
async def test_student_submit_homework_window_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _student_user(11))
    monkeypatch.setattr(api, "get_homework", lambda _hid: {"id": 1, "student_id": 11, "group_id": 0})
    monkeypatch.setattr(api, "get_user_groups", lambda _uid: [])
    monkeypatch.setattr(api, "get_homework_submission", lambda _hid, _uid: {"created_at": "2026-01-01T00:00:00+00:00"})
    monkeypatch.setattr(api, "_homework_window_open", lambda _hw, _sub: False)

    with pytest.raises(HTTPException) as exc:
        await api.student_submit_homework(
            1,
            api.HomeworkSubmitRequest(status="done", note="ok", proof_image_url=None),
            authorization="Bearer test",
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_holiday_cancel_auto_mode_rejects_non_holiday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _admin_user())
    monkeypatch.setattr(
        api,
        "execute_otmen_for_date",
        lambda *args, **kwargs: {"ok": False, "code": "not_holiday", "date_str": "2026-03-12"},
    )

    with pytest.raises(HTTPException) as exc:
        await api.admin_holiday_otmen_cancel(
            api.HolidayOtmenCancelRequest(date="2026-03-12", reason="test", mode="auto"),
            authorization="Bearer test",
        )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_holiday_cancel_manual_mode_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _admin_user(77))

    async def _noop_notify(_result):
        return None

    monkeypatch.setattr(api, "_notify_holiday_otmen_result", _noop_notify)
    monkeypatch.setattr(
        api,
        "execute_otmen_for_date",
        lambda *args, **kwargs: {
            "ok": True,
            "code": "done",
            "reason": "Manual otmen",
            "request_id": "req_manual_1",
            "stats": {"groups": 2, "sessions": 2, "bookings": 3},
        },
    )

    result = await api.admin_holiday_otmen_cancel(
        api.HolidayOtmenCancelRequest(date="2026-03-12", reason="manual run", mode="manual"),
        authorization="Bearer test",
    )

    assert result["mode"] == "manual"
    assert result["request_id"] == "req_manual_1"
    assert result["stats"]["bookings"] == 3


@pytest.mark.asyncio
async def test_holiday_reopen_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _admin_user())
    monkeypatch.setattr(api, "reopen_otmen_date", lambda _date: {"ok": True, "code": "done", "request_id": "req_1"})

    result = await api.admin_holiday_otmen_reopen(
        api.HolidayOtmenReopenRequest(date="2026-03-12"),
        authorization="Bearer test",
    )

    assert result["request_status"] == "reopened"
    assert result["request_id"] == "req_1"
