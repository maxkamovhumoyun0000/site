import re

with open('app/ui/navigation-config.ts', 'r') as f:
    content = f.read()

# Add to teacher sections
teacher_line_old = 'teacher: ["home", "chats", "groups", "attendance", "arena", "performance", "dcoin", "homework", "leaderboard", "videos", "books", "profile"],'
teacher_line_new = 'teacher: ["home", "chats", "groups", "substitutions", "attendance", "arena", "performance", "dcoin", "homework", "leaderboard", "videos", "books", "profile"],'

if teacher_line_old in content:
    content = content.replace(teacher_line_old, teacher_line_new)

# Add label
labels_end = content.find('};', content.find('export const SECTION_LABELS'))
if '"substitutions":' not in content[labels_end-200:labels_end]:
    content = content[:labels_end] + '  substitutions: "Vaqtinchalik O\'qituvchi",\n' + content[labels_end:]

with open('app/ui/navigation-config.ts', 'w') as f:
    f.write(content)

print("Nav config updated!")
