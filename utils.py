import os
from urllib.parse import quote, urlencode

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from i18n import t, detect_lang_from_user


def _miniapp_url(role: str, section: str, extra: dict | None = None) -> str | None:
    base = (os.getenv("TELEGRAM_MINI_APP_BASE_URL") or "").strip()
    if not base:
        # Keep the same production-safe fallback used by student_bot.py.
        base = "https://diamond-education.uz"
    if base and not base.lower().startswith(("http://", "https://")):
        base = f"https://{base.lstrip('/')}"
    if not base:
        return None
    params = {"role": role, "section": section}
    if extra:
        params.update({k: v for k, v in extra.items() if v is not None})
    sep = "&" if "?" in base else "?"
    return f"{base.rstrip('/')}{sep}{urlencode(params)}"


def _webapp_reply_button(text: str, role: str, section: str, extra: dict | None = None) -> KeyboardButton:
    url = _miniapp_url(role, section, extra)
    if not url:
        return KeyboardButton(text=text)
    return KeyboardButton(text=text, web_app=WebAppInfo(url=url))

def cancel_keyboard(lang='uz'):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t(lang, 'btn_cancel'))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_main_keyboard(lang='uz'):
    labels = {
        'new_user': t(lang, 'choose_user_type'),
        'results': t(lang, 'admin_results_btn'),
        'students': t(lang, 'students_list_title'),
        'teachers': t(lang, 'teachers_list_title'),
        'groups': t(lang, 'groups_menu'),
        'attendance': t(lang, 'admin_attendance_btn'),
        'vocab_io': t(lang, 'admin_vocab_io_btn'),
        'ai_menu': t(lang, 'admin_ai_menu_btn'),
        'export_all': t(lang, 'admin_export_xlsx_btn'),
        'dcoin_lb': t(lang, 'admin_dcoin_leaderboard_btn'),
    }
    return ReplyKeyboardMarkup(
        keyboard=[
            [_webapp_reply_button('➕ ' + labels['new_user'], "admin", "users"), KeyboardButton(text='👥 ' + labels['students'])],
            [KeyboardButton(text='👨‍🏫 ' + labels['teachers']), KeyboardButton(text='👥 ' + labels['groups'])],
            [KeyboardButton(text=labels['attendance']), KeyboardButton(text=t(lang, 'admin_cancel_lessons_btn'))],
            [KeyboardButton(text=labels['vocab_io']), KeyboardButton(text='📊 ' + labels['results'])],
            [_webapp_reply_button('💳 ' + t(lang, 'payments_btn'), "admin", "payments"), KeyboardButton(text=labels['dcoin_lb'])],
            [KeyboardButton(text=labels['ai_menu']), KeyboardButton(text=labels['export_all'])],
            [KeyboardButton(text='🌐 ' + t(lang, 'choose_lang'))],
        ],
        resize_keyboard=True,
    )


def create_user_type_keyboard(lang='uz'):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='👨‍🎓 ' + t(lang, 'new_student_with_test'), callback_data='user_type_1'),
            InlineKeyboardButton(text='👨‍🎓 ' + t(lang, 'existing_student_no_test'), callback_data='user_type_2')
        ],
        [InlineKeyboardButton(text='👨‍🏫 ' + t(lang, 'user_type_teacher'), callback_data='user_type_3')],
    ])


def create_subject_keyboard(lang='uz'):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'english_subject'), callback_data='subject_English')],
        [InlineKeyboardButton(text=t(lang, 'russian_subject'), callback_data='subject_Russian')],
        [InlineKeyboardButton(text=t(lang, 'matematika_subject'), callback_data='subject_Matematika')],
        [InlineKeyboardButton(text=t(lang, 'onatili_subject'), callback_data='subject_Ona tili')],
        [InlineKeyboardButton(text=t(lang, 'tarix_subject'), callback_data='subject_Tarix')],
        [InlineKeyboardButton(text=t(lang, 'arabtili_subject'), callback_data='subject_Arab tili')],
    ])


