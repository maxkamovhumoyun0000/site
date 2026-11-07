"""Speaking app subscription requests, approvals and server-side entitlements.

Payments are intentionally manual for now: users submit a plan request and
the dedicated Speaking administrator approves it after confirming payment.
Quota decisions are made here on the server, never trusted from the client.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field, StrictInt

from db import get_conn
from speaking_contract import is_speaking_app_account

router = APIRouter()
TASHKENT = timezone(timedelta(hours=5))
_SCHEMA_READY = False
_UNSET = object()

TERMS: dict[str, dict[str, Any]] = {
    "week": {"days": 7, "label": "7 kun"},
    "month": {"days": 30, "label": "1 oy"},
    "quarter": {"days": 90, "label": "3 oy"},
    "half_year": {"days": 180, "label": "6 oy"},
}
PLANS: dict[str, dict[str, Any]] = {
    "plus": {"name": "Plus", "prices": {"week": 30_000, "month": 70_000, "quarter": 150_000, "half_year": 350_000}},
    "pro": {"name": "Pro", "prices": {"week": 45_000, "month": 120_000, "quarter": 250_000, "half_year": 600_000}},
}

# Capabilities that are included for a learner entering through Diamond Student.
# Other explicitly paid capabilities still require an approved plan.
STUDENT_INCLUDED = {
    "speaking_questions", "library", "learning_path", "arena", "vocabulary_search",
    "saved_questions", "voice_room", "chats", "video_lessons",
}


def ensure_tables() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_user_subscriptions (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                plan_code TEXT NOT NULL,
                starts_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                approved_by BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_subscriptions_user ON speaking_user_subscriptions(user_id, status, expires_at DESC)")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_subscription_requests (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                plan_code TEXT NOT NULL,
                term_code TEXT NOT NULL,
                amount_uzs BIGINT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                reviewed_by BIGINT,
                review_note TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ
            )"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_speaking_subscription_requests_status ON speaking_subscription_requests(status, created_at DESC)")
        cur.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS uq_speaking_subscription_pending_user
               ON speaking_subscription_requests(user_id) WHERE status='pending'"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_subscription_prices (
                plan_code TEXT NOT NULL,
                term_code TEXT NOT NULL,
                price_uzs BIGINT NOT NULL CHECK (price_uzs >= 0),
                updated_by BIGINT,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(plan_code, term_code)
            )"""
        )
        for plan_code, plan in PLANS.items():
            for term_code, price in plan["prices"].items():
                cur.execute(
                    """INSERT INTO speaking_subscription_prices(plan_code,term_code,price_uzs)
                       VALUES(%s,%s,%s) ON CONFLICT(plan_code,term_code) DO NOTHING""",
                    (plan_code, term_code, int(price)),
                )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_entitlement_usage (
                user_id BIGINT NOT NULL,
                feature TEXT NOT NULL,
                window_key TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(user_id, feature, window_key)
            )"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS speaking_entitlement_sessions (
                user_id BIGINT NOT NULL,
                feature TEXT NOT NULL,
                session_key TEXT NOT NULL,
                window_key TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(user_id, feature, session_key)
            )"""
        )
        conn.commit()
        _SCHEMA_READY = True
    finally:
        cur.close()
        conn.close()


def _user(authorization: str | None) -> dict[str, Any]:
    from backend.main import _require_role, _user_row_from_bearer

    user = _user_row_from_bearer(authorization)
    _require_role(user, {"speaking_user", "student", "speaking_admin", "admin", "superadmin", "developer"})
    return user


def _student_linked(user: dict[str, Any]) -> bool:
    from backend.main import _role_from_login_type

    role = _role_from_login_type(int(user.get("login_type") or 0), str(user.get("login_id") or ""))
    return role == "student" and not is_speaking_app_account(user.get("speaking_app_account"))


def active_plan(user_id: int) -> dict[str, Any] | None:
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT plan_code, starts_at, expires_at FROM speaking_user_subscriptions
               WHERE user_id=%s AND status='active' AND starts_at<=NOW() AND expires_at>NOW()
               ORDER BY expires_at DESC LIMIT 1""",
            (int(user_id),),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()
        conn.close()


