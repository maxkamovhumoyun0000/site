"""
Payment compatibility layer.

This module keeps old bot call signatures while moving storage/logic to the
new payment automation model (payment_monthly_obligations + transactions/refunds).
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Tuple

import pytz
from openpyxl import Workbook

from db import DB_WRITE_LOCK, _ym_now, get_conn


PAYMENT_STATUS_PAID = "To'langan"
PAYMENT_STATUS_PARTIAL = "Qisman to'langan"
PAYMENT_STATUS_UNPAID = "To'lanmagan"
PAYMENT_STATUS_OVERDUE = "Kechikkan"
PAYMENT_STATUS_OVERPAY = "Ortiqcha to'lov"


def _month_key_months_ago(months_ago: int) -> str:
    now = datetime.now(pytz.timezone("Asia/Tashkent"))
    year = int(now.year)
    month = int(now.month) - int(months_ago)
    while month <= 0:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def _prev_month_ym(ym: str) -> str:
    y, m = map(int, ym.split("-"))
    if m == 1:
        return f"{y - 1}-12"
    return f"{y}-{m - 1:02d}"


def _is_month_overdue(ym: str, debt_amount: float) -> bool:
    if float(debt_amount or 0.0) <= 1e-9:
        return False
    tz = pytz.timezone("Asia/Tashkent")
    today = datetime.now(tz).date()
    try:
        y, m = [int(part) for part in str(ym).split("-", 1)]
        due_day = datetime(y, m, 15).date()
    except Exception:
        return False
    return today > due_day


def _status_label(final_amount: float, paid_amount: float, ym: str) -> str:
    final_v = max(0.0, float(final_amount or 0.0))
    paid_v = max(0.0, float(paid_amount or 0.0))
    debt_v = max(0.0, final_v - paid_v)
    over_v = max(0.0, paid_v - final_v)
    overdue = _is_month_overdue(ym, debt_v)
    if over_v > 1e-9:
        return PAYMENT_STATUS_OVERPAY
    if debt_v <= 1e-9:
        return PAYMENT_STATUS_PAID
    if paid_v > 1e-9:
        return PAYMENT_STATUS_OVERDUE if overdue else PAYMENT_STATUS_PARTIAL
    return PAYMENT_STATUS_OVERDUE if overdue else PAYMENT_STATUS_UNPAID


def _ensure_payment_tables() -> None:
    conn = get_conn()
    cur = conn.cursor()
    statements = (
        """
        CREATE TABLE IF NOT EXISTS payment_monthly_obligations (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL,
            ym TEXT NOT NULL,
            subject TEXT,
            course_id BIGINT,
            course_title TEXT,
            original_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            discount_type TEXT NOT NULL DEFAULT 'none',
            discount_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
            discount_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            final_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            paid_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            debt_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            overpayment_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'To''lanmagan',
            overdue INTEGER NOT NULL DEFAULT 0,
            due_day INTEGER NOT NULL DEFAULT 15,
            is_accountless INTEGER NOT NULL DEFAULT 0,
            meta_json TEXT,
            last_calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_paid_at TIMESTAMP,
            last_refund_at TIMESTAMP,
            closed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, group_id, ym)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id BIGSERIAL PRIMARY KEY,
            obligation_id BIGINT,
            user_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL,
            ym TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            payment_method TEXT NOT NULL DEFAULT 'cash',
            card_id BIGINT,
            note TEXT,
            is_advance INTEGER NOT NULL DEFAULT 0,
            confirmed_by_admin_id BIGINT,
            confirmed_by_admin_name TEXT,
            status_after TEXT,
            remaining_after DOUBLE PRECISION NOT NULL DEFAULT 0,
            overpayment_after DOUBLE PRECISION NOT NULL DEFAULT 0,
            refunded_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payment_refunds (
            id BIGSERIAL PRIMARY KEY,
            transaction_id BIGINT NOT NULL,
            obligation_id BIGINT,
            user_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL,
            ym TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            note TEXT NOT NULL,
            refunded_by_admin_id BIGINT,
            refunded_by_admin_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payment_bot_award_cache (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL,
            ym TEXT NOT NULL,
            payment_dcoin_amount DOUBLE PRECISION,
            paid_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, group_id, ym)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS payment_reminder_log (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            group_id BIGINT NOT NULL DEFAULT 0,
            ym TEXT NOT NULL,
            reminder_day INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, group_id, ym, reminder_day)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_payment_reminder_log_user_ym ON payment_reminder_log(user_id, ym)",
    )
    for sql in statements:
        try:
            cur.execute(sql)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    for sql in (
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS card_id BIGINT",
        "ALTER TABLE payment_transactions ADD COLUMN IF NOT EXISTS refunded_amount DOUBLE PRECISION NOT NULL DEFAULT 0",
    ):
        try:
            cur.execute(sql)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
    conn.close()


