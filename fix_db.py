with open("db.py", "r") as f:
    lines = f.readlines()

in_func = False
for i in range(len(lines)):
    if lines[i].startswith("def ensure_video_teachers_schema() -> None:"):
        in_func = True
    elif in_func and lines[i].startswith("def "):
        in_func = False
        
    if in_func:
        if "cur.execute('''" in lines[i] or "cur.execute(\"\"\"" in lines[i] or "cur.execute(\"ALTER" in lines[i] or "cur.execute('CREATE" in lines[i]:
            # if previous line is not try
            if i > 0 and "try:" not in lines[i-1] and "try:" not in lines[i-2]:
                indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
                lines[i] = f"{indent}try:\n    {lines[i]}"
                # we need to find the end of the execute block
                j = i + 1
                while j < len(lines):
                    if lines[j].strip().startswith("')") or lines[j].strip().startswith("')\"") or lines[j].strip() == "''')" or lines[j].strip() == ")\n" or lines[j].strip() == "')\n" or lines[j].strip() == "''')\n" or "')" in lines[j] or "''')" in lines[j] or "\"\"\")" in lines[j]:
                        # add except
                        lines[j] = f"    {lines[j]}{indent}except Exception:\n{indent}    try:\n{indent}        conn.rollback()\n{indent}    except Exception:\n{indent}        pass\n"
                        break
                    # indent the content
                    lines[j] = f"    {lines[j]}"
                    j += 1
