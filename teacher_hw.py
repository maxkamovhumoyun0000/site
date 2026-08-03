import json
import re
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, Message, CallbackQuery
from auth import detect_lang_from_user
from i18n import t
from db import get_user_by_telegram, get_group, create_homework, save_content_test
from diamondvoy_helpers import diamondvoy_gemini_answer, extract_diamondvoy_query_anywhere
from datetime import datetime
from teacher_bot import _teacher_keyboard

def _format_tests(tests: list) -> str:
    if not tests: return ""
    lines = []
    for i, t in enumerate(tests):
        q = t.get('q', '')
        opts = t.get('options', [])
        idx = t.get('correct_idx', 0)
        lines.append(f"{i+1}. {q}")
        labels = ['A', 'B', 'C', 'D']
        for j, opt in enumerate(opts):
            if j < 4:
                lines.append(f"{labels[j]}) {opt}")
        correct = labels[idx] if 0 <= idx < len(labels) else '?'
        lines.append(f"✅ To'g'ri: {correct}")
        lines.append("")
    return "\n".join(lines).strip()

async def handle_teacher_diamondvoy_text(message: Message, state_dict: dict, bot):
    chat_id = message.chat.id
    text = message.text or ""
    query = extract_diamondvoy_query_anywhere(text)
    lower_query = query.lower()

    if not state_dict.get('step') or not str(state_dict.get('step')).startswith('dhw_'):
        # Check if intent is homework creation
        if "vazifa" in lower_query or "homework" in lower_query or "uy ish" in lower_query or "uy vazifasi" in lower_query:
            state_dict['step'] = 'dhw_group'
            state_dict['data'] = {'homework_mode': True}
            
            user = get_user_by_telegram(str(message.from_user.id))
            from db import get_groups_by_teacher
            teacher_groups = get_groups_by_teacher(user.get("id"))
            
            if not teacher_groups:
                await message.answer("Sizga biriktirilgan guruhlar topilmadi. Avval guruh oching.")
                state_dict['step'] = None
                return

            kb = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=f"Guruh: {g.get('name')}")] for g in teacher_groups[:10]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await message.answer(
                "🤖 Zo'r! Qaysi guruhga vazifa bermoqchisiz? Quyidagi guruhlardan birini tanlang:",
                reply_markup=kb
            )
            return
            
        else:
            # Generic response
            lang = detect_lang_from_user(get_user_by_telegram(str(message.from_user.id)) or message.from_user)
            from diamondvoy_helpers import stream_diamondvoy_text_reply
            user = get_user_by_telegram(str(message.from_user.id))
            subjects = [user.get("subject") or "English"] if user else ["English"]
            
            status_msg = await message.answer("O'ylab ko'ryapman...")
            answer = await diamondvoy_gemini_answer(query, subjects, lang=lang, is_admin_context=True)
            await stream_diamondvoy_text_reply(bot, message.chat.id, answer, lang=lang, message_id=status_msg.message_id)
            return

    # If we are in homework flow
    step = state_dict.get('step')

    if step == 'dhw_group':
        user = get_user_by_telegram(str(message.from_user.id))
        from db import get_groups_by_teacher
        teacher_groups = get_groups_by_teacher(user.get("id"))
        
        selected_name = text.replace("Guruh: ", "").strip()
        matched_group = next((g for g in teacher_groups if g.get("name") == selected_name), None)
        
        if not matched_group:
            await message.answer("Bunday guruh topilmadi. Iltimos, pastdagi tugmalardan foydalaning.")
            return
            
        state_dict['data']['group_id'] = matched_group.get('id')
        state_dict['step'] = 'dhw_deadline'
        _set_web_hw_state(chat_id, state_dict)
        
        await message.answer(
            f"✅ Guruh tanlandi: {matched_group.get('name')}\n\nEndi vazifa uchun deadline (oxirgi muddat) ni yozing (masalan, 'Ertaga 20:00' yoki '15.10.2023 18:00'):",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    elif step == 'dhw_deadline':
        state_dict['data']['deadline'] = text
        state_dict['step'] = 'dhw_files'
        _set_web_hw_state(chat_id, state_dict)
        
        await message.answer(
            f"📅 Deadline qabul qilindi.\n\nEndi, o'quvchilar qanday turdagi fayllarni yuklay olishi kerak? (Rasm, Fayl, Ovozli xabar, Voice Room suhbati, yoki barchasi. Iltimos o'zingiz matn shaklida yozib qoldiring. Izoh qoldirish majburiy hisoblanadi):"
        )
        return

    elif step == 'dhw_files':
        # Analyze file requirements via LLM
        from ai_generator import _xai_generate_text
        import aiohttp
        prompt = f"""
        User replied with text about allowed file types for a homework assignment.
        Text: "{text}"
        
        Determine if the user wants to allow:
        - file (like PDF, Word, arbitrary files)
        - photo (images)
        - voice (voice messages/audio)
        - voiceroom (voice room, guruhli audio suhbat, conversation)
        
        Return exactly a JSON object with boolean values. Example:
        {{"file": true, "photo": false, "voice": true, "voiceroom": false}}
        ONLY RAW JSON NO MARKDOWN.
        """
        status = await message.answer("Talablaringiz o'qilmoqda...")
        try:
            async with aiohttp.ClientSession() as session:
                res = await _xai_generate_text(prompt, session=session)
            res = re.sub(r'```json', '', res)
            res = re.sub(r'```', '', res).strip()
            parsed = json.loads(res)
            
            state_dict['data']['req_file'] = bool(parsed.get('file', False))
            state_dict['data']['req_photo'] = bool(parsed.get('photo', False))
            state_dict['data']['req_voice'] = bool(parsed.get('voice', False))
            state_dict['data']['is_voiceroom'] = bool(parsed.get('voiceroom', False))
            
            kb = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="📝 O'zim Test qo'shish")],
                    [KeyboardButton(text="✨ AI Test yaratib bersin")],
                    [KeyboardButton(text="✅ Bo'ldi, homeworkni yubor")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            state_dict['step'] = 'dhw_tests_or_finish'
            _set_web_hw_state(chat_id, state_dict)
            await bot.edit_message_text(
                "✅ Fayl talablari saqlandi! Endi test qo'shishni xohlaysizmi yoki uy vazifasini o'zini yuboramizmi? Pastdagi tugmalardan tanlang yoki o'zingiz yozing.",
                chat_id=chat_id,
                message_id=status.message_id
            )
            await message.answer("Tanlang:", reply_markup=kb)
        except Exception as e:
            await bot.edit_message_text("Tushunmadim, iltimos boshqattan yozib yuboring (masalan: rasm va ovozli xabar)", chat_id=chat_id, message_id=status.message_id)
        return

    elif step == 'dhw_tests_or_finish':
        if "yubor" in lower_query or "boldi" in lower_query or "tayyor" in lower_query:
            await _publish_diamondvoy_hw(message, state_dict, bot)
        elif "yarat" in lower_query or "ai" in lower_query:
            state_dict['step'] = 'dhw_ai_test_gen'
            _set_web_hw_state(chat_id, state_dict)
            await message.answer("Men sizga test yaratib beraman. Qaysi mavzuda va nechta test kerak? (Masalan: 'Present Simple haqida 5 ta test')", reply_markup=ReplyKeyboardRemove())
        elif "o'zim" in lower_query or "qo'sh" in lower_query or "qosh" in lower_query:
            state_dict['step'] = 'dhw_wait_tests'
            _set_web_hw_state(chat_id, state_dict)
            await message.answer("Barcha testlarni yuboring (savol, variantlar, va hokazo). Har bir test uchun o'zining sekundi bo'lsa uni ham yozing (agar yozilmagan bo'lsa default 60 soniya olinadi). Men variantlarni o'zim ajratib olaman.", reply_markup=ReplyKeyboardRemove())
        else:
            await message.answer("Tushunmadim. Test qo'shishni xohlaysizmi yoki uy vazifasini o'zini yuboramizmi? 'boldi homeworklarni yubor' yozishingiz mumkin.")
        return

    elif step == 'dhw_wait_tests':
        from ai_generator import _xai_generate_text
        import aiohttp
        prompt = f"""
        Extract multiple choice tests from this text.
        Text: {text}
        
        Return a JSON array where each object has:
        - "q": string (the question)
        - "options": array of strings (A, B, C, D choices, just the text)
        - "correct_idx": integer (0, 1, 2, or 3) indicating the correct option. If not found, use 0.
        - "timer": integer (in seconds). If the text mentions a timer for this question, use it. Otherwise use 60.
        
        ONLY RETURN RAW JSON ARRAY. NO MARKDOWN.
        """
        status = await message.answer("Testlar tahlil qilinmoqda...")
        try:
            async with aiohttp.ClientSession() as session:
                res = await _xai_generate_text(prompt, session=session)
            res = re.sub(r'```json', '', res)
            res = re.sub(r'```', '', res).strip()
            tests = json.loads(res)
            
            existing_tests = state_dict['data'].get('tests', [])
            existing_tests.extend(tests)
            state_dict['data']['tests'] = existing_tests
            
            kb = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Bo'ldi, homeworkni yubor")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await bot.delete_message(chat_id=chat_id, message_id=status.message_id)
            await message.answer(
                f"✅ {len(tests)} ta test ajratib olindi! Jami testlar: {len(existing_tests)} ta.\n\n{_format_tests(tests)}\n\nHammasi tayyor bo'lsa 'bo'ldi homeworklarni yubor' deb yozing, yoki yana test yuboring.",
                reply_markup=kb
            )
        except Exception as e:
            await bot.edit_message_text(f"Xatolik yuz berdi: {e}. Iltimos qaytadan yuboring.", chat_id=chat_id, message_id=status.message_id)
        return

    elif step == 'dhw_ai_test_gen':
        from ai_generator import _xai_generate_text
        import aiohttp
        prompt = f"""
        Generate multiple choice tests for a school level student based on this request: "{text}".
        
        Return a JSON array where each object has:
        - "q": string (the question)
        - "options": array of strings (4 options)
        - "correct_idx": integer (0-3)
        - "timer": integer (default 60)
        
        ONLY RETURN RAW JSON ARRAY. NO MARKDOWN.
        """
        status = await message.answer("Testlar yaratilmoqda...")
        try:
            async with aiohttp.ClientSession() as session:
                res = await _xai_generate_text(prompt, session=session)
            res = re.sub(r'```json', '', res)
            res = re.sub(r'```', '', res).strip()
            tests = json.loads(res)
            
            state_dict['data']['tests'] = tests
            
            kb = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="✅ Bo'ldi, homeworkni yubor")]
                ],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            
            await bot.delete_message(chat_id=chat_id, message_id=status.message_id)
            await message.answer(
                f"✅ {len(tests)} ta test yaratildi! Ularni tekshirib chiqishingiz mumkin:\n\n{_format_tests(tests)}\n\nHammasi tayyor bo'lsa 'bo'ldi homeworklarni yubor' deb yozing.",
                reply_markup=kb
            )
            state_dict['step'] = 'dhw_tests_or_finish'
            _set_web_hw_state(chat_id, state_dict)
        except Exception as e:
            await bot.edit_message_text(f"Xatolik yuz berdi: {e}. Boshqacharoq yozib ko'ring.", chat_id=chat_id, message_id=status.message_id)
        return


