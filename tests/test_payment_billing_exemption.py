import sqlite3

import backend.main as api
import payment


class _Conn:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return self._conn.cursor()

    def close(self):
        self._conn.close()


def _db_with_exemption():
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.execute(
        "CREATE TABLE payment_billing_exempt_months(ym TEXT PRIMARY KEY, reason TEXT NOT NULL)"
    )
    raw.execute(
        "INSERT INTO payment_billing_exempt_months(ym, reason) VALUES (?, ?)",
        ("2026-10", "reset test"),
    )
    return _Conn(raw)


def test_month_exemption_only_matches_configured_month():
    conn = _db_with_exemption()
    cur = conn.cursor()

    assert payment._is_billing_exempt_month(cur, "2026-10")
    assert not payment._is_billing_exempt_month(cur, "2026-11")
    conn.close()


def test_main_billing_exemption_reads_configured_reason(monkeypatch):
    monkeypatch.setattr(api, "get_conn", _db_with_exemption)

    assert api._payment_billing_exemption("2026-10") == {
        "ym": "2026-10",
        "reason": "reset test",
    }
    assert api._payment_billing_exemption("2026-11") == {}


def test_exempt_obligation_refresh_clears_amounts_and_prevents_debt():
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.executescript(
        """
        CREATE TABLE payment_billing_exempt_months(ym TEXT PRIMARY KEY, reason TEXT NOT NULL);
        INSERT INTO payment_billing_exempt_months VALUES ('2026-10', 'reset test');
        CREATE TABLE payment_monthly_obligations(
            id INTEGER PRIMARY KEY, ym TEXT, original_amount REAL, discount_type TEXT,
            discount_percent REAL, discount_amount REAL, final_amount REAL, paid_amount REAL,
            debt_amount REAL, overpayment_amount REAL, status TEXT, overdue INTEGER,
            closed_at TEXT, updated_at TEXT
        );
        INSERT INTO payment_monthly_obligations VALUES
            (1, '2026-10', 500000, 'none', 0, 0, 500000, 100000, 400000, 0,
             'Qisman to\u0027langan', 1, NULL, NULL);
        """
    )

    refreshed = payment._refresh_obligation(raw.cursor(), 1)

    assert refreshed["original_amount"] == 0
    assert refreshed["final_amount"] == 0
    assert refreshed["paid_amount"] == 0
    assert refreshed["debt_amount"] == 0
    assert refreshed["overpayment_amount"] == 0
    assert refreshed["status"] == payment.PAYMENT_STATUS_PAID
    assert refreshed["overdue"] == 0
    raw.close()
