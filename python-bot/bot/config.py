from dataclasses import dataclass
import os


@dataclass
class Settings:
    telegram_token: str
    database_url: str
    cryptobot_token: str
    admin_ids: list[int]
    rub_usdt_rate: float
    webhook_secret: str | None


def load_settings() -> Settings:
    # dotenv optional
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    admin_ids_env = os.getenv("ADMIN_IDS", "")
    admin_ids: list[int] = []
    if admin_ids_env:
        admin_ids = [int(x.strip()) for x in admin_ids_env.split(",") if x.strip()]

    return Settings(
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        database_url=os.getenv("DATABASE_URL", ""),
        cryptobot_token=os.getenv("CRYPTOBOT_TOKEN", ""),
        admin_ids=admin_ids,
        rub_usdt_rate=float(os.getenv("RUB_USDT_RATE", "100")),
        webhook_secret=os.getenv("CRYPTOBOT_WEBHOOK_SECRET"),
    )


