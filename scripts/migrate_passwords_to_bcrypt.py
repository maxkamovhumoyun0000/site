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

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, login_id, password FROM users WHERE password IS NOT NULL AND password != '' ORDER BY id")
    rows = cur.fetchall() or []

    total = len(rows)
    already_hashed = 0
    to_migrate: list[tuple[int, str, str]] = []
    for row in rows:
        uid = int(row["id"])
        login_id = str(row["login_id"] or "")
        stored = str(row["password"] or "")
        if is_password_hash(stored):
            already_hashed += 1
        else:
            to_migrate.append((uid, login_id, stored))

    print(f"Foydalanuvchilar (paroli bor): {total}")
    print(f"  Allaqachon bcrypt:           {already_hashed}")
    print(f"  Migratsiya qilinadi:         {len(to_migrate)}")

    if args.dry_run:
        print("\n[DRY RUN] Hech narsa yozilmadi. Haqiqiy migratsiya uchun --dry-run siz ishlating.")
        for uid, login_id, _ in to_migrate[:20]:
            print(f"  - id={uid} login_id={login_id}")
        if len(to_migrate) > 20:
            print(f"  ... va yana {len(to_migrate) - 20} ta")
        conn.close()
        return 0

    done = 0
    errors = 0
    for uid, login_id, stored in to_migrate:
        try:
            cur.execute("UPDATE users SET password=? WHERE id=?", (hash_password(stored), uid))
            done += 1
            if done % args.batch_size == 0:
                conn.commit()
                print(f"  ... {done}/{len(to_migrate)}")
        except Exception as exc:
            conn.rollback()
            errors += 1
            print(f"  XATO id={uid} login_id={login_id}: {exc}")
    conn.commit()
    conn.close()

    print(f"\nTugadi: {done} ta hash'landi, {errors} ta xato.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
