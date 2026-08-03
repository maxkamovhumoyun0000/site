import sys
sys.path.append("/home/xumoyun-maxkamov/Desktop/diamond-site")
from db import lesson_is_slot_free_for_subject, get_conn
print(lesson_is_slot_free_for_subject("English", "2026-07-13", "14:00"))
