"""Convert uploaded lesson videos into an adaptive HLS ladder.

Run from the project root (the API also starts it for each new video upload):

    python scripts/transcode_videos_hls.py --all            # every active video asset
    python scripts/transcode_videos_hls.py --asset-id 42    # one asset
    python scripts/transcode_videos_hls.py --all --dry-run  # report only

Output goes to data/media_hls/<asset_id>/ (override with MEDIA_HLS_DIR):

    master.m3u8, v0/index.m3u8, v0/seg_00000.ts, v1/..., status.json

The ladder never upscales. 1080p, 720p and 480p renditions are produced only
when the source is at least that large; the short side is compared, so
portrait phone recordings keep their orientation. Work happens in
"<id>.tmp" and is renamed into place only after ffmpeg succeeds, so a player
never sees a half-written playlist. Originals are never modified.

One transcode runs at a time on the host (a lock file serialises them),
ffmpeg uses a bounded number of threads, and the API starts this under `nice`.
Requires ffmpeg and ffprobe on PATH.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

MEDIA_UPLOAD_DIR = REPO_ROOT / "data" / "media_uploads"
HLS_ROOT = Path(os.getenv("MEDIA_HLS_DIR") or (REPO_ROOT / "data" / "media_hls"))
FFMPEG_THREADS = max(1, int(os.getenv("MEDIA_HLS_THREADS", "3")))
SEGMENT_SECONDS = 4

# (short side, video kbit/s cap, audio kbit/s). Capped-CRF keeps simple scenes
# small while the cap protects slow networks during busy scenes.
LADDER = (
    (1080, 5000, 128),
    (720, 2800, 128),
    (480, 1100, 96),
)


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout
    data = json.loads(out or "{}")
    video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video:
        raise RuntimeError("no video stream")
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    rotation = 0
    for side in video.get("side_data_list") or []:
        if "rotation" in side:
            rotation = abs(int(float(side.get("rotation") or 0)))
    rotation = rotation or abs(int(float((video.get("tags") or {}).get("rotate") or 0)))
    if rotation in (90, 270):
        width, height = height, width
    return {
        "width": width,
        "height": height,
        "has_audio": audio is not None,
        "duration": float((data.get("format") or {}).get("duration") or 0.0),
    }


def _ladder_for(width: int, height: int) -> list[tuple[int, int, int]]:
    short_side = min(width, height) or 480
    rungs = [rung for rung in LADDER if short_side >= rung[0] * 0.9]
    if not rungs:
        # Small sources get one rendition at their own size.
        rungs = [(short_side - short_side % 2, LADDER[-1][1], LADDER[-1][2])]
    return rungs


def _ffmpeg_command(source: Path, out_dir: Path, info: dict) -> list[str]:
    landscape = info["width"] >= info["height"]
    rungs = _ladder_for(info["width"], info["height"])
    split = f"[0:v]split={len(rungs)}" + "".join(f"[s{i}]" for i in range(len(rungs)))
    scales = []
    for i, (side, _, _) in enumerate(rungs):
        size = f"-2:{side}" if landscape else f"{side}:-2"
        scales.append(f"[s{i}]scale={size}:flags=lanczos,format=yuv420p[v{i}]")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-filter_complex", ";".join([split, *scales]),
    ]
    stream_map = []
    for i, (_, kbps, audio_kbps) in enumerate(rungs):
        command += [
            "-map", f"[v{i}]",
            f"-c:v:{i}", "libx264",
            f"-crf:v:{i}", "21",
            f"-maxrate:v:{i}", f"{kbps}k",
            f"-bufsize:v:{i}", f"{kbps * 2}k",
        ]
        if info["has_audio"]:
            command += ["-map", "0:a:0", f"-c:a:{i}", "aac", f"-b:a:{i}", f"{audio_kbps}k", f"-ac:a:{i}", "2"]
            stream_map.append(f"v:{i},a:{i}")
        else:
            stream_map.append(f"v:{i}")
    command += [
        "-preset", "veryfast",
        "-profile:v", "high",
        "-threads", str(FFMPEG_THREADS),
        # A key frame every segment boundary keeps segments independent.
        "-force_key_frames", f"expr:gte(t,n_forced*{SEGMENT_SECONDS})",
        "-sc_threshold", "0",
        "-f", "hls",
        "-hls_time", str(SEGMENT_SECONDS),
        "-hls_playlist_type", "vod",
        "-hls_flags", "independent_segments",
        "-hls_segment_type", "mpegts",
        "-hls_segment_filename", str(out_dir / "v%v" / "seg_%05d.ts"),
        "-master_pl_name", "master.m3u8",
        "-var_stream_map", " ".join(stream_map),
        str(out_dir / "v%v" / "index.m3u8"),
    ]
    return command


def _video_assets(asset_id: int | None) -> list[dict]:
    from db import get_conn

    conn = get_conn()
    try:
        cur = conn.cursor()
        if asset_id:
            cur.execute("SELECT * FROM media_assets WHERE id=? LIMIT 1", (int(asset_id),))
        else:
            cur.execute(
                """
                SELECT * FROM media_assets
                WHERE COALESCE(is_active, 1)=1
                  AND (LOWER(COALESCE(asset_type, ''))='video' OR LOWER(COALESCE(content_type, '')) LIKE 'video/%')
                ORDER BY id
                """
            )
        return [dict(row) for row in (cur.fetchall() or [])]
    finally:
        conn.close()


def transcode(asset: dict, *, force: bool = False, dry_run: bool = False) -> str:
    asset_id = int(asset.get("id") or 0)
    stored_name = Path(str(asset.get("storage_path") or "")).name
    source = MEDIA_UPLOAD_DIR / stored_name
    final_dir = HLS_ROOT / str(asset_id)
    if not stored_name or not source.is_file():
        return f"asset {asset_id}: original missing, skipped"
    if (final_dir / "master.m3u8").is_file() and not force:
        return f"asset {asset_id}: already done"
    info = _probe(source)
    rungs = _ladder_for(info["width"], info["height"])
    label = "/".join(f"{side}p" for side, _, _ in rungs)
    if dry_run:
        return f"asset {asset_id}: would build {label} from {info['width']}x{info['height']} ({source.stat().st_size // 1_000_000} MB)"
    work_dir = HLS_ROOT / f"{asset_id}.tmp"
    shutil.rmtree(work_dir, ignore_errors=True)
    for i in range(len(rungs)):
        (work_dir / f"v{i}").mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    timeout = max(1800, int(info["duration"] * 6))
    subprocess.run(_ffmpeg_command(source, work_dir, info), check=True, timeout=timeout)
    if not (work_dir / "master.m3u8").is_file():
        raise RuntimeError("ffmpeg finished without a master playlist")
    (work_dir / "status.json").write_text(
        json.dumps(
            {
                "asset_id": asset_id,
                "renditions": label,
                "source": stored_name,
                "seconds": round(time.monotonic() - started, 1),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
        ),
        encoding="utf-8",
    )
    if final_dir.exists():
        shutil.rmtree(final_dir)
    os.replace(work_dir, final_dir)
    return f"asset {asset_id}: built {label} in {round(time.monotonic() - started)} s"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--asset-id", type=int)
    target.add_argument("--all", action="store_true")
    parser.add_argument("--force", action="store_true", help="rebuild even when a ladder exists")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        print("ffmpeg/ffprobe not found on PATH", file=sys.stderr)
        return 2
    HLS_ROOT.mkdir(parents=True, exist_ok=True)
    with open(HLS_ROOT / ".transcode.lock", "w") as lock_file:
        if not args.dry_run:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
        failures = 0
        for asset in _video_assets(args.asset_id):
            try:
                print(transcode(asset, force=args.force, dry_run=args.dry_run), flush=True)
            except Exception as exc:  # keep going with the next asset
                failures += 1
                shutil.rmtree(HLS_ROOT / f"{asset.get('id')}.tmp", ignore_errors=True)
                print(f"asset {asset.get('id')}: FAILED {type(exc).__name__}: {exc}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
