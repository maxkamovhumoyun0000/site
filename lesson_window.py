"""
Group lesson window check (Asia/Tashkent), aligned with attendance_manager logic.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytz

from db import get_group
from logging_config import get_logger

logger = get_logger(__name__)

TZ = pytz.timezone("Asia/Tashkent")


def is_group_lesson_window_active(group_id: int) -> bool:
    """
    True if current time is within [lesson_start - 10min, lesson_end] on a scheduled lesson day.
    If lesson_start/lesson_end are missing, returns False (strict).
    """
    g = get_group(group_id)
    if not g:
        return False
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    weekday = now.weekday()
    lesson_date = (g.get("lesson_date") or "").strip()
    has_today = False
    if lesson_date:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", lesson_date):
            has_today = lesson_date == today
        else:
            code = lesson_date.upper()
            if code in ("ODD", "MWF", "MON/WED/FRI", "MON,WED,FRI"):
                has_today = weekday in (0, 2, 4)
            elif code in ("EVEN", "TTS", "TUE/THU/SAT", "TUE,THU,SAT"):
                has_today = weekday in (1, 3, 5)
    if not has_today:
        return False

    start = (g.get("lesson_start") or "")[:5]
    end = (g.get("lesson_end") or "")[:5]
    if not start or not end:
        return False
    try:
        start_naive = datetime.strptime(f"{today} {start}", "%Y-%m-%d %H:%M")
        end_naive = datetime.strptime(f"{today} {end}", "%Y-%m-%d %H:%M")
        start_dt = TZ.localize(start_naive)
        end_dt = TZ.localize(end_naive)
        pre_dt = start_dt - timedelta(minutes=10)
    except Exception:
        logger.exception("is_group_lesson_window_active: bad schedule group_id=%s", group_id)
        return False
    return pre_dt <= now <= end_dt
