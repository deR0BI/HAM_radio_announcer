#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram-бот RDA Cluster (Python 3.13, aiogram 3.20).
"""

import asyncio
import hashlib
import json
import logging
import pathlib
import re
import socketio

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import Message, CallbackQuery, BotCommand

import config
import storage as db
import keyboards
import rda_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
log = logging.getLogger("RDA-bot")

# ───── загрузка RDA-кодов ─────
def load_rda() -> set[str]:
    for p in ("RDA_list_2025.json", "RDA_list_2025.csv"):
        f = pathlib.Path(p)
        if not f.exists(): continue
        if f.suffix == ".json":
            return set(json.loads(f.read_text(encoding="utf-8")))
        codes = set()
        for enc in ("utf-8-sig", "utf-8", "cp1251", "koi8-r", "latin1"):
            try:
                with f.open(encoding=enc) as fh:
                    for ln in fh:
                        code = re.split(r"[;\t ,]+", ln.strip())[0]
                        if re.fullmatch(r"[A-Z]{2}-\d{2}", code):
                            codes.add(code)
                break
            except UnicodeDecodeError:
                continue
        return codes
    return set()

RDA_SET = load_rda()
log.info("RDA codes loaded: %s", len(RDA_SET) or "none")

# ───── aiogram ─────
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
MAX_LEN = 4096

# ───── помощники ─────
def sha(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()

async def send_big(cid: int, text: str):
    for ofs in range(0, len(text), MAX_LEN):
        await bot.send_message(cid, text[ofs:ofs+MAX_LEN])

def split_args(m: Message, cmd: CommandObject | None) -> str:
    if cmd and cmd.args:
        return cmd.args
    if m.text:
        parts = m.text.split(maxsplit=1)
        return parts[1] if len(parts) == 2 else ""
    return ""

async def allowed(cid: int, rda: str, mode: str, freq: float) -> bool:
    rda_list = await db.get_rda(cid)
    if rda_list and not any(x in rda.split() for x in rda_list):
        return False
    m, lo, hi = await db.misc(cid)
    if m != "ANY" and m != mode.upper():
        return False
    return lo <= freq <= hi

# ─────────────────── HANDLERS ────────────────────

@dp.message(Command("start"))
async def cmd_start(m: Message, command: CommandObject | None = None):
    await db.upsert_user(m.chat.id, m.from_user.first_name, m.from_user.username)
    await m.answer(
        "👋  Бот рассылает анонсы и live-споты RDA.\nСправка — /help",
        reply_markup=keyboards.main_kb()
    )

@dp.message(Command("help"))
async def cmd_help(m: Message, command: CommandObject | None = None):
    await send_big(m.chat.id,
        "/sub_ann /unsub_ann — подписка/отписка от анонсов\n"
        "/sub_spots /unsub_spots — подписка/отписка от спотов\n"
        "/add_rda AD-01 … — добавить RDA-фильтр\n"
        "/set_mode DIGI|CW|SSB|ANY — фильтр по моде\n"
        "/set_band 14 14.35 | OFF — диапазон МГц\n"
        "/set_template … — ваш шаблон\n"
        "/my_filters — текущие фильтры\n"
        "/clear_rda — убрать все RDA-фильтры"
    )

async def _sub(m: Message, kind: str, on: bool):
    await db.change_sub(m.chat.id, kind, on)
    await m.answer("✅ Ок." if on else "❌ Больше не присылаю.")

@dp.message(Command("sub_ann"))
async def sub_ann(m: Message): await _sub(m, "ann", True)
@dp.message(Command("unsub_ann"))
async def unsub_ann(m: Message): await _sub(m, "ann", False)
@dp.message(Command("sub_spots"))
async def sub_spots(m: Message): await _sub(m, "spot", True)
@dp.message(Command("unsub_spots"))
async def unsub_spots(m: Message): await _sub(m, "spot", False)

@dp.message(Command("announcements"))
async def cmd_ann(m: Message, command: CommandObject | None = None):
    txt = rda_parser.build_announcements_message()
    await send_big(m.chat.id, txt or "Сейчас анонсов нет.")

@dp.message(Command("add_rda"))
async def cmd_add_rda(m: Message, command: CommandObject | None):
    codes = {c.upper() for c in re.split(r"[ ,;]+", split_args(m, command)) if c}
    if not codes:
        return await m.answer("Передайте коды (пример: /add_rda AD-01 BR-10).")
    if RDA_SET:
        wrong = codes - RDA_SET
        if wrong:
            await m.answer("⚠ Неизвестные: " + " ".join(sorted(wrong)))
            codes -= wrong
    added = await db.add_rda(m.chat.id, *codes)
    await m.answer(
        "🎯 Добавлено: " + ", ".join(sorted(added))
        if added else "Уже было."
    )

@dp.message(Command("clear_rda"))
async def cmd_clear_rda(m: Message):
    """Команда /clear_rda очищает все фильтры RDA."""
    await db.clear_rda(m.chat.id)
    await m.answer("✅ Все RDA-фильтры удалены.")

@dp.message(Command("my_filters"))
async def cmd_my_filters(m: Message, command: CommandObject | None = None):
    mode, lo, hi = await db.misc(m.chat.id)
    rda = await db.get_rda(m.chat.id)
    await m.answer(
        f"Mode: {mode}\n"
        f"Band: {lo}–{hi} МГц\n"
        f"RDA: {'; '.join(sorted(rda)) if rda else 'все'}"
    )

@dp.message(Command("set_mode"))
async def cmd_set_mode(m: Message, command: CommandObject | None):
    arg = split_args(m, command).upper()
    if arg in {"DIGI", "CW", "SSB"}:
        await db.set_mode(m.chat.id, arg)
        return await m.answer(f"Мода → {arg}")
    if arg in {"ANY", "OFF", ""}:
        await db.set_mode(m.chat.id, None)
        return await m.answer("Фильтр моды снят.")
    await m.answer("Укажите DIGI / CW / SSB / ANY")

@dp.message(Command("set_band"))
async def cmd_set_band(m: Message, command: CommandObject | None):
    a = split_args(m, command)
    if not a or a.upper() == "OFF":
        await db.set_band(m.chat.id, None, None)
        return await m.answer("Фильтр диапазона снят.")
    parts = re.split(r"[ ,]+", a)
    if len(parts) == 2 and all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        lo, hi = sorted(map(float, parts))
        await db.set_band(m.chat.id, lo, hi)
        return await m.answer(f"Диапазон {lo}–{hi} МГц")
    await m.answer("Пример: /set_band 14 14.35")

@dp.message(Command("set_template"))
async def cmd_set_template(m: Message, command: CommandObject | None):
    tmpl = split_args(m, command)
    if not tmpl:
        return await m.answer("Поле шаблона пусто. Используйте аргументы команды.")
    await db.set_template(m.chat.id, tmpl)
    await m.answer("Шаблон сохранён.")

# ─── reply-кнопки ───
@dp.message(F.text == "📋 Анонсы")
async def btn_ann(m: Message): await cmd_ann(m, None)

@dp.message(F.text == "✅ Подписаться на споты")
async def btn_sub(m: Message): await _sub(m, "spot", True)

@dp.message(F.text == "❌ Отписаться")
async def btn_unsub(m: Message): await _sub(m, "spot", False)

@dp.message(F.text == "🎛 Мои фильтры")
async def btn_filters(m: Message): await cmd_my_filters(m, None)

# ─── inline-кнопки ───
@dp.callback_query(F.data == "refresh")
async def cb_refresh(c: CallbackQuery):
    txt = rda_parser.build_announcements_message()
    await c.message.edit_text(txt, reply_markup=keyboards.announce_kb())
    await c.answer("Обновил")

@dp.callback_query(F.data == "expand")
async def cb_expand(c: CallbackQuery):
    all_txt = rda_parser.build_announcements_message(wrap=0)
    await send_big(c.message.chat.id, all_txt)
    await c.answer()

# ─── background tasks ───
async def ann_loop():
    last = None
    while True:
        try:
            txt = rda_parser.build_announcements_message(only_new=True)
            if txt and txt != last:
                last = txt
                for cid in await db.subscribers("ann"):
                    await send_big(cid, "🆕 <b>Новые анонсы</b>\n\n" + txt)
        except Exception:
            log.exception("ann_loop")
        await asyncio.sleep(config.CHECK_INTERVAL_SEC)

async def ws_loop():
    while True:
        sio = socketio.AsyncClient(logger=False, engineio_logger=False)

        @sio.on("new_spot")
        async def on_spot(msg: str):
            p = msg.split("|")
            callsign, time, freq, mode = p[0], p[1], float(p[2]), p[3]
            rda, text, spotter = p[5], p[7], p[8]
            if not rda or rda == "?": return
            if not await db.is_new(sha(callsign, time, p[2])): return
            for cid in await db.subscribers("spot"):
                if not await allowed(cid, rda, mode, freq): continue
                out = (await db.get_template(cid)).format(
                    callsign=callsign, mode=mode, freq=freq,
                    rda=rda, text=text.strip(),
                    spotter=spotter, time=time
                )
                await send_big(cid, out)

        try:
            await sio.connect(config.CLUSTER_WS_URL, transports=["websocket"])
            log.info("WS connected")
            await sio.wait()
        except Exception:
            log.exception("ws_loop")
        await asyncio.sleep(15)

# ─── startup ───
@dp.startup()
async def on_startup():
    await db.init_db()
    await bot.set_my_commands([
        BotCommand(command="announcements", description="Текущие анонсы"),
        BotCommand(command="sub_ann",       description="Подписаться на анонсы"),
        BotCommand(command="unsub_ann",     description="Отписаться от анонсов"),
        BotCommand(command="sub_spots",     description="Подписаться на споты"),
        BotCommand(command="unsub_spots",   description="Отписаться от спотов"),
        BotCommand(command="add_rda",       description="Добавить фильтр RDA"),
        BotCommand(command="clear_rda",     description="Очистить RDA-фильтры"),
        BotCommand(command="my_filters",    description="Мои фильтры"),
    ])
    asyncio.create_task(ann_loop())
    asyncio.create_task(ws_loop())
    log.info("🚀 Bot started")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
