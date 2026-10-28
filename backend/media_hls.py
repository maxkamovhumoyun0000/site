"""Adaptive (HLS) delivery for uploaded lesson videos.

Uploaded originals are phone recordings of 7-15 Mbit/s. Streaming those to a
phone on a mobile network stalls, and some of them keep the ``moov`` index at
the end of the file, so a player has to fetch the tail before it can start.

``scripts/transcode_videos_hls.py`` converts an original into a VOD HLS ladder
(1080p/720p/480p, 4-second segments) under ``data/media_hls/<asset_id>/``.
Players then start on a small segment, buffer ahead segment by segment and
switch quality with the network. The original file stays untouched and is
still served by ``/media/stream/{asset_id}`` as the fallback.

The HLS files are protected with the same signed media token as the original:
the playlist is rewritten so every variant and segment URI carries the token
of the request that fetched it.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

logger = logging.getLogger(__name__)
router = APIRouter()

REPO_ROOT = Path(__file__).resolve().parent.parent
HLS_ROOT = Path(os.getenv("MEDIA_HLS_DIR") or (REPO_ROOT / "data" / "media_hls"))
TRANSCODE_SCRIPT = REPO_ROOT / "scripts" / "transcode_videos_hls.py"
MASTER_PLAYLIST = "master.m3u8"

_SAFE_PART_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_READY_CACHE: dict[int, tuple[float, bool]] = {}
_READY_CACHE_TTL_SECONDS = 30.0


def hls_dir(asset_id: int) -> Path:
    return HLS_ROOT / str(int(asset_id))


def hls_ready(asset_id: int) -> bool:
    """True once the transcoder has atomically published the master playlist."""
    aid = int(asset_id or 0)
    if aid <= 0:
        return False
    now = time.monotonic()
    cached = _READY_CACHE.get(aid)
    if cached and cached[0] > now:
        return cached[1]
    ready = (hls_dir(aid) / MASTER_PLAYLIST).is_file()
    if len(_READY_CACHE) > 4096:
        _READY_CACHE.clear()
    _READY_CACHE[aid] = (now + _READY_CACHE_TTL_SECONDS, ready)
    return ready


def build_hls_url(asset_id: int | None, user_id: int | None = None) -> str | None:
    aid = int(asset_id or 0)
    if aid <= 0 or not hls_ready(aid):
        return None
    from backend.main import _issue_media_stream_token

    token = _issue_media_stream_token(aid, user_id=user_id)
    return f"/media/hls/{aid}/{MASTER_PLAYLIST}?token={quote(token)}"


def resolve_hls_file(asset_id: int, relative_path: str) -> Path | None:
    """Map a request path to a file inside this asset's HLS folder, or None."""
    parts = [part for part in str(relative_path or "").split("/") if part]
    if not parts or len(parts) > 2:
        return None
    if any(not _SAFE_PART_RE.match(part) or part.startswith(".") for part in parts):
        return None
    if not parts[-1].endswith((".m3u8", ".ts", ".m4s", ".mp4")):
        return None
    root = hls_dir(asset_id).resolve()
    target = (root / Path(*parts)).resolve()
    if root not in target.parents or not target.is_file():
        return None
    return target


_URI_ATTR_RE = re.compile(r'URI="([^"]+)"')


def rewrite_playlist(text: str, token: str) -> str:
    """Append the media token to every relative URI in an HLS playlist."""
    suffix = f"token={quote(token)}"

    def _with_token(uri: str) -> str:
        if "://" in uri or uri.startswith("/"):
            return uri
        return f"{uri}{'&' if '?' in uri else '?'}{suffix}"

    lines = []
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append(line)
        elif stripped.startswith("#"):
            lines.append(_URI_ATTR_RE.sub(lambda m: f'URI="{_with_token(m.group(1))}"', line))
        else:
            lines.append(_with_token(stripped))
    return "\n".join(lines) + "\n"


@router.get("/media/hls/{asset_id}/{file_path:path}")
async def media_hls_file(asset_id: int, file_path: str, token: str = Query(default="")):
    from backend.main import _verify_media_stream_token

    if not _verify_media_stream_token(int(asset_id), token):
        raise HTTPException(status_code=401, detail="Invalid or expired media token")
    target = resolve_hls_file(int(asset_id), file_path)
    if target is None:
        raise HTTPException(status_code=404, detail="Video segment not found")
    if target.suffix == ".m3u8":
        body = rewrite_playlist(target.read_text(encoding="utf-8", errors="replace"), token)
        return Response(
            content=body,
            media_type="application/vnd.apple.mpegurl",
            headers={"Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff"},
        )
    media_type = "video/mp2t" if target.suffix == ".ts" else "video/mp4"
    # Segments never change once published, so players and the OS HTTP cache
    # may keep them for the whole token lifetime.
    return FileResponse(
        str(target),
        media_type=media_type,
        headers={"Cache-Control": "private, max-age=86400, immutable", "X-Content-Type-Options": "nosniff"},
    )


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def schedule_transcode(asset_id: int) -> bool:
    """Start the background transcoder for a freshly uploaded video.

    The script serialises itself with a lock file, so several uploads queue up
    instead of running several ffmpeg processes on the API host at once.
    Disabled with MEDIA_HLS_AUTO=0 or when ffmpeg is not installed.
    """
    aid = int(asset_id or 0)
    if aid <= 0 or str(os.getenv("MEDIA_HLS_AUTO", "1")).strip() == "0":
        return False
    if not ffmpeg_available() or not TRANSCODE_SCRIPT.is_file():
        return False
    try:
        HLS_ROOT.mkdir(parents=True, exist_ok=True)
        log_path = HLS_ROOT / "transcode.log"
        with open(log_path, "ab") as log_file:
            command = [sys.executable, str(TRANSCODE_SCRIPT), "--asset-id", str(aid)]
            if shutil.which("nice"):
                command = ["nice", "-n", "15", *command]
            subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                command,
                cwd=str(REPO_ROOT),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        return True
    except Exception:
        logger.exception("could not start HLS transcode asset_id=%s", aid)
        return False
