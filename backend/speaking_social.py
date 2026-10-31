"""Speaking app: user About pages, own profile and blocking.

* ``GET /speaking/users/{id}/about``: the profile another learner sees from a
  private chat, user search or a voice room: name, login, avatar, bio, last
  seen, subjects, level, points, Speaking stats and which Diamond apps the
  account uses.  Phone numbers, e-mail addresses and credentials are never
  part of it.
* ``GET/PATCH /speaking/profile/me``: the same page for the signed-in user,
  plus editing the bio, Telegram / Instagram and (Speaking app accounts only)
  the name.
* ``GET /speaking/blocks``, ``POST/DELETE /speaking/users/{id}/block`` and
  ``POST /speaking/users/{id}/report``: blocking and reporting.  They reuse the
  shared ``web_user_blocks`` store, so a block made in the app also applies to
  chats, user search and voice rooms everywhere.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field

from db import get_conn
from speaking_contract import is_speaking_app_account

logger = logging.getLogger(__name__)
router = APIRouter()

BIO_MAX = 300
NAME_MAX = 80
_TELEGRAM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")
_INSTAGRAM_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
_SPEAKING_SOURCES = {"speaking", "speaking_app", "speaking_registration", "speaking_student_link"}
_WEBSITE_SOURCES = {"web", "login", "qr", "password_change"}
_TELEGRAM_SOURCES = {"telegram", "telegram_mobile_bot"}

_schema_ready = False
_schema_lock = threading.Lock()


def ensure_tables() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS speaking_user_profiles (
                    user_id BIGINT PRIMARY KEY,
                    bio TEXT NOT NULL DEFAULT '',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )"""
            )
            # Telegram / Instagram links are shown to other users only after
            # the user saved them here (admins may have entered them before).
            cur.execute(
                "ALTER TABLE speaking_user_profiles ADD COLUMN IF NOT EXISTS links_public INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()
            _schema_ready = True
        finally:
            cur.close()
            conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _viewer(authorization: str | None) -> dict[str, Any]:
    from backend.speaking_chats import _require_speaking_user

    return _require_speaking_user(authorization)


def _blocks_of(user_id: int) -> tuple[set[int], set[int]]:
    """(ids the user blocked, ids that blocked the user)."""
    from backend.main import community_safety

    mine = community_safety.blocked_ids(int(user_id), either_direction=False)
    both = community_safety.blocked_ids(int(user_id), either_direction=True)
    return mine, both - mine


def _iso(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if hasattr(value, "isoformat"):
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _query(sql: str, params: tuple = (), *, one: bool = False, strict: bool = False) -> Any:
    """Read-only query; required profile data can fail closed with strict=True."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        if one:
            row = cur.fetchone()
            return dict(row) if row else None
        return [dict(row) for row in cur.fetchall() or []]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        if strict:
            logger.exception("Speaking profile database read failed")
            raise
        logger.debug("Optional Speaking profile lookup unavailable", exc_info=True)
        return None if one else []
    finally:
        try:
            cur.close()
        except Exception:
            pass
        conn.close()


def _user_row(user_id: int) -> dict[str, Any] | None:
    from backend.main import _ensure_user_web_columns

    _ensure_user_web_columns()
    return _query(
        """SELECT id, login_id, first_name, last_name, profile_image_url, login_type, subject, level,
                  created_at, last_activity, last_login_at, instagram_url, telegram_url,
                  speaking_app_account, speaking_deleted_at, blocked, access_enabled
           FROM users WHERE id=? LIMIT 1""",
        (int(user_id),),
        one=True,
    )


def _own_profile_row(user_id: int) -> dict[str, Any]:
    ensure_tables()
    return _query(
        "SELECT bio, links_public FROM speaking_user_profiles WHERE user_id=? LIMIT 1",
        (int(user_id),),
        one=True,
    ) or {}


def _apps_used(user_id: int, row: dict[str, Any], speaking_answers: int) -> dict[str, bool]:
    sources = {
        str(item.get("source") or "").strip().lower()
        for item in _query("SELECT DISTINCT source FROM web_user_sessions WHERE user_id=?", (int(user_id),), strict=True)
    }
    push_apps = {
        str(item.get("app") or "").strip().lower()
        for item in _query("SELECT DISTINCT app FROM push_device_tokens WHERE user_id=?", (int(user_id),))
    }
    return {
        "speaking": bool(
            sources & _SPEAKING_SOURCES
            or speaking_answers > 0
            or is_speaking_app_account(row.get("speaking_app_account"))
        ),
        "student": "student" in sources or "student" in push_apps,
        "teacher": "teacher" in sources or "teacher" in push_apps,
        "website": bool(sources & _WEBSITE_SOURCES),
        "telegram": bool(sources & _TELEGRAM_SOURCES),
    }


def _subjects(user_id: int, row: dict[str, Any]) -> list[str]:
    try:
        from db import get_user_subjects

        subjects = [str(s).strip() for s in (get_user_subjects(int(user_id)) or []) if str(s).strip()]
    except Exception:
        subjects = []
    if not subjects:
        subjects = [s.strip() for s in str(row.get("subject") or "").split(",") if s.strip()]
    out: list[str] = []
    for subject in subjects:
        if subject not in out:
            out.append(subject)
    return out[:6]


def _levels(user_id: int, row: dict[str, Any]) -> list[dict[str, Any]]:
    levels: list[dict[str, Any]] = []
    from backend.speaking_placement import results_for

    for result in results_for(int(user_id)):
        levels.append({
            "subject": result["subject"],
            "level": result["level_code"],
            "label": result["level_label"],
            "source": "speaking_test",
            "tested_at": result.get("tested_at"),
        })
    student_level = str(row.get("level") or "").strip()
    if student_level and not is_speaking_app_account(row.get("speaking_app_account")):
        levels.append({"subject": None, "level": student_level, "label": student_level, "source": "student_app"})
    return levels


def _speaking_stats(user_id: int) -> dict[str, Any]:
    from backend.speaking_exams import build_badges, streak_from_days, _today, ensure_tables

    # Initialize the real progress tables lazily too, not only as a side
    # effect of visiting the exam screens first.
    ensure_tables()

    count = _query("SELECT COUNT(*) AS n FROM speaking_answer_analyses WHERE user_id=?", (int(user_id),), one=True, strict=True)
    answers = int((count or {}).get("n") or 0)
    mocks_rows = _query(
        """SELECT subject, COUNT(*) AS n, MAX(overall) AS best FROM speaking_exams
           WHERE user_id=? AND kind='mock' AND status='finished' GROUP BY subject""",
        (int(user_id),),
        strict=True,
    )
    mocks = sum(int(r.get("n") or 0) for r in mocks_rows)
    best = {
        str(r.get("subject") or "english"): (float(r["best"]) if r.get("best") is not None else None)
        for r in mocks_rows
    }
    day_rows = _query("SELECT DISTINCT day FROM speaking_daily_challenges WHERE user_id=?", (int(user_id),), strict=True)
    days = []
    for item in day_rows:
        value = item.get("day")
        try:
            days.append(value if hasattr(value, "toordinal") and not isinstance(value, datetime)
                        else datetime.fromisoformat(str(value)[:10]).date())
        except ValueError:
            continue
    current, best_streak = streak_from_days(sorted(set(days)), _today()) if days else (0, 0)
    strong = _query(
        "SELECT COUNT(*) AS n FROM speaking_answer_analyses WHERE user_id=? AND subject='english' AND part=2 AND score >= 6.5",
        (int(user_id),),
        one=True,
        strict=True,
    )
    badge_progress = build_badges(
        best_streak=best_streak, recordings=answers, mocks=mocks,
        part2_strong=int((strong or {}).get("n") or 0), subject="english",
    )
    return {
        "answers": answers,
        "mock_exams": mocks,
        "best_mock": best,
        "streak_current": current,
        "streak_best": best_streak,
        "badges": [b["key"] for b in badge_progress if b.get("earned")],
        "badge_progress": badge_progress,
    }


def _points(user_id: int) -> dict[str, float]:
    from db import get_dcoins, get_dpoints

    out = {"dcoins": 0.0, "dpoints": 0.0}
    out["dcoins"] = round(float(get_dcoins(int(user_id)) or 0), 1)
    out["dpoints"] = round(float(get_dpoints(int(user_id)) or 0), 1)
    return out


def _profile_payload(row: dict[str, Any], *, viewer_id: int) -> dict[str, Any]:
    from backend.main import _first_existing_avatar_url, _presence_summary_for_user
    from backend.speaking_chats import _public_user

    user_id = int(row.get("id") or 0)
    is_me = user_id == int(viewer_id)
    public = _public_user(row)
    i_blocked, blocked_me = _blocks_of(viewer_id) if not is_me else (set(), set())
    blocked_by_me = user_id in i_blocked
    has_blocked_me = user_id in blocked_me
    public.pop("last_active", None)
    base = {
        **public,
        "first_name": str(row.get("first_name") or "").strip(),
        "last_name": str(row.get("last_name") or "").strip(),
        "avatar_url": _first_existing_avatar_url(row.get("profile_image_url")) or public.get("avatar_url"),
        "is_me": is_me,
        "blocked_by_me": blocked_by_me,
        "blocked_me": has_blocked_me,
        "can_message": not is_me and not blocked_by_me and not has_blocked_me,
        "speaking_account": is_speaking_app_account(row.get("speaking_app_account")),
    }
    if has_blocked_me:
        # Like messengers: someone who blocked you shows only their name.
        return {
            "id": user_id,
            "full_name": base["full_name"],
            "login_id": "",
            "avatar_url": None,
            "role": base.get("role"),
            "is_me": False,
            "blocked_by_me": blocked_by_me,
            "blocked_me": True,
            "can_message": False,
            "limited": True,
        }
    stats = _speaking_stats(user_id)
    presence = _presence_summary_for_user(user_id)
    extra = _own_profile_row(user_id)
    links_visible = is_me or int(extra.get("links_public") or 0) == 1
    return {
        **base,
        "limited": False,
        "bio": str(extra.get("bio") or ""),
        "presence": {
            "is_online": bool(presence.get("is_online")),
            "last_online_at": presence.get("last_online_at"),
        },
        "member_since": _iso(row.get("created_at")),
        "subjects": _subjects(user_id, row),
        "levels": _levels(user_id, row),
        "points": _points(user_id),
        "speaking": stats,
        "apps": _apps_used(user_id, row, stats["answers"]),
        "telegram_url": (str(row.get("telegram_url") or "").strip() or None) if links_visible else None,
        "instagram_url": (str(row.get("instagram_url") or "").strip() or None) if links_visible else None,
    }


def _clear_user_cache(user_id: int) -> None:
    try:
        from backend.main import _USER_PAYLOAD_CACHE

        for key in list(_USER_PAYLOAD_CACHE.keys()):
            if isinstance(key, tuple) and key and key[0] == int(user_id):
                _USER_PAYLOAD_CACHE.pop(key, None)
    except Exception:
        pass


def _clean_name(value: str, field: str) -> str:
    text = " ".join(unicodedata.normalize("NFC", str(value or "")).split())
    if any(unicodedata.category(ch).startswith("C") for ch in text):
        raise HTTPException(status_code=422, detail=f"{field} contains invalid characters")
    if len(text) > NAME_MAX:
        raise HTTPException(status_code=422, detail=f"{field} is too long")
    if text and not any(ch.isalpha() for ch in text):
        raise HTTPException(status_code=422, detail=f"{field} must contain letters")
    return text


def normalize_telegram(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    handle = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me)/", "", raw, flags=re.IGNORECASE).lstrip("@").strip("/")
    if not _TELEGRAM_RE.match(handle):
        raise HTTPException(status_code=422, detail="Telegram username is not valid")
    return f"https://t.me/{handle}"


def normalize_instagram(value: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    handle = re.sub(r"^(https?://)?(www\.)?instagram\.com/", "", raw, flags=re.IGNORECASE).lstrip("@").strip("/")
    if not _INSTAGRAM_RE.match(handle) or handle.startswith(".") or handle.endswith("."):
        raise HTTPException(status_code=422, detail="Instagram username is not valid")
    return f"https://instagram.com/{handle}"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def _limit_about(viewer_id: int) -> None:
    """Profiles are opened one at a time from chats, search and rooms; the
    limit stops scripted walking through every account id."""
    try:
        from backend.main import _REDIS_CLIENT
        from backend.rate_limiting import consume_rate_limit
    except Exception:
        return
    for window, limit in ((3600, 120), (86400, 400)):
        allowed, retry_after = consume_rate_limit(
            _REDIS_CLIENT, f"speaking-about:{window}:{viewer_id}", limit=limit, window_seconds=window
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many profiles opened. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )


@router.get("/speaking/users/{user_id}/about")
@router.get("/api/speaking/users/{user_id}/about")
async def speaking_user_about(user_id: int, authorization: str | None = Header(default=None)):
    from backend.speaking_chats import _active_speaking_user

    viewer = _viewer(authorization)
    viewer_id = int(viewer.get("id") or 0)
    _limit_about(viewer_id)
    if not _active_speaking_user(int(user_id)):
        raise HTTPException(status_code=404, detail="Speaking user not found")
    row = _user_row(int(user_id))
    if not row:
        raise HTTPException(status_code=404, detail="Speaking user not found")
    return {"user": _profile_payload(row, viewer_id=viewer_id)}


class ProfileUpdateRequest(BaseModel):
    first_name: str | None = Field(default=None, max_length=NAME_MAX)
    last_name: str | None = Field(default=None, max_length=NAME_MAX)
    bio: str | None = Field(default=None, max_length=BIO_MAX)
    telegram: str | None = Field(default=None, max_length=120)
    instagram: str | None = Field(default=None, max_length=120)


class SpeakingCredentialUpdateRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    login_id: str | None = Field(default=None, min_length=4, max_length=64)
    new_password: str | None = Field(default=None, min_length=8, max_length=128)


def _validate_credential_update(payload: SpeakingCredentialUpdateRequest) -> tuple[str | None, str | None]:
    from backend.main import _public_registration_login_id

    if payload.login_id is None and payload.new_password is None:
        raise HTTPException(status_code=422, detail="Enter a new Login ID or password")
    login_id = _public_registration_login_id(payload.login_id) if payload.login_id is not None else None
    new_password = payload.new_password
    if new_password is not None and len(new_password.encode("utf-8")) > 72:
        raise HTTPException(status_code=422, detail="Password must be no more than 72 UTF-8 bytes")
    return login_id, new_password


def _own_payload(viewer: dict[str, Any]) -> dict[str, Any]:
    uid = int(viewer.get("id") or 0)
    row = _user_row(uid)
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    payload = _profile_payload(row, viewer_id=uid)
    i_blocked, _ = _blocks_of(uid)
    payload["blocked_count"] = len(i_blocked)
    payload["can_edit_name"] = is_speaking_app_account(row.get("speaking_app_account"))
    return payload


@router.get("/speaking/profile/me")
@router.get("/api/speaking/profile/me")
async def speaking_profile_me(authorization: str | None = Header(default=None)):
    return {"user": _own_payload(_viewer(authorization))}


@router.get("/speaking/profile/stats")
@router.get("/api/speaking/profile/stats")
async def speaking_profile_stats(authorization: str | None = Header(default=None)):
    viewer = _viewer(authorization)
    return {"stats": _speaking_stats(int(viewer.get("id") or 0))}


@router.get("/speaking/profile/levels")
@router.get("/api/speaking/profile/levels")
async def speaking_profile_levels(authorization: str | None = Header(default=None)):
    viewer = _viewer(authorization)
    user_id = int(viewer.get("id") or 0)
    row = _user_row(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"items": _levels(user_id, row)}


@router.get("/speaking/profile/badges")
@router.get("/api/speaking/profile/badges")
async def speaking_profile_badges(authorization: str | None = Header(default=None)):
    viewer = _viewer(authorization)
    stats = _speaking_stats(int(viewer.get("id") or 0))
    return {"items": stats["badge_progress"], "earned_keys": stats["badges"]}


@router.get("/speaking/profile/sessions")
@router.get("/api/speaking/profile/sessions")
async def speaking_profile_sessions(authorization: str | None = Header(default=None)):
    _viewer(authorization)
    from backend.main import list_user_sessions

    return await list_user_sessions(authorization)


@router.patch("/speaking/profile/credentials")
@router.patch("/api/speaking/profile/credentials")
async def update_speaking_profile_credentials(
    payload: SpeakingCredentialUpdateRequest,
    req: Request,
    response: Response,
    authorization: str | None = Header(default=None),
):
    """Update credentials on a standalone Speaking account, keeping this device signed in."""
    from backend.main import (
        _auth_token_response,
        _clear_auth_caches_for_user,
        _client_ip,
        _create_access_token,
        _decode_bearer_payload,
        _issue_web_session,
        _revoke_web_sessions,
        clear_login_throttle,
        get_user_by_id,
        hash_password,
        is_login_throttled,
        record_login_failure,
        verify_password,
    )

    viewer = _viewer(authorization)
    user_id = int(viewer.get("id") or 0)
    if user_id <= 0 or not is_speaking_app_account(viewer.get("speaking_app_account")):
        raise HTTPException(status_code=403, detail="Only a standalone Speaking account can change credentials here")
    login_id, new_password = _validate_credential_update(payload)

    client_ip = _client_ip(req)
    user_key = f"speaking-credentials:user:{user_id}"
    ip_key = f"speaking-credentials:ip:{client_ip}" if client_ip else ""
    if is_login_throttled(user_key) or (ip_key and is_login_throttled(ip_key)):
        raise HTTPException(status_code=429, detail="Too many credential attempts. Please try again later.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, login_id, password, speaking_app_account, speaking_deleted_at "
            "FROM users WHERE id=? LIMIT 1",
            (user_id,),
        )
        found = cur.fetchone()
        current = dict(found) if found else None
        if not current or not is_speaking_app_account(current.get("speaking_app_account")) or current.get("speaking_deleted_at"):
            raise HTTPException(status_code=403, detail="Only an active standalone Speaking account can change credentials")
        if not verify_password(payload.current_password, current.get("password")):
            record_login_failure(user_key)
            if ip_key:
                record_login_failure(ip_key)
            raise HTTPException(status_code=401, detail="Current password is incorrect")

        next_login_id = login_id or str(current.get("login_id") or "")
        if login_id is not None and login_id.upper() != str(current.get("login_id") or "").upper():
            cur.execute(
                "SELECT id FROM users WHERE UPPER(login_id)=? AND id<>? LIMIT 1",
                (login_id, user_id),
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="This Login ID is already in use")

        assignments = ["login_id=?", "session_version=COALESCE(session_version, 1) + 1"]
        params: list[Any] = [next_login_id]
        if new_password is not None:
            assignments.insert(1, "password=?")
            params.insert(1, hash_password(new_password))
        params.extend((user_id, current.get("password"), current.get("login_id")))
        cur.execute(
            f"UPDATE users SET {', '.join(assignments)} WHERE id=? AND password=? AND login_id=?",
            tuple(params),
        )
        if int(getattr(cur, "rowcount", 1) or 0) == 0:
            raise HTTPException(status_code=409, detail="Account changed. Please retry.")
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        code = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
        message = str(exc).lower()
        if code == "23505" or "unique constraint" in message or "unique violation" in message:
            raise HTTPException(status_code=409, detail="This Login ID is already in use") from exc
        logger.exception("Speaking credentials update failed user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Could not update credentials") from exc
    finally:
        cur.close()
        conn.close()

    clear_login_throttle(user_key)
    if ip_key:
        clear_login_throttle(ip_key)
    bearer_payload = _decode_bearer_payload(authorization)
    current_session_id = str(bearer_payload.get("sid") or bearer_payload.get("session_id") or "").strip()
    metadata = _query(
        "SELECT device_id, device_model FROM web_user_sessions WHERE session_id=? AND user_id=? LIMIT 1",
        (current_session_id, user_id),
        one=True,
    ) if current_session_id else None
    current_device_id = str((metadata or {}).get("device_id") or "").strip() or None
    current_device_model = str((metadata or {}).get("device_model") or "").strip() or None

    _clear_auth_caches_for_user(user_id)
    _revoke_web_sessions(user_id, keep_session_id=None, reason="speaking_credentials_changed")
    updated_user = get_user_by_id(user_id)
    if not updated_user:
        raise HTTPException(status_code=404, detail="Account not found")
    next_session_id, ttl_hours = _issue_web_session(
        updated_user,
        device_id=current_device_id,
        source="speaking_credentials_change",
        device_model=current_device_model,
    )
    token = _create_access_token(
        updated_user,
        telegram_id=bearer_payload.get("telegram_id"),
        session_id=next_session_id,
        ttl_hours=ttl_hours,
    )
    return _auth_token_response(req, response, token, updated_user)


@router.patch("/speaking/profile/me")
@router.patch("/api/speaking/profile/me")
async def update_speaking_profile_me(payload: ProfileUpdateRequest, authorization: str | None = Header(default=None)):
    from backend.community_safety import validate_public_text

    viewer = _viewer(authorization)
    uid = int(viewer.get("id") or 0)
    ensure_tables()
    updates: list[str] = []
    params: list[Any] = []
    if payload.first_name is not None or payload.last_name is not None:
        # School accounts keep the name the education centre registered.
        if not is_speaking_app_account(viewer.get("speaking_app_account")):
            raise HTTPException(status_code=403, detail="Your name is managed by your education centre")
        if payload.first_name is not None:
            first = _clean_name(payload.first_name, "First name")
            if not first:
                raise HTTPException(status_code=422, detail="First name is required")
            updates.append("first_name=?")
            params.append(first)
        if payload.last_name is not None:
            updates.append("last_name=?")
            params.append(_clean_name(payload.last_name, "Last name"))
    if payload.telegram is not None:
        updates.append("telegram_url=?")
        params.append(normalize_telegram(payload.telegram))
    if payload.instagram is not None:
        updates.append("instagram_url=?")
        params.append(normalize_instagram(payload.instagram))
    links_saved = payload.telegram is not None or payload.instagram is not None
    bio: str | None = None
    if payload.bio is not None:
        bio = " ".join(line.strip() for line in str(payload.bio).splitlines()).strip()
        if any(unicodedata.category(ch) == "Cc" for ch in bio):
            raise HTTPException(status_code=422, detail="Bio contains invalid characters")
        if bio:
            try:
                bio = validate_public_text(bio)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        bio = bio[:BIO_MAX]
    conn = get_conn()
    cur = conn.cursor()
    try:
        if updates:
            cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE id=?", (*params, uid))
        if bio is not None or links_saved:
            cur.execute(
                "INSERT INTO speaking_user_profiles (user_id) VALUES (?) ON CONFLICT (user_id) DO NOTHING",
                (uid,),
            )
        if bio is not None:
            cur.execute("UPDATE speaking_user_profiles SET bio=?, updated_at=NOW() WHERE user_id=?", (bio, uid))
        if links_saved:
            cur.execute(
                "UPDATE speaking_user_profiles SET links_public=1, updated_at=NOW() WHERE user_id=?",
                (uid,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
    _clear_user_cache(uid)
    return {"user": _own_payload(viewer)}


@router.get("/speaking/blocks")
@router.get("/api/speaking/blocks")
async def speaking_blocked_users(authorization: str | None = Header(default=None)):
    from backend.main import _display_name, _first_existing_avatar_url, community_safety

    viewer = _viewer(authorization)
    community_safety.ensure_schema()
    rows = _query(
        """SELECT b.blocked_user_id AS id, b.created_at AS blocked_at, u.login_id, u.first_name, u.last_name,
                  u.profile_image_url
           FROM web_user_blocks b JOIN users u ON u.id=b.blocked_user_id
           WHERE b.user_id=? ORDER BY b.created_at DESC LIMIT 500""",
        (int(viewer.get("id") or 0),),
    )
    return {"items": [
        {
            "id": int(r.get("id") or 0),
            "login_id": str(r.get("login_id") or ""),
            "full_name": _display_name(r),
            "avatar_url": _first_existing_avatar_url(r.get("profile_image_url")),
            "blocked_at": _iso(r.get("blocked_at")),
        }
        for r in rows
    ]}


@router.post("/speaking/users/{user_id}/block")
@router.post("/api/speaking/users/{user_id}/block")
async def speaking_block_user(user_id: int, authorization: str | None = Header(default=None)):
    from backend.main import community_safety

    viewer = _viewer(authorization)
    try:
        community_safety.block(int(viewer.get("id") or 0), int(user_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True, "blocked": True}


@router.delete("/speaking/users/{user_id}/block")
@router.delete("/api/speaking/users/{user_id}/block")
async def speaking_unblock_user(user_id: int, authorization: str | None = Header(default=None)):
    from backend.main import community_safety

    viewer = _viewer(authorization)
    community_safety.unblock(int(viewer.get("id") or 0), int(user_id))
    return {"success": True, "blocked": False}


class SpeakingReportRequest(BaseModel):
    reason: Literal["harassment", "inappropriate", "spam", "privacy", "other"] = "other"
    details: str = Field(default="", max_length=2000)
    context: Literal["profile", "chat", "voice_room"] = "profile"


@router.post("/speaking/users/{user_id}/report")
@router.post("/api/speaking/users/{user_id}/report")
async def speaking_report_user(user_id: int, payload: SpeakingReportRequest,
                               authorization: str | None = Header(default=None)):
    from backend.main import SafetyReportRequest, safety_report

    _viewer(authorization)
    return await safety_report(
        SafetyReportRequest(
            target_type="voice_user" if payload.context == "voice_room" else "user",
            target_id=str(int(user_id)),
            reason=payload.reason,
            details=payload.details,
            snapshot=f"Reported from the Speaking app ({payload.context}).",
        ),
        authorization,
    )
