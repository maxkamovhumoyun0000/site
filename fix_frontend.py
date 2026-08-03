import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# 1. Replace adminAddUserMembershipMode with adminAddUserJoinedAt
content = content.replace('const [adminAddUserMembershipMode, setAdminAddUserMembershipMode] = useState<"new" | "existing">("new");', 'const [adminAddUserJoinedAt, setAdminAddUserJoinedAt] = useState<string>("");')

# Replace the select box for adding member
old_select_member = """<label>
                    To'lov boshlanishi
                    <select value={adminAddUserMembershipMode} onChange={(event) => setAdminAddUserMembershipMode(event.target.value as "new" | "existing")}>
                      <option value="new">Yangi o'quvchi: qo'shilgan kundan hisoblanadi</option>
                      <option value="existing">Oldindan o'qigan: oyning boshidan hisoblanadi</option>
                    </select>
                  </label>"""
new_input_member = """<label>
                    Qo'shilgan sanasi
                    <input type="date" value={adminAddUserJoinedAt} onChange={(e) => setAdminAddUserJoinedAt(e.target.value)} />
                  </label>"""
content = content.replace(old_select_member, new_input_member)

# Replace the payload membership_mode with joined_at
content = content.replace('body: { membership_mode: groupAddMembershipMode }', 'body: { joined_at: adminAddUserJoinedAt || undefined }') # wait, where is groupAddMembershipMode?
content = content.replace('body: { membership_mode: adminAddUserMembershipMode }', 'body: { joined_at: adminAddUserJoinedAt || undefined }')

# 2. Let's find groupAddMembershipMode
# Let's search if `groupAddMembershipMode` exists
if 'groupAddMembershipMode' in content:
    content = content.replace('const [groupAddMembershipMode, setGroupAddMembershipMode] = useState<"new" | "existing">("new");', 'const [groupAddJoinedAt, setGroupAddJoinedAt] = useState<string>("");')
    
    old_group_add = """<label>
                                To'lov boshlanishi
                                <select className="input-field" value={groupAddMembershipMode} onChange={(e) => setGroupAddMembershipMode(e.target.value as "new" | "existing")}>
                                  <option value="new">Yangi: qo'shilgan kundan</option>
                                  <option value="existing">Oldindan: oy boshidan</option>
                                </select>
                              </label>"""
    new_group_add = """<label>
                                Qo'shilgan sanasi
                                <input type="date" className="input-field" value={groupAddJoinedAt} onChange={(e) => setGroupAddJoinedAt(e.target.value)} />
                              </label>"""
    content = content.replace(old_group_add, new_group_add)
    content = content.replace('body: { membership_mode: groupAddMembershipMode }', 'body: { joined_at: groupAddJoinedAt || undefined }')


# 3. Replace accountlessMembershipMode with accountlessJoinedAt
content = content.replace('const [accountlessMembershipMode, setAccountlessMembershipMode] = useState<"new" | "existing">("new");', 'const [accountlessJoinedAt, setAccountlessJoinedAt] = useState<string>("");')

old_select_acct = """<label>
            To'lov boshlanishi
            <select value={accountlessMembershipMode} onChange={(event) => setAccountlessMembershipMode(event.target.value as "new" | "existing")}>
              <option value="new">Yangi o'quvchi: bugundan</option>
              <option value="existing">Oldindan o'qigan: oy boshidan</option>
            </select>
          </label>"""
new_input_acct = """<label>
            Qo'shilgan sanasi
            <input type="date" value={accountlessJoinedAt} onChange={(e) => setAccountlessJoinedAt(e.target.value)} />
          </label>"""
content = content.replace(old_select_acct, new_input_acct)

content = content.replace('payload.membership_mode = accountlessMembershipMode;', 'payload.joined_at = accountlessJoinedAt || undefined;')

with open('app/page.tsx', 'w') as f:
    f.write(content)
print("page.tsx updated")

