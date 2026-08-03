import re

with open('backend/main.py', 'r') as f:
    content = f.read()

# 1. Update _payment_status_text signature and implementation
new_status_text = """def _payment_status_text(status: Any, lang: str = "uz") -> str:
    raw = str(status or "").strip()
    lowered = raw.lower()
    
    if lang == "ru":
        if "kechik" in lowered or lowered == PAYMENT_STATUS_OVERDUE.lower(): return f"⚠️ Просрочено"
        if "qisman" in lowered: return f"🟡 Частично"
        if "ortiqcha" in lowered: return f"🔵 Переплата"
        if "to'langan" in lowered or "tolangan" in lowered: return f"✅ Оплачено"
        return f"❌ Не оплачено"
    elif lang == "en":
        if "kechik" in lowered or lowered == PAYMENT_STATUS_OVERDUE.lower(): return f"⚠️ Overdue"
        if "qisman" in lowered: return f"🟡 Partially paid"
        if "ortiqcha" in lowered: return f"🔵 Overpaid"
        if "to'langan" in lowered or "tolangan" in lowered: return f"✅ Paid"
        return f"❌ Unpaid"
    else:
        if "kechik" in lowered or lowered == PAYMENT_STATUS_OVERDUE.lower(): return f"⚠️ {raw or PAYMENT_STATUS_OVERDUE}"
        if "qisman" in lowered: return f"🟡 {raw}"
        if "ortiqcha" in lowered: return f"🔵 {raw}"
        if "to'langan" in lowered or "tolangan" in lowered: return f"✅ {raw}"
        return f"❌ {raw or PAYMENT_STATUS_UNPAID}"
"""

old_status_text = re.search(r'def _payment_status_text\(status: Any\) -> str:.*?return f"❌ \{raw or PAYMENT_STATUS_UNPAID\}"', content, re.DOTALL).group(0)
content = content.replace(old_status_text, new_status_text)


# 2. Update _format_payment_reminder_text signature and implementation
new_format_text = """def _format_payment_reminder_text(
    *,
    lang: str = "uz",
    student_name: str,
    ym: str,
    status: str,
    debt_amount: float,
    groups_text: str,
    courses_text: str,
    card_line: str = "",
    overdue_items: list[dict[str, Any]] | None = None,
) -> str:
    if lang == "ru":
        lines = [
            "💳 Напоминание об оплате", "",
            f"👤 Ученик: {student_name or '-'}",
            f"📅 Месяц: {ym or '-'}",
            f"📌 Статус: {_payment_status_text(status, lang)}",
            f"💰 Оставшаяся сумма: {_payment_amount_text(debt_amount)}",
            f"👥 Группа: {groups_text or '-'}",
            f"📚 Курс: {courses_text or '-'}", "",
            "⏰ Срок: 25-числа каждого месяца",
            "💵 Способ оплаты: наличными или пластиковая карта",
        ]
        if card_line: lines.append(f"💳 {card_line}")
        overdue = [item for item in (overdue_items or []) if float(item.get("total_debt_amount") or 0.0) > 0]
        if overdue:
            lines.extend(["", "⚠️ Просроченные месяцы:"])
            for item in overdue[:4]: lines.append(f"• {str(item.get('ym') or '-')}: {_payment_amount_text(item.get('total_debt_amount') or 0.0)}")
        lines.extend(["", "✅ Если вы оплатили, дождитесь подтверждения от администратора.", "📲 Статус оплаты можно проверить в разделе «Мои оплаты» в боте."])
    elif lang == "en":
        lines = [
            "💳 Payment Reminder", "",
            f"👤 Student: {student_name or '-'}",
            f"📅 Month: {ym or '-'}",
            f"📌 Status: {_payment_status_text(status, lang)}",
            f"💰 Remaining amount: {_payment_amount_text(debt_amount)}",
            f"👥 Group: {groups_text or '-'}",
            f"📚 Course: {courses_text or '-'}", "",
            "⏰ Deadline: 25th of every month",
            "💵 Payment method: cash or credit card",
        ]
        if card_line: lines.append(f"💳 {card_line}")
        overdue = [item for item in (overdue_items or []) if float(item.get("total_debt_amount") or 0.0) > 0]
        if overdue:
            lines.extend(["", "⚠️ Overdue months:"])
            for item in overdue[:4]: lines.append(f"• {str(item.get('ym') or '-')}: {_payment_amount_text(item.get('total_debt_amount') or 0.0)}")
        lines.extend(["", "✅ If you have paid, please wait for admin confirmation.", "📲 You can check your payment status in the 'My Payments' section in the bot."])
    else:
        lines = [
            "💳 To'lov eslatmasi", "",
            f"👤 O'quvchi: {student_name or '-'}",
            f"📅 Oy: {ym or '-'}",
            f"📌 Holat: {_payment_status_text(status, lang)}",
            f"💰 Qolgan summa: {_payment_amount_text(debt_amount)}",
            f"👥 Guruh: {groups_text or '-'}",
            f"📚 Kurs: {courses_text or '-'}", "",
            "⏰ Muddat: har oyning 25-sanasi",
            "💵 To'lov usuli: naqd yoki plastik karta",
        ]
        if card_line: lines.append(f"💳 {card_line}")
        overdue = [item for item in (overdue_items or []) if float(item.get("total_debt_amount") or 0.0) > 0]
        if overdue:
            lines.extend(["", "⚠️ Kechikkan oylar:"])
            for item in overdue[:4]: lines.append(f"• {str(item.get('ym') or '-')}: {_payment_amount_text(item.get('total_debt_amount') or 0.0)}")
        lines.extend(["", "✅ To'lov qilgan bo'lsangiz, admin tasdiqlashini kuting.", "📲 To'lov holatini botdagi “Mening to'lovlarim” bo'limidan tekshirishingiz mumkin."])
    return "\\n".join(lines)
"""

old_format_text = re.search(r'def _format_payment_reminder_text\(.*?\)\s*->\s*str:.*?return "\\n"\.join\(lines\)', content, re.DOTALL).group(0)
content = content.replace(old_format_text, new_format_text)


# 3. Update callers to pass `lang`
# First caller around line 34112
caller1_old = """        text = _format_payment_reminder_text(
            student_name=_display_name(user),
            ym=current_ym,
            status=current_status,
            debt_amount=float(current_debt),
            groups_text=first_group,
            courses_text=first_course,
            card_line=card_line,
            overdue_items=overdue_items,
        )"""
caller1_new = """        text = _format_payment_reminder_text(
            lang=str(user.get("language") or "uz"),
            student_name=_display_name(user),
            ym=current_ym,
            status=current_status,
            debt_amount=float(current_debt),
            groups_text=first_group,
            courses_text=first_course,
            card_line=card_line,
            overdue_items=overdue_items,
        )"""
content = content.replace(caller1_old, caller1_new)

# Second caller around line 37740
caller2_old = """            text = _format_payment_reminder_text(
                student_name=_display_name(student),
                ym=ym,
                status=status,
                debt_amount=float(debt),
                groups_text=group_names,
                courses_text=course_names,
                card_line=card_line,
                overdue_items=overdue_items,
            )"""
caller2_new = """            text = _format_payment_reminder_text(
                lang=str(student.get("language") or "uz"),
                student_name=_display_name(student),
                ym=ym,
                status=status,
                debt_amount=float(debt),
                groups_text=group_names,
                courses_text=course_names,
                card_line=card_line,
                overdue_items=overdue_items,
            )"""
content = content.replace(caller2_old, caller2_new)


with open('backend/main.py', 'w') as f:
    f.write(content)

print("backend/main.py updated successfully")
