import re

with open("backend/main.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace set literals
old_set = r'\{"A1", "A2", "B1", "B2", "C1"\}'
new_set = '{"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"}'
content = re.sub(old_set, new_set, content)

old_set_mixed = r'\{"A1", "A2", "B1", "B2", "C1", "MIXED"\}'
new_set_mixed = '{"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED", "MIXED"}'
content = re.sub(old_set_mixed, new_set_mixed, content)

old_set_russian = r'\{"A1", "A2", "B1", "B2"\}'
new_set_russian = '{"BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE"}'
content = re.sub(old_set_russian, new_set_russian, content)

# Replace tuple literals
old_tuple = r'\("A1", "A2", "B1", "B2", "C1"\)'
new_tuple = '("BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED")'
content = re.sub(old_tuple, new_tuple, content)

# Replace list literals
old_list = r'\["A1", "A2", "B1", "B2", "C1"\]'
new_list = '["BEGINNER", "ELEMENTARY", "PRE-INTERMEDIATE", "INTERMEDIATE", "UPPER-INTERMEDIATE", "ADVANCED"]'
content = re.sub(old_list, new_list, content)

# Replace defaults
content = re.sub(r'default="A1"', 'default="BEGINNER"', content)
content = re.sub(r'or "A1"\)', 'or "BEGINNER")', content)
content = re.sub(r'="A1"', '="BEGINNER"', content)

# Dictionary order
old_cefr_order = r'\{"A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5, "MIXED": 6\}'
new_cefr_order = '{"BEGINNER": 0, "ELEMENTARY": 1, "PRE-INTERMEDIATE": 2, "INTERMEDIATE": 3, "UPPER-INTERMEDIATE": 4, "ADVANCED": 5, "MIXED": 6}'
content = re.sub(old_cefr_order, new_cefr_order, content)

with open("backend/main.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
