import json
import re

file_path = "/home/jus1-bea1s/Desktop/diamond site/app/ui/web-i18n.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

new_keys_uz = {
    "landing.whyUs.kicker": "Nega Biz",
    "landing.whyUs.title": "O'lchanadigan o'sish uchun yaratilgan",
}

new_keys_ru = {
    "landing.whyUs.kicker": "Почему мы",
    "landing.whyUs.title": "Создано для измеримого роста",
}

new_keys_en = {
    "landing.whyUs.kicker": "Why Us",
    "landing.whyUs.title": "Built for measurable growth",
}

def format_keys(keys_dict):
    return ",\n".join([f'    "{k}": "{v}"' for k, v in keys_dict.items()]) + ",\n  "

def inject_keys(text, locale, new_keys):
    pattern = rf'({locale}:\s*{{)'
    return re.sub(pattern, r'\1\n' + format_keys(new_keys).replace("\\", "\\\\"), text)

content = inject_keys(content, "uz", new_keys_uz)
content = inject_keys(content, "ru", new_keys_ru)
content = inject_keys(content, "en", new_keys_en)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("done")
