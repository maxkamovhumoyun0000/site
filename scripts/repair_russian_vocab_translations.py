"""Repair legacy Russian vocabulary rows whose Uzbek translation is a placeholder.

Run from the project root with configured Grok credentials. The job is
resumable: a successful row no longer matches the query, so a later run safely
continues with the remaining rows.
"""

import argparse
import asyncio

import ai_generator
from db import get_conn


def _pending_rows(limit: int) -> list[dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, word, level, translation_uz, translation_ru, definition, example
            FROM words
            WHERE LOWER(subject)=LOWER(?)
              AND LOWER(TRIM(COALESCE(translation_uz, ''))) LIKE ?
            ORDER BY id
            LIMIT ?
            """,
            ("Russian", "% so'zi", int(limit)),
        )
        return [dict(row) for row in (cur.fetchall() or [])]
    finally:
        conn.close()


async def _repair(limit: int, batch_size: int, dry_run: bool) -> tuple[int, int]:
    rows = _pending_rows(limit)
    repaired = 0
    skipped = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        by_level: dict[str, list[dict]] = {}
        for row in batch:
            level = ai_generator._normalize_russian_bank_level(
                str(row.get("level") or ""), "MIXED"
            )
            by_level.setdefault(level, []).append(row)
        updates: list[tuple[str, int]] = []
        for level, level_rows in by_level.items():
            enriched = await ai_generator._enrich_and_repair_vocab_items(
                "Russian", level, level_rows
            )
            for item in enriched:
                translation = str(item.get("translation_uz") or "").strip()
                if ai_generator._is_placeholder_uz_translation(translation):
                    skipped += 1
                    continue
                updates.append((translation, int(item["id"])))
        if dry_run:
            repaired += len(updates)
            continue
        if updates:
            conn = get_conn()
            try:
                cur = conn.cursor()
                cur.executemany(
                    "UPDATE words SET translation_uz=? WHERE id=?",
                    updates,
                )
                conn.commit()
                repaired += len(updates)
            finally:
                conn.close()
        print(
            f"batch={start // batch_size + 1} attempted={len(batch)} "
            f"repaired={repaired} skipped={skipped}",
            flush=True,
        )
    return repaired, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=35)
    parser.add_argument("--batch-size", type=int, default=35)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    limit = max(1, min(5000, int(args.limit)))
    batch_size = max(1, min(35, int(args.batch_size)))
    repaired, skipped = asyncio.run(_repair(limit, batch_size, args.dry_run))
    print(f"done repaired={repaired} skipped={skipped}")


if __name__ == "__main__":
    main()
