#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Async‑ORM (SQLAlchemy 2) + SQLite/PostgreSQL
"""

import datetime as dt
from typing import Optional

from sqlalchemy import (
    Column, DateTime, Enum, Float, Integer, String,
    ForeignKey, select, delete, func, update, Text
)
from sqlalchemy.ext.asyncio import (
    AsyncSession, async_sessionmaker, create_async_engine
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import config

# ────────── подключение ──────────
engine = create_async_engine(config.DB_URL, echo=False, pool_size=10)
Session: async_sessionmaker[AsyncSession] = async_sessionmaker(bind=engine)

class Base(DeclarativeBase): pass

# ────────── модели ──────────
class User(Base):
    __tablename__ = "users"
    chat_id:    Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(64))
    username:   Mapped[str | None] = mapped_column(String(64))
    fmt:        Mapped[str] = mapped_column(Text, default=config.DEFAULT_FMT)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=dt.datetime.utcnow
    )

class Subscription(Base):
    __tablename__ = "subscriptions"
    chat_id: Mapped[int] = mapped_column(ForeignKey(User.chat_id), primary_key=True)
    kind:    Mapped[str] = mapped_column(
        Enum("ann", "spot", name="sub_kind"), primary_key=True
    )

class FilterRDA(Base):
    __tablename__ = "filters_rda"
    chat_id:  Mapped[int] = mapped_column(ForeignKey(User.chat_id), primary_key=True)
    rda:      Mapped[str] = mapped_column(String(6), primary_key=True)

class FilterMisc(Base):
    __tablename__ = "filters_misc"
    chat_id: Mapped[int] = mapped_column(ForeignKey(User.chat_id), primary_key=True)
    mode:    Mapped[str] = mapped_column(String(8), default="ANY")   # DIGI / CW / ...
    f_min:   Mapped[float] = mapped_column(Float, default=0.0)
    f_max:   Mapped[float] = mapped_column(Float, default=99999.0)

class SeenSpot(Base):
    __tablename__ = "seen_spots"
    hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    ts:   Mapped[int] = mapped_column(Integer)

# ────────── инициализация ──────────
async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# ────────── USERS ──────────
async def upsert_user(cid: int, first: str, uname: str | None) -> None:
    async with Session() as s:
        await s.merge(User(chat_id=cid, first_name=first, username=uname))
        await s.commit()

async def set_template(cid: int, tmpl: str) -> None:
    async with Session() as s:
        await s.execute(
            update(User).where(User.chat_id == cid).values(fmt=tmpl)
        )
        await s.commit()

async def get_template(cid: int) -> str:
    async with Session() as s:
        res = await s.scalar(select(User.fmt).where(User.chat_id == cid))
        return res or config.DEFAULT_FMT

# ────────── SUBSCRIPTIONS ──────────
async def change_sub(cid: int, kind: str, on: bool) -> None:
    async with Session() as s:
        if on:
            s.add(Subscription(chat_id=cid, kind=kind))
        else:
            await s.execute(
                delete(Subscription).where(
                    Subscription.chat_id == cid, Subscription.kind == kind
                )
            )
        await s.commit()

async def subscribers(kind: str) -> list[int]:
    async with Session() as s:
        rows = await s.scalars(
            select(Subscription.chat_id).where(Subscription.kind == kind)
        )
        return rows.all()

# ────────── RDA‑FILTER ──────────
async def add_rda(cid: int, *codes: str) -> list[str]:
    async with Session() as s:
        have = (
            await s.scalars(
                select(FilterRDA.rda).where(FilterRDA.chat_id == cid)
            )
        ).all()
        new = [c for c in codes if c not in have]
        s.add_all([FilterRDA(chat_id=cid, rda=c) for c in new])
        await s.commit()
        return new

async def get_rda(cid: int) -> list[str]:
    async with Session() as s:
        rows = await s.scalars(
            select(FilterRDA.rda).where(FilterRDA.chat_id == cid)
        )
        return rows.all()

# ────────── MODE/BAND FILTER ──────────
async def set_mode(cid: int, mode: str | None) -> None:
    async with Session() as s:
        await _ensure_misc(s, cid)
        await s.execute(
            update(FilterMisc).where(FilterMisc.chat_id == cid).values(
                mode="ANY" if mode is None else mode.upper()
            )
        )
        await s.commit()

async def set_band(cid: int, lo: float | None, hi: float | None) -> None:
    async with Session() as s:
        await _ensure_misc(s, cid)
        await s.execute(
            update(FilterMisc).where(FilterMisc.chat_id == cid).values(
                f_min=0.0 if lo is None else lo,
                f_max=99999.0 if hi is None else hi,
            )
        )
        await s.commit()

async def misc(cid: int) -> FilterMisc:
    async with Session() as s:
        row = await s.get(FilterMisc, cid)
        return row or FilterMisc(chat_id=cid)

async def _ensure_misc(s: AsyncSession, cid: int) -> None:
    if not await s.get(FilterMisc, cid):
        s.add(FilterMisc(chat_id=cid))
        await s.flush()

# ────────── DEDUPLICATION ──────────
async def is_new(h: str) -> bool:
    async with Session() as s:
        if await s.get(SeenSpot, h):
            return False
        # trim
        cnt = await s.scalar(select(func.count()).select_from(SeenSpot))
        if cnt and cnt >= config.SEEN_LIMIT:
            oldest = await s.scalars(
                select(SeenSpot).order_by(SeenSpot.ts).limit(cnt - config.SEEN_LIMIT + 1)
            )
            for row in oldest: await s.delete(row)
        s.add(SeenSpot(hash=h, ts=int(dt.datetime.utcnow().timestamp())))
        await s.commit()
        return True
