from pathlib import Path
from datetime import datetime, timedelta, timezone


ROOT = Path(__file__).resolve().parents[1]


def test_speaking_subscription_prices_are_admin_managed_and_persisted():
    source = (ROOT / "backend" / "speaking_subscriptions.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS speaking_subscription_prices" in source
    assert '@router.get("/staff/speaking/subscription-prices")' in source
    assert '@router.put("/staff/speaking/subscription-prices")' in source
    request = source.split("async def create_speaking_subscription_request", 1)[1].split(
        "class SubscriptionPriceMatrix", 1
    )[0]
    assert "SELECT price_uzs FROM speaking_subscription_prices" in request
    assert 'PLANS[payload.plan_code]["prices"]' not in request


def test_subscription_requests_are_numeric_id_based_and_repeat_safe():
    backend = (ROOT / "backend" / "speaking_subscriptions.py").read_text(encoding="utf-8")
    assert "id BIGSERIAL PRIMARY KEY" in backend
    assert "uq_speaking_subscription_pending_user" in backend
    request = backend.split("async def create_speaking_subscription_request", 1)[1].split(
        "class SubscriptionPriceMatrix", 1
    )[0]
    assert '"duplicate": True' in request
    assert '"request": dict(existing)' in request
    assert "pg_advisory_xact_lock" in request


def test_speaking_admin_ui_displays_request_id_and_edits_prices():
    ui = (ROOT / "app" / "ui" / "admin-speaking-subscriptions.tsx").read_text(encoding="utf-8")
    assert "subscription-prices" in ui
    assert 'method: "PUT"' in ui
    assert "So‘rov #{item.id}" in ui


def test_speaking_subscription_and_usage_are_partitioned_by_product():
    backend = (ROOT / "backend" / "speaking_subscriptions.py").read_text(encoding="utf-8")
    assert 'ContextVar("speaking_product_code", default="english")' in backend
    assert "PRIMARY KEY(product_code, plan_code, term_code)" in backend
    assert "PRIMARY KEY(user_id, product_code, feature, window_key)" in backend
    assert "PRIMARY KEY(user_id, product_code, feature, session_key)" in backend
    assert "WHERE user_id=%s AND product_code=%s AND status='active'" in backend
    assert "WHERE user_id=%s AND product_code=%s AND status='pending'" in backend
    assert 'Field(default="english", pattern="^(english|russian)$")' in backend


def test_subscription_price_admin_can_filter_and_edit_each_app_independently():
    backend = (ROOT / "backend" / "speaking_subscriptions.py").read_text(encoding="utf-8")
    ui = (ROOT / "app" / "ui" / "admin-speaking-subscriptions.tsx").read_text(encoding="utf-8")
    assert 'product_code: str = Query(default="english", pattern="^(english|russian)$")' in backend
    assert 'product_code: str = Query(default="all", pattern="^(english|russian|all)$")' in backend
    assert "product_code=${productCode}" in ui
    assert "product_code: productCode" in ui


def test_new_auth_sessions_bind_the_selected_product_to_signed_tokens():
    main = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
    assert 'request.headers.get("X-Speaking-Product")' in main
    assert 'token_payload["speaking_product"] = current_product_code()' in main
    assert 'payload.get("speaking_product")' in main


def test_pro_upgrade_activates_immediately_and_preserves_remaining_paid_time():
    from backend.speaking_subscriptions import _subscription_activation_dates

    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    plus_expires = now + timedelta(days=12)
    starts, expires, upgrading = _subscription_activation_dates(
        "pro",
        [{"plan_code": "plus", "starts_at": now - timedelta(days=2), "expires_at": plus_expires}],
        now,
        30,
    )

    assert upgrading is True
    assert starts == now
    assert expires == plus_expires + timedelta(days=30)


def test_same_tier_renewal_and_downgrade_are_queued_after_current_plan():
    from backend.speaking_subscriptions import _subscription_activation_dates

    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    pro_expires = now + timedelta(days=12)
    existing = [{"plan_code": "pro", "starts_at": now, "expires_at": pro_expires}]

    renew_starts, renew_expires, renew_upgrading = _subscription_activation_dates(
        "pro", existing, now, 30
    )
    downgrade_starts, _, downgrade_upgrading = _subscription_activation_dates(
        "plus", existing, now, 30
    )

    assert renew_upgrading is False
    assert renew_starts == pro_expires
    assert renew_expires == pro_expires + timedelta(days=30)
    assert downgrade_upgrading is False
    assert downgrade_starts == pro_expires


def test_active_plan_prefers_highest_tier_when_legacy_rows_overlap():
    backend = (ROOT / "backend" / "speaking_subscriptions.py").read_text(encoding="utf-8")
    active_plan = backend.split("def active_plan(", 1)[1].split("def entitlement(", 1)[0]
    assert "WHEN 'pro' THEN 2 WHEN 'plus' THEN 1" in active_plan


def test_voice_room_quotas_differ_by_tier_and_student_link_stays_unlimited():
    from backend.speaking_subscriptions import entitlement

    user = {"id": 1, "login_type": 0, "login_id": "speaking-test", "speaking_app_account": True}
    free = entitlement(user, "voice_room", plan_record=None)
    plus = entitlement(user, "voice_room", plan_record={"plan_code": "plus"})
    pro = entitlement(user, "voice_room", plan_record={"plan_code": "pro"})

    assert free["allowed"] is False
    assert (free["daily_limit"], free["weekly_limit"]) == (30, 150)
    assert plus["allowed"] is True
    assert pro["allowed"] is True
    assert (plus["daily_limit"], plus["weekly_limit"]) == (60, 300)
    assert (pro["daily_limit"], pro["weekly_limit"]) == (120, 600)

    linked_student = {"id": 2, "login_type": 1, "login_id": "student-test", "speaking_app_account": False}
    student = entitlement(linked_student, "voice_room", plan_record=None)
    assert student["allowed"] is True
    assert student["daily_limit"] is None
    assert student["weekly_limit"] is None
