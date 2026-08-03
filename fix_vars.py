import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Lines to move:
# const selectedTeacherGroup = groups.find((g: GenericRow) => Number(g.id) === Number(selectedGroupId)) || null;
# const selectedIsTemporary = Boolean(selectedTeacherGroup?.temporary_access);
# const selectedTeacherGroupSubject = normalizeSubjectLabel(String(selectedTeacherGroup?.subject || ""));
# const matchingTeacherTempCandidates = tempTeacherCandidates.filter((row) => rowMatchesSubject(row, selectedTeacherGroupSubject));

block_to_remove = """    const selectedTeacherGroup = groups.find((g: GenericRow) => Number(g.id) === Number(selectedGroupId)) || null;
    const selectedIsTemporary = Boolean(selectedTeacherGroup?.temporary_access);
    const selectedTeacherGroupSubject = normalizeSubjectLabel(String(selectedTeacherGroup?.subject || ""));
    const matchingTeacherTempCandidates = tempTeacherCandidates.filter((row) => rowMatchesSubject(row, selectedTeacherGroupSubject));"""

if block_to_remove in content:
    content = content.replace(block_to_remove + '\n', '')
    
    # Insert right before `if (section === "home") {` in TeacherSection
    insert_pos = content.find('if (section === "home") {')
    content = content[:insert_pos] + block_to_remove + '\n\n  ' + content[insert_pos:]

    with open('app/page.tsx', 'w') as f:
        f.write(content)
    print("Variables hoisted!")
else:
    print("Block not found!")
