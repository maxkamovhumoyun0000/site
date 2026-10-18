"""Write the main-server Egress configuration without printing or committing secrets.

Run only on the production host after its .env and private Redis SSH tunnel
are present. The output lives outside the code deployment directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import dotenv_values


def main() -> None:
    env_path = Path(os.getenv("DIAMOND_SITE_ENV") or Path(__file__).resolve().parents[1] / ".env")
    env = dotenv_values(env_path)
    ws_url = str(env.get("LIVEKIT_URL") or "").strip()
    key = str(env.get("LIVEKIT_API_KEY") or "").strip()
    secret = str(env.get("LIVEKIT_API_SECRET") or "").strip()
    if not (ws_url.startswith("wss://") and key and secret):
        raise RuntimeError("LIVEKIT_URL/API_KEY/API_SECRET must be configured")
    config = {"api_key": key, "api_secret": secret, "ws_url": ws_url,
              "redis": {"address": "127.0.0.1:16379"}, "log_level": "info"}
    destination = Path("/etc/diamond-livekit-egress.json")
    temporary = destination.with_suffix(".tmp")
    old_umask = os.umask(0o077)
    try:
        temporary.write_text(json.dumps(config), encoding="utf-8")
        # The official image runs as uid 1001, gid 0. Group-root read access
        # lets it load the secret without making the config world-readable.
        os.chmod(temporary, 0o640)
        temporary.replace(destination)
    finally:
        os.umask(old_umask)
    recordings = Path("/srv/diamond-live-recordings")
    recordings.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chown(recordings, 1001, 0)
    os.chmod(recordings, 0o700)
    print("LiveKit Egress configuration and private recording directory ready")


if __name__ == "__main__":
    main()
