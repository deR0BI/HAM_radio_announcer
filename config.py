# -*- coding: utf-8 -*-
BOT_TOKEN = "7945274752:AAEAXhWIhvDOepFIkQXgba5HpU3jMy-qDWM"

CLUSTER_WS_URL = (
    "http://216.108.228.106:9000"
    "?call=R0BI"
    "&filter=all"
    "&name=Ivan"
)

DB_PATH = "bot.db"

SEEN_LIMIT = 2000              # сколько спотов держать в dedup‑кэше
CHECK_INTERVAL_SEC = 10 * 60   # опрос анонсов

DEFAULT_FMT = (
    "🆕 <b>{callsign}</b> • {mode} • {freq:.1f}kHz\n"
    "🏷 RDA: <b>{rda}</b>\n"
    "✏️ {text}\n"
    "👤 {spotter} • ⏰ {time}"
)
