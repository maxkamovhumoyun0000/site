#!/usr/bin/env python3
"""Set stable browser credentials for every admin configured in root .env."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import set_standard_admin_account_credentials


def main() -> int:
    try:
        rows = set_standard_admin_account_credentials()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1
    if not rows:
        print("No admin IDs configured.")
        return 0

    # Never print passwords: stdout ends up in terminal scrollback and SSH/CI
    # logs. The passwords come from .env, where the operator already has them.
    print("Standard admin website credentials set:")
    for row in rows:
        role = "MainAdmin" if row.get("role_label") == "main_admin" else "LimitedAdmin"
        print(f"{role} | tg:{row.get('telegram_id')} | login:{row.get('login_id')} | pass:(from .env, not shown)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
