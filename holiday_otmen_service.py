from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytz

from db import (
    create_lesson_otmen_request,
    get_all_groups,
    get_branch_date_closed_reason,
    get_conn,
    get_latest_lesson_otmen_request_by_date,
    get_group_users,
    get_lesson_otmen_request,
    get_pending_lesson_otmen_request_by_date,
    get_user_by_id,
    is_branch_date_closed_for_booking,
    is_lesson_otmen_date_cancelled,
    list_cancelled_lesson_otmen_requests,
    list_lesson_bookings_by_date,
    mark_lesson_otmen_request_status,
    open_branch_date_for_booking,
    set_branch_date_closed,
    set_lesson_booking_status,
)
from holiday_manager import get_days_status, uz_holidays

TASHKENT_TZ = pytz.timezone("Asia/Tashkent")


def _parse_iso_date(date_str: str):
    try:
        return datetime.strptime(str(date_str), "%Y-%m-%d").date()
    except Exception:
        return None


def is_official_holiday_date(date_str: str) -> bool:
    d = _parse_iso_date(date_str)
    if not d:
        return False
    return d in uz_holidays


def _normalize_cancel_mode(cancel_mode: str | None) -> str:
    raw = str(cancel_mode or "").strip().lower()
    if raw == "manual":
        return "manual"
    return "auto"


def _holiday_reason_db_for_date(date_str: str) -> str:
    d = _parse_iso_date(date_str)
    if not d:
        return "Bayram kuni"
    name = str(uz_holidays.get(d) or "").strip()
    return f"Bayram: {name}" if name else "Bayram kuni"


def list_upcoming_holiday_days(*, start_offset: int = 0, days_count: int = 11, lang: str = "uz") -> list[dict[str, Any]]:
    rows = get_days_status(start_offset=start_offset, days_count=days_count, lang=lang)
    out: list[dict[str, Any]] = []
    for row in rows:
        if not bool(row.get("is_holiday")):
            continue
        date_str = str(row.get("date_str") or "")
        pending = get_pending_lesson_otmen_request_by_date(date_str)
        is_cancelled = is_lesson_otmen_date_cancelled(date_str)
        c1 = is_branch_date_closed_for_booking("branch_1", date_str)
        c2 = is_branch_date_closed_for_booking("branch_2", date_str)
        is_closed = bool(c1 or c2)
        status = "cancelled" if is_cancelled else ("pending" if pending else ("closed" if is_closed else "open"))
        out.append(
            {
                "date": date_str,
                "date_str": date_str,
                "date_ui": row.get("date_ui"),
                "ddm": str(row.get("date_ui") or "").replace("-", "."),
                "weekday": row.get("weekday"),
                "reason": row.get("reason"),
                "reason_db": row.get("reason_db") or _holiday_reason_db_for_date(date_str),
                "is_holiday": True,
                "is_closed": is_closed,
                "closed_reason": get_branch_date_closed_reason("branch_1", date_str)
                or get_branch_date_closed_reason("branch_2", date_str),
                "request_status": status,
                "pending_request_id": str((pending or {}).get("id") or "") or None,
            }
        )
    return out


def ensure_otmen_request_for_day(
    date_str: str,
    reason: str | None = None,
    cancel_mode: str | None = "auto",
    *,
    dedupe_existing_auto: bool = False,
) -> str | None:
    if not _parse_iso_date(date_str):
        return None
    mode = _normalize_cancel_mode(cancel_mode)
    if mode == "auto" and not is_official_holiday_date(date_str):
        return None
    if mode == "auto" and dedupe_existing_auto:
        latest_auto = get_latest_lesson_otmen_request_by_date(str(date_str), cancel_mode="auto")
        if latest_auto:
            latest_status = str(latest_auto.get("status") or "").strip().lower()
            if latest_status == "pending":
                return str(latest_auto.get("id") or "") or None
            # Reopen-aware dedupe:
            # - reopened => allow creating a new auto request/alert
            # - cancelled/expired (and unknown legacy statuses) => keep dedupe block
            if latest_status != "reopened":
                return None
    row = get_pending_lesson_otmen_request_by_date(date_str)
    if row:
        return str(row.get("id"))
    req_id = uuid4().hex[:20]
    exp = (datetime.now(TASHKENT_TZ) + timedelta(hours=48)).isoformat()
    default_reason = _holiday_reason_db_for_date(date_str) if is_official_holiday_date(date_str) else "Manual otmen"
    final_reason = (reason or "").strip() or default_reason
    ok = create_lesson_otmen_request(req_id, str(date_str), final_reason, exp, cancel_mode=mode)
    return req_id if ok else None