def _get_or_create_obligation(cur, user_id: int, ym: str, group_id: int | None, subject: str | None) -> dict:
    gid = int(group_id or 0)
    if gid <= 0:
        return {}
    cur.execute(
        """
        SELECT *
        FROM payment_monthly_obligations
        WHERE user_id=? AND group_id=? AND ym=?
        LIMIT 1
        """,
        (int(user_id), gid, str(ym)),
    )
    row = dict(cur.fetchone() or {})
    if row:
        return row
    cur.execute(
        """
        INSERT INTO payment_monthly_obligations
        (
            user_id, group_id, ym, subject, original_amount,
            discount_type, discount_percent, discount_amount, final_amount,
            paid_amount, debt_amount, overpayment_amount, status, overdue,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, 0, 'none', 0, 0, 0, 0, 0, 0, ?, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, group_id, ym) DO NOTHING
        """,
        (int(user_id), gid, str(ym), (str(subject).strip() if subject else None), PAYMENT_STATUS_UNPAID),
    )
    cur.execute(
        """
        SELECT *
        FROM payment_monthly_obligations
        WHERE user_id=? AND group_id=? AND ym=?
        LIMIT 1
        """,
        (int(user_id), gid, str(ym)),
    )
    return dict(cur.fetchone() or {})


def _refresh_obligation(cur, obligation_id: int) -> dict:
    cur.execute("SELECT * FROM payment_monthly_obligations WHERE id=? LIMIT 1", (int(obligation_id),))
    row = dict(cur.fetchone() or {})
    if not row:
        return {}
    ym = str(row.get("ym") or _ym_now())
    final_amount = float(row.get("final_amount") or 0.0)
    paid_amount = float(row.get("paid_amount") or 0.0)
    debt_amount = max(0.0, final_amount - paid_amount)
    overpayment_amount = max(0.0, paid_amount - final_amount)
    status = _status_label(final_amount, paid_amount, ym)
    overdue = 1 if _is_month_overdue(ym, debt_amount) else 0
    closed_at = "CURRENT_TIMESTAMP" if debt_amount <= 1e-9 and final_amount > 0 else None
    if closed_at:
        cur.execute(
            """
            UPDATE payment_monthly_obligations
            SET debt_amount=?, overpayment_amount=?, status=?, overdue=?, closed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (float(debt_amount), float(overpayment_amount), str(status), int(overdue), int(obligation_id)),
        )
    else:
        cur.execute(
            """
            UPDATE payment_monthly_obligations
            SET debt_amount=?, overpayment_amount=?, status=?, overdue=?, closed_at=NULL, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (float(debt_amount), float(overpayment_amount), str(status), int(overdue), int(obligation_id)),
        )
    cur.execute("SELECT * FROM payment_monthly_obligations WHERE id=? LIMIT 1", (int(obligation_id),))
    return dict(cur.fetchone() or {})


