import re

with open('app/page.tsx', 'r') as f:
    content = f.read()

content = content.replace('tt( `', 't(locale, `')

with open('app/page.tsx', 'w') as f:
    f.write(content)

print("i18n backticks fixed!")
