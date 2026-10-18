"""Guard the moderator recording and replay click path against regressions."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SpeakingLiveRecordingContractTests(unittest.TestCase):
    def test_moderator_join_starts_recording_and_end_stops_it_first(self):
        source = (ROOT / "backend/speaking_live_video.py").read_text()
        moderator = source.split("async def staff_live_video_moderator_token(", 1)[1].split("@router.get", 1)[0]
        ending = source.split("async def end_live_video_room(", 1)[1].split("@router.get", 1)[0]
        self.assertIn("start_recording_for_room", moderator)
        self.assertIn('"recording_status": recording_status', moderator)
        self.assertLess(ending.index("stop_recording_for_room"), ending.index('"DeleteRoom"'))

    def test_replay_requires_moderator_decision_and_expiry(self):
        source = (ROOT / "backend/speaking_live_recordings.py").read_text()
        self.assertIn("secrets.token_hex(16)", source)
        self.assertIn("secrets.compare_digest(token, expected)", source)
        self.assertIn('lesson.get("recording_status") != "attached"', source)
        self.assertIn("expiry <= datetime.now(timezone.utc)", source)
        self.assertIn('recording_status=\'expired\'', source)
        self.assertIn('status_code=409, detail="The recording is not ready yet"', source)

    def test_recording_finalizes_before_livekit_room_is_deleted(self):
        source = (ROOT / "backend/speaking_live_recordings.py").read_text()
        stopping = source.split("def stop_recording_for_room(", 1)[1].split("def _refresh_status(", 1)[0]
        self.assertLess(stopping.index('"StopEgress"'), stopping.index('"ListEgress"'))
        self.assertIn("time.monotonic() + 20", stopping)
        self.assertIn("remote_status in _TERMINAL", stopping)
        self.assertIn('next_status = "ready" if path.is_file()', stopping)

    def test_recording_route_supports_api_prefix_stripping_and_range_playback(self):
        source = (ROOT / "backend/speaking_live_recordings.py").read_text()
        stream = source.split("async def stream_recording(", 1)[1].split("def expire_recordings(", 1)[0]
        self.assertIn('@router.get("/speaking/live-lessons/{lesson_id}/recording/{token}")', source)
        self.assertIn('@router.get("/api/speaking/live-lessons/{lesson_id}/recording/{token}")', source)
        self.assertIn('media_type="video/mp4"', stream)
        self.assertIn('content_disposition_type="inline"', stream)
        # Starlette FileResponse honors byte Range headers, enabling seek and
        # progressive buffering on browser and native video players.
        self.assertIn("return FileResponse(path", stream)

    def test_site_replay_uses_an_inline_preloaded_video_player(self):
        source = (ROOT / "app/ui/speaking-live-lessons.tsx").read_text()
        self.assertIn('<video', source)
        self.assertIn('preload="auto"', source)
        self.assertNotIn('window.open(\n                                  lesson.recording_url', source)

    def test_mobile_live_schedule_chat_routes_work_with_or_without_api_prefix(self):
        routes = {
            "backend/speaking_live_lessons.py": [
                "/speaking/live-lessons",
            ],
            "backend/speaking_live_video.py": [
                "/speaking/live-video/rooms",
                "/speaking/live-video/rooms/{room_id}/token",
                "/speaking/live-video/rooms/{room_id}/session-state",
                "/speaking/live-video/rooms/{room_id}/messages",
                "/speaking/live-video/rooms/{room_id}/hand",
                "/speaking/live-video/rooms/{room_id}/media-permissions",
                "/speaking/live-video/rooms/{room_id}/media-permissions/request",
                "/speaking/live-video/rooms/{room_id}/heartbeat",
                "/speaking/live-video/rooms/{room_id}/leave",
                "/speaking/live-video/rooms/{room_id}/end",
            ],
            "backend/speaking_chats.py": [
                "/speaking/chat/users",
                "/speaking/chats",
                "/speaking/chats/{chat_id}/messages",
            ],
        }
        for filename, paths in routes.items():
            source = (ROOT / filename).read_text(encoding="utf-8")
            for path in paths:
                with self.subTest(file=filename, path=path):
                    self.assertIn(f'@router.', source)
                    self.assertIn(f'"{path}"', source)
                    self.assertIn(f'"/api{path}"', source)

    def test_schedule_prompts_in_three_languages_and_hides_raw_audit_json(self):
        source = (ROOT / "app/ui/speaking-live-lessons.tsx").read_text()
        self.assertEqual(source.count('recordingDecision:'), 3)
        self.assertIn('modal === "recordingDecision"', source)
        self.assertIn("historyDetails(item.action", source)
        self.assertNotIn("JSON.stringify(item.details", source)


if __name__ == "__main__":
    unittest.main()