def export_payment_history_to_xlsx(
    owner_admin_id: int | None = None,
    filters: dict | None = None,
    scoped_group_ids: set[int] | None = None,
) -> Tuple[io.BytesIO, str]:
    _ensure_payment_tables()
    now = datetime.now(pytz.timezone("Asia/Tashkent"))
    filt = dict(filters or {})
    months = int(filt.get("months") or 3)
    months = min(36, max(1, months))
    from_ym = _month_key_months_ago(max(0, months - 1))
    date_from = str(filt.get("date_from") or "").strip()
    date_to = str(filt.get("date_to") or "").strip()
    selected_group_id = int(filt.get("group_id") or 0)
    teacher_filter = str(filt.get("teacher_name") or "").strip().lower()
    subject_filter = str(filt.get("subject") or "").strip().lower()
    status_filter = str(filt.get("payment_status") or "").strip().lower()
    method_filter = str(filt.get("payment_method") or "").strip().lower()

    conn = get_conn()
    cur = conn.cursor()
    where_scope = ""
    params_scope: list = []
    if owner_admin_id is not None:
        where_scope = """
            AND (
                u.owner_admin_id = ?
                OR u.id IN (
                    SELECT student_id FROM admin_student_shares
                    WHERE peer_admin_id = ? AND status = 'active'
                )
            )
        """
        params_scope = [int(owner_admin_id), int(owner_admin_id)]
    cur.execute(
        f"""
        SELECT
            tx.id, tx.user_id, tx.group_id, tx.ym, tx.amount, tx.payment_method, tx.card_id, tx.note, tx.is_advance,
            tx.status_after, tx.remaining_after, tx.overpayment_after, tx.confirmed_by_admin_name, tx.created_at,
            COALESCE(tx.refunded_amount, 0) AS refunded_amount,
            ob.original_amount, ob.discount_type, ob.discount_percent, ob.discount_amount, ob.final_amount, ob.debt_amount, ob.overpayment_amount,
            TRIM(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) AS student_name,
            u.phone AS student_phone,
            g.name AS group_name, g.subject AS group_subject, g.course_title, g.teacher_id,
            TRIM(COALESCE(t.first_name,'') || ' ' || COALESCE(t.last_name,'')) AS teacher_name,
            pc.card_number, pc.owner_first_name AS card_owner_first_name, pc.owner_last_name AS card_owner_last_name
        FROM payment_transactions tx
        LEFT JOIN payment_monthly_obligations ob ON ob.id = tx.obligation_id
        JOIN users u ON u.id = tx.user_id
        LEFT JOIN groups g ON g.id = tx.group_id
        LEFT JOIN users t ON t.id = g.teacher_id
        LEFT JOIN payment_cards pc ON pc.id = tx.card_id
        WHERE tx.ym >= ?
        {where_scope}
        ORDER BY tx.created_at DESC, tx.id DESC
        LIMIT 5000
        """,
        tuple([from_ym, *params_scope]),
    )
    tx_rows = [dict(r) for r in (cur.fetchall() or [])]

    tx_ids = [int(row.get("id") or 0) for row in tx_rows if int(row.get("id") or 0) > 0]
    bonus_map: dict[int, float] = {}
    penalty_map: dict[int, float] = {}
    if tx_ids:
        placeholders = ", ".join(["?"] * len(tx_ids))
        cur.execute(
            f"""
            SELECT source_transaction_id, SUM(COALESCE(amount,0)) AS total_amount
            FROM payment_bonus_log
            WHERE source_transaction_id IN ({placeholders})
              AND COALESCE(reversed,0)=0
            GROUP BY source_transaction_id
            """,
            tuple(tx_ids),
        )
        for row in (cur.fetchall() or []):
            item = dict(row)
            tid = int(item.get("source_transaction_id") or 0)
            if tid > 0:
                bonus_map[tid] = float(item.get("total_amount") or 0.0)
        cur.execute(
            f"""
            SELECT source_transaction_id, SUM(COALESCE(amount,0)) AS total_amount
            FROM payment_penalty_log
            WHERE source_transaction_id IN ({placeholders})
            GROUP BY source_transaction_id
            """,
            tuple(tx_ids),
        )
        for row in (cur.fetchall() or []):
            item = dict(row)
            tid = int(item.get("source_transaction_id") or 0)
            if tid > 0:
                penalty_map[tid] = float(item.get("total_amount") or 0.0)
    cur.execute(
        f"""
        SELECT
            r.id, r.transaction_id, r.user_id, r.group_id, r.ym, r.amount, r.refund_type, r.note, r.status_after, r.created_at,
            r.debt_after, r.overpayment_after, r.refunded_by_admin_name,
            TRIM(COALESCE(u.first_name,'') || ' ' || COALESCE(u.last_name,'')) AS student_name,
            u.phone AS student_phone,
            g.name AS group_name, g.subject AS group_subject, g.course_title, g.teacher_id,
            TRIM(COALESCE(t.first_name,'') || ' ' || COALESCE(t.last_name,'')) AS teacher_name
        FROM payment_refunds r
        JOIN users u ON u.id = r.user_id
        LEFT JOIN groups g ON g.id = r.group_id
        LEFT JOIN users t ON t.id = g.teacher_id
        WHERE r.ym >= ?
        {where_scope}
        ORDER BY r.created_at DESC, r.id DESC
        LIMIT 5000
        """,
        tuple([from_ym, *params_scope]),
    )
    refund_rows = [dict(r) for r in (cur.fetchall() or [])]

    refund_ids = [int(row.get("id") or 0) for row in refund_rows if int(row.get("id") or 0) > 0]
    refund_bonus_map: dict[int, float] = {}
    if refund_ids:
        placeholders = ", ".join(["?"] * len(refund_ids))
        cur.execute(
            f"""
            SELECT source_refund_id, SUM(COALESCE(amount,0)) AS total_amount
            FROM payment_bonus_log
            WHERE source_refund_id IN ({placeholders})
            GROUP BY source_refund_id
            """,
            tuple(refund_ids),
        )
        for row in (cur.fetchall() or []):
            item = dict(row)
            rid = int(item.get("source_refund_id") or 0)
            if rid > 0:
                refund_bonus_map[rid] = float(item.get("total_amount") or 0.0)
    conn.close()

    scoped = set(int(v) for v in (scoped_group_ids or set()) if int(v) > 0)

    def _row_date_ok(raw_value: str) -> bool:
        value = str(raw_value or "")
        day = value[:10]
        if date_from and day < date_from:
            return False
        if date_to and day > date_to:
            return False
        return True

    out_rows: list[dict] = []
    for row in tx_rows:
        group_id = int(row.get("group_id") or 0)
        if scoped and group_id > 0 and group_id not in scoped:
            continue
        if selected_group_id > 0 and group_id != selected_group_id:
            continue
        if not _row_date_ok(str(row.get("created_at") or "")):
            continue
        if teacher_filter and teacher_filter not in str(row.get("teacher_name") or "").lower():
            continue
        if subject_filter and subject_filter != "all" and subject_filter not in str(row.get("group_subject") or "").lower():
            continue
        method = str(row.get("payment_method") or "").strip().lower() or "cash"
        if method_filter and method_filter != "all" and method_filter != method:
            continue
        status = str(row.get("status_after") or PAYMENT_STATUS_UNPAID)
        if status_filter and status_filter != "all" and status_filter not in status.lower():
            continue
        card_number = str(row.get("card_number") or "").strip()
        digits = "".join(ch for ch in card_number if ch.isdigit())
        card_masked = f"{digits[:4]} **** **** {digits[-4:]}" if len(digits) >= 8 else card_number
        card_owner = f"{str(row.get('card_owner_first_name') or '').strip()} {str(row.get('card_owner_last_name') or '').strip()}".strip()
        out_rows.append(
            {
                "record_type": "payment",
                "student_name": row.get("student_name") or "-",
                "student_phone": row.get("student_phone") or "-",
                "group_name": row.get("group_name") or "-",
                "course_title": row.get("course_title") or "-",
                "group_subject": row.get("group_subject") or "-",
                "teacher_name": row.get("teacher_name") or "-",
                "original_amount": float(row.get("original_amount") or 0.0),
                "discount_type": row.get("discount_type") or "none",
                "discount_percent": float(row.get("discount_percent") or 0.0),
                "discount_amount": float(row.get("discount_amount") or 0.0),
                "final_amount": float(row.get("final_amount") or 0.0),
                "paid_amount": float(row.get("amount") or 0.0),
                "debt_amount": float(row.get("remaining_after") or row.get("debt_amount") or 0.0),
                "overpayment_amount": float(row.get("overpayment_after") or row.get("overpayment_amount") or 0.0),
                "ym": row.get("ym") or "-",
                "payment_method": method,
                "card_info": f"{card_owner} — {card_masked}".strip(" —") if (card_owner or card_masked) else "-",
                "status": status,
                "admin_name": row.get("confirmed_by_admin_name") or "-",
                "created_at": row.get("created_at") or "-",
                "note": row.get("note") or "",
                "refund_info": f"Refunded: {float(row.get('refunded_amount') or 0.0):.2f}" if float(row.get("refunded_amount") or 0.0) > 0 else "",
                "bonus_dpoint": float(bonus_map.get(int(row.get("id") or 0), 0.0)),
                "penalty_dcoin": float(penalty_map.get(int(row.get("id") or 0), 0.0)),
            }
        )

    for row in refund_rows:
        group_id = int(row.get("group_id") or 0)
        if scoped and group_id > 0 and group_id not in scoped:
            continue
        if selected_group_id > 0 and group_id != selected_group_id:
            continue
        if not _row_date_ok(str(row.get("created_at") or "")):
            continue
        if teacher_filter and teacher_filter not in str(row.get("teacher_name") or "").lower():
            continue
        if subject_filter and subject_filter != "all" and subject_filter not in str(row.get("group_subject") or "").lower():
            continue
        if method_filter and method_filter != "all" and method_filter != "refund":
            continue
        status = str(row.get("status_after") or PAYMENT_STATUS_UNPAID)
        if status_filter and status_filter != "all" and status_filter not in status.lower():
            continue
        out_rows.append(
            {
                "record_type": "refund",
                "student_name": row.get("student_name") or "-",
                "student_phone": row.get("student_phone") or "-",
                "group_name": row.get("group_name") or "-",
                "course_title": row.get("course_title") or "-",
                "group_subject": row.get("group_subject") or "-",
                "teacher_name": row.get("teacher_name") or "-",
                "original_amount": 0.0,
                "discount_type": "none",
                "discount_percent": 0.0,
                "discount_amount": 0.0,
                "final_amount": 0.0,
                "paid_amount": -abs(float(row.get("amount") or 0.0)),
                "debt_amount": float(row.get("debt_after") or 0.0),
                "overpayment_amount": float(row.get("overpayment_after") or 0.0),
                "ym": row.get("ym") or "-",
                "payment_method": "refund",
                "card_info": "-",
                "status": status,
                "admin_name": row.get("refunded_by_admin_name") or "-",
                "created_at": row.get("created_at") or "-",
                "note": row.get("note") or "",
                "refund_info": f"{str(row.get('refund_type') or 'partial')} refund, tx #{int(row.get('transaction_id') or 0)}",
                "bonus_dpoint": -abs(float(refund_bonus_map.get(int(row.get("id") or 0), 0.0))),
                "penalty_dcoin": 0.0,
            }
        )

    out_rows.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Payments"
    headers = [
        "Record Type",
        "Student full name",
        "Student phone",
        "Group",
        "Course",
        "Subject",
        "Teacher",
        "Original amount",
        "Discount type",
        "Discount percentage",
        "Discount amount",
        "Final payable amount",
        "Paid amount",
        "Debt after transaction",
        "Overpayment after transaction",
        "Month/year",
        "Payment method",
        "Card info",
        "Status after transaction",
        "Admin",
        "Date/time",
        "Note",
        "Refund info",
        "D'point bonus",
        "D'coin penalty",
    ]
    ws.append(headers)
    for row in out_rows:
        ws.append(
            [
                row.get("record_type") or "-",
                row.get("student_name") or "-",
                row.get("student_phone") or "-",
                row.get("group_name") or "-",
                row.get("course_title") or "-",
                row.get("group_subject") or "-",
                row.get("teacher_name") or "-",
                float(row.get("original_amount") or 0.0),
                row.get("discount_type") or "none",
                float(row.get("discount_percent") or 0.0),
                float(row.get("discount_amount") or 0.0),
                float(row.get("final_amount") or 0.0),
                float(row.get("paid_amount") or 0.0),
                float(row.get("debt_amount") or 0.0),
                float(row.get("overpayment_amount") or 0.0),
                row.get("ym") or "-",
                row.get("payment_method") or "-",
                row.get("card_info") or "-",
                row.get("status") or PAYMENT_STATUS_UNPAID,
                row.get("admin_name") or "-",
                row.get("created_at") or "-",
                row.get("note") or "",
                row.get("refund_info") or "",
                float(row.get("bonus_dpoint") or 0.0),
                float(row.get("penalty_dcoin") or 0.0),
            ]
        )

    for column in ws.columns:
        max_len = 0
        letter = column[0].column_letter
        for cell in column:
            try:
                max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[letter].width = min(max_len + 2, 38)

    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio, f"payment_history_{now.strftime('%Y-%m-%d')}.xlsx"


