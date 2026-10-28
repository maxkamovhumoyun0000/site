"""Speaking app "Video lessons".

The page shows two kinds of videos:

* lessons the Speaking admin uploads for the Speaking app only
  (``speaking_videos``), and
* videos from the main lesson catalogue (the ``videos`` table that the Student
  app shows) that the Speaking admin picked for the Speaking app
  (``speaking_video_picks``).

Both reuse the existing media assets, so playback goes through the same signed
``/media/stream`` original and, when transcoded, the adaptive ``/media/hls``
ladder.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from db import get_conn

logger = logging.getLogger(__name__)
router = APIRouter()

STAFF_ROLES = {"speaking_admin", "admin", "superadmin", "developer"}
SUBJECTS = {"english", "russian"}
_SCHEMA_READY = False


def _optional_user(authorization: str | None) -> dict[str, Any] | None:
    if not authorization:
        return None
    from backend.main import _user_row_from_bearer

    try:
        return _user_row_from_bearer(authorization)
    except HTTPException:
        return None


def _staff(authorization: str | None) -> dict[str, Any]:
    from backend.main import _require_role, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    _require_role(user, STAFF_ROLES)
    return user


def ensure_tables() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_videos (
                id BIGSERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT 'english',
                level TEXT NOT NULL DEFAULT '',
                thumbnail_url TEXT NOT NULL DEFAULT '',
                video_asset_id BIGINT,
                duration INTEGER NOT NULL DEFAULT 0,
                is_published BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                view_count INTEGER NOT NULL DEFAULT 0,
                created_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_video_picks (
                video_id BIGINT PRIMARY KEY REFERENCES videos(id) ON DELETE CASCADE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                added_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_videos_subject ON speaking_videos(subject, is_published, sort_order)")
        conn.commit()
        _SCHEMA_READY = True
    finally:
        cur.close()
        conn.close()


def _subject_key(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw.startswith(("rus", "рус")) or raw == "ru":
        return "russian"
    if raw.startswith(("eng", "ing")) or raw in {"en", "ielts", "cefr"}:
        return "english"
    return ""


def _iso(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else (str(value) if value else None)


def _playback(asset_id: int, raw_url: str, viewer_id: int | None) -> tuple[str | None, str | None]:
    from backend.main import _build_media_stream_url
    from backend.media_hls import build_hls_url

    if viewer_id is None:
        return None, None
    if asset_id > 0:
        return _build_media_stream_url(asset_id, user_id=viewer_id), build_hls_url(asset_id, viewer_id)
    return (raw_url or None), None


def _serialize(row: dict[str, Any], *, source: str, viewer_id: int | None) -> dict[str, Any]:
    from backend.main import _normalize_image_asset_url

    asset_id = int(row.get("video_asset_id") or 0)
    video_url, hls_url = _playback(asset_id, str(row.get("video_url") or "").strip(), viewer_id)
    video_id = int(row.get("id") or 0)
    return {
        "key": f"{source}-{video_id}",
        "source": source,
        "id": video_id,
        "title": str(row.get("title") or "").strip(),
        "description": str(row.get("description") or "").strip(),
        "author": str(row.get("author") or "").strip(),
        "level": str(row.get("level") or "").strip(),
        "subject": _subject_key(row.get("subject")) or "english",
        "thumbnail_url": _normalize_image_asset_url(str(row.get("thumbnail_url") or "").strip() or None),
        "duration": max(0, int(row.get("duration") or 0)),
        "view_count": int(row.get("view_count") or 0),
        "video_asset_id": asset_id or None,
        "is_published": bool(row.get("is_published")) if source == "speaking" else int(row.get("is_published") or 0) == 1,
        "created_at": _iso(row.get("created_at")),
        "video_url": video_url,
        "hls_url": hls_url,
    }


def _load(subject: str, *, include_drafts: bool, viewer_id: int | None) -> list[dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        own_sql = "SELECT * FROM speaking_videos WHERE 1=1"
        own_params: list[Any] = []
        if not include_drafts:
            own_sql += " AND is_published = TRUE"
        if subject:
            own_sql += " AND subject = %s"
            own_params.append(subject)
        cur.execute(own_sql + " ORDER BY sort_order, created_at DESC, id DESC LIMIT 300", tuple(own_params))
        own = [_serialize(dict(row), source="speaking", viewer_id=viewer_id) for row in cur.fetchall() or []]
        cur.execute(
            """SELECT v.*, p.sort_order AS pick_order
               FROM speaking_video_picks p JOIN videos v ON v.id = p.video_id
               WHERE v.is_published = 1
               ORDER BY p.sort_order, p.created_at DESC LIMIT 300"""
        )
        picks = []
        for row in cur.fetchall() or []:
            item = _serialize(dict(row), source="catalog", viewer_id=viewer_id)
            row_subject = _subject_key(dict(row).get("subject"))
            if subject and row_subject and row_subject != subject:
                continue
            picks.append(item)
        return own + picks
    finally:
        cur.close()
        conn.close()


@router.get("/speaking/videos")
@router.get("/api/speaking/videos")
async def list_speaking_videos(
    subject: str = Query(default="english", max_length=32),
    authorization: str | None = Header(default=None),
):
    """Public catalogue; playback URLs are signed only for a signed-in viewer."""
    ensure_tables()
    user = _optional_user(authorization)
    viewer_id = int(user.get("id") or 0) if user else None
    items = _load(_subject_key(subject) or "english", include_drafts=False, viewer_id=viewer_id)
    return {"items": items, "requires_login": user is None}


@router.post("/speaking/videos/{source}/{video_id}/view")
@router.post("/api/speaking/videos/{source}/{video_id}/view")
async def record_speaking_video_view(source: str, video_id: int, authorization: str | None = Header(default=None)):
    user = _optional_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    ensure_tables()
    if source not in {"speaking", "catalog"}:
        raise HTTPException(status_code=404, detail="Video not found")
    from backend.main import _REDIS_CLIENT
    from backend.rate_limiting import consume_rate_limit

    # One counted view per viewer and video every 6 hours.
    counted, _ = consume_rate_limit(
        _REDIS_CLIENT, f"speaking-video-view:{source}:{video_id}:{int(user.get('id') or 0)}", limit=1, window_seconds=6 * 3600
    )
    table = "speaking_videos" if source == "speaking" else "videos"
    conn = get_conn()
    cur = conn.cursor()
    try:
        if counted:
            cur.execute(f"UPDATE {table} SET view_count = COALESCE(view_count, 0) + 1 WHERE id = %s", (int(video_id),))
            conn.commit()
        cur.execute(f"SELECT COALESCE(view_count, 0) AS view_count FROM {table} WHERE id = %s", (int(video_id),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Video not found")
        return {"view_count": int(dict(row).get("view_count") or 0)}
    finally:
        cur.close()
        conn.close()


class SpeakingVideoInput(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=4000)
    subject: str = Field(default="english", pattern="^(english|russian)$")
    level: str = Field(default="", max_length=40)
    thumbnail_url: str = Field(default="", max_length=600)
    video_asset_id: int = Field(gt=0)
    duration: int = Field(default=0, ge=0, le=24 * 3600)
    is_published: bool = True


class SpeakingVideoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    subject: str | None = Field(default=None, pattern="^(english|russian)$")
    level: str | None = Field(default=None, max_length=40)
    thumbnail_url: str | None = Field(default=None, max_length=600)
    video_asset_id: int | None = Field(default=None, gt=0)
    duration: int | None = Field(default=None, ge=0, le=24 * 3600)
    is_published: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


class SpeakingVideoPicks(BaseModel):
    video_ids: list[int] = Field(default_factory=list, max_length=300)


def _check_video_asset(asset_id: int) -> None:
    from db import get_media_asset

    asset = get_media_asset(int(asset_id))
    kind = str((asset or {}).get("asset_type") or "").lower()
    content_type = str((asset or {}).get("content_type") or "").lower()
    if not asset or int(asset.get("is_active") or 0) != 1 or not (kind == "video" or content_type.startswith("video/")):
        raise HTTPException(status_code=422, detail="Upload the video file first")


def _check_thumbnail(url: str) -> str:
    from backend.main import _has_valid_thumbnail_like_url, _normalize_image_asset_url

    cleaned = str(url or "").strip()
    if not cleaned:
        return ""
    if not _has_valid_thumbnail_like_url(cleaned):
        raise HTTPException(status_code=422, detail="Thumbnail must be an uploaded image")
    return _normalize_image_asset_url(cleaned) or ""


@router.get("/staff/speaking/videos")
async def staff_list_speaking_videos(authorization: str | None = Header(default=None)):
    user = _staff(authorization)
    ensure_tables()
    viewer_id = int(user.get("id") or 0)
    own = [item for item in _load("", include_drafts=True, viewer_id=viewer_id) if item["source"] == "speaking"]
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT video_id FROM speaking_video_picks ORDER BY sort_order, created_at")
        pick_ids = [int(dict(row).get("video_id") or 0) for row in cur.fetchall() or []]
        cur.execute(
            """SELECT id, title, subject, level, thumbnail_url, duration, view_count, created_at
               FROM videos WHERE is_published = 1
               ORDER BY COALESCE(sort_order, id), id LIMIT 500"""
        )
        from backend.main import _normalize_image_asset_url

        catalog = [
            {
                "id": int(r.get("id") or 0),
                "title": str(r.get("title") or ""),
                "subject": _subject_key(r.get("subject")) or "",
                "level": str(r.get("level") or ""),
                "thumbnail_url": _normalize_image_asset_url(str(r.get("thumbnail_url") or "").strip() or None),
                "duration": int(r.get("duration") or 0),
                "view_count": int(r.get("view_count") or 0),
                "created_at": _iso(r.get("created_at")),
            }
            for r in (dict(row) for row in cur.fetchall() or [])
        ]
    finally:
        cur.close()
        conn.close()
    return {"items": own, "pick_ids": pick_ids, "catalog": catalog}


@router.post("/staff/speaking/videos")
async def staff_create_speaking_video(payload: SpeakingVideoInput, authorization: str | None = Header(default=None)):
    user = _staff(authorization)
    ensure_tables()
    _check_video_asset(payload.video_asset_id)
    thumbnail = _check_thumbnail(payload.thumbnail_url)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS next_order FROM speaking_videos")
        next_order = int(dict(cur.fetchone() or {}).get("next_order") or 1)
        cur.execute(
            """INSERT INTO speaking_videos
                   (title, description, subject, level, thumbnail_url, video_asset_id, duration, is_published, sort_order, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                payload.title.strip(), payload.description.strip(), payload.subject, payload.level.strip(), thumbnail,
                payload.video_asset_id, payload.duration, payload.is_published, next_order, int(user.get("id") or 0),
            ),
        )
        row = dict(cur.fetchone())
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return {"item": _serialize(row, source="speaking", viewer_id=int(user.get("id") or 0))}


