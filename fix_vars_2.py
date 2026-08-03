import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Remove the block from the bottom
block = """    const selectedTeacherGroup = groups.find((g: GenericRow) => Number(g.id) === Number(selectedGroupId)) || null;
    const selectedIsTemporary = Boolean(selectedTeacherGroup?.temporary_access);
    const selectedTeacherGroupSubject = normalizeSubjectLabel(String(selectedTeacherGroup?.subject || ""));
    const matchingTeacherTempCandidates = tempTeacherCandidates.filter((row) => rowMatchesSubject(row, selectedTeacherGroupSubject));"""

if block in content:
    content = content.replace(block, "")

# Insert it after tempTeacherCandidates
insert_marker = "const tempTeacherCandidates = (data.temporary_teacher_candidates || []) as GenericRow[];"
if insert_marker in content:
    content = content.replace(insert_marker, insert_marker + "\n" + block)

with open('app/page.tsx', 'w') as f:
    f.write(content)

print("Vars fixed!")
