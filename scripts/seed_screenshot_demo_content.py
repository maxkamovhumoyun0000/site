#!/usr/bin/env python3
"""Seed safe, screenshot-only English content for the authorized demo users.

This script never creates or modifies a real account.  It resolves only rows
that already carry the server-controlled ``screenshot_demo`` flag, gives the
Student demo one English group, and gives the Teacher demo illustrative groups,
students and homework for App Store screenshots.
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import (  # noqa: E402
    add_user_to_group,
    create_group,
    create_homework,
    ensure_homework_schema,
    ensure_screenshot_demo_schema,
    ensure_teacher_content_permissions_schema,
    ensure_user_group_membership_log_schema,
    ensure_user_subject_schema,
    get_conn,
    set_book_upload_permission,
    set_content_test_manage_permission,
    set_daily_test_upload_permission,
    set_screenshot_demo_wallet,
    set_teacher_ai_generation_permission,
    set_video_upload_permission,
    upsert_homework_submission,
)
from passwords import hash_password  # noqa: E402


STUDENT_GROUP = {
    "name": "English A2 · Morning",
    "level": "A2",
    "lesson_date": "Dushanba · Chorshanba · Juma",
    "lesson_start": "09:00",
    "lesson_end": "10:30",
}
TEACHER_GROUPS = (
    STUDENT_GROUP,
    {
        "name": "English B1 · Afternoon",
        "level": "B1",
        "lesson_date": "Seshanba · Payshanba · Shanba",
        "lesson_start": "13:30",
        "lesson_end": "15:00",
    },
    {
        "name": "IELTS Speaking · Evening",
        "level": "B2",
        "lesson_date": "Dushanba · Chorshanba · Juma",
        "lesson_start": "17:30",
        "lesson_end": "19:00",
    },
)
FIXTURE_NAMES = (
    ("Dilnoza", "Karimova"),
    ("Aziz", "Rahimov"),
    ("Malika", "Sodiqova"),
    ("Jasur", "Toshpulatov"),
    ("Madina", "Yusupova"),
    ("Sardor", "Qodirov"),
    ("Shahnoza", "Olimova"),
    ("Bekzod", "Nazarov"),
    ("Zilola", "Ergasheva"),
    ("Kamron", "Mirzayev"),
    ("Sevara", "Abdullayeva"),
    ("Oybek", "Ismoilov"),
    ("Nodira", "Tohirovа"),
    ("Akmal", "Mamatqulov"),
    ("Sabina", "Rasulova"),
    ("Diyor", "Usmonov"),
    ("Farangiz", "Aliyeva"),
    ("Ulugbek", "Xasanov"),
    ("Nigora", "Yuldasheva"),
    ("Temur", "Ochilov"),
    ("Mohira", "Abduqodirova"),
    ("Rustam", "Jalilov"),
    ("Iroda", "Ganiyeva"),
    ("Sherzod", "Norqulov"),
)


def _row_id(row: object) -> int:
    if isinstance(row, dict):
        return int(row.get("id") or 0)
    try:
        return int(row["id"] or 0)  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        return 0


def _find_demo_users() -> tuple[int, int]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id FROM users
            WHERE COALESCE(screenshot_demo, 0)=1
              AND COALESCE(login_type, 0) IN (1, 2)
              -- Fixture students are intentionally locked.  Only the active
              -- screenshot-login is eligible to receive the demo group.
              AND COALESCE(blocked, 0)=0
              AND COALESCE(access_enabled, 0)=1
              AND COALESCE(active, 0)=1
            ORDER BY id DESC
            LIMIT 1
            """
        )
        student_id = _row_id(cur.fetchone())
        cur.execute(
            """
            SELECT id FROM users
            WHERE COALESCE(screenshot_demo, 0)=1
              AND COALESCE(login_type, 0) IN (3, 4)
              AND COALESCE(blocked, 0)=0
              AND COALESCE(access_enabled, 0)=1
              AND COALESCE(active, 0)=1
            ORDER BY id DESC
            LIMIT 1
            """
        )
        teacher_id = _row_id(cur.fetchone())
        if not student_id or not teacher_id:
            raise RuntimeError("Both server-authorized screenshot demo users are required")
        cur.execute(
            """
            UPDATE users
            SET subject='English', level='A2', blocked=0, access_enabled=1,
                active=1, failed_logins=0, public_offer_agreed=1,
                placement_required=0, test_in_progress=0
            WHERE id IN (?, ?)
            """,
            (student_id, teacher_id),
        )
        conn.commit()
        return student_id, teacher_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_group(teacher_id: int, spec: dict[str, str]) -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM groups WHERE teacher_id=? AND name=? ORDER BY id LIMIT 1",
            (teacher_id, spec["name"]),
        )
        group_id = _row_id(cur.fetchone())
        if group_id:
            cur.execute(
                """
                UPDATE groups
                SET level=?, subject='English', lesson_date=?, lesson_start=?,
                    lesson_end=?, tz='Asia/Tashkent', lang='uz'
                WHERE id=?
                """,
                (
                    spec["level"],
                    spec["lesson_date"],
                    spec["lesson_start"],
                    spec["lesson_end"],
                    group_id,
                ),
            )
            conn.commit()
            return group_id
    finally:
        conn.close()
    return int(
        create_group(
            spec["name"],
            teacher_id,
            level=spec["level"],
            subject="English",
            lesson_date=spec["lesson_date"],
            lesson_start=spec["lesson_start"],
            lesson_end=spec["lesson_end"],
            tz="Asia/Tashkent",
            lang="uz",
        )
        or 0
    )