def entitlement(user: dict[str, Any], feature: str, *, plan_record: Any = _UNSET) -> dict[str, Any]:
    """Return plan decision, display cap, and bypass metadata for a feature."""
    linked = _student_linked(user)
    plan = active_plan(int(user.get("id") or 0)) if plan_record is _UNSET else plan_record
    tier = str((plan or {}).get("plan_code") or "free").lower()
    paid = tier in PLANS
    allowed = True
    daily: int | None = None
    weekly: int | None = None
    cap: int | None = None
    window: str | None = None
    interval_days: int | None = None

    if feature == "speaking_questions":
        allowed = True
    elif feature in {"library", "learning_path", "vocabulary_search", "saved_questions", "chats"}:
        allowed = paid or (linked and feature in STUDENT_INCLUDED)
    elif feature == "arena":
        allowed = True
        daily = None if paid or linked else 5
        cap, window = (daily, "day") if daily is not None else (None, None)
    elif feature == "voice_room":
        allowed = True
        if linked:
            daily = weekly = None
        elif tier == "pro":
            daily, weekly = 120, 600
        elif tier == "plus":
            daily, weekly = 120, 600
        else:
            daily, weekly = 30, 150
    elif feature == "vocabulary_notebook":
        allowed = paid
        weekly = None if tier == "pro" else (100 if tier == "plus" else 0)
        cap, window = (weekly, "week") if weekly is not None and weekly > 0 else (None, None)
    elif feature == "mock_exam":
        allowed = paid
        interval_days = 3 if tier == "pro" else 7 if tier == "plus" else None
    elif feature == "speaking_plan":
        allowed = paid
        interval_days = 7 if paid else None
    elif feature == "diamondvoy":
        if linked:
            # Student accounts use their linked Student entitlement and are not
            # charged against a second, Speaking-only counter.
            daily = weekly = None
        else:
            daily, weekly = ((20, 100) if tier == "pro" else (10, 50) if tier == "plus" else (3, None))
    elif feature == "answer_analysis":
        allowed = paid
        daily = 6 if tier == "pro" else 3 if tier == "plus" else 0
        if linked:
            allowed = paid
    elif feature == "teacher_feedback":
        allowed = tier == "pro"
        interval_days = 2 if allowed else None
    elif feature == "translator":
        allowed = paid
        daily, weekly = ((10, 50) if tier == "pro" else (5, 25) if tier == "plus" else (0, 0))
    elif feature == "video_lessons":
        allowed = tier == "pro" or (linked and feature in STUDENT_INCLUDED)
    elif feature == "progress":
        allowed = tier == "pro"
    elif feature == "daily_challenge":
        allowed = paid
    elif feature == "schedule":
        # Scheduling is intentionally unavailable until its separate rollout.
        allowed = False
    else:
        allowed = False

    return {
        "allowed": bool(allowed), "feature": feature,
        "plan_code": tier, "student_linked": linked,
        "daily_limit": daily, "weekly_limit": weekly,
        "interval_days": interval_days,
        "expires_at": (plan or {}).get("expires_at"),
    }


def require_feature(user: dict[str, Any], feature: str) -> dict[str, Any]:
    decision = entitlement(user, feature)
    if not decision["allowed"]:
        raise HTTPException(
            status_code=402,
            detail={"code": "subscription_required", "feature": feature, "plan_code": decision["plan_code"]},
        )
    return decision


