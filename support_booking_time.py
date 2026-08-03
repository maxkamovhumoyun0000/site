"""
Shared lesson booking time helpers (Asia/Tashkent) for student bot, support bot, and db layer.
"""
from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone

import pytz

SUPPORT_TZ = pytz.timezone("Asia/Tashkent")
SUPPORT_LESSON_DURATION_MINUTES = 60


def normalize_time_hhmm(time_raw: str | None) -> str | None:
    """
    Normalize time into HH:MM.
    Accepts: '14', '14:0', '14:00', ' 9 ', '9:3' (best-effort).
    Returns None if invalid.
    """
    s = str(time_raw or "").strip()
    if not s:
        return None
    if ":" in s:
        try:
            hh_s, mm_s = s.split(":", 1)
            hh = int(hh_s.strip())
            mm = int(mm_s.strip())
        except Exception:
            return None
    else:
        try:
            hh = int(s)
            mm = 0
        except Exception:
            return None
    if hh < 0 or hh > 23 or mm < 0 or mm > 59:
        return None
    return f"{hh:02d}:{mm:02d}"


def support_make_start_ts(date_iso: str, time_hhmm: str) -> str | None:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d").date()
        norm = normalize_time_hhmm(time_hhmm)
        if not norm:
            return None
        hh, mm = [int(x) for x in norm.split(":", 1)]
        local_dt = SUPPORT_TZ.localize(datetime.combine(d, dtime(hh, mm)))
        return local_dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def support_make_end_ts(start_ts_iso: str | None) -> str | None:
    if not start_ts_iso:
        return None
    try:
        s = start_ts_iso.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        d = d.astimezone(timezone.utc)
        return (d + timedelta(minutes=SUPPORT_LESSON_DURATION_MINUTES)).isoformat()
    except Exception:
        return None
