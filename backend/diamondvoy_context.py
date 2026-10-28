"""Verified account context for Diamondvoy (website and every app).

Diamondvoy answers questions such as "qaysi guruhlarim bor?", "kim qarzdor?",
"bugungi darslarim" or "progressim qanday?" from this context. Each section
mirrors what the user can already see in the app:

* students and Speaking users: only their own records;
* teachers: the groups they manage (own + temporary access) and the students
  in them, the same rule as /teacher/my-students;
* support teachers: bookings assigned to them or in their subjects, the same
  SQL as /support/bookings/*;
* admins: records inside their admin scope (limited admins see their own
  branch plus shared records), the same helpers as the admin pages.

Phone numbers, passwords and tokens are never included. Every section is
best-effort: a failing query drops that section instead of the answer.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Callable

from db import get_conn

logger = logging.getLogger(__name__)

_CACHE: dict[tuple[int, str], tuple[float, str]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 45.0
_MAX_CONTEXT_CHARS = 24000

_WEEKDAYS_UZ = ("Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba")


def _m():
    # Late import: backend.main imports this module.
    from backend import main as main_module

    return main_module


def _safe(fn: Callable[[], Any], fallback: Any) -> Any:
    try:
        return fn()
    except Exception:
        logger.debug("diamondvoy context section failed", exc_info=True)
        return fallback


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return [dict(row) for row in (cur.fetchall() or [])]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _placeholders(values: list[Any] | set[Any]) -> str:
    return ",".join("?" for _ in values)


def _money(value: Any) -> str:
    try:
        return f"{int(round(float(value or 0))):,}".replace(",", " ") + " so'm"
    except (TypeError, ValueError):
        return "0 so'm"


def _name(row: dict[str, Any] | None) -> str:
    return _m()._display_name(row)


def _schedule_text(group: dict[str, Any]) -> str:
    days = str(group.get("lesson_date") or "").strip().upper()
    label = {"MWF": "Du/Chor/Ju", "TTS": "Se/Pay/Sha"}.get(days, days or "-")
    start = str(group.get("lesson_start") or "").strip()
    end = str(group.get("lesson_end") or "").strip()
    times = f" {start}-{end}" if start and end else (f" {start}" if start else "")
    return f"{label}{times}"


def _today() -> date:
    return datetime.strptime(_m()._now_tashkent_date(), "%Y-%m-%d").date()


def _next_lesson(group: dict[str, Any], today: date) -> str:
    matches = _m()._group_schedule_matches_date
    for offset in range(0, 8):
        day = today + timedelta(days=offset)
        if matches(str(group.get("lesson_date") or ""), day):
            when = "bugun" if offset == 0 else ("ertaga" if offset == 1 else _WEEKDAYS_UZ[day.weekday()])
            return f"{when} ({day.isoformat()})"
    return "-"


def _section(title: str, lines: list[str], limit: int = 40) -> str:
    clean = [line for line in lines if line]
    if not clean:
        return ""
    extra = len(clean) - limit
    body = "\n".join(f"- {line}" for line in clean[:limit])
    if extra > 0:
        body += f"\n- ... va yana {extra} ta"
    return f"## {title}\n{body}"


def _now_line() -> str:
    today = _today()
    return f"Bugun: {today.isoformat()}, {_WEEKDAYS_UZ[today.weekday()]} (Toshkent vaqti)."


# ---------------------------------------------------------------------------
# Student (main platform)
# ---------------------------------------------------------------------------

def _student_groups(uid: int) -> list[dict[str, Any]]:
    from db import get_user_groups

    groups = [g for g in (get_user_groups(uid) or []) if int(g.get("active", 1) or 0) == 1]
    teacher_ids = {int(g.get("teacher_id") or 0) for g in groups if int(g.get("teacher_id") or 0) > 0}
    teachers: dict[int, dict[str, Any]] = {}
    if teacher_ids:
        for row in _rows(
            f"SELECT id, first_name, last_name FROM users WHERE id IN ({_placeholders(teacher_ids)})",
            tuple(teacher_ids),
        ):
            teachers[int(row.get("id") or 0)] = row
    for group in groups:
        group["_teacher_name"] = _name(teachers.get(int(group.get("teacher_id") or 0))) if group.get("teacher_id") else "-"
    return groups


def _student_section_groups(uid: int, groups: list[dict[str, Any]]) -> str:
    today = _today()
    lines = []
    for g in groups:
        level = str(g.get("level") or "").strip()
        lines.append(
            f"{g.get('name')} | fan: {g.get('subject') or '-'}{f' ({level})' if level else ''} | "
            f"o'qituvchi: {g.get('_teacher_name')} | jadval: {_schedule_text(g)} | keyingi dars: {_next_lesson(g, today)}"
            + (f" | kurs: {g.get('course_title')}" if g.get("course_title") else "")
        )
    return _section("Guruhlarim va darslarim", lines) or "## Guruhlarim va darslarim\n- Hozircha faol guruh yo'q."


def _student_section_attendance(uid: int) -> str:
    since = (_today() - timedelta(days=45)).isoformat()
    rows = _rows(
        """SELECT a.date, LOWER(COALESCE(a.status,'')) AS status, g.name AS group_name
           FROM attendance a LEFT JOIN groups g ON g.id=a.group_id
           WHERE a.user_id=? AND a.date>=? ORDER BY a.date DESC""",
        (uid, since),
    )
    if not rows:
        return ""
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"] or "noma'lum"] = counts.get(row["status"] or "noma'lum", 0) + 1
    summary = ", ".join(f"{status}: {count}" for status, count in sorted(counts.items()))
    recent = [f"{r.get('date')} — {r.get('group_name') or '-'}: {r.get('status')}" for r in rows[:8]]
    return _section("Davomat (oxirgi 45 kun)", [f"Jami: {summary}", *recent], limit=10)


def _student_section_homework(uid: int) -> str:
    from db import list_homeworks_for_student

    rows = list_homeworks_for_student(uid) or []
    lines = []
    for h in rows[:15]:
        status = str(h.get("submission_status") or "topshirilmagan")
        reviewed = " (tekshirilgan)" if h.get("reviewed_at") else ""
        delta = float(h.get("dpoints_delta") or 0)
        lines.append(
            f"{h.get('title') or 'Vazifa'} | {h.get('group_name') or '-'} | muddat: {str(h.get('due_at') or '-')[:16]} | "
            f"holat: {status}{reviewed}" + (f" | D'point: {delta:+g}" if delta else "")
            + (f" | izoh: {str(h.get('review_note'))[:120]}" if h.get("review_note") else "")
        )
    return _section("Uy vazifalari", lines, limit=15)


def _student_section_tests(uid: int) -> str:
    from db import get_daily_test_attempt_history, get_student_monthly_stats

    lines = []
    monthly = _safe(lambda: get_student_monthly_stats(uid), {}) or {}
    if monthly:
        answered = sum(float(monthly.get(k) or 0) for k in ("total_correct", "total_wrong", "total_skipped"))
        accuracy = round(float(monthly.get("total_correct") or 0) * 100 / answered, 1) if answered else 0
        lines.append(
            "Shu oy: testlar " + str(int(float(monthly.get("tests_completed") or 0))) + " ta yakunlangan"
            + f", aniqlik {accuracy}%"
            + f", o'rganilgan so'zlar {int(float(monthly.get('words_learned') or 0))}"
            + f", grammatika mavzulari {int(float(monthly.get('topics_completed') or 0))}"
        )
    for row in (get_daily_test_attempt_history(uid, limit=6) or []):
        lines.append(
            f"Kunlik test {row.get('test_date')} | {row.get('subject')} {row.get('level') or ''} | "
            f"to'g'ri {row.get('correct', row.get('correct_count', 0))}, xato {row.get('wrong', row.get('wrong_count', 0))}, "
            f"javobsiz {row.get('unanswered', row.get('unanswered_count', 0))} | holat: {row.get('status')}"
        )
    from db import get_placement_results_for_user

    placement = _safe(lambda: get_placement_results_for_user(uid, limit=1), []) or []
    if placement:
        p = placement[0]
        lines.append(f"Oxirgi daraja testi: {p.get('subject') or '-'} — {p.get('level') or '-'} ({str(p.get('created_at') or '')[:10]})")
    return _section("Test natijalari", lines, limit=10)


def _student_section_learning_path(uid: int) -> str:
    rows = _rows(
        """SELECT t.title, t.subject,
                  COUNT(DISTINCT m.id) AS modules,
                  COUNT(DISTINCT CASE WHEN p.status IN ('passed','completed') OR p.passed_at IS NOT NULL THEN m.id END) AS passed,
                  MAX(CASE WHEN f.passed_at IS NOT NULL THEN 1 ELSE 0 END) AS final_passed
           FROM learning_track_assignments a
           JOIN learning_tracks t ON t.id=a.track_id
           LEFT JOIN learning_modules m ON m.track_id=t.id
           LEFT JOIN learning_module_progress p ON p.module_id=m.id AND p.student_id=a.student_id
           LEFT JOIN learning_track_final_progress f ON f.track_id=t.id AND f.student_id=a.student_id
           WHERE a.student_id=? AND COALESCE(a.status,'active')='active'
           GROUP BY t.id, t.title, t.subject ORDER BY t.title""",
        (uid,),
    )
    lines = [
        f"{r.get('title')} ({r.get('subject')}): {int(r.get('passed') or 0)}/{int(r.get('modules') or 0)} modul"
        + (", yakuniy imtihon topshirilgan" if int(r.get("final_passed") or 0) else "")
        for r in rows
    ]
    return _section("Learning Path", lines, limit=8)


def _student_section_payments(uid: int) -> str:
    ym = _m()._payment_ym_now()
    rows = _rows(
        """SELECT o.final_amount, o.paid_amount, o.debt_amount, o.status, g.name AS group_name
           FROM payment_monthly_obligations o LEFT JOIN groups g ON g.id=o.group_id
           WHERE o.user_id=? AND o.ym=?""",
        (uid, ym),
    )
    lines = [
        f"{r.get('group_name') or '-'}: to'lov {_money(r.get('final_amount'))}, to'langan {_money(r.get('paid_amount'))}, "
        f"qarz {_money(r.get('debt_amount'))} ({r.get('status')})"
        for r in rows
        if float(r.get("final_amount") or 0) > 0 or float(r.get("debt_amount") or 0) > 0
    ]
    return _section(f"To'lovlar ({ym})", lines, limit=8)


def _student_section_balance_and_bookings(uid: int) -> str:
    from db import get_dcoins, get_dpoints, list_lesson_bookings_for_student

    lines = [
        f"D'coin: {round(float(_safe(lambda: get_dcoins(uid), 0) or 0), 2)}, "
        f"D'point: {round(float(_safe(lambda: get_dpoints(uid), 0) or 0), 2)}"
    ]
    for b in (_safe(lambda: list_lesson_bookings_for_student(uid, active_only=True), []) or [])[:5]:
        lines.append(f"Support dars bron: {b.get('date')} {b.get('time')} | {b.get('support_subject') or '-'} | {b.get('status')}")
    return _section("Balans va support darslar", lines, limit=8)


def _student_active_test_note(uid: int) -> str:
    """Whether the student has an unfinished test right now (anti-cheating)."""
    active: list[str] = []
    rows = _safe(
        lambda: _rows(
            "SELECT subject FROM daily_test_attempts WHERE user_id=? AND status='in_progress' AND test_date=?",
            (uid, _today().isoformat()),
        ),
        [],
    )
    if rows:
        active.append("kunlik test")
    from db import get_active_ai_test_attempt

    if _safe(lambda: get_active_ai_test_attempt(uid), None):
        active.append("AI test")
    if not active:
        return ""
    return (
        "## DIQQAT\n- Foydalanuvchida hozir tugallanmagan test bor: "
        + ", ".join(active)
        + ". Bu testning hech bir savoliga tayyor javob yoki variant harfini aytma."
    )


def _student_context(user: dict[str, Any]) -> list[str]:
    uid = int(user.get("id") or 0)
    groups = _safe(lambda: _student_groups(uid), [])
    levels = _safe(lambda: _m()._student_subject_levels_from_groups(uid), []) or []
    level_text = ", ".join(
        f"{item.get('subject')}: {item.get('level') or '-'}" for item in levels if isinstance(item, dict) and item.get("subject")
    )
    profile = (
        f"## Profil\n- {_name(user)} (login: {user.get('login_id') or '-'}), o'quvchi"
        + (f"\n- Fan/daraja: {level_text}" if level_text else "")
    )
    sections = [
        profile,
        _safe(lambda: _student_section_groups(uid, groups), ""),
        _safe(lambda: _student_section_tests(uid), ""),
        _safe(lambda: _student_section_homework(uid), ""),
        _safe(lambda: _student_section_attendance(uid), ""),
        _safe(lambda: _student_section_learning_path(uid), ""),
        _safe(lambda: _student_section_payments(uid), ""),
        _safe(lambda: _student_section_balance_and_bookings(uid), ""),
        _safe(lambda: _student_active_test_note(uid), ""),
    ]
    analysis = _safe(lambda: _m()._diamondvoy_student_learning_context(uid), "")
    if analysis:
        sections.append("## Shaxsiy tahlil va zaif mavzular\n" + str(analysis)[:5000])
    return sections


# ---------------------------------------------------------------------------
# Teacher
# ---------------------------------------------------------------------------

def _teacher_context(user: dict[str, Any]) -> list[str]:
    m = _m()
    uid = int(user.get("id") or 0)
    groups_raw = _safe(lambda: m._teacher_manageable_groups(uid), []) or []
    groups = [m._serialize_group_row(g) for g in groups_raw]
    group_ids = [int(g.get("id") or 0) for g in groups if int(g.get("id") or 0) > 0]
    today = _today()
    attendance_today = _safe(lambda: m._attendance_summary_for_groups(group_ids, today.isoformat()), {}) or {}

    group_lines = []
    for g in groups:
        gid = int(g.get("id") or 0)
        att = attendance_today.get(gid) or {}
        lesson_today = m._group_schedule_matches_date(str(g.get("lesson_date") or ""), today)
        group_lines.append(
            f"{g.get('name')} (ID {gid}) | {g.get('subject') or '-'} {g.get('level') or ''} | "
            f"{int(g.get('student_count') or 0)} o'quvchi | jadval: {_schedule_text(g)} | keyingi dars: {_next_lesson(g, today)}"
            + (" | vaqtinchalik ruxsat" if g.get("temporary_access") else "")
            + (f" | bugungi davomat: {att.get('present', 0)} keldi, {att.get('absent', 0)} kelmadi" if lesson_today and att else "")
            + (" | bugun dars bor, davomat hali belgilanmagan" if lesson_today and not att else "")
            + (" | mini guruh muzlatilgan" if g.get("mini_group_action_required") else "")
        )

    member_rows: list[dict[str, Any]] = []
    if group_ids:
        member_rows = _safe(
            lambda: _rows(
                f"""SELECT ug.group_id, u.id, u.first_name, u.last_name, u.login_id, u.level
                    FROM user_groups ug JOIN users u ON u.id=ug.user_id
                    WHERE ug.group_id IN ({_placeholders(group_ids)}) AND u.login_type IN (1,2,6)
                      AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT))='')
                    ORDER BY u.first_name, u.last_name""",
                tuple(group_ids),
            ),
            [],
        )
    student_ids = {int(r.get("id") or 0) for r in member_rows if int(r.get("id") or 0) > 0}
    stats = _safe(lambda: m._teacher_monthly_test_stats_for_students(student_ids), {}) or {}
    dpoints = _safe(lambda: m._dpoints_map_for_users(student_ids), {}) or {}
    absences: dict[int, int] = {}
    if student_ids:
        since = (today - timedelta(days=30)).isoformat()
        for row in _safe(
            lambda: _rows(
                f"""SELECT user_id, COUNT(*) AS n FROM attendance
                    WHERE user_id IN ({_placeholders(student_ids)}) AND group_id IN ({_placeholders(group_ids)})
                      AND date>=? AND LOWER(COALESCE(status,'')) IN ('absent','sababsiz','kelmadi')
                    GROUP BY user_id""",
                (*student_ids, *group_ids, since),
            ),
            [],
        ):
            absences[int(row.get("user_id") or 0)] = int(row.get("n") or 0)
    debts: dict[int, float] = {}
    if student_ids:
        for row in _safe(
            lambda: _rows(
                f"""SELECT user_id, SUM(debt_amount) AS debt FROM payment_monthly_obligations
                    WHERE ym=? AND group_id IN ({_placeholders(group_ids)}) GROUP BY user_id""",
                (m._payment_ym_now(), *group_ids),
            ),
            [],
        ):
            debts[int(row.get("user_id") or 0)] = float(row.get("debt") or 0)

    group_names = {int(g.get("id") or 0): g.get("name") for g in groups}
    student_lines = []
    for r in member_rows[:200]:
        sid = int(r.get("id") or 0)
        s = stats.get(sid) or {}
        student_lines.append(
            f"{_name(r)} | {group_names.get(int(r.get('group_id') or 0), '-')} | {r.get('level') or '-'} | "
            f"testlar {int(float(s.get('tests_completed') or 0))}, {round(float(s.get('accuracy_percent') or 0), 1)}% | "
            f"D'point {round(float(dpoints.get(sid, 0) or 0), 1)} | kelmagan(30k): {absences.get(sid, 0)}"
            + (f" | qarz: {_money(debts[sid])}" if debts.get(sid, 0) > 0 else "")
        )

    homework_lines = []
    from db import list_homeworks_for_admin

    homeworks = _safe(lambda: list_homeworks_for_admin(teacher_id=uid), []) or []
    for h in homeworks[:12]:
        homework_lines.append(
            f"{h.get('title') or 'Vazifa'} | {h.get('group_name') or '-'} | muddat: {str(h.get('due_at') or '-')[:16]}"
            + (f" | topshirgan: {int(h.get('submission_count') or 0)}/{int(h.get('group_member_count') or 0)}" if h.get("submission_count") is not None else "")
        )

    pending = _safe(
        lambda: m._teacher_pending_tasks(uid, groups, student_ids=student_ids, attendance_summary=attendance_today),
        {},
    ) or {}
    pending_line = (
        f"Belgilanmagan davomat: {pending.get('pending_attendance_groups', 0)} guruh, "
        f"tekshirilmagan vazifalar: {pending.get('pending_homework', 0)}, "
        f"support so'rovlar: {pending.get('pending_support_requests', 0)}"
        if pending else ""
    )
    return [
        f"## Profil\n- {_name(user)} (login: {user.get('login_id') or '-'}), o'qituvchi; fanlar: "
        + ", ".join(m._normalize_subjects(m._user_subjects_from_row(user), fallback=[]) or ["-"]),
        _section("Mening guruhlarim", group_lines) or "## Mening guruhlarim\n- Hozircha guruh yo'q.",
        _section("Bugungi vazifalar", [pending_line]),
        _section("Bergan uy vazifalarim", homework_lines, limit=12),
        _section(f"O'quvchilarim ({len(student_ids)} ta)", student_lines, limit=200),
    ]


# ---------------------------------------------------------------------------
# Support teacher
# ---------------------------------------------------------------------------

def _support_context(user: dict[str, Any]) -> list[str]:
    m = _m()
    subjects = _safe(lambda: m._support_actor_subjects(user), []) or []
    sections = [
        f"## Profil\n- {_name(user)} (login: {user.get('login_id') or '-'}), support o'qituvchi; fanlar: {', '.join(subjects) or '-'}"
    ]
    titles = {"upcoming": "Kelgusi bronlar", "attendance": "Davomat kutilayotgan bronlar (14 kun)", "bonus": "D'point berish oynasi ochiq bronlar"}
    for mode, title in titles.items():
        rows = _safe(lambda mode=mode: m._support_booking_rows_for_actor(user, mode, limit=60), []) or []
        if not rows:
            continue
        students = _safe(lambda rows=rows: m._booking_users_by_id(rows), {}) or {}
        lines = [
            f"{b.get('date')} {b.get('time')} | {_name(students.get(int(b.get('student_user_id') or 0)))} | "
            f"{b.get('support_subject') or '-'} | {b.get('purpose') or '-'} | {b.get('status')}"
            for b in rows
        ]
        sections.append(_section(title, lines, limit=30))
    temp_groups = _safe(lambda: m._teacher_manageable_groups(int(user.get("id") or 0)), []) or []
    if temp_groups:
        today = _today()
        sections.append(_section(
            "Vaqtinchalik guruhlarim",
            [f"{g.get('name')} | {_schedule_text(g)} | keyingi dars: {_next_lesson(g, today)}" for g in temp_groups],
        ))
    return sections


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

def _admin_context(user: dict[str, Any]) -> list[str]:
    from db import get_all_groups, get_all_users

    m = _m()
    ref = m._admin_ref_id(user)
    is_main = m._is_main_admin(ref)
    is_limited = m._is_limited_admin(ref)
    users = _safe(get_all_users, []) or []
    students = m._scope_users_for_admin(ref, users, login_type_filter=(1, 2, 6))
    teachers = [u for u in users if int(u.get("login_type") or 0) == 3]
    support = [u for u in users if int(u.get("login_type") or 0) == 5]
    groups = [g for g in m._scope_groups_for_admin(ref, _safe(get_all_groups, []) or []) if int(g.get("active", 1) or 0) == 1]
    group_ids = [int(g.get("id") or 0) for g in groups if int(g.get("id") or 0) > 0]
    scope = "bosh admin (hamma filial)" if is_main or not is_limited else "filial admini (o'z filiali + umumiy yozuvlar)"
    blocked = sum(1 for u in students if int(u.get("blocked") or 0) == 1)
    pending_approval = sum(1 for u in students if int(u.get("pending_approval") or 0) == 1)
    sections = [
        f"## Profil\n- {_name(user)} (login: {user.get('login_id') or '-'}), admin; ko'rinish doirasi: {scope}",
        _section("Umumiy statistika", [
            f"O'quvchilar: {len(students)} (bloklangan {blocked}, tasdiq kutayotgan {pending_approval})",
            f"O'qituvchilar: {len(teachers)}, support o'qituvchilar: {len(support)}, faol guruhlar: {len(groups)}",
        ]),
    ]

    teacher_names = {int(t.get("id") or 0): _name(t) for t in teachers}
    counts: dict[int, int] = {}
    if group_ids:
        for row in _safe(
            lambda: _rows(
                f"""SELECT ug.group_id, COUNT(*) AS n FROM user_groups ug JOIN users u ON u.id=ug.user_id
                    WHERE ug.group_id IN ({_placeholders(group_ids)}) AND u.login_type IN (1,2,6)
                      AND (ug.left_date IS NULL OR TRIM(CAST(ug.left_date AS TEXT))='')
                    GROUP BY ug.group_id""",
                tuple(group_ids),
            ),
            [],
        ):
            counts[int(row.get("group_id") or 0)] = int(row.get("n") or 0)
    today = _today()
    attendance_today = _safe(lambda: m._attendance_summary_for_groups(group_ids, today.isoformat()), {}) or {}
    group_lines = []
    lessons_today = 0
    for g in groups:
        gid = int(g.get("id") or 0)
        has_lesson = m._group_schedule_matches_date(str(g.get("lesson_date") or ""), today)
        lessons_today += 1 if has_lesson else 0
        att = attendance_today.get(gid) or {}
        group_lines.append(
            f"{g.get('name')} (ID {gid}) | {g.get('subject') or '-'} {g.get('level') or ''} | "
            f"o'qituvchi: {teacher_names.get(int(g.get('teacher_id') or 0), '-')} | {counts.get(gid, 0)} o'quvchi | {_schedule_text(g)}"
            + (f" | narx turi: {g.get('pricing_type')}" if g.get("pricing_type") and g.get("pricing_type") != "group" else "")
            + (" | mini guruh muzlatilgan, admin qarori kerak" if int(g.get("mini_group_action_required") or 0) else "")
            + (f" | bugun: {att.get('present', 0)} keldi, {att.get('absent', 0)} kelmadi" if has_lesson and att else "")
            + (" | bugun dars, davomat belgilanmagan" if has_lesson and not att else "")
        )
    sections.append(f"## Bugun\n- {lessons_today} ta guruhda dars bor.")
    sections.append(_section("Guruhlar", group_lines, limit=80))

    teacher_groups: dict[int, int] = {}
    for g in groups:
        tid = int(g.get("teacher_id") or 0)
        teacher_groups[tid] = teacher_groups.get(tid, 0) + 1
    sections.append(_section(
        "O'qituvchilar",
        [f"{_name(t)} ({t.get('login_id') or '-'}) | fan: {t.get('subject') or '-'} | {teacher_groups.get(int(t.get('id') or 0), 0)} guruh" for t in teachers],
        limit=60,
    ))

    if group_ids:
        ym = m._payment_ym_now()
        rows = _safe(
            lambda: _rows(
                f"""SELECT o.user_id, o.status, o.final_amount, o.paid_amount, o.debt_amount, g.name AS group_name
                    FROM payment_monthly_obligations o LEFT JOIN groups g ON g.id=o.group_id
                    WHERE o.ym=? AND o.group_id IN ({_placeholders(group_ids)})""",
                (ym, *group_ids),
            ),
            [],
        )
        if rows:
            student_names = {int(u.get("id") or 0): _name(u) for u in students}
            visible = [r for r in rows if int(r.get("user_id") or 0) in student_names]
            due = sum(float(r.get("final_amount") or 0) for r in visible)
            paid = sum(float(r.get("paid_amount") or 0) for r in visible)
            debt_rows = sorted((r for r in visible if float(r.get("debt_amount") or 0) > 0), key=lambda r: -float(r.get("debt_amount") or 0))
            sections.append(_section(f"To'lovlar ({ym})", [
                f"Hisoblangan: {_money(due)}, to'langan: {_money(paid)}, qarz: {_money(sum(float(r.get('debt_amount') or 0) for r in debt_rows))}",
                f"Qarzdorlar: {len({int(r.get('user_id') or 0) for r in debt_rows})} o'quvchi",
                *[f"Qarz: {student_names.get(int(r.get('user_id') or 0))} | {r.get('group_name') or '-'} | {_money(r.get('debt_amount'))} ({r.get('status')})" for r in debt_rows[:25]],
            ], limit=30))

    pending_bookings = _safe(
        lambda: _rows("SELECT COUNT(*) AS n FROM lesson_bookings WHERE status='pending' AND (start_ts IS NULL OR start_ts>=?)", (m._now_utc().isoformat(),)),
        [],
    )
    if pending_bookings:
        sections.append(f"## Support bronlar\n- Tasdiq kutayotgan bronlar: {int(pending_bookings[0].get('n') or 0)}")
    return sections


# ---------------------------------------------------------------------------
# Speaking app user
# ---------------------------------------------------------------------------

def _speaking_context(user: dict[str, Any]) -> list[str]:
    from db import get_dcoins, get_dpoints

    m = _m()
    uid = int(user.get("id") or 0)
    subjects = m._normalize_subjects(m._user_subjects_from_row(user), fallback=[])
    sections = [
        f"## Profil\n- {_name(user)} (login: {user.get('login_id') or '-'}), Diamond Speaking foydalanuvchisi; "
        f"fanlar: {', '.join(subjects) or '-'}; daraja: {user.get('level') or '-'}",
        f"## Balans\n- D'coin: {round(float(_safe(lambda: get_dcoins(uid), 0) or 0), 2)}, D'point: {round(float(_safe(lambda: get_dpoints(uid), 0) or 0), 2)}",
    ]
    tracks = _safe(
        lambda: _rows(
            """SELECT t.title, t.subject,
                      COUNT(DISTINCT m.id) AS modules,
                      COUNT(DISTINCT CASE WHEN a.passed=TRUE THEN m.id END) AS passed,
                      MAX(a.score) AS best_score,
                      EXISTS(SELECT 1 FROM speaking_learning_final_attempts fa WHERE fa.track_id=t.id AND fa.user_id=? AND fa.passed=TRUE) AS final_passed
               FROM speaking_learning_tracks t
               LEFT JOIN speaking_learning_modules m ON m.track_id=t.id
               LEFT JOIN speaking_learning_attempts a ON a.module_id=m.id AND a.user_id=?
               WHERE t.is_published=TRUE GROUP BY t.id, t.title, t.subject ORDER BY t.sort_order, t.id""",
            (uid, uid),
        ),
        [],
    )
    sections.append(_section("Speaking Learning Path", [
        f"{t.get('title')} ({t.get('subject')}): {int(t.get('passed') or 0)}/{int(t.get('modules') or 0)} modul o'tilgan"
        + (f", eng yaxshi ball {int(t.get('best_score'))}" if t.get("best_score") is not None else "")
        + (", yakuniy imtihon topshirilgan" if t.get("final_passed") else "")
        for t in tracks
    ], limit=10))
    lessons = _safe(
        lambda: _rows(
            """SELECT title, topic, subject, moderator_name, starts_at, status FROM speaking_live_lessons
               WHERE COALESCE(status,'') NOT IN ('cancelled','canceled') AND starts_at>=?
               ORDER BY starts_at ASC LIMIT 6""",
            (m._now_utc() - timedelta(hours=2),),
        ),
        [],
    )
    sections.append(_section("Kelgusi jonli darslar (hamma uchun ochiq jadval)", [
        f"{str(l.get('starts_at') or '')[:16]} | {l.get('title') or l.get('topic') or '-'} | {l.get('subject') or '-'} | {l.get('moderator_name') or '-'} | {l.get('status')}"
        for l in lessons
    ], limit=6))
    vocab = _safe(
        lambda: _rows(
            "SELECT COUNT(DISTINCT word_id) AS practiced, COUNT(DISTINCT CASE WHEN consecutive_correct>=3 THEN word_id END) AS mastered FROM vocab_word_mastery WHERE user_id=?",
            (uid,),
        ),
        [],
    )
    if vocab and int(vocab[0].get("practiced") or 0) > 0:
        sections.append(f"## Lug'at\n- Mashq qilingan so'zlar: {int(vocab[0].get('practiced') or 0)}, yaxshi o'zlashtirilgan: {int(vocab[0].get('mastered') or 0)}")
    return sections


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

_NO_TEST_ANSWERS_RULE = """
TEST JAVOBLARI QOIDASI (o'quvchi va Speaking foydalanuvchilari uchun, qat'iy):
- Foydalanuvchi test, quiz, uy vazifasi, imtihon, Learning Path, Arena yoki duel savolining tayyor javobini, to'g'ri variantini (A/B/C/D) yoki "qaysi biri to'g'ri"sini so'rasa (matn, rasm yoki fayl orqali bo'lsa ham), yakuniy javobni va variant harfini AYTMA.
- Buning o'rniga: qoidani tushuntir, savolni qanday yechishni bosqichma-bosqich ko'rsat, xuddi shunday boshqa misolni to'liq yechib ber, va foydalanuvchiga o'zi tanlashini ayt. U o'z javobini yozsa, to'g'ri yoki noto'g'riligini va nima uchunligini tushuntirishing mumkin.
- Istisno: foydalanuvchi YAKUNLANGAN testni tahlil qilsa (xabarda "testini yakunladim" va har bir savol uchun "Men tanlagan javob / To'g'ri javob" ro'yxati bo'lsa) va kontekstda tugallanmagan test yo'q bo'lsa, to'g'ri javoblarni va xatolarni tushuntirish mumkin.
- Diamondvoy o'zi tuzgan quiz_json mashq testlari bu qoidaga kirmaydi.
"""

_CONTEXT_RULES = """
Quyidagi ma'lumotlar foydalanuvchining hisobidan bevosita olingan (tasdiqlangan). Foydalanuvchi o'zi, guruhlari, darslari, o'quvchilari, natijalari, to'lovlari yoki jadvali haqida so'rasa, aynan shu ma'lumotlardan foydalan; ro'yxat va taqqoslashlarni jadvalda ber. Bu yerda bo'lmagan raqam, ism yoki natijani to'qima — "bu ma'lumot menda yo'q" deb ayt. Telefon raqam, parol yoki boshqa maxfiy ma'lumotni so'rasa bermagin."""


