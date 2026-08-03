import re

with open("backend/main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Make all level validation sets include the old codes as well
# e.g., {"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"}
# -> {"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED", "A1", "A2", "B1", "B2", "C1"}

old_set = r'\{"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"\}'
new_set = '{"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED", "A1", "A2", "B1", "B2", "C1"}'
content = re.sub(old_set, new_set, content)

old_set_mixed = r'\{"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED", "MIXED"\}'
new_set_mixed = '{"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED", "A1", "A2", "B1", "B2", "C1", "MIXED"}'
content = re.sub(old_set_mixed, new_set_mixed, content)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
