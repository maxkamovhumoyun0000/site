from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LiveVideoRoomLifecycleContractTests(unittest.TestCase):
    def test_only_host_end_deletes_the_sfu_room(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )

        leave_start = source.index("async def leave_live_video_room")
        end_start = source.index("async def end_live_video_room", leave_start)
        staff_start = source.index("async def staff_list_live_video_rooms", end_start)
        leave = source[leave_start:end_start]
        end = source[end_start:staff_start]

        self.assertNotIn('_livekit_room_request("DeleteRoom"', leave)
        self.assertIn('_livekit_room_request(', end)
        self.assertIn('"DeleteRoom",', end)
        self.assertIn('{"room": room_id},', end)
        self.assertIn("Only the host can end this live video room", end)
        self.assertIn("status='ending'", end)
        self.assertIn("status='active'", end)
        self.assertIn("status='ended'", end)
        self.assertIn("ignore_not_found=True", end)