def create_dual_choice_keyboard(prefix="test", lang='uz'):
    """Foydalanuvchiga ingliz, rus yoki boshqa fanlarni tanlash uchun tugmalar"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'english_subject'), callback_data=f'{prefix}_English')],
        [InlineKeyboardButton(text=t(lang, 'russian_subject'), callback_data=f'{prefix}_Russian')],
        [InlineKeyboardButton(text=t(lang, 'matematika_subject'), callback_data=f'{prefix}_Matematika')],
        [InlineKeyboardButton(text=t(lang, 'onatili_subject'), callback_data=f'{prefix}_Ona tili')],
        [InlineKeyboardButton(text=t(lang, 'tarix_subject'), callback_data=f'{prefix}_Tarix')],
        [InlineKeyboardButton(text=t(lang, 'arabtili_subject'), callback_data=f'{prefix}_Arab tili')],
    ])


def create_leaderboard_pagination_keyboard(current_page, total_pages, filter_type='global', lang='uz'):
    """Reyting sahifasini navigatsiya qilish uchun tugmalar (sahifa raqami callback_data da)."""
    enc = quote(filter_type, safe='')
    keyboard = []
    nav = []
    if current_page > 0:
        nav.append(InlineKeyboardButton(
            text=t(lang, 'btn_prev'),
            callback_data=f'lbprv|{current_page}|{enc}',
        ))
    if current_page < total_pages - 1:
        nav.append(InlineKeyboardButton(
            text=t(lang, 'btn_next'),
            callback_data=f'lbnext|{current_page}|{enc}',
        ))

    if nav:
        keyboard.append(nav)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def student_main_keyboard(lang='uz'):
    return ReplyKeyboardMarkup(
        keyboard=[
            [_webapp_reply_button('📚 ' + t(lang, 'grammar_rules'), "student", "grammar", {"auto_join": 1}), KeyboardButton(text='📊 ' + t(lang, 'progress'))],
            [KeyboardButton(text='💎 ' + t(lang, 'leaderboard')), KeyboardButton(text=t(lang, 'student_dcoin_btn'))],
            [_webapp_reply_button('📖 ' + t(lang, 'vocab_menu'), "student", "vocabulary-process", {"auto_join": 1}), _webapp_reply_button(t(lang, 'daily_test_btn'), "student", "daily-test-process", {"auto_join": 1})],
            [_webapp_reply_button('⚔️ ' + t(lang, 'menu_arena'), "student", "arena", {"arena_mode": "arena", "auto_join": 1})],
            [KeyboardButton(text='🆘 ' + t(lang, 'support_menu_btn'))],
            [KeyboardButton(text='👤 ' + t(lang, 'my_profile'))],
        ],
        resize_keyboard=True,
    )


def student_vocab_keyboard(lang='uz'):
    return ReplyKeyboardMarkup(
        keyboard=[
            [_webapp_reply_button('🔎 ' + t(lang, 'vocab_search_btn'), "student", "vocabulary-process", {"auto_join": 1}), _webapp_reply_button('🧠 ' + t(lang, 'vocab_quiz_btn'), "student", "vocabulary-process", {"auto_join": 1})],
            [_webapp_reply_button('⚙️ ' + t(lang, 'vocab_pref_btn'), "student", "vocabulary-process", {"auto_join": 1})],
            [KeyboardButton(text='⬅️ ' + t(lang, 'back_btn'))],
        ],
        resize_keyboard=True,
    )


def teacher_main_keyboard(lang='uz'):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, 'teacher_attendance_btn'))],
            [KeyboardButton(text=t(lang, 'teacher_vocab_io_btn'))],
            [KeyboardButton(text='⚔️ ' + t(lang, 'menu_arena')), KeyboardButton(text=t(lang, 'teacher_dcoin_leaderboard_btn'))],
            [KeyboardButton(text=t(lang, 'teacher_temp_share_btn'))],
            [KeyboardButton(text='👤 ' + t(lang, 'my_profile')), KeyboardButton(text='🌐 ' + t(lang, 'choose_lang'))],
        ],
        resize_keyboard=True,
    )


def create_group_action_keyboard(lang='uz'):
    """Adminning guruh boshqarish menyu"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='➕ ' + t(lang, 'group_create_btn'), callback_data='group_create')],
        [InlineKeyboardButton(text='👥 ' + t(lang, 'group_list_btn'), callback_data='group_list')],
        [InlineKeyboardButton(text=t(lang, 'admin_broadcast_btn'), callback_data='broadcast_start')],
    ])