def cleanup_old_payment_history() -> int:
    # Keep obligations/transactions as system-of-record. We only trim old dedupe/cache rows.
    _ensure_payment_tables()
    from_ym = _month_key_months_ago(6)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM payment_reminder_log WHERE ym < ?", (from_ym,))
    removed = int(cur.rowcount or 0)
    cur.execute("DELETE FROM payment_bot_award_cache WHERE ym < ?", (from_ym,))
    removed += int(cur.rowcount or 0)
    conn.commit()
    conn.close()
    return removed


def get_payment_history_for_student(student_id: int, months: int = 3) -> list:
    _ensure_payment_tables()
    from_ym = _month_key_months_ago(max(0, int(months) - 1))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT tx.*, ob.status, ob.final_amount, ob.discount_amount, ob.discount_type, ob.discount_percent,
               ob.debt_amount, ob.overpayment_amount, g.name AS group_name, g.level AS group_level
        FROM payment_transactions tx
        LEFT JOIN payment_monthly_obligations ob ON ob.id = tx.obligation_id
        LEFT JOIN groups g ON g.id = tx.group_id
        WHERE tx.user_id=? AND tx.ym >= ?
        ORDER BY tx.created_at DESC, tx.id DESC
        """,
        (int(student_id), from_ym),
    )
    rows = [dict(row) for row in (cur.fetchall() or [])]
    conn.close()
    return rows


def get_payment_stats_by_group(group_id: int, months: int = 3) -> dict:
    _ensure_payment_tables()
    from_ym = _month_key_months_ago(max(0, int(months) - 1))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            ym,
            COUNT(DISTINCT user_id) AS total_students,
            SUM(CASE WHEN status IN (?, ?) THEN 1 ELSE 0 END) AS paid_students,
            SUM(CASE WHEN status NOT IN (?, ?) THEN 1 ELSE 0 END) AS unpaid_students
        FROM payment_monthly_obligations
        WHERE group_id=? AND ym >= ?
        GROUP BY ym
        ORDER BY ym DESC
        """,
        (PAYMENT_STATUS_PAID, PAYMENT_STATUS_OVERPAY, PAYMENT_STATUS_PAID, PAYMENT_STATUS_OVERPAY, int(group_id), from_ym),
    )
    result = [dict(row) for row in (cur.fetchall() or [])]
    conn.close()
    return {"items": result}


