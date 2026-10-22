from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scheduled_subjects_include_english_ielts_and_cefr() -> None:
    lessons = (ROOT / "backend/speaking_live_lessons.py").read_text(encoding="utf-8")
    video = (ROOT / "backend/speaking_live_video.py").read_text(encoding="utf-8")
    for subject in ('"english"', '"ielts"', '"cefr"'):
        assert subject in lessons[lessons.index("def _normalise_payload"):lessons.index("@lru_cache")]
        assert subject in video[video.index("def _subject("):video.index("def _room_id(")]


def test_live_cannot_start_before_scheduled_time_even_via_api() -> None:
    source = (ROOT / "backend/speaking_live_lessons.py").read_text(encoding="utf-8")
    start = source[source.index("def _open_live_video_room("):source.index("@router.post(\"/staff/speaking/live-lessons/{lesson_id}/recording\")")]
    assert 'if _iso_datetime(str(lesson["starts_at"])) > datetime.now(timezone.utc):' in start
    assert "_ensure_livekit_room(room_id, initial_state)" in start
    assert start.index("Lesson cannot start before its scheduled time") < start.index("_ensure_livekit_room(room_id, initial_state)")
    worker = source[source.index("async def speaking_live_lesson_reminder_worker()"):]
    assert "start <= now" in worker
    assert "-1 <= minutes_left <= 5" not in worker


def test_speaking_admin_navigation_uses_schedule_not_separate_live_page() -> None:
    nav = (ROOT / "app/ui/navigation-config.ts").read_text(encoding="utf-8")
    admin = nav[nav.index('speaking_admin: ['):nav.index('speaking_admin: [') + 240]
    assert '"speaking-schedule"' in admin
    assert '"speaking-live"' not in admin
    page = (ROOT / "app/page.tsx").read_text(encoding="utf-8")
    assert 'currentSection === "speaking-live"' not in page


def test_livekit_control_grants_room_admin_for_metadata_updates() -> None:
    source = (ROOT / "backend/speaking_live_video.py").read_text(encoding="utf-8")
    token = source[source.index("def _livekit_control_token("):source.index("def _livekit_room_request(")]
    assert '"roomAdmin": True' in token
    assert 'grants["room"] = room' in token


def test_moderator_room_has_no_lock_button() -> None:
    source = (ROOT / "app/ui/livekit-moderator-room.tsx").read_text(encoding="utf-8")
    assert "updateState({ locked:" not in source


def test_live_lessons_do_not_require_or_schedule_an_end_time() -> None:
    backend = (ROOT / "backend/speaking_live_lessons.py").read_text(encoding="utf-8")
    ui = (ROOT / "app/ui/speaking-live-lessons.tsx").read_text(encoding="utf-8")
    assert "ends_at: str | None" in backend  # legacy client compatibility only
    assert "ALTER COLUMN ends_at DROP NOT NULL" in backend
    assert "starts_at,auto_open_video_room" in backend
    assert "SET title=?,topic=?,subject=?,moderator_name=?,audience_label=?,starts_at=?,auto_open_video_room" in backend
    assert "Lesson end time must be after start time" not in backend
    assert "ends_at" not in ui


def test_live_lessons_api_includes_ongoing_lessons_and_join_state() -> None:
    backend = (ROOT / "backend/speaking_live_lessons.py").read_text(encoding="utf-8")
    public_list = backend[backend.index("async def list_my_live_lessons"):backend.index("@router.get(\"/staff/speaking/live-lessons\")")]
    assert "WHERE status='live'" in public_list
    assert "can_join_live_video" in backend
    assert "ORDER BY CASE WHEN status='live' THEN 0 ELSE 1 END" in public_list


def test_livekit_webhook_verifies_body_and_finishes_schedule_idempotently() -> None:
    backend = (ROOT / "backend/speaking_live_video.py").read_text(encoding="utf-8")
    webhook = backend[backend.index("async def livekit_speaking_webhook"):backend.index("@router.get(\"/staff/speaking/live-video/rooms\")")]
    assert "jwt.decode(token, api_secret, algorithms=[\"HS256\"], issuer=api_key)" in webhook
    assert "hashlib.sha256(raw_body).digest()" in webhook
    assert "event.get(\"event\")" in webhook and "room_finished" in webhook
    assert "status='completed'" in webhook


def test_speaking_chat_compatibility_endpoints_exist() -> None:
    backend = (ROOT / "backend/speaking_chats.py").read_text(encoding="utf-8")
    for path in (
        '/api/speaking/chats/direct',
        '/api/speaking/chats/contacts',
        '/api/speaking/chats/direct/{target_user_id}',
        '/api/speaking/chats/community',
    ):
        assert path in backend


def test_speaking_community_is_a_distinct_channel_and_search_accepts_legacy_query_key() -> None:
    backend = (ROOT / "backend/speaking_chats.py").read_text(encoding="utf-8")
    main = (ROOT / "backend/main.py").read_text(encoding="utf-8")
    search = backend[backend.index("async def search_speaking_chat_users"):backend.index("async def list_speaking_direct_chats")]
    community = main[main.index("def _community_chat_thread_for_user"):main.index("def _community_chat_cleanup_expired_messages_if_due")]
    assert "query: str = Query(default=\"\"" in search
    assert "q: str | None = Query(default=None" in search
    assert "str(q if q is not None else query)" in search
    assert "normalized_channel not in {\"general\", \"speaking\"}" in community
    assert "_SPEAKING_COMMUNITY_CHAT_DIRECT_KEY" in community
    assert "_COMMUNITY_CHAT_DIRECT_KEY" in community
    assert "if normalized_channel == \"speaking\"" in community


def test_live_recordings_follow_seven_day_retention() -> None:
    lessons = (ROOT / "backend/speaking_live_lessons.py").read_text(encoding="utf-8")
    recordings = (ROOT / "backend/speaking_live_recordings.py").read_text(encoding="utf-8")
    video = (ROOT / "backend/speaking_live_video.py").read_text(encoding="utf-8")
    assert "RECORDING_RETENTION_DAYS = 7" in lessons
    assert "INTERVAL '7 days'" in lessons
    assert "INTERVAL '7 days'" in recordings
    assert "INTERVAL '7 days'" in video