async def handle_teacher_diamondvoy_callback(callback: CallbackQuery, state_dict: dict, bot):
    # Backward compatibility or catch if something slipped through
    await callback.answer("Iltimos, matn orqali davom eting.")


async def _publish_diamondvoy_hw(message: Message, state_dict: dict, bot):
    user = get_user_by_telegram(str(message.from_user.id))
    lang = detect_lang_from_user(user or message.from_user)
    group_id = state_dict['data'].get('group_id')
    deadline = state_dict['data'].get('deadline', 'Belgilanmagan')
    teacher_comment = state_dict['data'].get('comment', '')
    req_file = state_dict['data'].get('req_file', False)
    req_photo = state_dict['data'].get('req_photo', False)
    req_voice = state_dict['data'].get('req_voice', False)
    tests = state_dict['data'].get('tests', [])
    desc = f"Muddat (Deadline): {deadline}"
    if teacher_comment:
        desc += f"\nTopshiriq: {teacher_comment}"
    
    if req_file or req_photo or req_voice:
        desc += "\nMajburiy fayllar:"
        if req_file: desc += " [Fayl]"
        if req_photo: desc += " [Rasm]"
        if req_voice: desc += " [Ovozli xabar]"
        
    is_voiceroom = state_dict['data'].get('is_voiceroom', False)
    voiceroom_groups = []
    
    if is_voiceroom:
        from db import get_group_users
        import random
        users = get_group_users(group_id)
        student_ids = [u['id'] for u in users if u.get('role') == 'student']
        random.shuffle(student_ids)
        for i in range(0, len(student_ids), 3):
            chunk = student_ids[i:i+3]
            s1 = chunk[0]
            s2 = chunk[1] if len(chunk) > 1 else None
            s3 = chunk[2] if len(chunk) > 2 else None
            vg = {"student1_id": s1}
            if s2: vg["student2_id"] = s2
            if s3: vg["student3_id"] = s3
            voiceroom_groups.append(vg)
        
    if tests:
        homework_kind = "both" if (req_file or req_photo or req_voice) else "test"
    else:
        homework_kind = "list"
    hw = create_homework(
        teacher_id=user['id'],
        student_id=None,
        group_id=group_id,
        title="Diamondvoy Uy Vazifasi",
        description=desc,
        due_at=None,
        image_url=None,
        dcoin_effect=5.0,
        requires_voice_message=req_voice,
        requires_file=(req_file or req_photo),
        is_voiceroom=is_voiceroom,
        voiceroom_groups=voiceroom_groups,
        homework_kind=homework_kind
    )
    
    if not hw:
        await message.answer("Xatolik! Homework bazaga qo'shilmadi.", reply_markup=_teacher_keyboard(lang, user))
        return
        
    hw_id = hw.get("id")
    
    if tests:
        formatted_questions = []
        for i, t in enumerate(tests):
            formatted_questions.append({
                "id": i+1,
                "question": t.get("q", ""),
                "options": t.get("options", []),
                "correct_option_index": t.get("correct_idx", 0),
                "timer_seconds": t.get("timer", 60)
            })
            
        payload = {
            "questions": formatted_questions,
            "pass_percentage": 70,
            "dcoin_reward": 5.0,
            "time_limit_minutes": sum([q["timer_seconds"] for q in formatted_questions]) // 60 + 1
        }
        save_content_test(
            "homework", 
            hw_id, 
            json.dumps(payload), 
            user['id'], 
            title="Diamondvoy Testi", 
            created_by_role="teacher", 
            is_active=True
        )

    # Clear state
    state_dict['step'] = None
    state_dict['data'] = {}
    del _DIAMONDVOY_HW_STATE[message.chat.id]
    group = get_group(group_id)
    gname = group.get("name") if group else "Noma'lum"
    
    await _notify_students_homework(group_id, "Uy Vazifasi", desc)
    
    await message.answer(
        f"🎉 Tabriklayman! Uy vazifasi **{gname}** guruhiga muvaffaqiyatli yuborildi!\nJami testlar: {len(tests)}",
        reply_markup=_teacher_keyboard(lang, user)
    )

