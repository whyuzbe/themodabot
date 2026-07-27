"""
Если человек одновременно зарегистрирован как клиент (через /start) и имеет
активную сессию admin/manager/warehouse — клиентская reply-клавиатура не должна
показываться, пока он "работает" в стафф-режиме.
"""
from aiogram.types import ReplyKeyboardRemove, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest

from db.repos import Repos
from keyboards.client_kb import kb_main_menu


async def client_menu_kb(repos: Repos, tg_id: int, lang: str) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    session = await repos.staff.get_session(tg_id)
    if session:
        return ReplyKeyboardRemove()
    return await kb_main_menu(repos, lang)


async def with_warehouse_button(kb: InlineKeyboardMarkup, repos: Repos, gender: str, lang: str) -> InlineKeyboardMarkup:
    """Добавляет в конец клавиатуры категорий кнопку-ссылку на канал отчётов склада этого пола."""
    url = await repos.settings.get(f"report_channel_{gender}_url")
    if url:
        from locales.texts import tt
        kb.inline_keyboard.append([InlineKeyboardButton(text=await tt(repos, lang, "btn_restock_showcase"), url=url)])
    return kb


async def safe_edit(message, text: str, reply_markup=None):
    """
    Безопасный edit_text: если исходное сообщение было с фото (caption, не text) —
    Telegram не даёт сделать edit_text ('there is no text in the message to edit').
    В этом случае удаляем старое сообщение и присылаем новое текстовое.
    """
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest:
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer(text, reply_markup=reply_markup)