"""Regression tests for the October 2026 security audit (security-audit/).

Every test uses monkeypatched collaborators or synthetic data; none needs a
real database, Redis instance, Telegram bot or network access.
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException, Request, Response

import backend.main as api
from logging_config import SensitiveDataFilter


def _request(method: str = "GET", path: str = "/student/tests", headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({
        "type": "http",
        "method": method,
        "scheme": "https",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 443),
    })


# --- SA-02: cookie sessions must not skip the access-guard middlewares -------

def test_guard_authorization_uses_session_cookie_when_header_missing() -> None:
    request = _request(headers={"cookie": f"{api.WEB_AUTH_COOKIE_NAME}=opaque-jwt"})
    assert api._guard_authorization(request) == "Bearer opaque-jwt"


def test_guard_authorization_uses_cookie_when_header_is_marker() -> None:
    request = _request(headers={
        "cookie": f"{api.WEB_AUTH_COOKIE_NAME}=opaque-jwt",
        "authorization": f"Bearer {api.WEB_AUTH_COOKIE_MARKER}marker",
    })
    assert api._guard_authorization(request) == "Bearer opaque-jwt"


def test_guard_authorization_prefers_real_bearer_header() -> None:
    request = _request(headers={
        "cookie": f"{api.WEB_AUTH_COOKIE_NAME}=cookie-jwt",
        "authorization": "Bearer header-jwt",
    })
    assert api._guard_authorization(request) == "Bearer header-jwt"


def test_pending_approval_guard_blocks_cookie_only_request(monkeypatch: pytest.MonkeyPatch) -> None:
    pending_user = {"id": 9, "login_type": 1, "login_id": "ST0009", "public_signup": 1,
                    "pending_approval": 1, "access_enabled": 0, "blocked": 0}
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: pending_user)
    request = _request(path="/student/dashboard", headers={"cookie": f"{api.WEB_AUTH_COOKIE_NAME}=opaque-jwt"})

    async def should_not_run(_request: Request) -> Response:
        raise AssertionError("pending account reached the route through a cookie session")

    response = asyncio.run(api.public_registration_approval_guard(request, should_not_run))
    assert response.status_code == 403


def test_developer_guard_confines_cookie_only_request(monkeypatch: pytest.MonkeyPatch) -> None:
    developer = {"id": 3, "login_type": 4, "login_id": "DEVELOPER-X-01"}
    monkeypatch.setattr(api, "_user_row_from_bearer", lambda _auth: developer)
    monkeypatch.delenv("DEVELOPER_WEB_LOGIN_ID", raising=False)
    request = _request(path="/admin/users", headers={"cookie": f"{api.WEB_AUTH_COOKIE_NAME}=opaque-jwt"})

    async def should_not_run(_request: Request) -> Response:
        raise AssertionError("developer account escaped its workspace through a cookie session")

    response = asyncio.run(api.developer_workspace_access_guard(request, should_not_run))
    assert response.status_code == 403


# --- SA-01: Telegram initData must fail closed --------------------------------

def test_telegram_init_data_fails_closed_without_bot_tokens_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_telegram_bot_tokens", lambda: [])
    monkeypatch.setattr(api, "_is_production", True)
    with pytest.raises(HTTPException) as error:
        api._parse_and_validate_telegram_init_data("user=%7B%22id%22%3A1%7D", 1)
    assert error.value.status_code == 503


def test_telegram_init_data_requires_auth_date(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import hmac
    from urllib.parse import urlencode

    bot_token = "123456:synthetic-test-token-not-real"
    monkeypatch.setattr(api, "_telegram_bot_tokens", lambda: [bot_token])
    fields = {"user": '{"id": 42}'}
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    with pytest.raises(HTTPException) as error:
        api._parse_and_validate_telegram_init_data(urlencode(fields), 42)
    assert error.value.status_code == 401


# --- SA-04: reserved role login IDs ------------------------------------------

@pytest.mark.parametrize("login_id", ["DIAMOND-SP-1", "diamond-sp-1", "DEVELOPER-X-01", "DEVELOPER-X-02"])
def test_public_registration_rejects_reserved_role_login_ids(login_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEVELOPER_WEB_LOGIN_ID", raising=False)
    monkeypatch.delenv("SPEAKING_ADMIN_WEB_LOGIN_ID", raising=False)
    with pytest.raises(HTTPException) as error:
        api._public_registration_login_id(login_id)
    assert error.value.status_code == 422


def test_public_registration_accepts_normal_login_id() -> None:
    assert api._public_registration_login_id("alisher_99") == "ALISHER_99"


# --- SA-05: gamified answer oracle --------------------------------------------

class _FakeRedis:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.strings: dict[str, str] = {}

    def hincrby(self, key: str, field: str, amount: int) -> int:
        bucket = self.hashes.setdefault(key, {})
        bucket[field] = str(int(bucket.get(field, "0")) + amount)
        return int(bucket[field])

    def hsetnx(self, key: str, field: str, value: str) -> int:
        bucket = self.hashes.setdefault(key, {})
        if field in bucket:
            return 0
        bucket[field] = str(value)
        return 1

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def expire(self, key: str, seconds: int) -> bool:
        return True

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        if nx and key in self.strings:
            return False
        self.strings[key] = value
        return True


def test_first_checked_answer_is_the_scored_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(api, "_REDIS_CLIENT", fake)
    questions = [{"index": 0, "type": "mcq", "_answer": 2}]
    # Student probes option 0 (wrong) first, then 2 (correct).
    api._gamified_record_first_check("s1", "a:0", "0")
    api._gamified_record_first_check("s1", "a:0", "2")
    answers = api._gamified_apply_first_checks("s1", questions, {0: 2})
    assert answers[0] == 0


def test_first_checked_pair_is_the_scored_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeRedis()
    monkeypatch.setattr(api, "_REDIS_CLIENT", fake)
    questions = [{"index": 3, "type": "word_match", "_answer": {"cat": "mushuk", "dog": "it"}}]
    api._gamified_record_first_check("s2", "p:3\x1fcat", "it")
    api._gamified_record_first_check("s2", "p:3\x1fcat", "mushuk")
    answers = api._gamified_apply_first_checks("s2", questions, {3: {"cat": "mushuk", "dog": "it"}})
    assert answers[3] == {"cat": "it", "dog": "it"}


def test_unchecked_questions_keep_submitted_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_REDIS_CLIENT", _FakeRedis())
    questions = [{"index": 0, "type": "mcq", "_answer": 1}]
    assert api._gamified_apply_first_checks("s3", questions, {0: 1}) == {0: 1}


def test_answer_check_cap_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_REDIS_CLIENT", _FakeRedis())
    monkeypatch.setattr(api, "_GAMIFIED_MAX_CHECKS_PER_SESSION", 3)
    for i in range(3):
        api._gamified_record_first_check("s4", f"a:{i}", "0")
    with pytest.raises(HTTPException) as error:
        api._gamified_record_first_check("s4", "a:9", "0")
    assert error.value.status_code == 429


# --- SA-07: constant-time chat media signature --------------------------------

def test_chat_media_signature_check() -> None:
    good = api._chat_media_signature("photo.png")
    assert api._chat_media_signature_ok(good, "photo.png") is True
    assert api._chat_media_signature_ok("0" * len(good), "photo.png") is False
    assert api._chat_media_signature_ok("", "photo.png") is False


# --- SA-13: log redaction gaps ------------------------------------------------

@pytest.mark.parametrize("message, secret", [
    ('{"password": "Sup3rSecret!"}', "Sup3rSecret!"),
    ("{'session_string': 'BQAsyntheticsession'}", "BQAsyntheticsession"),
    ("GET https://api.telegram.org/bot1234567890:AAH-synthetic_token_value_abcdefghijk/sendMessage",
     "AAH-synthetic_token_value_abcdefghijk"),
    ("connect postgresql://diamond:dbpass123@127.0.0.1/diamond", "dbpass123"),
    ("api_hash=0123456789abcdef0123", "0123456789abcdef0123"),
])
def test_log_filter_redacts_additional_secret_shapes(message: str, secret: str) -> None:
    assert secret not in SensitiveDataFilter.redact(message)


def test_log_filter_keeps_plain_text() -> None:
    assert SensitiveDataFilter.redact("student opened lesson 12") == "student opened lesson 12"


# --- Sessions: 30-day bound and server-side session id required --------------

def test_token_without_session_id_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(api, "_auth_user_row_cached", lambda _uid: {"id": 5, "login_type": 1, "session_version": 1, "blocked": 0})
    api._AUTH_USER_ROW_CACHE.clear()
    legacy = pyjwt.encode(
        {"sub": "5", "sv": 1, "exp": datetime.now(timezone.utc) + timedelta(days=1)},
        api.SECRET_KEY,
        algorithm=api.ALGORITHM,
    )
    with pytest.raises(HTTPException) as error:
        api._user_row_from_bearer(f"Bearer {legacy}")
    assert error.value.status_code == 401


def test_token_without_exp_is_rejected() -> None:
    import jwt as pyjwt

    token = pyjwt.encode({"sub": "5", "sid": "ws_x"}, api.SECRET_KEY, algorithm=api.ALGORITHM)
    with pytest.raises(HTTPException) as error:
        api._decode_bearer_payload(f"Bearer {token}")
    assert error.value.status_code == 401


def test_access_token_lifetime_is_capped_at_30_days(monkeypatch: pytest.MonkeyPatch) -> None:
    import jwt as pyjwt

    user = {"id": 8, "login_type": 1, "login_id": "ST0008", "session_version": 1}
    monkeypatch.setattr(api, "_build_user_payload", lambda _u: type("P", (), {"id": 8, "role": "student", "login_type": 1, "login_id": "ST0008"})())
    token = api._create_access_token(user, session_id="ws_test", ttl_hours=24 * 365)
    claims = pyjwt.decode(token, api.SECRET_KEY, algorithms=[api.ALGORITHM])
    assert claims["exp"] - claims["iat"] <= 30 * 24 * 3600
    assert claims["sid"] == "ws_test"


# --- Admin scoping: env-configured admin logins resolve to their chat ids -----

def test_custom_limited_admin_login_maps_to_limited_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "ADMIN_CHAT_IDS", [111])
    monkeypatch.setattr(api, "LIMITED_ADMIN_CHAT_IDS", [222, 333])
    monkeypatch.setenv("LIMITED_ADMIN_WEB_LOGIN_2", "branch-two-admin")
    ref = api._admin_ref_id({"id": 99, "login_type": 4, "login_id": "BRANCH-TWO-ADMIN"})
    assert ref == 333
    assert api._is_general_admin_scope(ref) is False


def test_limited_admin_cannot_manage_other_branch_student(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "ADMIN_CHAT_IDS", [111])
    monkeypatch.setattr(api, "LIMITED_ADMIN_CHAT_IDS", [222, 333])
    other_branch_student = {"id": 5, "login_type": 2, "owner_admin_id": 333}
    assert api._can_manage_user_globally(222, other_branch_student) is False
    assert api._can_manage_user_globally(333, other_branch_student) is True
    assert api._can_manage_user_globally(111, other_branch_student) is True


# --- Teacher assignment targets -----------------------------------------------

def test_teacher_cannot_assign_to_foreign_group_or_student(monkeypatch: pytest.MonkeyPatch) -> None:
    teacher = {"id": 7, "login_type": 3, "login_id": "TC0007"}
    monkeypatch.setattr(api, "get_group", lambda gid: {"id": gid, "teacher_id": 99})
    monkeypatch.setattr(api, "teacher_has_temporary_group_access", lambda *_a: False)
    monkeypatch.setattr(api, "_teacher_student_ids", lambda _tid: {1, 2})
    with pytest.raises(HTTPException):
        api._require_teacher_assignment_targets(teacher, group_id=50, student_ids=[])
    with pytest.raises(HTTPException):
        api._require_teacher_assignment_targets(teacher, group_id=None, student_ids=[1, 3])
    api._require_teacher_assignment_targets(teacher, group_id=None, student_ids=[1, 2])


# --- Telegram bot sessions expire after 30 idle days ---------------------------

def test_bot_session_expires_after_30_idle_days(monkeypatch: pytest.MonkeyPatch) -> None:
    import auth as bot_auth
    from datetime import datetime, timedelta

    class _Cursor:
        def __init__(self, row):
            self._row = row

        def execute(self, *_args):
            return None

        def fetchone(self):
            return self._row

    class _Conn:
        def __init__(self, row):
            self._row = row

        def cursor(self):
            return _Cursor(self._row)

        def close(self):
            return None

    fresh = {"logged_in": 1, "last_activity": (datetime.now() - timedelta(days=3)).isoformat(), "last_login_at": None}
    stale = {"logged_in": 1, "last_activity": (datetime.now() - timedelta(days=45)).isoformat(), "last_login_at": None}
    monkeypatch.setattr(bot_auth, "get_conn", lambda: _Conn(fresh))
    assert bot_auth.validate_user_session(1) is True
    monkeypatch.setattr(bot_auth, "get_conn", lambda: _Conn(stale))
    assert bot_auth.validate_user_session(1) is False
