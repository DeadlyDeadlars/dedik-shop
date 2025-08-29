import asyncio
from aiogram import Bot, Dispatcher
from aiohttp import web
from .config import load_settings
from .db import Database
from .models import Tariffs, Users, Orders
from .cryptobot import CryptoBot
from .handlers import setup_handlers
from .webhook import create_app


async def main():
    settings = load_settings()
    if not settings.telegram_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing")

    db = Database(settings.database_url or "sqlite:///shop.sqlite3")
    await db.connect()
    await db.ensure_schema()

    tariffs = Tariffs(db)
    users = Users(db)
    orders = Orders(db)
    cryptobot = CryptoBot(settings.cryptobot_token) if settings.cryptobot_token else None

    bot = Bot(token=settings.telegram_token)
    dp = Dispatcher()

    services = {
        "db": db,
        "tariffs": tariffs,
        "users": users,
        "orders": orders,
        "cryptobot": cryptobot,
        "admin_ids": settings.admin_ids,
        "rub_usdt_rate": settings.rub_usdt_rate,
    }
    setup_handlers(dp, services)

    # Start both polling and aiohttp webhook server for CryptoBot
    app = create_app(bot, orders, settings.admin_ids, settings.webhook_secret)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=int(__import__('os').getenv('PORT', '8080')))
    await site.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