def create_group_list_keyboard(groups, lang='uz'):
    """Guruhlar ro'yxati uchun buttons"""
    buttons = []
    for g in groups:
        user_count = len(g.get('users', []))
        text = f"{g['name']} ({t(lang, 'ask_group_level')} {g['level']}) - {user_count} {t(lang, 'students_list_title').split()[0]}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f'group_select_{g["id"]}')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_teacher_selection_keyboard(teachers, lang='uz'):
    """O'qituvchi tanlash uchun buttons"""
    buttons = []
    for teacher in teachers:
        name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}"
        buttons.append([
            InlineKeyboardButton(text=name, callback_data=f'teacher_select_{teacher["id"]}'),
            InlineKeyboardButton(text=t(lang, 'admin_teacher_reset_pw_btn'), callback_data=f'teacher_reset_{teacher["id"]}')
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_group_teacher_selection_keyboard(teachers, lang='uz'):
    """Guruh yaratish uchun o'qituvchi tanlash (password reset tugmasiz)"""
    buttons = []
    for teacher in teachers:
        name = f"{teacher.get('first_name', '')} {teacher.get('last_name', '')}"
        buttons.append([InlineKeyboardButton(
            text=name,
            callback_data=f'group_teacher_select_{teacher["id"]}'
        )])
    buttons.append([InlineKeyboardButton(
        text=t(lang, 'admin_btn_create_without_teacher'),
        callback_data='create_group_no_teacher'
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_user_selection_keyboard(users, group_id=None):
    """O'quvchi tanlash uchun buttons"""
    buttons = []
    for u in users:
        name = f"{u.get('first_name', '')} {u.get('last_name', '')}"
        callback = f'add_user_to_group_{group_id}_{u["id"]}' if group_id else f'select_user_{u["id"]}'
        buttons.append([InlineKeyboardButton(text=name, callback_data=callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_user_selection_keyboard_by_type(users, group_id=None, lang='uz'):
    """Show users in separate columns by type (teachers and students)"""
    teachers = []
    students = []
    for u in users:
        name = f"{u.get('first_name', '')} {u.get('last_name', '')}"
        if u.get('login_type') == 3:
            teachers.append((u, name))
        else:
            students.append((u, name))

    buttons = []
    if teachers:
        buttons.append([InlineKeyboardButton(text=t(lang, 'admin_section_teachers'), callback_data='noop')])
        for u, name in teachers:
            callback = f'add_user_to_group_{group_id}_{u["id"]}' if group_id else f'select_user_{u["id"]}'
            buttons.append([InlineKeyboardButton(text=f"👨‍🏫 {name}", callback_data=callback)])
    if students:
        if teachers:
            buttons.append([InlineKeyboardButton(text="───", callback_data='noop')])
        buttons.append([InlineKeyboardButton(text=t(lang, 'admin_section_students'), callback_data='noop')])
        for u, name in students:
            callback = f'add_user_to_group_{group_id}_{u["id"]}' if group_id else f'select_user_{u["id"]}'
            buttons.append([InlineKeyboardButton(text=f"👨‍🎓 {name}", callback_data=callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def create_language_selection_keyboard_for_user(user_id, lang='uz'):
    """Create inline keyboard for selecting language for a specific user id"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'lang_btn_uz'), callback_data=f'set_lang_uz_{user_id}')],
        [InlineKeyboardButton(text=t(lang, 'lang_btn_ru'), callback_data=f'set_lang_ru_{user_id}')],
        [InlineKeyboardButton(text=t(lang, 'lang_btn_en'), callback_data=f'set_lang_en_{user_id}')],
    ])

def create_language_selection_keyboard_for_self(lang='uz'):
    """Create inline keyboard for user to set their own language (callbacks handled in student/teacher bots)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, 'lang_btn_uz'), callback_data='set_lang_me_uz')],
        [InlineKeyboardButton(text=t(lang, 'lang_btn_ru'), callback_data='set_lang_me_ru')],
        [InlineKeyboardButton(text=t(lang, 'lang_btn_en'), callback_data='set_lang_me_en')],
    ])
