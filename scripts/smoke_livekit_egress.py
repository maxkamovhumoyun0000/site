"""End-to-end private MP4 smoke test for the production Egress worker.

Records only a public page for a few seconds; it never creates an application
lesson or touches a student recording. Its uniquely named artifacts are removed.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib import request

import jwt
from dotenv import dotenv_values


def main() -> None:
    env = dotenv_values(os.getenv("DIAMOND_SITE_ENV", "/root/diamond-site/.env"))
    url = str(env.get("LIVEKIT_URL") or "").replace("wss://", "https://").rstrip("/")
    key = str(env.get("LIVEKIT_API_KEY") or "")
    secret = str(env.get("LIVEKIT_API_SECRET") or "")
    if not (url.startswith("https://") and key and secret):
        raise RuntimeError("LiveKit is not configured")
    now = datetime.now(timezone.utc)
    room_name = f"diamond-egress-smoke-{uuid.uuid4().hex[:12]}"
    token = jwt.encode({"iss": key, "nbf": int(now.timestamp()) - 5,
                        "exp": int((now + timedelta(minutes=5)).timestamp()),
                        "video": {"roomRecord": True, "roomCreate": True, "roomList": True, "roomAdmin": True, "room": room_name}}, secret, algorithm="HS256")
    name = f"smoke-{uuid.uuid4().hex}.mp4"
    path = Path("/srv/diamond-live-recordings") / name

    def call(method: str, body: dict, service: str = "Egress") -> dict:
        req = request.Request(f"{url}/twirp/livekit.{service}/{method}",
                              data=json.dumps(body).encode(), method="POST",
                              headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        with request.urlopen(req, timeout=40) as response:
            return json.loads(response.read() or b"{}")

    egress_id = ""
    try:
        result = call("StartEgress", {"web": {"url": "https://diamond-education.uz"},
                                      "outputs": [{"file": {"file_type": "MP4", "filepath": f"/recordings/{name}"}}]})
        egress_id = str(result.get("egressId") or result.get("egress_id") or "")
        if not egress_id:
            raise RuntimeError("Egress did not return an ID")
        print("egress-started")
        time.sleep(8)
        call("StopEgress", {"egress_id": egress_id})
        for _ in range(30):
            data = call("ListEgress", {"egress_id": egress_id})
            items = data.get("items") or data.get("egresses") or []
            status = str(items[0].get("status") if items else "")
            if status in {"3", "EGRESS_COMPLETE", "COMPLETE"}:
                break
            if status in {"4", "5", "6", "EGRESS_FAILED", "EGRESS_ABORTED", "EGRESS_LIMIT_REACHED"}:
                raise RuntimeError(f"Egress failed with status {status}")
            time.sleep(2)
        if not path.is_file() or path.stat().st_size < 1024:
            raise RuntimeError("Egress did not create a playable MP4")
        print(f"recording-ok bytes={path.stat().st_size}")
    finally:
        if egress_id:
            try:
                call("StopEgress", {"egress_id": egress_id})
            except Exception:
                pass
        path.unlink(missing_ok=True)
        path.with_suffix(".mp4.json").unlink(missing_ok=True)

    # Exercise the exact TemplateSource used for scheduled classes as well.
    room_file = Path("/srv/diamond-live-recordings") / f"smoke-{uuid.uuid4().hex}.mp4"
    room_egress_id = ""
    publisher = None
    try:
        call("CreateRoom", {"name": room_name, "empty_timeout": 120}, "RoomService")
        publisher = subprocess.Popen(
            ["/tmp/lk", "room", "join", "--identity", "egress-smoke", "--publish-demo", room_name],
            env={**os.environ, "LIVEKIT_URL": str(env["LIVEKIT_URL"]), "LIVEKIT_API_KEY": key, "LIVEKIT_API_SECRET": secret},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(20):
            participants = call("ListParticipants", {"room": room_name}, "RoomService").get("participants") or []
            if participants:
                break
            if publisher.poll() is not None:
                raise RuntimeError("Demo publisher exited before joining")
            time.sleep(1)
        else:
            raise RuntimeError("Demo publisher could not join the test room")
        response = call("StartEgress", {"room_name": room_name, "template": {"layout": "grid"},
                                        "outputs": [{"file": {"file_type": "MP4", "filepath": f"/recordings/{room_file.name}"}}]})
        room_egress_id = str(response.get("egressId") or response.get("egress_id") or "")
        if not room_egress_id:
            raise RuntimeError("Room recording did not return an ID")
        print("room-egress-started")
        time.sleep(8)
        call("StopEgress", {"egress_id": room_egress_id})
        for _ in range(30):
            result = call("ListEgress", {"egress_id": room_egress_id})
            items = result.get("items") or result.get("egresses") or []
            status = str(items[0].get("status") if items else "")
            if status in {"3", "EGRESS_COMPLETE", "COMPLETE"}:
                break
            if status in {"4", "5", "6", "EGRESS_FAILED", "EGRESS_ABORTED", "EGRESS_LIMIT_REACHED"}:
                raise RuntimeError(f"Room Egress failed with status {status}")
            time.sleep(2)
        if not room_file.is_file() or room_file.stat().st_size < 1024:
            raise RuntimeError("Room Egress did not create an MP4")
        print(f"room-recording-ok bytes={room_file.stat().st_size}")
    finally:
        if publisher and publisher.poll() is None:
            publisher.terminate()
            try:
                publisher.wait(timeout=5)
            except subprocess.TimeoutExpired:
                publisher.kill()
        if room_egress_id:
            try:
                call("StopEgress", {"egress_id": room_egress_id})
            except Exception:
                pass
        try:
            call("DeleteRoom", {"room": room_name}, "RoomService")
        except Exception:
            pass
        room_file.unlink(missing_ok=True)
        room_file.with_suffix(".mp4.json").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
