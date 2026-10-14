from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_developer_can_manage_a_finite_attendance_reopen_window() -> None:
    database = (ROOT / "db.py").read_text(encoding="utf-8")
    backend = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    workspace = (ROOT / "app" / "ui" / "developer-workspace.tsx").read_text(encoding="utf-8")

    assert "def get_attendance_reopen_settings" in database
    assert "def update_attendance_reopen_settings" in database
    assert "@app.get(\"/developer/attendance-reopen\")" in backend
    assert "@app.post(\"/developer/attendance-reopen\")" in backend
    assert "_require_developer_access(user)" in backend
    assert "get_attendance_reopen_settings" in backend
    assert "DeveloperAttendanceReopenView" in workspace
    assert '"/developer/attendance-reopen"' in workspace
    assert 'case "developer-attendance"' in workspace
