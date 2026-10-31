from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_speaking_profile_uses_real_profile_progress_and_level_sources():
    source = _read("backend/speaking_social.py")
    assert '@router.get("/api/speaking/profile/me")' in source
    assert "def _profile_payload(" in source
    assert '"speaking": stats' in source
    assert '"levels": _levels(user_id, row)' in source
    assert '"points": _points(user_id)' in source
    assert "results_for(int(user_id))" in source
    assert "speaking_answer_analyses" in source
    assert "speaking_exams" in source
    assert "badge_progress" in source
    assert "ensure_tables()" in source


def test_speaking_profile_exposes_owner_scoped_stats_levels_and_badges():
    source = _read("backend/speaking_social.py")
    for path in ("stats", "levels", "badges", "sessions"):
        assert f'@router.get("/api/speaking/profile/{path}")' in source
    section = source.split('async def speaking_profile_stats', 1)[1].split(
        '@router.get("/speaking/profile/levels")', 1
    )[0]
    assert "viewer = _viewer(authorization)" in section
    assert "int(viewer.get(\"id\") or 0)" in section


def test_standalone_speaking_credential_update_reauthenticates_and_rotates_sessions():
    source = _read("backend/speaking_social.py")
    assert '@router.patch("/api/speaking/profile/credentials")' in source
    section = source.split("async def update_speaking_profile_credentials", 1)[1].split(
        '@router.patch("/speaking/profile/me")', 1
    )[0]
    assert "is_speaking_app_account(viewer.get(\"speaking_app_account\"))" in section
    assert "verify_password(payload.current_password" in section
    assert "UPPER(login_id)=?" in section
    assert "WHERE id=? AND password=? AND login_id=?" in section
    assert 'reason="speaking_credentials_changed"' in section
    assert 'source="speaking_credentials_change"' in section
    assert "_create_access_token(" in section
    assert "current_password: str" in source
    assert "Password must be no more than 72 UTF-8 bytes" in source


def test_session_listing_is_owner_scoped_and_returns_only_active_sessions():
    source = _read("backend/main.py")
    section = source.split('async def list_user_sessions', 1)[1].split(
        '@app.delete("/user/account")', 1
    )[0]
    assert "WHERE user_id=?" in section
    assert "revoked_at IS NULL" in section
    assert "expires_at > ?" in section
    assert '"is_current": sid == current_session_id' in section
    profile_source = _read("backend/speaking_social.py")
    profile_sessions = profile_source.split("async def speaking_profile_sessions", 1)[1].split(
        '@router.patch("/speaking/profile/credentials")', 1
    )[0]
    assert "_viewer(authorization)" in profile_sessions
    assert "return await list_user_sessions(authorization)" in profile_sessions


def test_limited_admin_directory_is_global_read_only_and_restores_requested_pages():
    config = _read("app/ui/navigation-config.ts")
    limited = config.split('limited_admin: [', 1)[1].split('],', 1)[0]
    for section in (
        "study-room", "family-groups", "purchases", "homework", "leaderboard",
        "kpi", "attendance", "analytics", "holidays", "broadcasts", "surveys",
        "domain-email", "admin-callbacks", "voice-rooms",
    ):
        assert f'"{section}"' in limited

    source = _read("backend/main.py")
    listing = source.split("async def admin_users(", 1)[1].split("@app.get(\"/admin/proctoring/sessions\")", 1)[0]
    search = source.split("async def admin_search_users(", 1)[1].split("@app.get(\"/admin/users/suggest\")", 1)[0]
    assert "_limited_admin_owner_scope_sql" not in listing
    assert "_limited_admin_owner_scope_sql" not in search
    detail = source.split("async def admin_user_detail(", 1)[1].split("def _parse_price_text_value", 1)[0]
    assert "_can_manage_user_globally(admin_ref, target)" in detail


def test_password_writes_use_bcrypt_hashing_helpers_not_raw_payload_passwords():
    db = _read("db.py")
    auth = _read("auth.py")
    assert "hash_password(password)" in db
    assert "hash_password(password)" in auth
    assert "hash_password(password_clean.upper())" in db
    assert "verify_password(password_clean, stored_password)" in db