async def _notify_students_homework(group_id: int, hw_title: str, hw_desc: str):
    from db import get_conn
    from config import STUDENT_BOT_TOKEN
    import aiohttp
    
    if not STUDENT_BOT_TOKEN:
        return
        
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT u.telegram_id FROM users u JOIN user_groups ug ON u.id = ug.user_id WHERE ug.group_id=? AND u.telegram_id IS NOT NULL", (int(group_id),))
        rows = cur.fetchall()
        tids = [r.get("telegram_id") for r in rows if r.get("telegram_id")]
    finally:
        conn.close()
        
    if not tids:
        return
        
    msg = f"📚 <b>Yangi Uy Vazifasi!</b>\n\n<b>{hw_title}</b>\n\n{hw_desc}\n\n<i>Platformaga yoki botga kirib vazifani bajaring.</i>"
    
    async with aiohttp.ClientSession() as session:
        for tid in tids:
            url = f"https://api.telegram.org/bot{STUDENT_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": tid, "text": msg, "parse_mode": "HTML"}
            try:
                await session.post(url, json=payload)
            except:
                pass


_MESSAGES = {
    'uz': {
        'group_select': "👥 Qaysi guruhga vazifa bermoqchisiz? Qator raqamini yoki guruh nomini yozing:",
        'no_groups': "Sizda hech qanday guruh yo'q.",
        'deadline_prompt': "✅ Guruh tanlandi: {group_name}\n\n⏳ Endi vazifa uchun deadline (oxirgi muddat) ni yozing (masalan, 'Ertaga 20:00' yoki '15.10.2026 18:00'):\n\n[btn]Belgilanmagan[/btn] [btn]Ertaga 20:00[/btn]",
        'comment_prompt': "📅 Deadline qabul qilindi.\n\n📝 Endi, o'quvchilar uchun qanday topshiriq (komentariya) qoldirmoqchisiz? (Masalan: 'Kitobning 15-betidagi mashqlarni ishlash'):",
        'files_prompt': "✅ Komentariya qabul qilindi.\n\n📎 Endi, o'quvchilar qanday topshiriqlarni yuklay olishi kerak? (Tugma ustiga bossangiz tanlanadi):\n\n[btn]Fayl[/btn] [btn]Rasm[/btn] [btn]Ovozli xabar[/btn] [btn]Test[/btn]\n\n[btn]➡️ Davom etish[/btn]",
        'test_method': "✅ Fayl talablari saqlandi! Testni qanday yaratamiz?\n\n[btn]📝 O'zim Test qo'shish[/btn] [btn]✨ AI Test yaratib bersin[/btn]",
        'files_toggles': "Qaysi talablar bo'lishini tanlang (ustiga bossangiz o'zgaradi):\n\n{f} {r} {o} {t}\n\n[btn]➡️ Davom etish[/btn]",
        'test_ai_prompt': "🖼 Rasm yuklang (agar rasm asosida test kerak bo'lsa) yoki matn yozing (Masalan: 'Present Simple haqida 5 ta test')",
        'test_manual_prompt': "✍️ Barcha testlarni yuboring (savol, variantlar, va hokazo). Har bir test uchun o'zining sekundi bo'lsa uni ham yozing (agar yozilmagan bo'lsa default 60 soniya olinadi). Men variantlarni o'zim ajratib olaman.",
        'test_extracted': "✅ {count} ta test ajratib olindi! Jami testlar: {total} ta.\n\nHammasi tayyor bo'lsa 'bo'ldi homeworklarni yubor' tugmasini bosing, yoki yana test yuboring.\n\n[btn]✅ Bo'ldi, homeworkni yubor[/btn]",
        'test_generated': "✅ {count} ta test yaratildi! Ularni tekshirib chiqishingiz mumkin.\nHammasi tayyor bo'lsa 'bo'ldi homeworklarni yubor' tugmasini bosing.\n\n[btn]✅ Bo'ldi, homeworkni yubor[/btn]",
        'test_gen_error': "⚠️ Xatolik yuz berdi. Iltimos boshqacharoq yozib ko'ring yoki boshqa rasm yuklang.",
        'not_understood': "🤔 Tushunmadim. Test yaratishni xohlaysizmi yoki uy vazifasini o'zini yuboramizmi?\n\n[btn]📝 O'zim Test qo'shish[/btn] [btn]✨ AI Test yaratib bersin[/btn] [btn]✅ Bo'ldi, homeworkni yubor[/btn]"
    },
    'ru': {
        'group_select': "👥 Какой группе вы хотите дать домашнее задание? Напишите номер строки или название группы:",
        'no_groups': "У вас нет ни одной группы.",
        'deadline_prompt': "✅ Группа выбрана: {group_name}\n\n⏳ Теперь напишите дедлайн (крайний срок) для задания (например, 'Завтра 20:00'):\n\n[btn]Не указан[/btn] [btn]Завтра 20:00[/btn]",
        'comment_prompt': "📅 Дедлайн принят.\n\n📝 Теперь, какое задание (комментарий) вы хотите оставить для учеников? (Например: 'Решить упражнения на странице 15'):",
        'files_prompt': "✅ Комментарий принят.\n\n📎 Теперь выберите, какие файлы ученики должны загрузить? (Нажмите на кнопку для выбора):\n\n[btn]Файл[/btn] [btn]Фото[/btn] [btn]Голосовое сообщение[/btn] [btn]Тест[/btn]\n\n[btn]➡️ Продолжить[/btn]",
        'test_method': "✅ Требования к файлам сохранены! Как создадим тест?\n\n[btn]📝 Добавить тест самому[/btn] [btn]✨ Пусть AI создаст тест[/btn]",
        'files_toggles': "Выберите требования (нажмите для изменения):\n\n{f} {r} {o} {t}\n\n[btn]➡️ Продолжить[/btn]",
        'test_ai_prompt': "🖼 Загрузите фото или напишите текст (Например: '5 тестов по Present Simple')",
        'test_manual_prompt': "✍️ Отправьте все тесты (вопросы, варианты и т.д.).",
        'test_extracted': "✅ Извлечено {count} тестов! Всего тестов: {total}.\n\nЕсли всё готово, нажмите 'отправить домашнее задание'.\n\n[btn]✅ Отправить ДЗ[/btn]",
        'test_generated': "✅ Создано {count} тестов! Вы можете их проверить.\nЕсли всё готово, нажмите 'отправить ДЗ'.\n\n[btn]✅ Отправить ДЗ[/btn]",
        'test_gen_error': "⚠️ Произошла ошибка. Пожалуйста, попробуйте написать по-другому или загрузите другое фото.",
        'not_understood': "🤔 Не понял. Вы хотите создать тест или отправить само домашнее задание?\n\n[btn]📝 Добавить тест самому[/btn] [btn]✨ Пусть AI создаст тест[/btn] [btn]✅ Отправить ДЗ[/btn]"
    },
    'en': {
        'group_select': "👥 Which group do you want to assign homework to? Type the row number or group name:",
        'no_groups': "You don't have any groups.",
        'deadline_prompt': "✅ Group selected: {group_name}\n\n⏳ Now enter a deadline (e.g., 'Tomorrow 20:00'):\n\n[btn]Not set[/btn] [btn]Tomorrow 20:00[/btn]",
        'comment_prompt': "📅 Deadline accepted.\n\n📝 What instructions (comment) do you want to leave for the students?:",
        'files_prompt': "✅ Comment accepted.\n\n📎 What file types should students submit? (Click to select):\n\n[btn]File[/btn] [btn]Photo[/btn] [btn]Voice Message[/btn] [btn]Test[/btn]\n\n[btn]➡️ Continue[/btn]",
        'test_method': "✅ File requirements saved! How should we create the test?\n\n[btn]📝 Add Test Manually[/btn] [btn]✨ Let AI Generate[/btn]",
        'files_toggles': "Select requirements (click to toggle):\n\n{f} {r} {o} {t}\n\n[btn]➡️ Continue[/btn]",
        'test_ai_prompt': "🖼 Upload a photo or type text (e.g. '5 tests on Present Simple')",
        'test_manual_prompt': "✍️ Send all your tests (questions, options, etc.).",
        'test_extracted': "✅ Extracted {count} tests! Total tests: {total}.\n\nIf ready, click 'send homework'.\n\n[btn]✅ Send Homework[/btn]",
        'test_generated': "✅ Generated {count} tests! You can review them.\nIf ready, click 'send homework'.\n\n[btn]✅ Send Homework[/btn]",
        'test_gen_error': "⚠️ An error occurred. Please try rephrasing or upload a different image.",
        'not_understood': "🤔 I didn't understand. Create a test or submit homework?\n\n[btn]📝 Add Test Manually[/btn] [btn]✨ Let AI Generate[/btn] [btn]✅ Send Homework[/btn]"
    }
}

