from __future__ import annotations

import ast
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytz


ROOT = Path(__file__).resolve().parents[1]


def test_temporary_attendance_reopen_is_scoped_and_expires() -> None:
    backend = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    frontend = (ROOT / "app" / "page.tsx").read_text(encoding="utf-8")

    # The server remains authoritative and reads an explicit, finite override.
    assert "ATTENDANCE_REOPEN_START_DATE" in backend
    assert "ATTENDANCE_REOPEN_END_DATE" in backend
    assert "ATTENDANCE_REOPEN_UNTIL" in backend
    assert "def _attendance_temporary_reopen_active" in backend
    assert "if _attendance_temporary_reopen_active(date_text):" in backend

    # Cancelled lessons and historical group-membership authorization must stay
    # in force even when the normal timing window has a temporary exception.
    assert "is_lesson_otmen_date_cancelled(day_iso)" in backend
    assert "_membership_period_allows_date" in backend

    # The client must show the server-enabled date as open instead of blocking
    # the user before the attendance request can reach the server.
    assert "function isTemporaryAttendanceReopenDate" in frontend
    assert "isTemporaryAttendanceReopenDate(lessonDate)" in frontend
    assert "isTemporaryAttendanceReopenDate(String(card.date))" in frontend


def test_temporary_reopen_helper_allows_only_configured_dates() -> None:
    source = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    helper = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "_attendance_temporary_reopen_active"
    )

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            fixed = cls(2026, 10, 14, 12, 0, 0)
            return tz.localize(fixed) if tz else fixed

    namespace = {
        "os": os,
        "datetime": FrozenDateTime,
        "TASHKENT_TZ": pytz.timezone("Asia/Tashkent"),
    }
    exec(compile(ast.Module(body=[helper], type_ignores=[]), "<attendance-helper>", "exec"), namespace)

    with patch.dict(
        os.environ,
        {
            "ATTENDANCE_REOPEN_START_DATE": "2026-10-01",
            "ATTENDANCE_REOPEN_END_DATE": "2026-10-14",
            "ATTENDANCE_REOPEN_UNTIL": "2026-10-21T23:59:59+05:00",
        },
        clear=False,
    ):
        reopen_active = namespace["_attendance_temporary_reopen_active"]
        assert reopen_active("2026-10-01") is True
        assert reopen_active("2026-10-14") is True
        assert reopen_active("2026-09-30") is False
        assert reopen_active("2026-10-15") is False
