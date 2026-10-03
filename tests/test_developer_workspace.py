from __future__ import annotations

import backend.main as api


def test_developer_workspace_allows_only_its_mobile_release_endpoint() -> None:
    assert api._developer_workspace_path_is_allowed("/developer/mobile-release")


def test_developer_has_separate_system_release_and_maintenance_pages() -> None:
    assert api.SECTIONS_BY_ROLE["developer"] == ["home", "system-status", "mobile-release", "mobile-maintenance", "profile"]


def test_developer_release_payload_keeps_maintenance_settings_out() -> None:
    payload = api._normalize_developer_release_payload(
        {
            "student": {
                "min_version": "v4.0.1",
                "min_build": 401,
                "store_url": "https://example.test/student",
                "maintenance_enabled": True,
            },
            "teacher": {"min_version": "4.0.2", "ios_store_url": "https://example.test/teacher"},
        }
    )

    assert payload == {
        "min_student_version": "4.0.1",
        "min_student_build": 401,
        "student_play_store_url": "https://example.test/student",
        "min_teacher_version": "4.0.2",
        "teacher_app_store_url": "https://example.test/teacher",
    }
