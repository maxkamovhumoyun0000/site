from __future__ import annotations

from pathlib import Path


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
