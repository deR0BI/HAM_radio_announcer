# RDA‑Announcer Bot v2

⚡ **Что нового**

* Полностью асинхронная архитектура — ни единого блокирующего вызова.
* SQLite + Pydantic — настройки/данные сохраняются, конфиг через `.env`.
* Автоматическое подключение к публичному DX‑кластеру — RDA‑споты прилетают live.
* Красочный emoji‑UI — читаемо даже на мобильном.

## Быстрый старт

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
echo "BOT_TOKEN=123456:ABCDEF" > .env          # ← ваш токен
python -m rda_announcer.bot
