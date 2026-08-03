import re

with open('backend/main.py', 'r') as f:
    content = f.read()

old_payload_func = """def _group_membership_change_payload(group_id: int, student_id: int, message: str, **extra: Any) -> dict[str, Any]:
    student = _safe_call(lambda: get_user_by_id(int(student_id)), None) or {}
    groups = _safe_call(lambda: get_user_groups(int(student_id)), []) or []
    member = _serialize_user_row_light(student) if student else {"id": int(student_id)}
    member["group_count"] = len(groups)
    payload = {
        "message": message,
        "group_id": int(group_id),
        "student_id": int(student_id),
        "member": member,
        "group_count": len(_safe_call(lambda: get_group_users(int(group_id)), []) or []),
    }
    payload.update(extra)
    return payload"""

new_payload_func = """def _group_membership_change_payload(group_id: int, student_id: int, message: str, **extra: Any) -> dict[str, Any]:
    student = _safe_call(lambda: get_user_by_id(int(student_id)), None) or {}
    groups = _safe_call(lambda: get_user_groups(int(student_id)), []) or []
    member = _serialize_user_row_light(student) if student else {"id": int(student_id)}
    member["group_count"] = len(groups)
    
    group_count = 0
    try:
        from db import get_conn
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM user_groups WHERE group_id=?", (int(group_id),))
        row = cur.fetchone()
        if row:
            group_count = row[0]
    except Exception:
        pass

    payload = {
        "message": message,
        "group_id": int(group_id),
        "student_id": int(student_id),
        "member": member,
        "group_count": group_count,
    }
    payload.update(extra)
    return payload"""

if old_payload_func in content:
    content = content.replace(old_payload_func, new_payload_func)
    with open('backend/main.py', 'w') as f:
        f.write(content)
    print("Backend payload fixed!")
else:
    print("Could not find exact payload function to replace.")
