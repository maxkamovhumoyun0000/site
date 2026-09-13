from __future__ import annotations

import backend.main as api
import db
import diamondvoy_helpers as diamondvoy


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


def test_diamondvoy_accepts_uzbek_version_inflections_and_updates_both_apps(monkeypatch) -> None:
    saved: dict[str, object] = {}
    settings = {"min_student_version": "2.6.0", "min_teacher_version": "2.6.0"}
    monkeypatch.setattr(db, "get_app_version_settings", lambda: {**settings, **saved})
    monkeypatch.setattr(db, "update_app_version_settings", lambda fields: saved.update(fields) or {**settings, **saved})

    reply = diamondvoy.try_diamondvoy_app_version_action(
        "ilovalar versiyasini 2.7.0 yangilaylik", is_admin=True, lang="uz",
    )

    assert saved == {"min_student_version": "2.7.0", "min_teacher_version": "2.7.0"}
    assert reply is not None