def set_month_paid(
    user_id: int,
    ym: str | None = None,
    group_id: int | None = None,
    subject: str | None = None,
    paid: bool = True,
    paid_by_admin_id: int | None = None,
    paid_by_admin_name: str | None = None,
    payment_type: str | None = None,
):
    ym = ym or _ym_now()
    _ensure_payment_tables()
    gid = int(group_id or 0)
    if gid <= 0:
        return
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("BEGIN")
            obligation = _get_or_create_obligation(cur, int(user_id), str(ym), gid, subject)
            oid = int(obligation.get("id") or 0)
            if oid <= 0:
                conn.rollback()
                conn.close()
                return
            final_amount = float(obligation.get("final_amount") or 0.0)
            paid_amount = float(obligation.get("paid_amount") or 0.0)
            if paid:
                delta = max(0.0, final_amount - paid_amount)
                if delta > 1e-9:
                    cur.execute(
                        """
                        INSERT INTO payment_transactions
                        (
                            obligation_id, user_id, group_id, ym, amount, payment_method, note, is_advance,
                            confirmed_by_admin_id, confirmed_by_admin_name, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            oid,
                            int(user_id),
                            gid,
                            str(ym),
                            float(delta),
                            str(payment_type or "admin_bot_toggle"),
                            "legacy_toggle_paid",
                            int(paid_by_admin_id) if paid_by_admin_id else None,
                            (str(paid_by_admin_name).strip() if paid_by_admin_name else None),
                        ),
                    )
                    cur.execute(
                        """
                        UPDATE payment_monthly_obligations
                        SET paid_amount=COALESCE(paid_amount,0)+?,
                            last_paid_at=CURRENT_TIMESTAMP,
                            updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                        """,
                        (float(delta), oid),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE payment_monthly_obligations
                        SET last_paid_at=COALESCE(last_paid_at, CURRENT_TIMESTAMP),
                            updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                        """,
                        (oid,),
                    )
            else:
                cur.execute(
                    """
                    UPDATE payment_monthly_obligations
                    SET paid_amount=0,
                        overpayment_amount=0,
                        last_refund_at=CURRENT_TIMESTAMP,
                        updated_at=CURRENT_TIMESTAMP,
                        closed_at=NULL
                    WHERE id=?
                    """,
                    (oid,),
                )
            _refresh_obligation(cur, oid)
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()