def _get_msg(lang: str, key: str, **kwargs):
    if lang not in _MESSAGES:
        lang = 'uz'
    msg = _MESSAGES[lang].get(key, _MESSAGES['uz'].get(key, ''))
    return msg.format(**kwargs)

import os
WEB_HW_STATE_DIR = "data/web_hw_state"
os.makedirs(WEB_HW_STATE_DIR, exist_ok=True)

def _get_web_hw_state(chat_id):
    path = os.path.join(WEB_HW_STATE_DIR, f"{chat_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return __import__('json').load(f)
        except:
            return None
    return None

def _set_web_hw_state(chat_id, state_dict):
    path = os.path.join(WEB_HW_STATE_DIR, f"{chat_id}.json")
    if state_dict is None:
        if os.path.exists(path):
            os.remove(path)
    else:
        with open(path, "w", encoding="utf-8") as f:
            __import__('json').dump(state_dict, f)

async def handle_web_diamondvoy_hw_fsm(user_id, chat_id, text, image_urls, role, lang="uz"):
    if role not in ("teacher", "support", "admin"): return None
    text = (text or "").strip()
    lower_query = text.lower()
    
    if "vazifa" in lower_query or "homework" in lower_query or "uy ish" in lower_query or "uy vazifasi" in lower_query:
        # Eski holatlarni tozalash
        _set_web_hw_state(chat_id, None)
        return '{"type": "wizard_trigger", "wizard": "homework"}'
        
    # Agar state qolib ketgan bo'lsa uni ham tozalaymiz
    state_dict = _get_web_hw_state(chat_id)
    if state_dict:
        _set_web_hw_state(chat_id, None)
        
    return None

