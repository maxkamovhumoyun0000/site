from __future__ import annotations

import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

import backend.main as api
import db as database


def _admin(login_id: str, user_id: int = 7) -> dict:
    return {"id": user_id, "login_type": 4, "login_id": login_id}


def test_global_system_endpoints_are_limited_to_main_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "ADMIN_CHAT_IDS", [100])
    monkeypatch.setattr(api, "LIMITED_ADMIN_CHAT_IDS", [200])
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _admin("DIAMOND-LIM-1"))

    with pytest.raises(HTTPException) as settings_error:
        asyncio.run(api.admin_system_settings("Bearer test"))
    assert settings_error.value.status_code == 403

    with pytest.raises(HTTPException) as startup_error:
        asyncio.run(api.admin_startup_check("Bearer test"))
    assert startup_error.value.status_code == 403


def test_system_settings_never_return_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "ADMIN_CHAT_IDS", [100])
    monkeypatch.setattr(api, "LIMITED_ADMIN_CHAT_IDS", [200])
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: _admin("DIAMOND-ADM-1"))
    monkeypatch.setattr(api, "get_economy_rule_settings", lambda: {})
    monkeypatch.setattr(api, "count_available_daily_tests_global", lambda: 0)
    monkeypatch.setattr(api, "_support_metrics_payload", lambda: {})
    monkeypatch.setenv("DATABASE_URL", "postgresql://private:must-not-leak@example.invalid/db")

    payload = asyncio.run(api.admin_system_settings("Bearer test"))

    assert payload["is_main_admin"] is True
    assert "database_url" not in payload
    assert "must-not-leak" not in repr(payload)


def test_startup_check_redacts_database_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "DATABASE_URL", "postgresql://private:must-not-leak@example.invalid/db")
    monkeypatch.setattr(api, "get_conn", lambda: (_ for _ in ()).throw(RuntimeError("password=must-not-leak")))

    payload = api._startup_validation_report()

    assert "database_url" not in payload
    assert "must-not-leak" not in repr(payload)
    connection_check = next(item for item in payload["checks"] if item["name"] == "database_connection")
    assert connection_check == {"name": "database_connection", "ok": False, "error": "connection_failed"}


def test_chat_uploads_require_content_signature() -> None:
    valid_png = b"\x89PNG\r\n\x1a\n" + b"test"
    fake_png = b"GIF89a" + b"test"

    assert api._upload_content_matches_extension(valid_png, ".png") is True
    assert api._upload_content_matches_extension(fake_png, ".png") is False
    assert api._upload_content_matches_extension(b"not a pdf", ".pdf") is False
    assert api._upload_content_matches_extension(b"%PDF-1.7 test", ".pdf") is True


def test_office_upload_requires_matching_office_container() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")

    assert api._upload_content_matches_extension(buffer.getvalue(), ".docx") is True
    assert api._upload_content_matches_extension(buffer.getvalue(), ".xlsx") is False
    assert api._upload_content_matches_extension(b"PK\x03\x04not a zip", ".docx") is False


def test_upload_reader_stops_after_limit_plus_one_byte() -> None:
    upload = UploadFile(filename="oversized.txt", file=io.BytesIO(b"0123456789"))

    with pytest.raises(HTTPException) as error:
        asyncio.run(api._read_upload_limited(upload, 4))

    assert error.value.status_code == 413


def test_login_throttle_keeps_a_bounded_fallback_when_db_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    throttle_key = "security-test-fallback-unique"
    database._fallback_login_clear(throttle_key)
    monkeypatch.setattr(
        database,
        "ensure_login_throttle_schema",
        lambda: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )

    assert database.is_login_throttled(throttle_key, max_failures=2) is False
    database.record_login_failure(throttle_key)
    assert database.is_login_throttled(throttle_key, max_failures=2) is False
    database.record_login_failure(throttle_key)
    assert database.is_login_throttled(throttle_key, max_failures=2) is True
