import re

with open("db.py", "r") as f:
    lines = f.readlines()

in_func = False
for i, line in enumerate(lines):
    if line.startswith("def ensure_video_teachers_schema() -> None:"):
        in_func = True
    elif in_func and line.startswith("def "):
        in_func = False

    if in_func:
        if "except Exception:" in line:
            # check if next line is pass
            if i + 1 < len(lines) and "pass" in lines[i+1]:
                # replace pass with rollback then pass
                indent = lines[i+1][:len(lines[i+1]) - len(lines[i+1].lstrip())]
                lines[i+1] = f"{indent}try:\n{indent}    conn.rollback()\n{indent}except Exception:\n{indent}    pass\n"
        
        # Also remove the rogue conn.commit() and conn.close() at the beginning
        if "conn.commit()" in line and i < 6750: # The rogue one is around 6746
            lines[i] = ""
        if "conn.close()" in line and i < 6750:
            lines[i] = ""

with open("db.py", "w") as f:
    f.writelines(lines)
