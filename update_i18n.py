import re

with open("i18n.py", "r") as f:
    content = f.read()

uz_add = """
        'notification_homework_reviewed': "Homework tekshirildi: {title}\\nStatus: {status}\\nD'point: {delta}",
        'homework_status_done': "Bajarildi",
        'homework_status_not_done': "Bajarilmadi",
        'homework_btn_open': "Homeworkni ochish",
"""

ru_add = """
        'notification_homework_reviewed': "Домашнее задание проверено: {title}\\nСтатус: {status}\\nD'point: {delta}",
        'homework_status_done': "Выполнено",
        'homework_status_not_done': "Не выполнено",
        'homework_btn_open': "Открыть дз",
"""

en_add = """
        'notification_homework_reviewed': "Homework checked: {title}\\nStatus: {status}\\nD'point: {delta}",
        'homework_status_done': "Done",
        'homework_status_not_done': "Not done",
        'homework_btn_open': "Open homework",
"""

content = content.replace("'notification_new_homework': \"Yangi homework: {title}\\nO'qituvchi: {teacher_name}\",", "'notification_new_homework': \"Yangi homework: {title}\\nO'qituvchi: {teacher_name}\"," + uz_add)
content = content.replace("'notification_new_homework': \"Новое домашнее задание: {title}\\nУчитель: {teacher_name}\",", "'notification_new_homework': \"Новое домашнее задание: {title}\\nУчитель: {teacher_name}\"," + ru_add)
content = content.replace("'notification_new_homework': \"New homework: {title}\\nTeacher: {teacher_name}\",", "'notification_new_homework': \"New homework: {title}\\nTeacher: {teacher_name}\"," + en_add)

with open("i18n.py", "w") as f:
    f.write(content)
