import re

with open("backend/main.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('"A1"', '"BEGINNER"')
content = content.replace('"A2"', '"ELEMENTARY"')
content = content.replace('"B1"', '"PRE-INTERMEDIATE"')
content = content.replace('"B2"', '"INTERMEDIATE"')
content = content.replace('"C1"', '"UPPER-INTERMEDIATE"')
content = content.replace('"C2"', '"ADVANCED"')

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
