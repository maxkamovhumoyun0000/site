from fastapi import APIRouter, Header, HTTPException
from db import get_conn, _row_to_dict

router = APIRouter()


def _row(raw) -> dict:
    """SQLite ham, PostgreSQL (dict cursor) ham support qilsin."""
    if raw is None:
        return {}
    try:
        return dict(raw)
    except Exception:
        return {}


def _get_student_analytics(student_ids: set[int]) -> dict:
    if not student_ids:
        return {}

    clean_ids = sorted({int(sid) for sid in student_ids if int(sid or 0) > 0})
    if not clean_ids:
        return {}

    placeholders = ",".join(["?"] * len(clean_ids))
    ids_tuple = tuple(clean_ids)

    # ── 1. Homework stats ────────────────────────────────────────────────────
    hw_stats: dict = {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT student_id,
                   COUNT(id) AS total_hw,
                   SUM(CASE WHEN status NOT IN ('not_done','pending') THEN 1 ELSE 0 END) AS done_hw
            FROM web_homework_submissions
            WHERE student_id IN ({placeholders})
            GROUP BY student_id
        """, ids_tuple)
        for raw in cur.fetchall() or []:
            r = _row(raw)
            sid = int(r.get("student_id") or 0)
            if sid > 0:
                hw_stats[sid] = {
                    "total_hw": int(r.get("total_hw") or 0),
                    "done_hw":  int(r.get("done_hw")  or 0),
                }
    except Exception as e:
        print("HW stats error:", e)
        try: conn.rollback()
        except: pass
    finally:
        conn.close()

    # ── 2. Content test stats ────────────────────────────────────────────────
    # Jadval: correct_count, total_questions (score/total emas!)
    test_stats: dict = {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT user_id,
                   COUNT(id) AS total_tests,
                   AVG(
                       CASE WHEN COALESCE(total_questions,0) > 0
                            THEN COALESCE(correct_count,0) * 100.0 / total_questions
                            ELSE 0 END
                   ) AS avg_score
            FROM web_content_test_attempts
            WHERE user_id IN ({placeholders})
            GROUP BY user_id
        """, ids_tuple)
        for raw in cur.fetchall() or []:
            r = _row(raw)
            uid = int(r.get("user_id") or 0)
            if uid > 0:
                test_stats[uid] = {
                    "total_tests": int(r.get("total_tests") or 0),
                    "avg_score":   float(r.get("avg_score") or 0.0),
                }
    except Exception as e:
        print("Test stats error:", e)
        try: conn.rollback()
        except: pass
    finally:
        conn.close()

    # ── 3. Attendance stats ──────────────────────────────────────────────────
    attendance_stats: dict = {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(f"""
            SELECT user_id,
                   COUNT(id) AS total_days,
                   SUM(CASE WHEN LOWER(COALESCE(status,'')) = 'present' THEN 1 ELSE 0 END) AS present_days
            FROM attendance
            WHERE user_id IN ({placeholders})
            GROUP BY user_id
        """, ids_tuple)
        for raw in cur.fetchall() or []:
            r = _row(raw)
            uid = int(r.get("user_id") or 0)
            if uid > 0:
                attendance_stats[uid] = {
                    "total_days":   int(r.get("total_days")   or 0),
                    "present_days": int(r.get("present_days") or 0),
                }
    except Exception as e:
        print("Attendance stats error:", e)
        try: conn.rollback()
        except: pass
    finally:
        conn.close()

    # ── 4. D'Coin velocity (last 30 days) ────────────────────────────────────
    dcoin_speeds: dict = {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        from datetime import datetime, timedelta
        thirty_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        # dcoin_change kolonini tekshirish: ba'zi jadvalda dpoints_change bo'lishi mumkin
        cur.execute(f"""
            SELECT user_id,
                   SUM(COALESCE(dcoin_change,0)) AS total_earned
            FROM diamond_history
            WHERE user_id IN ({placeholders})
              AND COALESCE(dcoin_change,0) > 0
              AND created_at >= ?
            GROUP BY user_id
        """, ids_tuple + (thirty_ago,))
        for raw in cur.fetchall() or []:
            r = _row(raw)
            uid = int(r.get("user_id") or 0)
            if uid > 0:
                dcoin_speeds[uid] = float(r.get("total_earned") or 0.0)
    except Exception as e:
        print("Dcoin speed error:", e)
        try: conn.rollback()
        except: pass
    finally:
        conn.close()

    # ── Natija hisoblash ─────────────────────────────────────────────────────
    result: dict = {}
    for sid in clean_ids:
        hw   = hw_stats.get(sid,   {"total_hw": 0, "done_hw": 0})
        test = test_stats.get(sid, {"total_tests": 0, "avg_score": 0.0})
        att  = attendance_stats.get(sid, {"total_days": 0, "present_days": 0})

        hw_completion = (hw["done_hw"] / hw["total_hw"] * 100) if hw["total_hw"] > 0 else None
        avg_score     = test["avg_score"] if test["total_tests"] > 0 else None
        att_rate      = (att["present_days"] / att["total_days"] * 100) if att["total_days"] > 0 else None

        components = []
        if hw_completion is not None: components.append((hw_completion, 40))
        if avg_score     is not None: components.append((avg_score,     30))
        if att_rate      is not None: components.append((att_rate,      30))

        if components:
            total_w      = sum(w for _, w in components)
            health_score = sum(v * w for v, w in components) / total_w
        else:
            health_score = 100.0

        zone = "green" if health_score >= 80 else ("yellow" if health_score >= 55 else "red")

        risk_reasons = []
        if zone != "green":
            if att_rate      is not None and att_rate      < 70: risk_reasons.append(f"Davomat past ({round(att_rate, 1)}%)")
            if hw_completion is not None and hw_completion < 60: risk_reasons.append(f"Vazifalar bajarilishi past ({round(hw_completion, 1)}%)")
            if avg_score     is not None and avg_score     < 55: risk_reasons.append(f"Test ballari past ({round(avg_score, 1)} o'rtacha)")

        result[sid] = {
            "health_score":    round(health_score, 1),
            "zone":            zone,
            "risk_reasons":    risk_reasons,
            "hw_completion":   round(hw_completion or 0, 1),
            "avg_test_score":  round(avg_score or 0, 1),
            "attendance_rate": round(att_rate or 0, 1),
            "total_hw":        hw["total_hw"],
            "done_hw":         hw["done_hw"],
            "total_tests":     test["total_tests"],
            "total_days":      att["total_days"],
            "present_days":    att["present_days"],
            "dcoin_speed":     round(dcoin_speeds.get(sid, 0.0), 1),
        }

    return result


# ─────────────────────────────────────────────────────────────────────────────
# TEACHER analytics
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/teacher/analytics")
async def teacher_analytics(authorization: str | None = Header(default=None)):
    from backend.main import (
        _user_row_from_bearer, _require_role, TEACHER_STAFF_ROLES,
        _teacher_student_ids, _teacher_manageable_groups,
        _user_rows_by_ids_light, get_user_groups, _first_existing_avatar_url,
    )

    user = _user_row_from_bearer(authorization)
    _require_role(user, TEACHER_STAFF_ROLES)
    teacher_id = int(user.get("id") or 0)

    student_ids = _teacher_student_ids(teacher_id)
    if not student_ids:
        return {"students": [], "groups_comparison": []}

    stats = _get_student_analytics(student_ids)

    # Faqat shu teacher'ga tegishli guruhlar
    teacher_groups     = _teacher_manageable_groups(teacher_id)
    teacher_group_ids: set = {int(g.get("id") or 0) for g in teacher_groups if int(g.get("id") or 0) > 0}

    student_rows = _user_rows_by_ids_light(student_ids, limit=max(80, len(student_ids)))

    students_data: list = []
    groups_data_map: dict = {}

    for raw in student_rows:
        row    = _row(raw)
        sid    = int(row.get("id") or 0)
        if sid <= 0:
            continue
        s_stat = stats.get(sid, {})

        u_groups    = get_user_groups(sid) or []
        group_names = [g.get("name") for g in u_groups if g.get("name") and int(g.get("id") or 0) in teacher_group_ids]

        for g in u_groups:
            gid   = int(g.get("id") or 0)
            gname = g.get("name")
            if not gid or not gname or gid not in teacher_group_ids:
                continue
            if gid not in groups_data_map:
                groups_data_map[gid] = {"id": gid, "name": gname, "health_scores": [], "dcoin_speeds": []}
            groups_data_map[gid]["health_scores"].append(s_stat.get("health_score", 0.0))
            groups_data_map[gid]["dcoin_speeds"].append(s_stat.get("dcoin_speed", 0.0))

        avatar_url = _first_existing_avatar_url(row.get("profile_image_url")) or ""
        students_data.append({
            "id":              sid,
            "first_name":      row.get("first_name"),
            "last_name":       row.get("last_name"),
            "login_id":        row.get("login_id"),
            "phone":           row.get("phone"),
            "avatar_url":      avatar_url,
            "profile_image_url": avatar_url,
            "groups":          group_names,
            "health_score":    s_stat.get("health_score", 0),
            "zone":            s_stat.get("zone", "green"),
            "risk_reasons":    s_stat.get("risk_reasons", []),
            "hw_completion":   s_stat.get("hw_completion", 0),
            "avg_test_score":  s_stat.get("avg_test_score", 0),
            "attendance_rate": s_stat.get("attendance_rate", 0),
            "dcoin_speed":     s_stat.get("dcoin_speed", 0),
        })

    groups_comparison = []
    for gid, gdata in groups_data_map.items():
        scores = gdata["health_scores"]
        speeds = gdata["dcoin_speeds"]
        groups_comparison.append({
            "group_id":         gid,
            "group_name":       gdata["name"],
            "avg_health_score": round(sum(scores) / len(scores) if scores else 0, 1),
            "avg_dcoin_speed":  round(sum(speeds) / len(speeds) if speeds else 0, 1),
            "student_count":    len(scores),
        })

    return {"students": students_data, "groups_comparison": groups_comparison}


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN analytics
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/admin/analytics")
async def admin_analytics(authorization: str | None = Header(default=None)):
    from backend.main import (
        _user_row_from_bearer, _require_role,
        _user_rows_by_ids_light, get_user_groups,
    )

    user = _user_row_from_bearer(authorization)
    _require_role(user, {"admin"})

    # Barcha aktiv o'quvchilarni ol
    conn = get_conn()
    cur  = conn.cursor()
    student_ids: set = set()
    try:
        cur.execute("SELECT id FROM users WHERE login_type IN (1, 2) AND active = 1")
        for raw in cur.fetchall() or []:
            r = _row(raw)
            uid = int(r.get("id") or 0)
            if uid > 0:
                student_ids.add(uid)
    except Exception as e:
        print("Admin analytics user fetch error:", e)
    finally:
        conn.close()

    if not student_ids:
        return {"students": [], "groups_comparison": []}

    stats = _get_student_analytics(student_ids)

    student_rows = _user_rows_by_ids_light(student_ids, limit=len(student_ids))

    students_data: list = []
    groups_data_map: dict = {}

    for raw in student_rows:
        row    = _row(raw)
        sid    = int(row.get("id") or 0)
        if sid <= 0:
            continue
        s_stat    = stats.get(sid, {})
        u_groups  = get_user_groups(sid) or []
        group_names = [g.get("name") for g in u_groups if g.get("name")]

        for g in u_groups:
            gid   = int(g.get("id") or 0)
            gname = g.get("name")
            if not gid or not gname:
                continue
            if gid not in groups_data_map:
                groups_data_map[gid] = {"id": gid, "name": gname, "health_scores": [], "dcoin_speeds": []}
            groups_data_map[gid]["health_scores"].append(s_stat.get("health_score", 0.0))
            groups_data_map[gid]["dcoin_speeds"].append(s_stat.get("dcoin_speed", 0.0))

        students_data.append({
            "id":              sid,
            "first_name":      row.get("first_name"),
            "last_name":       row.get("last_name"),
            "login_id":        row.get("login_id"),
            "phone":           row.get("phone"),
            "groups":          group_names,
            "health_score":    s_stat.get("health_score", 0),
            "zone":            s_stat.get("zone", "green"),
            "risk_reasons":    s_stat.get("risk_reasons", []),
            "hw_completion":   s_stat.get("hw_completion", 0),
            "avg_test_score":  s_stat.get("avg_test_score", 0),
            "attendance_rate": s_stat.get("attendance_rate", 0),
            "dcoin_speed":     s_stat.get("dcoin_speed", 0),
        })

    groups_comparison = []
    for gid, gdata in groups_data_map.items():
        scores = gdata["health_scores"]
        speeds = gdata["dcoin_speeds"]
        groups_comparison.append({
            "group_id":         gid,
            "group_name":       gdata["name"],
            "avg_health_score": round(sum(scores) / len(scores) if scores else 0, 1),
            "avg_dcoin_speed":  round(sum(speeds) / len(speeds) if speeds else 0, 1),
            "student_count":    len(scores),
        })

    return {"students": students_data, "groups_comparison": groups_comparison}