def consume_usage(user: dict[str, Any], feature: str, window: str, limit: int | None) -> dict[str, int]:
    """Atomically consume quota across all API workers. Unlimited is a no-op."""
    if limit is None:
        return {"used": 0, "limit": 0, "remaining": -1, "reset_in_days": 1}
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        result = consume_usage_in_transaction(cur, int(user.get("id") or 0), feature, window, int(limit))
        conn.commit()
        return result
    finally:
        cur.close()
        conn.close()


def consume_usage_in_transaction(cur: Any, user_id: int, feature: str, window: str, limit: int, *, now: datetime | None = None) -> dict[str, int]:
    """Consume one quota unit inside a caller-owned transaction."""
    used_now = now or datetime.now(TASHKENT)
    if window == "week":
        start = used_now.date() - timedelta(days=used_now.weekday())
        key = f"week:{start.isoformat()}"
        reset = (start + timedelta(days=7) - used_now.date()).days
    else:
        key = f"day:{used_now.date().isoformat()}"
        reset = 1
    if limit <= 0:
        raise HTTPException(status_code=429, detail={"code": "quota_exceeded", "feature": feature, "used": 0, "limit": int(limit), "reset_in_days": reset})
    cur.execute(
        """INSERT INTO speaking_entitlement_usage(user_id, feature, window_key, used)
           VALUES(%s,%s,%s,1)
           ON CONFLICT(user_id,feature,window_key) DO UPDATE
           SET used=speaking_entitlement_usage.used+1, updated_at=NOW()
           WHERE speaking_entitlement_usage.used < %s RETURNING used""",
        (int(user_id), feature, key, int(limit)),
    )
    row = cur.fetchone()
    if not row:
        cur.execute(
            "SELECT used FROM speaking_entitlement_usage WHERE user_id=%s AND feature=%s AND window_key=%s",
            (int(user_id), feature, key),
        )
        used = int(dict(cur.fetchone() or {}).get("used") or 0)
        raise HTTPException(status_code=429, detail={"code": "quota_exceeded", "feature": feature, "used": used, "limit": int(limit), "reset_in_days": reset})
    used = int(dict(row).get("used") or 0)
    return {"used": used, "limit": int(limit), "remaining": max(0, int(limit) - used), "reset_in_days": reset}


