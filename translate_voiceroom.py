import os
import re

files_to_check = [
    "/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/student-voice-room.tsx",
    "/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/moderator-voice-room.tsx",
    "/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/use-voice-room.ts",
    "/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/voice-room/GlobalVoiceRoomContext.tsx",
]

replacements = [
    (r'"Failed to update room name"', r't("voiceroom.editNameFailed") || "Failed to update room name"'),
    (r'"Network error"', r't("common.networkError") || "Network error"'),
    (r'<h1>Voice Rooms</h1>', r'<h1>{t("voiceroom.title") || "Voice Rooms"}</h1>'),
    (r'>Voice Rooms<', r'>{t("voiceroom.title") || "Voice Rooms"}<'),
    (r'placeholder="e.g. English Speaking Club"', r'placeholder={t("voiceroom.name_placeholder") || "e.g. English Speaking Club"}'),
    (r'title="Start Game"', r'title={t("voiceroom.startGame") || "Start Game"}'),
    (r'title="End Room"', r'title={t("voiceroom.closeRoom") || "End Room"}'),
    (r'"Room"', r't("voiceroom.default_room") || "Room"'),
    (r'"User"', r't("voiceroom.user") || "User"'),
    (r'"Speaker"', r't("voiceroom.speaker") || "Speaker"'),
    (r'Replying to ', r'{t("voiceroom.replying_to") || "Replying to "} '),
]

for file_path in files_to_check:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
        
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {file_path}")

# Now let's update web-i18n.tsx
i18n_file = "/home/xumoyun-maxkamov/Desktop/diamond-site/app/ui/web-i18n.tsx"
with open(i18n_file, 'r', encoding='utf-8') as f:
    i18n_content = f.read()

new_keys = {
    'uz': '''    "voiceroom.editNameFailed": "Xona nomini o'zgartirish muvaffaqiyatsiz tugadi",
    "common.networkError": "Tarmoq xatosi",
    "voiceroom.title": "Voice Rooms",
    "voiceroom.name_placeholder": "masalan, English Speaking Club",
    "voiceroom.startGame": "O'yinni boshlash",
    "voiceroom.closeRoom": "Xonani yopish",
    "voiceroom.default_room": "Xona",
    "voiceroom.user": "Foydalanuvchi",
    "voiceroom.speaker": "Speaker",
    "voiceroom.replying_to": "Javob berilmoqda",
''',
    'ru': '''    "voiceroom.editNameFailed": "Не удалось обновить название комнаты",
    "common.networkError": "Ошибка сети",
    "voiceroom.title": "Voice Rooms",
    "voiceroom.name_placeholder": "например, English Speaking Club",
    "voiceroom.startGame": "Начать игру",
    "voiceroom.closeRoom": "Закрыть комнату",
    "voiceroom.default_room": "Комната",
    "voiceroom.user": "Пользователь",
    "voiceroom.speaker": "Спикер",
    "voiceroom.replying_to": "Ответ пользователю",
''',
    'en': '''    "voiceroom.editNameFailed": "Failed to update room name",
    "common.networkError": "Network error",
    "voiceroom.title": "Voice Rooms",
    "voiceroom.name_placeholder": "e.g. English Speaking Club",
    "voiceroom.startGame": "Start Game",
    "voiceroom.closeRoom": "Close Room",
    "voiceroom.default_room": "Room",
    "voiceroom.user": "User",
    "voiceroom.speaker": "Speaker",
    "voiceroom.replying_to": "Replying to",
'''
}

# The dictionary in web-i18n.tsx has blocks for uz, ru, en
for lang in ['uz', 'ru', 'en']:
    # We find the end of the dictionary for this lang by looking for the NEXT lang key or end of WEB_MESSAGES
    # A bit risky with regex, better to just inject before `  },\n  ru: {` or similar.
    search_str = f"  {lang}: {{\n"
    if search_str in i18n_content:
        # Check if we already injected
        if "voiceroom.editNameFailed" not in i18n_content.split(search_str)[1][:1000]:
            i18n_content = i18n_content.replace(search_str, search_str + new_keys[lang])
            
with open(i18n_file, 'w', encoding='utf-8') as f:
    f.write(i18n_content)
print("Updated web-i18n.tsx")
