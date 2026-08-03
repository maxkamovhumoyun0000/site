import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

# Revert globally: tt( " -> t(locale, "
content = content.replace('tt( "', 't(locale, "')

# In TeacherSection, we need tt(" instead of t(locale, "
# Let's find TeacherSection
start = content.find('function TeacherSection({')
end = content.find('function SupportSection({')

teacher_section = content[start:end]
teacher_section = teacher_section.replace('t(locale, "', 'tt("')

content = content[:start] + teacher_section + content[end:]

with open('app/page.tsx', 'w') as f:
    f.write(content)

print("i18n fixed!")
