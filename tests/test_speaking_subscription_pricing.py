from pathlib import Path


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
