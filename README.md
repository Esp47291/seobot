# SEO Bot — бот для управления отзывами (Яндекс Карты / 2ГИС)

Telegram-бот на aiogram 3: админ выдаёт задания на отзывы, пользователи отправляют скриншоты и реквизиты, выплаты только вручную через кнопку «Выплачено».

## Установка

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и заполните:

- `BOT_TOKEN` — токен от @BotFather
- `ADMIN_IDS` — ваш Telegram ID (можно узнать у @userinfobot), при нескольких админах: `123,456,789`

## Запуск

```bash
python main.py
```

При первом запуске создаётся БД SQLite в `data/seobot.db` и таблицы. Редактируйте тексты обучения в админке (/admin → Редактировать обучение).

## Деплой (systemd, Linux)

Создайте юнит `/etc/systemd/system/seobot.service`:

```ini
[Unit]
Description=SEO Bot (Yandex/2GIS reviews)
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/seobot
EnvironmentFile=/path/to/seobot/.env
ExecStart=/path/to/seobot/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Затем: `systemctl daemon-reload && systemctl enable --now seobot`.

## Структура

- `config.py` — настройки из .env
- `main.py` — точка входа, роутеры, middlewares
- `database/` — модели, репозитории, инициализация БД
- `handlers/` — пользовательские и админ-хендлеры
- `keyboards/` — клавиатуры
- `middlewares/` — сессия БД, проверка админа
- `utils/` — FSM-состояния

## Важно

- Выплаты только вручную: после перевода денег админ нажимает «Выплачено» в разделе «Подтверждённые, не оплаченные».
- Лимиты: Яндекс — 1 задание в 24 ч на пользователя, 2ГИС — 1 задание в 2 ч (настраиваются в .env).
