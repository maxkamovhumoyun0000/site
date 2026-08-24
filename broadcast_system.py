#!/usr/bin/env python3
"""
Broadcast System for Admin Bot - Comprehensive broadcast functionality
"""

import asyncio
import threading
from io import BytesIO
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from logging_config import get_logger
from db import get_all_users, get_user_by_id
from i18n import t, detect_lang_from_user
from config import ALL_ADMIN_IDS

logger = get_logger(__name__)
_broadcast_manager: Optional["BroadcastManager"] = None

BROADCAST_VOICE_MAX_BYTES = 20 * 1024 * 1024
BROADCAST_MEDIA_MAX_BYTES = 50 * 1024 * 1024


def is_broadcast_step_active(chat_id: int) -> bool:
    """
    Return True when this chat is currently inside any broadcast flow step.
    Used by admin_bot to avoid swallowing broadcast content messages.
    """
    if _broadcast_manager is None:
        return False
    state = _broadcast_manager.broadcast_states.get(chat_id) or {}
    return bool(state.get("step"))

class BroadcastManager:
    """Enhanced broadcast manager with inline button support"""
    
    def __init__(self, bot: Bot, *, sender_bots: Optional[Dict[str, Bot | None]] = None):
        self.bot = bot
        self.sender_bots = sender_bots or {"admin": bot}
        self.broadcast_states = {}  # Track broadcast operations per admin
        self.broadcast_queue = asyncio.Queue()
        self.current_broadcast = None
        self.sender_fallback_count = 0
        self.broadcast_stats = {
            'total_recipients': 0,
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
    
    def get_state(self, chat_id: int) -> Dict[str, Any]:
        """Get or create broadcast state for chat"""
        if chat_id not in self.broadcast_states:
            self.broadcast_states[chat_id] = {
                'step': None,
                'data': {},
                'recipients': [],
                'message_type': None,
                'content': None,
                'inline_button': None,
                'created_at': datetime.now()
            }
        return self.broadcast_states[chat_id]
    
    def reset_state(self, chat_id: int):
        """Reset broadcast state for chat"""
        if chat_id in self.broadcast_states:
            del self.broadcast_states[chat_id]
        logger.info(f"Broadcast state reset for chat {chat_id}")
    
    async def handle_broadcast_start(self, callback: CallbackQuery):
        """Handle broadcast start"""
        if callback.from_user.id not in ALL_ADMIN_IDS:
            lang = detect_lang_from_user(callback.from_user)
            await callback.answer(t(lang, "broadcast_access_denied"))
            return
        
        lang = detect_lang_from_user(callback.from_user)
        
        state = self.get_state(callback.message.chat.id)
        state['step'] = 'ask_recipients'
        state['admin_lang'] = lang
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "broadcast_recipients_all_students"), callback_data="broadcast_recipients:all_students"),
                InlineKeyboardButton(text=t(lang, "broadcast_recipients_all_teachers"), callback_data="broadcast_recipients:all_teachers")
            ],
            [
                InlineKeyboardButton(text=t(lang, "broadcast_recipients_all_users"), callback_data="broadcast_recipients:all_users"),
                InlineKeyboardButton(text=t(lang, "broadcast_recipients_by_group"), callback_data="broadcast_recipients:by_group")
            ],
            [
                InlineKeyboardButton(text=t(lang, "broadcast_recipients_custom"), callback_data="broadcast_recipients:custom")
            ]
        ])
        
        await callback.message.answer(
            t(lang, "broadcast_create_title"),
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        await callback.answer()
    
    async def handle_recipients_selection(self, callback: CallbackQuery):
        """Handle recipients selection"""
        state = self.get_state(callback.message.chat.id)
        lang = detect_lang_from_user(callback.from_user)
        recipients_type = callback.data.split(':', 1)[1]
        
        if recipients_type == 'all_students':
            students = [u for u in get_all_users() if int(u.get("login_type") or 0) in (1, 2)]
            from db import get_active_telegram_group_chats
            groups = get_active_telegram_group_chats()
            state['recipients'] = students + groups
            state['step'] = 'ask_content_type'
            
            await callback.message.answer(
                t(lang, "broadcast_selected_recipients_count", count=len(students) + len(groups), who=t(lang, "broadcast_who_students")),
                reply_markup=self._get_content_type_keyboard(lang),
                parse_mode='HTML'
            )
            
        elif recipients_type == 'all_teachers':
            from db import get_all_teachers
            teachers = get_all_teachers()
            state['recipients'] = teachers
            state['step'] = 'ask_content_type'
            
            await callback.message.answer(
                t(lang, "broadcast_selected_recipients_count", count=len(teachers), who=t(lang, "broadcast_who_teachers")),
                reply_markup=self._get_content_type_keyboard(lang),
                parse_mode='HTML'
            )
            
        elif recipients_type == 'all_users':
            all_users = get_all_users()
            from db import get_active_telegram_group_chats
            groups = get_active_telegram_group_chats()
            state['recipients'] = all_users + groups
            state['step'] = 'ask_content_type'
            
            await callback.message.answer(
                t(lang, "broadcast_selected_recipients_count", count=len(all_users) + len(groups), who=t(lang, "broadcast_who_users")),
                reply_markup=self._get_content_type_keyboard(lang),
                parse_mode='HTML'
            )
            
        elif recipients_type == 'by_group':
            from db import get_active_telegram_group_chats
            groups = get_active_telegram_group_chats()
            if not groups:
                await callback.message.answer(
                    t(lang, "broadcast_by_group_not_available")
                )
            else:
                state['recipients'] = groups
                state['step'] = 'ask_content_type'
                await callback.message.answer(
                    t(lang, "broadcast_selected_recipients_count", count=len(groups), who="Guruhlar"),
                    reply_markup=self._get_content_type_keyboard(lang),
                    parse_mode='HTML'
                )

            
        elif recipients_type == 'custom':
            state['step'] = 'ask_custom_recipients'
            await callback.message.answer(
                t(lang, "broadcast_custom_recipients_prompt", example="12345, 67890, 11111")
            )
        
        await callback.answer()
    
    def _get_content_type_keyboard(self, lang: str = "uz") -> InlineKeyboardMarkup:
        """Get content type selection keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "broadcast_content_text"), callback_data="broadcast_type:text"),
                InlineKeyboardButton(text=t(lang, "broadcast_content_file"), callback_data="broadcast_type:file")
            ],
            [
                InlineKeyboardButton(text=t(lang, "broadcast_content_photo"), callback_data="broadcast_type:photo"),
                InlineKeyboardButton(text=t(lang, "broadcast_content_video"), callback_data="broadcast_type:video")
            ],
            [
                InlineKeyboardButton(text=t(lang, "broadcast_content_audio"), callback_data="broadcast_type:audio"),
                InlineKeyboardButton(text=t(lang, "broadcast_content_voice"), callback_data="broadcast_type:voice")
            ]
        ])
    
    async def handle_content_type_selection(self, callback: CallbackQuery):
        """Handle content type selection"""
        state = self.get_state(callback.message.chat.id)
        lang = detect_lang_from_user(callback.from_user)
        content_type = callback.data.split(':', 1)[1]
        
        state['message_type'] = content_type
        state['step'] = 'ask_content'
        
        instructions = {
            'text': t(lang, "broadcast_instruction_text"),
            'file': t(lang, "broadcast_instruction_file"),
            'photo': t(lang, "broadcast_instruction_photo"),
            'video': t(lang, "broadcast_instruction_video"),
            'audio': t(lang, "broadcast_instruction_audio"),
            'voice': t(lang, "broadcast_instruction_voice"),
        }
        
        await callback.message.answer(
            instructions.get(content_type, t(lang, "broadcast_instruction_default")),
            reply_markup=self._get_cancel_keyboard(lang)
        )
        await callback.answer()
    
    def _get_cancel_keyboard(self, lang: str = "uz") -> InlineKeyboardMarkup:
        """Get cancel keyboard"""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t(lang, "broadcast_cancel_btn"), callback_data="broadcast_cancel")]
        ])
    
    async def handle_content(self, message: Message):
        """Handle broadcast content"""
        state = self.get_state(message.chat.id)
        
        if not state.get('step'):
            return
        
        if state['step'] == 'ask_custom_recipients':
            await self._handle_custom_recipients(message, state)
        elif state['step'] == 'ask_content':
            try:
                await self._handle_content_input(message, state)
            except ValueError as exc:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(str(exc) or t(lang, "broadcast_send_failed_try_again"))
            except Exception:
                logger.exception("broadcast content processing failed chat_id=%s", message.chat.id)
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_send_failed_try_again"))
    
    async def _handle_custom_recipients(self, message: Message, state: Dict[str, Any]):
        """Handle custom recipients input"""
        try:
            raw_text = (message.text or "").strip()
            if not raw_text:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_format_error_user_ids"))
                return
            recipient_ids = [int(x.strip()) for x in raw_text.split(',') if x.strip().isdigit()]
            
            if not recipient_ids:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_format_error_user_ids"))
                return
            
            # Validate user IDs
            valid_users = []
            invalid_ids = []
            
            for user_id in recipient_ids:
                user = get_user_by_id(user_id)
                if user:
                    valid_users.append(user)
                else:
                    invalid_ids.append(user_id)
            
            if invalid_ids:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(
                    t(lang, "broadcast_invalid_user_ids_found", invalid_ids=", ".join(map(str, invalid_ids)), found_count=len(valid_users))
                )
                return
            
            state['recipients'] = valid_users
            state['step'] = 'ask_content_type'
            
            await message.answer(
                t(
                    detect_lang_from_user(message.from_user),
                    "broadcast_custom_users_selected",
                    count=len(valid_users),
                ) + "\n\n" + t(detect_lang_from_user(message.from_user), "broadcast_choose_content_type"),
                reply_markup=self._get_content_type_keyboard(detect_lang_from_user(message.from_user))
            )
            
        except ValueError:
            lang = detect_lang_from_user(message.from_user)
            await message.answer(t(lang, "broadcast_format_error_numbers"))

    async def _download_admin_media(self, file_id: str, *, max_bytes: int) -> bytes:
        file_info = await self.bot.get_file(file_id)
        buffer = BytesIO()
        await self.bot.download_file(file_info.file_path, destination=buffer)
        data = buffer.getvalue()
        if not data:
            raise ValueError("Uploaded media is empty")
        if len(data) > int(max_bytes):
            raise ValueError("Uploaded media is too large")
        return data

    async def _build_media_content(
        self,
        *,
        file_id: str,
        caption: str | None,
        file_name: str,
        mime_type: str | None = None,
        duration: int | None = None,
        max_bytes: int = BROADCAST_MEDIA_MAX_BYTES,
    ) -> dict[str, Any]:
        data = await self._download_admin_media(file_id, max_bytes=max_bytes)
        return {
            "file_id": file_id,
            "file_bytes": data,
            "file_name": file_name,
            "mime_type": mime_type,
            "caption": caption,
            "duration": duration,
            "size_bytes": len(data),
        }
    
    async def _handle_content_input(self, message: Message, state: Dict[str, Any]):
        """Handle content input"""
        content_type = state['message_type']
        
        if content_type == 'text':
            if message.text:
                state['content'] = message.text
                state['step'] = 'ask_inline_button'
                await self._ask_inline_button(message, state)
            else:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_text_empty"))
        
        elif content_type == 'file':
            if message.document:
                state['content'] = await self._build_media_content(
                    file_id=message.document.file_id,
                    caption=message.caption,
                    file_name=message.document.file_name or "broadcast-file",
                    mime_type=message.document.mime_type,
                    max_bytes=BROADCAST_MEDIA_MAX_BYTES,
                )
                state['step'] = 'ask_inline_button'
                await self._ask_inline_button(message, state)
            else:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_file_missing"))
        
        elif content_type == 'photo':
            if message.photo:
                state['content'] = await self._build_media_content(
                    file_id=message.photo[-1].file_id,
                    caption=message.caption,
                    file_name="broadcast-photo.jpg",
                    mime_type="image/jpeg",
                    max_bytes=BROADCAST_MEDIA_MAX_BYTES,
                )
                state['step'] = 'ask_inline_button'
                await self._ask_inline_button(message, state)
            else:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_photo_missing"))
        
        elif content_type == 'video':
            if message.video:
                state['content'] = await self._build_media_content(
                    file_id=message.video.file_id,
                    caption=message.caption,
                    file_name=message.video.file_name or "broadcast-video.mp4",
                    mime_type=message.video.mime_type,
                    max_bytes=BROADCAST_MEDIA_MAX_BYTES,
                )
                state['step'] = 'ask_inline_button'
                await self._ask_inline_button(message, state)
            else:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_video_missing"))
        
        elif content_type == 'audio':
            if message.audio:
                state['content'] = await self._build_media_content(
                    file_id=message.audio.file_id,
                    caption=message.caption,
                    file_name=message.audio.file_name or "broadcast-audio.mp3",
                    mime_type=message.audio.mime_type,
                    max_bytes=BROADCAST_VOICE_MAX_BYTES,
                )
                state['step'] = 'ask_inline_button'
                await self._ask_inline_button(message, state)
            else:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_audio_missing"))

        elif content_type == 'voice':
            if message.voice:
                state['content'] = await self._build_media_content(
                    file_id=message.voice.file_id,
                    caption=message.caption,
                    file_name="broadcast-voice.ogg",
                    mime_type=message.voice.mime_type or "audio/ogg",
                    duration=message.voice.duration,
                    max_bytes=BROADCAST_VOICE_MAX_BYTES,
                )
                state['step'] = 'ask_inline_button'
                await self._ask_inline_button(message, state)
            else:
                lang = detect_lang_from_user(message.from_user)
                await message.answer(t(lang, "broadcast_voice_missing"))
    
    async def _ask_inline_button(self, message: Message, state: Dict[str, Any]):
        """Ask if user wants to add inline button"""
        lang = detect_lang_from_user(message.from_user)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t(lang, "broadcast_add_button_yes"), callback_data="broadcast_add_button:yes"),
                InlineKeyboardButton(text=t(lang, "broadcast_add_button_no"), callback_data="broadcast_add_button:no")
            ]
        ])
        
        await message.answer(
            t(lang, "broadcast_add_inline_button_prompt"),
            reply_markup=keyboard
        )
    
    async def handle_inline_button_decision(self, callback: CallbackQuery):
        """Handle inline button decision"""
        state = self.get_state(callback.message.chat.id)
        decision = callback.data.split(':', 1)[1]
        
        if decision == 'yes':
            state['step'] = 'ask_button_text'
            lang = detect_lang_from_user(callback.from_user)
            await callback.message.answer(
                t(lang, "broadcast_button_name_prompt"),
                reply_markup=self._get_cancel_keyboard(lang)
            )
        else:
            state['inline_button'] = None
            await self._show_preview(callback.message, state)
        
        await callback.answer()
    
    async def handle_button_text(self, message: Message):
        """Handle button text input"""
        state = self.get_state(message.chat.id)
        
        if not state.get('step') == 'ask_button_text':
            return
        
        button_text = (message.text or "").strip()
        
        if not button_text:
            lang = detect_lang_from_user(message.from_user)
            await message.answer(t(lang, "broadcast_button_name_empty"))
            return
        
        if len(button_text) > 64:
            lang = detect_lang_from_user(message.from_user)
            await message.answer(t(lang, "broadcast_button_name_too_long"))
            return
        
        state['inline_button'] = {'text': button_text}
        state['step'] = 'ask_button_url'
        
        lang = detect_lang_from_user(message.from_user)
        await message.answer(
            t(lang, "broadcast_button_name_saved_prompt_url", button_text=button_text),
            reply_markup=self._get_cancel_keyboard(lang)
        )
    
    async def handle_button_url(self, message: Message):
        """Handle button URL input"""
        state = self.get_state(message.chat.id)
        
        if not state.get('step') == 'ask_button_url':
            return
        
        button_url = (message.text or "").strip()
        
        if not button_url:
            lang = detect_lang_from_user(message.from_user)
            await message.answer(t(lang, "broadcast_url_empty"))
            return
        
        # Basic URL validation
        if not (button_url.startswith('https://') or button_url.startswith('http://') or 
                button_url.startswith('t.me/') or button_url.startswith('mailto:')):
            lang = detect_lang_from_user(message.from_user)
            await message.answer(t(lang, "broadcast_url_invalid_format"))
            return
        
        state['inline_button']['url'] = button_url
        await self._show_preview(message, state)
    
    async def _show_preview(self, message: Message, state: Dict[str, Any]):
        """Show broadcast preview"""
        recipients = state['recipients']
        content_type = state['message_type']
        content = state['content']
        inline_button = state.get('inline_button')
        
        lang = detect_lang_from_user(message.from_user)
        preview_text = t(lang, "broadcast_preview_title", recipients_count=len(recipients), content_type=content_type) + "\n"
        
        if content_type == 'text':
            preview_text += t(
                lang,
                "broadcast_preview_content_text",
                snippet=f"{content[:100]}{'...' if len(content) > 100 else ''}",
            ) + "\n"
        elif content_type == 'file':
            preview_text += t(lang, "broadcast_preview_content_file", filename=(content or {}).get('file_name') or 'document') + "\n"
        elif content_type == 'photo':
            preview_text += t(lang, "broadcast_preview_content_photo") + "\n"
        elif content_type == 'video':
            preview_text += t(lang, "broadcast_preview_content_video", filename=(content or {}).get('file_name') or 'video') + "\n"
        elif content_type == 'audio':
            preview_text += t(lang, "broadcast_preview_content_audio", filename=(content or {}).get('file_name') or 'audio') + "\n"
        elif content_type == 'voice':
            preview_text += t(lang, "broadcast_preview_content_voice", duration=(content or {}).get('duration') or '-') + "\n"
        
        if inline_button:
            preview_text += t(lang, "broadcast_preview_button_line", button_text=inline_button['text'], button_url=inline_button['url']) + "\n"
        else:
            preview_text += t(lang, "broadcast_preview_button_none") + "\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t(detect_lang_from_user(message.from_user), "broadcast_confirm_send_btn"), callback_data="broadcast_confirm"),
                InlineKeyboardButton(text=t(detect_lang_from_user(message.from_user), "broadcast_confirm_edit_btn"), callback_data="broadcast_edit"),
                InlineKeyboardButton(text=t(detect_lang_from_user(message.from_user), "broadcast_cancel_btn"), callback_data="broadcast_cancel")
            ]
        ])
        
        await message.answer(preview_text, reply_markup=keyboard, parse_mode='HTML')
    
    async def handle_broadcast_confirm(self, callback: CallbackQuery):
        """Handle broadcast confirmation"""
        state = self.get_state(callback.message.chat.id)
        
        if not state.get('recipients') or not state.get('content'):
            lang = detect_lang_from_user(callback.from_user)
            await callback.answer(t(lang, "broadcast_error_incomplete_data"))
            return
        
        # Start broadcast
        await self._start_broadcast(callback.message, state)
        await callback.answer()
    
    async def handle_broadcast_edit(self, callback: CallbackQuery):
        """Handle broadcast edit"""
        state = self.get_state(callback.message.chat.id)
        state['step'] = 'ask_content_type'
        
        lang = detect_lang_from_user(callback.from_user)
        await callback.message.answer(
            t(lang, "broadcast_edit_prompt"),
            reply_markup=self._get_content_type_keyboard(lang)
        )
        await callback.answer()
    
    async def handle_broadcast_cancel(self, callback: CallbackQuery):
        """Handle broadcast cancellation"""
        state = self.get_state(callback.message.chat.id)
        self.reset_state(callback.message.chat.id)
        
        lang = detect_lang_from_user(callback.from_user)
        await callback.message.answer(t(lang, "broadcast_cancelled"))
        await callback.answer()
    
    async def _start_broadcast(self, message: Message, state: Dict[str, Any]):
        """Start the actual broadcast"""
        recipients = state['recipients']
        content_type = state['message_type']
        content = state['content']
        inline_button = state.get('inline_button')
        
        # Reset statistics
        self.broadcast_stats = {
            'total_recipients': len(recipients),
            'successful': 0,
            'failed': 0,
            'skipped': 0
        }
        
        await message.answer(
            t(detect_lang_from_user(message.from_user), "broadcast_started_status", count=len(recipients)),
            parse_mode='HTML'
        )
        
        # Create preview message for testing
        test_message = await self._create_test_message(message.chat.id, content_type, content, inline_button)
        
        # Ask for confirmation to proceed
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text=t(detect_lang_from_user(message.from_user), "broadcast_confirm_proceed_yes"), callback_data="broadcast_proceed"),
                InlineKeyboardButton(text=t(detect_lang_from_user(message.from_user), "broadcast_cancel_btn"), callback_data="broadcast_cancel")
            ]
        ])
        
        await self.bot.send_message(
            message.chat.id,
            t(detect_lang_from_user(message.from_user), "broadcast_test_message_header"),
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
        # Store test message for actual broadcast
        state['test_message'] = test_message
    
    async def handle_broadcast_proceed(self, callback: CallbackQuery):
        """Proceed with actual broadcast"""
        state = self.get_state(callback.message.chat.id)
        
        if not state.get('test_message'):
            lang = detect_lang_from_user(callback.from_user)
            await callback.answer(t(lang, "broadcast_test_message_not_found"))
            return
        
        test_message = state['test_message']
        recipients = state['recipients']
        
        await callback.message.answer(
            t(detect_lang_from_user(callback.from_user), "broadcast_sending_status", count=len(recipients)),
            parse_mode='HTML'
        )
        
        # Send broadcast to all recipients
        await self._send_broadcast_to_all(recipients, test_message, callback.message.chat.id)
        
        await callback.answer()
    
    async def _create_test_message(self, chat_id: int, content_type: str, content: Any, inline_button: Optional[Dict] = None) -> Dict[str, Any]:
        """Create test message for preview"""
        test_message = {
            'type': content_type,
            'content': content,
            'inline_button': inline_button
        }
        
        # Send test message to admin for verification
        try:
            if content_type == 'text':
                await self.bot.send_message(
                    chat_id,
                    content,
                    reply_markup=self._create_inline_keyboard(inline_button) if inline_button else None,
                    parse_mode='HTML'
                )
            elif content_type == 'file':
                await self.bot.send_document(
                    chat_id,
                    content['file_id'],
                    caption=content.get('caption') or t(self.get_state(chat_id).get("admin_lang", "uz"), "broadcast_test_caption_file"),
                    reply_markup=self._create_inline_keyboard(inline_button) if inline_button else None,
                    parse_mode='HTML'
                )
            elif content_type == 'photo':
                await self.bot.send_photo(
                    chat_id,
                    content['file_id'],
                    caption=content.get('caption') or t(self.get_state(chat_id).get("admin_lang", "uz"), "broadcast_test_caption_photo"),
                    reply_markup=self._create_inline_keyboard(inline_button) if inline_button else None,
                    parse_mode='HTML'
                )
            elif content_type == 'video':
                await self.bot.send_video(
                    chat_id,
                    content['file_id'],
                    caption=content.get('caption') or t(self.get_state(chat_id).get("admin_lang", "uz"), "broadcast_test_caption_video"),
                    reply_markup=self._create_inline_keyboard(inline_button) if inline_button else None,
                    parse_mode='HTML'
                )
            elif content_type == 'audio':
                await self.bot.send_audio(
                    chat_id,
                    content['file_id'],
                    caption=content.get('caption') or t(self.get_state(chat_id).get("admin_lang", "uz"), "broadcast_test_caption_audio"),
                    reply_markup=self._create_inline_keyboard(inline_button) if inline_button else None,
                    parse_mode='HTML'
                )
            elif content_type == 'voice':
                await self.bot.send_voice(
                    chat_id,
                    content['file_id'],
                    caption=content.get('caption') or t(self.get_state(chat_id).get("admin_lang", "uz"), "broadcast_test_caption_voice"),
                    reply_markup=self._create_inline_keyboard(inline_button) if inline_button else None,
                    parse_mode='HTML'
                )
                
        except Exception as e:
            logger.error(f"Error creating test message: {e}")
            raise
        
        return test_message
    
    def _create_inline_keyboard(self, button: Optional[Dict]) -> Optional[InlineKeyboardMarkup]:
        """Create inline keyboard from button data"""
        if not button:
            return None
        
        url = button['url']
        from aiogram.types import WebAppInfo
        if "diamond-education.com" in url or "diamond-education.uz" in url or "?startapp=" in url:
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=button['text'], web_app=WebAppInfo(url=url))]
            ])
        
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button['text'], url=url)]
        ])

    def _resolve_sender_bot(self, recipient: Dict[str, Any]) -> Bot:
        role = self._recipient_role_key(recipient)
        preferred = self.sender_bots.get(role)
        if preferred is None and role == "support":
            preferred = self.sender_bots.get("teacher")
        if preferred is None:
            preferred = self.sender_bots.get("admin")
        if preferred is None:
            self.sender_fallback_count += 1
            return self.bot
        return preferred

    def _recipient_role_key(self, recipient: Dict[str, Any]) -> str:
        lt = int(recipient.get("login_type") or 0)
        if lt in (1, 2, 6):
            return "student"
        if lt == 3:
            return "teacher"
        if lt == 5:
            return "support"
        return "admin"

    def _media_input(self, content: dict[str, Any]) -> Any:
        data = content.get("file_bytes")
        if isinstance(data, (bytes, bytearray)) and data:
            return BufferedInputFile(bytes(data), filename=str(content.get("file_name") or "broadcast-media"))
        return content["file_id"]

    async def _send_payload(
        self,
        sender_bot: Bot,
        *,
        content_type: str,
        telegram_id: int,
        content: Any,
        inline_keyboard: Optional[InlineKeyboardMarkup],
    ) -> None:
        if content_type == 'text':
            await sender_bot.send_message(
                telegram_id,
                content,
                reply_markup=inline_keyboard,
                parse_mode='HTML'
            )
            return
        if content_type == 'file':
            await sender_bot.send_document(
                telegram_id,
                self._media_input(content),
                caption=content.get('caption'),
                reply_markup=inline_keyboard,
                parse_mode='HTML'
            )
            return
        if content_type == 'photo':
            await sender_bot.send_photo(
                telegram_id,
                self._media_input(content),
                caption=content.get('caption'),
                reply_markup=inline_keyboard,
                parse_mode='HTML'
            )
            return
        if content_type == 'video':
            await sender_bot.send_video(
                telegram_id,
                self._media_input(content),
                caption=content.get('caption'),
                reply_markup=inline_keyboard,
                parse_mode='HTML'
            )
            return
        if content_type == 'audio':
            await sender_bot.send_audio(
                telegram_id,
                self._media_input(content),
                caption=content.get('caption'),
                reply_markup=inline_keyboard,
                parse_mode='HTML'
            )
            return
        if content_type == 'voice':
            await sender_bot.send_voice(
                telegram_id,
                self._media_input(content),
                caption=content.get('caption'),
                reply_markup=inline_keyboard,
                parse_mode='HTML'
            )
            return
        raise ValueError(f"Unsupported broadcast content_type={content_type}")
    
    async def _send_broadcast_to_all(self, recipients: List[Dict], test_message: Dict, admin_chat_id: int):
        """Send broadcast to all recipients"""
        content_type = test_message['type']
        content = test_message['content']
        inline_button = test_message['inline_button']
        inline_keyboard = self._create_inline_keyboard(inline_button) if inline_button else None
        
        success_count = 0
        failed_count = 0
        self.sender_fallback_count = 0
        role_stats: dict[str, dict[str, int]] = {}
        error_buckets: dict[str, int] = {}
        
        for i, recipient in enumerate(recipients):
            role_key = self._recipient_role_key(recipient)
            role_stats.setdefault(role_key, {"attempted": 0, "sent": 0, "failed": 0, "skipped": 0})
            try:
                if not recipient.get('telegram_id'):
                    self.broadcast_stats['skipped'] += 1
                    role_stats[role_key]["skipped"] += 1
                    continue
                
                telegram_id = int(recipient['telegram_id'])
                sender_bot = self._resolve_sender_bot(recipient)
                role_stats[role_key]["attempted"] += 1
                try:
                    await self._send_payload(
                        sender_bot,
                        content_type=content_type,
                        telegram_id=telegram_id,
                        content=content,
                        inline_keyboard=inline_keyboard,
                    )
                except TelegramRetryAfter as retry_exc:
                    await asyncio.sleep(float(getattr(retry_exc, "retry_after", 1) or 1) + 0.5)
                    await self._send_payload(
                        sender_bot,
                        content_type=content_type,
                        telegram_id=telegram_id,
                        content=content,
                        inline_keyboard=inline_keyboard,
                    )
                
                success_count += 1
                role_stats[role_key]["sent"] += 1
                
                # Update progress every 10 messages
                if (i + 1) % 10 == 0:
                    progress = ((i + 1) / len(recipients)) * 100
                    await self.bot.send_message(
                        admin_chat_id,
                        t(
                            self.get_state(admin_chat_id).get("admin_lang", "uz"),
                            "broadcast_progress_report",
                            progress=f"{progress:.1f}",
                            current=i + 1,
                            total=len(recipients),
                            success=success_count,
                            failed=failed_count,
                        ),
                        parse_mode='HTML'
                    )
                
                # Add delay to avoid rate limiting
                await asyncio.sleep(0.1)
                
            except TelegramForbiddenError as e:
                failed_count += 1
                role_stats[role_key]["failed"] += 1
                error_buckets["forbidden"] = error_buckets.get("forbidden", 0) + 1
                logger.warning("Broadcast skipped forbidden recipient role=%s telegram_id=%s: %s", role_key, recipient.get("telegram_id"), e)
            except TelegramBadRequest as e:
                failed_count += 1
                role_stats[role_key]["failed"] += 1
                error_buckets["bad_request"] = error_buckets.get("bad_request", 0) + 1
                logger.warning("Broadcast bad request role=%s telegram_id=%s: %s", role_key, recipient.get("telegram_id"), e)
            except TelegramRetryAfter as e:
                failed_count += 1
                role_stats[role_key]["failed"] += 1
                error_buckets["retry_after"] = error_buckets.get("retry_after", 0) + 1
                logger.warning("Broadcast rate limited role=%s telegram_id=%s retry_after=%s", role_key, recipient.get("telegram_id"), getattr(e, "retry_after", None))
            except Exception as e:
                failed_count += 1
                role_stats[role_key]["failed"] += 1
                error_buckets["unknown"] = error_buckets.get("unknown", 0) + 1
                logger.exception("Failed to send broadcast role=%s telegram_id=%s", role_key, recipient.get("telegram_id"))
        
        # Send final statistics
        self.broadcast_stats['successful'] = success_count
        self.broadcast_stats['failed'] = failed_count
        self.broadcast_stats['role_stats'] = role_stats
        self.broadcast_stats['error_buckets'] = error_buckets

        # Mirror the broadcast into the app world: a `web_broadcasts` row
        # (in-app notification/popup) plus an FCM push for every targeted
        # user with a registered device — previously the bot broadcast only
        # reached Telegram chats and app users saw nothing.
        try:
            threading.Thread(
                target=self._send_web_broadcast,
                args=(test_message, recipients, success_count, failed_count),
                daemon=True,
            ).start()
        except Exception:
            logger.exception("web broadcast mirror failed to start")

        await self._send_final_statistics(admin_chat_id)

    def _send_web_broadcast(self, test_message: Dict[str, Any], recipients: List[Dict[str, Any]], sent: int, failed: int) -> None:
        """Sync app-side mirror of a Telegram broadcast (runs in a thread)."""
        import json as _json

        from db import get_conn
        import push_notifications

        content_type = test_message['type']
        content = test_message['content']
        inline_button = test_message.get('inline_button') or {}

        if content_type == 'text':
            text = str(content or '').strip()
        else:
            text = str((content or {}).get('caption') or '').strip() if isinstance(content, dict) else ''
        if not text:
            text = "Yangi e'lon"
        text = text[:2000]

        # Store the exact app-user IDs. Inferring an all-role target from the
        # final Telegram recipient list can leak a custom broadcast to every
        # student/teacher merely because its selected recipients share a role.
        # Telegram group rows use negative IDs and intentionally have no
        # app-user identity, so they are excluded from app delivery.
        user_ids = sorted({
            int(r.get('id') or 0)
            for r in recipients
            if int(r.get('id') or 0) > 0
        })
        target_type = "custom_users"
        target_ids_json = _json.dumps(user_ids)

        button_text = str(inline_button.get('text') or '').strip() or None
        button_url = str(inline_button.get('url') or '').strip() or None

        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO web_broadcasts
                    (creator_user_id, target_type, target_ids_json, message_text,
                     button_text, button_url, status, total_recipients,
                     sent_count, failed_count, skipped_count, finished_at)
                VALUES (NULL, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, 0, CURRENT_TIMESTAMP)
                """,
                (target_type, target_ids_json, text, button_text, button_url, len(recipients), int(sent), int(failed)),
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.exception("web broadcast insert failed")
        finally:
            conn.close()

        try:
            if user_ids:
                push_notifications.send_push_to_users(
                    user_ids,
                    "Diamond Education",
                    text,
                    data={
                        "target_screen": "notifications",
                        "notification_type": "broadcast",
                        "button_url": button_url or "",
                    },
                )
        except Exception:
            logger.exception("web broadcast push failed")
    
    async def _send_final_statistics(self, admin_chat_id: int):
        """Send final broadcast statistics"""
        stats = self.broadcast_stats
        total = stats['total_recipients']
        successful = stats['successful']
        failed = stats['failed']
        skipped = stats['skipped']
        
        success_rate = (successful / total * 100) if total > 0 else 0
        
        stats_text = t(
            self.get_state(admin_chat_id).get("admin_lang", "uz"),
            "broadcast_final_stats",
            total=total,
            successful=successful,
            failed=failed,
            skipped=skipped,
            success_rate=f"{success_rate:.1f}",
        )
        role_stats = stats.get("role_stats") or {}
        if role_stats:
            lines = []
            for role, row in sorted(role_stats.items()):
                lines.append(
                    f"{role}: ✅ {int(row.get('sent') or 0)} / {int(row.get('attempted') or 0)} · ❌ {int(row.get('failed') or 0)} · ⏭ {int(row.get('skipped') or 0)}"
                )
            stats_text += "\n\n" + "\n".join(lines)
        
        await self.bot.send_message(admin_chat_id, stats_text, parse_mode='HTML')
        
        # Reset state
        self.reset_state(admin_chat_id)
        
        if self.sender_fallback_count:
            logger.warning(
                "Broadcast sender fallback used count=%s (missing role bot instance)",
                self.sender_fallback_count,
            )
        logger.info(
            "Broadcast completed successful=%s total=%s failed=%s skipped=%s roles=%s errors=%s",
            successful,
            total,
            failed,
            skipped,
            stats.get("role_stats") or {},
            stats.get("error_buckets") or {},
        )

# Setup function for easy integration
def setup_broadcast_handlers(dp: Dispatcher, bot: Bot, *, sender_bots: Optional[Dict[str, Bot | None]] = None):
    """Setup broadcast handlers"""
    global _broadcast_manager
    broadcast_manager = BroadcastManager(bot, sender_bots=sender_bots)
    _broadcast_manager = broadcast_manager
    
    # Register callback handlers
    dp.callback_query(lambda c: c.data == 'broadcast_start')(broadcast_manager.handle_broadcast_start)
    dp.callback_query(lambda c: c.data.startswith('broadcast_recipients:'))(broadcast_manager.handle_recipients_selection)
    dp.callback_query(lambda c: c.data.startswith('broadcast_type:'))(broadcast_manager.handle_content_type_selection)
    dp.callback_query(lambda c: c.data.startswith('broadcast_add_button:'))(broadcast_manager.handle_inline_button_decision)
    dp.callback_query(lambda c: c.data == 'broadcast_confirm')(broadcast_manager.handle_broadcast_confirm)
    dp.callback_query(lambda c: c.data == 'broadcast_edit')(broadcast_manager.handle_broadcast_edit)
    dp.callback_query(lambda c: c.data == 'broadcast_cancel')(broadcast_manager.handle_broadcast_cancel)
    dp.callback_query(lambda c: c.data == 'broadcast_proceed')(broadcast_manager.handle_broadcast_proceed)
    
    # Register message handlers only for active broadcast steps.
    dp.message(
        lambda m: broadcast_manager.get_state(m.chat.id).get('step') in ('ask_custom_recipients', 'ask_content')
    )(broadcast_manager.handle_content)
    dp.message(
        lambda m: broadcast_manager.get_state(m.chat.id).get('step') == 'ask_button_text'
    )(broadcast_manager.handle_button_text)
    dp.message(
        lambda m: broadcast_manager.get_state(m.chat.id).get('step') == 'ask_button_url'
    )(broadcast_manager.handle_button_url)
    
    logger.info("Broadcast handlers setup completed")
    return broadcast_manager