def is_month_paid(user_id: int, ym: str | None = None, group_id: int | None = None) -> bool:
    ym = ym or _ym_now()
    gid = int(group_id or 0)
    if gid <= 0:
        return False
    _ensure_payment_tables()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT status, debt_amount
        FROM payment_monthly_obligations
        WHERE user_id=? AND group_id=? AND ym=?
        LIMIT 1
        """,
        (int(user_id), gid, str(ym)),
    )
    row = dict(cur.fetchone() or {})
    conn.close()
    if not row:
        return False
    status = str(row.get("status") or "")
    debt = float(row.get("debt_amount") or 0.0)
    return status in (PAYMENT_STATUS_PAID, PAYMENT_STATUS_OVERPAY) and debt <= 1e-9


def confirm_group_payment(
    user_id: int,
    ym: str | None = None,
    group_id: int | None = None,
    subject: str | None = None,
    paid_by_admin_id: int | None = None,
    paid_by_admin_name: str | None = None,
    payment_type: str | None = None,
) -> None:
    """Bot/web-safe wrapper around the new obligations write-model."""
    set_month_paid(
        user_id=user_id,
        ym=ym,
        group_id=group_id,
        subject=subject,
        paid=True,
        paid_by_admin_id=paid_by_admin_id,
        paid_by_admin_name=paid_by_admin_name,
        payment_type=payment_type,
    )


def revoke_group_payment(
    user_id: int,
    ym: str | None = None,
    group_id: int | None = None,
    subject: str | None = None,
    paid_by_admin_id: int | None = None,
    paid_by_admin_name: str | None = None,
    payment_type: str | None = None,
) -> None:
    """Bot/web-safe wrapper around the new obligations write-model."""
    set_month_paid(
        user_id=user_id,
        ym=ym,
        group_id=group_id,
        subject=subject,
        paid=False,
        paid_by_admin_id=paid_by_admin_id,
        paid_by_admin_name=paid_by_admin_name,
        payment_type=payment_type,
    )


def is_group_payment_closed(user_id: int, ym: str | None = None, group_id: int | None = None) -> bool:
    return is_month_paid(user_id=user_id, ym=ym, group_id=group_id)


def get_unpaid_obligations(user_id: int) -> list[dict]:
    _ensure_payment_tables()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT *
        FROM payment_monthly_obligations
        WHERE user_id=? AND debt_amount > 1e-9 AND status NOT IN (?, ?)
        """,
        (int(user_id), PAYMENT_STATUS_PAID, PAYMENT_STATUS_OVERPAY),
    )
    rows = [dict(row) for row in (cur.fetchall() or [])]
    conn.close()
    return rows



