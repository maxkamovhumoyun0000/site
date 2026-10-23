from __future__ import annotations

import asyncio
import io
import zipfile

import pytest
from fastapi import HTTPException, Request, Response, UploadFile

import auth as account_auth
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


def _http_request(method: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({
        "type": "http",
        "method": method,
        "path": "/auth/test",
        "query_string": b"",
        "headers": raw_headers,
        "server": ("diamond-education.uz", 443),
        "client": ("127.0.0.1", 12345),
        "scheme": "https",
    })


def test_browser_auth_cookie_is_first_party_secure_httponly_and_host_only() -> None:
    response = Response()
    request = _http_request("POST", {"origin": "https://diamond-education.uz"})

    assert api._set_web_auth_cookie(response, request, "opaque-session-token") is True
    cookie = response.headers["set-cookie"].lower()
    assert "diamond_session=opaque-session-token" in cookie
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie
    assert "domain=" not in cookie

    external = Response()
    telegram_request = _http_request("POST", {"origin": "https://web.telegram.org"})
    assert api._set_web_auth_cookie(external, telegram_request, "opaque-session-token") is False
    assert "set-cookie" not in external.headers


def test_cookie_authenticated_write_rejects_cross_origin_and_accepts_same_origin() -> None:
    cross_site = _http_request("POST", {
        "origin": "https://attacker.invalid",
        "cookie": "diamond_session=opaque-session-token",
    })
    called = False

    async def should_not_run(_request: Request) -> Response:
        nonlocal called
        called = True
        return Response()

    blocked = asyncio.run(api.cookie_session_auth_and_csrf(cross_site, should_not_run))
    assert blocked.status_code == 403
    assert called is False

    first_party = _http_request("POST", {
        "origin": "https://diamond-education.uz",
        "cookie": "diamond_session=opaque-session-token",
        "authorization": "Bearer cookie-session:non-secret-marker",
    })

    async def inspect_rewritten_auth(request: Request) -> Response:
        assert dict(request.scope["headers"])[b"authorization"] == b"Bearer opaque-session-token"
        return Response(content="ok")

    allowed = asyncio.run(api.cookie_session_auth_and_csrf(first_party, inspect_rewritten_auth))
    assert allowed.status_code == 200


def test_legacy_register_route_cannot_create_privileged_accounts() -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(api.register())
    assert error.value.status_code == 410


def test_scheduled_arena_run_update_rejects_untrusted_column_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(database, "ensure_arena_extras_schema", lambda: pytest.fail("schema should not run before validation"))

    with pytest.raises(ValueError, match="Unsupported scheduled arena run fields"):
        database.update_scheduled_arena_run(1, **{"status=1; DROP TABLE users; --": "finished"})


def test_admin_created_password_is_hashed_before_database_write(monkeypatch: pytest.MonkeyPatch) -> None:
    writes: list[tuple[str, tuple[object, ...]]] = []

    class Cursor:
        def execute(self, query: str, params: tuple[object, ...]) -> None:
            writes.append((query, params))

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

        def commit(self) -> None:
            pass

        def close(self) -> None:
            pass

    monkeypatch.setattr(account_auth, "generate_login_id", lambda **_kwargs: "ST1234")
    monkeypatch.setattr(account_auth, "validate_login_id", lambda _candidate: {"valid": True, "errors": []})
    monkeypatch.setattr(account_auth, "get_user_by_login_id", lambda _candidate: None)
    monkeypatch.setattr(account_auth, "audit_login_id", lambda *_args: {"requires_attention": False})
    monkeypatch.setattr(account_auth, "generate_password", lambda _length: "AbC123")
    monkeypatch.setattr(account_auth, "create_user", lambda **_kwargs: {"id": 42})
    monkeypatch.setattr(account_auth, "hash_password", lambda value: f"bcrypt:{value.upper()}")
    monkeypatch.setattr(account_auth, "get_conn", Connection)

    created = account_auth.create_user_sync("A", "B", "12345", "English", 1)

    assert created["password"] == "AbC123"
    assert writes[0][1][1] == "bcrypt:ABC123"


def test_legacy_plaintext_login_is_upgraded_to_case_compatible_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    user = {"id": 51, "login_id": "ST0051", "password": "Abc123", "blocked": 0}
    writes: list[tuple[object, ...]] = []

    class Cursor:
        rowcount = 1

        def execute(self, query: str, params: tuple[object, ...]) -> None:
            if query.startswith("UPDATE users SET password="):
                writes.append(params)

        def fetchone(self) -> dict | None:
            return user

    class Connection:
        def __init__(self, has_user: bool) -> None:
            self.has_user = has_user

        def cursor(self) -> Cursor:
            return Cursor()

        def commit(self) -> None:
            pass

        def close(self) -> None:
            pass

    connections = iter([Connection(True), Connection(False)])
    monkeypatch.setattr(database, "get_conn", lambda: next(connections))
    monkeypatch.setattr(database, "is_login_throttled", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(database, "clear_login_throttle", lambda *_args: None)
    monkeypatch.setattr(database, "clear_failed_logins", lambda *_args: None)

    upgraded, status = database.verify_login("ST0051", "abc123")

    assert status == "ok"
    assert upgraded is not None
    assert database.is_password_hash(upgraded["password"])
    assert database.verify_password("abc123", upgraded["password"])
    assert writes and writes[0][0].startswith("$2b$")
