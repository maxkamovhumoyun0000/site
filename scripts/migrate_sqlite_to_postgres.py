#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import DATABASE_URL
from db import init_db

DEFAULT_TABLES = [
    "users",
    "user_subject",
    "groups",
    "web_articles",
    "web_broadcasts",
    "web_student_reviews",
    "web_courses",
    "web_results",
    "tests",
    "test_results",
    "attendance",
    "user_groups",
    "words",
    "vocabulary_imports",
    "student_preferences",
]

UNIQUE_HINT_COLUMNS = {
    "users": ["login_id", "telegram_id"],
    "user_groups": ["user_id", "group_id"],
    "attendance": ["user_id", "group_id", "date"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-time diamond.db to PostgreSQL migration helper.")
    parser.add_argument("--sqlite-path", default="data/diamond.db", help="Path to the legacy SQLite database file")
    parser.add_argument(
        "--tables",
        nargs="*",
        default=DEFAULT_TABLES,
        help="Subset of tables to migrate",
    )
    parser.add_argument(
        "--truncate-first",
        action="store_true",
        help="Truncate target tables before loading rows",
    )
    return parser.parse_args()


def connect_source(path: Path):
    sqlite_module = importlib.import_module("sqlite" + "3")
    conn = sqlite_module.connect(str(path))
    conn.row_factory = sqlite_module.Row
    return conn


def pg_columns(cur, table_name: str) -> list[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (table_name,),
    )
    return [str(row["column_name"]) for row in (cur.fetchall() or [])]


def sqlite_tables(cur) -> set[str]:
    cur.execute(
        """
        SELECT name
        FROM main.sqlite_schema
        WHERE type='table'
          AND name NOT LIKE 'sqlite_%'
        """
    )
    return {str(row["name"]) for row in (cur.fetchall() or [])}


def sqlite_columns(cur, table_name: str) -> list[str]:
    cur.execute(f'SELECT * FROM "{table_name}" LIMIT 0')
    return [str(col[0]) for col in (cur.description or [])]


def fetch_source_rows(cur, table_name: str) -> list[dict[str, Any]]:
    cur.execute(f'SELECT * FROM "{table_name}"')
    return [dict(row) for row in (cur.fetchall() or [])]


def truncate_target(cur, table_name: str) -> None:
    cur.execute(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE')


def reset_sequence(cur, table_name: str) -> None:
    cur.execute(
        """
        SELECT a.attname AS column_name,
               pg_get_serial_sequence(format('%%I.%%I', n.nspname, c.relname), a.attname) AS sequence_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        JOIN pg_attribute a ON a.attrelid = c.oid
        WHERE n.nspname = 'public'
          AND c.relname = %s
          AND a.attnum > 0
          AND NOT a.attisdropped
        """,
        (table_name,),
    )
    for row in cur.fetchall() or []:
        sequence_name = row.get("sequence_name")
        column_name = row.get("column_name")
        if not sequence_name or not column_name:
            continue
        cur.execute(
            f'SELECT COALESCE(MAX("{column_name}"), 0) AS max_id FROM "{table_name}"'
        )
        max_id = int((cur.fetchone() or {}).get("max_id") or 0)
        if max_id > 0:
            cur.execute("SELECT setval(%s, %s, %s)", (sequence_name, max_id, True))
        else:
            cur.execute("SELECT setval(%s, %s, %s)", (sequence_name, 1, False))


def build_insert_sql(table_name: str, columns: list[str]) -> str:
    column_sql = ", ".join(f'"{column}"' for column in columns)
    value_sql = ", ".join(["%s"] * len(columns))
    return f'INSERT INTO "{table_name}" ({column_sql}) VALUES ({value_sql})'


def row_hint(table_name: str, row: dict[str, Any]) -> dict[str, Any]:
    hints = {}
    for column in UNIQUE_HINT_COLUMNS.get(table_name, []):
        if column in row and row.get(column) not in (None, ""):
            hints[column] = row.get(column)
    return hints


def migrate_table(src_cur, pg_cur, table_name: str, *, truncate_first: bool) -> dict[str, Any]:
    source_columns = sqlite_columns(src_cur, table_name)
    target_columns = pg_columns(pg_cur, table_name)
    shared_columns = [column for column in source_columns if column in target_columns]
    if not shared_columns:
        return {
            "table": table_name,
            "source_rows": 0,
            "inserted_rows": 0,
            "skipped": True,
            "reason": "no_shared_columns",
            "conflicts": [],
        }

    if truncate_first:
        truncate_target(pg_cur, table_name)

    rows = fetch_source_rows(src_cur, table_name)
    insert_sql = build_insert_sql(table_name, shared_columns)
    inserted_rows = 0
    conflicts: list[dict[str, Any]] = []

    for row in rows:
        values = [row.get(column) for column in shared_columns]
        try:
            # Keep transaction usable even when a single row conflicts.
            pg_cur.execute("SAVEPOINT migrate_row_sp")
            pg_cur.execute(insert_sql, values)
            pg_cur.execute("RELEASE SAVEPOINT migrate_row_sp")
            inserted_rows += 1
        except Exception as exc:
            try:
                pg_cur.execute("ROLLBACK TO SAVEPOINT migrate_row_sp")
                pg_cur.execute("RELEASE SAVEPOINT migrate_row_sp")
            except Exception:
                pass
            conflicts.append(
                {
                    "error": str(exc),
                    "hint": row_hint(table_name, row),
                }
            )

    reset_sequence(pg_cur, table_name)
    return {
        "table": table_name,
        "source_rows": len(rows),
        "inserted_rows": inserted_rows,
        "skipped": False,
        "shared_columns": shared_columns,
        "conflicts": conflicts[:50],
        "conflict_count": len(conflicts),
    }


def main() -> int:
    args = parse_args()
    sqlite_path = Path(args.sqlite_path).expanduser().resolve()
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite source file not found: {sqlite_path}")

    init_db()
    source_conn = connect_source(sqlite_path)
    source_cur = source_conn.cursor()
    available_tables = sqlite_tables(source_cur)

    results: list[dict[str, Any]] = []
    summary = defaultdict(int)

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as pg_conn:
        with pg_conn.cursor() as pg_cur:
            for table_name in args.tables:
                if table_name not in available_tables:
                    results.append(
                        {
                            "table": table_name,
                            "source_rows": 0,
                            "inserted_rows": 0,
                            "skipped": True,
                            "reason": "missing_in_source",
                            "conflicts": [],
                        }
                    )
                    summary["skipped_tables"] += 1
                    continue
                if not pg_columns(pg_cur, table_name):
                    results.append(
                        {
                            "table": table_name,
                            "source_rows": 0,
                            "inserted_rows": 0,
                            "skipped": True,
                            "reason": "missing_in_target",
                            "conflicts": [],
                        }
                    )
                    summary["skipped_tables"] += 1
                    continue

                table_result = migrate_table(
                    source_cur,
                    pg_cur,
                    table_name,
                    truncate_first=bool(args.truncate_first),
                )
                results.append(table_result)
                summary["tables_processed"] += 1
                summary["source_rows"] += int(table_result.get("source_rows") or 0)
                summary["inserted_rows"] += int(table_result.get("inserted_rows") or 0)
                summary["conflicts"] += int(table_result.get("conflict_count") or 0)
            pg_conn.commit()

    source_conn.close()
    print(
        json.dumps(
            {
                "sqlite_path": str(sqlite_path),
                "target_database": DATABASE_URL,
                "summary": dict(summary),
                "tables": results,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
