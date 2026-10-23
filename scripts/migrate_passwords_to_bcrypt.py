#!/usr/bin/env python3
"""Migrate legacy plaintext user passwords to bcrypt hashes.

Safe to run multiple times (idempotent): rows whose password already looks
like a bcrypt hash are skipped, and empty passwords (accountless students)
are left untouched — logins still work during migration because
passwords.verify_password accepts both forms.

Usage:
    python scripts/migrate_passwords_to_bcrypt.py --dry-run   # faqat hisobot
    python scripts/migrate_passwords_to_bcrypt.py             # haqiqiy migratsiya
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db import get_conn  # noqa: E402
from passwords import hash_password, is_password_hash  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash legacy plaintext passwords with bcrypt")
    parser.add_argument("--dry-run", action="store_true", help="faqat ko'rsatadi, yozmaydi")
    parser.add_argument("--batch-size", type=int, default=100, help="har bir UPDATE oldin nechta qator (default 100)")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size kamida 1 bo'lishi kerak")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, login_id, password FROM users WHERE password IS NOT NULL AND password != '' ORDER BY id")
    rows = cur.fetchall() or []

    total = len(rows)
    already_hashed = 0
    to_migrate: list[tuple[int, str]] = []
    for row in rows:
        uid = int(row["id"])
        stored = str(row["password"] or "")
        if is_password_hash(stored):
            already_hashed += 1
        else:
            to_migrate.append((uid, stored))

    print(f"Foydalanuvchilar (paroli bor): {total}")
    print(f"  Allaqachon bcrypt:           {already_hashed}")
    print(f"  Migratsiya qilinadi:         {len(to_migrate)}")

    if args.dry_run:
        print("\n[DRY RUN] Hech narsa yozilmadi. Haqiqiy migratsiya uchun --dry-run siz ishlating.")
        conn.close()
        return 0

    done = 0
    errors = 0
    for uid, stored in to_migrate:
        try:
            # Legacy authentication intentionally compared passwords without
            # case sensitivity. Hash the normalized value so that migration
            # preserves that long-standing login behavior.
            cur.execute(
                "UPDATE users SET password=? WHERE id=? AND password=?",
                (hash_password(stored.strip().upper()), uid, stored),
            )
            done += int(getattr(cur, "rowcount", 0) == 1)
            if done % args.batch_size == 0:
                conn.commit()
                print(f"  ... {done}/{len(to_migrate)}")
        except Exception as exc:
            conn.rollback()
            errors += 1
            print(f"  XATO id={uid} type={type(exc).__name__}")
    conn.commit()
    conn.close()

    print(f"\nTugadi: {done} ta hash'landi, {errors} ta xato.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
