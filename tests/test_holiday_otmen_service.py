from __future__ import annotations

import pytest

import holiday_otmen_service as svc


VALID_DATE = "2026-05-09"


def test_auto_mode_rejects_non_holiday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "is_official_holiday_date", lambda _date: False)
    assert svc.ensure_otmen_request_for_day(VALID_DATE, cancel_mode="auto") is None


def test_auto_dedupe_reuses_pending_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "is_official_holiday_date", lambda _date: True)
    monkeypatch.setattr(
        svc,
        "get_latest_lesson_otmen_request_by_date",
        lambda _date, cancel_mode=None: {"id": "req_pending", "status": "pending"},
    )

    called = {"create": 0}

    def _create(*args, **kwargs):
        called["create"] += 1
        return True

    monkeypatch.setattr(svc, "create_lesson_otmen_request", _create)

    req_id = svc.ensure_otmen_request_for_day(
        VALID_DATE,
        reason="Bayram",
        cancel_mode="auto",
        dedupe_existing_auto=True,
    )

    assert req_id == "req_pending"
    assert called["create"] == 0


@pytest.mark.parametrize("status", ["cancelled", "expired", "unknown", ""])
def test_auto_dedupe_blocks_for_non_reopened_statuses(monkeypatch: pytest.MonkeyPatch, status: str) -> None:
    monkeypatch.setattr(svc, "is_official_holiday_date", lambda _date: True)
    monkeypatch.setattr(
        svc,
        "get_latest_lesson_otmen_request_by_date",
        lambda _date, cancel_mode=None: {"id": "req_old", "status": status},
    )
    monkeypatch.setattr(svc, "create_lesson_otmen_request", lambda *args, **kwargs: True)

    req_id = svc.ensure_otmen_request_for_day(
        VALID_DATE,
        reason="Bayram",
        cancel_mode="auto",
        dedupe_existing_auto=True,
    )

    assert req_id is None


def test_auto_dedupe_reopened_allows_new_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(svc, "is_official_holiday_date", lambda _date: True)
    monkeypatch.setattr(
        svc,
        "get_latest_lesson_otmen_request_by_date",
        lambda _date, cancel_mode=None: {"id": "req_old", "status": "reopened"},
    )
    monkeypatch.setattr(svc, "get_pending_lesson_otmen_request_by_date", lambda _date: None)

    create_calls: list[tuple[tuple, dict]] = []

    def _create(*args, **kwargs):
        create_calls.append((args, kwargs))
        return True

    monkeypatch.setattr(svc, "create_lesson_otmen_request", _create)

    req_id = svc.ensure_otmen_request_for_day(
        VALID_DATE,
        reason="Bayram",
        cancel_mode="auto",
        dedupe_existing_auto=True,
    )

    assert isinstance(req_id, str) and req_id
    assert len(create_calls) == 1
    assert create_calls[0][1].get("cancel_mode") == "auto"
