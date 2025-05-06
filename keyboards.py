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
            [InlineKeyboardButton(text="🗺️ Все районы списком", callback_data="expand")],
        ]
    )

# ------------------ Меню настроек в чат-боте ------------------

def settings_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Режим",    callback_data="set_mode")],
        [InlineKeyboardButton(text="📡 Диапазон", callback_data="set_band")],
        [InlineKeyboardButton(text="📍 RDA-зоны", callback_data="set_rda")],
        [InlineKeyboardButton(text="✅ Готово",   callback_data="set_done")],
    ])

def mode_menu(current: str) -> InlineKeyboardMarkup:
    modes = ["ANY", "CW", "SSB", "DIGI"]
    row = []
    for m in modes:
        label = f"✅ {m}" if m == current else m
        row.append(InlineKeyboardButton(text=label, callback_data=f"mode|{m}"))
    return InlineKeyboardMarkup(inline_keyboard=[row])

def band_menu() -> InlineKeyboardMarkup:
    bands = [
        ("160 м\n1.8–2.0",         "band|1.8|2.0"),
        ("80 м\n3.5–4.0",          "band|3.5|4.0"),
        ("60 м (WARC)\n5.332–5.4055","band|5.332|5.4055"),
        ("40 м\n7.0–7.2",          "band|7.0|7.2"),
        ("30 м (WARC)\n10.1–10.15", "band|10.1|10.15"),
        ("20 м\n14.0–14.35",       "band|14.0|14.35"),
        ("17 м (WARC)\n18.068–18.168","band|18.068|18.168"),
        ("15 м\n21.0–21.45",       "band|21.0|21.45"),
        ("12 м (WARC)\n24.89–24.99","band|24.89|24.99"),
        ("10 м\n28.0–29.7",        "band|28.0|29.7"),
    ]
    rows = []
    for i in range(0, len(bands), 2):
        row = []
        for text, cb in bands[i:i+2]:
            row.append(InlineKeyboardButton(text=text, callback_data=cb))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="🔧 Другой…", callback_data="band|custom")])
    rows.append([InlineKeyboardButton(text="◀️ Назад",    callback_data="settings_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
