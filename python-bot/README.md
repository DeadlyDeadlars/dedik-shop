Python Telegram Shop Bot (Aiogram 3.x)

Quick start

1) Create and fill .env (copy .env.example):

   TELEGRAM_BOT_TOKEN=...
   # PostgreSQL пример
   # DATABASE_URL=postgresql://user:pass@localhost:5432/db
   # SQLite пример
   DATABASE_URL=sqlite:///shop.sqlite3
   CRYPTOBOT_TOKEN=...
   CRYPTOBOT_WEBHOOK_SECRET=...  # общий секрет для подписи вебхука
   ADMIN_IDS=123456789,987654321
   RUB_USDT_RATE=100  # необязательный фолбэк; по умолчанию бот берет курс из CryptoBot

2) Install deps:

   pip install -r requirements.txt

3) Run (бот запустит polling и локальный aiohttp сервер для вебхука CryptoBot на :8080/cryptobot-webhook):

   python -m bot.main