def was_notified_on_day(
    user_id: int,
    day: int,
    ym: str | None = None,
    group_id: int | None = None,
) -> bool:
    ym = ym or _ym_now()
    _ensure_payment_tables()
    conn = get_conn()
    cur = conn.cursor()
    gid = int(group_id or 0)
    cur.execute(
        "SELECT 1 FROM payment_reminder_log WHERE user_id=? AND ym=? AND group_id=? AND reminder_day=? LIMIT 1",
        (int(user_id), str(ym), gid, int(day)),
    )
    exists = cur.fetchone() is not None
    conn.close()
    return bool(exists)


def mark_notified_day(
    user_id: int,
    day: int,
    ym: str | None = None,
    group_id: int | None = None,
) -> bool:
    ym = ym or _ym_now()
    _ensure_payment_tables()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        gid = int(group_id or 0)
        cur.execute(
            """
            INSERT INTO payment_reminder_log(user_id, group_id, ym, reminder_day, created_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, group_id, ym, reminder_day) DO NOTHING
            """,
            (int(user_id), gid, str(ym), int(day)),
        )
        inserted = (getattr(cur, "rowcount", 0) or 0) > 0
        conn.commit()
        conn.close()
        return inserted


def get_month_payment_row(
    user_id: int,
    ym: str | None = None,
    group_id: int | None = None,
) -> dict | None:
    ym = ym or _ym_now()
    gid = int(group_id or 0)
    if gid <= 0:
        return None
    _ensure_payment_tables()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT o.*, a.payment_dcoin_amount
        FROM payment_monthly_obligations o
        LEFT JOIN payment_bot_award_cache a
          ON a.user_id=o.user_id AND a.group_id=o.group_id AND a.ym=o.ym
        WHERE o.user_id=? AND o.group_id=? AND o.ym=?
        LIMIT 1
        """,
        (int(user_id), gid, str(ym)),
    )
    row = dict(cur.fetchone() or {})
    if not row:
        conn.close()
        return None
    gid = int(group_id or 0)
    cur.execute(
        """
        SELECT reminder_day
        FROM payment_reminder_log
        WHERE user_id=? AND ym=? AND group_id=?
        ORDER BY reminder_day ASC
        """,
        (int(user_id), str(ym), gid),
    )
    days = [str(int((d or {}).get("reminder_day") or 0)) for d in (cur.fetchall() or []) if int((d or {}).get("reminder_day") or 0) > 0]
    conn.close()
    paid_status = str(row.get("status") or "")
    paid = 1 if paid_status in (PAYMENT_STATUS_PAID, PAYMENT_STATUS_OVERPAY) and float(row.get("debt_amount") or 0.0) <= 1e-9 else 0
    row["paid"] = int(paid)
    row["paid_at"] = row.get("last_paid_at")
    row["notified_days"] = ",".join(days)
    return row


def get_month_payment_dcoin_amount(
    user_id: int,
    ym: str | None = None,
    group_id: int | None = None,
) -> float | None:
    ym = ym or _ym_now()
    gid = int(group_id or 0)
    if gid <= 0:
        return None
    _ensure_payment_tables()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT payment_dcoin_amount
        FROM payment_bot_award_cache
        WHERE user_id=? AND group_id=? AND ym=?
        LIMIT 1
        """,
        (int(user_id), gid, str(ym)),
    )
    row = dict(cur.fetchone() or {})
    conn.close()
    val = row.get("payment_dcoin_amount") if row else None
    return float(val) if val is not None else None


