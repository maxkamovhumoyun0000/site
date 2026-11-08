from __future__ import annotations

from pathlib import Path

import backend.main as api
import diamondvoy_helpers as diamondvoy
import pytest


def test_force_update_compares_only_public_versions() -> None:
    assert api._is_app_version_below("2.6.9", "2.7.0", 999, 1)
    assert not api._is_app_version_below("2.7.0", "2.7.0", 1, 999)
    assert not api._is_app_version_below("2.7.1", "2.7.0", 1, 999)


def test_diamondvoy_payload_maps_to_the_persisted_flat_fields() -> None:
    payload = api._normalize_app_version_settings_payload(
        {
            "student": {"min_version": "v2.7.0", "store_url": "https://example.test/student"},
            "teacher": {"min_version": "2.7.0", "ios_store_url": "https://example.test/teacher"},
        }
    )

    assert payload["min_student_version"] == "2.7.0"
    assert payload["student_play_store_url"] == "https://example.test/student"
    assert payload["min_teacher_version"] == "2.7.0"
    assert payload["teacher_app_store_url"] == "https://example.test/teacher"


def test_diamondvoy_has_no_mobile_release_mutator() -> None:
    assert not hasattr(diamondvoy, "try_diamondvoy_app_version_action")


def test_maintenance_window_is_active_only_inside_its_configured_interval() -> None:
    active = api._maintenance_state(
        {
            "student_maintenance_enabled": 1,
            "student_maintenance_starts_at": "2026-10-02T08:00:00Z",
            "student_maintenance_ends_at": "2026-10-02T10:00:00Z",
        },
        "student",
        now=api.datetime(2026, 10, 2, 9, 0, tzinfo=api.timezone.utc),
    )
    before = api._maintenance_state(
        {
            "student_maintenance_enabled": 1,
            "student_maintenance_starts_at": "2026-10-02T08:00:00Z",
            "student_maintenance_ends_at": "2026-10-02T10:00:00Z",
        },
        "student",
        now=api.datetime(2026, 10, 2, 7, 59, tzinfo=api.timezone.utc),
    )

    assert active["active"] is True
    assert before["active"] is False


def test_global_maintenance_is_identical_for_student_teacher_and_speaking() -> None:
    settings = {
        "platform_maintenance_enabled": 1,
        "platform_maintenance_ends_at": "2026-10-02T10:00:00Z",
        "platform_maintenance_message_uz": "Umumiy texnik ishlar",
        "platform_maintenance_message_ru": "Общие технические работы",
        "platform_maintenance_message_en": "Platform maintenance",
    }
    now = api.datetime(2026, 10, 2, 9, 0, tzinfo=api.timezone.utc)

    states = [
        api._maintenance_state(settings, app, now=now)
        for app in ("student", "teacher", "speaking")
    ]

    assert all(state["active"] is True for state in states)
    assert {state["ends_at"] for state in states} == {"2026-10-02T10:00:00Z"}
    assert {state["message_uz"] for state in states} == {"Umumiy texnik ishlar"}


def test_static_release_maintenance_contract_includes_shared_end_time() -> None:
    repo = Path(__file__).resolve().parents[1]
    caddy = (repo / "scripts/caddy-maintenance-active.caddy").read_text()
    release_script = (repo / "scripts/activate_production_release.sh").read_text()

    assert caddy.count("__MAINTENANCE_ENDS_AT__") == 2
    assert '"ends_at":"__MAINTENANCE_ENDS_AT__"' in caddy
    assert 'maintenance_ends_at="$(date -u -d' in release_script
    assert 'set_platform_maintenance 1 "$maintenance_ends_at"' in release_script
    assert 'set_site_maintenance 1 "$maintenance_ends_at"' in release_script


def test_maintenance_settings_payload_accepts_only_safe_app_specific_fields() -> None:
    normalized = api._normalize_app_version_settings_payload(
        {
            "student": {
                "maintenance_enabled": True,
                "maintenance_starts_at": "2026-10-02T08:00:00Z",
                "maintenance_ends_at": "2026-10-02T10:00:00Z",
                "maintenance_message_uz": "Rejali texnik ishlar",
            }
        }
    )

    assert normalized["student_maintenance_enabled"] == 1
    assert normalized["student_maintenance_message_uz"] == "Rejali texnik ishlar"


def test_maintenance_state_selects_the_mobile_app_language() -> None:
    state = api._maintenance_state(
        {
            "student_maintenance_enabled": 1,
            "student_maintenance_message_uz": "O‘zbekcha xabar",
            "student_maintenance_message_ru": "Сообщение по-русски",
            "student_maintenance_message_en": "English message",
        },
        "student",
        language="ru",
    )

    assert state["message"] == "Сообщение по-русски"


def test_maintenance_window_rejects_an_end_before_its_start() -> None:
    with pytest.raises(api.HTTPException, match="must be after"):
        api._normalize_app_version_settings_payload(
            {
                "teacher": {
                    "maintenance_starts_at": "2026-10-02T10:00:00Z",
                    "maintenance_ends_at": "2026-10-02T08:00:00Z",
                }
            }
        )


def test_developer_scope_is_limited_to_the_dedicated_login() -> None:
    assert api._is_developer_account({"login_id": "developer-x-01"})
    assert not api._is_developer_account({"login_id": "MEDIA-X-01"})


def test_developer_workspace_path_allowlist_excludes_broad_admin_routes() -> None:
    assert api._developer_workspace_path_is_allowed("/developer/mobile-maintenance")
    assert api._developer_workspace_path_is_allowed("/admin/system-metrics/")
    assert not api._developer_workspace_path_is_allowed("/admin/payments/dashboard")


def test_developer_has_a_distinct_role_and_minimal_app_state() -> None:
    assert api._role_from_login_type(4, "DEVELOPER-X-01") == "developer"
    assert api._role_from_login_type(4, "ADMIN-X-01") == "admin"
    assert api.SECTIONS_BY_ROLE["developer"] == ["home", "profile"]
    assert api._build_role_boot_payload({}, "developer", {}) == {}
