# -*- coding: utf-8 -*-
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Анонсы")],
            [KeyboardButton(text="✅ Подписаться на споты"),
             KeyboardButton(text="❌ Отписаться")],
            [KeyboardButton(text="🎛 Мои фильтры")],
        ],
        resize_keyboard=True
    )

def announce_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh")],
            [InlineKeyboardButton(text="🗺️ Все районы списком", callback_data="expand")]
        ]
    )
