#!/usr/bin/env python3
"""Provision or rotate the single server-authorized screenshot demo account.

Usage (the two credentials are deliberately environment variables so they are
never committed to git):

  SCREENSHOT_DEMO_LOGIN='...' SCREENSHOT_DEMO_PASSWORD='...' \
    .venv/bin/python scripts/provision_screenshot_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The script is executed from ``scripts/``; make the project root importable
# before loading the backend's database/password helpers.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import (
    ensure_screenshot_demo_schema,
    ensure_user_subject_schema,
    get_conn,
)
from passwords import hash_password


def required_env(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def main() -> int:
    login_id = required_env("SCREENSHOT_DEMO_LOGIN")
    password = required_env("SCREENSHOT_DEMO_PASSWORD")
    first_name = (os.getenv("SCREENSHOT_DEMO_FIRST_NAME") or "Xumoyun").strip()
    last_name = (os.getenv("SCREENSHOT_DEMO_LAST_NAME") or "Maxkamov").strip()
    login_type = int((os.getenv("SCREENSHOT_DEMO_LOGIN_TYPE") or "1").strip())
    if login_type not in {1, 2, 3, 4}:
        raise RuntimeError("SCREENSHOT_DEMO_LOGIN_TYPE must be 1, 2, 3, or 4")

    ensure_screenshot_demo_schema()
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM users WHERE UPPER(login_id)=?", (login_id.upper(),))
        existing = cur.fetchone()
        password_hash = hash_password(password)
        if existing:
            user_id = int(existing["id"])
            cur.execute(
                """
                UPDATE users
                SET password=?, first_name=?, last_name=?, subject='English',
                    login_type=?, blocked=0, access_enabled=1, active=1,
                    screenshot_demo=1, failed_logins=0
                WHERE id=?
                """,
                (password_hash, first_name, last_name, login_type, user_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO users
                    (login_id, password, first_name, last_name, subject,
                     login_type, blocked, access_enabled, active, screenshot_demo)
                VALUES (?, ?, ?, ?, 'English', ?, 0, 1, 1, 1)
                RETURNING id
                """,
                (login_id, password_hash, first_name, last_name, login_type),
            )
            row = cur.fetchone()
            user_id = int(row["id"])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    # Seed the normal subject fanout so the account receives the same English
    # library and practice catalogue as a regular student.
    ensure_user_subject_schema()
    print(f"Screenshot demo account is ready (user_id={user_id}).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Provisioning failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
