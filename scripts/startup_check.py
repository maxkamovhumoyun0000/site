#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import DATABASE_URL
from db import get_conn


def run_check() -> dict:
    checks: list[dict] = []
    url_ok = bool(str(DATABASE_URL or "").strip())
    checks.append({"name": "database_url_present", "ok": url_ok})
    conn_ok = False
    table_ok = False
    required_tables = [
        "users",
        "groups",
        "user_subject",
        "web_articles",
        "web_broadcasts",
        "web_student_reviews",
        "web_courses",
        "web_results",
    ]
    found: set[str] = set()
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1 AS ok")
        _ = cur.fetchone()
        conn_ok = True
        checks.append({"name": "database_connection", "ok": True})
        for table in required_tables:
            try:
                if str(DATABASE_URL or "").strip().lower().startswith(('postgresql://', 'postgres://')):
                    # PostgreSQL
                    cur.execute(
                        "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name=? LIMIT 1",
                        (table,),
                    )
                else:
                    # SQLite
                    cur.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                        (table,),
                    )
                row = cur.fetchone()
                if row:
                    found.add(table)
            except Exception:
                continue
        conn.close()
        table_ok = len(found) == len(required_tables)
    except Exception as exc:
        checks.append({"name": "database_connection", "ok": False, "error": str(exc)})
    checks.append({"name": "required_tables", "ok": table_ok, "found": sorted(found), "required": required_tables})
    return {
        "ok": bool(url_ok and conn_ok and table_ok),
        "database_url": str(DATABASE_URL or ""),
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    report = run_check()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if bool(report.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
