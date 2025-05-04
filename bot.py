#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram‑бот «RDA Announcer»

Команды
───────
/announcements – прислать все текущие анонсы
/sub            – подписаться на автоматические уведомления
/unsub          – отменить подписку
"""

import asyncio
import logging
from typing import Final

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command

import config           #   • BOT_TOKEN             – токен, который дал @BotFather
import rda_parser       #   • build_announcements_message(only_new=False)

# ─────────── логирование ───────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("RDA‑bot")

# ─────────── инициализация бота/диспетчера ───────────
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)   # сразу HTML‑режим
)
dp = Dispatcher()

# ─────────── подписчики ───────────
SUBSCRIBERS: set[int] = {config.DEFAULT_CHAT_ID}   # владелец/группа по умолчанию

# ─────────── helper: «безопасная отправка» ───────────
MAX_LEN: Final[int] = 4096          # лимит Telegram для одного сообщения


async def safe_send(chat_id: int, text: str) -> None:
    """
    Отправить длинный текст, гарантированно укладываясь в 4096 символов.
    Режем только по двойному \n\n — границы анонсов.
    """
    if len(text) <= MAX_LEN:
        await bot.send_message(chat_id, text)
        return

    parts: list[str] = []
    buff: list[str] = []
    cur = 0
    for block in text.split("\n\n"):
        add = block + "\n\n"
        if cur + len(add) > MAX_LEN:
            parts.append("".join(buff).rstrip())
            buff, cur = [], 0
        buff.append(add)
        cur += len(add)
    if buff:
        parts.append("".join(buff).rstrip())

    for chunk in parts:
        await bot.send_message(chat_id, chunk)
        await asyncio.sleep(0.3)          # микропаузa, чтобы не засорять лог


# ─────────── handlers ───────────
@dp.message(Command("start"))
async def cmd_start(msg: types.Message) -> None:
    await msg.reply(
        "👋 Добро пожаловать! Я присылаю анонсы экспедиций RDA.\n\n"
        "<b>/announcements</b> — список анонсов сейчас\n"
        "<b>/sub</b>           — подписаться на автопуш\n"
        "<b>/unsub</b>         — отписаться"
    )


@dp.message(Command("announcements"))
async def cmd_announcements(msg: types.Message) -> None:
    text = rda_parser.build_announcements_message()
    if text:
        await safe_send(msg.chat.id, text)
    else:
        await msg.reply("Сейчас анонсов нет.")


@dp.message(Command("sub"))
async def cmd_sub(msg: types.Message) -> None:
    SUBSCRIBERS.add(msg.chat.id)
    await msg.reply("✅ Вы подписались на автоматические уведомления.")


@dp.message(Command("unsub"))
async def cmd_unsub(msg: types.Message) -> None:
    SUBSCRIBERS.discard(msg.chat.id)
    await msg.reply("❌ Подписка отменена.")


# ─────────── background push loop ───────────
async def push_loop() -> None:
    """Каждые N секунд проверяет сайт и присылает ТОЛЬКО новые анонсы."""
    while True:
        try:
            text = rda_parser.build_announcements_message(only_new=True)
            if text:
                for cid in SUBSCRIBERS.copy():
                    await safe_send(cid, text)
        except Exception:
            log.exception("Ошибка в push_loop")
        await asyncio.sleep(config.CHECK_INTERVAL_SEC)


# ─────────── entry point ───────────
async def main() -> None:
    # запускаем фоновую задачу ДО polling
    asyncio.create_task(push_loop())

    log.info(
        "🚀 Bot started — interval %s s | Python %s.%s",
        config.CHECK_INTERVAL_SEC, *asyncio.sys.version_info[:2]
    )

    # start_polling блокирует поток до Ctrl‑C
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