@router.put("/staff/speaking/videos/picks")
async def staff_set_speaking_video_picks(payload: SpeakingVideoPicks, authorization: str | None = Header(default=None)):
    user = _staff(authorization)
    ensure_tables()
    ids: list[int] = []
    for value in payload.video_ids:
        if int(value) > 0 and int(value) not in ids:
            ids.append(int(value))
    conn = get_conn()
    cur = conn.cursor()
    try:
        if ids:
            cur.execute("SELECT id FROM videos WHERE id = ANY(%s) AND is_published = 1", (ids,))
            existing = {int(dict(row).get("id") or 0) for row in cur.fetchall() or []}
            missing = [video_id for video_id in ids if video_id not in existing]
            if missing:
                raise HTTPException(status_code=422, detail=f"Videos not found or unpublished: {missing[:10]}")
        cur.execute("DELETE FROM speaking_video_picks")
        for position, video_id in enumerate(ids, start=1):
            cur.execute(
                "INSERT INTO speaking_video_picks (video_id, sort_order, added_by) VALUES (%s,%s,%s)",
                (video_id, position, int(user.get("id") or 0)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    return {"pick_ids": ids}


@router.put("/staff/speaking/videos/{video_id}")
async def staff_update_speaking_video(video_id: int, payload: SpeakingVideoUpdate, authorization: str | None = Header(default=None)):
    user = _staff(authorization)
    ensure_tables()
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    if updates.get("video_asset_id"):
        _check_video_asset(int(updates["video_asset_id"]))
    if "thumbnail_url" in updates:
        updates["thumbnail_url"] = _check_thumbnail(updates.get("thumbnail_url") or "")
    for key in ("title", "description", "level"):
        if key in updates and updates[key] is not None:
            updates[key] = str(updates[key]).strip()
    updates = {key: value for key, value in updates.items() if value is not None}
    allowed = {"title", "description", "subject", "level", "thumbnail_url", "video_asset_id", "duration", "is_published", "sort_order"}
    assignments = ", ".join(f"{key} = %s" for key in updates if key in allowed)
    values = [value for key, value in updates.items() if key in allowed]
    if not assignments:
        raise HTTPException(status_code=400, detail="No fields provided for update")
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"UPDATE speaking_videos SET {assignments}, updated_at = NOW() WHERE id = %s RETURNING *",
            (*values, int(video_id)),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Video not found")
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return {"item": _serialize(dict(row), source="speaking", viewer_id=int(user.get("id") or 0))}


@router.delete("/staff/speaking/videos/{video_id}")
async def staff_delete_speaking_video(video_id: int, authorization: str | None = Header(default=None)):
    _staff(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM speaking_videos WHERE id = %s RETURNING id", (int(video_id),))
        row = cur.fetchone()
        conn.commit()
    finally:
        cur.close()
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"id": int(video_id)}
