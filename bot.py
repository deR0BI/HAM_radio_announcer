#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram-бот RDA Cluster (Python 3.13, aiogram 3.20).
Включает «Мастер настроек» через inline-меню без потери основного функционала.
Теперь HTML-теги анонсов безопасно обрабатываются и отображаются корректно.
"""

import asyncio
import hashlib
import json
import logging
import pathlib
import re
import socketio
import html

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters.command import Command, CommandObject
from aiogram.types import Message, CallbackQuery, BotCommand
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

import config
import storage as db
import keyboards
import rda_parser

# ───── Логирование ─────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
log = logging.getLogger("RDA-bot")

# ───── Загрузка RDA-кодов ─────
def load_rda() -> set[str]:
    for p in ("RDA_list_2025.json", "RDA_list_2025.csv"):
        f = pathlib.Path(p)
        if not f.exists():
            continue
        if f.suffix == ".json":
            return set(json.loads(f.read_text(encoding="utf-8")))
        codes = set()
        for enc in ("utf-8-sig","utf-8","cp1251","koi8-r","latin1"):
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

# ───── Инициализация бота ─────
bot = Bot(
    token=config.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
MAX_LEN = 4096

# ───── Вспомогательные функции ─────
def sha(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()

def sanitize_html(text: str) -> str:
    esc = html.escape(text)
    for tag in ("b", "i"):
        esc = esc.replace(f"&lt;{tag}&gt;", f"<{tag}>")
        esc = esc.replace(f"&lt;/{tag}&gt;", f"</{tag}>")
    return esc

async def send_big(cid: int, text: str):
    # разбиваем по строкам, аккуратно набирая куски до MAX_LEN
    chunks: list[str] = []
    for line in text.split("\n"):
        if not chunks or len(chunks[-1]) + len(line) + 1 > MAX_LEN:
            chunks.append(line)
        else:
            chunks[-1] += "\n" + line
    # отправляем уже «целые» куски с корректными HTML-тегами
    for chunk in chunks:
        safe = sanitize_html(chunk)
        await bot.send_message(cid, safe, parse_mode=ParseMode.HTML)

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
    if m and m != "ANY" and m != mode.upper():
        return False
    return (lo is None or lo <= freq) and (hi is None or freq <= hi)

# ─────────────────── FSM: мастер настроек ────────────────────
class SettingsSG(StatesGroup):
    choosing  = State()  # главное меню
    mode      = State()  # выбор режима
    band_from = State()  # выбор предустановки или ручного ввода
    band_to   = State()  # ввод вручную
    rda       = State()  # ввод списка RDA

@dp.message(Command("settings"))
async def cmd_settings(m: Message, state: FSMContext):
    mode, lo, hi = await db.misc(m.chat.id)
    rda_lst = await db.get_rda(m.chat.id)
    await state.update_data(
        mode=mode or "ANY",
        band=(lo if lo is not None else 0.1, hi if hi is not None else 30.0),
        rda=rda_lst
    )
    await m.answer("🔧 Мастер настроек:", reply_markup=keyboards.settings_menu())
    await state.set_state(SettingsSG.choosing)

@dp.callback_query(F.data == "settings_back", SettingsSG.choosing)
async def cb_settings_back(cq: CallbackQuery):
    await cq.message.edit_text("🔧 Мастер настроек:", reply_markup=keyboards.settings_menu())

# 1) Режим
@dp.callback_query(F.data == "set_mode", SettingsSG.choosing)
async def cb_set_mode(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await cq.message.edit_text(
        "Выберите режим:", reply_markup=keyboards.mode_menu(data["mode"])
    )
    await state.set_state(SettingsSG.mode)

@dp.callback_query(F.data.startswith("mode|"), SettingsSG.mode)
async def cb_mode_selected(cq: CallbackQuery, state: FSMContext):
    _, m = cq.data.split("|", 1)
    await state.update_data(mode=m)
    await cq.answer(f"Режим → {m}")
    await cq.message.edit_text("🔧 Мастер настроек:", reply_markup=keyboards.settings_menu())
    await state.set_state(SettingsSG.choosing)

# 2) Диапазон
@dp.callback_query(F.data == "set_band", SettingsSG.choosing)
async def cb_set_band(cq: CallbackQuery, state: FSMContext):
    await cq.message.edit_text("Выберите диапазон:", reply_markup=keyboards.band_menu())
    await state.set_state(SettingsSG.band_from)

@dp.callback_query(F.data.startswith("band|"), SettingsSG.band_from)
async def cb_band_preset(cq: CallbackQuery, state: FSMContext):
    parts = cq.data.split("|")
    if len(parts) == 2 and parts[1] == "custom":
        await cq.message.edit_text("Введите диапазон (MHz), например: 1.8 29.0")
        await state.set_state(SettingsSG.band_to)
        return
    _, lo, hi = parts
    lo_f, hi_f = float(lo), float(hi)
    await state.update_data(band=(lo_f, hi_f))
    await cq.answer(f"Диапазон {lo}–{hi} МГц")
    await cq.message.edit_text("🔧 Мастер настроек:", reply_markup=keyboards.settings_menu())
    await state.set_state(SettingsSG.choosing)

@dp.message(SettingsSG.band_to)
async def msg_band_to(m: Message, state: FSMContext):
    parts = re.split(r"[ ,]+", m.text.strip())
    if len(parts) == 2 and all(re.fullmatch(r"\d+(\.\d+)?", p) for p in parts):
        lo, hi = sorted(map(float, parts))
        await state.update_data(band=(lo, hi))
        await m.answer(f"Диапазон {lo}–{hi} МГц установлен!")
        await m.answer("🔧 Мастер настроек:", reply_markup=keyboards.settings_menu())
        await state.set_state(SettingsSG.choosing)
    else:
        await m.reply("Неверный формат. Напишите: два числа через пробел, например: `1.8 29.0`.")

# 3) RDA-зоны
@dp.callback_query(F.data == "set_rda", SettingsSG.choosing)
async def cb_set_rda(cq: CallbackQuery, state: FSMContext):
    current = (await state.get_data())["rda"]
    await cq.message.edit_text(
        f"Текущий RDA: {', '.join(current) or '—'}\nВведите новые через запятую:"
    )
    await state.set_state(SettingsSG.rda)

@dp.message(SettingsSG.rda)
async def msg_rda(m: Message, state: FSMContext):
    items = [x.strip().upper() for x in m.text.split(",") if x.strip()]
    await state.update_data(rda=items)
    await m.answer("Список RDA обновлён!")
    await m.answer("🔧 Мастер настроек:", reply_markup=keyboards.settings_menu())
    await state.set_state(SettingsSG.choosing)

# 4) Сохранение настроек
@dp.callback_query(F.data == "set_done", SettingsSG.choosing)
async def cb_done(cq: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mode_v = data["mode"] if data["mode"] != "ANY" else None
    await db.set_mode(cq.from_user.id, mode_v)
    lo, hi = data["band"]
    await db.set_band(cq.from_user.id, lo, hi)
    await db.clear_rda(cq.from_user.id)
    if data["rda"]:
        await db.add_rda(cq.from_user.id, *data["rda"])
    await cq.message.edit_text("Все настройки сохранены ✅")
    await state.clear()

# ─────────────────── Оригинальные хендлеры ───────────────────
@dp.message(Command("start"))
async def cmd_start(m: Message, command: CommandObject | None = None):
    await db.upsert_user(m.chat.id, m.from_user.first_name, m.from_user.username)
    await m.answer(
        "👋 Бот рассылает анонсы и live-споты RDA.\nСправка — /help",
        reply_markup=keyboards.main_kb()
    )

@dp.message(Command("help"))
async def cmd_help(m: Message, command: CommandObject | None = None):
    await send_big(m.chat.id,
        "/sub_ann /unsub_ann — подписка/отписка от анонсов\n"
        "/sub_spots /unsub_spots — подписка/отписка от спотов\n"
        "/add_rda AD-01 … — добавить RDA-фильтр\n"
        "/set_mode DIGI|CW|SSB|ANY — фильтр по моде\n"
        "/set_band 1.8 29.0 | OFF — диапазон МГц\n"
        "/my_filters — текущие фильтры\n"
        "/clear_rda — убрать все RDA-фильтры\n"
        "/settings — открыть мастер настроек"
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
    await db.clear_rda(m.chat.id)
    await m.answer("✅ Все RDA-фильтры удалены.")

@dp.message(Command("my_filters"))
async def cmd_my_filters(m: Message, command: CommandObject | None = None):
    mode, lo, hi = await db.misc(m.chat.id)
    rda = await db.get_rda(m.chat.id)
    await m.answer(
        f"Mode: {mode or 'ANY'}\n"
        f"Band: {lo or 0.0}–{hi or 0.0} МГц\n"
        f"RDA: {'; '.join(sorted(rda)) if rda else 'все'}"
    )

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
        BotCommand(command="settings",      description="Мастер настроек"),
    ])
    asyncio.create_task(ann_loop())
    asyncio.create_task(ws_loop())
    log.info("🚀 Bot started")

# ─── Background loops ───
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
            if not rda or rda=="?": return
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

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
