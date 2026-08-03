import re
with open('app/globals.css', 'r') as f:
    css = f.read()

# Replace mobile group-roster-scroll
css = css.replace('max-height: 280px !important;\n    overflow-x: auto !important;\n    overflow-y: auto !important;', 'max-height: none !important;\n    overflow-x: auto !important;\n    overflow-y: visible !important;')

# Replace xs mobile
css = css.replace('max-height: 220px !important;', 'max-height: none !important;')
css = css.replace('max-height: 160px !important;', 'max-height: none !important;')

with open('app/globals.css', 'w') as f:
    f.write(css)
print("CSS fixed")
