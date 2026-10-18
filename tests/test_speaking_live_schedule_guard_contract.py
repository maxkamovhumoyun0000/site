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
