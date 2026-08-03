"""
Shared admin UI snippets (student control card, payments root menu).
Used by admin_bot and diamondvoy_core to avoid circular imports.
"""
from __future__ import annotations

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_CHAT_IDS, ALL_ADMIN_IDS, LIMITED_ADMIN_CHAT_IDS, limited_admin_label
from db import get_groups_by_teacher, get_peer_admins_for_student_share, get_teacher_total_students, is_access_active
from i18n import format_group_level_display, format_stored_user_level_display, t


def build_admin_teacher_detail_reply(teacher: dict, lang: str) -> tuple[str, InlineKeyboardMarkup]:
    """Teacher card text + keyboard (same as admin teacher list detail)."""
    teacher_id = int(teacher["id"])
    groups = get_groups_by_teacher(teacher_id)
    students_count = get_teacher_total_students(teacher_id)

    if teacher.get("blocked"):
        status = t(lang, "admin_status_blocked_label")
    elif is_access_active(teacher):
        status = t(lang, "admin_teacher_status_active_label")
    else:
        status = t(lang, "admin_teacher_status_inactive_label")

    text = t(
        lang,
        "admin_teacher_detail_header",
        first_name=teacher["first_name"],
        last_name=teacher["last_name"],
        subject=teacher.get("subject", "—"),
        phone=teacher.get("phone", "—"),
        login_id=teacher["login_id"],
        status=status,
        groups_count=len(groups),
        students_count=students_count,
    )
    for g in groups:
        text += f"• {g['name']} ({format_group_level_display(lang, g.get('level'), subject=g.get('subject'))})\n"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "admin_btn_edit_first"), callback_data=f"t_edit_fn_{teacher_id}"),
                InlineKeyboardButton(text=t(lang, "admin_btn_edit_last"), callback_data=f"t_edit_ln_{teacher_id}"),
            ],
            [InlineKeyboardButton(text=t(lang, "admin_btn_teacher_edit_phone_change"), callback_data=f"t_edit_ph_{teacher_id}")],
            [InlineKeyboardButton(text=t(lang, "admin_btn_teacher_password_update"), callback_data=f"t_reset_pw_{teacher_id}")],
            [
                InlineKeyboardButton(
                    text=(
                        t(lang, "admin_btn_teacher_daily_tests_disable")
                        if teacher.get("can_upload_daily_tests")
                        else t(lang, "admin_btn_teacher_daily_tests_enable")
                    ),
                    callback_data=f"t_toggle_daily_tests_{teacher_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        t(lang, "admin_btn_teacher_ai_disable")
                        if teacher.get("can_generate_ai")
                        else t(lang, "admin_btn_teacher_ai_enable")
                    ),
                    callback_data=f"t_toggle_ai_{teacher_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "admin_teacher_daily_tests_history_btn"),
                    callback_data=f"teacher_daily_tests_history_{teacher_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=t(lang, "btn_unblock") if teacher.get("blocked") else t(lang, "btn_block"),
                    callback_data=f"teacher_unblock_{teacher_id}" if teacher.get("blocked") else f"teacher_block_{teacher_id}",
                )
            ],
            [InlineKeyboardButton(text=t(lang, "admin_btn_delete_teacher_profile"), callback_data=f"teacher_delete_profile_{teacher_id}")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="teachers_list_view")],
        ]
    )
    return text, keyboard


