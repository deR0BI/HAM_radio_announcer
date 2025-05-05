#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite‑хранилище (aiosqlite) — полностью совместимо с Python 3.13.
"""

import datetime as dt
from typing import List, Tuple
import aiosqlite, config

def _conn():
    # Подключение с autocommit
    return aiosqlite.connect(
        config.DB_PATH,
        timeout=30,
        isolation_level=None
    )

SCHEMA = f"""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users(
  chat_id     INTEGER PRIMARY KEY,
  first_name  TEXT,
  username    TEXT,
  fmt         TEXT DEFAULT '{config.DEFAULT_FMT.replace("'","''")}',
  created_at  TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS subscriptions(
  chat_id INTEGER,
  kind    TEXT,
  PRIMARY KEY(chat_id, kind)
);
CREATE TABLE IF NOT EXISTS filters_rda(
  chat_id INTEGER,
  rda     TEXT,
  PRIMARY KEY(chat_id, rda)
);
CREATE TABLE IF NOT EXISTS filters_misc(
  chat_id INTEGER PRIMARY KEY,
  mode  TEXT  DEFAULT 'ANY',
  f_min REAL  DEFAULT 0,
  f_max REAL  DEFAULT 99999
);
CREATE TABLE IF NOT EXISTS seen_spots(
  hash TEXT PRIMARY KEY,
  ts   INTEGER
);
"""

async def init_db():
    """Создает таблицы при старте"""
    async with _conn() as db:
        await db.executescript(SCHEMA)

# ───── USERS ─────
async def upsert_user(cid: int, first: str, uname: str | None):
    async with _conn() as db:
        await db.execute(
            "INSERT INTO users(chat_id,first_name,username) VALUES(?,?,?) "
            "ON CONFLICT(chat_id) DO UPDATE SET "
            "first_name=excluded.first_name, username=excluded.username",
            (cid, first, uname)
        )

async def set_template(cid: int, tmpl: str):
    async with _conn() as db:
        await db.execute(
            "UPDATE users SET fmt=? WHERE chat_id=?",
            (tmpl, cid)
        )

async def get_template(cid: int) -> str:
    async with _conn() as db:
        cur = await db.execute(
            "SELECT fmt FROM users WHERE chat_id=?",
            (cid,)
        )
        row = await cur.fetchone()
        return row[0] if row else config.DEFAULT_FMT

# ───── SUBSCRIPTIONS ─────
async def change_sub(cid: int, kind: str, on: bool):
    async with _conn() as db:
        if on:
            await db.execute(
                "INSERT OR IGNORE INTO subscriptions(chat_id,kind) VALUES(?,?)",
                (cid, kind)
            )
        else:
            await db.execute(
                "DELETE FROM subscriptions WHERE chat_id=? AND kind=?",
                (cid, kind)
            )

async def subscribers(kind: str) -> List[int]:
    async with _conn() as db:
        cur = await db.execute(
            "SELECT chat_id FROM subscriptions WHERE kind=?",
            (kind,)
        )
        return [r[0] for r in await cur.fetchall()]

# ───── RDA FILTER ─────
async def add_rda(cid: int, *codes: str) -> List[str]:
    if not codes:
        return []
    async with _conn() as db:
        await db.executemany(
            "INSERT OR IGNORE INTO filters_rda(chat_id,rda) VALUES(?,?)",
            [(cid, c) for c in codes]
        )
        cur = await db.execute(
            "SELECT rda FROM filters_rda WHERE chat_id=?",
            (cid,)
        )
        return [r[0] for r in await cur.fetchall()]

async def get_rda(cid: int) -> List[str]:
    async with _conn() as db:
        cur = await db.execute(
            "SELECT rda FROM filters_rda WHERE chat_id=?",
            (cid,)
        )
        return [r[0] for r in await cur.fetchall()]

async def clear_rda(cid: int):
    """Очищает все RDA-фильтры пользователя"""
    async with _conn() as db:
        await db.execute(
            "DELETE FROM filters_rda WHERE chat_id=?",
            (cid,)
        )

# ───── MODE/BAND FILTER ─────
async def _ensure_misc(db, cid: int):
    await db.execute(
        "INSERT OR IGNORE INTO filters_misc(chat_id) VALUES(?)",
        (cid,)
    )

async def set_mode(cid: int, mode: str | None):
    async with _conn() as db:
        await _ensure_misc(db, cid)
        await db.execute(
            "UPDATE filters_misc SET mode=? WHERE chat_id=?",
            ("ANY" if mode is None else mode, cid)
        )

async def set_band(cid: int, lo: float | None, hi: float | None):
    async with _conn() as db:
        await _ensure_misc(db, cid)
        await db.execute(
            "UPDATE filters_misc SET f_min=?, f_max=? WHERE chat_id=?",
            (
                0.0 if lo is None else lo,
                99999.0 if hi is None else hi,
                cid
            )
        )

async def misc(cid: int) -> Tuple[str, float, float]:
    async with _conn() as db:
        cur = await db.execute(
            "SELECT mode,f_min,f_max FROM filters_misc WHERE chat_id=?",
            (cid,)
        )
        row = await cur.fetchone()
        return ("ANY", 0.0, 99999.0) if row is None else row

# ───── DE‑DUPLICATION ─────
async def is_new(hsh: str) -> bool:
    now = int(dt.datetime.utcnow().timestamp())
    async with _conn() as db:
        cur = await db.execute(
            "SELECT 1 FROM seen_spots WHERE hash=?",
            (hsh,)
        )
        if await cur.fetchone():
            return False
        await db.execute(
            "INSERT INTO seen_spots(hash,ts) VALUES(?,?)",
            (hsh, now)
        )
        # очищаем старое
        cur = await db.execute("SELECT COUNT(*) FROM seen_spots")
        cnt = (await cur.fetchone())[0]
        if cnt > config.SEEN_LIMIT:
            delta = cnt - config.SEEN_LIMIT
            await db.execute(
                "DELETE FROM seen_spots "
                "WHERE hash IN (SELECT hash FROM seen_spots ORDER BY ts LIMIT ?)",
                (delta,)
            )
        return True
