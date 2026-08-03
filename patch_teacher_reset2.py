import re
with open('backend/main.py', 'r') as f:
    content = f.read()

pattern = r'@app\.post\("/teacher/my-students/\{student_id\}/reset-password"\).*?return \{"message": "Password reset"\}'
new_route = """@app.post("/teacher/my-students/{student_id}/reset-password")
async def teacher_reset_student_password(student_id: int, authorization: str | None = Header(default=None)):
    user = _user_row_from_bearer(authorization)
    _require_role(user, {"teacher"})
    groups = _safe_call(lambda: get_groups_by_teacher(user["id"]), []) or []
    is_my_student = False
    for g in groups:
        members = _safe_call(lambda gid=g["id"]: get_group_users(int(gid)), []) or []
        if any(int(m.get("id") or 0) == student_id for m in members):
            is_my_student = True
            break
    if not is_my_student:
        raise HTTPException(status_code=403, detail="Student not found in your groups")

    target = get_user_by_id(student_id)
    if not target:
        raise HTTPException(status_code=404, detail="Student not found")

    new_password = generate_strong_password()
    update_user_password(student_id, new_password)
    
    qr_payload = None
    qr_token = None
    expires_at = None
    if target.get("login_id"):
        from utils import generate_qr_login_token
        qr_token, expires_at = generate_qr_login_token(target["login_id"])
        qr_payload = f"diamond_qr_login::{qr_token}"

    return {
        "message": "Password reset successfully",
        "password": new_password,
        "qr_payload": qr_payload,
        "qr_token": qr_token,
        "qr_expires_at": expires_at
    }"""

if re.search(pattern, content, re.DOTALL):
    content = re.sub(pattern, new_route, content, flags=re.DOTALL)
    with open('backend/main.py', 'w') as f:
        f.write(content)
    print("Replaced successfully")
else:
    print("Pattern not found")
