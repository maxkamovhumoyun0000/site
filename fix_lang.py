import os
import glob

files = glob.glob("**/*.py", recursive=True)
count = 0
for f in files:
    try:
        with open(f, 'r') as file:
            content = file.read()
        if '.get("language")' in content or ".get('language')" in content:
            print(f"Fixing {f}")
            content = content.replace('.get("language")', '.get("language")')
            content = content.replace(".get('language')", ".get('language')")
            with open(f, 'w') as file:
                file.write(content)
            count += 1
    except Exception as e:
        print(f"Error reading {f}: {e}")
print(f"Fixed {count} files")
