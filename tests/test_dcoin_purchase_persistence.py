from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

os.environ["REQUIRE_POSTGRES"] = "false"
os.environ["DATABASE_URL"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = lambda cursor, row: {
        column[0]: row[index] for index, column in enumerate(cursor.description or [])
    }
    return conn


def _seed_wallet_schema(path: Path) -> None:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            login_type INTEGER NOT NULL DEFAULT 1,
            subject TEXT
        )
        """
    )
    cur.execute("CREATE TABLE groups (id INTEGER PRIMARY KEY, subject TEXT)")
    cur.execute("CREATE TABLE user_groups (user_id INTEGER, group_id INTEGER)")
    cur.execute(
        """
        CREATE TABLE diamond_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            dcoin_change DOUBLE PRECISION NOT NULL,
            dpoints_change DOUBLE PRECISION,
            subject TEXT,
            created_at TIMESTAMP,
            change_type TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE user_dpoints (
            user_id INTEGER PRIMARY KEY,
            dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
            dcoin_floor DOUBLE PRECISION NOT NULL DEFAULT 0,
            dcoin_anchor_value DOUBLE PRECISION,
            dcoin_anchor_dpoints DOUBLE PRECISION,
            updated_at TIMESTAMP
        )
        """
    )
    cur.execute("INSERT INTO users (id, login_type, subject) VALUES (1, 1, 'English,Russian')")
    cur.execute("INSERT INTO user_dpoints (user_id, dpoints, updated_at) VALUES (1, 200, CURRENT_TIMESTAMP)")
    conn.commit()
    conn.close()


def _seed_proctoring_penalty_schema(path: Path) -> None:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            login_type INTEGER NOT NULL DEFAULT 1,
            subject TEXT,
            face_total_violations INTEGER DEFAULT 0,
            face_last_violation_at TIMESTAMP
        )
        """
    )
    cur.execute("CREATE TABLE groups (id INTEGER PRIMARY KEY, subject TEXT)")
    cur.execute("CREATE TABLE user_groups (user_id INTEGER, group_id INTEGER)")
    cur.execute(
        """
        CREATE TABLE user_dpoints (
            user_id INTEGER PRIMARY KEY,
            dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
            dcoin_floor DOUBLE PRECISION NOT NULL DEFAULT 0,
            dcoin_anchor_value DOUBLE PRECISION,
            dcoin_anchor_dpoints DOUBLE PRECISION,
            updated_at TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE diamond_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            dcoin_change DOUBLE PRECISION NOT NULL,
            dpoints_change DOUBLE PRECISION,
            subject TEXT,
            created_at TIMESTAMP,
            change_type TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE test_proctoring_sessions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            penalty_applied INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE proctoring_penalties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            proctoring_session_id INTEGER,
            test_type TEXT,
            penalty_rule TEXT,
            penalty_percent DOUBLE PRECISION,
            penalty_amount DOUBLE PRECISION,
            details_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("INSERT INTO users (id, login_type, subject) VALUES (1, 1, 'English,Russian')")
    cur.execute("INSERT INTO user_dpoints (user_id, dpoints, updated_at) VALUES (1, 100, CURRENT_TIMESTAMP)")
    cur.execute("INSERT INTO test_proctoring_sessions (id, user_id, penalty_applied) VALUES (10, 1, 0)")
    conn.commit()
    conn.close()


def _seed_commerce_schema(path: Path) -> None:
    conn = _connect(path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            login_type INTEGER NOT NULL DEFAULT 1,
            subject TEXT,
            face_total_violations INTEGER DEFAULT 0,
            face_last_violation_at TIMESTAMP
        )
        """
    )
    cur.execute("CREATE TABLE groups (id INTEGER PRIMARY KEY, subject TEXT)")
    cur.execute("CREATE TABLE user_groups (user_id INTEGER, group_id INTEGER)")
    cur.execute(
        """
        CREATE TABLE user_dpoints (
            user_id INTEGER PRIMARY KEY,
            dpoints DOUBLE PRECISION NOT NULL DEFAULT 0,
            dcoin_floor DOUBLE PRECISION NOT NULL DEFAULT 0,
            dcoin_anchor_value DOUBLE PRECISION,
            dcoin_anchor_dpoints DOUBLE PRECISION,
            updated_at TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE diamond_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            dcoin_change DOUBLE PRECISION NOT NULL,
            dpoints_change DOUBLE PRECISION,
            subject TEXT,
            created_at TIMESTAMP,
            change_type TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE books (
            id INTEGER PRIMARY KEY,
            title TEXT,
            purchase_count INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE student_book_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deadline_at TIMESTAMP,
            status TEXT DEFAULT 'active',
            UNIQUE(user_id, book_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE web_gifts (
            id INTEGER PRIMARY KEY,
            title TEXT,
            image_url TEXT,
            price_dcoin DOUBLE PRECISION DEFAULT 0,
            required_tickets INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE web_gift_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_id INTEGER NOT NULL,
            ticket_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, gift_id)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE web_gift_chest_spins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            winner_gift_id INTEGER,
            cost_dcoin DOUBLE PRECISION DEFAULT 0,
            awarded_tickets INTEGER DEFAULT 0,
            roulette_payload_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE web_purchase_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_id INTEGER,
            item_type TEXT NOT NULL,
            item_title TEXT,
            amount_spent DOUBLE PRECISION NOT NULL DEFAULT 0,
            balance_before DOUBLE PRECISION,
            balance_after DOUBLE PRECISION,
            source_page TEXT,
            meta_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute("INSERT INTO users (id, login_type, subject) VALUES (1, 1, 'English,Russian')")
    cur.execute("INSERT INTO users (id, login_type, subject) VALUES (2, 1, 'English')")
    cur.execute("INSERT INTO user_dpoints (user_id, dpoints, updated_at) VALUES (1, 200, CURRENT_TIMESTAMP)")
    cur.execute("INSERT INTO user_dpoints (user_id, dpoints, updated_at) VALUES (2, 10, CURRENT_TIMESTAMP)")
    cur.execute("INSERT INTO books (id, title, purchase_count) VALUES (7, 'Atomic Book', 0)")
    cur.execute("INSERT INTO web_gifts (id, title, price_dcoin, required_tickets, active) VALUES (9, 'Atomic Gift', 30, 3, 1)")
    conn.commit()
    conn.close()


def test_dcoin_purchase_does_not_snap_back_after_refetch_or_dpoint_award(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "wallet.db"
    _seed_wallet_schema(db_path)

    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))
    monkeypatch.setattr(db, "_is_postgres_enabled", lambda: False)

    assert db.get_user_subject_count(1) == 2
    assert db.get_dcoins(1) == 100.0

    assert db.try_consume_dcoins(1, 30.0, "English", change_type="book_purchase") is True

    after_purchase = db.get_dcoins(1)
    assert after_purchase == 70.0
    assert db.get_dcoins(1) == after_purchase

    db.add_dpoints(1, 20.0, subject="English", change_type="quiz_result")

    # The wallet can grow only by newly earned D'points / subject_count.
    # It must not jump back to the pre-purchase 100 D'coin balance.
    assert db.get_dcoins(1) == 80.0


def test_proctoring_penalty_is_idempotent_for_duplicate_failure_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "proctoring.db"
    _seed_proctoring_penalty_schema(db_path)

    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))
    monkeypatch.setattr(db, "_is_postgres_enabled", lambda: False)
    monkeypatch.setattr(db, "_ensure_proctoring_schema_runtime", lambda: None)
    monkeypatch.setattr(db, "ensure_dpoints_schema", lambda: True)

    assert db.apply_proctoring_penalty(
        1,
        10,
        test_type="daily",
        penalty_rule="face_missing_timeout",
        penalty_amount=25,
    ) is True
    assert db.apply_proctoring_penalty(
        1,
        10,
        test_type="daily",
        penalty_rule="face_missing_timeout",
        penalty_amount=25,
    ) is False

    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=1")
        assert float(cur.fetchone()["dpoints"]) == 75.0
        cur.execute("SELECT COUNT(*) AS count FROM proctoring_penalties")
        assert int(cur.fetchone()["count"]) == 1
        cur.execute("SELECT COUNT(*) AS count FROM diamond_history WHERE change_type='proctoring_max_penalty'")
        assert int(cur.fetchone()["count"]) == 1
        cur.execute("SELECT penalty_applied FROM test_proctoring_sessions WHERE id=10")
        assert int(cur.fetchone()["penalty_applied"]) == 1
    finally:
        conn.close()


def test_book_purchase_is_atomic_and_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "commerce.db"
    _seed_commerce_schema(db_path)

    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))
    monkeypatch.setattr(db, "_is_postgres_enabled", lambda: False)
    monkeypatch.setattr(db, "ensure_dpoints_schema", lambda: True)
    monkeypatch.setattr(db, "ensure_purchase_history_schema", lambda: None)

    first = db.purchase_book_with_dcoins(
        user_id=1,
        book_id=7,
        price_dcoin=30,
        deadline_at="2026-05-20T00:00:00+00:00",
        book_title="Atomic Book",
        deadline_days=7,
    )
    second = db.purchase_book_with_dcoins(
        user_id=1,
        book_id=7,
        price_dcoin=30,
        deadline_at="2026-05-20T00:00:00+00:00",
        book_title="Atomic Book",
        deadline_days=7,
    )

    assert first["ok"] is True
    assert first["already_purchased"] is False
    assert second["ok"] is True
    assert second["already_purchased"] is True

    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=1")
        assert float(cur.fetchone()["dpoints"]) == 140.0
        cur.execute("SELECT purchase_count FROM books WHERE id=7")
        assert int(cur.fetchone()["purchase_count"]) == 1
        cur.execute("SELECT COUNT(*) AS count FROM student_book_purchases")
        assert int(cur.fetchone()["count"]) == 1
        cur.execute("SELECT COUNT(*) AS count FROM web_purchase_history WHERE item_type='book'")
        assert int(cur.fetchone()["count"]) == 1
    finally:
        conn.close()


def test_gift_chest_charge_and_ticket_award_are_atomic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "gift.db"
    _seed_commerce_schema(db_path)

    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))
    monkeypatch.setattr(db, "_is_postgres_enabled", lambda: False)
    monkeypatch.setattr(db, "ensure_dpoints_schema", lambda: True)
    monkeypatch.setattr(db, "ensure_gifts_schema", lambda: None)
    monkeypatch.setattr(db, "ensure_purchase_history_schema", lambda: None)

    result = db.open_gift_chest_atomic(
        user_id=1,
        winner_gift_id=9,
        winner_title="Atomic Gift",
        cost_dcoin=40,
        awarded_tickets=1,
        roulette_payload_json="{}",
    )

    assert result["ok"] is True
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=1")
        assert float(cur.fetchone()["dpoints"]) == 120.0
        cur.execute("SELECT ticket_count FROM web_gift_tickets WHERE user_id=1 AND gift_id=9")
        assert int(cur.fetchone()["ticket_count"]) == 1
        cur.execute("SELECT COUNT(*) AS count FROM web_gift_chest_spins")
        assert int(cur.fetchone()["count"]) == 1
        cur.execute("SELECT COUNT(*) AS count FROM web_purchase_history WHERE item_type='chest'")
        assert int(cur.fetchone()["count"]) == 1
    finally:
        conn.close()


def test_gift_purchase_requires_tickets_and_charges_dcoin_once(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "gift_purchase.db"
    _seed_commerce_schema(db_path)

    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))
    monkeypatch.setattr(db, "_is_postgres_enabled", lambda: False)
    monkeypatch.setattr(db, "ensure_dpoints_schema", lambda: True)
    monkeypatch.setattr(db, "ensure_gifts_schema", lambda: None)
    monkeypatch.setattr(db, "ensure_purchase_history_schema", lambda: None)

    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO web_gift_tickets (user_id, gift_id, ticket_count) VALUES (1, 9, 3)")
        conn.commit()
    finally:
        conn.close()

    result = db.purchase_gift_with_tickets_atomic(user_id=1, gift_id=9)

    assert result["ok"] is True
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=1")
        assert float(cur.fetchone()["dpoints"]) == 140.0
        cur.execute("SELECT ticket_count FROM web_gift_tickets WHERE user_id=1 AND gift_id=9")
        assert int(cur.fetchone()["ticket_count"]) == 0
        cur.execute("SELECT COUNT(*) AS count FROM web_purchase_history WHERE item_type='gift'")
        assert int(cur.fetchone()["count"]) == 1
    finally:
        conn.close()

    second = db.purchase_gift_with_tickets_atomic(user_id=1, gift_id=9)
    assert second["ok"] is False
    assert second["reason"] == "insufficient_tickets"


def test_transfer_uses_global_wallet_and_checks_recipient(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "transfer.db"
    _seed_commerce_schema(db_path)

    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))
    monkeypatch.setattr(db, "_is_postgres_enabled", lambda: False)
    monkeypatch.setattr(db, "ensure_dpoints_schema", lambda: True)

    missing = db.transfer_dcoins_atomic(sender_id=1, recipient_id=99, amount=10, subject="English")
    assert missing["ok"] is False
    assert missing["reason"] == "user_not_found"

    result = db.transfer_dcoins_atomic(sender_id=1, recipient_id=2, amount=25, subject="English")
    assert result["ok"] is True

    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=1")
        assert float(cur.fetchone()["dpoints"]) == 150.0
        cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=2")
        assert float(cur.fetchone()["dpoints"]) == 35.0
        cur.execute("SELECT COUNT(*) AS count FROM diamond_history WHERE change_type='transfer_out'")
        assert int(cur.fetchone()["count"]) == 1
        cur.execute("SELECT COUNT(*) AS count FROM diamond_history WHERE change_type='transfer_in'")
        assert int(cur.fetchone()["count"]) == 1
    finally:
        conn.close()


def test_wallet_tx_helpers_roll_back_with_parent_transaction(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "wallet_tx.db"
    _seed_commerce_schema(db_path)

    monkeypatch.setattr(db, "get_conn", lambda: _connect(db_path))
    monkeypatch.setattr(db, "_is_postgres_enabled", lambda: False)
    monkeypatch.setattr(db, "ensure_dpoints_schema", lambda: True)

    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("BEGIN")
        assert db.add_dpoints_tx(cur, 1, 40.0, subject="English", change_type="payment_bonus") is True
        assert db.add_dcoins_tx(cur, 1, -10.0, subject="English", change_type="payment_penalty") is True
        conn.rollback()
    finally:
        conn.close()

    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT dpoints FROM user_dpoints WHERE user_id=1")
        assert float(cur.fetchone()["dpoints"]) == 200.0
        cur.execute("SELECT COUNT(*) AS count FROM diamond_history")
        assert int(cur.fetchone()["count"]) == 0
    finally:
        conn.close()
