import re

with open('/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py', 'r') as f:
    content = f.read()

# Fix Admin _common_ok
old_common_ok = """        if status_filter and status_filter != "all" and status_key:
            if status_filter not in str(row.get(status_key) or "").lower():
                return False
        return True"""

new_common_ok = """        if status_filter and status_filter != "all" and status_key:
            if status_filter not in str(row.get(status_key) or "").lower():
                return False
        if str(row.get("discount_type") or "") == "free_access":
            return False
        return True"""

content = content.replace(old_common_ok, new_common_ok)

# Fix Admin total_expected_amount
old_admin_expected = """"total_expected_amount": round(sum(float(row.get("original_amount") or 0.0) for row in filtered), 2),"""
new_admin_expected = """"total_expected_amount": round(sum(0.0 if str(row.get("discount_type") or "") == "free_access" else float(row.get("original_amount") or 0.0) for row in filtered), 2),"""
content = content.replace(old_admin_expected, new_admin_expected)

# Fix Student Payments
old_student_expected_sum = """total_expected = sum(float(row.get("original_amount") or 0.0) for row in filtered)"""
new_student_expected_sum = """total_expected = sum(0.0 if str(row.get("discount_type") or "") == "free_access" else float(row.get("original_amount") or 0.0) for row in filtered)"""
content = content.replace(old_student_expected_sum, new_student_expected_sum)

old_student_group_expected = """group_item["expected_amount"] += float(row.get("original_amount") or 0.0)"""
new_student_group_expected = """group_item["expected_amount"] += (0.0 if str(row.get("discount_type") or "") == "free_access" else float(row.get("original_amount") or 0.0))"""
content = content.replace(old_student_group_expected, new_student_group_expected)

old_student_teacher_expected = """teacher_item["expected_amount"] += float(row.get("original_amount") or 0.0)"""
new_student_teacher_expected = """teacher_item["expected_amount"] += (0.0 if str(row.get("discount_type") or "") == "free_access" else float(row.get("original_amount") or 0.0))"""
content = content.replace(old_student_teacher_expected, new_student_teacher_expected)

with open('/home/xumoyun-maxkamov/Desktop/diamond-site/backend/main.py', 'w') as f:
    f.write(content)