def set_month_payment_dcoin_amount(
    user_id: int,
    amount: float | None,
    ym: str | None = None,
    group_id: int | None = None,
) -> bool:
    ym = ym or _ym_now()
    gid = int(group_id or 0)
    if gid <= 0:
        return False
    _ensure_payment_tables()
    with DB_WRITE_LOCK:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO payment_bot_award_cache(user_id, group_id, ym, payment_dcoin_amount, paid_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, group_id, ym)
            DO UPDATE SET payment_dcoin_amount=excluded.payment_dcoin_amount, updated_at=CURRENT_TIMESTAMP
            """,
            (int(user_id), gid, str(ym), amount),
        )
        conn.commit()
        conn.close()
    return True


def apply_daily_overdue_penalties() -> int:
    """
    Legacy scheduler hook retained for compatibility.
    Overdue penalties are now applied only on payment confirmation in backend.
    """
    return 0


def get_payment_award_info(user_id: int, ym: str, group_id: int | None = None) -> dict:
    row = get_month_payment_row(int(user_id), ym=str(ym), group_id=group_id)
    paid = bool(row and int(row.get("paid") or 0) == 1)
    return {
        "paid": paid,
        "paid_at": (row or {}).get("paid_at"),
        "award_amount": float((row or {}).get("payment_dcoin_amount") or 0.0),
        "award_reason": "monthly_payment" if paid else None,
        "award_at": (row or {}).get("updated_at"),
    }


def apply_payment_status(
    *,
    user_id: int,
    group_id: int | None,
    ym: str,
    subject: str | None = None,
    paid: bool,
    paid_by_admin_id: int | None = None,
    paid_by_admin_name: str | None = None,
    payment_type: str | None = None,
) -> bool:
    set_month_paid(
        user_id=int(user_id),
        ym=str(ym),
        group_id=group_id,
        subject=subject,
        paid=bool(paid),
        paid_by_admin_id=paid_by_admin_id,
        paid_by_admin_name=paid_by_admin_name,
        payment_type=payment_type,
    )
    return True
def recalculate_obligation_for_leaving_student(user_id: int, group_id: int, leave_date_iso: str):
    """
    Called when a student leaves a group.
    Finds the obligation for the month of leave_date_iso.
    Counts the number of lessons attended from the start of the month to the leave_date_iso.
    Updates the final_amount of the obligation as (original_final_amount / 12) * attended_lessons.
    """
    import datetime
    from db import get_conn, get_group
    
    conn = get_conn()
    cur = conn.cursor()
    try:
        y, m, d = [int(x) for x in leave_date_iso.split("-")]
        ym = f"{y:04d}-{m:02d}"
        
        cur.execute(
            "SELECT * FROM payment_monthly_obligations WHERE user_id=? AND group_id=? AND ym=?",
            (int(user_id), int(group_id), ym)
        )
        ob = cur.fetchone()
        if not ob:
            return
            
        group = get_group(group_id)
        if not group:
            return
            
        start_date = datetime.date(y, m, 1)
        leave_date = datetime.date(y, m, d)
        
        lesson_pattern = str(group.get("lesson_date") or "").strip()
        
        pattern_days = set()
        if lesson_pattern:
            for part in lesson_pattern.replace(",", "-").replace(" ", "").split("-"):
                if part.isdigit():
                    pattern_days.add(int(part))
                    
        attended_lessons = 0
        curr_date = start_date
        while curr_date <= leave_date:
            weekday_iso = curr_date.isoweekday()
            if weekday_iso in pattern_days:
                attended_lessons += 1
            curr_date += datetime.timedelta(days=1)
            
        attended_lessons = min(attended_lessons, 12)
        
        base_amount = float(ob.get("original_amount") or 0.0)
        total_discount = float(ob.get("discount_amount") or 0.0)
        theoretical_full_amount = max(0.0, base_amount - total_discount)
        
        if theoretical_full_amount > 0 and attended_lessons < 12:
            new_final_amount = (theoretical_full_amount / 12.0) * attended_lessons
            cur.execute(
                "UPDATE payment_monthly_obligations SET final_amount=? WHERE id=?",
                (new_final_amount, int(ob["id"]))
            )
            _refresh_obligation(cur, int(ob["id"]))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()
