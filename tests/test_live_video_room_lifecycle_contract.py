from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LiveVideoRoomLifecycleContractTests(unittest.TestCase):
    def test_room_list_serializes_active_status(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )
        serializer_start = source.index("def _serialize_room(")
        serializer_end = source.index("\n\ndef _active_room_or_error", serializer_start)
        serializer = source[serializer_start:serializer_end]

        self.assertIn('"status": str(row.get("status") or "")', serializer)

    def test_room_creation_is_staff_only(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )
        create_start = source.index("async def create_live_video_room(")
        token_start = source.index("async def live_video_room_token(", create_start)
        create_endpoint = source[create_start:token_start]

        self.assertIn("_require_staff(authorization)", create_endpoint)

    def test_host_or_authorized_staff_end_deletes_the_sfu_room(self) -> None:
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
        self.assertIn("_require_active_staff(authorization)", end)
        self.assertIn("status='ending'", end)
        self.assertIn("status='active'", end)
        self.assertIn("status='ended'", end)
        self.assertIn("ignore_not_found=True", end)

    def test_web_moderator_token_is_staff_only_and_room_scoped(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )
        start = source.index("async def staff_live_video_moderator_token(")
        end = source.index("@router.post(\"/staff/speaking/live-video/rooms/{room_id}/participants/remove\")", start)
        endpoint = source[start:end]

        self.assertIn("_require_active_staff(authorization)", endpoint)
        self.assertIn('"room": room_id', endpoint)
        self.assertIn('"roomAdmin": True', endpoint)
        self.assertIn('"is_moderator": True', endpoint)

    def test_moderator_tokens_are_unique_per_device_session(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )
        start = source.index("async def staff_live_video_moderator_token(")
        end = source.index("@router.post(\"/staff/speaking/live-video/rooms/{room_id}/participants/remove\")", start)
        endpoint = source[start:end]

        self.assertIn("payload: LiveVideoModeratorTokenRequest | None", endpoint)
        self.assertIn('identity = f"speaking-admin-{user_id}-{session_id}"', endpoint)
        self.assertIn("device_name", endpoint)

    def test_regular_speaking_app_token_never_gets_moderator_grant(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )
        start = source.index("async def live_video_room_token(")
        end = source.index("@router.post(\"/staff/speaking/live-video/rooms/{room_id}/moderator-token\")", start)
        endpoint = source[start:end]

        self.assertIn('"roomAdmin": False', endpoint)

    def test_student_media_publish_is_source_scoped_and_not_enabled_on_join(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )
        start = source.index("async def live_video_room_token(")
        end = source.index(
            '@router.post("/staff/speaking/live-video/rooms/{room_id}/moderator-token")',
            start,
        )
        endpoint = source[start:end]

        self.assertIn('"canPublish": bool(publish_sources)', endpoint)
        self.assertIn('"canPublishSources": publish_sources', endpoint)
        self.assertNotIn('"canPublish": True', endpoint)
        self.assertIn('return ["SCREEN_SHARE", *[source for source in ("MICROPHONE", "CAMERA")', source)

    def test_moderator_permission_decision_updates_livekit_server_permissions(self) -> None:
        source = (ROOT / "backend" / "speaking_live_video.py").read_text(
            encoding="utf-8"
        )
        start = source.index("async def decide_live_video_media_permission(")
        end = source.index(
            '@router.post("/staff/speaking/live-video/rooms/{room_id}/participants/remove")',
            start,
        )
        endpoint = source[start:end]

        self.assertIn("_require_active_staff(authorization)", endpoint)
        self.assertIn("_sync_livekit_publish_permissions(room_id, identity, sources)", endpoint)
        self.assertIn("status='approved'", endpoint)
        self.assertIn('"canPublishSources": sources', source)