def _ensure_fixture_students() -> list[int]:
    conn = get_conn()
    cur = conn.cursor()
    ids: list[int] = []
    try:
        for index, (first_name, last_name) in enumerate(FIXTURE_NAMES, start=1):
            login_id = f"SCREENSHOT-DEMO-FIXTURE-{index:02d}"
            cur.execute("SELECT id FROM users WHERE UPPER(login_id)=?", (login_id,))
            user_id = _row_id(cur.fetchone())
            if not user_id:
                cur.execute(
                    """
                    INSERT INTO users(
                        login_id, password, first_name, last_name, subject,
                        login_type, blocked, access_enabled, active,
                        screenshot_demo, public_offer_agreed, placement_required
                    ) VALUES (?, ?, ?, ?, 'English', 2, 1, 0, 0, 1, 1, 0)
                    RETURNING id
                    """,
                    (
                        login_id,
                        hash_password(f"fixture-{index}-{random.SystemRandom().randint(100000, 999999)}"),
                        first_name,
                        last_name,
                    ),
                )
                user_id = _row_id(cur.fetchone())
            else:
                cur.execute(
                    """
                    UPDATE users
                    SET first_name=?, last_name=?, subject='English', login_type=2,
                        screenshot_demo=1, blocked=1, access_enabled=0, active=0,
                        public_offer_agreed=1, placement_required=0
                    WHERE id=?
                    """,
                    (first_name, last_name, user_id),
                )
            ids.append(user_id)
        conn.commit()
        return ids
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _restrict_student_to_primary_group(student_id: int, teacher_id: int, group_id: int) -> None:
    """The demo Student must display exactly one illustrative English group."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DELETE FROM user_groups
            WHERE user_id=? AND group_id IN (
                SELECT id FROM groups WHERE teacher_id=? AND id<>?
            )
            """,
            (student_id, teacher_id, group_id),
        )
        cur.execute(
            """
            UPDATE user_group_membership_log SET active=0, left_at=CURRENT_TIMESTAMP
            WHERE user_id=? AND group_id IN (
                SELECT id FROM groups WHERE teacher_id=? AND id<>?
            ) AND COALESCE(active, 1)=1
            """,
            (student_id, teacher_id, group_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _lock_fixture_accounts(ids: list[int]) -> None:
    if not ids:
        return
    conn = get_conn()
    cur = conn.cursor()
    try:
        placeholders = ",".join("?" for _ in ids)
        cur.execute(
            f"UPDATE users SET blocked=1, access_enabled=0, active=0 WHERE id IN ({placeholders})",
            tuple(ids),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _seed_homework(teacher_id: int, groups: list[int], fixtures: list[int]) -> int:
    due = datetime.now(timezone.utc) + timedelta(days=3)
    homework_specs = (
        (
            groups[0],
            "Vocabulary · Travel & transport",
            "Yangi so‘zlarni mashqlar bilan takrorlang va qisqa gaplarda ishlating.",
            "both",
            "screenshot-demo:travel-vocabulary",
        ),
        (
            groups[1],
            "Writing · My ideal weekend",
            "90–120 so‘z bilan dam olish kuningiz haqida yozing.",
            "list",
            "screenshot-demo:ideal-weekend",
        ),
        (
            groups[2],
            "Speaking · IELTS Part 2",
            "Describe a person who inspires you. Ovozli javob yuboring.",
            "list",
            "screenshot-demo:ielts-speaking",
        ),
    )
    first_homework_id = 0
    for index, (group_id, title, description, kind, key) in enumerate(homework_specs):
        homework = create_homework(
            teacher_id=teacher_id,
            group_id=group_id,
            title=title,
            description=description,
            due_at=(due + timedelta(days=index * 2)).isoformat(),
            homework_kind=kind,
            requires_voice_message=index == 2,
            requires_essay=index == 1,
            idempotency_key=key,
        ) or {}
        homework_id = int(homework.get("id") or 0)
        if index == 0:
            first_homework_id = homework_id
        if homework_id:
            for fixture_id in fixtures[index * 8 : index * 8 + 6]:
                upsert_homework_submission(
                    homework_id,
                    fixture_id,
                    "pending_review",
                    note="Namuna topshiriq — App Store skrinshotlari uchun.",
                )
    return first_homework_id


def main() -> int:
    ensure_screenshot_demo_schema()
    ensure_teacher_content_permissions_schema()
    ensure_user_subject_schema()
    ensure_homework_schema()
    ensure_user_group_membership_log_schema()

    student_id, teacher_id = _find_demo_users()
    for setter in (
        set_daily_test_upload_permission,
        set_teacher_ai_generation_permission,
        set_book_upload_permission,
        set_video_upload_permission,
    ):
        setter(teacher_id, True)
    set_content_test_manage_permission(teacher_id, "book", True)
    set_content_test_manage_permission(teacher_id, "video", True)

    group_ids = [_ensure_group(teacher_id, spec) for spec in TEACHER_GROUPS]
    if not all(group_ids):
        raise RuntimeError("Could not create screenshot demo groups")
    _restrict_student_to_primary_group(student_id, teacher_id, group_ids[0])
    add_user_to_group(student_id, group_ids[0])

    fixtures = _ensure_fixture_students()
    for index, fixture_id in enumerate(fixtures):
        add_user_to_group(fixture_id, group_ids[min(index // 8, len(group_ids) - 1)])
    _lock_fixture_accounts(fixtures)

    wallet_random = random.SystemRandom()
    set_screenshot_demo_wallet(
        student_id,
        wallet_random.randint(3400, 7900),
        wallet_random.randint(2400, 9200),
    )
    _seed_homework(teacher_id, group_ids, fixtures)

    print(
        "Screenshot demo content is ready "
        f"(student_groups=1, teacher_groups={len(group_ids)}, fixtures={len(fixtures)})."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Screenshot demo seeding failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
