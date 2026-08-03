import re

with open('backend/main.py', 'r') as f:
    content = f.read()

# 1. GroupMemberAddRequest
old_group_member = """class GroupMemberAddRequest(BaseModel):
    membership_mode: Literal["new", "existing"] = "new\""""
new_group_member = """class GroupMemberAddRequest(BaseModel):
    joined_at: str | None = None"""
content = content.replace(old_group_member, new_group_member)

# 2. AccountlessStudentConvertRequest? Wait, let's find `UserCreateAccountlessRequest`
old_user_acctless = """    subject: str | None = None
    membership_mode: Literal["new", "existing"] = "new"
    family_group_id: int | None = None"""
new_user_acctless = """    subject: str | None = None
    joined_at: str | None = None
    family_group_id: int | None = None"""
content = content.replace(old_user_acctless, new_user_acctless)

# 3. Replace joined_at = _membership_joined_at_for_mode(...) with joined_at = payload.joined_at
content = re.sub(r'joined_at\s*=\s*_membership_joined_at_for_mode\(payload\.membership_mode if payload else None\)', 'joined_at = payload.joined_at if payload else None', content)
content = re.sub(r'joined_at\s*=\s*_membership_joined_at_for_mode\(payload\.membership_mode\)', 'joined_at = payload.joined_at if payload else None', content)

# 4. Replace membership_mode=(payload.membership_mode if payload else "new") with nothing or something else, but wait, `_group_membership_change_payload` uses it!
# Let's see _group_membership_change_payload
# It accepts membership_mode: str = "new". We can just leave it as "new" or pass "new"
content = re.sub(r'membership_mode=\(payload\.membership_mode if payload else "new"\)', 'membership_mode="new"', content)

with open('backend/main.py', 'w') as f:
    f.write(content)

print("backend/main.py updated successfully")
