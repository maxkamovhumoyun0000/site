from __future__ import annotations

import pytest

import admin_bot


class DummyBot:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.sent.append({"chat_id": chat_id, "text": text, **kwargs})


@pytest.mark.asyncio
async def test_scheduler_skips_non_holiday(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyBot()
    monkeypatch.setattr(admin_bot, "bot", dummy)
    monkeypatch.setattr(admin_bot, "ALL_ADMIN_IDS", [1001])
    monkeypatch.setattr(
        admin_bot,
        "list_upcoming_holiday_days",
        lambda start_offset=0, days_count=11, lang="uz": [
            {
                "date_str": "2026-05-10",
                "date_ui": "10-05-2026",
                "weekday": "Yakshanba",
                "reason_db": "Holiday",
                "request_status": "open",
                "pending_request_id": None,
            }
        ],
    )
    monkeypatch.setattr(admin_bot, "is_official_holiday_date", lambda _date: False)

    ensure_calls = {"count": 0}

    def _ensure(*args, **kwargs):
        ensure_calls["count"] += 1
        return "req_should_not_happen"

    monkeypatch.setattr(admin_bot, "ensure_otmen_request_for_day", _ensure)

    await admin_bot.send_daily_otmen_alerts(start_offset=0, days_count=11)

    assert ensure_calls["count"] == 0
    assert dummy.sent == []


@pytest.mark.asyncio
async def test_scheduler_sends_holiday_alert_with_dedupe_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyBot()
    monkeypatch.setattr(admin_bot, "bot", dummy)
    monkeypatch.setattr(admin_bot, "ALL_ADMIN_IDS", [2001, 2002])
    monkeypatch.setattr(
        admin_bot,
        "list_upcoming_holiday_days",
        lambda start_offset=0, days_count=11, lang="uz": [
            {
                "date_str": "2026-05-09",
                "date_ui": "09-05-2026",
                "weekday": "Shanba",
                "reason_db": "Bayram",
                "request_status": "open",
                "pending_request_id": None,
            }
        ],
    )
    monkeypatch.setattr(admin_bot, "is_official_holiday_date", lambda _date: True)
    monkeypatch.setattr(admin_bot, "get_user_by_telegram", lambda _tg: {"language": "uz"})
    monkeypatch.setattr(admin_bot, "detect_lang_from_user", lambda _user: "uz")
    monkeypatch.setattr(admin_bot, "otmen_full_info_line", lambda _lang, _d: "Holiday info")
    monkeypatch.setattr(admin_bot, "t", lambda _lang, key, **kwargs: f"{key}")

    ensure_args: list[tuple[tuple, dict]] = []

    def _ensure(*args, **kwargs):
        ensure_args.append((args, kwargs))
        return "req_20260509"

    monkeypatch.setattr(admin_bot, "ensure_otmen_request_for_day", _ensure)

    await admin_bot.send_daily_otmen_alerts(start_offset=0, days_count=11)

    assert len(ensure_args) == 1
    assert ensure_args[0][1].get("cancel_mode") == "auto"
    assert ensure_args[0][1].get("dedupe_existing_auto") is True
    assert len(dummy.sent) == 2


@pytest.mark.asyncio
async def test_scheduler_skips_day_with_existing_pending_request(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyBot()
    monkeypatch.setattr(admin_bot, "bot", dummy)
    monkeypatch.setattr(admin_bot, "ALL_ADMIN_IDS", [3001])
    monkeypatch.setattr(
        admin_bot,
        "list_upcoming_holiday_days",
        lambda start_offset=0, days_count=11, lang="uz": [
            {
                "date_str": "2026-05-09",
                "date_ui": "09-05-2026",
                "weekday": "Shanba",
                "reason_db": "Bayram",
                "request_status": "pending",
                "pending_request_id": "existing_req",
            }
        ],
    )
    monkeypatch.setattr(admin_bot, "is_official_holiday_date", lambda _date: True)

    ensure_calls = {"count": 0}

    def _ensure(*args, **kwargs):
        ensure_calls["count"] += 1
        return "new_req"

    monkeypatch.setattr(admin_bot, "ensure_otmen_request_for_day", _ensure)

    await admin_bot.send_daily_otmen_alerts(start_offset=0, days_count=11)

    assert ensure_calls["count"] == 0
    assert dummy.sent == []


@pytest.mark.asyncio
async def test_scheduler_reopened_day_becomes_realert_eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy = DummyBot()
    monkeypatch.setattr(admin_bot, "bot", dummy)
    monkeypatch.setattr(admin_bot, "ALL_ADMIN_IDS", [4001])
    monkeypatch.setattr(
        admin_bot,
        "list_upcoming_holiday_days",
        lambda start_offset=10, days_count=1, lang="uz": [
            {
                "date_str": "2026-05-19",
                "date_ui": "19-05-2026",
                "weekday": "Seshanba",
                "reason_db": "Bayram",
                "request_status": "reopened",
                "pending_request_id": None,
            }
        ],
    )
    monkeypatch.setattr(admin_bot, "is_official_holiday_date", lambda _date: True)
    monkeypatch.setattr(admin_bot, "get_user_by_telegram", lambda _tg: {"language": "uz"})
    monkeypatch.setattr(admin_bot, "detect_lang_from_user", lambda _user: "uz")
    monkeypatch.setattr(admin_bot, "otmen_full_info_line", lambda _lang, _d: "Holiday info")
    monkeypatch.setattr(admin_bot, "t", lambda _lang, key, **kwargs: f"{key}")

    ensure_args: list[tuple[tuple, dict]] = []

    def _ensure(*args, **kwargs):
        ensure_args.append((args, kwargs))
        return "req_reopen_20260519"

    monkeypatch.setattr(admin_bot, "ensure_otmen_request_for_day", _ensure)

    await admin_bot.send_daily_otmen_alerts(start_offset=10, days_count=1)

    assert len(ensure_args) == 1
    assert ensure_args[0][1].get("cancel_mode") == "auto"
    assert ensure_args[0][1].get("dedupe_existing_auto") is True
    assert len(dummy.sent) == 1