def _groups_scheduled_for_date(date_str: str) -> list[dict[str, Any]]:
    d = _parse_iso_date(date_str)
    if not d:
        return []
    wd = d.weekday()
    groups = get_all_groups() or []
    out: list[dict[str, Any]] = []
    for g in groups:
        ld = (g.get("lesson_date") or "").strip()
        if not ld:
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2}$", ld):
            if ld == date_str:
                out.append(g)
            continue
        code = ld.upper()
        if code in ("MWF", "MON/WED/FRI", "MON,WED,FRI", "ODD") and wd in (0, 2, 4):
            out.append(g)
        elif code in ("TTS", "TUE/THU/SAT", "TUE,THU,SAT", "EVEN") and wd in (1, 3, 5):
            out.append(g)
    return out


def _dedupe_recipients(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        tg = str(row.get("telegram_id") or "").strip()
        if not tg:
            continue
        if tg in out:
            continue
        out[tg] = {
            "telegram_id": tg,
            "language": str(row.get("language") or "uz"),
            "id": row.get("id"),
            "login_type": row.get("login_type"),
        }
    return list(out.values())


def execute_otmen_request(
    req_id: str,
    *,
    admin_user_id: int | None,
    reason_override: str | None = None,
    cancel_mode: str | None = "auto",
) -> dict[str, Any]:
    req = get_lesson_otmen_request(req_id)
    if not req:
        return {"ok": False, "code": "invalid"}
    if str(req.get("status") or "") == "cancelled":
        return {"ok": False, "code": "already_done", "date_str": str(req.get("date_str") or "")}
    if str(req.get("status") or "") == "expired":
        return {"ok": False, "code": "expired", "date_str": str(req.get("date_str") or "")}

    date_str = str(req.get("date_str") or "")
    mode = _normalize_cancel_mode(cancel_mode)
    if mode == "auto" and not is_official_holiday_date(date_str):
        return {"ok": False, "code": "not_holiday", "date_str": date_str}
    if is_lesson_otmen_date_cancelled(date_str):
        return {"ok": False, "code": "already_done", "date_str": date_str}

    expires_at = str(req.get("expires_at") or "")
    try:
        exp = datetime.fromisoformat(expires_at) if expires_at else None
    except Exception:
        exp = None
    now_tz = datetime.now(TASHKENT_TZ)
    if exp and now_tz > exp:
        mark_lesson_otmen_request_status(req_id, "expired", admin_id=admin_user_id)
        return {"ok": False, "code": "expired", "date_str": date_str}

    groups = _groups_scheduled_for_date(date_str)

    sessions_count = 0
    if groups:
        conn = get_conn()
        cur = conn.cursor()
        try:
            for g in groups:
                cur.execute("DELETE FROM attendance WHERE group_id=? AND date=?", (g["id"], date_str))
                cur.execute(
                    "UPDATE attendance_sessions SET status='closed', closed_at=CURRENT_TIMESTAMP WHERE group_id=? AND date=?",
                    (g["id"], date_str),
                )
                if cur.rowcount > 0:
                    sessions_count += int(cur.rowcount)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()

    booking_count = 0
    booking_students: list[dict[str, Any]] = []
    bookings = list_lesson_bookings_by_date(date_str, statuses=("pending", "approved"))
    for b in bookings:
        ok = set_lesson_booking_status(
            str(b.get("id")),
            "canceled",
            admin_id=int(admin_user_id or 0),
            admin_note="holiday_otmen",
        )
        if not ok:
            continue
        booking_count += 1
        user_id = int(b.get("student_user_id") or 0)
        row = get_user_by_id(user_id) if user_id > 0 else None
        if row:
            booking_students.append(row)
            continue
        tg = str(b.get("student_telegram_id") or "").strip()
        if tg:
            booking_students.append({"telegram_id": tg, "language": "uz"})

    temporary_assignments_count = 0
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE temporary_group_assignments
            SET status='cancelled', cancelled_at=CURRENT_TIMESTAMP
            WHERE lesson_date=? AND status='active'
            """,
            (date_str,),
        )
        temporary_assignments_count = int(cur.rowcount or 0)
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()

    set_branch_date_closed("branch_1", date_str, "holiday_otmen")
    set_branch_date_closed("branch_2", date_str, "holiday_otmen")

    teachers: list[dict[str, Any]] = []
    students: list[dict[str, Any]] = []
    for g in groups:
        teacher_id = int(g.get("teacher_id") or 0)
        if teacher_id > 0:
            t_row = get_user_by_id(teacher_id)
            if t_row:
                teachers.append(t_row)
        for u in get_group_users(g["id"]):
            if int(u.get("login_type") or 0) in (1, 2):
                students.append(u)

    reason = (reason_override or req.get("reason") or _holiday_reason_db_for_date(date_str) or "").strip()
    mark_lesson_otmen_request_status(req_id, "cancelled", admin_id=admin_user_id)

    return {
        "ok": True,
        "code": "done",
        "cancel_mode": mode,
        "date_str": date_str,
        "reason": reason,
        "request_id": str(req_id),
        "stats": {
            "groups": len(groups),
            "sessions": int(sessions_count),
            "bookings": int(booking_count),
            "temporary_assignments": int(temporary_assignments_count),
            "arena": 0,
        },
        "teachers": _dedupe_recipients(teachers),
        "students": _dedupe_recipients(students),
        "booking_students": _dedupe_recipients(booking_students),
    }


def execute_otmen_for_date(
    date_str: str,
    *,
    admin_user_id: int | None,
    reason_override: str | None = None,
    cancel_mode: str | None = "manual",
) -> dict[str, Any]:
    date_iso = str(date_str or "").strip()
    if not _parse_iso_date(date_iso):
        return {"ok": False, "code": "invalid_date", "date_str": date_iso}
    mode = _normalize_cancel_mode(cancel_mode)
    if mode == "auto" and not is_official_holiday_date(date_iso):
        return {"ok": False, "code": "not_holiday", "date_str": date_iso}
    if is_lesson_otmen_date_cancelled(date_iso):
        return {"ok": False, "code": "already_done", "date_str": date_iso}
    req_id = ensure_otmen_request_for_day(date_iso, reason_override, cancel_mode=mode)
    if not req_id:
        return {"ok": False, "code": "invalid", "date_str": date_iso}
    return execute_otmen_request(
        req_id,
        admin_user_id=admin_user_id,
        reason_override=reason_override,
        cancel_mode=mode,
    )


def _latest_otmen_request_id_for_date(date_iso: str) -> str | None:
    row = get_latest_lesson_otmen_request_by_date(str(date_iso))
    return str((row or {}).get("id") or "") or None


def reopen_otmen_date(date_str: str) -> dict[str, Any]:
    date_iso = str(date_str or "").strip()
    if not _parse_iso_date(date_iso):
        return {"ok": False, "code": "invalid_date", "date_str": date_iso}
    open_branch_date_for_booking("branch_1", date_iso)
    open_branch_date_for_booking("branch_2", date_iso)
    req_id = _latest_otmen_request_id_for_date(date_iso)
    if req_id:
        mark_lesson_otmen_request_status(req_id, "reopened", admin_id=None)
    still_closed = is_branch_date_closed_for_booking("branch_1", date_iso) or is_branch_date_closed_for_booking("branch_2", date_iso)
    return {
        "ok": not bool(still_closed),
        "code": "done" if not still_closed else "failed",
        "date_str": date_iso,
        "request_id": req_id,
    }


def list_cancelled_otmen_requests(limit: int = 20) -> list[dict[str, Any]]:
    return list_cancelled_lesson_otmen_requests(limit=int(limit or 20))