def diamondvoy_user_context(user: dict[str, Any], role: str, *, speaking_account: bool) -> str:
    """Verified, role-scoped account context for one Diamondvoy request."""
    uid = int(user.get("id") or 0)
    kind = "speaking" if speaking_account else str(role or "").lower()
    if uid <= 0 or kind not in {"student", "teacher", "support", "admin", "speaking"}:
        return ""
    key = (uid, kind)
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] > now:
            return cached[1]
    builders = {
        "student": _student_context,
        "teacher": _teacher_context,
        "support": _support_context,
        "admin": _admin_context,
        "speaking": _speaking_context,
    }
    started = time.perf_counter()
    sections = _safe(lambda: builders[kind](user), []) or []
    body = "\n\n".join(section for section in sections if section)
    if len(body) > _MAX_CONTEXT_CHARS:
        body = body[:_MAX_CONTEXT_CHARS].rsplit("\n", 1)[0] + "\n- ... (qisqartirildi)"
    text = ""
    if body:
        text = (
            "\n\nVERIFIED ACCOUNT CONTEXT" + _CONTEXT_RULES + "\n" + _now_line() + "\n\n" + body
        )
    if kind in {"student", "speaking"}:
        text += "\n" + _NO_TEST_ANSWERS_RULE
    elapsed_ms = (time.perf_counter() - started) * 1000
    if elapsed_ms > 700:
        logger.info("diamondvoy.context slow kind=%s user_id=%s ms=%.0f chars=%s", kind, uid, elapsed_ms, len(text))
    with _CACHE_LOCK:
        if len(_CACHE) > 2000:
            _CACHE.clear()
        _CACHE[key] = (now + _CACHE_TTL_SECONDS, text)
    return text


def is_personal_context_query(text: str) -> bool:
    """Questions about the user's own account, groups or students.

    These must skip the generic bot-info and similar-answer caches so the
    reply uses the live context above.
    """
    import re

    normalized = str(text or "").lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    return bool(re.search(
        r"(mening|menga|meni |o'zim|progress|natija|xatolar|zaif|guruh|o'quvchilar|talaba|dars(lar|im|ing)|jadval|"
        r"davomat|qarz|to'lov|vazifa|homework|bron|booking|qachon|bugun|ertaga|kim |qaysi|nechta|statist|"
        r"my |mine|about me|group|student|lesson|schedule|attendance|payment|debt|today|tomorrow|who |which |how many|"
        r"мой|моя|мои|мне|меня|групп|ученик|урок|расписан|посещ|оплат|долг|сегодня|завтра|кто |какие|сколько)",
        normalized,
    ))
