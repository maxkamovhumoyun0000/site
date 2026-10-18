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

    def test_schedule_prompts_in_three_languages_and_hides_raw_audit_json(self):
        source = (ROOT / "app/ui/speaking-live-lessons.tsx").read_text()
        self.assertEqual(source.count('recordingDecision:'), 3)
        self.assertIn('modal === "recordingDecision"', source)
        self.assertIn("historyDetails(item.action", source)
        self.assertNotIn("JSON.stringify(item.details", source)


if __name__ == "__main__":
    unittest.main()