def reserve_arena_session(user: dict[str, Any], session_key: str, daily_limit: int | None) -> bool:
    """Atomically count one free-tier arena session, including reconnects only once."""
    if daily_limit is None:
        return False
    ensure_tables()
    now = datetime.now(TASHKENT)
    window_key = f"day:{now.date().isoformat()}"
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO speaking_entitlement_sessions(user_id,feature,session_key,window_key)
               VALUES(%s,'arena',%s,%s) ON CONFLICT DO NOTHING RETURNING session_key""",
            (int(user.get("id") or 0), str(session_key), window_key),
        )
        reserved = bool(cur.fetchone())
        if reserved:
            consume_usage_in_transaction(cur, int(user.get("id") or 0), "arena", "day", int(daily_limit), now=now)
        conn.commit()
        return reserved
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def release_arena_session(user: dict[str, Any], session_key: str) -> None:
    """Return a reservation when joining the session did not succeed."""
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """DELETE FROM speaking_entitlement_sessions WHERE user_id=%s AND feature='arena'
               AND session_key=%s RETURNING window_key""",
            (int(user.get("id") or 0), str(session_key)),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                """UPDATE speaking_entitlement_usage SET used=GREATEST(used-1,0),updated_at=NOW()
                   WHERE user_id=%s AND feature='arena' AND window_key=%s""",
                (int(user.get("id") or 0), dict(row)["window_key"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def consume_usage_windows(user: dict[str, Any], feature: str, limits: dict[str, int | None]) -> None:
    """Charge daily/weekly counters together, rolling back both on any denial."""
    now = datetime.now(TASHKENT)
    user_id = int(user.get("id") or 0)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        for window, limit in limits.items():
            if limit is None:
                continue
            consume_usage_in_transaction(cur, user_id, feature, window, int(limit), now=now)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def usage_count(user: dict[str, Any], feature: str, window: str) -> int:
    now = datetime.now(TASHKENT)
    if window == "week":
        start = now.date() - timedelta(days=now.weekday())
        key = f"week:{start.isoformat()}"
    else:
        key = f"day:{now.date().isoformat()}"
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT used FROM speaking_entitlement_usage WHERE user_id=%s AND feature=%s AND window_key=%s", (int(user.get("id") or 0), feature, key))
        return int(dict(cur.fetchone() or {}).get("used") or 0)
    finally:
        cur.close()
        conn.close()


def consume_interval(user: dict[str, Any], feature: str, interval_days: int | None) -> None:
    if interval_days is None:
        raise HTTPException(status_code=402, detail={"code": "subscription_required", "feature": feature})
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        consume_interval_in_transaction(cur, int(user.get("id") or 0), feature, interval_days)
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def consume_interval_in_transaction(cur: Any, user_id: int, feature: str, interval_days: int | None) -> None:
    """Enforce an interval quota inside a caller-owned transaction."""
    if interval_days is None:
        raise HTTPException(status_code=402, detail={"code": "subscription_required", "feature": feature})
    cur.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
        (f"speaking-entitlement:{int(user_id)}", feature),
    )
    cur.execute(
        """SELECT window_key FROM speaking_entitlement_usage
           WHERE user_id=%s AND feature=%s ORDER BY updated_at DESC LIMIT 1""",
        (int(user_id), feature),
    )
    row = cur.fetchone()
    if row:
        window_key = str(dict(row).get("window_key") or "")
        try:
            prior = datetime.fromisoformat(window_key.removeprefix("at:"))
        except Exception:
            prior = None
        now = datetime.now(timezone.utc)
        if prior and now - prior < timedelta(days=interval_days):
            remaining = max(1, interval_days - (now - prior).days)
            raise HTTPException(status_code=429, detail={"code": "quota_exceeded", "feature": feature, "retry_after_days": remaining})
    stamp = datetime.now(timezone.utc).isoformat()
    cur.execute(
        """INSERT INTO speaking_entitlement_usage(user_id, feature, window_key, used)
           VALUES(%s,%s,%s,1) ON CONFLICT(user_id,feature,window_key)
           DO UPDATE SET used=speaking_entitlement_usage.used+1, updated_at=NOW()""",
        (int(user_id), feature, f"at:{stamp}"),
    )


def _status_payload(user: dict[str, Any]) -> dict[str, Any]:
    ensure_tables()
    uid = int(user.get("id") or 0)
    plan = active_plan(uid)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT plan_code,term_code,price_uzs FROM speaking_subscription_prices")
        prices = {
            (str(row["plan_code"]), str(row["term_code"])): int(row["price_uzs"])
            for row in cur.fetchall()
        }
        cur.execute("SELECT id, plan_code, term_code, amount_uzs, status, created_at FROM speaking_subscription_requests WHERE user_id=%s ORDER BY id DESC LIMIT 1", (uid,))
        request = cur.fetchone()
        features = {name: entitlement(user, name, plan_record=plan) for name in (
            "speaking_questions", "daily_challenge", "library", "learning_path", "arena",
            "vocabulary_search", "vocabulary_notebook", "saved_questions", "voice_room",
            "mock_exam", "speaking_plan", "diamondvoy", "answer_analysis", "teacher_feedback",
            "translator", "video_lessons", "progress", "chats", "schedule",
        )}
        return {
            "plan_code": str((plan or {}).get("plan_code") or "free"),
            "expires_at": (plan or {}).get("expires_at"),
            "student_linked": _student_linked(user),
            "request": dict(request) if request else None,
            "plans": [
                {"code": code, "name": value["name"], "terms": [
                {"code": term, "label": TERMS[term]["label"], "days": TERMS[term]["days"], "price_uzs": prices.get((code, term), int(price))}
                    for term, price in value["prices"].items()
                ]}
                for code, value in PLANS.items()
            ],
            "features": features,
        }
    finally:
        cur.close()
        conn.close()


@router.get("/api/speaking/subscription")
@router.get("/speaking/subscription")
async def get_speaking_subscription(authorization: str | None = Header(default=None)):
    return _status_payload(_user(authorization))


class PlanRequest(BaseModel):
    plan_code: str = Field(pattern="^(plus|pro)$")
    term_code: str = Field(pattern="^(week|month|quarter|half_year)$")


@router.post("/api/speaking/subscription/requests")
@router.post("/speaking/subscription/requests")
async def create_speaking_subscription_request(payload: PlanRequest, authorization: str | None = Header(default=None)):
    user = _user(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s))",
            ("speaking-subscription-request", str(int(user["id"]))),
        )
        cur.execute(
            "SELECT id,plan_code,term_code,amount_uzs,status,created_at FROM speaking_subscription_requests WHERE user_id=%s AND status='pending' ORDER BY id DESC LIMIT 1",
            (int(user["id"]),),
        )
        existing = cur.fetchone()
        if existing:
            conn.commit()
            return {"request": dict(existing), "duplicate": True}
        cur.execute(
            "SELECT price_uzs FROM speaking_subscription_prices WHERE plan_code=%s AND term_code=%s",
            (payload.plan_code, payload.term_code),
        )
        price_row = cur.fetchone()
        if not price_row:
            raise HTTPException(status_code=503, detail={"code": "subscription_price_unavailable"})
        amount = int(dict(price_row)["price_uzs"])
        cur.execute(
            """INSERT INTO speaking_subscription_requests(user_id,plan_code,term_code,amount_uzs)
               VALUES(%s,%s,%s,%s) RETURNING id,plan_code,term_code,amount_uzs,status,created_at""",
            (int(user["id"]), payload.plan_code, payload.term_code, amount),
        )
        row = dict(cur.fetchone())
        conn.commit()
        return {"request": row, "duplicate": False}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


class SubscriptionPriceMatrix(BaseModel):
    prices: dict[str, dict[str, StrictInt]]


def _price_matrix(cur: Any) -> dict[str, dict[str, int]]:
    cur.execute("SELECT plan_code,term_code,price_uzs FROM speaking_subscription_prices ORDER BY plan_code,term_code")
    return _group_prices(cur.fetchall())


def _group_prices(rows: list[Any]) -> dict[str, dict[str, int]]:
    grouped: dict[str, dict[str, int]] = {}
    for row in rows:
        data = dict(row)
        grouped.setdefault(str(data["plan_code"]), {})[str(data["term_code"])] = int(data["price_uzs"])
    return grouped


@router.get("/staff/speaking/subscription-prices")
async def get_speaking_subscription_prices(authorization: str | None = Header(default=None)):
    _speaking_admin(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        return {"prices": _price_matrix(cur), "terms": TERMS}
    finally:
        cur.close()
        conn.close()


@router.put("/staff/speaking/subscription-prices")
async def update_speaking_subscription_prices(payload: SubscriptionPriceMatrix, authorization: str | None = Header(default=None)):
    admin = _speaking_admin(authorization)
    ensure_tables()
    expected_plans = set(PLANS)
    expected_terms = set(TERMS)
    if set(payload.prices) != expected_plans:
        raise HTTPException(status_code=422, detail={"code": "invalid_plan_codes"})
    for plan_code, terms in payload.prices.items():
        if set(terms) != expected_terms or any(isinstance(price, bool) or price < 0 or price > 100_000_000 for price in terms.values()):
            raise HTTPException(status_code=422, detail={"code": "invalid_subscription_prices", "plan_code": plan_code})
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("speaking-subscription-prices",))
        for plan_code, terms in payload.prices.items():
            for term_code, price in terms.items():
                cur.execute(
                    """INSERT INTO speaking_subscription_prices(plan_code,term_code,price_uzs,updated_by,updated_at)
                       VALUES(%s,%s,%s,%s,NOW()) ON CONFLICT(plan_code,term_code) DO UPDATE
                       SET price_uzs=EXCLUDED.price_uzs,updated_by=EXCLUDED.updated_by,updated_at=NOW()""",
                    (plan_code, term_code, int(price), int(admin.get("id") or 0)),
                )
        conn.commit()
        cur.execute("SELECT plan_code,term_code,price_uzs FROM speaking_subscription_prices ORDER BY plan_code,term_code")
        return {"prices": _group_prices(cur.fetchall())}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _speaking_admin(authorization: str | None) -> dict[str, Any]:
    from backend.main import _is_speaking_admin_account

    user = _user(authorization)
    if not _is_speaking_admin_account(user):
        raise HTTPException(status_code=403, detail="Speaking administrator access required")
    return user


@router.get("/staff/speaking/subscription-requests")
async def list_speaking_subscription_requests(status: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"), authorization: str | None = Header(default=None)):
    _speaking_admin(authorization)
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        where = "" if status == "all" else "WHERE r.status=%s"
        params: tuple[Any, ...] = () if status == "all" else (status,)
        cur.execute(
            f"""SELECT r.id,r.user_id,r.plan_code,r.term_code,r.amount_uzs,r.status,r.review_note,r.created_at,r.reviewed_at,
                       COALESCE(u.login_id,'') AS login_id,COALESCE(u.first_name,'') AS first_name,
                       COALESCE(u.last_name,'') AS last_name,COALESCE(c.email,'') AS email
                FROM speaking_subscription_requests r LEFT JOIN users u ON u.id=r.user_id
                LEFT JOIN speaking_account_contacts c ON c.user_id=r.user_id {where}
                ORDER BY r.created_at DESC LIMIT 300""",
            params,
        )
        return {"items": [dict(row) for row in cur.fetchall()]}
    finally:
        cur.close()
        conn.close()


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = Field(default="", max_length=500)


@router.post("/staff/speaking/subscription-requests/{request_id}/review")
async def review_speaking_subscription_request(request_id: int, payload: ReviewRequest, authorization: str | None = Header(default=None)):
    admin = _speaking_admin(authorization)
    if request_id <= 0:
        raise HTTPException(status_code=404, detail="Request not found")
    ensure_tables()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM speaking_subscription_requests WHERE id=%s FOR UPDATE", (request_id,))
        request = dict(cur.fetchone() or {})
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")
        if request["status"] != "pending":
            raise HTTPException(status_code=409, detail="Request has already been reviewed")
        decision = "approved" if payload.decision == "approve" else "rejected"
        cur.execute("UPDATE speaking_subscription_requests SET status=%s,reviewed_by=%s,review_note=%s,reviewed_at=NOW() WHERE id=%s", (decision, int(admin.get("id") or 0), payload.note.strip(), request_id))
        if decision == "approved":
            days = int(TERMS[str(request["term_code"])] ["days"])
            cur.execute(
                """INSERT INTO speaking_user_subscriptions(user_id,plan_code,starts_at,expires_at,status,approved_by)
                   SELECT %s,%s,starts_at,starts_at+(%s * INTERVAL '1 day'),'active',%s
                   FROM (SELECT GREATEST(NOW(),COALESCE(MAX(expires_at),NOW())) AS starts_at
                         FROM speaking_user_subscriptions WHERE user_id=%s AND status='active' AND expires_at>NOW()) current_plan
                   RETURNING id,expires_at""",
                (int(request["user_id"]), str(request["plan_code"]), days, int(admin.get("id") or 0), int(request["user_id"])),
            )
            subscription = dict(cur.fetchone())
        else:
            subscription = None
        conn.commit()
        return {"request_id": request_id, "status": decision, "subscription": subscription}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
