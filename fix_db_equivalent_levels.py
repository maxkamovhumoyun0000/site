import re

with open("db.py", "r", encoding="utf-8") as f:
    content = f.read()

func_code = """
def get_equivalent_levels(level: str | None) -> list[str]:
    raw = str(level or "").strip().upper()
    mapping = {
        "A1": ["A1", "BEGINNER"],
        "BEGINNER": ["A1", "BEGINNER"],
        "A2": ["A2", "ELEMENTARY"],
        "ELEMENTARY": ["A2", "ELEMENTARY"],
        "B1": ["B1", "PRE-INTERMEDIATE"],
        "PRE-INTERMEDIATE": ["B1", "PRE-INTERMEDIATE"],
        "B2": ["B2", "INTERMEDIATE"],
        "INTERMEDIATE": ["B2", "INTERMEDIATE"],
        "C1": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
        "UPPER-INTERMEDIATE": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
        "C2": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
        "ADVANCED": ["C1", "UPPER-INTERMEDIATE", "ADVANCED"],
    }
    return mapping.get(raw, [raw])
"""

if "def get_equivalent_levels" not in content:
    content = content.replace("def get_vocab_allowed_levels_for_user", func_code + "\ndef get_vocab_allowed_levels_for_user")

with open("db.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
