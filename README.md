# HAM Radio Announcer Bot v2 🛰️

Телеграм-бот для рассылки анонсов экспедиционных связей RDA и live-спотов с публичного DX-кластера.

---

## 💡 Ключевые возможности

- **Асинхронный движок** на Aiogram + asyncio  
- **Анонсы** экспедиций RDA: парсинг с rdaward.ru  
- **Live-споты**: WebSocket-клиент к публичному DX-кластеру  
- **Фильтры**:  
  - по режиму (`ANY`, `CW`, `SSB`, `DIGI`)  
  - по диапазону частот (MHz)  
  - по списку RDA-кодов (районы)  
- **Пользовательские настройки** (сохраняются в SQLite):  
  - подписка на анонсы и/или споты  
  - шаблон собственных публикаций  
  - список активных RDA-фильтров  
- **Дедупликация** спотов (храним последние N, настраивается)  
- **Удобные клавиатуры** и понятный emoji-интерфейс  

---

## 🛠 Установка и запуск

1. **Клонируем репозиторий**  
   ```bash
   git clone https://github.com/deR0BI/HAM_radio_announcer.git
   cd HAM_radio_announcer
Создаём виртуальное окружение

bash
Копировать
Редактировать
python3.13 -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell
. .venv/Scripts/Activate.ps1
Устанавливаем зависимости

bash
Копировать
Редактировать
pip install -r requirements.txt
Создаём файл конфигурации
В корне проекта создайте .env:

dotenv
Копировать
Редактировать
BOT_TOKEN=<Ваш Telegram Bot API токен>
CLUSTER_WS_URL=wss://dxcluster.example.com/ws
DB_PATH=bot.sqlite
DEFAULT_FMT="🆕 {callsign} • {mode} • {freq}"
SEEN_LIMIT=10000
Запускаем бота

bash
Копировать
Редактировать
python bot.py
После старта в логе появится:

Копировать
Редактировать
🚀 Bot started
📋 Команды
Команда	Описание
/start	Приветствие и краткая справка
/help	Показать все доступные команды
/sub_ann	Подписаться на анонсы экспедиций
/unsub_ann	Отписаться от анонсов
/sub_spots	Подписаться на live-споты
/unsub_spots	Отписаться от спотов
/add_rda <RDA…>	Добавить один или несколько RDA-фильтров
/clear_rda	Очистить список RDA-фильтров
/set_mode <MODE>	Установить фильтр по режиму (CW/SSB/DIGI/ANY)
/set_band <min> <max>	Установить диапазон частот (в МГц)
/set_template <TEXT>	Задать шаблон публикации
/my_filters	Показать текущие фильтры и подписки

📂 Структура проекта
bash
Копировать
Редактировать
.
├── bot.py            # Точка входа, маршрутизация и инициализация
├── storage.py        # CRUD-функции для пользователей и фильтров (aiosqlite)
├── db.py             # Обёртка над SQLite (поддержка Python 3.13)
├── rda_parser.py     # Парсер анонсов с rdaward.ru
├── keyboards.py      # Построение Reply/Inline клавиатур
├── config.py         # Значения по умолчанию и загрузка .env
├── requirements.txt  # Список зависимостей
└── .env.example      # Пример конфигурации
🤝 Вклад и лицензия
Форкните репозиторий

Создайте ветку feature/…

Внесите изменения, добавьте тесты

Откройте Pull Request

Пожалуйста, следуйте стандарту PEP-8 и используйте Black.

Лицензия: MIT © deR0BI