def build_student_share_keyboard_rows(
    lang: str,
    student: dict,
    viewer_admin_id: int,
) -> list[list[InlineKeyboardButton]]:
    """
    Limited admins: owner can share a student with other admins; peer can remove own access.
    Main admins (ADMIN_CHAT_IDS): share / revoke with each limited admin.
    Callbacks: ashr:{student_id}:{peer_id} (share), aush:{student_id}:{peer_id} (unshare).
    """
    if student.get("login_type") not in (1, 2):
        return []
    sid = int(student["id"])
    peers = get_peer_admins_for_student_share(sid)
    rows: list[list[InlineKeyboardButton]] = []

    if viewer_admin_id in ADMIN_CHAT_IDS:
        if not LIMITED_ADMIN_CHAT_IDS:
            return []
        for aid in LIMITED_ADMIN_CHAT_IDS:
            peer_label = limited_admin_label(int(aid))
            if aid in peers:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=t(lang, "admin_student_btn_unshare_with", peer=peer_label),
                            callback_data=f"aush:{sid}:{aid}",
                        )
                    ]
                )
            else:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=t(lang, "admin_student_btn_share_with", peer=peer_label),
                            callback_data=f"ashr:{sid}:{aid}",
                        )
                    ]
                )
        return rows

    if viewer_admin_id not in LIMITED_ADMIN_CHAT_IDS:
        return []
    owner = student.get("owner_admin_id")
    if owner is None:
        return []
    if viewer_admin_id == owner:
        for aid in ALL_ADMIN_IDS:
            if aid == owner:
                continue
            peer_label = limited_admin_label(int(aid)) if int(aid) in LIMITED_ADMIN_CHAT_IDS else f"Admin {aid}"
            if aid in peers:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=t(lang, "admin_student_btn_unshare_with", peer=peer_label),
                            callback_data=f"aush:{sid}:{aid}",
                        )
                    ]
                )
            else:
                rows.append(
                    [
                        InlineKeyboardButton(
                            text=t(lang, "admin_student_btn_share_with", peer=peer_label),
                            callback_data=f"ashr:{sid}:{aid}",
                        )
                    ]
                )
    elif viewer_admin_id in peers:
        rows.append(
            [
                InlineKeyboardButton(
                    text=t(lang, "admin_student_btn_unshare_self"),
                    callback_data=f"aush:{sid}:{viewer_admin_id}",
                )
            ]
        )
    return rows


async def send_admin_teacher_control_message(bot: Bot, chat_id: int, teacher: dict, lang: str) -> None:
    text, keyboard = build_admin_teacher_detail_reply(teacher, lang)
    await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML")


async def send_admin_student_control_message(
    bot: Bot,
    chat_id: int,
    selected_user: dict,
    lang: str,
    *,
    viewer_admin_id: int | None = None,
) -> None:
    """Same text + keyboard as admin user list selection (test, subjects, edit, reset pw, block)."""
    if selected_user.get("blocked"):
        status = t(lang, "admin_status_blocked_label")
    elif is_access_active(selected_user):
        status = t(lang, "admin_status_open_label")
    else:
        status = t(lang, "admin_status_closed_label")

    uid = int(selected_user["id"])
    kb_rows = [
        [InlineKeyboardButton(text=t(lang, "btn_send_test"), callback_data=f"user_test_{uid}")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_subject_settings"), callback_data=f"user_control_sub_{uid}")],
        [
            InlineKeyboardButton(text=t(lang, "admin_btn_edit_first"), callback_data=f"user_edit_first_{uid}"),
            InlineKeyboardButton(text=t(lang, "admin_btn_edit_last"), callback_data=f"user_edit_last_{uid}"),
        ],
        [InlineKeyboardButton(text=t(lang, "admin_btn_password_reset"), callback_data=f"user_reset_{uid}")],
        [InlineKeyboardButton(text=t(lang, "admin_btn_delete_student_profile"), callback_data=f"user_delete_profile_{uid}")],
    ]
    if selected_user.get("blocked"):
        kb_rows.append([InlineKeyboardButton(text=t(lang, "admin_btn_unblock_admin"), callback_data=f"user_unblock_{uid}")])
    else:
        kb_rows.append([InlineKeyboardButton(text=t(lang, "btn_block"), callback_data=f"user_block_{uid}")])
    if viewer_admin_id is not None:
        kb_rows.extend(build_student_share_keyboard_rows(lang, selected_user, viewer_admin_id))
    kb_rows.append([InlineKeyboardButton(text=t(lang, "btn_home_menu"), callback_data="back_to_menu")])

    await bot.send_message(
        chat_id,
        t(
            lang,
            "admin_user_card_basic",
            first_name=selected_user["first_name"],
            last_name=selected_user["last_name"],
            login_id=selected_user["login_id"],
            subject=selected_user.get("subject") or "-",
            level=format_stored_user_level_display(
                lang,
                selected_user.get("level"),
                subject=selected_user.get("subject"),
            )
            or "-",
            status=status,
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows),
    )


async def send_admin_payments_root_menu(bot: Bot, chat_id: int, lang: str) -> None:
    """Payments section root: search by login / name, export, back."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "payments_search_login"), callback_data="pay_search:login")],
            [InlineKeyboardButton(text=t(lang, "payments_search_name"), callback_data="pay_search:name")],
            [InlineKeyboardButton(text=t(lang, "payment_export_history"), callback_data="payment_export_history")],
            [InlineKeyboardButton(text=t(lang, "btn_back"), callback_data="admin_back_to_main")],
        ]
    )
    await bot.send_message(chat_id, t(lang, "payments_menu_title"), reply_markup=kb)
