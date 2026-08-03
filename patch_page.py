import re

with open("/home/xumoyun-maxkamov/Desktop/diamond-site/app/page.tsx", "r") as f:
    content = f.read()

# First we need to find the `let content: React.ReactNode;` line and the two blocks.
# The structure is:
#   let content: React.ReactNode;
#   if (!user) { ... } else if (isStudentRole ... ) { ... }
#   ...
#   } else if (
#     typeof window !== "undefined" &&
#     (window.Telegram?.WebApp?.initDataUnsafe?.start_param?.startsWith("survey_") ||
#      new URLSearchParams(window.location.search).get("startapp")?.startsWith("survey_"))
#   ) { ... } else { content = ( <DashboardShell ... /> ) }

import sys
parts = content.split("let content: React.ReactNode;")
if len(parts) != 2:
    print("Could not find 'let content: React.ReactNode;'")
    sys.exit(1)

pre = parts[0]
post = parts[1]

# We want to extract the entire survey block
pattern = re.compile(
    r'(\} else if \(\s*typeof window !== "undefined" &&\s*\(window\.Telegram\?\.WebApp\?\.initDataUnsafe\?\.start_param\?\.startsWith\("survey_"\) \|\|\s*new URLSearchParams\(window\.location\.search\)\.get\("startapp"\)\?\.startsWith\("survey_"\)\)\s*\) \{\s*const startAppParam = new URLSearchParams\(window\.location\.search\)\.get\("startapp"\) \|\| "";\s*const tgStartParam = window\.Telegram\?\.WebApp\?\.initDataUnsafe\?\.start_param \|\| "";\s*const activeSurveyParam = tgStartParam\.startsWith\("survey_"\) \? tgStartParam : startAppParam;\s*const surveyId = activeSurveyParam\.replace\("survey_", ""\);\s*content = \(\s*<StudentSurveyScreen\s*user=\{user\}\s*surveyId=\{surveyId\}\s*onFinish=\{.*?\}\s*/>\s*\);\s*)(\} else \{)'
, re.DOTALL)

match = pattern.search(post)
if not match:
    print("Could not find survey block")
    sys.exit(1)

survey_block = match.group(1)
post = post[:match.start()] + match.group(2) + post[match.end():]

# Now insert the survey block right after `let content: React.ReactNode;`
# But we have to adjust `} else if` to `if` and the original `if (!user)` to `} else if (!user)`

new_survey_block = survey_block.replace("} else if (", "if (", 1)
post = post.replace("if (!user) {", "} else if (!user) {", 1)

final_content = pre + "let content: React.ReactNode;\n  " + new_survey_block + post

with open("/home/xumoyun-maxkamov/Desktop/diamond-site/app/page.tsx", "w") as f:
    f.write(final_content)

print("Patched successfully")
